#!/usr/bin/env python3
"""정보 그래픽 4종 + 자막을 코드가 직접 그린다.

    python3 src/graphics.py --demo out/

왜 코드로 그리나
    타임라인·가족관계도·네임태그·금액강조는 회차마다 내용이 달라진다.
    이미지로 미리 만들 수 없고, 만들 수 있어도 회차마다 돈이 든다.
    **코드가 그리면 비용이 0원이고 내용이 언제나 정확하다.**

왜 SVG 가 아니라 Pillow 인가
    지침서는 SVG 를 적었지만, SVG 를 화면에 얹으려면 결국 그림으로 바꿔야 하고
    그러려면 변환기(cairosvg 등)를 하나 더 설치해야 한다.
    한글 글자 폭을 재서 줄을 바꾸는 일도 Pillow 쪽이 정확하다. 의존성 하나를 줄인다.

고령자 타깃 자막 규칙 (지침서 8번)
    - 자막 영역은 화면 높이의 1/6 이상
    - 상시 노출. 소리 없이도 따라올 수 있어야 한다
    - **어절 단위로 끊고 한 줄 최대 18자.** 한국어를 아무데서나 끊으면 읽기 어렵다
"""

import argparse
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent

# ── 디자인 토큰 ──────────────────────────────────────────
# ⭐ 색은 **세 개만** 쓴다.
#    예전에는 미색 종이 + 금색 + 진홍 + 회색 + 흰 자막이 한 화면에 다 있어
#    통일감이 없었다. 색이 많으면 화면이 시끄럽고 싸구려로 보인다.
#    나머지는 이 세 색에서 뽑아낸 농도 차이일 뿐이다.
INK = (22, 22, 26)          # 먹 — 글자와 선
PAPER = (247, 245, 240)     # 종이 — 카드 바탕
ACCENT = (168, 46, 42)      # 강조 — 판결·중요한 순간에만. 아껴 쓸수록 세진다

# 위 세 색에서 뽑은 농도 (새 색이 아니다)
MUTED = tuple(round(i + (p - i) * 0.55) for i, p in zip(INK, PAPER))    # 보조 글자
HAIR = tuple(round(i + (p - i) * 0.86) for i, p in zip(INK, PAPER))     # 가는 선

# 예전 이름 (남아 있는 호출부 호환)
CRIMSON = ACCENT
SLATE = MUTED
LINE = HAIR
GOLD = ACCENT
SHADOW = (0, 0, 0, 110)

SUB_MAX_CHARS = 18          # wrap_korean 의 기본값 (자막은 fit_subtitle 이 폭을 직접 잰다)

# ⭐ 화면 밖으로 나가지 않게 하는 두 장치 ────────────────────
#
# 1) 글자 크기의 기준은 **화면의 짧은 변**이다 (unit 함수).
#    예전에는 전부 H(화면 높이) 기준이었다. 가로 화면(1920×1080)에서는 H 가 짧은 변이라
#    맞았지만, 세로 쇼츠(1080×1920)에서는 H 가 **긴 변**이라 글자가 1.78배로 튀었다.
#    금액 카드의 숫자가 240px 로 그려져 카드 폭이 2688px 이 됐고, 1080px 화면에서
#    좌우가 잘려 '9억 8,400만 원' 이 '억 8,400만' 으로 보였다.
#    짧은 변을 기준으로 삼으면 가로·세로 어느 쪽이든 같은 크기로 읽힌다.
#
# 2) 그래도 넘치면 **통째로 줄여서** 넣는다 (fit_in_frame).
#    글자 길이는 회차마다 다르니 계산만으로 100% 막을 수 없다. 마지막에 한 번 더 재서
#    넘치면 줄이고 화면 안으로 민다. 잘린 채로 내보내는 일은 없어야 한다.
SAFE = 0.045                # 화면 가장자리에서 비워 두는 비율.
                            # 유튜브 쇼츠는 좌우에 UI 가 겹치고 기기마다 모서리가 둥글다.

# 자막 — 50·60대 시청자 기준. 폰에서 손 뻗은 거리로 읽혀야 한다.
# 실제 대본(EP001) 자막 길이: 중앙값 28자 · 90% 36자 · 최대 44자.
# 가로는 한 줄 19~20자로 끊어 2줄에 담기고, 아주 긴 줄만 글씨가 살짝 줄어든다.
SUB_SIZE = 0.062            # 짧은 변 대비 글자 크기 (예전 0.042 는 폰에서 작았다)
SUB_SIZE_V = 0.075          # 세로(쇼츠)용 — 화면이 좁아 비율이 다르다
SUB_WIDTH = 0.70            # 가로: 글자가 차지할 최대 폭 (한 줄 19~20자)
SUB_WIDTH_V = 0.88          # 세로: 폭이 좁으니 최대한 쓴다
SUB_LINES = 2               # 가로는 2줄이 기본. 3줄이면 화면 아래가 글자밭이 된다
SUB_LINES_V = 3             # 세로는 한 줄에 12자뿐이라 3줄까지 연다
SUB_BOTTOM = 0.085          # 화면 아래에서 띄우는 여백
SUB_BOTTOM_V = 0.20         # 세로는 UI 가 아래를 가리므로 더 띄운다

