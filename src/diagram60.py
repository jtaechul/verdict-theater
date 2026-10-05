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


def coin_icon(im, cx, cy, s=1.0, color=GOLD_B):
    """돈 — 금색 동전에 ₩."""
    ImageDraw.Draw(im).ellipse(P(cx - 48 * s, cy - 48 * s, cx + 48 * s, cy + 48 * s), fill=color + (255,))
    text(im, cx, cy + 2 * s, "₩", 54 * s, PANEL, F_UI_B, anchor="mm", stroke=0)


def home_icon(im, cx, cy, s=1.0, color=GOLD_B):
    """집·땅 — 지붕 + 벽 + 문."""
    d = ImageDraw.Draw(im)
    d.polygon([P(cx - 52 * s, cy - 6 * s), P(cx, cy - 50 * s), P(cx + 52 * s, cy - 6 * s)],
              fill=color + (255,))
    d.rectangle(P(cx - 38 * s, cy - 8 * s, cx + 38 * s, cy + 40 * s), fill=color + (255,))
    d.rectangle(P(cx - 10 * s, cy + 10 * s, cx + 10 * s, cy + 40 * s), fill=PANEL + (255,))


def doc_icon(im, cx, cy, s=1.0, color=GOLD_B):
    """서류 — 귀퉁이 접힌 종이 + 글줄."""
    d = ImageDraw.Draw(im)
    d.polygon([P(cx - 36 * s, cy - 48 * s), P(cx + 18 * s, cy - 48 * s), P(cx + 36 * s, cy - 30 * s),
               P(cx + 36 * s, cy + 48 * s), P(cx - 36 * s, cy + 48 * s)], fill=color + (255,))
    for k in range(3):
        y = cy - 14 * s + k * 20 * s
        d.rectangle(P(cx - 22 * s, y, cx + 22 * s, y + 6 * s), fill=PANEL + (255,))


def scale_icon(im, cx, cy, s=1.0, color=GOLD_B):
    """법 — 저울."""
    d = ImageDraw.Draw(im)
    d.rectangle(P(cx - 4 * s, cy - 44 * s, cx + 4 * s, cy + 36 * s), fill=color + (255,))
    d.rectangle(P(cx - 30 * s, cy + 34 * s, cx + 30 * s, cy + 44 * s), fill=color + (255,))
    d.rectangle(P(cx - 50 * s, cy - 40 * s, cx + 50 * s, cy - 33 * s), fill=color + (255,))
    for x in (-42, 42):
        d.line(P(cx + x * s, cy - 36 * s, cx + (x - 14) * s, cy), fill=color + (255,), width=int(3 * SS))
        d.line(P(cx + x * s, cy - 36 * s, cx + (x + 14) * s, cy), fill=color + (255,), width=int(3 * SS))
        d.pieslice(P(cx + (x - 18) * s, cy - 14 * s, cx + (x + 18) * s, cy + 14 * s), 0, 180,
                   fill=color + (255,))


def ring_icon(im, cx, cy, s=1.0, color=GOLD_B):
    """혼인 — 반지."""
    d = ImageDraw.Draw(im)
    d.ellipse(P(cx - 36 * s, cy - 24 * s, cx + 36 * s, cy + 48 * s), outline=color + (255,),
              width=int(9 * s * SS))
    d.polygon([P(cx, cy - 50 * s), P(cx + 16 * s, cy - 32 * s), P(cx, cy - 18 * s),
               P(cx - 16 * s, cy - 32 * s)], fill=INK + (255,))


# 그림 속 작은 그림 — 쟁점의 원칙 줄 · 판결 줄 · 끝줄에 이름으로 고른다 (사건마다 맞는 것)
ICONS = {"grave": grave_icon, "table": table_icon, "coin": coin_icon, "home": home_icon,
         "doc": doc_icon, "scale": scale_icon, "ring": ring_icon}


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


# ── 그림 설계 (대본 figs 가 정한다 · 코드에는 사건 글이 없다) ─────────────────
#    ⭐ 2026-10-02 손님: "앞으로 우리가 제작하는 영상에서도 동일한 방식으로 제작이 될 수 있게끔"
#       → 사람·글·자리를 전부 대본의 figs[id] 에 적는다. 여기는 **그리는 법**만 안다.
#       대본 짓는 법·예시는 .claude/skills/verdict-explainer/SKILL.md (S94 가 본보기).
COLORS = {"gold": GOLD_B, "red": RED, "ink": INK, "soft": SOFT, "grey": GREY, "mute": MUTE}


def col(name, default=GOLD_B):
    return COLORS.get(str(name or ""), default) if not isinstance(name, (list, tuple)) else tuple(name)


