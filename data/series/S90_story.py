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
# ⭐⭐⭐ 2026-08-28 — 겹치는 나레이션 컷을 뺐다 (문장은 한 글자도 안 줄였다)
#    손님: "굳이 지금 정상적으로 멀쩡하게 있는 나레이션을 왜 빼?"
#    빼는 것은 **대사가 이미 말한 것**뿐이다. 목소리는 겹칠 수 없으므로 같은
#    사실을 나레이션과 대사가 두 번 말하면 그만큼 길어지기만 한다.
#      뺀 것 — 32억(변호사가 말한다) · 병원지분 특약(변호사) ·
#             보험 아홉 건(변호사) · "대답하지 못했습니다"(화면이 보여 준다)
#    20컷 → 16컷 · 139초 → 약 117초.
CUTS = [
    # ── 훅 ─────────────────────────────────────────────────────
    # ⭐⭐ 2026-08-31 손님: "갑자기 32억이 나와서 내용 이해가 안 돼."
    #    맞다. 남편이 **뭐 하는 사람인지** 한 줄도 없어서 32억이 어디서 난
    #    돈인지 알 길이 없었다 ('병원 지분' 은 76초에 가서야 처음 나온다).
    #    빚 6억이 왜 아내에게 오는지도 없었다.
    #    → 「병원을 하던」 「물려받은」 두 낱말로 둘 다 푼다. 그림은 그대로다.
    dict(n=1, sec=10.4, who=["아내"],
         turns=[("나레이션", "2017년 2월, 병원을 하던 남편이 죽었습니다. "
                            "아내가 물려받은 것은 빚 6억뿐이었습니다.")],
         scene="the wife sits at a bank counter and looks down at a bankbook lying "
               "open in front of her, her hand still resting on it"),

    # ⚠️⚠️ 2026-08-28 — 이 컷을 "변호사가 나중에 말하니 겹친다" 며 뺐다가
    #    되살렸다. 변호사 대사는 **66초 뒤**에 나온다 — 겹치는 게 아니라
    #    훅을 죽인 것이었다. 제목이 「32억」인데 훅에 32억이 없었다.
    dict(n=2, sec=8.2, who=["내연녀"],
         turns=[("나레이션", "남편이 평생 모은 재산 32억은, 죽기 전에 이미 "
                            "내연녀 앞으로 전부 넘어가 있었습니다.")],
         scene="the other woman stands alone in a quiet hospital corridor, half "
               "turned toward the camera, calm and unhurried"),

    # ── 1막 배신 ────────────────────────────────────────────────
    dict(n=3, sec=8.6, who=["아내", "남편", "내연녀"],
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
         # ⚠️ 8초 안에 두 사람이 다 말해야 한다 — 남편 쪽을 한 마디로 줄였다
         turns=[("아내", "이게 무슨 말 같지도 않은 소리야."),
                ("남편", "도장이나 찍어.")],
         scene="the living room, the wife stands still in the middle of the room "
               "while her husband picks his car key up off the low table"),

    # ── 2막 기각, 그리고 그날 ────────────────────────────────────
    # ⚠️⚠️ 2026-08-28 — 이 나레이션을 대사 "기각? 내가 왜 져." 로 대체했다가
    #    되살렸다. 그 대사는 **누가·언제·무엇이** 를 하나도 안 말한다.
    #    빼고 나니 관객이 35~43초 동안 왜 법원인지 모른 채로 있었다.
    dict(n=6, sec=5.2, who=["남편"],
         turns=[("나레이션", "이듬해 남편이 먼저 이혼 소송을 냈습니다.")],
         scene="a courthouse filing counter, the husband slides a thick bound "
               "document across the counter and lets go of it"),
    dict(n=7, sec=4, who=["남편"],
         turns=[("남편", "기각? 내가 왜 져.")],
         scene="a courthouse corridor, the husband stands by a tall window and "
               "crushes a folded sheet of paper in one hand"),
    dict(n=8, sec=4, who=["남편"],
         turns=[("남편", "좋아하지 마. 아직 안 끝났어.")],
         scene="the husband stops at the top of a stone staircase and looks back "
               "down over his shoulder"),
    dict(n=9, sec=9.7, who=["남편", "내연녀"],
         turns=[("나레이션", "기각 판결이 난 2013년 9월, 남편은 바로 그날 자기 재산을 "
                            "내연녀 앞으로 넘기기 시작했습니다.")],
         scene="a quiet cafe table, the husband slides a thin stack of documents "
               "across the table toward the other woman"),

    # ── 3막 죽음 ────────────────────────────────────────────────
    dict(n=10, sec=6.7, who=["아내"],
         turns=[("나레이션", "3년 뒤, 남편은 내연녀와 살던 아파트에서 떨어져 "
                            "죽었습니다.")],
         scene="before dawn, the wife sits on the edge of the bed holding a phone to "
               "her ear, the room dark except for one lamp"),
    dict(n=11, sec=6, who=["아내", "내연녀"],
         turns=[("내연녀", "인사만 드리고 갈게요. …나머지는 나중에 얘기해요.")],
         scene="the other woman steps into the funeral hall where the wife is "
               "keeping vigil, and stops just inside the doorway"),

    # ── 4막 32억 ────────────────────────────────────────────────
    dict(n=12, sec=6, who=["아내", "변호사"],
         turns=[("변호사", "병원 지분에 보험금에… 다 합쳐서 삼십이억입니다.")],
         scene="a law office, the attorney spreads several documents open on "
               "the desk while the wife leans in over them"),
    # ⭐⭐ 2026-08-31 손님: "갑자기 대출 이자가 나와서 내용 이해가 안 돼."
    #    맞다. 「매달 이천만 원」 은 앞에 한 번도 안 나온 숫자인데 아내 대사에서
    #    불쑥 튀어나왔다. 그 돈이 무엇인지 먼저 알려 준다 — 그래야 다음 컷이 꽂힌다.
    #    ⚠️ 사람이 없는 컷이다(서류 클로즈업). 16컷과 같은 꼴이라 낯선 사람이
    #       들어올 자리가 없다.
    dict(n=13, sec=7.2, who=[],
         turns=[("나레이션", "남편은 죽기 전 3년 동안, 내연녀에게 매달 "
                            "이천만 원을 보내고 있었습니다.")],
         scene="a bank statement lying on a desk under a lamp, one column of "
               "identical monthly transfers running down the page, the paper "
               "filling the frame"),
    dict(n=14, sec=8, who=["아내"],
         turns=[("아내", "우리 애 등록금이 없어서 휴학시켰는데… 매달 이천만 "
                        "원씩이요?")],
         scene="the wife cannot take her eyes off the papers in front of her, one "
               "hand flat on the desk"),

    # ⚠️⚠️ 2026-08-28 — 사무실에서 곧바로 법정으로 넘어가, 아내가 소송을
    #    냈다는 말이 한 번도 없었다.
    dict(n=15, sec=5.4, who=["아내", "변호사"],
         turns=[("나레이션", "아내는 그 돈을 되찾겠다며 소송을 냈습니다.")],
         scene="the wife signs the last page of a thick document at a desk while "
               "the attorney sets the next page in front of her"),

    # ── 5막 반전 ────────────────────────────────────────────────
    dict(n=16, sec=8, who=["아내", "내연녀"],
         # ⚠️ 8초 안에 두 사람이 다 말해야 한다 — 두 줄 다 한 마디씩 줄였다
         turns=[("내연녀", "전 몰라요. 찍으라니까 찍었어요."),
                ("아내", "몰라? 이 날짜는 뭔데.")],
         scene="a courtroom, the other woman stands at the table with her chin up "
               "while the wife holds a single document out across the table"),
    dict(n=17, sec=4, who=[],
         turns=[("아내", "이 날짜… 그 사람 재판 진 날이야.")],
         scene="a very close view of a printed document held in a hand, the paper "
               "filling the frame, everything soft except the paper"),
    dict(n=18, sec=6, who=["아내"],
         turns=[("아내", "몰랐다면서. 근데 어떻게 그날 바로 찍어?")],
         scene="the wife takes one step closer, still holding the document down at "
               "her side"),

    # ── 결말 ────────────────────────────────────────────────────
    dict(n=19, sec=9.5, who=[],
         # ⚠️ 2026-08-31 손님: "아이들이 아니라 딸 하나잖아."
         #    맞다. 13컷은 "우리 애", 19컷은 아내와 딸 둘뿐인데 여기만
         #    '아이들' 이라 이야기가 어긋났다.
         turns=[("나레이션", "2020년 7월, 법원은 내연녀에게 10억을 아내와 "
                            "딸에게 돌려주라고 판결했습니다.")],
         # ⚠️⚠️ 2026-08-31 손님: "전혀 다른 사람이 들어가 있음."
         #    여기는 사람이 없어야 하는 컷인데 낯선 남녀가 그려져 나왔다.
         #    까닭 둘 — ① '법원 앞 계단' 은 **사람이 지나다니는 자리**라
         #    그림 모델이 저절로 사람을 세운다. ② 바로 다음 19컷이 그 계단에
         #    아내와 딸을 세우는 컷이라 장면까지 겹쳤다.
         #    → 사람이 있을 수 없는 자리로 바꾼다 (빈 법정 안).
         scene="the inside of an empty courtroom in the morning, rows of empty wooden "
               "benches and the raised bench at the front, quiet light through tall "
               "windows"),
    dict(n=20, sec=8.2, who=["아내", "딸"],
         turns=[("나레이션", "아내가 떠안을 뻔했던 빚 6억도 갚지 않게 됐습니다. "
                            "실제로 있었던 사건입니다.")],
         scene="the wife and her grown daughter walk down the courthouse steps side "
               "by side in daylight"),
]

