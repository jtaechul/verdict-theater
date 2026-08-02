#!/usr/bin/env python3
"""썸네일 만들기 — 판결 결과형(C).

    python3 tools/thumb_mock.py --out build/thumb

⛔ 인물 그림에 **절대 손대지 않는다**
    한 번 흰 테두리를 깎아내려다 얼굴을 망쳤다. 3.6%만 깎으려던 것이 실제로는
    10.4% 가 깎여 머리 위·턱·귀가 잘려 나갔다(실측). 손님이 "얼굴을 왜
    찌그러트렸냐"고 한 것이 이것이다.
    → 그림은 **원본 그대로** 쓴다. 아래 잘린 단면은 깎아서가 아니라
      **화면 밖으로 밀어내서** 감춘다. 모양을 건드리지 않는 방법이다.

글은 두 덩어리만
    참고 채널들의 썸네일은 예외 없이 '작은 한 줄 + 큰 두 줄' 이다.
    예전 시안은 라벨·인용·소제목·금액·결과까지 다섯 덩어리라 읽히지 않았다.

테두리
    참고 이미지 두 장 모두 화면 가장자리에 **크림색 테두리**를 두르고 있다.
    피드에서 다른 영상과 경계를 만들어 주는 장치다. 같은 방식으로 두른다.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BATANG = ROOT / "assets/fonts/KoPub_Batang_Pro_Bold.otf"
W, H = 1280, 720

INK = (12, 13, 18)
PAPER = (245, 243, 238)
GOLD = (238, 196, 104)
CREAM = (238, 226, 200)          # 바깥 테두리 — 참고 이미지의 그 색
BLOOD = (196, 44, 44)
BORDER = 13                      # 테두리 두께


def f(size):
    return ImageFont.truetype(str(BATANG), size)


def backdrop(name):
    """배경 — 흐리게, 어둡게, 왼쪽으로 갈수록 더 어둡게(글씨 자리를 비운다)."""
    p = ROOT / f"assets/bg/{name}"
    if p.exists():
        bg = Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(10))
    else:
        bg = Image.new("RGB", (W, H), (30, 32, 40))
    bg = Image.blend(bg, Image.new("RGB", (W, H), INK), 0.40)

    grad = Image.new("L", (W, 1))
    gp = grad.load()
    for x in range(W):
        t = x / (W - 1)
        gp[x, 0] = int(240 * max(0.0, 1.0 - (t / 0.72) ** 1.7))
    shade = Image.new("RGBA", (W, H), (*INK, 255))
    shade.putalpha(grad.resize((W, H), Image.BILINEAR))
    out = bg.convert("RGBA")
    out.alpha_composite(shade)
    return out


def drop_white_ring(im):
    """인물 둘레에 **인쇄된 순백 띠**만 투명하게 만든다. 모양은 안 건드린다.

    ⛔ 예전 실패 — 알파를 통째로 안쪽으로 밀었다(erode). 3.6%만 깎으려던 것이
       실제로는 10.4% 깎여 머리 위·턱·귀가 잘려 나갔다. 얼굴이 망가진다.
    ✅ 지금 방식 — **지울 픽셀을 색으로 고르되, 가장자리 근처로 한정**한다.
       ① 순백(RGB 245 이상, 세 값이 거의 같음)이고
       ② 실루엣 가장자리에서 안쪽으로 얼마 안 들어온 자리
       두 조건을 **모두** 만족하는 픽셀만 지운다.
       흰 셔츠는 ②에 걸려 안전하다 — 옷은 인물 안쪽에 있다.
       지워도 사람 모양은 그대로다. 없던 것을 없애는 것뿐이다."""
    a = im.getchannel("A")
    hard = a.point(lambda v: 255 if v > 200 else 0)
    # 가장자리 띠 = 원래 실루엣 - 안쪽으로 민 실루엣 (마스크로만 쓴다)
    w, h = im.size
    small = hard.resize((max(1, w // 4), max(1, h // 4)), Image.NEAREST)
    for _ in range(3):                                   # 넉넉히 잡아 띠를 덮는다
        small = small.filter(ImageFilter.MinFilter(9))
    inner = small.resize((w, h), Image.BILINEAR).point(lambda v: 255 if v > 128 else 0)

    import numpy as np
    arr = np.array(im)
    rgb, al = arr[..., :3].astype(int), arr[..., 3]
    ring = (np.array(inner) == 0) & (al > 8) & (rgb.min(axis=2) >= 245)
    arr[..., 3] = np.where(ring, 0, al)
    out = Image.fromarray(arr, "RGBA")
    box = out.getchannel("A").getbbox()
    return out.crop(box) if box else out


def put_person(base, code, pose, height, cx, bottom):
    """인물을 앉힌다. **모양은 원본 그대로** — 흰 띠만 벗긴다.

    bottom 이 화면 높이보다 크면 아래쪽이 화면 밖으로 나가, 잘린 단면이
    보이지 않는다."""
    p = ROOT / f"assets/char/{code}/{pose}.png"
    if not p.exists():
        print(f"  (그림 없음: {code}/{pose})")
        return
    im = Image.open(p).convert("RGBA")
    im = im.crop(im.getchannel("A").getbbox())
    im = drop_white_ring(im)
    r = height / im.height                       # 가로세로 비율 그대로
    im = im.resize((round(im.width * r), round(height)), Image.LANCZOS)
    base.alpha_composite(im, (round(cx - im.width / 2), round(bottom - im.height)))


def frame(d):
    """참고 이미지처럼 바깥에 크림색 테두리를 두른다."""
    for i in range(BORDER):
        d.rectangle((i, i, W - 1 - i, H - 1 - i), outline=CREAM)
    # 안쪽에 얇은 어두운 선을 하나 더 — 테두리가 배경에 녹지 않게 한다
    d.rectangle((BORDER, BORDER, W - 1 - BORDER, H - 1 - BORDER), outline=(40, 36, 30))


def text(d, s, xy, size, fill=PAPER, stroke=None):
    d.text(xy, s, font=f(size), fill=fill,
           stroke_width=max(5, size // 10) if stroke is None else stroke,
           stroke_fill=INK)


def build(lead, big1, big2, code, pose, bg, out):
    """lead = 작은 한 줄 / big1·big2 = 큰 두 줄. 그 이상은 넣지 않는다."""
    base = backdrop(bg)
    put_person(base, code, pose, height=800, cx=1010, bottom=H + 120)
    d = ImageDraw.Draw(base)

    text(d, lead, (62, 96), 44, fill=(226, 218, 200), stroke=5)
    d.rectangle((62, 168, 372, 174), fill=BLOOD)
    text(d, big1, (56, 404), 104, fill=GOLD)
    text(d, big2, (60, 540), 104)

    lab = f(30)
    tw = d.textlength("판결극장", font=lab)
    d.rectangle((W - tw - 74, 34, W - 38, 88), fill=(0, 0, 0))
    d.text((W - tw - 56, 48), "판결극장", font=lab, fill=GOLD)

    frame(d)
    base.convert("RGB").save(out, quality=94)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build/thumb")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if not BATANG.exists():
        print("바탕체 폰트가 없다")
        return 1
    build("어머니를 법정에 세운 장남", "1억 3,500만 원", "토해냈다",
          "M50A", "face_shock", "court_hall.jpg", out / "C1.jpg")
    build("9억을 받고도 소송했다", "장남 몫은", "0원",
          "M50A", "face_anger", "court_room.jpg", out / "C2.jpg")
    build("어머니 몫까지 요구한 장남", "법원의 답은", "달랐다",
          "M50A", "face_cold", "court_exterior.jpg", out / "C3.jpg")
    print(f"시안 3장 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