def labels(doc):
    """{관계 이름: (가명, 이름표 관계)} — 대본 인물표에서."""
    out = {}
    for p in doc.get("cast") or []:
        out[str(p.get("name"))] = (str(p.get("alias") or p.get("name")),
                                   str(p.get("tag") or p.get("name")))
    return out


def who_name(doc, who, role=None):
    """인물표의 사람 → (이름, 괄호 관계). role 을 주면 괄호를 그것으로."""
    nm, tg = labels(doc).get(who, (who, who))
    return nm, (tg if role is None else role)


def fig_card(doc, spec):
    def card(im):
        line(im, (330, 760), (750, 760), GOLD, 3, alpha=200)
        text(im, 540, 880, spec.get("text") or "", 124, GOLD_B, F_NAME, anchor="mm", stroke=3)
        if spec.get("sub"):
            text(im, 540, 1010, spec["sub"], 48, SOFT, F_UI, anchor="mm")
        line(im, (330, 1080), (750, 1080), GOLD, 3, alpha=200)
    return [El("card", card, anim="fade")]


def _edge(a, b, ra, rb, pad=12):
    (x1, y1), (x2, y2) = a, b
    n = math.hypot(x2 - x1, y2 - y1) or 1
    ux, uy = (x2 - x1) / n, (y2 - y1) / n
    return (x1 + ux * (ra + pad), y1 + uy * (ra + pad)), (x2 - ux * (rb + pad), y2 - uy * (rb + pad))