# ⭐ 글자에 **역할을 준다.**
#    예전에는 자막·이름표·금액·연표가 전부 나눔고딕Bold 하나였다.
#    전부 같은 인상이라 무엇이 중요한지 화면이 말해주지 못했다.
#    역할마다 글꼴을 달리하면 보는 사람이 읽기 전에 성격을 먼저 안다.
#    네 글꼴 모두 `fonts-nanum` 한 꾸러미에 들어 있어 따로 받을 것이 없다.
NANUM = "/usr/share/fonts/truetype/nanum/"

# 저장소에 직접 올린 폰트를 **가장 먼저** 쓴다 (assets/fonts/).
# KoPub 월드체는 출판용이라 본문 가독성이 좋고 상업적 사용도 무료다. 다만 apt 에 없고
# 이 실행 환경은 외부 내려받기가 막혀 있어 운영자가 올려야 한다.
# 올라오기 전까지는 나눔으로 돌아간다 — 화면이 비지 않게.
USER_FONTS = ROOT / "assets" / "fonts"

FONT_ROLE = {
    "sub":   ["KoPubWorldDotumBold", "NanumSquareB", "NanumGothicBold"],
    "label": ["KoPubWorldDotumMedium", "KoPubWorldDotumBold",
              "NanumBarunGothicBold", "NanumGothicBold"],
    "num":   ["KoPubWorldDotumBold", "NanumSquareB", "NanumGothicBold"],
    "serif": ["KoPubWorldBatangBold", "NanumMyeongjoBold", "NanumGothicBold"],
    "body":  ["KoPubWorldDotumLight", "KoPubWorldDotumMedium",
              "NanumBarunGothic", "NanumGothic"],
}


def _norm(name):
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _find_font(stem):
    """이름이 맞는 폰트 파일을 찾는다. 올린 폰트를 먼저 본다.

    파일 이름의 띄어쓰기·대소문자는 무시하므로 'KoPubWorld Dotum Bold.ttf' 도 잡힌다."""
    want = _norm(stem)
    if USER_FONTS.is_dir():
        for f in sorted(USER_FONTS.iterdir()):
            if f.suffix.lower() in (".ttf", ".otf") and _norm(f.stem) == want:
                return str(f)
    q = Path(NANUM + stem + ".ttf")
    return str(q) if q.exists() else None

# 나눔이 아예 없는 환경을 위한 마지막 대비책
FONT_CANDIDATES = [
    NANUM + "NanumSquareB.ttf",
    NANUM + "NanumGothicBold.ttf",
    NANUM + "NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/unifont/unifont.otf",
]
_font_cache = {}


def font_path(role=None):
    env = os.environ.get("VT_FONT")
    if env and Path(env).exists():
        return env
    for name in FONT_ROLE.get(role or "", []):
        got = _find_font(name)
        if got:
            return got
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    raise RuntimeError(
        "한글 폰트를 찾지 못했다. 워크플로에서 `sudo apt-get install -y fonts-nanum` 을 하거나 "
        "VT_FONT 환경변수로 폰트 경로를 지정하라."
    )


def font(size, role="sub"):
    key = (role, max(6, int(size)))
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(font_path(role), key[1])
    return _font_cache[key]


def unit(W, H):
    """글자 크기의 기준 길이 — 화면의 **짧은 변**. 위 ⭐ 1) 참조.

    가로(1920×1080)든 세로(1080×1920)든 1080 이 나오므로,
    같은 비율을 곱하면 두 화면에서 글자가 **같은 크기로** 읽힌다."""
    return min(W, H)


def fit_in_frame(card, W, H, margin=SAFE):
    """카드가 화면(안전 여백 안쪽)을 넘으면 통째로 줄인다.

    **넘긴 채로 내보내지 않는다.** 넘치면 잘리고, 잘린 자막·금액은
    시청자에게 그냥 오류로 보인다. 조금 작아지는 편이 낫다."""
    maxw = int(W * (1 - 2 * margin))
    maxh = int(H * (1 - 2 * margin))
    if card.width <= maxw and card.height <= maxh:
        return card
    s = min(maxw / card.width, maxh / card.height)
    return card.resize((max(1, round(card.width * s)),
                        max(1, round(card.height * s))), Image.LANCZOS)


def paste_safe(out, card, x, y, margin=SAFE):
    """카드를 화면 안으로 밀어 넣어 붙인다.

    카드 그림에는 흐린 그림자를 담을 여백(PAD)이 둘러 있으므로,
    **눈에 보이는 상자**가 안전 영역 안에 있으면 된다."""
    W, H = out.size
    card = fit_in_frame(card, W, H, margin)
    pad = round(PAD * card.width / max(1, card.width))      # 축소돼도 PAD 는 그대로 취급
    mx = int(W * margin)
    lo, hi = mx - pad, W - mx - card.width + pad
    x = int(min(max(x, lo), hi)) if hi >= lo else (W - card.width) // 2
    y = int(min(max(y, -pad), H - card.height + pad))
    out.paste(card, (x, y), card)
    return out


_measure = ImageDraw.Draw(Image.new("RGB", (8, 8)))


def text_w(s, f):
    """글자가 가로로 차지하는 폭(진행 폭). 가운데 정렬은 이 값으로 해야 맞다."""
    return int(_measure.textlength(s, font=f))


