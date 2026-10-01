"""⭐ 다음 사건 고르기 — 갈래가 한쪽으로 쏠리지 않게 (값 0원)

⭐⭐⭐ 2026-10-01 손님: "판례를 좀 다양한 걸 수집하면 안 되냐? 너무 유류분이냐 상속하고
   이거에만 매몰되어 있는 것 같은데 … 니치는 50대부터 70대, 80대 어르신들인 거는 유지하고."
   만든 네 사건(S90~S93) 가운데 셋이 상속이었다. 모으기만 넓혀서는 안 고쳐진다 —
   점수가 높은 순으로만 고르면 상속이 또 맨 위에 온다.

고르는 차례 (관리자 페이지 '다음 사건 고르기' 와 story90.pick_case 가 **같은 규칙**):
   ① 바로 앞 편과 **같은 갈래는 뒤로** 미룬다 (연속 금지)
   ② 상속은 최근 RECENT 편 가운데 INHERIT_MAX(30%)를 넘게 되면 뒤로 미룬다
   ③ 그 안에서 **어르신(50대 이상) 이야기**를 먼저
   ④ 그다음 심사 점수 → 기계 점수
   ⚠️ 미룰 뿐 지우지 않는다 — 고를 것이 그것뿐이면 그것을 쓴다.
   ⚠️ 이 규칙을 바꾸면 admin/worker.js 의 mixOrder 도 같이 바꾼다
      (tools/topicmix_check.py 가 두 쪽 결과를 같은 시험으로 맞춰 본다).
"""
import re

INHERIT = "상속"
INHERIT_MAX = 0.30
RECENT = 10


def _sid_no(sid):
    m = re.search(r"\d+", str(sid or ""))
    return int(m.group(0)) if m else 0


def recent_topics(works, queue):
    """만든 사건들의 갈래 — 오래된 것부터 (사건 번호 차례). works = {sid: {case_id…}}"""
    by_case = {str(c.get("case_id")): (c.get("topic") or "") for c in queue or []}
    out = []
    for sid in sorted(works or {}, key=_sid_no):
        cid = str((works[sid] or {}).get("case_id") or "")
        if cid:
            out.append(by_case.get(cid, ""))
    return out


def held_back(topic, recent):
    """이 갈래를 지금 고르면 규칙에 걸리는가 — 걸리면 그 까닭(글), 아니면 ''."""
    last = recent[-1] if recent else ""
    if topic and topic == last:
        return f"바로 앞 편도 {topic}"
    if topic == INHERIT:
        # 최근에 상속이 하나도 없으면 막지 않는다 — 처음 몇 편은 한 편만 골라도 비율이
        # 50·100%로 튀어 상속을 영영 못 고르게 된다
        win = recent[-(RECENT - 1):] if RECENT > 1 else []
        n = sum(1 for t in win if t == INHERIT)
        share = (n + 1) / (len(win) + 1)
        if n and share > INHERIT_MAX:
            return f"최근 상속이 {round(share * 100)}%가 된다 (30% 넘음)"
    return ""


def order(ready, recent):
    """심사를 통과한 사건들을 고를 차례로 늘어놓는다 (앞의 것이 추천)."""
    def key(c):
        return (1 if held_back(c.get("topic") or "", recent) else 0,
                0 if c.get("senior") else 1,
                -(c.get("gate_score") or 0),
                -(c.get("machine_score") or 0))
    return sorted(ready or [], key=key)