def fig_relations(doc, spec):
    """인물 관계도 — nodes(사람) · edges(선) · labels(이름표 바꿔 끼우기) · texts · marks.

    node  {"id", "who"(인물표) | "ghost": true + "name", "at": [x, y], "r", "role",
           "gold", "size", "label": "below"(기본) | "right" | false}
    edge  {"id", "a", "b", "style": "solid" | "paper"(금색 점선 · 서류상) | "sibling",
           "down": true(위 사람 이름표 아래에서 곧장 내려온다), "text", "text_at", "chip", "chip_t"}
    label {"id", "node", "role", "replaces": [...]}   texts {"id", "text", "at", "color", "replaces"}
    marks {"id", "kind": "caption" | "grave" | "banner" | "glow", …}"""
    nodes = {n["id"]: n for n in spec.get("nodes") or []}
    els = [El("heading", lambda im: heading(im, spec.get("title") or "인물 관계도"), anim="fade")]
    # 선 뜻풀이 — true: 실제/서류상 둘 · 없으면 서류상 선(paper)이 있을 때만 · false: 안 그린다
    #             [["solid", "실제 관계"], ["paper", "서류(호적)상 관계"]] 처럼 직접 적어도 된다
    lg = spec.get("legend", "auto")
    if lg == "auto":
        lg = any((e.get("style") or "") == "paper" for e in spec.get("edges") or [])
    if lg is True:
        lg = [["solid", "실제 관계"], ["paper", "서류(호적)상 관계"]]
    if lg:
        def legend(im, lg=lg):
            gap = 135                                  # S94 의 자리 그대로 (205 에서 시작)
            ws = [71 + tw(s, 32, F_UI) for _, s in lg]
            x = max(60, min(205, 540 - (sum(ws) + gap * (len(ws) - 1)) / 2))
            for (st, s), w in zip(lg, ws):
                if st == "solid":
                    line(im, (x, 262), (x + 57, 262), LINE, 5)
                else:
                    line(im, (x, 262), (x + 58, 262), GOLD_B, 6, dash=(14, 9))
                text(im, x + (71 if st == "solid" else 72), 262, s, 32, MUTE, F_UI, anchor="lm")
                x += w + gap
        els.append(El("legend", legend, anim="fade"))

    def xy(n):
        return tuple(nodes[n]["at"])

    def rad(n):
        return int(nodes[n].get("r") or 104)

    def name_of(n, role=None):
        nd = nodes[n]
        if nd.get("who"):
            return who_name(doc, nd["who"], nd.get("role") if role is None else role)
        return nd.get("name") or "", (nd.get("role") if role is None else role)

    for e in spec.get("edges") or []:
        a, b = e["a"], e["b"]
        st = e.get("style") or "solid"
        if e.get("down"):
            (ax, ay), (bx, by) = xy(a), xy(b)
            seg = ((ax, ay + rad(a) + 14 + 58), (bx, by - rad(b) - 12))
        elif st == "sibling":
            (ax, ay), (bx, by) = xy(a), xy(b)
            seg = ((ax + rad(a) + 14, ay), (bx - rad(b) - 14, by))
        else:
            seg = _edge(xy(a), xy(b), rad(a), rad(b), pad=14 if st == "paper" else 12)

        def draw(im, e=e, seg=seg, st=st):
            if st == "paper":
                line(im, *seg, GOLD_B, 7, dash=(24, 14))
            elif st == "sibling":
                line(im, *seg, GOLD_B, 6, dash=(18, 12))
            else:
                line(im, *seg, LINE, 5)
            if e.get("text"):
                tx, ty = e.get("text_at") or ((seg[0][0] + seg[1][0]) / 2, (seg[0][1] + seg[1][1]) / 2)
                text(im, tx, ty, e["text"], 36, col(e.get("color"), SOFT), F_UI, anchor="mm")
            if e.get("chip"):
                if st == "sibling":
                    cx, cy = (seg[0][0] + seg[1][0]) / 2, seg[0][1]
                else:
                    t = float(e.get("chip_t") or 0.38)
                    cx = seg[0][0] + (seg[1][0] - seg[0][0]) * t + 6
                    cy = seg[0][1] + (seg[1][1] - seg[0][1]) * t
                chip(im, cx, cy, e["chip"], GOLD_B, 32 if st == "sibling" else 34)
        els.append(El(e["id"], draw, anim="fade" if st == "sibling" else "wipe", wipe=seg))

    for nid, nd in nodes.items():
        def draw(im, nid=nid, nd=nd):
            x, y = xy(nid)
            r = rad(nid)
            if nd.get("ghost"):
                ghost(im, x, y, r)
            else:
                person(im, nd["who"], x, y, r, ring=GOLD_B if nd.get("gold") else (228, 224, 216))
            lab = nd.get("label", "below")
            if lab is False:
                return
            nm, rl = name_of(nid)
            if lab == "right":
                text(im, x + r + 24, y, nm, 52, INK, anchor="lm")
            else:
                nametag(im, x, y + r + 14, nm, rl or None, color=GOLD_B if nd.get("gold") else INK,
                        size=int(nd.get("size") or 48))
        els.append(El(nid, draw))

    for lb in spec.get("labels") or []:
        def draw(im, lb=lb):
            x, y = xy(lb["node"])
            nm, rl = name_of(lb["node"], lb.get("role"))
            nametag(im, x, y + rad(lb["node"]) + 14, nm, rl or None,
                    size=int(nodes[lb["node"]].get("size") or 48))
        els.append(El(lb["id"], draw, anim="fade", replaces=lb.get("replaces") or ()))

    for tx in spec.get("texts") or []:
        els.append(El(tx["id"], lambda im, tx=tx: text(
            im, *tx["at"], tx["text"], int(tx.get("size") or 36), col(tx.get("color"), SOFT),
            F_UI_B if tx.get("color") == "gold" else F_UI, anchor="mm"),
            anim="fade", replaces=tx.get("replaces") or ()))

    for mk in spec.get("marks") or []:
        k = mk.get("kind")
        if k == "caption":
            def draw(im, mk=mk):
                x, y = xy(mk["node"])
                chip(im, x, y + rad(mk["node"]) - 20, mk["text"], GREY, 30, solid=True, tcolor=PANEL)
        elif k == "grave":
            def draw(im, mk=mk):
                x, y = mk["at"]
                badge(im, x, y)
                if mk.get("text"):
                    text(im, x, y + 52, mk["text"], 30, GOLD_B, F_UI_B, anchor="ma")
        elif k == "banner":
            def draw(im, mk=mk):
                cw = tw(mk["tag"], 32, F_UI_B) + 40
                w = cw + 22 + tw(mk["text"], 34, F_UI_B)
                x0 = 540 - w / 2
                chip(im, x0 + cw / 2, 262, mk["tag"], col(mk.get("color"), RED), 32)
                text(im, x0 + cw + 22, 262, mk["text"], 34, INK, F_UI_B, anchor="lm")
        elif k == "glow":
            def draw(im, mk=mk):
                ring_glow(im, *xy(mk["node"]), rad(mk["node"]), col(mk.get("color"), RED))
        else:
            continue
        els.append(El(mk["id"], draw, anim="fade", replaces=mk.get("replaces") or (),
                      pulse=(k == "glow")))
    return els


