#!/usr/bin/env python3
"""썸네일 시안 만들기 (제안용).

    python3 tools/thumb_mock.py --ep EP001 --out build/thumb

왜 만드나
    말로 "인물 크게, 글씨 두 줄" 이라고 해봐야 안 와닿는다. 실제 그림으로 보여
    고르게 한다. 확정되면 src/thumbnail.py 로 옮겨 자동 생성에 넣는다.

참고한 문법 (손님이 주신 예시 4장의 공통점)
    · 얼굴이 화면을 거의 다 채운다. 잘려도 된다 — 본편과 규칙이 다르다
    · 글씨는 아래 3분의 1에 두 줄. 굵은 고딕 + 두꺼운 검정 테두리
    · 핵심 낱말만 색을 바꾼다 (노랑·빨강)
    · 인물 위에 작은 관계 딱지 ("장남", "70대 어머니")
    · 채널 딱지는 오른쪽 위
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT_B = ROOT / "assets/fonts/KoPub_Dotum_Pro_Bold.otf"
FONT_M = ROOT / "assets/fonts/KoPub_Dotum_Pro_Medium.otf"
W, H = 1280, 720

INK = (16, 17, 22)
WHITE = (255, 255, 255)
GOLD = (255, 214, 64)
RED = (255, 74, 74)


def f(path, size):
    return ImageFont.truetype(str(path), size)


def sprite(code, pose):
    p = ROOT / f"assets/char/{code}/{pose}.png"
    if not p.exists():
        return None
    im = Image.open(p).convert("RGBA")
    return im.crop(im.getchannel("A").getbbox())


def place(base, im, height, cx, bottom):
    """인물을 키 height 로 맞춰 (cx, bottom) 에 앉힌다. 화면 밖은 잘려도 된다."""
    if im is None:
        return
    r = height / im.height
    im = im.resize((max(1, int(im.width * r)), int(height)), Image.LANCZOS)
    base.alpha_composite(im, (int(cx - im.width / 2), int(bottom - im.height)))


def backdrop(name, dim=0.55, blur=6):
    p = ROOT / f"assets/bg/{name}"
    if p.exists():
        bg = Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(blur))
        bg = Image.blend(bg, Image.new("RGB", (W, H), INK), dim)
    else:
        bg = Image.new("RGB", (W, H), INK)
    return bg.convert("RGBA")


def big_line(d, text, y, size, colours, cx=None, left=None, stroke=None):
    """굵은 글씨 한 줄. colours 는 {낱말: 색} — 그 낱말만 색이 바뀐다."""
    font = f(FONT_B, size)
    stroke = stroke if stroke is not None else max(6, size // 9)
    parts, buf = [], ""
    for ch in text:
        buf += ch
    # 낱말 단위로 쪼개 색을 입힌다
    chunks, rest = [], text
    while rest:
        hit = None
        for word in colours:
            i = rest.find(word)
            if i >= 0 and (hit is None or i < hit[0]):
                hit = (i, word)
        if hit is None:
            chunks.append((rest, WHITE)); break
        i, word = hit
        if i:
            chunks.append((rest[:i], WHITE))
        chunks.append((word, colours[word]))
        rest = rest[i + len(word):]
    total = sum(d.textlength(t, font=font) for t, _ in chunks)
    x = (cx - total / 2) if cx is not None else left
    for t, col in chunks:
        d.text((x, y), t, font=font, fill=col,
               stroke_width=stroke, stroke_fill=INK)
        x += d.textlength(t, font=font)
    return size


def tag(d, text, cx, y, fg=WHITE, bg=(214, 40, 40)):
    """인물 위 작은 관계 딱지."""
    font = f(FONT_B, 34)
    tw = d.textlength(text, font=font)
    pad = 16
    box = (cx - tw / 2 - pad, y, cx + tw / 2 + pad, y + 54)
    d.rounded_rectangle(box, 10, fill=bg)
    d.text((cx - tw / 2, y + 6), text, font=font, fill=fg)


def logo(d):
    font = f(FONT_B, 30)
    t = "판결극장"
    tw = d.textlength(t, font=font)
    d.rounded_rectangle((W - tw - 56, 22, W - 20, 84), 12, fill=(0, 0, 0, 190))
    d.text((W - tw - 38, 36), t, font=font, fill=GOLD)


# ── 시안 A — 대립형 (예시 2 '빨간풍선' 문법) ────────────────────────
def variant_a(out):
    base = backdrop("court_room.jpg", dim=0.6, blur=8)
    place(base, sprite("F50A", "face_cry"), 700, 250, 700)      # 왼쪽 어머니
    place(base, sprite("M50A", "face_anger"), 760, 1055, 720)   # 오른쪽 장남
    d = ImageDraw.Draw(base)
    tag(d, "어머니", 250, 40)
    tag(d, "장남", 1055, 40, bg=(30, 60, 150))
    big_line(d, "어머니를 법정에 세운", 448, 70, {"법정": GOLD}, left=36)
    big_line(d, "장남이 받은 돈 0원", 542, 84, {"0원": RED}, left=36)
    logo(d)
    base.convert("RGB").save(out, quality=92)


# ── 시안 B — 3인 구도 (예시 1·4 문법) ───────────────────────────────
def variant_b(out):
    base = backdrop("funeral_hall.jpg", dim=0.5, blur=7)
    # ⚠️ 글씨가 가운데 인물 얼굴을 가로지르지 않게, 가운데는 작고 낮게 앉힌다.
    place(base, sprite("F50A", "face_sad"), 620, 190, 470)
    place(base, sprite("M50B", "face_cold"), 480, 640, 430)
    place(base, sprite("M50A", "face_anger"), 690, 1075, 480)
    d = ImageDraw.Draw(base)
    tag(d, "어머니", 190, 28)
    tag(d, "차남", 640, 22, bg=(60, 60, 70))
    tag(d, "장남", 1075, 18, bg=(30, 60, 150))
    d.rectangle((0, 486, W, H), fill=(12, 13, 18))       # 글씨 자리를 통째로 비운다
    big_line(d, "9억 챙기고도", 508, 78, {"9억": GOLD}, cx=W // 2)
    big_line(d, "빚은 어머니에게", 606, 86, {"빚": RED}, cx=W // 2)
    logo(d)
    base.convert("RGB").save(out, quality=92)


# ── 시안 C — 판결 결과형 (우리만의 차별점) ──────────────────────────
def variant_c(out):
    base = backdrop("court_hall.jpg", dim=0.62, blur=9)
    place(base, sprite("M50A", "face_shock"), 820, 900, 740)
    d = ImageDraw.Draw(base)
    tag(d, "소송 건 장남", 900, 40, bg=(30, 60, 150))
    big_line(d, "\"법대로 하시죠\"", 120, 66, {}, left=48)
    # 판결 도장 느낌의 붉은 테두리 상자
    d.rounded_rectangle((40, 430, 720, 660), 18, outline=RED, width=10)
    big_line(d, "1억 3,500만 원", 452, 82, {"1억 3,500만 원": GOLD}, left=70)
    big_line(d, "지급하라", 556, 76, {}, left=70)
    logo(d)
    base.convert("RGB").save(out, quality=92)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build/thumb")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if not FONT_B.exists():
        print("폰트가 없다"); return 1
    variant_a(out / "A_대립형.jpg")
    variant_b(out / "B_3인구도.jpg")
    variant_c(out / "C_판결결과형.jpg")
    print(f"시안 3장 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
