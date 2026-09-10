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


# ⭐⭐⭐ 60초 벽 — 이 채널에서 **가장 비싼 교훈**이다.
#    2026-09-01: 60초 이하 6편은 전부 1,209~1,554회 · 127초 1편은 **0회**.
#    대사 컷을 영상으로 바꾸면 컷 길이가 목소리 길이가 아니라 **영상 길이**가
#    된다(4·6·8초 중 하나). 그래서 편이 길어진다 — S92 는 2편·3편이 54초에서
#    **66초로** 뛴다. 사고 나고 경고를 찍는 것으로는 늦다(그때는 이미 값을
#    다 쓴 뒤다). **사기 전에** 재서, 넘칠 것 같으면 그 편의 대사 컷을 덜어낸다.
PART_MAX_SEC = 59.5
# ⚠️ 실측 잣대는 컷마다 최대 1.6초쯤 어긋난다(27컷 최소자승, 2026-09-08).
#    벽에 딱 붙여 놓으면 그 오차가 그대로 넘김이 된다. 안전분을 둔다.
SAFE_MARGIN = 2.5
# ⚠️⚠️ 잣대를 **여기 적지 않는다.** story90 에서 가져온다 — 두 벌로 두면
#    한쪽만 고쳐져 화면과 실제가 어긋난다 (실제로 _chars 를 다르게 세다가
#    편 길이가 10초 틀렸고, 대사 컷 14개 중 13개를 잘못 덜어냈다).
import story90 as _ST                                       # noqa: E402
SEC_PER_CHAR = _ST.SEC_PER_CHAR
SEC_PER_CUT = _ST.SEC_PER_CUT


def _chars(c):
    """그 컷이 말하는 글자 수 — **story90.chars 와 똑같이** 센다.

    ⚠️⚠️ 2026-09-10 — 처음엔 여기서 그냥 len() 을 썼다. story90 은 띄어쓰기와
       점(… ·)을 빼고 센다. 그 차이로 편 길이가 53.5초가 아니라 63.5초로
       나와, 60초 벽을 지키려던 코드가 **대사 컷 14개 중 13개를 덜어냈다.**
       잣대가 두 벌이면 한쪽이 반드시 거짓말을 한다.
    """
    return sum(len(re.sub(r"[\s…·]", "", str(t[1]))) for t in turns_of(c))


def cut_base(c):
    """그 컷이 **그림일 때** 차지하는 시간(초) — 실측 잣대."""
    return SEC_PER_CHAR * _chars(c) + SEC_PER_CUT


def part_secs(doc, talk_ns=None):
    """편마다 예상 길이(초). talk_ns 를 주면 그 컷들은 **영상 길이**로 센다.

    ⚠️ 영상은 자르기(talk_trim)가 되면 말 길이 + 여운으로 줄어든다. 그런데
       자르기는 **실패할 수 있다**(조용한 구간을 못 찾으면 그냥 둔다).
       여기서는 **안 잘렸을 때**로 잡는다 — 넘칠 위험을 낮춰 보면 안 된다.
    """
    talk_ns = set(talk_ns or [])
    out = {}
    for p in doc.get("parts") or []:
        a, b = p["cuts"]
        cs = [c for c in doc.get("cuts") or [] if a <= c["n"] <= b]
        out[int(p["no"])] = sum(
            talk_sec(turns_of(c)[0][1]) if c["n"] in talk_ns else cut_base(c)
            for c in cs)
    return out


def fit(doc, cuts=None):
    """60초를 넘길 편에서 **대사 컷을 덜어낸다** — (남길 컷들, 덜어낸 사연).

    긴 컷부터 덜어낸다(가장 많이 줄어든다). 값도 그만큼 안 나간다.
    ⚠️ 한 편에서 전부 덜어내도 안 되면 그대로 둔다 — 그 편은 대본이 길다는
       뜻이라 대본을 고쳐야 한다(여기서 더 할 수 있는 것이 없다).
    """
    keep = list(cuts if cuts is not None else talk_cuts(doc))
    why = []
    for p in doc.get("parts") or []:
        a, b = p["cuts"]
        no = int(p["no"])
        mine = [c for c in keep if a <= c["n"] <= b]
        # 긴 대사부터 뺀다
        mine.sort(key=lambda c: talk_sec(turns_of(c)[0][1]), reverse=True)
        while mine:
            got = part_secs(doc, [c["n"] for c in keep])[no]
            if got <= PART_MAX_SEC - SAFE_MARGIN:
                break
            drop = mine.pop(0)
            keep = [c for c in keep if c["n"] is not drop["n"]]
            keep = [c for c in keep if c["n"] != drop["n"]]
            why.append(f"{no}편 컷{drop['n']} — 그림으로 남긴다 "
                       f"(넣으면 {got:.0f}초 · 60초 벽에 너무 가깝다)")
    return keep, why


def plan(doc, krw_per_sec=0.08, usd_krw=1470.0):
    """화면에 그대로 적을 셈 — 몇 컷 · 몇 초 · 얼마.

    ⚠️ 값은 Veo 3.1-lite 실측(초당 $0.08)이다. cost.py 를 안 불러온다 —
       이 파일은 가벼워야 하고, 화면은 어차피 어림값만 보여 주면 된다.
       (진짜 장부는 만들 때 cost.py 가 적는다)
    """
    cuts, why = fit(doc)                 # ⭐ 60초 벽을 먼저 지킨다
    secs = [talk_sec(turns_of(c)[0][1]) for c in cuts]
    won = sum(round(s * krw_per_sec * usd_krw) for s in secs)
    parts = part_secs(doc, [c["n"] for c in cuts])
    # ⭐ 한 번 실행 한도(cost.RUN_KRW)에 걸려 **몇 번 눌러야 하는지** 미리 알린다.
    #    두 번째부터는 만든 것을 0원으로 다시 쓰므로 값은 더 안 나간다.
    #    ⚠️ cost.py 를 부르지 않는다 — 이 파일은 가벼워야 한다. 같은 기본값을 쓴다.
    import os
    cap = float(os.environ.get("VT_RUN_KRW", "3000"))
    presses, run, left = 1, 0.0, sorted(secs, reverse=True)
    for x in left:
        one = round(x * krw_per_sec * usd_krw)
        if run + one > cap:
            presses += 1
            run = 0.0
        run += one
    return {"n": len(cuts), "cuts": [c["n"] for c in cuts],
            "sec": sum(secs), "krw": won,
            "cap": cap, "presses": presses,
            # 화면이 **누르기 전에** 보여 줄 것들
            "parts": {str(k): round(v, 1) for k, v in parts.items()},
            "over": [k for k, v in parts.items() if v > PART_MAX_SEC],
            "dropped": why}
