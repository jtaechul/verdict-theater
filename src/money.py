#!/usr/bin/env python3
"""금액을 백만원 단위로 다듬는다.

왜 필요한가
    판결문 금액을 ±30% 변형하면 "9억 8,412만 원" 같은 끝자리가 나온다.
    귀로 들으면 자잘하고, 화면에 박아도 읽히지 않는다.
    드라마에서 중요한 것은 자릿수이지 끝자리가 아니다.

    그래서 백만원 미만을 잘라낸다.  9억 8,412만 원 → 9억 8,400만 원

⚠️ 100만원 미만은 건드리지 않는다
    잘라내면 0원이 되어 사실 자체가 사라진다. 월세 80만원이 0원이 되면
    이야기가 성립하지 않는다. 그런 금액은 원래 자릿수가 작아서
    "자잘하다"는 문제도 생기지 않는다.

    python3 src/money.py                          자체 점검
    python3 src/money.py data/scripts/EP001.json  이미 저장된 대본을 제자리에서 다듬기
"""
import json
import re
import sys

STEP = 1_000_000                      # 백만원 — 이 아래를 자른다
_UNIT = {"조": 10 ** 12, "억": 10 ** 8, "만": 10 ** 4}

# 1,749 처럼 쉼표가 있는 꼴과 1749 처럼 없는 꼴을 모두 받는다.
# 쉼표 꼴을 먼저 두면 "1749" 에서 "174" 만 집어가므로 쉼표를 의무로 만든다.
_NUM = r"\d{1,3}(?:,\d{3})+|\d+"

# "12억 400만 원" · "6,900만 원" · "1억원" · "1,000,000원" 을 모두 잡는다.
_MONEY = re.compile(
    rf"(?:{_NUM})\s*(?:[조억만]\s*)?(?:(?:{_NUM})\s*(?:[조억만]\s*)?)*원"
)
_PART = re.compile(rf"({_NUM})\s*([조억만]?)")


def parse(text):
    """'9억 8,412만 원' → 984120000. 못 읽으면 0."""
    total = 0
    for num, unit in _PART.findall(text):
        v = int(num.replace(",", ""))
        total += v * _UNIT[unit] if unit else v
    return total


def fmt(n):
    """984000000 → '9억 8,400만 원'. 사람이 읽는 꼴로 되돌린다."""
    if n <= 0:
        return "0원"
    out = []
    for unit, size in (("조", 10 ** 12), ("억", 10 ** 8), ("만", 10 ** 4)):
        q, n = divmod(n, size)
        if q:
            out.append(f"{q:,}{unit}")
    if n:
        out.append(f"{n:,}")
    return " ".join(out) + " 원"


def floor(n, step=STEP):
    """백만원 미만 절사. 단 100만원 미만 금액은 그대로 둔다(0원 방지)."""
    if n < step:
        return n
    return n - n % step


def tidy(text, step=STEP):
    """문장 안의 모든 금액 표기를 백만원 단위로 절사한다."""
    if not isinstance(text, str) or "원" not in text:
        return text

    def one(m):
        raw = m.group(0)
        n = parse(raw)
        cut = floor(n, step)
        if cut == n:                  # 이미 깔끔하다 — 표기를 손대지 않는다
            return raw
        return fmt(cut)

    return _MONEY.sub(one, text)


def tidy_doc(obj, step=STEP):
    """대본 전체(중첩된 dict/list 포함)의 모든 문자열을 훑는다.

    본문·amounts_used·그래픽 값·유튜브 설명을 따로 챙기지 않고 한 번에 훑는 이유는,
    한 군데라도 빠지면 '본문 금액이 amounts_used 와 다르다'는 검증에 걸리기 때문이다."""
    if isinstance(obj, str):
        return tidy(obj, step)
    if isinstance(obj, list):
        return [tidy_doc(x, step) for x in obj]
    if isinstance(obj, dict):
        return {k: tidy_doc(v, step) for k, v in obj.items()}
    return obj


def is_tidy(text, step=STEP):
    """문장 안의 금액이 전부 백만원 단위인가. 검증에서 쓴다."""
    for m in _MONEY.finditer(text or ""):
        n = parse(m.group(0))
        if n >= step and n % step:
            return False
    return True


def mentions(text):
    """문장 안에 나오는 금액 표기를 전부 돌려준다.

    '이 컷이 돈 이야기인가' 를 세는 데 쓴다 — 판결·금액 비중 10% 규칙(검증기)."""
    return [m.group(0) for m in _MONEY.finditer(text or "")]


def untidy(text, step=STEP):
    """백만원 단위가 아닌 금액 표기만 골라 돌려준다. 오류 메시지용."""
    out = []
    for m in _MONEY.finditer(text or ""):
        n = parse(m.group(0))
        if n >= step and n % step:
            out.append(m.group(0))
    return out


def _tidy_file(path):
    """이미 저장된 JSON 대본을 제자리에서 다듬는다. 모델을 부르지 않는다."""
    from pathlib import Path
    p = Path(path)
    doc = json.loads(p.read_text(encoding="utf-8"))
    before = untidy(json.dumps(doc, ensure_ascii=False))
    if not before:
        print(f"  {p.name}: 이미 전부 백만원 단위다. 그대로 둔다.")
        return 0
    p.write_text(json.dumps(tidy_doc(doc), ensure_ascii=False, indent=2) + "\n",
                 encoding="utf-8")
    seen = sorted(set(before))
    print(f"  {p.name}: {len(seen)}종 다듬음")
    for s in seen:
        print(f"      {s:18} → {tidy(s)}")
    return len(seen)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for f in sys.argv[1:]:
            _tidy_file(f)
        raise SystemExit(0)

    cases = [
        ("9억 8,412만 원", "9억 8,400만 원"),
        ("12억 400만 원", "12억 400만 원"),      # 이미 깔끔 — 그대로
        ("1억 6,560만 원", "1억 6,500만 원"),
        ("5억 4,252만 원", "5억 4,200만 원"),
        ("1,749만 원", "1,700만 원"),
        ("6,900만 원", "6,900만 원"),
        ("1억 371만 원", "1억 300만 원"),
        ("80만 원", "80만 원"),                  # 100만원 미만 — 손대지 않는다
        ("1,000,000원", "1,000,000원"),          # 딱 백만원 — 그대로
        ("3억 원", "3억 원"),
        ("1조 2,345억 6,789만 원", "1조 2,345억 6,700만 원"),
    ]
    bad = 0
    for src, want in cases:
        got = tidy(src)
        mark = "OK " if got == want else "!! "
        if got != want:
            bad += 1
        print(f"  {mark}{src:24} → {got}")

    # 문장 안에서도 되는가
    s = "법원은 1억 5,690만 원을 인정했고, 나머지 2,345만 원은 기각했다."
    print("\n  문장:", tidy(s))
    if "1억 5,600만 원" not in tidy(s) or "2,300만 원" not in tidy(s):
        bad += 1
        print("  !! 문장 안 치환 실패")

    # 금액이 아닌 것을 건드리지 않는가
    for keep in ("20여 년 전", "3막 22초", "재판장", ""):
        if tidy(keep) != keep:
            bad += 1
            print(f"  !! 금액이 아닌데 바뀌었다: {keep} → {tidy(keep)}")

    print(f"\n{'전부 통과' if not bad else f'{bad}건 실패'}")
    raise SystemExit(1 if bad else 0)
