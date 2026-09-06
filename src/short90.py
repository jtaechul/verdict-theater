#!/usr/bin/env python3
"""⭐ 90초 한 편을 만든다 — 그림 + 나레이션 + 자막 (2026-08-27 신설).

    python3 src/short90.py stills          컷마다 그림 한 장 (세로 9:16)
    python3 src/short90.py voice           컷마다 소리 (나레이션·대사)
    python3 src/short90.py build           한 편으로 조립 → build/s90/S90_short.mp4
    python3 src/short90.py all             위 셋을 차례로
    python3 src/short90.py meta            유튜브에 올릴 제목·설명·해시태그 (0원)

왜 16화가 아니라 한 편인가
    운영자 확정 — "90초로 만들어." 16화는 한 화에 사건이 하나뿐이라 "그래서
    뭔데" 를 16번 기다려야 했다. 한 편이면 5초 만에 32억이 나온다.

왜 Veo 를 안 쓰나 (기본값)
    운영자: "비오로 하기 돈아까우니까." 컷마다 영상을 만들면 90초에 7천 원이
    넘는다. **그림 한 장 + 나레이션**으로 만들면 같은 90초가 3천 원대다.
    손님이 보고 좋다고 한 참고 영상들도 전부 이 방식이다.
    대사 컷을 손으로 좋게 만들고 싶으면 S90.json 의 `veo` 프롬프트를 제미나이에
    붙여 만든 mp4 를 build/s90/clips/c07.mp4 로 넣어 두면 그 컷만 영상이 된다.

화면 (1080 × 1920 · 세로 꽉 채움)
    그림이 화면 전체 · 아주 느린 줌
    y 1300~1620  자막 (대사 컷은 위에 이름표)
    y 1620~1920  비움 — 유튜브 쇼츠 단추가 덮는 자리
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cost                                                  # noqa: E402
import reuse                                                 # noqa: E402
import still as ST                                           # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# ⭐⭐ 2026-09-01 — 사건이 여럿이 되었다. 어느 사건인지는 --sid 로 받는다.
#    ⚠️ 만드는 자리(build/s90)는 **한 곳으로 둔다.** 사건마다 폴더를 나누면
#       워크플로·보관함·관리자 페이지 세 곳의 길을 다 고쳐야 하는데, 어차피
#       한 번에 한 사건만 만든다(concurrency group 이 하나다).
SID = os.environ.get("VT_SID", "S90").strip().upper() or "S90"
DOC = ROOT / "data" / "series" / f"{SID}.json"
OUT = ROOT / "build" / "s90"

W, H = 1080, 1920
FPS = 30
FONT_SUB = ROOT / "assets" / "fonts" / "NanumGothic_ExtraBold.ttf"
FONT_NAME = ROOT / "assets" / "fonts" / "KoPub_Batang_Pro_Bold.otf"

SUB_TOP, SUB_BOT = 1300, 1620    # 자막 칸 (아래 300px 은 쇼츠 단추 자리라 비운다)
SUB_MAX, SUB_MIN, SUB_LINES = 104, 58, 3

# ⭐⭐ 2026-08-31 손님: "카라오케라면 전체 대사가 다 떠 있는 상태에서 색깔만
#    바뀌는 게 아니라 **해당 대사만 나타났다가 사라지게끔** 하는 걸 원한 거야."
#    맞다. 앞의 것은 노래방 자막이고, 손님이 원하신 것은 쇼츠에서 흔한
#    **한 토막씩 떴다 사라지는** 자막이다.
#    → 이제 한 번에 **한 토막만** 화면에 있다. 짧으니 글자도 훨씬 크게 나온다.
#
#    ⚠️ 낱말 하나씩 끊으면 너무 잘게 튄다("몰랐다면서." "근데" "어떻게" …).
#       숨 쉬는 단위로 묶는다 — 낱말 세 개까지, 글자 아홉 자까지.
# ⭐⭐⭐ 2026-09-05 손님: "자막이 단어 단위로 안 끊기고 말이 중간에 끊기는
#    경우가 부분적으로 있고, 글씨 크기가 갑자기 작아지거나 하는 상황이 발생해.
#    글씨 크기 변동이 없도록 유지해주고, 글씨가 많을 경우에는 중간에 문장을
#    끌어서 다음 자막으로 띄우면 되잖아."
#    맞다. 실측하면 한 컷 안에서 104 → 96 → 102 로 크기가 튀었고,
#    「당신 차에서 관계 / 맺는 소리가」 처럼 말 한복판이 갈렸다.
#    까닭 둘 —
#      ① **낱말 3개**로 못을 박아, 자리가 남아도 거기서 끊었다
#      ② 토막마다 **들어갈 때까지 글자를 줄여서**(fit) 크기가 달라졌다
#    → 크기를 하나로 고정하고, **그 크기로 한 줄에 들어가는 만큼** 담는다.
#      넘치면 줄이지 말고 **다음 자막으로 넘긴다.**
SUB_FIXED = 96                   # 자막 글씨 크기 — 토막마다 안 바뀐다
# ⚠️ 2026-09-05 — 여기 있던 CHUNK_CHARS(9자) · CHUNK_WORDS(3낱말) 를 **지웠다.**
#    토막을 글자·낱말 수로 못 박고 넘치면 글씨를 줄이던 옛 셈이다. 그것 때문에
#    말이 한복판에서 갈리고 크기가 튀었다. 이제 크기를 고정하고 **들어가는
#    만큼** 담는다(chunks_of). 쓰지 않는 값을 남겨 두면 언젠가 되살아난다.
# 숫자 뒤에 붙는 단위 — 이 앞에서는 끊지 않는다 ("이천만 / 원을" 방지)
UNIT = ("원", "억", "만", "천", "명", "년", "월", "일", "시", "분", "개", "배", "%")
NUMWORD = ("일", "이", "삼", "사", "오", "육", "칠", "팔", "구", "십",
           "백", "천", "만", "억", "조")
SUB_GAP = 1.24
SIDE = 60
# ⭐⭐ 2026-08-31 손님: "등장인물 소개 문구는 잘 보이게 바꿔 주고 왼쪽에
#    세로로 된 바(bar)를 그어 줘."
#    예전 이름표는 **가운데 정렬 + 옅은 금색 + 테두리 없음**이라, 아내의 밝은
#    가디건 위에서 글자가 그대로 묻혔다. 방송 자막처럼 바꾼다 —
#    왼쪽에 금색 세로 막대를 세우고, 그 옆에 왼쪽 맞춤으로 크게 적는다.
NAME_Y, NAME_SIZE = 1214, 54
NAME_BAR_W = 7          # 왼쪽 세로 막대 두께
NAME_BAR_GAP = 20       # 막대와 글자 사이
NAME_BAR_PAD = 7        # 막대가 글자 위아래로 더 뻗는 정도
# ⭐⭐⭐ 2026-09-01 손님: "영상 상단에는 1편 제목, 2편 제목이 하나 들어가
#    줘야 되는 거 아니야?"
#    맞다. 그리고 자리가 중요하다 —
#      · 유튜브 **제목**은 *볼지 말지 정하는* 사람이 본다. 거기 "2편" 이 보이면
#        "1편부터 봐야 하나" 하고 넘긴다 → 제목에는 번호를 안 쓴다.
#      · **화면 안**은 *이미 보고 있는* 사람만 본다. 번호가 이탈을 안 만들고
#        오히려 "시리즈구나" 가 된다 → 번호는 여기 넣는다.
#    ⚠️ 끝까지 띄우지 않는다. 위에 제목 아래에 자막이면 그림이 가운데 좁은
#       띠만 남아 답답하고, 드라마가 아니라 정보 영상처럼 보인다.
#       쇼츠에서 첫 화면은 썸네일 노릇을 하므로 **처음 2.5초만** 띄운다.
#    ⚠️ 맨 위 180px 은 유튜브 앱이 제 것으로 덮을 수 있어 피한다.
TITLE_SEC = 2.5                  # 떠 있는 시간
TITLE_Y = 208                    # 작은 줄(시리즈·편)이 시작하는 자리
TITLE_LABEL = 40                 # 작은 줄 글자 크기
TITLE_MAX, TITLE_MIN = 84, 52    # 큰 두 줄 글자 크기
TITLE_GAP = 1.30
TITLE_BAR_W, TITLE_BAR_GAP, TITLE_BAR_PAD = 9, 26, 12
# 사라질 때 세 단계로 옅어진다 — 뚝 끊기면 눈에 걸린다
TITLE_FADE = (1.0, 0.55, 0.22)
TITLE_SCRIM = 560                # 위에서 여기까지 서서히 어두워진다
TITLE_SCRIM_MAX = 0.62

# ⭐⭐ 2026-09-02 손님: "좌측 상단에 아주 작게(판결극장과 같은 글씨 크기로)
#    드라마 제목과 몇화인지 들어가는게 좋을 것 같아."
#    큰 제목 카드는 첫 2.5초만 뜨고 사라진다. 중간에 들어온 사람은 이것이
#    무슨 이야기의 몇 번째인지 알 길이 없다. → 오른쪽 위 채널 이름과
#    **같은 크기로 왼쪽 위에 늘 띄운다.** 조용히 있고 그림을 안 가린다.
#    ⚠️ 큰 제목 카드의 작은 금색 줄은 뺀다 — 같은 말이 두 번 보이면 지저분하다.
SERIES_ALPHA = 190               # 채널 이름(168)보다 아주 조금 또렷하게

# ⭐⭐ 2026-09-02 손님: "끝날 때 다음화에 계속이 들어가야 하는거 아니야?"
#    맞다. 앞서 "영상 끝에 다음 편 안내를 넣겠다" 고 해 놓고 빠뜨렸다.
#    ⚠️ 끝까지 본 사람에게만 보인다 — 그래서 여기가 다음 편으로 잇는 자리다.
TAIL_SEC = 1.7                   # 끝 알림이 떠 있는 시간
TAIL_Y = 900                     # 자막(1300~)과 이름표(1214)를 안 건드리는 자리
TAIL_SIZE = 78
TAIL_FADE = (0.30, 0.70, 1.0)    # 나타날 때 세 단계 (뚝 튀어나오면 눈에 걸린다)
TAIL_NEXT = "다음 편에 계속"
TAIL_LAST = "완결"
# ⭐⭐⭐ 2026-09-06 손님: "다음화가 궁금하다면은 구독과 좋아요, 알림을 좀
#    설정하도록 유도하는 건 어떨까." 끝까지 본 사람에게만 보이는 자리라
#    가장 좋다. 큰 글 아래에 **작게 한 줄** 더 둔다 (큰 글을 안 가린다).
# ⚠️ OS 이모지는 안 쓴다 — 기기마다 모양이 달라 싸구려처럼 보인다(0-2 규칙).
TAIL_SUB_NEXT = "다음 편이 궁금하다면  구독 · 좋아요 · 알림"
TAIL_SUB_LAST = "구독해 두시면 다음 사건을 놓치지 않습니다"
TAIL_SUB_SIZE = 40

SCRIM_TOP = 1080                 # 여기부터 아래로 서서히 어두워진다
SCRIM_MAX = 0.88                 # 맨 아래 어두움 (0~1)
MARK_SIZE, MARK_Y = 34, 44
CHANNEL = "판결극장"
GOLD = (198, 160, 74, 255)
GOLD_BRIGHT = (232, 197, 112, 255)   # 이름표 글자 — 밝은 그림 위에서도 읽히게

# ⭐⭐ 2026-08-31 손님: "카라오케 자막으로 변경하자."
#    한 낱말씩 불이 들어온다 — 지금 말하는 낱말이 금색으로 도드라진다.
#    ① 이미 말한 낱말  흰색 그대로
#    ② 지금 말하는 낱말 금색 (여기가 카라오케다)
#    ③ 아직 안 한 낱말 흰색을 흐리게
#    ⚠️ 흐린 글자도 **읽을 수는 있어야** 한다. 너무 흐리면 다음 말을 눈으로
#       못 좇는다 — 40% 아래로는 내리지 않는다.
SUB_DONE = (255, 255, 255, 255)
SUB_NOW = (245, 205, 116, 255)
SUB_TODO = (255, 255, 255, 112)
WHITE = (255, 255, 255, 255)
# ⭐⭐ 2026-08-31 손님: "속도가 조금 느린 거 같은데 조금만 더 빠르게 가능한가?"
#    재 보니 147초 가운데 **말이 없는 자리가 17초(11%)** 였다. 두 군데다 —
#      ① 대본에 적어 둔 최소 길이(sec)가 실제 말보다 길어서 남는 시간
#         — 그 숫자는 Veo 영상(4·6·8초)에 맞춘 것이라 그림 컷에는 뜻이 없다
#      ② 말이 끝난 뒤 여운 0.55초 × 스무 컷 = 11초
#    → 최소 길이를 안 쓰고, 여운을 줄이고, 말 자체도 조금 빠르게 한다.
#    ⚠️ 말을 빠르게 하는 것은 **조립할 때** 한다(atempo). 목소리를 다시
#       만들면 750원이 또 나가는데, 조립은 0원이기 때문이다.
PAD = 0.40                       # 말이 끝난 뒤 남기는 여운(초)
MIN_CUT = 2.2                    # 아무리 짧아도 이만큼은 보여 준다(깜빡임 방지)
# ⭐ 2026-09-02 손님: "1.2배속으로 바꿔."
#    1.08 → 1.20. 자막 시각도 이 값으로 나누므로(sub_windows) 함께 당겨진다 —
#    여기 한 곳만 고치면 목소리와 자막이 같이 빨라진다.
#    ⚠️ 목소리를 다시 만들지 않는다. 조립할 때 빨리 감는다(atempo) → 0원.
SPEED = 1.20                     # 말 빠르기 (1.28 을 넘기면 발음이 뭉개진다)

# ⭐⭐ 2026-08-31 손님: "배경음악이 좀 하나 깔려야 될 거 같거든? 우리 만들어
#    놓은 게 있으니까 그거 하나를 좀 깔도록 하고."
#    assets/bgm/ 에 여덟 곡이 이미 있다. 새로 만들 것이 없다(0원).
#    ⚠️ 왜 verdict 인가 — 우리 편이 129초인데 이 곡이 166초라 **한 바퀴로
#       끝까지 덮는다.** 짧은 곡을 쓰면 도는 자리에서 이음매가 들린다.
#       (그래도 어떤 곡을 골라도 되게 -stream_loop 로 돌려 둔다)
#    ⚠️ 말소리를 덮으면 안 된다. 그냥 볼륨만 낮추면 조용한 대목에서는 너무
#       작고 큰 대목에서는 여전히 방해가 된다. 그래서 **말이 나올 때만 음악을
#       눌러 주는**(사이드체인) 방식을 쓴다 — 말 없는 자리에서만 올라온다.
BGM = os.environ.get("S90_BGM", "verdict").strip()
BGM_VOL = 0.42                   # 눌리기 전 기본 크기
BGM_IN, BGM_OUT = 1.5, 3.0       # 시작에 서서히 들어오고, 끝에 서서히 빠진다
ZOOM_SRC = 1.4                   # 움직이기 전에 그림을 키워 두는 배수 (떨림 방지)

# ⭐⭐ 2026-08-31 손님: "줌인 줌아웃 등이 조금 더 있어서 생동감이 조금 더
#    넘쳤으면 좋겠어."
#    예전에는 **가운데서 1.10배까지 커지는 것 하나**뿐이었다. 방향만 컷마다
#    뒤집었을 뿐이라, 스무 컷을 이어 붙이면 같은 움직임이 계속 반복됐다.
#    → 카메라 움직임을 여섯 가지로 늘리고 **옆으로도 훑게** 한다.
#
#    한 줄은 (줌 시작, 줌 끝, 가로 시작, 가로 끝, 세로 시작, 세로 끝, 이름).
#    가로·세로는 0=왼쪽/위, 1=오른쪽/아래, 0.5=한가운데다.
#    ⚠️ 줌이 1.0 이면 옆으로 훑을 자리가 없다(화면이 딱 맞는다). 그래서
#       가장 작은 값도 1.04 로 둔다 — 늘 조금은 여유를 남긴다.
#    ⚠️ 1.30 을 넘기면 1.4배로 키워 둔 그림의 화소를 넘어서 흐려진다.
MOVES = [
    (1.04, 1.22, 0.50, 0.50, 0.50, 0.50, "천천히 다가간다"),
    (1.24, 1.06, 0.50, 0.50, 0.50, 0.50, "천천히 물러선다"),
    (1.06, 1.20, 0.62, 0.40, 0.48, 0.52, "다가가며 왼쪽으로"),
    (1.06, 1.20, 0.38, 0.60, 0.52, 0.48, "다가가며 오른쪽으로"),
    (1.16, 1.16, 0.50, 0.50, 0.34, 0.64, "위에서 아래로 훑는다"),
    (1.24, 1.08, 0.44, 0.56, 0.62, 0.42, "물러서며 위로"),
]
# 대사 컷은 사람 얼굴이 주인공이다 — 옆으로 크게 훑으면 얼굴이 잘린다.
# 그래서 대사 컷은 **다가가고 물러서는 것만**, 나레이션 컷은 훑는 것까지 쓴다.
MOVES_TALK = (0, 1)
MOVES_NARR = (0, 2, 4, 1, 3, 5)

# 목소리 — 사람마다 고정한다 (컷마다 달라지면 딴 사람이 된다)
# ⭐⭐⭐ 2026-08-31 손님 확정: "갈아탄다."
#
#   ⚠️ 여기가 목소리가 밋밋했던 **까닭 그 자체**였다. 이름이 `ko-KR-…` 이면
#      tts.say() 가 곧장 옛 구글 엔진으로 보낸다. 그 엔진에는 연기 지시를
#      받는 자리가 아예 없다. 16화 쪽에는 지시를 보내는 길이 다 만들어져
#      있는데 90초 편만 그 길을 안 쓰고 있었다.
#      → 제미나이 목소리 이름으로 바꾸면 그 길이 열린다.
#
#   나이에 맞춰 고른다 (tts.MATURE_F / MATURE_M 과 같은 결) —
#     아내 52세·남편 55세 → 연륜 있는 목소리
#     내연녀 30대·딸 20대 → 젊은 목소리
#     나레이션은 **누구와도 안 겹치는** 목소리여야 한다
VOICE = {
    "나레이션": "Alnilam",       # 낮고 묵직 — 사건을 전하는 소리
    "아내": "Gacrux",            # 연륜 — 50대 여성
    "내연녀": "Erinome",         # 젊다 — 30대 여성
    "남편": "Algenib",           # 거칠다 — 50대 남성
    "변호사": "Iapetus",         # 사무적 — 40대 남성
    "딸": "Leda",                # 어리다 — 20대 여성
}
NARR_RATE = 1.02                 # 나레이션은 아주 조금 빠르게 (또박또박은 유지)

# ⭐⭐⭐ 2026-09-04 — 사건마다 사람이 다르다(장남·며느리·시어머니…). 위 표에
#    없는 사람은 여태 **나레이션 목소리**로 말했다 — 30대 며느리가 낮고 묵직한
#    남자 소리로 말하는 셈이다. 대본이 적어 준 나이대·성별로 골라 준다.
VOICE_BY = {
    ("여", "10대"): "Leda",      ("남", "10대"): "Puck",
    ("여", "20대"): "Leda",      ("남", "20대"): "Puck",
    ("여", "30대"): "Erinome",   ("남", "30대"): "Iapetus",
    ("여", "40대"): "Kore",      ("남", "40대"): "Iapetus",
    ("여", "50대"): "Gacrux",    ("남", "50대"): "Algenib",
    ("여", "60대"): "Gacrux",    ("남", "60대"): "Alnilam",
    ("여", "70대"): "Gacrux",    ("남", "70대"): "Alnilam",
}


def voice_of(who, doc):
    """그 사람의 목소리. 표에 없으면 대본이 적은 나이대·성별로 고른다."""
    if who in VOICE:
        return VOICE[who]
    v = ((doc.get("people") or {}).get(who) or {})
    got = VOICE_BY.get((str(v.get("sex") or "여"), str(v.get("age") or "40대")))
    return got or VOICE["나레이션"]


class Short90Error(RuntimeError):
    pass


def turns_of(c):
    """이 컷에서 말하는 차례. 옛 대본(turns 없음)도 받아 준다."""
    if c.get("turns"):
        return [(w, t) for w, t in c["turns"]]
    return [(c.get("kind") or "나레이션", c.get("text") or "")]


def is_narr(c):
    return all(w == "나레이션" for w, _ in turns_of(c))


def load():
    if not DOC.exists():
        raise Short90Error(f"data/series/{SID}.json 이 없다 — "
                           f"python3 tools/build_short90.py {SID} 를 먼저 돌린다.")
    return json.loads(DOC.read_text(encoding="utf-8"))


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise Short90Error(f"ffmpeg 가 실패했다:\n{p.stderr[-900:]}")
    return p.stdout


def dur_of(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip() or 0)


def has_audio(path):
    """이 영상에 소리가 붙어 있는가."""
    out = run(["ffprobe", "-v", "error", "-select_streams", "a",
               "-show_entries", "stream=codec_type", "-of",
               "default=nw=1:nk=1", str(path)])
    return "audio" in out


# ── ① 그림 ────────────────────────────────────────────────────
# 화면 이름 ↔ 인물 카드 파일 이름 (카드에는 아내가 '본처' 로 적혀 있다)
ST_NAME = {"아내": "본처"}


def cards_dir():
    return OUT / "cards"


def salvage(d, suffix=".png"):
    """이미 만들어 둔 것을 **지문으로** 찾아 둔다 — {지문: 파일 내용}.

    ⚠️⚠️ 2026-08-31 — 컷 하나를 중간에 끼워 넣었더니 뒤 컷 번호가 전부 하나씩
       밀렸다. 파일 이름이 컷 번호(c13.png)라, 내용은 그대로인데 **이름이
       어긋나** 여덟 장을 다시 그릴 뻔했다 (1,056원).
       → 이름이 아니라 **지문**으로 찾는다. 앞으로 컷을 끼워 넣어도 값이 안 든다.
       ⚠️ 먼저 통째로 읽어 두고 나서 쓴다. 하나씩 옮기면 아직 안 옮긴 것을
          덮어써 버린다 (13→14 를 쓰는 순간 원래 14 가 사라진다).
    """
    have = {}
    for f in sorted(Path(d).glob(f"*{suffix}")):
        sg = reuse.sig_file(f)
        if not sg.exists():
            continue
        key = sg.read_text(encoding="utf-8").strip()
        if key and key not in have:
            have[key] = f.read_bytes()
    return have


# ── ⭐⭐⭐ 첫 장면은 **입이 안 움직인다** (2026-09-04 손님 지시) ──────
#    손님: "동영상에서 입은 안움직여도 될 것 같아."
#    맞다. 편 첫 컷은 **나레이션 컷**이라 화면에서는 아무도 말하지 않는다.
#    입이 움직이면 우리 나레이션과 어긋나 곧바로 가짜처럼 보인다.
#
#    그런데 지금 프롬프트에 두 가지가 걸려 있었다 —
#      ① "8-second" 라고 적혀 있다. 우리는 4초를 산다. 8초에 맞춰 움직임을
#         짜면 4초에서 잘려 어정쩡하게 끝난다.
#      ② "nobody speaks and nobody moves their lips" — **금지형**이다.
#         이 저장소의 오랜 규칙: 모델은 부정을 흘려듣고 오히려 그대로 한다.
#         입을 다물게 하려고 적은 줄이 입을 움직이게 만들 수 있다.
#    → 둘 다 고친다. **바라는 것만** 적는다.
OPEN_LIPS = (
    "MOTION: every person keeps their mouth closed and their jaw relaxed for "
    "the entire take, holding a quiet inward expression, thinking rather than "
    "talking. The only movement is one calm breath, a single slow blink, a "
    "small shift of the head or hand, hair and fabric drifting slightly, and "
    "light shifting softly across the scene. The camera holds still.")
OPEN_AUDIO = "AUDIO: only the quiet room tone of the location."


# ⭐ 첫 장면은 **첫 프레임부터** 움직여야 한다. 영상 모델은 긴 take 로 알면
#    앞머리를 정지 화면처럼 천천히 연다 — 손님: "이미지 나온후 영상 나왔다가".
OPEN_START = ("MOTION START: the movement is already under way in the very first "
              "frame and continues without pause to the last frame.")


def open_prompt(c):
    """편 첫 장면(4초)용 프롬프트 — 길이를 맞추고 입을 다물게 한다."""
    txt = str(c.get("veo") or c.get("still") or "")
    out = []
    for line in txt.splitlines():
        if line.startswith("AUDIO:"):
            # 금지형 줄을 통째로 **바라는 것만** 적은 줄로 바꾼다
            out.append(OPEN_AUDIO)
            continue
        # ⚠️⚠️ 2026-09-05 — 여기가 `"8-second"` 로 **박혀 있었다.** 그런데
        #    지문이 실제로 적어 오는 말은 `6-second` 였다(veo_sec 이 정한다).
        #    그래서 바꾸는 일이 **한 번도 일어나지 않았고**, 4초를 사면서
        #    모델에게는 6초짜리로 짜라고 시키고 있었다. 6초용 움직임을 4초에
        #    맞춰 잘라 내니 앞머리가 정지 화면처럼 열렸다.
        #    → 몇 초라고 적혀 있든 **우리가 사는 길이**로 바꾼다
        #      (src/vprompt.py 가 쓰는 것과 같은 방식).
        out.append(re.sub(r"\b\d+(?:\.\d+)?-second single continuous take",
                          f"{OPEN_SEC:g}-second single continuous take", line))
    out.append(OPEN_START)
    out.append(OPEN_LIPS)
    return "\n".join(out)


def open_cuts(doc):
    """편마다 **첫 컷** 번호. 여기만 진짜 영상으로 만든다."""
    return [part_cuts(doc, p)[0]["n"] for p in parts_of(doc) if part_cuts(doc, p)]


def open_dir():
    return OUT / "open"


def openers(doc):
    """편 첫 컷을 Veo 로 4초짜리 영상으로 만든다 (image-to-video).

    ⚠️ 값이 나간다. 그래서 —
       · 켜야만 돈다 (VT_OPEN_VIDEO)
       · 만들기 **전에** 얼마인지 적어 준다
       · 지문이 같으면 다시 안 만든다 (0원). 그림이 바뀌면 다시 만든다.
    """
    import veo                                              # 늦게 부른다(열쇠 필요)
    d = open_dir()
    d.mkdir(parents=True, exist_ok=True)
    ns = open_cuts(doc)
    st = OUT / "stills"
    krw1 = cost.video_krw(veo.MODEL, OPEN_SEC)
    print(f"■ 편 첫 장면 영상 {len(ns)}개 "
          f"({OPEN_SEC:g}초씩 · 한 개 약 {krw1:,.0f}원 · 최대 "
          f"{krw1 * len(ns):,.0f}원)")
    made, miss = 0, []
    for n in ns:
        out = d / f"c{n:02d}.mp4"
        still = st / f"c{n:02d}.png"
        if not still.exists():
            raise Short90Error(f"컷{n} 그림이 없다 — 먼저 stills 를 돌린다")
        c = [x for x in doc["cuts"] if x["n"] == n][0]
        # ⚠️ 우리 시스템용 판(veo)을 쓴다. 앱용 판(flow)이 아니다.
        #    ⭐ 첫 장면용으로 손본다 — 4초에 맞추고, 입을 다물게 한다.
        prompt = open_prompt(c)
        # ⚠️ 지문에 **그림 내용까지** 넣는다. 그림이 바뀌면 영상도 바뀌어야 한다.
        sig = reuse.sig_of(prompt, f"{OPEN_SEC:g}", OPEN_RATIO,
                           reuse.sig_of(still.read_bytes().hex()[:4096]))
        ok, why = reuse.can_reuse(out, sig)
        print(f"  컷{n:>2} 편 첫 장면")
        if ok:
            print("    (그대로다 — 건너뛴다 · 0원)")
            made += 1
            continue
        if why:
            print(f"    ⚠️ {why} — 다시 만든다")
        try:
            veo.make_clip(prompt, int(OPEN_SEC), out, ratio=OPEN_RATIO,
                          seed=veo._seed(doc.get("sid"), n), start=still)
        except veo.RaiFiltered:
            # ⭐⭐⭐ 2026-09-05 손님: "1화는 앞에 영상이 아닌 이미지야."
            #    까닭은 구글 **안전 필터**였다. 고장이 아니라 그때그때 걸리는
            #    것이라, 씨앗만 바꿔 한 번 더 부르면 통과하는 일이 잦다.
            #    ⚠️ 한 번 더 부르면 값이 또 나간다 — **딱 한 번만** 한다.
            print(f"    ⚠️ 안전 필터에 걸렸다 — 씨앗을 바꿔 **한 번만** "
                  f"다시 해 본다 (약 {krw1:,.0f}원)")
            try:
                veo.make_clip(prompt, int(OPEN_SEC), out, ratio=OPEN_RATIO,
                              seed=veo._seed(doc.get("sid"), n, "2"),
                              start=still)
            except Exception as e2:                          # noqa: BLE001
                print(f"    ⚠️ 두 번째도 못 만들었다 ({e2}) — 이 컷은 그림으로 갑니다")
                out.unlink(missing_ok=True)
                miss.append(n)
                continue
        except Exception as e:                               # noqa: BLE001
            # ⚠️ 첫 장면 하나가 안 나왔다고 편 전체를 못 만들면 안 된다.
            #    그 컷은 **그림으로** 간다 — 지금까지 하던 그대로다.
            print(f"    ⚠️ 못 만들었다 ({e}) — 이 컷은 그림으로 갑니다")
            out.unlink(missing_ok=True)
            miss.append(n)
            continue
        reuse.stamp(out, sig)
        made += 1
    print(f"\n■ 편 첫 장면 {made}/{len(ns)}개")
    # ⚠️ 조용히 그림으로 넘어가면 손님은 "왜 1화만 영상이 아니지?" 만 알게 된다.
    #    어느 편이 그림으로 열리는지 **크게** 적는다.
    if miss:
        no = {c: i + 1 for i, c in enumerate(ns)}
        print("  ⚠️⚠️ 첫 장면이 그림으로 열리는 편: "
              + " · ".join(f"{no[n]}편(컷{n})" for n in miss))
    return 0


def stills(doc):
    d = OUT / "stills"
    d.mkdir(parents=True, exist_ok=True)
    kept = salvage(d)
    # ⚠️ 컷 수로 곱하면 값을 부풀려 적게 된다. 편 앞머리 나레이션처럼
    #    **다른 컷과 지문이 똑같은 컷**은 다시 안 그리고 옮겨 쓴다(0원).
    # ⭐⭐⭐ 2026-09-06 손님: **"왜 계속 만든 것 중 재활용 가능한 걸 또 만들어서
    #    돈을 낭비하냐."** 맞는 지적이었다. 그리고 이 줄이 그 낭비를 **가리고
    #    있었다** — 여기서 "새로 그릴 것 27장 · 약 3,572원" 이라고 적어 놓고
    #    실제로는 6장만 그린 날이 있었다. 반대로 정말 27장을 그린 날도 같은
    #    글이 떴다. **둘을 구분할 수가 없었다.**
    #    → 보관함을 이미 받아 온 뒤이므로(salvage), **진짜로 다시 그릴 것이
    #      몇 장인지 여기서 세어서** 그리기 전에 적는다.
    plan = []
    for c in doc["cuts"]:
        refs = [p for p in (ST.card_path(cards_dir(), ST_NAME.get(w, w))
                            for w in c.get("who") or []) if p.exists()]
        sig = reuse.sig_of(c["still"], *refs)
        ok, _why = reuse.can_reuse(d / f"c{c['n']:02d}.png", sig)
        if not ok and sig not in kept:
            plan.append(c["n"])
    one = cost.image_krw(ST.MODEL, ST.SIZE)
    keep = len(doc["cuts"]) - len(plan)
    print(f"■ 컷 그림 {len(doc['cuts'])}장 — **다시 그릴 것 {len(plan)}장 "
          f"· 약 {one * len(plan):,.0f}원** (나머지 {keep}장은 그대로 씁니다 · 0원)")
    if plan:
        print(f"   다시 그리는 컷: {', '.join(str(n) for n in plan)}")
    made = 0
    for c in doc["cuts"]:
        out = d / f"c{c['n']:02d}.png"
        refs = [p for p in (ST.card_path(cards_dir(), ST_NAME.get(w, w))
                            for w in c.get("who") or []) if p.exists()]
        sig = reuse.sig_of(c["still"], *refs)
        ok, why = reuse.can_reuse(out, sig)
        print(f"  컷{c['n']:>2} {'·'.join(c.get('who') or []) or '—'}")
        if ok:
            print("    (그대로다 — 건너뛴다)")
            made += 1
            continue
        # ⭐ 이름은 어긋났어도 **같은 지문**의 그림이 있으면 그것을 옮겨 쓴다
        #    (컷을 끼워 넣어 번호가 밀렸을 때 — 값이 안 든다)
        if sig in kept:
            out.write_bytes(kept[sig])
            reuse.stamp(out, sig)
            print("    (이름만 밀렸다 — 그대로 옮겨 쓴다 · 0원)")
            made += 1
            continue
        if why:
            print(f"    ⚠️ {why} — 다시 만든다")
        ST.gen(c["still"], out, refs=refs, ratio="9:16",
               seed=ST.seed_of(doc.get("sid") or SID, c["n"]))
        # ⚠️ 새로 그렸으면 **가린 표시를 지운다.** 안 지우면 "이미 가렸다" 며
        #    건너뛰는데, 새 그림에서는 상표가 다른 자리에 있을 수 있다.
        out.with_suffix(".scrubbed").unlink(missing_ok=True)
        reuse.stamp(out, sig)
        made += 1
    print(f"\n■ 그림 {made}/{len(doc['cuts'])}장")
    # ⭐⭐ 2026-08-31 손님: "특정 은행 브랜드가 언급되면 안 돼."
    #    그림 모델이 실제 상표(하나은행)를 그려 넣은 적이 있다. 정해 둔 자리를
    #    흐리게 만든다 (값 0원). 영상이 아니라 **그림**에 걸어야 카메라가
    #    움직여도 자국이 함께 따라간다.
    sys.path.insert(0, str(ROOT / "tools"))
    import scrub_still                                       # noqa: E402
    scrub_still.scrub(d, doc)
    # ⭐⭐⭐ 2026-09-05 손님: "이미지 우측 하단에 재미난 워터마크가 살짝
    #    보이거든? 지금 화면이 어두워도 살짝 보여."
    #    그림 모델이 오른쪽 아래에 자기 표시를 찍는다. 영상으로 만들면 그대로
    #    따라 들어간다. 여기서 지운다 — **그림 단계에서** 지워야 편 첫 장면
    #    영상(그 그림을 넣어 움직이게 한다)에도 안 딸려 간다.
    import wipe_mark                                         # noqa: E402
    wipe_mark.main_dir(d)
    return 0 if made == len(doc["cuts"]) else 1


# ── ② 소리 ────────────────────────────────────────────────────
def voice_route_ok(tts, need):
    """이 길로 **필요한 줄 수만큼** 만들 수 있는가 — 만들기 **전에** 본다.

    ⚠️⚠️ 2026-08-31 — 여기가 조용히 망가지는 자리다.
       제미나이 목소리는 두 길이 있는데 한도가 하늘과 땅 차이다.
         구글 클라우드 길 — 하루 횟수 제한 없음
         AI 스튜디오 길   — **무료 등급 하루 10번**
       우리는 스물세 줄이 필요하다. 스튜디오 길로 가면 열한 번째 줄부터
       막히고, tts.say() 가 조용히 옛 구글 목소리로 물러선다. 그러면
       **한 편 안에서 아내 목소리가 중간에 바뀌고 감정이 사라진다.**
       영상은 멀쩡히 나오므로 눈으로는 안 보인다 — 그게 제일 나쁘다.
       → 돈 쓰기 전에 미리 보고, 안 되면 **아예 시작하지 않는다.**
    """
    # ⭐ 목소리가 중간에 바뀌는 것을 막는다 (tts.NO_FALLBACK 설명 참조).
    #   막히면 옛 목소리로 물러서지 않고 **거기서 멈춘다.** 만든 데까지는
    #   보관되므로 다음 날 눌러 이어서 만들 수 있다.
    tts.NO_FALLBACK = True
    if str(os.environ.get("SKIP_VOICE_ROUTE", "")).strip() == "1":
        return
    note = tts.route_note()
    print(f"■ 목소리 길: {note}")
    if "AI 스튜디오" in note:
        # ⚠️ 막지 않는다. 하루 한도는 **재 보기 전에는 모른다** — 무료 등급이면
        #    10번이지만 결제가 붙어 있으면 훨씬 많다. 우리 열쇠는 이 열쇠로
        #    그림을 50장 만든 이력이 있어 결제가 붙은 쪽으로 보인다.
        #    모르는 것을 단정해 손님을 구글 클라우드 콘솔까지 보내면 안 된다.
        #    막히면 어차피 아래 잠금이 **멈춰 세우고** 만든 데까지 보관한다.
        print(f"  ■ {need}줄을 만듭니다. 이 창구의 하루 한도는 열쇠 등급에\n"
              f"     달렸습니다 — 모자라면 거기서 멈추고 만든 데까지 보관합니다.\n"
              f"     ⭐ 목소리가 중간에 바뀌는 일은 없습니다 (다시 누르면 이어집니다).")


def voices(doc):
    """목소리를 만든다. **값은 반드시 장부에 남긴다.**

    ⭐⭐⭐ 2026-09-06 손님이 "돈 세는 곳 없는지 확인해" 라고 하셔서 또 세어 보니,
       **90초 쇼츠의 목소리 값이 8월 23일부터 장부에 한 줄도 안 적히고 있었다.**
       tts.say() 는 쓴 글자를 모아 두기만 하고(bill_add), 그것을 장부로 옮기는
       것은 bill_flush() 인데 — 옛 60초 쪽(src/shorts.py)만 그것을 불렀고
       여기서는 아무도 안 불렀다. 모아 두기만 하고 아무도 안 비웠다.
       더 나쁜 것: 한 달 한도(MONTH_KRW)는 장부만 보고 세므로, 안 적힌 돈은
       한도에도 안 잡힌다.
       → 여기서 **끝나든 실패하든(finally)** 반드시 비운다. 중간에 멈춰도
         이미 나간 돈은 적힌다.
    """
    import tts                                               # 늦게 부른다(열쇠 필요)
    try:
        return _voices(doc, tts)
    finally:
        won = tts.bill_flush(f"{SID} 90초 쇼츠")
        if won:
            print(f"■ 목소리 값 약 {won:,.0f}원 — 장부에 적었다")


def _voices(doc, tts):
    d = OUT / "voice"
    d.mkdir(parents=True, exist_ok=True)
    need = sum(len(turns_of(c)) for c in doc["cuts"])
    voice_route_ok(tts, need)
    # ⭐⭐ 2026-09-01 — **그림에만 있던 안전장치를 소리에도 단다.**
    #    컷을 끼워 넣으면 뒤 번호가 밀린다. 그림은 지문으로 찾아 옮겨 쓰는데
    #    (salvage) 소리는 그게 없어서, 편을 나누느라 컷 넷을 끼워 넣자
    #    **멀쩡한 목소리 스무 줄을 다시 만들 뻔했다.** 소리는 그림보다 비싸다.
    kept = salvage(d, ".wav")
    kept_len = {}
    for f in sorted(d.glob("*.wav")):
        sg = reuse.sig_file(f)
        ln = lens_of(f)
        if sg.exists() and ln.exists():
            kept_len.setdefault(sg.read_text(encoding="utf-8").strip(),
                                ln.read_bytes())
    print(f"■ 소리 {len(doc['cuts'])}줄")
    made = 0
    for c in doc["cuts"]:
        out = d / f"c{c['n']:02d}.wav"
        turns = turns_of(c)
        # ⭐ 줄마다 **어떻게 읽을지**(say)를 같이 들고 간다. 이게 이번 바꿈의
        #   핵심 — 같은 글자라도 어떻게 읽으라고 말해 주면 낭독이 연기가 된다.
        says = c.get("say") or [""] * len(turns)
        plan = [(w, t, voice_of(w, doc),
                 NARR_RATE if w == "나레이션" else 1.0,
                 says[i] if i < len(says) else "")
                for i, (w, t) in enumerate(turns)]
        # ⚠️ 지문에 지시도 넣는다 — 지시를 고치면 그 줄만 다시 만들어야 한다
        sig = reuse.sig_of(*[f"{w}|{t}|{v}|{r}|{h}" for w, t, v, r, h in plan])
        ok, why = reuse.can_reuse(out, sig)
        # ⚠️ 길이 기록이 없으면 자막을 맞출 수가 없다 → 그 컷만 다시 만든다
        if ok and not lens_of(out).exists():
            ok, why = False, "줄마다 길이 기록이 없다 — 자막을 못 맞춘다"
        print(f"  컷{c['n']:>2} [{'·'.join(w for w, _ in turns)}] {c['text'][:30]}")
        if ok:
            print("    (그대로다 — 건너뛴다)")
            made += 1
            continue
        # ⭐ 이름은 어긋났어도 **같은 지문**의 소리가 있으면 그것을 옮겨 쓴다
        #    (컷을 끼워 넣어 번호가 밀렸을 때 — 값이 안 든다)
        #    ⚠️ 줄마다 길이를 적어 둔 쪽지(.len.json)도 **같이** 옮긴다.
        #       안 옮기면 자막을 못 맞춰 그 컷만 다시 만들게 된다.
        if sig in kept and sig in kept_len:
            out.write_bytes(kept[sig])
            lens_of(out).write_bytes(kept_len[sig])
            reuse.stamp(out, sig)
            print("    (이름만 밀렸다 — 그대로 옮겨 쓴다 · 0원)")
            made += 1
            continue
        if why:
            print(f"    ⚠️ {why} — 다시 만든다")
        # ⭐ 한 컷 안에서 두 사람이 주고받으면 목소리를 따로 만들어 이어 붙인다
        parts = []
        for i, (w, t, v, r, how) in enumerate(plan):
            one = d / f"c{c['n']:02d}_{i}.wav"
            # 지시가 있으면 구글이 권하는 모양 그대로 (지시 → 쌍점 → 큰따옴표)
            style = f'{how} 다음 큰따옴표 안의 말만 그대로: "{t}"' if how else None
            got = tts.say(t, v, r, 0.0, one, style=style)
            if not got or not Path(got).exists():
                raise Short90Error(f"컷{c['n']} {w} 소리를 못 만들었다")
            parts.append(Path(got))
        # ⭐⭐ 2026-08-31 손님: "대사 목소리와 자막이 시간차가 발생."
        #    자막 바뀌는 때를 **글자 수로 짐작**하고 있었다. 그런데 실제로
        #    말하는 데 걸리는 시간은 글자 수와 안 맞는다(사람마다 속도가
        #    다르고 쉼도 있다). 게다가 컷 길이에는 여운(PAD)까지 들어 있어
        #    자막이 통째로 늘어났다 — 그래서 첫 줄이 오래 남고 둘째 줄이
        #    목소리보다 늦게 떴다.
        #    → 여기서 **줄마다 진짜 길이**를 재서 적어 둔다. 짐작을 없앤다.
        lens_of(out).write_text(
            json.dumps([round(dur_of(x), 3) for x in parts]), encoding="utf-8")
        if len(parts) == 1:
            parts[0].replace(out)
        else:
            lst = d / f"c{c['n']:02d}.txt"
            lst.write_text("".join(f"file '{x.name}'\n" for x in parts),
                           encoding="utf-8")
            run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                 "-i", str(lst), "-c", "copy", str(out)])
            for x in parts:
                x.unlink(missing_ok=True)
            lst.unlink(missing_ok=True)
        reuse.stamp(out, sig)
        made += 1
        print(f"    ✅ {out.name} ({dur_of(out):.1f}초)")
    print(f"\n■ 소리 {made}/{len(doc['cuts'])}줄")
    return 0 if made == len(doc["cuts"]) else 1


# ── ③ 자막 그림 ───────────────────────────────────────────────
def wrap(d, text, font, max_w):
    lines, cur = [], ""
    for word in str(text).split():
        t = (cur + " " + word).strip()
        if cur and d.textlength(t, font=font) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


ONE_LINE_MIN = 70                # 한 줄로 만들려고 여기까지는 줄여 본다


def fit(d, text, size_max, max_w, max_h, one_line=False):
    """칸에 들어갈 때까지 글자를 줄인다. 어르신용이라 SUB_MIN 아래로는 안 줄인다.

    ⭐ one_line — **한 토막은 한 줄이 훨씬 낫다.** 두 줄로 접히면 한 박자가
       두 덩어리로 보여 툭툭 끊긴다. 그래서 토막 자막은 조금 작아지더라도
       (ONE_LINE_MIN 까지) 한 줄에 넣는 쪽을 먼저 찾는다. 그래도 안 되면
       아래의 보통 방식으로 내려간다.
    """
    if one_line:
        for size in range(size_max, ONE_LINE_MIN - 1, -2):
            f = ImageFont.truetype(str(FONT_SUB), size)
            if d.textlength(text, font=f) <= max_w and size * SUB_GAP <= max_h:
                return f, [text], size
    for size in range(size_max, SUB_MIN - 1, -2):
        f = ImageFont.truetype(str(FONT_SUB), size)
        lines = wrap(d, text, f, max_w)
        if len(lines) <= SUB_LINES and len(lines) * size * SUB_GAP <= max_h:
            return f, lines, size
    f = ImageFont.truetype(str(FONT_SUB), SUB_MIN)
    return f, wrap(d, text, f, max_w)[:SUB_LINES], SUB_MIN


def overlay(c, out, turn=None, now=None, mark=""):
    """컷 하나(또는 그 안의 한 차례)의 자막·이름표를 투명 그림으로 그린다.

    now  — 지금 말하고 있는 **낱말 번호** (0부터). None 이면 전부 흰색.
    mark — 왼쪽 위에 늘 띄울 작은 글 ("32억 상속 사건 · 1편"). 큰 제목 카드는
           첫 2.5초만 뜨므로, 중간에 들어온 사람을 위해 이것을 계속 둔다.
    """
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # 아래쪽 어둡게 — 그림 위에 흰 글자를 얹어도 읽히게 (서서히 진해진다)
    scrim = Image.new("RGBA", (W, H - SCRIM_TOP), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    # ⚠️ 맨 아래(1920)에서 가장 진해지게 두면 **자막이 있는 자리(1300~1620)가
    #    아직 옅다.** 밝은 그림 위에서 글자가 묻힌다 — 자막 칸 아래쪽에서
    #    이미 가장 진하도록 잡는다.
    span = H - SCRIM_TOP
    full = max(1, SUB_BOT - SCRIM_TOP)
    for y in range(span):
        a = int(255 * SCRIM_MAX * min(1.0, y / full) ** 1.2)
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    img.alpha_composite(scrim, (0, SCRIM_TOP))

    d = ImageDraw.Draw(img)
    # 채널 이름 (오른쪽 위, 조용하게)
    mf = ImageFont.truetype(str(FONT_NAME), MARK_SIZE)
    d.text((W - SIDE, MARK_Y), CHANNEL, font=mf, fill=(255, 255, 255, 168),
           anchor="ra")
    # ⭐ 드라마 이름과 몇 편인지 (왼쪽 위, 채널 이름과 같은 크기로 늘)
    #   ⚠️ 밝은 그림 위에서도 읽히게 얇은 검은 테두리를 준다.
    if mark:
        d.text((SIDE, MARK_Y), str(mark), font=mf,
               fill=GOLD_BRIGHT[:3] + (SERIES_ALPHA,), anchor="la",
               stroke_width=3, stroke_fill=(0, 0, 0, 170))

    who, text = turn if turn else ("나레이션" if is_narr(c) else c["kind"], c["text"])

    # 이름표 — 대사만 (나레이션은 말하는 사람이 없다)
    #   ⭐ 왼쪽 금색 세로 막대 + 왼쪽 맞춤 글자 + 검은 테두리.
    #     막대 높이는 **글자가 실제로 차지하는 높이**를 재서 맞춘다 —
    #     이름이 두 글자든 세 글자든 늘 글자와 나란하다.
    if who != "나레이션":
        nf = ImageFont.truetype(str(FONT_NAME), NAME_SIZE)
        tx = SIDE + NAME_BAR_W + NAME_BAR_GAP
        box = d.textbbox((tx, NAME_Y), who, font=nf, anchor="la")
        d.rectangle([SIDE, box[1] - NAME_BAR_PAD,
                     SIDE + NAME_BAR_W, box[3] + NAME_BAR_PAD], fill=GOLD)
        d.text((tx, NAME_Y), who, font=nf, fill=GOLD_BRIGHT, anchor="la",
               stroke_width=3, stroke_fill=(0, 0, 0, 205))

    # 자막 — **그 토막만** 그린다 (2026-08-31 손님 확정)
    #   now 가 숫자면 그 토막 하나만 화면에 뜬다. 짧으니 글자가 훨씬 크다.
    #   now 가 None 이면 문장 전체 (검사·미리보기용)
    solo = now is not None
    if solo:
        ch = chunks_of(text)
        text = ch[now] if 0 <= now < len(ch) else text
    if solo:
        # ⭐⭐⭐ 2026-09-05 — 토막은 **크기를 안 줄인다.** 토막을 만들 때
        #    이미 한 줄에 들어가게 잘라 두었기 때문이다(chunks_of).
        #    줄이면 토막마다 크기가 튀어 손님이 "글씨가 갑자기 작아진다" 고
        #    하셨다. 낱말 하나가 화면보다 긴 아주 드문 경우에만 줄인다.
        f = ImageFont.truetype(str(FONT_SUB), SUB_FIXED)
        if d.textlength(text, font=f) <= W - SIDE * 2:
            lines, size = [text], SUB_FIXED
        else:
            f, lines, size = fit(d, text, SUB_FIXED, W - SIDE * 2,
                                 SUB_BOT - SUB_TOP, one_line=True)
    else:
        f, lines, size = fit(d, text, SUB_MAX, W - SIDE * 2,
                             SUB_BOT - SUB_TOP, one_line=False)
    step = size * SUB_GAP
    y = SUB_TOP + max(0, ((SUB_BOT - SUB_TOP) - len(lines) * step) / 2)
    k = 0                                    # 몇 번째 낱말까지 그렸나
    space = d.textlength(" ", font=f)
    for ln in lines:
        ws = ln.split()
        wide = sum(d.textlength(w, font=f) for w in ws) + space * (len(ws) - 1)
        x = (W - wide) / 2                   # 줄 전체를 가운데에 놓는다
        for w in ws:
            # 얇은 검은 테두리 — 밝은 그림 위에서도 글자가 안 묻힌다
            d.text((x, y), w, font=f, fill=WHITE, anchor="la",
                   stroke_width=4, stroke_fill=(0, 0, 0, 210))
            x += d.textlength(w, font=f) + space
            k += 1
        y += step
    img.save(out)
    return out


def tail_sub(text):
    """큰 글 아래 작게 붙는 유도 한 줄."""
    return TAIL_SUB_LAST if str(text) == TAIL_LAST else TAIL_SUB_NEXT


def end_card(text, out, alpha=1.0):
    """영상 끝에 뜨는 알림 — "다음 편에 계속" / "완결".

    ⭐⭐ 2026-09-02 손님: "끝날 때 다음화에 계속이 들어가야 하는거 아니야?"
       맞다. 끝까지 본 사람에게만 보이므로, 다음 편으로 잇기에 가장 좋은 자리다.
    ⚠️ 자막(1300~)과 이름표(1214)를 안 건드리는 높이에 둔다. 가운데 정렬.
    """
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(str(FONT_NAME), TAIL_SIZE)
    sf = ImageFont.truetype(str(FONT_NAME), TAIL_SUB_SIZE)
    sub = tail_sub(text)
    x1, y1, x2, y2 = d.textbbox((W / 2, TAIL_Y), str(text), font=f, anchor="ma")
    sy = y2 + 18                                 # 큰 글 바로 아래
    s1, _st, s2, sb = d.textbbox((W / 2, sy), sub, font=sf, anchor="ma")
    x1, x2, y2 = min(x1, s1), max(x2, s2), sb    # 판을 두 줄에 맞춰 넓힌다
    pad_x, pad_y = 46, 26
    # 글자 뒤에 어두운 판을 깔아 밝은 그림 위에서도 읽히게 한다
    plate = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle(
        [x1 - pad_x, y1 - pad_y, x2 + pad_x, y2 + pad_y],
        radius=18, fill=(0, 0, 0, 168))
    img.alpha_composite(plate)
    d = ImageDraw.Draw(img)
    # 금색 가는 줄 — 위아래로 짧게 (시리즈라는 느낌을 준다)
    d.line([(x1 - pad_x + 18, y1 - pad_y + 2), (x2 + pad_x - 18, y1 - pad_y + 2)],
           fill=GOLD, width=3)
    d.text((W / 2, TAIL_Y), str(text), font=f, fill=GOLD_BRIGHT, anchor="ma",
           stroke_width=4, stroke_fill=(0, 0, 0, 210))
    # 유도 한 줄 — 흰색·작게. 큰 글보다 조용해야 한다.
    d.text((W / 2, sy), sub, font=sf, fill=(255, 255, 255, 230), anchor="ma",
           stroke_width=3, stroke_fill=(0, 0, 0, 200))
    if alpha < 1.0:
        img.putalpha(img.split()[3].point(lambda v: int(v * alpha)))
    img.save(out)
    return out


def title_size(parts):
    """편 제목 글자 크기 — **모든 편이 같은 크기**여야 한 시리즈로 보인다.

    ⚠️ 편마다 따로 재면 짧은 편은 크고 긴 편은 작아져, 이어 봤을 때
       세 편이 남남처럼 보인다. 제일 긴 줄에 맞춰 하나로 정한다.
    """
    d = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    max_w = W - (SIDE + TITLE_BAR_W + TITLE_BAR_GAP) - SIDE
    lines = [str(x) for p in parts for x in (p.get("card") or [])]
    size = TITLE_MAX
    while size > TITLE_MIN:
        f = ImageFont.truetype(str(FONT_SUB), size)
        if not lines or max(d.textlength(x, font=f) for x in lines) <= max_w:
            break
        size -= 2
    return size


def title_card(part, out, alpha=1.0, size=None):
    """편 제목을 화면 **위쪽**에 그린다 — 쇼츠에서는 이것이 썸네일 노릇을 한다.

    모양은 인물 이름표와 같은 문법이다(왼쪽 금색 세로 막대 + 왼쪽 맞춤).
    새 디자인을 만들지 않고 이미 쓰는 것을 그대로 써야 세 편이 한 시리즈로
    보인다.

    part — {"no": 2, "label": "32억 상속 사건", "card": ["윗줄", "아랫줄"]}
    alpha — 1.0 이면 또렷하게, 낮을수록 옅게 (사라질 때 쓴다)
    """
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # 위쪽을 살짝 어둡게 — 밝은 그림 위에서도 흰 글자가 읽힌다
    scrim = Image.new("RGBA", (W, TITLE_SCRIM), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    for y in range(TITLE_SCRIM):
        a = int(255 * TITLE_SCRIM_MAX * max(0.0, 1 - y / TITLE_SCRIM) ** 1.4)
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    img.alpha_composite(scrim, (0, 0))

    d = ImageDraw.Draw(img)
    tx = SIDE + TITLE_BAR_W + TITLE_BAR_GAP
    max_w = W - tx - SIDE

    # ⚠️ 2026-09-02 — 여기 있던 작은 금색 줄("32억 상속 사건 · 1")을 뺐다.
    #    같은 말이 **왼쪽 위에 늘** 떠 있게 되어(overlay 의 mark) 두 번 보였다.
    # 큰 두 줄 — 크기는 **시리즈 전체가 같은 값**을 쓴다(title_size).
    #   안 주면 이 편만 보고 잡는다(혼자 그려 볼 때).
    lines = [str(x) for x in part["card"]][:2]
    if size is None:
        size = title_size([part])
    bf = ImageFont.truetype(str(FONT_SUB), size)

    y = TITLE_Y
    top = TITLE_Y
    for ln in lines:
        d.text((tx, y), ln, font=bf, fill=WHITE, anchor="la",
               stroke_width=5, stroke_fill=(0, 0, 0, 215))
        y += size * TITLE_GAP
    # 금색 세로 막대는 작은 줄부터 마지막 줄까지 한 번에 세운다
    d.rectangle([SIDE, top - TITLE_BAR_PAD,
                 SIDE + TITLE_BAR_W, y - size * (TITLE_GAP - 1) + TITLE_BAR_PAD],
                fill=GOLD)

    if alpha < 1.0:
        a = img.split()[3].point(lambda v: int(v * alpha))
        img.putalpha(a)
    img.save(out)
    return out


def meta(doc):
    """⭐ 유튜브에 올릴 **제목·설명·해시태그**를 파일로 뽑는다 (0원).

    ⚠️ 화면에서 본 것과 실제로 올라가는 것이 **반드시 같아야** 한다.
       그래서 관리자 페이지도 이 파일을 보여 주고, 올릴 때도 이 파일을 쓴다.
       두 곳에서 따로 만들면 언젠가 갈라진다.
    """
    import ytmeta                                            # 늦게 부른다
    m = ytmeta.meta90(doc)
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / "meta.json"
    f.write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n",
                 encoding="utf-8")
    print(f"■ {f} — {len(m['parts'])}편")
    for x in m["parts"]:
        print(f"\n  ── {x['part']}편 ──")
        print(f"  제목 ({len(x['title'])}자)\n    {x['title']}")
        print(f"  화면 위\n    {x['card'][0]} / {x['card'][1]}")
        print("  해시태그\n    " + " ".join("#" + t for t in x["tags"]))
        print("  설명\n" + "\n".join("    " + l
                                    for l in x["description"].split("\n")))
    return 0


# ── ④ 조립 ────────────────────────────────────────────────────
def lens_of(wav):
    """그 컷의 **줄마다 소리 길이**를 적어 둔 자리 (자막을 맞추는 데 쓴다)."""
    return Path(wav).with_suffix(".len.json")


# 끊어도 좋은 자리 — 조사·어미로 끝나는 낱말 뒤. 여기서 끊으면 말이 안 갈린다.
BREAK_END = ("은", "는", "이", "가", "을", "를", "에", "서", "로", "와", "과",
             "도", "만", "께", "요", "다", "죠", "군", "네", "까", "지", "터",
             "고", "며", "면", "야", "어", "아", "해", "죄", "라")
# 다음 낱말에 붙어야 하는 꼬리 — 이걸로 끝나면 혼자 두지 않고 같이 넘긴다
#   (관형형: 「헛소리한 / 거야」 「벌인 / 짓이」 처럼 갈리는 것을 막는다)
HANG_END = ("한", "던", "될", "할", "인", "온", "간", "린", "운", "른")
# 인용·관형형 꼬리 — 길어도 다음 낱말에 붙는다
#   (「배상하라는 / 판결」 「만나자는 / 문자」 「취급하는 / 태도」)
QUOTE_END = ("다는", "라는", "자는", "냐는", "하는", "되는", "지는", "이는", "받은")


def hangs(w):
    """다음 낱말에 **붙어야 하는** 말인가 (여기서 끊으면 말이 갈린다).

    ⭐⭐⭐ 2026-09-05 — 「는」·「은」 은 두 가지다. 처음엔 둘 다 무조건 붙였는데,
       그러면 **한국어에서 가장 자연스러운 끊는 자리**가 통째로 막힌다.
       실제로 「몰래 녹음한 행위는 법 / 위반으로」 처럼 엉뚱한 데서 갈렸다.
         · 관형형 — 「맺는 / 소리」 「좋은 / 사람」  → 붙어야 한다
         · 조사   — 「아내는」 「행위는」 「남편은」  → 끊어도 된다
       가르는 잣대(대본 19종을 세어서 정했다): **앞이 한 음절뿐이면 관형형**
       이다(맺는·아는·없는·좋은·모은). 두 음절 이상이면 조사다(아내는·행위는·
       남편은·법원은). 다만 「-다는·-라는·-자는·-하는」 같은 인용형은 길어도 붙는다.
    ⚠️ 헷갈리면 **붙이는 쪽**으로 판단한다. 잘못 붙이면 자막이 조금 짧아질
       뿐이지만, 잘못 끊으면 손님이 말씀하신 "말이 중간에 끊긴다" 가 된다.
    """
    t = str(w).rstrip(",")
    if t.endswith(("는", "은")):
        return len(t) <= 2 or t.endswith(QUOTE_END)
    return t.endswith(HANG_END)


def merge_units(ws):
    """숫자와 단위를 **한 덩어리로 붙인다** — 「삼천만 / 원짜리」로 갈리면
    돈이 얼마인지가 두 화면에 걸친다. 이 채널은 금액이 핵심이다."""
    out = []
    for w in ws:
        if out and w.startswith(UNIT) and (out[-1][-1:].isdigit()
                                           or out[-1].endswith(NUMWORD)):
            out[-1] = out[-1] + " " + w
        else:
            out.append(w)
    return out


def chunks_of(text, max_w=None):
    """한 줄을 **한 화면에 들어가는 토막**으로 나눈다.

    ⭐⭐⭐ 2026-09-05 손님 지시로 셈을 바꿨다.
       옛 방식: 낱말 3개 · 글자 9자로 못을 박고, 넘치면 **글씨를 줄였다.**
                → 자리가 남아도 거기서 끊겨 말이 갈리고, 크기가 토막마다 튀었다.
                  (실측: 한 컷 안에서 104 → 96 → 102)
       새 방식: 글씨 크기는 **고정**(SUB_FIXED). 그 크기로 **한 줄에 들어가는
                만큼** 담고, 넘치면 다음 토막으로 넘긴다.

    ⚠️ 끊는 자리는 **조사·어미 뒤**를 먼저 찾는다. 그냥 넘치는 데서 끊으면
       「당신 차에서 관계 / 맺는 소리가」 처럼 말 한복판이 갈린다.
    ⚠️ 문장 끝(. ? !)에서는 반드시 끊는다. 다음 문장이 딸려 붙으면 호흡이 어긋난다.
    """
    if max_w is None:
        max_w = W - SIDE * 2
    f = ImageFont.truetype(str(FONT_SUB), SUB_FIXED)
    ws = merge_units(str(text).split())
    if not ws:
        return [str(text)]
    sp = f.getlength(" ")

    def wide(items):
        return sum(f.getlength(x) for x in items) + sp * max(0, len(items) - 1)

    # ① 문장 단위로 먼저 자른다
    sents, cur = [], []
    for w in ws:
        cur.append(w)
        if w.endswith((".", "?", "!", "…")):
            sents.append(cur)
            cur = []
    if cur:
        sents.append(cur)

    # ② 문장마다 **들어가는 만큼** 담는다
    out = []
    for sent in sents:
        i = 0
        while i < len(sent):
            j = i + 1
            while j < len(sent) and wide(sent[i:j + 1]) <= max_w:
                j += 1
            if j < len(sent):                # 더 담을 것이 남았다 — 끊는 자리를 고른다
                for k in range(j - 1, i, -1):
                    t = sent[k].rstrip(",")
                    if t.endswith(BREAK_END) and not hangs(t):
                        j = k + 1
                        break
                # 관형형으로 끝나면 혼자 두지 않고 다음 토막에 딸려 보낸다
                while j - 1 > i and hangs(sent[j - 1]):
                    j -= 1
            out.append(" ".join(sent[i:j]))
            i = j
    return [x for x in out if x] or [str(text)]


def syl(t):
    """한국어 글자 수 (자막이 떠 있을 시간을 나누는 잣대)."""
    return max(1, len([x for x in str(t) if not x.isspace()]))


def sub_windows(c, sec, voice):
    """자막 한 줄씩 **언제부터 언제까지** 떠 있을지.

    ⭐⭐ 2026-08-31 손님: "대사 목소리와 자막이 시간차가 발생."
       예전에는 **글자 수로 짐작**해 컷 길이를 나눴다. 두 군데가 어긋난다 —
         ① 글자 수와 실제 말하는 시간은 안 맞는다 (속도·쉼이 사람마다 다르다)
         ② 컷 길이(sec)에는 말이 끝난 뒤의 여운(PAD)과 대본에 적힌 넉넉한
            초까지 들어 있다. 그 비율로 나누면 자막이 **통째로 늘어나서**
            첫 줄이 오래 남고 둘째 줄이 목소리보다 늦게 뜬다.
       이제 소리를 만들 때 적어 둔 **줄마다 진짜 길이**로 나눈다.
       (voice 가 None 이면 — 올린 영상의 소리를 쓰는 컷 — 옛 방식으로 돌아간다)
    """
    turns = turns_of(c)
    real = []
    if voice:
        f = lens_of(voice)
        if f.exists():
            try:
                got = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(got, list) and len(got) == len(turns):
                    # ⚠️ 소리를 SPEED 배로 빨리 감으므로 자막도 그만큼 당긴다.
                    #    안 그러면 자막만 원래 속도로 남아 말과 어긋난다.
                    real = [float(x) / SPEED for x in got]
            except Exception:                                # noqa: BLE001
                real = []
    at, t0 = [], 0.0
    if real:
        for i, d in enumerate(real):
            # 마지막 줄은 여운까지 끌고 간다 (말이 끝나도 글은 남아 있어야 한다)
            t1 = sec if i == len(real) - 1 else min(sec, t0 + d)
            at.append((t0, t1))
            t0 = t1
    else:
        tot = sum(syl(t) for _, t in turns)
        for i, (_, t) in enumerate(turns):
            t1 = sec if i == len(turns) - 1 else t0 + sec * syl(t) / tot
            at.append((t0, t1))
            t0 = t1
    return at


def move_of(c):
    """이 컷의 카메라 움직임 (MOVES 한 줄).

    ⚠️ 컷 번호로 **돌려 가며** 고른다 — 이웃한 컷이 같은 움직임이면 이어
       붙였을 때 안 움직이는 것처럼 보인다. 같은 컷은 늘 같은 움직임이라
       다시 만들어도 화면이 안 달라진다(무작위로 하면 매번 달라진다).
    """
    ring = MOVES_TALK if not is_narr(c) else MOVES_NARR
    return MOVES[ring[(int(c["n"]) - 1) % len(ring)]]


def cut_sec(c, voice, clip):
    """이 컷이 몇 초짜리인가, 그리고 소리를 올린 영상에서 가져오는가.

    ⚠️ 자막 장을 만들려면 컷 길이를 **먼저** 알아야 한다. 그래서 길이 셈을
       cut_video 밖으로 꺼내 두 곳이 같은 값을 쓰게 한다 (따로 세면 어긋난다).
    """
    clip = Path(clip) if clip and Path(clip).exists() else None
    talks = not is_narr(c)
    if clip and talks and has_audio(clip):
        return dur_of(clip), True
    # ⚠️ 예전에는 대본에 적힌 sec 과 견줘 **큰 쪽**을 썼다. 그런데 그 숫자는
    #    Veo 영상 길이(4·6·8초)라 그림 컷에는 뜻이 없고, 말보다 길면 그만큼
    #    화면이 멈춰 있다. 이제 **말 길이가 정한다.**
    return max(MIN_CUT, dur_of(voice) / SPEED + PAD), False


def karaoke(c, sec, voice, d, n, title=None, mark='', tail=''):
    """카라오케 자막 장들 — [(그림, 언제부터, 언제까지), …].

    ⭐⭐ 2026-08-31 손님: "카라오케 자막으로 변경하자."
       한 낱말씩 불이 들어오게 하려면 낱말마다 자막 장이 한 장씩 필요하다.
       낱말이 언제 나오는지는 **그 줄의 진짜 소리 길이**(.len.json)를
       글자 수로 나눠 잡는다 — 컷 안에서 자막이 목소리를 따라가게 한 것과
       같은 잣대다.

    ⚠️ 낱말 시간은 **재는 것이 아니라 나누는 것**이다. 구글 목소리는 낱말이
       언제 나오는지 안 알려 준다. 그래서 글자 수로 고르게 나눈다 — 한 줄
       안에서는 오차가 크지 않다(줄 자체는 진짜 길이에 맞춰 놓았기 때문).
    """
    # ⚠️ 2026-08-31 진짜 크기 시험이 잡았다 — 여기서 폴더를 안 만들고 있었다.
    #    build() 가 미리 만들어 줘서 안 드러났을 뿐, 다른 데서 부르면 죽는다.
    #    "부르는 쪽이 챙겨 주겠지" 는 언젠가 반드시 어긋난다.
    d = Path(d)
    d.mkdir(parents=True, exist_ok=True)
    turns = turns_of(c)
    wins = sub_windows(c, sec, voice)
    out = []
    # ⭐ 편의 **첫 컷**이면 화면 위에 편 제목을 얹는다 (2026-09-01).
    #    세 단계로 옅어지며 사라진다 — 뚝 끊기면 눈에 걸린다.
    if title:
        span = min(TITLE_SEC, max(0.6, sec))
        edges = [span * x for x in (0.0, 0.80, 0.90, 1.0)]
        for k, al in enumerate(TITLE_FADE):
            a, b = edges[k], edges[k + 1]
            if b - a < 0.02:
                continue
            png = d / f"c{n:02d}_title{k}.png"
            title_card(title, png, alpha=al, size=title.get("size"))
            out.append((png, a, b))
    # ⭐ 편의 **마지막 컷**이면 끝에 "다음 편에 계속" / "완결" 을 띄운다
    if tail:
        span = min(TAIL_SEC, max(0.5, sec * 0.5))
        t0 = max(0.0, sec - span)
        step = span * 0.18
        for k, al in enumerate(TAIL_FADE):
            a = t0 + step * k
            b = (t0 + step * (k + 1)) if k < len(TAIL_FADE) - 1 else sec
            if b - a < 0.02:
                continue
            png = d / f"c{n:02d}_tail{k}.png"
            end_card(tail, png, alpha=al)
            out.append((png, a, b))
    for i, ((who, text), (a, b)) in enumerate(zip(turns, wins)):
        parts = chunks_of(text)
        if not parts:
            continue
        span = max(0.05, b - a)
        tot = sum(syl(w) for w in parts)
        t0 = a
        for k, w in enumerate(parts):
            t1 = b if k == len(parts) - 1 else t0 + span * syl(w) / tot
            png = d / f"c{n:02d}_{i}_{k:02d}.png"
            overlay(c, png, (who, text), now=k, mark=mark)
            out.append((png, t0, t1))
            t0 = t1
    return out


def open_bg(c, opener, still, sec, frames):
    """편 첫 컷 배경 — 앞 4초는 Veo 영상, 그 뒤는 그림으로 넘어간다.

    ⚠️ 되돌려 잇지(loop) 않는다. 4초 지점에서 처음으로 툭 튀어 눈에 걸린다.
       그림 쪽 첫 장이 영상의 끝 장과 거의 같으므로(그 그림으로 만든 영상이다)
       0.5초만 겹쳐 넘기면 한 장면처럼 이어진다.
    돌려주는 것: (ffmpeg 입력 조각, 필터 글, 배경 입력 개수)
    """
    vlen = max(0.4, dur_of(opener) or OPEN_SEC)
    src = ["-i", str(opener)]
    scale = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}")
    # ⭐ 그림이 제대로 보일 만큼 안 남으면 — 영상 하나로 컷 전체를 덮는다.
    #    (0.2초짜리 그림은 "영상이 끝나고 사진으로 얼어붙는" 것으로만 보인다)
    if sec - vlen < OPEN_TAIL_MIN and sec <= vlen * OPEN_STRETCH_MAX:
        r = max(1.0, sec / vlen)
        vf = (f"[0:v]{scale},setpts={r:.4f}*PTS,fps={FPS},"
              f"trim=0:{sec:.3f},setpts=PTS-STARTPTS[bg];")
        return src, vf, 1
    olen = min(OPEN_SEC, vlen, max(0.4, sec))
    tail = sec - olen + OPEN_XFADE          # 겹치는 만큼 그림을 길게 뽑는다
    vf = (f"[0:v]{scale},fps={FPS},trim=0:{olen:.3f},"
          f"setpts=PTS-STARTPTS[ov];")
    if tail <= OPEN_XFADE + 0.05:
        # 컷이 짧아 그림이 나올 자리가 없다 — 영상만으로 채운다
        return src, vf.replace("[ov];", "[bg];"), 1
    sw, sh = int(W * ZOOM_SRC), int(H * ZOOM_SRC)
    z0, z1, x0, x1, y0, y1, _nm = move_of(c)
    tf = max(2, int(round(tail * FPS)))
    t = f"(on/{max(1, tf - 1)})"
    z = f"{z0:.4f}+({z1 - z0:.4f})*{t}"
    px = f"{x0:.4f}+({x1 - x0:.4f})*{t}"
    py = f"{y0:.4f}+({y1 - y0:.4f})*{t}"
    src += ["-loop", "1", "-i", str(still)]
    vf += (f"[1:v]scale={sw}:{sh}:force_original_aspect_ratio=increase,"
           f"crop={sw}:{sh},"
           f"zoompan=z='{z}':d={tf}"
           f":x='(iw-iw/zoom)*({px})'"
           f":y='(ih-ih/zoom)*({py})':s={W}x{H}:fps={FPS},"
           f"trim=0:{tail:.3f},setpts=PTS-STARTPTS[st];"
           f"[ov][st]xfade=transition=fade:duration={OPEN_XFADE:.3f}"
           f":offset={max(0.0, olen - OPEN_XFADE):.3f}[bg];")
    return src, vf, 2


def cut_video(c, still, voice, clip, ovs, out, opener=None):
    """컷 하나 → mp4. 손으로 만든 영상(clip)이 있으면 그것을 쓰고, 없으면 그림.

    ⭐⭐ 2026-08-27 손님: "이미지는 중간중간 섞여 있고 동영상도 있어야 돼."
       그래서 소리를 누가 낼지도 컷마다 갈린다 —
         · **대사 컷 + 올린 영상** → 그 영상 안에서 사람이 한국어로 말한다.
           우리 목소리를 덮어씌우면 입과 소리가 어긋난다 → **영상 소리를 쓴다**
         · **나레이션 컷** → 화면에서 아무도 말하지 않는다 → **우리 나레이션**
           (영상을 올렸어도 그 소리는 안 쓴다. 그래야 나레이션이 안 묻힌다)
    """
    clip = Path(clip) if clip and Path(clip).exists() else None
    # ⚠️ 길이는 cut_sec 한 곳에서만 센다. 자막 장을 만드는 쪽도 같은 값을 쓴다.
    sec, use_clip_audio = cut_sec(c, voice, clip)
    if use_clip_audio:
        # ⚠️ 말하는 길이는 **영상이 정한다.** 대본의 초에 맞춰 늘이거나 줄이면
        #    말이 잘리거나 같은 말이 두 번 나온다. 컷 길이 = 영상 길이.
        snd = []                      # 소리는 영상(0번) 안에 있다
        amap = "0:a"
        loop = []                     # 늘일 일이 없으니 되돌려 잇지 않는다
    else:
        snd = ["-i", str(voice)]      # 0=화면 · 자막들 · 마지막이 우리 목소리
        loop = ["-stream_loop", "-1"] if clip else []
    frames = max(2, int(round(sec * FPS)))
    nbg = 1
    if opener:
        # ⭐ 편 첫 컷 — 앞 4초만 진짜 영상, 그 뒤는 그림으로 이어진다.
        #    ⚠️ Veo 가 만든 소리는 안 쓴다. 첫 컷은 나레이션 컷이라 우리
        #       나레이션이 깔려야 한다 (겹치면 둘 다 안 들린다).
        src, vf, nbg = open_bg(c, opener, still, sec, frames)
    elif clip:
        # ⚠️ 올린 영상이 컷보다 짧으면 마지막 그림이 얼어붙는다 — 되돌려 잇는다
        src = [*loop, "-i", str(clip)]
        vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},fps={FPS},trim=0:{sec:.3f},setpts=PTS-STARTPTS[bg];")
    else:
        src = ["-loop", "1", "-i", str(still)]
        # 조금 키운 뒤 천천히 움직인다 — 원본 크기에서 바로 줌하면 덜덜 떨린다.
        # ⚠️ 2배로 키우면 컷 하나에 6초씩 걸려 너무 느리다. 1.4배면 또렷하고
        #    속도는 3분의 2다.
        sw, sh = int(W * ZOOM_SRC), int(H * ZOOM_SRC)
        z0, z1, x0, x1, y0, y1, _nm = move_of(c)
        # on = 지금 몇 번째 프레임인가. 0 에서 frames 까지 고르게 간다.
        t = f"(on/{max(1, frames - 1)})"
        z = f"{z0:.4f}+({z1 - z0:.4f})*{t}"
        # 가로·세로는 **남는 자리 안에서** 움직인다. 줌이 클수록 자리가 넓다.
        px = f"{x0:.4f}+({x1 - x0:.4f})*{t}"
        py = f"{y0:.4f}+({y1 - y0:.4f})*{t}"
        vf = (f"[0:v]scale={sw}:{sh}:force_original_aspect_ratio=increase,"
              f"crop={sw}:{sh},"
              f"zoompan=z='{z}':d={frames}"
              f":x='(iw-iw/zoom)*({px})'"
              f":y='(ih-ih/zoom)*({py})':s={W}x{H}:fps={FPS}[bg];")
    # ⭐ 한 컷 안에서 두 사람이 주고받으면 **자막도 차례대로** 바뀌어야 한다.
    #
    # ⭐⭐ 2026-08-31 손님: "대사 목소리와 자막이 시간차가 발생."
    #    예전에는 **글자 수로 짐작**해 컷 길이를 나눴다. 두 군데가 어긋난다 —
    #      ① 글자 수와 실제 말하는 시간은 안 맞는다 (사람마다 속도·쉼이 다르다)
    #      ② 컷 길이(sec)에는 말이 끝난 뒤의 여운(PAD)과 대본에 적힌 넉넉한
    #         초까지 들어 있어, 그 비율로 나누면 자막이 통째로 늘어난다.
    #         → 첫 줄이 오래 남고, 둘째 줄이 목소리보다 **늦게** 뜬다.
    #    이제 소리를 만들 때 적어 둔 **줄마다 진짜 길이**로 나눈다.
    #    (올린 영상의 소리를 쓰는 컷은 우리 목소리가 아니므로 옛 방식 그대로)
    #    이제 자막 장은 **낱말마다 한 장**이고, 각자 자기 시간대를 달고 온다
    #    (karaoke 가 만들어 준다). 여기서는 그 시간대에만 얹어 주면 된다.
    chain = "[bg]"
    for i, (_png, a, b) in enumerate(ovs):
        nxt = f"[v{i}]" if i < len(ovs) - 1 else "[v]"
        chain_in = chain
        # ⚠️ 배경이 둘일 수도 있다(영상 + 그림). 자막 장 번호는 그만큼 민다 —
        #    안 밀면 자막이 배경 그림 위에 얹히는 게 아니라 배경을 밀어낸다.
        vf += (f"{chain_in}[{i + nbg}:v]overlay=0:0:format=auto"
               f":enable='between(t,{a:.3f},{b:.3f})'{nxt};")
        chain = nxt
    vf = vf.rstrip(";")
    ovin = []
    for o, _a, _b in ovs:
        ovin += ["-i", str(o)]
    # 소리 입력 번호는 화면(0) + 자막 장수 뒤부터다
    if not use_clip_audio:
        amap = f"{nbg + len(ovs)}:a"
    run(["ffmpeg", "-y", "-v", "error", *src, *ovin, *snd,
         "-filter_complex", vf,
         # ⭐ 소리를 여기서 빨리 감는다 (atempo). 목소리를 다시 만들면 값이
         #   나가지만 조립은 0원이다. 올린 영상의 소리는 손대지 않는다.
         "-map", "[v]", "-map", amap,
         "-af", ("apad" if use_clip_audio else f"atempo={SPEED:.3f},apad"),
         "-t", f"{sec:.3f}", "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
         "-shortest", str(out)])
    return sec


def bgm_path():
    """깔 배경음악 파일. 없으면 None (그때는 음악 없이 그냥 간다)."""
    f = ROOT / "assets" / "bgm" / f"{BGM}.mp3"
    return f if f.exists() else None


def music(src, out):
    """말소리 아래에 배경음악을 깐다. 음악이 없으면 그대로 옮긴다.

    ⚠️ 음악이 말을 덮으면 아무 소용이 없다. **말이 나오는 동안에는 음악을
       눌러 준다**(sidechaincompress). 사람이 라디오에서 하는 그 일이다.
    ⚠️ 화면은 다시 만들지 않는다(-c:v copy) — 다시 만들면 화질이 한 번 더
       깎이고 시간도 오래 걸린다. 소리만 새로 얹는다.
    """
    b = bgm_path()
    sec = dur_of(src)
    if not b or sec <= 0:
        if b is None:
            print(f"  ⚠️ 배경음악 assets/bgm/{BGM}.mp3 이 없다 — 음악 없이 간다")
        shutil.copyfile(src, out)
        return out
    fade = max(0.0, sec - BGM_OUT)
    vf = (
        # 말소리를 둘로 나눈다 — 하나는 그대로 쓰고, 하나는 음악을 누르는 데 쓴다
        f"[0:a]asplit=2[voice][key];"
        f"[1:a]volume={BGM_VOL},atrim=0:{sec:.3f},asetpts=PTS-STARTPTS,"
        f"afade=t=in:st=0:d={BGM_IN},afade=t=out:st={fade:.3f}:d={BGM_OUT}[bed];"
        # 말이 나오면 음악을 눌러 준다 (말 없는 자리에서만 올라온다)
        f"[bed][key]sidechaincompress=threshold=0.02:ratio=12:attack=15:"
        f"release=450[duck];"
        # ⚠️⚠️ amix 는 기본으로 **입력 수만큼 나눈다** — 그냥 섞으면 말소리가
        #    5.5dB 작아진다(실측). 음악을 깔았더니 말이 더 안 들리면 거꾸로다.
        #    normalize=0 으로 끄고, 넘치는 봉우리는 alimiter 가 잡는다.
        f"[voice][duck]amix=inputs=2:duration=first:dropout_transition=0:"
        f"normalize=0,alimiter=limit=0.95[a]"
    )
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
         "-stream_loop", "-1", "-i", str(b),
         "-filter_complex", vf, "-map", "0:v", "-c:v", "copy",
         "-map", "[a]", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
         "-t", f"{sec:.3f}", str(out)])
    print(f"  ♪ 배경음악 {b.name} — 말이 나오면 저절로 눌린다")
    return out


def parts_of(doc):
    """편 목록. 편 수는 **대본이 정한다** — 2편이든 4편이든 여기는 안 고친다.

    ⚠️ 편 나누기가 없는 옛 대본도 돌아가야 한다 → 통째로 한 편으로 본다.
    """
    ps = [dict(x) for x in (doc.get("parts") or [])]
    if ps:
        return ps
    ns = [c["n"] for c in doc["cuts"]]
    return [{"no": 1, "cuts": [min(ns), max(ns)],
             "yt_title": doc.get("yt_title") or doc.get("title") or "",
             "card": [doc.get("title") or "", doc.get("hook") or ""]}]


def part_cuts(doc, part):
    a, b = part["cuts"]
    return [c for c in doc["cuts"] if a <= c["n"] <= b]


def part_file(doc, no):
    """그 편의 완성 영상 자리. 이름에 편 번호가 들어가야 따로 올릴 수 있다."""
    return OUT / f"{doc.get('sid', 'S90')}_part{int(no)}.mp4"


# ⚠️⚠️⚠️ 이 채널이 실제로 겪은 일이다 (2026-09-01) —
#    60초 이하로 만든 쇼츠 여섯 편은 **전부** 1,209~1,554회가 나왔는데,
#    127초짜리 한 편은 5시간 반 동안 **조회수 0** 이었다. 쇼츠 피드가 아예
#    안 태운 것이다. 규정상 3분까지 쇼츠지만, 이 채널에서 검증된 것은
#    60초 이하뿐이다. 그래서 넘으면 **크게** 알린다.
PART_MAX_SEC = 59.5

# ── ⭐⭐⭐ 편 첫 장면만 진짜 영상으로 (2026-09-04 손님 지시) ──────
#    손님: "각 편당 첫번째 씬만 영상으로 나오고 그 다음씬부터는 이미지로."
#    맞는 자리다. 편이 셋이면 **독립된 스와이프 판정이 셋**이고, 그 판정은
#    첫 1~2초에 갈린다. 게다가 2·3편의 첫 컷은 지금 앞 컷 그림을 옮겨 쓰고
#    있어(0원 아끼려고) 1편을 본 사람에게는 "봤던 화면"으로 시작한다.
#
#    ⚠️ 반드시 **그 컷 그림을 넣어 움직이게 한다**(image-to-video).
#       글로만 새로 그리면 인물 얼굴이 컷2부터와 달라져 오히려 싸구려가 된다.
#    ⚠️ 4초면 된다. 스와이프 판정 구간을 다 덮는다. 8초는 값만 두 배고
#       (편당 940원) 판정이 이미 끝난 구간을 산다.
#    ⚠️ 첫 컷은 9~10초라 4초로는 다 못 채운다. 되돌려 잇지(loop) 않는다 —
#       4초 지점에서 화면이 튀어 눈에 걸린다. 그림으로 **부드럽게 넘긴다**.
OPEN_SEC = 4.0                   # Veo 에게 살 길이 (초)
OPEN_XFADE = 0.5                 # 영상 → 그림으로 넘어가는 시간
# ⭐⭐⭐ 2026-09-05 손님: "3화 앞에는 영상부터 나와야 하는데, 이미지 나온후
#    영상 나왔다가 **또 같은 이미지가 나와.**"
#    편 첫 컷이 4.2초인데 영상이 4초다. 0.2초 남은 자리에 그림이 다시 떠서
#    "영상이 끝나고 사진으로 얼어붙는" 것처럼 보였다. 그림이 **제대로 보일
#    만큼 남지 않으면**(OPEN_TAIL_MIN) 그림을 아예 안 쓰고 영상을 조금 늘려
#    컷 전체를 덮는다. 늘리는 폭은 눈에 안 띄는 데까지만(OPEN_STRETCH_MAX).
OPEN_TAIL_MIN = 1.0              # 그림이 이만큼은 남아야 그림으로 넘어간다
OPEN_STRETCH_MAX = 1.15          # 영상을 늘려도 되는 최대 배율 (15%)
OPEN_RATIO = "9:16"              # 화면이 세로로 꽉 차므로 세로로 받는다
# 값이 나가는 일이라 **꺼진 채로** 둔다. 관리자 화면에서 켜야 돈다.
OPEN_VIDEO = os.environ.get("VT_OPEN_VIDEO", "").strip() in ("1", "예", "on")


def build_part(doc, part, stills_d, voice_d, clips_d, parts_d):
    """한 편을 조립한다 → build/s90/<SID>_part<N>.mp4"""
    cuts = part_cuts(doc, part)
    label = doc.get("series_label") or doc.get("title") or ""
    # ⚠️ 크기는 **편 하나가 아니라 전체**를 보고 정한다 — 그래야 세 편이 같다.
    #    only 로 한 편만 다시 만들어도 나머지 편과 크기가 어긋나지 않는다.
    head = {"no": part["no"], "label": label, "card": part["card"],
            "size": title_size(parts_of(doc))}
    # ⭐ 왼쪽 위에 늘 뜨는 작은 표시 — 중간에 들어온 사람도 무슨 이야기의
    #    몇 번째인지 안다 (큰 제목 카드는 첫 2.5초만 뜨고 사라진다)
    mark = f"{label} · {part['no']}편"
    # ⭐ 마지막 편이면 "완결", 아니면 "다음 편에 계속"
    nos = [int(x["no"]) for x in parts_of(doc)]
    tail = TAIL_LAST if int(part["no"]) == max(nos) else TAIL_NEXT
    print(f"\n■ {part['no']}편 — {part['card'][0]} / {part['card'][1]} "
          f"({len(cuts)}컷)")
    total, made = 0.0, []
    for i, c in enumerate(cuts):
        n = c["n"]
        still = stills_d / f"c{n:02d}.png"
        voice = voice_d / f"c{n:02d}.wav"
        clip = clips_d / f"c{n:02d}.mp4"
        if not still.exists() and not clip.exists():
            raise Short90Error(f"컷{n} 그림이 없다 — 먼저 stills 를 돌린다")
        if not voice.exists():
            raise Short90Error(f"컷{n} 소리가 없다 — 먼저 voice 를 돌린다")
        # ⭐ 카라오케 — 낱말마다 자막 장 한 장. 컷 길이를 먼저 알아야 하므로
        #    길이 셈(cut_sec)을 여기서 한 번 하고, cut_video 도 같은 값을 쓴다.
        # ⭐ 편 첫 컷이면 앞 4초를 Veo 영상으로 연다 (있을 때만 · 2026-09-04)
        opener = open_dir() / f"c{n:02d}.mp4"
        opener = opener if (i == 0 and opener.exists()) else None
        sec0, uca = cut_sec(c, voice, clip if clip.exists() else None)
        ovs = karaoke(c, sec0, None if uca else voice, OUT / "ov", n,
                      title=head if i == 0 else None, mark=mark,
                      tail=tail if i == len(cuts) - 1 else "")
        out = parts_d / f"c{n:02d}.mp4"
        sec = cut_video(c, still, voice, clip if clip.exists() else None, ovs,
                        out, opener=opener)
        total += sec
        made.append(out)
        if opener:
            how = f"편 첫 장면 영상 {OPEN_SEC:g}초 → 그림"
        elif not clip.exists():
            how = "그림"
        elif is_narr(c):
            how = "영상 + 우리 나레이션"
        else:
            how = "영상 (그 안에서 말한다)" if has_audio(clip) else "영상 + 우리 목소리"
        print(f"  컷{n:>2} [{c['kind']:<4}] {sec:>5.2f}초 ({how})"
              + ("  ← 편 제목" if i == 0 else "")
              + (f"  ← {tail}" if i == len(cuts) - 1 else ""))

    # ⚠️ concat 목록 안의 경로는 **목록 파일이 있는 자리 기준**이다. 파일 이름만
    #    적으면 옆 폴더에 있는 컷을 못 찾는다 (시험이 바로 잡아 줬다).
    lst = OUT / f"parts{part['no']}.txt"
    lst.write_text("".join(f"file '{x.relative_to(OUT)}'\n" for x in made),
                   encoding="utf-8")
    joined = OUT / f"joined{part['no']}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(joined)])
    final = part_file(doc, part["no"])
    music(joined, final)
    joined.unlink(missing_ok=True)       # 음악 얹기 전 판은 남길 까닭이 없다
    got = dur_of(final)
    # ⭐ 만든 사실을 상태 파일에 적는다 — 관리자 페이지가 여기서 길이를 읽는다
    import shortstate                                        # noqa: E402
    shortstate.mark_made(doc.get("sid") or "S90", part["no"], got)
    print(f"  ▶ {final.name} — {got:.1f}초 "
          f"({final.stat().st_size / 1e6:.1f}MB)")
    if got > PART_MAX_SEC:
        print(f"  ⚠️⚠️ {got:.0f}초 — **60초를 넘었다.** 이 채널은 60초 이하만"
              f" 조회수가 나왔다(127초 편은 0회였다). 컷을 옮겨 나누십시오.")
    elif got < 15:
        print(f"  ⚠️ {got:.0f}초 — 너무 짧다. 컷이 빠지지 않았는지 보십시오.")
    return got


def build(doc, only=None):
    """편마다 하나씩 만든다. only 를 주면 그 편만 (나머지는 손대지 않는다)."""
    stills_d, voice_d = OUT / "stills", OUT / "voice"
    clips_d = OUT / "clips"
    parts_d = OUT / "parts"
    parts_d.mkdir(parents=True, exist_ok=True)
    (OUT / "ov").mkdir(parents=True, exist_ok=True)

    ps = parts_of(doc)
    if only:
        want = {int(x) for x in only}
        bad = want - {int(x["no"]) for x in ps}
        if bad:
            raise Short90Error(f"그런 편이 없다: {sorted(bad)}")
        ps = [x for x in ps if int(x["no"]) in want]
    print(f"■ 「{doc['title']}」 {len(doc['cuts'])}컷 · "
          f"{len(ps)}편 조립" + (" (고른 편만)" if only else ""))
    secs = [build_part(doc, x, stills_d, voice_d, clips_d, parts_d) for x in ps]
    print("\n■ 다 됐다 — " + " · ".join(
        f"{x['no']}편 {t:.0f}초" for x, t in zip(ps, secs)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what",
                    choices=["stills", "open", "voice", "build", "all", "meta"])
    # ⭐ 2026-09-01 — 편마다 따로 만들 수 있어야 한다. 안 주면 전부 만든다.
    #    (그림·목소리는 편이 함께 쓰므로 늘 통째로 본다 — 나눠도 값이 같다)
    ap.add_argument("--part", default="",
                    help="만들 편 (예: 2 또는 1,3). 비우면 전부")
    # ⚠️ 사건은 프로그램이 뜰 때 정해진다(DOC 를 그때 잡기 때문이다).
    #    그래서 여기서는 **받은 값이 다르면 알려만** 주고, 진짜 지정은
    #    VT_SID 환경값으로 한다 — 워크플로가 그렇게 넘긴다.
    ap.add_argument("--sid", default="",
                    help="어느 사건인가 (환경값 VT_SID 와 같아야 한다)")
    a = ap.parse_args()
    if a.sid and a.sid.strip().upper() != SID:
        print(f"❌ 사건이 어긋난다 — 받은 것 {a.sid.upper()} · 지금 쓰는 것 {SID}\n"
              f"   VT_SID={a.sid.upper()} 로 넘겨 주십시오")
        return 2
    only = [int(x) for x in a.part.replace(" ", "").split(",") if x] or None
    try:
        doc = load()
        # ⭐ meta 는 돈이 안 나간다 — 만들기와 따로 부를 수 있어야 한다
        #   (관리자 페이지가 올릴 글을 미리 보여 줄 때 이것만 부른다)
        if a.what == "meta":
            return meta(doc)
        if a.what in ("stills", "all"):
            if stills(doc):
                return 1
        # ⭐ 편 첫 장면 영상 — **켰을 때만** 돈다 (값이 나간다).
        #    그림 다음, 목소리 앞이다: 그림을 넣어 움직이게 하기 때문이다.
        if a.what == "open" or (a.what == "all" and OPEN_VIDEO):
            if openers(doc):
                return 1
        elif a.what == "all":
            print("■ 편 첫 장면 영상 — 끔 (그림으로 갑니다 · 0원)")
        if a.what in ("voice", "all"):
            if voices(doc):
                return 1
        if a.what in ("build", "all"):
            if build(doc, only=only):
                return 1
            # 영상이 나왔으면 올릴 글도 같이 만들어 둔다 (0원)
            meta(doc)
        return 0
    except (Short90Error, ST.StillError, cost.MonthlyCapReached) as e:
        print(f"❌ {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
