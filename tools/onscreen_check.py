#!/usr/bin/env python3
"""⭐ **화면에 등록 안 된 사람이 나오지 않는지** 본다. 값 0원 (아무것도 안 만든다).

    python3 tools/onscreen_check.py

손님(2026-09-12, 화면 캡처와 함께)
  "지금 상대방이 장남인데 저 이미지는 장남이 아니잖아.
   등장인물을 등록했으면 등록 인물만 영상이나 이미지에 나올 수 있도록 해."

까닭은 **하나가 아니라 셋**이었다 —
  ① 대사 컷에는 사람 수를 세는 규칙이 **아예 없었다.** 나레이션 컷만
     "사람을 부르지 마라" 로 막아 두었고, 대사 쪽으로 그대로 샜다.
       컷5  who=['아버지']  "the old man stares at **the middle-aged man**"
     남는 사람은 얼굴 참조가 없으니 그림 모델이 **지어낸다.**
  ② 얼굴을 붙이는 scene_en 은 같은 나이·성별이 둘이면(장남·차남 둘 다
     50대 남) 일부러 안 붙인다 — 옳은 판단이다. 그런데 **안 붙이고 나서
     아무도 막지 않았다.** 못 붙이면 그리지 말았어야 했다.
  ③ 나레이션 규칙 자체도 **복수형에 뚫려 있었다.** `\\blawyer\\b` 는
     "two lawyers" 에 안 걸린다(뒤에 s 가 붙어 낱말 끝이 아니다).
     S92 컷31 이 규격 검사를 그대로 통과했다.

이 검사는 **되돌리면 걸리도록** 짰다 — 규칙을 지우거나 복수형을 빼거나
관문 한 곳을 없애면 여기서 빨간불이 난다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import story90 as ST                                         # noqa: E402
import short90 as S90                                        # noqa: E402
import build_short90 as B                                    # noqa: E402

bad = []


def ck(name, ok):
    print(("  ✅ " if ok else "  ❌ ") + name)
    if not ok:
        bad.append(name)


def cut(n, who, scene, speaker="아버지", text="여기 도장을 찍어라."):
    return {"n": n, "sec": 4.0, "who": list(who), "scene": scene,
            "turns": [[speaker, text]],
            "say": ["70대 남성이, 조용하고 단단하게"]}


def doc_of(*cuts):
    return {"sid": "TEST", "title": "시험",
            "people": {"아버지": {"age": "70대", "sex": "남"},
                       "장남": {"age": "50대", "sex": "남"},
                       "차남": {"age": "50대", "sex": "남"},
                       "딸": {"age": "50대", "sex": "여"}},
            "parts": [{"no": 1, "cuts": [1, len(cuts)], "title": "ㄱ",
                       "card": ["ㄱ", "ㄴ"]}],
            "cuts": list(cuts)}


def main():
    print("■ ① 사람 세기 — 화면 묘사에 몇 명이 있는가")
    # ⚠️ 이 시험이 **스스로 쉬운 문제를 내면** 아무것도 재지 못한다.
    #    그래서 손님이 실제로 보신 그 문장을 그대로 쓴다.
    two = "the old man stares at the middle-aged man with a stiff expression"
    ck("'the old man … the middle-aged man' 은 두 명으로 센다",
       len(ST.scene_heads(two)) == 2)
    ck("'stares at him' 은 사람 하나가 더 있는 것으로 센다",
       len(ST.scene_heads("the middle-aged woman stares at him")) == 2)
    ck("한 명짜리 묘사는 한 명으로 센다",
       len(ST.scene_heads("the middle-aged man crosses his arms")) == 1)
    # 헛걸리면 안 되는 것들 — 헛잡는 검사는 멀쩡한 일을 막는다
    ck("'at her side' 는 제 몸이지 딴 사람이 아니다 (헛걸리지 않는다)",
       len(ST.scene_heads("the wife holds the paper down at her side")) == 1)
    ck("'with her chin up' 도 헛걸리지 않는다",
       len(ST.scene_heads("the other woman stands with her chin up")) == 1)
    ck("'witness stand'(증인석)는 물건이지 사람이 아니다",
       ST.scene_heads("an empty witness stand under a courtroom light") == [])
    ck("사람이 하나도 없는 배경은 0명",
       ST.scene_heads("a folded document lies open on a worn wooden table") == [])

    print("\n■ ② 복수형이 그물을 빠져나가지 않는다")
    ck("'two lawyers' 를 사람으로 잡는다 (\\blawyer\\b 는 못 잡았다)",
       ST.narr_people("two lawyers sit at a large desk") != [])
    ck("'three doctors' 도 잡는다",
       ST.narr_people("three doctors walk down the hall") != [])
    ck("'witness stand' 는 나레이션에서도 헛걸리지 않는다",
       ST.narr_people("an empty witness stand under a light") == [])
    ck("규격 검사와 대본 만들기가 **같은 함수**를 쓴다",
       "narr_people" in (ROOT / "tools" / "build_short90.py").read_text("utf-8")
       and "narr_people(sc)" in (ROOT / "src" / "story90.py").read_text("utf-8"))

    print("\n■ ③ 규격 검사(story90.check)가 막는다")
    bad1 = ST.check(doc_of(cut(1, ["아버지"], two)))
    ck("who 1명인데 화면에 2명이면 규격 검사가 잡는다",
       any("화면에 나오는 사람" in b for b in bad1))
    ok1 = ST.check(doc_of(cut(1, ["아버지", "장남"], two)))
    ck("두 사람을 다 who 에 넣으면 통과한다 (고치는 길이 실제로 열려 있다)",
       not any("화면에 나오는 사람" in b for b in ok1))

    print("\n■ ④ 대본 만들기(build_short90)가 막는다")
    got = ""
    try:
        B.still_prompt(cut(9, ["아버지"], two))
    except SystemExit as e:
        got = str(e)
    ck("그림 지문을 만들기 **전에** 멈춘다", "화면에 사람이" in got)
    ck("멈추면서 고치는 길을 알려 준다", "who 에 넣거나" in got)
    got2 = ""
    try:
        B.still_prompt({"n": 9, "sec": 4.0, "who": [], "turns":
                        [["나레이션", "소송이 시작됐습니다."]], "say": ["담담하게"],
                        "scene": "two lawyers sit at a large desk"})
    except SystemExit as e:
        got2 = str(e)
    ck("나레이션 컷 복수형('two lawyers')도 여기서 멈춘다",
       "나레이션 컷 화면 묘사에 사람이" in got2)

    print("\n■ ⑤ 값이 나가는 자리(short90.stills)가 막는다")
    # ⚠️⚠️ 2026-09-12 — 여기는 처음에 **글만 읽었다**(소스에 그 낱말이 있나).
    #    그러는 사이 `ST.scene_extra` 라고 잘못 적어 stills 가 통째로 죽어
    #    있었는데(ST 는 still 모듈이지 story90 이 아니다) 이 검사는 초록불
    #    이었다. **글을 읽는 검사는 돌아가는지를 못 잰다.** 그래서 진짜로
    #    불러 본다 — 관문이 먼저 막으므로 그림은 한 장도 안 그린다(0원).
    import tempfile
    real_out, S90.OUT = S90.OUT, Path(tempfile.mkdtemp())
    hit = ""
    try:
        S90.stills(doc_of(cut(1, ["아버지"], two)))
    except S90.Short90Error as e:
        hit = str(e)
    except Exception as e:                                   # noqa: BLE001
        hit = f"[엉뚱한 고장] {type(e).__name__}: {e}"
    finally:
        S90.OUT = real_out
    ck("stills 를 **진짜로 불러도** 그리기 전에 멈춘다",
       "등장인물이 아닌 사람" in hit)
    ck("멈출 때 어느 컷인지 적어 준다 (엉뚱한 고장이 아니다)",
       "컷1" in hit and "엉뚱한 고장" not in hit)
    ok_hit = ""
    try:
        S90.OUT = Path(tempfile.mkdtemp())
        S90.stills(doc_of(cut(1, ["아버지", "장남"], two)))
    except S90.Short90Error as e:
        ok_hit = str(e)
    except Exception:                                        # noqa: BLE001
        ok_hit = ""
    finally:
        S90.OUT = real_out
    ck("둘 다 who 에 넣으면 이 관문은 안 막는다 (헛막지 않는다)",
       "등장인물이 아닌 사람" not in ok_hit)
    # ⚠️ 관문은 **돈을 쓰는 자리**에 있어야 한다. 규격 검사만 믿으면
    #    옛 대본이 옆문으로 들어온다 (실제로 세 번 그랬다).
    fn = (ROOT / "src" / "short90.py").read_text("utf-8")
    body = fn.split("def stills(")[1].split("\ndef ")[0]
    ck("stills 안에서 사람 수를 센다 (scene_extra)", "scene_extra(c)" in body)
    ck("넘치면 Short90Error 로 **그리기 전에** 멈춘다",
       "scene_extra" in body.split("raise Short90Error")[0])
    ck("멈출 때 어느 컷인지·몇 명인지 적어 준다",
       "화면 {h}명 vs 등장인물" in body)

    print("\n■ ⑥ 지금 있는 대본들이 이 규칙을 지키는가")
    # ⚠️ 이 대목만 **손님이 고치는 파일**을 본다. 그래서 여기서 걸려도
    #    검사를 실패시키지 않고 **알려만 준다** (대본은 손님 것이다).
    for f in sorted((ROOT / "data" / "series").glob("S*.json")):
        if ".story" in f.name or ".meta" in f.name or "broken" in f.name:
            continue
        try:
            d = json.loads(f.read_text("utf-8"))
        except Exception:                                    # noqa: BLE001
            continue
        hit = [b for b in ST.check(d)
               if "화면에 나오는 사람" in b or "나레이션 컷 화면" in b]
        print(f"  {'✅' if not hit else '⚠️ '} {f.stem}: "
              + ("등록 인물만 나온다" if not hit else f"{len(hit)}군데"))
        for h in hit:
            print(f"       {h[:90]}")

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 화면 인물: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 화면 인물: 등록 안 된 사람은 그리기 전에 막힌다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
