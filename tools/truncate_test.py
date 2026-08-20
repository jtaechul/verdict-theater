#!/usr/bin/env python3
"""⭐ 길이 상한에 걸렸을 때 되풀이해서 돈을 3배로 쓰지 않는지 본다. 0원 · 인터넷 0회.

    python3 tools/truncate_test.py

왜 (2026-08-20)
    시리즈 대본이 32,768 토큰 상한에서 잘렸다. 그런데 우리 코드가 **같은
    상한으로 3번 더** 불렀다. 잘릴 것이 뻔한데 15분 동안 3회분 값만 나갔다.

    되풀이해도 소용없는 오류(길이 상한·400·401·403·404)는 바로 멈춰야 한다.
    말로 고쳤다고 하지 말고, 잘린 응답을 흉내 내 **실제로 몇 번 부르는지** 센다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import llm                                                  # noqa: E402

FAIL = []


def ck(label, cond, extra=""):
    print(("   ✅ " if cond else "   ❌ ") + label + (f"  ({extra})" if extra else ""))
    if not cond:
        FAIL.append(label)


def run(finish_reason):
    """그 finishReason 을 주는 가짜 서버로 한 번 불러 보고, 실제 호출 수를 센다."""
    n = {"c": 0}

    def fake_post(url, payload):
        n["c"] += 1
        return {"candidates": [{"finishReason": finish_reason,
                                "content": {"parts": [{"text": "{}"}]}}],
                "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
                "modelVersion": "test"}

    real, llm._post = llm._post, fake_post
    try:
        g = llm.Gemini.__new__(llm.Gemini)
        g.key = "x"; g.calls = 0; g.max_calls = 99
        g.tokens_in = 0; g.tokens_out = 0; g.by_stage = {}
        g.last_model = ""; g._limits = {}
        g.pick = lambda t: "gemini-test"
        g._check_money = lambda: None
        try:
            g.json("시험")
            return n["c"], None
        except Exception as e:                               # noqa: BLE001
            return n["c"], e
    finally:
        llm._post = real


print("⭐ 길이 상한에서 돈을 되풀이해 쓰지 않는가\n")

print("① 잘렸을 때")
n, e = run("MAX_TOKENS")
ck("길이 상한 오류로 멈춘다", isinstance(e, llm.TooLong), type(e).__name__)
ck("**한 번만** 부른다 (예전에는 4번 불렀다)", n == 1, f"{n}회")
ck("무엇을 고쳐야 하는지 말해 준다", "max_output_tokens" in str(e), str(e)[:56])

print("\n② 잘리지 않았을 때는 그대로 돌아야 한다")
n, e = run("STOP")
ck("정상 응답은 한 번에 받는다", e is None and n == 1, f"{n}회 · {type(e).__name__}")

print("\n③ 갈래가 제대로 짜여 있는가")
ck("TooLong 은 LLMError 로도 잡힌다", issubclass(llm.TooLong, llm.LLMError))

print("\n" + "─" * 52)
print(f"❌ 길이 상한: {len(FAIL)}가지 실패" if FAIL else "✅ 길이 상한: 전부 통과")
sys.exit(1 if FAIL else 0)
