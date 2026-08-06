#!/usr/bin/env python3
"""음높이 손보기가 **소리를 망가뜨리지 않는지** 시험한다. 제미나이는 안 부른다.

2026-08-06 사고 재현
    H05 를 8.6반음 끌어내렸더니 손님이 "그냥 목소리가 기괴하게 들린다" 고 하셨다.
    숫자는 맞췄는데 소리를 망쳤다. 두 번 다시 그러면 안 된다.
    · 크게 벗어난 컷은 **손대지 않는다** (voiceguard 가 잡아 영상을 막는다)
    · 다시 읽히는 몫은 **회차에서 가장 심한 컷부터** 쓴다 (인물 순서가 아니라)
"""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import tts  # noqa: E402

T = Path(tempfile.mkdtemp(prefix="vt-pitch-"))
fails = []
CALLED = []


def check(label, cond, extra=""):
    print(f"  {'OK  ' if cond else 'FAIL'} {label} {extra}")
    if not cond:
        fails.append(label)


def make(cid, hz, sec=3.0):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"sine=frequency={hz}:duration={sec}:sample_rate=24000",
                    "-af", "tremolo=f=5:d=0.7", "-b:a", "160k", str(T / f"{cid}.mp3")],
                   check=True)


def f0(cid):
    return tts.measure_f0(T / f"{cid}.mp3")


# 실제 사고와 같은 판: 장남은 조금씩 여러 컷이 튀고, 해설 H05 하나가 아주 심하다
PLAN = ([("H%02d" % i, 84) for i in range(1, 5)] + [("H05", 137)]
        + [("N%02d" % i, 84) for i in range(1, 8)]
        + [("M%02d" % i, 120) for i in range(1, 6)]
        + [("M06", 143), ("M07", 101)]          # 손볼 만큼 튄 것 (+3.0 / -2.9반음)
        + [("M08", 172), ("M09", 174)])         # 많이 튄 것 (+6.2 / +6.4반음)
CUTS = ([{"id": c, "speaker": "narrator", "text": "가나다라마바사"}
         for c, _ in PLAN if not c.startswith("M")]
        + [{"id": c, "speaker": "v_M50A", "text": "가나다라마바사"}
           for c, _ in PLAN if c.startswith("M")])


def setup():
    for cid, hz in PLAN:
        make(cid, hz)
    CALLED.clear()


def retake(cid):
    CALLED.append(cid)
    make(cid, 84 if not cid.startswith("M") else 120)
    return True


print("=" * 72)
print("  시험 1 — 다시 읽히는 몫을 **가장 심한 컷부터** 쓰나 (H05 에 닿나)")
print("=" * 72)
setup()
tts.normalize_pitch(T, CUTS, retake=retake)
check("H05 를 다시 읽혔다", "H05" in CALLED, f"부른 컷={CALLED}")
check("H05 가 제 높이로 왔다", abs(f0("H05") - 84) < 6, f"→ {f0('H05'):.0f}Hz")

print("\n" + "=" * 72)
print("  시험 2 — 다시 읽히기가 없을 때: **망가뜨리지 않고 그냥 두나**")
print("=" * 72)
setup()
tts.normalize_pitch(T, CUTS, retake=None)
h = f0("H05")
check("H05 를 억지로 끌어내리지 않았다", h > 120,
      f"→ {h:.0f}Hz (137Hz 그대로여야 정상 · 83Hz 로 갔으면 실패)")
check("손볼 만큼 튄 컷(+3반음)은 맞춘다", abs(f0("M06") - f0("M01")) < 10,
      f"M06 143Hz → {f0('M06'):.0f}Hz · 기준 {f0('M01'):.0f}Hz")
check("많이 튄 컷(+6.2반음)은 손대지 않는다", f0("M08") > 160,
      f"M08 → {f0('M08'):.0f}Hz (172Hz 그대로여야 정상)")

print("\n" + "=" * 72)
print("  시험 3 — 한 번에 옮기는 폭이 2반음을 절대 안 넘나")
print("=" * 72)
setup()
before = {c: f0(c) for c, _ in PLAN}
tts.normalize_pitch(T, CUTS, retake=None)
import math  # noqa: E402
moved = [(c, abs(12 * math.log2(f0(c) / before[c])))
         for c, _ in PLAN if f0(c) and before[c]]
# 2.2 로 재는 이유: 높이 재기가 자기상관 칸 단위라 0.05반음쯤 오차가 난다.
# 실제로 옮기라고 시킨 값은 정확히 2.00반음이다.
big = [(c, m) for c, m in moved if m > 2.2]
check("2반음 넘게 옮긴 컷이 없다", not big, f"넘은 것 {big[:3]}")
check("최대 이동폭", True, f"{max(m for _, m in moved):.2f}반음")

print("\n" + "=" * 72)
print("  모두 통과" if not fails else f"  실패 {len(fails)}건: {fails}")
print("=" * 72)
sys.exit(1 if fails else 0)
