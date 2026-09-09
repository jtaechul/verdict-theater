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

    print("① 대본에 새 인물이 있으면 그 사람도 받는가")
    # 붙박이 대본 — 옛 다섯에 **없는** 사람들이 나온다
    doc = {"cuts": [{"n": 1, "who": ["아내", "시어머니"]},
                    {"n": 2, "who": ["아들"]},
                    {"n": 3, "who": []}],
           "people": {"공장장": {"sex": "남", "age": "60대"}}}
    got = FC.cast_of_doc(doc)
    for w in ("시어머니", "아들", "공장장"):
        ck(f"'{w}' 를 받는다", w in got, f"{sorted(got)}")
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

    print("\n④ 손이 고른 파일을 지우지 않는가")
    ck("이미 고른 파일이 있으면 다시 안 그린다",
       "!Object.keys(S90CARDS).length" in cuts_fn,
       "다시 그리면 손님이 고른 파일이 사라진다")

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
