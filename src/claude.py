#!/usr/bin/env python3
"""Claude API 호출부 — 대본 전용.

왜 대본만 Claude 인가
    지침서 0번: "대본 생성 프롬프트가 이 사업의 유일한 핵심 자산이다."
    이 사업은 대본 품질이 전부다. 긴 한국어 감정 서사, 절제된 대사, 인물의 말투 —
    여기서 갈린다.

    그림과 목소리는 Claude 가 못 만든다. 그건 Gemini 가 한다.
    그래서 **대본·심사·채점은 Claude, 이미지·음성은 Gemini** 로 나눈다.

    CLAUDE_API_KEY 가 없으면 자동으로 Gemini 로 넘어간다. 파이프라인이 멈추지 않는다.

llm.Gemini 와 같은 모양(`.json()`)을 갖는다
    script.py 와 gate.py 가 어느 쪽을 쓰든 코드를 바꾸지 않아도 되게 하기 위해서다.
"""

import json
import os
import re
import time
import urllib.error
import urllib.request

BASE = "https://api.anthropic.com/v1"
VERSION = "2023-06-01"
TIMEOUT = 600
RETRIES = 4
BACKOFF = [5, 15, 40]


class ClaudeError(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    """한 실행에서 허용한 호출 수를 넘었다. 과금 폭발 방지 장치."""


def _req(path, key, method="GET", body=None, timeout=TIMEOUT):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"{BASE}/{path}", data=data, method=method, headers={
        "x-api-key": key,
        "anthropic-version": VERSION,
        "content-type": "application/json",
        "user-agent": "verdict-theater/1.0",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


class Claude:
    def __init__(self, api_key=None, max_calls=24):
        self.key = (api_key or os.environ.get("CLAUDE_API_KEY", "")
                    or os.environ.get("ANTHROPIC_API_KEY", "")).strip()
        if not self.key:
            raise ClaudeError(
                "CLAUDE_API_KEY 가 없다.\n"
                "  저장소 → Settings → Secrets and variables → Actions\n"
                "  → New repository secret → 이름 CLAUDE_API_KEY"
            )
        self.max_calls = max_calls
        self.calls = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self._models = None

    # ── 모델 고르기 ──────────────────────────────────────
    def available(self):
        """모델 이름을 코드에 박지 않는다. Gemini 쪽과 같은 원칙이다."""
        if self._models is None:
            try:
                data = _req("models?limit=100", self.key, timeout=60)
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:300]
                raise ClaudeError(
                    f"모델 목록을 받지 못했다 (HTTP {e.code}). 키가 올바른지 확인하라.\n{body}")
            self._models = [m["id"] for m in data.get("data", [])]
        return self._models

    def pick(self, tier="pro"):
        """tier='pro' 대본 생성·소재 심사 / tier='flash' 채점·쇼츠 (더 싼 급)"""
        override = os.environ.get(f"CLAUDE_MODEL_{tier.upper()}") or os.environ.get("CLAUDE_MODEL")
        if override:
            return override.strip()

        models = self.available()
        if not models:
            raise ClaudeError("쓸 수 있는 모델이 하나도 없다.")

        def ver(name):
            m = re.search(r"-(\d+)(?:[-.](\d+))?", name)
            return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)

        want = "opus" if tier == "pro" else "sonnet"
        cands = [m for m in models if want in m]
        if not cands:
            cands = [m for m in models if ("sonnet" if tier == "pro" else "opus") in m]
        if not cands:
            cands = models
        cands.sort(key=lambda n: (ver(n), -len(n)), reverse=True)
        return cands[0]

    # ── 호출 ────────────────────────────────────────────
    def json(self, prompt, tier="pro", max_output_tokens=32768, temperature=0.9, label=""):
        """프롬프트를 보내고 JSON 하나를 받는다.

        Claude 에는 'JSON 만 내라'는 설정이 없다. 대신 응답을 `{` 로 시작하게 미리 채워두면
        모델이 그 뒤를 이어 쓰므로 설명문이 섞이지 않는다."""
        if self.calls >= self.max_calls:
            raise BudgetExceeded(
                f"이번 실행에서 이미 {self.calls}회 호출했다. 상한 {self.max_calls}회. "
                "무한 루프로 인한 과금 폭발을 막는 장치다."
            )
        model = self.pick(tier)
        payload = {
            "model": model,
            "max_tokens": max_output_tokens,
            "temperature": min(1.0, temperature),
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": "{"},     # JSON 으로 시작하도록 못 박는다
            ],
        }

        last = None
        for attempt in range(RETRIES):
            try:
                res = _req("messages", self.key, method="POST", body=payload)
                self.calls += 1
                u = res.get("usage", {})
                self.tokens_in += u.get("input_tokens", 0)
                self.tokens_out += u.get("output_tokens", 0)

                if res.get("stop_reason") == "max_tokens":
                    raise ClaudeError("출력이 길이 상한에서 잘렸다. max_output_tokens 를 늘려야 한다.")
                text = "".join(p.get("text", "") for p in res.get("content", [])
                               if p.get("type") == "text")
                if not text.strip():
                    raise ClaudeError(f"본문이 비었다 (stop_reason={res.get('stop_reason')})")
                raw = "{" + text                      # 미리 채운 `{` 를 되돌린다
                raw = raw.strip()
                if raw.startswith("```"):
                    raw = re.sub(r"^```[a-zA-Z]*\s*", "", raw)
                    raw = re.sub(r"\s*```$", "", raw)
                try:
                    return json.loads(raw)
                except json.JSONDecodeError as e:
                    raise ClaudeError(f"JSON 형식이 아니다: {e}\n앞부분: {raw[:200]}")

            except urllib.error.HTTPError as e:
                last = e
                if e.code in (400, 401, 403, 404):
                    body = e.read().decode("utf-8", "replace")[:400]
                    raise ClaudeError(f"호출 실패 (HTTP {e.code}) — 재시도해도 소용없다.\n{body}")
                if attempt < RETRIES - 1:
                    w = BACKOFF[attempt]
                    print(f"    (재시도 {attempt + 1}/{RETRIES - 1} — HTTP {e.code}, {w}초 대기)")
                    time.sleep(w)
            except (urllib.error.URLError, TimeoutError, ClaudeError) as e:
                last = e
                if attempt < RETRIES - 1:
                    w = BACKOFF[attempt]
                    print(f"    (재시도 {attempt + 1}/{RETRIES - 1} — {type(e).__name__}, {w}초 대기)")
                    time.sleep(w)
        self.calls += 1
        raise ClaudeError(f"{label or '호출'} 최종 실패: {last}")

    def report(self):
        return (f"모델 호출 {self.calls}회 · 입력 {self.tokens_in:,} 토큰 "
                f"· 출력 {self.tokens_out:,} 토큰")


