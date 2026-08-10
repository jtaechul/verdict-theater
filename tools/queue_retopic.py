#!/usr/bin/env python3
"""이미 받아 둔 판결문을 **다시 채점한다.** 값 0원 (인터넷도 안 쓴다).

    python3 tools/queue_retopic.py --check   # 어떻게 바뀌는지만 본다
    python3 tools/queue_retopic.py           # 실제로 고친다

왜 (2026-08-10 손님: "소재 대기열에는 내가 원하지 않는 것만 띄워놓고 이렇게 하잖아")
    걸러내는 기준을 고칠 때마다, **예전에 받아 둔 것은 옛 기준 그대로 남는다.**
    그러면 화면에는 계속 엉뚱한 것이 뜬다. 판결문은 이미 저장소에 있으므로
    다시 받을 필요 없이 그 파일만 다시 읽어 채점하면 된다 — 그래서 값이 0원이다.

하는 일
    · 갈래(상속·불륜…)를 찾은 낱말에서 채워 넣는다
    · 그 갈래 낱말이 본문에 하나도 없으면 → 대기열에서 빼서 rejected.json 으로 옮긴다
      ('낱말만 스치고 지나간' 엉뚱한 사건. 예: '부정한 행위' 한 마디 나온 임금 사건)
    · 남은 것은 지금 기준으로 점수를 다시 매긴다

⚠️ 이미 살펴본 것(gate_score 가 있는 것)은 건드리지 않는다. 돈 들여 평가한 결과다.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from collect import TOPIC_OF, topic_hits, real_topic, score  # noqa: E402

CASES = ROOT / "data" / "cases"
QUEUE = ROOT / "state" / "queue.json"
REJECTED = ROOT / "state" / "rejected.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="고치지 않고 결과만 본다")
    a = ap.parse_args()

    if not QUEUE.exists():
        print("대기열이 없습니다.")
        return 0
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    today = date.today()

    keep, drop, rescored, missing = [], [], 0, 0
    seen_no = set()   # 이미 남기기로 한 판결의 사건번호 (중복 판결 제거용)
    for c in queue:
        # 이미 살펴본 것은 그대로 둔다 (돈 들여 평가한 결과)
        if c.get("gate_score") is not None:
            keep.append(c)
            continue

        topic = c.get("topic") or TOPIC_OF.get(c.get("query", ""), "")
        c["topic"] = topic

        f = CASES / f"{c.get('case_id')}.json"
        if not f.exists():
            missing += 1
            keep.append(c)
            continue
        try:
            case = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            keep.append(c)
            continue

        body = case.get("판례내용", "")
        if not topic_hits(body, topic):
            c["drop_why"] = f"{topic} 사건이 아님(낱말만 스침)"
            drop.append(c)
            continue

        # 사건명까지 보고 진짜 갈래를 정한다. 낱말이 있어도 다툼이 딴 것이면 뺀다.
        t2 = real_topic(case, topic)
        if not t2:
            c["drop_why"] = f"{topic} 사건이 아님(다툼은 딴 것)"
            drop.append(c)
            continue
        if t2 != topic:
            c["topic"] = topic = t2      # 예: 불륜이 배경인 유류분 판결 → 상속으로 옮긴다

        # 같은 판결이 일련번호만 달라 두 번 있는 것을 뺀다 (실측: 2012르3746)
        no = (case.get("사건번호") or "").strip()
        if no and no in seen_no:
            c["drop_why"] = "같은 판결 중복"
            drop.append(c)
            continue
        if no:
            seen_no.add(no)

        old = c.get("machine_score")
        pts, _ = score(case, today, topic)
        if pts != old:
            c["machine_score"] = pts
            rescored += 1
        keep.append(c)

    keep.sort(key=lambda c: (c.get("gate_score") or 0, c.get("machine_score") or 0),
              reverse=True)

    print(f"대기열 {len(queue)}건")
    print(f"  · 갈래가 안 맞아 뺄 것   {len(drop)}건")
    print(f"  · 점수를 다시 매긴 것    {rescored}건")
    print(f"  · 판결문 파일이 없는 것  {missing}건 (그대로 둡니다)")
    print(f"  → 남는 것 {len(keep)}건")

    by = {}
    for c in keep:
        t = c.get("topic") or "(갈래 없음)"
        by[t] = by.get(t, 0) + 1
    print("\n갈래별로 남는 건수")
    for t, n in sorted(by.items(), key=lambda x: -x[1]):
        print(f"  {n:4d}건  {t}")

    if drop[:8]:
        print("\n빼는 것 (맛보기)")
        for c in drop[:8]:
            print(f"  {c.get('case_id'):>8}  {str(c.get('사건명',''))[:26]:28s} "
                  f"← '{c.get('query','')}'")

    if a.check:
        print("\n(--check 라서 고치지 않았습니다)")
        return 0

    if drop:
        old = json.loads(REJECTED.read_text(encoding="utf-8")) if REJECTED.exists() else []
        known = {str(c.get("case_id")) for c in old}
        add = [c for c in drop if str(c.get("case_id")) not in known]
        REJECTED.write_text(json.dumps(old + add, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    QUEUE.write_text(json.dumps(keep, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    print(f"\n고쳤습니다. 대기열 {len(keep)}건 · 옮긴 것 {len(drop)}건.")
    print("빼낸 것은 지운 게 아니라 옮긴 것이라, 다음 수집 때 다시 받지 않습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
