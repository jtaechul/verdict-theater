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

import http.client
import json
import os
import re
import time
import urllib.error
import urllib.request

BASE = "https://api.anthropic.com/v1"
VERSION = "2023-06-01"
TIMEOUT = 900          # 생각까지 하고 긴 대본을 쓰면 오래 걸린다. 넉넉히 준다
RETRIES = 4
BACKOFF = [5, 15, 40]

# 요즘 모델은 답을 내기 전에 '생각(thinking)'을 하고, 그게 기본으로 켜져 있다.
# 중요한 건 **max_tokens 가 생각과 답을 합쳐서 덮는다**는 점이다.
# 답 길이만 보고 한도를 잡으면 생각이 먼저 먹어치워 JSON 이 중간에서 잘린다.
# max_tokens 는 상한일 뿐 실제로 쓴 만큼만 과금되므로, 넉넉히 잡는 게 손해가 아니다.
THINK_ROOM = 8192      # 생각 몫으로 얹어주는 여유분
MIN_TOKENS = 2048      # 아무리 짧은 요청이라도 이만큼은 준다

# 긴 답을 '한 번에 다 써서 보내라'고 하면, 서버가 다 쓸 때까지 아무것도 안 보낸다.
# 그 침묵이 길어지면 중간 장비가 연결을 끊는다 — 실제로 19분치 작업이 이렇게 날아갔다.
#   http.client.RemoteDisconnected: Remote end closed connection without response
# 그래서 긴 답은 **스트리밍**(쓰는 대로 조금씩 받기)으로 받는다. 계속 데이터가 흐르므로
# 연결이 끊기지 않는다. 한도가 이 값을 넘으면 자동으로 스트리밍으로 바꾼다.
STREAM_OVER = 16000

# 네트워크가 끊기는 방식은 여러 가지다. RemoteDisconnected 는 URLError 가 아니라서
# 종전 코드가 놓쳤다(그래서 재시도도 못 하고 그대로 죽었다). OSError 로 넓게 잡는다.
NET_ERRORS = (OSError, http.client.HTTPException, TimeoutError)

# 모델마다 받아주는 설정이 다르고, 그 규칙은 예고 없이 바뀐다.
# 실제로 claude-opus-5 는 temperature 를 더 이상 받지 않아 소재 심사 6건이 전부 400 으로 죽었다.
# 모델 이름을 코드에 박지 않기로 한 이상, 이런 것도 박아두면 안 된다.
# → **거절당하면 그 설정만 빼고 다시 건다.** 모델이 바뀌어도 스스로 맞춘다.
DROPPABLE = ("temperature", "top_p", "top_k")

_REJECT_WORDS = ("deprecated", "unsupported", "not supported", "not allowed",
                 "unexpected", "unrecognized", "no longer")


def _unsupported_param(body, payload):
    """400 응답이 '이 설정은 못 받는다'고 말하면 그 설정 이름을 돌려준다."""
    low = body.lower()
    if not any(w in low for w in _REJECT_WORDS):
        return None
    for name in DROPPABLE:
        if name in payload and name in low:
            return name
    return None


CEILING = 64000          # 출력 한도를 스스로 올릴 때의 천장

# 프리필(응답을 `{` 로 미리 채워 JSON 으로 시작하게 만드는 수법)을 못 쓰는 모델을 위해,
# 같은 요구를 시스템 지시로 대신한다.
_JSON_SYSTEM = (
    "You output exactly one JSON object and nothing else. "
    "No preamble, no explanation, no apology, no markdown code fences. "
    "The first character of your reply is { and the last character is }. "
    "Write the JSON *values* in the same language as the user's request "
    "(Korean requests get Korean values)."
)


def _prefill_rejected(body):
    """이 모델이 '응답 미리 채워 넣기'를 안 받는다고 말하는가."""
    low = body.lower()
    return ("prefill" in low
            or "must end with a user message" in low
            or ("assistant" in low and "last message" in low))


def _extract_json(text):
    """설명문·코드펜스가 섞여 와도 JSON 객체 하나를 끄집어낸다.

    프리필을 못 쓰는 모델에서는 응답 앞뒤에 말이 붙을 수 있다.
    문자열 안에 있는 중괄호를 세면 안 되므로 따옴표와 역슬래시를 따라간다."""
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    start = s.find("{")
    if start < 0:
        raise ClaudeError(f"응답에 JSON 이 없다. 앞부분: {s[:200]}")
    depth = 0
    in_str = esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(s[start:i + 1])
                except json.JSONDecodeError as e:
                    raise ClaudeError(f"JSON 형식이 아니다: {e}\n앞부분: {s[start:start + 200]}")
    raise ClaudeError(f"JSON 이 중간에서 끊겼다 (받은 길이 {len(s)}). 앞부분: {s[:200]}")


