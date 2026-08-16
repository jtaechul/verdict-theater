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

무엇을 재나
    인물마다 컷의 **목소리 높이(Hz)** 를 재서 가운뎃값에서 몇 반음 벗어났는지 본다.
    12반음이 한 옥타브다.

⭐ 2026-08-08 — **통(take) 단위로 판정한다.**
    해설은 여러 줄을 '한 통'(호출 1번)으로 만들어 자른다. **한 통 안은 같은
    목소리라는 것을 만든 방식이 보장한다.** tts.py 가 남기는 이름표(groups.json)를 읽어
      · **통끼리** 가운뎃값 차이가 크면 → 중단 (진짜 다른 사람처럼 들린다)
      · 통 **안**에서 튀는 컷 → 경고만 (같은 통 = 같은 사람. 억양이다)
      · 이름표가 없는 컷(따로 만든 컷) → 예전처럼 컷 단위로 엄격히
    중단은 여전히 **해설에만** 건다. 등장인물 대사의 높낮이는 연기라 경고만 한다.

⭐⭐ 2026-08-15 — **잣대를 tts.py 와 하나로 합쳤다.** (네 번째 실패의 뿌리)
    맞추는 쪽(tts)은 "폭 4.1반음, 통과" 라 하고 이 검사기는 "5.0반음, 불합격" 이라
    했다 — 서로 딴 계산법이었기 때문이다. 이제 통 폭 계산(narrator_take_stats)과
    문턱 값(VOICE_*)을 **tts.py 에서 가져다 쓴다.** tts 의 마무리(settle)가 닫으면
    여기는 반드시 통과한다. 여기서 막혔다면 마무리가 못 돈 것이니
    실행 기록에서 '해설 통 높이 마무리' 줄을 찾아보면 된다.

    같은 날 함께 고친 것: **쇼츠 대본을 실제로 검사한다.** 예전에는 --shorts 를
    받아도 쇼츠 파일에 acts 칸이 없어 **한 컷도 안 재고 통과**시키고 있었다.
    본편과 쇼츠는 **따로** 판정한다 — 각각 다른 영상이라 서로 섞어 재면
    영상 하나 안에서는 멀쩡한데도 막는 억울한 중단이 생긴다.
