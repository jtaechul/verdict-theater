#!/usr/bin/env python3
"""작품 화면이 **사건마다 따로** 도는가 (값 0원 · 인터넷 0회)

    python3 tools/percase_check.py

⭐⭐⭐ 2026-09-02 손님: "지금 만들고 있는 영상을 들어가는 것도 지금 만들고
   있는 것만 볼 수 있게끔 되어 있어서 문제가 좀 있고."

   맞았다. 겉은 사건별로 나눠 놓고 **속은 아직 S90 에 묶여 있었다** —
     · 인물 그림 보관 자리가 'cards/S90-…' 로 박혀 있었다
     · 컷 영상 보관 자리가 'clips/S90-…' 로 박혀 있었다
     · 인물 이름 다섯(본처·남편·내연녀·딸·변호사)이 코드에 박혀 있었다
   그래서 새 사건을 열어 얼굴을 올려도 **S90 자리에 덮어쓰였고**, 사건마다
   다른 인물은 칸이 아예 안 떴다.

   이 검사가 하는 일은 하나다 — **다시 한 사건에 묶이지 않았는지** 보는 것.

⚠️ 주석에 적힌 것은 안 센다. 예전에 blob_auth_check 에서 "설명만 남고 코드가
   빠진" 꼴을 놓친 적이 있다 — 그때 배운 것을 여기도 쓴다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BAD = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + ("" if ok else f"  ({why})"))
    if not ok:
        BAD.append(name)


def code_only(js):
    """주석(//)을 걷어낸 코드만. 문자열 안의 // 는 여기서는 문제되지 않는다."""
    out = []
    for line in js.splitlines():
        t = line.lstrip()
        if t.startswith("//"):
            continue
        out.append(line)
    return "\n".join(out)


def main():
    print("⭐ 작품 화면이 사건마다 따로 도는가 (값 0원)\n")
    js = code_only((ROOT / "admin" / "worker.js").read_text(encoding="utf-8"))

    print("① 보관 자리에 사건 번호가 들어가는가")
    ck("인물 그림 자리가 사건별이다", "cards/${sid}-" in js,
       "cards/S90- 처럼 박아 두면 새 사건이 S90 자리를 덮어씁니다")
    ck("컷 영상 자리가 사건별이다", "clips/${sid}-" in js,
       "clips/S90- 처럼 박아 두면 새 사건이 S90 자리를 덮어씁니다")
    ck("인물 그림 자리에 S90 을 박아 두지 않았다", "cards/S90-" not in js)
    ck("컷 영상 자리에 S90 을 박아 두지 않았다", "clips/S90-" not in js)

    print("\n② 올릴 때 어느 사건인지 넘기는가")
    ck("인물 그림을 올릴 때 사건을 넘긴다", "upload-card?sid=" in js)
    ck("컷 영상을 올릴 때 사건을 넘긴다", "upload-cut?sid=" in js)
    ck("받는 쪽이 사건 번호를 읽는다 (인물)",
       re.search(r"upload-card'[\s\S]{0,200}?sidOf\(url\)", js) is not None)
    ck("받는 쪽이 사건 번호를 읽는다 (컷)",
       re.search(r"upload-cut'[\s\S]{0,200}?sidOf\(url\)", js) is not None)

    print("\n③ 인물 이름을 코드에 박아 두지 않았는가")
    # 사건마다 나오는 사람이 다르다. 대본에서 읽어야 한다.
    ck("화면이 인물을 대본에서 읽는다 (castOf)", "function castOf" in js,
       "다섯 이름을 박아 두면 다른 사건에서 엉뚱한 칸이 뜹니다")
    ck("화면이 그 목록을 실제로 쓴다", re.search(r"const cast = castOf\(\)", js)
       is not None)
    ck("받는 쪽도 대본에 나오는 사람인지로 본다",
       "S90_CARDS.indexOf(who) < 0" not in js,
       "이름을 목록으로 막으면 다른 사건 인물이 전부 튕깁니다")
    ck("모르는 이름도 자리 이름을 만들 수 있다 (whoKey)", "function whoKey" in js,
       "한글 이름은 보관함이 안 받습니다 — 영문 딱지가 필요합니다")

    print("\n④ 대본·영상·상태도 사건별인가")
    ck("대본을 사건 번호로 읽는다", "'data/series/' + sid + '.json'" in js)
    py = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
    ck("조립도 사건을 골라 읽는다 (VT_SID)", "VT_SID" in py)

    print("\n⑤ 얼굴이 사건 사이로 새지 않는가")
    # ⭐⭐⭐ 2026-09-05 손님: "에피소드에서 등장인물들을 좀 새로 생성하고
    #    싶거든? 전혀 다른 얼굴이 생성되도록."
    #    그때까지 얼굴 폴더도 보관 이름도 **S90 하나로 고정**이었다. 새 사건에
    #    새 얼굴을 넣으면 이미 올린 편의 얼굴까지 바뀐다.
    yml0 = (ROOT / ".github" / "workflows" / "short90.yml").read_text(encoding="utf-8")
    # ⚠️ 설명글(#)에 적힌 옛 이름에 속지 않는다 — **도는 줄**만 본다.
    #    (한 번 속았다: "cards90-S90 으로 고정이었다" 는 설명을 고장으로 셌다)
    yml = "\n".join(ln for ln in yml0.splitlines()
                    if not ln.lstrip().startswith("#"))
    rc = (ROOT / "tools" / "repo_cards.py").read_text(encoding="utf-8")
    ck("얼굴 보관 이름이 사건마다 다르다",
       "cards90-S90" not in yml and 'cards90-$S' in yml,
       "cards90-S90 으로 고정이면 앞 사건 얼굴을 받아 와 섞입니다")
    ck("얼굴 폴더를 사건 번호로 고른다", "def src_dir(sid)" in rc,
       "assets/cards/s90 하나만 보면 새 사건이 옛 얼굴을 씁니다")
    ck("전용 폴더가 없으면 기본 다섯으로 돌아간다", 'FALLBACK = "s90"' in rc)
    ck("워크플로가 사건 번호를 넘겨 준다",
       'repo_cards.py build/s90/cards "$S"' in yml)
    # 진짜로 갈리는지 돌려 본다 (0원)
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "repo_cards.py"),
                            td, "S91"], capture_output=True, text=True)
        ck("없는 사건은 기본 얼굴로 돌아간다고 말해 준다",
           "기본 얼굴" in r.stdout, r.stdout.strip()[:80])

    print("\n" + "─" * 60)
    if BAD:
        print("❌ 걸린 것:")
        for b in BAD:
            print("     " + b)
        return 1
    print("✅ 작품 화면: 사건마다 따로 돈다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
