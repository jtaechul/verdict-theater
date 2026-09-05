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

import io
import json
import os
import re
import time
import urllib.error
import urllib.request

import cost                       # 값을 원(₩)으로 적어 주는 표

BASE = "https://generativelanguage.googleapis.com/v1beta"
TIMEOUT = 300
RETRIES = 4
BACKOFF = [5, 15, 40]


class LLMError(RuntimeError):
    pass


class TooLong(LLMError):
    """출력이 길이 상한에서 잘렸다.

    ⚠️ 2026-08-20 — 이것을 **같은 상한으로 3번 더** 불렀다. 잘릴 것이 뻔한데
       15분 동안 3회분 값만 나갔다. 되풀이해도 소용없는 오류이므로 갈래를
       나눠 바로 멈춘다. 부르는 쪽이 max_output_tokens 를 올려야 한다."""


class BudgetExceeded(RuntimeError):
    """한 실행에서 허용한 호출 수를 넘었다. 과금 폭발 방지 장치."""


def _detail(e):
    """구글이 **왜** 거절했는지를 오류 문구에 붙인다.

    ⚠️ 2026-08-13 — 이게 없어서 오래 헤맸다. urllib 는 실패하면
       "HTTP Error 429: Too Many Requests" 한 줄만 남기고 **까닭이 적힌 본문을
       버린다.** 그런데 진짜 정보는 전부 그 본문에 있다 —
         · 429 가 '분당 제한'인지 '하루 한도 0'인지
         · 400 이면 어떤 값이 틀렸고 받아 주는 값은 무엇인지
       (실제로 aspectRatio 에 받아 주지 않는 값을 넣고도 그 사실을 몰랐다.)

    ⚠️ 열쇠는 절대 딸려 나가지 않게 한다 — 주소(url)에 열쇠가 들어 있으므로
       주소는 손대지 않고 **본문만** 쓰고, 혹시 몰라 key=... 는 지운다."""
    try:
        raw = e.read().decode("utf-8", "replace")
    except Exception:
        return e
    raw = re.sub(r"key=[\w\-]+", "key=***", raw)
    try:
        body = json.loads(raw).get("error", {}).get("message", "") or raw
    except Exception:
        body = raw
    body = body[:800].strip()
    # ⚠️ 본문을 한 번 읽으면 사라진다. 그런데 이 오류를 받아서 **다시 본문을 읽는**
    #    자리가 llm.py 안에 둘 있다(available·_call). 그래서 읽은 것을 그대로 다시
    #    끼워 넣어, 예전처럼 e.read() 해도 똑같이 나오게 한다.
    return urllib.error.HTTPError(
        "(주소 감춤)", e.code, f"{e.reason} — {body}" if body else str(e.reason),
        e.headers, io.BytesIO(raw.encode("utf-8")))


def _post(url, payload, timeout=TIMEOUT):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "User-Agent": "verdict-theater/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise _detail(e) from None


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "verdict-theater/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise _detail(e) from None


def _strip_fence(s):
    """모델이 ```json ... ``` 로 감싸 보내는 경우를 걷어낸다."""
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


