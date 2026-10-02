#!/usr/bin/env python3
"""그림 컷 — 관계도 · 연표 · 쟁점 · 서류 vs 실제 · 돈 · 판결 정리를 **직접 그려** 영상으로 (값 0원)

⭐⭐⭐ 2026-10-02 손님:
    "영상 안에 인물 관계도를 넣고 요거를 좀 설명하는 나레이션을 만드는 거는 돈을 안 드리고
     네가 별도로 할 수 있지 않나? … 모식도 애니메이션 또는 관계도 애니메이션을 만들어서 넣어주면"
    "글씨도 좀 키워주고 … 글이 조금 많은 재판의 쟁점이라던가 서류와 실제, 판결 정리 같은 경우는
     글을 조금 더 쉽게 적어도 아니면 그림으로 표현해도 괜찮아"

어떻게 도나
    · 대본 컷에 fig = {"id": 그림 이름, "add": [[요소, 신호 낱말], …]} 가 있으면 그림 컷이다.
      요소는 **그 낱말을 말하는 순간** 나타난다 (나레이션 글자 위치 ÷ 전체 글자 × 말 길이).
      신호 낱말이 비면 컷 첫머리에 차례로 나타난다.
    · 같은 그림을 쓰는 앞 컷에서 나온 요소는 처음부터 보인다 — 컷이 바뀌어도 그림이 이어진다.
    · 그림 설계(누가 어디 · 무슨 글)는 대본의 figs[id] = {"type": …, "bg": 창고 영상 번호}.
      글자 크기는 어르신 눈에 맞춰 크게 (이름 50px 안팎 · 작은 글도 30px 넘게).
    · 그림은 2배로 그려 줄인다(테두리가 매끈하다). 요소마다 한 번만 그리고, 프레임은 붙이기만 한다.
    · 자막(1300~1620)과 쇼츠 단추 자리(아래 300px)는 비운다 — 그림은 위쪽 180~1250 에 앉힌다.
"""
import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

import short90 as S9

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS = S9.W, S9.H, S9.FPS
SS = 2                                  # 두 배로 그려 줄인다
FD = ROOT / "assets" / "fonts"
F_NAME = FD / "KoPub_Batang_Pro_Bold.otf"
F_NAME_M = FD / "KoPub_Batang_Pro_Medium.otf"
F_UI = FD / "KoPub_Dotum_Pro_Medium.otf"
F_UI_B = FD / "KoPub_Dotum_Pro_Bold.otf"

GOLD, GOLD_B = (198, 160, 74), (232, 197, 112)
INK, MUTE, SOFT = (246, 243, 236), (186, 190, 199), (222, 217, 206)
LINE, RED, PANEL, CARD = (200, 195, 184), (230, 98, 84), (14, 18, 26), (24, 29, 40)
GREY = (150, 155, 166)

APPEAR = 0.42                           # 나타나는 데 걸리는 시간(초)
STAGGER = 0.14                          # 신호 낱말이 없는 요소들은 이만큼씩 차례로
LEAD = 0.08                             # 낱말보다 살짝 먼저 (눈이 귀보다 느리다)


# ── 그리기 바탕 ────────────────────────────────────────────────────
def font(p, size):
    return ImageFont.truetype(str(p), int(size * SS))


def P(*v):
    return tuple(int(round(x * SS)) for x in v)


def canvas():
    return Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))


def tw(s, size, f=F_NAME):
    return ImageDraw.Draw(Image.new("RGB", (4, 4))).textlength(s, font=font(f, size)) / SS


def text(im, x, y, s, size, color=INK, f=F_NAME, anchor="la", stroke=2, alpha=255):
    ImageDraw.Draw(im).text((x * SS, y * SS), s, font=font(f, size), fill=color + (alpha,),
                            anchor=anchor, stroke_width=int(stroke * SS),
                            stroke_fill=(0, 0, 0, 175))


def line(im, p, q, color, width=5, dash=None, alpha=240):
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    (x1, y1), (x2, y2) = p, q
    n = math.hypot(x2 - x1, y2 - y1) or 1
    if not dash:
        d.line(P(x1, y1, x2, y2), fill=color + (alpha,), width=int(width * SS))
        for x, y in (p, q):
            d.ellipse(P(x - width / 2, y - width / 2, x + width / 2, y + width / 2),
                      fill=color + (alpha,))
    else:
        on, off = dash
        t = 0.0
        while t < n:
            a, b = t / n, min(n, t + on) / n
            d.line(P(x1 + (x2 - x1) * a, y1 + (y2 - y1) * a,
                     x1 + (x2 - x1) * b, y1 + (y2 - y1) * b),
                   fill=color + (alpha,), width=int(width * SS))
            t += on + off
    im.alpha_composite(lay)


def arrow(im, p, q, color, width=6, head=26):
    (x1, y1), (x2, y2) = p, q
    n = math.hypot(x2 - x1, y2 - y1)
    ux, uy = (x2 - x1) / n, (y2 - y1) / n
    line(im, p, (x2 - ux * head * 0.8, y2 - uy * head * 0.8), color, width)
    ImageDraw.Draw(im).polygon(
        [P(x2, y2), P(x2 - ux * head - uy * head * 0.6, y2 - uy * head + ux * head * 0.6),
         P(x2 - ux * head + uy * head * 0.6, y2 - uy * head - ux * head * 0.6)],
        fill=color + (245,))