def fig_timeline(doc, spec):
    """연표 — rows [{"id", "year", "who", "what", "color": "gold"|"red", "what_color"}] ·
    cards [{"id", "after": 줄 id, "title", "text"}] · faces [{"id", "row", "who"}]."""
    X = 170
    rows = spec.get("rows") or []
    cards = {c["after"]: c for c in spec.get("cards") or []}
    y, at, card_at = 330, {}, {}
    for r in rows:
        at[r["id"]] = y
        y += 140
        if r["id"] in cards:
            top = y - 55
            card_at[cards[r["id"]]["id"]] = (top, top + 175)
            y = top + 175 + 80
    bottom = (max(at.values()) if at else 330) + 90

    def row(r):
        def draw(im):
            yy = at[r["id"]]
            c = col(r.get("color"), GOLD_B)
            chip(im, X, yy, r["year"], c, 30)
            text(im, 262, yy - 30, r["who"], 42, INK)
            if r.get("what"):
                text(im, 262, yy + 24, r["what"], 34, col(r.get("what_color"), SOFT), F_UI)
        return draw

    def card(cd):
        def draw(im):
            t, b = card_at[cd["id"]]
            box(im, 262, t, 1010, b, outline=GOLD_B, dash=(16, 10))
            text(im, 292, t + 33, cd.get("title") or "", 32, GOLD_B, F_UI_B)
            para(im, 292, t + 79, cd.get("text") or "", 36, 690, INK, F_UI_B)
        return draw

    els = [El("heading", lambda im: (heading(im, spec.get("title") or "일어난 순서"),
                                     line(im, (X, 300), (X, bottom), LINE, 4, alpha=170)),
              anim="fade")]
    for r in rows:
        els.append(El(r["id"], row(r), anim="fade"))
        if r["id"] in cards:
            els.append(El(cards[r["id"]]["id"], card(cards[r["id"]])))
    for fc in spec.get("faces") or []:
        els.append(El(fc["id"], lambda im, fc=fc: person(im, fc["who"], 960, at[fc["row"]], 56)))
    return els


def fig_issue(doc, spec):
    """재판의 쟁점 — suit(누가 누구를 · 무엇을) · rule(법 원칙 두 줄 · 그림) · question · cands(두 사람)."""
    su = spec.get("suit") or {}
    A, B = (210, 345), (870, 345)

    def suit(im):
        person(im, su["from"], *A, 74)
        person(im, su["to"], *B, 74, ring=GOLD_B)
        nametag(im, A[0], A[1] + 88, *who_name(doc, su["from"]), size=38)
        nametag(im, B[0], B[1] + 88, *who_name(doc, su["to"]), size=38, color=GOLD_B)
        arrow(im, (300, 345), (782, 345), RED, 7, head=30)
        if su.get("quote"):
            text(im, 541, 300, su["quote"], 38, INK, F_UI_B, anchor="mm")
        if su.get("year"):
            text(im, 541, 392, su["year"], 32, RED, F_UI_B, anchor="mm")

    def rule(im):
        rows = spec.get("rule") or []
        box(im, 70, 520, 1010, 760, outline=GOLD_B)
        for i, (ic, s) in enumerate(rows[:2]):
            y = 600 + i * 94
            if ic in ICONS:
                ICONS[ic](im, 170, y, s=0.95)
            text(im, 250, y - (0 if i == 0 else 4), s, 42 if i == 0 else 46,
                 INK if i == 0 else GOLD_B, F_UI_B if i == 0 else F_NAME, anchor="lm")

    cs = spec.get("cands") or []
    xs = (300, 780) if len(cs) > 1 else (540, 540)        # 후보가 한 명이면 가운데

    def cands(im):
        for (x, cd) in zip(xs, cs):
            person(im, cd["who"], x, 1010, 108, ring=GOLD_B if cd.get("gold") else (228, 224, 216))
            nametag(im, x, 1132, who_name(doc, cd["who"])[0], cd.get("role"), size=42,
                    color=GOLD_B if cd.get("gold") else INK)
        if len(cs) > 1:
            text(im, 540, 1010, "vs", 52, MUTE, F_NAME, anchor="mm")

    els = [El("heading", lambda im: heading(im, spec.get("title") or "재판의 쟁점"), anim="fade"),
           El("suit", suit, anim="fade"), El("rule", rule),
           El("question", lambda im: text(im, 540, 838, spec.get("question") or "", 54, INK, F_NAME,
                                          anchor="mm", stroke=3)),
           El("cands", cands)]
    for c in spec.get("chips") or []:
        els.append(El(c["id"], lambda im, c=c: chip(im, xs[min(1, int(c.get("under") or 0))], 1238,
                                                    c["text"], col(c.get("color"), RED), 32)))
    return els


