#!/usr/bin/env python3
"""⭐⭐⭐ **화면 글자와 말이 다른 숫자를 말하지 않는가.** 값 0원 · 인터넷 0회.

    python3 tools/number_check.py

⭐⭐⭐ 2026-09-11 손님: **"첫 화 영상 시작도 자막은 12억 나레이션은 13억이야.
   안 맞는 게 너무 많아."**

   1편 첫 2.5초에 화면 제목 카드가 뜬다. 그때 나레이션이 함께 나온다.
       화면: 통장 맡긴 날 사라진 **12억**
       소리: 아버지에게 **십삼억** 원의 토지 보상금이 입금된 날이었습니다
   둘 다 판결문에 있는 진짜 숫자다(장남이 이체한 12.27억 · 보상금 13.76억).
   그런데 **같은 순간에 나란히** 나오니 보는 사람에겐 틀린 것으로 보인다.
   숫자가 핵심인 채널에서 이것은 신뢰를 깎는다.

여기서 보는 것
   편 제목·화면 카드에 적힌 돈이, **그 편이 실제로 말하는 돈**과 어긋나지 않는가.
⚠️ 한글 숫자와 아라비아 숫자를 같은 값으로 본다 (칠억 = 7억).
⚠️ '수십억' 처럼 범위를 말하는 것은 넘어간다 — 어긋난 것이 아니다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERIES = ROOT / "data" / "series"

bad = []

DIGIT = {"영": 0, "일": 1, "이": 2, "삼": 3, "사": 4,
         "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
# 범위를 말하는 것 — 숫자로 치지 않는다
VAGUE = ("수십", "수백", "수천", "몇", "여러")


def ko_num(t):
    """'십삼' → 13 · '칠' → 7 · '이십이' → 22. 못 읽으면 None."""
    t = t.strip()
    if not t:
        return None
    if t.isdigit():
        return int(t)
    n, cur = 0, 0
    for ch in t:
        if ch in DIGIT:
            cur = DIGIT[ch]
        elif ch == "십":
            n += (cur or 1) * 10
            cur = 0
        elif ch == "백":
            n += (cur or 1) * 100
            cur = 0
        else:
            return None
    return n + cur


def moneys(s):
    """그 글에 나오는 '억' 단위 돈을 집합으로. 범위를 말하는 것은 뺀다."""
    got = set()
    for m in re.finditer(r"([0-9]+|[영일이삼사오육칠팔구십백]+)\s*억", str(s)):
        # ⚠️ '수십억' 은 '십억' 으로 읽히면 안 된다. 바로 앞 글자를 본다.
        #    (처음엔 앞 세 글자에서 '수십' 을 찾았는데, 그 세 글자가 '수' 하나
        #     뿐이라 안 걸렸다 — 검사의 검사가 잡아 줬다)
        before = str(s)[:m.start()]
        if before and before[-1] in "수몇":
            continue
        if any(v in before[-3:] for v in VAGUE):
            continue
        v = ko_num(m.group(1))
        if v:
            got.add(v)
    return got


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def main():
    print("⭐ 화면 글자와 말이 같은 숫자를 말하는가 (값 0원)\n")

    print("① 한글 숫자를 제대로 읽는가 (이 검사가 뜻이 있으려면)")
    for t, want in (("십삼", 13), ("칠", 7), ("이십이", 22), ("십이", 12), ("사", 4)):
        ck(f"'{t}' = {want}", ko_num(t) == want, str(ko_num(t)))
    ck("'칠억' 과 '7억' 을 같은 값으로 본다", moneys("칠억") == moneys("7억"))
    ck("'수십억' 은 숫자로 안 친다", not moneys("수십억을 가로챈"))
    ck("'이십이억' 을 읽는다", moneys("이십이억 원이 넘었습니다") == {22})

    print("\n② 편 제목·화면 카드가 **그 편이 말하는 돈**과 어긋나지 않는가")
    seen = 0
    for f in sorted(SERIES.glob("S*.story.json")):
        sid = f.stem.split(".")[0]
        d = json.loads(f.read_text(encoding="utf-8"))
        for p in d.get("parts") or []:
            a, b = p["cuts"]
            cs = [c for c in d["cuts"] if a <= c["n"] <= b]
            said = set()
            for c in cs:
                for _, t in c.get("turns") or []:
                    said |= moneys(t)
            # ⚠️ 카드는 **첫 컷과 같이** 뜬다 — 첫 컷이 말하는 돈을 먼저 본다
            first = moneys(" ".join(t for _, t in (cs[0].get("turns") or [])))
            for what, txt in (("화면 카드", " ".join(p.get("card") or [])),
                              ("제목", p.get("yt_title") or "")):
                shown = moneys(txt)
                if not shown:
                    continue
                seen += 1
                # 카드에 적힌 돈이 그 편 어디에서도 안 나오면 어긋난 것이다
                miss = shown - said
                extra = ""
                if what == "화면 카드" and first and not (shown & first):
                    extra = (f" · 첫 컷은 {sorted(first)}억을 말하는데 "
                             f"카드는 {sorted(shown)}억이라 **나란히** 뜬다")
                ck(f"{sid} {p['no']}편 {what}: {sorted(shown)}억",
                   not miss and not extra,
                   f"이 편은 {sorted(said) or '돈을'} 말하는데 {sorted(miss)}억이라 적혀 있다{extra}")
    ck("볼 것이 있었다 (검사가 헛돌지 않았다)", seen > 0)

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 숫자 어긋남: {len(bad)}군데 — 보는 사람에게는 틀린 것으로 보인다")
        for x in bad:
            print(f"     {x}")
        return 1
    print("✅ 숫자: 화면 글자와 말이 같은 돈을 말한다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