def chip(im, cx, cy, s, color=GOLD_B, size=34, solid=False, tcolor=None, f=F_UI_B):
    w = tw(s, size, f) + 40
    h = size + 24
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).rounded_rectangle(P(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                                          radius=int(h / 2 * SS),
                                          fill=(color + (245,)) if solid else (PANEL + (230,)),
                                          outline=color + (255,), width=int(3 * SS))
    im.alpha_composite(lay)
    text(im, cx, cy + 1, s, size, tcolor or (PANEL if solid else color), f, anchor="mm",
         stroke=0)
    return w


def box(im, x1, y1, x2, y2, outline=LINE, fill=CARD, alpha=228, width=3, dash=None, r=24):
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).rounded_rectangle(P(x1, y1, x2, y2), radius=int(r * SS),
                                          fill=fill + (alpha,),
                                          outline=None if dash else outline + (255,),
                                          width=int(width * SS))
    im.alpha_composite(lay)
    if dash:
        for a, b in (((x1 + r, y1), (x2 - r, y1)), ((x1 + r, y2), (x2 - r, y2)),
                     ((x1, y1 + r), (x1, y2 - r)), ((x2, y1 + r), (x2, y2 - r))):
            line(im, a, b, outline, width, dash=dash)


def cross(im, cx, cy, k=40, color=RED, width=14):
    line(im, (cx - k, cy - k), (cx + k, cy + k), color, width)
    line(im, (cx - k, cy + k), (cx + k, cy - k), color, width)


def wrap(s, size, f, width):
    out, cur = [], ""
    for w in s.split(" "):
        t = (cur + " " + w).strip()
        if tw(t, size, f) <= width:
            cur = t
        else:
            if cur:
                out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out


def para(im, x, y, s, size, width, color=INK, f=F_UI, gap=1.34, anchor="la"):
    lines = wrap(s, size, f, width)
    for i, ln in enumerate(lines):
        text(im, x, y + i * size * gap, ln, size, color, f, anchor=anchor)
    return y + len(lines) * size * gap


def heading(im, s, y=196):
    w = tw(s, 50)
    text(im, 540, y, s, 50, GOLD_B, F_NAME, anchor="mm")
    for sg in (-1, 1):
        line(im, (540 + sg * (w / 2 + 24), y), (540 + sg * (w / 2 + 136), y), GOLD, 3, alpha=210)


# ── 사람 ────────────────────────────────────────────────────────────
def disc(r):
    m = Image.new("L", (2 * r * SS, 2 * r * SS), 0)
    ImageDraw.Draw(m).ellipse([0, 0, 2 * r * SS - 1, 2 * r * SS - 1], fill=255)
    return m


def shadow(im, cx, cy, r, alpha=150):
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).ellipse(P(cx - r - 8, cy - r + 4, cx + r + 8, cy + r + 20),
                                fill=(0, 0, 0, alpha))
    im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(16 * SS)))


def glow(im, cx, cy, r, color=GOLD_B, alpha=170, grow=26):
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).ellipse(P(cx - r - grow, cy - r - grow, cx + r + grow, cy + r + grow),
                                fill=color + (alpha,))
    im.alpha_composite(lay.filter(ImageFilter.GaussianBlur(20 * SS)))


_FACES = {}


def face_img(role):
    """인물 카드(시트에서 자른 것)의 얼굴 — 카드가 없으면(깃허브 자체 점검 등) 윤곽 그림."""
    if role not in _FACES:
        f = S9.cards_dir() / f"{role}.png"
        if not f.exists():
            t = Image.new("RGB", (400, 400), (40, 44, 54))
            d = ImageDraw.Draw(t)
            d.ellipse([136, 72, 264, 200], fill=(100, 106, 120))
            d.ellipse([64, 224, 336, 480], fill=(100, 106, 120))
            _FACES[role] = t
            return t
        card = Image.open(f).convert("RGB")
        w, h = card.size
        fx, fy, side = w * 0.5, h * 0.155, w * 0.50
        _FACES[role] = card.crop((int(fx - side / 2), int(fy - side / 2),
                                  int(fx + side / 2), int(fy + side / 2)))
    return _FACES[role]


def person(im, role, cx, cy, r, ring=(228, 224, 216), dim=1.0):
    pic = face_img(role).resize((2 * r * SS, 2 * r * SS), Image.LANCZOS).convert("RGBA")
    if dim < 1.0:
        pic = Image.blend(pic, Image.new("RGBA", pic.size, (12, 15, 22, 255)), 1 - dim)
    shadow(im, cx, cy, r)
    im.paste(pic, P(cx - r, cy - r), disc(r))
    ImageDraw.Draw(im).ellipse(P(cx - r, cy - r, cx + r, cy + r), outline=ring + (255,),
                               width=int(6 * SS))


