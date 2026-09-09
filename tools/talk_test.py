#!/usr/bin/env python3
"""⭐ **대사 컷 하나를 시험 삼아 영상으로 사 본다.** (약 470~706원)

    python3 tools/talk_test.py S91            # 알아서 가장 알맞은 컷 하나
    python3 tools/talk_test.py S91 --cut 21   # 컷을 골라서
    python3 tools/talk_test.py S91 --dry      # 값 0원 — 무엇을 살지만 본다

⭐⭐⭐ 2026-09-08 손님: "나레이션은 이미지로, 대사는 영상으로 바꾸자."
   그 설계의 **0번 관문**이다. 한 사건 전부(5~7컷 · 3,500~4,900원)를 사기
   전에, **한 컷만 사서 눈과 귀로 본다.**

   왜 이 순서인가 — 구글 공식 문서가 Veo 의 대사·립싱크를 "영어는 완전 지원,
   다른 언어는 평가하지 않았다"고 못박아 두었다. 이 채널이 지금까지 산 영상은
   **전부 입을 다물게** 만든 것이라(short90.OPEN_LIPS), 한국어로 말하는
   영상은 한 번도 만들어 본 적이 없다. 되는지 모르는 채로 4,900원을 지르면
   안 된다.

   보실 것 세 가지
     ① 한국어 발음이 알아들을 만한가 (뭉개지지 않는가)
     ② 입 모양이 말과 맞는가
     ③ 화면에 글자(자막)가 박혀 나오지 않는가
        — 우리는 자막을 직접 얹으므로, 영상에 글자가 박히면 그 컷은 못 쓴다

⚠️ 값이 나간다. 그래서 **단추로만 돈다**(.github/workflows/talk-test.yml).
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import cost                                                  # noqa: E402
import short90 as S9                                         # noqa: E402
import veo                                                   # noqa: E402

# ⚠️ Veo 는 4·6·8초만 받는다 — 5초는 HTTP 400 이다.
#    4초면 720p, 6초면 1080p 로 간다(veo.res_for).
#    ⚠️⚠️ 싸다고 4초를 사면 안 된다. 대사가 4초보다 길면 말이 잘리거나
#       배우가 빨리 말해 버려, **되는지 안 되는지를 판정할 수 없는 시험**이
#       된다. 실제로 만들 때 고를 길이 그대로 산다(vprompt.seconds_for).
OK_SEC = (4, 6, 8)
# 안전필터가 자주 막는 낱말 — 시험용으로는 이런 대사를 안 고른다
HOT = ("관계", "잤", "몸", "성관계", "강간", "죽", "때렸")


def talk_cuts(doc):
    """대사 컷들 — **시험에 좋은 순서**로 돌려준다.

    좋은 시험 컷의 조건:
      · 말차례가 한 줄이다 (두 사람이 주고받으면 목소리가 둘이라 판정이 흐려진다)
      · 화면에 사람이 한 명이다 (누구 입을 볼지가 분명하다)
      · 안전필터에 걸릴 낱말이 없다
      · 대사가 짧다 (4초 안에 들어간다)
    """
    out = []
    for c in doc["cuts"]:
        if S9.is_narr(c) or len(c.get("turns") or []) != 1:
            continue
        text = c["turns"][0][1]
        if any(w in text for w in HOT):
            continue
        out.append(c)
    return sorted(out, key=lambda c: (len(c.get("who") or []),
                                      len(S9.turns_of(c)[0][1])))


def fit_sec(prompt, sec):
    """지문에 적힌 길이를 **우리가 사는 길이**로 바꾼다.

    ⚠️ 2026-09-05 에 이걸 안 해서, 6초용으로 짜라고 시켜 놓고 4초를 샀다.
       6초 움직임을 4초로 잘라 내니 앞머리가 정지 화면처럼 열렸다."""
    return re.sub(r"\b\d+(?:\.\d+)?-second single continuous take",
                  f"{int(sec)}-second single continuous take", prompt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sid")
    ap.add_argument("--cut", type=int, default=0, help="컷 번호 (비우면 알아서)")
    ap.add_argument("--sec", type=int, default=0, choices=(0, 4, 6, 8),
                    help="살 길이(초). 비우면 대사 길이에 맞춰 고른다")
    ap.add_argument("--dry", action="store_true", help="값 0원 — 무엇을 살지만 본다")
    a = ap.parse_args()

    sid = a.sid.strip().upper()
    f = ROOT / "data" / "series" / f"{sid}.json"
    if not f.exists():
        print(f"❌ 대본이 없습니다: data/series/{sid}.json")
        return 2
    doc = json.loads(f.read_text(encoding="utf-8"))

    cands = talk_cuts(doc)
    if not cands:
        print("❌ 시험할 만한 대사 컷이 없습니다 "
              "(말차례 한 줄 · 안전한 낱말 조건을 만족하는 컷이 없다)")
        return 2
    c = ([x for x in doc["cuts"] if x["n"] == a.cut] or [None])[0] if a.cut \
        else cands[0]
    if c is None:
        print(f"❌ 컷{a.cut} 이 없습니다")
        return 2
    if S9.is_narr(c):
        print(f"❌ 컷{c['n']} 은 나레이션 컷입니다 — 대사 컷을 고르십시오.\n"
              f"   고를 만한 컷: {[x['n'] for x in cands]}")
        return 2

    who, text = S9.turns_of(c)[0]
    # ⭐ 실제로 만들 때와 **같은 길이**를 산다 (짧게 사면 말이 잘려 판정 불가)
    sec = a.sec
    if not sec:
        import vprompt                                       # noqa: E402
        want = vprompt.seconds_for(text)
        sec = next((x for x in OK_SEC if x >= want), OK_SEC[-1])
    prompt = fit_sec(c.get("veo") or c.get("still") or "", sec)
    krw = cost.video_krw(veo.MODEL, sec)

    print(f"■ 시험 구매 — {sid} 컷{c['n']} [{who}]")
    print(f"   대사   \"{text}\"")
    print(f"   화면에 있는 사람  {', '.join(c.get('who') or []) or '(없음)'}")
    print(f"   {sec}초 · {veo.res_for(sec)} · 9:16 · 약 {krw:,.0f}원 "
          f"(대사 길이에 맞춰 고른 값)")
    print(f"   (고를 만한 컷: {[x['n'] for x in cands]})")
    if a.dry:
        print("\n(연습이라 실제로는 안 삽니다 · 0원)")
        return 0

    still = S9.OUT / "stills" / f"c{c['n']:02d}.png"
    if not still.exists():
        print(f"\n❌ 그 컷 그림이 없습니다: {still}\n"
              f"   먼저 [쇼츠 만들기] 로 그림을 만들어 두어야 합니다 "
              f"(그림을 첫 장면으로 넣어야 얼굴이 안 바뀝니다).")
        return 2

    out = S9.OUT / "talk_test" / f"{sid}_c{c['n']:02d}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        veo.make_clip(prompt, sec, out, ratio=S9.OPEN_RATIO,
                      seed=veo._seed(sid, c["n"], "talk"), start=still)
    except veo.RaiFiltered:
        print("\n⚠️ 구글 안전필터가 막았습니다 (돈은 안 나갔습니다).\n"
              "   다른 컷으로 다시 해 보십시오 — 대사에 든 낱말 때문입니다.")
        return 1
    print(f"\n✅ 만들었습니다 — {out.name} "
          f"({out.stat().st_size / 1e6:.1f}MB)")
    print("\n■ 보실 것 세 가지")
    print("   ① 한국어 발음이 알아들을 만한가")
    print("   ② 입 모양이 말과 맞는가")
    print("   ③ 화면에 글자(자막)가 박혀 있지 않은가")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
