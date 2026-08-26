# -*- coding: utf-8 -*-
"""S001 — 16화 이야기 데이터 (사건 장부 + 대사). 사람이 읽고 고치는 파일.

⭐⭐⭐ 2026-08-25 전면 재설계 (운영자)
    "자극성만 신경쓰니까 씬 간 연결성과 스토리 전개가 제대로 이루어지지 않고
     있어. 너무 어색해. 이건 광고가 아니고 드라마라는걸 다시 한번 생각해."

    맞는 말이었다. 옛 대본을 세어 보니 —
      · 5~16화, **12화 연속**으로 '아내와 그 여자가 어딘가에서 마주쳐 말싸움'
      · 은행 앞·보험사 앞·법무사 앞·법원 앞 — 그 여자가 **거기 있을 이유가 없다**
      · "보험사에도 가보시든가요" — **원수가 다음 단서를 친절히 알려준다** (4곳)
      · 16화 중 14화가 물음표로 끝나는데 그중 4곳은 다음 화가 그 질문을 무시
      · 첫 대사부터 끝까지 세기가 100 — 조용한 화가 **0개**
      · 아이들은 네 번 언급되고 화면에는 **한 번도** 안 나옴

    광고는 3초마다 결정타가 필요하다. 드라마는 **약하게 시작해서 어긋나고
    그래서 무슨 일이 벌어지는가**를 본다. 다섯 가지로 다시 짰다.
      ① 한 화 = 한 사건. 3컷은 **시작 → 어긋남 → 결과**
      ② 이번 화의 `leaves` 가 다음 화의 `because` 와 **글자 그대로 같아야** 한다
         (story_check 가 검사한다 — 이것이 '씬 간 연결'의 뼈대다)
      ③ 정보는 원수가 아니라 **세상**에서 온다 (전화·창구·변호사·우편)
      ④ 조용한 화(`quiet`)를 넣는다 — 다음 폭발이 세진다
      ⑤ 컷당 대사 4개 → **2~3개**. 사람은 10초에 네 마디를 안 한다
"""

# ⭐ 금액 장부 — 실제 판결문 금액을 조금 늘려 백만원 단위 절사 (운영자 지시)
LEDGER = {
    "병원지분": "십억",       # 판결문 9억 8,445만
    "보험금": "십삼억",       # 판결문 12억 8,004만 (보험 9건)
    "현금": "구억",           # 판결문 8억 5,347만
    "빚": "육억",             # 판결문 5억 7,497만
    "합계": "삼십이억",       # 31억 1,797만
    "판결": "십억",           # 9억 4,198만 반환
    "보험료": "이천만 원",     # 매달
}

# ⚠️ 2026-08-25 — 옷차림 표(WEARS)를 없앴다. 옷은 **루미나 기준 사진**이
#    잡는 몫이고, 컷 프롬프트에 또 적으면 레퍼런스와 싸워서 오히려 흔들린다.
#    (운영자: "우리 옷에 관한 정보는 안 넣기로 규칙에 정했잖아?!")
VOICES = {
    "Wife": ("Wife — a warm mid-range woman's voice in her fifties, native Korean "
             "speaker, weary and a little breathy, trails off at the end of a sentence"),
    "Husband": ("Husband — a low, slightly gravelly man's voice in his fifties, native "
                "Korean speaker, clipped and impatient, drops in volume at the end"),
    "Other woman": ("Other woman — a clear woman's voice in her forties, native Korean "
                    "speaker, cool and unhurried, with a small lilt at the end"),
    "Daughter": ("Daughter — a light young woman's voice in her early twenties, native "
                 "Korean speaker, careful and a little flat, keeps the end of a "
                 "sentence low"),
    "Lawyer": ("Lawyer — an even man's voice in his forties, native Korean speaker, "
               "measured and unhurried, keeps the same level all the way through"),
}

W, H, O, D, L = "Wife", "Husband", "Other woman", "Daughter", "Lawyer"

# 화면에 나오는 차례 (샷·이름표 순서). 새 사람을 넣으면 여기에도 넣는다.
ORDER = [W, H, O, D, L]