def fig_flow(doc, spec):
    """돈·물건이 간 길 — from → to · amount · claim(주장 · X 가 붙는다) · doc(증거 글) · chips."""
    A, B = (215, 390), (865, 390)
    fr, to = spec["from"], spec["to"]

    def people(im):
        person(im, fr["who"], *A, 100)
        person(im, to["who"], *B, 100, ring=GOLD_B)
        nametag(im, A[0], A[1] + 114, *who_name(doc, fr["who"]), size=42)
        nametag(im, B[0], B[1] + 114, *who_name(doc, to["who"]), size=42, color=GOLD_B)

    def flow(im):
        arrow(im, (330, 390), (750, 390), GOLD_B, 8, head=32)
        text(im, 540, 338, spec.get("amount") or "", 52, GOLD_B, F_NAME, anchor="mm", stroke=3)
        if spec.get("sub"):
            text(im, 540, 440, spec["sub"], 32, SOFT, F_UI, anchor="mm")

    def claim(im):
        cl = spec.get("claim") or {}
        box(im, 70, 610, 1010, 800, outline=RED)
        chip(im, 70 + 40 + tw(cl.get("tag") or "", 32, F_UI_B) / 2 + 20, 652, cl.get("tag") or "",
             RED, 32)
        text(im, 110, 730, cl.get("text") or "", 48, INK, F_NAME)

    def docu(im):
        dc = spec.get("doc") or {}
        box(im, 70, 840, 1010, 1040, outline=GOLD_B)
        chip(im, 70 + 40 + tw(dc.get("tag") or "", 32, F_UI_B) / 2 + 20, 882, dc.get("tag") or "",
             GOLD_B, 32)
        para(im, 110, 930, dc.get("text") or "", 40, 860, INK, F_UI_B)

    els = [El("heading", lambda im: heading(im, spec.get("title") or ""), anim="fade"),
           El("people", people, anim="fade"), El("flow", flow, anim="fade"),
           El("claim", claim), El("doc", docu),
           El("cross", lambda im: cross(im, 940, 705, k=46, width=15))]
    for c in spec.get("chips") or []:
        x = 790 if c.get("side") == "right" else 290
        els.append(El(c["id"], lambda im, c=c, x=x: chip(im, x, 1092, c["text"],
                                                          col(c.get("color"), GOLD_B), 34,
                                                          solid=bool(c.get("solid")))))
    return els


def fig_compare(doc, spec):
    """서류 vs 실제 — subject(한 사람) · left(서류상 · 흔히 고인 윤곽) · right(실제) · year · ruling ·
    fix(바로잡음 화살표) · broken(끊김 + 결과)."""
    sj, lf, rt = spec["subject"], spec["left"], spec["right"]
    S_, A, B = (540, 370), (255, 790), (825, 790)
    pl = ((S_[0] - 70, S_[1] + 90), (A[0] + 60, A[1] - 110))
    rl = ((S_[0] + 70, S_[1] + 90), (B[0] - 60, B[1] - 110))

    def slot(im, side, x, y, color):
        if side.get("ghost"):
            ghost(im, x, y, 100, ring=color, dash=True)
        else:
            person(im, side["who"], x, y, 100)
        chip(im, x, y + 140, side.get("chip") or "", color, 34)
        nm = side.get("name") or (who_name(doc, side["who"])[0] if side.get("who") else "")
        text(im, x, y + 186, nm, 38, SOFT if side.get("ghost") else INK,
             F_UI_B if side.get("ghost") else F_NAME, anchor="ma")

    def broken(im):
        (x1, y1), (x2, y2) = pl
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        line(im, (x1, y1), (mx + 22, my - 30), RED, 8)
        line(im, (mx - 22, my + 30), (x2, y2), RED, 8)
        if spec.get("broken"):
            chip(im, mx - 96, my - 30, spec["broken"], RED, 40, solid=True, tcolor=(255, 255, 255))
        if spec.get("result"):
            chip(im, 540, 1150, spec["result"], RED, 40, solid=True, tcolor=(255, 255, 255))

    def fix(im):
        cross(im, A[0], A[1], k=58, width=16)
        arrow(im, (B[0] - 112, B[1] + 6), (A[0] + 116, A[1] + 6), GOLD_B, 7, head=28)
        if spec.get("fix"):
            text(im, 540, A[1] + 56, spec["fix"], 34, GOLD_B, F_UI_B, anchor="mm")

    return [El("heading", lambda im: heading(im, spec.get("title") or ""), anim="fade"),
            El("son", lambda im: (person(im, sj["who"], *S_, 104),
                                  nametag(im, S_[0], S_[1] + 118, who_name(doc, sj["who"])[0], None,
                                          size=46))),
            El("slots", lambda im: (slot(im, lf, *A, GOLD_B), slot(im, rt, *B, INK)), anim="fade"),
            El("link_paper", lambda im: line(im, *pl, GOLD_B, 7, dash=(22, 13)), anim="wipe", wipe=pl),
            El("link_real", lambda im: line(im, *rl, INK, 6), anim="wipe", wipe=rl),
            El("year", lambda im: chip(im, 540, 1040, spec.get("year") or "", RED, 40, solid=True,
                                       tcolor=(255, 255, 255))),
            El("ruling", lambda im: text(im, 540, 1108, spec.get("ruling") or "", 38, RED, F_UI_B,
                                         anchor="mm"), anim="fade"),
            El("fix", fix),
            El("broken", broken, replaces=("year", "ruling", "link_paper"))]


