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


def _per_part(got, doc):
    """고른 컷을 편별로 센다 (제한을 켜 뒀을 때만 쓴다)."""
    per = {}
    for c in got:
        for p in doc["parts"]:
            if p["cuts"][0] <= c["n"] <= p["cuts"][1]:
                per[p["no"]] = per.get(p["no"], 0) + 1
    return per


def main():
    print("⭐ 대사 컷만 영상이 되는가 (값 0원)\n")
    doc = fake()
    got = S9.talk_cuts(doc)

    print("① 나레이션 컷은 한 컷도 안 산다")
    narr = [c["n"] for c in got if S9.is_narr(c)]
    ck("고른 것 가운데 나레이션이 없다", not narr, f"컷{narr} 이 나레이션이다")
    ck("고른 것이 있다 (아무것도 안 고르면 기능이 죽은 것이다)", got)

    print("\n② 대사 컷은 **하나도 빠짐없이** 영상으로 간다")
    # ⭐⭐⭐ 2026-09-10 손님: "대사 치는 부분에서 영상으로 제작된 거는
    #    일부에 불과하고." 맞는 지적이었다. 손님 설계는 "나레이션은 모두
    #    이미지, 대사 부분만 영상" 인데, 내가 값을 아끼려고 편마다 1컷으로
    #    막아 놨다 — S92 는 대사 14컷 중 4컷만 영상이 됐다.
    #    그 제한은 설계가 아니라 **내 임의**였다.
    # ⚠️ 이 시험은 "제한이 0(제한 없음)이다" 를 글로 보지 않는다.
    #    진짜 대본으로 **골라 보고**, 고를 수 있는 대사 컷이 남았는지 센다.
    talkable = [c for c in doc["cuts"]
                if not S9.is_narr(c) and len(S9.turns_of(c)) == 1
                and not any(w in S9.turns_of(c)[0][1] for w in S9.TALK_HOT)]
    inner = []
    for p in doc["parts"]:
        a, b = p["cuts"]
        mine = [c for c in talkable if a < c["n"] < b]
        inner += mine
    miss = sorted(c["n"] for c in inner if c not in got)
    ck("고를 수 있는 대사 컷이 하나도 안 남는다",
       not miss, f"컷{miss} 이 그림으로 남았다 — 편마다·인물마다 걸어 둔 "
                 f"수 제한이 살아 있다는 뜻이다")
    if S9.TALK_PER_PART or S9.TALK_PER_PERSON:
        over = [k for k, v in _per_part(got, doc).items()
                if S9.TALK_PER_PART and v > S9.TALK_PER_PART]
        ck(f"제한을 켜 두면 그 수를 지킨다 (편 {S9.TALK_PER_PART})",
           not over, f"{over}편이 넘겼다")

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
    # ⚠️⚠️ 2026-09-10 — 예전에는 여기서 `tot <= 3000` 을 걸었다. 그 숫자는
    #    "편마다 한 컷" 이던 시절의 값이고, **그 제한 자체가 손님 설계와
    #    어긋난 것**이었다. 뚜껑을 숫자로 박아 두면, 설계가 바뀔 때 검사가
    #    옛 설계를 지키는 편에 선다 (그래서 대사 14컷 중 4컷만 나갔다).
    #    → 값은 막지 않는다. 대신 **누르기 전에 진짜 값이 화면에 뜨는지**를
    #      본다. 손님 규칙은 "값을 숨기지 마라" 이지 "싸게 하라" 가 아니다.
    import talkplan                                          # noqa: E402
    pl = talkplan.plan(doc)
    ck("셈이 한 곳에서만 나온다 (short90 과 talkplan 이 같은 답)",
       [c["n"] for c in got] == pl["cuts"], f'{[c["n"] for c in got]} vs {pl["cuts"]}')
    js = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
    ck("화면이 스스로 안 센다 (doc.talk 을 읽는다)",
       "S90DOC.talk" in js and "706 * n" not in js,
       "화면이 따로 세면 언젠가 또 어긋난다")
    ck("화면이 컷 수와 값을 함께 적는다",
       "talkPlan().n" in js and "talkPlan().krw" in js)
    ck("값을 모르면 0원이라고 안 적는다",
       "stale" in js and "값을 아직 모릅니다" in js,
       "0원이라고 적으면 승인 자체가 거짓이 된다")
    bs = (ROOT / "tools" / "build_short90.py").read_text(encoding="utf-8")
    ck("대본을 지을 때 값을 찍어 둔다 (doc['talk'])",
       'doc["talk"] = talkplan.plan(doc)' in bs)
    print(f"   · 이 시험 대본이면 대사 {pl['n']}컷 · {pl['sec']}초 "
          f"· 약 {pl['krw']:,}원")
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
    # ⚠️ 2026-09-11 — 지문 셈을 talk_sig 한 곳으로 모았다. 그 안을 본다.
    _s9 = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
    sig_fn = (re.search(r"\ndef talk_sig\([\s\S]*?(?=\ndef )", _s9) or [""])[0]
    ck("지문에 그림과 모델을 넣는다 (그림이 바뀌면 다시 만든다)",
       "read_bytes" in sig_fn and "model" in sig_fn and "str(sec)" in sig_fn,
       "그림이나 모델이 바뀌어도 옛 영상을 그대로 쓴다")
    ck("이름이 밀려도 다시 안 산다 (salvage)", "salvage(" in fn)
    ck("안전필터에 걸리면 딱 한 번만 다시 산다",
       fn.count("veo.make_clip(") == 2)
    build = (re.search(r"\ndef build_part\([\s\S]*?(?=\ndef )", src) or [""])[0]
    ck("손으로 올린 영상이 기계 것보다 먼저다",
       "if not clip.exists():" in build and "talk_dir()" in build)
    ck("말 끝에서 잘라 자막이 뒤에 안 남는다",
       "def talk_trim(" in src and "talk_trim(" in fn)
    ck("안전필터 고위험 대사는 애초에 안 고른다", "TALK_HOT" in src)

    print("\n⑦ -2 **그림을 넣어** 영상을 만드는가 (image-to-video)")
    # ⭐⭐⭐ 2026-09-12 손님: **"이미지 제작하고 그 이미지 가지고 영상 만드는 거
    #    맞지? 그렇게 해야 된다."**
    #    맞다. 그런데 이 규칙을 지키는 검사는 **편 첫 장면(open_check)에만**
    #    있었고, 정작 지금 쓰는 **대사 영상에는 없었다.**
    #    글로만 새로 그리면 그 컷 그림과 얼굴이 달라진다 — 앞뒤 컷이 딴 사람이
    #    된다. 이 채널이 여러 번 겪은 사고다.
    ck("대사 영상을 **그 컷 그림에서** 만든다 (start=still)",
       fn.count("start=still") >= 2,
       "글로만 새로 그리면 앞뒤 컷의 얼굴이 달라진다")
    ck("안전필터로 다시 살 때도 그림을 넣는다",
       fn.count("veo.make_clip(") == fn.count("start=still"),
       "다시 살 때만 글로 그리면 그 컷만 딴 얼굴이 된다")
    ck("그림이 없으면 **아예 안 산다** (돈만 나가고 딴 얼굴이 나온다)",
       "그림이 없다 — 먼저 stills 를 돌린다" in fn)
    ck("지문에도 그 그림을 넣는다 (그림이 바뀌면 영상도 다시 만든다)",
       "read_bytes" in sig_fn)

    print("\n⑧ 조립이 **지금 대본에 맞는 영상만** 쓰는가")
    # ⭐⭐⭐ 2026-09-11 손님: "제대로 제작이 안된다."
    #    조립(build_part)이 talk/ 에 **파일이 있으면 그냥 썼다.** 그래서
    #    9월 10일에 만든 컷34 클립(자막 고치기 전 판 · 8.00초 통짜)이
    #    그대로 들어가 말이 끝난 뒤 3초를 가만히 서 있는 화면이 됐다.
    #    그 컷은 60초 벽 때문에 **덜어낸 컷**이라 계획에 아예 없었다.
    #    "파일이 있으면 쓴다" 는 판단은 예전에도 세 번 사고를 냈다.
    import tempfile                                          # noqa: E402
    src9 = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
    ck("조립이 지문을 본다 (talk_ok)", "talk_ok(c, t, still)" in src9,
       "파일이 있으면 쓰는 판단은 옛 영상을 그대로 끌고 온다")
    ck("안 맞으면 그림으로 간다고 알려 준다", "지금 대본과 안 맞는다" in src9)
    ck("만들 때와 조립할 때가 **같은 지문**을 쓴다", src9.count("talk_sig(") >= 2)
    ck("계획에 없는 옛 영상은 치운다", "이번 계획에 없다 — 치운다" in src9)
    ck("손으로 올린 영상은 건드리지 않는다",
       "reuse.by_hand(clip)" in src9 and "reuse.by_hand(f)" in src9)

    tmp = Path(tempfile.mkdtemp())
    still = tmp / "c05.png"
    still.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 20000)
    clip = tmp / "c05.mp4"
    clip.write_bytes(b"0" * 20000)
    cut = {"n": 5, "who": ["장남"], "say": ["담담하게"],
           "turns": [["장남", "형이 다 가져갔잖아"]],
           "scene": "장남 sits at a table", "still": "x", "veo": "y"}
    import reuse as R                                        # noqa: E402
    R.stamp(clip, "엉뚱한지문")
    ck("지문이 다른 영상은 안 쓴다", not S9.talk_ok(cut, clip, still)[0],
       "옛 영상이 그대로 들어간다")
    sec = S9.talk_sec(S9.turns_of(cut)[0][1])
    R.stamp(clip, S9.talk_sig(cut, sec, still, model="veo-test"))
    ck("지문이 같아도 모델이 다르면 안 쓴다",
       not S9.talk_ok(cut, clip, still)[0])
    R.stamp(clip, S9.talk_sig(cut, sec, still))
    ck("지문이 맞으면 쓴다 (괜히 다시 안 만든다)",
       S9.talk_ok(cut, clip, still)[0])

    camera()

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 대사 장면: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 대사 장면: 대사 컷만 · 편마다 하나 · 실패해도 그림으로 간다")
    return 0


