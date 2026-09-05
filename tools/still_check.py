#!/usr/bin/env python3
"""⭐ 컷 그림이 **엉뚱하게 나오지 않는지** 본다. 값 0원 (그림을 안 그린다).

    python3 tools/still_check.py

손님(2026-09-05, 화면 캡처와 함께)
  ① "1화에 관련 없는 등장인물의 이미지가 들어가 있어."
  ② "이미지 우측 하단에 재미난 워터마크가 살짝 보이거든?"

①의 까닭 — 사람이 없는 컷(who 가 빈 컷)인데 프롬프트가 **세 줄에 걸쳐
   사람을 그리라고 시키고** 있었다.
     SHOT:    …. Nobody's face in frame.        ← 금지형. 모델은 흘려듣는다
     FRAMING: … the person kept in the middle…  ← 사람을 가운데 두라고 시킴
     CAMERA:  … only the people are sharp…      ← 또 사람을 요구
   ⚠️ 2026-08-31 에 이 줄을 **원인으로 의심된다고 적어 놓고 미뤘다.**
      미룬 것이 그대로 다시 났다. 다시는 안 미룬다.
"""
import re
import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw, ImageFont                  # noqa: E402

import build_short90 as B                                    # noqa: E402
import wipe_mark as W                                        # noqa: E402

bad = []
# ⚠️⚠️ 2026-09-05 (두 번째) — 예전 목록은 여섯 낱말뿐이었고, 게다가 **COLOR
#    앞까지만** 봤다 ("색·화풍 줄은 사람 얘기가 아니다" 라고 적고 넘겼다).
#    바로 그 줄들이 사람을 부르고 있었다 —
#      "invented characters" · "skin tones" · "skin texture" ·
#      "body proportions" · "Korean faces"
#    → 낱말을 넓히고 **지문 전체**를 본다.
PERSON = (r"\bpersons?\b|\bpeople\b|\bfaces?\b|\bheads?\b|\bwaist\b"
          r"|\bmouths?\b|\bcharacters?\b|\bskin\b|\bbody\b|\bbodies\b"
          r"|\bfigures?\b|\bhumans?\b|\bmen\b|\bwomen\b|\bman\b|\bwoman\b")


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name
          + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def main():
    print("⭐ 컷 그림 (값 0원 — 그림을 안 그린다)\n")

    print("① 사람 없는 컷에 사람을 부르지 않는가")
    empty = B.still_prompt({"who": [], "scene": "a car is parked on a dark street"})
    hit = re.findall(PERSON, empty, re.I)    # ⚠️ 지문 **전체**를 본다
    ck("사람이라는 낱말이 지문 어디에도 안 나온다 (색·화풍 줄까지)",
       not hit, " · ".join(sorted(set(hit))))
    ck("금지형으로 적지 않는다 (Nobody's …)",
       "Nobody" not in empty and "nobody" not in empty,
       "모델은 '하지 마' 를 흘려듣고 오히려 그린다")
    ck("무엇을 그릴지 적는다", "The place itself is the subject" in empty)

    print("\n① -2 사람이 있는 컷은 그대로다 (지문이 안 바뀌어야 0원)")
    got = B.still_prompt({"who": ["아내"], "scene": "the wife sits at a table"})
    ck("사람 컷은 여전히 사람을 가운데 둔다",
       "the person kept in the middle" in got)
    ck("사람 컷은 여전히 얼굴이 또렷하다", "only the people are sharp" in got)

    print("\n① -3 화면 묘사에 사람이 있는데 안 세운 컷을 잡는가")
    # ⭐ who 가 비면 얼굴 기준 그림을 안 붙인다 → 그림 모델이 아무 얼굴이나
    #    지어낸다. 화면 묘사가 사람을 부르고 있으면 반드시 세워야 한다.
    import story90 as ST                                    # noqa: E402
    doc = {"cuts": [{"n": 1, "who": [], "say": ["담담하게"],
                     "turns": [["나레이션", "시험"]],
                     "scene": "the wife hides a small device under the seat"},
                    {"n": 2, "who": [], "say": ["담담하게"],
                     "turns": [["나레이션", "시험"]],
                     "scene": "a car is parked on a dark street at night"}],
           "people": {}}
    ST.autofix(doc)
    ck("사람이 나오는 묘사면 그 사람을 화면에 세운다",
       doc["cuts"][0]["who"] == ["아내"], str(doc["cuts"][0]["who"]))
    ck("사람이 없는 묘사는 그대로 둔다 (괜히 세우지 않는다)",
       doc["cuts"][1]["who"] == [], str(doc["cuts"][1]["who"]))
    ck("이름 짝이 맞는다 (story90.SCENE_EN ↔ build_short90.EN)",
       set(ST.SCENE_EN) == set(B.EN),
       f"{sorted(set(ST.SCENE_EN) ^ set(B.EN))}")

    print("\n② 오른쪽 아래 표시를 지우는가")
    s9 = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
    ck("그림을 만든 **뒤에** 지운다", "wipe_mark.main_dir(d)" in s9)
    ck("영상 조립이 아니라 **그림 단계**에서 지운다",
       s9.index("wipe_mark.main_dir") < s9.index("def voice_route_ok"),
       "그림에서 지워야 편 첫 장면 영상에도 안 딸려 간다")

    print("\n② -2 진짜로 지워지는가 (가짜 표시로 시험 · 0원)")
    x0, y0, x1, y1 = W.box_of(1080, 1920)
    ck(f"덮는 자리가 오른쪽 아래다 (x {x0}~{x1} · y {y0}~{y1})",
       x1 == 1080 and y1 == 1920 and x0 > 800 and y0 > 1600)
    with tempfile.TemporaryDirectory() as td:
        for nm, xy in (("모서리", (1064, 1904)), ("30px 안", (1050, 1885)),
                       ("70px 안", (1010, 1850))):
            im = Image.new("RGB", (1080, 1920), (26, 34, 30))
            d = ImageDraw.Draw(im)
            for y in range(0, 1920, 4):
                d.line((0, y, 1080, y + 12), fill=(30, 40, 34), width=2)
            try:
                fnt = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 46)
            except Exception:                                # noqa: BLE001
                fnt = ImageFont.load_default()
            d.text(xy, "AI", font=fnt, fill=(235, 235, 235), anchor="rs")
            f = Path(td) / "c01.png"
            im.save(f)
            b4 = max(Image.open(f).convert("L").crop((x0, y0, x1, y1)).getdata())
            W.wipe(f)
            o = Image.open(f).convert("L")
            af = max(o.crop((x0, y0, x1, y1)).getdata())
            ck(f"{nm}에 찍힌 표시가 사라진다 ({b4} → {af})", af < 80)
            # 경계선이 보이면 "가렸다" 가 눈에 띈다
            e1 = sum(o.crop((x0 - 6, y0 + 40, x0 - 1, y0 + 60)).getdata()) / 100
            e2 = sum(o.crop((x0 + 1, y0 + 40, x0 + 6, y0 + 60)).getdata()) / 100
            ck(f"{nm}: 경계선이 안 보인다 (밝기 차 {abs(e1 - e2):.1f})",
               abs(e1 - e2) < 8)

    # ⭐ 자막이 갈리는 것·글씨 크기가 튀는 것·나레이션 주어는
    #    tools/sub_check.py 가 본다 (여기는 **컷 그림**만 본다).

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 컷 그림: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 컷 그림: 엉뚱한 사람이 안 들어가고, 오른쪽 아래 표시가 지워진다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
