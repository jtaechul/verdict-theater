#!/usr/bin/env python3
"""⭐ **쓴 돈이 장부 밖으로 새지 않는가.** 값 0원.

    python3 tools/ledger_check.py

⭐⭐⭐ 2026-09-05 손님: **"이 정도 돈이면은 전부 다 영상으로 만들 수도
   있었잖아. 다시 한번 확인해서 돈 세는 돈 없는지 확인해."**

   세어 보니 **대본 만들기(한 번 약 2,100원)가 장부에 한 줄도 안 적히고
   있었다.** 두 군데가 동시에 비어 있었기 때문이다 —
     ① `src/story90.py` 가 `cost.record()` 를 아예 안 불렀다
     ② `.github/workflows/story90.yml` 에 장부를 저장하는 칸이 없었다
   그래서 9월 5일에 두 번 지은 약 4,200원이 장부 밖에 있었다. 더 나쁜 것은
   **한 달 한도(MONTH_KRW)도 그 돈을 못 본다**는 점이다 — 장부만 보고 세기
   때문에, 실제로 25,000원을 넘겨도 막히지 않는다.

여기서 보는 것
   ① 돈 쓰는 워크플로는 **전부** 장부를 저장하는 칸을 갖고 있는가
   ② 그 워크플로가 부르는 프로그램이 **정말로** cost.record 를 부르는가
      (칸만 있고 안 적으면 파일이 안 바뀌어 아무 일도 안 일어난다)
   ③ 장부를 적는 자리가 성공·실패 **양쪽**에 다 있는가
      (반려돼도 돈은 이미 나갔다)
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"

# 돈이 나가는 열쇠. 이 중 하나라도 워크플로 env 에 있으면 "돈 쓰는 칸" 이다.
KEYS = ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_TTS_KEY",
        "TYPECAST_API_KEY")
# ⚠️ 열쇠를 **쓰는지 확인만** 하고 모델은 안 부르는 것 — 값이 0원이라 봐준다.
FREE = {"keycheck.yml"}

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name
          + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def progs(text):
    """이 워크플로가 부르는 우리 프로그램들."""
    return sorted(set(re.findall(r"python3 ((?:src|tools)/[\w.]+\.py)", text)))


def main():
    print("⭐ 쓴 돈이 장부에 다 적히는가 (값 0원)\n")

    print("① 돈 쓰는 워크플로가 장부를 저장하는가")
    pay = []
    for f in sorted(WF.glob("*.yml")):
        t = f.read_text(encoding="utf-8")
        if f.name in FREE or not any(k in t for k in KEYS):
            continue
        pay.append((f, t))
    ck(f"돈 쓰는 워크플로를 찾았다 ({len(pay)}개)", pay)
    miss = [f.name for f, t in pay if "state/spend.json" not in t]
    ck("전부 장부를 저장한다", not miss, " · ".join(miss))
    half = [f.name for f, t in pay
            if "state/spend.json" in t
            and not re.search(r"쓴 돈 장부[\s\S]{0,80}if: always\(\)", t)]
    ck("실패해도 장부를 남긴다 (if: always) — 반려돼도 돈은 나갔다",
       not half, " · ".join(half))

    print("\n② 그 워크플로가 부르는 프로그램이 정말로 적는가")
    # ⚠️ 칸만 있고 프로그램이 안 적으면 파일이 안 바뀌어 아무 일도 안 난다.
    #    실제로 story90 이 그랬다 — 칸도 없었고 부르지도 않았다.
    for f, t in pay:
        ps = [p for p in progs(t) if (ROOT / p).exists()]
        if not ps:
            continue
        # 그 프로그램들이 (직접이든 불러 쓰는 것으로든) 돈을 적는가
        wrote = []
        for p in ps:
            src = (ROOT / p).read_text(encoding="utf-8")
            if re.search(r"cost\.record\(|_c\.record\(", src):
                wrote.append(p)
                continue
            # 부르는 쪽이 아니라 **불러 쓰는 것**이 적을 수도 있다
            for mod in re.findall(r"^import (\w+)", src, re.M):
                m = ROOT / "src" / f"{mod}.py"
                if m.exists() and re.search(r"cost\.record\(|_c\.record\(",
                                            m.read_text(encoding="utf-8")):
                    wrote.append(p)
                    break
        ck(f"{f.name} — 부르는 프로그램이 장부에 적는다",
           wrote, f"{ps} 가운데 적는 것이 하나도 없다")

    print("\n③ 대본 만들기는 성공·실패 **양쪽 다** 적는가")
    st = (ROOT / "src" / "story90.py").read_text(encoding="utf-8")
    mn = (re.search(r"\ndef main\(\)[\s\S]*?\nif __name__", st) or [""])[0]
    n = len(re.findall(r'cost\.record\("대본 만들기"', mn))
    ck(f"두 자리에 다 적는다 (지금 {n}자리)", n >= 2,
       "반려돼도 돈은 이미 나갔다 — 그 자리에도 적어야 한다")
    ck("반려 자리에도 적는다", "(반려)" in mn)

    print("\n④ 한 달 한도가 그 돈을 볼 수 있는가")
    c = (ROOT / "src" / "cost.py").read_text(encoding="utf-8")
    ck("한 달 셈은 장부를 읽는다", "def month_total" in c)
    ck("한도를 넘으면 시작을 막는다", "MonthlyCapReached" in c)
    # ⚠️ 장부에 안 적히면 한도는 그 돈을 영영 못 본다 — ①②가 곧 한도의 눈이다
    ck("그래서 ①②가 곧 한도의 눈이다 (여기까지 통과해야 뜻이 있다)", not bad)

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 장부: {len(bad)}군데 — 쓴 돈이 안 보이게 샐 수 있다")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 장부: 돈 쓰는 칸이 전부 적고, 한 달 한도가 그것을 본다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
