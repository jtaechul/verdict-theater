#!/usr/bin/env python3
"""⭐ 플로우에서 받은 클립을 손질한다 — 워터마크 지우고 쇼츠용으로 자른다.

    python3 src/clip.py 받은클립.mp4                 → 두 벌 만든다
    python3 src/clip.py 받은클립.mp4 --out build/    → 저장할 곳 지정
    python3 src/clip.py 받은클립.mp4 --only short    → 쇼츠용만

무엇을 만드나
    *_long.mp4   16:9 그대로 · 워터마크만 지운 것 (8분 롱폼용)
    *_short.mp4  4:3 로 잘라낸 것 (쇼츠용 · 2026-08-20 운영자 지시)

왜 (2026-08-20 운영자 지시)
    ① "오른쪽 아래 제미나이 워터마크는 자동으로 없애게끔 해줘."
       실제 클립에서 재보니 1280×720 기준 오른쪽 아래 반짝이 표시가
       x 1132~1192 · y 570~630 에 있다. 화면 크기가 달라져도 따라가도록
       **비율로** 잡는다(오른쪽에서 6.9% · 아래에서 12.5% 자리).
       delogo 는 상자 테두리 색으로 안을 메운다 — 그 자리가 흐린 배경이라
       깨끗하게 지워진다(실제 클립으로 확인).
    ② "가로 4, 세로 3으로 크롭해서 쇼츠 영상에 사용하자."
       16:9(1280×720) 에서 가운데를 4:3(960×720) 으로 잘라낸다.
       ⚠️ 이 크롭만으로도 워터마크는 잘려 나간다(워터마크 x1132 > 크롭 끝 1120).
          그래도 delogo 를 **먼저** 건다 — 롱폼(16:9)에는 크롭이 없기 때문이다.

    소리는 그대로 옮긴다(다시 압축하지 않는다). 화면만 다시 만든다.
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# 워터마크 자리 — 실제 클립(1280×720)에서 잰 값이다.
#   반짝이 표시가 x 1132~1192 · y 570~630 → 오른쪽에서 88px, 아래에서 90px, 60×60
# ⚠️ 처음엔 이걸 '화면 너비의 몇 %' 로 적었는데, 세로 영상(720×1280)에 넣으면
#    34×107 짜리 엉뚱한 상자가 나왔다. 워터마크는 화면 비율을 따라 늘어나는 것이
#    아니라 **정해진 크기로 얹히는 그림**이다. 그래서 720p 기준 픽셀로 적고,
#    화면이 커지면 그만큼만 키운다(720p 의 짧은 변을 기준).
BASE = 720               # 플로우가 내주는 화질 (짧은 변)
MARK_RIGHT_PX = 84       # 오른쪽 끝에서 상자 오른쪽까지 (잰 값 88 - 여유 4)
MARK_BOTTOM_PX = 86      # 아래 끝에서 상자 아래까지 (잰 값 90 - 여유 4)
MARK_PX = 68             # 상자 한 변 (잰 값 60 + 여유 8) — 넓혀도 깨끗하다(확인함)

SHORT_RATIO = (4, 3)     # 쇼츠에 쓸 가로세로 (운영자 지시)


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True).stdout
    s = json.loads(out)["streams"][0]
    return int(s["width"]), int(s["height"]), float(s.get("duration") or 0)


def mark_box(w, h):
    """이 화면 크기에서 워터마크가 있는 상자 (x, y, w, h).

    delogo 는 상자가 화면 밖으로 나가면 통째로 실패한다. 안쪽으로 물린다."""
    k = min(w, h) / BASE                 # 720p 보다 크면 그만큼 키운다
    bw = bh = max(8, round(MARK_PX * k))
    x = w - round(MARK_RIGHT_PX * k) - bw
    y = h - round(MARK_BOTTOM_PX * k) - bh
    x = max(1, min(x, w - bw - 1))
    y = max(1, min(y, h - bh - 1))
    return x, y, bw, bh


def crop_box(w, h, ratio=SHORT_RATIO):
    """가운데를 정해진 가로세로로 잘라낸다 (짝수로 맞춘다 — h264 가 요구한다)."""
    rw, rh = ratio
    if w * rh > h * rw:                      # 원본이 더 넓다 → 좌우를 자른다
        cw, ch = round(h * rw / rh), h
    else:                                    # 원본이 더 높다 → 위아래를 자른다
        cw, ch = w, round(w * rh / rw)
    cw -= cw % 2
    ch -= ch % 2
    return (w - cw) // 2, (h - ch) // 2, cw, ch


def run(src, dst, vf):
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vf", vf,
           "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p",
           "-c:a", "copy",                   # 소리는 건드리지 않는다
           "-movflags", "+faststart", str(dst)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패:\n{p.stderr[:500]}")
    return dst


def tidy(src, out_dir, only=""):
    src = Path(src)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h, sec = probe(src)
    mx, my, mw, mh = mark_box(w, h)
    delogo = f"delogo=x={mx}:y={my}:w={mw}:h={mh}"
    made = []

    print(f"{src.name} — {w}×{h} · {sec:.1f}초")
    print(f"  워터마크 지울 자리: x{mx} y{my} {mw}×{mh}")

    if only in ("", "long"):
        d = out_dir / f"{src.stem}_long.mp4"
        run(src, d, delogo)
        made.append(d)
        print(f"  ✅ {d.name} — 16:9 그대로 · 워터마크 지움 (롱폼용)")

    if only in ("", "short"):
        cx, cy, cw, ch = crop_box(w, h)
        d = out_dir / f"{src.stem}_short.mp4"
        run(src, d, f"{delogo},crop={cw}:{ch}:{cx}:{cy}")
        made.append(d)
        print(f"  ✅ {d.name} — {cw}×{ch} ({SHORT_RATIO[0]}:{SHORT_RATIO[1]}) 쇼츠용")
        if cx + cw <= mx:
            print("     (이 크롭은 워터마크 자리를 아예 잘라낸다 — 두 겹으로 막힌다)")
    return made


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip", help="플로우에서 받은 mp4")
    ap.add_argument("--out", default="build/clips", help="저장할 곳")
    ap.add_argument("--only", default="", choices=["", "long", "short"])
    a = ap.parse_args()
    if not shutil.which("ffmpeg"):
        print("❌ ffmpeg 가 없다", file=sys.stderr)
        return 2
    if not Path(a.clip).exists():
        print(f"❌ {a.clip} 이 없다", file=sys.stderr)
        return 2
    tidy(a.clip, a.out, a.only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