def ghost(im, cx, cy, r, ring=GREY, dash=False):
    """사진이 없는 사람(고인) — 윤곽만."""
    shadow(im, cx, cy, r, alpha=120)
    s = 2 * r * SS
    t = Image.new("RGBA", (s, s), (40, 44, 54, 255))
    d = ImageDraw.Draw(t)
    d.ellipse([s * 0.34, s * 0.18, s * 0.66, s * 0.50], fill=(100, 106, 120, 255))
    d.ellipse([s * 0.16, s * 0.56, s * 0.84, s * 1.20], fill=(100, 106, 120, 255))
    im.paste(t, P(cx - r, cy - r), disc(r))
    if dash:
        n = 28
        for k in range(n):
            if k % 2:
                continue
            a0, a1 = 360 * k / n, 360 * (k + 1) / n
            ImageDraw.Draw(im).arc(P(cx - r, cy - r, cx + r, cy + r), a0, a1,
                                   fill=ring + (255,), width=int(6 * SS))
    else:
        ImageDraw.Draw(im).ellipse(P(cx - r, cy - r, cx + r, cy + r), outline=ring + (255,),
                                   width=int(5 * SS))


def nametag(im, cx, y, name, role=None, color=INK, size=48):
    """「윤정숙 (딸)」 — 이름이 먼저, 괄호에 관계 (손님 확정 · 2026-10-02)."""
    rsize = int(size * 0.76)
    wn = tw(name, size)
    wr = tw(f" ({role})", rsize, F_NAME_M) if role else 0
    x0 = cx - (wn + wr) / 2
    text(im, x0, y, name, size, color)
    if role:
        text(im, x0 + wn, y + (size - rsize) * 0.8, f" ({role})", rsize, SOFT, F_NAME_M)
    return y + size + 10


def grave_icon(im, cx, cy, s=1.0, color=GOLD_B):
    """봉분 + 상석 (묘)."""
    d = ImageDraw.Draw(im)
    d.pieslice(P(cx - 46 * s, cy - 34 * s, cx + 46 * s, cy + 34 * s), 180, 360,
               fill=color + (255,))
    d.rectangle(P(cx - 30 * s, cy + 2 * s, cx + 30 * s, cy + 10 * s), fill=color + (255,))
    d.rectangle(P(cx - 20 * s, cy + 10 * s, cx - 14 * s, cy + 22 * s), fill=color + (255,))
    d.rectangle(P(cx + 14 * s, cy + 10 * s, cx + 20 * s, cy + 22 * s), fill=color + (255,))


def table_icon(im, cx, cy, s=1.0, color=GOLD_B):
    """제사상 — 낮은 상 + 초 두 자루."""
    d = ImageDraw.Draw(im)
    d.rectangle(P(cx - 50 * s, cy - 2 * s, cx + 50 * s, cy + 8 * s), fill=color + (255,))
    for x in (-40, 34):
        d.rectangle(P(cx + x * s, cy + 8 * s, cx + (x + 6) * s, cy + 30 * s), fill=color + (255,))
    for x in (-24, 18):
        d.rectangle(P(cx + x * s, cy - 34 * s, cx + (x + 7) * s, cy - 2 * s), fill=INK + (255,))
        d.ellipse(P(cx + (x - 1) * s, cy - 48 * s, cx + (x + 8) * s, cy - 34 * s),
                  fill=(255, 196, 92, 255))


def ring_glow(im, cx, cy, r, color=RED):
    """얼굴은 그대로 두고 둘레만 빛나게 (붉은 고리 + 번진 빛 · 안쪽은 비운다)."""
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(lay).ellipse(P(cx - r - 16, cy - r - 16, cx + r + 16, cy + r + 16),
                                outline=color + (230,), width=int(22 * SS))
    lay = lay.filter(ImageFilter.GaussianBlur(10 * SS))
    hole = Image.new("L", im.size, 0)
    ImageDraw.Draw(hole).ellipse(P(cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2), fill=255)
    lay.putalpha(ImageChops.subtract(lay.getchannel("A"), hole))
    im.alpha_composite(lay)
    ImageDraw.Draw(im).ellipse(P(cx - r - 5, cy - r - 5, cx + r + 5, cy + r + 5),
                               outline=color + (255,), width=int(8 * SS))


def badge(im, cx, cy, r=38):
    shadow(im, cx, cy, r, alpha=110)
    ImageDraw.Draw(im).ellipse(P(cx - r, cy - r, cx + r, cy + r), fill=GOLD_B + (255,),
                               outline=(255, 238, 200, 255), width=int(3 * SS))
    grave_icon(im, cx, cy + 4, s=0.52, color=PANEL)


# ── 요소 ────────────────────────────────────────────────────────────
class El:
    """그림 한 조각 — 1배 크기로 잘라 둔 그림(sprite)과 자리."""

    def __init__(self, name, draw, anim="pop", replaces=(), pulse=False, wipe=None):
        self.name, self.draw, self.anim = name, draw, anim
        self.replaces, self.pulse, self.wipe = tuple(replaces), pulse, wipe
        self.sprite, self.xy = None, (0, 0)

    def build(self):
        im = canvas()
        self.draw(im)
        im = im.resize((W, H), Image.LANCZOS)
        bb = im.getbbox() or (0, 0, 1, 1)
        self.sprite, self.xy = im.crop(bb), (bb[0], bb[1])
        return self


