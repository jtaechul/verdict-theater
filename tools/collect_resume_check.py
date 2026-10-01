#!/usr/bin/env python3
"""⭐ 모으다 **끊겨도** 찾은 판례를 잃지 않는가 — 값 0원 · 인터넷 0회

    python3 tools/collect_resume_check.py

2026-10-01 — 새 갈래(노후사기) 시험 수집 중 법제처 연결이 끊겼다. 낱말 다섯을 훑어
1차 통과 136건을 찾았는데 **한 건도 남지 않았다**: 낱말은 '찾아봤음' 으로 적혀 다음
실행도 다시 안 찾고, 찾은 목록은 예산이 다 찼을 때만 pending 으로 남기게 돼 있었다.

진짜 collect.main 을 가짜 법제처로 돌려 본다 (임시 폴더 — 진짜 상태 파일은 안 건드린다):
  ① 목록을 보다 끊김 → 찾아 둔 것이 pending 으로 남는다
  ② 다음 실행이 그것을 이어받아 본문을 받는다 (목록을 다시 안 봐도)
  ③ 본문을 받다 끊김 → 못 받은 나머지가 pending 으로 남는다
  ④ 갈래를 골라 누르면 그 갈래 남은 것만 이어받고, 딴 갈래 남은 것은 그대로 둔다
  ⑤ '어르신 다섯' — 다섯 갈래 낱말만 훑고, 본문도 갈래를 돌아가며 받는다
"""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from urllib.error import URLError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import collect as C                                          # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


# 노후사기·치매 확인 낱말이 다 들어 있는 3,000자 넘는 본문
BODY = ("【주 문】 피고는 원고에게 1억 원을 지급하라. 【이 유】 1. 기초사실 원고는 피고의 "
        "권유로 노후자금을 투자하였고, 피고는 원금과 고수익을 약속하였으나 이를 편취하였다. "
        "당시 원고의 어머니는 치매로 의사능력이 없었고 후견인이 선임되었다. "
        "원고는 부모를 모시고 부양하였고, 선산의 분묘로 가는 통행로가 막혔으며, "
        "아버지는 요양원에 입소한 노인이었다. ") * 30


def row(n):
    return {"판례일련번호": f"9{n:05d}", "사건명": "약정금", "사건번호": f"2024가합{n}",
            "선고일자": "2024.05.01", "법원명": "서울중앙지방법원", "법원종류코드": "",
            "사건종류명": "민사", "사건종류코드": C.CIVIL_CODE, "판결유형": "판결",
            "선고": "선고", "데이터출처명": "대법원"}


class Fake:
    """법제처 대신 — 정해 둔 곳에서 연결이 끊긴다."""
    fail_search = set()
    fail_fetch_after = None
    totals = {}            # 갈래 → 검색 총 건수 (좁은 낱말 · 넓은 낱말 흉내)

    def __init__(self, oc, used_today=0, limit=C.DAILY_LIMIT):
        self.used = used_today
        self.n_fetch = 0

    def search(self, query, page=1, display=100, scope=None):
        self.used += 1
        if query in Fake.fail_search:
            raise URLError("[Errno 104] Connection reset by peer")
        base = C.QUERIES.index(query) * 10
        return Fake.totals.get(C.TOPIC_OF.get(query), 3), [row(base + i) for i in range(3)]

    def fetch(self, case_id):
        self.used += 1
        if Fake.fail_fetch_after is not None and self.n_fetch >= Fake.fail_fetch_after:
            raise URLError("[Errno 104] Connection reset by peer")
        self.n_fetch += 1
        return {"판례정보일련번호": case_id, "사건명": "약정금",
                "사건번호": f"2024가합{case_id}", "선고일자": "2024-05-01",
                "법원명": "서울중앙지방법원", "판례내용": BODY}


def run(td, topic, calls=40):
    C.CASES, C.STATE = td / "cases", td / "collect_state.json"
    C.QUEUE, C.LAST = td / "queue.json", td / "collect_last.json"
    C.LawAPI = Fake
    sys.argv = ["collect.py", "--topic", topic, "--max-calls", str(calls), "--pages", "1"]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        C.main()
    st = json.loads(C.STATE.read_text(encoding="utf-8"))
    q = json.loads(C.QUEUE.read_text(encoding="utf-8")) if C.QUEUE.exists() else []
    return st, q, out.getvalue()


print("⭐ 끊겨도 잃지 않는가 — 값 0원\n")
REAL = (C.STATE, C.QUEUE, C.LAST, C.CASES)
real = {p: p.read_bytes() for p in REAL[:3] if p.exists()}
n_cases = len(list(REAL[3].glob("*.json")))

