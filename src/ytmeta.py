#!/usr/bin/env python3
"""⭐ 유튜브에 올릴 제목·설명·해시태그를 만든다. 0원 (모델을 안 부른다).

    python3 src/ytmeta.py S001 1                  화면에 보여만 준다
    python3 src/ytmeta.py S001 1 --out meta.json  파일로

왜 (2026-08-20 운영자 지시)
    "동영상 올릴 때 유튜브 쇼츠 영상, 제목이라든가 설명, 해시태그 아무것도
     안 들어가 있어."
    맞다. 쇼츠는 만들었는데 **올릴 때 쓸 글이 하나도 없었다.**

    대본에 이미 있는 것(후킹·제목·대사·사건)으로 **돈 안 쓰고** 만든다.
    대본에 `yt_title` 같은 칸이 있으면 그것을 먼저 쓴다(다음 대본부터).
    관리자 페이지에서 손으로 고칠 수 있으므로 여기서는 '쓸 만한 초안' 이면 된다.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERIES = ROOT / "data" / "series"

TITLE_MAX = 100          # 유튜브 제목 한도
DESC_MAX = 4900
TAG_MAX = 15

# 채널이 늘 달고 가는 것
BASE_TAGS = ["판결극장", "실화사연", "사연", "법률사연", "쇼츠드라마", "shorts"]

# ⚠️ 처음엔 제목을 낱말로 쪼개 태그를 만들었더니 `#바람난 #남편이 #빼돌린` 이
#    나왔다. 쓸 수 없다. 주제 낱말이 보이면 **제대로 된 태그**로 바꾼다.
TOPIC = [
    (("유류분", "상속", "상속재산", "한정승인"), ["유류분", "상속", "상속분쟁"]),
    (("내연", "불륜", "바람", "상간", "동거녀"), ["불륜", "외도", "상간소송"]),
    (("이혼", "위자료", "재산분할"), ["이혼", "위자료", "재산분할"]),
    (("보험금", "사망보험"), ["보험금분쟁"]),
    (("사기", "횡령", "빼돌", "가로챈"), ["재산다툼"]),
    (("층간", "이웃"), ["이웃분쟁"]),
    (("임대", "전세", "보증금"), ["부동산분쟁"]),
    (("폭행", "상해"), ["형사사건"]),
]


def topic_tags(*texts):
    """제목·사건 갈래에서 **쓸 만한** 태그를 뽑는다 (낱말 쪼개기 금지)."""
    blob = " ".join(clean(t) for t in texts)
    out = []
    for keys, tags in TOPIC:
        if any(k in blob for k in keys):
            for t in tags:
                if t not in out:
                    out.append(t)
    return out[:5]


def clean(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


def first_line(ep):
    """이 화에서 가장 센 대사 한 줄 (1컷 자막)."""
    cuts = ep.get("cuts") or []
    if not cuts:
        return ""
    s = clean(cuts[0].get("subtitle"))
    return clean(s.split(" / ")[0]).strip('"')


def make(doc, no):
    ep = next((e for e in doc.get("episodes") or []
               if int(e.get("no", 0)) == int(no)), None)
    if not ep:
        raise SystemExit(f"❌ {no}화가 없다")

    total = len(doc.get("episodes") or [])
    hook = clean(ep.get("hook")) or clean(ep.get("title"))
    line = first_line(ep)
    series = clean(doc.get("title"))

    # ── 제목 ──────────────────────────────────────────
    # 대본이 정해 준 것이 있으면 그것으로 (다음 대본부터 들어온다)
    title = clean(ep.get("yt_title"))
    if not title:
        title = hook or line or series
    # ⭐ 몇 화인지는 **우리가** 붙인다. 대본에 적지 말라고 일러 두었으므로
    #    yt_title 을 그대로 쓰는 경우에도 여기서 붙어야 한다.
    if f"({no}/" not in title:
        title = f"{title} ({no}/{total})"
    if "#shorts" not in title.lower():
        if len(title) + 8 <= TITLE_MAX:
            title += " #shorts"
    title = title[:TITLE_MAX]

    # ── 해시태그 ──────────────────────────────────────
    tags = [clean(x).lstrip("#") for x in (ep.get("yt_tags") or []) if clean(x)]
    if not tags:
        tags = topic_tags(doc.get("case_type"), series, hook, clean(ep.get("recap")))
    for b in BASE_TAGS:
        if b not in tags:
            tags.append(b)
    tags = tags[:TAG_MAX]

    # ── 설명 ──────────────────────────────────────────
    desc = clean(ep.get("yt_desc"))
    if not desc:
        recap = clean(ep.get("recap"))
        body = [f"[{series}] {no}화 / 전 {total}화"]
        if hook:
            body.append("")
            body.append(hook)
        if recap and int(no) > 1:
            body.append(f"(지난 이야기: {recap})")
        body += [
            "",
            "실제 판결문을 바탕으로 각색한 이야기입니다.",
            "등장인물의 이름·지명·금액은 모두 바꾸었습니다.",
            "",
            f"매일 한 편씩 올라갑니다. 다음 화도 놓치지 마세요.",
            "",
            " ".join("#" + t for t in tags),
        ]
        desc = "\n".join(body)
    desc = desc[:DESC_MAX]

    return {"sid": doc.get("series_id") or "", "ep": int(no),
            "title": title, "description": desc, "tags": tags,
            "privacy": "private"}


def load(sid):
    p = SERIES / f"{sid}.json"
    if not p.exists():
        raise SystemExit(f"❌ {sid} 대본이 없다")
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    a = argparse.ArgumentParser()
    a.add_argument("sid")
    a.add_argument("no")
    a.add_argument("--out", default="")
    g = a.parse_args()
    m = make(load(g.sid), g.no)
    print(f"제목 ({len(m['title'])}자)\n  {m['title']}\n")
    print(f"해시태그 {len(m['tags'])}개\n  " + " ".join("#" + t for t in m["tags"]) + "\n")
    print("설명\n" + "\n".join("  " + l for l in m["description"].split("\n")))
    if g.out:
        Path(g.out).parent.mkdir(parents=True, exist_ok=True)
        Path(g.out).write_text(json.dumps(m, ensure_ascii=False, indent=1),
                               encoding="utf-8")
        print(f"\n✅ {g.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
