#!/usr/bin/env python3
"""올릴 글(제목·설명·해시태그)을 준비한다.

    python3 tools/fetch_meta90.py '<쓰지 않는다>' build/s90/meta.json

⭐⭐⭐ 2026-09-06 — **올릴 글은 저장해 둔 것 한 곳에서만 온다.**

   그날 있었던 일: 손님이 [세 편 예약 공개로 올리기] 를 누르셨는데, 올라간
   세 편에 **옛 제목("…낯선 여자의 신음 소리 #shorts")과 옛 해시태그**가
   붙었다. 저장소의 글은 이미 새것으로 바뀌어 있었는데도 그랬다.

   까닭: 여기가 "관리자 화면이 보낸 글이 이긴다" 였다. 손님 폰의 화면이
   새로고침 안 된 옛 화면이라, 그 화면이 들고 있던 **옛 글**을 그대로 실어
   보냈고 그것이 저장된 새 글을 이겼다. 화면을 고쳐도 폰에 떠 있는 옛 화면은
   못 고친다 — 그러니 **화면을 믿는 구조 자체**를 버린다.

   → 이제 올릴 글은 `data/series/<사건>.meta.json` 하나뿐이다.
     제목을 고치려면 [② -2 대본 고치기] 를 쓴다. 그러면 저장된 글이 바뀌고,
     화면이든 유튜브든 같은 글을 본다.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# 되살아나면 안 되는 것들 (2026-09-06 — 검색량이 안 잡혀 뺀 태그들)
DEAD = ("shorts", "법률사연", "쇼츠드라마", "실화사연", "외도")


def blocked(meta):
    """올리면 안 되는 글인가 — 막을 까닭을 줄줄이 돌려준다.

    ⭐⭐⭐ 2026-09-06 — 마지막 문지기다. 글이 어디서 왔든(화면·저장된 파일·
       옛 보관함) **여기를 지나야 올라간다.** 그날 옛 글이 세 편이나 올라간
       뒤에야 알았다. 올리기 전에 막는 자리가 한 곳도 없었기 때문이다.
    """
    why = []
    for x in (meta.get("parts") or [meta]):
        head = f"{x.get('part') or ''}편 ".strip() + " " if x.get("part") else ""
        if "#" in str(x.get("title") or ""):
            why.append(f"{head}제목에 해시태그가 들어 있다 — {x.get('title')}")
        for t in (x.get("tags") or []):
            if str(t).strip().lower() in DEAD:
                why.append(f"{head}없앤 해시태그가 되살아났다 — #{t}")
    return why


def show(out):
    """무엇이 올라가는지 화면에 적는다 — 올린 뒤에 "뭐가 올라갔지" 하면 늦다."""
    try:
        m = json.loads(Path(out).read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return
    for x in (m.get("parts") or [m]):
        head = f"{x['part']}편 " if x.get("part") else ""
        print(f"\n  {head}제목     {x.get('title', '')}")
        print("  해시태그 " + " ".join("#" + t for t in (x.get("tags") or [])))
        print(f"  설명     {len(x.get('description') or '')}자")


def main():
    raw = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "build/s90/meta.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    if raw and raw not in ("{}", "null"):
        # ⚠️ 옛 화면이 아직 글을 실어 보낸다. 받되 **쓰지 않는다.**
        print("■ 화면이 보낸 글이 있지만 쓰지 않습니다 "
              "(옛 화면이면 옛 글이 올라갑니다 — 2026-09-06 사고)")

    sid = (os.environ.get("VT_SID") or "S90").strip().upper()
    made = ROOT / "data" / "series" / f"{sid}.meta.json"
    if not made.exists():
        print(f"❌ 올릴 글이 없습니다 ({made.relative_to(ROOT)})\n"
              "   python3 tools/build_short90.py 로 대본을 다시 지으면 생깁니다")
        return 1
    print(f"■ 올릴 글은 저장해 둔 {made.name} 하나만 씁니다 (0원)")
    out.write_text(made.read_text(encoding="utf-8"), encoding="utf-8")
    show(out)

    # ⭐ 마지막 문지기 — 옛 글이면 여기서 멈춘다 (올린 뒤엔 늦다)
    why = blocked(json.loads(out.read_text(encoding="utf-8")))
    if why:
        print("\n❌ 옛 글입니다 — 올리지 않고 멈춥니다")
        for w in why:
            print(f"   · {w}")
        print("\n   고치는 법: 관리자 페이지에서 [② -2 대본 고치기] 를 한 번\n"
              "   누르시면 올릴 글이 새로 지어집니다 (0원).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
