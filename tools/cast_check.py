#!/usr/bin/env python3
"""⭐ **등장인물이 사건마다 따라가는가.** 값 0원.

    python3 tools/cast_check.py

⚠️⚠️⚠️ 2026-09-09 손님: "매번 이렇게 등장인물이 고정되는 게 아닌데 매번
   똑같은 등장인물만 등록할 수 있도록 하는 오류가 발생하고 있어."

   맞았다. 같은 목록이 **세 곳에 따로 박혀** 있었고, 셋 다 옛 다섯이었다.
     ① admin/worker.js castOf() — 대본을 읽기 **전에** 칸을 그리고,
        대본이 도착해도 다시 안 그렸다. 그래서 언제나 옛 다섯이었다.
     ② tools/fetch_cards.py OK = ("본처","남편","내연녀","딸","변호사")
        — 그 다섯 말고는 올려도 "모르는 사람" 이라며 조용히 버렸다.
     ③ 이름이 두 벌이다 — 화면은 '아내', 카드 파일은 '본처'.
        ①을 고치는 순간 올린 얼굴이 엉뚱한 이름으로 저장될 뻔했다.

여기서 보는 것
   ① 대본에 새 인물이 있으면 **그 사람도** 받는가
   ② 이름 맞춤표가 세 곳에서 같은가 (한쪽만 고치면 얼굴이 새어 나간다)
   ③ 화면이 대본을 읽은 **뒤에** 인물 칸을 다시 그리는가
   ④ 손이 고른 파일이 있으면 다시 그리지 않는가 (고른 것이 지워지면 안 된다)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import fetch_cards as FC                                     # noqa: E402
import short90 as S9                                         # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def main():
    print("⭐ 등장인물이 사건마다 따라가는가 (값 0원)\n")

    print("① 컷에 서는 사람만 받는가")
    # 붙박이 대본 — 옛 다섯에 **없는** 사람이 컷에 서고,
    #              people 에는 **컷에 안 서는** 사람이 하나 들어 있다.
    doc = {"cuts": [{"n": 1, "who": ["아내", "시어머니"]},
                    {"n": 2, "who": ["아들"]},
                    {"n": 3, "who": []}],
           "people": {"공장장": {"sex": "남", "age": "60대"},
                      "아내": {}, "시어머니": {}, "아들": {}}}
    got = FC.cast_of_doc(doc)
    for w in ("시어머니", "아들"):
        ck(f"컷에 서는 '{w}' 를 받는다", w in got, f"{sorted(got)}")
    # ⚠️⚠️ 2026-09-10 손님이 바로 걸린 자리다. people 에만 있는 사람(S92 의
    #    어머니 — 나레이션에 네 번 나오지만 컷에는 한 번도 안 선다)까지 칸을
    #    만들었더니, 올리면 서버가 "누구 그림인지 알 수 없습니다" 로 거절했다.
    ck("컷에 안 서고 말로만 언급되는 '공장장' 은 안 받는다",
       "공장장" not in got, f"{sorted(got)} — 올릴 수 없는 칸이 생긴다")
    ck("'아내' 는 카드 이름 '본처' 로 바뀐다", "본처" in got and "아내" not in got,
       f"{sorted(got)}")
    ck("대본에 없는 사람은 안 받는다", "변호사" not in got, f"{sorted(got)}")
    ck("빈 대본이면 옛 다섯으로 물러선다",
       FC.cast_of_doc({}) == set(FC.FALLBACK))

    print("\n② 이름 맞춤표가 세 곳에서 같은가")
    js = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
    m = re.search(r"const CARD_NAME = \{([^}]*)\}", js)
    jsmap = dict(re.findall(r"'([^']+)'\s*:\s*'([^']+)'", m.group(1))) if m else {}
    ck("화면과 만들기(short90.ST_NAME)가 같다", jsmap == S9.ST_NAME,
       f"화면 {jsmap} · 만들기 {S9.ST_NAME}")
    ck("화면과 받는 쪽(fetch_cards.CARD_NAME)이 같다", jsmap == FC.CARD_NAME,
       f"화면 {jsmap} · 받는 쪽 {FC.CARD_NAME}")

    print("\n③ 화면이 대본을 읽은 뒤에 인물 칸을 다시 그리는가")
    ck("인물 칸이 제 자리(div)에 있다", "id=\"s90cast\"" in js.replace("'", '"'))
    cuts_fn = (re.search(r"async function s90Cuts\(\)[\s\S]*?\n}", js) or [""])[0]
    ck("대본을 읽은 뒤 그 칸을 다시 그린다",
       "s90cast" in cuts_fn and "short90Card()" in cuts_fn,
       "대본이 도착해도 옛 다섯이 화면에 남는다")
    ck("사건을 바꾸면 그린 기록을 지운다", "CASTDRAWN = ''" in js)

    print("\n④ 틀린 목록을 애초에 안 그리는가")
    # ⚠️⚠️⚠️ 2026-09-10 — 여기가 "이미 고른 파일이 있으면 다시 안 그린다" 였다.
    #    손님이 고른 파일을 지키려던 규칙인데, **바로 그것이 버그를 붙잡고
    #    있었다.** 딸 얼굴을 이미 올려 두셨더니 다시 안 그려서 틀린 다섯이
    #    화면에 그대로 남았다. 검사가 버그를 요구하고 있었던 것이다.
    #    → 고칠 자리는 다시 그리는 쪽이 아니라 **처음 그리는 쪽**이다.
    #      대본을 읽기 전에는 누가 나오는지 모르므로 아무 목록도 안 그린다.
    work = (re.search(r"function workScreen[\s\S]*?\n}", js)
            or re.search(r"h \+= '<div id=\"s90cast\"[\s\S]{0,400}", js) or [""])[0]
    ck("처음에는 등장인물 목록을 안 그린다 (불러오는 중만 띄운다)",
       "s90cast" in js and "등장인물을 읽는 중" in js,
       "대본을 읽기 전에 그리면 늘 옛 다섯이 뜬다")
    ck("첫 그림에 short90Card() 를 바로 안 넣는다",
       "'<div id=\"s90cast\">' + short90Card()" not in js
       and "'<div id=\'s90cast\'>' + short90Card()" not in js,
       "그 자리에서 그리면 대본이 없어 옛 다섯이 된다")
    ck("사람이 바뀌면 올린 얼굴이 있어도 다시 그린다",
       "!Object.keys(S90CARDS).length" not in cuts_fn,
       "얼굴을 하나라도 올려 두면 틀린 목록이 화면에 굳는다")
    ck("사람이 그대로면 다시 안 그린다 (고른 파일이 안 지워진다)",
       "now !== CASTDRAWN" in cuts_fn)

    print("\n⑤ 화면·서버·만들기가 **같은 기준**을 보는가")
    # ⚠️⚠️⚠️ 2026-09-10 — 여기가 틀어져서 손님이 걸렸다. 화면은 people 까지
    #    보고 칸을 만들었는데 서버는 who 만 인정했다. 화면이 만든 칸에 올리니
    #    "누구 그림인지 알 수 없습니다" 가 떴다. 기준이 하나여야 한다.
    cast_fn = (re.search(r"function castOf\(\)[\s\S]*?\n}", js) or [""])[0]
    srv_fn = (re.search(r"function castOfDoc\(doc\)[\s\S]*?\n}", js) or [""])[0]
    ck("서버에 셈하는 자리가 하나 있다 (castOfDoc)", srv_fn)
    for nm, fn in (("화면(castOf)", cast_fn), ("서버(castOfDoc)", srv_fn)):
        ck(f"{nm} 는 컷의 who 를 본다", ".who" in fn)
        ck(f"{nm} 는 people 을 안 본다", ".people" not in fn,
           "말로만 언급되는 사람까지 칸이 생겨 올릴 수 없게 된다")
    fcsrc = (ROOT / "tools" / "fetch_cards.py").read_text(encoding="utf-8")
    fcfn = (re.search(r"def cast_of_doc\(doc\)[\s\S]*?(?=\ndef )", fcsrc) or [""])[0]
    ck("받는 쪽(fetch_cards)도 people 을 안 본다", '"people"' not in fcfn,
       "화면·서버와 기준이 달라진다")
    # ⚠️ 얼굴을 워크플로로 넘기는 자리도 같은 셈을 써야 한다 — 여기가 옛 다섯
    #    이면 아버지·장남 얼굴을 올려도 워크플로에 아예 안 실린다.
    # ⚠️ 앞의 화면 쪽 fetch('/api/make-short90') 가 아니라 **서버 갈래**를 본다
    mk = (re.search(r"url\.pathname === '/api/make-short90'[\s\S]{0,1800}", js)
          or [""])[0]
    ck("워크플로로 넘길 때도 그 사건 사람 전부를 넘긴다",
       "castOfDoc(" in mk and "for (const k of S90_CARDS)" not in mk,
       "올린 얼굴이 워크플로에 안 실린다")
    # ⚠️⚠️ 2026-09-10 — 이 셈을 sid 가 정해지기 **전에** 두었다가 그 자리에서
    #    죽을 뻔했다(선언 전 사용). 순서를 못 박는다.
    ck("사건 번호(sid)를 정한 뒤에 얼굴을 셈한다",
       mk.index("const sid") < mk.index("castOfDoc(") if "const sid" in mk
       and "castOfDoc(" in mk else False,
       "sid 를 선언하기 전에 쓰면 그 자리에서 죽는다")

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 등장인물: {len(bad)}군데 — 사건이 바뀌어도 옛 사람만 뜬다")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 등장인물: 사건마다 대본을 따라간다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
