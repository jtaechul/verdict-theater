#!/usr/bin/env python3
"""해설 목소리를 **컷마다 재서, 어느 컷이 무엇이 다른지** 숫자로 보여준다. 값 0원.

    python3 src/voicecheck.py data/scripts/EP001.json --voice build/voice
    python3 src/voicecheck.py data/scripts/EP001.json --cut H05,A1-15

왜 이렇게 다시 만들었나
    손님이 "이 컷 해설이 얇고 하이톤이다" 라고 세 번 짚어 주셨는데, 나는 세 번 다
    **그 컷을 재보지도 않고** 전체 평균만 보고 고쳤다. 그래서 세 번 다 빗나갔다.
      · 1차: 목소리 크기를 맞췄다 → 크기가 원인이 아니었다
      · 2차: 음색을 평균으로 당겼다 → 최대 ±4dB 이라 모자랐다
      · 3차: 튀는 컷을 다시 읽혔다 → 손님이 짚은 컷은 순번에 밀려 손도 못 댔다
    이제 **지목된 컷을 다른 컷과 나란히 놓고** 다섯 가지를 잰다.

무엇을 재나 (컷마다)
    크기   평균 음량(dB)              — 가까웠다 멀어졌다 하는 느낌
    높이   목소리 기본 주파수(Hz)      — 굵다/가늘다
    저음   300Hz 아래 비중(dB)        — 낮을수록 **얇게** 들린다
    고음   3.5kHz 위 비중(dB)         — 높을수록 **날카롭게** 들린다
    속도   글자 수 ÷ 길이(자/초)       — 빨랐다 느렸다

어떻게 읽나
    다섯 가지 각각에 대해 **가운뎃값**과 **보통 흔들리는 폭**(위아래 10% 를 뺀 폭)을
    낸다. 그리고 컷마다 '보통 폭의 몇 배나 벗어났는지' 를 점수로 매긴다.
    점수가 큰 것이 진짜 튀는 컷이다 — **문턱값은 이 분포를 보고 정한다.**
    (지금까지 쓰던 0.8dB·2.5dB 는 내가 근거 없이 정한 값이라 멀쩡한 컷을 무더기로
     '튄다' 고 셌다. 그것이 3차 수정이 빗나간 이유다.)

한 번도 API 를 부르지 않는다 — 이미 만들어 둔 파일만 읽는다.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tts import measure_f0  # noqa: E402

# 저음·고음 경계는 tts·render 와 **같은 값**을 쓴다. 따로 두면 숫자를 못 비교한다.
TONE_LOW, TONE_HIGH = 300, 3500


def mean_db(path, af=""):
    """평균 음량(dB). af 를 주면 그 필터를 건 뒤의 크기. 못 재면 None."""
    chain = (af + "," if af else "") + "volumedetect"
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
                            "-af", chain, "-f", "null", "-"],
                           capture_output=True, text=True, timeout=120)
    except Exception:
        return None
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else None


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def pct(vals, q):
    s = sorted(vals)
    return s[min(len(s) - 1, max(0, int(len(s) * q)))]


def measure(path, text):
    """한 컷의 다섯 가지. 하나라도 못 재면 None 을 넣어 **못 잰 것을 감춘다 안 한다.**"""
    d = duration(path)
    full = mean_db(path)
    if d <= 0.2 or full is None or full < -60:
        return None
    lo = mean_db(path, f"lowpass=f={TONE_LOW}")
    hi = mean_db(path, f"highpass=f={TONE_HIGH}")
    return {
        "크기": full,
        "높이": measure_f0(path),
        "저음": None if lo is None else lo - full,
        "고음": None if hi is None else hi - full,
        "속도": len(text) / d,
        "_초": d,
    }


KEYS = ("크기", "높이", "저음", "고음", "속도")
UNIT = {"크기": "dB", "높이": "Hz", "저음": "dB", "고음": "dB", "속도": "자/초"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--voice", default="build/voice")
    ap.add_argument("--who", default="narrator", help="이 인물만 (비우면 전부)")
    ap.add_argument("--cut", default="H05,A1-15",
                    help="점수가 낮아도 **반드시 보여줄** 컷 (쉼표로 구분)")
    ap.add_argument("--top", type=int, default=12, help="가장 튀는 컷 몇 개를 볼까")
    a = ap.parse_args()

    doc = json.loads(Path(a.script).read_text(encoding="utf-8"))
    vdir = Path(a.voice)
    if not vdir.exists():
        print(f"❌ 음성 폴더가 없다: {vdir}")
        return 2
    pin = {s.strip() for s in a.cut.split(",") if s.strip()}

    rows, miss = [], 0
    for act in doc.get("acts", []):
        for c in act.get("cuts", []):
            text = (c.get("text") or "").strip()
            sp = c.get("speaker", "narrator")
            if not text or (a.who and sp != a.who):
                continue
            p = vdir / f"{c['id']}.mp3"
            if not p.exists() or p.with_suffix(".silent").exists():
                miss += 1
                continue
            m = measure(p, text)
            if m:
                m["id"], m["글"] = c["id"], text
                rows.append(m)

    if len(rows) < 5:
        print(f"❌ 잰 컷이 {len(rows)}개뿐이라 비교할 수 없다.")
        return 2

    who = "해설" if a.who == "narrator" else (a.who or "전원")
    print(f"음성 점검 — {Path(a.script).stem} · {who} {len(rows)}컷"
          f"{f' (건너뛴 컷 {miss}개)' if miss else ''}\n")

    # ── ① 다섯 가지가 보통 얼마나 흔들리는지 (문턱값은 여기서 정한다) ──
    stat = {}
    print("■ 보통 얼마나 흔들리나  (이 분포를 보고 문턱값을 정한다)")
    print(f"    {'':4s} {'가운뎃값':>10s} {'보통 폭':>9s} {'가장 낮음':>10s} {'가장 높음':>10s}")
    for k in KEYS:
        v = [r[k] for r in rows if r[k] is not None]
        if len(v) < 5:
            print(f"    {k:4s}   ⚠️ 재지 못함 ({len(v)}/{len(rows)}컷만 측정됨)")
            stat[k] = None
            continue
        mid, lo, hi = pct(v, 0.5), pct(v, 0.1), pct(v, 0.9)
        stat[k] = (mid, max(1e-6, hi - lo))
        print(f"    {k:4s} {mid:10.1f} {hi - lo:9.1f} {min(v):10.1f} {max(v):10.1f}  {UNIT[k]}")

    # ── ② 컷마다 '보통 폭의 몇 배나 벗어났나' ──
    for r in rows:
        s, worst = 0.0, ""
        for k in KEYS:
            if stat.get(k) is None or r[k] is None:
                continue
            mid, spread = stat[k]
            z = abs(r[k] - mid) / spread
            if z > s:
                s, worst = z, k
            r[f"z_{k}"] = (r[k] - mid) / spread
        r["점수"], r["가장튄것"] = s, worst

    def show(title, items):
        if not items:
            return
        print(f"\n■ {title}")
        head = "    " + f"{'컷':8s}{'점수':>6s}" + "".join(f"{k:>8s}" for k in KEYS)
        print(head)
        print("    " + "-" * (len(head) - 4))
        for r in items:
            cells = "".join(
                (f"{r['z_' + k]:+8.1f}" if r.get(f"z_{k}") is not None else f"{'?':>8s}")
                for k in KEYS)
            print(f"    {r['id']:8s}{r['점수']:6.1f}{cells}")
            print(f"        {r['글'][:44]}")

    ranked = sorted(rows, key=lambda r: -r["점수"])
    show(f"가장 튀는 컷 {a.top}개  (숫자는 '보통 폭의 몇 배' — +는 높음, -는 낮음)",
         ranked[:a.top])

    named = [r for r in rows if r["id"] in pin]
    if named:
        show("손님이 지목한 컷", named)
        print("\n■ 지목한 컷 판정")
        for r in named:
            rank = ranked.index(r) + 1
            print(f"    {r['id']} — {len(rows)}컷 중 {rank}번째로 많이 벗어남"
                  f" · 가장 벗어난 항목: {r['가장튄것']}")
            for k in KEYS:
                z = r.get(f"z_{k}")
                if z is None or abs(z) < 0.8:
                    continue
                d = "높다" if z > 0 else "낮다"
                print(f"        {k} {r[k]:7.1f}{UNIT[k]} — 보통보다 {abs(z):.1f}배 {d}")
            if r["점수"] < 1.0:
                print("        → 숫자로는 다른 컷과 크게 다르지 않다."
                      " 원인이 이 다섯 가지 밖에 있다는 뜻이다.")
    else:
        print(f"\n⚠️ 지목한 컷({', '.join(sorted(pin))})을 찾지 못했다 — 이름을 확인하십시오.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
