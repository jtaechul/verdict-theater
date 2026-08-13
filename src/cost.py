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

import json
import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "state" / "spend.json"      # 쓴 돈 장부

# ── 한도 (원) ────────────────────────────────────────────
#
#   ⭐ 왜 '몇 번 불렀나' 가 아니라 '얼마 썼나' 로 막는가
#
#   원래는 호출 횟수(max_calls)로만 막고 있었다. 그런데 호출 하나의 값은
#   프롬프트 크기와 모델에 따라 10원에서 2,000원까지 벌어진다. 실측하면
#   같은 '24회 상한' 이 208원일 수도 13,230원일 수도 있다.
#   **횟수로는 돈을 막을 수 없다.** 그래서 원으로 막는다.
#
#   두 겹으로 막는다.
#     한 번 실행    RUN_KRW  — 한 번 누를 때 이만큼 넘으면 거기서 멈춘다
#     한 달 전체    MONTH_KRW— 이번 달 누적이 넘으면 아예 시작하지 않는다
#   둘 다 GitHub Secrets 나 워크플로 입력으로 바꿀 수 있다.
#   ⚠️ 한도는 **실제 드는 값보다 조금만 위**에 있어야 뜻이 있다.
#      6,000원 / 50,000원 은 내가 아무 근거 없이 잡은 값이었다. 한 번 실행이
#      2,100원인데 한도가 6,000원이면 세 배가 새도 안 막힌다 — 막는 시늉만 한 것이다.
#      (손님: "한번에 6000원은 미친 듯이 비싼 거 같은데?" — 맞는 지적이다)
#
#      지금 한 번 실행에 실제로 드는 값
#        대본 1편 (Opus, 생각 깊이 보통)   약 2,100원
#        소재 심사                        0원 (소재가 쌓여 있으면 건너뛴다)
#      → 한 번 3,000원이면 정상 실행은 통과하고, 새기 시작하면 바로 막힌다.
RUN_KRW = float(os.environ.get("VT_RUN_KRW", "3000"))
MONTH_KRW = float(os.environ.get("VT_MONTH_KRW", "25000"))

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

# ── 그림 한 장 값 (달러) ──────────────────────────────────
#
#   ⚠️ 2026-08-13 — 여기가 **통째로 비어 있었다.** 위의 표는 글자(토큰) 값만
#      적혀 있고, 그림은 장당 값이라 계산이 안 됐다. 그래서 assets_gen.gen_image
#      가 돈 계산도, 장부 기록도, 한도 검사도 **하나도 안 하고 있었다.**
#      무료 한도가 0이라 그림이 아예 안 만들어지던 동안에는 드러나지 않았는데,
#      결제를 걸면 그때부터 **그림값만 한도 밖에서 새어 나간다.**
#
#   ⚠️ 모르는 모델·크기는 **가장 비싼 값으로 친다.** 적게 잡으면 한도가
#      안 걸려서 막는 시늉만 하게 된다. 장부는 넉넉히 잡는 쪽이 안전하다.
#      실제 청구액은 gen_image 가 응답의 usageMetadata 를 찍어 주므로
#      한 번 돌려 보고 이 표를 실측값으로 고치면 된다.
IMAGE_USD = [
    # (이름 조각,               1K,    2K,    4K)
    ("gemini-3-pro-image",     0.134, 0.134, 0.240),
    ("gemini-3.1-flash-image", 0.060, 0.090, 0.180),   # 추정 — 실측 전까지 넉넉히
    ("gemini-3-flash-image",   0.060, 0.090, 0.180),   # 추정
    ("gemini-2.5-flash-image", 0.039, 0.039, 0.039),   # 크기 지정을 안 받는 모델
]
IMAGE_USD_UNKNOWN = 0.30        # 표에 없는 모델은 이만큼으로 친다 (일부러 비싸게)


def image_krw(model, size="1K"):
    """그림 한 장 값(원). 모르는 것은 **비싸게** 잡는다."""
    name = (model or "").lower()
    col = {"1K": 0, "2K": 1, "4K": 2}.get(str(size).upper(), 1)
    for key, *usd in IMAGE_USD:
        if key in name:
            return usd[col] * USD_KRW
    return IMAGE_USD_UNKNOWN * USD_KRW