"""

import argparse
import json
import math
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("GEMINI_API_KEY", "")     # 재기만 한다 — 모델은 안 부른다
from tts import (measure_f0, narrator_take_stats,               # noqa: E402
                 VOICE_WARN as WARN, VOICE_STOP as STOP,
                 VOICE_SPREAD as SPREAD_STOP, VOICE_MIN_CUTS as MIN_CUTS)


def semitone(hz, mid):
    return 12.0 * math.log2(hz / mid) if hz > 0 and mid > 0 else 0.0


def narrator_by_takes(items, gmap, warns, stops):
    """해설을 통 단위로 판정한다. 표에 찍을 (가운뎃값, 폭, 통 설명줄들)을 돌려준다.

    items = [(cid, hz)] · gmap = {cid: 통 이름표}
    ⚠️ 폭 계산은 tts.narrator_take_stats — 맞추는 쪽과 **같은 함수**다."""
    mid, takes, meds, solo, spread = narrator_take_stats(items, gmap)
    lines = []

    # ① 통끼리 — 가운뎃값의 폭이 크면 진짜 다른 사람처럼 들린다 → 중단
    if len(meds) >= 2:
        for sig, got in sorted(takes.items(), key=lambda kv: kv[1][0][0]):
            off = semitone(meds[sig], mid)
            lines.append(f"      통 {got[0][0]}~{got[-1][0]} ({len(got)}컷)"
                         f" {meds[sig]:.0f}Hz({off:+.1f}반음)")
        if spread > SPREAD_STOP:
            stops.append(f"해설 통끼리 폭 {spread:.1f}반음 — 통이 서로 다른 사람처럼 들린다")

    # ② 통 안에서 튀는 컷 — 같은 통 = 같은 사람. 억양이므로 경고만.
    for sig, got in takes.items():
        for cid, hz in got:
            gap = semitone(hz, meds[sig])
            if abs(gap) > WARN:
                warns.append(f"해설 {cid} — 제 통 안에서 {gap:+.1f}반음"
                             " (같은 통이라 같은 사람 — 억양으로 보임)")

    # ③ 이름표 없는 컷(따로 만든 컷)은 저마다 딴 호출이다 → 예전처럼 엄격히
    for cid, hz in solo:
        gap = abs(semitone(hz, mid))
        if gap > STOP:
            stops.append(f"해설 {cid} — {hz:.0f}Hz ({semitone(hz, mid):+.1f}반음, 따로 만든 컷)")
        elif gap > WARN:
            warns.append(f"해설 {cid} — {hz:.0f}Hz ({semitone(hz, mid):+.1f}반음)")

    return mid, spread, lines


def doc_cuts(doc):
    """본편({acts:[{cuts}]})과 쇼츠({shorts:[{cuts}]}) 모두에서 컷을 꺼낸다.

    ⚠️ 2026-08-15 — 예전에는 acts 만 봤다. 쇼츠 파일에는 acts 가 없어서
       --shorts 검사가 **아무것도 안 재고 조용히 통과**하고 있었다."""
    if doc.get("acts"):
        return [c for a in doc["acts"] for c in (a.get("cuts") or [])]
    return [c for s_ in doc.get("shorts", []) for c in (s_.get("cuts") or [])]


def judge_doc(label, cuts, vdir, gmap, warns, stops):
    """대본 하나(본편 또는 쇼츠)를 판정해 표를 찍는다. 잰 컷 수를 돌려준다."""
    by = {}
    seen = set()
    for c in cuts:
        cid = c.get("id")
        if not cid or cid in seen or not (c.get("text") or "").strip():
            continue
        p = vdir / f"{cid}.mp3"
        if not p.exists() or p.with_suffix(".silent").exists():
            continue
        seen.add(cid)
        hz = measure_f0(p)
        if hz:
            by.setdefault(c.get("speaker", "narrator"), []).append((cid, hz))

    if not by:
        print(f"  [{label}] 잰 컷이 없다 — 음성이 아직 없는 대본이다")
        return 0

    print(f"  [{label}]")
    print(f"    {'인물':10s}{'컷':>4s}{'가운뎃값':>10s}{'폭':>8s}   가장 벗어난 컷")
    print("    " + "-" * 62)

    for sp in sorted(by):
        items = by[sp]
        name = "해설" if sp == "narrator" else sp
        if len(items) < MIN_CUTS:
            print(f"    {name:10s}{len(items):4d}   (컷이 적어 건너뜀)")
            continue

        if sp == "narrator" and any(c in gmap for c, _ in items):
            # ⭐ 통 단위 판정 (위 설명 참조)
            mid, spread, take_lines = narrator_by_takes(items, gmap, warns, stops)
            offs = sorted(((abs(semitone(h, mid)), cid, h) for cid, h in items),
                          reverse=True)
            worst = offs[0]
            mark = "  ← 중단" if spread > SPREAD_STOP else \
                   ("  ← 경고" if worst[0] > WARN else "")
            print(f"    {name:10s}{len(items):4d}{mid:10.1f}Hz{spread:7.1f}반음"
                  f"   {worst[1]} {worst[2]:.0f}Hz({semitone(worst[2], mid):+.1f}반음){mark}")
            for ln in take_lines:
                print(ln)
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
    return len(seen)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--voice", default="build/voice")
    ap.add_argument("--shorts", action="store_true", help="쇼츠 대본도 함께 본다")
    a = ap.parse_args()

    # (이름, 대본) — 본편과 쇼츠는 각각 딴 영상이므로 **따로** 판정한다.
    docs = [("본편", json.loads(Path(a.script).read_text(encoding="utf-8")))]
    if a.shorts:
        sp = Path(a.script).with_suffix(".shorts.json")
        if sp.exists():
            docs.append(("쇼츠", json.loads(sp.read_text(encoding="utf-8"))))

    vdir = Path(a.voice)
    if not vdir.is_dir():
        print(f"❌ 음성 폴더가 없다: {vdir}")
        return 2

    try:
        gmap = json.loads((vdir / "groups.json").read_text(encoding="utf-8"))
    except Exception:
        gmap = {}

    print(f"목소리 한결같음 검사 — {Path(a.script).stem}\n")
    warns, stops = [], []
    measured = 0
    for label, doc in docs:
        measured += judge_doc(label, doc_cuts(doc), vdir, gmap, warns, stops)
        print()

    if not measured:
        # ⚠️ 조용히 통과시키면 안 된다. '검사했는데 괜찮음' 과
        #    '검사를 아예 못 함' 은 완전히 다른 말이다.
        print("⚠️ 잰 컷이 하나도 없다 — 검사를 못 했다 (numpy 가 없거나 음성이 없다)")
        return 3

    if stops:
        print(f"❌ 목소리가 흩어졌습니다 ({len(stops)}건). 이대로 영상을 만들면 안 됩니다.")
        for s in stops[:12]:
            print(f"    {s}")
        if len(stops) > 12:
            print(f"    … 그 밖에 {len(stops) - 12}건")
        print("\n   이 멈춤은 정상이라면 안 나옵니다 — 음성 만들기 끝의 '해설 통 높이"
              "\n   마무리' 가 같은 잣대로 미리 닫기 때문입니다. 실행 기록(음성 단계)에서"
              "\n   그 줄이 왜 못 닫았는지(ffmpeg 실패 등)를 보면 원인이 나옵니다.")
        return 1
    if warns:
        print(f"⚠️ 살펴볼 컷이 {len(warns)}개 있습니다 (영상은 만듭니다 —"
              " 같은 통 안의 높낮이와 등장인물 연기는 막지 않습니다).")
        for s in warns[:8]:
            print(f"    {s}")
        return 0
    print("✅ 인물마다 한 목소리입니다. 3반음 넘게 벗어난 컷이 없습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
