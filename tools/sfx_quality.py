#!/usr/bin/env python3
"""효과음이 **진짜 소리인지, 기계가 만든 '삑' 소리인지** 가린다. 값 0원.

    python3 tools/sfx_quality.py              # 지금 있는 효과음 전부 검사
    python3 tools/sfx_quality.py --strict     # 삑 소리가 하나라도 있으면 실패(1)

왜 (2026-08-09 손님: "중간에 불필요하게 '삑 삑' 소리가 나는 효과음이 있는데
                     이거는 들어가지 않도록 제거해 줘. 6분30초~6분32초")
    그 자리는 A2-27, 깔린 소리는 `clock.mp3` 였다. 그런데 이 파일은 **시계 소리가
    아니었다** — 1400Hz 순수 전자음을 1초 간격으로 두 번 울리는 것, 곧 "삑… 삑" 이다.
    같은 방식으로 만들어진 가짜가 넷이었다(전부 33,062바이트 · 정확히 2.00초):

        clock.mp3     1400Hz 삑     ← 6분30초의 그 소리 (본편에서 10번 울렸다)
        monitor.mp3    880Hz 삑
        phone.mp3     1000Hz 삑
        heartbeat.mp3   52Hz 웅

    문제의 뿌리는 "한 자리를 지우는 것" 이 아니라 **가짜 소리 파일** 이다.
    그래서 자리를 지우지 않고, 이 검사로 **가짜를 아예 못 쓰게 막는다.**

어떻게 가리나 (귀가 아니라 자로 잰다)
    진짜 소리(발소리·종이·문)는 소리의 힘이 여러 높이에 넓게 퍼진다.
    기계가 만든 삑 소리는 **딱 한 높이에만** 힘이 몰린다.
    그 몰린 정도(tonality)가 25%를 넘으면 삑 소리로 본다.
    실측: 가짜 넷은 42·47·58·97%, 진짜 여섯은 1·3·3·4·4·5% — 사이가 넉넉히 벌어진다.

    ⚠️ ffmpeg 나 numpy 가 없으면 **못 잰다(None)**. 그때는 막지 않는다 —
       못 재는 것을 '가짜' 로 몰면 멀쩡한 소리까지 사라진다.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SFX_DIR = ROOT / "assets" / "sfx"

# 한 높이에 힘이 이만큼 넘게 몰려 있으면 '기계가 만든 삑' 으로 본다.
# 실측(2026-08-09): 가짜 42~97% · 진짜 1~5%. 25%는 그 한가운데다.
BEEP_TONALITY = 0.25

_cache = {}


def tone_ratio(path):
    """가장 센 높이 언저리(±3%)에 소리의 힘이 얼마나 몰렸는지. 0~1.

    못 재면 None 을 준다(ffmpeg·numpy 없음, 파일 깨짐 등)."""
    path = str(path)
    if path in _cache:
        return _cache[path]
    val = None
    try:
        import numpy as np
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "22050",
             "-f", "s16le", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
        a = np.frombuffer(raw, dtype="<i2").astype(float) / 32768.0
        if len(a) >= 2048 and float(np.abs(a).max()) > 1e-4:
            sp = np.abs(np.fft.rfft(a * np.hanning(len(a))))
            fr = np.fft.rfftfreq(len(a), 1 / 22050)
            peak = float(fr[int(np.argmax(sp))])
            near = (fr > peak * 0.97) & (fr < peak * 1.03)
            tot = float(sp.sum())
            if tot > 0:
                val = float(sp[near].sum() / tot)
    except Exception:
        val = None
    _cache[path] = val
    return val


def is_beep(path):
    """기계가 만든 '삑' 소리인가. 못 재면 False(막지 않는다)."""
    r = tone_ratio(path)
    return r is not None and r >= BEEP_TONALITY


def peak_hz(path):
    """가장 센 높이(Hz). 사람에게 보여 줄 때만 쓴다."""
    try:
        import numpy as np
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "22050",
             "-f", "s16le", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
        a = np.frombuffer(raw, dtype="<i2").astype(float) / 32768.0
        if len(a) < 2048:
            return None
        sp = np.abs(np.fft.rfft(a * np.hanning(len(a))))
        fr = np.fft.rfftfreq(len(a), 1 / 22050)
        return float(fr[int(np.argmax(sp))])
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=str(SFX_DIR))
    ap.add_argument("--strict", action="store_true",
                    help="삑 소리가 하나라도 있으면 실패로 끝낸다")
    a = ap.parse_args()

    files = sorted(Path(a.dir).glob("*.mp3"))
    if not files:
        print(f"{a.dir} 에 효과음이 없습니다.")
        return 0

    bad = []
    unknown = 0
    print(f"{'이름':16s}{'몰린정도':>9s}{'센높이':>9s}  판정")
    print("-" * 52)
    for p in files:
        r = tone_ratio(p)
        if r is None:
            unknown += 1
            print(f"{p.stem:16s}{'-':>9s}{'-':>9s}  못 쟀습니다")
            continue
        hz = peak_hz(p)
        beep = r >= BEEP_TONALITY
        if beep:
            bad.append(p.stem)
        print(f"{p.stem:16s}{r * 100:8.0f}%{(hz or 0):8.0f}Hz  "
              f"{'⚠ 기계가 만든 삑 소리' if beep else '진짜 소리'}")

    print()
    if bad:
        print(f"삑 소리 {len(bad)}개: {', '.join(bad)}")
        print("  → 이 소리들은 영상에 깔리지 않습니다(add_sfx.py 가 건너뜁니다).")
        print("  → 진짜 소리로 바꾸려면 [효과음 받아오기] 를 돌리십시오.")
    else:
        print("모두 진짜 소리입니다.")
    if unknown:
        print(f"(못 잰 것 {unknown}개 — ffmpeg 나 numpy 가 없으면 못 잽니다)")

    return 1 if (bad and a.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
