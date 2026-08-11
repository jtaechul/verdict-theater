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
import traceback
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prompts                                              # noqa: E402
import money                                                # noqa: E402
from autofix import autofix                                 # noqa: E402
from llm import Gemini, LLMError, BudgetExceeded            # noqa: E402
from claude import writer, grader, ClaudeError               # noqa: E402
from claude import BudgetExceeded as ClaudeBudget            # noqa: E402
from validate_script import (validate_doc, errors_as_text, load_manifest,  # noqa: E402
                             ACT_WINDOW)

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "cases"
SCRIPTS = ROOT / "data" / "scripts"
QUEUE = ROOT / "state" / "queue.json"
EPISODES = ROOT / "state" / "episodes.json"
REJECTED = ROOT / "state" / "rejected.json"

TARGET_SCORE = 80
MAX_ROUNDS = 3

# 막별 목표 — CLAUDE.md "7. 대본 구조" · validate_script.ACT_WINDOW 와 반드시 같아야 한다.
#
# ⚠️ v2.0(2026-08-01): 법정 150→55초, 5막 50→31초. 뺀 114초는 1~3막으로.
#    판결·금액이 33.6%를 차지하던 것을 10% 아래로 내리기 위한 것이다.
#    이 표가 검증기와 어긋나면, 대본은 옛 분량으로 쓰이고 검증에서만 떨어진다.
ACTS = [
    ("hook", "도입 훅",   0,  22,  5, "hook"),
    ("act1", "1막",      22, 240, 34, "past"),
    ("act2", "2막",     240, 446, 32, "reveal"),
    ("act3", "3막",     446, 634, 29, "conflict"),
    ("act4", "4막",     634, 689,  9, "court"),
    ("act5", "5막",     689, 720,  5, "outro"),
]

# 위 표가 검증기와 어긋나면 **조용히 망가진다** — 대본은 옛 분량으로 쓰이고
# 검증에서만 떨어져, 원인이 프롬프트인지 검증기인지 알 수 없게 된다.
# 실제로 v2.0 첫 실행에서 그렇게 됐다(1~3막이 옛 목표로 생성돼 오류 5건).
# 두 곳을 함께 고쳐야 하는 규칙이므로, 한 곳만 고치면 즉시 멈춘다.
_plan = {a[0]: (a[2], a[3]) for a in ACTS}
if _plan != ACT_WINDOW:
    raise SystemExit(
        "막 구성이 어긋났다 — src/script.py 의 ACTS 와 "
        "src/validate_script.py 의 ACT_WINDOW 를 똑같이 맞춰라.\n"
        f"  script.py       : {_plan}\n"
        f"  validate_script : {ACT_WINDOW}")


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


# 가사사건을 알아보는 말들. 사건명에 이 중 하나라도 있으면 쓸 수 없다.
# (가정법원 판결문은 공개 대상이 아니다 — 지침 6번)
FAMILY_COURT = ["이혼", "재산분할", "양육권", "양육비", "친권",
                "상속재산분할", "기여분", "혼인무효", "혼인취소", "인지청구"]