def _max_tokens_cap(body):
    """400 응답이 '출력 한도를 넘었다'고 말하면 그 한도를 숫자로 돌려준다.

    Claude 의 모델 목록에는 출력 한도가 안 나온다(Gemini 는 나온다).
    그래서 물어볼 수 없고, 거절당했을 때 응답에 적힌 숫자로 배우는 수밖에 없다."""
    m = re.search(r"max_tokens:\s*\d+\s*>\s*(\d+)", body)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d[\d,]*)\s*,?\s*which is the maximum allowed number of output tokens", body)
    if m:
        return int(m.group(1).replace(",", ""))
    return None


class ClaudeError(RuntimeError):
    """fatal=True 는 '설정을 바꿔도 소용없다'는 뜻이다.

    열쇠가 틀렸거나 잔액이 없는 경우가 여기 해당한다. 사전 점검이 이걸 만나면
    본 호출을 시도하지 않고 바로 멈춘다 — 어차피 똑같이 실패하기 때문이다."""

    def __init__(self, msg, fatal=False):
        super().__init__(msg)
        self.fatal = fatal


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


def _stream(path, key, body, timeout=TIMEOUT):
    """긴 답을 조금씩 받아 조립한다.

    한 번에 다 받는 것과 결과는 똑같다 — 받는 방식만 다르다. 서버가 글을 쓰는 동안
    계속 조각이 흘러오므로 연결이 끊기지 않는다. 조립이 끝나면 한 번에 받았을 때와
    같은 모양으로 돌려주므로, 부르는 쪽 코드는 바뀔 게 없다."""
    data = json.dumps(dict(body, stream=True)).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/{path}", data=data, method="POST", headers={
        "x-api-key": key,
        "anthropic-version": VERSION,
        "content-type": "application/json",
        "accept": "text/event-stream",
        "user-agent": "verdict-theater/1.0",
    })
    parts = {}                       # 조각 번호 → 지금까지 모은 글
    stop = None
    usage = {"input_tokens": 0, "output_tokens": 0}

    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            try:
                ev = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            kind = ev.get("type")

            if kind == "message_start":
                u = (ev.get("message") or {}).get("usage") or {}
                usage["input_tokens"] = u.get("input_tokens", 0)
            elif kind == "content_block_start":
                blk = ev.get("content_block") or {}
                if blk.get("type") == "text":
                    parts[ev.get("index", 0)] = blk.get("text", "")
            elif kind == "content_block_delta":
                d = ev.get("delta") or {}
                if d.get("type") == "text_delta":
                    i = ev.get("index", 0)
                    parts[i] = parts.get(i, "") + d.get("text", "")
            elif kind == "message_delta":
                stop = (ev.get("delta") or {}).get("stop_reason", stop)
                usage["output_tokens"] = (ev.get("usage") or {}).get(
                    "output_tokens", usage["output_tokens"])
            elif kind == "error":
                e = ev.get("error") or {}
                raise ClaudeError(f"스트리밍 중 오류: {e.get('type')} {e.get('message')}")

    text = "".join(parts[i] for i in sorted(parts))
    return {"content": [{"type": "text", "text": text}],
            "stop_reason": stop, "usage": usage}


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
        self.fails = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self.cache_write = 0   # 기억시키느라 낸 토큰 (한 번, 정가의 2배)
        self.cache_read = 0    # 기억해 둔 걸 다시 쓴 토큰 (정가의 10분의 1)
        self._models = None
        # 배운 것은 모델별로 따로 기억한다. opus 와 sonnet 은 받아주는 설정이 다를 수 있다.
        self._drop = {}         # 모델 → 거절당한 설정 이름들
        self._cap = {}          # 모델 → 출력 한도 (거절당하며 알아낸 값)
        self._prefill = {}      # 모델 → 응답 미리 채워 넣기를 쓸 수 있는가
        self._probed = set()    # 사전 점검을 마친 모델

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
    def json(self, prompt, tier="pro", max_output_tokens=32768, temperature=0.9,
             label="", cache_prefix=""):
        """프롬프트를 보내고 JSON 하나를 받는다.

        cache_prefix — 여러 호출에서 **글자 하나 안 틀리고 똑같이** 반복되는 앞부분.
          대본 생성이 그렇다. 지시문 + 판례 본문 13,449 토큰이 설계 1회 + 막별 6회,
          모두 7번 똑같이 나간다. 그대로 두면 편당 659원이 순수한 중복이다.
          여기에 표시해 두면 서버가 한 번만 읽고 기억한다 — 다음부터는 10분의 1 값이다."""
        model = self.pick(tier)
        self._warmup(model)
        return self._call(model, prompt, max_output_tokens, temperature, label, cache_prefix)

    def _warmup(self, model):
        """본 작업 전에 아주 작은 호출 한 번으로 '이 모델이 받아주는 설정'을 알아낸다.

        왜 이걸 따로 두는가
          모델이 바뀌면 받아주는 설정도 바뀐다. 그걸 본 작업 도중에 알게 되면
          비싼 호출이 줄줄이 실패한다 — 실제로 소재 심사 6건이 두 번 통째로 날아갔다
          (한 번은 temperature, 한 번은 프리필).
          그러지 말고 **토큰 몇 개짜리 호출 한 번으로 먼저 알아내고**,
          알아낸 설정을 그 실행 내내 쓴다.

        여기서 실패해도 멈추지 않는다. 진짜 문제라면 본 호출에서 같은 오류가 다시 나고,
        그때 제대로 된 메시지가 나간다."""
        if model in self._probed:
            return
        self._probed.add(model)
        try:
            self._call(model, '{"ok": true} 를 그대로 출력하라.', 64, 0.0, "사전 점검", "")
        except BudgetExceeded:
            raise
        except ClaudeError as e:
            if e.fatal:
                raise          # 열쇠·잔액 문제. 본 호출을 걸어봐야 똑같이 실패한다
            # 내용 문제(작은 프롬프트라 생긴 것일 수 있다)는 넘어가고 본 호출에서 확인한다
            print(f"    (사전 점검 실패 — 본 호출에서 다시 확인한다: {str(e)[:120]})")

    def _call(self, model, prompt, max_output_tokens, temperature, label, cache_prefix=""):
        if self.calls >= self.max_calls:
            raise BudgetExceeded(
                f"이번 실행에서 이미 {self.calls}회 호출했다. 상한 {self.max_calls}회. "
                "무한 루프로 인한 과금 폭발을 막는 장치다."
            )
        max_output_tokens = max(max_output_tokens + THINK_ROOM, MIN_TOKENS)
        cap = self._cap.get(model)
        if cap and max_output_tokens > cap:
            print(f"    (출력 한도 조정: {max_output_tokens:,} → {cap:,} · {model})")
            max_output_tokens = cap

        # 프리필을 쓸 수 있는 모델이면 응답을 `{` 로 시작하게 못 박는다.
        # 못 쓰는 모델이면 시스템 지시 + 꺼내 읽기로 대신한다.
        prefill = self._prefill.get(model, True)

        # 반복되는 앞부분은 따로 떼어 "이건 기억해 둬라"고 표시한다.
        # ttl 1시간을 쓰는 이유: 막 하나 쓰는 데 2~3분씩 걸려 7번이면 20분이다.
        # 기본 5분짜리로는 중간에 잊어버려 오히려 매번 다시 읽게 된다.
        if cache_prefix:
            content = [
                {"type": "text", "text": cache_prefix,
                 "cache_control": {"type": "ephemeral", "ttl": "1h"}},
                {"type": "text", "text": prompt},
            ]
        else:
            content = prompt

        payload = {
            "model": model,
            "max_tokens": max_output_tokens,
            "temperature": min(1.0, temperature),
            "system": _JSON_SYSTEM,
            "messages": [{"role": "user", "content": content}],
        }
        if prefill:
            payload["messages"].append({"role": "assistant", "content": "{"})
        for name in self._drop.get(model, ()):   # 이미 거절당한 설정은 처음부터 빼고 보낸다
            payload.pop(name, None)

        last = None
        attempt = 0
        adjusted = 0                             # 설정을 고쳐 다시 건 횟수 (재시도 횟수와 별개)
        while attempt < RETRIES:
            try:
                if payload["max_tokens"] > STREAM_OVER:
                    res = _stream("messages", self.key, payload)
                else:
                    res = _req("messages", self.key, method="POST", body=payload)
                self.calls += 1
                u = res.get("usage", {})
                self.tokens_in += u.get("input_tokens", 0)
                self.tokens_out += u.get("output_tokens", 0)
                self.cache_write += u.get("cache_creation_input_tokens", 0)
                self.cache_read += u.get("cache_read_input_tokens", 0)

                # 모델이 안전상의 이유로 거절할 수 있다. 오류가 아니라 정상 응답으로 온다.
                # 같은 걸 다시 물어도 또 거절한다 — 재시도하면 시간만 버린다.
                if res.get("stop_reason") == "refusal":
                    self.fails += 1
                    cat = (res.get("stop_details") or {}).get("category")
                    raise ClaudeError(
                        "모델이 안전상의 이유로 답변을 거절했다"
                        + (f" (분류: {cat})" if cat else "")
                        + ".\n  이 판례의 소재가 걸렸을 수 있다. 다른 판례로 넘어가라.",
                        fatal=True)

                if res.get("stop_reason") == "max_tokens":
                    # 같은 요청을 그대로 다시 걸면 똑같이 잘린다. 한도를 올려서 걸어야 한다.
                    room = self._cap.get(model) or CEILING
                    cur = payload["max_tokens"]
                    if cur < room and adjusted < 4:
                        payload["max_tokens"] = min(room, cur * 2)
                        adjusted += 1
                        print(f"    (출력이 잘렸다 — 한도를 {payload['max_tokens']:,} 로 올려 다시 건다)")
                        continue
                    raise ClaudeError(
                        f"출력이 길이 상한({cur:,})에서 잘렸다. 더 올릴 수 없다.")

                text = "".join(p.get("text", "") for p in res.get("content", [])
                               if p.get("type") == "text")
                if not text.strip():
                    raise ClaudeError(f"본문이 비었다 (stop_reason={res.get('stop_reason')})")
                if payload["messages"][-1]["role"] == "assistant":
                    text = "{" + text            # 미리 채운 `{` 를 되돌린다
                return _extract_json(text)

            except urllib.error.HTTPError as e:
                last = e
                body = e.read().decode("utf-8", "replace")[:400]

                # 400 이라고 다 끝난 게 아니다. "그건 못 받는다"는 뜻이면 고쳐서 다시 건다.
                if e.code == 400 and adjusted < 4:
                    bad = _unsupported_param(body, payload)
                    if bad:
                        self._drop.setdefault(model, set()).add(bad)
                        payload.pop(bad, None)
                        adjusted += 1
                        print(f"    (이 모델은 '{bad}' 설정을 받지 않는다 — 빼고 다시 건다)")
                        continue
                    if _prefill_rejected(body) and payload["messages"][-1]["role"] == "assistant":
                        self._prefill[model] = False
                        payload["messages"] = payload["messages"][:-1]
                        adjusted += 1
                        print("    (이 모델은 응답 미리 채우기를 받지 않는다 — 빼고 다시 건다)")
                        continue
                    lim = _max_tokens_cap(body)
                    if lim and lim < payload.get("max_tokens", 0):
                        self._cap[model] = lim
                        payload["max_tokens"] = lim
                        adjusted += 1
                        print(f"    (이 모델의 출력 한도는 {lim:,} — 줄여서 다시 건다)")
                        continue

                if e.code in (400, 401, 403, 404):
                    self.fails += 1
                    raise ClaudeError(
                        f"호출 실패 (HTTP {e.code}) — 재시도해도 소용없다.\n{body}", fatal=True)
                attempt += 1
                if attempt < RETRIES:
                    w = BACKOFF[attempt - 1]
                    print(f"    (재시도 {attempt}/{RETRIES - 1} — HTTP {e.code}, {w}초 대기)")
                    time.sleep(w)
            # 연결이 끊기는 방식은 여러 가지다(RemoteDisconnected · 리셋 · 타임아웃 …).
            # 종전엔 URLError 만 잡아서 RemoteDisconnected 를 놓치고 그대로 죽었다.
            except NET_ERRORS + (ClaudeError,) as e:
                # 고칠 수 없다고 판정된 것(안전 거절 등)은 다시 걸어도 같은 답이다.
                if getattr(e, "fatal", False):
                    raise
                last = e
                attempt += 1
                if attempt < RETRIES:
                    w = BACKOFF[attempt - 1]
                    print(f"    (재시도 {attempt}/{RETRIES - 1} — {type(e).__name__}, {w}초 대기)")
                    time.sleep(w)
        self.calls += 1
        self.fails += 1
        raise ClaudeError(f"{label or '호출'} 최종 실패: {last}")

    def report(self):
        s = (f"모델 호출 {self.calls}회 · 입력 {self.tokens_in:,} 토큰 "
             f"· 출력 {self.tokens_out:,} 토큰")
        if self.fails:
            s += f" · 실패 {self.fails}회"
        if self.cache_read or self.cache_write:
            # 정가로 다 냈다면 얼마였을지와 비교해 실제로 아낀 값을 보여준다.
            full = self.tokens_in + self.cache_write + self.cache_read
            paid = self.tokens_in + self.cache_write * 2 + self.cache_read * 0.1
            s += (f"\n재사용: 기억 {self.cache_write:,} · 다시 씀 {self.cache_read:,} 토큰"
                  f" → 입력값 {full:,} 어치를 {paid:,.0f} 값에 냈다")
            if full > paid:
                s += f" ({(1 - paid / full) * 100:.0f}% 절감)"
        return s


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
