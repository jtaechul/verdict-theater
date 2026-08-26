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

⭐⭐ 2026-08-25 — 검사를 다시 짰다 (운영자)
    "자극성만 신경쓰니까 씬 간 연결성과 스토리 전개가 제대로 이루어지지 않고
     있어. 이건 광고가 아니고 드라마라는걸 다시 한번 생각해."

    옛 검사 ③ 은 **"마지막 대사가 물음표로 끝나야 한다"** 였다. 그게 오히려
    화를 광고로 만들었다 — 16화 중 14화가 물음표로 끝나는데, 그중 4곳은
    다음 화가 그 질문을 무시하고 딴 얘기를 시작했다. 물음표는 이어짐을
    **흉내만** 낸 것이지 실제로 이어 준 것이 아니었다.
    → 물음표는 **알림**으로 내리고, 진짜 이어짐을 글자로 검사한다.

무엇을 보나 (버리는 것)
    ① **누설** — 아직 안 밝혀진 사실을 앞 화에서 미리 말하지 않는가
       (아내가 없는 화 `irony` 는 시청자만 먼저 아는 화라 빼고 본다)
    ② **실행** — 그 화에 배정된 폭로가 대사에 실제로 있는가
    ③ **이음** — 이 화가 남긴 것(leaves)이 다음 화가 시작되는 까닭(because)과
       **글자 그대로 같은가.** 다르면 두 화 사이가 끊긴 것이다
    ④ **금액** — 대사에 나오는 돈이 금액 장부에 있는 값인가
    ⑤ **때** — 화가 넘어갈 때 시점이 거꾸로 가지 않는가
    ⑥ **되풀이 폭로** — 같은 폭로를 두 화가 나눠 갖지 않는가
    ⑦ **되풀이 대결** — 같은 사람 조합이 세 화를 넘어 잇달지 않는가
       (옛 대본은 5~16화, 12화 연속으로 아내와 그 여자가 싸웠다)
    ⑧ **셈여림** — 조용한 화(quiet)가 하나는 있고 절반은 넘지 않는가

무엇을 알리기만 하나 (안 버린다)
    · **끊기** — 마지막 대사가 물음표·말줄임으로 끝나지 않는 화
      (조용한 화는 여운으로 끝나는 게 맞으므로 알리지도 않는다)
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


# 한 화에 몇 명이 말하든 조합을 하나의 이름으로 (되풀이 대결 검사용)
def cast_key(ep):
    who = set()
    for c in ep.get("cuts") or []:
        who |= {w for w, _ in S.dia_turns(c.get("prompt"))}
    return " · ".join(sorted(who))


CHAIN_MAX = 3          # 같은 조합이 잇달아도 되는 최대 화 수


def scan(doc, soft=None):
    """어긋난 곳들을 돌려준다. soft 를 넘기면 '알리기만 할 것' 이 담긴다."""
    bad = []
    soft = soft if soft is not None else []
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

        # ③ 이음 — 이 화가 남긴 것이 다음 화가 시작되는 까닭인가
        nxt = next((x for x in eps if x.get("no") == (no or 0) + 1), None)
        if nxt is not None:
            leaves = str(e.get("leaves") or "").strip()
            because = str(nxt.get("because") or "").strip()
            if not leaves:
                bad.append(f"{no}화: 이 화가 남기는 것(leaves)이 비었다 — "
                           f"다음 화가 무엇에서 시작되는지 알 수 없다")
            elif leaves != because:
                bad.append(f"{no}화 → {nxt.get('no')}화 사이가 끊겼다\n"
                           f"        {no}화가 남긴 것 : {leaves}\n"
                           f"        {nxt.get('no')}화가 시작되는 까닭: "
                           f"{because or '(비었다)'}")

        # 끊기 — **알리기만 한다.** 물음표를 강제하면 화가 광고처럼 된다.
        cuts = e.get("cuts") or []
        if cuts and no != len(eps) and not e.get("quiet"):
            turns = S.dia_turns(cuts[-1].get("prompt"))
            last = turns[-1][1].strip() if turns else ""
            if not last.endswith(("?", "…")):
                soft.append(f"{no}화: 마지막 대사가 여운 없이 끝난다 — "
                            f"'{last[-18:]}'")

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

    # ⑦ 같은 조합이 세 화를 넘어 잇달지 않는가
    run_key, run_from = None, None
    run = 0
    for e in eps + [{}]:
        k = cast_key(e) if e else None
        if k == run_key:
            run += 1
            continue
        if run_key and run > CHAIN_MAX:
            bad.append(f"{run_from}화부터 {run}화 잇달아 같은 사람끼리만 "
                       f"부딪힌다 — {run_key} (상대를 바꿔야 단조롭지 않다)")
        run_key, run_from, run = k, e.get("no") if e else None, 1

    # ⑧ 셈여림 — 조용한 화가 하나는 있어야 하고, 절반을 넘어서도 안 된다
    if eps:
        quiet = [e.get("no") for e in eps if e.get("quiet")]
        if not quiet:
            bad.append("조용한 화(quiet)가 하나도 없다 — 16화 내내 세기가 "
                       "같으면 시청자가 무뎌진다")
        elif len(quiet) > len(eps) // 2:
            bad.append(f"조용한 화가 {len(quiet)}개다 (절반 "
                       f"{len(eps) // 2}개 이내여야 늘어지지 않는다)")
    return bad


