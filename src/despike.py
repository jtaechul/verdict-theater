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


# ── 어깨 좌우로 삐죽 튀어나온 것 ────────────────────────────
BOTTOM_ZONE = 0.30      # 아래 30% 안에서 '가장 넓은 줄' 을 찾는다
MAX_TRIM = 0.15         # 그래도 키의 15% 넘게는 자르지 않는다 (몸이 뭉텅 날아가면 안 된다)
MIN_BULGE = 0.03        # 폭 대비 3% 넘게 들어갔을 때만 손댄다


def _row_span(mask, y, W):
    """그 줄의 (왼끝, 오른끝, 폭). 비어 있으면 (0, 0, 0).

    한 줄씩 잘라 getbbox 를 쓴다 — 파이썬으로 픽셀을 하나씩 도는 것보다 훨씬 빠르다."""
    bb = mask.crop((0, y, W, y + 1)).getbbox()
    return (bb[0], bb[2] - 1, bb[2] - bb[0]) if bb else (0, 0, 0)


def flatten_bottom(sp):
    """어깨가 **불룩 나왔다가 다시 좁아지며** 생기는 좌우 삐죽이를 없앤다.

    무엇이 문제였나
        상반신(bust·face) 그림은 가슴께에서 끊긴 컷아웃이라, 아래로 갈수록
        어깨가 가장 넓은 채로 화면 밖으로 나가야 한다. 그런데 AI 가 만든 그림은
        아래를 **둥글게 마무리**해 놓았다 — 어깨에서 제일 넓어졌다가 바닥으로
        갈수록 다시 좁아진다. 거기에 흰 테두리가 둘러지면서 좌우 맨 끝이
        **뾰족한 삼각형**으로 튀어나와 보인다. 실측: 38장 중 29장이 그랬다.

    어떻게 없애나
        아래쪽에서 **가장 넓은 줄을 찾아 거기서 수평으로 자른다.**
        그러면 그 줄이 곧 바닥이 되어 어깨가 제일 넓은 채로 끝난다 —
        나왔다 들어가는 자리가 아예 없어지므로 삐죽이도 없다.
        **지우기만 하고 없는 픽셀을 지어내지 않는다.**

    ⚠️ 전신(full_*)에는 쓰지 않는다. 전신은 팔이 가장 넓고 발이 좁은 것이
       당연해서, 같은 규칙을 대면 **다리가 잘린다.** (부르는 쪽에서 거른다)"""
    a = sp.getchannel("A")
    W, H = sp.size
    mask = a.point(lambda v: 255 if v > 40 else 0)
    bb = mask.getbbox()
    if not bb:
        return sp, 0
    top, bot = bb[1], bb[3] - 1
    ink = bot - top
    if ink < 40:
        return sp, 0

    lo = max(top, bot - int(ink * BOTTOM_ZONE))
    span = {y: _row_span(mask, y, W) for y in range(lo, bot + 1)}
    zone = [y for y, s in span.items() if s[2]]
    if not zone:
        return sp, 0
    wy = max(zone, key=lambda y: span[y][2])
    if (span[wy][2] - span[bot][2]) / W <= MIN_BULGE:
        return sp, 0                      # 이미 아래로 갈수록 넓다 — 손댈 것 없다

    # ⚠️ 너무 많이 잘려야 한다면 **아예 손대지 않는다.** 두 가지 이유다.
    #    ① 그런 그림은 얼굴만 딴 컷이라, 제일 넓은 곳이 어깨가 아니라 **머리카락**이다.
    #       거기서 자르면 턱과 목이 날아간다 (실측: F50A/face_anger).
    #    ② 조금씩 잘라 두면 이 스크립트를 다시 돌릴 때마다 또 잘린다.
    #       에셋 만들기에서 매번 도는 스크립트라 **몇 번을 돌려도 결과가 같아야** 한다.
    if bot - wy > ink * MAX_TRIM:
        return sp, 0

    out = sp.crop((0, 0, W, wy + 1))
    nb = out.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
    return (out.crop(nb) if nb else out), bot - wy


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="지우지 않고 확인만")
    ap.add_argument("--only", default="", help="이 인물만 (쉼표로 구분)")
    args = ap.parse_args()

    files = sorted(CHAR.glob("*/*.png"))
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        files = [f for f in files if f.parent.name in want]

    total = flat = 0
    for f in files:
        sp = Image.open(f).convert("RGBA")
        out, n = despike(sp)
        if n:
            total += 1
            print(f"  {f.parent.name}/{f.stem:14} 조각 {n}개 제거  {sp.size} → {out.size}")

        # ⭐ 전신(full_*)은 건드리지 않는다 — 팔이 넓고 발이 좁은 것이 정상이라
        #    같은 규칙을 대면 다리가 잘린다.
        if not f.name.startswith("full"):
            out2, cut = flatten_bottom(out)
            if cut:
                flat += 1
                print(f"  {f.parent.name}/{f.stem:14} 어깨 삐죽이 — 아래 {cut}줄 잘라냄"
                      f"  {out.size} → {out2.size}")
                out = out2

        if out.size != sp.size and not args.dry:
            out.save(f)

    print(f"\n조각 제거 {total}장 · 어깨 삐죽이 제거 {flat}장 (전체 {len(files)}장)"
          + ("   [--dry — 저장하지 않았다]" if args.dry else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
