#!/usr/bin/env python3
"""⭐ **대본 한 줄 고치기**가 처음부터 끝까지 이어지는가. 값 0원.

    python3 tools/editline_check.py

⭐⭐⭐ 2026-09-05 손님: **"이거는 지금 내가 대본을 바꿀 수가 없게 돼 있잖아.
   근본적인 문제를 해결하려면 어떻게 해야 되는 거야?"**

   한 글자가 틀려도 [대본 다시 만들기](약 2,100원) 말고는 길이 없었다.
   실제로 S91 컷18 이 판결문과 **방향이 거꾸로** 나왔다 —
   상간녀가 "위자료를 더 올려 불렀다" 고 썼는데 실제는 반소로 3,000만 원 청구.

여기서 보는 것
   ① 도구가 그 줄만 고치고 나머지는 안 건드리는가 (그림 지문이 그대로여야 0원)
   ② 규격(편당 225자)을 넘기면 **저장하지 않는가**
   ③ 단추 → 창구 → 워크플로 → 도구까지 이름이 이어지는가
   ④ 이 길에서 돈이 안 나가는가 (AI 를 안 부른다)

⚠️ 저장된 대본 파일에 안 기댄다 — 시험용 대본을 여기서 만든다.
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import story90 as ST                                        # noqa: E402
import edit_line as E                                       # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name
          + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def fake_story():
    """3편 × 9컷짜리 시험용 대본. 편마다 200자 안팎."""
    narr = "아내는 남편의 차에서 낯선 목소리를 들었습니다."
    talk = "당신 차에서 관계 맺는 소리가 다 찍혔어."
    cuts, parts = [], []
    for k in range(3):
        a = k * 9 + 1
        for n in range(a, a + 9):
            who = "나레이션" if (n - a) in (0, 4, 8) else "아내"
            t = narr if who == "나레이션" else talk
            cuts.append({"n": n, "who": [] if who == "나레이션" else ["아내"],
                         "turns": [[who, t]], "say": ["담담하게"],
                         "sec": 5.0, "scene": "a quiet parked car at night"})
        parts.append({"no": k + 1, "cuts": [a, a + 8],
                      "card": ["첫 줄", "둘째 줄"],
                      "yt_title": "남편 차에 녹음기를 숨긴 아내가 들은 것"})
    return {"sid": "S99", "title": "삼천만 원 위자료, 녹음기가 잡아낸 하룻밤",
            "series_label": "녹음기 사건", "hook": "남편 차에 녹음기를 숨겼다",
            "case_id": "184315", "parts": parts, "people": {}, "cuts": cuts}


def main():
    print("⭐ 대본 한 줄 고치기 (값 0원 — AI 를 안 부른다)\n")

    print("① 그 줄만 고치고 나머지는 안 건드리는가")
    doc0 = fake_story()
    tmp = Path(tempfile.mkdtemp())
    p = tmp / "S99.story.json"
    p.write_text(json.dumps(doc0, ensure_ascii=False, indent=1), encoding="utf-8")
    real = E.story_path
    E.story_path = lambda sid: p                             # 시험용 파일로 돌린다
    try:
        new = "여자는 오히려 불법 녹음이라며 삼천만 원을 요구했습니다."
        doc, _p, was, _log, why = E.edit("S99", 18, new)
        ck("고친 줄이 바뀐다", doc["cuts"][17]["turns"][0][1] == new)
        ck("무엇이 어떻게 바뀌었는지 알려 준다",
           any("→" in x for x in was), str(was))
        same = [c["n"] for a, c in zip(doc0["cuts"], doc["cuts"])
                if a["turns"] != c["turns"]]
        ck("다른 컷은 한 글자도 안 바뀐다 (그래서 0원)", same == [18], str(same))
        ck("화면 묘사는 그대로다 (그림을 다시 안 그린다)",
           all(a["scene"] == c["scene"]
               for a, c in zip(doc0["cuts"], doc["cuts"])))
        ck("길이(sec)를 다시 센다",
           doc["cuts"][17]["sec"] != doc0["cuts"][17]["sec"])
        ck("규격에 걸리지 않는다", not why, str(why[:2]))

        print("\n② 상한을 넘기면 저장하지 않는가")
        # ⚠️ 한 편 상한을 확실히 넘기는 길이여야 시험이 뜻이 있다.
        #    ⭐ 2026-09-08 — 상한이 초(PART_SEC_MAX)로 바뀌고 잣대도 실측으로
        #       다시 맞춰지면서, 옛 시험 글(약 100자)로는 더 이상 안 넘는다.
        #       상한에서 되짚어 **필요한 만큼** 길게 만든다 — 손으로 적은
        #       길이를 두면 상한을 조금만 올려도 시험이 조용히 무력해진다.
        _need = int((ST.PART_SEC_MAX - ST.SEC_PER_CUT * 9) / ST.SEC_PER_CHAR) + 60
        long = ("여자는 오히려 불법 녹음이라며 똑같이 삼천만 원을 물어내라고 "
                "맞소송을 걸었고 그 재판은 여름이 다 가도록 이어졌으며 "
                "두 사람은 끝내 한마디도 서로에게 건네지 않은 채 법정에서만 "
                "마주 앉아 서로의 잘못을 하나씩 꺼내 놓았습니다. ") * 6
        long = long[:_need * 2]          # 띄어쓰기가 섞여 있어 넉넉히 자른다
        _d2, _p2, _w2, _l2, why2 = E.edit("S99", 18, long)
        ck("편당 길이를 넘기면 반려한다",
           any("60초 벽" in x for x in why2), str(why2[:2]))
        # ⭐ 사유가 "규격 위반" 이 아니라 **몇 자·몇 컷·몇 초·왜**여야 한다
        msg = " ".join(why2)
        ck("반려 사유를 사람 말로 적어 준다 (몇 자·몇 컷·몇 초·왜)",
           "자 " in msg and "컷 =" in msg and "초다" in msg
           and "조회수 0" in msg, msg[:90])
        ck("파일은 그대로 남는다 (반려는 저장을 안 한다)",
           json.loads(p.read_text(encoding="utf-8"))["cuts"][17]["turns"][0][1]
           != long)

        print("\n② -2 없는 것을 달라고 하면 사람 말로 막는가")
        for nm, fn in (("없는 컷", lambda: E.edit("S99", 99, "x")),
                       ("없는 대사 줄", lambda: E.edit("S99", 1, "x", turn=5))):
            try:
                fn()
                ck(f"{nm} 은 막는다", False, "그냥 넘어갔다")
            except SystemExit as e:
                ck(f"{nm} 은 막는다", "❌" in str(e), str(e)[:60])
    finally:
        E.story_path = real

    print("\n③ 단추 → 창구 → 워크플로 → 도구가 이어지는가")
    js = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
    yml = (ROOT / ".github" / "workflows" / "story-edit.yml").read_text(
        encoding="utf-8")
    ck("화면에 [고치기] 단추가 있다", "editLine(" in js and ">고치기<" in js)
    ck("고칠 말을 물어본다", "function editLine" in js and "prompt(" in js)
    ck("누르기 전에 전·후를 보여 주고 물어본다",
       re.search(r"function editLine[\s\S]*?'전: '[\s\S]*?'후: '[\s\S]*?confirm\(",
                 js) is not None)
    ck("값이 0원이라고 화면에 적혀 있다",
       re.search(r"function editLine[\s\S]*?값 0원", js) is not None)
    ck("창구가 있다", "'/api/edit-line'" in js)
    api = (re.search(r"if \(url\.pathname === '/api/edit-line'[\s\S]*?\n      \}",
                     js) or [""])[0]
    ck("사건·컷 번호를 확인한다",
       "^S" + chr(92) + "d{1,4}$" in api
       and "^" + chr(92) + "d{1,3}$" in api)
    ck("빈 글은 안 보낸다", "고칠 말이 비어 있습니다" in api)
    ck("너무 긴 글도 막는다", "200자까지" in api)
    ck("워크플로를 부른다", "story-edit.yml/dispatches" in api)
    for k in ("sid", "cut", "turn", "text"):
        ck(f"워크플로가 '{k}' 를 받는다", re.search(rf"^      {k}:", yml, re.M))
    ck("워크플로가 그 도구를 부른다", "tools/edit_line.py" in yml)
    ck("고치고 나면 저장한다", "tools/push.sh" in yml)
    # ⚠️ 시작만 시키고 끝내면 손님은 됐는지 안 됐는지 모른다 (2026-09-04)
    ck("끝까지 지켜보고 알려 준다",
       re.search(r"function editLine[\s\S]*?watchRun\('story-edit\.yml'", js)
       is not None)
    ck("실패하면 까닭을 화면에 적는다",
       re.search(r"function editLine[\s\S]*?showErr\([^)]*고치지 못했습니다",
                 js) is not None)

    print("\n④ 이 길에서 돈이 안 나가는가")
    ck("워크플로가 모델 열쇠를 안 쓴다",
       "GEMINI_API_KEY" not in yml and "ANTHROPIC" not in yml)
    ck("도구가 모델을 안 부른다",
       not re.search(r"import (claude|veo|tts)\b",
                     (ROOT / "tools" / "edit_line.py").read_text(encoding="utf-8")))
    ck("화면에도 0원이라고 적혀 있다", "값 0원입니다" in js)

    print("\n⑤ 편에 붙은 글은 **모두** 고칠 길이 있는가")
    # ⭐⭐ 2026-09-10 — S92 2편에서 났다. 나레이션은 판결문에 맞춰 고쳤는데
    #    화면 제목(card)은 「어머니의 위자료 7억」 이 그대로 남아, 같은 편에서
    #    화면 글자와 나레이션이 **서로 다른 말**을 했다 (판결문에 '위자료' 는
    #    한 번도 안 나온다). 까닭은 단순했다 — 제목(--title)만 고칠 수 있고
    #    화면 제목은 고칠 손잡이가 아예 없었다.
    # ⚠️ 항목 목록을 손으로 적지 않는다. **대본이 실제로 들고 있는 것**에서
    #    뽑는다 — 나중에 편에 새 글칸이 생기면 손잡이를 달기 전까지 여기서
    #    걸린다 (손으로 적어 두면 조용히 또 빠진다).
    src = (ROOT / "tools" / "edit_line.py").read_text(encoding="utf-8")
    KNOB = {"yt_title": "--title", "card": "--card"}
    for k, v in fake_story()["parts"][0].items():
        if k in ("no", "cuts"):                  # 뼈대다 — 보는 사람에게 안 뜬다
            continue
        flag = KNOB.get(k)
        ck(f"편의 '{k}' 를 고칠 손잡이가 있다", bool(flag),
           "이 글칸은 대본을 통째로 다시 뽑아야만 고쳐진다 (약 2,100원)")
        if not flag:
            continue
        ck(f"{flag} 를 인자로 받는다", f'ap.add_argument("{flag}"' in src)
        ck(f"{flag} 가 main 에서 갈라진다",
           re.search(rf"a\.{flag[2:]} is not None", src) is not None)
        ck(f"{flag} 가 part[{k!r}] 을 실제로 바꾼다",
           re.search(rf'part\["{k}"\] = ', src) is not None)

    # 진짜로 돌려 본다 — 그 편만 바뀌고 나머지 편은 그대로여야 한다
    doc0 = fake_story()
    tmp2 = Path(tempfile.mkdtemp())
    p2 = tmp2 / "S99.story.json"
    p2.write_text(json.dumps(doc0, ensure_ascii=False, indent=1), encoding="utf-8")
    real2 = E.story_path
    E.story_path = lambda sid: p2
    # ⚠️ 손잡이가 아예 없을 때 여기서 터지면(AttributeError) 뒤 검사가 못 돈다.
    #    빨간불은 나야 하되 **깨끗이** 나야 한다 — 없으면 한 줄로 적고 건너뛴다.
    if not hasattr(E, "edit_card"):
        ck("화면 제목을 고치는 함수가 있다", False, "edit_card 가 없다")
        E.story_path = real2
        print("\n" + "─" * 60)
        print(f"❌ 대본 한 줄 고치기: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    try:
        d3, _p3, w3, _l3, why3 = E.edit_card("S99", 2, "윗줄 고침|아랫줄 고침")
        ck("화면 제목 두 줄이 바뀐다",
           d3["parts"][1]["card"] == ["윗줄 고침", "아랫줄 고침"])
        ck("다른 편 화면 제목은 그대로다",
           d3["parts"][0]["card"] == doc0["parts"][0]["card"]
           and d3["parts"][2]["card"] == doc0["parts"][2]["card"])
        ck("무엇이 어떻게 바뀌었는지 알려 준다", any("→" in x for x in w3), str(w3))
        ck("규격에 걸리지 않는다", not why3, str(why3[:2]))
        for nm, arg in (("두 줄이 아니면", "한 줄뿐"),
                        ("빈 줄이 섞이면", "윗줄|")):
            try:
                E.edit_card("S99", 2, arg)
                ck(f"{nm} 막는다", False, "그냥 넘어갔다")
            except SystemExit as e:
                ck(f"{nm} 막는다", "❌" in str(e), str(e)[:60])
        try:
            E.edit_card("S99", 99, "가|나")
            ck("없는 편은 막는다", False, "그냥 넘어갔다")
        except SystemExit as e:
            ck("없는 편은 막는다", "❌" in str(e), str(e)[:60])
    finally:
        E.story_path = real2

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 대본 한 줄 고치기: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 대본 한 줄 고치기: 그 줄만 · 규격을 지키고 · 값 0원")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
