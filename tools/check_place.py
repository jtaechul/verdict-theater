#!/usr/bin/env python3
"""대본의 모든 컷에서 인물 배치를 재어 두 가지 약속을 검사한다.

    python3 tools/check_place.py

  1) 전신(full_*)이 아닌 인물은 **아래끝이 화면 바닥에 닿아야** 한다.
     닿는다 = 인물의 진짜 아래끝(흰 테두리 제외)이 화면 바닥선 아래로 내려간다.
  2) 좌·우가 **절대 잘리면 안 된다.** (확대 연출이 깎는 몫까지 감안)
  3) 머리 위도 잘리면 안 된다.

가로(1920x1080)와 세로 쇼츠(1080x1920) 두 가지를 모두 본다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import render as R  # noqa: E402


def main():
    ep = sys.argv[1] if len(sys.argv) > 1 else "EP001"
    src = ROOT / "data" / "scripts" / f"{ep}.json"
    doc = json.loads(src.read_text(encoding="utf-8"))
    cuts = [c for a in doc["acts"] for c in a["cuts"]]

    bad_bottom, bad_side, bad_top, bad_face = [], [], [], []
    n = 0
    for W, H, vert in ((1920, 1080, False), (1080, 1920, True)):
        for i, cut in enumerate(cuts):
            if not (cut.get("chars") or []):
                continue
            R.PLACE_LOG = []
            R.build_plates(cut, W, H, vertical=vert)
            for p in R.PLACE_LOG:
                n += 1
                tag = (f"{'세로' if vert else '가로'} #{i:3} "
                       f"{p['code']}/{p['pose']}")
                # 1) 아래끝이 화면 바닥에 닿는가 (인물 아래끝 = y + h - bleed)
                if not p["pose"].startswith("full"):
                    body_bottom = p["y"] + p["h"] - p["bleed"]
                    if body_bottom < H:
                        bad_bottom.append(f"{tag}  아래끝이 {H - body_bottom}px 떠 있다")
                # 2) 좌우 (확대가 깎는 edge 안쪽에 들어와야 온전하다)
                if p["x"] < p["edge"] - 1 or p["x"] + p["w"] > W - p["edge"] + 1:
                    bad_side.append(
                        f"{tag}  좌 {p['x']} · 우 {W - (p['x'] + p['w'])} "
                        f"(여유 {p['edge']} 필요)")
                # 3) 머리 위
                if p["y"] < p["edge"] - 1:
                    bad_top.append(f"{tag}  위 {p['y']} (여유 {p['edge']} 필요)")
                # 4) 자막이 턱(=얼굴 아래끝)을 덮는가 (자막을 옮긴 컷은 제외)
                if p.get("sub_moved") is None and p["y"] + p["chin"] > p["sub_top"]:
                    bad_face.append(
                        f"{tag}  자막이 턱을 {p['y'] + p['chin'] - p['sub_top']}px 덮는다")
    R.PLACE_LOG = None

    print(f"검사한 인물 배치 {n}건 ({ep})\n")
    for name, rows in (("아래끝이 바닥에 안 닿음", bad_bottom),
                       ("좌우 잘림", bad_side),
                       ("머리 위 잘림", bad_top),
                       ("자막이 얼굴을 덮음", bad_face)):
        print(f"■ {name}: {len(rows)}건")
        for r in rows[:20]:
            print("   " + r)
        if len(rows) > 20:
            print(f"   … 외 {len(rows) - 20}건")
    return 1 if (bad_bottom or bad_side or bad_top or bad_face) else 0


if __name__ == "__main__":
    raise SystemExit(main())
