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

from PIL import Image, ImageChops, ImageDraw, ImageFont

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
INTRO_SIZE = 46         # 처음 나오는 사람의 관계 한 줄 (이름 옆 · 어르신 눈에 읽히게)
INTRO_GAP = 16
INTRO_ABOVE = 42        # 이름이 먼저인 이름표 — 관계 한 줄을 이름 위에 (2026-10-02)
CHAP_Y, CHAP_SIZE = 128, 34   # 화면 위 대목 표시 (마크 아래 가운데)
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
# ⭐⭐⭐ 2026-10-02 손님: "대사 사이사이에 쉬는 공간 없이 가서" — 1분 전부 영상(all_video)은
#    목소리 앞뒤 무음을 잘라 두고(tools/drama60.py) 여운도 이만큼만 둔다.
PAD_TIGHT = 0.12


def gap_of(doc):
    """말과 말 사이 쉼(초) — 전부 영상 드라마만 대본이 정한다.

    ⭐⭐⭐ 2026-10-02 손님: "말과 말 사이에 0.5초 정도는 남겨도 괜찮아." (S94 v5 · gap 0.5)
       처음엔 "쉬는 공간 없이"(0.12초)였다. 대본에 gap 이 없으면 그 값 그대로다."""
    try:
        return max(0.0, float(doc.get("gap"))) if doc.get("gap") is not None else PAD_TIGHT
    except (TypeError, ValueError):
        return PAD_TIGHT
MIN_CUT = 2.2                    # 아무리 짧아도 이만큼은 보여 준다(깜빡임 방지)
# ⭐ 2026-09-02 손님: "1.2배속으로 바꿔."
#    1.08 → 1.20. 자막 시각도 이 값으로 나누므로(sub_windows) 함께 당겨진다 —
#    여기 한 곳만 고치면 목소리와 자막이 같이 빨라진다.
#    ⚠️ 목소리를 다시 만들지 않는다. 조립할 때 빨리 감는다(atempo) → 0원.
SPEED = 1.28                     # 말 빠르기 (2026-10-02 손님: "1.28배로 가자")
# ⭐⭐⭐ 2026-10-02 손님: "발음 뭉개지지 않게끔 … 방지하는 것도 코드에 넣고" (핵심 규칙)
#    뭉개짐은 지금까지 두 번 났다. 둘 다 **빨리 감기를 겹쳐 건** 탓이다
#    (2026-08-08 1.12×1.2=1.34배 · 2026-08-22 1.35배). 그래서 세 겹으로 막는다.
#    ① 상한 — 목소리를 만들 때 걸린 배속 × 조립 배속이 SPEED_MAX 를 넘지 않는다
#       (말투 결 '담백하게' 는 1.12배로 만든다 → 조립은 1.28/1.12 ≈ 1.14배만 건다)
#    ② 한 번만 — 조립할 때 **한 번** 건다. 이미 빨라진 소리를 또 감지 않는다
#    ③ 자음을 살리는 감기 — atempo 대신 rubberband(transients=crisp ·
#       formant=preserved). 자음의 터지는 소리를 뭉개지 않고 늘이고 줄인다.
#       ffmpeg 에 없으면 atempo 로 물러선다(깃허브 러너에는 있다).
SPEED_MAX = 1.28                 # tts.RATE_MAX 와 같은 값 — 넘기면 한국어 자음이 무너진다
_RB = None


def baked_rate():
    """목소리를 **만들 때** 이미 걸린 배속 (말투 결이 정한다 · 기본 1.0)."""
    try:
        import tts                                           # 늦게 부른다
        return max(1.0, float(tts.style_of().get("rate") or 1.0))
    except Exception:                                        # noqa: BLE001
        return 1.0


def speed():
    """조립할 때 걸 배속 — 만들 때 걸린 배속과 곱해 SPEED_MAX 를 넘지 않는다."""
    return max(1.0, min(SPEED, SPEED_MAX / baked_rate()))


def has_rubberband():
    global _RB
    if _RB is None:
        try:
            r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                               capture_output=True, text=True)
            _RB = " rubberband " in r.stdout
        except OSError:
            _RB = False
    return _RB


def tempo_filter(k):
    """소리를 k 배로 빨리 감는 필터 한 줄 (높낮이는 그대로)."""
    if abs(k - 1.0) < 0.005:
        return "anull"
    if has_rubberband():
        return (f"rubberband=tempo={k:.4f}:transients=crisp:detector=compound:"
                f"formant=preserved:pitchq=quality:channels=together")
    return f"atempo={k:.4f}"

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
    # ⭐⭐⭐ 2026-09-20 손님: "카메라 무빙인데 … 그냥 줌인이랑 줌아웃밖에
    #    없잖아." 실측(S93 대사 컷 21개) — **전부** 이 둘만 번갈아 나왔다.
    #    "옆으로 훑으면 얼굴이 잘린다" 는 안전장치가 대사 컷의 무빙을
    #    통째로 둘로 줄여 버린 것이다.
    #    → 대사 컷에도 위 2·3·4·5번을 **폭을 절반으로 줄여** 쓴다(손님 선택
    #      "좌우 이동도 추가·변화 폭 최대"). 절반이면 화면 가운데 있는
    #      얼굴이 프레임 밖으로 밀려날 자리가 좁아 안전하면서도, 나레이션과
    #      거의 같은 만큼(6가지) 다양해진다.
    #    ⚠️ 나레이션 것(2~5번)의 **절반 값**이어야 한다 — 그대로 베끼면
    #       원래 문제(옆으로 훑어 얼굴이 잘림)가 되돌아온다.
    (1.06, 1.16, 0.56, 0.44, 0.49, 0.51, "다가가며 살짝 왼쪽으로"),
    (1.06, 1.16, 0.44, 0.56, 0.51, 0.49, "다가가며 살짝 오른쪽으로"),
    (1.12, 1.12, 0.50, 0.50, 0.42, 0.58, "살짝 위에서 아래로"),
    (1.20, 1.10, 0.47, 0.53, 0.56, 0.44, "살짝 물러서며 위로"),
]
# 나레이션은 사람이 없거나 작아 옆으로 크게 훑어도 괜찮다 — 6번 전부 쓴다.
# 대사 컷은 사람 얼굴이 주인공이라 **폭을 줄인 6~9번**까지만 더한다.
MOVES_TALK = (0, 1, 6, 7, 8, 9)
MOVES_NARR = (0, 2, 4, 1, 3, 5)

# ── ⭐⭐⭐ 2026-09-19 — **한 컷을 둘로 잘라 보여 주던 것을 되돌린다.**
#    그날 낮에 넣었다가 그날 저녁에 뺐다. 손님:
#      "이렇게 줌을 두 번 하는 거는 굉장히 어색하고 **더 이미지인 걸
#       부각하는 것 같다**."
#    맞는 말씀이고 까닭이 분명하다 — 같은 그림을 겹쳐 넘기면 **새 정보가
#    0**이다. 눈은 "화면이 바뀌었다" 보다 "아까 그 사진을 또 보네" 를 먼저
#    읽는다. 그래서 사진임을 감추기는커녕 **드러낸다.**
#
#    ⚠️ 진짜 병은 따로 있었다. 컷이 오래 머무는 것이 아니라 **컷마다 구도가
#       전부 같은 것**이었다 — 그림 프롬프트가 "허리 위 미디엄" 과 "빈 방
#       와이드" 두 가지뿐이고, tools/build_short90.py 의 연출(shot_of)은
#       **영상 프롬프트에만** 이어져 있어 그림에는 한 프레임도 안 닿았다.
#       증상을 건드리면 이렇게 더 나빠진다. 병을 고쳐야 한다.
#    → 한 컷은 **한 프레이밍**이다. tools/linger_check.py 가 지킨다.

# ── ⭐⭐⭐ 정지 그림을 **살아 있게** 한다 (2026-09-17 손님 지시) ────────
#    손님: "나레이션은 등장인물 이미지나 배경이미지만 나오고 카메라 줌인,
#           줌아웃, 흔들림, 무빙이나 모션 등으로 영상효과를 주면 비용이
#           절감되고 영상처럼 보일 것 같은데."
#
#    무빙(켄번즈)은 **이미 하고 있다**(위 MOVES). 그런데도 사진 티가 나는
#    까닭은 무빙이 없어서가 아니라 **화면이 얼어 있어서**다 —
#    밀고 당겨도 프레임끼리 픽셀이 한 개도 안 바뀐다. 진짜 영상은 눈 깜빡임·
#    빛 일렁임·필름 알갱이 때문에 매 프레임이 미세하게 다르다.
#
#    실측(1초 · 프레임 간 평균 밝기차)
#        지금       0.000   ← 완전히 얼어 있다
#        알갱이 얹음 0.265   ← 매 프레임이 다르다
#
#    ⚠️ 흔들림(shake)은 **일부러 안 넣는다.** 정지 그림을 흔들면 시차가 없는
#       것이 더 도드라지고(판때기가 통째로 흔들린다), 손에 들고 보는 쇼츠에서
#       화면이 흔들리면 멀미를 유발해 오히려 이탈 요인이 된다.
#    ⚠️ 아주 약하게만 준다. 세게 주면 압축이 망가져 용량만 커지고 지저분해진다.
LIVE_GRAIN = "noise=alls=6:allf=t"
# 램프가 아주 미세하게 숨 쉬는 정도 (±0.4%). 눈에 '보이는' 것이 아니라
# '얼어 있지 않다' 고 느끼게 하는 몫이다.
LIVE_BREATH = "eq=brightness='0.004*sin(2*PI*t/3)':eval=frame"
LIVE = f"{LIVE_GRAIN},{LIVE_BREATH}"

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
    # ⚠️ 예전에는 60·70대 남자가 **Alnilam** 이었다 — 나레이션과 같은 소리다.
    #    노인이 말할 때마다 나레이션이 말하는 것처럼 들린다. 갈라 놓는다.
    ("여", "60대"): "Gacrux",    ("남", "60대"): "Schedar",
    ("여", "70대"): "Sulafat",   ("남", "70대"): "Rasalgethi",
}


def voice_of(who, doc):
    """그 사람의 목소리 — **나이대·성별이 정한다.**

    ⭐⭐⭐ 2026-09-20 손님: "나이 보고 목소리 고르게 고쳐."
       예전에는 이름표(VOICE)를 **먼저** 봤다. 그래서 핵심 다섯(아내·남편·
       내연녀·딸·변호사)은 대본이 나이를 뭐라고 적든 늘 같은 목소리였다 —
       예순의 아내도, 서른의 아내도 50대 소리로 말했다.
       → 이제 나이대·성별로 고르고, **이름표는 나이를 모를 때의 기본값**이다.
       (나이 기본값은 story90.PEOPLE_BASE 한 곳에 있다 — 두 벌로 두지 않는다)

    ⚠️ 나레이션 목소리는 **누구에게도 안 준다.** 겹치면 등장인물이 말하는지
       나레이션이 말하는지 귀로 구별이 안 된다.
    """
    if who == "나레이션":
        return VOICE["나레이션"]
    v = (ST90.people_of(doc) or {}).get(who) or {}
    got = VOICE_BY.get((str(v.get("sex") or "").strip(),
                        str(v.get("age") or "").strip()))
    if not got:
        got = VOICE.get(who)                 # 나이를 모르면 이름표로
    if not got or got == VOICE["나레이션"]:
        got = VOICE_BY[(str(v.get("sex") or "여"), "40대")]
    return got


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


def has_speech(path):
    """이 영상 안에서 **사람이 실제로 말하는가**.

    ⭐⭐⭐ 2026-09-12 손님: **"왜 대사 치는 부분인데 음성 목소리가 안 나오는데."**
       까닭: 여기 바로 위 has_audio 는 **소리 트랙이 붙어 있는지**만 본다.
       Veo 는 말을 안 하고 방 안 소리(room tone)만 담은 영상을 내보낼 때가
       있다 — 우리가 지문에 "with only the quiet room tone of the location
       underneath" 라고 시켜서 넣게 한 그 소리다. 트랙은 멀쩡히 있으니
       has_audio 는 통과다. 그러면 cut_sec 이 "영상 안에서 말한다" 고 판단해
       우리 목소리를 안 얹고, 그 컷은 **통째로 조용해진다.** 워크플로는
       초록불이라 아무도 모른다.
       → "소리가 있는가" 가 아니라 **"말이 있는가"** 를 묻는다.
         재는 자리는 자막을 맞출 때 쓰는 speech_span 과 **같은 자**다
         (따로 재면 자막과 소리 판단이 어긋난다).
    """
    if not has_audio(path):
        return False
    return speech_span(path)[1] is not None


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


def open_prompt(c, sec=None):
    """편 첫 장면용 프롬프트 — 길이를 맞추고 입을 다물게 한다.

    ⚠️ 2026-09-17 — `sec` 이 생겼다. **전체 영상**(VT_ALL_VIDEO)에서는 컷마다
       사는 길이가 다르기 때문이다. 안 주면 예전 그대로 OPEN_SEC(4초).
    """
    sec = OPEN_SEC if sec is None else sec
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
                          f"{sec:g}-second single continuous take", line))
    out.append(OPEN_START)
    out.append(OPEN_LIPS)
    return "\n".join(out)


def open_sec_of(c):
    """이 컷에 살 길이(초). 전체 영상이면 **컷 길이만큼**, 아니면 4초."""
    if not (ALL_VIDEO or PEOPLE_VIDEO):
        return OPEN_SEC
    return float(talk_sec(turns_of(c)[0][1]))