class Gemini:
    def __init__(self, api_key=None, max_calls=12, max_krw=None):
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
        self.last_model = ""   # 마지막으로 실제 쓴 모델 (값 계산에 쓴다)
        # 단계별로 얼마 나갔는지 따로 센다 (claude.py 와 같은 방식).
        # 이름 → [횟수, 원]
        self.by_stage = {}
        self.max_krw = max_krw if max_krw is not None else cost.RUN_KRW
        self._models = None
        self._limits = {}

    # ── 모델 고르기 ──────────────────────────────────────
    def available(self):
        if self._models is None:
            try:
                data = _get(f"{BASE}/models?key={self.key}&pageSize=200")
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:300]
                raise LLMError(f"모델 목록을 받지 못했다 (HTTP {e.code}). 키가 올바른지 확인하라.\n{body}")
            self._models = []
            for m in data.get("models", []):
                if "generateContent" not in m.get("supportedGenerationMethods", []):
                    continue
                name = m["name"].split("/", 1)[-1]
                self._models.append(name)
                # 모델마다 한 번에 낼 수 있는 출력 길이가 다르다. 넘겨 요청하면
                # 중간에서 잘린 JSON 이 와서 통째로 버려야 한다. 미리 받아 맞춘다.
                self._limits[name] = m.get("outputTokenLimit") or 0
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
    def json(self, prompt, tier="pro", max_output_tokens=32768, temperature=0.9,
             label="", cache_prefix="", effort=""):
        """프롬프트를 보내고 JSON 하나를 받는다.

        effort — 얼마나 깊이 생각할지. Claude 쪽과 **부르는 모양을 맞추기 위해** 받는다.
          Gemini 는 이 이름의 설정이 없어 지금은 쓰지 않는다. 받아만 두면
          부르는 쪽(script.py)이 어느 쪽을 쓰든 코드를 바꿀 필요가 없다 —
          이 자리가 없으면 Gemini 로 돌 때 통째로 죽는다.

        cache_prefix — Claude 쪽과 서명을 맞추기 위한 것. Gemini 는 반복되는 앞부분을
        알아서 재사용하므로 따로 표시할 게 없고, 그냥 앞에 붙여 보내면 된다."""
        prompt = cache_prefix + prompt
        # ⭐ 돈으로 막는다. 횟수로는 못 막는다 —
        #    호출 하나의 값이 프롬프트 크기와 모델에 따라 10원~2,000원까지 벌어져
        #    같은 '24회 상한' 이 208원일 수도 13,230원일 수도 있다(실측).
        #    여기서 멈추면 지금까지 만든 것은 건져내는 길로 빠진다.
        self._check_money()
        if self.calls >= self.max_calls:
            raise BudgetExceeded(
                f"이번 실행에서 이미 {self.calls}회 호출했다. 상한 {self.max_calls}회. "
                "무한 루프로 인한 과금 폭발을 막는 장치다."
            )
        model = self.pick(tier)
        cap = self._limits.get(model) or 0
        if cap and max_output_tokens > cap:
            print(f"    (출력 한도 조정: {max_output_tokens:,} → {cap:,} · {model})")
            max_output_tokens = cap
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
                self.last_model = res.get("modelVersion") or model
                u = res.get("usageMetadata", {})
                self.tokens_in += u.get("promptTokenCount", 0)
                # ⚠️⚠️ 2026-09-05 — **생각한 만큼(thinking)을 안 세고 있었다.**
                #    제미나이는 생각한 토큰도 나가는 값에 넣는데, 여기서는
                #    candidatesTokenCount 만 셌다. 그래서 화면에 56원이라고
                #    찍혔지만 실제로는 더 나갔다. 값을 적게 세면 한도(RUN_KRW)가
                #    막는 시늉만 하게 된다.
                self.tokens_out += (u.get("candidatesTokenCount", 0)
                                    + u.get("thoughtsTokenCount", 0))
                try:
                    one = cost.krw(self.last_model,
                                   u.get("promptTokenCount", 0),
                                   u.get("candidatesTokenCount", 0)
                                   + u.get("thoughtsTokenCount", 0)) or 0.0
                    row = self.by_stage.setdefault(label or "이름 없음", [0, 0.0])
                    row[0] += 1
                    row[1] += one
                except Exception:
                    pass

                cands = res.get("candidates") or []
                if not cands:
                    fb = res.get("promptFeedback", {})
                    raise LLMError(f"응답이 비었다. 차단 사유: {fb.get('blockReason', '알 수 없음')}")
                c = cands[0]
                if c.get("finishReason") == "MAX_TOKENS":
                    raise TooLong("출력이 길이 상한에서 잘렸다. "
                                  f"max_output_tokens({max_output_tokens:,}) 를 늘려야 한다.")
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
                # 잘린 것은 같은 상한으로 다시 불러도 똑같이 잘린다 — 값만 곱절
                if isinstance(e, TooLong):
                    raise
                if attempt < RETRIES - 1:
                    w = BACKOFF[attempt]
                    print(f"    (재시도 {attempt + 1}/{RETRIES - 1} — {e}, {w}초 대기)")
                    time.sleep(w)
        self.calls += 1
        raise LLMError(f"{label or '호출'} 최종 실패: {last}")


    # ── 돈 계산 · 한도 ──────────────────────────────────
    def spent_krw(self):
        """이번 실행에서 지금까지 쓴 돈(원). 단가를 모르는 모델이면 0."""
        return cost.krw(self.last_model, self.tokens_in, self.tokens_out,
                        getattr(self, "cache_write", 0),
                        getattr(self, "cache_read", 0)) or 0.0

    def _check_money(self):
        cap = getattr(self, "max_krw", 0) or 0
        if cap <= 0:
            return
        used = self.spent_krw()
        if used >= cap:
            raise BudgetExceeded(
                f"이번 실행에서 약 {used:,.0f}원을 썼다. 한 번 실행 한도 {cap:,.0f}원에 닿았다.\n"
                "  여기서 멈춘다. **지금까지 만든 대본은 저장한다.**\n"
                "  → 관리자 페이지에서 [이어서 마저 만들기] 를 한 번 더 누르면\n"
                "    만들어 둔 컷은 그대로 두고 남은 단계만 이어서 한다.\n"
                "  한도를 늘리려면 대본 만들기 화면의 '한 번에 쓸 수 있는 돈' 칸을 고쳐라.")

    def report(self):
        s = (f"모델 호출 {self.calls}회 · 입력 {self.tokens_in:,} 토큰 "
             f"· 출력 {self.tokens_out:,} 토큰")
        # 토큰 숫자는 사람에게 뜻이 없다. 얼마 나갔는지를 원으로 적는다.
        won = cost.line(self.last_model, self.tokens_in, self.tokens_out)
        if won:
            s += f"\n{won}"
        s += self.stage_table()
        return s

    def stage_table(self):
        """단계별로 얼마 나갔는지 비싼 순으로 적는다.

        "한 편에 3,000원" 만 알면 어디를 줄일지 못 고른다.
        비싼 줄이 눈에 보여야 거기부터 손을 댄다."""
        rows = [(w, n, name) for name, (n, w) in self.by_stage.items() if w > 0]
        if len(rows) < 2:
            return ""
        rows.sort(reverse=True)
        total = sum(w for w, _, _ in rows) or 1
        out = ["", "  어디에 나갔나 (비싼 순)"]
        for w, n, name in rows[:12]:
            bar = "\u2588" * max(1, round(w / total * 20))
            out.append(f"    {cost.pad(name, 16)} {w:>7,.0f}\uc6d0 "
                       f"{w / total * 100:>4.0f}% {bar}  ({n}\ud68c)")
        if len(rows) > 12:
            rest = sum(w for w, _, _ in rows[12:])
            out.append(f"    {cost.pad('그 밖에', 16)} {rest:>7,.0f}원")
        return "\n".join(out)


if __name__ == "__main__":
    g = Gemini()
    print("쓸 수 있는 모델:", len(g.available()), "개")
    print("  품질용(pro)  :", g.pick("pro"))
    print("  저가용(flash):", g.pick("flash"))
