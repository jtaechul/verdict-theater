#!/usr/bin/env python3
"""⭐ 쇼츠 배치(위 후킹 · 가운데 영상 · 아래 자막)가 맞게 그려지는지 본다. 0원.

    python3 tools/shorts_test.py

왜 (2026-08-20 운영자 지시)
    "상단 검은 빈 프레임에는 후킹 문구가 들어가고, 아래쪽 검은 빈 프레임에는
     자막이 들어가도록 하자."

    글자가 **정해진 칸 안에** 들어갔는지, 영상 자리를 침범하지 않는지,
    유튜브 단추가 덮는 아래쪽을 비워 뒀는지를 그림의 픽셀로 직접 확인한다.
    (자리를 눈대중으로 적었다가 여러 번 고친 적이 있다 — 그림을 재서 본다)
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import shorts as S                                          # noqa: E402
from PIL import Image                                       # noqa: E402

FAIL = []


def ck(label, cond, extra=""):
    print(("   ✅ " if cond else "   ❌ ") + label + (f"  ({extra})" if extra else ""))
    if not cond:
        FAIL.append(label)


def rows_with_ink(img, y0, y1):
    """그 구간에서 글자가 실제로 그려진 줄 번호들."""
    a = img.crop((0, y0, S.W, y1)).split()[-1]        # 투명도 칸
    out = []
    for y in range(y1 - y0):
        line = a.crop((0, y, S.W, y + 1)).tobytes()
        if max(line) > 40:
            out.append(y0 + y)
    return out


print("⭐ 쇼츠 배치 시험\n")

print("① 칸이 서로 겹치지 않는가")
ck("위 검은 칸 → 영상 → 아래 검은 칸 순서다",
   S.HOOK_BOT <= S.VIDEO_Y < S.VIDEO_Y + S.VIDEO_H <= S.SUB_TOP,
   f"후킹끝 {S.HOOK_BOT} · 영상 {S.VIDEO_Y}~{S.VIDEO_Y + S.VIDEO_H} · 자막 {S.SUB_TOP}")
ck("영상이 정확히 4:3", S.W * 3 == S.VIDEO_H * 4, f"{S.W}×{S.VIDEO_H}")
ck("전체가 쇼츠 규격(9:16)", S.W * 16 == S.H * 9, f"{S.W}×{S.H}")
ck("유튜브 단추 자리(아래 300px 이상)를 비워 뒀다", S.H - S.SUB_BOT >= 300,
   f"{S.H - S.SUB_BOT}px 비움")

print("\n② 글자가 제자리에만 그려지는가 (그림을 픽셀로 잰다)")
with tempfile.TemporaryDirectory() as d:
    png = S.overlay_png("바람난 남편이 빼돌린 15억",
                        "당신 진짜 제정신이야? / 더는 숨 막혀서 못 살아. / "
                        "누구 맘대로 집을 나가!", Path(d) / "t.png")
    img = Image.open(png).convert("RGBA")
    ck("그림 크기가 화면과 같다", img.size == (S.W, S.H), f"{img.size}")

    hook_ink = rows_with_ink(img, S.HOOK_TOP, S.HOOK_BOT)
    sub_ink = rows_with_ink(img, S.SUB_TOP, S.SUB_BOT)
    video_ink = rows_with_ink(img, S.VIDEO_Y, S.VIDEO_Y + S.VIDEO_H)
    below_ink = rows_with_ink(img, S.SUB_BOT, S.H)

    ck("후킹 문구가 위 칸에 그려졌다", len(hook_ink) > 20, f"{len(hook_ink)}줄")
    ck("자막이 아래 칸에 그려졌다", len(sub_ink) > 20, f"{len(sub_ink)}줄")
    ck("영상 자리에는 글자가 없다", not video_ink, f"{len(video_ink)}줄 침범")
    ck("유튜브 단추 자리에도 글자가 없다", not below_ink, f"{len(below_ink)}줄 침범")

    mark_ink = rows_with_ink(img, 0, S.VIDEO_Y and S.HOOK_TOP)
    ck("우측 상단에 채널 이름이 있다", len(mark_ink) > 5, f"{len(mark_ink)}줄")

print("\n③ 자막을 말한 사람마다 줄을 나누는가")
from PIL import ImageDraw                                   # noqa: E402
d0 = ImageDraw.Draw(Image.new("RGBA", (S.W, S.H)))
f, ls = S.fit(d0, "가나다라마. / 바사아자차. / 카타파하.", S.FONT_M,
              S.SUB_SIZE, S.W - S.SIDE * 2, 4, split_slash=True)
ck("빗금마다 줄이 바뀐다", len(ls) == 3, f"{ls}")
f, ls = S.fit(d0, "한 사람만 말하는 컷입니다.", S.FONT_M,
              S.SUB_SIZE, S.W - S.SIDE * 2, 4, split_slash=True)
ck("한 사람만 말하면 한 줄", len(ls) == 1, f"{ls}")

print("\n④ 긴 글도 칸을 안 넘는가 (글자를 줄여서라도 넣는다)")
long_hook = "이십 년을 함께 산 아내에게 남긴 것은 빚 칠억과 이혼 서류 한 장뿐이었다"
f, ls = S.fit(d0, long_hook, S.FONT_B, S.HOOK_SIZE, S.W - S.SIDE * 2, 3)
ck("긴 후킹 문구도 3줄 안에 들어간다", len(ls) <= 3, f"{len(ls)}줄 · {f.size}px")
ck("그래도 너무 작아지지는 않는다", f.size >= 40, f"{f.size}px")

print("\n⑤ 진짜 영상으로 한 번 만들어 본다")
if not shutil.which("ffmpeg"):
    print("   ⚠️ ffmpeg 가 없어 건너뛴다")
else:
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        fake = d / "cut.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y",
             "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=24:d=2",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(fake)],
            check=True, capture_output=True)
        out = S.compose(fake, "후킹 문구", "자막 한 줄", d / "o.mp4", d / "tmp")
        import clip as C
        w, h, sec = C.probe(out)
        ck("쇼츠 크기(1080×1920)로 나온다", (w, h) == (S.W, S.H), f"{w}×{h}")
        ck("길이가 원본과 같다", abs(sec - 2.0) < 0.3, f"{sec:.1f}초")
        a = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                            "-show_entries", "stream=codec_name", "-of", "csv=p=0",
                            str(out)], capture_output=True, text=True).stdout.strip()
        ck("소리가 붙어 있다", a != "", a or "없음")

print("\n" + "─" * 52)
print(f"❌ 쇼츠 배치: {len(FAIL)}가지 실패" if FAIL else "✅ 쇼츠 배치: 전부 통과")
sys.exit(1 if FAIL else 0)
