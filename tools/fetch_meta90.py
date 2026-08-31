#!/usr/bin/env python3
"""올릴 글(제목·설명·해시태그)을 준비한다.

    python3 tools/fetch_meta90.py '<주소 또는 빈칸>' build/s90/meta.json

⚠️⚠️ 화면에서 본 글과 실제로 올라가는 글이 **반드시 같아야 한다.**
   손님이 관리자 페이지에서 제목을 고쳤는데 다른 글이 올라가면, 무엇이
   올라갔는지 아무도 모른다. 그래서 고친 글이 있으면 **그것이 이긴다.**
   없을 때만 대본에서 만든다 (src/short90.py meta · 0원).
"""
import json
import os
import subprocess
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

    print("■ 고치신 글이 없어 대본에서 만듭니다 (0원)")
    r = subprocess.run([sys.executable, str(ROOT / "src" / "short90.py"), "meta"],
                       capture_output=True, text=True)
    print(r.stdout[-800:] or r.stderr[-400:])
    made = ROOT / "build" / "s90" / "meta.json"
    if not made.exists():
        print("❌ 올릴 글을 못 만들었습니다")
        return 1
    if made.resolve() != out.resolve():
        out.write_text(made.read_text(encoding="utf-8"), encoding="utf-8")
    show(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
