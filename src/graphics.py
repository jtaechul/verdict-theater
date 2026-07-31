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

SUB_MAX_CHARS = 18          # 한 줄 최대 글자 수
SUB_MAX_LINES = 3

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


def text_size(d, s, f):
    box = d.textbbox((0, 0), s, font=f)
    return box[2] - box[0], box[3] - box[1]


# ── 자막 ────────────────────────────────────────────────
def wrap_korean(s, max_chars=SUB_MAX_CHARS):
    """어절(띄어쓰기) 단위로 끊는다. 한 어절이 max 를 넘으면 그 어절만 통째로 한 줄에 둔다.

    한국어를 글자 수로만 잘라 '정숙 씨는 그 서류의 날' / '짜를 몰랐습니다' 처럼 되면
    어르신 시청자가 읽다가 놓친다."""
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
    return lines[:SUB_MAX_LINES]


def draw_subtitle(img, text, vertical=False):
    """화면 아래쪽에 자막을 얹는다. 반투명 띠 + 흰 글자 + 검은 테두리."""
    if not text:
        return img
    W, H = img.size
    max_chars = 12 if vertical else SUB_MAX_CHARS
    lines = wrap_korean(text, max_chars)

    size = int(H * (0.042 if not vertical else 0.038))
    f = font(size)
    gap = int(size * 0.34)
    block_h = len(lines) * size + (len(lines) - 1) * gap
    pad = int(size * 0.55)

    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)

    band_top = H - int(H * (0.16 if not vertical else 0.30)) - pad
    band_h = block_h + pad * 2
    d.rectangle([0, band_top, W, band_top + band_h], fill=(0, 0, 0, 120))

    y = band_top + pad
    for ln in lines:
        w, _ = text_size(d, ln, f)
        x = (W - w) // 2
        for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2), (-2, 2), (2, -2)):
            d.text((x + dx, y + dy), ln, font=f, fill=(0, 0, 0, 230))
        d.text((x, y), ln, font=f, fill=(255, 255, 255, 255))
        y += size + gap

    return Image.alpha_composite(img.convert("RGBA"), layer)