def line_h(f):
    """한 줄이 세로로 차지하는 높이 — 윗공간(ascent) + 아랫공간(descent).

    ⚠️ 이걸 안 쓰고 `textbbox` 높이로 줄을 쌓으면 어긋난다.
    PIL 은 `d.text((x, y))` 의 y 를 '윗공간을 포함한 줄의 꼭대기' 로 잡는데,
    textbbox 높이는 **잉크가 실제로 묻은 부분**만 재기 때문이다.
    이 차이 때문에 금액 카드의 구분선이 숫자를 가로질러 그어졌고,
    자막이 계산보다 아래로 내려가 화면 밑단에 붙었다."""
    a, d = f.getmetrics()
    return a + d


def text_size(d, s, f):
    """잉크가 묻은 네모의 크기. 카드 폭을 잡을 때만 쓴다(세로 배치엔 line_h)."""
    box = d.textbbox((0, 0), s, font=f)
    return box[2] - box[0], box[3] - box[1]


# ── 자막 ────────────────────────────────────────────────
def wrap_korean(s, max_chars=SUB_MAX_CHARS):
    """어절(띄어쓰기) 단위로 끊는다. 한 어절이 max 를 넘으면 그 어절만 통째로 한 줄에 둔다.

    한국어를 글자 수로만 잘라 '정숙 씨는 그 서류의 날' / '짜를 몰랐습니다' 처럼 되면
    어르신 시청자가 읽다가 놓친다.

    ⚠️ **줄 수를 자르지 않는다.** 예전에는 마지막에 `[:3]` 으로 잘랐는데,
    긴 문장의 끝 어절이 소리 없이 사라졌다 ('…본 적이' 에서 '없었습니다.' 가 증발).
    자막은 들리지 않는 사람의 유일한 통로다. 한 글자도 버리면 안 된다.
    넘치면 글자를 줄이는 것은 fit_subtitle 이 맡는다."""
    words = s.split()
    lines, cur = [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if len(cand) <= max_chars or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_subtitle(text, W, H, vertical=False):
    """문장 전체가 들어가는 글자 크기와 줄나눔을 찾는다.

    큰 글씨부터 시작해 목표 줄 수에 들어갈 때까지 조금씩 줄인다.
    끝까지 안 들어가면 줄을 한 줄 더 쓴다 — **글자를 버리는 선택지는 없다.**"""
    base = int(unit(W, H) * (SUB_SIZE_V if vertical else SUB_SIZE))
    floor_px = int(base * 0.74)                 # 이보다 작아지면 어르신이 못 읽는다
    # 안전 여백보다 넓게 잡지 않는다 — 넓게 잡으면 글자가 화면 밖으로 나간다
    maxw = W * min(SUB_WIDTH_V if vertical else SUB_WIDTH, 1 - 2 * SAFE)
    want = SUB_LINES_V if vertical else SUB_LINES

    size = base
    while size >= floor_px:
        lines = _wrap_px(text, font(size), maxw)
        if len(lines) <= want:
            return lines, size
        size = int(size * 0.94)
    return _wrap_px(text, font(floor_px), maxw), floor_px   # 줄이 늘더라도 통째로 보여준다


def _wrap_px(text, f, maxw):
    """실제 글자 폭을 재서 어절 단위로 줄을 나눈다.

    글자 수로 세면 안 된다 — 한글·숫자·쉼표·마침표가 저마다 폭이 달라
    '9억 8,400만 원' 같은 줄에서 한참 어긋난다."""
    lines, cur = [], ""
    for w in str(text).split():
        cand = f"{cur} {w}".strip()
        if text_w(cand, f) <= maxw or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [str(text)]


def _scrim(W, scrim_h, top_alpha=0, bottom_alpha=228, gamma=1.25):
    """아래로 갈수록 짙어지는 그늘 한 겹.

    통짜 검은 띠(예전 방식)는 경계선이 화면을 가로로 뚝 잘라 싸구려로 보인다.
    그늘은 배경과 이어지면서도 글자를 확실히 띄운다 — 방송 자막이 쓰는 방식이다."""
    grad = Image.new("L", (1, scrim_h))
    px = grad.load()
    for i in range(scrim_h):
        t = (i / max(1, scrim_h - 1)) ** gamma
        px[0, i] = int(top_alpha + (bottom_alpha - top_alpha) * t)
    shade = Image.new("RGBA", (W, scrim_h), (10, 11, 15, 255))
    shade.putalpha(grad.resize((W, scrim_h)))
    return shade


def draw_subtitle(img, text, vertical=False):
    """화면 아래쪽 자막.

    고친 것 (예전이 왜 구렸나)
      · 글씨 4.2% → 6.2%. 폰에서 어르신이 읽을 크기가 아니었다
      · 통짜 검은 띠 → 아래로 짙어지는 그늘. 가로줄이 화면을 자르지 않는다
      · 8방향 겹쳐찍기 → PIL 의 stroke_width. 겹쳐찍기는 획 모서리를 뭉갠다
      · 밑에 그림자 한 겹을 깔아 밝은 배경에서도 글자가 뜬다
      · 3줄 → 2줄. 3줄이면 화면 아래 절반이 글자밭이 된다"""
    if not text:
        return img
    W, H = img.size
    lines, size = fit_subtitle(text, W, H, vertical)
    f = font(size)
    lh = line_h(f)
    gap = int(size * 0.16)
    block_h = len(lines) * lh + (len(lines) - 1) * gap

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))

    # 그늘은 글자 블록보다 넉넉히 위에서 시작해 화면 바닥까지 간다
    top = H - int(H * (SUB_BOTTOM_V if vertical else SUB_BOTTOM)) - block_h
    scrim_top = max(0, top - int(size * 1.7))
    layer.paste(_scrim(W, H - scrim_top), (0, scrim_top))

    # ⭐ 테두리를 얇게, 그림자를 부드럽게.
    #    예전에는 테두리가 글자 크기의 8.5%(66px 글자에 5.6px)나 됐다.
    #    그렇게 두꺼우면 'ㅁ' 안쪽이 메워지고 획 모서리가 뭉개져 촌스러워진다.
    #    방송 자막은 **얇은 테두리 + 흐린 그림자**를 쓴다. 글자는 또렷해지고
    #    배경에서 뜨는 효과는 그림자가 대신 맡는다.
    stroke = max(1, round(size * 0.030))
    blur = max(2, round(size * 0.075))
    drop = max(2, round(size * 0.045))

    # 1) 흐린 그림자 — 따로 그려서 번지게 한 뒤 깔아 준다
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    y = top
    for ln in lines:
        x = (W - text_w(ln, f)) // 2
        sd.text((x, y + drop), ln, font=f, fill=(0, 0, 0, 190),
                stroke_width=stroke * 2, stroke_fill=(0, 0, 0, 190))
        y += lh + gap
    layer = Image.alpha_composite(layer, shadow.filter(ImageFilter.GaussianBlur(blur)))

    # 2) 본문 — 흰 글자 + 얇고 짙은 테두리
    d = ImageDraw.Draw(layer)
    y = top
    for ln in lines:
        x = (W - text_w(ln, f)) // 2
        d.text((x, y), ln, font=f, fill=(255, 255, 255, 255),
               stroke_width=stroke, stroke_fill=(12, 12, 16, 235))
        y += lh + gap

    return Image.alpha_composite(img.convert("RGBA"), layer)


