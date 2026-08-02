#!/usr/bin/env python3
"""컷 몇 개를 실제 화면 그대로 그려 한 장의 확인용 시트로 만든다.

    python3 tools/preview.py 0,4,33,55 out.png            가로 본편
    python3 tools/preview.py 0,4 out.png --vertical       세로 쇼츠
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw  # noqa: E402
import render as R  # noqa: E402


def frame(cut, W, H, vertical):
    move, gfx, sub = R.build_plates(cut, W, H, vertical=vertical)
    out = move.convert("RGBA")
    out = Image.alpha_composite(out, gfx)
    out = Image.alpha_composite(out, sub)
    return out.convert("RGB")


def main():
    idx = [int(s) for s in sys.argv[1].split(",")]
    out_path = sys.argv[2]
    vertical = "--vertical" in sys.argv
    W, H = (1080, 1920) if vertical else (1920, 1080)

    doc = json.loads((ROOT / "data" / "scripts" / "EP001.json").read_text(encoding="utf-8"))
    cuts = [c for a in doc["acts"] for c in a["cuts"]]

    TH = 560 if vertical else 400
    tiles = []
    for i in idx:
        im = frame(cuts[i], W, H, vertical)
        k = TH / im.height
        im = im.resize((round(im.width * k), TH), Image.LANCZOS)
        card = Image.new("RGB", (im.width, TH + 24), (255, 255, 255))
        card.paste(im, (0, 24))
        who = ",".join(c.get("pose", "") for c in (cuts[i].get("chars") or []))
        ImageDraw.Draw(card).text((6, 6), f"#{i}  {who}", fill=(0, 0, 0))
        # 화면 아래 경계선을 빨갛게 — 인물이 여기 닿아야 한다
        ImageDraw.Draw(card).line([(0, TH + 23), (im.width, TH + 23)], fill=(230, 20, 20), width=2)
        tiles.append(card)

    cols = 2 if vertical else 2
    rows = (len(tiles) + cols - 1) // cols
    tw, th = max(t.width for t in tiles), tiles[0].height
    sheet = Image.new("RGB", (tw * cols, th * rows), (250, 250, 252))
    for i, t in enumerate(tiles):
        sheet.paste(t, (tw * (i % cols), th * (i // cols)))
    sheet.save(out_path)
    print(out_path, sheet.size)


if __name__ == "__main__":
    raise SystemExit(main())
