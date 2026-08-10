#!/usr/bin/env python3
"""판례 수집 + 1·2차 기계 선정.

    python3 src/collect.py --max-calls 180

무엇을 하나
    검색어 40개로 판례 목록을 받아, 기계가 걸러낼 수 있는 것을 먼저 걸러낸다.
    통과한 것만 본문을 받아 점수를 매기고 data/cases/ 에 저장한다.
    3차 LLM 드라마성 평가(src/gate.py)는 그다음이다.

왜 기계 필터가 먼저인가
    LLM 호출은 돈이 든다. 사건종류코드만 봐도 버릴 것을 LLM에 보내면 낭비다.
    걸러낼 지점은 언제나 가장 싼 단계여야 한다.

하루 200회 상한
    법제처 일일 한도가 공개되지 않아 안전 마진을 둔다.
    한 번에 다 못 받으므로 state/collect_state.json 에 진행 상황을 남기고,
    다음 실행이 이어서 받는다. 백필은 3일에 나눠 끝낸다.
"""

import argparse
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lawapi import (LawAPI, DailyLimitReached, DAILY_LIMIT, DEFAULT_OC,  # noqa: E402
                    FULLTEXT)

# 판례를 어디까지 뒤질지. 본문까지 뒤진다 — 제목만 뒤지면 '상간' 같은 말이 통째로 빠진다.
# 이 값이 바뀌면 아래 main() 이 '이미 찾아봤다' 표시를 지우고 전부 다시 훑는다.
SEARCH_SCOPE = FULLTEXT

# 예산 가운데 '목록 보기' 에 쓸 몫. 나머지는 본문 받기에 쓴다.
# 목록만 잔뜩 보고 본문을 못 받으면 저장되는 판례가 0건이 된다.
LIST_SHARE = 0.35

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "cases"
STATE = ROOT / "state" / "collect_state.json"
QUEUE = ROOT / "state" / "queue.json"
LAST = ROOT / "state" / "collect_last.json"   # 지난 수집 결과 (관리자 페이지가 읽는다)

