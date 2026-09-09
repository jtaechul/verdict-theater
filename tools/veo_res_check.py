#!/usr/bin/env python3
"""⭐ **구글이 거절한 화질·길이 조합을 다시 고르지 않는가.** 값 0원.

    python3 tools/veo_res_check.py

⚠️⚠️⚠️ 2026-09-09 — **같은 실수를 두 번 했다.**

   2026-09-05  1080p 로 4초를 사려다 HTTP 400.
       "1080p is not supported for a duration of 4 seconds."
     그때 "그럼 6초부터는 되겠지" 하고 **짐작해서** 상수를 박았다.
   2026-09-09  대사 컷(6초)을 사려다 HTTP 400.
       "1080p is not supported for a duration of 6 seconds."
     짐작이 틀렸고, 그 사이 세 달 동안 아무도 몰랐다 — 실제로 사는 것은
     늘 4초여서 그 길로 안 갔기 때문이다.

여기서 보는 것
   ① 구글이 **실제로 거절한** 조합을 res_for() 가 다시 고르지 않는가
   ② 통과 목록에 적힌 것이 실제로 사서 확인한 것들뿐인가
   ③ 우리가 사는 길이(4·6·8초)마다 res_for() 가 답을 내는가

⚠️ 살아 있는 자료에 안 묶는다. 아래 표는 **구글이 준 오류 원문**을 그대로
   붙박이로 적어 둔 것이다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import veo                                                   # noqa: E402

# ── 붙박이: 구글이 실제로 준 답 (오류 원문 그대로) ────────────────
REJECTED = [
    (4, "1080p", "2026-09-05 · 1080p is not supported for a duration of 4 seconds."),
    (6, "1080p", "2026-09-09 · 1080p is not supported for a duration of 6 seconds."),
]
ACCEPTED = [
    (4, "720p", "2026-09-05 · 편 첫 장면 3개 성공"),
]
# Veo 가 받는 길이 (5초·7초는 HTTP 400)
OUR_SEC = (4, 6, 8)

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def main():
    print("⭐ 거절당한 화질·길이를 다시 고르지 않는가 (값 0원)\n")

    print("① 구글이 거절한 조합을 다시 고르지 않는가")
    for sec, res, note in REJECTED:
        got = veo.res_for(sec)
        ck(f"{sec}초에 {res} 를 안 고른다  ({note})", got != res,
           f"res_for({sec}) 가 {got} 를 골랐다 — 그 조합은 이미 거절당했다")

    print("\n② 통과 목록이 실제로 사서 확인한 것들인가")
    ok_1080 = veo.RES_OK.get("1080p", ())
    bad_1080 = [s for s, r, _ in REJECTED if r == "1080p" and s in ok_1080]
    ck("1080p 통과 목록에 거절당한 길이가 없다", not bad_1080,
       f"{bad_1080}초가 적혀 있다 — 실제로는 거절당한 길이다")
    for sec, res, note in ACCEPTED:
        ck(f"{sec}초 {res} 는 통과 목록에 있다  ({note})",
           sec in veo.RES_OK.get(res, ()) or res == "720p")

    print("\n③ 우리가 사는 길이마다 답이 나오는가")
    for sec in OUR_SEC:
        got = veo.res_for(sec)
        ck(f"{sec}초 → {got}", got in ("720p", "1080p"))

    print("\n④ 짐작으로 적은 상수가 남아 있지 않은가")
    src = (ROOT / "src" / "veo.py").read_text(encoding="utf-8")
    code = "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))
    ck("RES_MIN_SEC_1080 같은 '이 길이부터 된다' 짐작이 없다",
       "RES_MIN_SEC_1080" not in code,
       "한 번 거절당한 것을 보고 다음 길이를 짐작하면 또 죽는다")

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 화질·길이: {len(bad)}군데 — 구글이 거절해 영상을 못 산다")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 화질·길이: 실제로 통과한 조합만 고른다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
