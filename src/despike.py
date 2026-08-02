#!/usr/bin/env python3
"""컷아웃 어깨에 솟은 조각을 없앤다.

    python3 src/despike.py                     assets/char 전체
    python3 src/despike.py --dry               지우지 않고 몇 개인지만 본다
    python3 src/despike.py --only M50A,M50B

무엇이 문제였나
    인물 시트에서 여러 명이 어깨를 맞대고 붙어 나오면, 세로로 잘라 떼어낼 때
    **옆 사람의 어깨 조각이 얇게 딸려온다.** 거기에 흰 테두리가 둘러지면서
    어깨 좌우에 위로 뾰족하게 솟은 것이 생겼다.

어떻게 없애나
    어깨선 **위쪽**만 따로 본다. 거기에는 원래 머리 하나만 있어야 한다.
    머리 말고 다른 덩어리가 있으면 그것이 딸려온 조각이므로 지운다.
    어깨 아래는 손대지 않는다 — 팔·다리가 잘리면 안 되기 때문이다.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
CHAR = ROOT / "assets" / "char"


def _rows(mask):
    """줄마다 (왼끝, 오른끝, 폭). 비어 있으면 (0,0,0)."""
    W, H = mask.size
    px = mask.load()
    out = []
    for y in range(H):
        xs = [x for x in range(W) if px[x, y]]
        out.append((min(xs), max(xs), max(xs) - min(xs) + 1) if xs else (0, 0, 0))
    return out


def shoulder_row(mask):
    """어깨가 시작되는 줄. 못 찾으면 None."""
    rows = _rows(mask)
    W, H = mask.size
    solid = [y for y, r in enumerate(rows) if r[2] > W * 0.04]
    if not solid:
        return None
    top, bot = solid[0], solid[-1]
    n = max(3, int((bot - top) * 0.16))
    probe = [rows[y][2] for y in range(top, min(H, top + n)) if rows[y][2]]
    if not probe:
        return None
    head_w = sorted(probe)[len(probe) // 2]
    for y in range(top + n, bot + 1):
        if rows[y][2] > head_w * 1.55:
            return y
    return None


def _components(mask, min_area):
    W, H = mask.size
    px = mask.load()
    seen = bytearray(W * H)
    out = []
    for sy in range(H):
        for sx in range(W):
            if seen[sy * W + sx] or px[sx, sy] < 128:
                continue
            stack = [(sx, sy)]
            pts = [sy * W + sx]
            seen[sy * W + sx] = 1
            while stack:
                x, y = stack.pop()
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < W and 0 <= ny < H and not seen[ny * W + nx] \
                            and px[nx, ny] >= 128:
                        seen[ny * W + nx] = 1
                        pts.append(ny * W + nx)
                        stack.append((nx, ny))
            if len(pts) >= min_area:
                out.append(pts)
    return out


def _runs(px, y, W):
    """한 줄에서 불투명한 구간들을 (시작, 끝) 으로 돌려준다."""
    out, st = [], None
    for x in range(W):
        on = px[x, y] >= 128
        if on and st is None:
            st = x
        elif not on and st is not None:
            out.append((st, x - 1)); st = None
    if st is not None:
        out.append((st, W - 1))
    return out


def despike(sp, scale=4, thin=25, back=29):
    """인물 옆에 남은 **칸 테두리 조각**(세로 기둥 + 아래 가로줄)을 지운다.

    ⚠️ 세 번 헛짚었다. 기록해 둔다.
       ① '어깨선 위쪽의 다른 덩어리' → 0장. 조각은 바닥부터 어깨까지 서 있다.
       ② '가장 큰 덩어리만 남기기' → 0장. 흰 테두리가 조각과 몸통을 이어 붙여 놓았다.
       ③ '가슴 높이에서 좌우 좁은 구간 잘라내기' → 0장. 아래쪽에서 조각과 몸통의
          x 범위가 겹쳐(자켓 아랫단과 같은 자리) 잘라내면 몸까지 잘린다.
    실제로 남은 것은 **가늘다**. 굵은 것만 남기고(깎았다 부풀리기) 그중 가장 큰 덩어리를
    고른 뒤, 그 둘레만큼만 되살리면 가는 조각은 돌아오지 않는다.
    목처럼 가는 부분은 조각보다 굵어서 살아남는다."""
    a = sp.getchannel("A")
    solid = a.point(lambda v: 255 if v > 128 else 0)
    sw, sh_ = max(1, sp.width // scale), max(1, sp.height // scale)
    small = solid.resize((sw, sh_), Image.BILINEAR).point(lambda v: 255 if v > 110 else 0)

    thick = small.filter(ImageFilter.MinFilter(thin)).filter(ImageFilter.MaxFilter(thin))
    comps = _components(thick, min_area=max(6, (sw * sh_) // 900))
    if not comps:
        return sp, 0
    comps.sort(key=len, reverse=True)

    buf = bytearray(sw * sh_)
    for i in comps[0]:
        buf[i] = 255
    core = Image.frombytes("L", (sw, sh_), bytes(buf)).filter(ImageFilter.MaxFilter(back))
    keep = core.resize(sp.size, Image.BILINEAR).point(lambda v: 255 if v > 90 else 0)
    keep = keep.filter(ImageFilter.GaussianBlur(2))

    before = sum(solid.histogram()[128:])
    out = sp.copy()
    out.putalpha(ImageChops.multiply(a, keep))
    after = sum(out.getchannel("A").point(lambda v: 255 if v > 128 else 0).histogram()[128:])
    if before and (before - after) / before < 0.004:      # 실질적으로 안 지워졌다
        return sp, 0
    bb = out.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
    return (out.crop(bb) if bb else out), max(1, len(comps) - 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="지우지 않고 확인만")
    ap.add_argument("--only", default="", help="이 인물만 (쉼표로 구분)")
    args = ap.parse_args()

    files = sorted(CHAR.glob("*/*.png"))
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        files = [f for f in files if f.parent.name in want]

    total = 0
    for f in files:
        sp = Image.open(f).convert("RGBA")
        out, n = despike(sp)
        if not n:
            continue
        total += 1
        print(f"  {f.parent.name}/{f.stem:14} 조각 {n}개 제거  {sp.size} → {out.size}")
        if not args.dry:
            out.save(f)
    print(f"\n{total}장에서 어깨 조각을 지웠다 (전체 {len(files)}장)"
          + ("   [--dry — 저장하지 않았다]" if args.dry else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
