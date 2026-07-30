#!/usr/bin/env python3
"""법제처 국가법령정보 OPEN API 클라이언트.

호출 한도를 코드가 강제한다. 사람이 지키는 규칙은 언젠가 깨진다.
  - 호출 간격 1.1초 이상
  - 하루 200회 상한 (state/collect_state.json 에 누적 기록)

실측으로 확인된 처리 함정을 여기서 전부 흡수한다.
  - 값이 CDATA로 감싸짐 → XML 파서가 처리
  - 본문에 <br/> 섞임 → 개행 치환 후 태그 제거
  - 선고일자 형식 불일치 → YYYY-MM-DD 통일
  - 법원명이 빈 값 → 사건번호에서 추출
  - 하급심은 판시사항·판결요지·참조조문이 전부 빈 값 → 본문에서 조문 추출해 보관
"""

import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE_LIST = "https://www.law.go.kr/DRF/lawSearch.do"
BASE_BODY = "https://www.law.go.kr/DRF/lawService.do"

# 법제처 인증키(OC). 비밀이 아니다.
#   - 법제처가 누구에게나 발급하는 공개 API의 식별자다
#   - 이 값은 CLAUDE.md 5번과 STARTGUIDE.md 에 이미 평문으로 적혀 있다
#   - 즉 Secrets 로 감춰봐야 감춰지는 것이 없고, 등록을 깜빡하면 파이프라인만 멈춘다
# 그래서 기본값을 코드에 두고, 필요하면 LAW_OC 환경변수로 덮어쓸 수 있게 한다.
# (GEMINI_API_KEY 는 진짜 비밀이다. 그건 반드시 Secrets 에만 넣는다)
DEFAULT_OC = "panryetheater"

MIN_INTERVAL = 1.1      # 호출 간격(초)
DAILY_LIMIT = 200       # 하루 상한
TIMEOUT = 40
RETRIES = 4             # 최초 1회 + 재시도 3회
BACKOFF = [2, 5, 12]    # 재시도 전 대기(초)

BODY_FIELDS = [
    "판례정보일련번호", "사건명", "사건번호", "선고일자", "선고", "법원명", "법원종류코드",
    "사건종류명", "사건종류코드", "판결유형", "판시사항", "판결요지", "참조조문",
    "참조판례", "판례내용",
]
LIST_FIELDS = [
    "판례일련번호", "사건명", "사건번호", "선고일자", "법원명", "법원종류코드",
    "사건종류명", "사건종류코드", "판결유형", "선고", "데이터출처명",
]


class DailyLimitReached(RuntimeError):
    """하루 200회 상한에 도달. 오늘은 여기까지."""


class LawAPI:
    def __init__(self, oc, used_today=0, limit=DAILY_LIMIT):
        if not oc:
            raise ValueError("법제처 인증키(LAW_OC)가 없다. GitHub Secrets 에 등록했는지 확인하라.")
        self.oc = oc
        self.used = used_today
        self.limit = limit
        self._last = 0.0

    # ── 내부 ──────────────────────────────────────────────
    def _get(self, base, params):
        """한 번 호출. 일시적 오류는 물러섰다가 다시 시도한다.

        법제처 서버는 이따금 연결을 끊는다(Connection reset). 200회짜리 백필이
        그 한 번 때문에 통째로 죽으면 안 되므로 재시도를 넣는다.
        재시도는 호출 수에 포함하지 않는다 — 서버가 응답을 안 준 것이기 때문이다."""
        if self.used >= self.limit:
            raise DailyLimitReached(f"오늘 {self.used}회 호출. 상한 {self.limit}회에 도달했다.")
        url = f"{base}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "verdict-theater/1.0"})

        last_err = None
        for attempt in range(RETRIES):
            gap = time.monotonic() - self._last
            if gap < MIN_INTERVAL:
                time.sleep(MIN_INTERVAL - gap)
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                    raw = resp.read()
                self._last = time.monotonic()
                self.used += 1
                return raw
            except Exception as e:                     # 연결 끊김·타임아웃·5xx 등
                last_err = e
                self._last = time.monotonic()
                if attempt < RETRIES - 1:
                    wait = BACKOFF[attempt]
                    print(f"    (재시도 {attempt + 1}/{RETRIES - 1} — {type(e).__name__}, {wait}초 대기)")
                    time.sleep(wait)
        self.used += 1                                  # 끝내 실패해도 시도는 소모로 친다
        raise last_err

    # ── 공개 ──────────────────────────────────────────────
    def search(self, query, page=1, display=100):
        """검색어로 판례 목록을 받는다. (판례일련번호 등 목록 필드만)"""
        raw = self._get(BASE_LIST, {
            "OC": self.oc, "target": "prec", "type": "XML",
            "query": query, "display": display, "page": page,
        })
        root = ET.fromstring(raw)
        total = _text(root.find("totalCnt"))
        rows = []
        for p in root.findall("prec"):
            rows.append({k: _text(p.find(k)) for k in LIST_FIELDS})
        return int(total or 0), rows

    def fetch(self, case_id):
        """판례 본문을 받아 정규화한 dict 로 돌려준다."""
        raw = self._get(BASE_BODY, {
            "OC": self.oc, "target": "prec", "type": "XML", "ID": case_id,
        })
        root = ET.fromstring(raw)
        d = {k: clean(_text(root.find(k))) for k in BODY_FIELDS}
        d["선고일자"] = norm_date(d["선고일자"])
        if not d["법원명"]:
            d["법원명"] = court_from_case_no(d["사건번호"])
        d["_fields_present"] = {
            k: bool(d[k]) for k in ("판시사항", "판결요지", "참조조문", "판례내용")
        }
        d["_laws_in_body"] = laws_in(d["판례내용"])
        d["_sections"] = sections_in(d["판례내용"])
        return d


# ── 정규화 도우미 ────────────────────────────────────────
def _text(el):
    return (el.text or "") if el is not None else ""


def clean(s):
    """<br/> 개행 치환 → 잔여 태그 제거 → 빈 줄 정리."""
    if not s:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def norm_date(s):
    """목록 `2024.07.09` / 본문 `20240709` → `2024-07-09`."""
    s = (s or "").strip()
    if re.fullmatch(r"\d{8}", s):
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    m = re.fullmatch(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return s


def court_from_case_no(case_no):
    """법원명이 빈 값일 때 사건번호에서 추출. 예: 부산고등법원(창원)-2024-나-14544"""
    m = re.match(r"([가-힣]+법원(?:\([가-힣]+\))?)", case_no or "")
    return m.group(1) if m else ""


def laws_in(body):
    """본문에 인용된 법조문. 하급심은 참조조문 필드가 비어 있어 이것이 유일한 출처다."""
    return sorted(set(re.findall(r"민법 제\d+조(?:의\d+)?(?: 제\d+항)?", body or "")))


def sections_in(body):
    """대본 작성에 필요한 구획이 실제로 있는지 표시한다."""
    b = body or ""
    return {
        "주문": bool(re.search(r"【\s*주\s*문\s*】", b)),
        "청구취지": bool(re.search(r"【\s*청구취지", b)),
        "인정사실": bool(re.search(r"(인정사실|기초사실|사안의 개요)", b)),
    }
