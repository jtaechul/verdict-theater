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

심사할 차례 ('전부' 로 심사할 때 — gate.py · judge_order):
   쓸 만한 것(심사 통과 · 아직 안 만든 것)이 **적은 갈래부터 돌아가며** 한 건씩.
   ENOUGH(5)건 넘게 쌓인 갈래는 그 뒤 — 다른 갈래를 다 매긴 뒤에야 매긴다.
   (예전엔 기계 점수 순이라 가족 낱말·억 단위가 많은 상속이 늘 먼저 매겨졌다)
   매겨 봤더니 거의 안 나오는 갈래(10건 넘게 매겨 통과 10% 아래)는 맨 뒤.
   (10-01 밤: 쓸 만한 것 0건인 '재산' 이 맨 앞에 와 25건 전부 탈락 · 1,560원)
"""
import re

INHERIT = "상속"
INHERIT_MAX = 0.30
RECENT = 10

# ⭐⭐ 2026-10-01 — 어르신 갈래 다섯 (모으기·심사에서 한 번에 고르는 이름)
#    손님은 아이폰 화면으로만 누르신다. 갈래마다 따로 누르면 다섯 번을 차례로
#    기다려야 하고(모으기는 한 번에 하나만 돈다 — 겹쳐 누르면 앞의 것이 취소된다),
#    '전부' 로 누르면 옛 갈래까지 섞여 새 갈래가 몇 건씩밖에 안 매겨진다.
#    ⚠️ 이 이름은 collect.yml 선택지 · admin/worker.js 선택지와 **한 글자도** 같아야 한다.
SENIOR = ("노후사기", "효도계약", "치매", "땅·선산", "요양")
TOPIC_SETS = {"어르신 다섯": SENIOR}


def members(choice):
    """고른 이름 → 그 안의 갈래들. '어르신 다섯' 이면 다섯, 갈래 하나면 그 하나, 비면 ()."""
    choice = (choice or "").strip()
    if not choice:
        return ()
    return TOPIC_SETS.get(choice, (choice,))


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


# ⭐⭐ 2026-10-01 — 쓸 만한 것이 이만큼 쌓인 갈래는 '전부' 심사에서 맨 뒤로 간다
ENOUGH = 5
# ⭐⭐ 2026-10-02 — 매겨 봤더니 **거의 안 나오는 갈래**는 그보다도 뒤로 간다.
#    10-01 밤: 쓸 만한 것이 0건이던 '재산' 이 맨 앞에 와서 심사 25건을 다 가져갔고,
#    25건 전부 탈락했다 (세금·회사 다툼 — 1,560원). 재산 낱말(명의신탁·부당이득…)은
#    법률 일반어라 사람 이야기가 드물다. '모자라다' 와 '안 나온다' 는 다르다.
BARREN_MIN = 10       # 이만큼 매겨 봤는데
BARREN_RATE = 0.10    # 통과가 이 비율 아래면 '거의 안 나오는 갈래'


def judge_order(queue, used=(), limit=10, history=()):
    """'전부' 로 심사할 때 이번에 매길 것 — 아직 안 매긴 것 가운데 앞에서부터 limit 건.

    쓸 만한 것(심사 통과 · 아직 안 만든 것)이 적은 갈래부터 돌아가며 한 건씩,
    갈래 안에서는 기계 점수가 높은 것부터. ENOUGH 건 넘게 쌓인 갈래는 그 뒤,
    매겨 본 것이 BARREN_MIN 건 넘는데 통과가 BARREN_RATE 아래인 갈래는 맨 뒤.
    history = 대기열에서 치운 것(state/rejected.json) — 탈락 기록이 거기로 옮겨 가므로
    '거의 안 나오는가' 는 그것까지 보고 센다."""
    used = {str(u) for u in used or ()}
    judged, passed = {}, {}
    for c in list(queue or []) + list(history or []):
        if c.get("gate_score") is None:
            continue
        t = c.get("topic") or ""
        judged[t] = judged.get(t, 0) + 1
        passed[t] = passed.get(t, 0) + (1 if c.get("gate_pass") else 0)

    def barren(t):
        n = judged.get(t, 0)
        return n >= BARREN_MIN and passed.get(t, 0) / n < BARREN_RATE
    stock = {}
    for c in queue or []:
        if c.get("gate_pass") and str(c.get("case_id")) not in used:
            t = c.get("topic") or ""
            stock[t] = stock.get(t, 0) + 1
    groups = {}
    rest = [c for c in queue or [] if c.get("gate_score") is None]
    for c in sorted(rest, key=lambda c: -(c.get("machine_score") or 0)):
        groups.setdefault(c.get("topic") or "", []).append(c)

    def rank(t):
        return (stock.get(t, 0), -(groups[t][0].get("machine_score") or 0), t)

    hungry = sorted((t for t in groups if stock.get(t, 0) < ENOUGH and not barren(t)), key=rank)
    full = sorted((t for t in groups if stock.get(t, 0) >= ENOUGH and not barren(t)), key=rank)
    dry = sorted((t for t in groups if barren(t)), key=rank)
    out = []
    for tier in (hungry, full, dry):
        while len(out) < limit and any(groups[t] for t in tier):
            for t in tier:
                if groups[t] and len(out) < limit:
                    out.append(groups[t].pop(0))
    return out
