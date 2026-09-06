#!/usr/bin/env python3
"""⭐ **제목·해시태그가 조회수에 도움이 되는 모양인가.** 값 0원.

    python3 tools/tag_check.py

⭐⭐⭐ 2026-09-06 손님: **"자꾸 제목에다가 shorts라고 넣었는데 이거 의미가
   있는 거야? 조회수에 부정적인 영향을 미치는 것만 당장 없애고, 긍정적인
   영향을 미칠 만한 해시태그를 넣도록 코드 수정해."**

■ 제목의 #shorts — **의미 없다.**
   유튜브는 2022년부터 **세로 9:16 + 짧은 길이**로 쇼츠를 스스로 알아본다.
   제목에 적어도 하는 일이 없으면서 제목 100자 가운데 8자를 먹고, 쇼츠 화면
   에서 제목이 잘리는 자리를 잡아먹는다. → 뺐다.

■ 해시태그 — **실측 검색량으로 갈아 끼웠다** (vidIQ · 한국 · 2026-09-06)
       사연        666,590      막장드라마   66,734
       불륜         61,342      남편        41,276
       이혼사연     38,434      부부        38,272
       사이다사연   36,400      반전사연    35,163
   ⚠️ 그때까지 쓰던 것 가운데 **검색량이 안 잡히는 것** —
      법률사연 · 쇼츠드라마 · 실화사연 · 외도 · shorts → 뺐다.
      태그가 많다고 좋은 게 아니라, 뜻 없는 태그는 있는 것을 묽게 만든다.
   ⚠️ 사연극장·실화사건은 **남겼다** — 2026-09-04 에 손님이 넣으라고 하신
      것이다. 다만 뒤로 밀었다.
   ⚠️ 유튜브가 제목 위에 클릭할 수 있게 띄우는 것은 **앞의 세 개**뿐이다.
      그래서 가장 큰 것(사연)을 맨 앞에 둔다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import ytmeta as YM                                         # noqa: E402

bad = []

# 검색량이 안 잡혀 뺀 것들 — 다시 들어오면 안 된다
DEAD = ("법률사연", "쇼츠드라마", "실화사연", "외도", "shorts")
# 2026-09-04 손님이 넣으라고 하신 것 — 빼면 안 된다
KEEP = ("사연극장", "실화사건")


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name
          + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def fake_doc(hook="남편 차에 녹음기를 숨겼다"):
    cuts, ps = [], []
    for k in range(3):
        a = k * 9 + 1
        for n in range(a, a + 9):
            who = "나레이션" if (n - a) in (0, 4, 8) else "아내"
            cuts.append({"n": n, "kind": who, "who": [], "sec": 5.0,
                         "turns": [[who, "아내는 남편의 불륜을 알게 됐습니다."]],
                         "say": ["담담하게"], "scene": "a parked car at night"})
        ps.append({"no": k + 1, "cuts": [a, a + 8],
                   "card": ["첫 줄", "둘째 줄"],
                   "yt_title": "남편 차에 녹음기를 숨긴 아내가 들은 것은"})
    return {"sid": "S99", "title": "상간녀 위자료 사건", "series_label": "시험",
            "hook": hook, "cuts": cuts, "parts": ps}


def main():
    print("⭐ 제목·해시태그 (값 0원)\n")

    m = YM.meta90(fake_doc())["parts"][0]

    print("① 제목에서 #shorts 를 뺐는가")
    ck("제목에 #shorts 가 없다", "#shorts" not in m["title"].lower(), m["title"])
    ck("제목이 100자 안이다", len(m["title"]) <= 100, f"{len(m['title'])}자")
    for f, nm in ((ROOT / "src" / "ytmeta.py", "파이썬"),
                  (ROOT / "admin" / "worker.js", "관리자 화면")):
        t = f.read_text(encoding="utf-8")
        # 주석에 적힌 설명은 봐준다 — **붙이는 코드**만 없어야 한다
        code = "\n".join(l for l in t.splitlines()
                         if not l.strip().startswith(("#", "//")))
        ck(f"{nm}: 제목에 붙이는 코드가 없다",
           "+= ' #shorts'" not in code and '+= " #shorts"' not in code)

    print("\n② 검색량이 안 잡히던 태그를 뺐는가")
    got = set(m["tags"])
    ck("죽은 태그가 하나도 없다", not (got & set(DEAD)),
       " · ".join(sorted(got & set(DEAD))))
    ck("손님이 넣으라 하신 것은 남아 있다 (사연극장·실화사건)",
       all(k in got for k in KEEP), " · ".join(k for k in KEEP if k not in got))

    print("\n③ 큰 것이 맨 앞에 오는가 (제목 위에 뜨는 것은 앞의 셋뿐)")
    ck("맨 앞이 '사연' 이다 (한국 검색량 666,590 · 1위)",
       m["tags"][0] == "사연", " ".join(m["tags"][:3]))
    ck("두 번째·세 번째는 그 사건의 주제다",
       m["tags"][1] == "불륜" and m["tags"][2] == "이혼사연",
       " ".join(m["tags"][:3]))
    ck("실측으로 고른 태그가 들어 있다",
       {"사이다사연", "반전사연", "막장드라마"} <= got,
       " ".join(sorted({"사이다사연", "반전사연", "막장드라마"} - got)))
    ck("태그가 너무 많지 않다 (15개까지)", len(m["tags"]) <= 15,
       f"{len(m['tags'])}개")

    print("\n④ 화면과 파이썬이 같은 목록을 쓰는가 (한쪽만 고치는 사고 방지)")
    js = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
    for nm, want in (("LEAD", YM.LEAD_TAGS), ("BASE", YM.BASE_TAGS)):
        got_js = re.search(rf"const YT_{nm}_TAGS = \[([^\]]*)\]", js)
        lst = [x.strip().strip("'") for x in got_js.group(1).split(",")
               if x.strip()] if got_js else []
        ck(f"{nm} 목록이 같다 ({len(want)}개)", lst == list(want),
           f"화면 {lst} · 파이썬 {list(want)}")

    print("\n⑤ 사건 갈래가 달라도 맨 앞은 '사연' 인가")
    for hook, want in (("아버지 유산 32억을 형이 가로챘다", "유류분"),
                       ("전세 보증금을 못 받았다", "부동산분쟁")):
        mm = YM.meta90(fake_doc(hook))["parts"][0]
        ck(f"「{hook[:14]}…」 맨 앞이 '사연'", mm["tags"][0] == "사연",
           " ".join(mm["tags"][:3]))

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 제목·해시태그: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 제목·해시태그: 제목이 깨끗하고, 검색량 큰 것이 맨 앞에 온다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
