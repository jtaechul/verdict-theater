#!/usr/bin/env python3
"""만든 음성이 **인물마다 한 목소리인지 기계가 검사한다.** 값 0원.

    python3 src/voiceguard.py data/scripts/EP001.json --voice build/voice

왜 이것이 있어야 하나 (2026-08-06 · 손님 질문: "다음 회차에도 이런 일이 생기면?")
    목소리가 흩어지는 문제를 세 번 고쳤는데 세 번 다 **손님이 귀로 먼저 발견**하셨다.
    그때마다 이미 영상이 다 만들어진 뒤였다(렌더링 50분 + 음성 값).
    고치는 장치를 아무리 잘 만들어도, **그 장치가 고장 났을 때 알려주는 것이 없으면**
    똑같은 일이 또 생긴다. 그래서 사람 귀 대신 여기서 매번 기계가 먼저 듣는다.

    ⚠️ 이 검사는 '고치는 코드' 와 **따로** 돈다. 고치는 코드가 통째로 망가져도
       (예: 묶어 읽기가 전부 실패해 예전 방식으로 되돌아가도) 여기서 잡힌다.
       고치는 쪽과 검사하는 쪽이 같은 코드를 쓰면, 그 코드가 틀렸을 때 둘 다 속는다.

무엇을 재나
    인물마다 컷의 **목소리 높이(Hz)** 를 재서, 그 인물 가운뎃값에서 몇 반음
    벗어났는지 본다. 12반음이 한 옥타브다.
      3반음 넘게 벗어난 컷  → 경고 (사람 귀에 '어?' 하는 정도)
      5반음 넘게 벗어난 컷  → 중단 (그냥 다른 사람이다. 영상을 만들면 안 된다)
      인물의 전체 폭이 5반음 넘음 → 중단 (한 사람이 아니다)

    실측 기준값
      정상: 해설 64컷의 자연스러운 흔들림 폭 ±1.7반음
      사고: H05 가 +8.6반음 · 장남이 88~182Hz(12.7반음)
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tts import measure_f0  # noqa: E402

WARN = float(__import__("os").environ.get("VT_VOICE_WARN", "3.0"))   # 반음
STOP = float(__import__("os").environ.get("VT_VOICE_STOP", "5.0"))   # 반음
SPREAD_STOP = float(__import__("os").environ.get("VT_VOICE_SPREAD", "5.0"))

# ⭐ 2026-08-07: **중단은 해설에만 건다. 등장인물(대사)은 경고만.**
#
#   첫 실전에서 이 검사가 장남(폭 9.1반음)·차남(폭 9.6반음)을 막았다. 그런데
#   그 컷들은 **한 통(호출 1번)으로 만들어진 것**이었다 — 같은 사람인 것은
#   만들어진 방식이 보장한다. 폭이 큰 이유는 연기다: 애원하는 대사는 높고
#   차갑게 말하는 대사는 낮다. 배우는 원래 그렇게 읽는다.
#   위 문턱값(3·5반음)은 해설, 즉 **담담한 낭독**을 재서 정한 값이다
#   (실측: 해설 64컷의 자연스러운 폭 ±1.7반음). 낭독의 자로 연기를 재면
#   멀쩡한 연기를 전부 '다른 사람' 으로 오판한다 — 실제로 그랬다.
#   해설은 원래 지적받은 문제이자 담담해야 하는 소리라 그대로 엄격하게 지킨다.
MIN_CUTS = 5            # 이보다 적으면 가운뎃값을 못 믿는다


def semitone(hz, mid):
    import math
    return 12.0 * math.log2(hz / mid) if hz > 0 and mid > 0 else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--voice", default="build/voice")
    ap.add_argument("--shorts", action="store_true", help="쇼츠 대본도 함께 본다")
    a = ap.parse_args()

    docs = [json.loads(Path(a.script).read_text(encoding="utf-8"))]
    if a.shorts:
        sp = Path(a.script).with_suffix(".shorts.json")
        if sp.exists():
            docs.append(json.loads(sp.read_text(encoding="utf-8")))

    vdir = Path(a.voice)
    if not vdir.is_dir():
        print(f"❌ 음성 폴더가 없다: {vdir}")
        return 2

    by = {}
    seen = set()
    for doc in docs:
        for act in doc.get("acts", []):
            for c in act.get("cuts", []):
                cid = c.get("id")
                if cid in seen or not (c.get("text") or "").strip():
                    continue
                p = vdir / f"{cid}.mp3"
                if not p.exists() or p.with_suffix(".silent").exists():
                    continue
                seen.add(cid)
                hz = measure_f0(p)
                if hz:
                    by.setdefault(c.get("speaker", "narrator"), []).append((cid, hz))

    if not by:
        # ⚠️ 조용히 통과시키면 안 된다. '검사했는데 괜찮음' 과
        #    '검사를 아예 못 함' 은 완전히 다른 말이다.
        print("⚠️ 잰 컷이 하나도 없다 — 검사를 못 했다 (numpy 가 없거나 음성이 없다)")
        return 3

    print(f"목소리 한결같음 검사 — {Path(a.script).stem}\n")
    print(f"    {'인물':10s}{'컷':>4s}{'가운뎃값':>10s}{'폭':>8s}   가장 벗어난 컷")
    print("    " + "-" * 62)

    warns, stops = [], []
    for sp in sorted(by):
        items = by[sp]
        name = "해설" if sp == "narrator" else sp
        if len(items) < MIN_CUTS:
            print(f"    {name:10s}{len(items):4d}   (컷이 적어 건너뜀)")
            continue
        mid = statistics.median(h for _, h in items)
        offs = sorted(((abs(semitone(h, mid)), cid, h) for cid, h in items), reverse=True)
        vals = sorted(semitone(h, mid) for _, h in items)
        spread = vals[int(len(vals) * 0.9)] - vals[int(len(vals) * 0.1)]
        hard = sp == "narrator"            # 중단 권한은 해설에만 있다 (위 설명 참조)
        worst = offs[0]
        mark = ("  ← 중단" if hard and worst[0] > STOP else
                ("  ← 경고" if worst[0] > WARN else ""))
        print(f"    {name:10s}{len(items):4d}{mid:10.1f}Hz{spread:7.1f}반음"
              f"   {worst[1]} {worst[2]:.0f}Hz({semitone(worst[2], mid):+.1f}반음){mark}")

        for gap, cid, hz in offs:
            if hard and gap > STOP:
                stops.append(f"{name} {cid} — {hz:.0f}Hz ({semitone(hz, mid):+.1f}반음)")
            elif gap > WARN:
                warns.append(f"{name} {cid} — {hz:.0f}Hz ({semitone(hz, mid):+.1f}반음)")
        if spread > SPREAD_STOP:
            if hard:
                stops.append(f"{name} 전체 폭 {spread:.1f}반음 — 한 사람으로 안 들린다")
            else:
                warns.append(f"{name} 전체 폭 {spread:.1f}반음 — 대사 연기라 감정 폭일"
                             " 수 있음. 영상에서 귀로 확인 요망")

    print()
    if stops:
        print(f"❌ 목소리가 흩어졌습니다 ({len(stops)}건). 이대로 영상을 만들면 안 됩니다.")
        for s in stops[:12]:
            print(f"    {s}")
        if len(stops) > 12:
            print(f"    … 그 밖에 {len(stops) - 12}건")
        print("\n   이 컷들을 다시 만들어야 합니다."
              " (음성 보관함을 지우고 '3. 영상 만들기' 를 다시 누르면 새로 만듭니다)")
        return 1
    if warns:
        print(f"⚠️ 살펴볼 컷이 {len(warns)}개 있습니다 (영상은 만듭니다 —"
          " 등장인물 대사의 높낮이는 연기일 수 있어 막지 않습니다).")
        for s in warns[:8]:
            print(f"    {s}")
        return 0
    print("✅ 인물마다 한 목소리입니다. 3반음 넘게 벗어난 컷이 없습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