def frame_of(el, k, t):
    """나타나는 중(k 0→1)인 요소 그림과 자리."""
    sp, (x, y) = el.sprite, el.xy
    e = 1 - (1 - k) ** 3                                   # 천천히 멈춘다
    if el.pulse:
        e *= 0.62 + 0.38 * (0.5 + 0.5 * math.sin(t * 2 * math.pi * 0.9))
    if el.anim == "wipe" and el.wipe and k < 1:
        (x1, y1), (x2, y2) = el.wipe
        n = math.hypot(x2 - x1, y2 - y1) or 1
        ux, uy = (x2 - x1) / n, (y2 - y1) / n
        cut = e * n
        m = Image.new("L", sp.size, 0)
        # 시작점에서 cut 만큼까지의 반평면 (스프라이트 자리 기준)
        bx, by = x1 - x + ux * cut, y1 - y + uy * cut
        big = 4000
        px, py = -uy, ux
        ImageDraw.Draw(m).polygon([(bx + px * big, by + py * big),
                                   (bx - px * big, by - py * big),
                                   (bx - px * big - ux * big, by - py * big - uy * big),
                                   (bx + px * big - ux * big, by + py * big - uy * big)],
                                  fill=255)
        sp = sp.copy()
        sp.putalpha(ImageChops.multiply(sp.getchannel("A"), m))
        return sp, (x, y)
    if el.anim == "pop" and k < 1:
        sc = 0.86 + 0.14 * (1 + 2.2 * (e - 1) ** 3 + 1.2 * (e - 1) ** 2)
        sw, sh = max(1, int(sp.width * sc)), max(1, int(sp.height * sc))
        sp = sp.resize((sw, sh), Image.BILINEAR)
        x, y = x + (el.sprite.width - sw) // 2, y + (el.sprite.height - sh) // 2
    if e < 0.999:
        sp = sp.copy()
        sp.putalpha(sp.getchannel("A").point(lambda v: int(v * e)))
    return sp, (x, y)


# ── 그림 설계 ───────────────────────────────────────────────────────
def labels(doc):
    """{관계 이름: (가명, 이름표 관계)} — 대본 인물표에서."""
    out = {}
    for p in doc.get("cast") or []:
        out[str(p.get("name"))] = (str(p.get("alias") or p.get("name")),
                                   str(p.get("tag") or p.get("name")))
    return out


def fig_card(doc, spec):
    def card(im):
        line(im, (330, 760), (750, 760), GOLD, 3, alpha=200)
        text(im, 540, 880, spec.get("text") or "", 124, GOLD_B, F_NAME, anchor="mm", stroke=3)
        if spec.get("sub"):
            text(im, 540, 1010, spec["sub"], 48, SOFT, F_UI, anchor="mm")
        line(im, (330, 1080), (750, 1080), GOLD, 3, alpha=200)
    return [El("card", card, anim="fade")]


