#!/usr/bin/env python3
"""3차 게이트 — LLM 드라마성 평가 (통과선 60점).

    python3 src/gate.py --limit 10

파이프라인에서의 위치

    수집 → 1차 기계 배제 → 2차 기계 가점 → ★3차 여기 → 대기열(점수순)

**이 단계가 유일한 폐기 지점이다.** 여기서 60점 미만은 버린다.
대본 단계에는 폐기가 없다(최고점 버전으로 발행한다).

걸러낼 지점을 가장 싼 단계에 두는 이유는 두 가지다.
  1. 대본을 다 만든 뒤 버리면 호출비가 낭비된다
  2. "소재가 나빴는가 / 대본 생성기가 나빴는가"가 분리된다
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prompts                                    # noqa: E402
import money                                      # noqa: E402
from llm import Gemini, LLMError, BudgetExceeded  # noqa: E402
from claude import writer, ClaudeError            # noqa: E402
from claude import BudgetExceeded as ClaudeBudget # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "cases"
QUEUE = ROOT / "state" / "queue.json"

PASS_MARK = 60


def load_queue():
    return json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else []


def save_queue(q):
    # 통과한 것 먼저, 그 안에서 게이트 점수 → 기계 점수 순
    q.sort(key=lambda c: (bool(c.get("gate_pass")),
                          c.get("gate_score") or 0,
                          c.get("machine_score") or 0), reverse=True)
    QUEUE.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def case_for_prompt(case):
    """모델에 넣을 판례 JSON. 본문이 매우 길 수 있어 안전하게 자른다."""
    keep = ["판례정보일련번호", "사건명", "사건번호", "선고일자", "법원명",
            "사건종류명", "판결유형", "판시사항", "판결요지", "참조조문", "판례내용"]
    d = {k: case.get(k, "") for k in keep}
    body = d["판례내용"]
    if len(body) > 40000:
        d["판례내용"] = body[:40000] + "\n\n…(이하 생략)"
    d["_사건번호_주의"] = "대본에 절대 쓰지 않는다"
    return json.dumps(d, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10, help="이번에 평가할 판례 수")
    ap.add_argument("--max-calls", type=int, default=0, help="모델 호출 상한 (기본: limit + 2)")
    ap.add_argument("--writer", choices=["claude", "gemini"], default=None,
                    help="심사할 곳. 비우면 CLAUDE_API_KEY 가 있을 때 Claude")
    args = ap.parse_args()

    queue = load_queue()
    todo = [c for c in queue if c.get("gate_score") is None][:args.limit]
    if not todo:
        print("평가할 판례가 없다. 먼저 src/collect.py 로 수집하라.")
        print(f"대기열 {len(queue)}건 (전부 평가 완료)")
        return 0

    try:
        llm, who = writer(max_calls=args.max_calls or (args.limit + 2), prefer=args.writer)
    except (LLMError, ClaudeError) as e:
        print(f"❌ {e}")
        return 2

    body = prompts.load("drama_gate")
    print(f"심사하는 곳: {who} · 모델: {llm.pick('pro')}")
    print(f"평가 대상 {len(todo)}건 (대기열 {len(queue)}건 중 미평가분)")
    print()

    by_id = {c["case_id"]: c for c in queue}
    done = passed = failed = 0

    for c in todo:
        cid = c["case_id"]
        path = CASES / f"{cid}.json"
        if not path.exists():
            print(f"  {cid}  판례 파일이 없다 — 건너뜀")
            continue
        case = json.loads(path.read_text(encoding="utf-8"))
        try:
            res = llm.json(prompts.fill(body, CASE_JSON=case_for_prompt(case)),
                           tier="pro", max_output_tokens=4096, temperature=0.4,
                           label=f"게이트 {cid}")
        except (BudgetExceeded, ClaudeBudget) as e:
            print(f"\n{e}")
            break
        except (LLMError, ClaudeError) as e:
            print(f"  {cid}  평가 실패: {e}")
            failed += 1
            continue

        total = int(res.get("total", 0))
        ok = bool(res.get("pass")) and total >= PASS_MARK and not res.get("reject")
        row = by_id[cid]
        row.update({
            "gate_score": total,
            "gate_pass": ok,
            "case_type": res.get("case_type", ""),
            "one_line": res.get("one_line", ""),
            "twist_hint": res.get("twist_hint", ""),
            "victim": res.get("victim", ""),
            "villain": res.get("villain", ""),
            # 대본에 쓸 금액은 백만원 단위로 다듬는다. 여기서부터 맞춰 둔다.
            "amount_krw": money.floor(int(res.get("amount_krw") or 0)),
            "amount_label": money.tidy(res.get("amount_label", "")),
            "gate_scores": res.get("scores", {}),
            "gate_reject": res.get("reject", []),
            "gate_note": res.get("note", ""),
        })
        done += 1
        passed += 1 if ok else 0
        mark = "통과" if ok else "폐기"
        why = ", ".join(res.get("reject", [])) if res.get("reject") else ""
        print(f"  {cid}  {total:3d}점 {mark}  {res.get('case_type', ''):8s} "
              f"{(res.get('one_line') or '')[:34]}  {why}")
        save_queue(queue)                       # 한 건마다 저장 — 중간에 죽어도 잃지 않는다

    print()
    print("─" * 60)
    print(f"평가 {done}건 · 통과 {passed}건 · 폐기 {done - passed}건"
          + (f" · 오류 {failed}건" if failed else ""))
    print(llm.report())

    ready = [c for c in queue if c.get("gate_pass")]
    print(f"\n제작 가능 대기열: {len(ready)}건")
    for c in ready[:8]:
        print(f"  {c.get('gate_score', 0):3d}점  {c['case_id']}  {c.get('case_type', ''):8s} "
              f"{(c.get('one_line') or '')[:36]}")

    # 한 건도 못 했으면 초록 체크를 주면 안 된다.
    # 예전에 "19초 만에 성공"으로 끝났는데 실은 6건 전부 400 으로 죽어 있었다.
    # 운영자는 로그를 열어보지 않으므로, 실패는 실패로 보여야 한다.
    if done == 0:
        print("\n한 건도 평가하지 못했다. 위의 오류 내용을 보라.")
        return 3
    if failed:
        print(f"\n{failed}건은 오류로 건너뛰었다. 다시 실행하면 그 건들만 재시도한다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
