#!/usr/bin/env python3
"""⭐ 대사 목소리가 **너무 격하지 않은지** 본다. 값 0원 (모델을 안 부른다).

    python3 tools/calm_check.py

손님(2026-09-04): "다음번부턴 대사 목소리 감정이 너무 격하게 표현되지
않도록 코드에도 반영해줘."

기계 목소리는 "세게 읽어라" 하면 연기가 되는 게 아니라 **소리만 커진다.**
그러면 싸구려 더빙처럼 들린다. 한국 드라마의 싸움은 내지르지 않는다 —
낮게, 조용하게, 그래서 더 서늘하다.

막는 자리가 **세 겹**이라, 셋이 다 살아 있는지 본다.
  ① prompts/story90_gen.md  — 대본을 짓는 AI 에게 애초에 그렇게 시킨다
  ② src/story90.py          — 그래도 격한 말이 오면 조용한 말로 바꿔 끼운다
  ③ src/tts.py              — 지시가 아예 없을 때 쓰는 판도 눌러 담은 판이다
한 겹만 남아도 다시 격해지므로 셋을 한꺼번에 본다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import story90 as S9                                          # noqa: E402
import tts                                                    # noqa: E402

# 어디에도 있으면 안 되는 말 (연기 지시 안에서)
BANNED = r"목소리를 높|터져 나오|터뜨리|폭발하|소리치|내지르|악을 쓰|울부짖|절규|오열|비명|이를 악물|서슬 퍼렇|몰아붙이|쏘아붙이|다그치|날카롭게|앙칼|격앙|격정|격하게"

# soften() 이 반드시 눌러야 하는 보기 (되돌리면 여기서 걸린다)
CASES = [
    "50대 여성이, 믿기지 않아 목소리가 확 올라가며 분노가 터져 나오듯",
    "50대 남성이, 이를 악물고 화를 눌러 담아 낮지만 서슬 퍼렇게",
    "50대 여성이, 울음을 삼키느라 목이 메어 끝을 떨면서 힘겹게",
    "50대 여성이, 낮게 몰아붙이며 되묻듯 날카롭게",
    "50대 여성이, 악을 쓰듯 소리치며 격앙되어 세게",
    "30대 여성이, 감정이 터져 나오고 비명을 지르듯 울부짖으며",
    "20대 남성이, 내지르면서 강하게 다그치듯",
]
# 이런 것은 건드리면 안 된다 (멀쩡한 지시까지 뭉개면 안 된다)
KEEP = [
    "40대 남성이, 사무적으로 담담하게 숫자를 읽어 주듯",
    "30대 여성이, 옅게 웃음기를 섞어 조용하고 차갑게",
    "사건을 전하는 낮고 묵직한 목소리로, 쇼츠 속도에 맞춰 담담하고 또렷하게",
]

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def main():
    print("⭐ 대사 감정이 너무 격하지 않은가 (값 0원)\n")

    # ── ① 대본 짓는 AI 에게 시켰는가 ──────────────────────────
    print("① 대본을 짓는 자리 (prompts/story90_gen.md)")
    md = (ROOT / "prompts" / "story90_gen.md").read_text(encoding="utf-8")
    ck("감정을 속으로 눌러 담으라고 적혀 있다", "속으로 눌러 담는다" in md)
    ck("쓰지 말 말이 목록으로 적혀 있다",
       md.count("쓰지 않는 말") >= 1 and md.count("목소리를 높여") >= 1)
    ck("눌러 담은 보기가 들어 있다", "낮고 서늘하게" in md)
    # 격한 보기를 그대로 두면 AI 가 그것을 베낀다 (보기가 가장 센 신호다)
    exam = re.findall(r"`([^`]*(?:여성이|남성이)[^`]*)`", md)
    hotex = [e for e in exam if re.search(BANNED, e)]
    ck("보기에 격한 말이 남아 있지 않다", not hotex,
       "격한 보기: " + " · ".join(hotex[:2]))

    # ── ② 그래도 오면 바꿔 끼우는가 ───────────────────────────
    print("\n② 격한 말이 와도 눌러 주는가 (src/story90.py)")
    src = (ROOT / "src" / "story90.py").read_text(encoding="utf-8")
    ck("검사하기 전에 눌러 준다 (2,100원짜리 대본을 안 물린다)",
       re.search(r"cool_all\(doc\)[\s\S]{0,400}?bad = check\(doc\)", src) is not None)
    ck("눌렀는데도 남으면 규격 위반으로 잡는다", "too_hot(one)" in src)
    miss = []
    for t in CASES:
        new, hit = S9.soften(t)
        if not hit or S9.too_hot(new) or re.search(BANNED, new):
            miss.append(t[:34])
    ck(f"격한 보기 {len(CASES)}줄을 다 눌렀다", not miss,
       "못 누른 것: " + " · ".join(miss[:2]))
    hurt = [t for t in KEEP if S9.soften(t)[1]]
    ck("멀쩡한 지시는 안 건드린다", not hurt, "건드린 것: " + " · ".join(hurt[:2]))
    # 같은 말을 두 번 끼워 넣지 않는가
    dup = []
    for t in CASES:
        new, _ = S9.soften(t)
        for _, calm in S9.HOT:
            if new.count(calm) > 1:
                dup.append(new[:40])
    ck("같은 말을 두 번 끼워 넣지 않는다", not dup, " · ".join(dup[:1]))

    # ── ③ 지시가 없을 때 쓰는 판 (src/tts.py) ─────────────────
    print("\n③ 지시가 없을 때 쓰는 판 (src/tts.py)")
    ck(f"기본 결이 눌러 담은 결이다 ({tts.STYLE_DEFAULT})",
       tts.STYLE_DEFAULT != "fierce")
    st = tts.STYLES[tts.STYLE_DEFAULT]
    ck("기본 결이 세기를 얹지 않는다", not st.get("add"))
    ck("빠르기를 안 올린다 (조립에서 이미 1.2배로 당긴다)",
       abs(float(st.get("rate") or 1.0) - 1.0) < 0.001)
    hot = [h for _, h in (st.get("mood") or tts.MOOD) if re.search(BANNED, h)]
    ck("줄마다의 판에 격한 말이 없다", not hot, " · ".join(hot[:2]))
    ck("마지막 수단 지시도 감정을 부추기지 않는다",
       "감정을 실어" not in tts.soft("아무 말"))
    # ⚠️ 이 저장소의 오랜 규칙 — "하지 마" 로 적으면 모델이 부정을 흘려듣고
    #    오히려 그대로 한다. 연기 지시도 **바라는 것만** 적어야 한다.
    # ⚠️ **금지로 적은 것**만 잡는다. "믿기지 않는다는 듯" 처럼 감정을
    #    묘사하는 말은 금지가 아니다 (한 번 잘못 잡았다).
    NO = r"지\s*말(?:고|라|자)|지\s*않(?:고|게)|(?<![가-힣])말고(?![가-힣])"
    look = [h for _, h in (st.get("mood") or tts.MOOD)]
    look += [st.get("how") or "", st.get("mood_base") or "", tts.soft("가")]
    neg = [x for x in look if x and re.search(NO, x)]
    ck("지시를 '하지 마' 로 적지 않았다 (모델이 부정을 흘려듣는다)",
       not neg, " · ".join(neg[:2]))
    # 실제로 말을 넣어 지시를 뽑아 본다 (표만 보고 넘어가지 않는다)
    live = [tts.mood(t) for t in ("당장 나가!", "정말 몰랐다는 거야?",
                                  "어떻게 나한테 이럴 수 있어", "그 돈은 내 몫이었다")]
    ck("진짜 대사를 넣어도 격한 지시가 안 나온다",
       not any(re.search(BANNED, x) for x in live),
       " · ".join(x for x in live if re.search(BANNED, x))[:60])
    # 되돌릴 길이 남아 있는가 (손님이 "다시 세게" 하실 수 있어야 한다)
    ck("'격하게' 결은 지우지 않고 남겨 두었다 (되돌릴 수 있다)",
       "fierce" in tts.STYLES)

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 대사 감정: {len(bad)}군데 — 다시 격해질 수 있다")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 대사 감정: 세 겹이 다 살아 있다 (눌러 담은 톤)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
