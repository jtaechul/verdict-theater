#!/usr/bin/env python3
"""인물 그림에 구워진 **흰 스티커 테두리**를 벗긴다.

    python3 tools/strip_ring.py            # 전부
    python3 tools/strip_ring.py --dry      # 재보기만

왜 벗기나
    assets_gen 이 인물 둘레에 흰 테두리(인물 높이의 2.8%)와 그림자를 구워 넣었다.
    '잡지에서 오려 붙인 느낌' 을 노린 것인데, 실제 화면에서는 스티커를 붙인 것처럼
    싸구려로 보인다. 손님이 여러 번 지적했다.
    참고로 받은 유튜브 썸네일 네 장에는 그런 테두리가 하나도 없다 — 인물은
    배경에 자연스럽게 얹혀 있고, 떨어져 보이게 하는 일은 **그림자**가 맡는다.

⛔ 알파를 안쪽으로 밀어(erode) 지우면 안 된다
    한 번 그렇게 했다가 3.6% 만 깎으려던 것이 10.4% 깎여 머리 위·턱·귀가
    잘려 나갔다. 얼굴이 망가진다.

✅ 지우는 방법 — **모양이 아니라 색으로, 가장자리 근처만**
    ① 순백(RGB 245 이상)이고
    ② 실루엣 가장자리 띠 안에 있는 픽셀
    둘을 **모두** 만족하는 것만 지운다. 흰 셔츠는 ②에 걸려 안전하다.
    구워진 그림자(반투명 검정)도 함께 걷어낸다 — 렌더러가 새로 깔아 준다.
    사람 모양은 한 픽셀도 안 바뀐다. 없던 것을 없애는 것뿐이다.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
CHARS = ROOT / "assets" / "char"

RING_BAND = 0.075        # 가장자리에서 이 비율까지를 '테두리 띠' 로 본다
WHITE_AT = 245           # 이 값 이상이면 인쇄된 순백으로 본다
SOLID_AT = 200           # 이 값 미만 알파는 구워진 그림자로 본다


def edge_band(alpha, pct):
    """실루엣 가장자리 띠 마스크. 안쪽(본체)은 False."""
    hard = alpha.point(lambda v: 255 if v >= SOLID_AT else 0)
    w, h = hard.size
    small = hard.resize((max(1, w // 4), max(1, h // 4)), Image.NEAREST)
    steps = max(1, round(small.height * pct / 4))       # MinFilter(9) = 한 번에 4px
    for _ in range(steps):
        small = small.filter(ImageFilter.MinFilter(9))
    inner = small.resize((w, h), Image.BILINEAR).point(lambda v: 255 if v > 128 else 0)
    return np.array(inner) == 0


def strip(path, dry=False):
    im = Image.open(path).convert("RGBA")
    arr = np.array(im)
    rgb, al = arr[..., :3].astype(int), arr[..., 3]

    band = edge_band(im.getchannel("A"), RING_BAND)
    ring = band & (al >= SOLID_AT) & (rgb.min(axis=2) >= WHITE_AT)   # 흰 테두리
    haze = al < SOLID_AT                                             # 구워진 그림자
    kill = ring | haze
    n = int(kill.sum())
    if not n:
        return 0, im.size, im.size

    arr[..., 3] = np.where(kill, 0, al)
    out = Image.fromarray(arr, "RGBA")
    box = out.getchannel("A").getbbox()
    out = out.crop(box) if box else out
    if not dry:
        out.save(path)
    return n, im.size, out.size


def core(path):
    """인물 '속살' 픽셀 수 — 불투명하면서 순백이 아닌 것.

    테두리·그림자를 걷어내도 이 값은 그대로여야 한다. 줄었다면 얼굴을 깎은 것이다."""
    arr = np.array(Image.open(path).convert("RGBA"))
    return int(((arr[..., 3] >= SOLID_AT) &
                (arr[..., :3].astype(int).min(axis=2) < WHITE_AT)).sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="저장하지 않고 재보기만")
    ap.add_argument("--only", default="", help="이 인물만 (쉼표로 여러 명)")
    a = ap.parse_args()

    want = {s.strip() for s in a.only.split(",") if s.strip()}
    files = sorted(CHARS.rglob("*.png"))
    if want:
        files = [p for p in files if p.parent.name in want]
    if not files:
        print("대상 그림이 없다")
        return 1

    cores = {p: core(p) for p in files}      # 처리 전 '인물 속살' 픽셀 수
    worst = 0.0
    for p in files:
        n, before, after = strip(p, dry=a.dry)
        # ⚠️ 크기가 줄어드는 것은 **정상**이다 — 인물 바깥의 테두리·그림자가
        #    사라진 만큼 줄어든다. 인물이 깎였는지는 크기가 아니라 **속살**로 본다.
        core_now = core(p)
        shrink = 1 - (core_now / cores[p]) if cores.get(p) else 0
        worst = max(worst, shrink)
        flag = "  ⚠️ 인물이 깎였다" if shrink > 0.01 else ""
        print(f"  {p.parent.name}/{p.name:22s} 지운 픽셀 {n:>8,}  "
              f"{before[0]}x{before[1]} → {after[0]}x{after[1]}{flag}")
    print(f"\n{len(files)}장 {'재보기' if a.dry else '처리'} 완료. "
          f"인물 속살 최대 손실 {worst:.2%} (1% 넘으면 얼굴이 깎인 것)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