def fig_verdict(doc, spec):
    """판결 정리 — rows [{"id", "icon": {"who"} | ICONS 이름, "claim", "answer", "mark": "x"|"o"|""}]
    (1~3줄 · 주장이 받아들여지지 않았으면 x(기본), 받아들여졌으면 o) · lose(결론 띠) · stay(끝 한 줄)."""
    rows = spec.get("rows") or []
    n = max(1, len(rows))
    hgt, step = (250, 290) if n <= 2 else (210, 236)
    y0 = 280
    end = y0 + step * (n - 1) + hgt

    def row(i, r):
        def draw(im):
            y = y0 + step * i
            box(im, 60, y, 1020, y + hgt, outline=LINE)
            ic = r.get("icon")
            if isinstance(ic, dict) and ic.get("who"):
                person(im, ic["who"], 150, y + 92, 52)
            elif ic in ICONS:
                ICONS[ic](im, 150, y + 92, s=0.9 if ic == "grave" else 1.0)
            text(im, 228, y + 92, r.get("claim") or "", 46, INK, F_NAME, anchor="lm")
            mk = r.get("mark", "x")
            if mk == "x":
                cross(im, 945, y + 92, k=40, width=14)
            elif mk == "o":
                ImageDraw.Draw(im).ellipse(P(945 - 42, y + 92 - 42, 945 + 42, y + 92 + 42),
                                           outline=GOLD_B + (255,), width=int(13 * SS))
            text(im, 228, y + hgt - 64, r.get("answer") or "", 38, GOLD_B, F_UI_B, anchor="lm")
        return draw

    st = spec.get("stay") or {}

    def stay(im):
        ic = st.get("icon")
        if ic in ICONS:
            ICONS[ic](im, 340, end + 240, s=0.9)
            text(im, 410, end + 242, st.get("text") or "", 48, INK, F_NAME, anchor="lm")
        else:
            text(im, 540, end + 242, st.get("text") or "", 48, INK, F_NAME, anchor="mm")

    els = [El("heading", lambda im: heading(im, spec.get("title") or "판결"), anim="fade")]
    els += [El(r["id"], row(i, r)) for i, r in enumerate(rows)]
    els += [El("lose", lambda im: (box(im, 60, end + 30, 1020, end + 150, outline=GOLD_B, fill=GOLD_B,
                                       alpha=245),
                                   text(im, 540, end + 90, spec.get("lose") or "", 46, PANEL, F_NAME,
                                        anchor="mm", stroke=0))),
            El("stay", stay)]
    return els


# ── ⭐ 글판(board) — 법 원칙 · 몫 셈 · 주장과 판단을 **한 줄씩** 쌓는다 (2026-10-05 · S95 긴 영상) ──
#    관계도·연표처럼 정해진 꼴이 없는 설명(유류분이란 · 빚을 빼야 하나 · 기한 · 셈)을 위한 그림이다.
#    items 는 위에서부터 쌓이고, 칸이 차면 **다음 장**으로 넘어간다(앞 장 줄은 사라지고 제목은 남는다).
#    item {"id", "kind", "text", "sub", "icon"(ICONS), "tag", "color", "segs"(bar)}
#      kind: big(큰 말 + 풀이) · line(그림 + 한 줄) · chip(알약) · claim(주장 · cross 로 X) ·
#            quote(판결 말 · 따옴표 띠) · result(결론 · 금색) · eq(셈) · bar(몫 막대 · segs)
#    cross: claim 줄 id — 그 줄에 X 를 긋는 요소 이름도 "cross" 다.
BOARD_H = {"big": 168, "line": 92, "chip": 84, "claim": 150, "quote": 112, "result": 104,
           "eq": 96, "bar": 212}
BOARD_TOP, BOARD_BOTTOM = 300, 1250        # 세로 화면 그림 칸 (아래는 자막 자리)