def draw_top_line(img, text):
    """쇼츠 첫 화면 위쪽에 얹는 한 줄. 상황을 1초 안에 알려준다.

    넘기다 걸린 사람은 **누가 누군지 전혀 모른다.** 본편을 봐야 알 수 있는 대명사 대신
    이 한 줄로 무슨 상황인지 못 박는다. 아래 자막과 겹치지 않게 화면 위쪽에 둔다."""
    if not text:
        return img
    W, H = img.size
    u = unit(W, H)
    x0, x1 = int(W * max(0.055, SAFE)), int(W * min(0.945, 1 - SAFE))
    # 글자를 배지 안쪽 폭에 맞춘다. 글자 수로 끊으면 회차마다 넘치거나 남는다.
    inner = (x1 - x0) - int(u * 0.10)
    f = _fit_font(u * 0.055, u * 0.034,
                  _wrap_px(text, font(int(u * 0.055), "label"), inner), inner, role="label")
    size = f.size
    lh = line_h(f)
    lines = _wrap_px(text, f, inner)
    gap = int(size * 0.14)
    block = len(lines) * lh + (len(lines) - 1) * gap
    pad_y, pad_x = int(size * 0.42), int(size * 0.9)

    top = int(H * 0.085)
    y0, y1 = top - pad_y, top + block + pad_y
    radius = int(size * 0.42)

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    # 그림자 — 흐린 한 겹. 배지가 화면 위에 떠 보인다
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        [x0, y0 + int(size * 0.22), x1, y1 + int(size * 0.22)], radius, fill=(0, 0, 0, 150))
    layer = Image.alpha_composite(layer, sh.filter(ImageFilter.GaussianBlur(int(size * 0.30))))

    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([x0, y0, x1, y1], radius, fill=INK + (238,))
    d.rectangle([x0, y1 - max(3, round(size * 0.07)), x1, y1], fill=ACCENT)  # 아래 강조선
    y = top
    for ln in lines:
        d.text(((W - text_w(ln, f)) // 2, y), ln, font=f, fill=(255, 253, 250, 255))
        y += lh + gap
    return Image.alpha_composite(img.convert("RGBA"), layer)


# ── 정보 그래픽 4종 ──────────────────────────────────────
PAD = 40                    # 카드 둘레 여백. 흐린 그림자가 잘리지 않게 넉넉히 둔다


def _fit_font(start_px, floor_px, texts, maxw, role="sub"):
    """주어진 글들이 모두 maxw 안에 들어오는 가장 큰 글자 크기를 찾는다.

    회차마다 항목 이름 길이가 제각각이라 크기를 고정하면 어떤 회차에서는 넘친다.
    넘친 글자는 카드 밖에서 잘려 나가 그대로 방송된다 — 크기를 내용에 맞춘다."""
    size = int(start_px)
    floor_px = max(8, int(floor_px))
    while size > floor_px:
        f = font(size, role)
        if all(text_w(t, f) <= maxw for t in texts if t):
            return f
        size -= 1
    return font(floor_px, role)


def _card(w, h, radius=24, accent_top=False):
    """정보 카드 한 장. 판결문을 닮은 미색 종이.

    ⭐ 예전보다 **납작하게** 만든다.
       금색 테두리를 두르고 그림자를 짙게 깔았더니, 종이라기보다 '스티커' 로 보였다.
       테두리를 없애고 그림자를 옅게 낮추면 화면에 얹힌 종이처럼 차분해진다.
       강조가 필요하면 테두리 대신 **위쪽 가는 선 한 줄**(accent_top)만 쓴다."""
    W, H = w + PAD * 2, h + PAD * 2
    box = [PAD, PAD, PAD + w, PAD + h]

    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        [box[0], box[1] + round(h * 0.03) + 4, box[2], box[3] + round(h * 0.03) + 4],
        radius, fill=(0, 0, 0, 105))
    img = sh.filter(ImageFilter.GaussianBlur(PAD * 0.50))

    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius, fill=PAPER + (252,))
    if accent_top:
        # 카드 위쪽에만 강조색 가는 선. 테두리를 두르는 것보다 훨씬 조용하다.
        bar = max(3, round(h * 0.012))
        d.rounded_rectangle([box[0], box[1], box[2], box[1] + radius], radius, fill=ACCENT)
        d.rectangle([box[0], box[1] + bar, box[2], box[1] + radius], fill=PAPER + (252,))
    return img, d, box