# ⭐⭐⭐ 연기 지시 (2026-08-31 손님 확정: "갈아탄다")
#
#   제미나이 목소리는 대사와 함께 **"어떻게 읽어라"** 를 말로 받는다.
#   자동 규칙(tts.MOOD)은 물음표만 보고 "날카롭게 되묻듯" 으로 읽는데,
#   컷4 "여보… 이 사람 누구야?" 는 날카로우면 안 되고 **떨려야** 한다.
#   스무 컷 스물세 줄뿐이라 **한 줄씩 손으로** 적는 것이 가능하고, 그게 제일 좋다.
#
#   ⚠️ 지시에 대사를 넣지 않는다. 지시는 '어떻게', 대사는 turns 가 진다.
#   ⚠️ 나레이션은 손님이 **빠른 쪽(②)** 을 고르셨다 — "쇼츠 속도에 맞춰".
#      느리게 읽히는 말('한 박자 쉬고' 같은)은 넣지 않는다.
#   ⚠️ 키는 (컷 번호, 줄 번호). 컷을 끼워 넣으면 번호가 밀리므로
#      tools/build_short90.py 가 **줄 수와 맞는지 검사**한다.

NARR = ("사건을 전하는 낮고 묵직한 목소리로, 쇼츠 속도에 맞춰 담담하고 또렷하게")