def open_cuts(doc):
    """진짜 영상으로 만들 **말 없는 컷**(나레이션) 번호.

    ⭐⭐⭐ 2026-09-17 손님: "아예 전체를 다 영상으로 만드는 버전도 하나 추가해줘."
       · 평소       : 편마다 **첫 컷** 하나 (입 다문 4초)
       · 전체 영상  : 그 편의 **나레이션 컷 전부**, 각자 컷 길이만큼
       대사 컷은 여기서 안 센다 — talk_cuts 가 따로 맡는다(입이 움직여야 한다).
    ⚠️ 전체 영상은 이 둘(나레이션 + 대사)을 **같이** 켜서 만든다.
    """
    if PEOPLE_VIDEO:
        # 사람이 서 있는 나레이션 컷만. 빈 장소는 그림 + 켄번즈로 둔다
        return [c["n"] for c in doc.get("cuts") or []
                if is_narr(c) and (c.get("who") or [])]
    if ALL_VIDEO:
        # ⚠️ 무료 스톡이 이미 있는 컷은 사지 않는다 — 값이 두 번 나간다
        return [c["n"] for c in doc.get("cuts") or []
                if is_narr(c)
                and not (stock_dir() / f"c{c['n']:02d}.mp4").exists()]
    return [part_cuts(doc, p)[0]["n"] for p in parts_of(doc) if part_cuts(doc, p)]


def open_dir():
    return OUT / "open"


# ── ⭐⭐⭐ 대사 컷을 영상으로 (2026-09-09 손님 지시) ────────────────
#    손님: "나레이션은 모두 이미지로 대체하고, 대사 부분만 영상으로 제작하는
#           방식이 더 나을 것 같아. 나레이션을 충분히 넣어 이해를 높이고
#           대사 부분은 영상으로 제작해서 등장인물에 몰입도를 강화."
#
#    2026-09-09 시험 구매(S91 컷21 · 706원)로 **한국어 발화가 쓸 만하다**는
#    것을 눈과 귀로 확인한 뒤에 붙인다. 그 전에는 붙이지 않았다.
#
#    ⚠️ 소리는 **Veo 가 만든 것을 쓴다.** 우리 TTS 로 덮지 않는다 —
#       덮으면 입과 소리가 어긋난다. 2026-08-23 에 운영자가 두 판을 귀로
#       비교하고 구글 쪽을 고른 기록이 src/vprompt.py:127 에 있다.
#       cut_video() 는 이미 그렇게 되어 있다(대사 컷 + 소리 있는 영상이면
#       영상 소리를 쓰고 컷 길이도 영상이 정한다).
#
#    ⚠️⚠️ **같은 인물을 너무 여러 컷 사지 않는다.** Veo 에는 목소리를 지정하는
#       수단이 없어서, 같은 인물이라도 클립마다 다른 사람처럼 들릴 수 있다.
#       클립 수가 곧 목소리가 흔들릴 기회 수다.
# ⭐⭐⭐ 2026-09-17 손님: "아예 전체를 다 영상으로 만드는 버전도 하나 추가해줘.
#    근데 내 생각에는 일단 이미지를 만들고 해야 하니까 그렇게 한다라는 걸 적어줘."
#    맞는 말씀이다. 이 시스템은 **그림을 첫 프레임으로 넣어 움직이는** 방식
#    (image-to-video)이라 그림이 반드시 먼저다. 그림 없이는 openers 가 멈춘다.
#
#    전체 영상 = 나레이션 컷(openers) + 대사 컷(talkers) 을 **같이** 켠 것이다.
#    새 갈래를 만들지 않는다 — 갈래가 늘면 값 막는 자리를 또 잊는다
#    (실제로 2026-09-10 에 openers·talkers 두 갈래가 다 뚫려 있었다).
#    ⚠️ 값이 크다. S93 기준 한 편 약 7,800원 · 네 편 약 31,300원.
#       그래서 화면에서 **편 하나씩** 만들게 하고, 한 번 실행 뚜껑이 막는다.
ALL_VIDEO = os.environ.get("VT_ALL_VIDEO", "").strip() in ("1", "예", "on")
# ⭐⭐⭐ 2026-09-17 손님 선택 — **인물이 나오는 컷만** 영상으로.
#    "전체" 는 사물·장소까지 다 사서 24,226원이 든다. 그런데 시청자가
#    가짜라고 느끼는 것은 빈 방이 아니라 **얼어붙은 사람 얼굴**이다.
#    서류·도장 클로즈업은 실제 드라마도 거의 안 움직인다 — 그림이 맞다.
#    → 인물 컷만 사면 8,704원. 값은 3분의 1인데 오히려 더 드라마 같다.
PEOPLE_VIDEO = os.environ.get(
    "VT_PEOPLE_VIDEO", "").strip() in ("1", "예", "on")
# 전체 영상이면 대사 컷도 당연히 영상이다 (따로 켜 달라고 하지 않는다)
# ⚠️ 열쇠를 **읽는 자리는 한 줄**로 둔다 — 검사가 "읽는 자리가 하나뿐인가"
#    를 글자로 세기 때문이다(두 곳에서 읽으면 한쪽만 끄고 껐다고 믿게 된다).
_TALK_ENV = os.environ.get("VT_TALK_VIDEO", "").strip() in ("1", "예", "on")
# ⭐⭐⭐ 2026-09-20 손님 선택 — **결정적 순간만** 영상으로 (편마다 한 컷).
#    손님: "카메라 구도가 너무 단조로운데." 구도는 그림으로 풀었지만
#    '카메라가 진짜로 움직이는' 느낌은 그림으로는 못 만든다. 그 느낌이 가장
#    필요한 자리 — 편의 마지막 대사 컷 하나씩만 산다.
#    ⚠️ 고르는 규칙은 talkplan.key_cuts 한 곳에 있다(여기서 안 센다).
_KEY_ENV = os.environ.get("VT_KEY_VIDEO", "").strip() in ("1", "예", "on")
TALK_VIDEO = ALL_VIDEO or PEOPLE_VIDEO or _TALK_ENV or _KEY_ENV
# ⭐⭐⭐ 2026-09-10 — 고르는 규칙은 **src/talkplan.py 한 곳**에만 둔다.
#    여기와 화면(worker.js)이 따로 세다가, 화면이 2,824원이라고 적고 실제로는
#    12,936원이 나가는 꼴이 됐다. 세는 자리를 하나로 만든다.
#    손님 설계: "나레이션은 모두 이미지, 대사 부분만 영상." 그래서 제한 없음이
#    기본이다 — 편마다 1컷으로 막아 둔 것은 설계가 아니라 내 임의였다.
import talkplan                                             # noqa: E402
# ⚠️⚠️ 2026-09-12 — 여기 위의 `ST` 는 **still**(그림) 모듈이다. story90 이
#    아니다. 이름이 비슷해 `ST.scene_extra(...)` 라고 적었다가 stills 이
#    통째로 죽었다(AttributeError). **글만 읽는 검사는 그걸 못 잡는다** —
#    돌려 보는 검사(short90_test)가 잡았다. 그래서 이름을 갈라 둔다.
import story90 as ST90                                      # noqa: E402
TALK_PER_PART = talkplan.TALK_PER_PART
TALK_PER_PERSON = talkplan.TALK_PER_PERSON
TALK_OK_SEC = talkplan.TALK_OK_SEC
TALK_HOT = talkplan.TALK_HOT
# 대사 뒤에 남기는 여운(초). 말이 끝난 뒤 이만큼만 두고 잘라 낸다.
# ⚠️⚠️ 2026-09-10 — 이 줄이 **한 번 사라진 적이 있다.** 위 블록을 갈아끼우며
#    같이 날아갔는데, talk_trim 은 영상을 살 때만 도는 자리라 검사 72개가
#    전부 초록불이었다 (값이 나가는 순간 NameError 로 죽었을 것이다).
#    → tools/name_check.py 가 이제 이런 것을 잡는다.
TALK_TAIL = 0.45
# 말이 끝난 뒤에도 자막이 이만큼 더 남는다 (읽을 시간을 준다).
# ⚠️ TALK_TAIL 과 같은 값이면 자막이 컷 끝과 딱 붙어 뚝 끊긴다.
SUB_TAIL = 0.35
_SPAN_CACHE = {}                 # 같은 영상을 두 번 재지 않는다


def stock_dir():
    """⭐ 2026-09-17 — Pexels 무료 실사 영상을 받아 둔 자리 (값 0원).

    **사람이 한 명도 없는 나레이션 컷**에만 쓴다. 우리 색감을 입혀 받으므로
    AI 그림 컷과 색이 안 튄다. 받는 것은 src/stock_video.py 가 한다.
    """
    return OUT / "stock"


def video_dir():
    """⭐ 1분 전부 영상(all_video) — 컷마다 옴니가 만든 영상 (tools/drama60.py).
    ⚠️ 손님이 손으로 올린 영상(clips/)·대사 영상(talk/)과 섞지 않는다."""
    return OUT / "video60"


def talk_dir():
    """⚠️ 손님이 손으로 올린 영상(clips/)과 **섞지 않는다.** 워크플로가
       clips/ 를 통째로 덮어썼다 되올리므로, 섞으면 손 올린 것이 조용히
       사라진다."""
    return OUT / "talk"


def talk_sec(text):
    """그 대사에 살 길이(초) — talkplan 이 정한다."""
    return talkplan.talk_sec(text)


def talk_cuts(doc):
    """영상으로 살 대사 컷들 — 고르는 규칙은 talkplan 에 있다.

    ⚠️ 여기서 따로 세지 않는다. 화면·대본짓기·실제 제작이 **같은 셈**을
       써야 화면에 적힌 값이 진짜 값이 된다.

    ⭐⭐⭐ 2026-09-10 — **60초 벽을 사기 전에 지킨다.**
       대사 컷을 영상으로 바꾸면 그 컷 길이가 목소리 길이가 아니라 영상
       길이(4·6·8초)가 된다. S92 는 그것만으로 2편·3편이 54초에서 66초로
       뛴다. 이 채널에서 60초를 넘은 편은 조회수가 **0** 이었다.
       만든 뒤에 경고를 찍는 것으로는 늦다 — 그때는 값을 이미 다 쓴 뒤다.
       → talkplan.fit 이 넘칠 편의 **긴 대사 컷부터 그림으로 남긴다.**
    """
    keep, why = talkplan.fit(doc)
    for w in why:
        print(f"  ⏸ {w}")
    return keep


def talk_prompt(c, sec):
    """대사 컷용 지문 — 길이만 우리가 사는 값으로 맞춘다.

    ⚠️ 편 첫 장면(open_prompt)과 달리 **입을 다물게 하지 않는다.** 여기서는
       말하는 것이 목적이다. 지문에는 이미 DIALOGUE·VOICE·AUDIO 가 들어
       있다(tools/build_short90.py 가 넣는다) — 그대로 둔다."""
    txt = str(c.get("veo") or c.get("still") or "")
    txt = re.sub(r"\b\d+(?:\.\d+)?-second single continuous take",
                 f"{int(sec)}-second single continuous take", txt)
    # ⭐⭐⭐ 2026-09-11 손님: **"말이 너무들 느려."**
    #    느린 것은 모델 탓이 아니라 **우리가 시킨 것**이었다. AUDIO 줄에
    #    "real spontaneous speech with uneven rhythm and short breaths between
    #     phrases"(구절마다 숨 쉬며 들쭉날쭉하게) 가 들어 있다. 그대로 읽으니
    #    4초짜리 대사가 6~8초로 늘어졌다.
    #    ⚠️ 그 상수(src/series.AUDIO_FIX)는 **16화 대본 48컷에도 박혀 있다.**
    #       거기를 고치면 저장해 둔 대본이 통째로 "AUDIO 줄이 없다" 로 걸린다
    #       (tools/script_check.py 가 그렇게 잡아 줬다). 그래서 **대사 영상
    #       지문에서만** 그 대목을 바꿔 끼운다.
    txt = txt.replace(
        "real spontaneous speech with uneven rhythm and short breaths "
        "between phrases",
        "spoken at a brisk natural conversational pace, no pauses between "
        "phrases and no drawn-out syllables, every consonant crisp and "
        "clearly articulated")
    return txt


