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
    """2026-09-03 에 반려된 그 모양 — 사람 아닌 화자 + 짧은 제목.

    ⚠️ 나머지는 **지금 규격에 맞게** 채운다 (3편 · 편당 9컷 · 편마다 나레이션
       셋 이상 · 편은 나레이션으로 시작 · 사람은 말하기 전에 화면에 먼저 ·
       같은 말을 다시 쓰지 않는다). 그래야 시험이 재려는 것 — 손보기와
       되받아 고치기 — 만 남는다.
    """
    def cut(n, who, text, face=None):
        return {"n": n, "who": list(face or ([] if who == "나레이션" else [who])),
                "turns": [[who, text]], "say": ["담담하게 낮은 목소리로"],
                "scene": "a woman sits alone in a dim room"}

    cuts, n = [], 0

    def add(who, text, face=None):
        nonlocal n
        n += 1
        cuts.append(cut(n, who, text, face))

    for part in range(3):
        # 편은 나레이션으로 열고, 인물은 화면에 먼저 세운 뒤 말하게 한다
        add("나레이션", f"{part + 1}막이 열리던 그날의 이야기를 지금부터 전해 드립니다",
            ["아내"])
        add("나레이션", f"그 무렵 아내가 무엇을 알게 되었는지부터 짚어야 합니다 {part}",
            ["아내", "남편"])
        add("아내", f"차에서 나온 그 목소리를 나는 {part}번이나 되돌려 들었어요")
        add("남편", f"그건 {part}년도 더 된 일이고 지금은 아무 사이도 아니라니까")
        add("나레이션", f"그러나 남편의 말과 달리 통화 기록에는 {part}년치가 남아 있었습니다")
        add("아내", f"통화가 {part}백 번이 넘는데 아무 사이가 아니라는 말인가요")
        add("남편", f"그 사람 이름은 이 집에서 {part}번도 꺼내지 말라고 했잖아")
        add("나레이션", f"아내는 그날 밤 {part}시가 넘은 시각에 변호사를 찾아갔습니다")
        add("아내", f"소장에 적을 금액은 {part}천만 원으로 하겠다고 말했습니다")

    cuts[12] = cut(13, "법원", "원고의 청구를 기각한다")   # ← 여기서 걸렸다
    cuts[12]["who"] = ["법원"]
    return {
        "title": "녹음기 사건", "series_label": "녹음기 사건",
        "hook": "남편 차에 녹음기를 숨겼다",
        "people": {},
        "cuts": cuts,
        "parts": [
            {"no": 1, "cuts": [1, 9], "card": ["남편 차에서", "소리가 났다"],
             "yt_title": "남편 차에 녹음기를 숨긴 아내가 들은 것은 충격이었다"},
            # ⚠️ 짧은 제목 — 이런 것이 실제로 대본 한 편을 통째로 날렸다.
            {"no": 2, "cuts": [10, 18], "card": ["증거를 들이대자", "돌아온 맞소송"],
             "yt_title": "불륜 들키자 되레 고소한 상간녀"},
            {"no": 3, "cuts": [19, 27], "card": ["법정에 선 두 사람", "판결이 났다"],
             "yt_title": "법원이 상간녀에게 물린 위자료 삼천만 원의 근거"},
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
    # ⭐⭐⭐ 2026-09-05 손님: "야 대본 다시 만들기가 없잖아. 이거 메뉴를
    #    추가해 줘야 내가 만들지."
    #    맞다. 대본이 한 번 나오면 다시 지을 길이 화면에 없었다. 대기열은
    #    이미 쓴 사건을 빼고 보여 주므로 거기로 돌아가도 그 사건이 없다.
    # ⭐⭐⭐ 2026-09-05 손님: "야 대본 다시 만들기가 없잖아." → 작품 화면에
    #    달았더니 "이렇게 열기 밖에 안떠서 쇼츠 대본을 다시 만들수 없어."
    #    대기열에서 그 사건을 **보고 있는데** 다시 지으려면 한 화면 더 들어가야
    #    했다. 보고 있는 자리에서 눌릴 수 있어야 한다 → 두 자리 다 본다.
    print("\n①-2 대본을 다시 지을 수 있는가 (두 자리에서 다)")
    wd = (re.search(r"function workDraw\(\)[\s\S]*?\n}", js) or [""])[0]
    qc = (re.search(r"function queueCard\([\s\S]*?\n}", js) or [""])[0]
    rs = (re.search(r"async function restory\([\s\S]*?\n}\n", js) or [""])[0]

    ck("작품 화면에 단추가 있다",
       'id="w-restory"' in wd and "workStory()" in wd)
    ck("대기열 줄에도 단추가 있다",
       "againStory(this)" in qc and "대본 다시 짓기" in qc)
    ck("대기열 줄이 사건 번호를 data- 로 넘긴다 (따옴표로 안 끼운다)",
       'data-sid="' in qc,
       "onclick 글자에 끼우면 따옴표 하나로 페이지가 통째로 깨진다")
    # ⚠️ 셈이 두 벌이면 한쪽만 고쳐 놓고 고쳤다고 믿게 된다
    # ⚠️ '/api/make-story' 를 세면 안 된다 — **새 사건 만들기**(makeStory)도
    #    같은 창구를 쓴다. 그건 다른 일이라 두 곳인 게 맞다.
    #    여기서 볼 것은 **다시 짓기 셈이 두 벌이 아닌가** 이다.
    ck("다시 짓기 셈은 한 곳에만 있다 (두 단추가 같은 것을 부른다)",
       bool(rs) and "restory(WORK" in js and "restory(btn" in js
       and js.count("덮어씁니다") == 1 and js.count("약 300원") == 1
       and js.count("유튜브에 올렸습니다") == 2,   # 확인 글 1 + 화면 경고 1
       "확인 글·값·경고가 두 벌이 되면 한쪽만 낡는다")

    ck("그 사건의 판례 번호로 부른다", "case_id: cid" in rs and "w.case_id" in rs)
    ck("두 번 눌려도 한 번만 돈다", "WBUSY['restory']" in rs)
    ck("도는 동안 단추가 잠긴다", "btn.disabled = true" in rs)
    ck("누르기 전에 값을 알려 준다", "약 300원" in rs)
    ck("같은 번호로 덮어쓴다고 알려 준다", "덮어씁니다" in rs)
    ck("이미 올린 편이 있으면 경고한다",
       "유튜브에 올렸습니다" in rs and "유튜브에 올렸습니다" in wd,
       "올라간 영상과 내용이 달라지는 것을 모르고 누르면 안 된다")
    ck("끝까지 지켜보고 결과를 알려 준다",
       "watchRun('story90.yml'" in rs and "storySay(" in rs)
    ck("다 되면 화면을 새 대본으로 다시 그린다",
       "openWork(sid)" in rs and "loadWorks(true)" in rs)
    ck("어느 화면에서 눌러도 그 화면이 갱신된다",
       "VIEW === 'work'" in rs and "else load();" in rs)
    # 알림 자리가 다른 화면과 겹치면 엉뚱한 칸에 뜬다 (실제로 겪은 사고)
    ck("알림 자리 이름이 다른 화면과 안 겹친다",
       js.count('id="w-restory-msg"') == 1 and js.count('id="w-story-msg"') == 1)

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
    ch = re.search(r"글자 수 합계는 (\d+)~(\d+)자", md)
    ck(f"편당 글자 수를 검사기({ST.PART_CHARS_MIN}~{ST.PART_CHARS}자) "
       f"안쪽으로 시킨다",
       bool(ch) and ST.PART_CHARS_MIN <= int(ch.group(1))
       and int(ch.group(2)) <= ST.PART_CHARS,
       (ch.group(1) + "~" + ch.group(2) + "자를 시킨다") if ch
       else "프롬프트에 글자 수 범위가 없다")
    cu = re.search(r"한 편은 컷 \*\*(\d+)~(\d+)개\*\*", md)
    ck(f"한 편 컷 수를 검사기({ST.PART_MIN_CUTS}~{ST.PART_MAX_CUTS}컷) "
       f"안쪽으로 시킨다",
       bool(cu) and ST.PART_MIN_CUTS <= int(cu.group(1))
       and int(cu.group(2)) <= ST.PART_MAX_CUTS,
       (cu.group(1) + "~" + cu.group(2) + "컷을 시킨다") if cu
       else "프롬프트에 컷 수가 없다")
    ck(f"화면 제목 길이가 프롬프트와 같다 ({ST.CARD_MAX}자)",
       f"{ST.CARD_MAX}자" in md)
    pa = re.search(r"전체는 \*\*(\d+)~(\d+)편\*\*", md)
    ck(f"편 수를 검사기({ST.PARTS_MIN}~{ST.PARTS_MAX}편) 안쪽으로 시킨다",
       bool(pa) and ST.PARTS_MIN <= int(pa.group(1))
       and int(pa.group(2)) <= ST.PARTS_MAX,
       (pa.group(1) + "~" + pa.group(2) + "편을 시킨다") if pa
       else "프롬프트에 편 수가 없다")

    # ⭐⭐⭐ 2026-09-05 손님: "두편이야? 세 편 이상 나오게 해야지.
    #    너무 빠르게 본론으로 들어가 버리니까 내용이 이해가 안 돼."
    #    S91 을 재 보니 2편 15컷 389자 — S90(3편 24컷 607자)보다 36% 얇았다.
    #    같은 일이 다시 나지 않게, 얇게 만드는 길을 하나씩 막았는지 본다.
    print("\n④-2 대본이 다시 얇아지지 않는가")
    ck("2편은 못 나온다", ST.PARTS_MIN >= 3)
    ck("짧게 써도 잡힌다 (글자 하한이 있다)", ST.PART_CHARS_MIN >= 180)
    ck("말줄임표에 상한이 있다", ST.ELLIPSIS_MAX <= 3)
    ck("'단순하면 2편' 같은 쉬운 길을 안 열어 준다",
       "단순하면 2편" not in md and "최소 3편" in md)
    ck("한 컷에 한 걸음만 나가라고 적었다", "한 컷은 한 걸음만" in md)
    ck("대사에 손에 잡히는 것을 담으라고 적었다",
       "손에 잡히는 것 하나" in md)
    ck("나레이션이 신문 기사가 되지 말라고 적었다", "신문 기사가 아니라 장면" in md)
    # 진짜로 잡는지 — S91(2편·짧음·말줄임표 많음)을 새것으로 쳐서 재 본다
    s91 = json.loads((ROOT / "data" / "series" / "S91.story.json")
                     .read_text(encoding="utf-8"))
    b91 = ST.check(s91, new=True)
    for want in ("편이 2개다", "185자", "말줄임표", "컷이다"):
        ck(f"S91 의 문제를 잡는다 ({want})",
           any(want in x for x in b91), str(b91[:2]))
    ck("이미 만들어 둔 대본은 그대로 둔다 (뒤늦게 빨간불이 안 난다)",
       not ST.check(s91, new=False))

    # ── ⑤ 사람을 늘릴 수 있는가 ──────────────────────────────
    # ⭐⭐⭐ 2026-09-05 손님: "단순히 짧아서 길게 늘리는 게 아니라, 이 이야기를
    #    충분히 이해할 수 있게끔 … 극적으로 몰입을 할 수 있게 하는 게 목적이야."
    #    분량 하한만 두면 AI 는 **채운다** — 같은 말을 늘여 쓰거나 빈 대사를
    #    더 넣는다. 그러면 길어지면서 지루해지기까지 한다.
    #    그래서 '길이'가 아니라 '따라갈 수 있는가' 를 재는 못이 같이 있어야 한다.
    print("\n④-2-2 길이가 아니라 **이해**를 재는가")
    ck("목적을 프롬프트 맨 앞에 못 박았다",
       "길이는 목적이 아니라" in md)
    ck("채우려고 늘리지 말라고 적었다",
       "분량을 채우려고 늘리지 마라" in md and "같은 말을 다시 쓰거나" in md)
    ck("늘릴 자리에 무엇을 넣을지 적었다 (왜 · 그래서)",
       "빠진 걸음" in md and "왜 그랬는지" in md)
    ck("편마다 누가·무엇을·왜·그래서를 묻는다",
       all(k in md for k in ("**누가**", "**무엇을 했나**", "**왜**", "**그래서**")))
    ck("글자 하한을 '채워라' 가 아니라 '걸음이 빠졌다' 로 적었다",
       "걸음이 빠졌다는 뜻이다" in md and "글자를 채우라는 말이\n  아니다" in md)
    ck("새 인물은 말하기 전에 화면에 먼저 나오라고 적었다",
       "말하기 전에** 화면에 먼저 나온다" in md)
    ck("맥락은 나레이션이 나른다고 적었다", "맥락은 나레이션이 나른다" in md)

    print("\n④-2-3 그 못이 진짜로 잡는가 (S91 로 재 본다)")
    # ⚠️ 이름과 재는 것이 어긋나 있었다 — 이름은 '얼굴' 인데 잰 것은
    #    나레이션 줄 수였다. 검사 이름이 틀리면 빨간불이 나도 어디가
    #    문제인지 알 수 없다.
    ck("편마다 맥락을 나르는 나레이션을 요구한다", ST.NARR_MIN_PER_PART >= 3)
    b91h = ST.check(s91, new=True)
    for want, why in (("화면에 한 번도 안 나온 채", "누가 말하는지 모른다"),
                      ("껑충 뛰고 있다는 뜻", "짧은 것은 증상이라고 알려 준다")):
        ck(f"S91 에서 잡는다 — {why}",
           any(want in x for x in b91h), str(b91h[:2]))
    # 되풀이로 분량만 채운 대본을 만들어 넣어 본다 (0원)
    pad = json.loads(json.dumps(s91))
    same = pad["cuts"][0]["turns"][0][1]
    pad["cuts"][5]["turns"][0][1] = same
    ck("같은 말을 다시 써서 분량을 채우면 잡는다",
       any("같은 말을 다시 한다" in x for x in ST.check(pad, new=True)))
    # 대사로 시작하는 편도 잡아야 한다
    st2 = json.loads(json.dumps(s91))
    st2["cuts"][0]["turns"][0][0] = "아내"
    st2["cuts"][0]["who"] = ["아내"]
    ck("편이 대사로 시작하면 잡는다",
       any("대사로 시작한다" in x for x in ST.check(st2, new=True)))
    # 나레이션이 모자라면 잡는가
    st3 = json.loads(json.dumps(s91))
    for c in st3["cuts"]:
        for t in c["turns"]:
            if t[0] == "나레이션" and c["n"] > 1:
                t[0] = "아내"
    ck("나레이션이 모자라면 잡는다",
       any("나레이션이" in x and "줄뿐이다" in x
           for x in ST.check(st3, new=True)))

    print("\n④-3 값과 번호가 어긋나지 않는가")
    llm = (ROOT / "src" / "llm.py").read_text(encoding="utf-8")
    # ⚠️ 제미나이는 **생각한 토큰**도 값에 넣는다. 그것을 안 세면 화면에 찍힌
    #    값이 실제보다 적고, 한도(RUN_KRW)가 막는 시늉만 하게 된다.
    ck("생각한 만큼도 값에 센다 (thoughtsTokenCount)",
       llm.count("thoughtsTokenCount") >= 2,
       "안 세면 화면 값이 실제보다 적게 찍힌다")
    ck("같은 판례로 다시 지으면 그 번호를 다시 쓴다", "def sid_for(" in src
       and "again or next_sid()" in src,
       "안 그러면 한 사건이 목록에 둘로 뜬다")

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
