#!/usr/bin/env python3
"""Gemini API 호출부.

설계에서 신경 쓴 것

1. **모델 이름을 코드에 박지 않는다.**
   Gemini 모델 이름은 자주 바뀐다(gemini-1.5-pro → 2.0 → 2.5 …).
   이름을 박아두면 어느 날 갑자기 파이프라인이 죽고, 운영자는 원인을 알 수 없다.
   그래서 실행할 때마다 **API에 "지금 쓸 수 있는 모델 목록"을 물어보고 고른다.**
   GEMINI_MODEL 환경변수가 있으면 그걸 우선한다.

2. **비용 상한을 코드가 강제한다.**
   지침서 11번: "버그로 무한 루프가 돌면 과금이 폭발한다."
   한 번 실행에서 쓸 수 있는 호출 수를 미리 정하고, 넘으면 예외를 던진다.

3. **JSON만 받는다.**
   모든 프롬프트가 "JSON 하나만 출력"을 요구한다. responseMimeType 을 지정해
   모델이 설명문을 섞지 못하게 막고, 그래도 섞이면 코드가 걷어낸다.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request

BASE = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT = 300
RETRIES = 4
BACKOFF = [5, 15, 40]


class LLMError(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    """한 실행에서 허용한 호출 수를 넘었다. 과금 폭발 방지 장치."""


def _post(url, payload, timeout=TIMEOUT):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "User-Agent": "verdict-theater/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "verdict-theater/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _strip_fence(s):
    """모델이 ```json ... ``` 로 감싸 보내는 경우를 걷어낸다."""
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


class Gemini:
    def __init__(self, api_key=None, max_calls=12):
        self.key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        if not self.key:
            raise LLMError(
                "GEMINI_API_KEY 가 없다.\n"
                "  저장소 → Settings → Secrets and variables → Actions\n"
                "  → New repository secret → 이름 GEMINI_API_KEY\n"
                "  값은 aistudio.google.com 에서 발급한 키다."
            )
        self.max_calls = max_calls
        self.calls = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self._models = None

    # ── 모델 고르기 ──────────────────────────────────────
    def available(self):
        if self._models is None:
            try:
                data = _get(f"{BASE}/models?key={self.key}&pageSize=200")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:300]
                raise LLMError(f"모델 목록을 받지 못했다 (HTTP {e.code}). 키가 올바른지 확인하라.\n{body}")
            self._models = [
                m["name"].split("/", 1)[-1]
                for m in data.get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", [])
            ]
        return self._models

    def pick(self, tier="pro"):
        """지금 쓸 수 있는 모델 중에서 고른다.

        tier='pro'   품질 우선 — 대본 생성, 드라마성 평가
        tier='flash' 속도·비용 우선 — 대본 채점, 쇼츠
        """
        override = os.environ.get(f"GEMINI_MODEL_{tier.upper()}") or os.environ.get("GEMINI_MODEL")
        if override:
            return override.strip()

        models = self.available()
        if not models:
            raise LLMError("쓸 수 있는 모델이 하나도 없다.")

        def ver(name):
            m = re.search(r"gemini-(\d+)(?:\.(\d+))?", name)
            return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)

        want = "pro" if tier == "pro" else "flash"
        other = "flash" if tier == "pro" else "pro"

        # 실험판·미리보기·특수 용도는 뒤로 민다
        def bad(n):
            return any(w in n for w in ("exp", "thinking", "image", "tts", "embedding",
                                        "vision", "learnlm", "live", "native-audio"))

        cands = [m for m in models if want in m and not bad(m)]
        if not cands:
            cands = [m for m in models if other in m and not bad(m)]
        if not cands:
            cands = [m for m in models if not bad(m)] or models

        # 버전이 높고, 이름이 짧은 것(별칭)을 선호
        cands.sort(key=lambda n: (ver(n), -len(n)), reverse=True)
        return cands[0]

    # ── 호출 ────────────────────────────────────────────
    def json(self, prompt, tier="pro", max_output_tokens=32768, temperature=0.9, label=""):
        """프롬프트를 보내고 JSON 하나를 받는다."""
        if self.calls >= self.max_calls:
            raise BudgetExceeded(
                f"이번 실행에서 이미 {self.calls}회 호출했다. 상한 {self.max_calls}회. "
                "무한 루프로 인한 과금 폭발을 막는 장치다."
            )
        model = self.pick(tier)
        url = f"{BASE}/models/{model}:generateContent?key={self.key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": "application/json",
            },
        }

        last = None
        for attempt in range(RETRIES):
            try:
                res = _post(url, payload)
                self.calls += 1
                u = res.get("usageMetadata", {})
                self.tokens_in += u.get("promptTokenCount", 0)
                self.tokens_out += u.get("candidatesTokenCount", 0)

                cands = res.get("candidates") or []
                if not cands:
                    fb = res.get("promptFeedback", {})
                    raise LLMError(f"응답이 비었다. 차단 사유: {fb.get('blockReason', '알 수 없음')}")
                c = cands[0]
                if c.get("finishReason") == "MAX_TOKENS":
                    raise LLMError("출력이 길이 상한에서 잘렸다. max_output_tokens 를 늘려야 한다.")
                parts = c.get("content", {}).get("parts") or []
                text = "".join(p.get("text", "") for p in parts)
                if not text.strip():
                    raise LLMError(f"본문이 비었다 (finishReason={c.get('finishReason')})")
                try:
                    return json.loads(_strip_fence(text))
                except json.JSONDecodeError as e:
                    raise LLMError(f"JSON 형식이 아니다: {e}\n앞부분: {text[:200]}")

            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as e:
                last = e
                code = getattr(e, "code", None)
                if code in (400, 401, 403, 404):          # 되풀이해도 소용없는 오류
                    body = e.read().decode("utf-8", "replace")[:400] if hasattr(e, "read") else ""
                    raise LLMError(f"호출 실패 (HTTP {code}) — 재시도해도 소용없다.\n{body}")
                if attempt < RETRIES - 1:
                    w = BACKOFF[attempt]
                    print(f"    (재시도 {attempt + 1}/{RETRIES - 1} — {type(e).__name__} {code or ''}, {w}초 대기)")
                    time.sleep(w)
            except LLMError as e:
                last = e
                if attempt < RETRIES - 1:
                    w = BACKOFF[attempt]
                    print(f"    (재시도 {attempt + 1}/{RETRIES - 1} — {e}, {w}초 대기)")
                    time.sleep(w)
        self.calls += 1
        raise LLMError(f"{label or '호출'} 최종 실패: {last}")

    def report(self):
        return (f"모델 호출 {self.calls}회 · 입력 {self.tokens_in:,} 토큰 "
                f"· 출력 {self.tokens_out:,} 토큰")


if __name__ == "__main__":
    g = Gemini()
    print("쓸 수 있는 모델:", len(g.available()), "개")
    print("  품질용(pro)  :", g.pick("pro"))
    print("  저가용(flash):", g.pick("flash"))
