#!/usr/bin/env python3
"""올릴 글(제목·설명·해시태그)을 준비한다.

    python3 tools/fetch_meta90.py '<주소 또는 빈칸>' build/s90/meta.json

⚠️⚠️ 화면에서 본 글과 실제로 올라가는 글이 **반드시 같아야 한다.**
   손님이 관리자 페이지에서 제목을 고쳤는데 다른 글이 올라가면, 무엇이
   올라갔는지 아무도 모른다. 그래서 고친 글이 있으면 **그것이 이긴다.**
   없을 때만 대본과 함께 지어 둔 글(data/series/S90.meta.json)을 쓴다.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NEED = ("title", "description", "tags")


def _open(url):
    # 보관함은 암호를 받는다 (tools/fetch_cards.py 와 같은 길)
    req = urllib.request.Request(url, headers={
        "User-Agent": "verdict-theater",
        "x-vt-pass": os.environ.get("ADMIN_PASS", ""),
    })
    return urllib.request.urlopen(req, timeout=120)


def show(out):
    """무엇이 올라가는지 화면에 적는다 — 올린 뒤에 "뭐가 올라갔지" 하면 늦다."""
    try:
        m = json.loads(Path(out).read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return
    print(f"\n  제목     {m.get('title', '')}")
    print("  해시태그 " + " ".join("#" + t for t in (m.get("tags") or [])))
    print(f"  설명     {len(m.get('description') or '')}자")


def main():
    raw = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "build/s90/meta.json")
    out.parent.mkdir(parents=True, exist_ok=True)

    got = None
    if raw and raw not in ("{}", "null"):
        try:
            if raw.startswith("http"):
                with _open(raw) as r:
                    got = json.loads(r.read().decode("utf-8"))
            else:
                got = json.loads(raw)
        except Exception as e:                               # noqa: BLE001
            print(f"  ⚠️ 고치신 글을 못 읽었다 ({str(e)[:80]}) — 대본에서 만든다")
            got = None

    if isinstance(got, dict) and all(got.get(k) for k in NEED):
        got.setdefault("sid", "S90")
        got.setdefault("ep", 0)
        out.write_text(json.dumps(got, ensure_ascii=False, indent=1) + "\n",
                       encoding="utf-8")
        print("■ 관리자 페이지에서 고치신 글을 그대로 씁니다")
        show(out)
        return 0

    # ⚠️⚠️ 2026-08-31 — 여기서 src/short90.py 를 불렀다가 **PIL 이 없어 죽었다.**
    #    글 한 장 만들자고 **영상 만드는 모듈을 통째로** 부른 것이 잘못이다
    #    (short90.py 는 맨 윗줄에서 그림 라이브러리를 부른다).
    #    이제 올릴 글은 대본을 지을 때 **미리 지어 저장소에 들어 있다.**
    #    그 파일을 그대로 쓴다 — 아무것도 안 깔아도 되고, 화면에 보이는
    #    글과 똑같은 글이 올라간다.
    made = ROOT / "data" / "series" / "S90.meta.json"
    if not made.exists():
        print("❌ 올릴 글이 없습니다 (data/series/S90.meta.json)\n"
              "   python3 tools/build_short90.py 로 대본을 다시 지으면 생깁니다")
        return 1
    print("■ 고치신 글이 없어 대본과 함께 지어 둔 글을 씁니다 (0원)")
    out.write_text(made.read_text(encoding="utf-8"), encoding="utf-8")
    show(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