# ── 검색어 사전 (CLAUDE.md 5번) ───────────────────────────
#
# ⭐ v2 — 실측으로 고쳤다 (2026-08-03).
#    수집된 판례 112건을 주제별로 세어 보니 **불륜 0건 · 혼외자 0건** 이었다.
#    검색은 하고 있었는데(부정행위 428건, 위자료 304건, 친생자 92건, 인지청구 70건)
#    한 건도 안 들어왔다. 원인 세 가지:
#
#      ① '부정행위' 는 법률 문서에서 **세금(조세포탈)·보험(고지의무)·징계** 쪽 뜻으로
#         훨씬 많이 쓰인다. 428건이 걸려도 우리가 찾는 불륜 사건이 아니다.
#      ② '상간자' 는 판결문에 거의 안 쓰인다 — 검색 결과 **단 1건**.
#         실제 사건명은 「손해배상(기)」 로 붙는다.
#      ③ 친생자관계·인지청구는 **가정법원** 사건이라 판결문이 공개되지 않는다.
#         실제로 282건이 '민사 아님(가사)' 로 배제됐다. 규칙 문제가 아니라 구할 수가 없다.
#
#    그래서 **들어가는 문을 바꾼다.** 같은 이야기라도 어떤 소송으로 갔느냐에 따라
#    판결문을 구할 수 있고 없고가 갈린다.
#      불륜   : 이혼(가사) ✗   →  상간자 위자료 = 손해배상(기)(민사) ○
#      혼외자 : 인지청구(가사) ✗ →  민법 제1014조 가액지급청구(민사) ○
#
# ⚠️ D·H·I군은 **아직 실적이 없는 후보**다. 수집을 한 번 돌려 실제로 걸리는지
#    확인한 뒤, 헛도는 검색어는 빼고 잘 걸리는 것만 남긴다.
# ⭐ 검색어를 **갈래(topic)별로** 묶는다. 갈래는 두 가지 일을 한다.
#    ① 대기열 화면에서 갈래별로 골라 볼 수 있다 (상속만 잔뜩 뜨는 것을 막는다)
#    ② 갈래마다 '진짜 그 사건인지' 확인하는 낱말이 달라진다 (아래 TOPIC_WORDS)
QUERY_GROUPS = {
    "상속": ["유류분", "유류분반환", "상속회복", "유언무효", "유언효력", "사인증여",
             "특별수익", "상속재산분할", "상속포기", "한정승인", "상속채무", "유언집행",
             "기여분"],
    # ⭐ 불륜(상간자 소송) — 2026-08-10 전면 재정비.
    #    옛 기록의 '0건' 은 검색어 탓이 아니라 **제목만 뒤지고 있어서** 였다.
    #    상간자 소송의 사건명은 '손해배상(기)' 라 제목만 봐서는 영영 안 걸린다.
    #    본문까지 뒤지고 여러 쪽을 넘겨 받으니 중복 빼고 586건이 1차를 통과했다.
    #    ⚠️ '정조' 를 낱말로 쓰면 안 된다. 옛 판결문에서 '정조(定租)'는 소작료를
    #       뜻하고, '환지확정조서'·'청산확정조서' 같은 말에도 글자가 들어 있어
    #       1990~2000년대 땅 사건이 무더기로 딸려 온다(실측 확인). '정조의무'로 쓴다.
    #    ⚠️ '제3자 위자료'(1,678건)도 뺐다. 넓기만 하고 걸리는 것은 교통사고·
    #       국가배상이라 예산만 먹는다.
    "불륜": ["상간", "상간자", "상간녀", "상간남", "불륜", "정조의무", "혼인파탄",
             "부정한 행위", "배우자 부정행위", "부정행위 위자료", "간통", "외도"],
    "재산": ["명의신탁", "증여계약해제", "부담부증여", "사해행위취소",
             "부당이득반환", "소유권이전등기말소", "근저당권설정말소"],
    "부양": ["부양료", "부양의무", "구상금", "요양병원", "성년후견", "의사무능력",
             "부양청구"],
    "노년": ["재혼", "사실혼재산", "사실혼해소", "유족연금"],
    "가업": ["가업승계", "주식증여", "명의대여"],
    # 상속을 다 나눈 뒤 나타난 자식이 '내 몫을 돈으로 달라' 고 하는 사건(민법 1014조).
    # 가사가 아니라 민사다.
    "혼외자": ["가액지급", "피인지자", "상속분가액", "가액반환", "친생자관계", "인지청구"],
    # 제사와 유골을 누가 모실지 형제가 다투는 사건. 대법원 전원합의체까지 있다.
    "제사": ["제사주재자", "분묘", "유골", "봉안"],
    "빚": ["보증채무", "연대보증", "차용금"],
}
QUERIES = [q for qs in QUERY_GROUPS.values() for q in qs]
TOPIC_OF = {q: t for t, qs in QUERY_GROUPS.items() for q in qs}

# ── 1차 하드 배제 ────────────────────────────────────────
CIVIL_CODE = "400101"                     # 민사
BAD_SOURCE = "국세법령정보시스템"           # 세금 사건이 민사로 위장 유입
MIN_BODY = 3000                           # 본문 3,000자 미만 배제

# 판결유형 — "정확히 '판결'만 통과"로 짜면 안 된다. 실측(2026-07-30)에서 확인:
#   실제 값은 '판결', '원고일부승소', '원고패소', '전원합의체 판결',
#   '판결 : 상고', '판결 : 확정', '판결 : 항소', '제1민사부판결 : 확정' 등으로 흩어진다.
#   전부 판결이다. 정확 일치로 거르면 민사 사건의 상당수를 그냥 버린다.
# 지침서의 의도는 "결정·명령은 사실관계가 부족하니 뺀다"는 것이므로 금지 목록으로 뒤집는다.
NOT_A_JUDGMENT = ["결정", "명령", "조정", "화해", "취하", "이송", "회부"]

BANNED = [
    "과세", "부과처분", "환급", "양도소득", "증여세", "상속세", "취득세", "종합소득",
    "아동", "청소년", "강간", "강제추행", "성폭력", "음란", "성매매",
    "선거", "정당", "정치자금", "특허", "상표", "저작권침해", "산업재해",
]

