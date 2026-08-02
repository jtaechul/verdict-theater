#!/usr/bin/env python3
"""썸네일 만들기 — 판결 결과형(C).

    python3 tools/thumb_mock.py --out build/thumb

무엇을 파는 썸네일인가
    예시로 받은 채널들은 전부 "막장 상황" 을 판다. 우리는 **"그래서 얼마를
    물어냈나"** 를 판다. 50~60대가 궁금한 것은 사연보다 결말이고, 금액이 박힌
    썸네일은 답을 보여주면서도 눌러야 이유를 알 수 있게 만든다.

지켜야 할 것
    · **폰트는 바탕체.** 고딕은 예능처럼 보인다. 법정물은 바탕·명조가 맞는다.
    · **인물 아래 흰 선이 보이면 안 된다.** 인물 그림에는 흰 테두리(실측 52px)와
      검은 그림자(88px)가 구워져 있다. 둘 다 벗겨내고(strip_edge), 그러고도
      **화면 아래로 밀어내** 잘린 단면 자체가 안 보이게 앉힌다.
    · 얼굴은 잘려도 된다 — 본편과 규칙이 정반대다. 썸네일은 꽉 차야 한다.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BATANG = ROOT / "assets/fonts/KoPub_Batang_Pro_Bold.otf"
W, H = 1280, 720

INK = (10, 11, 16)
PAPER = (242, 240, 234)
GOLD = (233, 190, 98)
BLOOD = (188, 40, 40)

# 인물 그림에 구워진 흰 테두리 두께(그림 높이 대비). 실측 52/1445 = 3.6%.
EDGE_PCT = 0.040


def f(size):
    return ImageFont.truetype(str(BATANG), size)


def strip_edge(im, pct=EDGE_PCT):
    """흰 테두리와 검은 그림자를 벗겨 **인물만** 남긴다.

    왜 색으로 못 지우나
        인물이 흰 셔츠를 입고 있다. '흰색을 지운다' 로 하면 셔츠에 구멍이 난다.
        그래서 색이 아니라 **모양으로** 깎는다 — 알파(투명도)를 안쪽으로 민다.
    4분의 1 크기에서 깎고 되돌린다. 가장자리 처리라 그 정도로 충분하고 빠르다."""
    a = im.getchannel("A").point(lambda v: 255 if v > 200 else 0)   # 그림자부터 제거
    w, h = im.size
    small = a.resize((max(1, w // 4), max(1, h // 4)), Image.NEAREST)
    for _ in range(max(1, int(round(small.height * pct / 4)))):     # 한 번에 4px 깎임
        small = small.filter(ImageFilter.MinFilter(9))
    a2 = small.resize((w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.2))
    out = im.copy()
    out.putalpha(a2)
    box = a2.getbbox()
    return out.crop(box) if box else out


def drop_shadow(im, blur=30, alpha=175):
    """인물 뒤에 깔 부드러운 그림자. 흰 테두리 대신 배경과 떼어 놓는다."""
    a = im.getchannel("A").filter(ImageFilter.GaussianBlur(blur))
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sh.putalpha(a.point(lambda v: int(v * alpha / 255)))
    return sh


def backdrop(name):
    """배경 — 흐리게, 어둡게, 왼쪽으로 갈수록 더 어둡게(글씨 자리를 비운다)."""
    p = ROOT / f"assets/bg/{name}"
    if p.exists():
        bg = Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(9))
    else:
        bg = Image.new("RGB", (W, H), (28, 30, 38))
    bg = Image.blend(bg, Image.new("RGB", (W, H), INK), 0.42)

    grad = Image.new("L", (W, 1))
    gp = grad.load()
    for x in range(W):
        t = x / (W - 1)
        gp[x, 0] = int(238 * max(0.0, 1.0 - (t / 0.80) ** 1.6))
    shade = Image.new("RGBA", (W, H), (*INK, 255))
    shade.putalpha(grad.resize((W, H), Image.BILINEAR))
    out = bg.convert("RGBA")
    out.alpha_composite(shade)

    vg = Image.new("L", (1, H))
    vp = vg.load()
    for y in range(H):
        t = abs(y / (H - 1) - 0.5) * 2
        vp[0, y] = int(160 * max(0.0, (t - 0.55) / 0.45) ** 1.2)
    vig = Image.new("RGBA", (W, H), (*INK, 255))
    vig.putalpha(vg.resize((W, H), Image.BILINEAR))
    out.alpha_composite(vig)
    return out


def put_person(base, code, pose, height, cx, bottom):
    """인물을 앉힌다. bottom 이 H 보다 크면 아래로 잘려 **단면이 안 보인다.**"""
    p = ROOT / f"assets/char/{code}/{pose}.png"
    if not p.exists():
        print(f"  (그림 없음: {code}/{pose})")
        return
    im = Image.open(p).convert("RGBA")
    im = im.crop(im.getchannel("A").getbbox())
    im = strip_edge(im)
    r = height / im.height
    im = im.resize((max(1, int(im.width * r)), int(height)), Image.LANCZOS)
    x, y = int(cx - im.width / 2), int(bottom - im.height)
    base.alpha_composite(drop_shadow(im), (x - 12, y + 10))
    base.alpha_composite(im, (x, y))


def text(d, s, xy, size, fill=PAPER, stroke=None):
    font = f(size)
    d.text(xy, s, font=font, fill=fill,
           stroke_width=max(4, size // 12) if stroke is None else stroke,
           stroke_fill=INK)


def build(label, quote, amount, verdict, code, pose, bg, out):
    base = backdrop(bg)
    # bottom = H + 110 → 인물의 잘린 아래 단면이 화면 밖으로 나간다
    put_person(base, code, pose, height=780, cx=1000, bottom=H + 110)
    d = ImageDraw.Draw(base)

    d.rectangle((44, 92, 50, 236), fill=GOLD)          # 왼쪽 금색 세로선
    text(d, label, (72, 96), 33, fill=(206, 202, 192), stroke=4)
    text(d, f"“{quote}”", (66, 146), 64)

    d.rectangle((44, 392, 700, 399), fill=BLOOD)       # 판결 구분선
    text(d, "법원의 답", (70, 420), 35, fill=(208, 124, 124), stroke=4)
    text(d, amount, (62, 470), 100, fill=GOLD)
    text(d, verdict, (68, 596), 62)

    lab = f(29)                                        # 채널 딱지
    tw = d.textlength("판결극장", font=lab)
    d.rectangle((W - tw - 54, 22, W - 22, 74), fill=(0, 0, 0))
    d.rectangle((W - tw - 54, 22, W - 22, 26), fill=GOLD)
    d.text((W - tw - 38, 36), "판결극장", font=lab, fill=GOLD)

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
    build("어머니를 법정에 세운 장남", "법대로 하시죠", "1억 3,500만 원",
          "장남이 물어냈다", "M50A", "face_shock", "court_hall.jpg", out / "C1.jpg")
    build("9억을 받고도 소송한 장남", "제 몫이 비잖아요", "1억 3,500만 원",
          "돌려주라", "M50A", "face_anger", "court_room.jpg", out / "C2.jpg")
    build("어머니 몫까지 요구한 장남", "당연히 내 지분이지", "지분 0원",
          "법원이 답했다", "M50A", "face_cold", "court_exterior.jpg", out / "C3.jpg")
    print(f"시안 3장 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
