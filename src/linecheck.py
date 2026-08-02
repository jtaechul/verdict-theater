#!/usr/bin/env python3
"""인물 컷아웃에 **칸 선**(인쇄된 검은 줄)이 남아 있는지 검사한다. 고치지는 않는다.

    python3 src/linecheck.py                     전부 검사
    python3 src/linecheck.py --zoom build/line    걸린 곳을 확대해 그림으로 저장

왜 '고치지 않는' 검사기인가
    선을 자동으로 지우려고 **다섯 번** 시도했고 다섯 번 다 틀렸다.
      ① 가장자리에서 순검정 한 겹씩 벗기기   → 검은 곱슬머리를 30겹 먹었다
      ② 바깥 12줄만 보기                    → 선이 안쪽에 있어 거의 다 놓쳤다
      ③ 검정을 타고 흘러들며 얇은 것만       → 니트·법복을 흰 줄로 찢었다
      ④ 실루엣 폭의 절반을 가로질러야 선     → 판사 세로선(높이의 34%)을 놓쳤다
      ⑤ 가장자리 따라가며 지우기            → 검은 바지·구두를 물어뜯었다
    밝기로도 모양으로도 '인쇄된 선'과 '검은 옷'을 안전하게 가를 수 없다.
    그래서 자동 수술을 그만두고 **원인을 없앴다** — 인물 그림을 격자 시트에서
    잘라내지 않고 `char_sheet.py` 가 한 장에 한 포즈씩 만든다(칸이 없으면 칸 선도 없다).
    이 검사기는 그 뒤에 남은 **안전망**이다. 걸리면 사람이 보고 다시 만들면 된다.

무엇을 선으로 보나 — 실측으로 고른 조건
    ① 순검정(가장 밝은 채널 22 미만)이 **곧게** 길게 이어진다
       실측 — 판사 왼쪽 선 404px · 법복/양복/바지는 이 문턱에서 거의 안 걸린다
    ② 그 줄이 실루엣 **가장자리에 붙어** 있다 (안쪽 주름은 선이 아니다)
       실측 — 진짜 선 1.9% · 옷 주름은 12~95%
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
CHAR = ROOT / "assets" / "char"

PURE = 22        # 이 값 미만이 순검정 (실측: 선 0~21 · 바지 22~28 · 법복 37~42 · 양복 30~49)
MIN_LEN = 0.25   # 그림의 이 비율만큼 곧게 이어져야 '선'  (실측: 판사 선 34.6%)
EDGE = 0.05      # 실루엣 가장자리에서 이 비율 안쪽까지만 선으로 본다 (실측: 진짜 선 1.9%)


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
    keep = ImageChops.subtract(a, ring)
    out = big.copy()
    out.putalpha(keep)
    bb = keep.point(lambda v: 255 if v > 40 else 0).getbbox()
    return out.crop(bb) if bb else out


def _runs(flags):
    """1차원 True 열에서 (가장 긴 길이, 그 시작 위치)"""
    best = cur = start = best_at = 0
    for i, v in enumerate(flags):
        if v:
            if cur == 0:
                start = i
            cur += 1
            if cur > best:
                best, best_at = cur, start
        else:
            cur = 0
    return best, best_at


def find_line(path):
    """이 그림에 칸 선이 있으면 (방향, 길이비율, 가장자리비율, 좌표) 없으면 None."""
    sp = strip_outline(Image.open(path).convert("RGBA"))
    W, H = sp.size
    px = sp.convert("RGB").load()
    ap = sp.getchannel("A").load()

    def black(x, y):
        p = px[x, y]
        return ap[x, y] > 128 and max(p[0], p[1], p[2]) < PURE

    op_cols = [x for x in range(W) if any(ap[x, y] > 128 for y in range(0, H, 7))]
    op_rows = [y for y in range(H) if any(ap[x, y] > 128 for x in range(0, W, 7))]
    if not op_cols or not op_rows:
        return None
    x0, x1 = op_cols[0], op_cols[-1]
    y0, y1 = op_rows[0], op_rows[-1]

    hits = []
    for x in range(W):                                     # 세로선
        n, at = _runs([black(x, y) for y in range(H)])
        if n >= H * MIN_LEN:
            side = min(x - x0, x1 - x) / max(1, x1 - x0)
            if side <= EDGE:
                hits.append(("세로", n / H, side, (x, at, x, at + n)))
    for y in range(H):                                     # 가로선
        n, at = _runs([black(x, y) for x in range(W)])
        if n >= W * MIN_LEN:
            side = min(y - y0, y1 - y) / max(1, y1 - y0)
            if side <= EDGE:
                hits.append(("가로", n / W, side, (at, y, at + n, y)))
    if not hits:
        return None
    return max(hits, key=lambda h: h[1])                   # 가장 긴 것


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--zoom", default="", help="걸린 곳을 확대해 저장할 폴더")
    args = ap.parse_args()

    files = sorted(CHAR.glob("*/*.png"))
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        files = [f for f in files if f.parent.name in want]

    bad = []
    for f in files:
        got = find_line(f)
        if got:
            kind, length, side, box = got
            name = f"{f.parent.name}/{f.stem}"
            bad.append((name, kind, length, side))
            print(f"  {name:24} {kind} 선 — 길이 {length*100:.0f}% · "
                  f"가장자리에서 {side*100:.1f}%")
            if args.zoom:
                out = Path(args.zoom)
                out.mkdir(parents=True, exist_ok=True)
                sp = strip_outline(Image.open(f).convert("RGBA"))
                x, y, x2, y2 = box
                pad = 70
                crop = sp.crop((max(0, min(x, x2) - pad), max(0, min(y, y2) - pad),
                                min(sp.width, max(x, x2) + pad),
                                min(sp.height, max(y, y2) + pad))).convert("RGB")
                crop.resize((crop.width * 2, crop.height * 2), Image.NEAREST) \
                    .save(out / f"{f.parent.name}_{f.stem}.png")

    if bad:
        print(f"\n칸 선이 남은 그림 {len(bad)}장 / 검사 {len(files)}장")
        print("→ char_sheet.py --redo 로 그 포즈만 다시 만드십시오 (한 장에 한 포즈).")
        return 1
    print(f"칸 선 없음 — 검사 {len(files)}장 전부 깨끗합니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ── 인물 그림 비율·여백 검사 (손님 요청 3번) ──────────────
# ⚠️ 이번 회차 그림에는 적용하지 않는다. **다음 회차부터** 새로 만든 그림이
#    규격에 맞는지 여기서 걸러낸다.
#    실측: 지금 그림은 가로÷세로 0.82~1.06(거의 정사각). 그래서 화면에서 키우면
#    가로가 먼저 꽉 차 세로로 못 커지고, 세로 쇼츠에서 인물이 48% 에 그친다.
SHAPE_MAX_RATIO = 0.80      # 가로÷세로. 이보다 넓으면 '너무 납작하다'
SHAPE_SIDE_PAD = 0.04       # 어깨 양옆에 최소 이만큼 여백(그림 폭 대비)


def shape_check(path):
    """그림 하나의 비율과 좌우 여백을 잰다. → (가로세로비, 왼여백, 오른여백)"""
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    a = im.getchannel("A")
    box = a.getbbox()
    if not box:
        return None
    im = im.crop(box)
    W, H = im.size
    px = im.load()
    left = right = W
    for y in range(0, H, max(1, H // 60)):
        row = [x for x in range(W) if px[x, y][3] > 40]
        if row:
            left = min(left, row[0])
            right = min(right, W - 1 - row[-1])
    return W / H, left / W, right / W
