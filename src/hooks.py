#!/usr/bin/env python3
"""⭐ 이미 만든 시리즈의 **후킹 한 줄과 유튜브 제목만** 다시 뽑는다.

    python3 src/hooks.py S001            # 모델이 다시 뽑는다 (수십 원)
    python3 src/hooks.py S001 --free     # 0원 — 대사에서 규칙으로 뽑는다

왜 (2026-08-20 운영자 지시)
    "제목이랑 후킹 좀 더 자극적으로 뽑아. 자꾸 점잔 빼지 말고 선비처럼.
     신경을 자극하고 관심을 유도하고, 속이지 않는 범위 내에서 최대한
     과장되고 사람들이 유인되게끔."

    S001 은 `hook` 이 아예 비어 있어서 화면 맨 위에 화 제목이 그대로 올라갔다 —
    `집을 나가는 남편` `이혼 소송 기각`. 이건 목차지 후킹이 아니다.

    ⚠️ 이야기는 한 글자도 안 건드린다. 대본 전체를 다시 사면 수백 원이지만
       후킹만 뽑으면 수십 원이다. **컷 프롬프트는 모델에 안 보낸다.**
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import prompts                                              # noqa: E402
from claude import writer                                   # noqa: E402

SERIES = ROOT / "data" / "series"

HOOK_MAX = 22          # 화면 맨 위 한 줄 (넘으면 두 줄로 접혀 영상을 가린다)
YT_MAX = 40            # 유튜브 제목 ((n/16) · #shorts 는 우리가 붙인다)


def strip_len(t):
    return len(re.sub(r"\s+", " ", str(t or "")).strip())


def brief(doc):
    """모델에 보낼 것만 추린다 — 컷 프롬프트(영어 6줄)는 빼서 값을 아낀다."""
    out = {"title": doc.get("title") or "", "episodes": []}
    for e in doc.get("episodes") or []:
        out["episodes"].append({
            "no": e.get("no"),
            "title": e.get("title") or "",
            "recap": e.get("recap") or "",
            "lines": [c.get("subtitle") or "" for c in (e.get("cuts") or [])],
        })
    return json.dumps(out, ensure_ascii=False, indent=1)


# ── 0원 수리 ────────────────────────────────────────────────
# 모델을 안 부르고 대사에서 뽑는다. 모델만큼 좋지는 않지만
# 화 제목을 그대로 올리는 것보다는 훨씬 낫다.
DROP = ("당신", "그래", "아니", "왜", "뭐")


def punchy(sub):
    """자막 한 줄에서 가장 센 토막을 고른다."""
    parts = [p.strip().strip('"') for p in str(sub or "").split(" / ")]
    parts = [p for p in parts if p]
    if not parts:
        return ""
    # 숫자가 들어간 줄이 가장 세다 → 그 다음은 짧고 단정적인 줄
    num = [p for p in parts if re.search(r"\d|억|만 원|십 원|한 푼", p)]
    pool = num or parts
    pool = [p for p in pool if strip_len(p) <= HOOK_MAX] or pool
    return min(pool, key=lambda p: abs(strip_len(p) - 16))


def free(doc):
    """0원 — 각 화 후킹 컷의 센 대사를 따옴표째 후킹으로 쓴다."""
    n = 0
    for e in doc.get("episodes") or []:
        cuts = e.get("cuts") or []
        if not (e.get("hook") or "").strip() and cuts:
            p = punchy(cuts[0].get("subtitle"))
            if p:
                e["hook"] = f'"{p[:HOOK_MAX]}"'
                n += 1
        if not (e.get("yt_title") or "").strip():
            base = (e.get("hook") or "").strip('"') or (e.get("title") or "")
            ser = (doc.get("title") or "").strip()
            t = f"{ser} — {base}" if ser and strip_len(ser) + strip_len(base) + 3 <= YT_MAX \
                else base
            if t:
                e["yt_title"] = t[:YT_MAX]
                n += 1
    return n


# ── 모델 수리 ───────────────────────────────────────────────
def paid(doc, prefer=""):
    llm, who = writer(max_calls=2, prefer=(prefer or "gemini"))
    body = prompts.fill(prompts.load("series_hooks"), SERIES_JSON=brief(doc))
    got = llm.json(body, tier="pro", max_output_tokens=8192, temperature=0.95,
                   label="후킹", effort="high")
    by = {int(x.get("no", 0)): x for x in (got.get("episodes") or [])}
    n = 0
    for e in doc.get("episodes") or []:
        g = by.get(int(e.get("no", 0)))
        if not g:
            continue
        h = re.sub(r"\s+", " ", str(g.get("hook") or "")).strip()
        t = re.sub(r"\s+", " ", str(g.get("yt_title") or "")).strip()
        if h:
            e["hook"], n = h[:HOOK_MAX], n + 1
        if t:
            e["yt_title"], n = t[:YT_MAX], n + 1
    if (got.get("title") or "").strip():
        doc["title"] = got["title"].strip()
    return n, who


def main():
    a = argparse.ArgumentParser()
    a.add_argument("sid")
    a.add_argument("--free", action="store_true", help="0원 — 모델을 안 부른다")
    a.add_argument("--writer", default="", help="claude / gemini (기본: gemini)")
    a.add_argument("--dry", action="store_true", help="저장하지 않고 보여만 준다")
    g = a.parse_args()

    p = SERIES / f"{g.sid}.json"
    if not p.exists():
        print(f"❌ {g.sid} 대본이 없다", file=sys.stderr)
        return 2
    doc = json.loads(p.read_text(encoding="utf-8"))
    old = {e.get("no"): (e.get("hook") or e.get("title") or "")
           for e in (doc.get("episodes") or [])}

    if g.free:
        n = free(doc)
        who = "0원(대사에서 뽑음)"
    else:
        n, who = paid(doc, g.writer)

    print(f"{g.sid} — {who} · {n}곳을 새로 뽑았다\n")
    print(f"시리즈 제목: {doc.get('title')}")
    for e in doc.get("episodes") or []:
        no = e.get("no")
        print(f"\n{no:>2}화  전: {old.get(no)}")
        print(f"     후킹: {e.get('hook')}")
        print(f"     제목: {e.get('yt_title')}")

    if g.dry:
        print("\n(--dry 라 저장하지 않았다)")
        return 0
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💾 {p.name} 에 저장했다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
