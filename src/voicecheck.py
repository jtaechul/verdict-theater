#!/usr/bin/env python3
"""만들어 둔 음성이 **얼마나 흔들리는지 숫자로 잰다.** 값은 들지 않는다.

    python3 src/voicecheck.py data/scripts/EP001.json --voice build/voice

왜 필요한가
    "해설 목소리가 중간중간 바뀐다" 는 말은 맞는데, **무엇이** 바뀌는지 모르면
    고칠 수가 없다. 실제로 기록을 열어 보니 모델은 한 번도 안 바뀌었고
    높이도 반음 안에 들어 있었다. 그러면 남은 것은 **크기(볼륨)와 말하는 속도**다.
    짐작으로 고치면 또 헛돈이 나가므로, 먼저 잰다.

무엇을 재나 (컷마다)
    · 크기   — 평균 음량(dB). 컷마다 들쭉날쭉하면 '가까웠다 멀어졌다' 하게 들린다
    · 높이   — 목소리 기본 주파수(Hz). 낮을수록 굵다
    · 속도   — 글자 수 ÷ 길이(초). 빨랐다 느렸다 하면 딴사람처럼 들린다

무엇을 보여주나
    인물마다 **가운뎃값과 퍼짐(폭)** 을 내고, 가장 튀는 컷 5개를 짚어 준다.
    폭이 좁으면 문제없는 것이고, 넓으면 그것이 흔들림의 정체다.

한 번도 API 를 부르지 않는다 — 이미 만들어 둔 파일만 읽는다.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tts import measure_f0  # noqa: E402

# 이 정도를 넘으면 사람 귀에 '딴 사람' 으로 들리기 시작한다 (판단 기준)
LOUD_SPREAD_OK = 3.0        # dB. 위아래 10% 를 뺀 폭
RATE_SPREAD_OK = 0.25       # 가운뎃값 대비 비율
PITCH_SPREAD_OK = 1.0       # 반음


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def loudness(path):
    """평균 음량(dB). ffmpeg 의 volumedetect 가 알려준다."""
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(path),
                        "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    for ln in r.stderr.splitlines():
        if "mean_volume:" in ln:
            try:
                return float(ln.split("mean_volume:")[1].split("dB")[0].strip())
            except ValueError:
                return None
    return None


def spread(vals):
    """위아래 10% 를 뺀 폭. 한두 개 튀는 값에 휘둘리지 않는다."""
    if len(vals) < 5:
        return 0.0
    s = sorted(vals)
    return s[int(len(s) * 0.9)] - s[int(len(s) * 0.1)]


def mid(vals):
    return sorted(vals)[len(vals) // 2] if vals else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--voice", default="build/voice")
    ap.add_argument("--who", default="", help="이 인물만 (예: narrator)")
    a = ap.parse_args()

    doc = json.loads(Path(a.script).read_text(encoding="utf-8"))
    vdir = Path(a.voice)
    if not vdir.exists():
        print(f"❌ 음성 폴더가 없다: {vdir}")
        return 2

    rows = {}
    miss = 0
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
            d = duration(p)
            if d <= 0.2:
                continue
            rows.setdefault(sp, []).append({
                "id": c["id"], "db": loudness(p), "hz": measure_f0(p),
                "rate": len(text) / d, "sec": d,
            })

    if not rows:
        print("❌ 잴 음성이 하나도 없다.")
        return 2

    print(f"음성 점검 — {Path(a.script).stem}   (건너뛴 컷 {miss}개)\n")
    verdict, unmeasured = [], False
    for sp, items in sorted(rows.items(), key=lambda kv: -len(kv[1])):
        db = [r["db"] for r in items if r["db"] is not None]
        hz = [r["hz"] for r in items if r["hz"]]
        rt = [r["rate"] for r in items]
        ds, rs = spread(db), spread(rt)
        rrel = rs / mid(rt) if mid(rt) else 0
        hs = 0.0
        if len(hz) >= 5:
            import math
            lo, hi = sorted(hz)[int(len(hz) * 0.1)], sorted(hz)[int(len(hz) * 0.9)]
            hs = 12 * math.log2(hi / lo) if lo > 0 else 0.0

        name = "해설" if sp == "narrator" else sp
        print(f"■ {name}  {len(items)}컷")
        print(f"    크기  가운데 {mid(db):6.1f}dB   폭 {ds:4.1f}dB"
              f"   {'괜찮음' if ds <= LOUD_SPREAD_OK else '★ 넓다 — 가까웠다 멀어졌다 들린다'}")
        # ⚠️ 못 잰 것을 '괜찮음' 으로 찍으면 안 된다. 안 재고 통과시킨 것을
        #    괜찮다고 읽어 버리면, 진짜 원인을 엉뚱한 데서 찾게 된다.
        if len(hz) >= 5:
            print(f"    높이  가운데 {mid(hz):6.0f}Hz   폭 {hs:4.1f}반음"
                  f"   {'괜찮음' if hs <= PITCH_SPREAD_OK else '★ 넓다'}")
        else:
            print(f"    높이  ⚠️ 재지 못함 ({len(hz)}/{len(items)}컷만 측정됨)"
                  " — numpy 가 없거나 소리가 너무 짧습니다")
        print(f"    속도  가운데 {mid(rt):6.1f}자/초 폭 {rs:4.1f}자/초({rrel * 100:.0f}%)"
              f" {'괜찮음' if rrel <= RATE_SPREAD_OK else '★ 넓다 — 빨랐다 느렸다 들린다'}")

        # 가장 튀는 컷 — 가운뎃값에서 얼마나 벗어났는지로 줄 세운다
        mdb, mrt = mid(db), mid(rt)
        worst = sorted(items, key=lambda r: -(abs((r["db"] or mdb) - mdb) / max(1e-6, ds or 1)
                                              + abs(r["rate"] - mrt) / max(1e-6, rs or 1)))[:5]
        print("    가장 튀는 컷:")
        for r in worst:
            print(f"      {r['id']:8s} {r['db'] or 0:6.1f}dB "
                  f"{r['hz'] or 0:5.0f}Hz {r['rate']:4.1f}자/초 ({r['sec']:.1f}초)")
        print()
        if sp == "narrator":
            verdict = [("크기", ds > LOUD_SPREAD_OK),
                       ("높이", len(hz) >= 5 and hs > PITCH_SPREAD_OK),
                       ("속도", rrel > RATE_SPREAD_OK)]
            unmeasured = len(hz) < 5

    if verdict:
        bad = [n for n, b in verdict if b]
        print("── 해설 판정 ──")
        if bad:
            print(f"  흔들리는 것: {' · '.join(bad)}")
            print("  → 이것들은 **이미 만들어 둔 음성에 대고 고칠 수 있다**(ffmpeg, 0원).")
            print("     다시 만들 필요가 없다.")
        elif unmeasured:
            print("  크기·속도는 좁은데 **높이를 재지 못했다.**")
            print("  → 높이를 못 잰 채로 '괜찮다' 고 판단하면 안 된다. 위의 경고를 보고")
            print("     numpy 설치를 확인한 뒤 다시 재십시오.")
        else:
            print("  세 가지 다 좁다 — 숫자로는 흔들림이 안 보인다.")
            print("  → 그렇다면 원인은 말투·억양이라 다시 만들어야 바뀐다(값이 든다).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
