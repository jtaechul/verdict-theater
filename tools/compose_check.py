#!/usr/bin/env python3
"""⭐ **구도가 그림에도 닿는가.** 값 0원 (인터넷 0회).

    python3 tools/compose_check.py

⭐⭐⭐ 2026-09-20 손님: "카메라 구도가 아직도 너무 단조로운데 … 이게 지금
   이미지만 나와서 이렇게 된 거예요?"

   **그렇다.** 뜯어보니 연출(shot_of — 와이드·인서트·로우앵글·어깨너머·
   락오프 + 권력 각도)은 **영상 프롬프트 한 곳에서만** 불리고 있었다.
   그림 프롬프트는 36컷에 문구가 **둘뿐**이었다 —
       21컷 "허리 위로 잡아 모든 얼굴이 또렷하게"
       15컷 "장소 자체가 주인공, 조용히 비어 있게"
   게다가 마지막 실행은 영상을 한 편도 안 샀다(옵션 전부 꺼짐). 화면의
   100%가 그림이므로 **연출이 한 프레임도 안 닿았다.**

   ⚠️ 이런 것은 **글로는 안 드러난다.** 연출 코드가 멀쩡히 있고 검사도
      초록불이었다. 잇는 자리가 하나 빠졌을 뿐인데 결과는 "아무것도 안 한
      것"과 같았다. → 여기서 **만들어 낸 지문을 세어** 본다.

여기서 지키는 것
   ① 그림 지문의 구도가 **여러 가지**다 (하나면 컷이 전부 같아 보인다)
   ② 그림과 영상이 **같은 구도표**를 읽는다 (두 벌이면 한쪽만 좋아진다)
   ③ 이웃한 컷이 같은 구도가 아니다
   ④ 그림 지문에는 **움직임이 안 들어간다** (그림은 못 움직인다)
   ⑤ 장소 컷 구도에 사람이 안 섞인다 (핵심 규칙)
   ⑥ 같은 컷은 늘 같은 구도다 (무작위면 다시 만들 때마다 값이 나간다)
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

spec = importlib.util.spec_from_file_location("b", ROOT / "tools"
                                              / "build_short90.py")
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)

bad = []
# 움직임을 말하는 낱말 — 그림 지문에 있으면 안 된다
MOVING = re.compile(r"\b(zoom|push(?:ing)? in|pull(?:ing)? back|pan(?:ning)?|"
                    r"dolly|drift(?:ing)?|track(?:ing)?|lateral move|"
                    r"locked off|already under way)\b", re.I)
PERSON = re.compile(r"\b(person|people|man|woman|men|women|face|faces|"
                    r"mouths?|他|figure)\b", re.I)


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name
          + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def shot_line(txt):
    m = re.search(r"SHOT: (.+)", txt or "")
    return m.group(1).strip() if m else ""


def main():
    print("⭐ 구도가 그림에도 닿는가 (값 0원)\n")

    print("① 그림 지문의 구도가 여러 가지인가 (진짜 대본으로 잰다)")
    f = ROOT / "data" / "series" / "S93.json"
    if not f.exists():
        ck("S93 대본이 있다", False, "data/series/S93.json 이 없다")
        return 1
    doc = json.loads(f.read_text("utf-8"))
    cuts = doc.get("cuts") or []
    talk_s, place_s, seq = [], [], []
    for c in cuts:
        line = shot_line(c.get("still"))
        if not line:
            continue
        # 화면 묘사(컷마다 다르다)를 빼고 **구도 지시**만 본다
        key = line.replace(str(c.get("scene") or ""), "").strip(" .")[:70]
        seq.append((c["n"], key))
        (place_s if not (c.get("who") or []) or c.get("narr")
         else talk_s).append(key)
    kinds = {k for _n, k in seq}
    ck(f"구도가 여러 가지다 ({len(kinds)}가지 · 예전 2가지)", len(kinds) >= 8,
       "컷마다 같은 구도면 켄번즈를 걸어도 단조롭다")
    ck(f"사람 컷 구도가 여러 가지다 ({len(set(talk_s))}가지)",
       len(set(talk_s)) >= 3)
    ck(f"장소 컷 구도가 여러 가지다 ({len(set(place_s))}가지)",
       len(set(place_s)) >= 3)

    print("\n② 그림과 영상이 같은 구도표를 읽는가")
    src = (ROOT / "tools" / "build_short90.py").read_text("utf-8")
    ck("그림 지문이 compose_of 를 부른다",
       src.count("compose_of(c, prev, ctx, who)") >= 2,
       "여기가 빠져 있어서 연출이 한 프레임도 안 닿았다")
    ck("영상 지문도 같은 compose_of 를 부른다",
       "compose_of(c, prev, ctx)" in src.split("def shot_of")[1])
    ck("구도표가 한 벌이다 (PLACE/TALK/CAST 세 표뿐)",
       all(x in src for x in ("PLACE_SHOTS", "TALK_SHOTS",
                              "CAST_NARR_SHOTS")))
    # ⚠️ ctx(결정적 순간·힘 뒤집힘)를 여기서 다시 만들면 **잣대가 두 벌**이
    #    된다(그러다 컷 1·8·18 을 잘못 잡았다). 표의 글귀가 대본에 실제로
    #    박혀 있는지만 본다 — 닿았는지를 재는 데는 그것이면 충분하다.
    heads = []
    for tbl in (B.PLACE_SHOTS, B.TALK_SHOTS, B.CAST_NARR_SHOTS):
        for shot, _fr in tbl:
            heads.append(shot.split("{")[0].strip()[:28])
    heads += ["An over-the-shoulder shot past", "A tight close-up on the face"]
    off = [c["n"] for c in cuts
           if shot_line(c.get("still"))
           and not any(h and h in c["still"] for h in heads)]
    ck("대본에 찍힌 그림 구도가 **표에서 나온 것**이다", not off,
       f"컷 {off[:5]} — 대본이 옛 표로 지어졌다 (대본 다시 짓기 필요)")

    print("\n③ 이웃한 컷이 같은 구도가 아닌가")
    nb = [b for (x, p), (b, q) in zip(seq, seq[1:]) if p == q]
    ck("이웃한 컷이 같은 구도가 아니다", not nb, f"컷 {nb[:6]}")

    print("\n④ 그림 지문에 움직임이 안 들어가는가 (그림은 못 움직인다)")
    moved = []
    for c in cuts:
        hit = MOVING.findall(c.get("still") or "")
        if hit:
            moved.append((c["n"], hit[:2]))
    ck("그림 지문에 카메라 움직임이 없다", not moved, str(moved[:3]))
    v = [c for c in cuts if c.get("veo")]
    # ⚠️ **멈춘 샷도 연출이다.** 결정적 순간엔 일부러 카메라를 세운다(전부
    #    움직이면 싸구려가 된다). 그러니 "움직인다" 가 아니라 "카메라를 어떻게
    #    할지 적혀 있다" 를 본다.
    def has_cam(t):
        return bool(MOVING.search(t)) or "holding still" in t
    ck("영상 지문에는 카메라 지시가 있다 (움직이거나, 일부러 멈추거나)",
       bool(v) and all(has_cam(c["veo"]) for c in v[:8]),
       "아무 지시도 없으면 그림과 다를 게 없다")
    moving_n = sum(1 for c in v if MOVING.search(c["veo"]))
    ck(f"그중 대부분은 실제로 움직인다 ({moving_n}/{len(v)}컷)",
       len(v) and moving_n >= len(v) * 0.6,
       "멈춘 샷만 이어지면 영상을 산 뜻이 없다")

    print("\n⑤ 장소 컷 구도에 사람이 안 섞이는가 (핵심 규칙)")
    leak = []
    for n in range(1, 25):
        g = B.still_prompt({"n": n, "who": [], "turns": [["나레이션", "ㄱ"]],
                            "scene": "a thick folder on a desk"}, None, {})
        hit = PERSON.findall(shot_line(g))
        if hit:
            leak.append((n, hit))
    ck("장소 컷 구도에 사람 낱말이 없다", not leak, str(leak[:3]))

    print("\n⑥ 같은 컷은 늘 같은 구도인가 (무작위면 값이 또 나간다)")
    c0 = {"n": 7, "who": ["아내"], "turns": [["아내", "말한다"]],
          "scene": "the wife sits at a table"}
    got = {B.still_prompt(dict(c0), None, {"talks": True}) for _ in range(5)}
    ck("다섯 번 불러도 같은 지문이다", len(got) == 1,
       "달라지면 다시 만들 때마다 그림 값이 새로 나간다")

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 구도: {len(bad)}군데")
        for x in bad:
            print(f"     {x}")
        return 1
    print("✅ 구도: 그림에도 닿고 · 여러 가지고 · 사람은 안 섞인다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
