"""⭐ **어느 대사 컷을 영상으로 살 것인가** — 고르는 규칙 한 곳.

⚠️⚠️ 2026-09-10 — 이 파일이 생긴 까닭.
   관리자 화면은 값을 `706원 × 편 수` 로 어림했다. "편마다 한 컷" 이던 시절의
   셈이다. 제한을 풀어 **대사 컷 전부**를 영상으로 만들게 바꾸자, 화면이 적어
   주는 값이 **거짓말**이 됐다 (실제 12,936원인데 화면은 2,824원).
   손님이 값에 특히 예민한데(“돈먹는 하마”), 화면이 거짓 값을 적으면
   승인 자체가 뜻이 없다.

   → 고르는 규칙을 **여기 한 곳에만** 둔다.
     · src/short90.py  — 실제로 영상을 살 때 쓴다
     · tools/build_short90.py — 대본을 지을 때 doc["talk"] 에 찍어 둔다
     · admin/worker.js — 그 찍힌 값을 **그대로 읽는다** (스스로 안 센다)
   화면이 스스로 세면 언젠가 또 어긋난다. 세는 자리를 하나로 만든다.

⚠️ **가벼운 파일로 둔다.** PIL·requests 를 부르지 않는다 — tools/ 쪽에서
   import 해야 하는데, 무거운 것을 물고 오면 워크플로가 죽는다
   (2026-08-31 · 2026-09-09 에 같은 사고가 두 번 났다).
"""
import os
import re

TALK_OK_SEC = (4, 6, 8)          # Veo 가 받는 길이 (5·7초는 HTTP 400)
# 0 = 제한 없음. **제한 없음이 기본이다** — 손님 설계가 "대사 부분만 영상" 이다.
TALK_PER_PART = int(os.environ.get("VT_TALK_PER_PART", "0"))
TALK_PER_PERSON = int(os.environ.get("VT_TALK_PER_PERSON", "0"))
# 안전필터가 자주 막는 낱말. 막히면 그 컷 값이 그냥 날아간다.
TALK_HOT = ("관계", "잤", "몸", "성관계", "강간", "죽이", "때렸")


def turns_of(c):
    return [t for t in (c.get("turns") or []) if t and len(t) >= 2]


def is_narr(c):
    ts = turns_of(c)
    return bool(ts) and all(str(t[0]).strip() == "나레이션" for t in ts)


def talk_sec(text):
    """그 대사에 살 길이(초). Veo 가 받는 값 중에서 고른다."""
    want = len(re.sub(r"[\s…·]", "", str(text))) / 4.6 + 0.8
    return next((x for x in TALK_OK_SEC if x >= want), TALK_OK_SEC[-1])


def talk_cuts(doc):
    """영상으로 살 대사 컷들.

    고르는 규칙(하나라도 어긋나면 그 컷은 그림으로 남는다):
      · 말차례가 **한 줄**이다 — 두 사람이 주고받으면 한 클립에 목소리가
        둘 들어가 흔들림이 두 배가 된다.
      · 편의 **첫 컷도 마지막 컷도 아니다** — 첫 컷에는 편 제목 카드가,
        마지막 컷에는 「다음 편에 계속」 카드가 얹힌다.
      · 안전필터 고위험 낱말이 없다.
    """
    got, per = [], {}
    for p in doc.get("parts") or []:
        a, b = p["cuts"]
        cs = [c for c in doc.get("cuts") or [] if a <= c["n"] <= b]
        if len(cs) < 3:
            continue
        cand = [c for c in cs[1:-1]
                if not is_narr(c) and len(turns_of(c)) == 1
                and not any(w in turns_of(c)[0][1] for w in TALK_HOT)]
        cand.sort(key=lambda c: len(turns_of(c)[0][1]))
        n = 0
        for c in cand:
            who = turns_of(c)[0][0]
            if TALK_PER_PERSON and per.get(who, 0) >= TALK_PER_PERSON:
                continue
            got.append(c)
            per[who] = per.get(who, 0) + 1
            n += 1
            if TALK_PER_PART and n >= TALK_PER_PART:
                break
    return got


def plan(doc, krw_per_sec=0.08, usd_krw=1470.0):
    """화면에 그대로 적을 셈 — 몇 컷 · 몇 초 · 얼마.

    ⚠️ 값은 Veo 3.1-lite 실측(초당 $0.08)이다. cost.py 를 안 불러온다 —
       이 파일은 가벼워야 하고, 화면은 어차피 어림값만 보여 주면 된다.
       (진짜 장부는 만들 때 cost.py 가 적는다)
    """
    cuts = talk_cuts(doc)
    secs = [talk_sec(turns_of(c)[0][1]) for c in cuts]
    won = sum(round(s * krw_per_sec * usd_krw) for s in secs)
    return {"n": len(cuts), "cuts": [c["n"] for c in cuts],
            "sec": sum(secs), "krw": won}
