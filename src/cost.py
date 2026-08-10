#!/usr/bin/env python3
"""모델값을 **원(₩)으로** 적어 준다.

    python3 src/cost.py                     단가표와 예시를 본다
    python3 src/cost.py --in 229632 --out 10004    직접 계산해 본다

왜 필요한가
    실행이 끝나면 로그에 "입력 229,632 토큰" 같은 숫자가 찍힌다.
    이건 사람에게 아무 뜻이 없다. 얼마 나갔는지를 원으로 적어야
    운영자가 "이 단계가 비싸구나" 를 그 자리에서 안다.

⚠️ 단가는 회사가 바꾼다. 바뀌면 **아래 표만** 고치면 온 저장소에 반영된다.
   환율은 워크플로에서 USD_KRW 환경변수로 덮어쓸 수 있다.
"""

import os

# 1달러를 몇 원으로 칠 것인가. (src/tts.py 와 같은 기본값을 쓴다)
USD_KRW = float(os.environ.get("USD_KRW", "1470"))

# ── 단가표 (100만 토큰당 달러) ────────────────────────────
#    2026-08 공시가 기준. 이름의 일부만 맞아도 잡히게 해 뒀다
#    (모델 이름은 자주 바뀌는데 값은 계열별로 유지되기 때문이다).
#    위에서부터 먼저 맞는 것을 쓴다 — 긴 이름을 위에 둔다.
PRICES = [
    # (이름 조각,        입력,   출력)
    ("claude-opus",      5.00,  25.00),
    ("claude-sonnet",    3.00,  15.00),
    ("claude-haiku",     1.00,   5.00),
    ("gemini-3-pro",     2.00,  12.00),
    ("gemini-2.5-pro",   1.25,  10.00),
    ("gemini-3-flash",   0.30,   2.50),
    ("gemini-2.5-flash", 0.30,   2.50),
    ("flash",            0.30,   2.50),   # 이름이 바뀌어도 flash 면 싼 쪽
    ("pro",              2.00,  12.00),   # 이름이 바뀌어도 pro 면 비싼 쪽
]

# 기억해 두고 다시 쓰기(프롬프트 캐싱)의 값. 입력 단가에 곱한다.
CACHE_WRITE_X = 1.25      # 기억시켜 둘 때는 조금 더 낸다
CACHE_READ_X = 0.10       # 다시 쓸 때는 10분의 1만 낸다


def rate(model):
    """모델 이름 → (입력 단가, 출력 단가). 모르면 None."""
    name = (model or "").lower()
    for key, tin, tout in PRICES:
        if key in name:
            return tin, tout
    return None


def krw(model, tokens_in=0, tokens_out=0, cache_write=0, cache_read=0):
    """이번 실행에 든 값을 원으로. 단가를 모르면 None 을 준다."""
    r = rate(model)
    if not r:
        return None
    tin, tout = r
    usd = (tokens_in * tin
           + cache_write * tin * CACHE_WRITE_X
           + cache_read * tin * CACHE_READ_X
           + tokens_out * tout) / 1_000_000
    return usd * USD_KRW


def line(model, tokens_in=0, tokens_out=0, cache_write=0, cache_read=0):
    """로그 한 줄로. 단가를 모르면 조용히 빈 문자열."""
    won = krw(model, tokens_in, tokens_out, cache_write, cache_read)
    if won is None:
        return ""
    return f"이번에 든 값: 약 {won:,.0f}원  ({model})"


def compare(tokens_in, tokens_out, models=None):
    """같은 일을 어느 모델로 하면 얼마인지 나란히 본다."""
    models = models or ["claude-opus-5", "claude-sonnet-5",
                        "gemini-3-pro", "gemini-2.5-flash"]
    rows = []
    for m in models:
        w = krw(m, tokens_in=tokens_in, tokens_out=tokens_out)
        if w is not None:
            rows.append((m, w))
    return rows


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="tin", type=int, default=229632,
                    help="입력 토큰 (기본: 2026-08-10 소재 심사 10건 실측치)")
    ap.add_argument("--out", dest="tout", type=int, default=10004,
                    help="출력 토큰")
    ap.add_argument("--each", type=int, default=10, help="몇 건 어치인가")
    a = ap.parse_args()

    print(f"환율 {USD_KRW:,.0f}원/$ 기준 · 입력 {a.tin:,} · 출력 {a.tout:,} 토큰")
    print("─" * 52)
    for m, w in compare(a.tin, a.tout):
        per = f"  (한 건 {w / a.each:,.0f}원)" if a.each else ""
        print(f"  {m:18s} {w:8,.0f}원{per}")
