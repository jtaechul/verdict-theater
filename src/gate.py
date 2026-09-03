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
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prompts                                    # noqa: E402
import cost                                       # noqa: E402
import money                                      # noqa: E402
from llm import Gemini, LLMError, BudgetExceeded  # noqa: E402
from claude import writer, grader, ClaudeError    # noqa: E402
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


# ⭐ 심사에 넣을 판례 본문 길이 (앞 / 뒤, 글자 수)
#
#   여기는 **채점**이지 대본을 쓰는 자리가 아니다. 0~100점을 매기는 데
#   봐야 할 곳은 두 군데뿐이다.
#     앞  — 【주 문】(누가 얼마를 받았나) + 【이 유】1. 기초사실 (누가 무엇을 했나)
#     뒤  — 결론
#   그 사이에 낀 것은 유류분 산정표·감정가 목록·법리 인용이다.
#   드라마인지 아닌지를 가리는 데는 아무 보탬이 안 되면서 값은 그대로 나간다.
#
#   실측 (2026-08-11 심사 10건): 본문 189,718자 = 165,769토큰 = 565원.
#   앞 9,000 + 뒤 3,000 으로 줄이면 109,698자 — **값이 58%로 내려간다.**
#   그 10건 중 3건은 애초에 12,000자가 안 돼 손도 대지 않는다.
#   (모아 둔 판례 197건의 중앙값이 5,862자다 — 대부분은 통째로 다 들어간다.)
#
#   숫자는 워크플로에서 환경변수로 바꿀 수 있다.
GATE_HEAD = int(os.environ.get("VT_GATE_HEAD", "9000"))
GATE_TAIL = int(os.environ.get("VT_GATE_TAIL", "3000"))


def trim_body(body, head=None, tail=None):
    """판례 본문에서 가운데를 들어내고 앞과 뒤만 남긴다.

    짧으면 손대지 않고 그대로 돌려준다. 잘랐을 때는 잘랐다고 본문에 적는다 —
    모델이 '뒤가 끊긴 글'이 아니라 '가운데가 빠진 글'로 읽어야 하기 때문이다."""
    head = GATE_HEAD if head is None else head
    tail = GATE_TAIL if tail is None else tail
    if not body or len(body) <= head + tail:
        return body
    gone = len(body) - head - tail
    return (body[:head]
            + f"\n\n…(가운데 {gone:,}자 생략 — 산정표·감정가 목록·법리 인용)…\n\n"
            + body[-tail:])


def case_for_prompt(case):
    """모델에 넣을 판례 JSON. 본문이 매우 길 수 있어 안전하게 자른다."""
    keep = ["판례정보일련번호", "사건명", "사건번호", "선고일자", "법원명",
            "사건종류명", "판결유형", "판시사항", "판결요지", "참조조문", "판례내용"]
    d = {k: case.get(k, "") for k in keep}
    d["판례내용"] = trim_body(d["판례내용"])
    d["_사건번호_주의"] = "대본에 절대 쓰지 않는다"
    return json.dumps(d, ensure_ascii=False, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10, help="이번에 평가할 판례 수")
    # ⭐⭐ 2026-09-02 손님: "지금 사건이 다 유류분이나 상속 이런 거밖에 없어.
    #    내가 분명히 불륜이나 이런 것들도 수집하라고 했잖아."
    #    맞다. 그런데 원인은 모으기가 아니었다 — **심사가 아예 안 돌고 있었다.**
    #    대기열 165건 가운데 152건이 점수 없이 쌓여 있었고, 점수 없는 것은
    #    화면 목록에서 고를 수가 없다. 그래서 손님 눈에는 옛날에 심사한
    #    상속 13건만 보였다.
    #    → 갈래를 골라 심사할 수 있게 한다. 불륜부터 매기면 바로 쓸 수 있다.
    ap.add_argument("--topic", default="",
                    help="이 갈래만 심사 (불륜·상속·재산…). 비우면 전부")
    ap.add_argument("--max-calls", type=int, default=0, help="모델 호출 상한 (기본: limit + 2)")
    ap.add_argument("--writer", choices=["gemini"], default=None,
                    help="심사할 곳. 비우면 값싼 쪽(Gemini)으로 채점한다")
    args = ap.parse_args()

    # ⭐ 돈을 쓰기 **전에** 한 달 한도부터 본다. 넘었으면 시작조차 하지 않는다.
    try:
        used, left = cost.guard_month("소재 심사")
    except cost.MonthlyCapReached as e:
        print(f"❌ {e}")
        return 7
    print(f"이번 달 쓴 돈 {used:,.0f}원 · 남은 한도 {left:,.0f}원 "
          f"(한 달 {cost.MONTH_KRW:,.0f}원)")

    queue = load_queue()
    want = (args.topic or "").strip()
    rest = [c for c in queue if c.get("gate_score") is None]
    if want:
        rest = [c for c in rest if (c.get("topic") or "") == want]
    # ⭐ 점수 높은 것부터 매긴다 — 예산이 모자라도 쓸 만한 것이 먼저 걸린다
    rest.sort(key=lambda c: -(c.get("machine_score") or 0))
    todo = rest[:args.limit]
    if not todo:
        left = sum(1 for c in queue if c.get("gate_score") is None)
        print(f"평가할 판례가 없다{f' ({want} 갈래에는)' if want else ''}.")
        print(f"대기열 {len(queue)}건 · 아직 안 매긴 것 {left}건")
        return 0
    print(f"■ 심사할 것 {len(todo)}건"
          + (f" ({want} 갈래)" if want else "")
          + f" · 아직 안 매긴 것 {len(rest)}건")

    # ⭐ 심사는 **채점**이다. 글을 쓰는 일이 아니므로 값싼 쪽(Gemini)으로 보낸다.
    #    (2026-08-10 손님: "채점은 Gemini api로 하고, 대본 생성만 Claude api로")
    #    한 번 누를 때 판례 10건을 매기느라 이 자리에서만 모델을 10번 부른다 —
    #    한 편에 드는 모델 호출의 절반이 넘는데, 그게 전부 가장 비싼 값으로 돌고 있었다.
    #    ⚠️ 2026-08-23 부터 양쪽 다 제미나이라 어느 길로 가도 결과는 같다.
    try:
        pick = (grader if not args.writer else writer)
        llm, who = pick(max_calls=args.max_calls or (args.limit + 2), prefer=args.writer)
    except (LLMError, ClaudeError) as e:
        print(f"❌ {e}")
        return 2

    body = prompts.load("drama_gate")
    # 모델 이름은 화면에 보여주는 것뿐이다. 이름을 물어보다 실패했다고 제작이
    # 멈추면 안 되므로 감싼다 (예전엔 이 print 한 줄에서 통째로 죽었다).
    try:
        model_name = llm.pick("pro")
    except Exception:
        model_name = "(이름 확인 실패)"
    print(f"심사하는 곳: {who} · 모델: {model_name}  (채점이라 값싼 쪽을 쓴다)")
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
    cost.record("소재 심사", getattr(llm, "spent_krw", lambda: 0)(), f"{done}건 평가")

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