# 그래픽 안에 글자를 어디에 그렸는지 기록해 둔다.
# 띠(band)는 **일부러 화면 끝까지** 뻗으므로, 그림 전체를 재면 늘 '화면 밖' 으로 잡힌다.
# 정작 잘리면 안 되는 것은 **글자**다. 그래서 글자 자리만 따로 적어 두고 검사기가 그것을 본다.
_TEXT_BOXES = []


def _t(d, xy, text, f, ox=0, oy=0, **kw):
    """글자를 그리면서 그 자리를 기록한다. ox/oy 는 띠가 화면에 놓일 위치."""
    x, y = xy
    _TEXT_BOXES.append((x + ox, y + oy, x + ox + text_w(text, f), y + oy + line_h(f)))
    d.text((x, y), text, font=f, **kw)


def _band(W, h, alpha=222, accent_top=True):
    """화면 가로를 **끝에서 끝까지** 지나는 띠.

    ⭐ 예전에는 흰 종이 카드를 화면 가운데 띄웠다. 모서리가 둥글고 그림자가 깔린
       흰 상자는 **휴대폰 앱 화면**처럼 보인다 — 다큐멘터리나 드라마의 자막 그래픽이 아니다.
       방송 그래픽은 상자를 띄우지 않는다. **화면 밖으로 흘러나가는 띠** 위에 글자를 얹는다.
       그래야 화면의 일부로 읽히고, 떠 있는 스티커처럼 보이지 않는다."""
    img = Image.new("RGBA", (W, h), INK + (alpha,))
    d = ImageDraw.Draw(img)
    if accent_top:
        d.rectangle([0, 0, W, max(2, round(h * 0.018))], fill=ACCENT)
    d.line([(0, h - 1), (W, h - 1)], fill=HAIR + (60,))
    return img, d


def _pale(t):
    """어두운 띠 위에 올릴 밝은 글자색. 종이색에서 뽑는다(새 색을 만들지 않는다)."""
    return tuple(round(255 - (255 - c) * t) for c in PAPER)


def _spaced(text, gap=" "):
    """'판 결 금 액' 처럼 자간을 벌린다. 작은 라벨을 격식 있게 보이게 한다."""
    return gap.join(list(text.replace(" ", "")))


