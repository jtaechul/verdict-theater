#!/usr/bin/env python3
"""도입 훅(앞 22초)이 **알아들을 수 있는 말인지** 잰다. 인터넷 0회 · 0원.

    python3 tools/hook_test.py            # 저장된 대본 전부
    python3 tools/hook_test.py EP002      # 한 편만

왜 이 검사가 있는가 (2026-08-14)
    운영자: "이번 오프닝 훅 부분은 대사가 지금 전혀 무슨 내용인지 파악도 안 되고
             그래 좀 문제가 많아."
    EP002 훅이 실제로 이랬다.

        H01 "저한테 다 맡기고 가셨어요."            ← 저가 누구? 누가 갔나?
        H02 "이십 년을 혼인신고한 아내가, 그 자리에"  ← 그 자리가 어디?
        H03 "조문객들은 선희 씨를 비켜 지나갔습니다"  ← 선희가 누구?
        H04 "오늘은 그냥 돌아가세요."               ← 누가 누구에게?
        H05 "그 사람은 … 그런데 왜, 저 사람이"      ← 둘이 같은 사람인가?

    **가리키는 말만 있고 가리키는 대상이 없었다.** 보는 사람은 50~60대이고
    휴대전화로 한 번 본다. 되감아 보지 않는다.

    ⭐ 핵심규칙(CLAUDE.md): 프롬프트에 규칙을 적었으면 **지켜졌는지 재는 코드도
       같이 만든다.** 못 재는 규칙은 규칙이 아니라 희망이다.
       그래서 훅 프롬프트에 규칙을 적으면서 이 자를 같이 만든다.

무엇을 재나 (사람 눈이 아니라 글자를 센다)
    ① 가리키는 말   그 사람 · 저 사람 · 그 자리 · 저기 · 거기 …
                    훅에서는 가리킬 대상이 아직 소개된 적이 없으므로 쓰면 안 된다.
    ② 소개 없는 이름 사람 이름이 나오는데 그 앞에 **관계말**(아내·남편·아들 …)이
                    한 번도 안 나왔으면, 보는 사람은 그가 누구인지 모른다.
    ③ 무엇을 다투나 훅 다섯 컷 안에 다툼거리를 가리키는 말이 하나도 없으면
                    "그래서 뭘 보라는 거냐" 가 된다.
    ④ 길이         훅 전체가 설계한 22초 안에 들어오는가.
                    ⚠️ '한 컷에 몇 자까지' 는 재지 않는다. 컷은 음성 길이에 맞춰
                       늘어나므로(render.cut_durations) 말이 잘리지 않기 때문이다.
                       그걸 모르고 넣었다가 멀쩡한 EP001 훅을 다 떨어뜨릴 뻔했다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "data" / "scripts"

# ① 훅에서 쓰면 안 되는 '가리키는 말'
POINTERS = ["그 사람", "저 사람", "그 자리", "그 분", "저 분", "그분", "저분",
            "저기", "거기", "그때 그", "그 일", "그 여자", "그 남자"]

# ② 사람을 알아보게 해 주는 '관계말'
RELATIONS = ["아내", "남편", "아들", "딸", "어머니", "아버지", "엄마", "아빠",
             "형", "누나", "동생", "며느리", "사위", "장남", "차남", "막내",
             "부인", "재혼", "전처", "유족", "상속인", "형제", "자매", "조카",
             "이모", "고모", "삼촌", "할머니", "할아버지", "사장", "직원", "동료"]

# ③ 다툼거리를 가리키는 말
CONFLICT = ["유류분", "상속", "유언", "재산", "집", "땅", "가게", "돈", "빚",
            "소송", "재판", "법원", "판결", "계약", "명의", "이름", "몫", "지분",
            "위자료", "합의", "고소", "청구"]

HOOK_WINDOW = 22.0   # 도입 훅에 주어진 시간(초) — script.py 의 ACTS 표와 같다

ok = True


def bad(m):
    global ok
    print(f"   ❌ {m}")
    ok = False


def warn(m):
    print(f"   ⚠️ {m}")


def check(path):
    global ok
    doc = json.loads(path.read_text(encoding="utf-8"))
    hook = next((a for a in (doc.get("acts") or []) if a.get("id") == "hook"), None)
    if not hook or not hook.get("cuts"):
        print(f"\n{path.stem}: 도입 훅이 없다 — 건너뛴다")
        return
    cuts = hook["cuts"]
    texts = [(c.get("id", "?"), (c.get("text") or "").strip(), float(c.get("sec") or 0))
             for c in cuts]
    joined = " ".join(t for _i, t, _s in texts)

    print(f"\n── {path.stem} 도입 훅 ({len(cuts)}컷) ──")
    for cid, t, sec in texts:
        print(f"   [{cid}] {sec:.1f}초  {t}")
    print()

    # ① 가리키는 말
    found = [(cid, w) for cid, t, _s in texts for w in POINTERS if w in t]
    if found:
        for cid, w in found[:6]:
            bad(f"[{cid}] '{w}' — 가리키는 말인데 훅에서는 그게 누구/어디인지 "
                "아직 아무도 모른다. 정체를 그대로 적어라")
    else:
        print("   ✅ 가리키는 말(그 사람·저 자리 …)이 없다")

    # ② 소개 없는 이름
    #    '선희 씨' 처럼 [이름]+씨 꼴을 찾는다. 그 앞에 관계말이 한 번도 안 나왔으면 문제다.
    rel_at = min([joined.find(r) for r in RELATIONS if r in joined] or [10 ** 9])
    names = [(m.start(), m.group(1)) for m in re.finditer(r"([가-힣]{2,3})\s*씨", joined)]
    lone = [n for pos, n in names if pos < rel_at]
    if lone:
        bad(f"이름 {', '.join(sorted(set(lone)))} 이(가) **관계말보다 먼저** 나온다 "
            "— 보는 사람은 그가 누구인지 모른다. "
            "'이십 년을 같이 산 아내' 처럼 관계를 먼저 밝혀라")
    elif names:
        print(f"   ✅ 이름({', '.join(sorted({n for _p, n in names}))})이 "
              "관계말 뒤에 나온다")
    else:
        print("   ✅ 이름을 던져 놓지 않았다")

    # ③ 누가 · 무엇을 다투나
    rels = sorted({r for r in RELATIONS if r in joined})
    cons = sorted({c for c in CONFLICT if c in joined})
    if not rels:
        bad("훅 어디에도 **관계말**(아내·아들·형 …)이 없다 — 누구 이야기인지 모른다")
    else:
        print(f"   ✅ 누구 이야기인지 나온다: {', '.join(rels[:5])}")
    if not cons:
        bad("훅 어디에도 **무엇을 다투는지**가 없다 — 그래서 뭘 보라는 건지 모른다")
    else:
        print(f"   ✅ 무엇을 다투는지 나온다: {', '.join(cons[:5])}")

    # ④ 훅 전체가 설계한 창(22초) 안에 들어오나
    #
    # ⚠️ 처음엔 "한 컷에 sec x 5.5자를 넘으면 말이 잘린다" 로 재려 했다. **틀렸다.**
    #    render.cut_durations 를 읽어 보니 `d = max(대본초, 실제음성길이 + 0.6)` 이다.
    #    곧 컷이 **음성에 맞춰 늘어나므로 말은 잘리지 않는다.** 그 검사를 넣었으면
    #    아무 문제 없는 EP001 훅을 다섯 컷 다 불합격시킬 뻔했다.
    #    (tts.py 도 같은 말을 적어 두었다 — "'글자당 몇 초' 를 숫자로 박아 두지
    #     않는다. 그것도 짐작이기 때문이다." 나는 그 짐작을 또 하려 했다.)
    #
    #    진짜로 정해져 있는 것은 **훅이 쓸 수 있는 시간(0~22초)** 뿐이다. 그것만 잰다.
    total = sum(sec for _i, _t, sec in texts)
    if total > HOOK_WINDOW * 1.25:
        bad(f"훅 다섯 컷이 {total:.1f}초다 — 설계는 {HOOK_WINDOW}초다. 너무 늘어진다")
    else:
        print(f"   ✅ 훅 전체 {total:.1f}초 (설계 {HOOK_WINDOW}초)")
    # 읽는 속도는 **참고로만** 알린다 (음성이 길면 컷이 늘어날 뿐, 잘리지는 않는다)
    fast = [(cid, len(t) / sec) for cid, t, sec in texts if sec > 0 and len(t) / sec > 8.0]
    if fast:
        warn("빨리 읽어야 하는 컷 (잘리지는 않고 컷이 길어진다): "
             + " · ".join(f"{cid} 1초에 {r:.1f}자" for cid, r in fast))

    # ⑤ 첫 컷은 사람 대사로, 3초 안에
    cid0, t0, sec0 = texts[0]
    if (cuts[0].get("speaker") or "") == "narrator":
        warn(f"[{cid0}] 첫 컷이 나레이션이다 — 사람 대사로 시작하는 편이 붙잡는다")
    if sec0 > 3.0:
        warn(f"[{cid0}] 첫 컷이 {sec0:.1f}초다 — 3초 안에 끝나는 편이 좋다")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        paths = [SCRIPTS / f"{a}.json" for a in args]
    else:
        paths = sorted(p for p in SCRIPTS.glob("EP*.json")
                       if not any(x in p.name for x in (".eval.", ".shorts.", ".draft.")))
    if not paths:
        print("대본이 없다.")
        return 0

    print("⭐ 도입 훅이 **알아들을 수 있는 말인가** (앞 22초 · 되감기 없음)")
    for p in paths:
        if p.exists():
            check(p)

    print()
    print("─" * 56)
    if ok:
        print("✅ 도입 훅: 알아들을 수 있다")
        return 0
    print("❌ 도입 훅: 알아듣기 어렵다")
    print("   → [2. 대본 만들기] → [도입 훅만 다시 쓰기] 를 누르십시오 (약 150원).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