# ── 어느 쪽을 쓸지 고르기 ────────────────────────────────
def writer(max_calls=24, prefer=None):
    """대본·심사·채점에 쓸 모델을 고른다.

    고르는 순서
      1. VT_WRITER 환경변수 (claude / gemini) — 워크플로 버튼에서 넘어온다
      2. CLAUDE_API_KEY 가 있으면 Claude
      3. 없으면 Gemini

    글은 Claude, 그림과 소리는 Gemini. 둘 다 없으면 여기서 멈춘다."""
    import llm

    want = (prefer or os.environ.get("VT_WRITER", "")).strip().lower()
    has_claude = bool((os.environ.get("CLAUDE_API_KEY", "")
                       or os.environ.get("ANTHROPIC_API_KEY", "")).strip())
    has_gemini = bool(os.environ.get("GEMINI_API_KEY", "").strip())

    if want == "gemini" or (not want and not has_claude):
        if not has_gemini:
            raise llm.LLMError(
                "대본을 쓸 열쇠가 하나도 없다.\n"
                "  CLAUDE_API_KEY 또는 GEMINI_API_KEY 를 Secrets 에 등록하라."
            )
        return llm.Gemini(max_calls=max_calls), "gemini"

    if not has_claude:
        raise ClaudeError("CLAUDE_API_KEY 가 없는데 claude 를 쓰라고 지정됐다.")
    return Claude(max_calls=max_calls), "claude"


if __name__ == "__main__":
    c = Claude()
    print("쓸 수 있는 모델:", len(c.available()), "개")
    print("  대본용(pro)  :", c.pick("pro"))
    print("  채점용(flash):", c.pick("flash"))
