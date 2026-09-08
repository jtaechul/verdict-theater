#!/usr/bin/env python3
"""⭐ **대본 길이를 재는 잣대가 실제와 맞는가.** 값 0원.

    python3 tools/sec_scale_check.py

⭐⭐⭐ 2026-09-08 — 잣대가 **54% 틀린 채 일곱 달을 갔다.**

   `story90.SEC_PER_CHAR` 는 2026-09-01 에 0.248 로 박혔다. 그날 말 빠르기
   (short90.SPEED)가 1.08 이었다. 그 **다섯 시간 뒤** SPEED 를 1.20 으로
   올렸는데 잣대는 아무도 안 고쳤다. 두 숫자가 서로를 모른 채 떨어져 있었다.

   그래서 —
     · S91 1편 201자 → 잣대는 "50초" 라 하고, **실제는 41.3초**였다.
     · 225자 상한이 실제로는 **38초짜리 벽**이었다. 60초까지 22초가 남는데
       검사가 그 앞에서 막았다.
     · 손님(9/5): "영상이 너무 짧은데? 너무 빠르게 본론으로 들어가 버리니까
       내용이 이해가 안 돼." — 대본 탓이 아니라 **재는 자** 탓이었다.

여기서 보는 것
   ① 잣대가 **실제로 만든 영상**의 길이를 맞히는가 (붙박이 실측표로 시험)
   ② 글자만이 아니라 **컷 수**도 재는가 (컷마다 고정 시간이 붙는다)
   ③ 상한이 60초 벽(short90.PART_MAX_SEC) 안쪽에 안전분을 두고 있는가
   ④ 대본 프롬프트가 시키는 글자 수가 그 초 안에 들어가는가

⚠️ 손님이 고치는 파일(data/series/*.json)에 기대지 않는다. 아래 실측표는
   2026-09-06 에 실제로 만들어 유튜브에 올린 S91 세 편을 **붙박이로** 적어 둔
   것이다. 살아 있는 자료에 검사를 묶었다가 세 번 데었다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import short90 as S9                                         # noqa: E402
import story90 as ST                                         # noqa: E402

# ── 붙박이 실측표 (2026-09-06 · S91 · build 로그와 state/shorts.json 에서) ──
#    (편, 글자수(chars() 기준), 컷수, 실제 만들어진 길이(초))
MEASURED = [(1, 201, 9, 41.3), (2, 222, 9, 45.5), (3, 221, 9, 42.3)]
TOL = 2.5                        # 이만큼까지는 맞는 것으로 본다

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def est(ch, cuts):
    return ST.SEC_PER_CHAR * ch + ST.SEC_PER_CUT * cuts


def main():
    print("⭐ 대본 길이 잣대가 실제와 맞는가 (값 0원)\n")

    print("① 실제로 만든 영상의 길이를 맞히는가")
    for no, ch, cuts, real in MEASURED:
        got = est(ch, cuts)
        ck(f"{no}편 {ch}자 {cuts}컷 → 잰 값 {got:.1f}초 (실제 {real}초)",
           abs(got - real) <= TOL, f"{abs(got - real):.1f}초 어긋난다")

    print("\n② 글자만이 아니라 컷 수도 재는가")
    # 같은 글자 수인데 컷이 둘 더 많으면 그만큼 길어져야 한다
    ck("컷이 늘면 잰 값도 늘어난다",
       est(220, 11) - est(220, 9) > 2.0,
       "컷마다 붙는 고정 시간(SEC_PER_CUT)이 0이면 컷을 쪼개도 안 걸린다")
    ck("story90 에 part_sec() 이 있다", hasattr(ST, "part_sec"))
    if hasattr(ST, "part_sec"):
        fake = [{"turns": [["나레이션", "가" * 40]]} for _ in range(9)]
        ck("part_sec() 이 컷 목록으로 잰다",
           abs(ST.part_sec(fake) - est(360, 9)) < 0.01)

    print("\n③ 상한이 60초 벽 안쪽에 안전분을 두는가")
    wall = getattr(S9, "PART_MAX_SEC", 59.5)
    ck(f"대본 상한({ST.PART_SEC_MAX}초)이 조립 벽({wall}초)보다 낮다",
       ST.PART_SEC_MAX < wall)
    ck(f"안전분이 {TOL}초 이상이다 (잣대 오차만큼)",
       wall - ST.PART_SEC_MAX >= TOL,
       f"지금 {wall - ST.PART_SEC_MAX:.1f}초 — 잣대가 조금만 빗나가도 60초를 넘는다")

    print("\n④ 프롬프트가 시키는 글자 수가 그 초 안에 들어가는가")
    import re
    md = (ROOT / "prompts" / "story90_gen.md").read_text(encoding="utf-8")
    m = re.search(r"글자 수 합계는 (\d+)~(\d+)자", md)
    ck("프롬프트에 글자 수 범위가 있다", bool(m))
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        # 컷 수가 가장 많을 때(가장 길어질 때)로 본다 — 여기서 안 넘어야 한다
        worst = est(hi, ST.PART_MAX_CUTS)
        ck(f"많이 썼을 때({hi}자 {ST.PART_MAX_CUTS}컷 = {worst:.0f}초)도 "
           f"상한({ST.PART_SEC_MAX}초) 안이다", worst <= ST.PART_SEC_MAX,
           "시킨 대로 썼는데 검사에서 반려된다 — 대본값 2,100원이 날아간다")
        best = est(lo, ST.PART_MIN_CUTS)
        ck(f"적게 썼을 때({lo}자 {ST.PART_MIN_CUTS}컷 = {best:.0f}초)도 "
           f"하한({ST.PART_SEC_MIN}초) 위다", best >= ST.PART_SEC_MIN,
           "시킨 대로 썼는데 '너무 짧다'로 반려된다")

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 길이 잣대: {len(bad)}군데 — 편이 짧아지거나 60초를 넘는다")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 길이 잣대: 실제와 맞고, 60초 벽 안쪽에 안전분이 있다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