def board_pages(items, top=BOARD_TOP, bottom=BOARD_BOTTOM, gap=22):
    """줄마다 (장 번호, 위 y). 칸을 넘으면 다음 장 맨 위로."""
    out, page, y = {}, 0, top
    for it in items:
        h = BOARD_H.get(it.get("kind") or "line", 92)
        if y + h > bottom and y > top:
            page, y = page + 1, top
        out[it["id"]] = (page, y)
        y += h + gap
    return out


def fig_board(doc, spec):
    items = [it for it in spec.get("items") or [] if isinstance(it, dict)]
    pos = board_pages(items)
    L, R, CX = 70, 1010, 540

    def draw_item(it):
        def draw(im):
            k = it.get("kind") or "line"
            y = pos[it["id"]][1]
            c = col(it.get("color"), GOLD_B)
            s = it.get("text") or ""
            if k == "big":
                box(im, L, y, R, y + BOARD_H["big"], outline=GOLD_B)
                x = L + 40
                if it.get("icon") in ICONS:
                    ICONS[it["icon"]](im, L + 90, y + 84, s=1.05)
                    x = L + 170
                text(im, x, y + 58, s, 64, GOLD_B, F_NAME, anchor="lm", stroke=3)
                if it.get("sub"):
                    text(im, x, y + 124, it["sub"], 38, INK, F_UI_B, anchor="lm")
            elif k == "line":
                x = L + 20
                if it.get("icon") in ICONS:
                    ICONS[it["icon"]](im, L + 56, y + 46, s=0.72)
                    x = L + 120
                para(im, x, y + 18, s, 44, R - x - 10, col(it.get("color"), INK), F_UI_B)
            elif k == "chip":
                chip(im, CX, y + 42, s, c, 38, solid=bool(it.get("solid")))
            elif k == "claim":
                box(im, L, y, R, y + BOARD_H["claim"], outline=RED)
                tag = it.get("tag") or "주장"
                chip(im, L + 40 + tw(tag, 32, F_UI_B) / 2 + 20, y + 40, tag, RED, 32)
                para(im, L + 40, y + 76, s, 42, R - L - 160, INK, F_NAME)
            elif k == "quote":
                box(im, L + 30, y, R - 30, y + BOARD_H["quote"], outline=SOFT, dash=(14, 10))
                para(im, CX, y + 30, f"“{s}”", 40, R - L - 120, SOFT, F_NAME_M, anchor="ma")
            elif k == "result":
                text(im, CX, y + 52, s, 56, c, F_NAME, anchor="mm", stroke=3)
                if it.get("sub"):
                    text(im, CX, y + 98, it["sub"], 34, SOFT, F_UI, anchor="mm")
            elif k == "eq":
                text(im, CX, y + 48, s, 50, INK, F_NAME, anchor="mm", stroke=3)
            elif k == "bar":
                segs = it.get("segs") or []
                n = sum(int(g.get("n") or 1) for g in segs) or 1
                x0, x1, top = L + 30, R - 30, y + 64
                cw = (x1 - x0) / n
                text(im, CX, y + 24, s, 38, SOFT, F_UI_B, anchor="mm")
                k0 = 0
                for g in segs:
                    m = int(g.get("n") or 1)
                    gc = col(g.get("color"), GREY)
                    for j in range(m):
                        xa = x0 + (k0 + j) * cw
                        box(im, xa + 4, top, xa + cw - 4, top + 84, outline=gc, fill=gc,
                            alpha=235 if g.get("color") else 150, r=12)
                    text(im, x0 + (k0 + m / 2) * cw, top + 124, f"{g.get('label') or ''} {m}", 38,
                         gc if g.get("color") else INK, F_UI_B, anchor="mm")
                    k0 += m
        return draw

    first = {}
    for it in items:
        first.setdefault(pos[it["id"]][0], it["id"])
    els = [El("heading", lambda im: heading(im, spec.get("title") or ""), anim="fade")]
    for it in items:
        pg = pos[it["id"]][0]
        # 새 장의 첫 줄이 나오면 앞 장 줄들은 사라진다 (제목은 남는다)
        rep = [x["id"] for x in items if pos[x["id"]][0] == pg - 1] if first[pg] == it["id"] and pg else []
        els.append(El(it["id"], draw_item(it), anim="fade" if it.get("kind") in ("quote", "eq") else "pop",
                      replaces=rep))
    cid = spec.get("cross")
    if cid and cid in pos:
        it = next(x for x in items if x["id"] == cid)
        y = pos[cid][1]
        els.append(El("cross", lambda im: cross(im, R - 70, y + BOARD_H.get(it.get("kind"), 92) / 2,
                                                k=44, width=15)))
    return els