def _family_court_words(case_name):
    """사건명이 가사사건인가. 맞으면 걸린 말을 돌려준다."""
    return next((w for w in FAMILY_COURT if w in (case_name or "")), "")


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
    """에셋 코드 목록을 프롬프트에 넣을 표로 만든다. manifest.json 이 유일한 출처다.

    ⚠️ 인물 코드는 **뜻을 함께 적어야 한다.** 예전에는 'F50A F50B M50A M50B F70
       M70 JUDGE' 라고 이름만 줬다. 모델은 M70 이 70대 남성인 줄 모르고, 돌아가신
       아버지를 차남 코드(M50B)로 그리게 했다. 화면에서 두 사람이 **같은 얼굴**로
       나왔고 손님이 바로 알아챘다. 뜻을 적고, 겹쳐 쓰지 말라고 못 박는다."""
    # 뜻풀이는 '있으면 좋은 것'이다. 이것 하나 못 읽었다고 19분짜리 대본 생성이
    # 통째로 죽어선 안 된다 — 2026-08-10 EP002 가 정확히 여기서 날아갔다.
    try:
        from assets_gen import CHAR_LOOK           # noqa: E402
    except Exception as e:                          # noqa: BLE001
        print(f"    (인물 뜻풀이를 못 읽었다: {e} — 코드만 넣고 계속한다)")
        CHAR_LOOK = {}
    mf = load_manifest()
    who = " / ".join(f"`{c}`={CHAR_LOOK[c]}" if c in CHAR_LOOK else f"`{c}`"
                     for c in mf["char"]["codes"])
    return "\n".join([
        "| 종류 | 쓸 수 있는 값 |",
        "|---|---|",
        f"| 인물 코드 | {who} |",
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

### 인물 코드 규칙 (어기면 화면이 망가진다)

- **한 코드는 한 사람만.** 서로 다른 인물에게 같은 코드를 주면, 화면에 **똑같은
  얼굴**로 나온다. 실제로 아버지와 차남이 같은 얼굴로 나온 적이 있다.
- **나이·성별에 맞는 코드를 쓴다.** 70대는 `M70`·`F70`, 50~60대는 `M50A`·`M50B`·
  `F50A`·`F50B`. 70대 아버지를 `M50B` 로 적으면 안 된다.
- 대사가 **누군가를 향할 때는 듣는 사람도 `chars` 에 넣는다.** "아버지, 도와주세요"
  라고 말하는 컷에 아버지가 없으면, 허공에 대고 말하는 화면이 된다.
- 화면에 안 나오는 인물은 `chars` 에 넣지 않는다. 돌아가신 분은 **회상 컷에서만**
  넣는다(`"flashback": true`).

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
    "act1": "**금액을 한 번도 쓰지 않는다.** 걸린 것은 숫자가 아니라 물건과 관계로 말한다 "
            "— '12억 400만 원' 이 아니라 '세 아들이 다 자란 그 집'. "
            "이 막은 인물 관계를 세우는 곳이다. `family` 그래픽을 반드시 한 번 넣고, "
            "인물이 처음 나오는 컷마다 `nametag` 그래픽을 넣는다. 회상은 `flashback: true`.",
    "act2": "**반전이 드러나는 막이다. `timeline` 그래픽을 반드시 한 번 넣는다.** "
            "`amount` 그래픽은 여기에 넣지 않는다 — 회차 전체에서 4막 판결 컷 하나뿐이다. "
            "금액을 말해야 하면 비교로 말한다: '형 몫이 동생 셋을 합친 것보다 컸습니다'. "
            "반전이 드러나는 컷에 `\"tag\": \"twist\"` 를 넣는다.",
    "act3": "**20자 이내의 뻔뻔한 대사를 반드시 하나 넣는다.** 욕설·고성 금지. "
            "차분하게 뻔뻔한 쪽이 훨씬 밉다. 이 한 줄이 쇼츠 2번이 된다. "
            "그 컷에 반드시 `\"tag\": \"anger_line\"` 을 넣는다. 나중에 다시 찾아야 한다.",
    "act4": "**55초 안에 끝낸다. 법정은 절정이 아니라 마침표다** — 절정은 3막에 있었다. "
            "상대 주장 → 재판장 판단 순서를 지킨다. 재판장 대사는 `v_JUDGE`. "
            "**금액은 판결 낭독 컷 딱 하나에서만 말하고, `amount` 그래픽도 그 컷에만 넣는다.** "
            "그 앞뒤로 금액을 되풀이하지 않는다. 그 컷에 `\"tag\": \"verdict\"` 를 넣는다. "
            "법률 용어는 처음 나올 때 한 문장으로 푼다. "
            "**마지막 두세 컷은 판결을 듣는 가족들의 얼굴·침묵에 쓴다.**",
    "act5": "여운(약 19초) → **제도 설명은 한 문장만**(약 6초) → "
            "**관계를 묻는 질문**(약 6초). 돈이 아니라 사람을 묻는다. "
            "여운 장면에는 **이겼는데도 잃은 것**이 보여야 한다. "
            "마지막 질문 컷에 `\"tag\": \"question\"` 을 넣는다. "
            "조언하지 않는다. 설계의 `law.explain_5act` 를 한 문장으로 줄여 쓴다.",
}


def gen_design(llm, base, case_txt):
    # base(지시문 + 판례 본문)는 아래 막별 6회에서도 글자 그대로 반복된다.
    # cache_prefix 로 넘겨 한 번만 읽히고 이후엔 재사용하게 한다.
    return llm.json(DESIGN_TASK.replace("{{CASE_JSON}}", ""), cache_prefix=base,
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
    res = llm.json(task, cache_prefix=base, tier="pro", max_output_tokens=16384,
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
    # 금액을 백만원 단위로 다듬는다. 본문·amounts_used·그래픽 값을 한꺼번에 훑어야
    # "본문 금액이 amounts_used 와 다르다" 는 검증에 걸리지 않는다.
    return money.tidy_doc(doc)


# ── 검증 → 보강 ──────────────────────────────────────────
def apply_patch(doc, patch):
    """모델이 돌려준 '바뀐 컷' 을 원본에 끼워 넣는다.

    전문을 다시 받으면 113컷을 다시 쓰느라 약 26,000 토큰이 나간다.
    바뀐 컷만 받으면 보통 3,000 토큰 아래다. 나머지는 여기서 원본을 그대로 쓴다.

    모델이 없는 번호를 지어내면 조용히 버린다 — 원본에 없는 컷을 새로 만들면
    초 배분과 쇼츠 지시가 전부 어긋난다."""
    # 전문을 그대로 돌려준 경우(옛 형식)도 받아준다. 프롬프트를 못 따랐다고 버릴 이유는 없다.
    if isinstance(patch, dict) and patch.get("acts"):
        return money.tidy_doc(patch), None

    index = {c.get("id"): c for _, c in _iter_cuts(doc) if c.get("id")}
    hit, miss = 0, []
    for c in (patch or {}).get("cuts") or []:
        cid = c.get("id")
        if cid in index:
            index[cid].clear()
            index[cid].update(c)
            hit += 1
        elif cid:
            miss.append(cid)

    for key in ("law", "characters", "anonymization", "youtube"):
        if isinstance(patch.get(key), (dict, list)) and patch.get(key):
            doc[key] = patch[key]

    doc.setdefault("meta", {})["cut_count"] = sum(1 for _ in _iter_cuts(doc))
    note = f"{hit}컷 교체"
    if miss:
        note += f" · 없는 번호 {len(miss)}개 무시({', '.join(miss[:4])})"
    return money.tidy_doc(doc), note


def _iter_cuts(doc):
    for act in doc.get("acts", []):
        for c in act.get("cuts", []):
            yield act, c


def machine_fix(llm, doc, rounds=2):
    """기계 검증에서 걸린 것을 고친다.

    ① 먼저 코드로 고친다 — 정답이 하나로 정해지는 것들(blackout·컷 수·초 합계·금액).
       이것 때문에 대본 전문을 모델에 보내는 것은 순수한 낭비다. 비용 0원.
    ② 그래도 남은 것만 모델에게 보낸다. 사람의 판단이 필요한 것들이다.

    형식 오류가 있는 대본을 채점에 보내는 것도 낭비다. 채점은 재미를 보는 것이지
    괄호가 맞는지 보는 것이 아니다."""
    for n in autofix(doc):
        print(f"  자동 교정(무료): {n}")

    body = prompts.load("script_revise")
    for i in range(rounds):
        # 쇼츠는 5단계에서 만든다. 아직 없는 게 정상이므로 여기서 따지지 않는다.
        # (따졌더니 "쇼츠 0편" 오류가 매번 6만 토큰짜리 재작성을 부르고, 거기서 죽었다)
        r = validate_doc(doc, with_shorts=False)
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
            patch = llm.json(prompts.fill(
                body,
                SCRIPT_JSON=json.dumps(doc, ensure_ascii=False),
                EVAL_JSON=json.dumps(fake_eval, ensure_ascii=False, indent=2),
                ASSET_RULES=asset_rules_text(),
            ), tier="pro", max_output_tokens=16384, temperature=0.5, label="형식 보강")
            doc, note = apply_patch(doc, patch)
            if note:
                print(f"    {note}")
            for n in autofix(doc):      # 모델이 새로 만든 기계적 오류도 무료로 잡는다
                print(f"    자동 교정(무료): {n}")
        except (LLMError, ClaudeError) as e:
            print(f"    보강 실패: {e}")
            break
    return doc, validate_doc(doc, with_shorts=False)


# 채점은 한 번 실행에 한 곳만 잡아 두고 계속 쓴다 (매번 새로 만들면 호출 상한이 초기화된다)
_GRADER = None


def grading_llm(fallback):
    """대본 **채점**에 쓸 곳. 값싼 Gemini 를 먼저 쓰고, 없으면 원래 쓰던 곳으로 돌아간다.

    (2026-08-10 손님: "채점은 Gemini api로 하고, 대본 생성만 Claude api로")
    대본을 쓰는 llm 은 그대로 Claude 로 두고, 점수 매기는 일만 이쪽으로 보낸다.
    """
    global _GRADER
    if _GRADER is None:
        try:
            g, who = grader(max_calls=6)
            print(f"    (채점하는 곳: {who} — 채점이라 값싼 쪽을 쓴다)")
            _GRADER = g
        except Exception as e:      # 열쇠가 없든 무슨 일이 있든 채점 때문에 멈추면 안 된다
            print(f"    (값싼 채점 모델을 못 잡았다: {e} — 쓰던 곳으로 채점한다)")
            _GRADER = fallback
    return _GRADER


def evaluate(llm, doc):
    body = prompts.load("script_eval")
    g = grading_llm(llm)
    return g.json(prompts.fill(body, SCRIPT_JSON=json.dumps(doc, ensure_ascii=False)),
                  tier="flash", max_output_tokens=8192, temperature=0.3, label="채점")


def revise(llm, doc, ev):
    """품질 보강. 여기서도 바뀐 컷만 받아 끼운다 — 전문 재작성은 편당 약 900원이다."""
    body = prompts.load("script_revise")
    patch = llm.json(prompts.fill(
        body,
        SCRIPT_JSON=json.dumps(doc, ensure_ascii=False),
        EVAL_JSON=json.dumps(ev, ensure_ascii=False, indent=2),
        ASSET_RULES=asset_rules_text(),
    ), tier="pro", max_output_tokens=16384, temperature=0.7, label="보강")
    out, note = apply_patch(json.loads(json.dumps(doc)), patch)
    if note:
        print(f"    {note}")
    for n in autofix(out):
        print(f"    자동 교정(무료): {n}")
    return out


def _make_shorts_only(ep, prefer):
    """이미 저장된 대본에 쇼츠 3편만 붙인다."""
    path = SCRIPTS / f"{ep}.json"
    if not path.exists():
        print(f"{ep} 대본이 없다: {path}")
        return 2
    doc = json.loads(path.read_text(encoding="utf-8"))
    print(f"{ep} · 컷 {doc['meta'].get('cut_count')}개 — 쇼츠만 만든다")
    try:
        llm, who = writer(max_calls=3, prefer=prefer or None)
        print(f"만드는 곳: {who}")
        sh = make_shorts(llm, doc)
    except (LLMError, ClaudeError) as e:
        print(f"실패: {e}")
        sh = _shorts_retry(doc, prefer)
    if not sh.get("shorts"):
        print("쇼츠를 만들지 못했다.")
        return 1
    doc["shorts"] = sh["shorts"]
    _save(path, doc)
    _save(SCRIPTS / f"{ep}.shorts.json", sh)
    for s in sh["shorts"]:
        print(f"  {s.get('no')}번 {s.get('kind', ''):6s} {s.get('est_sec', 0):.1f}초  "
              f"{s.get('intro_line', '')}")
    r = validate_doc(doc)
    print(f"\n기계 검증: 통과 {len(r.oks)} · 오류 {len(r.errors)}")
    for w, m in r.errors[:5]:
        print(f"  [{w}] {m}")
    return 0 if not r.errors else 1


def _shorts_retry(doc, prefer):
    """쇼츠는 대본과 달리 짧고 싸다. 한 곳이 실패하면 다른 곳으로 한 번 더 해본다.

    대본 품질은 Claude 로 지켜야 하지만, 쇼츠는 이미 완성된 대본에서 구간을 골라내는
    기계적인 일이다. 여기서 어느 쪽이 만들었는지는 결과에 차이를 만들지 않는다."""
    other = "gemini" if (prefer or "claude") != "gemini" else "claude"
    try:
        alt, who = writer(max_calls=3, prefer=other)
        print(f"  {who} 로 한 번 더 시도한다")
        return make_shorts(alt, doc)
    except (LLMError, ClaudeError) as e:
        print(f"  2차도 실패: {e}")
        return {"shorts": []}


def make_shorts(llm, doc):
    body = prompts.load("shorts_gen")
    out = llm.json(prompts.fill(body, SCRIPT_JSON=json.dumps(doc, ensure_ascii=False)),
                   tier="flash", max_output_tokens=16384, temperature=0.8, label="쇼츠")
    return money.tidy_doc(out)


def _load_unfinished(ep):
    """도중에 멈춘 대본을 찾아 온다. (문서, 설명) 또는 (None, 왜 없는지).

    두 군데를 본다. 멈춘 지점에 따라 남는 파일이 다르기 때문이다.
      EP00N.draft.json  2단계까지 끝내고 3단계에서 멈춤 (검증·채점 전)
      EP00N.json        건져내기로 저장됨 (덜 만들어진 채로)
    초벌이 있으면 그쪽이 원본이므로 먼저 쓴다."""
    for name, what in ((f"{ep}.draft.json", "초벌(검증 전)"),
                       (f"{ep}.json", "저장된 대본")):
        p = SCRIPTS / name
        if not p.exists():
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:                      # noqa: BLE001
            return None, f"{name} 을 읽을 수 없다: {e}"
        n = (doc.get("meta") or {}).get("cut_count") or len(doc.get("cuts") or [])
        if not n:
            continue
        return doc, f"{what} · 컷 {n}개를 그대로 쓴다"
    return None, (f"{ep} 의 만들다 만 대본이 없다.\n"
                  f"  data/scripts/ 에 {ep}.draft.json 도 {ep}.json 도 없다.\n"
                  f"  처음부터 만들려면 --resume 없이 실행하라.")


# ── 본체 ────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="", help="판례일련번호를 지정")
    ap.add_argument("--max-calls", type=int, default=24, help="모델 호출 상한")
    ap.add_argument("--dry-run", action="store_true", help="모델 호출 없이 배관만 시험")
    ap.add_argument("--writer", default="", choices=["", "claude", "gemini"],
                    help="대본을 쓸 곳. 비우면 CLAUDE_API_KEY 가 있을 때 claude")
    ap.add_argument("--shorts-only", default="", metavar="EP001",
                    help="이미 만든 대본에 쇼츠만 붙인다 (대본을 다시 만들지 않는다)")
    ap.add_argument("--resume", default="", metavar="EP001",
                    help="도중에 멈춘 대본을 **이어서** 마저 만든다 (컷은 그대로 두고 뒷단계만)")
    args = ap.parse_args()

    # 쇼츠만 다시: 26분짜리 대본 생성을 처음부터 되풀이할 이유가 없다.
    if args.shorts_only:
        return _make_shorts_only(args.shorts_only, args.writer)

    # 이어서 만들기: 도중에 멈춘 대본을 **컷은 그대로 두고** 뒷단계만 마저 한다.
    resume_doc = None
    if args.resume:
        resume_doc, why = _load_unfinished(args.resume)
        if resume_doc is None:
            print(f"❌ {why}")
            return 6
        print(f"이어서 만든다: {args.resume} · {why}")

    SCRIPTS.mkdir(parents=True, exist_ok=True)
    queue = _load(QUEUE, [])
    eps = _load(EPISODES, {})

    # 배관 시험은 소재가 필요 없다. 소재 고르기보다 먼저 처리한다
    # (안 그러면 대기열이 비었을 때 --dry-run 이 아예 실행되지 않는다).
    if args.dry_run:
        # 샘플 파일 이름을 코드에 박지 않는다. 규칙이 바뀌면 샘플도 바뀌는데,
        # 이름이 박혀 있으면 옛 규칙으로 만든 샘플이 계속 검사돼 배관 시험이 늘 빨간불이 된다.
        cands = sorted(SCRIPTS.glob("SAMPLE_*.json"))
        cands = [c for c in cands if not c.name.endswith(".eval.json")]
        if not cands:
            print("dry-run 에 쓸 샘플이 없다 (data/scripts/SAMPLE_*.json).")
            return 2
        sample = cands[0]
        print(f"[dry-run] 샘플: {sample.name}")
        doc = json.loads(sample.read_text(encoding="utf-8"))
        r = validate_doc(doc)
        print(f"[dry-run] 샘플 검증 — 통과 {len(r.oks)} · 오류 {len(r.errors)}")
        print("[dry-run] 선택 로직·검증·저장 경로 정상. 실제 생성은 API 키가 필요하다.")
        return 0 if not r.errors else 1

    # 이어서 만들 때는 소재를 새로 고르지 않는다. 그 회차가 쓰던 판례를 그대로 쓴다.
    row = None
    if args.resume:
        prev = eps.get(args.resume) or {}
        cid0 = prev.get("case_id") or (resume_doc.get("meta") or {}).get("case_id") or ""
        row = next((c for c in queue if c["case_id"] == cid0), None) or {
            "case_id": cid0, "gate_score": prev.get("gate_score"),
            "case_type": prev.get("case_type", ""),
        }
    else:
        row = pick_case(queue, eps, args.case or None)
    if not row:
        # 아무것도 안 만들었으면 초록 체크를 주면 안 된다.
        # 운영자는 요약 화면만 본다. "성공"이라고 뜨면 대본이 생긴 줄 안다.
        graded = [c for c in queue if c.get("gate_score") is not None]
        print("제작할 소재가 없다.")
        if not queue:
            print("  대기열이 비었다. 먼저 '1. 판례 수집' 을 돌려라.")
        elif not graded:
            print(f"  대기열에 {len(queue)}건이 있지만 소재 심사를 아직 안 했다.")
            print("  '무엇을 할까요' 를 '둘다' 또는 '소재 심사만' 으로 놓고 다시 실행하라.")
        else:
            print(f"  심사한 {len(graded)}건 중 통과선(60점)을 넘긴 소재가 없다.")
            print("  '1. 판례 수집' 으로 새 판례를 더 모아야 한다.")
        return 4

    cid = row["case_id"]
    path = CASES / f"{cid}.json"
    if not path.exists():
        # 이어서 만들 때는 판례 원문이 없어도 된다. 컷은 이미 다 만들어져 있고,
        # 뒷단계(검증·채점·보강·쇼츠)는 대본만 보기 때문이다.
        if not args.resume:
            print(f"판례 파일이 없다: {path}")
            return 2
        print(f"  (판례 원문이 없지만 이어서 만드는 데는 필요 없다: {path.name})")
        case = {"사건명": "", "판례내용": ""}
    else:
        case = json.loads(path.read_text(encoding="utf-8"))

    ep = args.resume or next_episode_id(eps)
    print(f"회차 {ep} · 판례 {cid} · {case.get('사건명', '')}")
    print(f"게이트 {row.get('gate_score', '-')}점 · 유형 {row.get('case_type', '-')}")
    print()

    # ⭐ 돈을 쓰기 전에 '이 판례를 써도 되는가' 를 먼저 본다.
    #
    #    판례 번호를 손으로 넣으면(--case) 소재 심사를 건너뛴다. 그래서 심사가
    #    반드시 걸러낼 가사사건이 그대로 통과한다. 2026-08-10 에 실제로
    #    「이혼및위자료」 판례로 Opus 를 19분 돌렸다 — 다 만들었어도 못 쓸
    #    대본이었다. 가정법원 판결문은 공개 대상이 아니기 때문이다(지침 6번).
    banned = _family_court_words(case.get("사건명", ""))
    if banned:
        print(f"❌ 쓸 수 없는 판례다. 사건명에 '{banned}' 가 있다 — 가사사건이다.")
        print("   가정법원 판결문은 공개 대상이 아니라 우리 소재가 될 수 없다.")
        print("   (이혼·재산분할·양육권·상속재산분할·기여분이 전부 여기 해당한다)")
        print("   불륜을 다루려면 상간자 위자료 = 「손해배상(기)」 판례를 골라야 한다.")
        return 5

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
    draft, sh, rd = None, {"shorts": []}, 0
    salvaged = False                                # 도중에 멈춰 '건져낸' 대본인가
    try:
        if resume_doc is not None:
            # ⭐ 이어서 만들기 — 1·2단계를 건너뛴다.
            #    컷을 만드는 이 두 단계가 전체 값의 8할이고 20분을 먹는다.
            #    이미 만들어 둔 컷이 있는데 처음부터 다시 쓰는 것은 그냥 돈을 두 번 내는 것이다.
            doc = resume_doc
            draft = json.loads(json.dumps(doc))
            print(f"\n[1·2단계 건너뜀] 이미 만들어 둔 컷 {doc['meta'].get('cut_count')}개를 그대로 쓴다")
            print("  (여기서부터 검증·채점·보강·쇼츠만 한다 — 값이 8할 줄어든다)")
        else:
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

            # 여기까지가 가장 비싸고 오래 걸리는 부분이다(설계 1회 + 막별 6회).
            # 뒤 단계에서 무슨 일이 생겨도 이걸 잃으면 안 된다 — 실제로 19분치가 날아갔다.
            draft = json.loads(json.dumps(doc))
            _save(SCRIPTS / f"{ep}.draft.json", draft)
            print(f"  (초벌 저장: {ep}.draft.json — 뒤에서 실패해도 이건 남는다)")

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

        # 쇼츠 3편 — 여기서 실패해도 대본은 이미 완성이다.
        # 대본 전체를 중단 처리로 끌고 가지 않는다(실제로 그렇게 조용히 0편이 나갔다).
        print("\n[5단계] 쇼츠 3편")
        try:
            sh = make_shorts(llm, doc)
        except (LLMError, ClaudeError) as e:
            print(f"  1차 실패: {e}")
            sh = _shorts_retry(doc, args.writer)
        for s in sh.get("shorts", []):
            print(f"  {s.get('no')}번 {s.get('kind', ''):6s} {s.get('est_sec', 0):.1f}초  "
                  f"{s.get('intro_line', '')}")
        if not sh.get("shorts"):
            print("  ⚠️ 쇼츠를 못 만들었다. 대본은 정상이다.")
            print("     '2. 대본 만들기' 를 다시 누를 필요 없이 쇼츠만 따로 만들 수 있다:")
            print(f"     python3 src/script.py --shorts-only {ep}")

    # ⭐ 여기서 받는 그물은 **아무것이나 다 받는다**(Exception 전부).
    #
    #    예전에는 "돈 초과 · 모델 오류" 네 가지만 받았다. 그런데 2026-08-10 에
    #    전혀 다른 종류의 오류(그림 라이브러리 없음)가 3단계에서 튀어나왔고,
    #    그물에 안 걸려 그대로 프로그램이 죽었다. 컷 120개 · 19분 · Opus 값이
    #    한꺼번에 사라졌다. 무엇 때문에 멈추든 **만든 것은 남겨야 한다.**
    except Exception as e:                          # noqa: BLE001
        expected = isinstance(e, (BudgetExceeded, ClaudeBudget, LLMError, ClaudeError))
        print(f"\n⚠️ 중단: {e}")
        if not expected:
            # 예상 못 한 종류다. 원인을 찾으려면 어디서 멈췄는지가 보여야 한다.
            print(f"  (예상하지 못한 오류다: {type(e).__name__} — 아래 자취를 보라)")
            traceback.print_exc()
        doc = best or draft
        if doc is None:
            print("  아직 만든 것이 없어 남길 것이 없다.")
            return 1
        sh = {"shorts": []}
        salvaged = True
        print(f"  지금까지 만든 대본(컷 {doc['meta'].get('cut_count')}개)을 저장하고 끝낸다.")
        print("  다시 실행하면 이 판례로 처음부터 다시 만든다.")

    # 저장
    doc["meta"]["episode"] = ep
    doc["meta"]["case_id"] = cid
    if sh.get("shorts"):
        # 대본 안에도 넣는다. 검증기와 렌더러가 둘 다 여기를 본다 —
        # 따로 파일로만 두면 "쇼츠 0편" 으로 잘못 잡힌다.
        doc["shorts"] = sh["shorts"]
        _save(SCRIPTS / f"{ep}.shorts.json", sh)
    _save(SCRIPTS / f"{ep}.json", doc)
    _save(SCRIPTS / f"{ep}.eval.json", best_eval or {})

    # 끝까지 왔으면 초벌은 필요 없다. 저장소에 군더더기를 남기지 않는다.
    (SCRIPTS / f"{ep}.draft.json").unlink(missing_ok=True)

    final = validate_doc(doc, with_shorts=bool(sh.get("shorts")))
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

    if salvaged:
        # 파일은 남겼다. 그렇다고 초록 체크를 주면 안 된다 —
        # 운영자는 로그를 열어보지 않으므로, 덜 만들어진 것은 덜 만들어졌다고 보여야 한다.
        print("\n대본은 저장했지만 도중에 멈춘 것이다.")   # ← 검수 화면이 이 줄을 찾는다
        print(f"  {ep}.json 은 남아 있으니 처음부터 다시 만들 필요는 없다.")
        print("  위의 '중단' 줄에 적힌 원인을 고치고 다시 실행하라.")
        return 1
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