# 기억해 두고 다시 쓰기(프롬프트 캐싱)의 값. 입력 단가에 곱한다.
#
#   ⚠️ 기억시켜 두는 값은 **얼마나 오래 기억하느냐**에 따라 다르다.
#      5분짜리 1.25배 · 1시간짜리 2배.
#      src/claude.py 는 1시간짜리를 쓴다 (막 하나 쓰는 데 2~3분씩 걸려 7번이면
#      20분이다. 5분짜리로는 중간에 잊어버려 오히려 매번 정가로 다시 읽는다).
#      그러니 여기도 1시간 값인 2배로 적어야 장부가 맞는다.
#      1.25 로 적혀 있던 동안 장부는 실제보다 **적게** 나오고 있었다.
CACHE_WRITE_X = 2.00      # 1시간 기억: 입력 정가의 2배
CACHE_READ_X = 0.10       # 다시 쓸 때는 10분의 1만 낸다


def pad(text, width):
    """한글이 섞인 글을 화면 폭 기준으로 맞춘다.

    한글은 영문 두 칸을 차지한다. 파이썬의 f"{s:<14}" 는 **글자 수**로 세기 때문에
    한글이 섞이면 표가 어긋난다. 여기서는 화면에 보이는 폭으로 센다."""
    text = str(text)
    seen = 0
    out = []
    for ch in text:
        w = 2 if ord(ch) > 0x1100 and not (0x2000 <= ord(ch) <= 0x2BFF) else 1
        if seen + w > width:
            break
        out.append(ch)
        seen += w
    return "".join(out) + " " * (width - seen)


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


# ── 장부 (state/spend.json) ──────────────────────────────
#
# 한 번 실행할 때마다 얼마 썼는지 한 줄씩 쌓는다. 이것이 있어야
#   · 이번 달에 얼마 나갔는지 화면에서 볼 수 있고
#   · 한 달 한도를 넘었을 때 **시작 전에** 막을 수 있다
# 값이 0원이면 적지 않는다(모델을 안 부른 실행까지 남길 이유가 없다).


def _load():
    if not LEDGER.exists():
        return []
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:                                   # noqa: BLE001
        return []                                       # 장부가 깨져도 제작은 멈추지 않는다


def record(kind, won, note="", when=None):
    """쓴 돈 한 줄을 장부에 남긴다. 실패해도 절대 예외를 올리지 않는다."""
    try:
        if not won or won <= 0:
            return
        rows = _load()
        rows.append({"date": (when or date.today()).isoformat(),
                     "kind": kind, "krw": round(float(won)), "note": note[:120]})
        rows = rows[-2000:]                             # 오래된 것은 잘라낸다
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
    except Exception as e:                              # noqa: BLE001
        print(f"    (장부에 못 적었다: {e} — 제작은 계속한다)")


def month_total(when=None):
    """이번 달에 쓴 돈 합계."""
    ym = (when or date.today()).isoformat()[:7]
    return sum(r.get("krw", 0) for r in _load() if str(r.get("date", "")).startswith(ym))


def month_left(when=None):
    return max(0.0, MONTH_KRW - month_total(when))


class MonthlyCapReached(RuntimeError):
    """이번 달 한도를 다 썼다. 시작하기 전에 막는다."""


def guard_month(what="이번 작업"):
    """돈을 쓰기 **전에** 부른다. 한 달 한도를 넘었으면 시작조차 하지 않는다."""
    used, left = month_total(), month_left()
    if left <= 0:
        raise MonthlyCapReached(
            f"이번 달에 이미 {used:,.0f}원을 썼다. 한 달 한도 {MONTH_KRW:,.0f}원을 넘었으므로 "
            f"{what}을 시작하지 않는다.\n"
            f"  한도를 올리려면 저장소 Secrets 에 VT_MONTH_KRW 를 넣어라 (단위: 원).\n"
            f"  다음 달 1일이 되면 저절로 풀린다.")
    return used, left