def fig_family(doc, spec):
    L = labels(doc)
    jn, jt = L.get("딸", ("딸", "딸"))
    gn, gt = L.get("이복동생", ("이복동생", "이복동생"))
    on, _ot = L.get("새어머니", ("새어머니", "새어머니"))
    F, M, O, C1, C2 = (540, 400), (235, 660), (845, 660), (235, 1010), (845, 1010)
    rF, rM, rO, rC = 78, 92, 104, 112

    def edge(a, b, ra, rb, pad=12):
        (x1, y1), (x2, y2) = a, b
        n = math.hypot(x2 - x1, y2 - y1)
        ux, uy = (x2 - x1) / n, (y2 - y1) / n
        return (x1 + ux * (ra + pad), y1 + uy * (ra + pad)), (x2 - ux * (rb + pad), y2 - uy * (rb + pad))

    fm = edge(F, M, rF, rM)
    fo = edge(F, O, rF, rO)
    m1 = ((M[0], M[1] + rM + 14 + 58), (C1[0], C1[1] - rC - 12))
    o2 = ((O[0], O[1] + rO + 14 + 58), (C2[0], C2[1] - rC - 12))
    pp = edge(C2, M, rC, rM, pad=14)
    sib = ((C1[0] + rC + 14, C1[1]), (C2[0] - rC - 14, C2[1]))
    t = 0.38
    chip_xy = (pp[0][0] + (pp[1][0] - pp[0][0]) * t, pp[0][1] + (pp[1][1] - pp[0][1]) * t)

    def legend(im):
        line(im, (205, 262), (262, 262), LINE, 5)
        text(im, 276, 262, "실제 관계", 32, MUTE, F_UI, anchor="lm")
        line(im, (532, 262), (590, 262), GOLD_B, 6, dash=(14, 9))
        text(im, 604, 262, "서류(호적)상 관계", 32, MUTE, F_UI, anchor="lm")

    def claim1(im):
        chip(im, 300, 262, "땅주인 주장 ①", RED, 32)
        text(im, 430, 262, "제사는 아들이 → 권리는 윤기철", 34, INK, F_UI_B, anchor="lm")

    return [
        El("heading", lambda im: heading(im, "인물 관계도"), anim="fade"),
        El("legend", legend, anim="fade"),
        El("line_fm", lambda im: (line(im, *fm, LINE, 5),
                                  text(im, 350, 506, "부부", 36, SOFT, F_UI, anchor="mm")),
           anim="wipe", wipe=fm),
        El("line_fo", lambda im: line(im, *fo, LINE, 5), anim="wipe", wipe=fo),
        El("rel_fo", lambda im: text(im, 740, 506, "내연 관계", 36, SOFT, F_UI, anchor="mm"),
           anim="fade"),
        El("line_m1", lambda im: line(im, *m1, LINE, 5), anim="wipe", wipe=m1),
        El("line_o2", lambda im: line(im, *o2, LINE, 5), anim="wipe", wipe=o2),
        El("paper", lambda im: (line(im, *pp, GOLD_B, 7, dash=(24, 14)),
                                chip(im, chip_xy[0] + 6, chip_xy[1], "서류상: 본처의 아들",
                                     GOLD_B, 34)),
           anim="wipe", wipe=pp),
        El("sibling", lambda im: (line(im, *sib, GOLD_B, 6, dash=(18, 12)),
                                  chip(im, 540, C1[1], "서류상 친동생", GOLD_B, 32)), anim="fade"),
        El("father", lambda im: (ghost(im, *F, rF), text(im, F[0] + rF + 24, F[1], "아버지", 52,
                                                          INK, anchor="lm"))),
        El("mother", lambda im: (ghost(im, *M, rM),
                                 nametag(im, M[0], M[1] + rM + 14, "어머니", "본처"))),
        El("other", lambda im: person(im, "새어머니", *O, rO)),
        El("other_label", lambda im: nametag(im, O[0], O[1] + rO + 14, on, "내연녀"),
           anim="fade"),
        El("child1", lambda im: (person(im, "딸", *C1, rC, ring=GOLD_B),
                                 nametag(im, C1[0], C1[1] + rC + 14, jn, jt, color=GOLD_B))),
        El("child2", lambda im: (person(im, "이복동생", *C2, rC),
                                 nametag(im, C2[0], C2[1] + rC + 14, gn, gt, size=44))),
        El("mother_gone", lambda im: chip(im, M[0], M[1] + rM - 20, "1969 별세", GREY, 30,
                                          solid=True, tcolor=PANEL), anim="fade"),
        El("grave", lambda im: (badge(im, 92, M[1] - rM - 12),
                                text(im, 92, M[1] - rM + 40, "산에 묘", 30, GOLD_B,
                                     F_UI_B, anchor="ma"))),
        El("remarry", lambda im: text(im, 740, 506, "1973년 재혼", 36, GOLD_B, F_UI_B,
                                      anchor="mm"), anim="fade", replaces=("rel_fo",)),
        El("other_new", lambda im: nametag(im, O[0], O[1] + rO + 14, on, "새어머니"),
           anim="fade", replaces=("other_label",)),
        El("claim1", claim1, anim="fade", replaces=("legend",)),
        El("claim1_glow", lambda im: ring_glow(im, *C2, rC, RED), anim="fade", pulse=True),
    ]


def fig_timeline(doc, spec):
    X = 170
    rows = {
        "r1969": (330, "1969", "어머니 별세", "아버지의 산에 묘", GOLD_B, SOFT),
        "r1996": (470, "1996", "아버지 → 윤기철", "산을 물려줌", GOLD_B, SOFT),
        "r2006a": (610, "2006.6", "윤기철 → 다른 사람", "산을 팖 (아버지 별세 두 달 전)", GOLD_B, SOFT),
        "r2006b": (750, "2006.8", "아버지 별세 · 한옥자 → 윤정숙", "세 번에 걸쳐 1억 5천만 원",
                   GOLD_B, GOLD_B),
        "r2008": (1090, "2008", "오병철 씨 등 → 산을 삼", "소송을 낸 땅주인", GOLD_B, SOFT),
    }

    def row(key):
        y, yr, who, what, cc, wc = rows[key]

        def draw(im):
            chip(im, X, y, yr, cc, 30)
            text(im, 262, y - 30, who, 42, INK)
            text(im, 262, y + 24, what, 34, wc, F_UI)
        return draw

    def card(im):
        box(im, 262, 835, 1010, 1010, outline=GOLD_B, dash=(16, 10))
        text(im, 292, 868, "확인서", 32, GOLD_B, F_UI_B)
        para(im, 292, 914, "'한옥자, 윤기철 모자와 법적으로 다투지 않는다'", 36, 690, INK, F_UI_B)

    els = [El("heading", lambda im: (heading(im, "산과 돈, 일어난 순서"),
                                     line(im, (X, 300), (X, 1180), LINE, 4, alpha=170)),
              anim="fade")]
    els += [El(k, row(k), anim="fade") for k in ("r1969", "r1996", "r2006a", "r2006b")]
    els += [El("card", card), El("r2008", row("r2008"), anim="fade"),
            El("owner", lambda im: person(im, "땅주인", 960, 1090, 56))]
    return els