# ⭐ 손해배상 사건은 **괄호 안 한 글자로 종류가 갈린다.** 이것을 안 보면
#    의료사고·교통사고·국가배상이 상간자 소송인 척 잔뜩 섞여 들어온다.
#    (2026-08-10 실측: 불륜 낱말로 걸린 586건 중 의료 23·국가 18·자동차 9건이 섞여 있었다)
#    본문을 받기 **전에** 사건명만 보고 걸러내므로 값도 아낀다.
#      (기) 그 밖의 것 ← 상간자 위자료가 여기 들어온다  ○
#      (의) 의료 · (국) 국가 · (자) 자동차 · (산) 산업재해 · (환) 환경 · (건) 건설  ✗
BAD_DAMAGE_KINDS = ["(의)", "(국)", "(자)", "(산)", "(환)", "(건)", "(지)"]

# 갈래마다 '진짜 그 사건인지' 가려내는 낱말. 본문에 이 중 몇 개가 나오는지로 가점한다.
# 불륜 갈래에 이것이 없으면, '부정한 행위' 라는 흔한 법률 표현 한 마디 때문에
# 엉뚱한 사건(임금·구상금)이 위로 올라온다.
#
# ⚠️ 여기에 **흔한 말을 넣으면 안 된다.** 두 번 데였다(2026-08-10 실측):
#     · '정조'  → '환지확정조서' 의 글자에 걸려 1990년대 땅 사건이 무더기로 통과
#     · '혼인관계' → 이혼·재산분할 등 아무 가정 사건에나 나와 걸러내는 구실을 못 함
#    그래서 불륜은 **그 사건에만 나오는 말**로만 확인한다.
TOPIC_WORDS = {
    "불륜": ["상간", "부정한 행위", "부정행위", "정조의무", "간통", "외도"],
    "상속": ["상속", "유류분", "유언", "피상속인", "상속인", "증여"],
    "부양": ["부양", "요양", "간병", "부모"],
    "혼외자": ["인지", "친생자", "혼외", "상속분"],
    "제사": ["제사", "분묘", "유골", "봉안", "선산"],
}

# ── 2차 기계 가점 ────────────────────────────────────────
# ⚠️ 판결문은 당사자를 '원고·피고·소외1'로 비실명 처리해 제공한다.
#    그래서 '어머니·아들' 같은 일상어만 세면 정작 우리가 원하는 하급심 상속 사건이
#    낮은 점수를 받는다. 판결문이 실제로 쓰는 관계어를 함께 넣는다.
FAMILY_WORDS = [
    # 일상 호칭
    "어머니", "아버지", "아들", "딸", "며느리", "사위", "형제", "자매", "남편", "아내",
    "장남", "차남", "손자", "손녀", "시어머니", "시아버지", "올케", "동서",
    # 판결문이 쓰는 관계어
    "배우자", "자녀", "망인", "피상속인", "상속인", "유족", "혼인", "재혼", "부양", "친생자",
]


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"date": "", "calls_today": 0, "queries": {}, "fetched": [], "hard_rejected": {}}


def save_state(st):
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def hard_reject(row):
    """1차 — 목록 정보만으로 버릴 수 있는 것. 본문을 받기 전에 판단한다."""
    if row.get("사건종류코드") != CIVIL_CODE:
        return f"민사 아님({row.get('사건종류명') or row.get('사건종류코드')})"
    if row.get("데이터출처명") == BAD_SOURCE:
        return "세금 사건(국세법령정보시스템)"
    kind = row.get("판결유형", "")
    for w in NOT_A_JUDGMENT:
        if w in kind:
            return f"판결 아님({kind})"
    name = row.get("사건명", "")
    for w in BANNED:
        if w in name:
            return f"금지어 '{w}'"
    # 손해배상 중 의료·교통·국가배상 등은 가족 이야기가 아니다. 본문 받기 전에 뺀다.
    if "손해배상" in name:
        for k in BAD_DAMAGE_KINDS:
            if k in name:
                return f"가족 얘기 아님(손해배상{k})"
    return None


def topic_hits(body, topic):
    """본문에 그 갈래 낱말이 몇 종류 나오는지. 0이면 그 갈래 사건이 아니다."""
    tw = TOPIC_WORDS.get(topic or "")
    if not tw:
        return 1          # 확인 낱말이 없는 갈래는 통과시킨다
    return sum(1 for w in tw if w in body)


