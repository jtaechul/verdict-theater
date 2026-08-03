#!/usr/bin/env python3
"""유튜브 채널 배너를 규격에 맞게 만든다.

    python3 tools/banner.py                        저장소 배경으로 만든다
    python3 tools/banner.py --bg 내그림.png         제미나이로 만든 그림으로 만든다
    python3 tools/banner.py --out banner.png       저장 위치

왜 이 도구가 필요한가
    유튜브 배너는 **2048x1152 보다 작으면 업로드를 거부한다.**
    화면에는 '채널 배너를 업데이트하지 못했습니다. 다시 시도해 주세요' 라고만 뜨고
    왜 안 되는지는 알려주지 않는다.

    제미나이가 내주는 그림은 긴 변이 대개 1024~1408px 이라 이 문턱을 못 넘는다.
    프롬프트에 'at least 2560x1440' 이라고 적어도 소용없다 — 모델의 출력 해상도는
    프롬프트로 바뀌지 않는다. 그래서 만든 뒤에 규격으로 맞춰 주는 단계가 필요하다.

    한글 글자도 마찬가지다. AI 가 그린 한글은 깨져 나오므로 글자는 여기서 얹는다.

⭐ 안전 영역
    배너는 기기마다 보이는 넓이가 다르다. TV 는 전체가 보이고, 휴대폰은 가운데만 보인다.
    **모든 기기에서 보이는 것은 가운데 1235x338 뿐이다.** 글자는 반드시 그 안에 넣는다.
    바깥은 잘려도 되는 장식으로만 쓴다.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter  # noqa: E402
import graphics as G                                          # noqa: E402

# 유튜브 규격
W, H = 2560, 1440                   # 권장 업로드 크기
SAFE_W, SAFE_H = 1235, 338          # 모든 기기에서 보이는 가운데 영역
MIN_W, MIN_H = 2048, 1152           # 이보다 작으면 업로드가 거부된다
MAX_BYTES = 6 * 1024 * 1024         # 6MB

TITLE = "판결극장"
TAGLINE = "실제 판결을 재구성한 드라마"

# 기본 배경 — 어둡고 차분하며 가운데가 비어 있는 것이 좋다
DEFAULT_BG = ["court_exterior.jpg", "court_hall.jpg", "funeral_hall.jpg"]


def pick_bg(name=None):
    if name:
        p = Path(name)
        if not p.exists():
            p = ROOT / "assets" / "bg" / name
        if not p.exists():
            raise SystemExit(f"그림을 찾지 못했습니다: {name}")
        return p
    for n in DEFAULT_BG:
        p = ROOT / "assets" / "bg" / n
        if p.exists():
            return p
    got = sorted((ROOT / "assets" / "bg").glob("*.jpg"))
    if not got:
        raise SystemExit("assets/bg 에 배경 그림이 없습니다.")
    return got[0]


def cover(img, w, h):
    """가로세로비를 지키며 (w,h) 를 꽉 채우도록 키우고 가운데를 자른다.

    늘려서 찌그러뜨리지 않는다 — 사람 얼굴이나 기둥이 휘면 바로 티가 난다."""
    s = max(w / img.width, h / img.height)
    nw, nh = max(w, round(img.width * s)), max(h, round(img.height * s))
    img = img.resize((nw, nh), Image.LANCZOS)
    x, y = (nw - w) // 2, (nh - h) // 2
    return img.crop((x, y, x + w, y + h))


def build(bg_path):
    base = Image.open(bg_path).convert("RGB")
    small = base.width < MIN_W or base.height < MIN_H
    img = cover(base, W, H)

    # 배경은 글자의 배경일 뿐이다. 세게 어둡게 눌러 글자가 확실히 뜨게 한다.
    img = ImageEnhance.Brightness(img).enhance(0.34)
    img = ImageEnhance.Color(img).enhance(0.45)
    img = img.filter(ImageFilter.GaussianBlur(3))

    # 가운데(안전 영역)를 가장 어둡게 — 글자가 놓이는 자리다.
    sx, sy = (W - SAFE_W) // 2, (H - SAFE_H) // 2
    scrim = Image.new("L", (W, H), 0)
    ImageDraw.Draw(scrim).ellipse(
        [sx - SAFE_W * 0.55, sy - SAFE_H * 1.5,
         sx + SAFE_W * 1.55, sy + SAFE_H * 2.5], fill=190)
    scrim = scrim.filter(ImageFilter.GaussianBlur(220))
    img = Image.composite(Image.new("RGB", (W, H), (10, 10, 12)), img, scrim)

    d = ImageDraw.Draw(img)

    # ── 글자 (전부 안전 영역 안) ──────────────────────────
    tf = G.font(196, "sub")
    tw = G.text_w(TITLE, tf)
    # 안전 영역보다 넓어지면 줄인다. 잘린 채로 내보내지 않는다.
    size = 196
    while tw > SAFE_W * 0.80 and size > 60:
        size -= 4
        tf = G.font(size, "sub")
        tw = G.text_w(TITLE, tf)
    th = G.line_h(tf)

    gf = G.font(max(30, round(size * 0.26)), "body")
    gw = G.text_w(TAGLINE, gf)
    gh = G.line_h(gf)

    rule_gap = round(size * 0.22)
    block = th + rule_gap + gh
    top = sy + (SAFE_H - block) // 2

    # 제목 — 종이색(거의 흰색)
    d.text(((W - tw) // 2, top), TITLE, font=tf, fill=G.PAPER)

    # 제목과 부제 사이에 진홍 가는 선 한 줄. 강조색은 여기 한 번만 쓴다.
    ry = top + th + rule_gap // 2
    rw = round(tw * 0.30)
    d.rectangle([(W - rw) // 2, ry - 2, (W + rw) // 2, ry + 1], fill=G.ACCENT)

    # 부제 — 조금 눌러서 제목을 방해하지 않게
    d.text(((W - gw) // 2, top + th + rule_gap), TAGLINE, font=gf,
           fill=(198, 194, 186))
    return img, small, size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bg", help="쓸 그림 (없으면 저장소 배경)")
    ap.add_argument("--out", default="banner.png")
    a = ap.parse_args()

    src = pick_bg(a.bg)
    img, small, size = build(src)
    out = Path(a.out)
    img.save(out, "PNG", optimize=True)

    # PNG 가 6MB 를 넘으면 JPG 로 바꾼다 — 유튜브가 용량으로도 거부한다.
    if out.stat().st_size > MAX_BYTES:
        out = out.with_suffix(".jpg")
        img.save(out, "JPEG", quality=92, optimize=True)

    mb = out.stat().st_size / 1024 / 1024
    print(f"바탕 그림 : {src.name}")
    if small:
        print("            (원본이 규격보다 작아 키웠습니다)")
    print(f"만든 파일 : {out}")
    print(f"크기      : {img.width} x {img.height}   용량 {mb:.2f} MB")
    print(f"제목 글자 : {size}px")
    print()
    print("유튜브 배너 기준")
    print(f"  최소 {MIN_W}x{MIN_H} : {'통과' if img.width >= MIN_W and img.height >= MIN_H else '미달'}")
    print(f"  6MB 이하        : {'통과' if out.stat().st_size <= MAX_BYTES else '초과'}")
    print(f"  16:9 비율       : {'통과' if abs(img.width / img.height - 16 / 9) < 0.01 else '어긋남'}")


if __name__ == "__main__":
    main()
