#!/usr/bin/env python3
"""대본 생성 + 채점 + 부분 보강 (최대 3회) + 쇼츠 3편.

    python3 src/script.py                 대기열에서 다음 회차 하나를 만든다
    python3 src/script.py --case 608371   판례를 지정해서 만든다
    python3 src/script.py --dry-run       모델 호출 없이 배관만 시험한다

왜 한 번에 안 뽑고 나눠 뽑나
    12분 대본은 컷 113개다. JSON 으로 3만 토큰이 넘는다.
    모델의 한 번 출력 한도에 걸리면 **중간에서 잘린 JSON** 이 오고, 그러면 통째로 버려야 한다.
    그래서 두 단계로 나눈다.

        1단계 설계  — 인물·익명화·금액·법조문·막별 뼈대만 (작은 출력)
        2단계 막별  — 막 하나씩 컷을 채운다 (6번, 각각 작은 출력)

    덤으로 품질도 오른다. 한 번에 113컷을 쓰면 뒤로 갈수록 성의가 떨어지는데,
    막 단위로 끊으면 각 막에 집중력이 온전히 들어간다.

흐름
    설계 → 막별 생성 → 기계 검증 → 채점(별도 호출) → 미달 항목만 보강 → 재채점 (최대 3회)
    → 쇼츠 3편 → 저장 → state/episodes.json 갱신
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prompts                                              # noqa: E402
from llm import Gemini, LLMError, BudgetExceeded            # noqa: E402
from claude import writer, ClaudeError                       # noqa: E402
from claude import BudgetExceeded as ClaudeBudget            # noqa: E402
from validate_script import validate_doc, errors_as_text, load_manifest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "cases"
SCRIPTS = ROOT / "data" / "scripts"
QUEUE = ROOT / "state" / "queue.json"
EPISODES = ROOT / "state" / "episodes.json"
REJECTED = ROOT / "state" / "rejected.json"

TARGET_SCORE = 80
MAX_ROUNDS = 3

# 막별 목표 — CLAUDE.md "7. 대본 구조"
ACTS = [
    ("hook", "도입 훅",   0,  22,  5, "hook"),
    ("act1", "1막",      22, 200, 28, "past"),
    ("act2", "2막",     200, 370, 26, "reveal"),
    ("act3", "3막",     370, 520, 23, "conflict"),
    ("act4", "4막",     520, 670, 23, "court"),
    ("act5", "5막",     670, 720,  8, "outro"),
]


# ── 상태 파일 ────────────────────────────────────────────
def _load(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def _save(p, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def next_episode_id(eps):
    n = 1
    while f"EP{n:03d}" in eps:
        n += 1
    return f"EP{n:03d}"


def pick_case(queue, eps, case_id=None):
    """제작할 판례를 고른다.

    같은 사건 유형을 연속 2편 초과하지 않는다. 점수가 높아도 3편째는 다른 유형으로 넘긴다.
    유류분만 세 편 연달아 나가면 시청자가 같은 이야기로 느낀다."""
    if case_id:
        row = next((c for c in queue if c["case_id"] == case_id), None)
        return row or {"case_id": case_id, "gate_score": None, "case_type": ""}

    used = {v.get("case_id") for v in eps.values()}
    recent = [v.get("case_type") for v in sorted(
        eps.values(), key=lambda v: v.get("created_at", ""))[-2:]]
    blocked = recent[0] if len(recent) == 2 and recent[0] == recent[1] and recent[0] else None

    ready = [c for c in queue if c.get("gate_pass") and c["case_id"] not in used]
    ready.sort(key=lambda c: (c.get("gate_score") or 0, c.get("machine_score") or 0), reverse=True)
    if not ready:
        return None
    if blocked:
        alt = next((c for c in ready if c.get("case_type") != blocked), None)
        if alt:
            print(f"  유형 분산: '{blocked}' 이 연속 2편이라 다른 유형으로 넘긴다")
            return alt
        print(f"  ⚠️ '{blocked}' 말고 쓸 소재가 없다. 연속 3편이 된다")
    return ready[0]


# ── 프롬프트 조립 ────────────────────────────────────────
def asset_rules_text():
    """에셋 코드 목록을 프롬프트에 넣을 표로 만든다. manifest.json 이 유일한 출처다."""
    mf = load_manifest()
    return "\n".join([
        "| 종류 | 쓸 수 있는 값 |",
        "|---|---|",
        f"| 인물 코드 | {' '.join(mf['char']['codes'])} |",
        f"| 포즈 | {' '.join(mf['char']['poses'])} |",
        f"| 배경 | {' '.join(mf['bg']['codes'])} |",
        f"| 음악 | {' '.join(mf['bgm']['codes'])} |",
        f"| 앰비언스 | {' '.join(mf['amb']['codes'])} |",
        f"| 효과음 | {' '.join(mf['sfx']['codes'])} |",
        f"| 목소리 | {' '.join(mf['speakers'])} |",
        f"| 그래픽 | {' '.join(mf['gfx'])} |",
    ])


def case_json_for_prompt(case, gate_row):
    keep = ["판례정보일련번호", "사건명", "선고일자", "법원명", "사건종류명",
            "판시사항", "판결요지", "참조조문", "판례내용"]
    d = {k: case.get(k, "") for k in keep}
    body = d["판례내용"]
    if len(body) > 60000:
        d["판례내용"] = body[:60000] + "\n\n…(이하 생략)"
    d["_본문에서_찾은_조문"] = case.get("_laws_in_body", [])
    if gate_row.get("twist_hint"):
        d["_게이트가_찾은_반전"] = gate_row["twist_hint"]
    if gate_row.get("one_line"):
        d["_게이트_한줄요약"] = gate_row["one_line"]
    return json.dumps(d, ensure_ascii=False, indent=2)


# ── 1단계: 설계 ──────────────────────────────────────────
DESIGN_TASK = """
---

