#!/usr/bin/env python3
"""⭐ 클립 손질(워터마크 지우기 + 4:3 크롭)이 진짜 되는지 본다. 0원 · 인터넷 0회.

    python3 tools/clip_test.py

왜 (2026-08-20 운영자 지시)
    "오른쪽 아래 제미나이 워터마크는 자동으로 없애게끔 해줘. 이걸 코드에 반드시
     반영해."  /  "가로 4, 세로 3으로 크롭해서 쇼츠 영상에 사용하자."

    말로 "지웠다" 하면 안 된다. **가짜 클립에 밝은 표시를 실제로 얹어 놓고**,
    손질한 뒤 그 자리가 정말 어두워졌는지 픽셀로 재서 확인한다.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import clip as C                                            # noqa: E402

FAIL = []


def ck(label, cond, extra=""):
    print(("   ✅ " if cond else "   ❌ ") + label + (f"  ({extra})" if extra else ""))
    if not cond:
        FAIL.append(label)


def brightness(path, x, y, w, h, t=1.0):
    """그 자리 밝기 평균 (0~255). 워터마크가 있으면 훨씬 밝다."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(path), "-frames:v", "1",
         "-vf", f"crop={w}:{h}:{x}:{y},format=gray", "-f", "rawvideo", "-"],
        capture_output=True).stdout
    return sum(raw) / len(raw) if raw else -1


if not __import__("shutil").which("ffmpeg"):
    print("⚠️ ffmpeg 가 없어 건너뛴다")
    sys.exit(0)

print("⭐ 클립 손질 시험\n")

print("① 화면 크기가 달라져도 워터마크 자리를 맞게 잡는가")
for w, h in [(1280, 720), (720, 1280), (1920, 1080)]:
    x, y, bw, bh = C.mark_box(w, h)
    ck(f"{w}×{h} 상자가 화면 안에 있다", 0 < x and 0 < y and x + bw < w and y + bh < h,
       f"x{x} y{y} {bw}×{bh}")
    ck(f"{w}×{h} 상자가 네모다", bw == bh)
ck("720p 세로 영상에서도 상자가 찌그러지지 않는다",
   C.mark_box(720, 1280)[2] == C.mark_box(1280, 720)[2],
   "예전에는 34×107 짜리가 나왔다")

print("\n② 4:3 크롭이 정확한가")
for w, h in [(1280, 720), (1920, 1080)]:
    cx, cy, cw, ch = C.crop_box(w, h)
    ck(f"{w}×{h} → {cw}×{ch} 이 정확히 4:3", cw * 3 == ch * 4, f"{cw}:{ch}")
    ck(f"{w}×{h} 크롭이 짝수다 (h264 요구)", cw % 2 == 0 and ch % 2 == 0)
    ck(f"{w}×{h} 크롭이 가운데다", cx * 2 + cw == w or abs(w - (cx * 2 + cw)) <= 1)
cx, cy, cw, ch = C.crop_box(1280, 720)
mx, _, _, _ = C.mark_box(1280, 720)
ck("4:3 크롭이 워터마크 자리를 아예 잘라낸다", cx + cw <= mx, f"크롭 끝 {cx + cw} ≤ 표시 {mx}")

print("\n③ 진짜 영상으로 — 밝은 표시를 얹고 지워지는지 픽셀로 잰다")
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    fake = d / "fake.mp4"
    x, y, bw, bh = C.mark_box(1280, 720)
    # 어둑한 화면 + 오른쪽 아래에 밝은 네모(가짜 워터마크) + 소리
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", "color=c=0x203040:s=1280x720:r=24:d=3",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
         "-vf", f"drawbox=x={x + 6}:y={y + 6}:w={bw - 12}:h={bh - 12}:color=white@0.9:t=fill",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(fake)],
        check=True, capture_output=True)

    before = brightness(fake, x, y, bw, bh)
    ck("가짜 워터마크가 실제로 밝게 얹혔다", before > 120, f"밝기 {before:.0f}")

    made = C.tidy(fake, d)
    long_mp4 = next(p for p in made if p.name.endswith("_long.mp4"))
    short_mp4 = next(p for p in made if p.name.endswith("_short.mp4"))

    after = brightness(long_mp4, x, y, bw, bh)
    ck("워터마크가 지워졌다 (밝기가 배경 수준으로 내려감)", after < 80,
       f"{before:.0f} → {after:.0f}")

    w2, h2, _ = C.probe(short_mp4)
    ck("쇼츠본이 4:3 이다", w2 * 3 == h2 * 4, f"{w2}×{h2}")
    wl, hl, _ = C.probe(long_mp4)
    ck("롱폼본은 원래 크기 그대로다", (wl, hl) == (1280, 720), f"{wl}×{hl}")

    # 소리가 살아 있어야 한다 (다시 압축하지 않고 그대로 옮긴다)
    a = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                        "-show_entries", "stream=codec_name", "-of", "csv=p=0",
                        str(short_mp4)], capture_output=True, text=True).stdout.strip()
    ck("소리가 그대로 붙어 있다", a != "", a or "없음")

print("\n" + "─" * 52)
print(f"❌ 클립 손질: {len(FAIL)}가지 실패" if FAIL else "✅ 클립 손질: 전부 통과")
sys.exit(1 if FAIL else 0)
