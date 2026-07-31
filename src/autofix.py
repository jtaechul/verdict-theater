#!/usr/bin/env python3
"""기계적으로 확정되는 오류를 코드로 고친다. 모델을 부르지 않는다 — 비용 0원.

왜 필요한가
    검증에서 걸리는 오류 중 상당수는 "정답이 하나로 정해지는" 것들이다.
      · meta.cut_count 가 실제 컷 수와 다르다   → 세어서 넣으면 끝
      · blackout 이 막 마지막 컷에 없다          → 규칙이 곧 정답
      · 막별 초 합계가 목표에서 벗어났다          → 비율대로 맞추면 끝
      · amb 가 비었다                            → 앞 컷 것을 이어받으면 끝

    그런데 지금까지는 이런 것 하나 때문에 **대본 전문(약 26,000 토큰)을
    모델에게 보내고 전문을 다시 받았다.** 113컷을 다시 써서 숫자 하나를 고친 셈이다.
    편당 한 번만 일어나도 약 900원이 그냥 나간다.

    여기서 먼저 고쳐서 넘기면, 모델은 사람의 판단이 필요한 것만 본다.

⚠️ 손대지 않는 것
    뜻이 바뀌는 것은 건드리지 않는다 — 대사 내용, 절대 연도, 인물 수, 법조문.
    그런 것은 사람(모델)이 판단해야 한다.

    python3 src/autofix.py data/scripts/EP001.json    제자리에서 고치기
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import money                                                # noqa: E402
from validate_script import ACT_WINDOW, ACT_TOL, MAX_CUT_SEC  # noqa: E402

MIN_CUT_SEC = 1.0          # 이보다 짧으면 화면이 깜빡이는 것으로 보인다
HOOK_FIRST_MAX = 3.0       # 3초 관문 — 첫 컷은 3초를 넘을 수 없다


def _round1(x):
    return round(x + 1e-9, 1)


def _rebalance(cuts, want, tol, first_max=None):
    """막의 초 합계를 목표에 맞춘다. 비율대로 늘리거나 줄인 뒤 한도로 자른다."""
    if not cuts:
        return 0
    secs = [float(c.get("sec") or 0) for c in cuts]
    cur = sum(secs)
    if abs(cur - want) <= tol:
        return 0

    lim = []
    for i in range(len(cuts)):
        hi = MAX_CUT_SEC
        if i == 0 and first_max:
            hi = min(hi, first_max)
        lim.append((MIN_CUT_SEC, hi))

    ratio = (want / cur) if cur > 0 else 1.0
    new = [_round1(min(max(s * ratio, lo), hi)) for s, (lo, hi) in zip(secs, lim)]

    # 자르고 남은 오차를 여유 있는 컷에 0.1초씩 나눠 준다
    for _ in range(4000):
        gap = _round1(want - sum(new))
        if abs(gap) < 0.05:
            break
        step = 0.1 if gap > 0 else -0.1
        moved = False
        for i in range(len(new)):
            lo, hi = lim[i]
            nxt = _round1(new[i] + step)
            if lo <= nxt <= hi:
                new[i] = nxt
                moved = True
                if abs(_round1(want - sum(new))) < 0.05:
                    break
        if not moved:                     # 전부 한도에 닿았다 — 더 못 맞춘다
            break

    changed = 0
    for c, s, o in zip(cuts, new, secs):
        if abs(s - o) >= 0.05:
            c["sec"] = s
            changed += 1
    return changed


def autofix(doc):
    """제자리에서 고치고, 무엇을 고쳤는지 한국어로 돌려준다."""
    notes = []

    # 1. 7초를 넘는 컷을 한도로 자른다 (먼저 해야 아래 초 합계가 맞는다)
    long_cuts = [c for _, c in _all(doc) if float(c.get("sec") or 0) > MAX_CUT_SEC]
    for c in long_cuts:
        c["sec"] = MAX_CUT_SEC
    if long_cuts:
        notes.append(f"{MAX_CUT_SEC}초 넘는 컷 {len(long_cuts)}개를 한도로 줄였다")

    # 2. 막별 초 합계를 목표에 맞춘다
    fixed_acts = []
    for act in doc.get("acts", []):
        aid = act.get("id")
        if aid not in ACT_WINDOW:
            continue
        lo, hi = ACT_WINDOW[aid]
        n = _rebalance(act.get("cuts", []), hi - lo, ACT_TOL,
                       first_max=HOOK_FIRST_MAX if aid == "hook" else None)
        if n:
            fixed_acts.append(f"{aid}({n}컷)")
    if fixed_acts:
        notes.append("막별 초 합계를 맞췄다: " + ", ".join(fixed_acts))

    # 3. blackout — 각 막의 마지막 컷에만 있어야 한다. 규칙이 곧 정답이다.
    bl = 0
    for act in doc.get("acts", []):
        cuts = act.get("cuts", [])
        for i, c in enumerate(cuts):
            want = (i == len(cuts) - 1)
            if bool(c.get("blackout")) != want:
                c["blackout"] = want
                bl += 1
    if bl:
        notes.append(f"blackout {bl}컷을 규칙대로 맞췄다")

    # 4. amb 가 빈 컷은 앞 컷 것을 이어받는다. 무음 구간이 생기는 것만 막는다.
    amb = 0
    for act in doc.get("acts", []):
        prev = ""
        for c in act.get("cuts", []):
            if c.get("amb"):
                prev = c["amb"]
            elif prev:
                c["amb"] = prev
                amb += 1
    if amb:
        notes.append(f"비어 있던 amb {amb}컷을 앞 컷 것으로 채웠다")

    # 5. meta.cut_count — 세면 되는 값이다
    n = sum(1 for _ in _all(doc))
    if doc.setdefault("meta", {}).get("cut_count") != n:
        doc["meta"]["cut_count"] = n
        notes.append(f"meta.cut_count 를 실제 컷 수({n})로 맞췄다")

    # 6. 금액을 백만원 단위로 (money.py 와 같은 규칙)
    before = money.untidy(json.dumps(doc, ensure_ascii=False))
    if before:
        doc.update(money.tidy_doc(doc))
        notes.append(f"자잘한 금액 {len(set(before))}종을 백만원 단위로 끊었다")

    return notes


def _all(doc):
    for act in doc.get("acts", []):
        for c in act.get("cuts", []):
            yield act, c


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    for f in sys.argv[1:]:
        p = Path(f)
        d = json.loads(p.read_text(encoding="utf-8"))
        notes = autofix(d)
        if not notes:
            print(f"  {p.name}: 기계적으로 고칠 것이 없다")
            continue
        p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  {p.name}:")
        for n in notes:
            print(f"      · {n}")