def fig_issue(doc, spec):
    L = labels(doc)
    on_, ot_ = L.get("땅주인", ("땅주인", "땅주인"))
    jn, jt = L.get("딸", ("딸", "딸"))
    gn, _gt = L.get("이복동생", ("이복동생", "이복동생"))
    A, B = (210, 345), (870, 345)

    def suit(im):
        person(im, "땅주인", *A, 74)
        person(im, "딸", *B, 74, ring=GOLD_B)
        nametag(im, A[0], A[1] + 88, on_, ot_, size=38)
        nametag(im, B[0], B[1] + 88, jn, jt, size=38, color=GOLD_B)
        arrow(im, (300, 345), (782, 345), RED, 7, head=30)
        text(im, 541, 300, "\"묘를 파내 달라\"", 38, INK, F_UI_B, anchor="mm")
        text(im, 541, 392, "2011년 소송", 32, RED, F_UI_B, anchor="mm")

    def rule(im):
        box(im, 70, 520, 1010, 760, outline=GOLD_B)
        grave_icon(im, 170, 600, s=0.95)
        text(im, 250, 600, "묘를 지킬 권리는", 42, INK, F_UI_B, anchor="lm")
        table_icon(im, 170, 696, s=0.95)
        text(im, 250, 692, "제사를 모시는 사람에게", 46, GOLD_B, F_NAME, anchor="lm")

    def question(im):
        text(im, 540, 838, "어머니 제사를 모실 사람은?", 54, INK, F_NAME, anchor="mm", stroke=3)

    def cands(im):
        person(im, "이복동생", 300, 1010, 108)
        person(im, "딸", 780, 1010, 108, ring=GOLD_B)
        text(im, 540, 1010, "vs", 52, MUTE, F_NAME, anchor="mm")
        nametag(im, 300, 1132, gn, "호적상 아들", size=42)
        nametag(im, 780, 1132, jn, "친딸", size=42, color=GOLD_B)

    return [El("heading", lambda im: heading(im, "재판의 쟁점"), anim="fade"),
            El("suit", suit, anim="fade"), El("rule", rule), El("question", question),
            El("cands", cands),
            El("claim_no", lambda im: chip(im, 780, 1238, "땅주인: 윤정숙 씨는 아니다", RED, 32)),
            El("two", lambda im: None)]


def fig_money(doc, spec):
    L = labels(doc)
    hn, ht = L.get("새어머니", ("새어머니", "새어머니"))
    jn, jt = L.get("딸", ("딸", "딸"))
    A, B = (215, 390), (865, 390)

    def people(im):
        person(im, "새어머니", *A, 100)
        person(im, "딸", *B, 100, ring=GOLD_B)
        nametag(im, A[0], A[1] + 114, hn, ht, size=42)
        nametag(im, B[0], B[1] + 114, jn, jt, size=42, color=GOLD_B)

    def flow(im):
        arrow(im, (330, 390), (750, 390), GOLD_B, 8, head=32)
        text(im, 540, 338, "1억 5천만 원", 52, GOLD_B, F_NAME, anchor="mm", stroke=3)
        text(im, 540, 440, "세 번에 나눠", 32, SOFT, F_UI, anchor="mm")

    def claim(im):
        box(im, 70, 610, 1010, 800, outline=RED)
        chip(im, 210, 652, "땅주인 주장", RED, 32)
        text(im, 110, 730, "묘를 포기한 대가였다", 48, INK, F_NAME)

    def docu(im):
        box(im, 70, 840, 1010, 1040, outline=GOLD_B)
        chip(im, 180, 882, "확인서", GOLD_B, 32)
        para(im, 110, 930, "한옥자·윤기철 모자와 법적으로 다투지 않는다", 40, 860, INK, F_UI_B)

    return [El("heading", lambda im: heading(im, "1억 5천만 원"), anim="fade"),
            El("people", people, anim="fade"), El("flow", flow, anim="fade"),
            El("claim", claim), El("doc", docu),
            El("nograve", lambda im: chip(im, 790, 1092, "묘 이야기 없음", GOLD_B, 34,
                                          solid=True)),
            El("cross", lambda im: cross(im, 940, 705, k=46, width=15)),
            El("testimony", lambda im: chip(im, 290, 1092, "증언도 못 믿는다", RED, 34))]


