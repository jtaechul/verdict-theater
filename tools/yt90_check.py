#!/usr/bin/env python3
"""90초 한 편을 유튜브에 올리는 길이 성한가 (값 0원 · 인터넷 0회)

    python3 tools/yt90_check.py

⚠️⚠️ 여기서 지키려는 것은 딱 하나다 —
   **화면에서 본 글과 실제로 올라가는 글이 같아야 한다.**
   제목을 고쳤는데 다른 글이 올라가면 무엇이 올라갔는지 아무도 모르고,
   유튜브는 되돌리기가 번거롭다. 그래서 글을 만드는 자리를 **한 곳**으로
   묶어 두고, 그 묶음이 풀리지 않았는지 매번 본다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import ytmeta                                                # noqa: E402

BAD = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + ("" if ok else f"  ({why})"))
    if not ok:
        BAD.append(name)


def main():
    print("⭐ 90초 한 편 유튜브 올리기 점검 (값 0원)\n")
    doc = json.loads((ROOT / "data" / "series" / "S90.json")
                     .read_text(encoding="utf-8"))
    m = ytmeta.meta90(doc)

    print("① 올릴 글이 유튜브 규격에 맞는가")
    ck(f"제목이 100자 안이다 ({len(m['title'])}자)", 0 < len(m["title"]) <= 100)
    ck("제목에 #shorts 가 있다 (쇼츠로 잡힌다)", "#shorts" in m["title"].lower())
    # 16화용 build() 는 "(3화)" 를 붙인다. 한 편짜리에 붙으면 거짓말이 된다
    ck("제목에 몇 화인지 안 붙는다 (한 편짜리다)",
       not re.search(r"\(\d+\s*화", m["title"]), m["title"])
    ck("설명이 비어 있지 않다", len(m["description"]) > 50)
    ck("설명이 4900자 안이다", len(m["description"]) <= 4900)
    ck(f"해시태그가 있다 ({len(m['tags'])}개)", 1 <= len(m["tags"]) <= 15)
    ck("해시태그에 # 이 안 붙어 있다 (유튜브가 알아서 붙인다)",
       not any(t.startswith("#") for t in m["tags"]))
    ck("설명에 '매일 한 편씩' 같은 거짓말이 없다",
       "매일 한 편" not in m["description"])
    ck("기본은 비공개다 (실수로 공개되지 않게)", m.get("privacy") == "private")

    print("\n② 글을 만드는 자리가 한 곳인가")
    js = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
    # 관리자 페이지가 제 나름대로 글을 지어내면 화면과 실제가 갈라진다
    ck("관리자 페이지가 90초 편 글을 따로 지어내지 않는다",
       not re.search(r"function\s+yt90\s*\(", js),
       "worker.js 에 글 만드는 함수가 생겼다 — 언젠가 두 글이 갈라진다")
    ck("관리자 페이지는 지어 둔 글을 읽는다",
       "data/series/S90.meta.json" in js)
    # ⚠️ 영상을 만들기 전에도 칸이 떠야 한다. 릴리스에만 기대면 처음 쓰는
    #    손님에게는 유튜브 칸이 아예 안 보인다 (실제로 그랬다).
    made = ROOT / "data" / "series" / "S90.meta.json"
    ck("올릴 글이 저장소에 지어져 있다 (영상 안 만들어도 뜬다)", made.exists())
    if made.exists():
        got = json.loads(made.read_text(encoding="utf-8"))
        ck("지어 둔 글이 지금 대본과 같다", got.get("title") == m["title"],
           "python3 tools/build_short90.py 를 다시 돌리십시오")

    print("\n③ 만들 때 글도 같이 보관하는가")
    mk = (ROOT / ".github" / "workflows" / "short90.yml").read_text(encoding="utf-8")
    ck("영상을 보관할 때 meta.json 도 같이 보관한다",
       "short90-S90 meta.json" in mk,
       "안 보관하면 관리자 페이지가 올릴 글을 못 읽는다")

    print("\n④ 올리는 워크플로")
    up = (ROOT / ".github" / "workflows" / "short90-upload.yml")
    ck("올리는 워크플로가 있다", up.exists())
    if up.exists():
        t = up.read_text(encoding="utf-8")
        ck("단추로만 돈다 (밀기만 해도 올라가면 큰일이다)",
           "workflow_dispatch" in t and "\n  push:" not in t)
        ck("고치신 글을 먼저 쓴다 (fetch_meta90)", "fetch_meta90.py" in t)
        # ⚠️ 2026-08-31 — 글 한 장 만들자고 영상 만드는 모듈(PIL 이 필요하다)을
        #    통째로 불렀다가 죽었다. 올릴 글은 이미 지어져 있으니 그냥 읽는다.
        fm = (ROOT / "tools" / "fetch_meta90.py").read_text(encoding="utf-8")
        # ⚠️ 주석에 적힌 것은 안 센다. 예전에 blob_auth_check 에서 똑같이
        #    "설명만 남고 코드가 빠진" 꼴을 놓쳤다 — 그때 배운 것을 여기도 쓴다.
        code = "\n".join(l for l in fm.splitlines()
                         if not l.lstrip().startswith("#"))
        code = re.sub(r'"""[\s\S]*?"""', "", code)          # 머리말도 뺀다
        ck("올릴 글을 만들려고 영상 모듈을 부르지 않는다",
           "src/short90.py" not in code and "import short90" not in code,
           "PIL 이 없는 자리에서 죽는다 — 지어 둔 글을 읽으십시오")
        ck("지어 둔 글을 읽는다", "S90.meta.json" in fm)
        ck("영상을 보관함에서 꺼내 온다", "short90-S90 short.mp4" in t)
        ck("upload.py series 로 올린다", "upload.py series S90" in t)
        ck("기본값이 비공개다", "default: '비공개 (나만 보기)'" in t)
        ck("연습(올리지 않고 확인만)을 고를 수 있다", "연습 (올리지 않고 확인만)" in t)
        # ⚠️ 저장소에 이미 적힌 교훈 — 워크플로 안에 파이썬을 박으면 YAML 이 깨진다
        ck("워크플로 안에 파이썬을 박지 않았다",
           "python3 -c \"\n" not in t, "파일로 빼십시오")
        import yaml
        yaml.safe_load(t)
        ck("YAML 이 성하다", True)

    print("\n" + "─" * 60)
    if BAD:
        print("❌ 걸린 것:")
        for b in BAD:
            print("     " + b)
        return 1
    print("✅ 유튜브 올리기 점검: 전부 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