def g_nametag(text, W=1920, H=1080):
    """인물 이름표 — 방송 로워서드.

    화면 **왼쪽 끝에 붙어** 시작해 오른쪽으로 뻗는다. 떠 있는 알약이 아니라
    화면에 박힌 띠다. 아래에 강조색 가는 선 하나만 둔다."""
    u = unit(W, H)
    f = _fit_font(u * 0.038, u * 0.026, [text], int(W * 0.55), role="label")
    lh = line_h(f)
    # 띠는 화면 왼쪽 끝에서 시작하지만 **글자는 안전 여백 안쪽**에서 시작한다.
    # 쇼츠는 왼쪽 가장자리에 UI 가 겹치는 기기가 있다.
    pad_x, pad_y = round(W * SAFE), round(u * 0.018)
    bw = pad_x + text_w(text, f) + round(u * 0.045)
    bh = lh + pad_y * 2

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    band = Image.new("RGBA", (bw, bh), INK + (228,))
    d = ImageDraw.Draw(band)
    d.rectangle([0, bh - max(3, round(u * 0.005)), bw, bh], fill=ACCENT)
    _t(d, (pad_x, pad_y), text, f,
       oy=round(H * 0.60) - bh // 2, fill=_pale(0.06))
    out.alpha_composite(band, (0, round(H * 0.60) - bh // 2))
    return out


def g_amount(value, note="", W=1920, H=1080):
    """금액 — 화면을 가로지르는 띠 위에 숫자만 크게.

    상자를 없애니 숫자가 화면의 주인이 된다. 라벨은 자간을 벌려 작게,
    숫자는 크게, 설명은 그 아래 가는 선 밑에."""
    u = unit(W, H)
    inner = int(W * (1 - 2 * SAFE))
    cap = font(u * 0.021, "label")
    big = _fit_font(u * 0.130, u * 0.055, [value], inner, role="num")
    small = _fit_font(u * 0.028, u * 0.018, [note] if note else [], inner, role="body")
    label = _spaced("판결금액")

    gap1, gap2 = round(u * 0.014), round(u * 0.020)
    pad = round(u * 0.045)
    bh = (line_h(cap) + gap1 + line_h(big)
          + (gap2 * 2 + line_h(small) if note else 0) + pad * 2)

    band, d = _band(W, bh)
    y = pad
    oy = round(H * 0.16)
    _t(d, ((W - text_w(label, cap)) // 2, y), label, cap, oy=oy, fill=_pale(0.48))
    y += line_h(cap) + gap1
    _t(d, ((W - text_w(value, big)) // 2, y), value, big, oy=oy, fill=_pale(0.02))
    if note:
        y += line_h(big) + gap2
        d.line([(W * 0.42, y), (W * 0.58, y)], fill=_pale(0.65) + (110,), width=2)
        y += gap2
        _t(d, ((W - text_w(note, small)) // 2, y), note, small, oy=oy, fill=_pale(0.42))

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(band, (0, round(H * 0.16)))
    return out


def g_timeline(items, W=1920, H=1080):
    """연표. 판결극장의 반전은 전부 시간 순서다.
    '재혼 열한 달 전'이 말로만 지나가면 충격이 전달되지 않는다.

    상자를 없애고, 화면을 가로지르는 **한 줄** 위에 점을 찍는다."""
    items = items[:5]
    n = max(1, len(items))
    u = unit(W, H)
    x0, x1 = round(W * 0.10), round(W * 0.90)
    slot = (x1 - x0) // max(1, n - 1) if n > 1 else (x1 - x0)

    lab = _fit_font(u * 0.030, u * 0.017,
                    [str(it.get("label", ""))[:16] for it in items], slot - 16, role="label")
    when = _fit_font(u * 0.025, u * 0.015,
                     [str(it.get("when", ""))[:14] for it in items], slot - 16, role="body")

    pad = round(u * 0.045)
    bh = pad * 2 + line_h(lab) + round(u * 0.055) + line_h(when)
    band, d = _band(W, bh)

    y_line = pad + line_h(lab) + round(u * 0.028)
    d.line([(x0, y_line), (x1, y_line)], fill=_pale(0.70) + (120,), width=2)

    for i, it in enumerate(items):
        x = x0 + slot * i if n > 1 else (x0 + x1) // 2
        last = (i == n - 1)
        r = round(u * 0.0085)
        if last:
            d.ellipse([x - r * 2, y_line - r * 2, x + r * 2, y_line + r * 2],
                      outline=ACCENT, width=max(2, round(u * 0.003)))
        d.ellipse([x - r, y_line - r, x + r, y_line + r],
                  fill=ACCENT if last else _pale(0.55))

        t1 = str(it.get("label", ""))[:16]
        t2 = str(it.get("when", ""))[:14]
        lo, hi = round(W * SAFE), W - round(W * SAFE)
        tx1 = min(max(x - text_w(t1, lab) // 2, lo), hi - text_w(t1, lab))
        tx2 = min(max(x - text_w(t2, when) // 2, lo), hi - text_w(t2, when))
        oy = round(H * 0.15)
        _t(d, (tx1, pad), t1, lab, oy=oy, fill=_pale(0.04))
        _t(d, (tx2, y_line + round(u * 0.024)), t2, when, oy=oy,
           fill=ACCENT if last else _pale(0.45))

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(band, (0, round(H * 0.15)))
    return out


def g_family(nodes, W=1920, H=1080):
    """가족 관계도. 상속 사건은 관계 파악이 전제다. 도표 1장이 5분 설명을 대체한다.

    네모 상자를 없앤다. 이름을 한 줄에 늘어놓고 가는 선으로만 잇는다."""
    nodes = nodes[:5]
    n = max(1, len(nodes))
    u = unit(W, H)
    x0, x1 = round(W * 0.10), round(W * 0.90)
    slot = (x1 - x0) / max(1, n)

    nm = _fit_font(u * 0.034, u * 0.020,
                   [str(x.get("name", ""))[:8] for x in nodes], int(slot * 0.88), role="label")
    rel = _fit_font(u * 0.024, u * 0.014,
                    [str(x.get("rel", ""))[:12] for x in nodes], int(slot * 0.92), role="body")

    pad = round(u * 0.048)
    bh = pad * 2 + line_h(nm) + round(u * 0.016) + line_h(rel)
    band, d = _band(W, bh)

    y_nm = pad
    y_rel = pad + line_h(nm) + round(u * 0.016)
    y_mid = y_nm + line_h(nm) // 2
    for i, nd in enumerate(nodes):
        cx = round(x0 + slot * (i + 0.5))
        t1 = str(nd.get("name", ""))[:8]
        t2 = str(nd.get("rel", ""))[:12]
        w1 = text_w(t1, nm)
        if i < n - 1:                       # 이름과 이름 사이를 가는 선으로 잇는다
            nx = round(x0 + slot * (i + 1.5))
            w2 = text_w(str(nodes[i + 1].get("name", ""))[:8], nm)
            a, b = cx + w1 // 2 + round(u * 0.018), nx - w2 // 2 - round(u * 0.018)
            if b > a:
                d.line([(a, y_mid), (b, y_mid)], fill=_pale(0.72) + (110,), width=2)
        oy = round(H * 0.16)
        _t(d, (cx - w1 // 2, y_nm), t1, nm, oy=oy, fill=_pale(0.04))
        _t(d, (cx - text_w(t2, rel) // 2, y_rel), t2, rel, oy=oy, fill=_pale(0.45))

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.alpha_composite(band, (0, round(H * 0.16)))
    return out


GFX = {"nametag": g_nametag, "amount": g_amount, "timeline": g_timeline, "family": g_family}


def render_gfx(spec, W=1920, H=1080):
    """대본의 gfx 항목을 그림으로 바꾼다. 모르는 종류면 None."""
    _TEXT_BOXES.clear()
    if not spec:
        return None
    t = spec.get("type")
    fn = GFX.get(t)
    if not fn:
        return None
    if t == "nametag":
        return fn(spec.get("text", ""), W, H)
    if t == "amount":
        return fn(spec.get("value", ""), spec.get("note", ""), W, H)
    if t == "timeline":
        return fn(spec.get("items", []), W, H)
    if t == "family":
        return fn(spec.get("nodes", []), W, H)
    return None


# ── 배경 처리 ────────────────────────────────────────────
def prepare_bg(path, W=1920, H=1080, flashback=False, blur=14):
    """배경을 블러 처리해 깔개로 만든다.

    블러가 두 가지를 해결한다.
      1. AI 생성 결함(깨진 한글 간판, 뒤틀린 원근)을 덮는다
      2. 배경 재사용이 드러나지 않는다
    회상은 저채도 세피아 + 비네트로 시간을 구분한다. 없으면 시청자가 시간을 못 따라간다."""
    from PIL import ImageEnhance
    img = Image.open(path).convert("RGB")
    # 화면비에 맞춰 잘라 채우기
    sw, sh = img.size
    scale = max(W / sw, H / sh)
    img = img.resize((int(sw * scale), int(sh * scale)), Image.LANCZOS)
    left, top = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((left, top, left + W, top + H))
    img = img.filter(ImageFilter.GaussianBlur(blur))

    if flashback:
        img = ImageEnhance.Color(img).enhance(0.35)         # 저채도
        sep = Image.new("RGB", img.size, (112, 88, 58))
        img = Image.blend(img, sep, 0.22)                    # 세피아
        img = ImageEnhance.Brightness(img).enhance(0.92)
        img = _vignette(img, 0.55)
    else:
        img = ImageEnhance.Brightness(img).enhance(0.78)     # 인물이 떠 보이게 살짝 어둡게
        img = _vignette(img, 0.35)
    return img.convert("RGBA")


def _vignette(img, strength):
    W, H = img.size
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse([-int(W * 0.25), -int(H * 0.35), int(W * 1.25), int(H * 1.35)], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(int(min(W, H) * 0.12)))
    dark = Image.new("RGB", (W, H), (0, 0, 0))
    return Image.composite(img, Image.blend(img, dark, strength), mask)


# ── 시험용 ──────────────────────────────────────────────
def demo(outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    samples = {
        "nametag": {"type": "nametag", "text": "한정숙 · 68세 · 아내"},
        "amount": {"type": "amount", "value": "1억 5,600만 원", "note": "십 년의 새벽"},
        "timeline": {"type": "timeline", "items": [
            {"label": "아들과 땅 계약", "when": "스물여섯 해 전"},
            {"label": "정숙 씨와 재혼", "when": "열한 달 뒤"},
            {"label": "남편 사망", "when": "십 년 뒤"}]},
        "family": {"type": "family", "nodes": [
            {"name": "한정숙", "rel": "아내 · 3/7"},
            {"name": "서동일", "rel": "아들 · 2/7"},
            {"name": "서미경", "rel": "딸 · 2/7"}]},
    }
    base = Image.new("RGBA", (1920, 1080), (40, 44, 52, 255))
    for name, spec in samples.items():
        layer = render_gfx(spec)
        img = Image.alpha_composite(base, layer)
        img = draw_subtitle(img, "정숙 씨는 그 서류의 날짜를 몰랐습니다. 아직은.")
        p = out / f"gfx_{name}.png"
        img.convert("RGB").save(p, quality=92)
        print(f"  {p}  {img.size}")

    print("\n자막 줄바꿈 시험 — 원문이 한 글자도 빠지지 않아야 한다")
    bad = 0
    for s in ["그 땅은, 처음부터 제 겁니다.",
              "정숙 씨는 그 서류의 날짜를 몰랐습니다. 아직은.",
              "먼 나라의 땅 하나. 칠억이 넘었지만 정숙 씨는 본 적이 없었습니다.",
              "그날 아침 정숙 씨가 받아 든 등기부등본에는, 십 년을 함께 산 남편의 "
              "이름이 어디에도 남아 있지 않았습니다."]:
        lines, size = fit_subtitle(s, 1920, 1080)
        print(f"  원문: {s}")
        for ln in lines:
            print(f"    | {ln}")
        keep = "".join(lines).replace(" ", "") == s.replace(" ", "")
        print(f"    {len(lines)}줄 · {size}px · 원문 보존 {'OK' if keep else '❌ 글자 유실'}")
        bad += 0 if keep else 1
    return 1 if bad else 0


def ink_box(img, thresh=40):
    """또렷하게 보이는 부분만의 범위. 흐린 그림자는 빼고 잰다.

    ⚠️ 그냥 `getbbox()` 를 쓰면 안 된다. 카드 그림자를 가우시안 블러로 번지게 하므로
    아주 옅은 알파가 화면 끝까지 깔린다. 그러면 어떤 그림이든 '화면 가득' 으로 나와서
    `bb[0] < 0` 같은 검사는 **영원히 통과** 하는 허수가 된다.
    실제로 자막·쇼츠 도입문 검사가 그렇게 헛돌고 있었다."""
    a = img.getchannel("A").point(lambda v: 255 if v >= thresh else 0)
    return a.getbbox()


def check_frame(script_path):
    """대본의 **모든** 자막·그래픽을 가로·세로 양쪽으로 그려 보고,
    화면 밖으로 나가는 것이 하나라도 있으면 실패로 알린다.

    왜 필요한가: 세로 쇼츠에서 금액 카드가 좌우로 잘려 '9억 8,400만 원' 이
    '억 8,400만' 으로 방송됐다. 사람 눈으로 113컷 × 2방향을 다 볼 수는 없다.
    글자 길이는 회차마다 달라지므로, 회차마다 기계가 재야 한다."""
    import json
    doc = json.loads(Path(script_path).read_text(encoding="utf-8"))
    cuts = [c for a in doc["acts"] for c in a["cuts"]]
    shapes = [("가로", 1920, 1080, False), ("세로", 1080, 1920, True)]
    bad = []

    def probe(tag, name, img, W, limit):
        """또렷한 부분이 안전 여백 안에 있는지. limit 은 좌우로 허용하는 최소 여백."""
        bb = ink_box(img)
        if bb and (bb[0] < limit or bb[2] > W - limit):
            bad.append(f"{tag} {name} 가로 {bb[0]}~{bb[2]} (화면 {W}, 여백 {limit:.0f} 필요)")

    for tag, W, H, vert in shapes:
        limit = W * SAFE * 0.5
        # 자막 한 줄이 실제로 차지하는 폭도 직접 잰다 — 그림으로만 보면 놓치는 경우가 있다
        sub_max = W * (1 - 2 * SAFE)
        for c in cuts:
            if c.get("gfx"):
                lay = render_gfx(c["gfx"], W, H)
                if lay:
                    # 띠는 일부러 화면 끝까지 뻗는다. 글자만 안전 여백 안에 있으면 된다.
                    for bx0, _by0, bx1, _by1 in _TEXT_BOXES:
                        if bx0 < limit or bx1 > W - limit:
                            bad.append(f"{tag} {c['id']} {c['gfx'].get('type')} "
                                       f"글자 {bx0}~{bx1} (화면 {W}, 여백 {limit:.0f} 필요)")
                            break
            txt = (c.get("text") or "").strip()
            if not txt:
                continue
            # 자막은 **그림으로 재지 않는다.** 아래 그늘(scrim)이 일부러 화면 폭을 다 쓰므로
            # 그림을 재면 언제나 '가로 0~W' 로 나와 전부 위반으로 잡힌다.
            # 실제로 넘치면 안 되는 것은 **글자**다 — 글자 폭을 직접 잰다.
            lines, size = fit_subtitle(txt, W, H, vert)
            f = font(size)
            wide = [ln for ln in lines if text_w(ln, f) > sub_max]
            if wide:
                bad.append(f"{tag} {c['id']} 자막 줄이 폭 초과: {wide[0][:20]}…")
            if "".join(lines).replace(" ", "") != txt.replace(" ", ""):
                bad.append(f"{tag} {c['id']} 자막 글자 유실")

    # 쇼츠 도입·마무리 문장도 세로로 확인한다
    for s in doc.get("shorts", []):
        t = (s.get("intro_line") or "").strip()
        if t:                                   # 도입은 금색 배지 — 그림으로 잰다
            blank = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
            probe("세로", f"쇼츠{s.get('no')} intro_line",
                  draw_top_line(blank, t), 1080, 1080 * SAFE * 0.5)
        t = (s.get("outro_line") or "").strip()
        if t:                                   # 마무리는 자막으로 나간다 — 글자 폭을 잰다
            lines, size = fit_subtitle(t, 1080, 1920, True)
            f = font(size)
            if any(text_w(ln, f) > 1080 * (1 - 2 * SAFE) for ln in lines):
                bad.append(f"세로 쇼츠{s.get('no')} outro_line 글자가 폭 초과")
            if "".join(lines).replace(" ", "") != t.replace(" ", ""):
                bad.append(f"세로 쇼츠{s.get('no')} outro_line 글자 유실")

    n = len(cuts)
    if bad:
        print(f"❌ 화면 밖으로 나가는 것 {len(bad)}건 (컷 {n}개 × 가로·세로 검사)")
        for b in bad[:20]:
            print(f"   {b}")
        if len(bad) > 20:
            print(f"   … 외 {len(bad) - 20}건")
        return 1
    print(f"✅ 컷 {n}개를 가로·세로 양쪽으로 확인 — 화면 밖으로 나가는 것 없음")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", default="", help="시험 이미지를 이 폴더에 만든다")
    ap.add_argument("--check", default="", help="이 대본의 모든 컷이 화면 안에 드는지 검사")
    a = ap.parse_args()
    if a.check:
        sys.exit(check_frame(a.check))
    if a.demo:
        sys.exit(demo(a.demo))
    print(f"폰트: {font_path()}")