def fig_paper(doc, spec):
    L = labels(doc)
    gn, _gt = L.get("이복동생", ("이복동생", "이복동생"))
    hn, _ht = L.get("새어머니", ("새어머니", "새어머니"))
    jn, _jt = L.get("딸", ("딸", "딸"))
    S_, A, B = (540, 370), (255, 790), (825, 790)
    pl = ((S_[0] - 70, S_[1] + 90), (A[0] + 60, A[1] - 110))
    rl = ((S_[0] + 70, S_[1] + 90), (B[0] - 60, B[1] - 110))

    def son(im):
        person(im, "이복동생", *S_, 104)
        nametag(im, S_[0], S_[1] + 118, gn, None, size=46)

    def slots(im):
        ghost(im, *A, 100, ring=GOLD_B, dash=True)
        person(im, "새어머니", *B, 100)
        chip(im, A[0], A[1] + 140, "서류상 엄마", GOLD_B, 34)
        chip(im, B[0], B[1] + 140, "진짜 엄마", INK, 34)
        text(im, A[0], A[1] + 186, f"{jn} 씨 어머니", 36, SOFT, F_UI_B, anchor="ma")
        text(im, B[0], B[1] + 186, hn, 40, INK, F_NAME, anchor="ma")

    def fix(im):
        cross(im, A[0], A[1], k=58, width=16)
        arrow(im, (B[0] - 112, B[1] + 6), (A[0] + 116, A[1] + 6), GOLD_B, 7, head=28)
        text(im, 540, A[1] + 56, "호적 정정", 34, GOLD_B, F_UI_B, anchor="mm")

    def broken(im):
        (x1, y1), (x2, y2) = pl
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        line(im, (x1, y1), (mx + 22, my - 30), RED, 8)
        line(im, (mx - 22, my + 30), (x2, y2), RED, 8)
        chip(im, mx - 96, my - 30, "남남", RED, 40, solid=True, tcolor=(255, 255, 255))
        chip(im, 540, 1150, "서류상으로도 남남", RED, 40, solid=True, tcolor=(255, 255, 255))

    return [El("heading", lambda im: heading(im, f"{gn} 씨의 어머니는?"), anim="fade"),
            El("son", son), El("slots", slots, anim="fade"),
            El("link_paper", lambda im: line(im, *pl, GOLD_B, 7, dash=(22, 13)), anim="wipe",
               wipe=pl),
            El("link_real", lambda im: line(im, *rl, INK, 6), anim="wipe", wipe=rl),
            El("year", lambda im: chip(im, 540, 1040, "2001년", RED, 40, solid=True,
                                       tcolor=(255, 255, 255))),
            El("ruling", lambda im: text(im, 540, 1108, "'친아들 아님' 판결", 38, RED, F_UI_B,
                                         anchor="mm"), anim="fade"),
            El("fix", fix),
            El("broken", broken, replaces=("year", "ruling", "link_paper"))]


def fig_verdict(doc, spec):
    def row(y, icon, claim, answer):
        def draw(im):
            box(im, 60, y, 1020, y + 250, outline=LINE)
            icon(im, 150, y + 92)
            text(im, 228, y + 92, claim, 46, INK, F_NAME, anchor="lm")
            cross(im, 945, y + 92, k=40, width=14)
            text(im, 228, y + 186, answer, 38, GOLD_B, F_UI_B, anchor="lm")
        return draw

    def coin(im, cx, cy):
        ImageDraw.Draw(im).ellipse(P(cx - 48, cy - 48, cx + 48, cy + 48), fill=GOLD_B + (255,))
        text(im, cx, cy + 2, "₩", 54, PANEL, F_UI_B, anchor="mm", stroke=0)

    return [El("heading", lambda im: heading(im, "판결"), anim="fade"),
            El("row1", row(280, lambda im, x, y: person(im, "이복동생", x, y, 52),
                           "호적상 아들이 제사?", "→ 친딸 윤정숙 씨가 지킨다")),
            El("row2", row(570, coin, "돈 받고 묘 포기?", "→ 확인서에 묘 이야기 없음")),
            El("lose", lambda im: (box(im, 60, 880, 1020, 1000, outline=GOLD_B, fill=GOLD_B,
                                       alpha=245),
                                   text(im, 540, 940, "1심 · 항소심 모두 땅주인 패소", 46, PANEL,
                                        F_NAME, anchor="mm", stroke=0))),
            El("stay", lambda im: (grave_icon(im, 340, 1090, s=0.9),
                                   text(im, 410, 1092, "어머니 묘는 그대로", 48, INK, F_NAME,
                                        anchor="lm")))]


FIGS = {"card": fig_card, "family": fig_family, "timeline": fig_timeline,
        "issue": fig_issue, "money": fig_money, "paper": fig_paper, "verdict": fig_verdict}


# ── 바탕 · 시간 · 그리기 ────────────────────────────────────────────
def bg_of(n):
    """창고 영상 n번의 한 장면을 흐리고 어둡게 — 그림 뒤 바탕 (영상과 이어진 느낌)."""
    out = S9.OUT / "figs" / f"bg_{int(n):02d}.png"
    if out.exists():
        return Image.open(out).convert("RGB")
    lf = S9.video_dir() / "library.json"
    lib = json.loads(lf.read_text(encoding="utf-8")) if lf.exists() else {}
    e = next((v for v in lib.values() if int(v.get("n") or 0) == int(n)), None)
    out.parent.mkdir(parents=True, exist_ok=True)
    if e and (S9.video_dir() / e["raw"]).exists():
        raw = S9.video_dir() / e["raw"]
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{S9.dur_of(raw) * 0.6:.2f}",
                            "-i", str(raw), "-frames:v", "1", "-vf", f"scale={W}:{H}",
                            "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
        import io
        im = Image.open(io.BytesIO(r.stdout)).convert("RGB")
    else:
        im = Image.new("RGB", (W, H), (30, 34, 44))
    im = im.filter(ImageFilter.GaussianBlur(26))
    im = Image.blend(im, Image.new("RGB", im.size, (8, 11, 18)), 0.80)
    im.save(out)
    return im