# ⭐⭐ 새로 들어온 두 사람 (2026-08-25 운영자가 고른 안 — "딸·변호사 2명 추가").
#    까닭 — ① 딸이 있어야 **조용한 화**가 가능하다 (소리 안 지르고 더 아픈 화)
#          ② 변호사가 있어야 아내가 금액을 **스스로 발견**한다.
#             옛 대본은 그 여자가 "보험사에도 가보시든가요" 하고 알려 줬다.
#    ⚠️ 생김새 글은 여기서만 적는다. 컷 프롬프트에는 절대 안 들어간다.
# ⚠️ 기준 그림 프롬프트(flow_sheet)·설명(flow_desc)은 **여기서 안 쓴다.**
#    src/charsheet.py 가 짓는다 — 배경·자세·화면잡기·빛·하지 말 것까지 한 벌로
#    들어가야 하고, 그 문구가 바뀌면 다섯 사람이 **같이** 바뀌어야 한다.
#    손으로 베껴 두면 한쪽만 낡아서 사람마다 다른 그림체가 나온다.
NEW_CHARS = [
    {
        "name": "딸",
        "flow_prompt": ("Korean woman, 22 years old, round face, calm dark eyes, "
                        "straight black hair tied back low. Photorealistic, natural "
                        "skin texture, grounded everyday Korean realism."),
        "face_tag": "22, round face, straight black hair tied back low",
        "role_en": "the daughter",
        "voice": ("a light young woman's voice in her early twenties, native Korean "
                  "speaker, careful and a little flat, keeps the end of a sentence low"),
    },
    {
        "name": "변호사",
        "flow_prompt": ("Korean man, 45 years old, long face, steady eyes, short black "
                        "hair combed back. Photorealistic, natural skin texture, "
                        "grounded everyday Korean realism."),
        "face_tag": "45, long face, short black hair combed back",
        "role_en": "the lawyer",
        "voice": ("an even man's voice in his forties, native Korean speaker, measured "
                  "and unhurried, keeps the same level all the way through"),
    },
]

