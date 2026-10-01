#!/usr/bin/env python3
"""⭐ **그림 먼저 보기** — 컷 그림을 폰에서 보기 좋게 줄여 보관함에 올린다 (값 0원)

    python3 tools/stills_view.py S95 build/s90/stills            (만들고 올린다)
    python3 tools/stills_view.py S95 build/s90/stills --dry      (만들기만 — 시험용)

⭐⭐⭐ 2026-10-01 손님 승인 — 해양생물 쇼츠의 핵심 규칙 '이미지 먼저 검토, 영상은
   그 다음'. 2분 드라마는 단추 하나로 그림과 옴니 영상(약 7천 원)을 한꺼번에
   만들었다. 구도가 틀려도 영상값이 먼저 나갔다.
   → ① 그림만 만든다 → 관리자 페이지에서 **눈으로 본다** → 고칠 컷만 다시 그린다
     → ② 영상을 만든다. 이 도구가 ①과 '본다' 사이를 잇는다.

올리는 곳: 릴리스 stillsview-<사건>
   v-c01.jpg …   컷 그림 (폭 540 · 폰에서 가볍게)
   v-i05.jpg …   증거 확대 그림
   view.json     컷마다 무엇인지 (나레이션/대사 · 인물 · 구도 · 이웃 닮음)
⚠️ 옛 미리보기는 지운다 — 남겨 두면 컷이 줄었을 때 지난 그림이 섞여 보인다.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

WIDTH = 540
TAG = "stillsview-{sid}"


def kind_of(c):
    t = (c.get("turns") or [["나레이션", ""]])[0]
    return "나레이션" if t[0] == "나레이션" else t[0]


def make(sid, stills, out):
    """미리보기 파일들 + view.json 을 out 에 만든다. 돌려주는 것: 올릴 파일 이름들."""
    from PIL import Image
    import lookalike as LK
    doc = json.loads((ROOT / "data" / "series" / f"{sid}.json").read_text("utf-8"))
    stills, out = Path(stills), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        alike = json.loads((stills / "_alike.json").read_text("utf-8"))
    except Exception:                                        # noqa: BLE001
        alike = {}
    try:
        retake = json.loads((stills / "_retake.json").read_text("utf-8"))
    except Exception:                                        # noqa: BLE001
        retake = {}
    files, rows = [], []
    prev = None
    for c in doc.get("cuts") or []:
        n = int(c["n"])
        src = stills / f"c{n:02d}.png"
        row = {"n": n, "kind": kind_of(c), "who": c.get("who") or [],
               "text": str((c.get("turns") or [["", ""]])[0][1])[:80],
               "shot": (c.get("shot") or {}).get("key", ""),
               "file": "", "insert": "", "retake": int(retake.get(str(n)) or 0)}
        if src.exists():
            name = f"v-c{n:02d}.jpg"
            im = Image.open(src).convert("RGB")
            im = im.resize((WIDTH, int(im.height * WIDTH / im.width)))
            im.save(out / name, quality=82)
            files.append(name)
            row["file"] = name
            if prev is not None:
                v = LK.likeness(prev, src)
                row["like_prev"] = None if v is None else round(v, 2)
            prev = src
        else:
            prev = None
        a = alike.get(f"c{n:02d}")
        if a:
            row["redrawn"] = a
        ins = stills / f"i{n:02d}.png"
        if c.get("insert") and ins.exists():
            name = f"v-i{n:02d}.jpg"
            im = Image.open(ins).convert("RGB")
            im = im.resize((WIDTH, int(im.height * WIDTH / im.width)))
            im.save(out / name, quality=82)
            files.append(name)
            row["insert"] = name
            row["insert_word"] = c["insert"].get("word", "")
        rows.append(row)
    import cost
    import still as ST
    view = {"sid": sid, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cuts": rows, "same": LK.SAME,
            # 다시 그리기 한 장 값 — 화면이 세지 않고 이것을 읽는다
            "one_krw": round(cost.image_krw(ST.MODEL, ST.SIZE))}
    (out / "view.json").write_text(json.dumps(view, ensure_ascii=False, indent=1),
                                   encoding="utf-8")
    files.append("view.json")
    return files


def upload(sid, out, files):
    import release_file as RF
    tag = TAG.format(sid=sid)
    fail = 0
    for name in files:
        if RF.put(tag, name, str(Path(out) / name)) != 0:
            fail += 1
    RF.prune(tag, set(files))
    return fail


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if len(a) < 2:
        print(__doc__)
        return 2
    sid, stills = a[0].upper(), a[1]
    out = ROOT / "build" / "stillsview"
    files = make(sid, stills, out)
    print(f"■ 그림 미리보기 {len(files) - 1}장 — {out.relative_to(ROOT)}")
    if "--dry" in a:
        return 0
    bad = upload(sid, out, files)
    if bad:
        print(f"⚠️ 미리보기 {bad}장을 못 올렸습니다 — 관리자 페이지에서 일부가 안 보일 수 있습니다")
        return 1
    print(f"✅ 관리자 페이지에서 볼 수 있습니다 (보관함 {TAG.format(sid=sid)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
