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

# 이름은 띄어쓰기·밑줄·대소문자를 무시하고 견준다.
#   'KoPub_Dotum_Pro_Bold.otf' · 'KoPubWorld Dotum Bold.ttf' 둘 다 잡힌다.
# ⭐ 화면 글자는 **전부 바탕체(명조)** 로 간다.
#    고딕은 정보를 전달하는 글씨다 — 웹페이지·안내판·자막방송이 쓴다.
#    판결극장은 드라마다. 드라마 자막·타이틀 카드는 바탕체가 정석이고,
#    획 끝의 삐침이 화면에 무게와 시대감을 준다. 굵기로만 층을 나눈다.
#      Bold   자막 · 금액 숫자 · 회상 시점
#      Medium 이름표 · 항목 이름
#      Light  나이·관계 같은 보조 설명
FONT_ROLE = {
    "sub":   ["KoPubBatangProBold", "KoPubWorldBatangBold",
              "NanumMyeongjoBold", "NanumGothicBold"],
    "label": ["KoPubBatangProMedium", "KoPubWorldBatangMedium",
              "KoPubBatangProBold", "NanumMyeongjoBold", "NanumGothicBold"],
    "num":   ["KoPubBatangProBold", "KoPubWorldBatangBold",
              "NanumMyeongjoBold", "NanumGothicBold"],
    "serif": ["KoPubBatangProBold", "KoPubWorldBatangBold",
              "NanumMyeongjoBold", "NanumGothicBold"],
    "body":  ["KoPubBatangProLight", "KoPubWorldBatangLight",
              "KoPubBatangProMedium", "NanumMyeongjo", "NanumGothic"],
}

# ⭐ 글자 크기표 — 짧은 변(unit) 대비 (시작 크기, 최소 크기).
#    여기가 "홈페이지 같다" 던 원인이다. 라벨을 1.9%(1080p 에서 20픽셀)로 두면
#    웹페이지 각주처럼 보인다. 드라마 카드는 **폰을 무릎에 놓고도** 읽혀야 한다.
#    기준을 정한다 — 자막이 6.2%. 어떤 보조 글자도 그 3분의 1(2.1%) 아래로 두지 않는다.
#    한곳에 모아 두어야 회차마다 감으로 고치지 않는다.
TEXT = {
    "name":     (0.052, 0.036),   # 이름표 — 인물 이름
    "name_sub": (0.032, 0.023),   # 이름표 — 나이·관계
    "amt_lab":  (0.040, 0.026),   # 금액이 무슨 돈인지 ('부당이득 반환 금액')
    "amt_num":  (0.155, 0.070),   # 금액 숫자
    "tl_lab":   (0.040, 0.025),   # 연표 항목
    "tl_when":  (0.033, 0.022),   # 연표 시점
    "fam_name": (0.050, 0.031),   # 가족 이름
    "fam_rel":  (0.035, 0.023),   # 가족 관계
    "time_cap": (0.072, 0.042),   # 회상 시점 자막
    "top_line": (0.056, 0.036),   # 쇼츠 상단 한 줄
}


