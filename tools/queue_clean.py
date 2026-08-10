#!/usr/bin/env python3
"""'쓰지 않기로 한' 판례를 대기열에서 **딴 곳으로 옮긴다.** 값 0원.

    python3 tools/queue_clean.py            # 옮긴다
    python3 tools/queue_clean.py --check    # 몇 건인지만 본다

왜 (2026-08-09 손님: "쓰지 않기로 함으로 구분된 판례는 삭제해도 되지 않아?")
    화면에서 치우는 것은 맞다. 그런데 **그냥 지우면 안 된다.**
    collect.py 는 `이미 대기열에 있는 case_id` 를 보고 같은 판례를 다시 안 받는다 —
    즉 **대기열이 '이미 본 것' 기억장치를 겸하고 있다.**
    지워 버리면 다음 수집 때 그 판례가 다시 들어오고, 3차 평가(LLM)를 **또** 돌려
    값이 나간다. 쓰지 않기로 한 것을 돈 주고 다시 판단하는 셈이다.

    그래서 지우지 않고 **state/rejected.json 으로 옮긴다.**
      · 대기열(화면)에서는 사라진다  → 손님이 원하신 것
      · '이미 본 것' 기억은 남는다    → 다시 안 받고, 값도 안 나간다
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "state" / "queue.json"
REJECTED = ROOT / "state" / "rejected.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="옮기지 않고 개수만 본다")
    a = ap.parse_args()

    if not QUEUE.exists():
        print("대기열이 없습니다.")
        return 0
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    old = json.loads(REJECTED.read_text(encoding="utf-8")) if REJECTED.exists() else []

    # 살펴본 결과 '쓰지 않기로 한' 것 = 점수는 매겼는데 통과 못 한 것
    out = [c for c in queue
           if c.get("gate_score") is not None and not c.get("gate_pass")]
    keep = [c for c in queue if c not in out]

    print(f"대기열 {len(queue)}건 · 쓰지 않기로 한 것 {len(out)}건 → 남는 것 {len(keep)}건")
    for c in out[:10]:
        print(f"  {c.get('gate_score', '?'):>3}점  {c.get('case_id')}  "
              f"{str(c.get('사건명', ''))[:34]}")
    if len(out) > 10:
        print(f"  … 모두 {len(out)}건")
    if not out:
        print("옮길 것이 없습니다.")
        return 0
    if a.check:
        print("(--check 라서 옮기지 않았습니다)")
        return 0

    known = {str(c.get("case_id")) for c in old}
    moved = [c for c in out if str(c.get("case_id")) not in known]
    REJECTED.write_text(json.dumps(old + moved, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    QUEUE.write_text(json.dumps(keep, ensure_ascii=False, indent=2) + "\n",
                     encoding="utf-8")
    print(f"\n{len(moved)}건을 {REJECTED.name} 으로 옮겼습니다 (모두 {len(old) + len(moved)}건).")
    print("화면에서는 사라지고, 다음 수집 때 다시 받지 않습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
