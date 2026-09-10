#!/usr/bin/env python3
"""⭐⭐⭐ **60초 벽을 진짜로 막는가.** 값 0원 · 인터넷 0회.

    python3 tools/wall_check.py

이 채널에서 **가장 비싼 교훈**이다 (2026-09-01 실측):
    60초 이하 6편 → 전부 1,209~1,554회
    127초   1편 → **0회** (5시간 반)
공개 설정·재생 상태·쇼츠 분류는 셋 다 정상이었다. 남은 차이는 길이 하나다.

⚠️⚠️⚠️ 2026-09-10 — "절대 넘기지 않는다" 고 적어 놓고, 정작 **막는 자리가
   한 군데도 없었다.**
     · src/short90.build_part 은 다 만든 **뒤에** 글만 찍고 넘어갔다
     · 관리자 화면은 노란 글씨만 띄우고 [올리기] 단추는 살려 뒀다
     · src/upload.py 는 길이를 아예 안 봤다
   그래서 S92 2편(62.3초)·3편(64.1초)이 만들어진 채 올리기만 기다리고 있었다.
   경고는 규칙이 아니다. **되돌릴 수 없는 자리에서 막아야 규칙이다.**

여기서 보는 것
   ① 사기 전에 막는가 — 대사 영상이 편을 60초 너머로 밀면 그 컷을 덜어내는가
   ② 올리기에서 막는가 — 60초를 넘은 편은 올라가지 않는가
   ③ 화면이 누르기 전에 편 길이를 알려 주는가
   ④ 만들어 둔 편 가운데 60초를 넘은 것이 없는가
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import story90 as ST                                         # noqa: E402
import talkplan as TP                                        # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def fake(parts, cuts_per, chars_per):
    """편마다 같은 크기인 시험용 대본. 대사 컷은 편 가운데에 둔다."""
    cuts, ps, n = [], [], 0
    for k in range(parts):
        a = n + 1
        for i in range(cuts_per):
            n += 1
            who = "나레이션" if i in (0, cuts_per - 1) else "아내"
            cuts.append({"n": n, "who": [] if who == "나레이션" else ["아내"],
                         "turns": [[who, "가" * chars_per]], "say": ["담담하게"],
                         "scene": "a lamp lights an empty chair"})
        ps.append({"no": k + 1, "cuts": [a, n],
                   "card": ["가", "나"], "yt_title": "제" * 30})
    return {"sid": "S99", "parts": ps, "cuts": cuts, "people": {}}


def main():
    print("⭐ 60초 벽을 진짜로 막는가 (값 0원)\n")

    print("① 사기 전에 막는가 (대사 영상이 편을 밀어 올릴 때)")
    # 벽에 아슬아슬한 대본 — 대사 컷을 전부 영상으로 사면 반드시 넘는다
    doc = fake(2, 9, 30)
    base = TP.part_secs(doc)
    ck(f"시험 대본이 벽 아래에 있다 ({base[1]:.0f}초)",
       base[1] <= TP.PART_MAX_SEC, str(base))
    allc = TP.talk_cuts(doc)
    full = TP.part_secs(doc, [c["n"] for c in allc])
    ck(f"대사 컷을 **전부** 사면 벽을 넘는다 ({full[1]:.0f}초) — 시험이 뜻이 있다",
       full[1] > TP.PART_MAX_SEC, f"{full}  넘지 않으면 이 시험은 아무것도 안 잰다")
    keep, why = TP.fit(doc)
    got = TP.part_secs(doc, [c["n"] for c in keep])
    over = [k for k, v in got.items() if v > TP.PART_MAX_SEC]
    ck("덜어낸 뒤에는 어느 편도 벽을 안 넘는다", not over, f"{over}편이 넘는다")
    ck("무엇을 왜 덜어냈는지 알려 준다", bool(why), "조용히 덜어내면 손님이 모른다")
    # ⚠️⚠️ 여기에 `PART_MAX_SEC - TP.SAFE_MARGIN` 을 쓰면 **검사가 자기가
    #    검사할 상수를 읽는 꼴**이 된다. 안전분을 0으로 바꿔도 그대로 통과한다
    #    (2026-09-10 에 실제로 그랬다). 숫자를 여기 적어 잣대를 밖에 둔다.
    #    2.0초 근거: 대사 영상은 4·6·8초 중 하나로 **올림**되므로 컷마다
    #    예상보다 최대 2초 가까이 길어질 수 있다.
    NEED = 2.0
    ck(f"안전분이 {NEED}초 이상이다 (대사 영상은 4·6·8초로 올림된다)",
       TP.SAFE_MARGIN >= NEED, f"지금 {TP.SAFE_MARGIN}초")
    ck(f"덜어낸 뒤 가장 긴 편이 벽에서 {NEED}초 이상 떨어져 있다",
       max(got.values()) <= TP.PART_MAX_SEC - NEED + 0.01,
       f"가장 긴 편 {max(got.values()):.1f}초 · 벽 {TP.PART_MAX_SEC}초")
    ck("실제 제작도 같은 길로 간다 (short90.talk_cuts → talkplan.fit)",
       "talkplan.fit(doc)" in (ROOT / "src" / "short90.py").read_text(encoding="utf-8"),
       "화면만 지키고 제작이 안 지키면 뜻이 없다")

    print("\n② **올리기**에서 막는가 (되돌릴 수 없는 자리)")
    up = (ROOT / "src" / "upload.py").read_text(encoding="utf-8")
    ck("올리기가 편 길이를 읽는다",
       re.search(r"shortstate\.made\(", up) is not None,
       "길이를 안 보면 막을 수가 없다")
    ck("60초를 넘으면 올리지 않고 돌려보낸다",
       re.search(r"got > MAX_SHORT_SEC[\s\S]{0,400}return 2", up) is not None)
    ck("상한을 손으로 안 적는다 (talkplan.PART_MAX_SEC 를 쓴다)",
       "MAX_SHORT_SEC = talkplan.PART_MAX_SEC" in up,
       "손으로 적으면 벽이 바뀔 때 조용히 어긋난다")
    ck("그래도 올릴 길은 남긴다 (--long-ok)", "--long-ok" in up)
    import shortstate                                        # noqa: E402
    ck("shortstate 가 길이를 돌려준다", hasattr(shortstate, "made"))

    print("\n③ 화면이 **누르기 전에** 편 길이를 알려 주는가")
    js = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
    ck("만든 뒤 편 길이를 미리 적어 준다", "만들고 나면: " in js)
    ck("덜어낸 컷 수도 적어 준다", "그림으로 남깁니다" in js)
    ck("60초 벽을 말로 알려 준다", "60초 벽 안" in js)

    print("\n④ 만들어 둔 편 가운데 벽을 넘은 것이 없는가")
    st = json.loads((ROOT / "state" / "shorts.json").read_text(encoding="utf-8"))
    over2 = []
    for sid, row in st.items():
        for no, p in (row.get("parts") or {}).items():
            sec = p.get("sec")
            if sec and float(sec) > TP.PART_MAX_SEC:
                over2.append(f"{sid} {no}편 {sec}초")
    ck("60초를 넘은 편이 없다", not over2, " · ".join(over2)
       + "  ← 다시 만들거나 대본을 줄여야 한다")

    print("\n⑤ 대본 규격이 벽 안쪽에 있는가")
    for sid in ("S90", "S91", "S92"):
        f = ROOT / "data" / "series" / f"{sid}.story.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        worst = 0
        for p in d.get("parts") or []:
            a, b = p["cuts"]
            cs = [c for c in d["cuts"] if a <= c["n"] <= b]
            worst = max(worst, ST.part_sec(cs))
        ck(f"{sid} 가장 긴 편이 상한({ST.PART_SEC_MAX}초) 안이다 ({worst:.1f}초)",
           worst <= ST.PART_SEC_MAX, f"{worst:.1f}초")

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 60초 벽: {len(bad)}군데 — 넘긴 편은 조회수가 0이었다")
        for x in bad:
            print(f"     {x}")
        return 1
    print("✅ 60초 벽: 사기 전에 덜어내고 · 올리기에서 막고 · 미리 알려 준다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
