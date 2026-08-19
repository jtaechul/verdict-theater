#!/usr/bin/env python3
"""썸네일 만들기 — 판결 결과형(C).

    python3 tools/thumb_mock.py --out build/thumb

참고 채널 6곳의 썸네일에서 읽어낸 문법 (전부 지킨다)
    · 큰 글씨가 **화면 폭의 90%를 꽉 채운다.** 이것이 가장 큰 차이였다 —
      내 예전 시안은 55% 라 폰에서 작고 얌전해 보였다.
    · 흰(또는 검은) 테두리를 **아주 두껍게.** 글자 굵기의 20% 이상.
    · 인물마다 **노란 딱지**를 바로 옆에 붙인다 — (장남) (어머니).
      누가 누구인지 0.5초 안에 알아야 한다.
    · 인물은 둘 이상, **표정이 대비**되게.
    · 색을 아낀다고 얌전해지면 안 된다. 빨강·노랑을 과감히 쓴다.

우리만의 차별점
    참고 채널들은 '막장 상황' 을 판다. 우리는 **"그래서 얼마를 물어냈나"** 를 판다.
    큰 줄에 반드시 **금액**이 들어간다.

인물 그림은 원본 그대로 쓴다
    흰 테두리는 손대지 않는다(손님 확인: 싸구려로 보이지 않는다).
    아래 잘린 단면은 **화면 밖으로 밀어내** 감춘다.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BATANG = ROOT / "assets/fonts/KoPub_Batang_Pro_Bold.otf"
W, H = 1280, 720

INK = (10, 11, 16)
PAPER = (255, 255, 255)
YELLOW = (255, 216, 64)
BLOOD = (222, 46, 46)
CREAM = (240, 228, 200)
BORDER = 11
FADE_FROM = 430          # 이 줄부터 어두워지기 시작 (얼굴 아래)
FADE_TO = 572            # 이 줄부터는 완전히 어둡다 — 인물 아래 단면이 여기 잠긴다


def fit(text, target_w, lo=40, hi=190):
    """글자가 target_w 를 꽉 채우는 크기를 찾는다. 참고 이미지의 핵심."""
    best = lo
    while lo <= hi:
        mid = (lo + hi) // 2
        f = ImageFont.truetype(str(BATANG), mid)
        if ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(text, font=f) <= target_w:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return ImageFont.truetype(str(BATANG), best)


def backdrop(name):
    p = ROOT / f"assets/bg/{name}"
    if p.exists():
        bg = Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(11))
    else:
        bg = Image.new("RGB", (W, H), (30, 32, 40))
    return Image.blend(bg, Image.new("RGB", (W, H), INK), 0.42).convert("RGBA")


def person(base, code, pose, height, cx, bottom):
    """원본 그대로. bottom > H 면 아래 단면이 화면 밖으로 나간다."""
    p = ROOT / f"assets/char/{code}/{pose}.png"
    if not p.exists():
        print(f"  (그림 없음: {code}/{pose})")
        return None
    im = Image.open(p).convert("RGBA")
    im = im.crop(im.getchannel("A").getbbox())
    r = height / im.height
    im = im.resize((round(im.width * r), round(height)), Image.LANCZOS)
    x, y = round(cx - im.width / 2), round(bottom - im.height)
    base.alpha_composite(im, (x, y))
    return (x, y, im.width, im.height)


def label(d, text, cx, y):
    """인물 옆 노란 딱지 — 참고 이미지의 (남편) (내연녀) 방식."""
    f = ImageFont.truetype(str(BATANG), 52)
    t = f"({text})"
    tw = d.textlength(t, font=f)
    d.text((cx - tw / 2, y), t, font=f, fill=YELLOW,
           stroke_width=11, stroke_fill=INK)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build/thumb")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if not BATANG.exists():
        print("바탕체 폰트가 없다")
        return 1

    plans = [
        ("C1.jpg", "court_hall.jpg",
         [("F50A", "face_cry", 640, 320, 648, "어머니"),
          ("M50A", "face_anger", 680, 960, 656, "장남")],
         "어머니를 법정에 세운 장남", "1억 3,500만 원 토해냈다"),
        ("C2.jpg", "court_room.jpg",
         [("F50A", "face_sad", 640, 300, 648, "어머니"),
          ("M50A", "face_shock", 690, 970, 658, "장남")],
         "9억을 받고도 소송했다", "장남 몫은 0원이었다"),
        ("C3.jpg", "funeral_hall.jpg",
         [("M50B", "face_sad", 640, 300, 648, "차남"),
          ("M50A", "face_cold", 680, 960, 656, "장남")],
         "장례식 날 날아온 소장", "법원이 형을 멈춰세웠다"),
    ]

    for fn, bg, cast, small, big in plans:
        base = backdrop(bg)
        d0 = ImageDraw.Draw(base)
        for code, pose, h, cx, bot, name in cast:
            person(base, code, pose, h, cx, bot)
        for code, pose, h, cx, bot, name in cast:
            label(d0, name, cx, max(10, bot - h - 18))

        # 아래 글씨 자리 — **딱 끊는 판이 아니라 서서히 어두워지는 그늘**이다.
        # ⚠️ 판을 딱 끊어 깔면 그 윗선에서 인물의 잘린 아래 단면(흰 테두리)이
        #    가로줄로 드러난다. 실제로 그렇게 나왔다.
        #    그늘로 스며들게 하면 인물이 어둠 속으로 들어가 단면이 사라진다 —
        #    참고 이미지들이 쓰는 방식이다.
        grad = Image.new("L", (1, H))
        gp = grad.load()
        for yy in range(H):
            k = (yy - FADE_FROM) / max(1, FADE_TO - FADE_FROM)
            gp[0, yy] = int(250 * min(1.0, max(0.0, k)) ** 0.85)
        band = Image.new("RGBA", (W, H), (*INK, 255))
        band.putalpha(grad.resize((W, H), Image.BILINEAR))
        base.alpha_composite(band, (0, 0))
        d = ImageDraw.Draw(base)

        fs = ImageFont.truetype(str(BATANG), 46)
        tw = d.textlength(small, font=fs)
        d.text(((W - tw) / 2, H - 232), small, font=fs, fill=(252, 220, 220),
               stroke_width=8, stroke_fill=INK)

        fb = fit(big, int(W * 0.93))                       # 폭을 꽉 채운다
        tw = d.textlength(big, font=fb)
        d.text(((W - tw) / 2, H - 172), big, font=fb, fill=PAPER,
               stroke_width=max(12, fb.size // 7), stroke_fill=INK)

        lab = ImageFont.truetype(str(BATANG), 29)
        tl = d.textlength("판결극장", font=lab)
        d.rectangle((W - tl - 60, 22, W - 24, 74), fill=(0, 0, 0))
        d.text((W - tl - 42, 34), "판결극장", font=lab, fill=YELLOW)

        for i in range(BORDER):
            d.rectangle((i, i, W - 1 - i, H - 1 - i), outline=CREAM)
        base.convert("RGB").save(out / fn, quality=94)
    print(f"시안 3장 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
