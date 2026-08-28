# -*- coding: utf-8 -*-
"""⭐ 90초 한 편 — 「32억」 (2026-08-27 운영자 확정: "90초로 만들어")

왜 16화가 아니라 한 편인가
    16화는 한 화가 20초인데 사건이 하나뿐이라, 보는 사람이 "그래서 뭔데" 를
    16번 기다려야 했다. 90초 한 편은 같은 시간에 사건이 훨씬 많이 들어간다 —
    32억이 나오는 시점이 12화(4분 뒤)에서 **5초**로 당겨진다.

이 파일이 전부다
    화면 글(자막·나레이션)·길이·화면 묘사만 여기 적는다. 그림 프롬프트와
    영상 프롬프트는 tools/build_short90.py 가 짓는다.
    ⚠️ 사람 생김새·옷은 여기 안 적는다 — build_short90.py 의 PEOPLE 한 곳이다.
       두 곳에 적으면 한쪽만 고쳐서 사람이 컷마다 달라진다.

⭐⭐⭐ 대사 쓰는 법 — 네 줄 (2026-08-28 확정 · 어기면 다시 쓴다)
    ① 그 사람이 그 순간 **아는 것만** 말한다. 모르는 걸 아는 척하는 대사를 안 쓴다
    ② 설명하지 않고 **반응**만 한다. 숫자·날짜·사실은 나레이션이 지고 대사는 감정만
    ③ 말을 짧게 자르고 끝을 흐린다. 문장을 다 맺지 않는 것이 실제 사람 말이다
    ④ 사람마다 말버릇이 있다 — 아내는 되묻고, 남편은 끊어 던지고,
       내연녀는 예의 바르게 찌른다

대사 규칙 (tools/talk_check.py 가 검사한다)
    · 대사는 사실을 나르지 않는다 — 숫자·날짜는 **나레이션**이 진다
    · 토막내지 않는다. 한 사람이 두 문장 넘게 말하지 않는다
    · 구어체 — "네가" 가 아니라 "니가"
    · 높임말은 쌍마다 고정: 아내→내연녀 반말 · 내연녀→아내 존댓말 ·
      아내→변호사 존댓말 · 아내→남편 반말

날짜 (판결문 그대로 안 쓴다 — 일(日)은 아예 안 쓴다)
    기각 2013-08-09 → **2013년 9월** · 사망 2017-01-08 → **2017년 2월** ·
    판결 2020-06-24 → **2020년 7월** · 법원 이름은 안 밝힌다
"""

TITLE = "바람난 남편이 빼돌린 32억"
HOOK = "남편이 죽고, 남은 건 빚 6억이었습니다"
YT_TITLE = "남편이 죽고 남은 건 빚 6억, 재산 32억은 내연녀 앞으로 가 있었습니다"

