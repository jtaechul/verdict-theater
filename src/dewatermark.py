#!/usr/bin/env python3
"""AI 이미지 생성기가 오른쪽 아래에 찍는 로고 워터마크를 지운다.

    python3 src/dewatermark.py assets/bg            폴더 전체를 제자리에서 처리
    python3 src/dewatermark.py assets/bg/court_hall.jpg
    python3 src/dewatermark.py assets/bg --dry      지우지 않고 무엇을 할지만 본다

왜 필요한가
    제미나이(Gemini·Imagen)로 배경을 만들면 오른쪽 아래 모서리에 마름모 모양 로고가
    박혀 나온다. 그대로 쓰면 12분 내내 화면 구석에 남의 로고가 붙어 있고,
    유튜브 섬네일에도 그대로 들어간다.

어떻게 지우나 — **거울처럼 접어 덮기**
    그 구석을 **바로 왼쪽의 같은 크기 조각을 좌우로 뒤집어** 덮는다.
    거울로 접는 것이라 접는 선(조각의 왼쪽 끝)에서는 값이 원본과 정확히 같다 —
    이음매가 생길 수 없다. 위쪽 가장자리만 서서히 이어 붙이면 끝이다.

    위쪽 조각을 위아래로 뒤집는 방법도 있지만 쓰지 않는다. 그러면 **가로로 이어지던
    것이 끊긴다** — 벽과 바닥이 만나는 선, 책상 모서리, 지평선이 엉뚱한 높이에
    다시 나타난다. 실제로 시험해 보니 이음매가 가로줄로 드러났다.

    잘라내지 않는 이유: 아래를 잘라내면 화면 비율이 틀어지고, 다시 늘리면
    배경 전체가 미세하게 뭉개진다. 구석 하나 때문에 그림 전체를 손댈 이유가 없다.

이미 지운 그림을 또 지워도 되나
    된다. 같은 자리를 한 번 더 덮을 뿐이라 그림이 나빠지지 않는다.
    다만 헛일을 줄이려고 처리한 파일 목록을 `.dewatermark.json` 에 적어 둔다.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

# 워터마크가 앉는 자리 — 그림 크기 대비 비율 (왼쪽, 위, 오른쪽, 아래).
# 제미나이 로고는 오른쪽 아래 모서리에서 조금 띄워 찍힌다. 기기·비율마다 조금씩
# 다르므로 실제 로고보다 **넉넉하게** 잡는다. 넉넉해도 배경이라 티가 나지 않는다.
BOX = (0.800, 0.820, 1.0, 1.0)

# 가장자리를 녹이는 폭 (조각 짧은 변 대비).
# ⚠️ 이 값이 크면 안 된다. 처음엔 0.22 에 가우시안 흐림까지 썼는데, 덮는 자리의
#    위쪽 40픽셀이 반투명이 되어 **로고 윗부분이 그대로 비쳐 나왔다**(실측: 확대해 보니
#    별 모양이 옅게 남아 있었다). 이제 위·왼쪽에서 이 폭만큼만 곧게 이어 붙이고,
#    그 안쪽은 100% 덮는다.
FEATHER = 0.28
EXTS = (".jpg", ".jpeg", ".png", ".webp")
LEDGER = ".dewatermark.json"


def wm_box(W, H):
    """이 그림에서 워터마크를 덮을 사각형 (왼쪽, 위, 오른쪽, 아래) 픽셀."""
    x0, y0, x1, y1 = BOX
    return (int(W * x0), int(H * y0), int(W * x1), int(H * y1))


def patch(img):
    """워터마크 자리를 바로 왼쪽 조각을 뒤집어 덮는다. 새 이미지를 돌려준다.

    ⚠️ 투명한 그림(인물 컷아웃 PNG)은 투명도를 그대로 지켜야 한다.
       RGB 로 바꿔 버리면 배경이 검게 채워져 컷아웃이 통째로 망가진다."""
    transparent = img.mode in ("RGBA", "LA") or (
        img.mode == "P" and "transparency" in img.info)
    img = img.convert("RGBA" if transparent else "RGB")
    W, H = img.size
    x0, y0, x1, y1 = wm_box(W, H)
    bw, bh = x1 - x0, y1 - y0
    if bw < 4 or bh < 4:
        return img

    # ⭐ 덮을 조각은 **바로 왼쪽**에서 가져와 좌우로 뒤집는다.
    #    위쪽에서 가져와 위아래로 뒤집어도 되지만, 그러면 **가로로 이어지던 것이 끊긴다** —
    #    방바닥과 벽이 만나는 선, 책상 모서리, 지평선 같은 것들이 엉뚱한 높이에 다시 나타난다.
    #    (실측: 가로 띠가 있는 그림에서 이음매가 선으로 드러났다.)
    #    좌우로 뒤집으면 ① 같은 높이의 것이 같은 높이에 오고
    #                  ② 뒤집는 축(조각의 왼쪽 끝)에서는 값이 원본과 **정확히 같아**
    #                     이음매가 생길 수 없다.
    if x0 - bw >= 0:
        src = img.crop((x0 - bw, y0, x0, y1)).transpose(Image.FLIP_LEFT_RIGHT)
    elif y0 - bh >= 0:
        src = img.crop((x0, y0 - bh, x1, y0)).transpose(Image.FLIP_TOP_BOTTOM)
    else:
        src = img.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(bh / 3))

    # 마스크 — 위쪽 가장자리에서만 서서히 이어 붙인다.
    # 왼쪽은 뒤집는 축이라 이미 딱 맞고, 오른쪽·아래는 그림의 끝이다.
    # 가우시안 흐림이 아니라 곧은 기울기를 쓴다 — 어디부터 완전히 덮이는지가
    # 계산으로 딱 떨어져야, 로고가 반투명 구간에 걸리는 사고가 안 난다.
    # (실측: 흐림 마스크를 썼더니 덮는 자리 위쪽 40픽셀이 반투명이 되어 로고가 비쳤다.)
    f = max(2, int(min(bw, bh) * FEATHER))
    mask = Image.new("L", (bw, bh), 255)
    mp = mask.load()
    for y in range(min(f, bh)):
        v = int(255 * (y / f))
        for x in range(bw):
            mp[x, y] = v

    out = img.copy()
    out.paste(src, (x0, y0), mask)
    return out


def _digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def process(path, dry=False, quality=94):
    """파일 하나를 처리한다. 바뀌었으면 True."""
    img = Image.open(path)
    W, H = img.size
    if dry:
        x0, y0, x1, y1 = wm_box(W, H)
        print(f"  {path.name:34} {W}x{H} → 덮을 자리 ({x0},{y0})-({x1},{y1})")
        return False
    out = patch(img)
    if path.suffix.lower() in (".jpg", ".jpeg"):
        out.convert("RGB").save(path, quality=quality, subsampling=0)
    else:
        out.save(path)
    print(f"  {path.name:34} {W}x{H}  워터마크 자리 덮음")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="+", help="이미지 파일 또는 폴더")
    ap.add_argument("--dry", action="store_true", help="지우지 않고 자리만 확인")
    ap.add_argument("--force", action="store_true", help="이미 처리한 파일도 다시 처리")
    args = ap.parse_args()

    files, root = [], None
    for t in args.target:
        p = Path(t)
        if p.is_dir():
            root = root or p
            files += [f for f in sorted(p.iterdir()) if f.suffix.lower() in EXTS]
        elif p.is_file():
            files.append(p)
        else:
            print(f"없는 경로: {p}", file=sys.stderr)

    if not files:
        print("처리할 이미지가 없다.")
        return 0

    # 이미 처리한 파일은 건너뛴다 (내용이 그대로일 때만)
    ledger_path = (root or files[0].parent) / LEDGER
    done = {}
    if ledger_path.exists() and not args.force:
        try:
            done = json.loads(ledger_path.read_text(encoding="utf-8"))
        except Exception:
            done = {}

    changed, skipped = 0, 0
    for f in files:
        if not args.force and done.get(f.name) == _digest(f):
            skipped += 1
            continue
        if process(f, dry=args.dry):
            changed += 1
            done[f.name] = _digest(f)

    if not args.dry and changed:
        ledger_path.write_text(json.dumps(done, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    print(f"\n{changed}장 처리 · {skipped}장 건너뜀(이미 처리) · 전체 {len(files)}장")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