with tempfile.TemporaryDirectory() as t:
    td = Path(t)
    print("① 목록을 보다 끊김 (노후사기 다섯째 낱말에서)")
    Fake.fail_search, Fake.fail_fetch_after = {"유사수신"}, None
    st, q, log = run(td, "노후사기")
    ck("앞 낱말 넷에서 찾은 12건이 pending 으로 남는다",
       len(st.get("pending", [])) == 12, f"pending {len(st.get('pending', []))}건\n{log[-400:]}")
    ck("끊긴 낱말은 '찾아봤음' 으로 안 적힌다 (다음에 다시 찾는다)",
       not st["queries"].get("유사수신", {}).get("listed"))
    ck("화면에 '이어받는다' 고 알린다", "다음 실행이 이어받는다" in log)
    kept = {p["id"] for p in st.get("pending", [])}
    st, q, log = run(td, "노후사기")
    ck("또 끊겨도 지난번에 남긴 12건을 잃지 않는다 (목록을 보다 끊긴 경우)",
       {p["id"] for p in st.get("pending", [])} == kept, f"pending {len(st.get('pending', []))}건")

    print("\n② 다음 실행이 이어받는다")
    Fake.fail_search = set()
    st, q, log = run(td, "노후사기")
    ids = {c["case_id"] for c in q}
    ck("남겨 둔 12건 + 남은 낱말 둘의 6건 = 18건이 대기열에 들어온다",
       len(ids) == 18 and kept <= ids, f"{len(ids)}건 · 빠진 것 {sorted(kept - ids)}")
    ck("다 받았으면 pending 이 빈다", st.get("pending") == [], str(st.get("pending")))

with tempfile.TemporaryDirectory() as t:
    td = Path(t)
    print("\n③ 본문을 받다 끊김 (치매 9건 가운데 4건째 뒤)")
    Fake.fail_search, Fake.fail_fetch_after = set(), 4
    st, q, log = run(td, "치매")
    ck("받은 4건은 대기열에 남는다", len(q) == 4, f"{len(q)}건")
    ck("못 받은 5건이 pending 으로 남는다",
       len(st.get("pending", [])) == 5, f"pending {len(st.get('pending', []))}건")
    Fake.fail_fetch_after = None
    left5 = {p["id"] for p in st.get("pending", [])}

    print("\n④ 딴 갈래를 누르면 남은 것은 그대로 둔다")
    st, q, log = run(td, "노후사기")
    ck("노후사기를 누르면 노후사기만 받는다 (치매 남은 5건에 예산을 안 쓴다)",
       len(q) == 4 + 18 and not (left5 & {c["case_id"] for c in q}), f"{len(q)}건")
    ck("치매 남은 5건은 pending 에 그대로 있다",
       {p["id"] for p in st.get("pending", [])} == left5, f"{st.get('pending')}")
    st, q, log = run(td, "치매")
    ck("치매를 다시 누르면 나머지 5건을 받는다", len(q) == 27 and st.get("pending") == [],
       f"{len(q)}건 · pending {len(st.get('pending', []))}")

with tempfile.TemporaryDirectory() as t:
    td = Path(t)
    print("\n⑤ '어르신 다섯' — 다섯 갈래를 한 번에, 고르게")
    Fake.fail_search, Fake.fail_fetch_after = set(), None
    # 노후사기 낱말만 좁게(5건) — 예전처럼 '좁은 낱말부터' 받으면 노후사기 18건이 예산을 먼저 먹는다
    Fake.totals = {"노후사기": 5, "효도계약": 900, "치매": 900, "땅·선산": 900, "요양": 900}
    (td / "collect_state.json").write_text(json.dumps({
        "date": "", "calls_today": 0, "queries": {}, "fetched": [], "hard_rejected": {},
        "scope": C.SEARCH_SCOPE, "pending": [{"q": "유류분", "id": "x1", "court": ""}]},
        ensure_ascii=False), encoding="utf-8")
    st, q, log = run(td, "어르신 다섯", calls=60)
    five = set(C.QUERY_GROUPS["노후사기"] + C.QUERY_GROUPS["효도계약"] + C.QUERY_GROUPS["치매"]
               + C.QUERY_GROUPS["땅·선산"] + C.QUERY_GROUPS["요양"])
    ck("다섯 갈래 낱말만 훑는다", set(st["queries"]) == five,
       str(set(st["queries"]) ^ five))
    by = {}
    for c in q:
        by[c["topic"]] = by.get(c["topic"], 0) + 1
    ck("본문도 갈래를 돌아가며 받는다 (노후사기 18건이 예산을 다 먹지 않는다)",
       len(by) == 5 and by.get("노후사기", 0) <= 12 and min(by.values()) >= 6, str(by))
    ck("딴 갈래(상속) 남은 것은 손대지 않고 남겨 둔다",
       any(p["id"] == "x1" for p in st.get("pending", []))
       and "x1" not in {c["case_id"] for c in q})
    Fake.totals = {}

after = {p: p.read_bytes() for p in REAL[:3] if p.exists()}
ck("진짜 상태 파일은 그대로다 (시험이 실제 대기열을 안 건드린다)",
   after == real and len(list(REAL[3].glob("*.json"))) == n_cases)

print("─" * 56)
if bad:
    print(f"❌ {len(bad)}개 걸렸습니다 — 고치고 다시")
    sys.exit(1)
print("✅ 끊겨도 찾은 판례를 잃지 않는다: 목록 중 · 본문 중 · 이어받기 · 갈래별 남은 것")
