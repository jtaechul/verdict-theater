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
# ⭐⭐⭐ 2026-09-06 손님: "다음화가 궁금하다면은 구독과 좋아요, 알림을 좀
#    설정하도록 유도하는 건 어떨까." 영상 끝 화면(short90.TAIL_SUB_*)과
#    **같은 말**을 쓴다 — 화면과 설명이 따로 놀면 안 된다.
CTA_NEXT = "다음 편이 궁금하시면 구독 · 좋아요 · 알림 설정을 해 두십시오."
CTA_LAST = "구독해 두시면 다음 사건을 놓치지 않습니다. 좋아요와 알림 설정도 부탁드립니다."

DESC_MAX = 4900
TAG_MAX = 15

# 채널이 늘 달고 가는 것
# ⭐ 2026-09-04 손님: "앞으로 해시태그에 실화사건, 사연극장 도 추가해줘"
# ⚠️ 이 목록을 고치면 **admin/worker.js 의 YT_BASE_TAGS 도 같이** 고쳐야 한다.
#    화면에서 본 해시태그와 실제로 올라가는 해시태그가 갈라지면 무엇이
#    올라갔는지 아무도 모른다. tools/pair_check.py 가 둘이 같은지 본다.
BASE_TAGS = ["판결극장", "사연극장", "실화사건", "실화사연",
             "사연", "법률사연", "쇼츠드라마", "shorts"]

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
    # ⚠️ 후킹에는 색 넣을 자리를 별표로 표시해 둔다 (`*15억*`).
    #    그건 **화면에 그릴 때만** 쓰는 표시라 유튜브 제목·설명에서는 뗀다.
    hook = clean(re.sub(r"\*([^*]+)\*", r"\1", str(ep.get("hook") or ""))) \
        or clean(ep.get("title"))
    line = first_line(ep)
    series = clean(doc.get("title"))

    # ── 제목 ──────────────────────────────────────────
    # 대본이 정해 준 것이 있으면 그것으로 (다음 대본부터 들어온다)
    title = clean(ep.get("yt_title"))
    if not title:
        title = hook or line or series
    # ⭐ 몇 화인지는 **우리가** 붙인다. 대본에 적지 말라고 일러 두었으므로
    #    yt_title 을 그대로 쓰는 경우에도 여기서 붙어야 한다.
    # ⭐⭐ 2026-08-24 — 예전엔 `(1/16)` 이었다. 그런데 처음 보는 사람에게
    #    "16편짜리"는 **분량 부담**으로 읽힌다(1화 이탈률 60%를 파고들다 나온 것).
    #    순서는 알려 주되 총 편수는 안 보이게 `(1화)` 로 바꾼다.
    if f"({no}화" not in title and f"({no}/" not in title:
        title = f"{title} ({no}화)"
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


# ── ⭐ 90초 한 편 (2026-08-31) ─────────────────────────────
#
#   16화짜리와 대본 모양이 다르다 — episodes 도 없고 몇 화도 없다.
#   그래서 위의 build() 를 그대로 못 쓴다. 다만 **한도·기본 태그·주제 태그**는
#   같은 것을 쓴다 (두 곳에 따로 적으면 언젠가 갈라진다).
def narr_lines(doc, n=3):
    """나레이션 컷에서 줄거리 몇 줄. 대본이 바뀌면 설명도 저절로 바뀐다."""
    out = []
    for c in doc.get("cuts") or []:
        if c.get("kind") == "나레이션" and clean(c.get("text")):
            out.append(clean(c["text"]))
        if len(out) >= n:
            break
    return out


def cuts_of(doc, part):
    """그 편에 들어가는 컷만."""
    a, b = part["cuts"]
    return [c for c in (doc.get("cuts") or []) if a <= c["n"] <= b]


def part_meta(doc, part, last=False):
    """한 **편**의 제목·설명·해시태그. 0원 (모델을 안 부른다).

    ⭐⭐ 2026-09-01 — 한 사건을 여러 편으로 나눠 올린다. 편마다 제목·설명이
       달라야 한다. 특히 **설명은 그 편에 나오는 나레이션**으로 짓는다 —
       3편 설명에 1편 줄거리가 붙으면 사람이 "이건 봤는데" 하고 넘긴다.
    ⚠️ 제목에 "2편" 을 안 쓴다. 제목은 *볼지 말지 정하는 자리*라, 번호가
       보이면 "1편부터 봐야 하나" 하고 넘긴다 (2026-09-01 손님과 확정).
       편 번호는 **영상 화면 안**에만 넣는다 — 거기는 이미 보는 사람만 본다.
    """
    series = clean(doc.get("title"))
    label = clean(doc.get("series_label")) or series
    sub = {"cuts": cuts_of(doc, part)}

    title = clean(part.get("yt_title")) or clean(doc.get("yt_title")) or series
    if "#shorts" not in title.lower() and len(title) + 8 <= TITLE_MAX:
        title += " #shorts"
    title = title[:TITLE_MAX]

    tags = [clean(x).lstrip("#") for x in (part.get("tags")
                                          or doc.get("yt_tags") or []) if clean(x)]
    if not tags:
        tags = topic_tags(series, clean(doc.get("hook")),
                          " ".join(narr_lines(sub, 4)))
    for b in BASE_TAGS:
        if b not in tags:
            tags.append(b)
    tags = tags[:TAG_MAX]

    body = [clean(part["card"][0]) + ", " + clean(part["card"][1]), ""]
    body += narr_lines(sub, 2)
    body += ["", "법원은 어떻게 판단했을까요.", "", f"「{label}」"]
    # ⭐⭐⭐ 2026-09-06 손님: "다음화가 궁금하다면은 구독과 좋아요, 알림을 좀
    #    설정하도록 유도하는 건 어떨까." 영상 끝 화면(short90.end_card)에도
    #    같은 말을 띄운다 — 화면과 설명이 따로 놀면 안 된다.
    #    ⚠️ 마지막 편에는 "다음 편" 이라고 하지 않는다 (없는 편을 기다리게 된다).
    body += ["", CTA_LAST if last else CTA_NEXT]
    body += [
        "",
        "실제 판결을 바탕으로 각색한 이야기입니다.",
        "등장인물의 이름과 지명은 바꾸었고, 판사의 실명은 밝히지 않습니다.",
        "",
        " ".join("#" + t for t in tags),
    ]
    desc = "\n".join(body)[:DESC_MAX]

    return {"sid": doc.get("sid") or "S90", "part": part["no"],
            "title": title, "description": desc, "tags": tags,
            "card": list(part["card"]), "label": label,
            "privacy": "private"}


def _last(doc):
    """마지막 편 번호 (없으면 0)."""
    nos = [int(p.get("no") or 0) for p in (doc.get("parts") or [])]
    return max(nos) if nos else 0


def meta90(doc):
    """사건 하나의 **편별** 올릴 글. 편 수는 대본이 정한다 (2편이든 4편이든).

    ⚠️ 예전에는 한 편짜리라 낱개(dict)를 냈다. 지금은 편이 여럿이라 목록을
       내되, 모양을 알아보기 쉽게 {sid, parts:[...]} 로 감싼다.
    """
    return {"sid": doc.get("sid") or "S90",
            "label": clean(doc.get("series_label")) or clean(doc.get("title")),
            "parts": [part_meta(doc, p, last=(int(p.get("no") or 0) == _last(doc)))
                      for p in (doc.get("parts") or [])]}