def speech_sec(c):
    w = S9.OUT / "voice" / f"c{c['n']:02d}.wav"
    if w.exists():
        return S9.dur_of(w) / S9.speed()
    import story90 as ST90
    return ST90.SEC60_PER_CHAR * ST90.chars(c)


def when(c, trigger, speech):
    """신호 낱말을 말하기 시작하는 때(초) — 글자 위치로 나눈다 (목소리는 고르게 흐른다)."""
    t = c["turns"][0][1]
    if not trigger:
        return None
    i = t.find(trigger)
    if i < 0:
        return None
    before = len([x for x in t[:i] if not x.isspace()])
    total = max(1, len([x for x in t if not x.isspace()]))
    return max(0.0, speech * before / total - LEAD)


_BUILT = {}


def elements(doc, fid):
    if fid not in _BUILT:
        spec = doc["figs"][fid]
        els = FIGS[spec["type"]](doc, spec)
        _BUILT[fid] = {e.name: e.build() for e in els}
    return _BUILT[fid]


def schedule(doc, c, sec):
    """(앞 컷에서 이미 보이는 것, [(요소, 나타나는 때)])."""
    fid = c["fig"]["id"]
    els = elements(doc, fid)
    shown = []
    for pc in doc["cuts"]:
        if pc["n"] >= c["n"]:
            break
        if (pc.get("fig") or {}).get("id") != fid:
            continue
        for nm, _trig in pc["fig"]["add"]:
            if nm in els:
                shown = [x for x in shown if x not in els[nm].replaces] + [nm]
    sp = speech_sec(c)
    adds, k = [], 0
    for nm, trig in c["fig"]["add"]:
        if nm not in els:
            continue
        t = when(c, trig, sp)
        if t is None:
            t = 0.05 + STAGGER * k
            k += 1
        adds.append((nm, min(t, max(0.0, sec - APPEAR - 0.1))))
    return shown, adds


def render(doc, c, sec, out, frames=None):
    """그림 컷 하나 → mp4 (1080×1920 · 30fps · 소리 없음 · 값 0원)."""
    fid = c["fig"]["id"]
    els = elements(doc, fid)
    order = list(els)
    shown, adds = schedule(doc, c, sec)
    t_in = {nm: t for nm, t in adds}
    gone = {}                                   # 갈아 끼워져 사라지는 요소 → 사라지기 시작하는 때
    for nm, t in adds:
        for r in els[nm].replaces:
            gone[r] = t
    bg = bg_of(doc["figs"][fid].get("bg", 1)).convert("RGBA")
    n = int(round(sec * FPS)) if frames is None else frames
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-an",
                             "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                             "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    cache_key, cache_img = None, None
    try:
        for f in range(n):
            t = f / FPS
            static, live = [], []
            for nm in order:
                e = els[nm]
                if nm in gone:
                    k = (t - gone[nm]) / APPEAR
                    if nm in shown or (nm in t_in and t >= t_in[nm]):
                        if k <= 0:
                            (live if e.pulse else static).append((nm, 1.0))
                        elif k < 1:
                            live.append((nm, 1 - k))
                    continue
                if nm in shown and nm not in t_in:
                    (live if e.pulse else static).append((nm, 1.0))
                elif nm in t_in and t >= t_in[nm]:
                    k = (t - t_in[nm]) / APPEAR
                    if k >= 1 and not e.pulse:
                        static.append((nm, 1.0))
                    else:
                        live.append((nm, min(1.0, k)))
            key = tuple(nm for nm, _ in static)
            if key != cache_key:
                cache_img = bg.copy()
                for nm, _ in static:
                    cache_img.alpha_composite(els[nm].sprite, dest=els[nm].xy)
                cache_key = key
            im = cache_img
            if live:
                im = cache_img.copy()
                for nm, k in live:
                    sp, xy = frame_of(els[nm], k, t)
                    im.alpha_composite(sp, dest=(max(0, xy[0]), max(0, xy[1])))
            proc.stdin.write(im.convert("RGB").tobytes())
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode:
        raise RuntimeError(f"그림 컷 {c['n']} 영상을 못 만들었다")
    return out


def still(doc, c, out):
    """그 컷의 **마지막 모습** 한 장 (검사·미리보기 · 0원)."""
    fid = c["fig"]["id"]
    els = elements(doc, fid)
    shown, adds = schedule(doc, c, 99)
    vis = list(shown)
    for nm, _t in adds:
        vis = [x for x in vis if x not in els[nm].replaces] + [nm]
    im = bg_of(doc["figs"][fid].get("bg", 1)).convert("RGBA")
    for nm in els:
        if nm in vis:
            im.alpha_composite(els[nm].sprite, dest=els[nm].xy)
    im.convert("RGB").save(out)
    return out
