#!/usr/bin/env python3
"""대본의 모든 컷에서 인물 배치를 재어 여덟 가지 약속을 검사한다.

    python3 tools/check_place.py

  1) 전신(full_*)이 아닌 인물은 **아래끝이 무대 바닥에 닿아야** 한다.
     닿는다 = 인물의 진짜 아래끝(흰 테두리 제외)이 무대 바닥선 아래로 내려간다.
  2) 좌·우가 **절대 잘리면 안 된다.** (확대 연출이 깎는 몫까지 감안)
  3) 머리 위도 잘리면 안 된다.
  4) 자막이 얼굴을 덮으면 안 된다. (자막 띠가 있는 컷은 애초에 해당 없음)
  5) ⭐ **두 인물이 서로 겹치면 안 된다.**
  5-2) ⭐ **같은 컷에 선 두 사람의 머리 크기가 비슷해야** 한다.
  6) ⭐ **이름표가 다른 인물을 덮으면 안 된다.** (주인 본인은 덮어도 된다)
  7) ⭐ **이름표가 주인보다 남에게 더 가까이 붙으면 안 된다.**

가로(1920x1080)와 세로 쇼츠(1080x1920) 두 가지를 모두 본다.

⚠️ '바닥' 은 **화면 바닥이 아니라 무대 바닥**이다. 자막 검은 띠가 생긴 뒤로
   인물은 띠 위 무대 안에서만 논다. 화면 전체 높이로 재면 띠 높이(가로 238px)만큼
   "인물이 떠 있다" 는 헛경보가 컷마다 나온다. 실제로 그렇게 345건이 잘못 떴다.
   그래서 배치 기록(PLACE_LOG)에 적힌 무대 크기(p['W'], p['H'])로만 잰다.

⭐ 5·6번을 왜 넣었나 (손님이 화면을 캡처해 보내 확인된 실제 사고)
   · A1-03 이 아버지와 어머니를 둘 다 `pos:"left"` 로 적어, 두 사람이 **같은 자리에
     포개졌다.** 화면에는 머리가 두 겹인 어머니가 나오고 이름표는 '아버지' 였다.
   · H04 는 오른쪽에 선 차남의 이름표를 띄웠는데, 이름표가 늘 화면 왼쪽에 그려져
     **왼쪽에 선 어머니 옆에** 붙었다. 시청자에게는 어머니 = 김성훈 으로 보인다.
   둘 다 렌더링은 아무 오류 없이 끝난다. 영상을 눈으로 봐야만 드러나는 종류라
   114컷 × 2방향을 사람이 다 볼 수 없다. 기계가 재야 한다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import graphics as G  # noqa: E402
import render as R  # noqa: E402


# 같은 컷에 선 두 사람의 머리 크기 차이 한도.
# 듣는 사람을 일부러 12% 줄이므로(render.LISTEN_SCALE) 1/0.88 = 1.14 는 정상이다.
HEAD_TOL = 1.20


def overlap(a, b):
    """두 네모가 겹치는 넓이(픽셀). 안 겹치면 0."""
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if (w > 0 and h > 0) else 0


def main():
    ep = sys.argv[1] if len(sys.argv) > 1 else "EP001"
    src = ROOT / "data" / "scripts" / f"{ep}.json"
    doc = json.loads(src.read_text(encoding="utf-8"))
    R.set_cast(doc)                     # 이름표 주인을 찾으려면 배역 명단이 필요하다
    cuts = [c for a in doc["acts"] for c in a["cuts"]]

    bad_bottom, bad_side, bad_top, bad_face = [], [], [], []
    bad_overlap, bad_tag, bad_near, bad_head = [], [], [], []
    n = 0
    for W, H, vert in ((1920, 1080, False), (1080, 1920, True)):
        for i, cut in enumerate(cuts):
            if not (cut.get("chars") or []):
                continue
            R.PLACE_LOG = []
            R.build_plates(cut, W, H, vertical=vert)
            here = list(R.PLACE_LOG)
            cid = cut.get("id", f"#{i}")
            for p in here:
                n += 1
                # ⚠️ 무대 크기로 잰다 — 화면 크기가 아니다(맨 위 설명 참고).
                sw, sh = p["W"], p["H"]
                tag = f"{'세로' if vert else '가로'} {cid:6s} {p['code']}/{p['pose']}"
                # 1) 아래끝이 무대 바닥에 닿는가 (인물 아래끝 = y + h - bleed)
                if not p["pose"].startswith("full"):
                    body_bottom = p["y"] + p["h"] - p["bleed"]
                    if body_bottom < sh:
                        bad_bottom.append(f"{tag}  아래끝이 {sh - body_bottom}px 떠 있다")
                # 2) 좌우 (확대가 깎는 edge 안쪽에 들어와야 온전하다)
                #    ⚠️ 겹침을 풀며 옮긴 인물은 그림 상자가 화면 밖으로 나갈 수 있다.
                #       투명한 여백일 뿐이므로 **보이는 부분(rect)** 으로 잰다.
                r = p.get("rect") or (p["x"], p["y"], p["x"] + p["w"], p["y"] + p["h"])
                if r[0] < p["edge"] - 1 or r[2] > sw - p["edge"] + 1:
                    bad_side.append(
                        f"{tag}  좌 {r[0]} · 우 {sw - r[2]} (여유 {p['edge']} 필요)")
                # 3) 머리 위
                if r[1] < p["edge"] - 1:
                    bad_top.append(f"{tag}  위 {r[1]} (여유 {p['edge']} 필요)")
                # 4) 자막이 턱(=얼굴 아래끝)을 덮는가
                #    자막 띠가 있는 컷(sub_top=None)은 자막이 무대 밖이라 해당 없다.
                #    자막을 위로 옮긴 컷(sub_moved)도 따로 계산했으므로 뺀다.
                if p.get("sub_top") is not None and p.get("sub_moved") is None \
                        and p["y"] + p["chin"] > p["sub_top"]:
                    bad_face.append(
                        f"{tag}  자막이 턱을 {p['y'] + p['chin'] - p['sub_top']}px 덮는다")

            # 5) 두 인물이 겹치는가 — 보이는 부분(흰 테두리 포함)으로 잰다
            for a in range(len(here)):
                for b in range(a + 1, len(here)):
                    ov = overlap(here[a]["rect"], here[b]["rect"])
                    if ov > 0:
                        bad_overlap.append(
                            f"{'세로' if vert else '가로'} {cid:6s} "
                            f"{here[a]['code']} ↔ {here[b]['code']} 가 {ov:,}px² 겹친다")

            # 5-2) 같은 컷에 선 두 사람의 **머리 크기**가 비슷한가.
            #      한 사람만 크면 같은 방에 있는 것으로 안 보인다. 실제로 A1-30 에서
            #      어머니 머리가 아들 머리의 세 배로 나갔다(머리 재는 방법이 틀려서).
            #      말하는 사람이 듣는 사람보다 조금 큰 것은 일부러 넣은 연출이다.
            if len(here) == 2 and all(p.get("head") for p in here):
                hs = sorted(p["head"] for p in here)
                if hs[1] / max(1, hs[0]) > HEAD_TOL:
                    bad_head.append(
                        f"{'세로' if vert else '가로'} {cid:6s} 머리 크기가 "
                        f"{hs[1] / hs[0]:.2f}배 차이 — "
                        + " ↔ ".join(f"{p['code']} {p['head']}px" for p in here))

            # 6) 이름표가 **다른** 인물을 덮는가
            spec = cut.get("gfx") or {}
            if spec.get("type") == "nametag" and here:
                sw, sh = here[0]["W"], here[0]["H"]
                owner = R.tag_owner(spec, cut.get("chars") or [])
                align = R.nametag_align(spec, cut.get("chars") or [], here, sw, sh)
                tw, th = G.nametag_size(spec.get("text", ""), sw, sh)
                m = round(sw * G.NAMETAG_MARGIN)
                base = round(sh * (0.50 if sh > sw else 0.655))
                x0 = max(m, sw - m - tw) if align == "right" else m
                box = (x0, base - th, x0 + tw, base)
                for p in here:
                    if p["code"] == owner:
                        continue           # 자기 이름표다 — 조금 겹쳐도 헷갈리지 않는다
                    ov = overlap(box, p["rect"])
                    if ov > 0:
                        bad_tag.append(
                            f"{'세로' if vert else '가로'} {cid:6s} 이름표"
                            f"'{spec.get('text')}' 가 {p['code']} 를 {ov:,}px² 덮는다")

                # 7) 이름표가 **주인보다 남에게 더 가까이** 붙어 있지 않은가.
                #    덮지 않아도 남의 옆에 붙어 있으면 그 사람 이름으로 읽힌다 —
                #    H04 가 정확히 그랬다(오른쪽 차남의 이름표가 왼쪽 어머니 옆에).
                mine = next((p for p in here if p["code"] == owner), None)
                if mine is not None and len(here) > 1:
                    cx = (box[0] + box[2]) / 2
                    def gap_to(p):
                        return abs(cx - (p["rect"][0] + p["rect"][2]) / 2)
                    closer = [p["code"] for p in here
                              if p["code"] != owner and gap_to(p) < gap_to(mine)]
                    if closer:
                        bad_near.append(
                            f"{'세로' if vert else '가로'} {cid:6s} 이름표"
                            f"'{spec.get('text')}'({owner}) 가 {closer} 쪽에 더 가깝다")
    R.PLACE_LOG = None

    print(f"검사한 인물 배치 {n}건 ({ep})\n")
    rows_all = (("아래끝이 바닥에 안 닿음", bad_bottom),
                ("좌우 잘림", bad_side),
                ("머리 위 잘림", bad_top),
                ("자막이 얼굴을 덮음", bad_face),
                ("인물끼리 겹침", bad_overlap),
                ("머리 크기가 서로 다름", bad_head),
                ("이름표가 남을 덮음", bad_tag),
                ("이름표가 엉뚱한 사람 쪽에 붙음", bad_near))
    for name, rows in rows_all:
        print(f"■ {name}: {len(rows)}건")
        for r in rows[:20]:
            print("   " + r)
        if len(rows) > 20:
            print(f"   … 외 {len(rows) - 20}건")
    return 1 if any(rows for _n, rows in rows_all) else 0


if __name__ == "__main__":
    raise SystemExit(main())