def selftest():
    """⚠️ 잡지도 못하면서 초록불만 켜는 검사가 제일 위험하다."""
    def ep(no, when, must, last, extra="", **kw):
        turns = f'  Wife (numb, in Korean): "{extra}"\n' if extra else ""
        d = {"no": no, "when": when, "must": must, "reveal": f"r{no}",
             "because": f"c{no}", "leaves": f"c{no + 1}",
             "cuts": [{"n": 1, "prompt":
                       "DIALOGUE: x\n" + turns +
                       f'  Wife (numb, in Korean): "{last}"'}]}
        d.update(kw)
        return d

    def two(**kw):
        """멀쩡한 두 화 — 이음·조용한 화·상대 바꾸기까지 다 맞춰 둔다."""
        a = ep(1, "2012년 가을", ["기각"], "기각이야?", quiet=True, **kw)
        b = ep(2, "2013년 8월", ["십억"], "십억이라니.")
        b["cuts"][0]["prompt"] = ("DIALOGUE: x\n"
                                  '  Husband (numb, in Korean): "십억이라니."')
        return {"ledger": {}, "episodes": [a, b]}

    ok = two()
    assert not scan(ok), f"멀쩡한 것을 걸었다: {scan(ok)}"

    d = two(); d["episodes"][0]["cuts"][0]["prompt"] = (
        "DIALOGUE: x\n  Wife (numb, in Korean): \"십억\"\n"
        "  Wife (numb, in Korean): \"기각이야?\"")
    assert any("미리 말한다" in b for b in scan(d)), f"누설을 못 잡는다: {scan(d)}"

    d = two(); d["episodes"][0]["must"] = ["없는말"]
    assert any("대사에 없다" in b for b in scan(d)), "빠진 폭로를 못 잡는다"

    # ③ 이음 — 앞 화가 남긴 것과 다음 화가 시작되는 까닭이 다르면 잡는다
    d = two(); d["episodes"][1]["because"] = "엉뚱한 데서 시작한다"
    assert any("사이가 끊겼다" in b for b in scan(d)), f"끊긴 이음을 못 잡는다: {scan(d)}"
    d = two(); d["episodes"][0]["leaves"] = ""
    assert any("비었다" in b for b in scan(d)), "빈 leaves 를 못 잡는다"

    # 끊기는 **버리지 않고 알린다**
    d = two(); d["episodes"][0]["quiet"] = False
    d["episodes"][1]["quiet"] = True
    d["episodes"][0]["cuts"][0]["prompt"] = (
        "DIALOGUE: x\n  Wife (numb, in Korean): \"답이다.\"")
    soft = []
    got = scan(d, soft)
    assert not any("여운" in b for b in got), "끊기로 버리면 안 된다"
    assert any("여운" in b for b in soft), f"끊기를 알리지도 않는다: {soft}"

    d = two(); d["ledger"] = {"a": "십억"}
    d["episodes"][0]["cuts"][0]["prompt"] = (
        "DIALOGUE: x\n  Wife (numb, in Korean): \"십오억?\"")
    d["episodes"][0]["must"] = ["십오억"]
    assert any("장부에 없는 금액" in b for b in scan(d)), "장부 밖 금액을 못 잡는다"

    d = two(); d["episodes"][0]["when"] = "2015년 봄"
    assert any("거꾸로" in b for b in scan(d)), "때가 거꾸로 가는 것을 못 잡는다"

    # ⑦ 같은 사람끼리만 네 화 잇달면 잡는다
    eps = []
    for n in range(1, 6):
        e = ep(n, f"201{n}년 봄", [f"m{n}"], f"m{n}?", quiet=(n == 1))
        eps.append(e)
    d = {"ledger": {}, "episodes": eps}
    assert any("잇달아 같은 사람" in b for b in scan(d)), \
        f"되풀이 대결을 못 잡는다: {scan(d)}"

    # ⑧ 조용한 화가 하나도 없으면 잡는다
    d = two(); d["episodes"][0]["quiet"] = False
    assert any("조용한 화" in b for b in scan(d)), "셈여림을 못 잡는다"

    print("   ✅ 자기시험: 누설 · 빠진 폭로 · 끊긴 이음 · 장부 밖 금액 · "
          "거꾸로 가는 때 · 되풀이 대결 · 셈여림 다 잡는다")


def main():
    print("⭐ 이야기 정합성 검사 (값 0원)\n")
    selftest()
    fails = 0
    for p in sorted((ROOT / "data" / "series").glob("S*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        soft = []
        bad = scan(doc, soft)
        eps = doc.get("episodes") or []
        print(f"\n{p.stem} — {len(eps)}화")
        if bad:
            fails += len(bad)
            for b in bad:
                print("   ❌ " + b)
        else:
            print("   ✅ 폭로가 화마다 하나씩 · 미리 새지 않는다")
            print("   ✅ 앞 화가 남긴 것에서 다음 화가 시작된다 (이음)")
            print("   ✅ 금액이 장부와 같다 · 때가 앞으로만 간다")
            print("   ✅ 상대가 바뀐다 · 조용한 화가 섞여 있다")
            for e in eps:
                print("      %2d화 %-11s %-9s %-6s %s"
                      % (e.get("no"), e.get("when", ""), e.get("mood", ""),
                         "조용" if e.get("quiet") else
                         ("아이러니" if e.get("irony") else ""),
                         (e.get("reveal") or "")[:30]))
        for b in soft:
            print("   ·  " + b)
    print("\n" + "─" * 60)
    if fails:
        print(f"❌ 이야기 정합성: {fails}가지 어긋남 — 고치고 다시")
        return 1
    print("✅ 이야기 정합성: 전부 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
