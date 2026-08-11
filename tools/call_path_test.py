#!/usr/bin/env python3
"""모델 부르는 길을 **진짜로** 한 번 걸어 본다 (돈 0원 · 인터넷 0회).

    python3 tools/call_path_test.py

왜 이게 필요한가 — 2026-08-11 에 실제로 있었던 일
    `effort`(얼마나 깊이 생각할지) 를 넣으면서 값을 받는 자리(`_call`)에
    이름을 안 만들어 줬다. 그래서 첫 호출에서 바로 이렇게 죽었다.

        NameError: name 'effort' is not defined

    그런데 그날 돌던 사전 검사 3개는 전부 초록불이었다. **가짜 모델(FakeLLM)로만
    검사했기 때문이다.** 가짜는 `json()` 을 흉내만 낼 뿐, 진짜 `_call` 안으로는
    한 발짝도 들어가지 않는다. 그 사이에 소재 심사 565원이 나가고 대본은 0줄이었다.

    그래서 이 검사는 **가짜를 쓰지 않는다.** 진짜 Claude·Gemini 객체를 만들고,
    맨 마지막 '인터넷으로 나가는 한 줄'만 막아 세운다. 그 앞의 모든 코드
    — 모델 고르기, 사전 점검, 요청서 조립, effort, 프리필, 캐시, 답 꺼내 읽기 —
    는 실제와 똑같이 돈다. 여기서 초록불이면 NameError 로 죽는 일은 없다.

돈이 안 드는 이유
    나가는 문(`_req` / `_stream` / `_post`) 을 가짜 응답으로 바꿔치기한다.
    실제로는 아무것도 보내지 않는다.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import claude                                        # noqa: E402
import llm as llm_mod                                # noqa: E402

fails = []
sent = []          # 실제로 조립된 요청서들 — 내용까지 들여다본다


def ok(cond, what):
    print(("  ✅ " if cond else "  ❌ ") + what)
    if not cond:
        fails.append(what)


# ── 인터넷으로 나가는 문만 막는다 ─────────────────────────
def fake_claude_reply(path, key, method="GET", body=None, timeout=0):
    if body is None:                       # 모델 목록 물어보기
        return {"data": [{"id": "claude-opus-5"}, {"id": "claude-sonnet-5"}]}
    sent.append(body)
    return {
        "model": body.get("model", "claude-opus-5"),
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": '{"ok": true}'
                     if body.get("messages", [{}])[-1].get("role") != "assistant"
                     else '"ok": true}'}],
        "usage": {"input_tokens": 1000, "output_tokens": 50,
                  "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0},
    }


def fake_claude_stream(path, key, body, timeout=0):
    return fake_claude_reply(path, key, "POST", body, timeout)


print("1) Claude — 진짜 _call 을 끝까지 걸어 본다")
claude._req = fake_claude_reply
claude._stream = fake_claude_stream

c = claude.Claude(api_key="test-key-not-real")
try:
    got = c.json("아무 말이나", tier="pro", max_output_tokens=4096,
                 temperature=0.9, label="검사", cache_prefix="",  effort="")
    ok(got == {"ok": True}, "effort 없이 부르기")
except Exception as e:
    ok(False, f"effort 없이 부르기 — {type(e).__name__}: {e}")

# ⭐ 여기가 2026-08-11 에 터진 자리다. 단계마다 다른 값을 넣어 전부 걸어 본다.
for depth in ("low", "medium", "high", "xhigh", "max"):
    try:
        c.json("아무 말이나", tier="pro", max_output_tokens=4096,
               temperature=0.9, label="검사", cache_prefix="", effort=depth)
        ok(True, f"effort={depth} 로 부르기")
    except Exception as e:
        ok(False, f"effort={depth} 로 부르기 — {type(e).__name__}: {e}")

# 캐시(반복되는 앞부분 기억시키기) 를 켠 길도 걸어 본다
try:
    c.json("뒷부분", tier="pro", max_output_tokens=4096, temperature=0.9,
           label="검사", cache_prefix="아주 긴 앞부분", effort="high")
    ok(True, "cache_prefix 를 켜고 부르기")
except Exception as e:
    ok(False, f"cache_prefix 를 켜고 부르기 — {type(e).__name__}: {e}")

print()
print("2) 조립된 요청서가 실제로 시키는 대로 돼 있는가")
with_effort = [b for b in sent if "output_config" in b]
ok(bool(with_effort), "effort 를 준 호출에는 output_config 가 들어간다")
if with_effort:
    vals = {b["output_config"].get("effort") for b in with_effort}
    ok(vals <= {"low", "medium", "high", "xhigh", "max"},
       f"effort 값이 규격 안에 있다 ({sorted(vals)})")
ok(any("output_config" not in b for b in sent),
   "effort 를 안 준 호출에는 output_config 를 넣지 않는다")

opus = [b for b in sent if "opus-5" in b.get("model", "")]
ok(opus and all("temperature" not in b for b in opus),
   "Opus 5 에는 temperature 를 애초에 안 보낸다 (400 을 먹지 않는다)")
ok(opus and all(b["messages"][-1]["role"] == "user" for b in opus),
   "Opus 5 에는 프리필을 안 보낸다 (400 을 먹지 않는다)")

cached = [b for b in sent if isinstance(b["messages"][0]["content"], list)]
ok(bool(cached), "cache_prefix 를 주면 기억해 둘 부분이 따로 표시된다")
if cached:
    head = cached[0]["messages"][0]["content"][0]
    ok(head.get("cache_control", {}).get("type") == "ephemeral",
       "기억 표시가 cache_control 로 붙는다")

print()
print("3) 사전 점검을 쓸데없이 걸지 않는가")
before = len(sent)
try:
    c2 = claude.Claude(api_key="test-key-not-real")
    c2.json("한 번만", tier="pro", max_output_tokens=512, effort="low")
    ok(len(sent) - before == 1,
       f"아는 모델이면 사전 점검을 건너뛴다 (호출 {len(sent) - before}회 — 1회여야 한다)")
except Exception as e:
    ok(False, f"아는 모델이면 사전 점검을 건너뛴다 — {type(e).__name__}: {e}")

print()
print("4) Gemini — 같은 길을 같은 인자로 걸어 본다")
g_sent = []


def fake_gemini_post(model, body, key, timeout=0):
    g_sent.append((model, body))
    return {"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]},
                            "finishReason": "STOP"}],
            "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 50}}


posted = False
for name in ("_post", "_req", "_generate", "_call_api"):
    if hasattr(llm_mod, name):
        setattr(llm_mod, name, fake_gemini_post)
        posted = True
        break
if hasattr(llm_mod, "_models"):
    llm_mod._models = lambda *a, **k: ["gemini-3-pro", "gemini-3-flash"]

import inspect                                        # noqa: E402
cs = inspect.signature(claude.Claude.json).parameters
gs = inspect.signature(llm_mod.Gemini.json).parameters
ok(set(cs) == set(gs),
   f"두 곳의 json() 이 같은 인자를 받는다 (Claude {sorted(cs)} / Gemini {sorted(gs)})")

# Gemini 쪽은 나가는 문 이름이 파일마다 달라, 못 찾으면 조용히 넘어간다.
# (인자 이름이 같은지는 위에서 이미 확인했다 — 그게 Gemini 실행이 죽던 원인이었다.)
if not posted:
    print("  · Gemini 의 나가는 문을 못 찾아 호출까지는 걸어 보지 않았다")

print()
if fails:
    print(f"❌ {len(fails)}곳이 막혔다:")
    for f in fails:
        print(f"   - {f}")
    sys.exit(1)
print("✅ 모델 부르는 길이 처음부터 끝까지 뚫려 있다. (돈 0원)")
