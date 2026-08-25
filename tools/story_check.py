#!/usr/bin/env python3
"""이야기가 앞뒤로 맞는가 — **정합성 검사** (0원 · 인터넷 0회 · 1초)

    python3 tools/story_check.py              실제 대본을 검사한다
    python3 tools/story_check.py --selftest   검사기가 진짜 잡는지 스스로 시험

왜 이 검사가 있는가 (2026-08-25 운영자)
    운영자가 대본에서 이런 것을 짚어 냈다 —
      "남편: '내 앞으로 된 건 이미 하나도 없거든.' … 이 대사는 맞는 거야?"
    낱말은 맞았지만 **시점이 틀렸다.** 그 대사를 1화에 넣었는데, 재산을
    넘기는 것은 2013년 이혼 기각 뒤(3·4화)의 일이다. 1화에서 그 말을 하면
    아직 일어나지 않은 일을 말하는 것이다.
    이런 것은 눈으로 읽어서는 안 보인다 — 16화를 한꺼번에 놓고 봐야 보인다.

무엇을 보나
    ① **누설** — 아직 안 밝혀진 사실을 앞 화에서 미리 말하지 않는가
       (아내가 없는 화 `irony` 는 시청자만 먼저 아는 화라 빼고 본다)
    ② **실행** — 그 화에 배정된 폭로가 대사에 실제로 있는가
    ③ **끊기** — 마지막 대사가 물음표로 끝나는가 (마지막 화만 예외)
    ④ **금액** — 대사에 나오는 돈이 금액 장부에 있는 값인가
    ⑤ **때** — 화가 넘어갈 때 시점이 거꾸로 가지 않는가
    ⑥ **되풀이** — 같은 폭로를 두 화가 나눠 갖지 않는가
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import series as S                                           # noqa: E402

# 대사에 나올 수 있는 돈 표현 (한글 수사 + 숫자)
MONEY = re.compile(r"(?:[일이삼사오육칠팔구십백천만억\d]+\s*(?:억|천만\s*원|만\s*원))")
# 때 표기 → 정렬용 숫자
SEASON = {"봄": 3, "여름": 6, "가을": 9, "겨울": 12}


def when_key(t):
    """'2013년 8월' · '2017년 여름' → 정렬할 수 있는 숫자."""
    m = re.match(r"(\d{4})년\s*(?:(\d{1,2})월|(봄|여름|가을|겨울))?", str(t or ""))
    if not m:
        return None
    y = int(m.group(1))
    mo = int(m.group(2)) if m.group(2) else SEASON.get(m.group(3), 1)
    return y * 12 + mo


def lines_of(ep):
    """그 화의 대사를 한 덩이 글로."""
    return " / ".join(t for c in ep.get("cuts") or []
                      for _, t in S.dia_turns(c.get("prompt")))


def scan(doc):
    """어긋난 곳들을 돌려준다."""
    bad = []
    eps = doc.get("episodes") or []
    ledger = set((doc.get("ledger") or {}).values())
    said = {e.get("no"): lines_of(e) for e in eps}

    seen_reveal = {}
    for e in eps:
        no = e.get("no")
        must = [m for m in (e.get("must") or []) if str(m).strip()]
        mine = said.get(no, "")

        # ② 배정된 폭로가 이 화 대사에 실제로 있는가
        if e.get("reveal") and not must:
            bad.append(f"{no}화: 폭로를 적어 두고 검사 낱말(must)이 없다")
        for m in must:
            if m not in mine:
                bad.append(f"{no}화: 이 화의 폭로가 대사에 없다 — '{m}' "
                           f"({e.get('reveal')})")

        # ① 아직 안 밝혀진 사실을 앞 화가 미리 말하지 않는가
        for prev in eps:
            pno = prev.get("no")
            if pno is None or no is None or pno >= no:
                continue
            if prev.get("irony"):        # 시청자만 먼저 아는 화는 봐준다
                continue
            for m in must:
                if m in said.get(pno, ""):
                    bad.append(f"{pno}화: {no}화에서 밝혀질 것을 미리 말한다 — '{m}'")

        # ⑥ 같은 폭로를 두 화가 나눠 갖지 않는가
        key = str(e.get("reveal") or "").strip()
        if key:
            if key in seen_reveal:
                bad.append(f"{no}화: {seen_reveal[key]}화와 폭로가 같다 — '{key}'")
            seen_reveal[key] = no

        # ③ 질문으로 끊는가
        cuts = e.get("cuts") or []
        if cuts and no != len(eps):
            turns = S.dia_turns(cuts[-1].get("prompt"))
            last = turns[-1][1].strip() if turns else ""
            if not last.endswith(("?", "…")):
                bad.append(f"{no}화: 마지막 대사가 질문이 아니다 — '{last[-18:]}' "
                           f"(답으로 끝나면 다음 화를 볼 이유가 없다)")

        # ④ 대사에 나오는 돈이 장부에 있는 값인가
        if ledger:
            for m in MONEY.findall(mine):
                m = re.sub(r"\s+", " ", m).strip()
                if m not in ledger:
                    bad.append(f"{no}화: 장부에 없는 금액이 나온다 — '{m}' "
                               f"(장부: {', '.join(sorted(ledger))})")

    # ⑤ 때가 거꾸로 가지 않는가
    prev_k, prev_no = None, None
    for e in eps:
        k = when_key(e.get("when"))
        if k is None:
            bad.append(f"{e.get('no')}화: 때(when)가 없거나 못 읽는다 — "
                       f"'{e.get('when')}'")
            continue
        if prev_k is not None and k < prev_k:
            bad.append(f"{e.get('no')}화: 때가 거꾸로 간다 "
                       f"({prev_no}화 {eps[prev_no - 1].get('when')} → "
                       f"{e.get('when')})")
        prev_k, prev_no = k, e.get("no")
    return bad


def selftest():
    """⚠️ 잡지도 못하면서 초록불만 켜는 검사가 제일 위험하다."""
    def ep(no, when, must, last, extra=""):
        turns = f'  Wife (numb, in Korean): "{extra}"\n' if extra else ""
        return {"no": no, "when": when, "must": must, "reveal": f"r{no}",
                "cuts": [{"n": 1, "prompt":
                          "DIALOGUE: x\n" + turns +
                          f'  Wife (numb, in Korean): "{last}"'}]}
    ok = {"ledger": {}, "episodes": [ep(1, "2012년 가을", ["기각"], "기각이야?"),
                                     ep(2, "2013년 8월", ["십억"], "십억이라니.")]}
    assert not scan(ok), f"멀쩡한 것을 걸었다: {scan(ok)}"

    d = {"ledger": {}, "episodes": [ep(1, "2012년 가을", ["가"], "가?", "십억"),
                                    ep(2, "2013년 8월", ["십억"], "끝.")]}
    got = scan(d)
    assert any("미리 말한다" in b for b in got), f"누설을 못 잡는다: {got}"

    d = {"ledger": {}, "episodes": [ep(1, "2012년 가을", ["없는말"], "가?"),
                                    ep(2, "2013년 8월", ["가"], "끝.")]}
    assert any("대사에 없다" in b for b in scan(d)), "빠진 폭로를 못 잡는다"

    d = {"ledger": {}, "episodes": [ep(1, "2012년 가을", ["가"], "답이다."),
                                    ep(2, "2013년 8월", ["가"], "끝.")]}
    assert any("질문이 아니다" in b for b in scan(d)), "답으로 끝나는 것을 못 잡는다"

    d = {"ledger": {"a": "십억"},
         "episodes": [ep(1, "2012년 가을", ["가"], "십오억?"),
                      ep(2, "2013년 8월", ["가"], "끝.")]}
    assert any("장부에 없는 금액" in b for b in scan(d)), "장부 밖 금액을 못 잡는다"

    d = {"ledger": {}, "episodes": [ep(1, "2015년 봄", ["가"], "가?"),
                                    ep(2, "2013년 8월", ["가"], "끝.")]}
    assert any("거꾸로" in b for b in scan(d)), "때가 거꾸로 가는 것을 못 잡는다"
    print("   ✅ 자기시험: 누설 · 빠진 폭로 · 답으로 끝내기 · 장부 밖 금액 · "
          "거꾸로 가는 때 다 잡는다")


def main():
    print("⭐ 이야기 정합성 검사 (값 0원)\n")
    selftest()
    fails = 0
    for p in sorted((ROOT / "data" / "series").glob("S*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        bad = scan(doc)
        eps = doc.get("episodes") or []
        print(f"\n{p.stem} — {len(eps)}화")
        if bad:
            fails += len(bad)
            for b in bad:
                print("   ❌ " + b)
        else:
            print("   ✅ 폭로가 화마다 하나씩 · 미리 새지 않는다")
            print("   ✅ 질문으로 끊는다 (마지막 화 빼고)")
            print("   ✅ 금액이 장부와 같다 · 때가 앞으로만 간다")
            for e in eps:
                print("      %2d화 %-11s %-14s %s"
                      % (e.get("no"), e.get("when", ""), e.get("mood", ""),
                         (e.get("reveal") or "")[:34]))
    print("\n" + "─" * 60)
    if fails:
        print(f"❌ 이야기 정합성: {fails}가지 어긋남 — 고치고 다시")
        return 1
    print("✅ 이야기 정합성: 전부 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