# 화별 이야기.
#   when     화면에 띄울 때 (해가 바뀌면 시청자가 알아야 한다)
#   because  이 화가 벌어지는 까닭 — **앞 화의 leaves 와 글자 그대로 같아야** 한다
#   leaves   이 화가 남기는 것 → 다음 화의 because 가 된다
#   reveal   이 화에서 **처음** 밝혀지는 것 (사건 장부)
#   must     그 폭로가 대사에 실제로 있는지 검사할 낱말
#   irony    아내가 없는 화 (시청자만 먼저 안다) — 누설 검사에서 뺀다
#   quiet    소리 안 지르는 화 — 세기를 낮춰 다음 폭발을 세게 한다
#   shots    컷 자리별 샷 크기 (two=두 사람 / ots=어깨너머 / close=클로즈업)
#   extras   말은 안 해도 그 컷 화면에 서 있는 사람
#   cuts     [장소키, 움직임, [(말한 사람, 대사)...]]
EPS = [
 dict(no=1, title="낯선 여자", when="2012년 가을", act=1,
      mood="믿기지 않음", words=["numb", "shaken", "breaking"],
      hook="남편이 *낯선 여자*를 데리고 왔다",
      yt_title="남편이 낯선 여자를 집에 데리고 들어왔습니다",
      recap="", because="",
      leaves="남편은 아이들한테는 아내가 말하라고 했다",
      reveal="남편이 내연녀를 집에 데려와 이혼을 요구한다",
      must=["이혼하자"],
      shots=["two", "close", "ots"],
      extras={1: [O], 2: [H, O]},
      cuts=[
        ("현관", "the wife turns from the doorway with a spoon still in one hand as her "
                 "husband steps in with a woman close behind him",
         [(W, "왜 이렇게 늦었어. 밥 다 식었는데."),
          (W, "…손님이셔?"),
          (H, "들어와. 어차피 알 사람이야.")]),
        ("거실", "the wife stands still in the middle of the living room while the woman "
                 "sits down on the sofa behind her and the husband waits by the door",
         [(W, "저기요. 지금 거기 앉으시는 거예요?"),
          (W, "여보, 이 사람 누구냐고 물었잖아.")]),
        ("거실", "the husband takes his car key from the low table and turns toward the "
                 "door while his wife stays where she is",
         [(H, "일 년 됐어. 숨길 생각 없어."),
          (H, "이혼하자. 애들한텐 네가 말하고."),
          (W, "…애들한테? 그걸 왜 내가 말해?")]),
      ]),
 dict(no=2, title="딸이 먼저 뜯었다", when="2012년 겨울", act=1,
      mood="삼키는 마음", words=["quiet", "careful", "holding"],
      hook="이혼 소장을 *딸이 먼저* 뜯었다",
      yt_title="이혼 소장을 딸이 먼저 뜯어 봤습니다",
      recap="남편이 내연녀를 집에 데려왔다",
      because="남편은 아이들한테는 아내가 말하라고 했다",
      leaves="아내는 딸에게 알아서 하겠다고 말했다",
      reveal="남편이 이혼 소송을 냈고 딸이 먼저 알게 된다",
      must=["소송"], quiet=True,
      shots=["ots", "two", "close"],
      extras={3: [D]},
      cuts=[
        ("현관", "the daughter stands just inside the door and holds out a torn-open "
                 "envelope toward her mother, who has stopped with one shoe half off",
         [(D, "엄마, 이거 아빠가 보낸 거야?"),
          (W, "…이리 줘."),
          (D, "아빠 이름이 있던데.")]),
        ("부엌", "the mother sets a bowl down in front of her daughter and sits across "
                 "the small table, both hands flat on the tabletop",
         [(D, "이혼 소송이라고 하던데."),
          (W, "어른들 일이야. 밥이나 먹어."),
          (D, "엄마, 울었어?")]),
        ("부엌", "the mother turns back to the counter and keeps her hands moving over "
                 "the cutting board while her daughter stays sitting behind her",
         [(W, "괜찮아. 양파 썰어서 그래."),
          (W, "너는 아무 걱정 하지 마."),
          (W, "…엄마가 알아서 할게.")]),
      ]),
 dict(no=3, title="기각", when="2013년 8월", act=1,
      mood="억눌린 분노", words=["tight", "hard", "furious"],
      hook="바람피운 쪽이 걸었다가 *기각당했다*",
      yt_title="바람피운 남편이 낸 이혼 소송, 법원이 기각했습니다",
      recap="딸이 소장을 먼저 뜯어 보았다",
      because="아내는 딸에게 알아서 하겠다고 말했다",
      leaves="남편은 방법이 없는 건 아니라고 했다",
      reveal="법원이 남편의 이혼 청구를 기각한다",
      must=["기각"],
      shots=["two", "ots", "close"],
      extras={3: [W]},
      cuts=[
        ("법원복도", "the husband steps in front of his wife to block the corridor, one "
                     "hand closed tight at his side",
         [(H, "도장 하나 찍는 게 그렇게 어려워?"),
          (W, "방금 판사님 말 못 들었어?"),
          (H, "그깟 종이 한 장이 뭐라고.")]),
        ("법원복도", "the wife turns her back and presses one palm flat on the wall while "
                     "the husband stays two steps behind her",
         [(W, "기각. 당신 이혼 청구 기각이야."),
          (H, "들킨 게 재수 없었을 뿐이야."),
          (W, "잘못한 쪽에 책임이 있대.")]),
        ("법원복도", "the husband stops at the top of the stairs and looks back down the "
                     "corridor, the wife still standing where he left her",
         [(H, "재산 때문에 이러는 거지?"),
          (H, "두고 봐. 방법이 없는 건 아니니까…")]),
      ]),
 dict(no=4, title="짐을 싸는 남편", when="2013년 가을", act=1,
      mood="말라붙은 정", words=["flat", "cold", "final"],
      hook="남편이 *짐을 싸서* 나갔다",
      yt_title="기각당한 남편이 짐을 싸서 집을 나갔습니다",
      recap="남편의 이혼 청구가 기각됐다",
      because="남편은 방법이 없는 건 아니라고 했다",
      leaves="남편이 집을 나가고 아내와 딸만 남았다",
      reveal="남편이 집을 나가 아내와 딸만 남는다",
      must=["나갈게"],
      shots=["ots", "two", "close"],
      extras={3: [D]},
      cuts=[
        ("거실", "the husband pulls a travel bag out from beside the sofa and starts "
                 "filling it while his wife stands in the middle of the room",
         [(H, "짐 좀 챙길게. 오래 안 걸려."),
          (W, "재판에서 졌잖아. 어딜 가."),
          (H, "판결은 판결이고, 나는 나갈게.")]),
        ("현관", "the husband sets the bag down on the entry step and reaches for the "
                 "door handle while his wife stops in the doorway behind him",
         [(W, "애들은 어쩌고. 아빠가 이러면 어떡해."),
          (H, "생활비는 보낼게."),
          (W, "돈 얘기가 아니잖아.")]),
        ("현관", "the wife stays facing the closed front door with one hand still on "
                 "the handle, her daughter waiting behind her",
         [(W, "괜찮아. 엄마 안 울어."),
          (W, "저 사람 곧 돌아올 거야."),
          (W, "…돌아오겠지. 그렇지?")]),
      ]),
 dict(no=5, title="모르는 번호", when="2014년 봄", act=1,
      mood="서늘한 예감", words=["puzzled", "uneasy", "alert"],
      hook="모르는 번호가 *남편 서류*를 물었다",
      yt_title="모르는 번호가 남편 서류를 확인해 달라고 했습니다",
      recap="남편이 짐을 싸서 집을 나갔다",
      because="남편이 집을 나가고 아내와 딸만 남았다",
      leaves="아내는 전화를 받았지만 아무것도 알아내지 못했다",
      reveal="아내가 남편 서류를 확인하는 전화를 받는다",
      must=["받는 사람"],
      shots=["close", "two", "ots"],
      extras={1: [D]},
      cuts=[
        ("거실", "the wife stops halfway across the living room with the phone against "
                 "her ear and one hand going still on the back of a chair",
         [(W, "네, 제가 그 사람 아내인데요."),
          (W, "받는 사람을 바꿨다고요? 무슨 말씀이세요.")]),
        ("거실", "the daughter comes in from the hallway and stops beside her mother, "
                 "who lowers the phone to her chest",
         [(D, "엄마, 누구야?"),
          (W, "몰라. 보험회사라는데 잘못 걸었대."),
          (D, "잘못 걸었는데 왜 그렇게 오래 통화해.")]),
        ("거실", "the wife sets the phone face down on the table and keeps her hand on "
                 "it while her daughter waits in the doorway",
         [(W, "아니야. 그냥 잘못 온 전화야."),
          (D, "아빠한테 물어보라니까."),
          (W, "…근데 왜 내 이름을 알았을까?")]),
      ]),
 dict(no=6, title="새벽 전화", when="2017년 1월", act=2,
      mood="무너짐", words=["numb", "shaken", "hollow"],
      hook="새벽 전화 *남편분이 떨어지셨습니다*",
      yt_title="새벽에 전화가 왔습니다. 남편이 떨어졌다고",
      recap="모르는 번호가 남편 서류를 물었다",
      because="아내는 전화를 받았지만 아무것도 알아내지 못했다",
      leaves="아내는 남편이 내연녀 집에서 떨어져 죽은 것을 알았다",
      reveal="남편이 내연녀와 살던 집에서 떨어져 죽는다",
      must=["떨어졌"],
      shots=["close", "two", "ots"],
      cuts=[
        ("거실", "the wife sits up on the edge of the sofa with the phone at her ear, "
                 "one hand gripping the armrest",
         [(W, "여보세요… 네, 제가 아내인데요."),
          (W, "네? 어디서 떨어졌다고요?")]),
        ("병원복도밤", "the wife comes down the corridor and stops in front of the woman, "
                       "who rises from one of the steel chairs",
         [(W, "그이가 왜 거기서 떨어져요."),
          (O, "혼자 나갔어요. 나도 자다가 알았고."),
          (W, "왜 당신 집이야. 왜 하필 거기야.")]),
        ("병원복도밤", "the woman takes her bag from the chair and steps around the wife "
                       "toward the exit, then stops",
         [(O, "저도 놀랐어요. 그만 좀 하세요."),
          (W, "그이가 왜 당신 집에서…"),
          (O, "장례비는 그쪽이 내시는 거죠?")]),
      ]),
 dict(no=7, title="장례식장", when="2017년 1월", act=2,
      mood="치미는 모욕", words=["tight", "hard", "cold"],
      hook="장례식장에 온 내연녀 *다 내 거예요*",
      yt_title="장례식장에 내연녀가 찾아왔습니다",
      recap="남편은 내연녀 집에서 떨어져 죽었다",
      because="아내는 남편이 내연녀 집에서 떨어져 죽은 것을 알았다",
      leaves="내연녀가 남긴 건 전부 자기 것이라고 했다",
      reveal="내연녀가 남편이 남긴 것이 전부 자기 것이라고 말한다",
      must=["다 내 거"],
      shots=["two", "close", "ots"],
      extras={2: [O]},
      cuts=[
        ("장례식장", "the wife comes out through the sliding door and stops the woman in "
                     "the middle of the reception floor",
         [(W, "여기가 어디라고 와."),
          (O, "마지막 인사는 하고 가야죠."),
          (W, "당장 내 눈앞에서 꺼져.")]),
        ("장례식장", "the wife stands very still in the middle of the floor while the "
                     "woman waits a few steps behind her",
         [(W, "이십 년이야. 이십 년을 같이 살았어."),
          (W, "그 사람 밥은 내가 차렸어.")]),
        ("장례식장", "the woman turns at the doorway with her bag on one shoulder while "
                     "the wife stays where she is",
         [(O, "그이가 남긴 건 다 내 거예요."),
          (W, "내 남편 물건에 네가 왜 손을 대."),
          (O, "곧 알게 되실 텐데요…")]),
      ]),
 dict(no=8, title="통장을 열었다", when="2017년 2월", act=2,
      mood="절박함", words=["low", "tight", "breaking"],
      hook="통장을 열자 남은 건 *빚 육억*뿐",
      yt_title="남편 통장을 열어 보니 빚만 6억 남아 있었습니다",
      recap="내연녀가 남긴 건 전부 자기 것이라 했다",
      because="내연녀가 남긴 건 전부 자기 것이라고 했다",
      leaves="아내는 남편 통장에 빚만 남은 것을 보았다",
      reveal="남편의 통장에 남은 것은 빚 육억뿐이다",
      must=["빚 육억"], quiet=True,
      shots=["ots", "two", "close"],
      extras={1: [D], 3: [D]},
      cuts=[
        ("은행창구", "the wife sits at the low counter and puts both hands flat on it, "
                     "her daughter standing behind the chair",
         [(W, "이게… 이게 다예요?"),
          (W, "남은 게 빚 육억이라고요?"),
          (D, "엄마, 잘못 본 거 아니야?")]),
        ("은행창구", "the daughter comes round to the side of the counter and crouches "
                     "next to her mother's chair",
         [(D, "엄마, 아빠 돈은 어디 갔는데."),
          (W, "…몰라. 하나도 안 남았대."),
          (D, "그럼 우리가 그 빚을 갚아야 해?")]),
        ("은행창구", "the wife keeps looking straight ahead at the counter while her "
                     "daughter waits beside her",
         [(W, "미안해. 엄마가 진짜 몰랐어."),
          (W, "네 아빠가 이럴 사람이 아닌데…")]),
      ]),
 dict(no=9, title="등록금", when="2017년 3월", act=2,
      mood="삼키는 마음", words=["quiet", "careful", "resolved"],
      hook="딸의 등록금을 *못 냈다*",
      yt_title="딸 등록금을 못 냈습니다",
      recap="남편 통장에 남은 것은 빚뿐이었다",
      because="아내는 남편 통장에 빚만 남은 것을 보았다",
      leaves="아내는 빼돌린 돈을 찾아보기로 했다",
      reveal="아내가 딸의 등록금을 내지 못한다",
      must=["등록금"], quiet=True,
      shots=["close", "two", "ots"],
      extras={1: [D]},
      cuts=[
        ("부엌", "the wife stands at the counter with her back half turned and keeps "
                 "stirring a pot while her daughter sits at the table",
         [(W, "휴학? 왜 갑자기 휴학을 해."),
          (W, "한 학기만 더 다니면 되잖아.")]),
        ("부엌", "the daughter pushes her bowl aside and looks up while her mother sits "
                 "down across from her",
         [(D, "엄마, 등록금 못 냈잖아."),
          (W, "엄마가 어떻게든 해볼게."),
          (D, "그만해. 나 다 알아.")]),
        ("부엌", "the daughter stops in the doorway on her way out while the wife "
                 "stays at the table with both hands around a cold cup",
         [(W, "네 아빠 돈 어디로 갔는지 찾을 거야."),
          (D, "어떻게 찾아."),
          (W, "다 찾아서 네 앞으로 돌려놓을게…")]),
      ]),
 dict(no=10, title="병원 지분 십억", when="2017년 5월", act=2,
      mood="맞부딪힘", words=["tight", "hard", "cold"],
      hook="병원 지분 *십억*까지 내연녀 앞으로",
      yt_title="병원 지분 10억까지 내연녀 앞으로 넘어가 있었습니다",
      recap="아내는 빼돌린 돈을 찾아보기로 했다",
      because="아내는 빼돌린 돈을 찾아보기로 했다",
      leaves="아내는 십억 말고 더 있는지 알아보기로 했다",
      reveal="병원 지분 십억이 내연녀 앞으로 넘어가 있다",
      must=["십억", "특약"],
      shots=["two", "ots", "close"],
      cuts=[
        ("병원복도", "the wife comes down the corridor and stops in front of the woman, "
                     "who is standing by the wheeled trolley",
         [(W, "네가 여기 왜 있어."),
          (O, "제 병원인데 왜 나가요."),
          (W, "이게 언제부터 네 병원이야.")]),
        ("병원복도", "the woman walks past the wife toward the far end of the corridor "
                     "and the wife turns to follow her with her eyes",
         [(O, "그이 몫 십억, 전부 제 앞으로 왔어요."),
          (W, "그건 죽기 전 얘기지."),
          (O, "특약에 부인보다 내가 먼저라고 적혀 있어요.")]),
        ("병원복도", "the wife stands alone in the empty corridor and takes out her "
                     "phone, then holds it in both hands",
         [(W, "십억이 통째로 넘어갔어."),
          (W, "이게 다일까. 아직 더 있는 거 아니야?")]),
      ]),
 dict(no=11, title="보험 아홉 건", when="2017년 6월", act=2,
      mood="기막힘", words=["low", "tight", "hard"],
      hook="보험 아홉 건 *십삼억* 전부 내연녀",
      yt_title="사망보험 9건, 13억이 전부 내연녀 앞으로 되어 있었습니다",
      recap="병원 지분 십억이 내연녀 앞으로 갔다",
      because="아내는 십억 말고 더 있는지 알아보기로 했다",
      leaves="아내는 보험료가 어디서 나갔는지 알아보기로 했다",
      reveal="사망보험금 십삼억이 전부 내연녀 앞으로 되어 있다",
      must=["십삼억"],
      shots=["two", "close", "ots"],
      extras={2: [L]},
      cuts=[
        ("변호사사무실", "the lawyer turns his laptop away and sits back while the wife "
                         "leans forward in the visitor chair",
         [(L, "보험이 아홉 건 나왔습니다."),
          (W, "아홉 건이요? 무슨 보험이요."),
          (L, "받는 사람이 전부 내연녀입니다. 다 합쳐 십삼억이요.")]),
        ("변호사사무실", "the wife stops moving with one hand halfway to the desk and "
                         "stays like that, the lawyer waiting across from her",
         [(W, "십삼억이요…"),
          (W, "우리 애 등록금은 못 냈어요. 한 학기를요.")]),
        ("변호사사무실", "the wife sits back down and the lawyer folds both hands on the "
                         "desk between them",
         [(W, "그 돈이 어디서 났는데요."),
          (L, "매달 이천만 원씩 나갔습니다."),
          (W, "…어느 통장에서 나갔는데요?")]),
      ]),
 dict(no=12, title="다 합치니 삼십이억", when="2017년 8월", act=3,
      mood="벼른 결심", words=["low", "steady", "hard"],
      hook="다 합치니 *삼십이억*이었다",
      yt_title="다 합쳐 보니 32억이 빠져나가 있었습니다",
      recap="보험금 십삼억도 내연녀 앞이었다",
      because="아내는 보험료가 어디서 나갔는지 알아보기로 했다",
      leaves="아내는 통장 기록을 전부 챙겨 두었다",
      reveal="현금과 수표로 구억이 더 빠져나가 합계가 삼십이억이 된다",
      must=["삼십이억"],
      shots=["close", "two", "ots"],
      extras={1: [D]},
      cuts=[
        ("부엌", "the wife sits at the small table with a stack of bankbooks in front of "
                 "her and moves them one by one to her left, her daughter waiting in "
                 "the doorway",
         [(W, "현금하고 수표로만 구억이 더 나갔어."),
          (W, "이걸 몇 년에 걸쳐서 했더라.")]),
        ("부엌", "the daughter sits down across the table and the wife pushes one "
                 "bankbook toward her",
         [(D, "다 합치면 얼마야?"),
          (W, "삼십이억."),
          (D, "…삼십이억? 그게 다 우리 돈이었잖아.")]),
        ("부엌", "the wife gathers the bankbooks into one pile and puts a rubber band "
                 "around them, then holds the pile in both hands",
         [(W, "이건 하나도 안 버릴 거야."),
          (D, "엄마, 이걸로 되겠어?"),
          (W, "…이게 시작이야. 어디까지 갈 수 있을까?")]),
      ]),
 dict(no=13, title="되돌릴 건 절반", when="2017년 겨울", act=3,
      mood="팽팽함", words=["steady", "tight", "cold"],
      hook="빚은 끊었는데 되돌릴 건 *절반*뿐",
      yt_title="빚 6억은 끊었지만 되돌릴 수 있는 건 절반뿐이었습니다",
      recap="현금까지 합쳐 삼십이억이 나갔다",
      because="아내는 통장 기록을 전부 챙겨 두었다",
      leaves="아내는 절반이라도 받아내겠다고 했다",
      reveal="빚은 갚지 않아도 되지만 되돌릴 수 있는 것은 절반까지다",
      must=["절반"],
      shots=["two", "ots", "close"],
      extras={3: [L]},
      cuts=[
        ("변호사사무실", "the lawyer sets a slim bankbook on the desk and turns it toward "
                         "the wife, who is already sitting forward",
         [(L, "빚 육억은 안 갚으셔도 됩니다."),
          (W, "그게 돼요?"),
          (L, "물려받은 만큼만 갚는 걸로 신고했습니다.")]),
        ("변호사사무실", "the wife stands up out of the chair and the lawyer stays seated "
                         "with one hand open on the desk",
         [(W, "그럼 삼십이억은요. 다 받을 수 있어요?"),
          (L, "되돌릴 수 있는 건 절반까지입니다."),
          (W, "절반이요? 다 가져간 사람이 절반을 가져요?")]),
        ("변호사사무실", "the wife stops at the door with one hand on the frame and turns "
                         "back into the room",
         [(W, "그래도 할래요."),
          (W, "절반이라도 다 받아낼 거예요."),
          (W, "…그 절반은 우리 애들 몫이잖아요?")]),
      ]),
 dict(no=14, title="서명한 날짜", when="2018년 가을", act=3,
      mood="무너지는 거짓말", words=["cool", "tight", "hard"],
      hook="몰랐다던 서명 날짜가 *기각 당일이었다*",
      yt_title="몰랐다던 내연녀, 서명 날짜가 이혼 기각 당일이었습니다",
      recap="되돌릴 수 있는 건 절반까지였다",
      because="아내는 절반이라도 받아내겠다고 했다",
      leaves="내연녀는 왜 그날인지 대답하지 못했다",
      reveal="내연녀의 서명 날짜가 이혼 기각 당일이라는 것이 드러난다",
      must=["팔월 구일"],
      shots=["two", "close", "ots"],
      extras={2: [O]},
      cuts=[
        ("법정", "the woman stands at the front of the courtroom and the wife rises from "
                 "the bench behind her",
         [(O, "저는 몰랐어요. 하라는 대로 썼을 뿐이에요."),
          (W, "몰랐다고?"),
          (W, "신분증까지 네가 냈던데.")]),
        ("법정", "the wife holds up a thin bankbook at arm's length and keeps it there, "
                 "the woman half turned toward her",
         [(W, "보험료 낸 통장, 여기 있어."),
          (W, "매달 그 사람 통장에서 나갔더라.")]),
        ("법정", "the woman turns fully around to face the wife and then looks down at "
                 "the floor, both hands at her sides",
         [(W, "네가 서명한 날짜, 이천십삼년 팔월 구일이야."),
          (O, "…그게 왜요."),
          (W, "이혼 재판 진 그날이야. 몰랐다며, 근데 왜 그날이야?")]),
      ]),
 dict(no=15, title="삼 년째", when="2019년 가을", act=3,
      mood="지침", words=["tired", "low", "steady"],
      hook="재판 *삼 년째*, 딸이 그만하자고 했다",
      yt_title="재판 3년째, 딸이 이제 그만하자고 했습니다",
      recap="내연녀는 왜 그날인지 답 못 했다",
      because="내연녀는 왜 그날인지 대답하지 못했다",
      leaves="아내는 끝까지 가겠다고 했다",
      reveal="재판이 삼 년째로 길어져 딸이 그만하자고 한다",
      must=["삼 년"], quiet=True,
      shots=["two", "close", "ots"],
      extras={2: [D]},
      cuts=[
        ("법원복도", "the daughter comes down the corridor to where her mother is "
                     "sitting on the bench and stays standing in front of her",
         [(D, "엄마, 오늘도 또 미뤄졌대."),
          (W, "괜찮아. 기다리면 돼."),
          (D, "벌써 삼 년이야. 이제 그만하자.")]),
        ("법원복도", "the mother keeps both hands folded in her lap and looks straight "
                     "ahead down the corridor while her daughter waits beside her",
         [(W, "엄마가 못 지켜준 게 미안해서 그래."),
          (W, "네 아빠 돈, 그냥 두고는 못 살겠어.")]),
        ("법원복도", "the mother stands up from the bench and the daughter steps aside "
                     "to let her pass toward the courtroom doors",
         [(D, "엄마가 너무 힘들잖아."),
          (W, "여기서 놓으면 그 사람이 이기는 거야."),
          (W, "…끝까지 갈 거야.")]),
      ]),
 dict(no=16, title="판결", when="2020년 6월", act=3,
      mood="담담한 승리", words=["low", "steady", "released"],
      hook="법원 *십억 전부 돌려주라*",
      yt_title="법원이 내연녀에게 10억을 돌려주라고 했습니다",
      recap="딸이 그만하자고 했지만 아내는 갔다",
      because="아내는 끝까지 가겠다고 했다",
      leaves="",
      reveal="법원이 내연녀에게 십억을 돌려주라고 판결한다",
      must=["돌려주라"],
      shots=["two", "ots", "close"],
      extras={3: [D]},
      cuts=[
        ("법원앞", "the wife comes down the courthouse steps at an even pace and the "
                   "woman is waiting at the bottom",
         [(W, "십억. 다 돌려주라고 했어."),
          (O, "십억을 어떻게 돌려줘요."),
          (W, "네가 가져간 만큼이야.")]),
        ("법원앞", "the woman steps up one stair toward the wife and the wife stays "
                   "where she is",
         [(O, "내가 옆에서 얼마나 고생했는데."),
          (W, "고생? 우리 애는 학교를 그만뒀어."),
          (O, "한 푼도 못 줘요.")]),
        ("법원앞", "the wife walks down the last steps to where her daughter is waiting "
                   "and they start off together",
         [(W, "이제 가자. 집에 가자."),
          (W, "이 돈은 전부 너희들 몫이야."),
          (W, "…엄마가 다 받아냈어.")]),
      ]),
]