def speech_span(path):
    """소리에서 **말이 시작한 시각과 끝난 시각**을 찾는다 — (시작, 끝).

    ⭐⭐⭐ 2026-09-10 손님(두 번째): "아직도 대사 음성이랑 자막이 맞지 않아."
       첫 판은 ffmpeg 의 silencedetect(-35dB 고정)를 썼다. 그런데 Veo 영상에는
       **방 안 소리(room tone)가 늘 깔려 있다** — 우리가 지문에 "with only the
       quiet room tone of the location underneath" 라고 시켜서 넣은 것이다.
       그 배경음이 -35dB 보다 크면 silencedetect 는 **조용한 구간을 하나도
       못 찾는다.** 그러면 (0, 전체) 가 되어 자막이 컷 전체에 퍼진다 —
       고치기 전과 똑같아진다.
       실측:
           배경음 무음 · -50dB → 시작 1.20 · 끝 3.20  (맞음)
           배경음 -34dB · -24dB → 시작 0.00 · 끝 4.70  (못 찾음)
       ⚠️ 내 시험이 **디지털 무음**을 썼기에 늘 통과했다. 시험이 너무 쉬우면
          없는 것을 있다고 말해 준다.

       → 고정 dB 를 버리고, 그 소리의 **자기 배경음 대비**로 잰다.
         50ms 씩 크기를 재서, 조용한 쪽(하위 10%)보다 훨씬 큰 구간을 말로 본다.
         배경음이 크든 작든 똑같이 걸린다.
    """
    try:
        import array
        HZ, WIN = 8000, 0.05
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-vn",
             "-ac", "1", "-ar", str(HZ), "-f", "s16le", "-"],
            capture_output=True).stdout
        a = array.array("h")
        a.frombytes(raw[: len(raw) // 2 * 2])
        if not a:
            return 0.0, None
        step = int(HZ * WIN)
        lv = []
        for i in range(0, len(a) - step + 1, step):
            chunk = a[i:i + step]
            lv.append((sum(x * x for x in chunk) / step) ** 0.5)
        if len(lv) < 6:
            return 0.0, None
        srt = sorted(lv)
        floor = srt[max(0, int(len(srt) * 0.10))]      # 배경음
        peak = srt[int(len(srt) * 0.95)]               # 말소리
        # 말이랄 게 없으면(배경음과 봉우리가 비슷하면) 손대지 않는다
        if peak <= max(floor * 2.5, 1.0):
            return 0.0, None
        cut = floor + (peak - floor) * 0.20            # 배경음보다 확실히 큰 자리
        on = [i for i, v in enumerate(lv) if v >= cut]
        if not on:
            return 0.0, None
        beg, fin = on[0] * WIN, (on[-1] + 1) * WIN
        dur = dur_of(path) or (len(lv) * WIN)
        beg = max(0.0, min(beg, dur))
        fin = max(beg + 0.3, min(fin, dur))
        if fin - beg < 0.4:
            return 0.0, None
        if beg > dur * 0.6:                            # 앞이 6할 넘게 조용할 리 없다
            return 0.0, fin
        return beg, fin
    except Exception:                                        # noqa: BLE001
        return 0.0, None


def speech_end(path):
    """말이 끝난 시각만 (옛 이름 — 부르는 데가 있어 남겨 둔다)."""
    return speech_span(path)[1]


def talk_trim(path, sec):
    """말이 끝난 뒤 남는 조용한 시간을 잘라 낸다.

    ⚠️⚠️ 이것이 **자막이 어긋나는 것을 막는 자리**다. 대사 컷은 영상 소리를
       쓰므로 컷 길이 = 영상 길이인데, 6초를 사도 대사는 4.5초에 끝난다.
       그러면 자막 한 장이 6초 내내 떠 있어 말이 끝난 뒤에도 1.5초를 더
       남는다 (손님이 2026-08-31 에 지적하신 그 증상).
       → 말 끝 + 여운 만큼만 남기고 자른다. 자를 것이 없으면 그대로 둔다.
    """
    end = speech_end(path)
    if not end:
        return False
    want = min(sec, end + TALK_TAIL)
    if sec - want < 0.35:            # 자를 만큼이 아니면 그냥 둔다
        return False
    tmp = path.with_suffix(".trim.mp4")
    try:
        run(["ffmpeg", "-y", "-v", "error", "-i", str(path),
             "-t", f"{want:.3f}", "-c", "copy", str(tmp)])
        tmp.replace(path)
        print(f"    ✂️ 말이 {end:.1f}초에 끝나 {want:.1f}초로 자른다 "
              f"(자막이 뒤에 남지 않게)")
        return True
    except Exception:                                        # noqa: BLE001
        tmp.unlink(missing_ok=True)
        return False


def talkers(doc):
    """대사 컷을 Veo 로 영상으로 만든다 (image-to-video · 소리는 Veo 것).

    ⚠️ 값이 나간다. 그래서 openers() 와 같은 규칙을 지킨다 —
       켜야만 돌고 · 만들기 전에 얼마인지 적고 · 지문이 같으면 안 만들고
       (0원) · 실패하면 그 컷만 **그림으로** 돌아간다.
    """
    # ⭐⭐⭐ 2026-09-30 — **2분 드라마는 옴니 플래시로 산다** (손님 확정).
    #    그 컷 그림을 첫 장면으로, 화면 인물의 시트 칸을 참조로 넣는다.
    #    대사는 옴니가 직접 말한다 (손님 선택: "옴니 목소리 그대로").
    #    안전 검사에 걸리면 첫 장면 없이 **참조만**으로 한 번 더 해 본다
    #    (Veo 의 '씨앗 바꿔 다시' 자리 — 옴니는 씨앗을 안 받는다).
    drama = talkplan.is_drama(doc)
    if drama:
        import omni                                         # 늦게 부른다(열쇠 필요)
        MODEL, FILT, CAP = omni.MODEL, omni.OmniFiltered, omni.RunCapReached
    else:
        import veo                                          # 늦게 부른다(열쇠 필요)
        MODEL, FILT, CAP = veo.MODEL, veo.RaiFiltered, veo.RunCapReached
    d = talk_dir()
    d.mkdir(parents=True, exist_ok=True)
    cs = talk_cuts(doc)
    st = OUT / "stills"
    plan = [(c, c.get("omni_sec") if drama and c.get("omni_sec")
             else talkplan.talk_sec_of(doc, turns_of(c)[0][1])) for c in cs]
    tot = sum(cost.video_krw(MODEL, x) for _, x in plan)
    print(f"■ 대사 장면 영상 {len(plan)}컷 · 최대 약 {tot:,.0f}원")
    # ⭐ 이름이 밀려도 다시 안 사게 — 지문으로 찾아 옮겨 쓴다 (그림·소리와 같은 길)
    kept = salvage(d, ".mp4")
    made, miss = 0, []
    spent, again = 0.0, 0        # spent = 이번에 진짜 나간 값 · again = 0원으로 다시 쓴 것
    for c, sec in plan:
        n = c["n"]
        who, text = turns_of(c)[0]
        out = d / f"c{n:02d}.mp4"
        still = st / f"c{n:02d}.png"
        if not still.exists():
            raise Short90Error(f"컷{n} 그림이 없다 — 먼저 stills 를 돌린다")
        prompt = (c.get("omni") if drama else None) or talk_prompt(c, sec)
        if drama and not c.get("omni"):
            raise Short90Error(f"컷{n} 옴니 지문이 없다 — 대본을 다시 짓는다 "
                               f"(tools/build_short90.py)")
        # ⚠️ 지문에 **그림 내용 전체**와 모델 이름까지 넣는다. 그림이 바뀌거나
        #    모델이 바뀌면 영상도 다시 만들어야 한다.
        sig = talk_sig(c, sec, still, MODEL, prompt)
        # ⭐⭐⭐ 2026-09-14 — **여기서 talk_ok 를 안 쓰고 있었다.**
        #    살리는 장치(그림이 같아 보이면 그대로 쓴다)를 조립하는 쪽
        #    (build_part → talk_ok)에만 넣고, 정작 **돈을 쓰는 이 자리**에는
        #    안 넣었다. 그래서 열 개를 살릴 수 있었는데 전부 "다시 만든다" 로
        #    가서, 여섯 개를 새로 사고(2,822원) 한도에 걸려 멈췄다.
        #    ⚠️ 관문이든 살림이든 **돈이 나가는 자리에 있어야 뜻이 있다.**
        #       같은 잘못을 이 파일에서만 네 번째 한다.
        ok, why = talk_ok(c, out, still)
        print(f"  컷{n:>2} [{who}] {text[:26]}  ({sec}초)")
        if ok:
            print("    (그대로다 — 건너뛴다 · 0원)")
            made += 1
            again += 1
            continue
        if sig in kept:
            out.write_bytes(kept[sig])
            reuse.stamp(out, sig)
            print("    (이름만 밀렸다 — 그대로 옮겨 쓴다 · 0원)")
            made += 1
            again += 1
            continue
        if why:
            print(f"    ⚠️ {why} — 다시 만든다")
        krw1 = cost.video_krw(MODEL, sec)
        # ⭐⭐⭐ 2026-09-10 — **한 번 실행 한도가 여기에 없었다.**
        #    대사 컷이 14개면 12,900원이 나가는데, 이 채널이 정한 한 번 한도는
        #    3,000원이다. 다른 곳(still.py · veo.py)에는 다 걸려 있는데
        #    가장 비싼 이 자리만 뻥 뚫려 있었다.
        #    → 넘으면 **거기서 멈춘다.** 만든 것은 그대로 남고, 다시 누르면
        #      없는 것만 채운다(만든 것은 0원으로 다시 쓴다).
        if spent + krw1 > cost.RUN_KRW:
            print(f"    ⏸ 한 번 실행 한도({cost.RUN_KRW:,.0f}원)에 닿았다 "
                  f"— 여기서 멈춘다. 만든 {made}개는 그대로 남는다.\n"
                  f"       나머지는 **다시 누르면** 이어서 만듭니다 "
                  f"(만든 것은 0원으로 다시 씁니다).")
            miss += [x["n"] for x, _ in plan if x["n"] >= n and x["n"] not in miss]
            break
        # ⭐⭐⭐ 2026-09-14 — 못 만들었을 때 **이미 있던 영상까지 지우고
        #    있었다.** 한도에 걸려 멈춘 컷 여덟 개가 그렇게 사라졌다
        #    (예전에 산 것 · 약 3,760원어치). 돈이 모자라 못 샀다는 것이
        #    이미 산 것을 버릴 까닭이 될 수는 없다.
        #    → 이번에 실제로 건드린 파일만 지운다.
        was = out.stat().st_mtime_ns if out.exists() else None
        # 화면 인물의 시트 칸 (2분 드라마) — 지문의 Image2… 차례와 같다(who 차례)
        refs = [ST.card_path(cards_dir(), ST_NAME.get(w, w))
                for w in (c.get("who") or [])] if drama else []
        if drama and not all(p.exists() for p in refs):
            raise Short90Error(f"컷{n} 인물 시트 칸이 없다 — 인물 시트부터 "
                               f"만든다 (src/castsheet.py make)")
        try:
            if drama:
                omni.make(prompt, [still] + refs, out, sec, task="image_to_video")
            else:
                # ⭐ 씨앗을 **말하는 사람**으로 묶는다. 컷 번호로 묶으면 같은 인물의
                #   여러 컷이 확실히 다른 씨앗을 받아 목소리가 더 흔들린다.
                veo.make_clip(prompt, sec, out, ratio=OPEN_RATIO,
                              seed=veo._seed(doc.get("sid"), who, "talk"),
                              start=still)
        except FILT:
            print(f"    ⚠️ 안전 필터에 걸렸다 — "
                  + ("첫 장면 없이 **참조만**으로 " if drama else "씨앗을 바꿔 ")
                  + f"**한 번만** 다시 해 본다 (약 {krw1:,.0f}원)")
            try:
                if drama:
                    omni.make(c.get("omni_ref") or prompt, refs, out, sec,
                              task="reference_to_video")
                else:
                    veo.make_clip(prompt, sec, out, ratio=OPEN_RATIO,
                                  seed=veo._seed(doc.get("sid"), who, "talk2"),
                                  start=still)
            except Exception as e2:                          # noqa: BLE001
                print(f"    ⚠️ 두 번째도 못 만들었다 ({e2}) — 이 컷은 그림으로 갑니다")
                drop_if_new(out, was)
                miss.append(n)
                continue
        except CAP as e:
            # ⭐ 값이 모자라 멈춘 것이지 **고장이 아니다.** 그림으로 떨어뜨리지
            #   않고 여기서 멈춘다 — 다시 누르면 만든 것은 0원으로 쓰고
            #   없는 것만 이어서 만든다.
            print(f"    ⏸ {e}")
            miss += [x["n"] for x, *_ in plan if x["n"] >= n and x["n"] not in miss]
            break
        except Exception as e:                               # noqa: BLE001
            print(f"    ⚠️ 못 만들었다 ({e})")
            if out.exists() and was is not None and out.stat().st_mtime_ns == was:
                print("       (전에 사 둔 영상은 **그대로 둡니다** — 돈을 버리지 않습니다)")
            else:
                print("       이 컷은 그림으로 갑니다")
            drop_if_new(out, was)
            miss.append(n)
            continue
        # ⭐⭐ 소리가 진짜로 들어 있는지 본다. 무음 영상을 그대로 쓰면 그 컷이
        #    통째로 조용해지고, 워크플로는 초록불이라 아무도 모른다.
        if not has_audio(out):
            print("    ⚠️ 소리가 없는 영상이다 — 이 컷은 그림으로 갑니다")
            drop_if_new(out, was)      # 방금 만든 것이라 치우는 게 맞다
            miss.append(n)
            continue
        # ⚠️ 트랙은 있는데 **말이 없는** 경우가 있다(방 안 소리만). 지워 버리면
        #    이미 낸 값(470원)이 날아가고 다음에 또 사야 한다 — 화면은 멀쩡하니
        #    **화면은 쓰고 우리 목소리를 얹는다.** cut_sec 이 알아서 그렇게 한다.
        if not has_speech(out):
            print("    ⚠️ 영상 안에서 말을 안 한다 — 화면은 쓰고 "
                  "**우리 목소리**를 얹습니다")
        talk_trim(out, sec)
        reuse.stamp(out, sig)
        made += 1
        spent += krw1
    # ⭐⭐⭐ 계획에 없는 옛 영상을 치운다. 안 치우면 조립이 그것을 주워 쓴다
    #    (9/10 에 만든 컷34 가 그렇게 들어갔다 — 8초 통짜에 덜어낸 컷이었다).
    want = {c["n"] for c, _ in plan}
    for f in sorted(d.glob("c*.mp4")):
        try:
            no = int(f.stem[1:])
        except ValueError:
            continue
        if no in want or reuse.by_hand(f):
            continue
        f.unlink(missing_ok=True)
        reuse.sig_file(f).unlink(missing_ok=True)
        print(f"  🧹 컷{no} 영상은 이번 계획에 없다 — 치운다 "
              f"(안 치우면 옛 영상이 그대로 들어간다)")
    print(f"\n■ 대사 장면 {made}/{len(plan)}컷 · 이번에 쓴 값 약 {spent:,.0f}원")
    # ⭐ 아낀 값을 적는다. 아낀 값이 0이면 보관이 안 되고 있다는 뜻이다.
    if plan:
        one = cost.video_krw(MODEL, plan[0][1])
        reuse.note("대사 영상", again, max(0, made - again), one)
    if miss:
        print("  ⚠️⚠️ 그림으로 가는 대사 컷: " + " · ".join(f"컷{n}" for n in miss))
    return 0


def drop_if_new(out, was):
    """못 만들었을 때 **이번에 새로 생긴 파일만** 치운다.

    ⚠️ 예전에는 무조건 지웠다. 그래서 한 푼도 못 쓰고 멈춘 컷의 **이미 사 둔
       영상**까지 사라졌다 (2026-09-14, 여덟 개 · 약 3,760원어치).
       반쪽만 쓰인 쓰레기 파일은 치워야 하지만, **손도 못 댄 옛 파일**은
       그대로 두는 것이 맞다.
    """
    out = Path(out)
    if not out.exists():
        return
    if was is None or out.stat().st_mtime_ns != was:
        out.unlink(missing_ok=True)


def talk_sig(c, sec, still, model=None, prompt=None):
    """그 대사 영상을 **무엇으로 만들었는지** 한 줄로. talkers 와 조립이 같이 쓴다.

    ⭐⭐⭐ 2026-09-11 손님: "제대로 제작이 안된다."
       조립(build_part)이 talk/ 에 **파일이 있으면 그냥 썼다.** 지금 대본의
       계획인지, 언제 만든 것인지 보지 않았다. 그래서 9월 10일에 만든
       컷34 클립(자막 고치기 전 판 · 8.00초 통짜)이 그대로 들어가,
       말이 끝난 뒤 3초를 가만히 서 있는 화면이 됐다. 게다가 그 컷은
       60초 벽 때문에 **덜어낸 컷**이라 이번 계획에 아예 없었다.
       "있으면 쓴다" 는 판단은 예전에도 세 번 사고를 냈다 (src/reuse.py).
       → 지문이 맞을 때만 쓴다. 셈하는 자리를 하나로 둔다.
    """
    # ⭐ 2026-09-30 — 2분 드라마 컷은 옴니로 산다 (대본이 omni 지문을 들고 온다).
    #    만들 때(talkers)와 쓸 때(talk_ok)가 **같은 모델·같은 지문**으로 재야
    #    이미 산 영상을 알아본다 — 어긋나면 멀쩡한 영상을 버리고 또 산다.
    if model is None:
        if c.get("omni"):
            import omni                                      # noqa: E402
            model = omni.MODEL
        else:
            import veo                                       # noqa: E402
            model = veo.MODEL
    if prompt is None:
        prompt = c.get("omni") or talk_prompt(c, sec)
    # ⭐⭐⭐ 2026-09-13 — 지문을 **두 토막**으로 나눈다: "무슨 말을 하는가" 와
    #    "어느 그림에서 나왔는가". 나누는 까닭 —
    #    표시 지우기(wipe_mark)가 stills 를 돌릴 때마다 그림 파일을 다시
    #    저장해서 **바이트가 매번 달라졌다**. 그림은 똑같은데 지문이 깨지니
    #    대사 영상 14개가 통째로 다시 사졌다 (한 번에 6,821원).
    #    표시 지우기는 이제 한 번만 하도록 고쳤지만, 그것만으로는 **이미 사
    #    둔 영상**을 살릴 수 없다. 두 토막으로 두면 앞 토막(말)이 같은지
    #    따로 볼 수 있어서, 뒤 토막(그림)이 어긋났을 때 **그림을 눈으로
    #    맞춰 보고** 살릴 수 있다 (talk_ok 를 보라).
    head = reuse.sig_of(prompt, str(sec), OPEN_RATIO, model)
    tail = reuse.sig_of(Path(still).read_bytes().hex())
    return f"{head}.{tail}"


# 영상 첫 장면과 그림이 **같은 그림인가** 를 재는 잣대.
# 실측(S92 14컷): 같은 그림 3.8~6.7 · 다른 그림 38.6~65.7 — 사이가 넓다.
SAME_PIC = 15.0


def same_picture(clip, still):
    """이 영상은 **이 그림에서 나온 것인가** — 첫 장면을 그림과 견준다.

    ⭐ 바이트가 아니라 **보이는 것**으로 따진다. 영상은 그림을 씨앗으로 넣어
       만들므로 첫 장면은 그 그림과 거의 같다. 그림 파일을 다시 저장해서
       바이트만 달라진 경우와, 그림을 **정말 다시 그린** 경우를 이것으로
       가른다 (앞의 것은 살리고 뒤의 것은 다시 산다).
    """
    try:
        out = Path(clip).with_suffix(".frame.png")
        run(["ffmpeg", "-y", "-v", "error", "-i", str(clip),
             "-frames:v", "1", str(out)])
        a = Image.open(still).convert("RGB")
        b = Image.open(out).convert("RGB").resize(a.size)
        px = ImageChops.difference(a, b).convert("L").resize((64, 114))
        out.unlink(missing_ok=True)
        d = list(px.getdata())
        return sum(d) / len(d)
    except Exception:                                        # noqa: BLE001
        return None


def talk_gaps(doc, cuts=None):
    """**영상이어야 하는데 그림으로 갈** 대사 컷 번호들.

    ⭐⭐⭐ 2026-09-14 손님: "이 부분은 영상이 아니라 이미지로 만들어져 있어.
       다시는 이런 일들이 발생하지 않게 코드 수정해."
       한도에 걸려 못 산 컷 여덟 개가 조용히 그림으로 떨어졌는데, 워크플로는
       초록불이었다. 3편은 대사 네 컷이 전부 그림이라 통째로 슬라이드쇼였다.
       **덜 된 것을 덜 됐다고 말할 수 있어야** 막을 수도, 알릴 수도 있다.

    ⚠️ '전부 그림' 으로 눌렀을 때(TALK_VIDEO 꺼짐)는 빈손을 돌려준다 —
       그건 고장이 아니라 **고른 것**이다.
    """
    if not TALK_VIDEO:
        return []
    keep, _why = talkplan.fit(doc)      # ⚠️ 번호가 아니라 **컷** 을 돌려준다
    st, td = OUT / "stills", talk_dir()
    by = {c["n"]: c for c in doc["cuts"]}
    out = []
    for n in [x["n"] for x in keep]:
        if cuts is not None and n not in cuts:
            continue
        clip, still = td / f"c{n:02d}.mp4", st / f"c{n:02d}.png"
        if not (clip.exists() and still.exists() and talk_ok(by[n], clip, still)[0]):
            out.append(n)
    return sorted(out)


def talk_ok(c, clip, still):
    """이 대사 영상을 지금 대본에 써도 되는가. (된다/안 된다, 왜)"""
    clip, still = Path(clip), Path(still)
    if not clip.exists() or not still.exists():
        return False, ""
    if reuse.by_hand(clip):          # 손으로 올린 것은 손님 것이다 — 늘 이긴다
        return True, ""
    try:
        sec = c.get("omni_sec") or talk_sec(turns_of(c)[0][1])
        want = talk_sig(c, sec, still)
        ok, why = reuse.can_reuse(clip, want)
        if ok:
            return True, ""
        # ⭐⭐⭐ 2026-09-13 — **말이 같고 그림도 같아 보이면 살린다.**
        #    표시 지우기가 그림 파일을 다시 저장해 바이트만 달라진 경우다.
        #    그냥 버리면 멀쩡한 영상 열 개(약 4,700원)를 다시 사게 된다.
        #    ⚠️ 앞 토막(무슨 말을 몇 초로 하는가)이 **똑같을 때만** 본다.
        #       대사가 바뀌었으면 그림이 같아도 못 쓴다 — 입과 말이 어긋난다.
        got = (reuse.sig_file(clip).read_text(encoding="utf-8").strip()
               if reuse.sig_file(clip).exists() else "")
        same_talk = got and "." in got and got.split(".")[0] == want.split(".")[0]
        # ⚠️ 옛 지문(2026-09-13 이전)은 한 토막이라 앞뒤를 가를 수가 없다.
        #    그래서 **그림이 같고 길이가 말이 될 때만** 살린다.
        #    ⚠️⚠️ 길이를 "산 초와 똑같은가" 로 보면 안 된다 — 산 뒤에
        #       talk_trim 이 말 끝의 조용한 자리를 잘라 둔다(4초 → 3.42초).
        #       처음에 그렇게 재서 멀쩡한 다섯 컷을 버릴 뻔했다.
        #       **산 초보다 길지만 않으면** 된다 (8초짜리 옛 통짜를 막는다).
        old_one = (got and "." not in got and dur_of(clip) <= sec + 0.35)
        if same_talk or old_one:
            d = same_picture(clip, still)
            if d is not None and d < SAME_PIC:
                reuse.stamp(clip, want)      # 다음부터는 바로 통과한다
                return True, ""
            if d is not None:
                return False, f"그림이 바뀌었다 (닮음 {d:.0f})"
        return ok, why
    except Exception as e:                                   # noqa: BLE001
        return False, str(e)


def openers(doc):
    """말 없는 컷을 Veo 영상으로 만든다 (image-to-video).

    · 평소      : 편마다 첫 컷 하나 · 4초 (VT_OPEN_VIDEO)
    · 전체 영상 : 나레이션 컷 **전부** · 컷 길이만큼 (VT_ALL_VIDEO)

    ⚠️ 값이 나간다. 그래서 —
       · 켜야만 돈다
       · 만들기 **전에** 얼마인지 적어 준다
       · 지문이 같으면 다시 안 만든다 (0원). 그림이 바뀌면 다시 만든다.
    ⚠️ **그림이 먼저다.** 그림을 첫 프레임으로 넣어 움직이므로, 그림이 없으면
       여기서 멈춘다(아래 Short90Error). 전체 영상도 예외가 아니다.
    """
    import veo                                              # 늦게 부른다(열쇠 필요)
    d = open_dir()
    d.mkdir(parents=True, exist_ok=True)
    ns = open_cuts(doc)
    st = OUT / "stills"
    by_n = {c["n"]: c for c in doc.get("cuts") or []}
    secs = {n: open_sec_of(by_n[n]) for n in ns if n in by_n}
    tot = sum(cost.video_krw(veo.MODEL, s) for s in secs.values())
    what = "전체 영상 · 나레이션 컷" if ALL_VIDEO else "편 첫 장면 영상"
    print(f"■ {what} {len(ns)}개 "
          f"({sum(secs.values()):g}초 · 최대 약 {tot:,.0f}원)")
    made, miss = 0, []
    for n in ns:
        out = d / f"c{n:02d}.mp4"
        still = st / f"c{n:02d}.png"
        if not still.exists():
            raise Short90Error(f"컷{n} 그림이 없다 — 먼저 stills 를 돌린다")
        c = by_n[n]
        sec1 = secs[n]
        krw1 = cost.video_krw(veo.MODEL, sec1)
        # ⚠️ 우리 시스템용 판(veo)을 쓴다. 앱용 판(flow)이 아니다.
        #    ⭐ 말 없는 컷용으로 손본다 — 길이를 맞추고, 입을 다물게 한다.
        prompt = open_prompt(c, sec1)
        # ⚠️ 지문에 **그림 내용까지** 넣는다. 그림이 바뀌면 영상도 바뀌어야 한다.
        sig = reuse.sig_of(prompt, f"{sec1:g}", OPEN_RATIO,
                           reuse.sig_of(still.read_bytes().hex()[:4096]))
        ok, why = reuse.can_reuse(out, sig)
        print(f"  컷{n:>2} {what} ({sec1:g}초 · 약 {krw1:,.0f}원)")
        if ok:
            print("    (그대로다 — 건너뛴다 · 0원)")
            made += 1
            continue
        if why:
            print(f"    ⚠️ {why} — 다시 만든다")
        try:
            veo.make_clip(prompt, int(sec1), out, ratio=OPEN_RATIO,
                          seed=veo._seed(doc.get("sid"), n), start=still)
        except veo.RaiFiltered:
            # ⭐⭐⭐ 2026-09-05 손님: "1화는 앞에 영상이 아닌 이미지야."
            #    까닭은 구글 **안전 필터**였다. 고장이 아니라 그때그때 걸리는
            #    것이라, 씨앗만 바꿔 한 번 더 부르면 통과하는 일이 잦다.
            #    ⚠️ 한 번 더 부르면 값이 또 나간다 — **딱 한 번만** 한다.
            print(f"    ⚠️ 안전 필터에 걸렸다 — 씨앗을 바꿔 **한 번만** "
                  f"다시 해 본다 (약 {krw1:,.0f}원)")
            try:
                veo.make_clip(prompt, int(sec1), out, ratio=OPEN_RATIO,
                              seed=veo._seed(doc.get("sid"), n, "2"),
                              start=still)
            except Exception as e2:                          # noqa: BLE001
                print(f"    ⚠️ 두 번째도 못 만들었다 ({e2}) — 이 컷은 그림으로 갑니다")
                out.unlink(missing_ok=True)
                miss.append(n)
                continue
        except veo.RunCapReached as e:
            # ⭐ 값이 모자라 멈춘 것이지 **고장이 아니다.** 그림으로 떨어뜨리면
            #   손님은 "왜 영상이 안 됐지" 하고 다시 눌러 또 값을 쓴다.
            #   여기서 멈추고, 다시 누르면 만든 것은 0원으로 쓰고 이어서 만든다.
            print(f"    ⏸ {e}")
            miss.append(n)
            break
        except Exception as e:                               # noqa: BLE001
            # ⚠️ 첫 장면 하나가 안 나왔다고 편 전체를 못 만들면 안 된다.
            #    그 컷은 **그림으로** 간다 — 지금까지 하던 그대로다.
            print(f"    ⚠️ 못 만들었다 ({e}) — 이 컷은 그림으로 갑니다")
            out.unlink(missing_ok=True)
            miss.append(n)
            continue
        reuse.stamp(out, sig)
        made += 1
    print(f"\n■ {what} {made}/{len(ns)}개")
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
    drama = talkplan.is_drama(doc)
    # ⭐⭐ 2026-09-10 — 나레이션 컷에는 **얼굴 참조를 안 붙인다.**
    #    붙이면 장소 그림에 그 사람이 들어간다. 지문 조립(still_prompt)도
    #    같은 잣대로 갈린다 — 한쪽만 고치면 지문은 장소인데 참조는 사람인
    #    엇갈린 그림이 나온다.
    # ⭐⭐⭐ 2026-10-01 손님: "나레이션컷에서도 등장인물 얼굴 나오는거로 반영해."
    #    2분 드라마는 나레이션 컷에도 그 순간의 인물이 나온다 → 얼굴 참조를
    #    **붙인다.** 가르는 자리는 지문과 같은 함수 하나(story90.still_who).
    def refs_of(c):
        return [p for p in (ST.card_path(cards_dir(), ST_NAME.get(w, w))
                            for w in ST90.still_who(c, drama)) if p.exists()]

    # ⭐⭐⭐ 2026-09-10 손님: **"장남이라고 해놓고선 등장인물이 아닌 사람이
    #    자꾸 나타나. 등장인물을 등록했으면 등록 인물만 나오게 해."**
    #    까닭은 바로 위 `if p.exists()` 였다. 얼굴 그림이 없으면 **조용히 빼고**
    #    그냥 그렸다. 그런데 지문에는 "PEOPLE: the reference images show 장남"
    #    이 그대로 적혀 있다 — 모델은 "장남을 보여 주는 참조 그림이 있다" 고
    #    듣고는 그림이 없으니 **아무 남자나 지어낸다.**
    #    → 값(132원)도 나가고, 나온 그림은 엉뚱한 사람이라 다시 그려야 한다.
    #      **그리기 전에 막는다.**
    lack = {}
    for c in doc["cuts"]:
        for w in ST90.still_who(c, drama):
            if not ST.card_path(cards_dir(), ST_NAME.get(w, w)).exists():
                lack.setdefault(w, []).append(c["n"])
    # ⭐⭐⭐ 2026-09-12 손님: **"등장인물을 등록했으면 등록 인물만 나오게 해."**
    #    얼굴 그림이 다 있어도, 화면 묘사가 who 보다 사람을 많이 부르면
    #    남는 사람은 참조가 없다 — 모델이 지어낸다. 얼굴이 없는 것과 똑같은
    #    사고인데 자리만 다르다. **값이 나가는 자리에서 같이 막는다.**
    many = []
    for c in doc["cuts"]:
        extra, heads = ST90.scene_extra(c)
        if extra:
            many.append((c["n"], len(heads), c.get("who") or [], c.get("scene")))
    if many:
        raise Short90Error(
            "화면에 **등장인물이 아닌 사람**이 들어 있습니다 — 그리면 생판 "
            "남이 나옵니다.\n"
            + "\n".join(f"   · 컷{n} : 화면 {h}명 vs 등장인물 {len(w)}명"
                        f"({', '.join(w) or '없음'})\n     {sc}"
                        for n, h, w, sc in many)
            + "\n   고치는 길 둘(둘 다 값 0원): ① 그 사람을 who 에 넣는다"
              "  ② 화면 묘사에서 그 사람을 뺀다\n"
              "   python3 tools/edit_line.py --sid <사건> --cut <번호> "
              "--scene \"...\"")
    if lack:
        raise Short90Error(
            "등장인물 얼굴 그림이 없습니다 — 그리면 **엉뚱한 사람**이 나옵니다.\n"
            + "\n".join(f"   · {w} : 컷 {', '.join(str(x) for x in ns)}"
                        for w, ns in lack.items())
            + "\n   관리자 페이지 [① 인물 그림] 에서 그 사람 얼굴을 올린 뒤 "
              "다시 눌러 주십시오.\n"
              "   (얼굴 없이 그리면 값은 값대로 나가고 다시 그려야 합니다)")

    # ⭐⭐⭐ 2026-10-01 — **그림 먼저 확인 → 고칠 컷만 다시** (손님 승인 · 해양생물 쇼츠의
    #    '이미지 먼저 검토, 영상은 그 다음'). 관리자 페이지에서 고른 컷만 새 씨앗으로
    #    다시 그린다. 몇 번째로 다시 그렸는지 남겨 두어(_retake.json · 보관함에 같이
    #    들어간다) 같은 씨앗으로 같은 그림이 또 나오지 않게 한다.
    redo = redo_cuts()
    retake = load_retake(d)
    for c in doc["cuts"]:
        refs = refs_of(c)
        sig = reuse.sig_of(c["still"], *refs)
        ok, _why = reuse.can_reuse(d / f"c{c['n']:02d}.png", sig)
        if (not ok and sig not in kept) or c["n"] in redo:
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
        refs = refs_of(c)
        sig = reuse.sig_of(c["still"], *refs)
        ok, why = reuse.can_reuse(out, sig)
        print(f"  컷{c['n']:>2} {'·'.join(c.get('who') or []) or '—'}")
        again = c["n"] in redo
        if ok and not again:
            print("    (그대로다 — 건너뛴다)")
            made += 1
            continue
        # ⭐ 이름은 어긋났어도 **같은 지문**의 그림이 있으면 그것을 옮겨 쓴다
        #    (컷을 끼워 넣어 번호가 밀렸을 때 — 값이 안 든다)
        if sig in kept and not again:
            out.write_bytes(kept[sig])
            reuse.stamp(out, sig)
            print("    (이름만 밀렸다 — 그대로 옮겨 쓴다 · 0원)")
            made += 1
            continue
        if again:
            retake[str(c["n"])] = int(retake.get(str(c["n"])) or 0) + 1
            print(f"    ↻ 관리자 페이지에서 고른 컷 — 새 씨앗으로 다시 그린다 "
                  f"({retake[str(c['n'])]}번째)")
        elif why:
            print(f"    ⚠️ {why} — 다시 만든다")
        k = int(retake.get(str(c["n"])) or 0)
        ST.gen(c["still"], out, refs=refs, ratio="9:16",
               seed=(ST.seed_of(doc.get("sid") or SID, c["n"]) if not k else
                     ST.seed_of(doc.get("sid") or SID, c["n"], "retake", k)))
        if again:
            save_retake(d, retake)
        # ⚠️ 새로 그렸으면 **가린 표시를 지운다.** 안 지우면 "이미 가렸다" 며
        #    건너뛰는데, 새 그림에서는 상표가 다른 자리에 있을 수 있다.
        out.with_suffix(".scrubbed").unlink(missing_ok=True)
        # ⚠️ 새로 그렸으면 **표시 지우기도 다시** 해야 한다 (2026-09-13)
        out.with_suffix(".wiped").unlink(missing_ok=True)
        reuse.stamp(out, sig)
        made += 1
    print(f"\n■ 그림 {made}/{len(doc['cuts'])}장")
    # ⭐ 얼마를 아꼈는지 적는다 (보관이 조용히 죽으면 여기서 드러난다)
    reuse.note("컷 그림", made - len(plan), len(plan), one)
    # ⭐⭐⭐ 2026-10-01 — 증거 확대 그림 · 이웃 컷 닮음 다시 그리기 (2분 드라마)
    ins_ok = inserts(doc, d)
    if drama:
        redraw_alike(doc, d, refs_of)
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
    return 0 if (made == len(doc["cuts"]) and ins_ok) else 1


RETAKE_LOG = "_retake.json"


def redo_cuts():
    """관리자 페이지에서 '다시 그리기' 로 고른 컷 번호 (VT_REDO_STILLS="3,7")."""
    raw = os.environ.get("VT_REDO_STILLS", "")
    out = set()
    for x in re.split(r"[,\s]+", raw.strip()):
        if x.isdigit() and 1 <= int(x) <= 99:
            out.add(int(x))
    return out


def load_retake(d):
    try:
        got = json.loads((Path(d) / RETAKE_LOG).read_text(encoding="utf-8"))
        return got if isinstance(got, dict) else {}
    except Exception:                                        # noqa: BLE001
        return {}


def save_retake(d, retake):
    (Path(d) / RETAKE_LOG).write_text(json.dumps(retake, ensure_ascii=False) + "\n",
                                      encoding="utf-8")


def insert_file(d, n):
    """컷 n 의 증거 확대 그림 자리 (컷 그림 c07.png 옆에 i07.png)."""
    return Path(d) / f"i{int(n):02d}.png"


def inserts(doc, d):
    """⭐⭐⭐ 2026-10-01 — **증거 확대 그림** (해양생물 쇼츠의 '특징 줌인' · 손님 승인).
    나레이션이 그 물건을 말하는 순간 화면이 이 그림으로 넘어간다 (조립: cut_video).
    물건만 그린다 — 얼굴 참조를 안 붙인다 (사람이 들어오면 안 되는 그림이다).
    지문이 같으면 다시 안 그린다 (0원). 못 그려도 편을 죽이지 않는다 — 그 컷은
    확대 없이 간다 (꾸밈이지 이야기가 아니다). 돌려주는 것: 다 됐는가."""
    want = [c for c in doc["cuts"] if (c.get("insert") or {}).get("still")]
    if not want:
        return True
    one = cost.image_krw(ST.MODEL, ST.SIZE)
    todo = [c for c in want if not reuse.can_reuse(
        insert_file(d, c["n"]), reuse.sig_of(c["insert"]["still"]))[0]]
    print(f"\n■ 증거 확대 그림 {len(want)}장 — 새로 그릴 것 {len(todo)}장 "
          f"· 약 {one * len(todo):,.0f}원")
    ok = True
    for c in want:
        out = insert_file(d, c["n"])
        sig = reuse.sig_of(c["insert"]["still"])
        print(f"  컷{c['n']:>2} 확대 — {c['insert'].get('word', '')}")
        if reuse.can_reuse(out, sig)[0]:
            print("    (그대로다 — 건너뛴다)")
            continue
        try:
            ST.gen(c["insert"]["still"], out, refs=[], ratio="9:16",
                   seed=ST.seed_of(doc.get("sid") or SID, c["n"], "insert"))
            reuse.stamp(out, sig)
            out.with_suffix(".wiped").unlink(missing_ok=True)
        except Exception as e:                                # noqa: BLE001
            print(f"    ⚠️ 못 그렸다 ({e}) — 이 컷은 확대 없이 갑니다")
            ok = False
    return ok


# ⭐⭐⭐ 2026-10-01 — **이웃 컷이 같은 구도로 보이면 그 컷만 한 번 다시** (손님 승인)
#    반려동물 식당 쇼츠에서 가져왔다. 구도 계획(plan_shots)이 크기·방향을 다르게
#    시켜도 그림 모델이 가끔 앞 컷과 거의 같은 화면을 그린다. 그림이 나온 뒤
#    **눈으로 보듯** 견주고(src/lookalike.py), 너무 닮은 컷만 앞 컷을 보여 주며
#    "확실히 다르게" 다시 그린다. 한 편에 lookalike.REDRAW_MAX 장까지.
#    ⚠️ 같은 컷을 두 번 다시 그리지 않는다 — 기록(_alike.json)이 그림 보관함에
#       함께 들어간다. 안 남기면 누를 때마다 또 그려 값이 샌다.
ALIKE_LOG = "_alike.json"
ALIKE_NOTE = ("The LAST reference image is the previous shot of this film. Use it only "
              "to make this frame look clearly different from it: a different shot "
              "size and a different camera angle, exactly as SHOT says. The people "
              "look exactly like their own reference images.")


def redraw_alike(doc, d, refs_of):
    import lookalike                                         # noqa: E402
    logp = Path(d) / ALIKE_LOG
    try:
        done = json.loads(logp.read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        done = {}
    cuts = doc["cuts"]
    hits = []
    for a, b in zip(cuts, cuts[1:]):
        pa, pb = Path(d) / f"c{a['n']:02d}.png", Path(d) / f"c{b['n']:02d}.png"
        if not (pa.exists() and pb.exists()):
            continue
        v = lookalike.likeness(pa, pb)
        sg = reuse.sig_file(pb)
        sig_b = sg.read_text(encoding="utf-8").strip() if sg.exists() else ""
        key = f"c{b['n']:02d}"
        if v is None or v < lookalike.SAME:
            continue
        if (done.get(key) or {}).get("sig") == sig_b:
            print(f"  컷{b['n']} 은 앞 컷과 닮았지만 이미 한 번 다시 그렸다 — 그대로 간다")
            continue
        hits.append((v, a, b, sig_b))
    if not hits:
        print("\n■ 이웃 컷 닮음 — 같은 구도로 보이는 컷 없음 (0원)")
        return
    pick = sorted(hits, key=lambda x: -x[0])[:lookalike.REDRAW_MAX]
    pick.sort(key=lambda x: x[2]["n"])          # 앞 컷부터 — 뒤 컷은 고친 앞 컷을 본다
    one = cost.image_krw(ST.MODEL, ST.SIZE)
    print(f"\n■ 이웃 컷 닮음 {len(hits)}곳 — {len(pick)}장 다시 그린다 "
          f"(약 {one * len(pick):,.0f}원)")
    for v, a, b, sig_b in pick:
        prev_png = Path(d) / f"c{a['n']:02d}.png"
        out = Path(d) / f"c{b['n']:02d}.png"
        print(f"  컷{b['n']} — 컷{a['n']} 과 닮음 {v:.2f} (잣대 {lookalike.SAME})")
        try:
            ST.gen(b["still"] + "\n" + ALIKE_NOTE, out, refs=refs_of(b) + [prev_png],
                   ratio="9:16", seed=ST.seed_of(doc.get("sid") or SID, b["n"], "alike"))
        except Exception as e:                                # noqa: BLE001
            print(f"    ⚠️ 못 그렸다 ({e}) — 그대로 간다")
            continue
        # ⭐ 그 컷 지문 그대로 적는다 — 다음에 누르면 이 그림을 0원으로 다시 쓴다
        reuse.stamp(out, sig_b)
        out.with_suffix(".scrubbed").unlink(missing_ok=True)
        out.with_suffix(".wiped").unlink(missing_ok=True)
        after = lookalike.likeness(prev_png, out)
        done[f"c{b['n']:02d}"] = {"sig": sig_b, "prev": f"c{a['n']:02d}",
                                  "before": round(v, 3),
                                  "after": None if after is None else round(after, 3)}
        print(f"    → 닮음 {v:.2f} → {after if after is None else round(after, 2)}")
    logp.write_text(json.dumps(done, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")


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


def overlay(c, out, turn=None, now=None, mark="", intro=None, alias=None, labels=None,
            bare=False):
    """컷 하나(또는 그 안의 한 차례)의 자막·이름표를 투명 그림으로 그린다.

    now  — 지금 말하고 있는 **낱말 번호** (0부터). None 이면 전부 흰색.
    mark — 왼쪽 위에 늘 띄울 작은 글 ("32억 상속 사건 · 1편"). 큰 제목 카드는
           첫 2.5초만 뜨므로, 중간에 들어온 사람을 위해 이것을 계속 둔다.
    intro — (이름, 관계) — 그 사람이 **처음 나오는 컷**이면 이름표 자리에 이름과
           관계 한 줄을 띄운다 (나레이션 컷이어도). intro_of() 가 정한다.
    alias — {관계 이름: 가명} — 이름표가 "딸 (윤정숙)" 이 된다 (aliases_of).
    bare — 자막 글은 빼고 그늘·마크·이름표·대목 표시만 (말 앞뒤 쉼 · 아래 karaoke).
    labels — {관계 이름: 이름표 글} — 있으면 이것이 이긴다 (labels_of · 「윤정숙 (딸)」).
           이름이 먼저인 이름표(name_first)는 관계 한 줄을 이름 **위에** 얹는다 —
           「윤기철 (배다른 남동생)」 처럼 길어 옆에 붙일 자리가 없다.
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
    #   ⭐ 2026-10-02 — 처음 나오는 사람이면(intro) 나레이션 컷에도 이름표를 띄우고,
    #     이름 옆에 관계 한 줄을 작게 붙인다 ("이복동생 · 아버지가 밖에서 낳은 아들").
    # ⭐ 화면 위 가운데 — 지금 어느 대목인지 (「재판 · 땅주인 주장 ②」 · 2026-10-02 S94 v5)
    #    그림 컷(관계도 등)은 그림에 제목이 있으므로 안 띄운다.
    chap = str(c.get("chapter") or "").strip()
    if chap and not c.get("fig"):
        chapter_chip(img, chap)
        d = ImageDraw.Draw(img)

    tag = who if who != "나레이션" else (intro[0] if intro else "")
    if tag:
        label = ((labels or {}).get(tag)
                 or (f"{tag} ({alias[tag]})" if alias and alias.get(tag) else tag))
        nf = ImageFont.truetype(str(FONT_NAME), NAME_SIZE)
        tx = SIDE + NAME_BAR_W + NAME_BAR_GAP
        box = d.textbbox((tx, NAME_Y), label, font=nf, anchor="la")
        d.rectangle([SIDE, box[1] - NAME_BAR_PAD,
                     SIDE + NAME_BAR_W, box[3] + NAME_BAR_PAD], fill=GOLD)
        d.text((tx, NAME_Y), label, font=nf, fill=GOLD_BRIGHT, anchor="la",
               stroke_width=3, stroke_fill=(0, 0, 0, 205))
        if intro and intro[0] == tag and intro[1] and labels:
            # 이름이 먼저인 이름표 — 관계 한 줄은 이름 바로 **위**에 (흰 글자)
            rf = ImageFont.truetype(str(FONT_NAME), INTRO_ABOVE)
            d.text((tx, box[1] - NAME_BAR_PAD - 12), intro[1], font=rf,
                   fill=(255, 255, 255, 240), anchor="ld",
                   stroke_width=3, stroke_fill=(0, 0, 0, 205))
        elif intro and intro[0] == tag and intro[1]:
            rf = ImageFont.truetype(str(FONT_NAME), INTRO_SIZE)
            rel = f"· {intro[1]}"
            rx = box[2] + INTRO_GAP
            room = W - SIDE - rx
            while d.textlength(rel, font=rf) > room and rf.size > 28:
                rf = ImageFont.truetype(str(FONT_NAME), rf.size - 2)
            d.text((rx, box[3]), rel, font=rf, fill=(255, 255, 255, 235),
                   anchor="ld", stroke_width=3, stroke_fill=(0, 0, 0, 205))

    if bare:
        img.save(out)
        return out

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


def chapter_chip(img, text):
    """화면 위 가운데 작은 띠 — 「재판 · 땅주인 주장 ②」 (금색 테두리 · 어두운 바탕)."""
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(str(FONT_SUB), CHAP_SIZE)
    w = d.textlength(text, font=f)
    h = CHAP_SIZE + 22
    x1, x2 = W / 2 - w / 2 - 22, W / 2 + w / 2 + 22
    plate = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle([x1, CHAP_Y - h / 2, x2, CHAP_Y + h / 2],
                                            radius=h / 2, fill=(14, 18, 26, 200),
                                            outline=GOLD_BRIGHT, width=3)
    img.alpha_composite(plate)
    ImageDraw.Draw(img).text((W / 2, CHAP_Y + 1), text, font=f, fill=GOLD_BRIGHT,
                             anchor="mm")


def labels_of(doc):
    """{관계 이름: 이름표 글}. name_first 면 「윤정숙 (딸)」 (괄호 안은 tag · 없으면 관계 이름),
    아니면 옛 모양 「딸 (윤정숙)」. 가명이 없으면 빈 것 (이름표는 관계 이름 그대로)."""
    out = {}
    for p in doc.get("cast") or []:
        nm, al = str(p.get("name") or ""), str(p.get("alias") or "").strip()
        if not nm or not al:
            continue
        tag = str(p.get("tag") or nm).strip()
        out[nm] = f"{al} ({tag})" if doc.get("name_first") else f"{nm} ({al})"
    return out if doc.get("name_first") else {}


def tail_sub(text):
    """큰 글 아래 작게 붙는 유도 한 줄."""
    return TAIL_SUB_LAST if str(text) == TAIL_LAST else TAIL_SUB_NEXT


def end_card(text, out, alpha=1.0, note=""):
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
    # ⭐ 가명 알림 (2026-10-02) — 셋째 줄 · 더 작고 옅게
    nfnt = ImageFont.truetype(str(FONT_NAME), max(24, int(TAIL_SUB_SIZE * 0.8)))
    ny = y2 + 14
    if note:
        n1, _nt, n2, nb = d.textbbox((W / 2, ny), note, font=nfnt, anchor="ma")
        x1, x2, y2 = min(x1, n1), max(x2, n2), nb
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
    if note:
        d.text((W / 2, ny), note, font=nfnt, fill=(255, 255, 255, 170), anchor="ma",
               stroke_width=2, stroke_fill=(0, 0, 0, 180))
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
    돈이 얼마인지가 두 화면에 걸친다. 이 채널은 금액이 핵심이다.

    ⭐ 2026-10-02 (S94 v5 그림 시안에서 잡았다) — 「윤정숙 / 씨의」 처럼 이름과 '씨' 가
       두 화면에 갈렸다. '씨'·'씨의'·'씨는' 은 앞 이름에 붙인다. 「1억 / 5천만 원」 ·
       「40여 / 년」 도 한 덩어리로 (앞이 억·만·천으로 끝나고 뒤가 숫자로 시작하면 붙인다).
    """
    out = []
    for w in ws:
        prev = out[-1].rstrip(",") if out else ""
        if out and out[-1][-1:] != "," and (
                (w.startswith(UNIT) and (prev[-1:].isdigit() or prev.endswith(NUMWORD)
                                         or re.search(r"\d여$", prev)))
                or (w.startswith("씨") and re.fullmatch(r"씨[가-힣]{0,3}[.,!?]?", w))
                or (w[:1].isdigit() and re.search(r"\d(억|만|천)$", prev))):
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


def clip_span(clip, sec):
    """영상 소리를 쓰는 컷에서 **말이 실제로 나는 구간** — (시작, 끝).

    ⭐⭐⭐ 2026-09-10 손님: "대사 음성이랑 자막이랑 안 맞게 제작되는 오류."
       대사 컷은 우리 목소리 파일이 없다(영상 안에서 배우가 말한다). 그래서
       자막 창이 **컷 전체 (0 ~ 끝)** 로 잡혀 있었다. 그런데 Veo 영상은
         · 앞 0.5~1.5초는 배우가 아직 입을 안 뗀다
         · 뒤 0.45초는 여운(TALK_TAIL)이라 아무 말이 없다
       그 조용한 구간까지 자막이 나눠 가지니, 낱말이 하나같이 목소리보다
       **먼저** 켜진다. 한 컷 안에서 계속 밀린다.
       → 소리를 실제로 재서 **말이 나는 구간에만** 자막을 나눈다 (값 0원).

    ⚠️ 재기에 실패하면 옛 방식(컷 전체)으로 돌아간다. 자막이 아예 안 뜨는
       것보다는 조금 어긋나는 편이 낫다.
    """
    if not clip:
        return 0.0, sec
    key = str(clip)
    if key in _SPAN_CACHE:                  # 한 컷을 두 번 재지 않는다
        return _SPAN_CACHE[key]
    beg, fin = speech_span(clip)
    beg = max(0.0, min(float(beg or 0.0), sec))
    fin = sec if fin is None else max(beg + 0.3, min(float(fin) + SUB_TAIL, sec))
    if fin - beg < 0.5:                     # 잘못 잰 것이다 — 손대지 않는다
        beg, fin = 0.0, sec
    _SPAN_CACHE[key] = (beg, fin)
    return beg, fin


def sub_windows(c, sec, voice, clip=None):
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
                    real = [float(x) / speed() for x in got]
            except Exception:                                # noqa: BLE001
                real = []
    # ⭐ 영상 소리를 쓰는 컷(우리 목소리가 없는 컷)은 **말이 나는 구간**만 쓴다
    beg, fin = clip_span(clip, sec) if (clip and not voice) else (0.0, sec)
    at, t0 = [], beg
    if real:
        for i, d in enumerate(real):
            # 마지막 줄은 여운까지 끌고 간다 (말이 끝나도 글은 남아 있어야 한다)
            t1 = fin if i == len(real) - 1 else min(fin, t0 + d)
            at.append((t0, t1))
            t0 = t1
    else:
        tot = sum(syl(t) for _, t in turns)
        span = max(0.05, fin - beg)
        for i, (_, t) in enumerate(turns):
            t1 = fin if i == len(turns) - 1 else t0 + span * syl(t) / tot
            at.append((t0, t1))
            t0 = t1
    return at


def move_of(c):
    """이 컷의 카메라 움직임 (MOVES 한 줄).

    ⚠️ 컷 번호로 **돌려 가며** 고른다 — 이웃한 컷이 같은 움직임이면 이어
       붙였을 때 안 움직이는 것처럼 보인다. 같은 컷은 늘 같은 움직임이라
       다시 만들어도 화면이 안 달라진다(무작위로 하면 매번 달라진다).
    """
    if (c.get("shot") or {}).get("move") in DRAMA_KB:
        z0, z1, x0, x1, y0, y1 = DRAMA_KB[c["shot"]["move"]]
        if c["shot"]["move"] == "drift" and int(c["n"]) % 2 == 0:
            x0, x1 = x1, x0                      # 옆으로 훑기는 컷마다 방향을 바꾼다
        return (z0, z1, x0, x1, y0, y1, f"2분 드라마 · {c['shot']['move']}")
    ring = MOVES_TALK if not is_narr(c) else MOVES_NARR
    return MOVES[ring[(int(c["n"]) - 1) % len(ring)]]


# ── ⭐⭐⭐ 2026-10-01 — **2분 드라마 카메라 무빙** (손님 승인 · 다른 쇼츠에서 배운 것)
#    ① **부드럽게 출발 · 부드럽게 멈춤** (smoothstep). 예전 켄번즈는 처음부터
#       끝까지 같은 빠르기라 컷 경계에서 '툭' 시작해 '툭' 멈췄다.
#    ② 나레이션이 **인물 이름을 부르는 순간** 그 얼굴 쪽으로 다가간다
#       (반려동물 식당 쇼츠의 "심각하다" 줌 · 해양생물 쇼츠의 '특징 줌인').
#       얼굴 자리는 구도 계획이 정해 둔다 — 가운데, 눈은 위에서 3분의 1.
#    ③ 한 프레임에 줌이 STEP_MAX 넘게 변하지 않는다 (계단식 줌 금지 — 반려동물
#       쇼츠에서 "뚝뚝 끊긴다" 로 실제로 걸렸다).
#    ④ 나레이션이 **증거 물건**을 말하는 순간 그 물건 확대 그림으로 넘어갔다가
#       돌아온다 (insert_bg).
#    ⚠️ 옛 여러 편은 그대로다 — 컷에 shot(구도 계획)이 있을 때만 이 길로 간다.
DRAMA_KB = {     # 움직임 → (줌 처음, 줌 끝, 가로 처음, 가로 끝, 세로 처음, 세로 끝)
    "push": (1.04, 1.20, 0.50, 0.50, 0.50, 0.42),
    "pull": (1.20, 1.05, 0.50, 0.50, 0.42, 0.50),
    "drift": (1.12, 1.15, 0.38, 0.62, 0.46, 0.46),
    "hold": (1.04, 1.09, 0.50, 0.50, 0.50, 0.46),
}
FACE_Z = (1.04, 1.08, 1.22)      # 이름 전 아주 느리게 → 이름 순간부터 얼굴 가까이
# ⚠️ NAME_Y 는 이미 이름표 자리(1214)다 — 같은 이름을 쓰면 이름표가 죽는다 (2026-10-01 실제로 덮어썼다)
FACE_Y = (0.50, 0.46, 0.28)      # 얼굴(눈이 위에서 3분의 1) 쪽으로 화면을 올린다
NAME_PUSH_SEC = 1.6              # 이름에서 얼굴까지 다가가는 시간
NAME_EARLY = 0.08                # 이름보다 아주 조금 먼저 움직이기 시작한다
STEP_MAX = 0.02                  # 한 프레임 줌 변화 상한 (넘으면 '툭' 보인다)
INSERT_SEC = 1.8                 # 증거 확대 화면이 떠 있는 시간
INSERT_MIN = 0.8                 # 이보다 짧게밖에 못 띄우면 아예 안 띄운다
INSERT_Z = (1.00, 1.10)          # 확대 화면 안에서도 천천히 다가간다


def key_time(c, sec, words):
    """나레이션에서 그 낱말이 **들리는 순간**(초) — 없으면 None.
    ⚠️ 구글 목소리는 낱말 시각을 안 알려 준다. 자막(karaoke)과 같은 잣대로
       글자 수로 나눈다 — 자막이 켜지는 순간과 카메라가 움직이는 순간이 같다."""
    turns = turns_of(c)
    if not turns or not is_narr(c):
        return None
    text = str(turns[0][1])
    at = [text.find(w) for w in words if w and w in text]
    if not at:
        return None
    spoken = max(0.5, sec - PAD)
    before = len([x for x in text[:min(at)] if not x.isspace()])
    return spoken * before / syl(text)


def _ease(a, b, t="(on/{fps})"):
    """a~b 초 사이를 0→1 로 부드럽게 (ffmpeg 수식). 그 밖은 0 또는 1."""
    tt = t.format(fps=FPS)
    span = max(0.05, b - a)
    p = f"min(1,max(0,({tt}-{a:.3f})/{span:.3f}))"
    return f"pow({p},2)*(3-2*{p})"


def ease_at(a, b, t):
    """_ease 의 파이썬 판 — 검사(tools/camera_check.py)가 수식과 같은 값을 잰다."""
    p = min(1.0, max(0.0, (t - a) / max(0.05, b - a)))
    return p * p * (3 - 2 * p)


def drama_path(c, sec):
    """2분 드라마 그림 컷의 카메라 길 — [(값 셋 (처음·가운데·끝), 1단 끝 초, 2단 끝 초)]
    줌·가로·세로 세 갈래가 같은 때에 움직인다. 1단(0~t1)과 2단(t1~t2) 두 토막."""
    z0, z1, x0, x1, y0, y1, _ = move_of(c)
    who = [w for w in (c.get("who") or []) if w]
    tk = key_time(c, sec, who)
    if tk is not None and sec - tk >= NAME_PUSH_SEC * 0.6:
        t1 = max(0.3, tk - NAME_EARLY)
        t2 = min(sec - 0.05, t1 + NAME_PUSH_SEC)
        return {"z": FACE_Z, "x": (0.5, 0.5, 0.5), "y": FACE_Y, "t1": t1, "t2": t2,
                "why": f"이름이 들리는 {tk:.1f}초에 얼굴로"}
    return {"z": (z0, z1, z1), "x": (x0, x1, x1), "y": (y0, y1, y1),
            "t1": max(0.3, sec), "t2": max(0.3, sec) + 1.0, "why": "부드럽게 한 번"}


def path_expr(v, t1, t2):
    a, b, cc = v
    return (f"{a:.4f}+({b - a:.4f})*{_ease(0.0, t1)}"
            f"+({cc - b:.4f})*{_ease(t1, t2)}")


def path_at(v, t1, t2, t):
    a, b, cc = v
    return a + (b - a) * ease_at(0.0, t1, t) + (cc - b) * ease_at(t1, t2, t)


def drama_zoom(c, sec):
    """drama_path → zoompan 필터 글."""
    p = drama_path(c, sec)
    f = max(2, int(round(sec * FPS)))
    return (f"zoompan=z='{path_expr(p['z'], p['t1'], p['t2'])}':d={f}"
            f":x='(iw-iw/zoom)*({path_expr(p['x'], p['t1'], p['t2'])})'"
            f":y='(ih-ih/zoom)*({path_expr(p['y'], p['t1'], p['t2'])})'"
            f":s={W}x{H}:fps={FPS}")


def insert_span(c, sec):
    """증거 확대 화면을 띄울 때 — (시작, 끝) 초. 못 띄우면 None."""
    ins = c.get("insert") or {}
    tk = key_time(c, sec, [ins.get("word")]) if ins.get("word") else None
    if tk is None:
        return None
    a = max(0.2, tk - 0.05)
    b = a + INSERT_SEC
    # ⚠️ 끝에 얼굴이 0.5초도 안 남으면 깜빡 돌아왔다 끝나 **튀어 보인다** —
    #    그때는 확대 화면으로 컷을 맺는다 (2026-10-01 시험 렌더에서 0.25초가 남았다)
    if sec - b < 0.6:
        b = sec
    return (a, b) if b - a >= INSERT_MIN else None


def insert_bg(c, still, sec, src, vf, nbg):
    """⭐ 증거 확대 — 배경 [bg] 위에 그 물건 그림을 **그 낱말이 들리는 동안** 얹는다.
    (그림이 없거나 시간이 모자라면 아무것도 안 한다 — 꾸밈이지 이야기가 아니다)"""
    span = insert_span(c, sec)
    ins = Path(still).parent / f"i{int(c['n']):02d}.png"
    if not span or not ins.exists() or not vf.endswith("[bg];"):
        return src, vf, nbg
    a, b = span
    dur = b - a
    f = max(2, int(round(dur * FPS)))
    sw, sh = int(W * ZOOM_SRC), int(H * ZOOM_SRC)
    z = (f"{INSERT_Z[0]:.4f}+({INSERT_Z[1] - INSERT_Z[0]:.4f})*"
         f"{_ease(0.0, dur)}")
    src = src + ["-loop", "1", "-i", str(ins)]
    vf = (vf[:-len("[bg];")] + "[bg0];"
          + f"[{nbg}:v]scale={sw}:{sh}:force_original_aspect_ratio=increase,"
          f"crop={sw}:{sh},zoompan=z='{z}':d={f}:x='(iw-iw/zoom)/2'"
          f":y='(ih-ih/zoom)/2':s={W}x{H}:fps={FPS},{LIVE},"
          f"trim=0:{dur:.3f},setpts=PTS-STARTPTS+{a:.3f}/TB[ins];"
          f"[bg0][ins]overlay=0:0:eof_action=pass"
          f":enable='gte(t,{a:.3f})*lt(t,{b:.3f})'[bg];")
    return src, vf, nbg + 1


def shot_plan(c, sec):
    """이 컷을 보여 줄 프레이밍 — **늘 하나**다. [(초, 카메라)]

    ⚠️ 2026-09-19 에 긴 컷을 둘로 잘라 겹쳐 넘겨 봤다가 되돌렸다(위 설명).
       여럿으로 다시 만들려거든 그 기록부터 읽어라.
    """
    return [(sec, move_of(c))]


def zoom_chain(mv, d):
    """카메라 한 줄 → zoompan 필터 글. (프레이밍마다 똑같이 쓴다)"""
    z0, z1, x0, x1, y0, y1, _nm = mv
    f = max(2, int(round(d * FPS)))
    t = f"(on/{max(1, f - 1)})"
    return (f"zoompan=z='{z0:.4f}+({z1 - z0:.4f})*{t}':d={f}"
            f":x='(iw-iw/zoom)*({x0:.4f}+({x1 - x0:.4f})*{t})'"
            f":y='(ih-ih/zoom)*({y0:.4f}+({y1 - y0:.4f})*{t})'"
            f":s={W}x{H}:fps={FPS}")


def still_bg(c, still, sec):
    """그림 한 장 → 컷 배경 [bg].

    돌려주는 것: (ffmpeg 입력 조각, 필터 글, 배경 입력 개수)
    """
    # 조금 키운 뒤 천천히 움직인다 — 원본 크기에서 바로 줌하면 덜덜 떨린다.
    # ⚠️ 2배로 키우면 컷 하나에 6초씩 걸려 너무 느리다. 1.4배면 또렷하고
    #    속도는 3분의 2다.
    sw, sh = int(W * ZOOM_SRC), int(H * ZOOM_SRC)
    src = ["-loop", "1", "-i", str(still)]
    d, mv = shot_plan(c, sec)[0]
    # ⭐ 2분 드라마 — 부드럽게 출발·멈춤 + 이름이 들리는 순간 얼굴로 (위 설명)
    zc = drama_zoom(c, d) if c.get("shot") else zoom_chain(mv, d)
    # ⭐ 얼어 있지 않게 (위 LIVE 설명 참고) — 값 0원
    return src, (f"[0:v]scale={sw}:{sh}:force_original_aspect_ratio=increase,"
                 f"crop={sw}:{sh},{zc},{LIVE}[bg];"), 1


def cut_sec(c, voice, clip):
    """이 컷이 몇 초짜리인가, 그리고 소리를 올린 영상에서 가져오는가.

    ⚠️ 자막 장을 만들려면 컷 길이를 **먼저** 알아야 한다. 그래서 길이 셈을
       cut_video 밖으로 꺼내 두 곳이 같은 값을 쓰게 한다 (따로 세면 어긋난다).
    """
    clip = Path(clip) if clip and Path(clip).exists() else None
    talks = not is_narr(c)
    # ⚠️ has_audio 가 아니라 has_speech 다. 말이 없는 영상의 소리를 쓰면
    #    그 컷이 통째로 조용해진다 (손님이 보신 바로 그 화면).
    if clip and talks and has_speech(clip):
        return dur_of(clip), True
    # ⚠️ 예전에는 대본에 적힌 sec 과 견줘 **큰 쪽**을 썼다. 그런데 그 숫자는
    #    Veo 영상 길이(4·6·8초)라 그림 컷에는 뜻이 없고, 말보다 길면 그만큼
    #    화면이 멈춰 있다. 이제 **말 길이가 정한다.**
    return max(MIN_CUT, dur_of(voice) / speed() + PAD), False


ALIAS_NOTE = "등장인물 이름은 모두 가명입니다"


def aliases_of(doc):
    """{관계 이름: 가명} — 대본 인물표의 alias (없으면 빈 것)."""
    return {str(p.get("name")): str(p.get("alias")).strip()
            for p in doc.get("cast") or [] if str(p.get("alias") or "").strip()}


def intro_of(doc):
    """{컷 번호: (이름, 관계)} — 인물이 **처음 나오는 컷**에 관계 한 줄을 띄운다.

    ⭐⭐⭐ 2026-10-02 손님: "처음보는 사람이 보아도 스토리 전개를 이해하고 공감할 수 있도록."
       처음 보는 시청자 시험(AI 가 60대 시청자로 본 것)에서 가장 먼저 걸린 것이 **누가 누구인지**
       였다 (딸 · 이복동생 · 새어머니 · 땅주인). 대본의 cast.intro 가 있으면 첫 등장에 붙인다.
    대사 컷은 말하는 사람만, 나레이션 컷은 화면의 첫 새 인물만 (한 컷에 이름표 하나).

    ⭐ 처음 보는 시청자 시험 두 번째(같은 날): "인물 관계가 너무 빠르게 지나가서 한 번 보고는
       정리하기가 헷갈린다." → 나레이션 컷에도 **화면 속 사람의 이름표를 늘** 띄운다
       (관계 한 줄은 첫 등장에만 · 그다음은 이름만). 대사 컷은 원래 이름표가 있다.
    """
    rel = {str(p.get("name")): str(p.get("intro") or "").strip()
           for p in doc.get("cast") or [] if str(p.get("intro") or "").strip()}
    seen, out = set(), {}
    for c in doc.get("cuts") or []:
        if is_narr(c):
            order = [w for w in (c.get("who") or []) if w in rel]
        else:
            order = [turns_of(c)[0][0]]
        new = next((w for w in order if w not in seen), None)
        if new and new in rel:
            out[c["n"]] = (new, rel[new])
            seen.add(new)
        elif is_narr(c) and order:
            out[c["n"]] = (order[0], "")
    return out


def karaoke(c, sec, voice, d, n, title=None, mark='', tail='', clip=None, intro=None,
            alias=None, note='', labels=None):
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
    wins = sub_windows(c, sec, voice, clip)
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
            end_card(tail, png, alpha=al, note=note)
            out.append((png, a, b))
    words = []
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
            overlay(c, png, (who, text), now=k, mark=mark, intro=intro, alias=alias,
                    labels=labels)
            words.append((png, t0, t1))
            t0 = t1
    # ⭐⭐ 2026-10-02 (S94 v5 · 말 사이 0.5초) — 영상 속 배우가 말하는 컷은 자막이 **말하는 동안만**
    #    뜬다(talksub_test). 그런데 그 밖의 순간엔 겹그림이 통째로 빠져 **그늘·마크·이름표·대목
    #    표시가 0.5초씩 꺼졌다 켜졌다** (쉼이 0.12초일 땐 안 보였다). → 말 앞뒤에는 자막 글만 뺀
    #    겹그림(bare)을 깐다. 자막 글은 그대로 말하는 동안만 뜬다.
    if words:
        bare = d / f"c{n:02d}_bare.png"
        first, last = words[0][1], words[-1][2]
        if first > 0.02 or sec - last > 0.02:
            overlay(c, bare, turns[0], mark=mark, intro=intro, alias=alias, labels=labels,
                    bare=True)
        if first > 0.02:
            out.append((bare, 0.0, first))
        out += words
        if sec - last > 0.02:
            out.append((bare, last, sec))
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
           # ⭐ 영상에서 그림으로 넘어간 뒤에도 얼어 있지 않게
           f"{LIVE},"
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
        src, vf, nbg = still_bg(c, still, sec)
        # ⭐ 2분 드라마 — 증거를 말하는 순간 그 물건 확대 그림 (있을 때만)
        if c.get("insert"):
            src, vf, nbg = insert_bg(c, still, sec, src, vf, nbg)
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
               # ⭐⭐⭐ 2026-09-14 손님: **"자막이 나타났다 사라지면서 계속
               #    검은색으로 깜빡거리는 현상이 발생해."**
               #    까닭: between(t,a,b) 는 **양쪽 끝을 다 넣는다.** 자막 장은
               #    앞 장의 끝(b)과 뒷 장의 시작(a)이 같은 값이라, 딱 그 한
               #    프레임에서 **두 장이 겹쳐 깔린다.** 자막 판(어두운 그늘)이
               #    두 겹이 되어 그 프레임만 확 어두워진다 → 깜빡임.
               #    실측(S92 4편): 프레임 1292·1322·1370·1412 에서 자막칸
               #    밝기 65.5 → 41.5 → 65.5 (딱 한 프레임씩).
               #    → 끝은 **빼고** 본다(반열린 구간). 그러면 어느 순간에도
               #      자막 장은 **정확히 하나**만 깔린다.
               f":enable='gte(t,{a:.3f})*lt(t,{b:.3f})'{nxt};")
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
         "-af", ("apad" if use_clip_audio else f"{tempo_filter(speed())},apad"),
         "-t", f"{sec:.3f}", "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
         # ⭐⭐⭐ 2026-09-14 손님(화면 캡처): **"이 부분은 대사 음성이 안 나오는데?"**
         #    컷마다 소리 **채널 수가 달랐다.**
         #      나레이션 컷 → 우리 목소리(모노 1채널)
         #      대사 컷    → Veo 영상 소리(스테레오 2채널)
         #    이어붙이기(concat -c copy)는 **첫 컷의 규격**으로 트랙을 하나
         #    만든다. 뒤에 규격이 다른 토막이 섞이면 그 토막의 소리가 통째로
         #    사라진다. 1편 실측 — 컷2는 살고 **컷5·6·8은 소리가 없었다.**
         #    화면·자막은 멀쩡하고 배경음악도 깔려 있어서 **영상만 봐서는
         #    모른다.** 손님이 보고 알려 주셔야 알았다.
         #    → 컷을 만들 때 **채널 수를 못 박는다.** 모노든 스테레오든 전부
         #      2채널로 맞춰 나가므로 이어붙여도 규격이 어긋나지 않는다.
         #    ⚠️ 소리 크기·속도가 아니라 **규격**이 문제였다. 이런 것은 귀로
         #      들어야 알고, 그래서 검사(tools/join_check.py)가 실제로 이어
         #      붙여서 컷마다 소리가 살아 있는지 잰다.
         "-ac", "2",
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


# ── ⭐⭐⭐ 썸네일 (2026-09-07 손님 지시) ─────────────────────────
#    손님: "섬네일을 내가 지정한 걸로 똑바로 올렸으면 이런 일 없잖아.
#           맨날 올릴 때 섬네일이 이상한 대로 지정되어 있으니까."
#    맞는 말씀이다. 90초 쇼츠를 올리는 길에는 **썸네일을 올리는 자리가 아예
#    없었다.** 그래서 유튜브가 영상 한가운데 아무 장면이나 골라 썼다.
#
#    어디를 뽑나 — 편 첫 장면의 이 시각. 여기에는
#      · 화면 위 제목 카드(두 줄)  · 인물 얼굴  · 첫 자막
#    이 다 들어 있다. 우리가 이미 디자인해 둔 화면이므로 따로 그릴 값이 없다.
#    ⚠️ 쇼츠 피드(세로로 넘기는 화면)는 썸네일을 안 쓴다 — 영상이 바로 돈다.
#       썸네일이 먹히는 곳은 **검색·채널 페이지·구독 피드**다. 거기서 갈린다.
THUMB_AT = 1.2                   # 편 첫 장면에서 이 시각(초)의 화면을 뽑는다
THUMB_MAX_BYTES = 1_900_000      # 유튜브 상한 2MB — 안전하게 그 밑으로


def part_thumb(doc, no):
    """그 편의 썸네일 자리. 영상과 같은 이름에 확장자만 다르다."""
    return OUT / f"{doc.get('sid', 'S90')}_part{int(no)}.jpg"


def make_thumb(final, out):
    """완성 영상에서 한 장면을 뽑아 썸네일로 둔다 (0원).

    ⚠️ 유튜브는 2MB 를 넘으면 거절한다. 넘으면 품질을 낮춰 다시 뽑는다 —
       한 번 만들어 놓고 "올렸겠지" 하면 조용히 안 올라간다."""
    for q in (2, 5, 9):
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{THUMB_AT:g}",
             "-i", str(final), "-frames:v", "1", "-q:v", str(q), str(out)])
        if out.exists() and out.stat().st_size <= THUMB_MAX_BYTES:
            return out
    return out


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
# 전체 영상이면 나레이션 컷도 전부 영상이다 (openers 가 맡는다)
_OPEN_ENV = os.environ.get("VT_OPEN_VIDEO", "").strip() in ("1", "예", "on")
OPEN_VIDEO = ALL_VIDEO or PEOPLE_VIDEO or _OPEN_ENV


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
    # ⭐ 2분 드라마는 한 편이 전부다 — "1편" 이라고 적으면 "2편이 있나" 한다
    mark = label if talkplan.is_drama(doc) else f"{label} · {part['no']}편"
    # ⭐ 마지막 편이면 "완결", 아니면 "다음 편에 계속"
    nos = [int(x["no"]) for x in parts_of(doc)]
    tail = TAIL_LAST if int(part["no"]) == max(nos) else TAIL_NEXT
    print(f"\n■ {part['no']}편 — {part['card'][0]} / {part['card'][1]} "
          f"({len(cuts)}컷)")
    total, made = 0.0, []
    intros = intro_of(doc)
    alias = aliases_of(doc)
    labels = labels_of(doc)
    note = str(doc.get("end_note") or "") or (ALIAS_NOTE if alias else "")
    for i, c in enumerate(cuts):
        n = c["n"]
        still = stills_d / f"c{n:02d}.png"
        voice = voice_d / f"c{n:02d}.wav"
        clip = clips_d / f"c{n:02d}.mp4"
        # ⭐ 2026-09-09 — 손으로 올린 것이 **언제나 이긴다.** 없을 때만 기계가
        #    만든 대사 영상을 쓴다. 손님이 공들여 올린 영상이 조용히 기계
        #    것으로 덮이면 안 된다.
        # ⭐ 1분 전부 영상 — 모든 컷이 옴니 영상이다 (손으로 올린 것이 있으면 그게 이긴다)
        if not clip.exists() and doc.get("all_video"):
            v = video_dir() / f"c{n:02d}.mp4"
            if v.exists():
                clip = v
        if not clip.exists():
            # ⭐⭐⭐ 2026-09-11 — **지문이 맞을 때만 쓴다.**
            #    예전에는 파일이 있으면 그냥 썼다. 그래서 9월 10일에 만든
            #    컷34 클립(자막 고치기 전 판 · 8.00초 통짜)이 그대로 들어가
            #    말이 끝난 뒤 3초를 가만히 서 있는 화면이 됐다. 게다가 그 컷은
            #    60초 벽 때문에 **덜어낸 컷**이라 계획에 아예 없었다.
            t = talk_dir() / f"c{n:02d}.mp4"
            if t.exists():
                good, why = talk_ok(c, t, still)
                if good:
                    clip = t
                else:
                    print(f"  ⚠️ 컷{n} 대사 영상은 지금 대본과 안 맞는다"
                          f"{(' — ' + why) if why else ''} — 그림으로 갑니다")
        # ⭐⭐⭐ 2026-09-17 — 사람 없는 장소 컷은 **무료 실사 영상**이 있으면
        #    그것을 쓴다(0원). 그림을 밀고 당기는 것보다 진짜로 움직인다.
        #    ⚠️ 사람이 나오는 컷에는 절대 안 쓴다 — 우리 등장인물 얼굴이
        #       아니기 때문이다(핵심 규칙). 그래서 who 가 빈 나레이션 컷만.
        if not clip.exists() and is_narr(c) and not (c.get("who") or []):
            sk = stock_dir() / f"c{n:02d}.mp4"
            if sk.exists():
                clip = sk
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
                      tail=tail if i == len(cuts) - 1 else "",
                      # ⭐ 영상 소리를 쓰는 컷이면 그 영상에서 말이 나는
                      #    구간을 재서 자막을 거기에 맞춘다 (값 0원)
                      clip=clip if (uca and clip.exists()) else None,
                      intro=intros.get(n), alias=alias, note=note, labels=labels)
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
            how = ("영상 (그 안에서 말한다)" if has_speech(clip)
                   else "영상 + 우리 목소리")
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
    # ⭐ 썸네일도 같이 뽑아 둔다 (0원) — 없으면 유튜브가 아무 장면이나 쓴다
    th = make_thumb(final, part_thumb(doc, part["no"]))
    if th.exists():
        print(f"  ▣ {th.name} — 썸네일 ({th.stat().st_size / 1000:.0f}KB)")
    # ⭐ 만든 사실을 상태 파일에 적는다 — 관리자 페이지가 여기서 길이를 읽는다
    import shortstate                                        # noqa: E402
    # ⭐⭐⭐ 2026-09-14 — 이 편에서 **영상이어야 하는데 그림으로 간** 대사 컷.
    #    적어 두면 올리기(src/upload.py)가 막고 화면에도 뜬다.
    gaps = talk_gaps(doc, set(n for n, *_ in [(c["n"],) for c in cuts]))
    shortstate.mark_made(doc.get("sid") or "S90", part["no"], got, gaps)
    if gaps:
        print(f"  ⚠️⚠️ **이 편은 아직 덜 됐습니다.** 대사인데 그림으로 간 컷: "
              f"{' · '.join('컷' + str(n) for n in gaps)}\n"
              f"       (영상을 못 산 컷입니다. 한도를 올리고 다시 누르면 "
              f"이어서 만듭니다 — 이미 만든 것은 0원입니다)")
    print(f"  ▶ {final.name} — {got:.1f}초 "
          f"({final.stat().st_size / 1e6:.1f}MB)")
    wall = talkplan.part_max_sec(doc)
    if got > wall:
        if talkplan.is_drama(doc):
            print(f"  ⚠️⚠️ {got:.0f}초 — **2분을 넘었다.** 2분 드라마는 "
                  f"{wall:.0f}초 안이어야 한다. 나레이션을 줄여 다시 지으십시오.")
        else:
            print(f"  ⚠️⚠️ {got:.0f}초 — **60초를 넘었다.** 이 채널은 60초 이하만"
                  f" 조회수가 나왔다(127초 편은 0회였다). 컷을 옮겨 나누십시오.")
    elif got < 15:
        print(f"  ⚠️ {got:.0f}초 — 너무 짧다. 컷이 빠지지 않았는지 보십시오.")
    return got


def build(doc, only=None):
    """편마다 하나씩 만든다. only 를 주면 그 편만 (나머지는 손대지 않는다)."""
    global PAD
    if doc.get("all_video"):
        PAD = gap_of(doc)                # 말 사이 쉼 — 대본이 정한다 (기본 0.12초)
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
    # ⭐⭐⭐ 2026-09-14 손님: **"다시는 이런 일들이 발생하지 않게 코드 수정해."**
    #    대사 영상을 만들라고 눌렀는데 여덟 컷을 못 사서 그림으로 떨어졌는데,
    #    여기는 "■ 다 됐다" 를 찍고 0(성공)을 돌려줬다. 워크플로는 초록불,
    #    손님은 다 된 줄 알고 보시다가 슬라이드쇼를 만났다.
    #    → **다 안 됐으면 다 됐다고 하지 않는다.** 만든 것은 그대로 두고
    #      (값을 버리지 않는다) 실행만 실패로 끝낸다. 그래야 눈에 띈다.
    gaps = talk_gaps(doc)
    if gaps:
        print(f"\n❌ **아직 덜 됐습니다** — 대사인데 그림으로 간 컷 "
              f"{len(gaps)}개: {' · '.join('컷' + str(n) for n in gaps)}")
        print("   만든 것은 그대로 보관했습니다 (값은 안 버립니다).")
        print("   한 달 한도를 올리고 [전체 만들기] 를 다시 누르면 "
              "**없는 것만** 이어서 만듭니다 (이미 만든 것은 0원).")
        print("   ⚠️ 이 편들은 올리기가 막힙니다 — 덜 된 것이 채널에 "
              "올라가면 지울 수 없기 때문입니다.")
        return 1
    print("\n■ 다 됐다 — " + " · ".join(
        f"{x['no']}편 {t:.0f}초" for x, t in zip(ps, secs)))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what",
                    choices=["stills", "open", "talk", "voice", "build",
                             "all", "meta"])
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
        # ⭐ 대사 장면 영상 — **켰을 때만** 돈다 (값이 나간다).
        #    그림 다음이다: 그 컷 그림을 첫 프레임으로 넣어야 얼굴이 안 바뀐다.
        if a.what == "talk" or (a.what == "all" and TALK_VIDEO):
            if talkers(doc):
                return 1
        elif a.what == "all":
            print("■ 대사 장면 영상 — 끔 (그림으로 갑니다 · 0원)")
        if a.what in ("voice", "all"):
            if voices(doc):
                return 1
        if a.what in ("build", "all"):
            if build(doc, only=only):
                return 1
            # 영상이 나왔으면 올릴 글도 같이 만들어 둔다 (0원)
            meta(doc)
        # ⭐⭐⭐ 2026-09-10 — 끝에 **얼마를 아꼈는지** 적는다.
        #    손님: "이미 제작된 것 중 제대로 된 것은 다시 제작되지 않도록 하여
        #    비용이 낭비되지 않도록." 재활용은 예전부터 돌았지만 얼마나 아꼈는지
        #    아무도 안 적어서, 보관이 조용히 죽어 매번 다시 만들고 있어도
        #    화면에는 똑같이 보였다. 아낀 값이 0이면 여기서 크게 알린다.
        reuse.book_flush(SID)
        return 0
    except (Short90Error, ST.StillError, cost.MonthlyCapReached) as e:
        print(f"❌ {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
