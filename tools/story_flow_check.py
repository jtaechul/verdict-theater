#!/usr/bin/env python3
"""⭐ 대본 짓기가 **끝까지 가는지** 본다. 값 0원 (모델을 안 부른다).

    python3 tools/story_flow_check.py

손님(2026-09-04): "나 이 사건으로 쇼츠 만들기 눌렀는데 왜 아무것도 안떠?"

실제로는 돌았다. 46초 만에 규격 검사에서 반려됐고(2,100원), 그중 하나는
**제목이 25자, 통과선이 26자** — 딱 한 글자였다. 그런데 화면은 "5~10분 뒤
새로고침" 하고 끝냈으니 새로 고쳐도 아무것도 없었다.

고친 절차가 다시 무너지지 않게 다섯 자리를 본다.
  ① 화면이 끝까지 지켜보고 결과를 알려 주는가
  ② 워크플로가 **실패해도** 결과표와 받은 대본을 남기는가
  ③ 자동 손보기 → 검사 → 되받아 고치기 → 남기기, 차례가 맞는가
  ④ 시킨 숫자와 재는 숫자가 같은가 (달라서 25자가 나왔다)
  ⑤ 사람을 사건마다 늘릴 수 있고, 늘린 사람이 제 목소리를 받는가
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import prompts                                               # noqa: E402
import short90 as S9                                         # noqa: E402
import story90 as ST                                         # noqa: E402

# ── 모의 실행에 쓸 것들 ────────────────────────────────────────
class FakeLLM:
    """인터넷 없이 '되받아 고치기' 를 흉내 낸다 (값 0원).

    ⚠️ 진짜 모델을 안 부른다. 여기서 보는 것은 **고친 것을 제대로 끼워
       넣는가**이지 모델이 잘 쓰는가가 아니다.
    """

    def json(self, body, **kw):
        return {"parts": [{"no": 2, "yt_title":
                           "불륜 들키자 불법녹음이라며 되레 고소한 상간녀의 최후"}]}


def fake_s91():
    """2026-09-03 에 반려된 그 모양 — 사람 아닌 화자 + 25자 제목."""
    def cut(n, who, text):
        return {"n": n, "who": [] if who == "나레이션" else [who],
                "turns": [[who, text]], "say": ["담담하게 낮은 목소리로"],
                "scene": "a woman sits alone in a dim room"}
    cuts = [cut(i, "아내" if i % 2 else "남편", "짧은 대사 " + str(i))
            for i in range(1, 17)]
    cuts[12] = cut(13, "법원", "원고의 청구를 기각한다")   # ← 여기서 걸렸다
    cuts[12]["who"] = ["법원"]
    return {
        "title": "녹음기 사건", "series_label": "녹음기 사건",
        "hook": "남편 차에 녹음기를 숨겼다",
        "people": {},
        "cuts": cuts,
        "parts": [
            {"no": 1, "cuts": [1, 8], "card": ["남편 차에서", "소리가 났다"],
             "yt_title": "남편 차에 녹음기를 숨긴 아내가 들은 것은 충격이었다"},
            # ⚠️ 짧은 제목 — 이런 것이 실제로 2,100원을 통째로 날렸다.
            #    (그때는 25자였고 통과선이 26자, 딱 한 글자 차이였다. 지금은
            #     아래 선을 22자로 내렸으므로 시험은 그보다 더 짧게 둔다.)
            {"no": 2, "cuts": [9, 16], "card": ["증거를 들이대자", "돌아온 맞소송"],
             "yt_title": "불륜 들키자 되레 고소한 상간녀"},
        ],
    }

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name
          + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def main():
    print("⭐ 대본 짓기가 끝까지 가는가 (값 0원)\n")
    js = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
    yml = (ROOT / ".github" / "workflows" / "story90.yml").read_text(encoding="utf-8")
    src = (ROOT / "src" / "story90.py").read_text(encoding="utf-8")

    # ── ① 화면이 결과를 알려 주는가 ───────────────────────────
    print("① 화면이 끝까지 지켜보는가")
    mk = (re.search(r"async function makeStory\([\s\S]*?\n}", js) or [""])[0]
    ck("대본 만들기가 실행을 끝까지 지켜본다",
       "watchRun('story90.yml'" in mk)
    ck("'새로고침 하십시오' 하고 끝내지 않는다",
       "5~10분 뒤에 이 화면을 새로 고쳐" not in mk)
    ck("결과표를 읽어 주는 창구가 있다", "/api/story-last" in js)
    ck("실패하면 걸린 곳을 화면에 적는다",
       "function storySay" in js and "규격에 맞게 못 만들었습니다" in js)
    ck("성공하면 작품 목록을 새로 읽는다",
       re.search(r"function storySay[\s\S]*?loadWorks\(true\)", js) is not None)

    # ── ② 실패해도 남기는가 ───────────────────────────────────
    print("\n② 실패해도 결과를 남기는가")
    ck("적어 두기가 실패해도 돈다 (if: always())",
       re.search(r"name: 저장소에 적어 두기\s*\n\s*if: always\(\)", yml) is not None)
    ck("대본 짓기가 바로 안 죽고 결과를 넘긴다",
       "set +e" in yml and "PIPESTATUS[0]" in yml)
    ck("빨간불은 **적어 둔 뒤에** 낸다",
       yml.index("저장소에 적어 두기") < yml.index("못 만들었으면 빨간불"))
    ck("결과표를 저장소에 올린다 (state)",
       "git add data/series state" in yml)
    ck("결과표 파일 이름이 맞다 (state/story_last.json)",
       "story_last.json" in src and "state/story_last.json" in js)

    # ── ③ 절차의 차례 ────────────────────────────────────────
    print("\n③ 손보기 → 검사 → 되받아 고치기 → 남기기")
    mn = (re.search(r"\ndef main\(\)[\s\S]*?\n\nif __name__", src) or [""])[0]
    for what, pat in (("자동 손보기(0원)가 먼저다", r"fixed = autofix\(doc\)"),
                      ("그다음 검사한다", r"bad = check\(doc\)"),
                      ("걸리면 되받아 고친다", r"repair\(llm, doc, bad\)"),
                      ("그래도 안 되면 받은 대본을 남긴다", r"\.broken\.json"),
                      ("얼마 썼는지 적어 준다", r"spent\(\)")):
        ck(what, re.search(pat, mn) is not None)
    order = [mn.find("autofix(doc)"), mn.find("bad = check(doc)"),
             mn.find("repair(llm"), mn.find(".broken.json")]
    ck("차례가 뒤집히지 않았다", all(a >= 0 and a < b
                                    for a, b in zip(order, order[1:])),
       str(order))
    ck("되받아 고치기는 두 번까지만 (돈이 새지 않게)", ST.FIX_ROUNDS <= 2)
    ck("고치는 프롬프트가 있다", bool(prompts.load("story90_fix")))

    # ── ④ 시킨 숫자 = 재는 숫자 ──────────────────────────────
    print("\n④ 시킨 숫자와 재는 숫자가 같은가")
    md = prompts.load("story90_gen")
    ck(f"제목 아래 선이 프롬프트에도 적혀 있다 ({ST.TITLE_MIN}자)",
       f"{ST.TITLE_MIN}자보다 짧으면 안 된다" in md)
    ck("잘된 제목 길이(22~24자)를 검사가 막지 않는다", ST.TITLE_MIN <= 22)
    # ⚠️ **똑같아야 하는 것이 아니다.** 프롬프트가 더 좁게 시키는 것은 좋다
    #    (안쪽을 겨냥해야 실수로 넘지 않는다). 막아야 하는 것은 그 반대 —
    #    **프롬프트가 검사기보다 헐겁게 시키는 것**이다. 그러면 모델은 시킨
    #    대로 썼는데 검사에서 반려돼 2,100원이 날아간다.
    ch = re.search(r"글자 수 합계가 (\d+)자를 넘지 않는다", md)
    ck(f"편당 글자 수를 검사기({ST.PART_CHARS}자) 안쪽으로 시킨다",
       bool(ch) and int(ch.group(1)) <= ST.PART_CHARS,
       (ch.group(1) + "자를 시킨다") if ch else "프롬프트에 글자 수가 없다")
    cu = re.search(r"한 편은 컷 \*\*(\d+)~(\d+)개\*\*", md)
    ck(f"한 편 컷 수를 검사기({ST.PART_MIN_CUTS}~{ST.PART_MAX_CUTS}컷) "
       f"안쪽으로 시킨다",
       bool(cu) and ST.PART_MIN_CUTS <= int(cu.group(1))
       and int(cu.group(2)) <= ST.PART_MAX_CUTS,
       (cu.group(1) + "~" + cu.group(2) + "컷을 시킨다") if cu
       else "프롬프트에 컷 수가 없다")
    ck(f"화면 제목 길이가 프롬프트와 같다 ({ST.CARD_MAX}자)",
       f"{ST.CARD_MAX}자" in md)
    ck(f"편 수가 프롬프트와 같다 (2~4편)", "2~4편" in md)

    # ── ⑤ 사람을 늘릴 수 있는가 ──────────────────────────────
    print("\n⑤ 사람을 사건마다 늘릴 수 있는가")
    d = {"people": {"며느리": {"age": "30대", "sex": "여"}}}
    ck("대본이 세운 사람을 화자로 쓸 수 있다", "며느리" in ST.who_ok(d))
    ck("늘린 사람이 제 목소리를 받는다 (나레이션 소리가 아니다)",
       S9.voice_of("며느리", d) != S9.VOICE["나레이션"],
       S9.voice_of("며느리", d))
    ck("사람 목록을 조립 쪽으로 넘긴다",
       '"people": dict(story.get("people")'
       in (ROOT / "tools" / "build_short90.py").read_text(encoding="utf-8"))
    # 법원은 사람이 아니다 — 0원으로 나레이션으로 돌려야 한다
    t = {"people": {"법원": {"age": "50대", "sex": "남"}},
         "cuts": [{"n": 1, "who": ["법원"],
                   "turns": [["법원", "기각한다"]], "say": ["담담하게"]}]}
    ST.autofix(t)
    ck("법원·판사를 화자로 쓰면 0원으로 나레이션이 된다",
       t["cuts"][0]["turns"][0][0] == "나레이션" and not t["cuts"][0]["who"])
    # 같은 잘못을 두 번 세지 않는다
    t2 = {"cuts": [{"n": 1, "who": ["사돈"], "turns": [["사돈", "말"]],
                    "say": ["담담하게"], "scene": "a woman sits"}],
          "parts": [{"no": 1, "cuts": [1, 1], "yt_title": "x" * 30,
                     "card": ["가", "나"]}]}
    hits = [b for b in ST.check(t2) if "사돈" in b]
    ck("한 잘못을 두 줄로 세지 않는다", len(hits) == 1, str(hits))

    # ── ⑥ 진짜로 끝까지 가는지 모의 실행 (인터넷 없이 · 0원) ──
    #    표만 보고 넘어가지 않는다. **S91 이 걸렸던 그 대본 그대로**를 넣어
    #    손보기 → 검사 → 되받아 고치기까지 돌려 보고, 통과로 끝나는지 본다.
    print("\n⑥ S91 이 걸렸던 그 대본으로 모의 실행 (0원)")
    doc = fake_s91()
    was = ST.check(doc)
    ck("옛 절차라면 반려됐을 대본이다 (사람 아닌 화자 + 짧은 제목)",
       len(was) >= 2, str(was[:3]))
    fixed = ST.autofix(doc)
    ck("자동 손보기가 '법원' 을 나레이션으로 돌린다",
       any("법원" in x for x in fixed), str(fixed))
    left = ST.check(doc)
    ck("손보기만으로 '법원' 문제가 사라진다",
       not any("법원" in b for b in left), str(left))
    ck("제목이 짧은 것은 남는다 (말은 AI 가 지어야 한다)",
       any("제목" in b for b in left), str(left))
    # 되받아 고치기를 인터넷 없이 흉내 낸다
    log, left2 = ST.repair(FakeLLM(), doc, left)
    ck("되받아 고치기가 제목을 고쳐 넣는다", any("yt_title" in x for x in log),
       str(log))
    ck("고친 뒤에는 규격을 다 지킨다 — 저장까지 간다", not left2, str(left2))

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 대본 짓기 절차: {len(bad)}군데 — 다시 조용히 실패할 수 있다")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 대본 짓기 절차: 손보고 · 고쳐 보고 · 안 되면 까닭을 알려 준다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
