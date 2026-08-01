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
INK = (24, 24, 28)
PAPER = (250, 249, 246)
GOLD = (198, 160, 74)
CRIMSON = (176, 58, 46)
SLATE = (86, 92, 104)
LINE = (214, 210, 202)
SHADOW = (0, 0, 0, 110)

SUB_MAX_CHARS = 18          # wrap_korean 의 기본값 (자막은 fit_subtitle 이 폭을 직접 잰다)

# 자막 — 50·60대 시청자 기준. 폰에서 손 뻗은 거리로 읽혀야 한다.
# 실제 대본(EP001) 자막 길이: 중앙값 28자 · 90% 36자 · 최대 44자.
# 가로는 한 줄 19~20자로 끊어 2줄에 담기고, 아주 긴 줄만 글씨가 살짝 줄어든다.
SUB_SIZE = 0.062            # 화면 높이 대비 글자 크기 (예전 0.042 는 폰에서 작았다)
SUB_SIZE_V = 0.042          # 세로(쇼츠)용 — 화면이 좁아 비율이 다르다
SUB_WIDTH = 0.70            # 가로: 글자가 차지할 최대 폭 (한 줄 19~20자)
SUB_WIDTH_V = 0.88          # 세로: 폭이 좁으니 최대한 쓴다
SUB_LINES = 2               # 가로는 2줄이 기본. 3줄이면 화면 아래가 글자밭이 된다
SUB_LINES_V = 3             # 세로는 한 줄에 12자뿐이라 3줄까지 연다
SUB_BOTTOM = 0.085          # 화면 아래에서 띄우는 여백
SUB_BOTTOM_V = 0.20         # 세로는 UI 가 아래를 가리므로 더 띄운다

# 한글이 나오는 폰트를 순서대로 찾는다. 러너에는 fonts-nanum 을 설치한다.
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/unifont/unifont.otf",
]
_font_cache = {}


def font_path():
    env = os.environ.get("VT_FONT")
    if env and Path(env).exists():
        return env
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    raise RuntimeError(
        "한글 폰트를 찾지 못했다. 워크플로에서 `sudo apt-get install -y fonts-nanum` 을 하거나 "
        "VT_FONT 환경변수로 폰트 경로를 지정하라."
    )


def font(size):
    key = size
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(font_path(), size)
    return _font_cache[key]


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
    base = int(H * (SUB_SIZE_V if vertical else SUB_SIZE))
    floor_px = int(base * 0.74)                 # 이보다 작아지면 어르신이 못 읽는다
    maxw = W * (SUB_WIDTH_V if vertical else SUB_WIDTH)
    want = SUB_LINES_V if vertical else SUB_LINES
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    def wrap_px(size):
        """실제 글자 폭을 재서 나눈다. 글자 수는 한글·숫자·문장부호마다 폭이 달라 부정확하다."""
        f = font(size)
        lines, cur = [], ""
        for w in text.split():
            cand = f"{cur} {w}".strip()
            if text_size(tmp, cand, f)[0] <= maxw or not cur:
                cur = cand
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines or [text]

    size = base
    while size >= floor_px:
        lines = wrap_px(size)
        if len(lines) <= want:
            return lines, size
        size = int(size * 0.94)
    return wrap_px(floor_px), floor_px         # 한 줄 더 늘어나더라도 통째로 보여준다


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

    d = ImageDraw.Draw(layer)
    stroke = max(2, int(size * 0.085))
    drop = max(2, int(size * 0.06))
    y = top
    for ln in lines:
        x = (W - text_w(ln, f)) // 2
        # 1) 아래로 살짝 내린 그림자 — 배경에서 글자를 떼어 놓는다
        d.text((x, y + drop), ln, font=f, fill=(0, 0, 0, 120),
               stroke_width=stroke, stroke_fill=(0, 0, 0, 120))
        # 2) 본문 — 흰 글자 + 아주 짙은 테두리
        d.text((x, y), ln, font=f, fill=(255, 255, 255, 255),
               stroke_width=stroke, stroke_fill=(10, 10, 14, 240))
        y += lh + gap

    return Image.alpha_composite(img.convert("RGBA"), layer)


