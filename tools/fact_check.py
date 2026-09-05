#!/usr/bin/env python3
"""⭐ **판결문 대조(사실 검사)**가 진짜로 도는가. 값 0원 (가짜 AI 로 시험한다).

    python3 tools/fact_check.py

⭐⭐⭐ 2026-09-05 손님: **"상간녀가 위자료를 더 높여 불렀다. 이거는 반대가
   되는 거 아니야? 이런 부분들은 왜 사전에 그 검증을 못하는 거지?"**

   그때까지 대본 검사는 **규격만** 봤다 — 편 수·글자 수·컷 수·화자·주어.
   "이 말이 판결문과 맞는가" 를 보는 검사는 **한 개도 없었다.** 판결문은
   `data/cases/<번호>.json` 에 저장돼 있는데 대본을 지은 뒤 아무도 안 봤다.
   그래서 S91 컷18 이 이렇게 나갔다 —

       여자는 사생활 침해라며 **위자료를 더 올려 불렀습니다.**

   판결문의 실제는 정반대다. 위자료 3,000만 원은 **아내가 상간녀에게** 받는
   돈이고, 상간녀가 한 것은 **반소로 3,000만 원을 청구**한 것이다(50만 원 인용).

여기서 보는 것
   ① 어긋난 곳을 반려 사유로 만들어 내는가
   ② 알려 준 한 줄을 **0원으로** 끼워 넣는가 (AI 를 또 안 부른다)
   ③ 각색(지어낸 대사·장면)은 안 잡는가 — 프롬프트에 그렇게 적혀 있는가
   ④ 이 검사가 죽어도 2,100원짜리 대본을 안 날리는가
   ⑤ 고치는 쪽이 판결문을 받는가 (안 주면 사실을 못 고친다)
   ⑥ 값과 부르는 횟수 뚜껑이 이 한 번을 담고 있는가
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import story90 as ST                                        # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name
          + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


class FakeLLM:
    """가짜 AI. 판결문을 진짜로 읽지 않고, 정해 둔 답만 돌려준다 (값 0원)."""

    def __init__(self, answer):
        self.answer, self.seen = answer, []

    def json(self, body, **kw):
        self.seen.append(body)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def doc_with(line):
    """컷18 이 그 줄인 시험용 대본 (저장된 파일을 안 읽는다)."""
    cuts, parts = [], []
    for k in range(3):
        a = k * 9 + 1
        for n in range(a, a + 9):
            who = "나레이션" if (n - a) in (0, 4, 8) else "아내"
            t = ("아내는 남편의 차에서 낯선 목소리를 들었습니다."
                 if who == "나레이션" else "당신 차에서 다 찍혔어.")
            cuts.append({"n": n, "who": [] if who == "나레이션" else ["아내"],
                         "turns": [[who, t]], "say": ["담담하게"], "sec": 5.0,
                         "scene": "a quiet parked car at night"})
        parts.append({"no": k + 1, "cuts": [a, a + 8],
                      "card": ["첫 줄", "둘째 줄"], "yt_title": "시험 제목"})
    cuts[17]["turns"] = [["나레이션", line]]
    return {"sid": "S99", "case_id": "184315", "title": "시험", "cuts": cuts,
            "parts": parts, "people": {}}


ROW = {"case_id": "184315", "one_line": "", "twist_hint": "", "case_type": "",
       "victim": "", "villain": "", "amount_label": ""}

WRONG = "여자는 사생활 침해라며 위자료를 더 올려 불렀습니다."
RIGHT = "여자는 오히려 불법 녹음이라며 똑같이 삼천만 원을 요구했습니다."


def main():
    print("⭐ 판결문 대조 (값 0원 — 가짜 AI 로 시험한다)\n")

    print("① 어긋난 곳을 반려 사유로 만들어 내는가")
    llm = FakeLLM({"wrong": [{
        "n": 18,
        "무엇이틀렸나": "상간녀가 위자료를 올려 불렀다고 썼다",
        "판결문은": "상간녀가 반소로 3,000만 원을 청구했고 50만 원만 인정됐다",
        "이렇게": RIGHT}]})
    doc = doc_with(WRONG)
    why, tip = ST.factcheck(llm, doc, ROW)
    ck("어긋난 곳을 하나 잡았다", len(why) == 1, str(why))
    ck("컷 번호가 사유에 적힌다", why and why[0].startswith("컷18"), str(why[:1]))
    ck("판결문이 뭐라 하는지도 적어 준다", why and "판결문:" in why[0])
    ck("그 자리에 넣을 한 줄도 받아 둔다", tip.get(18) == RIGHT, str(tip))

    print("\n① -2 보낸 글에 판결문과 대본이 다 들어 있는가")
    sent = llm.seen[0]
    ck("판결문 본문을 보낸다", "녹음장치를 부착" in sent)
    ck("대본을 보낸다", WRONG in sent)
    ck("각색은 잡지 말라고 적혀 있다",
       "지어낸 대사와 장면" in sent and "잘못이 아니다" in sent)
    ck("의심스러우면 잡지 말라고 적혀 있다", "의심스러우면" in sent)

    print("\n② 알려 준 한 줄을 0원으로 끼워 넣는가")
    moved = ST.apply_tip(doc, tip)
    ck("컷18 이 바뀐다", doc["cuts"][17]["turns"][0][1] == RIGHT)
    ck("무엇이 바뀌었는지 적어 준다", moved and "컷18" in moved[0], str(moved))
    ck("다른 컷은 안 건드린다",
       [c["n"] for c, o in zip(doc["cuts"], doc_with(WRONG)["cuts"])
        if c["turns"] != o["turns"]] == [18])
    ck("길이(sec)를 다시 센다", doc["cuts"][17]["sec"] != 5.0)
    # ⚠️ 두 사람이 주고받는 컷은 어느 줄인지 애매하다 — 손대지 않는다
    two = doc_with(WRONG)
    two["cuts"][17]["turns"] = [["아내", "가"], ["남편", "나"]]
    ST.apply_tip(two, {18: RIGHT})
    ck("두 줄짜리 컷은 기계가 안 건드린다 (AI 에게 되묻는다)",
       two["cuts"][17]["turns"][0][1] == "가")

    print("\n③ 어긋난 곳이 없으면 조용한가")
    why2, tip2 = ST.factcheck(FakeLLM({"wrong": []}), doc_with(RIGHT), ROW)
    ck("잘 쓴 대본은 안 잡는다", why2 == [] and tip2 == {})

    print("\n④ 이 검사가 죽어도 대본을 날리지 않는가")
    src = (ROOT / "src" / "story90.py").read_text(encoding="utf-8")
    mn = (re.search(r"def main\(\)[\s\S]*?\n\nif __name__", src) or [""])[0]
    ck("판결문 대조를 감싸서 부른다",
       re.search(r"try:\s*\n\s*why, tip = factcheck", mn) is not None)
    ck("죽어도 규격 검사로 넘어간다", "규격 검사만 하고 갑니다" in mn)
    ck("규격 검사보다 **먼저** 돈다 (고치는 자리를 한 번에 모으려고)",
       mn.index("factcheck(") < mn.index("bad = check(doc)"))

    print("\n⑤ 고치는 쪽이 판결문을 받는가")
    ck("되받아 고치기에 판결문을 넘긴다", "repair(llm, doc, bad, row)" in src)
    ck("고치기 함수가 그것을 받는다", "def repair(llm, doc, bad, row=None)" in src)
    fx = (ROOT / "prompts" / "story90_fix.md").read_text(encoding="utf-8")
    ck("고치는 프롬프트에 판결문 자리가 있다", "{{CASE}}" in fx)
    ck("고치는 프롬프트도 각색은 봐주라고 적는다",
       "지어낸 것이 당연하다" in fx)

    print("\n⑥ 값과 횟수 뚜껑이 이 한 번을 담는가")
    ck("부르는 횟수를 늘렸다 (짓기1 + 대조1 + 고치기2 + 여유2)",
       "max_calls=6" in src)
    yml = (ROOT / ".github" / "workflows" / "story90.yml").read_text(
        encoding="utf-8")
    cap = int((re.search(r"VT_RUN_KRW: '(\d+)'", yml) or [0, "0"])[1])
    ck(f"한 번 실행 뚜껑이 진짜 값 바로 위다 ({cap:,}원)",
       2400 <= cap <= 4000, f"{cap:,}원 — 너무 낮거나(중간에 멈춘다) 너무 높다")
    js = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
    ck("화면이 적어 둔 값이 진짜 값과 맞는다 (300원이라고 적혀 있었다)",
       "약 2,200원입니다" in js and "약 300원 안팎입니다" not in js)
    ck("한 줄만 틀렸을 때는 0원 길을 알려 준다",
       "대본 고치기] 가 0원입니다" in js)

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 판결문 대조: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 판결문 대조: 뒤집힌 사실을 잡고 · 각색은 봐주고 · 죽어도 안 날린다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
