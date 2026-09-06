#!/usr/bin/env python3
"""⭐ 대본 **한 줄만** 고친다. 값 0원 (AI 를 안 부른다).

    python3 tools/edit_line.py --sid S91 --cut 18 --text "여자는 …"
    python3 tools/edit_line.py --sid S91 --cut 3 --turn 1 --text "…"   # 두 번째 줄
    python3 tools/edit_line.py --sid S91 --cut 7 --scene "the wife …"  # 화면 묘사

⭐⭐⭐ 2026-09-05 손님: **"이거는 지금 내가 대본을 바꿀 수가 없게 돼 있잖아."**
   맞는 지적이었다. 지금까지는 한 글자가 틀려도 [대본 다시 만들기](약 2,100원)
   말고는 길이 없었다. 27컷을 통째로 다시 뽑아야 하고, 새로 뽑아도 맞는다는
   보장이 없다. 실제로 이번 S91 컷18 이 판결문과 **방향이 거꾸로** 나왔다
   (상간녀가 "위자료를 더 올려 불렀다" → 실제는 반소로 3,000만 원을 청구).

값이 안 드는 까닭
  · 글은 우리가 넣는다 (AI 를 안 부른다)
  · 그림은 화면 묘사(scene)를 안 바꾸면 지문이 그대로라 **다시 안 그린다**
  · 목소리는 그 줄만 다시 만든다 (한 줄 약 10원)

⚠️ 고친 뒤 반드시 **규격 검사**를 다시 돌린다. 편당 글자 수(225자)를 넘기면
   60초를 넘고, 60초를 넘으면 쇼츠 피드가 안 태운다.
   ⚠️ `new=False` 로 본다 — 이미 만들어 둔 대본이라 새 규격을 뒤늦게 들이대면
      손대지도 않은 자리가 반려된다 (2026-09-04 에 정한 규칙).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import story90 as ST                                        # noqa: E402


def story_path(sid):
    return ROOT / "data" / "series" / f"{sid}.story.json"


def edit_title(sid, no, title):
    """편 **제목**(유튜브에 올라가는 제목)을 고친다. 값 0원.

    ⭐ 2026-09-06 — 제목은 컷 대사가 아니라 편(part)에 붙어 있어 따로 고친다.
       쇼츠는 제목이 '볼지 말지' 를 정하는 거의 유일한 자리다.
    """
    p = story_path(sid)
    if not p.exists():
        raise SystemExit(f"❌ {p.name} 이 없습니다")
    doc = json.loads(p.read_text(encoding="utf-8"))
    part = next((x for x in doc.get("parts") or []
                 if int(x.get("no") or 0) == int(no)), None)
    if part is None:
        raise SystemExit(f"❌ {sid} 에 {no}편이 없습니다")
    t = str(title).strip()
    if not t:
        raise SystemExit("❌ 제목이 비었습니다")
    if len(t) > 90:                       # 유튜브 상한 100자 · #shorts 자리를 남긴다
        raise SystemExit(f"❌ 제목이 {len(t)}자입니다 — 90자까지입니다")
    was = part.get("yt_title")
    part["yt_title"] = t
    return doc, p, [f"제목: 「{was}」 → 「{t}」"], [], ST.check(doc, new=False)


def edit(sid, n, text=None, turn=0, scene=None, who=None):
    """컷 하나를 고치고, 무엇이 어떻게 바뀌었는지 돌려준다."""
    p = story_path(sid)
    if not p.exists():
        raise SystemExit(f"❌ {p.name} 이 없습니다")
    doc = json.loads(p.read_text(encoding="utf-8"))
    cut = next((c for c in doc.get("cuts") or [] if c.get("n") == n), None)
    if cut is None:
        raise SystemExit(f"❌ {sid} 에 컷{n} 이 없습니다")

    was = []
    if text is not None:
        turns = [list(t) for t in (cut.get("turns") or [])]
        if not 0 <= turn < len(turns):
            raise SystemExit(f"❌ 컷{n} 에는 대사 줄이 {len(turns)}개뿐입니다 "
                             f"({turn} 번째 줄을 달라고 하셨습니다)")
        was.append(f"말  : 「{turns[turn][1]}」 → 「{text}」")
        turns[turn][1] = str(text).strip()
        cut["turns"] = turns
        cut["sec"] = round(ST.chars(cut) / 4.6 + 1.2, 1)
    if scene is not None:
        was.append(f"화면: 「{cut.get('scene')}」 → 「{scene}」")
        cut["scene"] = str(scene).strip()
    if who is not None:
        w = [x.strip() for x in str(who).split(",") if x.strip()]
        was.append(f"사람: {cut.get('who')} → {w}")
        cut["who"] = w
    if not was:
        raise SystemExit("❌ 고칠 것을 안 주셨습니다 (--text · --scene · --who)")

    # ⭐ 기계가 확실히 아는 것은 0원으로 손본다 (화자·사람 목록·연기 지시)
    log = ST.autofix(doc)
    # ⚠️ 규격을 다시 본다. 안 맞으면 **저장하지 않는다.**
    bad = ST.check(doc, new=False)
    return doc, p, was, log, bad


def rebuild(sid):
    """<SID>.json (그림·영상 지문) 을 다시 만든다. 값 0원."""
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "build_short90.py"),
                        sid], capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        raise SystemExit(f"❌ 다시 만들기 실패:\n{r.stdout[-800:]}{r.stderr[-800:]}")
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", required=True)
    ap.add_argument("--cut", type=int, default=0)
    ap.add_argument("--turn", type=int, default=0, help="한 컷에 두 줄이면 0/1")
    ap.add_argument("--text", default=None, help="새 대사")
    ap.add_argument("--scene", default=None, help="새 화면 묘사(영어)")
    ap.add_argument("--who", default=None, help="화면에 세울 사람 (쉼표로)")
    ap.add_argument("--title", default=None, help="편 제목 (유튜브에 올라가는 것)")
    ap.add_argument("--part", type=int, default=0, help="--title 을 고칠 편 번호")
    ap.add_argument("--dry", action="store_true", help="저장하지 않고 보기만")
    a = ap.parse_args()

    sid = a.sid.upper()
    if a.title is not None:
        doc, p, was, log, bad = edit_title(sid, a.part, a.title)
        head = f"■ {sid} {a.part}편"
    else:
        doc, p, was, log, bad = edit(sid, a.cut, a.text, a.turn, a.scene, a.who)
        head = f"■ {sid} 컷{a.cut}"
    print(head)
    for x in was:
        print(f"  {x}")
    for x in log:
        print(f"  · 기계가 손봤다 — {x}")

    for part in doc.get("parts") or []:
        aa, bb = part["cuts"]
        ch = sum(ST.chars(c) for c in doc["cuts"] if aa <= c["n"] <= bb)
        flag = "  ← 상한 넘음" if ch > ST.PART_CHARS else ""
        print(f"  {part['no']}편 {ch}자 ({ch * ST.SEC_PER_CHAR:.1f}초){flag}")

    if bad:
        print(f"\n❌ 규격에 안 맞습니다 ({len(bad)}군데) — **저장하지 않았습니다**")
        for b in bad[:10]:
            print(f"  · {b}")
        return 1
    if a.dry:
        print("\n(보기만 했습니다 — 저장하지 않았습니다)")
        return 0

    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                 encoding="utf-8")
    rebuild(sid)
    print(f"\n✅ {p.name} 와 {sid}.json 을 고쳤습니다 (값 0원)")
    print(f"   그림은 그대로 씁니다. 고친 컷의 **목소리만** 다시 만들면 됩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