def draw_top_line(img, text):
    """쇼츠 첫 화면 위쪽에 얹는 한 줄. 상황을 1초 안에 알려준다.

    넘기다 걸린 사람은 **누가 누군지 전혀 모른다.** 본편을 봐야 알 수 있는 대명사 대신
    이 한 줄로 무슨 상황인지 못 박는다. 아래 자막과 겹치지 않게 화면 위쪽에 둔다."""
    if not text:
        return img
    W, H = img.size
    size = int(H * 0.036)
    f = font(size)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lines = wrap_korean(text, 14)
    gap = int(size * 0.3)
    block = len(lines) * size + (len(lines) - 1) * gap
    pad = int(size * 0.6)
    top = int(H * 0.09)
    d.rounded_rectangle([int(W * 0.06), top - pad, int(W * 0.94), top + block + pad],
                        int(size * 0.5), fill=(198, 160, 74, 235))
    y = top
    for ln in lines:
        w, _ = text_size(d, ln, f)
        d.text(((W - w) // 2, y), ln, font=f, fill=(26, 22, 8, 255))
        y += size + gap
    return Image.alpha_composite(img.convert("RGBA"), layer)


# ── 정보 그래픽 4종 ──────────────────────────────────────
def _card(w, h, radius=24):
    img = Image.new("RGBA", (w + 24, h + 24), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([12, 16, w + 12, h + 16], radius, fill=SHADOW)   # 그림자
    d.rounded_rectangle([12, 12, w + 12, h + 12], radius, fill=PAPER + (245,))
    return img, d


def g_nametag(text, W=1920, H=1080):
    """인물 이름표. 고정 배우 7명을 회차마다 다른 역으로 쓰므로 없으면 누가 누군지 모른다."""
    size = int(H * 0.030)
    f = font(size)
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw, th = text_size(tmp, text, f)
    pad_x, pad_y = int(size * 0.9), int(size * 0.55)
    cw, ch = tw + pad_x * 2, th + pad_y * 2

    card, d = _card(cw, ch, radius=int(ch * 0.28))
    d.rectangle([12, 12, 12 + int(size * 0.22), ch + 12], fill=CRIMSON)   # 왼쪽 강조 띠
    d.text((12 + pad_x, 12 + pad_y - int(size * 0.12)), text, font=f, fill=INK)

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(card, (int(W * 0.055), int(H * 0.70)), card)
    return out


def g_amount(value, note="", W=1920, H=1080):
    """금액 강조. 숫자는 귀로 들어오지 않는다. 큰 글씨로 화면에 박는다."""
    big = font(int(H * 0.115))
    small = font(int(H * 0.034))
    tmp = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    vw, vh = text_size(tmp, value, big)
    nw, nh = text_size(tmp, note, small) if note else (0, 0)

    cw = max(vw, nw) + int(H * 0.13)
    ch = vh + (nh + int(H * 0.035) if note else 0) + int(H * 0.10)
    card, d = _card(cw, ch, radius=int(H * 0.03))

    y = 12 + int(H * 0.045)
    d.text((12 + (cw - vw) // 2, y), value, font=big, fill=CRIMSON)
    if note:
        y += vh + int(H * 0.035)
        d.text((12 + (cw - nw) // 2, y), note, font=small, fill=SLATE)

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(card, ((W - card.width) // 2, int(H * 0.18)), card)
    return out


def g_timeline(items, W=1920, H=1080):
    """연표. 판결극장의 반전은 전부 시간 순서다.
    '재혼 열한 달 전'이 말로만 지나가면 충격이 전달되지 않는다."""
    items = items[:5]
    n = max(1, len(items))
    lab = font(int(H * 0.030))
    when = font(int(H * 0.026))

    cw, ch = int(W * 0.86), int(H * 0.30)
    card, d = _card(cw, ch, radius=int(H * 0.028))

    y_line = 12 + int(ch * 0.52)
    x0, x1 = 12 + int(cw * 0.08), 12 + int(cw * 0.92)
    d.line([(x0, y_line), (x1, y_line)], fill=LINE, width=6)

    step = (x1 - x0) / max(1, n - 1) if n > 1 else 0
    for i, it in enumerate(items):
        x = int(x0 + step * i) if n > 1 else (x0 + x1) // 2
        last = (i == n - 1)
        color = CRIMSON if last else GOLD
        r = int(H * 0.016)
        d.ellipse([x - r, y_line - r, x + r, y_line + r], fill=color)

        t1 = str(it.get("label", ""))[:16]
        t2 = str(it.get("when", ""))[:14]
        w1, _ = text_size(d, t1, lab)
        w2, _ = text_size(d, t2, when)
        d.text((x - w1 // 2, y_line - int(ch * 0.30)), t1, font=lab, fill=INK)
        d.text((x - w2 // 2, y_line + int(ch * 0.13)), t2, font=when, fill=color)

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(card, ((W - card.width) // 2, int(H * 0.13)), card)
    return out


def g_family(nodes, W=1920, H=1080):
    """가족 관계도. 상속 사건은 관계 파악이 전제다. 도표 1장이 5분 설명을 대체한다."""
    nodes = nodes[:5]
    n = max(1, len(nodes))
    nm = font(int(H * 0.032))
    rel = font(int(H * 0.025))

    cw, ch = int(W * 0.80), int(H * 0.28)
    card, d = _card(cw, ch, radius=int(H * 0.028))

    y = 12 + int(ch * 0.50)
    slot = cw / n
    for i, nd in enumerate(nodes):
        cx = int(12 + slot * (i + 0.5))
        bw, bh = int(slot * 0.78), int(ch * 0.46)
        d.rounded_rectangle([cx - bw // 2, y - bh // 2, cx + bw // 2, y + bh // 2],
                            int(bh * 0.22), outline=LINE, width=4, fill=(255, 255, 255, 255))
        t1 = str(nd.get("name", ""))[:8]
        t2 = str(nd.get("rel", ""))[:12]
        w1, _ = text_size(d, t1, nm)
        w2, _ = text_size(d, t2, rel)
        d.text((cx - w1 // 2, y - int(bh * 0.30)), t1, font=nm, fill=INK)
        d.text((cx - w2 // 2, y + int(bh * 0.04)), t2, font=rel, fill=SLATE)
        if i < n - 1:
            d.line([(cx + bw // 2, y), (int(12 + slot * (i + 1.5)) - bw // 2, y)],
                   fill=LINE, width=4)

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    out.paste(card, ((W - card.width) // 2, int(H * 0.14)), card)
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
        "amount": {"type": "amount", "value": "1억 5,690만 원", "note": "십 년의 새벽"},
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

    print("\n자막 줄바꿈 시험 (어절 단위, 한 줄 18자)")
    for s in ["그 땅은, 처음부터 제 겁니다.",
              "정숙 씨는 그 서류의 날짜를 몰랐습니다. 아직은.",
              "먼 나라의 땅 하나. 칠억이 넘었지만 정숙 씨는 본 적이 없었습니다."]:
        print(f"  원문: {s}")
        for ln in wrap_korean(s):
            print(f"    | {ln}  ({len(ln)}자)")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", default="", help="시험 이미지를 이 폴더에 만든다")
    a = ap.parse_args()
    if a.demo:
        sys.exit(demo(a.demo))
    print(f"폰트: {font_path()}")
