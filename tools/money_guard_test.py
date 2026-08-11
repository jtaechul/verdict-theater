#!/usr/bin/env python3
"""돈이 새는 것을 막는 장치가 **진짜로 막는지** 본다. 비용 0원.

    python3 tools/money_guard_test.py

왜 이 검사가 있는가 (2026-08-11)
    2026-08-10 에 약 4,600원을 그냥 날렸다. 그때 있던 안전장치는
    '몇 번 불렀나'(max_calls) 하나뿐이었는데, 호출 하나의 값이 10원에서
    2,000원까지 벌어지므로 **횟수로는 돈을 막을 수 없다.**
    같은 '24회 상한' 이 208원일 수도 13,230원일 수도 있다.

    그래서 원(₩)으로 막는 장치를 두 겹 넣었다. 이 검사는 그 둘을 다 눌러 본다.
      1. 한 번 실행 한도 — 쓰는 도중 한도에 닿으면 멈추는가
      2. 한 달 한도     — 넘었으면 시작조차 안 하는가
      3. 장부          — 쓴 돈이 실제로 쌓이는가
"""

import json
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import cost                                        # noqa: E402
from claude import Claude, BudgetExceeded          # noqa: E402

ok = True


def bad(m):
    global ok
    print("❌ " + m)
    ok = False


# ── 1. 한 번 실행 한도 — 쓰는 도중에 멈추는가 ──────────────
print("① 한 번 실행 한도 (한도 1,000원으로 놓고 시험)")
c = Claude.__new__(Claude)                          # 열쇠 없이 계산기만 쓴다
c.calls = c.tokens_in = c.tokens_out = 0
c.cache_write = c.cache_read = 0
c.last_model = "claude-opus-5"
c.max_krw = 1000.0

c.tokens_in, c.tokens_out = 50_000, 5_000           # 약 434원
try:
    c._check_money()
    print(f"   ✅ {c.spent_krw():,.0f}원 — 한도 안이라 계속 간다")
except BudgetExceeded:
    bad(f"{c.spent_krw():,.0f}원인데 벌써 멈췄다 — 너무 일찍 막는다")

c.tokens_in, c.tokens_out = 150_000, 20_000         # 약 1,837원
try:
    c._check_money()
    bad(f"{c.spent_krw():,.0f}원을 썼는데 안 멈춘다 — 한도가 작동하지 않는다")
except BudgetExceeded as e:
    print(f"   ✅ {c.spent_krw():,.0f}원 — 한도를 넘어 멈췄다")
    if "VT_RUN_KRW" not in str(e):
        bad("멈추면서 한도 올리는 법을 안 알려준다")

# ── 2. 한 달 한도 — 시작조차 안 하는가 ─────────────────────
print()
print("② 한 달 한도 (한도 10,000원 · 이미 9,999원 쓴 상태로 시험)")
tmp = Path(tempfile.mkdtemp(prefix="ledger-"))
cost.LEDGER = tmp / "spend.json"
cost.MONTH_KRW = 10_000.0

cost.record("소재 심사", 4_000, "시험")
cost.record("대본 만들기", 5_999, "시험")
if abs(cost.month_total() - 9_999) > 1:
    bad(f"장부 합계가 틀리다: {cost.month_total()}")
else:
    print(f"   ✅ 장부에 쌓인다: 이번 달 {cost.month_total():,.0f}원")

try:
    cost.guard_month("대본 만들기")
    print(f"   ✅ 아직 {cost.month_left():,.0f}원 남아 시작할 수 있다")
except cost.MonthlyCapReached:
    bad("아직 1원 남았는데 시작을 막는다")

cost.record("대본 만들기", 2_000, "시험 — 한도 넘김")
try:
    cost.guard_month("대본 만들기")
    bad(f"이번 달 {cost.month_total():,.0f}원으로 한도를 넘겼는데 그냥 시작한다")
except cost.MonthlyCapReached as e:
    print(f"   ✅ 이번 달 {cost.month_total():,.0f}원 — 시작 전에 막았다")
    if "VT_MONTH_KRW" not in str(e) or "다음 달" not in str(e):
        bad("막으면서 어떻게 풀지를 안 알려준다")

# ── 3. 장부가 깨져도 제작이 멈추지 않는가 ──────────────────
print()
print("③ 장부 파일이 깨졌을 때")
cost.LEDGER.write_text("{망가진 내용", encoding="utf-8")
try:
    n = cost.month_total()
    print(f"   ✅ 깨진 장부를 읽어도 안 죽는다 (합계 {n:,.0f}원으로 보고 계속)")
except Exception as e:                              # noqa: BLE001
    bad(f"장부가 깨지면 제작까지 죽는다: {e}")

# ── 4. 심사 안 한 소재로 대본을 만들려 하면 돈 쓰기 전에 막는가 ──
#
#    2026-08-11 부터 '대본 만들기' 는 쓸 소재가 쌓여 있으면 소재 심사를
#    건너뛴다. 그러면 심사를 안 거친 판례가 그대로 대본으로 넘어갈 길이
#    열린다 — 못 쓸 이야기에 3,000원을 쓰게 된다. 그 문이 닫혀 있는지 본다.
print()
print("④ 심사 안 한 소재는 돈 쓰기 전에 막는가")
import re                                            # noqa: E402
src = (ROOT / "src" / "script.py").read_text(encoding="utf-8")

guard = re.search(r'if not args\.resume and row\.get\("gate_score"\) is None:', src)
if not guard:
    bad("심사 안 한 소재를 막는 자리가 사라졌다")
else:
    print("   ✅ 심사 안 한 소재(점수 없음)를 막는다")

if not re.search(r'if not args\.resume and not row\.get\("gate_pass"\):', src):
    bad("심사에서 떨어진 소재를 막는 자리가 사라졌다")
else:
    print("   ✅ 심사에서 떨어진 소재도 막는다")

# 막는 자리가 돈 쓰는 자리보다 **앞에** 있어야 한다. 뒤에 있으면 소용없다.
if guard:
    spend = src.find("llm, who = writer(max_calls=args.max_calls")
    if spend < 0 or guard.start() > spend:
        bad("막는 자리가 모델을 부르는 자리보다 뒤에 있다 — 돈이 이미 나간 뒤다")
    else:
        print("   ✅ 모델을 부르기 전에 막는다 (값 0원)")

import shutil
shutil.rmtree(tmp, ignore_errors=True)
print()
print("─" * 52)
print("✅ 돈 막는 장치: 정상" if ok else "❌ 돈 막는 장치: 문제 있음")
sys.exit(0 if ok else 1)
