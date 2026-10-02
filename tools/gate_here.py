#!/usr/bin/env python3
"""⭐ 작업 칸 심사 — **0원** (클로드가 이 작업 칸에서 직접 매긴다)

    python3 tools/gate_here.py export --topic "어르신 다섯" --out <폴더>  # 매길 판례를 꺼낸다
    python3 tools/gate_here.py merge <결과.json> [<결과.json> …]          # 매긴 결과를 대기열에 적는다

⭐⭐⭐ 2026-10-02 손님: "왜 또 돈들어? 그냥 니가 여기서 심사하고 올려 돈쓰지마"
   돈 드는 심사(src/gate.py · 제미나이 · 한 건 약 60원)와 **같은 채점표**
   (prompts/drama_gate.md), **같은 입력**(gate.case_for_prompt — 앞 9,000 · 뒤 3,000자),
   **같은 적기**(gate.apply_result)를 쓴다. 다른 것은 채점하는 곳 하나뿐이다 —
   대기열 줄에 gate_by 로 남긴다.

결과 파일: [{채점표 출력 형식 그대로}, …] 또는 {case_id: {…}, …}
  · total 은 일곱 항목 합으로 **다시 센다** (더하기를 틀려도 통과선이 흔들리지 않게)
  · pass 는 채점표 규칙대로 다시 정한다 (합 60 이상 그리고 즉시 탈락 사유 없음)
  · case_type 이 채점표 목록 밖이면 '기타' · one_line 은 50자에서 자른다
  · 이미 매긴 판례는 건드리지 않는다 (--force 로만)
"""
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import gate                                                   # noqa: E402
import topicmix                                               # noqa: E402

PROMPT = ROOT / "prompts" / "drama_gate.md"
SCORE_KEYS = ("conflict", "betrayal", "twist", "empathy", "catharsis", "amount", "detail")
SCORE_MAX = {"conflict": 20, "betrayal": 20, "twist": 15, "empathy": 15,
             "catharsis": 15, "amount": 8, "detail": 7}
REJECT_CODES = {"family_court", "tax_case", "criminal_sensitive", "famous_case",
                "no_person", "too_short", "sensitive"}
GATE_BY = "작업 칸(클로드) · 0원"


def case_types():
    """채점표의 case_type 목록 — 프롬프트 글에서 그대로 읽는다 (두 곳에 따로 적지 않는다)."""
    text = PROMPT.read_text(encoding="utf-8")
    m = re.search(r"case_type` 목록.*?```\n(.*?)```", text, re.S)
    return set(m.group(1).split()) if m else set()


def normalize(res, types):
    """채점 결과 하나를 채점표 규칙대로 다듬는다. 고칠 수 없으면 (None, 까닭)."""
    sc = res.get("scores") or {}
    try:
        scores = {k: max(0, min(SCORE_MAX[k], int(sc.get(k, 0)))) for k in SCORE_KEYS}
    except (TypeError, ValueError):
        return None, "점수가 숫자가 아니다"
    reject = [r for r in (res.get("reject") or []) if r in REJECT_CODES]
    total = sum(scores.values())
    ct = str(res.get("case_type") or "").strip()
    out = dict(res)
    out.update({
        "scores": scores,
        "total": total,
        "reject": reject,
        "pass": total >= gate.PASS_MARK and not reject,
        "case_type": ct if ct in types else "기타",
        "one_line": str(res.get("one_line") or "").strip()[:50],
        "amount_krw": int(res.get("amount_krw") or 0),
        "senior": bool(res.get("senior")),
    })
    return out, ""


def load_results(paths):
    rows = []
    for p in paths:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = [dict(v, case_id=k) for k, v in data.items()]
        rows.extend(data)
    return rows


def export(choice, out, limit):
    queue = gate.load_queue()
    want = set(topicmix.members(choice)) if choice else None
    todo = [c for c in queue if c.get("gate_score") is None
            and (want is None or (c.get("topic") or "") in want)]
    todo.sort(key=lambda c: -(c.get("machine_score") or 0))
    todo = todo[:limit] if limit else todo
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    index = []
    for c in todo:
        f = gate.CASES / f"{c['case_id']}.json"
        if not f.exists():
            continue
        case = json.loads(f.read_text(encoding="utf-8"))
        (out / f"{c['case_id']}.json").write_text(gate.case_for_prompt(case), encoding="utf-8")
        index.append({"case_id": c["case_id"], "topic": c.get("topic", ""),
                      "사건명": c.get("사건명", ""), "machine_score": c.get("machine_score")})
    (out / "_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n",
                                     encoding="utf-8")
    by = {}
    for r in index:
        by[r["topic"]] = by.get(r["topic"], 0) + 1
    print(f"매길 판례 {len(index)}건 → {out}  ({' · '.join(f'{t} {n}' for t, n in by.items())})")
    return 0


def merge(paths, force=False):
    queue = gate.load_queue()
    by_id = {str(c["case_id"]): c for c in queue}
    types = case_types()
    done, skipped, bad = [], [], []
    for res in load_results(paths):
        cid = str(res.get("case_id") or "")
        row = by_id.get(cid)
        if row is None:
            bad.append(f"{cid} 대기열에 없다")
            continue
        if row.get("gate_score") is not None and not force:
            skipped.append(cid)
            continue
        norm, why = normalize(res, types)
        if norm is None:
            bad.append(f"{cid} {why}")
            continue
        gate.apply_result(row, norm)
        row["gate_by"] = GATE_BY
        row["gate_at"] = date.today().isoformat()
        done.append(row)
    gate.save_queue(queue)

    by = {}
    for r in done:
        t = r.get("topic") or "(갈래 없음)"
        n, ok = by.get(t, (0, 0))
        by[t] = (n + 1, ok + (1 if r.get("gate_pass") else 0))
    print(f"매긴 것 {len(done)}건 · 통과 {sum(1 for r in done if r.get('gate_pass'))}건 "
          f"(값 0원 · {GATE_BY})")
    for t, (n, ok) in sorted(by.items(), key=lambda x: -x[1][1]):
        print(f"  {t:6s} {n:3d}건 매김 → 통과 {ok:3d}건")
    if skipped:
        print(f"  이미 매긴 것 {len(skipped)}건은 건드리지 않았다 (--force 로만)")
    for b in bad:
        print(f"  ⚠️ {b}")
    return 0 if done or not bad else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--topic", default="", help="갈래 또는 '어르신 다섯' (비우면 전부)")
    e.add_argument("--out", required=True)
    e.add_argument("--limit", type=int, default=0)
    m = sub.add_parser("merge")
    m.add_argument("files", nargs="+")
    m.add_argument("--force", action="store_true")
    a = ap.parse_args()
    if a.cmd == "export":
        return export(a.topic, a.out, a.limit)
    return merge(a.files, a.force)


if __name__ == "__main__":
    sys.exit(main())