SAY = {
    (1, 0): NARR,
    (2, 0): NARR,
    (3, 0): NARR,
    (4, 0): "50대 여성이, 숨이 막혀 말이 잘 안 나오는 채로 아주 작게 떨면서",
    (4, 1): "50대 남성이, 귀찮다는 듯 무심하게 툭 던지듯",
    (5, 0): "50대 여성이, 믿기지 않아 목소리가 확 올라가며 분노가 터져 나오듯",
    (5, 1): "50대 남성이, 감정 없이 차갑게 끊어서 명령하듯",
    (6, 0): NARR,
    (7, 0): "50대 남성이, 어이없다는 듯 코웃음을 치고 곧 서늘하게 낮추어",
    (8, 0): "50대 남성이, 이를 악물고 화를 눌러 담아 낮지만 서슬 퍼렇게",
    (9, 0): NARR,
    (10, 0): NARR,
    (11, 0): "30대 여성이, 예의 바른 존댓말 뒤에 여유를 감추고 차분하게",
    (12, 0): "40대 남성이, 사무적으로 담담하게 숫자를 읽어 주듯",
    (13, 0): NARR,
    (14, 0): "50대 여성이, 울음을 삼키느라 목이 메어 끝을 떨면서 힘겹게",
    (15, 0): NARR,
    (16, 0): "30대 여성이, 억울한 척 또박또박 존댓말로 잡아떼듯",
    (16, 1): "50대 여성이, 낮게 몰아붙이며 되묻듯 날카롭게",
    (17, 0): "50대 여성이, 혼잣말처럼 아주 작게, 알아차린 순간의 서늘함으로",
    (18, 0): "50대 여성이, 확인 사살하듯 한 마디씩 눌러서 조용하고 단단하게",
    (19, 0): NARR,
    (20, 0): NARR,
}