# ⚠️ 지금은 1단계다 — 설계만 한다

컷은 아직 쓰지 않는다. 아래만 낸다.

```json
{
  "meta": { "case_id": "...", "case_type": "...", "title_candidates": ["","",""],
            "logline": "...", "runtime_sec": 720, "cut_count": 113 },
  "anonymization": { ... 위 규칙대로 ... },
  "law": { "refs_from_case": [...], "refs_source": "참조조문|본문추출|없음", "explain_5act": "..." },
  "characters": [ ... ],
  "acts": [
    { "id": "hook", "title": "막 제목", "start_sec": 0, "end_sec": 22,
      "bgm": "hook", "cuts": [],
      "beats": ["이 막에서 벌어질 일을 3~6줄로", "..."] }
  ],
  "youtube": { "description_body": "...", "chapters": [...], "pinned_comment": "...", "tags": [...] }
}
```

- `acts` 는 hook · act1 · act2 · act3 · act4 · act5 **여섯 개**를 순서대로 낸다
- `cuts` 는 **전부 빈 배열**로 둔다. 2단계에서 채운다
- `beats` 가 2단계의 설계도다. **여기서 반전의 위치와 분노 대사를 미리 정해둔다**
- `youtube.chapters` 는 막 시작 초와 제목 6개
"""

ACT_TASK = """
---

# ⚠️ 지금은 2단계다 — 막 하나의 컷만 쓴다

## 이미 정해진 설계 (반드시 그대로 따른다)

```json
{{DESIGN}}
```

인물 이름·나이·금액·조문은 **위 설계에 적힌 것과 한 글자도 다르면 안 된다.**

## 이번에 쓸 막

| 항목 | 값 |
|---|---|
| 막 | `{{ACT_ID}}` — {{ACT_TITLE}} |
| 시각 | {{START}}초 ~ {{END}}초 |
| 길이 | **{{LEN}}초** (±3초 안에 맞춘다) |
| 컷 수 | **{{N}}개 전후** |
| 이 막의 뼈대 | {{BEATS}} |

{{EXTRA}}

## 출력

이 막의 컷 배열만 낸다. 다른 것은 넣지 않는다.

```json
{ "cuts": [ { "id": "...", "sec": 6.0, "bg": "...", "flashback": false,
              "chars": [...], "speaker": "...", "text": "...",
              "gfx": null, "sfx": null, "amb": "...", "blackout": false } ] }
```

