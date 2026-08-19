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


# ── 되풀이되는 딸깍 소리 ────────────────────────────────
# ⚠️ 2026-08-13 손님: "시계초침 소리같이 '척척척척척' 이런 소리가 나는데 매우
#    어울리지 않고 어색하고 겉도는 느낌이야. 앞으로 다시는 삽입되지 않도록 조치해줘."
#
#    범인은 clock.mp3 였는데 **위의 is_beep 이 이걸 못 잡았다.** 실측:
#        파일 전체로 재면        0.1%   (25% 넘어야 걸린다)
#        가장 큰 구간만 재도     1.5%
#    까닭은 분명하다. 20밀리초짜리 짧은 딸깍은 소리의 힘이 원래 넓게 번진다.
#    '한 높이에 몰렸나' 로는 영원히 못 잡는다 — 2초짜리 옛 파일은 걸렸는데,
#    만드는 법이 남아 있어 4초짜리로 다시 만들어지면서 검사를 빠져나갔다.
#
#    잡아야 할 특징은 음색이 아니라 **규칙적으로 되풀이된다**는 것이다.
#    소리가 올라오는 순간(onset)만 뽑아 자기상관을 보면 바로 드러난다.
#    실측: clock 0.32(0.96초마다 4번) · phone 0.36(0.30초마다 10번) ·
#          진짜 소리들은 0.00~0.22.
TICK_SCORE = 0.30       # 이만큼 규칙적이면 '되풀이 딸깍'
TICK_REPS = 2.5         # 게다가 이만큼은 되풀이돼야 한다 (한두 번은 그냥 소리다)
TICK_MIN, TICK_MAX = 0.25, 1.6      # 사람이 '되풀이된다' 고 느끼는 주기(초)

_tick_cache = {}


def tick_score(path):
    """(규칙성 0~1, 주기 초, 몇 번 되풀이) — 못 재면 None."""
    path = str(path)
    if path in _tick_cache:
        return _tick_cache[path]
    val = None
    try:
        import numpy as np
        sr, hop = 16000, 0.005
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr),
             "-f", "s16le", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True).stdout
        x = np.frombuffer(raw, dtype="<i2").astype(float) / 32768.0
        n = int(sr * hop)
        m = len(x) // n
        if m >= 8:
            e = np.abs(x[:m * n]).reshape(m, n).max(axis=1)
            d = np.diff(e)
            d[d < 0] = 0                       # 소리가 **올라오는 순간**만 본다
            if d.std() > 1e-6:
                d = d - d.mean()
                ac = np.correlate(d, d, "full")[len(d) - 1:]
                ac /= ac[0]
                lo = int(TICK_MIN / hop)
                hi = min(len(ac) - 1, int(TICK_MAX / hop))
                if hi > lo:
                    k = lo + int(np.argmax(ac[lo:hi]))
                    per = k * hop
                    val = (float(ac[k]), per, (len(x) / sr) / per)
    except Exception:
        val = None
    _tick_cache[path] = val
    return val


def is_ticky(path):
    """시계 초침처럼 **규칙적으로 되풀이되는** 소리인가. 못 재면 False."""
    r = tick_score(path)
    return r is not None and r[0] >= TICK_SCORE and r[2] >= TICK_REPS


def is_fake(path):
    """영상에 깔면 안 되는 소리 — 순수음이거나 되풀이 딸깍이면 안 된다."""
    return is_beep(path) or is_ticky(path)


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
