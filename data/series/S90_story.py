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
CUTS = [
    # ── 훅 ─────────────────────────────────────────────────────
    dict(n=1, kind="나레이션", sec=5.6, who=["아내"],
         text="2017년 2월, 남편이 죽었습니다. 그런데 남편 통장에 남은 것은 빚 6억뿐이었습니다.",
         scene="the wife sits at a bank counter and looks down at a bankbook lying open "
               "in front of her, her hand still resting on it"),
    dict(n=2, kind="나레이션", sec=4.8, who=["내연녀"],
         text="남편의 재산 32억은 이미 내연녀 앞으로 전부 넘어가 있었습니다.",
         scene="the other woman stands alone in a quiet hospital corridor, half turned "
               "toward the camera, calm and unhurried"),

    # ── 1막 배신 ────────────────────────────────────────────────
    dict(n=3, kind="나레이션", sec=5.1, who=["아내", "남편", "내연녀"],
         text="5년 전인 2012년 가을, 결혼 20년 된 남편이 낯선 여자를 집으로 데려왔습니다.",
         scene="the wife has just opened her front door and sees the woman standing "
               "behind her husband on the entry step"),
    dict(n=4, kind="아내", sec=3.1, who=["아내", "남편", "내연녀"],
         # ⚠️ 손님: "어 손님 오셨어? 이게 말이 되는 대사야?" — 맞다. 아내는 그 여자가
         #    누군지 모른다. 모르는 걸 아는 척하는 대사는 안 쓴다.
         text="여보… 이 사람 누구야?",
         scene="the wife stops half way through taking off one shoe and straightens up "
               "without looking away from the woman"),
    dict(n=5, kind="남편", sec=2.6, who=["남편", "내연녀"],
         text="일 년 됐어. 이제 와서 뭘 물어.",
         scene="the husband gestures the woman toward the sofa and she sits down and "
               "crosses her legs"),
    dict(n=6, kind="아내", sec=2.9, who=["아내"],
         text="일 년…? 그럼 내가 아침마다 밥 차릴 때도.",
         scene="the wife stands still in the middle of the living room, jaw tight, "
               "eyes fixed on something just off camera"),
    dict(n=7, kind="남편", sec=3.1, who=["남편"],
         text="도장이나 찍어. 애들한텐 니가 말하고.",
         scene="the husband picks his car key up off the low table and turns toward "
               "the door without looking back"),

    # ── 2막 기각, 그리고 그날 ────────────────────────────────────
    dict(n=8, kind="나레이션", sec=5.8, who=["남편"],
         text="이듬해 남편은 이혼 소송을 냈지만, 2013년 9월 법원은 남편의 청구를 기각했습니다.",
         scene="a courthouse corridor, the husband stands by a tall window and crushes "
               "a folded sheet of paper in one hand"),
    dict(n=9, kind="남편", sec=3.8, who=["남편"],
         text="좋아하지 마. 아직 안 끝났어.",
         scene="the husband stops at the top of a stone staircase and looks back down "
               "over his shoulder"),
    dict(n=10, kind="나레이션", sec=6.3, who=["남편", "내연녀"],
         text="그리고 판결이 난 바로 그날, 남편은 자기 재산을 내연녀 앞으로 넘기기 시작했습니다.",
         scene="a quiet cafe table, the husband slides a thin stack of documents across "
               "the table toward the other woman"),
    dict(n=11, kind="나레이션", sec=7.3, who=["내연녀"],
         text="남편은 자기가 죽으면 병원 지분 10억을 아내가 아니라 내연녀가 받도록 "
              "계약서에 특약을 넣었습니다.",
         # ⚠️ 'her sleeve' 처럼 사람 옷을 적으면 기준 그림과 싸운다 (wear_bait)
         scene="a close view of a woman's hand pressing a red seal onto the bottom "
               "of a document lying on a table, the paper filling most of the frame"),
    dict(n=12, kind="나레이션", sec=5.4, who=[],
         text="사망보험 아홉 건도 남편은 받을 사람을 전부 내연녀로 바꿔 놓았습니다.",
         scene="a desk with a thick stack of blank insurance policy folders squared up "
               "under a desk lamp, nobody in frame"),

    # ── 3막 죽음 ────────────────────────────────────────────────
    dict(n=13, kind="나레이션", sec=5.8, who=["아내"],
         text="그로부터 3년 뒤인 2017년 2월, 남편은 내연녀와 살던 아파트에서 떨어져 죽었습니다.",
         scene="before dawn, the wife sits on the edge of the bed holding a phone to "
               "her ear, the room dark except for one lamp"),
    dict(n=14, kind="내연녀", sec=3.3, who=["아내", "내연녀"],
         # ⚠️ 상주는 아내다. 내연녀는 찾아온 쪽이라 "우세요" 가 아니다 (2026-08-26 고침)
         text="인사만 드리고 갈게요. …나머지는 나중에 얘기해요.",
         scene="the other woman steps into the funeral hall where the wife is keeping "
               "vigil, and stops just inside the doorway"),

    # ── 4막 32억 ────────────────────────────────────────────────
    dict(n=15, kind="나레이션", sec=7.4, who=["아내", "변호사"],
         text="아내가 변호사와 함께 찾아낸 돈은 병원 지분 10억, 사망보험금 13억, "
              "현금과 수표로 9억, 다 합쳐 32억이었습니다.",
         scene="a lawyer's office, the lawyer spreads several documents open on the "
               "desk while the wife leans in over them"),
    dict(n=16, kind="아내", sec=5.6, who=["아내"],
         text="우리 애 등록금이 없어서 휴학시켰는데… 매달 이천만 원씩이요?",
         scene="the wife cannot take her eyes off the papers in front of her, one hand "
               "flat on the desk"),

    # ── 5막 반전 ────────────────────────────────────────────────
    dict(n=17, kind="내연녀", sec=4.3, who=["내연녀"],
         text="전 몰라요. 찍으라니까 찍은 거예요.",
         scene="a courtroom, the other woman stands at the table and lifts her chin, "
               "looking straight ahead"),
    dict(n=18, kind="아내", sec=2.3, who=["아내"],
         text="몰라? 그럼 이 날짜는 뭔데.",
         scene="the wife holds a single document out at arm's length across the "
               "courtroom table"),
    dict(n=19, kind="아내", sec=3.6, who=[],
         text="이 날짜… 그 사람 재판 진 날이야.",
         scene="a very close view of a printed document held in a hand, the paper "
               "filling the frame, everything soft except the paper"),
    dict(n=20, kind="아내", sec=3.4, who=["아내"],
         text="몰랐다면서. 근데 어떻게 그날 바로 찍어?",
         scene="the wife takes one step closer, still holding the document down at "
               "her side"),
    dict(n=21, kind="나레이션", sec=2.8, who=["내연녀"],
         text="내연녀는 대답하지 못했습니다.",
         scene="the other woman lowers her eyes and looks away to one side"),

    # ── 결말 ────────────────────────────────────────────────────
    dict(n=22, kind="나레이션", sec=5.8, who=[],
         text="2020년 7월, 법원은 내연녀에게 10억을 아내와 아이들에게 돌려주라고 판결했습니다.",
         scene="the wide stone front steps of a courthouse in daylight, empty, seen "
               "from below"),
    dict(n=23, kind="나레이션", sec=5.8, who=["아내", "딸"],
         text="아내가 떠안을 뻔했던 빚 6억도 갚지 않게 됐습니다. 실제로 있었던 사건입니다.",
         scene="the wife and her grown daughter walk down the courthouse steps side by "
               "side in daylight"),
]