- 컷 번호: hook 은 `H01`부터, 나머지는 `{{PREFIX}}-01` 부터
- `sec` 합계가 **{{LEN}}초 ±3** 이어야 한다
- 마지막 컷만 `blackout: true`
- 모든 컷에 `amb` 를 채운다
"""

ACT_EXTRA = {
    "hook": "**첫 컷은 3.0초 이내, 인물 대사로 시작한다.** 금액·결말을 밝히지 않는다. "
            "22초가 끝날 때 답 없는 질문을 남긴다.",
    "act1": "**첫 다섯 컷 안(22~50초)에 다투는 재산의 크기를 반드시 낸다.** "
            "숫자만 던지지 말고 그것이 주인공에게 무슨 의미인지 한 마디 붙인다. "
            "인물이 처음 나오는 컷마다 `nametag` 그래픽을 넣는다. 회상은 `flashback: true`.",
    "act2": "**반전이 드러나는 막이다. `timeline` 그래픽을 반드시 한 번 넣는다.** "
            "금액이 처음 크게 나오면 `amount` 그래픽도 넣는다. "
            "반전이 드러나는 컷에 `\"tag\": \"twist\"` 를 넣는다.",
    "act3": "**20자 이내의 뻔뻔한 대사를 반드시 하나 넣는다.** 욕설·고성 금지. "
            "차분하게 뻔뻔한 쪽이 훨씬 밉다. 이 한 줄이 쇼츠 2번이 된다. "
            "그 컷에 반드시 `\"tag\": \"anger_line\"` 을 넣는다. 나중에 다시 찾아야 한다.",
    "act4": "상대 주장 → 재판장 판단 순서를 지킨다. 재판장 대사는 `v_JUDGE`. "
            "**판결 낭독에 금액을 특정하고 `amount` 그래픽을 넣는다.** "
            "그 컷에 `\"tag\": \"verdict\"` 를 넣는다. "
            "법률 용어는 처음 나올 때 한 문장으로 푼다.",
    "act5": "여운(약 20초) → 법령 설명(약 20초) → **예/아니오로 답할 수 없는 질문**(약 10초). "
            "마지막 질문 컷에 `\"tag\": \"question\"` 을 넣는다. "
            "조언하지 않는다. 설계의 `law.explain_5act` 를 여기서 쓴다.",
}


def gen_design(llm, base, case_txt):
    return llm.json(base + DESIGN_TASK.replace("{{CASE_JSON}}", ""),
                    tier="pro", max_output_tokens=8192, temperature=0.85, label="설계")


def gen_act(llm, base, design, act):
    aid, title, start, end, n, bgm = act
    prefix = "H" if aid == "hook" else f"A{aid[-1]}"
    beats = next((a.get("beats", []) for a in design["acts"] if a["id"] == aid), [])
    task = (ACT_TASK
            .replace("{{DESIGN}}", json.dumps(
                {k: design[k] for k in ("meta", "anonymization", "law", "characters")},
                ensure_ascii=False, indent=2))
            .replace("{{ACT_ID}}", aid).replace("{{ACT_TITLE}}", title)
            .replace("{{START}}", str(start)).replace("{{END}}", str(end))
            .replace("{{LEN}}", str(end - start)).replace("{{N}}", str(n))
            .replace("{{BEATS}}", " / ".join(beats) or "(설계에 없음)")
            .replace("{{EXTRA}}", ACT_EXTRA.get(aid, ""))
            .replace("{{PREFIX}}", prefix))
    res = llm.json(base + task, tier="pro", max_output_tokens=16384,
                   temperature=0.9, label=f"막 {aid}")
    return res.get("cuts", [])


def assemble(design, acts_cuts):
    doc = {k: design.get(k) for k in ("meta", "anonymization", "law", "characters")}
    doc["acts"] = []
    for (aid, title, start, end, _n, bgm) in ACTS:
        src = next((a for a in design["acts"] if a["id"] == aid), {})
        doc["acts"].append({
            "id": aid, "title": src.get("title", title),
            "start_sec": start, "end_sec": end,
            "bgm": src.get("bgm", bgm), "cuts": acts_cuts.get(aid, []),
        })
    doc["shorts"] = []
    doc["youtube"] = design.get("youtube", {})
    doc["meta"]["cut_count"] = sum(len(a["cuts"]) for a in doc["acts"])
    return doc


# ── 검증 → 보강 ──────────────────────────────────────────
def machine_fix(llm, doc, rounds=2):
    """기계 검증에서 걸린 것을 모델에게 고치게 한다. 채점 전에 먼저 한다.

    형식 오류가 있는 대본을 채점에 보내는 것은 낭비다. 채점은 재미를 보는 것이지
    괄호가 맞는지 보는 것이 아니다."""
    body = prompts.load("script_revise")
    for i in range(rounds):
        r = validate_doc(doc)
        if not r.errors:
            return doc, r
        print(f"  기계 검증: 오류 {len(r.errors)}건 → 보강 {i + 1}차")
        for w, m in r.errors[:6]:
            print(f"    [{w}] {m}")
        fake_eval = {
            "total": 0, "verdict": "revise", "revise_targets": [],
            "instructions": [{
                "item": "형식", "cut_ids": [],
                "what": "아래 기계 검증 오류를 전부 해결한다. 내용은 최대한 그대로 두고 형식만 고친다.\n"
                        + errors_as_text(r),
                "why": "형식이 틀리면 렌더링이 통째로 실패한다",
            }],
            "blocking": [{"kind": "machine_validation", "cut_id": "", "found": m, "fix": w}
                         for w, m in r.errors[:12]],
            "strengths": [],
        }
        try:
            doc = llm.json(prompts.fill(
                body,
                SCRIPT_JSON=json.dumps(doc, ensure_ascii=False),
                EVAL_JSON=json.dumps(fake_eval, ensure_ascii=False, indent=2),
                ASSET_RULES=asset_rules_text(),
            ), tier="pro", max_output_tokens=60000, temperature=0.5, label="형식 보강")
        except (LLMError, ClaudeError) as e:
            print(f"    보강 실패: {e}")
            break
    return doc, validate_doc(doc)


def evaluate(llm, doc):
    body = prompts.load("script_eval")
    return llm.json(prompts.fill(body, SCRIPT_JSON=json.dumps(doc, ensure_ascii=False)),
                    tier="flash", max_output_tokens=8192, temperature=0.3, label="채점")


def revise(llm, doc, ev):
    body = prompts.load("script_revise")
    return llm.json(prompts.fill(
        body,
        SCRIPT_JSON=json.dumps(doc, ensure_ascii=False),
        EVAL_JSON=json.dumps(ev, ensure_ascii=False, indent=2),
        ASSET_RULES=asset_rules_text(),
    ), tier="pro", max_output_tokens=60000, temperature=0.7, label="보강")


def make_shorts(llm, doc):
    body = prompts.load("shorts_gen")
    return llm.json(prompts.fill(body, SCRIPT_JSON=json.dumps(doc, ensure_ascii=False)),
                    tier="flash", max_output_tokens=16384, temperature=0.8, label="쇼츠")


# ── 본체 ────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="", help="판례일련번호를 지정")
    ap.add_argument("--max-calls", type=int, default=24, help="모델 호출 상한")
    ap.add_argument("--dry-run", action="store_true", help="모델 호출 없이 배관만 시험")
    ap.add_argument("--writer", default="", choices=["", "claude", "gemini"],
                    help="대본을 쓸 곳. 비우면 CLAUDE_API_KEY 가 있을 때 claude")
    args = ap.parse_args()

    SCRIPTS.mkdir(parents=True, exist_ok=True)
    queue = _load(QUEUE, [])
    eps = _load(EPISODES, {})

    row = pick_case(queue, eps, args.case or None)
    if not row:
        print("제작할 소재가 없다.")
        print("  1) src/collect.py 로 판례를 모으고")
        print("  2) src/gate.py 로 드라마성 평가를 돌려 통과분을 만든 뒤 다시 실행하라.")
        return 0

    cid = row["case_id"]
    path = CASES / f"{cid}.json"
    if not path.exists():
        print(f"판례 파일이 없다: {path}")
        return 2
    case = json.loads(path.read_text(encoding="utf-8"))

    ep = next_episode_id(eps)
    print(f"회차 {ep} · 판례 {cid} · {case.get('사건명', '')}")
    print(f"게이트 {row.get('gate_score', '-')}점 · 유형 {row.get('case_type', '-')}")
    print()

    if args.dry_run:
        sample = SCRIPTS / "SAMPLE_608371.json"
        if not sample.exists():
            print("dry-run 에 쓸 샘플이 없다.")
            return 2
        doc = json.loads(sample.read_text(encoding="utf-8"))
        r = validate_doc(doc)
        print(f"[dry-run] 샘플 검증 — 통과 {len(r.oks)} · 오류 {len(r.errors)}")
        print(f"[dry-run] 선택 로직·검증·저장 경로 정상. 실제 생성은 GEMINI_API_KEY 가 필요하다.")
        return 0 if not r.errors else 1

    try:
        llm, who = writer(max_calls=args.max_calls, prefer=args.writer or None)
    except (LLMError, ClaudeError) as e:
        print(f"❌ {e}")
        return 2

    base = prompts.fill(prompts.load("script_gen"),
                        CASE_JSON=case_json_for_prompt(case, row))
    print(f"대본을 쓰는 곳: {who}")
    print(f"모델: {llm.pick('pro')} (생성) / {llm.pick('flash')} (채점)")

    best, best_score, best_eval = None, -1, None
    try:
        # 1단계 설계
        print("\n[1단계] 설계")
        design = gen_design(llm, base, case)
        print(f"  제목 후보: {design['meta'].get('title_candidates', [''])[0]}")
        print(f"  인물 {len(design.get('characters', []))}명 · "
              f"금액 배율 {design.get('anonymization', {}).get('amount_scale')}")

        # 2단계 막별 생성
        print("\n[2단계] 막별 컷 생성")
        cuts = {}
        for act in ACTS:
            c = gen_act(llm, base, design, act)
            cuts[act[0]] = c
            print(f"  {act[0]:5s} {len(c):3d}컷 {sum(x.get('sec', 0) for x in c):6.1f}초 "
                  f"(목표 {act[4]}컷 {act[3] - act[2]}초)")
        doc = assemble(design, cuts)

        # 기계 검증 → 형식 보강
        print("\n[3단계] 기계 검증")
        doc, r = machine_fix(llm, doc)
        print(f"  통과 {len(r.oks)} · 경고 {len(r.warns)} · 오류 {len(r.errors)}")

        # 채점 → 보강 루프
        print("\n[4단계] 채점 · 보강")
        for rd in range(1, MAX_ROUNDS + 1):
            ev = evaluate(llm, doc)
            total = int(ev.get("total", 0))
            low = [k for k, v in ev.get("scores", {}).items()
                   if v.get("max") and v["score"] < v["max"] * 0.6]
            blocking = ev.get("blocking", [])
            print(f"  {rd}회차: {total}점 · {ev.get('verdict')} · "
                  f"차단 {len(blocking)}건 · 붕괴 항목 {low or '없음'}")
            print(f"    {ev.get('one_line', '')}")
            if total > best_score:
                best, best_score, best_eval = json.loads(json.dumps(doc)), total, ev
            if total >= TARGET_SCORE and not blocking and not low:
                print("  통과")
                break
            if rd == MAX_ROUNDS:
                print(f"  {MAX_ROUNDS}회 끝. 폐기하지 않고 최고점({best_score}점) 버전으로 간다")
                _record_rejected(row, best_eval)
                break
            try:
                doc = revise(llm, doc, ev)
                doc, r = machine_fix(llm, doc, rounds=1)
            except (LLMError, ClaudeError) as e:
                # 보강 한 번 실패로 회차를 통째로 버리지 않는다.
                # 지금까지 최고점 버전이 이미 best 에 있다.
                print(f"  보강 실패({e}) → 최고점({best_score}점) 버전으로 마무리한다")
                break

        doc = best or doc

        # 쇼츠 3편
        print("\n[5단계] 쇼츠 3편")
        sh = make_shorts(llm, doc)
        for s in sh.get("shorts", []):
            print(f"  {s.get('no')}번 {s.get('kind', ''):6s} {s.get('est_sec', 0):.1f}초  "
                  f"{s.get('intro_line', '')}")

    except (BudgetExceeded, ClaudeBudget) as e:
        print(f"\n⚠️ {e}")
        if best is None:
            return 1
        doc, sh = best, {"shorts": []}
    except (LLMError, ClaudeError) as e:
        print(f"\n❌ 생성 실패: {e}")
        return 1

    # 저장
    doc["meta"]["episode"] = ep
    doc["meta"]["case_id"] = cid
    _save(SCRIPTS / f"{ep}.json", doc)
    _save(SCRIPTS / f"{ep}.eval.json", best_eval or {})
    if sh.get("shorts"):
        _save(SCRIPTS / f"{ep}.shorts.json", sh)

    final = validate_doc(doc)
    eps[ep] = {
        "case_id": cid,
        "gate_score": row.get("gate_score"),
        "stage": "evaluated" if not final.errors else "scripting",
        "script_score": best_score,
        "revise_count": max(0, rd - 1),
        "case_type": row.get("case_type", ""),
        "created_at": date.today().isoformat(),
        "validation_errors": len(final.errors),
    }
    _save(EPISODES, eps)

    print()
    print("─" * 60)
    print(f"{ep} 저장 완료 · 채점 {best_score}점 · 컷 {doc['meta'].get('cut_count')}개")
    print(f"기계 검증: 통과 {len(final.oks)} · 오류 {len(final.errors)}")
    print(llm.report())
    if final.errors:
        print("\n⚠️ 형식 오류가 남았다. 렌더링 전에 반드시 고쳐야 한다:")
        for w, m in final.errors[:8]:
            print(f"  [{w}] {m}")
    return 0


def _record_rejected(row, ev):
    """3회 보강 후에도 미달한 건을 남긴다. 쌓이면 게이트 기준을 보정하는 근거가 된다."""
    rec = _load(REJECTED, [])
    rec.append({
        "case_id": row.get("case_id"),
        "case_type": row.get("case_type", ""),
        "gate_score": row.get("gate_score"),
        "script_score": int((ev or {}).get("total", 0)),
        "weak_items": (ev or {}).get("revise_targets", []),
        "one_line": (ev or {}).get("one_line", ""),
        "date": date.today().isoformat(),
    })
    _save(REJECTED, rec)


if __name__ == "__main__":
    sys.exit(main())
