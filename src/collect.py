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
from lawapi import LawAPI, DailyLimitReached, DAILY_LIMIT, DEFAULT_OC  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "data" / "cases"
STATE = ROOT / "state" / "collect_state.json"
QUEUE = ROOT / "state" / "queue.json"

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
QUERIES = [
    # A군 상속 — 확보 43건. 채널의 기둥이므로 그대로 둔다
    "유류분", "유류분반환", "상속회복", "유언무효", "유언효력", "사인증여",
    "특별수익", "상속재산분할", "상속포기", "한정승인", "상속채무",
    # B군 재산 — 확보 15건
    "명의신탁", "증여계약해제", "부담부증여", "사해행위취소",
    "부당이득반환", "소유권이전등기말소", "근저당권설정말소",
    # C군 부양 — 확보 6건
    "부양료", "부양의무", "구상금", "요양병원", "성년후견", "의사무능력",
    # D군 불륜 — **개편.** 옛 검색어('부정행위','상간자','위자료')는 0건이었다.
    #            판결문이 실제로 쓰는 말로 바꾼다.
    "상간", "상간녀", "상간남", "정조", "혼인파탄", "부정한 행위",
    # E군 노년
    "재혼", "사실혼재산", "사실혼해소", "유족연금",
    # F군 가업
    "가업승계", "주식증여", "명의대여",
    # G군 기타
    "친생자관계", "인지청구", "기여분", "부양청구", "차용금", "유언집행",
    # H군 혼외자 — **신설.** 상속을 다 나눈 뒤에 나타난 자식이 '내 몫을 돈으로 달라'
    #            고 청구하는 사건(민법 제1014조). 가사가 아니라 민사다.
    "가액지급", "피인지자", "상속분가액", "가액반환",
    # I군 확장 — **신설.** 순수 민사이면서 50~60대에게 남 얘기가 아닌 소재.
    #            제사와 유골을 누가 모실지 형제가 다투는 사건은 대법원 전원합의체까지 있다.
    "제사주재자", "분묘", "유골", "봉안", "보증채무", "연대보증",
]

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
    return None


def score(case, today):
    """2차 — 본문을 보고 대본화 가능성에 점수를 매긴다."""
    body = case.get("판례내용", "")
    court = case.get("법원명", "")
    pts, why = 0, []

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
    ap.add_argument("--queries", default="", help="쉼표로 구분한 검색어. 비우면 40개 전부")
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

    budget = min(args.max_calls, DAILY_LIMIT - st["calls_today"])
    if budget <= 0:
        print(f"오늘은 이미 {st['calls_today']}회 호출했다. 상한 {DAILY_LIMIT}회.")
        print("내일 다시 실행하면 이어서 받는다.")
        return 0

    api = LawAPI(oc, used_today=st["calls_today"])
    CASES.mkdir(parents=True, exist_ok=True)

    todo = [q.strip() for q in args.queries.split(",") if q.strip()] or QUERIES
    fetched = set(st["fetched"])
    new_cases, hard_counts = [], {}

    print(f"검색어 {len(todo)}개 · 이번 실행 예산 {budget}회 "
          f"(오늘 누적 {st['calls_today']}/{DAILY_LIMIT})")
    print()

    try:
        # 1단계 — 목록을 받아 1차 배제
        candidates = []
        for q in todo:
            qs = st["queries"].setdefault(q, {"total": 0, "listed": False})
            if qs.get("listed"):
                continue
            if api.used - st["calls_today"] >= budget:
                break
            total, rows = api.search(q, page=1, display=100)
            qs["total"] = total
            qs["listed"] = True
            kept = 0
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
            print(f"  {q:12s} 총 {total:4d}건 → 1차 통과 {kept:3d}건")

        # 중복 제거 (검색어가 겹쳐 같은 판례가 여러 번 잡힌다)
        seen, uniq = set(), []
        for q, r in candidates:
            cid = r["판례일련번호"]
            if cid in seen:
                continue
            seen.add(cid)
            uniq.append((q, r))

        print()
        print(f"1차 통과 {len(uniq)}건 (중복 제거 후). 남은 예산으로 본문을 받는다.")
        print()

        # 2단계 — 본문을 받아 2차 가점
        for q, r in uniq:
            if api.used - st["calls_today"] >= budget:
                print("  … 예산 소진. 다음 실행에서 이어받는다.")
                break
            cid = r["판례일련번호"]
            case = api.fetch(cid)
            body = case.get("판례내용", "")
            if len(body) < MIN_BODY:
                hard_counts[f"본문 {MIN_BODY}자 미만"] = hard_counts.get(f"본문 {MIN_BODY}자 미만", 0) + 1
                fetched.add(cid)
                continue
            pts, why = score(case, today)
            case["_query"] = q
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
                "body_len": len(body),
                "gate_score": None,          # 3차 LLM 평가 전
            })
            print(f"  {cid:8s} {pts:3d}점  {case.get('법원명','')[:12]:14s} "
                  f"{case.get('사건명','')[:26]}")
    except DailyLimitReached as e:
        print(f"\n{e}")
    except Exception as e:                    # 네트워크 오류 등 — 여기까지는 저장한다
        print(f"\n⚠️ 중단: {type(e).__name__}: {e}")

    # 저장
    st["calls_today"] = api.used
    st["fetched"] = sorted(fetched)
    st["hard_rejected"] = {**st.get("hard_rejected", {}), **hard_counts}
    save_state(st)

    queue = json.loads(QUEUE.read_text(encoding="utf-8")) if QUEUE.exists() else []
    known = {q["case_id"] for q in queue}
    queue += [c for c in new_cases if c["case_id"] not in known]
    queue.sort(key=lambda c: (c.get("gate_score") or 0, c["machine_score"]), reverse=True)
    QUEUE.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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
