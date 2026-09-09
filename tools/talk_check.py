#!/usr/bin/env python3
"""⭐ **대사 컷만 영상이 되는가 · 값이 새지 않는가.** 값 0원.

    python3 tools/talk_check.py

⭐⭐⭐ 2026-09-09 손님: "나레이션은 모두 이미지로 대체하고, 대사 부분만
   영상으로 제작하는 방식이 더 나을 것 같아. 나레이션을 충분히 넣어 이해를
   높이고 대사 부분은 영상으로 제작해서 등장인물에 몰입도를 강화."

   2026-09-09 시험 구매(S91 컷21 · 706원)로 한국어 발화가 쓸 만한 것을 눈과
   귀로 확인한 뒤에 붙였다.

여기서 보는 것
   ① 나레이션 컷은 **한 컷도** 영상으로 안 산다 (손님 지시의 핵심)
   ② 편마다 정해진 수만 산다 · 같은 인물을 너무 여러 번 안 산다
   ③ 첫 컷·마지막 컷은 안 고른다 (제목 카드·「다음 편에 계속」이 얹히는 자리)
   ④ 값이 얼마나 나가는지 · 편 첫 장면과 동시에 안 켜지는지
   ⑤ 실패하면 그 컷만 **그림으로** 돌아가는가 (편 전체를 안 죽인다)
   ⑥ 손으로 올린 영상이 기계 것에 안 덮이는가
   ⑦ 자막이 뒤에 남지 않게 말 끝에서 자르는가

⚠️ 손님이 고치는 파일에 안 묶는다 — 붙박이 대본으로 시험한다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import short90 as S9                                         # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def fake(nparts=3, per=9):
    """붙박이 대본 — 편마다 나레이션 여섯·대사 셋."""
    cuts, parts, n = [], [], 0
    for p in range(nparts):
        a = n + 1
        for i in range(per):
            n += 1
            # 첫 컷·마지막 컷은 나레이션, 가운데 셋은 대사
            if i in (2, 4, 6):
                who = ["아내", "남편", "내연녀"][i // 2 - 1]
                t = f"{who}가 {p}편에서 하는 말입니다 이것은 {i}번째 대사"
            else:
                who, t = "나레이션", f"{p}편 {i}번째 나레이션입니다 길게 풀어 씁니다"
            cuts.append({"n": n, "who": [] if who == "나레이션" else [who],
                         "turns": [[who, t]],
                         "veo": "a 6-second single continuous take of a room"})
        parts.append({"no": p + 1, "cuts": [a, n], "card": ["가", "나"]})
    return {"sid": "S99", "title": "시험", "cuts": cuts, "parts": parts}


def main():
    print("⭐ 대사 컷만 영상이 되는가 (값 0원)\n")
    doc = fake()
    got = S9.talk_cuts(doc)

    print("① 나레이션 컷은 한 컷도 안 산다")
    narr = [c["n"] for c in got if S9.is_narr(c)]
    ck("고른 것 가운데 나레이션이 없다", not narr, f"컷{narr} 이 나레이션이다")
    ck("고른 것이 있다 (아무것도 안 고르면 기능이 죽은 것이다)", got)

    print("\n② 편마다·인물마다 정해진 수만 산다")
    per_part = {}
    for c in got:
        for p in doc["parts"]:
            if p["cuts"][0] <= c["n"] <= p["cuts"][1]:
                per_part[p["no"]] = per_part.get(p["no"], 0) + 1
    over = [k for k, v in per_part.items() if v > S9.TALK_PER_PART]
    ck(f"편마다 {S9.TALK_PER_PART}컷까지다", not over, f"{over}편이 넘겼다")
    who = {}
    for c in got:
        w = S9.turns_of(c)[0][0]
        who[w] = who.get(w, 0) + 1
    over2 = [k for k, v in who.items() if v > S9.TALK_PER_PERSON]
    ck(f"같은 인물은 {S9.TALK_PER_PERSON}컷까지다 "
       f"(목소리가 흔들릴 기회를 줄인다)", not over2, f"{over2} 가 넘겼다")

    print("\n③ 첫 컷·마지막 컷은 안 고른다")
    # ⚠️⚠️ 처음에는 위 붙박이 대본으로 봤는데, 거기서는 첫·마지막 컷이
    #    나레이션이라 **가려내는 규칙을 없애도 시험이 통과했다.** 시험이
    #    재려는 것을 못 재고 있었던 것이다.
    #    → 첫 컷과 마지막 컷을 **짧은 대사**로 둔 대본을 따로 만든다. 고르는
    #      규칙이 같은 값이면 짧은 것을 먼저 고르므로, 가려내지 않으면
    #      반드시 그 둘이 뽑힌다.
    edoc = fake()
    for p in edoc["parts"]:
        a, b = p["cuts"]
        for n2, who2 in ((a, "아내"), (b, "남편")):
            c2 = [x for x in edoc["cuts"] if x["n"] == n2][0]
            c2["who"] = [who2]
            c2["turns"] = [[who2, "짧은 말"]]      # 가장 짧다 = 가장 먼저 뽑힌다
    egot = S9.talk_cuts(edoc)
    edge = []
    for p in edoc["parts"]:
        a, b = p["cuts"]
        edge += [c["n"] for c in egot if c["n"] in (a, b)]
    ck("편 첫 컷·마지막 컷이 안 들어 있다", not edge,
       f"컷{edge} — 제목 카드와 「다음 편에 계속」이 얹히는 자리다")
    ck("그래도 가운데에서 골라 온다 (아무것도 안 고르면 뜻이 없다)", egot)

    print("\n④ 값과 스위치")
    import cost, veo                                         # noqa: E402
    tot = sum(cost.video_krw(veo.MODEL, S9.talk_sec(S9.turns_of(c)[0][1]))
              for c in got)
    ck(f"세 편에 약 {tot:,.0f}원 — 한 사건 값의 절반을 안 넘는다",
       tot <= 3000, f"{tot:,.0f}원")
    src = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
    ck("켜야만 돈다 (VT_TALK_VIDEO)", "VT_TALK_VIDEO" in src)
    yml = (ROOT / ".github" / "workflows" / "short90.yml").read_text(encoding="utf-8")
    ck("편 첫 장면과 동시에 안 켜진다",
       "startsWith(inputs.video_kind, '대사 장면')" in yml
       and "startsWith(inputs.video_kind, '편 첫 장면')" in yml)

    print("\n⑤~⑦ 안전장치")
    fn = (re.search(r"\ndef talkers\([\s\S]*?(?=\ndef )", src) or [""])[0]
    ck("실패하면 그 컷만 그림으로 간다 (편 전체를 안 죽인다)",
       "이 컷은 그림으로 갑니다" in fn and "continue" in fn)
    ck("소리 없는 영상을 걸러 낸다 (조용한 실패를 막는다)",
       "has_audio(" in fn)
    ck("지문에 그림과 모델을 넣는다 (그림이 바뀌면 다시 만든다)",
       "veo.MODEL" in fn and "read_bytes().hex()" in fn)
    ck("이름이 밀려도 다시 안 산다 (salvage)", "salvage(" in fn)
    ck("안전필터에 걸리면 딱 한 번만 다시 산다",
       fn.count("veo.make_clip(") == 2)
    build = (re.search(r"\ndef build_part\([\s\S]*?(?=\ndef )", src) or [""])[0]
    ck("손으로 올린 영상이 기계 것보다 먼저다",
       "if not clip.exists():" in build and "talk_dir()" in build)
    ck("말 끝에서 잘라 자막이 뒤에 안 남는다",
       "def talk_trim(" in src and "talk_trim(" in fn)
    ck("안전필터 고위험 대사는 애초에 안 고른다", "TALK_HOT" in src)

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 대사 장면: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 대사 장면: 대사 컷만 · 편마다 하나 · 실패해도 그림으로 간다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
