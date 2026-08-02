#!/usr/bin/env python3
"""컷아웃 아래에 남은 **검은 띠**를 잘라낸다.

    python3 src/blackbar.py --dry      잘라낼 곳만 확인
    python3 src/blackbar.py            실제로 잘라내고 저장
    python3 src/blackbar.py --only M50A

무엇이 문제였나
    인물 시트에서 칸 아래쪽 경계선이 인물과 함께 딸려 나왔다. 그 위에 흰 테두리가
    둘러지면서, 인물 밑에 **검은 가로 띠 + 흰 테두리**가 붙은 채로 남았다.

어떻게 잘라내나
    ① 흰 테두리를 벗긴다 — 바깥(투명한 곳)에서 흰색을 타고 들어가며 지운다.
       ⚠️ 알파를 깎는 방법은 안 된다. 테두리를 만들 때 머리카락 사이 같은 오목한 곳이
          흰색으로 메워지는데, 같은 만큼 깎아도 그 메움은 열리지 않는다.
    ② 맨 아래에서 위로 훑으며 '거의 완전한 검정이 가로로 쭉 이어지는 줄' 을 센다.
       옷의 검정과 구분되는 이유: 이 띠는 **한 줄이 통째로 새까맣고 폭이 일정하다.**
    ③ 그만큼 잘라내고 흰 테두리를 다시 두른다.

    ⚠️ 전신(full_*)에는 손대지 않는다. 검은 바지·구두가 있어 잘못 자를 위험이 있다.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import assets_gen as A  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHAR = ROOT / "assets" / "char"

DARK = 62            # 이 값보다 어두우면 '검정' 으로 본다
FILL = 0.93          # 한 줄에서 검정이 차지해야 하는 최소 비율
MIN_BAND = 0.003     # 그림 높이의 이 비율보다 두꺼워야 띠로 인정한다
MAX_BAND = 0.15      # 이보다 두꺼우면 띠가 아니라 검은 옷이다 — 건드리지 않는다


def strip_outline(sp, white_at=238):
    """흰 스티커 테두리를 벗긴다 — 바깥에서 흰색을 타고 들어가며 지운다."""
    pad = 2
    W, H = sp.width + pad * 2, sp.height + pad * 2
    big = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    big.paste(sp, (pad, pad))
    r, g, b = big.convert("RGB").split()
    a = big.getchannel("A")
    near_white = ImageChops.multiply(
        ImageChops.multiply(r.point(lambda v: 255 if v >= white_at else 0),
                            g.point(lambda v: 255 if v >= white_at else 0)),
        b.point(lambda v: 255 if v >= white_at else 0))
    outside = ImageChops.lighter(a.point(lambda v: 255 if v < 128 else 0), near_white)
    ImageDraw.floodfill(outside, (0, 0), 90, thresh=0)
    ring = outside.point(lambda v: 255 if v == 90 else 0)
    keep = ImageChops.subtract(a, ring).filter(ImageFilter.GaussianBlur(1.0))
    out = big.copy()
    out.putalpha(keep)
    bb = keep.point(lambda v: 255 if v > 40 else 0).getbbox()
    return out.crop(bb) if bb else out


def black_band(sp):
    """아래에서 위로 이어지는 검은 띠의 두께(픽셀). 없으면 0.

    ⚠️ '어두우면 자른다' 로는 안 된다. 남색 양복·검은 스웨터도 어두워서
       아래에서부터 옷을 통째로 잘라먹는다.
    띠는 **인쇄된 선**이라 옷과 다르다 — 한 줄이 통째로 새까맣고,
    밝기 편차가 거의 없고, 좌우 끝이 자로 그은 듯 일정하다. 그 세 가지를 함께 본다."""
    from PIL import ImageStat
    rgb, a = sp.convert("RGB"), sp.getchannel("A")
    r, g, b = rgb.split()
    dark = ImageChops.multiply(
        ImageChops.multiply(r.point(lambda v: 255 if v < DARK else 0),
                            g.point(lambda v: 255 if v < DARK else 0)),
        ImageChops.multiply(b.point(lambda v: 255 if v < DARK else 0),
                            a.point(lambda v: 255 if v > 150 else 0)))
    solid = a.point(lambda v: 255 if v > 150 else 0)
    W, H = sp.size
    dp, sp_ = dark.load(), solid.load()
    step = max(1, W // 220)

    band, spans = 0, []
    for y in range(H - 1, -1, -1):
        on = [x for x in range(0, W, step) if sp_[x, y]]
        if not on:
            band += 1
            continue
        blk = sum(1 for x in on if dp[x, y])
        if len(on) < (W / step) * 0.35 or blk / len(on) < FILL:
            break
        spans.append((on[0] * step, on[-1] * step))
        band += 1
    # ⚠️ '밝기 편차가 작고 좌우 끝이 일정해야 한다' 는 조건은 실제 파일에서 다 걸렀다
    #    (실측: 편차 41.6, 좌끝 흔들림 99px). 인쇄된 선처럼 깔끔하지 않기 때문이다.
    #    대신 **두께 상한**으로 옷과 가른다. 띠는 얇고, 검은 옷은 두껍다.
    if band < H * MIN_BAND or band > H * MAX_BAND or not spans:
        return 0
    return band


def fix(path, dry=False):
    sp = Image.open(path).convert("RGBA")
    plain = strip_outline(sp)
    band = black_band(plain)
    if not band:
        return 0
    cut = plain.crop((0, 0, plain.width, max(1, plain.height - band)))
    cut = A.trim_alpha(cut)
    if cut is None:
        return 0
    print(f"  {path.parent.name}/{path.stem:14} 검은 띠 {band}px 잘라냄"
          f"  {sp.size} → {cut.width}x{cut.height}(테두리 전)")
    if not dry:
        A.white_outline(cut).save(path)
    return band


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="자르지 않고 확인만")
    ap.add_argument("--only", default="", help="이 인물만 (쉼표로 구분)")
    args = ap.parse_args()

    files = [f for f in sorted(CHAR.glob("*/*.png"))
             if not f.stem.startswith("full_")]      # 전신은 건드리지 않는다
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        files = [f for f in files if f.parent.name in want]

    n = sum(1 for f in files if fix(f, dry=args.dry))
    print(f"\n{n}장에서 검은 띠를 잘라냈다 (검사 {len(files)}장, 전신 제외)"
          + ("   [--dry — 저장하지 않았다]" if args.dry else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
