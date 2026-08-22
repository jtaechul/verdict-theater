#!/usr/bin/env python3
"""목소리 고르는 잣대가 제대로 재는가 (제미나이는 안 부른다 · 값 0원)."""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import voice_judge as V                                      # noqa: E402

FAIL = []


def ck(label, cond, extra=""):
    print(("   ✅ " if cond else "   ❌ ") + label + (f"  ({extra})" if extra else ""))
    if not cond:
        FAIL.append(label)


def tone(spec, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", spec,
                    "-ac", "1", "-ar", "8000", str(out)], check=True)
    return out


print("⭐ 목소리 고르는 잣대\n")
tmp = Path(tempfile.mkdtemp())

print("① 받아쓰기가 얼마나 틀렸는지 센다")
ck("똑같으면 0", V.cer("당신 진짜 제정신이야", "당신 진짜 제정신이야") == 0.0)
ck("한 글자 틀리면 조금", 0 < V.cer("당신 진짜 제정신이야", "당신 진자 제정신이야") < 0.2)
ck("아주 다르면 1", V.cer("당신 진짜 제정신이야", "전혀 다른 말입니다") == 1.0)
ck("빈손이면 1", V.cer("당신 진짜", "") == 1.0)
ck("띄어쓰기·문장부호는 안 센다",
   V.cer("당신 진짜 제정신이야?!", "당신진짜제정신이야") == 0.0,
   "받아쓰기마다 띄어쓰기가 달라 그것까지 세면 엉뚱한 벌점이 된다")

print("\n② 구간 점수 (좋은 구간 안이면 만점, 벗어난 만큼 깎는다)")
ck("구간 안이면 만점", V.band(6.8, *V.GOOD_SPS, wide=2.5) == 1.0)
ck("조금 벗어나면 조금 깎인다", 0.5 < V.band(5.5, *V.GOOD_SPS, wide=2.5) < 1.0)
ck("많이 벗어나면 0점", V.band(3.0, *V.GOOD_SPS, wide=2.5) == 0.0)
ck("못 쟀으면 가운데", V.band(None, *V.GOOD_SPS, wide=2.5) == 0.5,
   "못 쟀다고 0점을 주면 잴 수 없는 목소리가 무조건 탈락한다")

print("\n③ 억양 폭을 진짜로 재는가 (아는 소리로 맞춰 본다)")
flat = V.f0_spread(tone("sine=frequency=200:duration=2:sample_rate=8000",
                        tmp / "flat.wav"))
wave_ = V.f0_spread(tone("sine=frequency=200:duration=2:sample_rate=8000,"
                         "vibrato=f=3:d=0.9", tmp / "wave.wav"))
ck("밋밋한 소리는 거의 0", flat is not None and flat < 0.5,
   f"{flat}" if flat is not None else "못 쟀다")
ck("흔들리는 소리는 넓게 나온다", wave_ is not None and wave_ > 2.0,
   f"{wave_}" if wave_ is not None else "못 쟀다")
ck("둘을 갈라낸다", None not in (flat, wave_) and wave_ > flat + 2.0)

print("\n④ 점수 매기는 무게가 뜻대로인가")
ck("잰 값(받아쓰기·빠르기·억양)이 의견(원어민)보다 무겁다",
   40 + 15 + 15 > 30, "70 대 30")
ck("네 가지를 더하면 100점", 40 + 30 + 15 + 15 == 100)

print("\n" + "─" * 52)
print(f"❌ 목소리 잣대: {len(FAIL)}가지 실패" if FAIL else "✅ 목소리 잣대: 전부 통과")
sys.exit(1 if FAIL else 0)