# 한 컷 =
#   n     번호
#   kind  "나레이션" 또는 말하는 사람 이름
#   sec   최소 길이(초). 실제 길이는 만들어진 목소리 길이로 다시 잡는다
#   text  화면에 뜨는 글 = 소리로 읽는 글 (둘이 늘 같다)
#   scene 그림·영상에 넣을 화면 묘사 (영어)
#   who   그 화면에 나오는 사람들 (PEOPLE 의 이름)
# 한 컷 =
#   n      번호
#   sec    최소 길이(초)
#   turns  [(말하는 사람, 글)] — 사람이 여럿이면 주고받는다. "나레이션" 은 해설
#   scene  그림·영상에 넣을 화면 묘사 (영어)
#   who    그 화면에 나오는 사람들
#
# ⭐⭐⭐ 2026-08-28 손님: "대사하는 영상에 대사가 너무 적어서 시간이 남잖아."
#    맞다. Veo 는 4초가 최소인데 대사 한 줄이 2.3~2.9초라 1~2초씩 죽었다.
#    대사를 늘리는 대신 **두 컷을 하나로 합쳐 주고받게** 했다 — 죽는 시간이
#    사라지고, 진짜 대화가 되고, 만들 클립도 14개에서 10개로 줄었다.
#    그리고 나레이션이 지던 것 셋(기각·32억)을 사람 입으로 옮겨
#    대사 비중을 36% → 52% 로 올렸다.
CUTS = [
    # ── 훅 ─────────────────────────────────────────────────────
    dict(n=1, sec=5.6, who=["아내"],
         turns=[("나레이션", "2017년 2월, 남편이 죽었습니다. 그런데 남편 통장에 "
                            "남은 것은 빚 6억뿐이었습니다.")],
         scene="the wife sits at a bank counter and looks down at a bankbook lying "
               "open in front of her, her hand still resting on it"),
    dict(n=2, sec=4.8, who=["내연녀"],
         turns=[("나레이션", "남편의 재산 32억은 이미 내연녀 앞으로 전부 넘어가 "
                            "있었습니다.")],
         scene="the other woman stands alone in a quiet hospital corridor, half "
               "turned toward the camera, calm and unhurried"),

    # ── 1막 배신 ────────────────────────────────────────────────
    dict(n=3, sec=5.1, who=["아내", "남편", "내연녀"],
         turns=[("나레이션", "5년 전인 2012년 가을, 결혼 20년 된 남편이 낯선 여자를 "
                            "집으로 데려왔습니다.")],
         scene="the wife has just opened her front door and sees the woman standing "
               "behind her husband on the entry step"),
    dict(n=4, sec=8, who=["아내", "남편", "내연녀"],
         turns=[("아내", "여보… 이 사람 누구야?"),
                ("남편", "일 년 됐어. 이제 와서 뭘 물어.")],
         scene="just inside the apartment entrance in the evening, the wife stands "
               "frozen with a ladle still in one hand while her husband steps past "
               "her without stopping"),
    dict(n=5, sec=8, who=["아내", "남편"],
         turns=[("아내", "일 년…? 그럼 내가 아침마다 밥 차릴 때도."),
                ("남편", "도장이나 찍어. 애들한텐 니가 말하고.")],
         scene="the living room, the wife stands still in the middle of the room "
               "while her husband picks his car key up off the low table"),

    # ── 2막 기각, 그리고 그날 ────────────────────────────────────
    dict(n=6, sec=4, who=["남편"],
         turns=[("남편", "…기각? 이게 기각이라고?")],
         scene="a courthouse corridor, the husband stands by a tall window and "
               "crushes a folded sheet of paper in one hand"),
    dict(n=7, sec=4, who=["남편"],
         turns=[("남편", "좋아하지 마. 아직 안 끝났어.")],
         scene="the husband stops at the top of a stone staircase and looks back "
               "down over his shoulder"),
    dict(n=8, sec=6.3, who=["남편", "내연녀"],
         turns=[("나레이션", "그 판결이 난 2013년 9월, 남편은 바로 그날 자기 재산을 "
                            "내연녀 앞으로 넘기기 시작했습니다.")],
         scene="a quiet cafe table, the husband slides a thin stack of documents "
               "across the table toward the other woman"),
    dict(n=9, sec=5.5, who=["내연녀"],
         turns=[("나레이션", "죽으면 병원 지분 10억을 내연녀가 받도록, 계약서에 "
                            "특약까지 넣었습니다.")],
         scene="a close view of a woman's hand pressing a red seal onto the bottom "
               "of a document lying on a table, the paper filling most of the frame"),
    dict(n=10, sec=4.5, who=[],
         turns=[("나레이션", "사망보험 아홉 건도 받을 사람을 전부 내연녀로 "
                            "바꿨습니다.")],
         scene="a desk with a thick stack of blank insurance policy folders squared "
               "up under a desk lamp, nobody in frame"),

    # ── 3막 죽음 ────────────────────────────────────────────────
    dict(n=11, sec=5.0, who=["아내"],
         turns=[("나레이션", "3년 뒤, 남편은 내연녀와 살던 아파트에서 떨어져 "
                            "죽었습니다.")],
         scene="before dawn, the wife sits on the edge of the bed holding a phone to "
               "her ear, the room dark except for one lamp"),
    dict(n=12, sec=4, who=["아내", "내연녀"],
         turns=[("내연녀", "인사만 드리고 갈게요. …나머지는 나중에 얘기해요.")],
         scene="the other woman steps into the funeral hall where the wife is "
               "keeping vigil, and stops just inside the doorway"),

    # ── 4막 32억 ────────────────────────────────────────────────
    dict(n=13, sec=6, who=["아내", "변호사"],
         turns=[("변호사", "병원 지분에 보험금에… 다 합쳐서 삼십이억입니다.")],
         scene="a lawyer's office, the lawyer spreads several documents open on the "
               "desk while the wife leans in over them"),
    dict(n=14, sec=6, who=["아내"],
         turns=[("아내", "우리 애 등록금이 없어서 휴학시켰는데… 매달 이천만 "
                        "원씩이요?")],
         scene="the wife cannot take her eyes off the papers in front of her, one "
               "hand flat on the desk"),

    # ── 5막 반전 ────────────────────────────────────────────────
    dict(n=15, sec=8, who=["아내", "내연녀"],
         turns=[("내연녀", "전 몰라요. 찍으라니까 찍은 거예요."),
                ("아내", "몰라? 그럼 이 날짜는 뭔데.")],
         scene="a courtroom, the other woman stands at the table with her chin up "
               "while the wife holds a single document out across the table"),
    dict(n=16, sec=4, who=[],
         turns=[("아내", "이 날짜… 그 사람 재판 진 날이야.")],
         scene="a very close view of a printed document held in a hand, the paper "
               "filling the frame, everything soft except the paper"),
    dict(n=17, sec=4, who=["아내"],
         turns=[("아내", "몰랐다면서. 근데 어떻게 그날 바로 찍어?")],
         scene="the wife takes one step closer, still holding the document down at "
               "her side"),
    dict(n=18, sec=2.8, who=["내연녀"],
         turns=[("나레이션", "내연녀는 대답하지 못했습니다.")],
         scene="the other woman lowers her eyes and looks away to one side"),

    # ── 결말 ────────────────────────────────────────────────────
    dict(n=19, sec=5.8, who=[],
         turns=[("나레이션", "2020년 7월, 법원은 내연녀에게 10억을 아내와 "
                            "아이들에게 돌려주라고 판결했습니다.")],
         scene="the wide stone front steps of a courthouse in daylight, empty, seen "
               "from below"),
    dict(n=20, sec=5.8, who=["아내", "딸"],
         turns=[("나레이션", "아내가 떠안을 뻔했던 빚 6억도 갚지 않게 됐습니다. "
                            "실제로 있었던 사건입니다.")],
         scene="the wife and her grown daughter walk down the courthouse steps side "
               "by side in daylight"),
]
