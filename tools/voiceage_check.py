#!/usr/bin/env python3
"""⭐ **목소리를 나이로 고르는가.** 값 0원 (인터넷 0회).

    python3 tools/voiceage_check.py

⭐⭐⭐ 2026-09-20 손님: "너 지금 등장인물 나이에 따라서 목소리를 잘 조정하고
   있는 건 맞아?" → **아니었다.** 두 군데가 나이를 버리고 있었다.
     ① short90.voice_of 가 **이름표(VOICE)를 먼저** 봤다. 그래서 핵심 다섯
        (아내·남편·내연녀·딸·변호사)은 대본이 나이를 뭐라 적든 늘 같은
        목소리였다 — 예순의 아내도, 서른의 아내도 50대 소리로 말했다.
     ② story90.people_of 가 그 다섯의 나이를 **손으로 박아 두고**, 대본이
        적어 준 나이를 `nm in out: continue` 로 **버렸다.**
   → 나이대·성별이 먼저 정하고, 이름표는 나이를 모를 때의 기본값이다.

여기서 지키는 것
   ① 대본이 적은 나이가 **이긴다** (기본값을 덮어쓴다)
   ② 나이가 바뀌면 목소리도 바뀐다 (안 바뀌면 나이를 안 보는 것이다)
   ③ 나레이션 목소리는 **누구에게도 안 준다** (귀로 구별이 안 된다)
   ④ 남녀가 안 바뀐다 (여자 배역에 남자 소리가 가면 안 된다)
   ⑤ 나이 기본값이 **한 곳**에만 있다 (두 벌이면 한쪽만 고쳐진다)
   ⑥ 모르는 사람도 조용히 제 나이 목소리를 받는다
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import short90 as S9                                        # noqa: E402
import story90 as ST                                        # noqa: E402
import tts as T                                             # noqa: E402

bad = []
AGES = ("10대", "20대", "30대", "40대", "50대", "60대", "70대")


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name
          + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def doc_with(**ppl):
    return {"people": {k: v for k, v in ppl.items()}, "cuts": [], "parts": []}


def main():
    print("⭐ 목소리를 나이로 고르는가 (값 0원)\n")

    print("① 대본이 적은 나이가 이긴다 (기본값을 덮어쓴다)")
    base = ST.people_of({})
    ck("안 적어 주면 기본값이 나온다", base["아내"]["age"] == "50대",
       str(base.get("아내")))
    got = ST.people_of(doc_with(아내={"age": "60대", "sex": "여"}))
    ck("적어 주면 그 나이가 나온다 (예순의 아내)",
       got["아내"]["age"] == "60대", str(got.get("아내")))
    ck("안 적은 사람은 기본값 그대로", got["딸"]["age"] == "20대")
    src = (ROOT / "src" / "story90.py").read_text("utf-8")
    ck("기본 다섯을 건너뛰지 않는다 (옛 버그: nm in out → continue)",
       "if not nm:" in src.split("def people_of")[1][:900],
       "건너뛰면 대본이 적은 나이가 통째로 버려진다")

    print("\n② 나이가 바뀌면 목소리도 바뀌는가")
    seen = {}
    for a in AGES:
        seen[a] = S9.voice_of("아내", doc_with(아내={"age": a, "sex": "여"}))
    ck(f"아내 나이를 바꾸면 목소리가 갈린다 ({len(set(seen.values()))}가지)",
       len(set(seen.values())) >= 3, str(seen))
    ck("예순의 아내와 스물의 아내가 다른 소리다",
       seen["60대"] != seen["20대"], f"{seen['60대']} vs {seen['20대']}")
    ck("이름표를 먼저 보지 않는다",
       S9.voice_of("아내", doc_with(아내={"age": "20대", "sex": "여"}))
       != S9.VOICE["아내"],
       "이름표가 먼저면 나이를 아무리 적어도 안 바뀐다")

    print("\n③ 나레이션 목소리는 누구에게도 안 준다")
    narr = S9.VOICE["나레이션"]
    clash = [k for k, v in S9.VOICE_BY.items() if v == narr]
    ck(f"나이표에 나레이션 목소리가 없다 ({narr})", not clash, str(clash))
    who_all = ["아내", "남편", "내연녀", "딸", "변호사", "장남", "며느리"]
    hit = [(w, a, s) for w in who_all for a in AGES for s in ("남", "여")
           if S9.voice_of(w, doc_with(**{w: {"age": a, "sex": s}})) == narr]
    ck("어느 나이·성별을 넣어도 나레이션 소리가 안 나온다", not hit, str(hit[:3]))
    ck("나레이션은 늘 제 목소리다", S9.voice_of("나레이션", {}) == narr)

    print("\n④ 남녀가 안 바뀌는가")
    fem, male = set(T.GEM_F), set(T.GEM_M)
    wrong = []
    for (sx, a), v in S9.VOICE_BY.items():
        if sx == "여" and v not in fem:
            wrong.append((sx, a, v))
        if sx == "남" and v not in male:
            wrong.append((sx, a, v))
    ck("여자 칸은 여자 목소리 · 남자 칸은 남자 목소리", not wrong, str(wrong[:3]))
    ck("나이표가 일곱 나이대를 다 덮는다",
       all((s, a) in S9.VOICE_BY for s in ("남", "여") for a in AGES))

    print("\n⑤ 나이 기본값이 한 곳에만 있는가")
    s9 = (ROOT / "src" / "short90.py").read_text("utf-8")
    ck("short90 이 story90 의 나이를 읽는다",
       "ST90.people_of(doc)" in s9,
       "따로 세면 화면과 소리가 갈라진다")
    # ⚠️ '50대' 라는 글자 자체는 나이표(VOICE_BY)와 주석에도 나온다 — 그건
    #    잘못이 아니다. 막아야 하는 것은 **사람마다 나이를 또 적어 둔 표**다.
    ck("short90 에 사람별 나이표를 또 두지 않았다",
       '"아내": {"age"' not in s9 and "'아내': {'age'" not in s9,
       "두 벌이면 한쪽만 고쳐져 소리와 그림이 갈라진다")
    ck("기본값 표가 story90 에 있다", hasattr(ST, "PEOPLE_BASE")
       and set(ST.PEOPLE_BASE) >= {"아내", "남편", "내연녀", "딸", "변호사"})

    print("\n⑥ 진짜 대본으로 재 본다 (S93)")
    f = ROOT / "data" / "series" / "S93.json"
    if f.exists():
        d = json.loads(f.read_text("utf-8"))
        spk = sorted({w for c in d.get("cuts") or [] for w, _ in c["turns"]})
        vs = {w: S9.voice_of(w, d) for w in spk}
        ck(f"말하는 사람마다 목소리가 있다 ({len(vs)}명)",
           all(vs.values()), str(vs))
        chars = [v for w, v in vs.items() if w != "나레이션"]
        ck("등장인물끼리 목소리가 안 겹친다", len(set(chars)) == len(chars),
           str(vs))
        ck("등장인물 중에 나레이션 소리가 없다", narr not in chars, str(vs))
    else:
        ck("S93 대본이 있다", False)

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 목소리·나이: {len(bad)}군데")
        for x in bad:
            print(f"     {x}")
        return 1
    print("✅ 목소리: 나이가 정하고 · 나레이션과 안 겹치고 · 남녀가 맞다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