# 옛 이름(S94 v5 첫 판)도 받는다 — family · money · paper
FIGS = {"card": fig_card, "relations": fig_relations, "family": fig_relations,
        "timeline": fig_timeline, "issue": fig_issue, "flow": fig_flow, "money": fig_flow,
        "compare": fig_compare, "paper": fig_compare, "verdict": fig_verdict, "board": fig_board}
KIND = {"family": "relations", "money": "flow", "paper": "compare"}
# 종류마다 꼭 있어야 할 칸 (없으면 빈 그림이 나온다)
NEEDS = {"card": ("text",), "relations": ("nodes",), "timeline": ("rows",),
         "issue": ("suit", "rule", "question"), "flow": ("from", "to", "amount"),
         "compare": ("subject", "left", "right"), "verdict": ("rows", "lose"), "board": ("items",)}


def kind_of(t):
    return KIND.get(t, t)


def whos(spec):
    """그림이 얼굴을 그리는 사람들 (인물표 이름) — 종류마다 자리가 다르다."""
    k, out = kind_of(spec.get("type")), []
    if k == "relations":
        out = [n.get("who") for n in spec.get("nodes") or [] if not n.get("ghost")]
    elif k == "timeline":
        out = [f.get("who") for f in spec.get("faces") or []]
    elif k == "issue":
        su = spec.get("suit") or {}
        out = [su.get("from"), su.get("to")] + [c.get("who") for c in spec.get("cands") or []]
    elif k == "flow":
        out = [(spec.get("from") or {}).get("who"), (spec.get("to") or {}).get("who")]
    elif k == "compare":
        out = [(spec.get(s) or {}).get("who") for s in ("subject", "left", "right")
               if not (spec.get(s) or {}).get("ghost")]
    elif k == "verdict":
        out = [r["icon"].get("who") for r in spec.get("rows") or [] if isinstance(r.get("icon"), dict)]
    return [w for w in out if w]


def validate(doc):
    """그림 설계와 그림 컷이 맞물리는가 — 틀려도 그리기는 **말없이** 지나간다 (값 0원 · 그리지 않는다).
    · 그림 이름(fig.id)이 figs 에 있는가 · 종류(type)를 아는가 · 종류마다 꼭 있어야 할 칸
    · add 의 요소가 그 그림에 있는가 — 없으면 그 요소가 **안 나온다**
    · 신호 낱말이 그 컷 나레이션에 있는가 — 없으면 말과 상관없이 **첫머리에** 나온다
    · 그림 속 얼굴(who)이 인물표에 있는가 — 없으면 얼굴 대신 **윤곽**이 나온다"""
    bad = []
    figs = doc.get("figs") or {}
    cast = {str(p.get("name")) for p in doc.get("cast") or [] if isinstance(p, dict)}
    names = {}
    for fid, spec in figs.items():
        t = (spec or {}).get("type")
        if t not in FIGS:
            bad.append(f"그림 「{fid}」 의 종류 '{t}' 를 모른다 — "
                       f"{', '.join(sorted({kind_of(x) for x in FIGS}))} 가운데 하나")
            continue
        miss = [k for k in NEEDS.get(kind_of(t), ()) if not spec.get(k)]
        if miss:
            bad.append(f"그림 「{fid}」({kind_of(t)}) 에 {', '.join(miss)} 칸이 없다")
            continue
        try:
            names[fid] = [e.name for e in FIGS[t](doc, spec)]
        except (KeyError, TypeError, ValueError, IndexError) as ex:
            bad.append(f"그림 「{fid}」 설계가 틀렸다 — {type(ex).__name__}: {ex}")
            continue
        for w in sorted(set(whos(spec)) - cast):
            bad.append(f"그림 「{fid}」 의 얼굴 '{w}' 가 인물표(cast)에 없다 — 얼굴 대신 윤곽이 나온다")
    for c in doc.get("cuts") or []:
        fg = c.get("fig")
        if not fg:
            continue
        n, fid = c.get("n"), fg.get("id")
        if fid not in figs:
            bad.append(f"컷{n}: 그림 「{fid}」 설계가 figs 에 없다")
            continue
        if fid not in names:
            continue
        said = str(((c.get("turns") or [["", ""]])[0] + ["", ""])[1])
        for nm, trig in fg.get("add") or []:
            if nm not in names[fid]:
                bad.append(f"컷{n}: 그림 「{fid}」 에 '{nm}' 요소가 없다 — 안 나온다 "
                           f"(있는 것: {', '.join(names[fid])})")
            if trig and trig not in said:
                bad.append(f"컷{n}: 신호 낱말 「{trig}」 가 나레이션에 없다 — '{nm}' 이(가) 말과 "
                           f"상관없이 첫머리에 나온다")
    return bad


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