def camera():
    """⭐⭐⭐ 2026-09-17 — 컷 성격에 따라 구도·카메라 무빙이 갈리는가.

    손님이 연출 규칙표를 주시며 반영을 지시하셨다. 그때까지 영상 프롬프트는
    **모든 컷이 똑같았다** ("waist up … static camera"). 우스운 것은, 정지
    그림에는 컷마다 다른 무빙이 이미 들어가고 있었다는 점이다 —
    그림이 영상보다 더 움직였다.
    ⚠️ 살아 있는 대본을 안 읽는다. 재려는 모양을 여기서 만든다.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "b90", ROOT / "tools" / "build_short90.py")
    B = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(B)

    print("\n⑨ 컷 성격에 따라 구도·카메라가 갈리는가")
    HALL = "an empty funeral hall with dim lamps"
    narr = {"n": 1, "who": [], "scene": HALL,
            "turns": [("나레이션", "그날의 일을 전해 드립니다")]}
    solo = {"n": 3, "who": ["딸"], "scene": f"딸 stands holding a paper in {HALL}",
            "turns": [("딸", "엄마, 저 두 사람은 누구야")]}
    # ⚠️ 받아치는 말 — 사람이 바뀌고 **같은 자리**다. 우리 대본에서 대립은
    #    '한 컷에 두 사람' 이 아니라 이렇게 컷을 나눠 나온다. 한 컷 안의
    #    사람 수만 보면 오버 더 숄더가 한 번도 안 걸린다(실제로 그랬다).
    reply = {"n": 4, "who": ["아내"],
             "scene": f"아내 sits with her hands folded in her lap in {HALL}",
             "turns": [("아내", "네 아버지가 밖에 두고 살던 사람이다")]}
    far = {"n": 9, "who": ["변호사"],
           "scene": "변호사 sits in a law office with a case file",
           "turns": [("변호사", "그 길부터 다투어 보시지요")]}

    s_narr = B.shot_of(narr)[0]
    s_solo = B.shot_of(solo, narr)[0]
    s_rep = B.shot_of(reply, solo)[0]
    s_far = B.shot_of(far, reply)[0]
    ck("나레이션 컷은 와이드다 (공간을 보여 준다)", "wide shot" in s_narr, s_narr[:90])
    ck("혼자 말하는 컷은 미디엄 + 느린 줌인이다",
       "medium shot" in s_solo and "zoom in" in s_solo, s_solo[:90])
    ck("받아치는 컷은 오버 더 숄더다 (대립 구도)",
       "over-the-shoulder" in s_rep, s_rep[:90])
    ck("자리가 바뀌면 받아치는 것으로 안 본다",
       "over-the-shoulder" not in s_far, s_far[:90])
    # ⚠️ 나레이션 컷에는 사람이라는 낱말이 한 번도 나오면 안 된다.
    #    그림 쪽은 2026-09-05 에 고쳤는데 **영상 쪽은 안 고쳐져 있었다** —
    #    빈 빈소 컷에 "the person kept in the middle" 이 들어가 있었다.
    three = "\n".join(B.shot_of(narr))
    ck("나레이션 컷 지문에 사람 낱말이 없다",
       not any(w in three for w in ("person", "people", "face", "faces")),
       three[:120])
    # 같은 무빙만 이어지면 지루하다 — 나레이션은 돌려 가며 쓴다
    moves = {B.shot_of(dict(narr, n=i))[0] for i in (1, 2, 3)}
    ck("나레이션 컷 무빙이 이웃끼리 다르다", len(moves) == 3, f"{len(moves)}가지")
    ck("같은 컷은 늘 같은 무빙이다 (다시 만들어도 안 달라진다)",
       B.shot_of(dict(narr, n=5))[0] == B.shot_of(dict(narr, n=5))[0])
    # 눈선은 세로 화면에서 위쪽 1/3 — 아래는 자막 띠가 덮는다
    ck("사람 컷은 눈선을 위쪽에 둔다", "eye line" in B.shot_of(solo, narr)[1])

    # ⚠️ 가져온 규칙표에서 **일부러 뺀 것**이 도로 들어오지 않았는지 본다.
    #    ⚠️ 소스 글자를 세면 **설명 주석까지** 걸린다(실제로 걸렸다).
    #       진짜로 모델에게 가는 것은 만들어진 지문이므로 그것을 본다.
    out = (B.veo_prompt(solo, narr) + "\n" + B.veo_prompt(narr)).lower()
    ck("--ar 를 안 보낸다 (미드저니 문법 · Veo 는 ratio 로 받는다)",
       "--ar" not in out, "글자로 읽혀 화면에 뜰 수 있다")
    ck("8k·4k 를 안 보낸다 (우리 금지어 — 안전필터에 걸린 이력)",
       not re.search(r"\b[48]k\b", out))
    ck("색은 지금 것을 지킨다 (teal and orange 로 안 간다)",
       "teal and orange" not in out and "warm neutral base" in out)


if __name__ == "__main__":
    raise SystemExit(main())