def score(case, today, topic=""):
    """2차 — 본문을 보고 대본화 가능성에 점수를 매긴다.

    topic 을 주면 **그 갈래가 맞는지**까지 본다. 이것이 없으면 '부정한 행위'
    같은 흔한 법률 표현 한 마디에 걸린 엉뚱한 사건이 위로 올라온다.
    """
    body = case.get("판례내용", "")
    court = case.get("법원명", "")
    pts, why = 0, []

    # 갈래 확인 — 그 갈래의 낱말이 본문에 여럿 나와야 진짜다.
    # (아예 하나도 없는 것은 여기 오기 전에 topic_hits() 로 걸러진다)
    tw = TOPIC_WORDS.get(topic or "")
    if tw:
        n = topic_hits(body, topic)
        if n >= 2:
            pts += 25; why.append(f"{topic} 확실 +25")
        elif n == 1:
            pts += 5; why.append(f"{topic} 약함 +5")

    # ⚠️ 법원명은 줄임말로도 온다. 실측: '청주지법', '서울고법', '부산고등법원(창원)'.
    #    '지방법원'만 찾으면 '청주지법'이 1심 가점 30점을 통째로 놓친다.
    if "지방법원" in court or "지법" in court:
        pts += 30; why.append("1심 +30")
    elif "고등법원" in court or "고법" in court:
        pts += 20; why.append("2심 +20")
    elif "대법원" in court:
        pts += 5; why.append("대법원 +5")

    if case.get("_sections", {}).get("인정사실"):
        pts += 25; why.append("인정사실 +25")

    hits = sum(1 for w in FAMILY_WORDS if w in body)
    fam = min(15, hits * 3)
    if fam:
        pts += fam; why.append(f"가족어 {hits}종 +{fam}")

    d = case.get("선고일자", "")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
        years = (today - datetime.strptime(d, "%Y-%m-%d").date()).days / 365.25
        if years <= 5:
            pts += 10; why.append("최근 5년 +10")

    if re.search(r"\d\s*억", body):
        pts += 10; why.append("억 단위 +10")

    if len(body) > 20000:
        pts += 10; why.append("장문 +10")

    return pts, why


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-calls", type=int, default=DAILY_LIMIT,
                    help=f"이번 실행에서 쓸 최대 호출 수 (기본 {DAILY_LIMIT})")
    ap.add_argument("--queries", default="", help="쉼표로 구분한 검색어. 비우면 전부")
    ap.add_argument("--topic", default="", help="갈래만 지정 (상속·불륜·부양…). 그 갈래 검색어만 훑는다")
    ap.add_argument("--pages", type=int, default=3,
                    help="검색어 하나당 몇 쪽까지 넘겨 볼지 (한 쪽 100건, 기본 3)")
    args = ap.parse_args()

    oc = os.environ.get("LAW_OC", "").strip()
    if oc:
        print(f"법제처 인증키: 환경변수 LAW_OC 사용 ({oc[:4]}…)")
    else:
        oc = DEFAULT_OC
        print(f"법제처 인증키: 기본값 사용 ({oc}). 비밀이 아니므로 등록 없이 동작한다.")

    today = date.today()
    st = load_state()
    if st.get("date") != today.isoformat():          # 날이 바뀌면 호출 수를 되돌린다
        st["date"] = today.isoformat()
        st["calls_today"] = 0

    # ⭐ 뒤지는 범위가 바뀌면 **전에 찾아본 기록을 무효로 한다.**
    #    안 그러면 '이미 찾아봤다(listed)' 표시 때문에 새 방식으로 다시 안 찾는다.
    #    2026-08-10: 제목만 뒤지던 것을 본문까지 뒤지도록 고쳤으므로, 예전에
    #    제목만으로 훑어 본 41개 검색어를 전부 다시 훑어야 한다.
    if st.get("scope") != SEARCH_SCOPE:
        n = sum(1 for v in st.get("queries", {}).values() if v.get("listed"))
        for v in st.get("queries", {}).values():
            v["listed"] = False
        st["scope"] = SEARCH_SCOPE
        if n:
            print(f"뒤지는 범위가 바뀌었다 → 전에 찾아본 {n}개 검색어를 다시 훑는다.")
            print("(예전 기록은 '제목만' 뒤진 결과라 그대로 두면 놓친 판례를 영영 못 받는다)")
        print()

    budget = min(args.max_calls, DAILY_LIMIT - st["calls_today"])
    if budget <= 0:
        print(f"오늘은 이미 {st['calls_today']}회 호출했다. 상한 {DAILY_LIMIT}회.")
        print("내일 다시 실행하면 이어서 받는다.")
        return 0

    api = LawAPI(oc, used_today=st["calls_today"])
    CASES.mkdir(parents=True, exist_ok=True)

    # 무엇을 훑을지 — 직접 적은 낱말 > 갈래 지정 > 전부
    todo = [q.strip() for q in args.queries.split(",") if q.strip()]
    if not todo and args.topic:
        todo = QUERY_GROUPS.get(args.topic.strip(), [])
        if not todo:
            print(f"'{args.topic}' 이라는 갈래는 없다. 있는 갈래: "
                  + " · ".join(QUERY_GROUPS))
            return 1
        print(f"갈래 '{args.topic}' 만 훑는다 ({len(todo)}개 낱말)")
    todo = todo or QUERIES
    fetched = set(st["fetched"])
    new_cases, hard_counts = [], {}
    ran = []            # 이번에 실제로 훑은 검색어별 결과 (관리자 페이지에서 보여준다)
    left = []           # 목록엔 올랐는데 예산이 모자라 못 받은 것 (다음 실행이 이어받는다)

    print(f"검색어 {len(todo)}개 · 이번 실행 예산 {budget}회 "
          f"(오늘 누적 {st['calls_today']}/{DAILY_LIMIT})")
    print()

    # ⭐ 예산을 **목록 보기와 본문 받기로 나눈다.**
    #    목록만 잔뜩 보면 정작 본문을 못 받아 저장되는 판례가 0건이 된다.
    #    (2026-08-10 에 실제로 그랬다 — 목록은 통과 19건인데 저장은 2건)
    list_budget = max(1, int(budget * LIST_SHARE))

    try:
        # 1단계 — 목록을 받아 1차 배제
        # ⚠️ 한 쪽(100건)만 보면 안 된다. '부정한 행위' 는 46,563건이라
        #    첫 쪽만 보고 끝내면 나머지를 통째로 못 본다. 여러 쪽을 넘겨 받는다.
        candidates = []
        for q in todo:
            qs = st["queries"].setdefault(q, {"total": 0, "listed": False})
            # 전에 1쪽만 봤는데 이번에 3쪽을 보라고 했으면 **다시 훑어야 한다.**
            # 안 그러면 '이미 찾아봤다' 표시에 막혀 나머지 쪽을 영영 못 본다.
            if qs.get("listed") and qs.get("pages", 1) >= args.pages:
                continue
            if api.used - st["calls_today"] >= list_budget:
                print("  … 목록 예산 소진. 나머지 낱말은 다음 실행에서 이어받는다.")
                break
            total, kept, done = 0, 0, 0
            for page in range(1, args.pages + 1):
                if api.used - st["calls_today"] >= list_budget:
                    break
                done = page
                total, rows = api.search(q, page=page, display=100, scope=SEARCH_SCOPE)
                for r in rows:
                    cid = r.get("판례일련번호")
                    if not cid or cid in fetched:
                        continue
                    reason = hard_reject(r)
                    if reason:
                        hard_counts[reason] = hard_counts.get(reason, 0) + 1
                        continue
                    candidates.append((q, r))
                    kept += 1
                if len(rows) < 100:          # 마지막 쪽까지 봤다
                    break
            qs["total"] = total
            qs["listed"] = True
            qs["pages"] = max(qs.get("pages", 0), done)   # 몇 쪽까지 봤는지 기억한다
            ran.append({"q": q, "total": total, "kept": kept})
            print(f"  {q:12s} 총 {total:4d}건 → 1차 통과 {kept:3d}건")

        # ⭐ 지난번에 **목록에는 올렸는데 본문을 못 받은 것**을 먼저 이어받는다.
        #    이게 없으면 큰 구멍이 생긴다: 낱말은 '이미 찾아봤음'으로 표시되는데
        #    본문은 예산이 모자라 몇 건밖에 못 받는다. 그러면 다음에 다시 돌려도
        #    목록을 건너뛰어 **남은 수백 건을 영영 못 받는다.**
        #    (2026-08-10: 불륜 후보 586건 중 83건만 받고 예산이 끝났다)
        pend = [(p["q"], {"판례일련번호": p["id"], "법원명": p.get("court", "")})
                for p in st.get("pending", [])
                if p.get("id") not in fetched]
        if pend:
            print(f"지난번에 못 받은 {len(pend)}건을 먼저 이어받는다.")
        candidates = pend + candidates

        # 중복 제거 (검색어가 겹쳐 같은 판례가 여러 번 잡힌다)
        seen, uniq = set(), []
        for q, r in candidates:
            cid = r["판례일련번호"]
            if cid in seen or cid in fetched:
                continue
            seen.add(cid)
            uniq.append((q, r))

        # ⭐ **좁은 낱말로 걸린 것부터 본문을 받는다.**
        #    예산은 한정돼 있는데 순서를 안 정하면, '제3자 위자료'(1,678건) 처럼
        #    아무 데나 걸리는 넓은 낱말이 예산을 먼저 다 먹고, 정작 '상간자'(18건)
        #    처럼 딱 맞는 판례를 못 받는다. 좁은 낱말 = 딱 맞는 사건이다.
        #    같은 낱말 안에서는 1심(지방법원)을 먼저 — 사실관계가 자세해 대본이 잘 나온다.
        # 낱말이 얼마나 넓은지. 이번에 안 훑은 낱말(이어받는 것)은 지난 기록에서 본다.
        width = {q: v.get("total", 99999) for q, v in st.get("queries", {}).items()}
        width.update({r["q"]: r["total"] for r in ran})

        def order(item):
            q, r = item
            court = r.get("법원명", "")
            rank = 0 if ("지방법원" in court or "지법" in court) else (
                   1 if ("고등법원" in court or "고법" in court) else 2)
            return (width.get(q, 99999), rank)

        uniq.sort(key=order)

        print()
        print(f"1차 통과 {len(uniq)}건 (중복 제거 후). 남은 예산으로 본문을 받는다.")
        print("(좁은 낱말로 걸린 것 · 1심부터 받는다)")
        print()

        # 2단계 — 본문을 받아 2차 가점
        for i, (q, r) in enumerate(uniq):
            if api.used - st["calls_today"] >= budget:
                left = uniq[i:]
                print(f"  … 예산 소진. 남은 {len(left)}건은 다음 실행에서 이어받는다.")
                break
            cid = r["판례일련번호"]
            case = api.fetch(cid)
            body = case.get("판례내용", "")
            if len(body) < MIN_BODY:
                hard_counts[f"본문 {MIN_BODY}자 미만"] = hard_counts.get(f"본문 {MIN_BODY}자 미만", 0) + 1
                fetched.add(cid)
                continue
            topic = TOPIC_OF.get(q, "")
            # ⭐ 낱말만 스치고 지나간 엉뚱한 사건은 **대기열에 넣지 않는다.**
            #    '부정한 행위' 는 흔한 법률 표현이라 임금·구상금 사건에도 나온다.
            #    그런 것까지 쌓이면 대기열이 원하지 않는 것으로 뒤덮인다.
            #    (2026-08-10 손님: "소재 대기열에는 내가 원하지 않는 것만 띄워놓고")
            if not topic_hits(body, topic):
                k = f"{topic} 사건이 아님(낱말만 스침)"
                hard_counts[k] = hard_counts.get(k, 0) + 1
                fetched.add(cid)
                continue
            pts, why = score(case, today, topic)
            case["_query"] = q
            case["_topic"] = topic
            case["_machine_score"] = pts
            case["_machine_why"] = why
            (CASES / f"{cid}.json").write_text(
                json.dumps(case, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            fetched.add(cid)
            new_cases.append({
                "case_id": cid,
                "사건명": case.get("사건명", ""),
                "법원명": case.get("법원명", ""),
                "선고일자": case.get("선고일자", ""),
                "machine_score": pts,
                "query": q,
                "topic": topic,              # 갈래 — 대기열에서 골라 보는 데 쓴다
                "body_len": len(body),
                "gate_score": None,          # 3차 LLM 평가 전
            })
            print(f"  {cid:8s} {pts:3d}점  {topic:4s} {case.get('법원명','')[:12]:14s} "
                  f"{case.get('사건명','')[:26]}")
    except DailyLimitReached as e:
        print(f"\n{e}")
    except Exception as e:                    # 네트워크 오류 등 — 여기까지는 저장한다
        print(f"\n⚠️ 중단: {type(e).__name__}: {e}")

    # 저장
    st["calls_today"] = api.used
    st["fetched"] = sorted(fetched)
    # 못 받고 남은 것을 적어 둔다. 다음 실행이 여기서부터 이어받는다.
    st["pending"] = [{"q": q, "id": r["판례일련번호"], "court": r.get("법원명", "")}
                     for q, r in left if r["판례일련번호"] not in fetched]
    st["hard_rejected"] = {**st.get("hard_rejected", {}), **hard_counts}
    save_state(st)

    queue = json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else []
    # ⚠️ '이미 본 것' 은 대기열 **더하기 쓰지 않기로 한 것** 이다.
    #    쓰지 않기로 한 판례는 화면에서 치우려고 state/rejected.json 으로 옮긴다
    #    (tools/queue_clean.py). 그것까지 봐야 **다시 받아 다시 평가하는 낭비**가 없다.
    #    2026-08-09 손님: "쓰지 않기로 함으로 구분된 판례는 삭제해도 되지 않아?"
    rej = ROOT / "state" / "rejected.json"
    seen_out = set()
    if rej.exists():
        try:
            seen_out = {q["case_id"] for q in json.loads(rej.read_text(encoding="utf-8"))}
        except Exception:
            seen_out = set()
    known = {q["case_id"] for q in queue} | seen_out
    queue += [c for c in new_cases if c["case_id"] not in known]
    # 예전에 받아 둔 것들은 갈래가 없다. 찾은 낱말을 보고 채워 넣는다(스스로 고쳐진다).
    for c in queue:
        if not c.get("topic"):
            c["topic"] = TOPIC_OF.get(c.get("query", ""), "")
    queue.sort(key=lambda c: (c.get("gate_score") or 0, c["machine_score"]), reverse=True)
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ⭐ 이번 수집 결과를 **파일로 남긴다.** 관리자 페이지가 이것을 읽어 보여준다.
    #    (2026-08-10 손님: "수집 결과 보기는 관리자 페이지 메뉴나 버튼으로 넣어야 할 거
    #     아니야? 내가 채팅창 들어와서 봐야겠냐?")
    #    깃허브 실행 기록을 뒤지지 않아도 아이폰에서 바로 보이게 하려는 것이다.
    LAST.write_text(json.dumps({
        "at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "searched": len(ran),                    # 이번에 훑은 검색어 수
        "found": sum(r["total"] for r in ran),   # 검색으로 걸린 총 건수
        "passed": sum(r["kept"] for r in ran),   # 1차를 통과한 건수
        "new": len(new_cases),                   # 실제로 새로 받아 저장한 건수
        "queue": len(queue),                     # 저장한 뒤 대기열 총 건수
        "calls": api.used,
        "limit": DAILY_LIMIT,
        "queries": sorted(ran, key=lambda r: -r["kept"]),
        "dropped": sorted(({"why": k, "n": v} for k, v in hard_counts.items()),
                          key=lambda r: -r["n"]),
        "top": [{"id": c["case_id"], "score": c["machine_score"],
                 "name": c["사건명"][:40], "court": c["법원명"], "q": c["query"],
                 "topic": c.get("topic", "")}
                for c in sorted(new_cases, key=lambda c: -c["machine_score"])[:8]],
        # 갈래별로 몇 건 받았는지 — 화면에서 한눈에 보시라고
        "topics": sorted(
            ({"topic": t, "n": sum(1 for c in new_cases if c.get("topic") == t)}
             for t in {c.get("topic", "") for c in new_cases}),
            key=lambda r: -r["n"]),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print()
    print("─" * 60)
    print(f"새로 받은 판례 {len(new_cases)}건 · 대기열 총 {len(queue)}건")
    print(f"오늘 호출 {api.used}/{DAILY_LIMIT}회")
    if hard_counts:
        print("\n1차에서 걸러낸 것")
        for k, v in sorted(hard_counts.items(), key=lambda x: -x[1]):
            print(f"  {v:4d}건  {k}")
    if new_cases:
        top = sorted(new_cases, key=lambda c: -c["machine_score"])[:5]
        print("\n기계 점수 상위 5건")
        for c in top:
            print(f"  {c['machine_score']:3d}점  {c['case_id']}  {c['사건명'][:30]}")
    print("\n다음: python3 src/gate.py  (3차 LLM 드라마성 평가)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