def _px(key, u):
    """크기표의 비율을 실제 픽셀 (시작, 최소) 로 바꾼다."""
    a, b = TEXT[key]
    return u * a, u * b


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
    이 한 줄로 무슨 상황인지 못 박는다. 본문 그래픽과 같은 방향(판 없음)으로 —
    강조색 짧은 선 하나와 글자만."""
    if not text:
        return img
    W, H = img.size
    u = unit(W, H)
    inner = int(W * (1 - 2 * max(0.075, SAFE)))
    f = _fit_font(*_px("top_line", u),
                  _wrap_px(text, font(int(u * TEXT["top_line"][0]), "label"), inner),
                  inner, role="label")
    lines = _wrap_px(text, f, inner)
    lh, gap = line_h(f), round(f.size * 0.14)

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    y = round(H * 0.085)
    d.line([(W // 2 - round(u * 0.050), y), (W // 2 + round(u * 0.050), y)],
           fill=ACCENT, width=max(3, round(u * 0.005)))
    y += round(u * 0.030)
    for ln in lines:
        d.text(((W - text_w(ln, f)) // 2, y), ln, font=f, fill=_pale(0.02))
        y += lh + gap
    return Image.alpha_composite(img.convert("RGBA"), _lift(layer, radius=round(u * 0.011)))


def draw_time_caption(img, text):
    """회상으로 들어갈 때 화면 가운데 잠깐 뜨는 시점 자막 — '십수 년 전'.

    색만 세피아로 바뀌면 시청자는 '화면이 이상해졌다' 로 본다.
    **언제인지 글자로 말해 줘야** 시간이 옮겨간 것을 안다.
    본문 그래픽과 같은 방향(판 없음) — 위아래 가는 선 사이에 글자만."""
    if not text:
        return img
    W, H = img.size
    u = unit(W, H)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    f = _fit_font(*_px("time_cap", u), [text], int(W * (1 - 2 * SAFE) * 0.8), role="serif")
    tw = text_w(text, f)
    # ⚠️ 0.40 은 인물 얼굴 높이다. 실제 컷아웃을 넣어 보니 '사십 년 전' 이
    #    어머니 이마를 가로질렀다. 인물 머리 **위쪽**으로 올린다.
    #    (넓은 정보 카드는 0.175~0.235 에 있고, 시점 자막과 같은 컷에 나오지 않는다.)
    cx, cy = W // 2, round(H * (0.30 if H > W else 0.27))
    half = max(tw // 2 + round(u * 0.055), round(u * 0.13))
    lw = max(2, round(u * 0.0025))
    gap = round(u * 0.030)

    d.line([(cx - half, cy - gap), (cx + half, cy - gap)], fill=_pale(0.62) + (190,), width=lw)
    d.text((cx - tw // 2, cy), text, font=f, fill=_pale(0.02))
    d.line([(cx - half, cy + line_h(f) + gap), (cx + half, cy + line_h(f) + gap)],
           fill=_pale(0.62) + (190,), width=lw)

    # ⚠️ 인물 얼굴 위에 그대로 얹으면 글자와 얼굴이 서로를 잡아먹는다.
    #    (세로 쇼츠에서 '아버지 생전' 이 인물 목에 걸쳐 둘 다 안 읽혔다.)
    #    판을 깔지는 않는다 — 위아래로 스르르 사라지는 그늘만 둔다.
    #    영화가 시점 자막을 넣을 때 쓰는 방식이고, 자막 그늘과 같은 장치다.
    #    ⭐ 그늘은 _lift **앞에** 깐다. 뒤에 깔면 _lift 가 띠까지 글자로 착각해
    #      화면 위쪽 절반을 통째로 어둡게 만든다.
    bh = line_h(f) + gap * 5
    band = Image.new("L", (1, bh))
    bp = band.load()
    for i in range(bh):
        t = abs(i / max(1, bh - 1) - 0.5) * 2                # 가운데 0, 위아래 끝 1
        bp[0, i] = int(160 * (1 - t) ** 1.5)
    shade = Image.new("RGBA", (W, bh), (10, 11, 15, 255))
    shade.putalpha(band.resize((W, bh)))

    out = img.convert("RGBA")
    out.alpha_composite(shade, (0, max(0, cy - round(gap * 2.4))))
    return Image.alpha_composite(out, _lift(layer, radius=round(u * 0.011)))


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


def _lift(layer, radius=10, alpha=170, spread=3):
    """⭐ 판을 깔지 않는 대신 두 겹으로 글자를 띄운다.

    이 방향(활자)의 유일한 위험은 **밝은 배경에서 흰 글자가 묻히는 것**이다.
    실제로 밝은 벽 배경으로 시험해 보니 작은 라벨이 거의 안 보였다.
    상자를 다시 깔면 도로 앱 화면이 되므로, 상자 없이 두 가지로 푼다.

      1) 그늘 — 글자 모양 그대로 번진다. 네모가 보이지 않는다
      2) 위쪽 그라데이션 — 자막이 아래에서 쓰는 것과 같은 방식.
         글자가 놓인 높이까지만 은은하게 덮고 아래로 스르르 사라진다.
         어두운 장면에서는 거의 보이지 않고, 밝은 장면에서만 일한다"""
    W, H = layer.size
    box = layer.getchannel("A").point(lambda v: 255 if v >= 24 else 0).getbbox()
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))

    if box:
        pad = round(H * 0.055)
        bottom = min(H, box[3] + pad)
        fade = max(1, round(H * 0.10))
        grad = Image.new("L", (1, bottom))
        px = grad.load()
        for y in range(bottom):
            left = bottom - y
            px[0, y] = 132 if left > fade else round(132 * (left / fade) ** 1.4)
        shade = Image.new("RGBA", (W, bottom), (10, 11, 14, 255))
        shade.putalpha(grad.resize((W, bottom)))
        out.alpha_composite(shade, (0, 0))

    a = layer.getchannel("A").point(lambda v: min(255, v * spread))
    a = a.filter(ImageFilter.GaussianBlur(radius))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a.point(lambda v: round(v * alpha / 255)))
    out.alpha_composite(sh)
    out.alpha_composite(layer)
    return out


def _pale(t):
    """어두운 화면 위에 올릴 밝은 글자색. 종이색에서 뽑는다(새 색을 만들지 않는다)."""
    return tuple(round(255 - (255 - c) * t) for c in PAPER)


def _spaced(text, gap="  "):
    """'판 결 금 액' 처럼 자간을 벌린다. 작은 라벨이 격식 있게 읽힌다."""
    return gap.join(list(str(text).replace(" ", "")))


def g_nametag(text, W=1920, H=1080):
    """인물 이름표 — 강조색 짧은 선 하나와 이름만. 판도 상자도 없다.

    ⭐ 이름과 나머지를 나눠 두 줄로 앉힌다.
       '김성일 · 50세 · 장남' 을 한 줄로 같은 크기로 늘어놓으면 명단처럼 읽힌다.
       드라마는 **이름이 각인돼야** 한다 — 이름을 크게, 나이·관계는 아래에 작게.

    ⚠️ 자막 그늘 위로 올라타지 않도록 **아래끝을 고정하고 위로 쌓는다.**
       크기를 키우면 아래로 자라는 구조였는데, 그러면 자막과 겹친다."""
    u = unit(W, H)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)

    head, _, tail = str(text).partition("·")
    head, tail = head.strip(), tail.strip()
    maxw = int(W * (0.80 if H > W else 0.52))
    fn = _fit_font(*_px("name", u), [head], maxw, role="label")
    ft = _fit_font(*_px("name_sub", u), [tail], maxw, role="body") if tail else None

    gap = round(u * 0.012)
    block = line_h(fn) + (gap + line_h(ft) if ft else 0)
    x = round(W * 0.055)
    y = round(H * (0.50 if H > W else 0.655)) - block       # 아래끝 기준으로 위로 쌓는다

    d.line([(x, y - round(u * 0.028)), (x + round(u * 0.075), y - round(u * 0.028))],
           fill=ACCENT, width=max(3, round(u * 0.005)))
    _t(d, (x, y), head, fn, fill=_pale(0.02))
    if ft:
        _t(d, (x, y + line_h(fn) + gap), tail, ft, fill=_pale(0.42))
    return _lift(out, radius=round(u * 0.009))


def g_amount(value, note="", W=1920, H=1080):
    """금액 — 화면 위쪽에 숫자만 크게. 판을 깔지 않는다.

    ⭐ 라벨을 '판결금액' 으로 못 박지 않는다.
       대본이 '부당이득 반환 금액' 이라고 일러 주는데도 화면에는 늘 '판결금액' 을
       크게 쓰고, 정작 무슨 돈인지는 2.4% 짜리 각주로 아래에 붙였다.
       **뜻이 겹치는 말을 두 번 쓴 셈**이고, 중요한 쪽이 작았다.
       이제 무슨 돈인지를 위에 제대로 된 크기로 쓰고, 숫자, 강조선 — 세 켜로 끝낸다."""
    u = unit(W, H)
    inner = int(W * (1 - 2 * SAFE))
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)

    lab = str(note or "판결금액").strip()
    if len(lab.replace(" ", "")) <= 6:
        lab = _spaced(lab)              # 짧은 말만 자간을 벌린다. 길면 두 줄로 넘친다
    cap = _fit_font(*_px("amt_lab", u), [lab], inner, role="label")
    big = _fit_font(*_px("amt_num", u), [value], inner, role="num")

    y = round(H * 0.175)
    _t(d, ((W - text_w(lab, cap)) // 2, y), lab, cap, fill=_pale(0.40))
    y += line_h(cap) + round(u * 0.024)
    vw = text_w(value, big)
    _t(d, ((W - vw) // 2, y), value, big, fill=_pale(0.01))
    y += line_h(big) + round(u * 0.020)
    # 강조선은 숫자 폭에 맞춰 늘린다. 폭에 상관없이 고정 길이로 그으면
    # 큰 숫자 밑에서는 짤막한 점처럼 보여 실수한 것 같다.
    half = max(round(u * 0.055), round(vw * 0.14))
    d.line([(W // 2 - half, y), (W // 2 + half, y)],
           fill=ACCENT, width=max(3, round(u * 0.005)))
    return _lift(out, radius=round(u * 0.012))


def g_timeline(items, W=1920, H=1080):
    """연표. 판결극장의 반전은 전부 시간 순서다.
    '재혼 열한 달 전'이 말로만 지나가면 충격이 전달되지 않는다.

    판 없이 가는 선 한 줄과 점만. 마지막(결정적) 점만 강조색."""
    items = items[:5]
    n = max(1, len(items))
    u = unit(W, H)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)

    x0, x1 = round(W * 0.10), round(W * 0.90)
    step = (x1 - x0) // max(1, n - 1) if n > 1 else 0
    lab = _fit_font(*_px("tl_lab", u),
                    [str(it.get("label", ""))[:16] for it in items],
                    int(step * 0.94) if n > 1 else int(W * 0.6), role="label")
    whn = _fit_font(*_px("tl_when", u),
                    [str(it.get("when", ""))[:14] for it in items],
                    int(step * 0.94) if n > 1 else int(W * 0.6), role="body")

    yl = round(H * 0.235)
    d.line([(x0, yl), (x1, yl)], fill=_pale(0.72) + (120,), width=2)
    lo, hi = round(W * SAFE), W - round(W * SAFE)
    for i, it in enumerate(items):
        x = x0 + step * i if n > 1 else (x0 + x1) // 2
        last = (i == n - 1)
        r = round(u * 0.006)
        d.ellipse([x - r, yl - r, x + r, yl + r], fill=ACCENT if last else _pale(0.55))
        if last:
            rr = r * 2
            d.ellipse([x - rr, yl - rr, x + rr, yl + rr],
                      outline=ACCENT, width=max(2, round(u * 0.0025)))
        t1 = str(it.get("label", ""))[:16]
        t2 = str(it.get("when", ""))[:14]
        _t(d, (min(max(x - text_w(t1, lab) // 2, lo), hi - text_w(t1, lab)),
               yl - round(u * 0.030) - line_h(lab)), t1, lab, fill=_pale(0.03))
        _t(d, (min(max(x - text_w(t2, whn) // 2, lo), hi - text_w(t2, whn)),
               yl + round(u * 0.026)), t2, whn, fill=ACCENT if last else _pale(0.45))
    return _lift(out, radius=round(u * 0.009))


def g_family(nodes, W=1920, H=1080):
    """가족 관계도. 상속 사건은 관계 파악이 전제다. 도표 1장이 5분 설명을 대체한다.

    상자를 두지 않는다. 이름을 늘어놓고 가는 선으로만 잇는다."""
    nodes = nodes[:5]
    n = max(1, len(nodes))
    u = unit(W, H)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(out)

    x0, x1 = round(W * 0.10), round(W * 0.90)
    slot = (x1 - x0) / max(1, n)
    nm = _fit_font(*_px("fam_name", u),
                   [str(x.get("name", ""))[:8] for x in nodes],
                   int(slot * 0.84), role="label")
    rel = _fit_font(*_px("fam_rel", u),
                    [str(x.get("rel", ""))[:12] for x in nodes],
                    int(slot * 0.90), role="body")

    y_nm = round(H * 0.200)
    y_rel = y_nm + line_h(nm) + round(u * 0.014)
    y_mid = y_nm + line_h(nm) // 2
    for i, nd in enumerate(nodes):
        cx = round(x0 + slot * (i + 0.5))
        t1 = str(nd.get("name", ""))[:8]
        t2 = str(nd.get("rel", ""))[:12]
        w1 = text_w(t1, nm)
        if i < n - 1:
            nx = round(x0 + slot * (i + 1.5))
            w2 = text_w(str(nodes[i + 1].get("name", ""))[:8], nm)
            a, b = cx + w1 // 2 + round(u * 0.018), nx - w2 // 2 - round(u * 0.018)
            if b > a:
                d.line([(a, y_mid), (b, y_mid)], fill=_pale(0.74) + (110,), width=2)
        _t(d, (cx - w1 // 2, y_nm), t1, nm, fill=_pale(0.03))
        _t(d, (cx - text_w(t2, rel) // 2, y_rel), t2, rel, fill=_pale(0.45))
    return _lift(out, radius=round(u * 0.009))


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
        if t:
            # 도입 문장도 자막과 같다 — 뒤에 깔리는 그라데이션은 일부러 화면 폭을 다 쓴다.
            # 그림으로 재면 늘 위반으로 잡히므로 **글자 폭**을 잰다.
            u = unit(1080, 1920)
            inner = int(1080 * (1 - 2 * max(0.075, SAFE)))
            f = _fit_font(u * 0.050, u * 0.032,
                          _wrap_px(t, font(int(u * 0.050), "label"), inner),
                          inner, role="label")
            if any(text_w(ln, f) > 1080 * (1 - 2 * SAFE) for ln in _wrap_px(t, f, inner)):
                bad.append(f"세로 쇼츠{s.get('no')} intro_line 글자가 폭 초과")
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