def draw_top_line(img, text):
    """쇼츠 첫 화면 위쪽에 얹는 한 줄. 상황을 1초 안에 알려준다.

    넘기다 걸린 사람은 **누가 누군지 전혀 모른다.** 본편을 봐야 알 수 있는 대명사 대신
    이 한 줄로 무슨 상황인지 못 박는다. 아래 자막과 겹치지 않게 화면 위쪽에 둔다."""
    if not text:
        return img
    W, H = img.size
    size = int(H * 0.042)
    f = font(size)
    lh = line_h(f)
    lines = wrap_korean(text, 13)
    gap = int(size * 0.14)
    block = len(lines) * lh + (len(lines) - 1) * gap
    pad_y, pad_x = int(size * 0.42), int(size * 0.9)

    top = int(H * 0.085)
    x0, x1 = int(W * 0.055), int(W * 0.945)
    y0, y1 = top - pad_y, top + block + pad_y
    radius = int(size * 0.42)

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    # 그림자 — 흐린 한 겹. 배지가 화면 위에 떠 보인다
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        [x0, y0 + int(size * 0.22), x1, y1 + int(size * 0.22)], radius, fill=(0, 0, 0, 150))
    layer = Image.alpha_composite(layer, sh.filter(ImageFilter.GaussianBlur(int(size * 0.30))))

    d = ImageDraw.Draw(layer)
    d.rounded_rectangle([x0, y0, x1, y1], radius, fill=GOLD + (242,))
    d.rounded_rectangle([x0, y0, x1, y1], radius, outline=(255, 246, 222, 190),
                        width=max(2, int(size * 0.055)))
    y = top
    for ln in lines:
        d.text(((W - text_w(ln, f)) // 2, y), ln, font=f, fill=(30, 24, 10, 255))
        y += lh + gap
    return Image.alpha_composite(img.convert("RGBA"), layer)


# ── 정보 그래픽 4종 ──────────────────────────────────────
PAD = 40                    # 카드 둘레 여백. 흐린 그림자가 잘리지 않게 넉넉히 둔다


def _fit_font(start_px, floor_px, texts, maxw):
    """주어진 글들이 모두 maxw 안에 들어오는 가장 큰 글자 크기를 찾는다.

    회차마다 항목 이름 길이가 제각각이라 크기를 고정하면 어떤 회차에서는 넘친다.
    넘친 글자는 카드 밖에서 잘려 나가 그대로 방송된다 — 크기를 내용에 맞춘다."""
    size = int(start_px)
    floor_px = max(8, int(floor_px))
    while size > floor_px:
        f = font(size)
        if all(text_w(t, f) <= maxw for t in texts if t):
            return f
        size -= 1
    return font(floor_px)


def _card(w, h, radius=24):
    """종이 카드 한 장. 판결문 느낌의 미색 종이 + 흐린 그림자 + 금색 실선.

    예전에는 그림자를 '4픽셀 내린 같은 모양'으로 그렸다. 경계가 딱 떨어져
    스티커를 붙인 것처럼 보였다. 흐리게 번지는 그림자로 바꾸면 카드가 화면 위에 뜬다."""
    W, H = w + PAD * 2, h + PAD * 2
    box = [PAD, PAD, PAD + w, PAD + h]

    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle(
        [box[0], box[1] + int(h * 0.05) + 6, box[2], box[3] + int(h * 0.05) + 6],
        radius, fill=(0, 0, 0, 165))
    img = sh.filter(ImageFilter.GaussianBlur(PAD * 0.42))

    d = ImageDraw.Draw(img)
    d.rounded_rectangle(box, radius, fill=PAPER + (250,))
    d.rounded_rectangle(box, radius, outline=GOLD + (150,), width=3)     # 금색 실선 한 겹
    return img, d, box


def g_nametag(text, W=1920, H=1080):
    """인물 이름표. 고정 배우 7명을 회차마다 다른 역으로 쓰므로 없으면 누가 누군지 모른다.

    자리를 옮겼다. 예전에는 화면 높이 70% 지점 — 인물 몸통 한가운데였다.
    방송 자막처럼 왼쪽 아래, 자막 그늘 바로 위에 둔다."""
    size = int(H * 0.036)
    f = font(size)
    lh = line_h(f)
    pad_x, pad_y = int(size * 0.95), int(size * 0.34)
    bar_x, bar_w = int(size * 0.55), max(4, int(size * 0.14))
    cw = bar_x + bar_w + pad_x + text_w(text, f) + pad_x
    ch = lh + pad_y * 2

    card, d, box = _card(cw, ch, radius=int(ch * 0.24))
    x0, y0 = box[0], box[1]
    # 붉은 세로 막대는 카드 **안쪽**에 둔다. 예전엔 카드 왼쪽 모서리에 붙여 그려
    # 둥근 모서리 밖으로 삐져나온 혹처럼 보였다.
    d.rounded_rectangle([x0 + bar_x, y0 + pad_y, x0 + bar_x + bar_w, y0 + ch - pad_y],
                        bar_w // 2, fill=CRIMSON)
    d.text((x0 + bar_x + bar_w + pad_x, y0 + pad_y), text, font=f, fill=INK)

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # 자막 그늘이 시작되는 높이보다 위. 인물 얼굴·자막 어느 쪽도 가리지 않는다
    y = int(H * 0.60) - card.height // 2
    out.paste(card, (int(W * 0.05) - PAD, y), card)
    return out


def g_amount(value, note="", W=1920, H=1080):
    """금액 강조. 숫자는 귀로 들어오지 않는다. 큰 글씨로 화면에 박는다.

    금액 위에 '판결 금액' 이라는 작은 표찰을 붙인다. 숫자만 덩그러니 뜨면
    그게 받은 돈인지 못 받은 돈인지 알 수 없어 시청자가 멈칫한다."""
    cap = font(int(H * 0.026))
    big = font(int(H * 0.125))
    small = font(int(H * 0.032))
    label = "판 결 금 액"
    lw, lh_ = text_w(label, cap), line_h(cap)
    vw, vh = text_w(value, big), line_h(big)
    nw, nh = (text_w(note, small), line_h(small)) if note else (0, 0)

    gap1, gap2 = int(H * 0.006), int(H * 0.024)
    pad = int(H * 0.040)
    cw = max(vw, nw, lw) + int(H * 0.15)
    ch = lh_ + gap1 + vh + (gap2 * 2 + nh if note else 0) + pad * 2
    card, d, box = _card(cw, ch, radius=int(H * 0.028))
    x0, y0 = box[0], box[1]

    y = y0 + pad
    d.text((x0 + (cw - lw) // 2, y), label, font=cap, fill=GOLD)
    y += lh_ + gap1
    d.text((x0 + (cw - vw) // 2, y), value, font=big, fill=CRIMSON)
    if note:
        y += vh + gap2
        # 숫자와 설명 사이 가는 구분선. 줄 높이(line_h)로 자리를 잡아야
        # 선이 숫자를 가로지르지 않는다 — 잉크 높이로 재면 선이 숫자 위로 올라온다.
        d.line([(x0 + int(cw * 0.36), y), (x0 + int(cw * 0.64), y)], fill=LINE, width=3)
        y += gap2
        d.text((x0 + (cw - nw) // 2, y), note, font=small, fill=SLATE)

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(card, ((W - card.width) // 2, int(H * 0.14) - PAD), card)
    return out


def g_timeline(items, W=1920, H=1080):
    """연표. 판결극장의 반전은 전부 시간 순서다.
    '재혼 열한 달 전'이 말로만 지나가면 충격이 전달되지 않는다."""
    items = items[:5]
    n = max(1, len(items))
    cw, ch = int(W * 0.86), int(H * 0.31)

    # 글자를 슬롯 안에 맞춘다. 예전에는 크기를 고정해 두어 마지막 항목
    # '장남, 유류분 소장 제출' 이 카드 오른쪽 밖으로 잘려 나갔다.
    slot = int(cw * 0.80 / max(1, n - 1)) if n > 1 else int(cw * 0.8)
    lab = _fit_font(H * 0.032, H * 0.021,
                    [str(it.get("label", ""))[:16] for it in items], slot - 12)
    when = _fit_font(H * 0.027, H * 0.019,
                     [str(it.get("when", ""))[:14] for it in items], slot - 12)

    card, d, box = _card(cw, ch, radius=int(H * 0.028))
    bx, by = box[0], box[1]

    y_line = by + int(ch * 0.54)
    x0, x1 = bx + int(cw * 0.10), bx + int(cw * 0.90)
    d.line([(x0, y_line), (x1, y_line)], fill=LINE, width=5)

    step = (x1 - x0) / max(1, n - 1) if n > 1 else 0
    for i, it in enumerate(items):
        x = int(x0 + step * i) if n > 1 else (x0 + x1) // 2
        last = (i == n - 1)
        color = CRIMSON if last else GOLD
        r = int(H * 0.0155)
        # 마지막(결정적) 시점만 테두리를 둘러 눈이 먼저 간다
        d.ellipse([x - r - 7, y_line - r - 7, x + r + 7, y_line + r + 7],
                  fill=PAPER + (255,))
        d.ellipse([x - r, y_line - r, x + r, y_line + r], fill=color)
        if last:
            d.ellipse([x - r - 11, y_line - r - 11, x + r + 11, y_line + r + 11],
                      outline=color + (120,), width=4)

        t1 = str(it.get("label", ""))[:16]
        t2 = str(it.get("when", ""))[:14]
        # 양 끝 항목은 가운데 정렬하면 카드 밖으로 넘친다. 카드 안으로 밀어 넣는다.
        lo, hi = bx + 10, bx + cw - 10
        tx1 = min(max(x - text_w(t1, lab) // 2, lo), hi - text_w(t1, lab))
        tx2 = min(max(x - text_w(t2, when) // 2, lo), hi - text_w(t2, when))
        d.text((tx1, y_line - int(ch * 0.14) - line_h(lab)), t1, font=lab, fill=INK)
        d.text((tx2, y_line + int(ch * 0.11)), t2, font=when, fill=color)

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(card, ((W - card.width) // 2, int(H * 0.12) - PAD), card)
    return out


def g_family(nodes, W=1920, H=1080):
    """가족 관계도. 상속 사건은 관계 파악이 전제다. 도표 1장이 5분 설명을 대체한다."""
    nodes = nodes[:5]
    n = max(1, len(nodes))
    nm = font(int(H * 0.034))
    rel = font(int(H * 0.026))

    cw, ch = int(W * 0.80), int(H * 0.29)
    card, d, box = _card(cw, ch, radius=int(H * 0.028))
    bx, by = box[0], box[1]

    y = by + int(ch * 0.52)
    slot = cw / n
    for i, nd in enumerate(nodes):
        cx = int(bx + slot * (i + 0.5))
        bw, bh = int(slot * 0.76), int(ch * 0.50)
        if i < n - 1:                      # 이음선을 먼저 — 상자 뒤로 들어간다
            d.line([(cx, y), (int(bx + slot * (i + 1.5)), y)], fill=LINE, width=5)

        t1 = str(nd.get("name", ""))[:8]
        t2 = str(nd.get("rel", ""))[:12]
        d.rounded_rectangle([cx - bw // 2, y - bh // 2, cx + bw // 2, y + bh // 2],
                            int(bh * 0.20), outline=LINE, width=3, fill=(255, 255, 255, 255))
        d.rectangle([cx - bw // 2 + 2, y - bh // 2 + 2,
                     cx - bw // 2 + int(bw * 0.035), y + bh // 2 - 2], fill=GOLD)  # 왼쪽 금색 띠
        d.text((cx - text_w(t1, nm) // 2, y - int(bh * 0.30)), t1, font=nm, fill=INK)
        d.line([(cx - int(bw * 0.28), y + int(bh * 0.045)),
                (cx + int(bw * 0.28), y + int(bh * 0.045))], fill=LINE, width=2)
        d.text((cx - text_w(t2, rel) // 2, y + int(bh * 0.10)), t2, font=rel, fill=SLATE)

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(card, ((W - card.width) // 2, int(H * 0.13) - PAD), card)
    return out


GFX = {"nametag": g_nametag, "amount": g_amount, "timeline": g_timeline, "family": g_family}


def render_gfx(spec, W=1920, H=1080):
    """대본의 gfx 항목을 그림으로 바꾼다. 모르는 종류면 None."""
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", default="", help="시험 이미지를 이 폴더에 만든다")
    a = ap.parse_args()
    if a.demo:
        sys.exit(demo(a.demo))
    print(f"폰트: {font_path()}")
