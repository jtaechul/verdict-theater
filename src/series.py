#!/usr/bin/env python3
"""⭐ 시리즈 대본 — 판례 1건을 30초짜리 16화로 쪼갠다 (구글 영상 제작용).

    python3 src/series.py                 다음 소재로 시리즈 하나
    python3 src/series.py --case 230761   그 판례로
    python3 src/series.py --check S001    이미 만든 것만 다시 검사 (0원)

왜 (2026-08-18 대개편)
    영상을 구글(옴니 플래시)이 만든다. 하루 무료 크레딧 50개 = 6초 클립 5개 =
    30초. 그래서 한 회차를 12분짜리로 쓰던 옛 방식은 통째로 버리고,
    **판례 하나를 30초 × 16화**로 쪼갠다. 매일 한 편 내고, 16일이면 8분짜리
    롱폼이 공짜로 나온다(이미 만든 클립을 잇기만 하면 되므로).

지키는 것 (운영자 지시)
    ① 매 화 첫 컷은 후킹 — 설명으로 시작하는 화는 반려
    ② 영상 안에 글자가 한 자도 나오면 안 된다 — 글자가 나올 물건을 안 부른다
    ③ 자막·채널명은 우리 프로그램이 나중에 얹는다 (subtitle 칸에 따로 적는다)

값
    글만 쓴다 — 회차(16화 전부)당 수백 원. 영상값은 여기서 한 푼도 안 나간다.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import prompts                                              # noqa: E402
from claude import writer                                   # noqa: E402
import charsheet                                            # noqa: E402

SERIES_DIR = ROOT / "data" / "series"
CASES = ROOT / "data" / "cases"
QUEUE = ROOT / "state" / "queue.json"
STATE = ROOT / "state" / "series.json"

EPISODES = 16          # 16화 × 30초 = 8분 (롱폼 한 편)
CUTS = 5               # 한 화 5컷
SEC = 6                # 컷 하나 6초 (플로우 무료 하루 50크레딧 = 45크레딧)
ROLES = ["후킹", "상황", "맞섬", "뒤집기", "끊기"]

# ⚠️ 2026-08-19 첫 실행에서 20군데가 걸렸는데 **15군데가 이 한 줄** 때문이었다.
#    지난 줄거리를 18자로 정해 뒀는데, 한국어로 지난 화를 요약하기엔 너무 짧다.
#    실물로 재보지 않고 숫자를 적은 내 잘못이다(시트 검사 오판 265원과 같은 실수).
#    화면 아래 한 줄 자막으로 읽히는 길이는 30자까지가 무난하다.
RECAP_MAX = 30

# ⚠️ 2026-08-20 — 대사 18자도 recap 18자와 **똑같이 재보지 않고 적은 숫자**였다.
#    실제 드라마 한 줄을 재보니 "재판장님, 저는 그 돈을 만진 적이 없습니다." = 24자,
#    말하면 약 3.5초다. 6초 클립에 넉넉히 들어간다. 18자는 한국어 한 문장을
#    끝맺지도 못하는 길이라 억지 대사가 나온다.
# ⚠️ 2026-08-20 (두 번째) — 한 줄 24자 제한이 **한 글자 차이로** 멀쩡한 대사
#    둘을 막았다 ("악의적 증여는 시효 상관없이 다 토해내야 해." 25자 ≈ 5초).
#    총합 28자 제한이 이미 같은 일을 하고 있었다 — 혼자 말하면 28자를 다 쓰면
#    되고, 둘이 나누면 한쪽이 24자를 쓰는 순간 상대는 4자밖에 못 써서 총합에서
#    걸린다. 겹치는 제한을 하나 더 두어 돈만 날렸다. 총합 하나로 통일한다.
#    (recap 18자 · 대사 18자 · paper · phone 에 이어 **다섯 번째** 같은 실수다.
#     숫자를 정할 때는 반드시 실물을 먼저 잰다.)

# ⚠️ 2026-08-20 손님: "뭔 대사가 저렇게 짧아.. 무슨 한 컷에 대사를 한 명만 치면
#    스토리 전개가 전혀 안 되지 않아?"  — 재봤더니 둘 다 맞았다.
#      · 80컷 **전부** 말하는 사람이 1명 (주고받는 대화가 한 번도 없다)
#      · 대사 평균 13.9자 (6초에 28~33자가 들어가는데 절반도 안 썼다)
#    원인은 모델이 아니라 내 규격이었다 — 프롬프트에 '대사 한 줄', '말하는
#    사람'(단수) 이라고 못 박아 두었다.
#    한국어는 초당 약 5자. 6초 클립에서 앞뒤 숨 쉴 틈을 빼면 약 5.5초를 말하니
#    **한 컷에 28자**까지 들어간다. 두 사람이면 각 14자씩 — 실제 드라마 한
#    합이 딱 그 길이다("이 집, 이제 저희 겁니다." 14자).
# ⚠️ 2026-08-20 (세 번째) 손님: "대사가 너무 적어. 말도 어색해. 구어체가
#    아닌 것 같고 실제 같지 않아."  — 재봤더니 또 맞았다.
#      · 대사 112줄 / 80컷 = 컷당 1.4줄 (거의 한 마디씩만 하고 끝난다)
#      · 대사 20줄(18%)에 법률·서류 용어가 들어 있다
#        ("대법원 판례상 사망보험금은 내 거야." — 싸우면서 이렇게 말하는 사람은 없다)
#    까닭: 사실을 전할 통로가 대사밖에 없어서 입에 다 밀어 넣었다.
#    그래서 ① 주고받는 횟수를 늘리고 ② 사실은 '설명 자막(caption)' 이 지게 한다.
# ⚠️ 여기서 **재는 단위 자체가 틀렸다**는 것을 찾았다.
#    나는 '글자 수'로 재고 있었는데, 공백·쉼표·물음표는 **소리가 나지 않는다.**
#      "여기가 어디라고 뻔뻔하게 와?"  = 16자지만 실제 소리는 12음절
#    실제 대본 112줄을 재보니 글자 수가 소리보다 1.44배 많았다.
#    그래서 28자로 막았던 것은 실제로는 19음절 = 약 3.5초뿐 — 6초 클립이
#    늘 반쯤 비어 있었다. 손님이 "대사가 너무 적어" 라고 한 것이 이것이다.
#    이제 **음절로 센다.** 한국어 드라마 대사는 초당 5~6음절이고, 6초 중
#    5.5초를 말하니 약 30음절이 들어간다.
def syl(t):
    """실제로 소리 나는 것만 센다 — 공백·쉼표·물음표는 시간을 안 잡아먹는다."""
    return len(re.findall(r"[가-힣]", t or ""))


# ⚠️ 최소치를 12로 뒀더니 **모델이 바닥에 붙어서 썼다** — 80컷 중 30컷이
#    12~15음절(2.2~2.7초)에 몰렸고 평균이 6초의 56%에 그쳤다. 특히 혼자
#    말하는 컷이 짧았다(주고받는 컷은 이미 24~25음절을 쓰고 있었다).
#    바닥이 곧 목표가 되므로, 바닥을 20음절(3.6초 · 6초의 60%)로 올린다.
# ⚠️ 2026-08-20 (네 번째) 손님: "실제 사람은 말을 좀 더 빨리 하잖아."
#    맞다. 실제 대본에 나온 대사를 말다툼 속도로 재보니 —
#      "여기가 어디라고 와. 당장 안 나가?"   13음절 / 1.9초 = 초당 6.8
#      "매일 같이 살았으면서 그걸 모른다고?" 15음절 / 2.2초 = 초당 6.8
#      "돈 다 빼돌리고 나한테 이딴 빚만…"    18음절 / 3.0초 = 초당 6.0
#    평균 **초당 6.4음절**. 내가 잡았던 5.5는 느렸고, 그래서 상한 30음절이
#    실제로는 4.7초 — 6초 중 1.3초가 남았다. 6.4로 다시 잡는다.
SYL_PER_SEC = 6.4      # 실측 (말다툼 속도). 화면 문구도 전부 이 값을 쓴다

# ⭐⭐ 2026-08-21 — **실제로 만들어진 영상을 재 봤다.** (1화 1컷, 6.02초)
#      0.00~0.98초  무음   ← 앞에 1초를 그냥 버린다
#      0.98~2.55초  1번째 대사
#      2.79~4.20초  2번째 대사
#      4.57~6.02초  3번째 대사
#    말한 시간 4.43초에 32음절 = **초당 7.2음절.** 아나운서보다 빠르다.
#    이렇게 쏟아내면 받침·연음이 뭉개져 원어민이라도 어눌하게 들린다.
#    운영자: "외국인 노동자가 어설픈 한국말 하는 것 같다."
#
#    두 가지를 고친다.
#      ① 영상 앞 1초는 **못 쓴다고 보고** 빼고 계산한다 (0.4초가 아니라 1.2초)
#      ② 급하지 않게 말할 속도(초당 6.0)로 상한을 잡는다
#    ⚠️ 예전에 운영자가 "대사가 너무 짧다" 고 한 것은 9.6음절일 때다.
#       26음절은 그때의 세 배에 가까우므로 그 지적을 되돌리는 것이 아니다.
DEAD_HEAD = 1.2        # 실측 — 앞머리에 말 없이 버려지는 시간
EASY_SYL_PER_SEC = 6.0  # 급하지 않게 또박또박 말하는 속도
SPEAK_SEC = SEC - DEAD_HEAD    # 6초 중 실제로 말할 수 있는 시간 = 4.8초

# ⭐ 숫자를 손으로 적지 않고 **위 실측값에서 계산한다.**
#    이번에만 recap 18 · 대사 18 · 28자 · 24자 · 33자 · 20음절을 눈대중으로
#    적었다가 여섯 번 고쳤다. 계산해서 나오게 하면 속도만 다시 재면 된다.
DIA_SYL_MAX = int(SPEAK_SEC * EASY_SYL_PER_SEC)  # 4.8초 × 6.0 = 28음절
# ⚠️ "바닥은 빈 컷만 막고, 길이는 목표치가 끌어올린다" 고 했는데 **틀렸다.**
#    목표를 30~34 로 적어 뒀는데 80컷 중 30음절을 넘긴 것은 **1컷뿐**이었고
#    53컷이 24~27에 몰렸다(평균 25.2). 모델에게 목표는 권고일 뿐이고 실제로
#    강제되는 것은 바닥뿐이다 — 이번에 바닥을 올릴 때마다 평균이 따라
#    올라간 것도 같은 까닭이다(12→16→20 일 때 15.5→18.4→22.1).
#    그러니 **바닥을 목표 바로 아래에 둔다.**
# ⚠️ 28 로 올렸더니 80컷 중 41컷이 걸렸다. 나눠 보니 원인이 한쪽에 있었다 —
#      혼자 말하는 컷 47개: 평균 28.7음절 (4.5초) — 이미 충분하다
#      주고받는 컷   33개: 평균 26.5음절, **전부 두 번만** 주고받는다
#    길이가 모자란 것이 아니라 **주고받는 횟수가 모자랐다.** 두 번을 세 번으로
#    (A→B→A) 늘리면 한 번에 10~12음절씩 30~35가 된다. 그건 프롬프트가 할 일이고,
#    바닥은 다시 '거의 빈 컷'만 막는 자리로 돌려놓는다(반씩 걸러 내면 돈만 나간다).
DIA_SYL_MIN = int(3.2 * EASY_SYL_PER_SEC)       # 3.2초어치 = 19음절
# ⚠️ 상한을 35 → 28 로 내리자 이미 만든 S001 의 80컷 중 15컷이 걸렸다.
#    그런데 그 15컷은 전부 **29~30음절**, 한두 음절 넘칠 뿐이었다.
#    이런 것으로 16화를 반려하면 돈만 나간다(이 저장소가 여러 번 겪은 일이다).
#    → 두 단계로 나눈다. 목표는 28, **진짜 못 말할 길이**만 반려한다.
DIA_SYL_HARD = int(5.5 * EASY_SYL_PER_SEC)      # 5.5초어치 = 33음절
TALKERS_MAX = 3        # 한 컷에 말을 주고받는 횟수 ("뭐?" "들었잖아." "야!")
TALK_MIN = 2           # 한 화 5컷 중 **주고받는 컷**이 최소 몇 컷이어야 하는가
SUB_MAX = 60           # 자막은 주고받은 대사를 다 담아야 한다 (' / ' 로 나눈다)

# 프롬프트 6줄 규격 — 이 순서, 이 이름이 아니면 반려한다
LINES = ["SHOT:", "SUBJECT:", "ACTION:", "DIALOGUE:", "AUDIO:",
         "SETTING:", "CONTINUITY:", "COLOR:", "STYLE:", "Avoid:"]
LINES_OPT = ["VOICE:"]      # 대사가 있는 컷에만 붙는다

# ⭐⭐ 2026-08-20 운영자: "영상 색상톤도 통일시켜야 할 것 같아."
#    컷마다 색이 튀면 다섯 조각을 이어 붙였을 때 딴 작품처럼 보인다.
#    STYLE 줄의 "muted desaturated palette" 만으로는 느슨하다 —
#    **모든 컷에 글자 그대로 똑같은 색 지시**를 따로 한 줄 둔다.
#    (고정 문구라 normalize 가 80컷에 자동으로 갈아 끼운다)
COLOR_FIX = ("COLOR: the same colour grade in every shot of the series — "
             "warm neutral base, slightly lifted blacks, gentle amber "
             "highlights from the practical lamps, muted greens and cyans, "
             "natural unsaturated skin tones, low overall contrast, "
             "a calm evening illustrated look that stays identical from the "
             "first shot to the last.")

# ⭐⭐ 2026-08-20 운영자: "나레이션이 너무 로봇 같은데?"
#    프롬프트를 다시 보니 **소리에 관한 지시가 한 줄도 없었다.**
#    있는 것이라곤 `(furious)` 같은 한 낱말뿐. 그러면 영상 만드는 쪽은
#    안전한 쪽 — **또박또박 읽는 낭독**을 고른다. 그게 로봇처럼 들리는 것이다.
#    게다가 대사가 화면 밖 **해설자 목소리**로 얹히는 일도 잦다.
#    → 두 줄을 새로 붙인다.
#      VOICE — 누가 어떤 목소리로 말하는가 (인물마다 다르게)
#      AUDIO — 낭독이 아니라 **그 자리에서 하는 말**이라고 못 박는다
#    ⚠️ "on screen" 이라고 썼더니 **screen(화면)** 이 '글자 나올 물건' 검사에
#       걸려 80컷이 통째로 반려됐다. `between words` 의 **words** 도 '읽는 말'
#       로 걸려 봉투가 나오는 컷을 막았다. 고정 문구는 다른 검사에 걸리는
#       낱말을 피해서 쓴다 — 한 낱말이 80컷을 통째로 막는다.
#    ⭐ 2026-08-20 운영자: "나레이션이 외국인이 한국말하는 것처럼 들린다."
#       프롬프트가 **무슨 말로 하는지 한 번도 안 알려 줬다.** 지시는 전부 영어고
#       대사만 한글이라, 영상 만드는 쪽은 영어 억양·리듬을 한글에 그대로 씌운다.
#
#    ⭐⭐ 그런데 한국어라고 알려 줘도 계속 외국인 소리가 났다. 운영자가 제미나이
#       자문을 받아 왔고, 그 지적이 맞았다 —
#       **"no foreign accent, no English accent" 가 오히려 역효과였다.**
#       영상 만드는 쪽은 `no` 보다 뒤에 붙은 `foreign` `English` 라는 낱말
#       자체에 끌린다. 없애라고 부른 것을 불러들인 셈이다.
#       → 부정 명령을 전부 걷어내고 **바라는 것만 적는다.**
#         (`no narrator` `no music` 도 같은 이유로 걷어내고,
#          "이 소리만 들린다" 는 **긍정문**으로 바꿨다)
#
#       그리고 대사가 한국어라는 것을 **대문자 표시**로 못 박고,
#       말투 괄호마다 `in Korean` 을 붙인다 (제미나이 자문 3·4번).
DIA_LANG = "[LANGUAGE: KOREAN] "
# ⭐ 제미나이가 다시 써 온 것에서 가장 값진 한 줄 — **겹쳐 말하지 않는다.**
#    6초짜리에서 목소리가 겹치면 한국어가 뭉개져 더 어색하게 들린다.
#    우리 쪽에도 이득이다 — 가라오케 자막이 **말 사이 정적**으로 사람을
#    가르는데, 겹쳐 말하면 그 경계를 못 찾는다.
DIA_ORDER = "each person speaks one after another, never overlapping"
AUDIO_FIX = ("AUDIO: the two people in the shot say the lines themselves with "
             "their lips moving in sync, every line spoken in natural, fluent "
             "and highly authentic everyday Korean by native speakers with "
             "standard Seoul intonation, real spontaneous speech with uneven "
             "rhythm and short breaths between phrases, each person "
             "speaking one after another so every word stays clear, with only "
             "the quiet room tone of the location underneath.")
AUDIO_SILENT = ("AUDIO: the shot is quiet, with only the room tone of the "
                "location and the small everyday sounds of the place.")

# 인물 설명에서 성격을 읽어 목소리를 짓는다 (인물표에 voice 가 없을 때)
VOICE_TONE = [
    ("tired", "weary and a little breathy, trails off at the end of a sentence"),
    ("worn", "weary and a little breathy, trails off at the end of a sentence"),
    ("agitated", "clipped and impatient, drops in volume at the end"),
    ("angry", "tight and rising, breaks a little when it gets loud"),
    ("confident", "cool and unhurried, with a small lilt at the end"),
    ("sharp", "quick and cutting, barely waits for the other person"),
    ("calm", "steady and low, unhurried"),
    ("gentle", "soft and slow, warm"),
    ("cold", "flat and quiet, almost bored"),
]


# ⭐ 제미나이 자문 3번 — 대사에 쉼표를 넣어 주면 억양이 한 번 **리셋**되어
#    외국어 특유의 늘어지는 억양이 줄어든다. 부르는 말 뒤가 가장 자연스럽다.
#      "당신 진짜 제정신이야?"  →  "당신, 진짜 제정신이야?"
#    ⚠️ 사람이 쓴 대사를 우리가 손대는 것이라 **아주 조심스럽게** 한다 —
#       맨 앞의 부르는 말 뒤에만, 그것도 문장이 길 때만 넣는다.
#    ⚠️ 처음에는 `당신` `너` `자기` `왜` 까지 넣었다가 **말뜻을 망가뜨렸다** —
#         "당신 명의로 다 해놨어" → "당신, 명의로…"  (당신은 부르는 말이 아니다)
#         "자기 혼자 떨어졌다고요" → "자기, 혼자…"    (자기 혼자 = 저 혼자)
#       꾸미는 말로도 쓰이는 낱말은 기계가 가릴 수 없다. **감탄사만** 남긴다.
LEAD = ["야", "여보", "이봐", "저기", "얘", "아이고", "그래", "아니", "그럼",
        "그러니까"]
LEAD_MIN_SYL = 8            # 이보다 짧으면 쉼표가 오히려 어색하다
# 소리 지르는 말투. 물음표를 `?!` 로 만들어 힘을 더 준다.
LOUD = ["shout", "yell", "scream", "furious", "rage", "angry", "roar"]


def add_breath(say, tone):
    """대사 한 마디에 숨 쉴 자리를 만든다 (쉼표·느낌표)."""
    t = say.strip()
    if not t:
        return say
    for w in LEAD:
        if t.startswith(w + " ") and syl(t) >= LEAD_MIN_SYL:
            t = w + ", " + t[len(w) + 1:]
            break
    if any(k in (tone or "").lower() for k in LOUD) and t.endswith("?"):
        t = t[:-1] + "?!"
    return t


# ⭐⭐ 2026-08-20 — 제미나이가 다시 써 온 것을 보고 고친다.
#    대사를 한 줄에 ` / ` 로 이어 붙이지 않고 **한 사람에 한 줄**로 나눈다.
#    말 차례가 눈에 보이면 영상 만드는 쪽이 억양을 사람마다 새로 잡는다.
#      DIALOGUE: [LANGUAGE: KOREAN] each person speaks one after another…
#        Wife (furious, in Korean): "당신 진짜 제정신이야?!"
#        Husband (annoyed, in Korean): "더는 숨 막혀서 못 살아."
#    ⚠️ 아래 대사 줄은 **두 칸 들여쓴다.** 줄 이름 검사가 `Wife:` 를 규격 줄로
#       착각하지 않게 하려는 것이다 (들여쓴 줄은 검사에서 건너뛴다).
DIA_INDENT = "  "


def dia_span(lines):
    """DIALOGUE 줄 + 그 아래 들여쓴 대사 줄들의 범위 (시작, 끝)."""
    i = next((k for k, l in enumerate(lines) if l.startswith("DIALOGUE:")), None)
    if i is None:
        return None, None
    j = i + 1
    while j < len(lines) and lines[j].startswith(DIA_INDENT):
        j += 1
    return i, j


def dia_text(prompt):
    """대사 덩어리를 한 덩이 글로 (음절 세기·금지어 검사에 쓴다)."""
    lines = str(prompt or "").split("\n")
    i, j = dia_span(lines)
    return "\n".join(lines[i:j]) if i is not None else ""


def dia_turns(prompt):
    """대사 덩어리에서 (말하는 사람, 대사) 를 말한 차례대로 뽑는다.

    ⚠️ 2026-08-21 — 이 함수가 shorts.py 에 있었는데, 목소리만 만드는 일
       (tts.sample)에서 부르려고 shorts 를 들여왔다가 **PIL(그림 모듈)이
       없다고 죽었다.** 소리 만드는 데 그림 모듈이 왜 필요한가.
       대본을 읽는 일이므로 **대본 쪽(series.py)이 제 자리**다.
    """
    out = []
    for l in str(prompt or "").split("\n"):
        if not l.startswith(DIA_INDENT):
            continue
        m = re.match(r'\s*([^:(]+?)\s*(?:\([^)]*\))?\s*:\s*"(.+)"\s*$', l)
        if m:
            out.append((m.group(1).strip(), m.group(2).strip()))
    return out


def dia_says(prompt):
    """대사 덩어리에서 따옴표 안 말만 뽑는다."""
    return re.findall(r'"([^"]*)"', dia_text(prompt))


def turn_label(who):
    """`the wife` → `Wife` (말 차례가 눈에 확 들어오게)."""
    t = re.sub(r"^the\s+", "", str(who or "").strip())
    return t[:1].upper() + t[1:] if t else t


def fix_dialogue_lang(doc):
    """대사를 **한 사람에 한 줄**로 나누고, 한국어 표시·맥락·숨을 넣는다.

    제미나이 자문 3·4번 + 다시 써 온 것 반영 (2026-08-20).
    """
    n = 0
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
            lines = (c.get("prompt") or "").split("\n")
            a, b = dia_span(lines)
            if a is None:
                continue
            # ⚠️ 이미 여러 줄로 나눠 둔 것을 다시 고칠 때, 머리말(한국어 표시 ·
            #    차례대로 말하기)까지 대사로 끌어들이면 줄이 뭉개지고 말이
            #    겹쳐 붙는다. 머리말은 **떼어 내고** 대사만 다시 짠다.
            head = lines[a][len("DIALOGUE:"):]
            for junk in (DIA_LANG, DIA_ORDER):
                head = head.replace(junk, "")
            head = re.sub(r"\(all lines spoken[^)]*\)\s*", "", head).strip()
            said = [l.strip() for l in lines[a + 1:b] if l.strip()]
            if not said:
                said = [x.strip() for x in head.split(" / ") if x.strip()]
                head = ""
            if head:                      # 머리말 자리에 대사가 남아 있으면 앞에 붙인다
                said = [x.strip() for x in head.split(" / ") if x.strip()] + said
            if not said or " ".join(said).lower() in ("none.", "none"):
                continue

            # 한 사람에 한 마디씩 끊는다
            turns, tone = [], ""
            for part in said:
                bits = part.split('"')
                for j, bb in enumerate(bits):
                    if j % 2 == 0:
                        m = re.findall(r"\(([^)]+)\)", bb)
                        tone = m[-1] if m else tone
                        bits[j] = re.sub(
                            r"\(([^)]+)\)",
                            lambda x: x.group(0) if "korean" in x.group(1).lower()
                            else f"({x.group(1)}, in Korean)", bb)
                    else:
                        bits[j] = add_breath(bb, tone)
                who = bits[0].strip().rstrip(":").strip()
                bits[0] = turn_label(who) + (": " if who else "")
                turns.append(DIA_INDENT + '"'.join(bits).strip())

            block = [f"DIALOGUE: {DIA_LANG}{DIA_ORDER}"] + turns
            if lines[a:b] != block:
                lines[a:b] = block
                n += 1
            c["prompt"] = "\n".join(lines)
    return n


def voice_of(ch):
    """인물 하나 → 목소리 한 줄. 인물표에 적혀 있으면 그것을 쓴다."""
    v = (ch.get("voice") or "").strip()
    if v:
        return v
    low = (ch.get("flow_prompt") or "").lower()
    male = bool(re.search(r"\bman\b|\bmale\b|\bboy\b", low))
    m = re.search(r"(\d+)\s*years?\s*old", low)
    age = int(m.group(1)) if m else 45
    pitch = ("a low, slightly gravelly man's voice" if male
             else ("a warm mid-range woman's voice" if age >= 50
                   else "a clear woman's voice"))
    band = ("in his" if male else "in her") + \
           (" fifties" if 50 <= age < 60 else
            " forties" if 40 <= age < 50 else
            " sixties" if 60 <= age < 70 else
            " thirties" if 30 <= age < 40 else " middle years")
    tone = next((t for w, t in VOICE_TONE if w in low), "plain and everyday")
    return f"{pitch} {band}, native Korean speaker, {tone}"


def fix_voice(doc):
    """컷마다 VOICE·AUDIO 줄을 붙인다. 로봇 낭독을 막는 가장 큰 손잡이다."""
    vs = {}
    for ch in doc.get("characters") or []:
        v = voice_of(ch)
        # ⚠️ 대사 줄의 이름표는 `Wife:` 처럼 짧게 쓴다. 그 꼴도 같이 넣어 두지
        #    않으면 말하는 사람을 못 찾아 VOICE 줄이 통째로 빠진다.
        for k in ((ch.get("name") or "").strip(),
                  (ch.get("role_en") or "").strip(),
                  turn_label(ch.get("role_en") or "")):
            if k:
                vs[k] = v
    n = 0
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
            lines = [l for l in (c.get("prompt") or "").split("\n")
                     if not l.startswith(("VOICE:", "AUDIO:"))]
            di, dend = dia_span(lines)
            if di is None:
                c["prompt"] = "\n".join(lines)
                continue
            # ⚠️ 대사가 여러 줄이 되었으므로 **덩어리 전체**를 본다.
            #    한 줄만 보면 말하는 사람이 안 잡혀 VOICE 줄이 안 붙었다.
            said = "\n".join(lines[di:dend])[len("DIALOGUE:"):].strip()
            # ⚠️ 말하는 사람은 **따옴표 밖**에서만 찾는다. 대사 안에 '남편' 같은
            #    낱말이 들어 있으면(예: "내 남편이 왜 거기서 죽어") 그것을
            #    말하는 사람으로 잘못 잡아 VOICE 줄에 한글이 섞였다.
            outside = " ".join(b for i, b in enumerate(said.split('"')) if i % 2 == 0)
            add = []
            if said and said.lower() not in ("none.", "none"):
                # 이 컷에서 실제로 말하는 사람만 골라 넣는다 (긴 이름부터)
                who = sorted([k for k in vs if k in outside],
                             key=lambda k: outside.index(k))
                seen, keep = set(), []
                for k in who:
                    if vs[k] in seen:
                        continue
                    seen.add(vs[k])
                    keep.append(f"{k} — {vs[k]}")
                if keep:
                    add.append("VOICE: " + "; ".join(keep) + ".")
                add.append(AUDIO_FIX)
            else:
                add.append(AUDIO_SILENT)
            lines[dend:dend] = add          # 대사 덩어리 **아래**에 붙인다
            n += len(add)
            c["prompt"] = "\n".join(lines)
    return n

# ⭐⭐ 2026-08-20 운영자: "프롬프트 복사하니까 또 이렇게 뜬다" —
#      shot:%20Medium%20two-shot,...%20%EB%82%A8%ED%8E%B8...
#
#    원인을 찾았다. **우리 복사 코드 잘못이 아니다.**
#    프롬프트가 `SHOT:` 으로 시작하는데, 붙여 넣는 쪽(크롬·플로우 입력칸)이
#    `단어:` 로 시작하는 글을 **인터넷 주소(URL)** 로 읽는다.
#    `http:` `mailto:` 처럼 `shot:` 을 주소 이름으로 본 것이다. 그러면
#      · 주소 이름은 소문자로 바뀌고 (SHOT: → shot:)
#      · 나머지는 주소 규칙대로 %20 · %EB.. 로 바뀐다
#    실제로 브라우저에 `new URL(프롬프트)` 를 넣으면 손님이 본 그 글자가 나온다.
#    (첫 물음표 앞의 `:` 만 %3A 로 바뀐 것도 주소 규칙 그대로다)
#
#    그래서 **주소로 보일 여지 자체를 없앤다** — 맨 앞에 콜론 없는 머리말을
#    한 줄 둔다. 첫 낱말 뒤에 곧바로 `:` 가 오지 않으면 주소가 아니다.
#    이 줄은 영상에도 도움이 되는 말이라 버리는 줄이 아니다.
#    ⭐⭐ 2026-08-20 두 번째 — 플로우가 이 머리말에 이렇게 답했다:
#       "이 프롬프트는 **유명인의 동영상 생성**에 관한 정책을 위반할 가능성이…"
#       `Live-action Korean drama` 는 **실제로 방영된 한국 드라마를 실사로
#       다시 만들어 달라**는 말로 읽힌다. 거기에 Avoid 줄의 `actor`(배우),
#       STYLE 줄의 `Korean TV drama realism` 까지 겹쳐 "실존 배우"로 보였다.
#       → 방송·배우를 가리키는 말을 모두 빼고, **지어낸 인물**임을 먼저 밝힌다.
#    ⚠️ `realistic live footage` 도 뺐다 — "실제로 찍은 영상" 으로 읽혀
#       실존 인물 쪽으로 기운다. 사실적인 느낌은 STYLE 줄이 이미 지고 있다.
HEAD_FIX = (f"Fictional scene, invented characters, semi-realistic "
            f"illustrated drama. {SEC}-second single continuous take.")


def looks_like_url(t):
    """붙여 넣을 때 주소로 오해받을 글인가 (맨 앞이 `단어:` 인가)."""
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9+.\-]*:", str(t or "").lstrip()))
# ⚠️ 2026-08-20 운영자: "중간에 화면에서 배경이 바뀐다거나, 남자 주인공 옷이
#    바뀌고 얼굴이 바뀌는 부분도 있다."
#    6초 클립 **한 개 안에서** 장면이 갈아엎히는 것이다. 영상 만드는 쪽은
#    가만 두면 중간에 컷을 바꾸거나 다른 사람을 넣는다.
#    → 모든 컷에 **한 번에 찍은 것처럼** 이라고 못 박는다. 이 줄은 고정 문구라
#      normalize 가 80컷에 자동으로 갈아 끼운다 — **지금 대본도 그대로 고쳐진다.**
# ⭐⭐ 2026-08-21 운영자: "이럴 거면 절반 정도는 애니메이션풍으로 만드는 게
#    낫지 않아?" — 직감이 맞았다. **그림체로 가면 이번에 싸운 문제 넷이
#    한꺼번에 풀린다.**
#      ① 입 모양 — 더빙의 유일한 약점. 그림 입은 단순해서 어긋나도 안 걸린다
#      ② 유명인 정책 — 다섯 번 막혔다. 그림은 실존 인물로 안 읽힌다
#      ③ 얼굴이 컷마다 바뀜 — 단순한 얼굴이 훨씬 잘 고정된다
#      ④ 손가락 녹아듦 — 단순한 손은 원래 그런 것이라 티가 안 난다
#    ⚠️ 다만 **반반은 안 한다.** 한 영상 안에서 화풍이 바뀌면 싸구려로 보인다.
#       전부 하나로 통일한다.
#    ⚠️ 그리고 **만화가 아니라 그림체**다. 판결극장은 실제 판결이 밑천이라
#       무게가 빠지면 안 된다. 채도를 낮추고 선을 살린 반실사로 간다.
STYLE_FIX = ("STYLE: one single continuous take, no cut, no scene change, "
             "same location and same person from first frame to last, "
             "identical clothing throughout, "
             "semi-realistic hand-drawn illustration style with clean confident "
             "linework and soft cel shading, grounded adult proportions and "
             "restrained faces rather than cartoon exaggeration, muted "
             "desaturated palette, soft practical lighting, shallow depth of "
             "field, consistent line weight in every shot.")

# ⚠️ 영상에 글자가 나오는 가장 큰 원인은 '글자가 있는 물건'을 부른 것이다.
#    그런데 **두 번 연속으로 지나치게 넓은 낱말이 멀쩡한 대본을 막았다.**
#      1차 'phone'  — 전화기에는 글자가 없다. 전화 받는 장면이 모두 막혔다.
#      2차 'paper' — 종이 한 장에도 글자는 없다. 6화 1컷이 이것 하나로 반려됐다.
#    반려는 돈을 다시 쓰게 만들고, 글자가 조금 새는 것은 delogo 로 지우면 된다.
#    손해가 훨씬 큰 쪽으로 기울인다 — **그 자체가 글자인 것**만 무조건 막는다.
TEXT_HARD = ["signage", "banner", "billboard", "poster", "newspaper", "magazine",
             "headline", "subtitle", "caption", "nameplate", "plaque",
             "certificate", "whiteboard", "blackboard", "receipt", "text"]

# 글자가 나올 수도 있는 물건 — '읽는다 / 쓰여 있다' 와 같이 나올 때만 막는다.
#    봉투를 건네는 것은 되고, 봉투를 읽는 것은 안 된다.
TEXT_SOFT = ["paper", "document", "letter", "book", "screen", "monitor",
             "contract", "label", "file", "folder", "envelope", "sign"]

# 위 물건을 '글자가 보이게' 만드는 말
READING = ["read", "reads", "reading", "written", "writing", "printed", "print",
           "legible", "handwriting", "inscription", "title", "words", "letters",
           "signature"]


def word(w, s):
    return re.search(rf"\b{w}s?\b", s) is not None


def text_bait(head):
    """글자가 나올 물건을 불렀는가."""
    hit = [w for w in TEXT_HARD if word(w, head)]
    if any(word(r, head) for r in READING):
        hit += [w for w in TEXT_SOFT if word(w, head)]
    return hit


def load(p, dflt):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return dflt


def next_id(state):
    n = 1 + max((int(k[1:]) for k in state if re.fullmatch(r"S\d+", k)), default=0)
    return f"S{n:03d}"


def pick_case(queue, state):
    """아직 시리즈로 안 만든 것 중 점수가 가장 높은 판례."""
    used = {v.get("case_id") for v in state.values()}
    ready = [c for c in queue if c.get("gate_pass") and c["case_id"] not in used]
    ready.sort(key=lambda c: (c.get("gate_score") or 0, c.get("machine_score") or 0),
               reverse=True)
    return ready[0] if ready else None


def case_json(row):
    """판결문 본문 + 게이트가 찾아 둔 힌트를 프롬프트에 넣을 꼴로."""
    body = load(CASES / f"{row['case_id']}.json", {})
    keep = ["사건명", "선고일자", "사건종류명", "판시사항", "판결요지", "판례내용"]
    d = {k: body.get(k, "") for k in keep}
    if len(d["판례내용"]) > 60000:
        d["판례내용"] = d["판례내용"][:60000] + "\n\n…(이하 생략)"
    d["_한줄요약"] = row.get("one_line", "")
    d["_반전"] = row.get("twist_hint", "")
    d["_사건유형"] = row.get("case_type", "")
    return json.dumps(d, ensure_ascii=False, indent=2)


# ⚠️ 'extra people in focus' 는 **두 번째 주인공까지 막는 말**로 읽힌다.
#    주고받는 대화를 하려면 두 사람이 같이 화면에 있어야 한다. 막고 싶은 것은
#    지나가는 행인이지 상대역이 아니므로 'background extras' 로 못 박는다.
AVOID_FIX = ("Avoid: overlapping voices, on-screen text, signage, documents with visible writing, "
             "screens, background extras in focus, "
             "cutting to another shot, changing the background mid-shot, "
             "the person changing clothes or face mid-shot, "
             "swapping in a different person.")


# ⭐⭐ 2026-08-20 세 번째 — 얼굴 설명을 다 뺐는데도 플로우가 계속 막았다.
#    "이 프롬프트는 유명인의 동영상 생성에 관한 정책을 위반할 가능성이…"
#    남은 것은 **한글 배역말**이다. `SUBJECT: 남편 …` 에서 기계는 `남편` 이
#    무슨 뜻인지 모른다 — 아는 것은 "사람 자리에 들어간 모르는 낱말" 뿐이라
#    **사람 이름**으로 읽는다. 이름이 붙은 사람을 사진처럼 만들어 달라는 말이
#    되니 유명인 검사에 걸린다.
#    → 컷 프롬프트에서는 배역을 **영어 관계말**로 적는다.
#      대사(따옴표 안)는 한국어 그대로 둔다 — 그건 화면에 나올 말이다.
#    ⚠️ 화면·도서관·DM 에 보이는 이름은 그대로 한글이다. 바뀌는 것은
#      **플로우에 보내는 컷 프롬프트뿐**이다.
ROLE_EN = {
    "본처": "the wife", "아내": "the wife", "부인": "the wife",
    "남편": "the husband", "전남편": "the former husband",
    "내연녀": "the other woman", "내연남": "the other man",
    "상간녀": "the other woman", "상간남": "the other man",
    "며느리": "the daughter-in-law", "사위": "the son-in-law",
    "시동생": "the brother-in-law", "시누이": "the sister-in-law",
    "시어머니": "the mother-in-law", "시아버지": "the father-in-law",
    "장모": "the mother-in-law", "장인": "the father-in-law",
    "어머니": "the mother", "아버지": "the father", "엄마": "the mother",
    "아빠": "the father", "아들": "the son", "딸": "the daughter",
    "장남": "the eldest son", "장녀": "the eldest daughter",
    "동생": "the younger sibling", "형": "the older brother",
    "누나": "the older sister", "언니": "the older sister",
    "오빠": "the older brother", "고모": "the aunt", "이모": "the aunt",
    "삼촌": "the uncle", "조카": "the nephew", "손자": "the grandson",
    "손녀": "the granddaughter", "할머니": "the grandmother",
    "할아버지": "the grandfather", "사장": "the boss",
    "동업자": "the business partner", "친구": "the friend",
    "변호사": "the lawyer", "의사": "the doctor", "간호사": "the nurse",
    "직원": "the employee", "이웃": "the neighbour",
}
WOMAN = ["woman", "female", "her ", "she "]


def role_en(ch, used):
    """배역 하나 → 컷 프롬프트에 쓸 영어 관계말 (겹치면 번호를 붙인다)."""
    nm = (ch.get("name") or "").strip()
    en = ROLE_EN.get(nm)
    if not en:
        low = (ch.get("flow_prompt") or "").lower()
        en = "the woman" if any(w in low for w in WOMAN) else "the man"
    base, i = en, 2
    while en in used:
        en, i = f"{base} ({i})", i + 1
    used.add(en)
    return en


def name_map(doc):
    """한글 배역말 → 영어 관계말. 긴 이름부터 바꿔야 겹치지 않는다."""
    used, out = set(), {}
    for ch in doc.get("characters") or []:
        nm = (ch.get("name") or "").strip()
        if nm:
            out[nm] = role_en(ch, used)
    return dict(sorted(out.items(), key=lambda kv: len(kv[0]), reverse=True))


def _outside_quotes(line, fn):
    """따옴표 **밖**만 바꾼다 (대사는 한국어 그대로 둬야 한다)."""
    bits = line.split('"')
    return '"'.join(b if i % 2 else fn(b) for i, b in enumerate(bits))


def fix_names(doc):
    """컷 프롬프트의 한글 배역말을 영어 관계말로 바꾼다."""
    mp = name_map(doc)
    if not mp:
        return 0
    # 인물표에도 적어 둔다 — 인물 설명 칸(flow_desc)이 이것을 쓴다
    for ch in doc.get("characters") or []:
        en = mp.get((ch.get("name") or "").strip())
        if en and ch.get("role_en") != en:
            ch["role_en"] = en
            ch["flow_desc"] = ""          # 다음 fill 에서 영어로 다시 만든다
    def sub(t):
        for ko, en in mp.items():
            t = t.replace(ko, en)
        return t
    n = 0
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
            lines = (c.get("prompt") or "").split("\n")
            for i, l in enumerate(lines):
                new = _outside_quotes(l, sub)
                if new != l:
                    lines[i], n = new, n + 1
            c["prompt"] = "\n".join(lines)
    doc["_name_map"] = mp
    return n


# ⭐ 제미나이가 다시 써 온 것에서 가져온 둘째 — **입모양 맞추기를 ACTION 에.**
#    소리 줄(AUDIO)보다 **그림 지시 옆**에 두는 것이 더 잘 먹는다.
LIPSYNC = (" Both people keep their lips moving in exact sync with the "
           "Korean lines they say.")


# ⭐⭐ 2026-08-21 — 실제로 만든 쇼츠를 눈으로 보고 고친다.
#    플로우가 `Medium two-shot` 을 **전신이 다 나오는 넓은 그림**으로 그렸다.
#    가로 영상에서는 괜찮지만, 세로 쇼츠로 잘라 놓으면 얼굴이 화면 높이의
#    8% 밖에 안 된다 — 휴대전화로 보면 **표정이 하나도 안 읽힌다.**
#    쇼츠에서 표정이 안 보이면 그냥 넘긴다.
#    → 모든 컷에 "허리 위로, 얼굴이 크게" 를 못 박는다.
#      (넓게 잡으라고 쓴 컷도 이 말이 있으면 훨씬 당겨서 그린다)
#    ⚠️ 처음에 "close enough to **read** every expression" 이라고 썼다가
#       **read** 가 '글자 읽는 물건' 검사에 걸려 봉투가 나오는 컷을 막았다.
#       (screen · words 에 이어 세 번째다. 고정 문구는 다른 검사에 걸리는
#        낱말을 피해서 쓴다 — 이제 시험이 **모든 고정 문구를 한꺼번에** 본다)
FRAMING = (" Framed from the waist up so both faces fill much of the frame, "
           "close enough that every expression is clear.")


def fix_framing(doc):
    """SHOT 줄에 '허리 위로, 얼굴 크게' 를 붙인다."""
    n = 0
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
            lines = (c.get("prompt") or "").split("\n")
            for i, l in enumerate(lines):
                if not l.startswith("SHOT:") or FRAMING.strip() in l:
                    continue
                lines[i], n = l.rstrip() + FRAMING, n + 1
            c["prompt"] = "\n".join(lines)
    return n


def fix_lipsync(doc):
    """ACTION 줄 끝에 입모양 맞추기를 붙인다."""
    n = 0
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
            if "DIALOGUE: None." in (c.get("prompt") or ""):
                continue
            lines = (c.get("prompt") or "").split("\n")
            for i, l in enumerate(lines):
                if not l.startswith("ACTION:") or LIPSYNC.strip() in l:
                    continue
                lines[i], n = l.rstrip() + LIPSYNC, n + 1
            c["prompt"] = "\n".join(lines)
    return n


# ⭐⭐ 2026-08-20 운영자: "과거 제작된 영상의 연장선상에서 제작될 수 있도록
#    scene extension(장면 연장)도 매 프롬프트에 반영하자."
#    컷 하나하나를 따로 뽑으면 다섯 조각이 서로 남남처럼 보인다.
#    **앞 컷에서 이어지는 장면**이라고 말해 주면 방·빛·사람이 이어진다.
#    · 같은 화 안에서 장소가 같으면 → "바로 그 방에서 이어진다"
#    · 장소가 바뀌면 → "같은 사람·같은 색으로, 장소만 옮긴다"
#    · 화가 넘어가면 → "같은 이야기의 뒷날. 사람과 색은 그대로"
#    · 맨 첫 컷 → "이야기의 첫 장면. 여기서부터 이어진다"
CONT_FIRST = ("CONTINUITY: this is the opening shot of the story; establish "
              "the room and the people here, and every later shot continues "
              "from this look.")


def _gist(prompt):
    """앞 컷이 무엇으로 끝났는지 한 토막 (동작 줄에서 딴다)."""
    act = next((l for l in str(prompt or "").split("\n")
                if l.startswith("ACTION:")), "")
    act = act[len("ACTION:"):].replace(LIPSYNC, "").strip().rstrip(".")
    return act[:110]


def _place(prompt):
    return next((l for l in str(prompt or "").split("\n")
                 if l.startswith("SETTING:")), "")


def fix_continuity(doc):
    """컷마다 '앞 장면에서 이어진다' 를 적어 준다 (장면 연장)."""
    flat = [(e, c) for e in (doc.get("episodes") or [])
            for c in (e.get("cuts") or [])]
    n = 0
    for k, (e, c) in enumerate(flat):
        if k == 0:
            line = CONT_FIRST
        else:
            pe, pc = flat[k - 1]
            gist = _gist(pc.get("prompt"))
            if pe is not e:
                line = ("CONTINUITY: this shot belongs to the same continuing "
                        "story as the previous shot, in which " + gist +
                        ". It is a later moment, so the place may change, but "
                        "the same people, the same faces, the same voices and "
                        "exactly the same colour grade carry over.")
            elif _place(pc.get("prompt")) == _place(c.get("prompt")):
                line = ("CONTINUITY: this shot continues straight on from the "
                        "previous shot, in which " + gist + ". Same room, same "
                        "people, same clothes, same hair, same light and the "
                        "same colour grade — pick up exactly where that shot "
                        "ended, as one unbroken scene.")
            else:
                line = ("CONTINUITY: this shot follows the previous shot, in "
                        "which " + gist + ". The scene moves to another place "
                        "a little later, but the same people, the same "
                        "clothes, the same faces and exactly the same colour "
                        "grade carry over.")
        lines = [l for l in (c.get("prompt") or "").split("\n")
                 if not l.startswith("CONTINUITY:")]
        at = next((i for i, l in enumerate(lines)
                   if l.startswith(("COLOR:", "STYLE:"))), len(lines))
        lines.insert(at, line)
        if c.get("prompt") != "\n".join(lines):
            n += 1
        c["prompt"] = "\n".join(lines)
    return n


def fix_color(doc):
    """모든 컷에 **똑같은** 색 지시를 넣는다 (색이 튀면 딴 작품처럼 보인다)."""
    n = 0
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
            lines = [l for l in (c.get("prompt") or "").split("\n")
                     if not l.startswith("COLOR:")]
            at = next((i for i, l in enumerate(lines)
                       if l.startswith("STYLE:")), len(lines))
            lines.insert(at, COLOR_FIX)
            if c.get("prompt") != "\n".join(lines):
                n += 1
            c["prompt"] = "\n".join(lines)
    return n


def fix_subject_dup(doc):
    """SUBJECT 줄에서 **같은 사람이 두 번** 나오는 것을 지운다.

    ⚠️ 모델이 실제로 이렇게 썼다 (S001 13줄) —
         `남편 in a black suit facing 본처 in a grey blouse facing 남편 in a black suit.`
       A가 B를 보는데 다시 A를 본다는 말이다. 영상 만드는 쪽이 이걸 보면
       사람이 셋인 줄 알고 **한 명을 더 그려 넣는다.** 앞의 것만 남긴다.
    """
    names = sorted([(c.get("name") or "").strip()
                    for c in (doc.get("characters") or []) if (c.get("name") or "").strip()],
                   key=len, reverse=True)
    n = 0
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
            lines = (c.get("prompt") or "").split("\n")
            for i, l in enumerate(lines):
                if not l.startswith("SUBJECT:"):
                    continue
                body = l[len("SUBJECT:"):].strip()
                dot = "." if body.endswith(".") else ""
                parts = re.split(r"\s+facing\s+", body.rstrip("."))
                seen, keep = set(), []
                for pt in parts:
                    who = next((nm for nm in names if pt.strip().startswith(nm)),
                               pt.strip()[:12])
                    if who in seen:
                        continue
                    seen.add(who)
                    keep.append(pt.strip())
                new = "SUBJECT: " + " facing ".join(keep) + dot
                if new != l:
                    lines[i], n = new, n + 1
            c["prompt"] = "\n".join(lines)
    return n


# ⭐⭐ 2026-08-22 운영자: "프롬프트에서 자꾸 옷이랑 뒤에 배경이 바뀌어.
#    이전에 생성된 이미지와 연속된다는 말이 추가될 필요가 있을 거 같다."
#
#    ⚠️ 그 말은 **이미 들어 있다.** CONTINUITY 줄이 컷마다
#       "Same room, same people, same clothes, same hair, same light" 라고
#       말하고 있는데도 바뀌었다.
#    ⚠️ 까닭: **플로우는 앞 컷을 기억하지 못한다.** 컷마다 백지에서 새로 그린다.
#       앞이 무엇이었는지 모르는데 "앞이랑 똑같이" 그릴 수가 없다.
#       그러니 그 말을 더 세게 써 봐야 소용이 없다.
#
#    진짜 까닭은 **말이 뭉뚱그려져 있는 것**이다 —
#       `a casual jacket`             → 세상의 온갖 자켓 중 아무거나
#       `a simple cardigan`           → 매번 다른 색
#       `Korean apartment living room` → 매번 다른 거실
#    같은 글자를 다섯 컷에 똑같이 써 놔도, 그 글자가 가리키는 것이 하나가
#    아니면 다섯 번 다르게 나온다.
#
#    → 고칠 것은 "같게 그려라" 가 아니라 **무엇인지 못 박는 것**이다.
#      색·소재·가구까지 적어 두면 기억이 없어도 매번 같은 것이 나온다.
#      이것이 기억 없는 모델에게 연속성을 주는 유일한 방법이다.
#
#    ⚠️ 얼굴·나이는 절대 안 적는다 — 유명인 정책에 다섯 번 막혔던 자리다.
#      옷과 가구만 적는다.
VAGUE = re.compile(r"\b(a |an |the )?(casual|simple|plain|ordinary|everyday|"
                   r"nice|smart|basic|neat|regular|typical|comfortable)\s+", re.I)

# 뭉뚱그린 옷 이름 → 색·소재까지 박은 말. 사람마다 다른 것이 가게 돌려 쓴다.
WEAR_LOOK = {
    "cardigan": ["a moss-green ribbed knit cardigan over a cream floral blouse",
                 "a dusty-blue wool cardigan over a white round-neck top"],
    "jacket":   ["an olive-green cotton work jacket over a grey crewneck, "
                 "with dark charcoal trousers",
                 "a faded navy canvas jacket over a black henley, "
                 "with grey trousers"],
    "dress":    ["a deep wine-red sleeveless dress with a thin gold necklace",
                 "a black wrap dress with a narrow belt"],
    "suit":     ["a charcoal single-breasted suit with a white shirt and "
                 "a slate-grey tie",
                 "a dark navy suit with a pale blue shirt, no tie"],
    "coat":     ["a camel wool coat over a black turtleneck",
                 "a dark grey trench coat over a white shirt"],
    "shirt":    ["a pale blue oxford shirt with the sleeves rolled up",
                 "a soft white linen shirt"],
    "blouse":   ["a cream silk blouse with a small round collar",
                 "a pale lilac blouse with pleated cuffs"],
    "sweater":  ["a heather-grey lambswool sweater",
                 "a burgundy cable-knit sweater"],
}
WEAR_ANY = ["a stone-grey cotton overshirt over a white tee, dark trousers",
            "a deep-green knit top with a thin cardigan, black trousers"]

# 뭉뚱그린 장소 → 가구·창·빛까지 박은 말. **같은 장소는 늘 같은 글자**로.
ROOM_LOOK = {
    "living room": ("a beige three-seat fabric sofa along the left wall, "
                    "a tall dark-wood bookshelf behind, a wide balcony window "
                    "with the night city beyond, a low walnut coffee table "
                    "with a single white ceramic vase, warm floor lamp in the "
                    "right corner"),
    "kitchen": ("pale wood cabinets, a white countertop with a steel kettle, "
                "a small round dining table with two chairs, a window over "
                "the sink"),
    "bedroom": ("a low bed with a grey linen duvet, a wooden nightstand with "
                "a small lamp, a mirrored wardrobe along the right wall"),
    "hallway": ("a narrow corridor with pale grey walls, a steel apartment "
                "door with a keypad lock, a single ceiling light, a folded "
                "cardboard box against the skirting"),
    "courtroom": ("pale wood panelling, a raised bench with a folded flag "
                  "to one side, rows of empty wooden benches, tall frosted "
                  "windows on the left"),
    "office": ("a plain desk with a closed laptop and a stack of paper files, "
               "a grey filing cabinet behind, vertical blinds half drawn"),
    "cafe": ("a small square table by a window, two mugs, a wooden counter "
             "with a chalkboard menu behind"),
    "car": ("the front seats of a small sedan, dark dashboard, rain-speckled "
            "windscreen, city lights blurred outside"),
    "restaurant": ("a booth table with a white cloth, a pendant lamp low over "
                   "the table, dark panelled wall behind"),
}


def _pick(bank, k):
    return bank[k % len(bank)]


# ⭐⭐ 2026-08-22 — 제미나이 제안: "이전 영상에 이어서 제작된다는 말을 넣어라."
#
#    그냥 컷 프롬프트에 넣는 것은 소용이 없다. 플로우는 새로 만들 때 앞 컷을
#    기억하지 못하기 때문이다 (그래서 옷·배경을 색·가구까지 못 박았다).
#    **그런데 플로우에는 [이 영상에서 이어서 만들기](장면 연장)가 있다.**
#    그 기능을 쓰면 앞 영상의 **마지막 프레임을 실제로 물려받는다** — 그때는
#    "이어서 만든다" 는 말이 진짜 뜻을 갖는다.
#
#    다만 그때는 프롬프트도 달라야 한다. 방·옷·빛을 다시 세우면 물려받은
#    화면과 싸워서 오히려 튄다. **바뀌는 것만** 적어야 한다.
#    → 같은 장소가 이어지는 컷에는 **이어서 만들기용 짧은 프롬프트**를 따로 붙인다.
EXT_HEAD = ("Continue directly from the final frame of the previous clip. "
            "Same room, same people, same clothes, same hair, same light — "
            "do not re-establish anything, just carry straight on.")


def fix_extend(doc):
    """같은 장소가 이어지는 컷에 **이어서 만들기용** 프롬프트를 붙인다."""
    n = 0
    for e in doc.get("episodes") or []:
        cuts = e.get("cuts") or []
        for i, c in enumerate(cuts):
            if i == 0 or _place(cuts[i - 1].get("prompt")) != _place(c.get("prompt")):
                if c.pop("ext", None) is not None:
                    n += 1
                continue
            keep = [l for l in (c.get("prompt") or "").split("\n")
                    if l.startswith(("SHOT:", "ACTION:", "DIALOGUE:", "AUDIO:",
                                     "VOICE:", "  "))]
            ext = HEAD_FIX + "\n" + EXT_HEAD + "\n" + "\n".join(keep)
            if c.get("ext") != ext:
                c["ext"] = ext
                n += 1
    return n


def fix_look(doc):
    """옷과 장소를 **색·가구까지 못 박는다.** 뭉뚱그린 말은 매번 다르게 나온다."""
    n = 0
    # ① 옷 — 인물마다 하나를 정해 그 화 내내 똑같이
    worn, k = {}, 0
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
            for i, l in enumerate((c.get("prompt") or "").split("\n")):
                if not l.startswith("SUBJECT:"):
                    continue
                for m in re.finditer(r"\bin ([^,.]+?)(?=\s+facing\b|[,.]|$)", l):
                    piece = m.group(1).strip()
                    if piece in worn:
                        continue
                    if not VAGUE.search(piece) and len(piece.split()) > 4:
                        continue                  # 이미 자세하다 — 그냥 둔다
                    base = next((w for w in WEAR_LOOK if w in piece.lower()), "")
                    worn[piece] = (_pick(WEAR_LOOK[base], k) if base
                                   else _pick(WEAR_ANY, k))
                    k += 1
    # ② 장소 — 같은 장소는 늘 같은 글자로
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
            lines = (c.get("prompt") or "").split("\n")
            for i, l in enumerate(lines):
                if l.startswith("SUBJECT:"):
                    new = l
                    for old, good in worn.items():
                        new = new.replace("in " + old, "wearing " + good)
                    if new != l:
                        lines[i] = new
                        n += 1
                elif l.startswith("SETTING:"):
                    low = l.lower()
                    room = next((r for r in ROOM_LOOK if r in low), "")
                    if room and ROOM_LOOK[room][:24] not in l:
                        body = l[len("SETTING:"):].strip().rstrip(".")
                        lines[i] = f"SETTING: {body} — {ROOM_LOOK[room]}."
                        n += 1
            c["prompt"] = "\n".join(lines)
    return n


def fix_outfits(doc):
    """모든 컷에서 같은 인물은 **그 화 안에서 똑같은 옷**을 입게 만든다.

    ⚠️ 2026-08-20 — 1화 완성본을 보니 본처의 카디건이 1컷 초록 → 3컷 베이지 →
       5컷 초록으로 튀었다. SUBJECT 에 `본처 in a simple cardigan` 이라고만 써
       색을 안 정해 줬기 때문이다. 영상 만드는 쪽은 매번 새로 고른다.

    ⚠️ 그리고 이걸 고치면서 한 번 더 틀렸다. **16화 전체에서** 가장 흔한 옷을
       골랐더니 1화 거실 장면에 법정 정장을 입혔다. 사람은 날마다 옷을 갈아입는다 —
       맞춰야 할 범위는 **한 화 안**이다.

    · 인물표에 `outfit` 이 있으면 그것으로 (글쓴이가 정한 것)
    · 없으면 **그 화에서 가장 많이 쓴 옷차림**으로 나머지를 맞춘다 (0원 수리)
    · `face_tag` 는 있으면 이름 뒤에 똑같이 붙인다 — 플로우 캐릭터를 안 붙여도
      얼굴이 잡히게 (첫 화에서 남편이 컷마다 다른 배우로 나왔다)
    """
    fixed, face = {}, {}
    for c in doc.get("characters") or []:
        nm = (c.get("name") or "").strip()
        if not nm:
            continue
        if (c.get("outfit") or "").strip():
            fixed[nm] = c["outfit"].strip()
        if (c.get("face_tag") or "").strip():
            face[nm] = c["face_tag"].strip()
    names = all_names(doc)
    # 인물표는 한글 이름으로 적혀 있으므로, 영어 관계말에도 같은 옷을 물려준다
    for ko, en in (doc.get("_name_map") or {}).items():
        if ko in fixed and en not in fixed:
            fixed[en] = fixed[ko]
    if not names:
        return 0

    def subj_of(c):
        return next((l for l in (c.get("prompt") or "").split("\n")
                     if l.startswith("SUBJECT:")), "")

    n = 0
    for e in doc.get("episodes") or []:
        cuts = e.get("cuts") or []
        # 이 화에서 각 인물이 무엇을 입었나 → 가장 많은 것으로 통일
        wear = dict(fixed)
        for nm in names:
            if nm in wear:
                continue
            v = []
            for c in cuts:
                # ⚠️ 여기서 `([^,.]*)` 로 끝까지 먹으면
                #    "본처 in a cardigan facing 남편 in a jacket" 에서
                #    본처의 옷이 **"a cardigan facing 남편 in a jacket"** 이 된다.
                #    그대로 되돌려 넣으면 `facing …` 이 한 줄에 네 번 겹친다
                #    (실제로 S001 17줄이 이렇게 망가졌다). `facing` 에서 끊는다.
                m = re.search(rf"{re.escape(nm)}(?:\([^)]*\))?\s+in\s+"
                              rf"([^,.]*?)(?=\s+facing\s|[,.]|$)", subj_of(c))
                if m:
                    v.append(m.group(1).strip())
            if v:
                wear[nm] = max(set(v), key=v.count)
        if not wear and not face:
            continue
        for c in cuts:
            lines = (c.get("prompt") or "").split("\n")
            for i, l in enumerate(lines):
                if not l.startswith("SUBJECT:"):
                    continue
                new = l
                for nm, of in wear.items():
                    new = re.sub(rf"({re.escape(nm)})(?:\([^)]*\))?\s+in\s+"
                                 rf"[^,.]*?(?=\s+facing\s|[,.]|$)",
                                 rf"\1 in {of}", new)
                # ⭐⭐ 2026-08-20 — 여기서 이름 뒤에 얼굴을 박았더니 플로우가
                #    **모든 컷을 거절했다**: "유명인의 동영상 생성에 관한 정책을
                #    위반할 가능성이 있습니다."
                #    `남편(55, square face, short neatly parted black hair)` 는
                #    기계 눈에 "**남편**이라는 사람, 55살, 이 얼굴" 로 보인다 —
                #    실존 인물을 찍어 달라는 말과 똑같은 꼴이다.
                #    (본처·남편은 배역말인데 기계는 사람 이름으로 읽는다)
                #    첫 영상이 성공했을 때는 `남편 in a casual jacket` 이었다.
                #    얼굴은 **플로우 캐릭터(기준 사진)** 가 잡아 주는 몫이고,
                #    컷 프롬프트는 이름 + 옷차림까지만 적는다.
                #    → 박아 둔 것이 있으면 **떼어 낸다.**
                for nm in names:
                    new = re.sub(rf"(?<![\w가-힣]){re.escape(nm)}\([^)]*\)",
                                 nm, new)
                if new != l:
                    lines[i] = new
                    n += 1
            c["prompt"] = "\n".join(lines)
    return n


# 받침이 있고 없고에 따라 조사가 달라진다. '당신' 은 받침이 있으므로
# 받침 있는 쪽 조사로 바꿔 줘야 한다 — 안 그러면 "당신가" 가 된다.
JOSA = {"가": "이", "는": "은", "를": "을", "와": "과", "야": "아",
        "라": "이라", "랑": "이랑", "로": "으로"}


def to_you(text, word):
    """'저 여자가' → '당신이' 처럼 조사까지 맞춰 바꾼다."""
    def rep(m):
        return "당신" + JOSA.get(m.group(1) or "", m.group(1) or "")
    return re.sub(re.escape(word) + r"(랑|라|가|는|를|와|야|로)?", rep, text)


# 닿는 동작 → 안 닿고도 같은 뜻이 되는 동작 (2026-08-20)
#   첫 영상에서 "grabs 남편 by the arm" 때문에 손가락이 옷 속으로 녹아들었다.
#   반려하면 16화를 다시 사야 하므로 **우리가 바꿔 준다.**
# 사람을 가리키는 말. **사람에게** 닿는 것만 바꾼다.
# ⚠️ 물건에 닿는 것은 오히려 권장한다(책상을 내리치는 것은 잘 그려진다).
#    처음에는 상대를 안 가려서 `slams his hand on the table`(책상을 내리침)과
#    `hugs the keys`(열쇠를 껴안음)까지 바꿔 문장이 망가졌다. 그래서
#    **상대가 사람일 때만** 바꾸도록 사람 이름·사람 낱말을 넣어 맞춘다.
PERSON_WORDS = ["her", "him", "his wife", "her husband", "the wife",
                "the husband", "the woman", "the man", "the other woman",
                "the other man", "the daughter", "the son", "the mother",
                "the father", "the girl", "the boy"]

# 왼쪽이 찾을 말, 오른쪽이 바꿔 넣을 말. `{P}` 자리에 사람이 와야만 바뀐다.
TOUCH_FIX = [
    (r"\bgrabs?\s+{P}\s+by the (?:arm|wrist|shoulder|collar)s?",
     r"steps in front of \1, blocking the way"),
    (r"\bgrabs?\s+{P}(?:'s)?\s+(?:arm|wrist|hand|shoulder)s?",
     r"reaches toward \1 but stops short"),
    (r"\bgrabs?\s+{P}", r"steps in front of \1, blocking the way"),
    (r"\bshakes?\s+off\s+(?:her|his)\s+hands?", "pulls away sharply"),
    (r"\bshakes?\s+{P}\s+by the shoulders?", r"leans toward \1, shouting"),
    (r"\b(?:pushes|shoves)\s+{P}", r"steps hard toward \1"),
    (r"\bpulls?\s+{P}\s+(?:closer|back|toward|away)", r"turns sharply to \1"),
    (r"\b(?:hugs?|embraces?)\s+{P}",
     r"stands close to \1, arms at the sides"),
    (r"\bhands?\s+(?:over\s+)?(?:a|an|the|his|her)?\s*(.+?)\s+to\s+{P}",
     r"sets the \1 down on the table and steps back"),
    (r"\bhands?\s+{P}\s+(?:a|an|the|his|her)\s+(\S+)",
     r"sets the \2 down on the table and steps back"),
    (r"\btakes?\s+(?:her|his)\s+hands?", "reaches out but stops short"),
    (r"\bclutches?\s+(?:her|his)\s+(?:arm|sleeve|collar)s?",
     "grips her own sleeve"),
    (r"\bsnatch(?:es)?\s+(.+?)\s+from\s+{P}",
     r"stares at the \1 in \2's hand"),
    (r"\btouch(?:es)?\s+{P}", r"stops just short of \1"),
    (r"\bslaps?\s+{P}", r"raises a hand at \1 and freezes"),
    (r"\bholds?\s+{P}(?:'s)?\s+(?:arm|hand|wrist|shoulder)s?",
     r"stays a step away from \1"),
]

# 바꿔 넣는 말에 이미 태도가 들어 있다("blocking the way"). 원래 문장 끝에
# 붙어 있던 태도말(firmly, aggressively …)을 같이 지우지 않으면
# "pulls away sharply aggressively" 처럼 겹쳐서 어색해진다.
ADV = r"(?:\s+(?:very|so)?\s*\w+ly)?"


def _person_re(doc):
    """이 대본에 나오는 사람을 가리키는 말 하나로 묶는다(긴 것부터)."""
    names = all_names(doc)
    words = sorted([w for w in names + PERSON_WORDS if w],
                   key=len, reverse=True)
    # ⚠️ 인물표에 없는 사람이 ACTION 에 나오기도 한다(시동생 등). ACTION 줄은
    #    이름 말고는 전부 영어이므로 **한글 덩어리는 곧 사람 이름**이다.
    return "(" + "|".join([re.escape(w) for w in words] + [r"[가-힣]+"]) + ")"


def fix_touch(doc):
    """서로 닿는 동작을 **안 닿는 동작**으로 바꾼다.

    ⚠️ 첫 영상 1화 1컷이 `grabs 남편 by the arm` 이었고, 실제로 여자 손가락이
       남자 옷 속으로 녹아들었다. 영상 만드는 쪽이 닿는 자리를 못 그린다.
       알리기만 해서는 16화가 그대로 나가므로 **우리가 바꿔 준다.**
       바꾼 곳은 손볼 곳으로 알린다.
    ⚠️ 물건은 건드리지 않는다 — 책상을 내리치는 동작은 화를 보여 주는
       가장 좋은 방법이고 오류도 안 난다.
    """
    P = _person_re(doc)
    rules = [(re.compile(pat.replace("{P}", P) + ADV, re.I), rep)
             for pat, rep in TOUCH_FIX]
    out = []
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
            lines = (c.get("prompt") or "").split("\n")
            for i, l in enumerate(lines):
                if not l.startswith("ACTION:"):
                    continue
                new = l
                for rx, rep in rules:
                    new = rx.sub(rep, new)
                if new != l:
                    lines[i] = new
                    out.append(f"{e.get('no')}화 {c.get('n')}컷: 닿는 동작을 바꿨다 "
                               f"— {l[8:52].strip()} → {new[8:52].strip()}")
            c["prompt"] = "\n".join(lines)
    doc["_touch_fixed"] = out
    return len(out)


def fix_facing(doc):
    """맞은편 사람을 3인칭으로 부른 대사를 '당신' 으로 고친다.

    ⚠️ 대사를 우리가 손대는 것은 조심스럽지만, 이것 하나로 16화를 다시 사는
       것이 더 나쁘다. "저 여자가 이유였어?" → "당신이 이유였어?" 는 뜻이
       그대로고 말도 자연스럽다. 고친 곳은 **손볼 곳으로 반드시 알린다.**
    """
    chars = doc.get("characters") or []
    out = []
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
            hit = facing_error(c, chars)
            if not hit:
                continue
            lines = (c.get("prompt") or "").split("\n")
            a, b = dia_span(lines)
            for i in range(a or 0, b or 0):
                l = lines[i]
                new = l
                for w in hit:
                    new = to_you(new, w)
                if new != l:
                    lines[i] = new
                    out.append(f"{e.get('no')}화 {c.get('n')}컷: "
                               f"'{', '.join(hit)}' → '당신' 으로 고쳤다 "
                               f"(맞은편 사람을 남 부르듯 했다) — 읽어 보십시오")
            c["prompt"] = "\n".join(lines)
            # 자막도 같이
            sub = c.get("subtitle") or ""
            for w in hit:
                sub = to_you(sub, w)
            c["subtitle"] = sub
    doc["_facing_fixed"] = out
    return len(out)


def normalize(doc):
    """고쳐 쓸 수 있는 것은 **버리지 말고 우리가 고친다.**

    ⚠️ 2026-08-19 — STYLE 줄 한 글자가 다르다고 16화 전체를 버리고 다시 사게
       돼 있었다. 그 줄은 어차피 **모든 컷에서 똑같아야 하는 고정 문구**라
       모델에게 받을 이유가 없다. 여기서 갈아 끼운다.
       (내용에 관한 것 — 후킹·글자 나올 물건·대사 길이 — 은 고치지 않는다.
        그건 이야기를 바꾸는 일이라 사람이 판단할 몫이다.)"""
    n = 0
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
            lines = (c.get("prompt") or "").split("\n")
            out = []
            for l in lines:
                if l.startswith("STYLE:") and l != STYLE_FIX:
                    l, n = STYLE_FIX, n + 1
                elif l.startswith("Avoid:") and l != AVOID_FIX:
                    l, n = AVOID_FIX, n + 1
                out.append(l)
            # 대사 없는 컷에 DIALOGUE 줄을 통째로 빠뜨리는 일이 있다.
            # 빈 값이 'None.' 으로 정해져 있으므로 우리가 끼워 넣는다
            # (이야기를 바꾸는 게 아니라 빈칸을 채우는 것뿐이다).
            if not any(l.startswith("DIALOGUE:") for l in out):
                at = next((i for i, l in enumerate(out)
                           if l.startswith("SETTING:")), len(out))
                out.insert(at, "DIALOGUE: None.")
                n += 1
            # 아예 빠뜨린 경우에도 우리가 붙인다 — 고정 문구라 받을 이유가 없다
            if not any(l.startswith("STYLE:") for l in out):
                out.append(STYLE_FIX)
                n += 1
            # Avoid 는 **맨 끝**이어야 한다. 순서만 바뀐 것으로 16화를 다시 살 수 없다.
            out = [l for l in out if not l.startswith("Avoid:")]
            out.append(AVOID_FIX)
            # ⭐ 머리말은 **맨 앞**이어야 한다. 없으면 붙여 넣을 때 `SHOT:` 이
            #    주소 이름으로 읽혀 글자가 %20 · %EB.. 로 깨진다 (2026-08-20).
            # ⚠️ 예전엔 머리말 글자("Live-action Korean drama,")를 그대로 베껴
            #    걸러 냈다. 머리말을 손보는 순간 옛 것이 안 걸러져 **줄이 매번
            #    하나씩 늘어났다.** 고정 문구를 글자로 베끼면 늘 이렇게 된다.
            #    → 콜론 없는 '머리말 꼴' 을 통째로 걸러 내고 지금 것을 넣는다.
            out = [l for l in out if l.strip()
                   and l != HEAD_FIX
                   and not re.match(r"^[^:]*single continuous take\.\s*$", l)]
            out.insert(0, HEAD_FIX)
            if (c.get("prompt") or "").split("\n")[:1] != [HEAD_FIX]:
                n += 1
            c["prompt"] = "\n".join(out)
    if n:
        print(f"  (고정 문구 {n}줄을 우리가 채워 넣었다 — 이것 때문에 버리지 않는다)")
    tf = fix_touch(doc)
    if tf:
        print(f"  (서로 닿는 동작 {tf}곳을 안 닿는 동작으로 바꿨다)")
    j = fix_facing(doc)
    if j:
        print(f"  (맞은편 사람을 3인칭으로 부른 대사 {j}곳을 고쳤다)")
    # ⭐ 인물 기준 사진 프롬프트를 제대로 된 것으로 채운다 (2026-08-20 운영자
    #    지시: "인물 생성 프롬프트가 너무 짧아 배경이 이상하게 뜬다").
    #    25낱말짜리로는 배경·자세·화면잡기가 매번 새로 뽑힌다.
    q = fix_subject_dup(doc)
    if q:
        print(f"  (한 줄에 같은 사람을 두 번 적은 SUBJECT {q}줄을 정리했다 "
              f"— 그대로 두면 사람이 한 명 더 그려진다)")
    # ⭐⭐ 2026-08-20 운영자: "플로우에서 캐릭터 음성을 미리 지정해 둔 것이
    #    원인으로 보인다. 그걸 해제할 테니 **캐릭터 정보와 매번 프롬프트에**
    #    목소리 정보를 넣자."
    #    → 인물표에 목소리를 박아 두면 인물 설명 칸(flow_desc)에도 실린다.
    for ch in doc.get("characters") or []:
        v = voice_of(ch)
        if (ch.get("voice") or "").strip() != v:
            ch["voice"], ch["flow_desc"] = v, ""
    c2 = charsheet.fill(doc)
    if c2:
        print(f"  (인물 {c2}명의 기준 사진 프롬프트를 풀세트로 채웠다)")
    k = fix_outfits(doc)
    k += fix_look(doc)
    k += fix_extend(doc)
    if k:
        print(f"  (옷차림 {k}줄을 인물표대로 맞췄다 — 컷마다 옷이 바뀌면 딴사람으로 보인다)")
    # ⭐ 배역말 바꾸기는 **맨 마지막**이다. 위의 고치개들이 모두 한글 이름으로
    #    찾기 때문에, 먼저 바꿔 버리면 하나도 안 걸린다.
    nm = fix_names(doc)
    if nm:
        print(f"  (컷 프롬프트의 한글 배역말 {nm}줄을 영어 관계말로 바꿨다 "
              f"— 기계가 사람 이름으로 읽어 유명인 검사에 걸린다)")
        charsheet.fill(doc)        # 인물 설명 칸도 영어 관계말로 다시 만든다
    # ⭐ 목소리·소리 줄은 **맨 마지막**. 배역말이 영어로 바뀐 뒤라야
    #    VOICE 줄의 이름이 DIALOGUE 줄의 이름과 맞는다.
    fr = fix_framing(doc)
    if fr:
        print(f"  (SHOT {fr}줄에 '허리 위로·얼굴 크게' 를 붙였다 — 세로 쇼츠에서 "
              f"얼굴이 작으면 표정이 안 읽힌다)")
    fix_lipsync(doc)
    g = fix_dialogue_lang(doc)
    if g:
        print(f"  (대사 {g}줄에 한국어 표시·숨 쉴 자리를 넣었다 — 영어 억양이 "
              f"한글에 씌워지는 것을 막는다)")
    k2 = fix_color(doc)
    if k2:
        print(f"  (색 지시 {k2}컷을 하나로 맞췄다 — 컷마다 색이 튀면 딴 작품처럼 보인다)")
    k3 = fix_continuity(doc)
    if k3:
        print(f"  (앞 장면에서 이어진다는 지시 {k3}컷에 붙였다 — 장면 연장)")
    hm = fix_hook_mark(doc)
    if hm:
        print(f"  (후킹 {hm}개에 강조 표시를 넣었다 — 숫자에 색이 들어간다)")
    v = fix_voice(doc)
    if v:
        print(f"  (목소리·소리 지시 {v}줄을 붙였다 — 이게 없으면 또박또박 "
              f"읽는 낭독이 되어 로봇처럼 들린다)")
    return doc


def all_names(doc):
    """검사에 쓸 이름 — 한글 배역말 + 바꿔 넣은 영어 관계말."""
    ko = [(c.get("name") or "").strip()
          for c in (doc.get("characters") or []) if (c.get("name") or "").strip()]
    en = list((doc.get("_name_map") or name_map(doc)).values())
    return sorted(set(ko + en), key=len, reverse=True)


# 사람이 입으로 하지 않는 '딱지'. 판결문·기사에나 쓰는 제3자 호칭이라
# 대사에 들어가면 즉시 어색해진다 ("내연녀 집에서 떨어져 죽었다고요?").
# ⚠️ 이것 때문에 16화를 버리지는 않는다 — 한 줄만 손보면 되는 일이다.
#    반려가 아니라 **손볼 곳**으로 알려 준다.
SPOKEN_BAN = ["내연녀", "내연남", "상간녀", "상간남", "피상속인"]

# ⭐ 2026-08-20 — 첫 실제 영상에서 **여자 손가락이 남자 옷 속으로 녹아들었다.**
#    영상 만드는 쪽이 두 사람이 닿는 자리를 아직 제대로 못 그린다.
#    닿는 동작을 안 부르면 그 오류가 아예 안 생긴다.
#    ⚠️ 반려까지 하지는 않는다 — 이야기를 바꾸는 일이라 사람이 볼 몫이고,
#       무엇보다 이런 것으로 16화를 다시 사면 안 된다. **손볼 곳**으로 알린다.
# ⚠️ 처음에는 낱말만 보고 알렸더니 **닿지도 않은 컷 다섯 개**를 잘못 잡았다 —
#    `hugs the keys`(열쇠를 껴안음) `holds her bag`(제 가방을 듦)
#    `shakes her head`(제 고개를 저음) `pulls her hair`(제 머리를 쥠).
#    그래서 **상대가 사람일 때만** 알린다.
TOUCH_VERB = (r"(?:grabs?|grabbing|grips?|holds?|takes?|pushe?s?|shoves?|"
              r"shakes?|hugs?|embraces?|slaps?|snatch(?:es)?|clutch(?:es)?|"
              r"pulls?|touch(?:es)?|hands?|pats?|kiss(?:es)?|drags?)"
              r"(?:\s+off)?")
# 싸울 때 **남의** 몸에서 잡는 자리. 머리·머리카락은 제 것을 만지는 쪽이라 뺀다.
OTHER_PART = ("arms?", "wrists?", "shoulders?", "collar", "sleeve", "hands?",
              "neck", "throat", "face", "chest", "waist", "back")


def touch_hits(act, names):
    """이 ACTION 줄에서 **사람에게** 닿는 곳만 골라 낸다."""
    who = "|".join(re.escape(n) for n in names) if names else r"(?!x)x"
    part = "|".join(OTHER_PART)
    pats = [rf"\b{TOUCH_VERB}\s+(?:{who}|[가-힣]+)\b",             # grabs 남편
            rf"\b{TOUCH_VERB}\s+(?:her|his|the)\s+(?:{part})\b",  # grabs her arm
            rf"\b{TOUCH_VERB}\s+(?:her|him)\b(?!\s+[a-z])"]       # pushes her.
    out = []
    for pt in pats:
        out += [m.group(0).strip() for m in re.finditer(pt, act, re.I)]
    return sorted(set(out))

# 서류·판결문에나 쓰는 말. 싸우는 사람 입에서 나오면 즉시 가짜가 된다.
# ⚠️ 한두 줄은 봐준다(법정 장면에서는 실제로 나온다). 대사 전체가 법률
#    설명이 되어 버리는 것을 막는 것이 목적이므로 **줄 수로** 센다.
STIFF = ["유류분", "한정승인", "상속재산", "상속액", "판례", "시효", "증여",
         "물가상승률", "반환청구", "귀책", "고유재산", "사망보험금", "악의적",
         "청구권", "소명", "입증", "채권자", "피고", "원고"]
STIFF_MAX = 5          # 이보다 많으면 대본 전체가 법률 설명이라는 뜻


# ⭐⭐ 후킹·제목 (2026-08-20 운영자 지시)
#    "제목이랑 후킹 좀 더 자극적으로 뽑아. 자꾸 점잔 빼지 말고 선비처럼."
#    S001 은 hook 이 아예 비어서 화 제목이 그대로 화면 맨 위에 올라갔다 —
#    `집을 나가는 남편` `이혼 소송 기각`. 이건 목차지 후킹이 아니다.
#    ⚠️ 이것으로 16화를 버리지는 않는다(한 줄이면 고친다). **손볼 곳**으로 알린다.
HOOK_MAX = 22           # 화면 맨 위 한 줄. 넘으면 두 줄로 접혀 영상을 가린다
# ⚠️ 밋밋한 것들은 하나같이 짧았다 — `앙심을 품다`(6자) `끝없는 빼돌리기`(7자).
#    누가 무엇을 했는지 담으려면 자리가 필요하다. 열두 자는 있어야 한다.
HOOK_MIN_LEN = 12
YT_TITLE_MAX = 40       # (n/16) 과 #shorts 는 우리가 붙인다
# ⚠️ 2026-08-21 — "명사로 끝나면 밋밋하다" 는 규칙이 **틀렸다.**
#    운영자: "차라리 '불륜녀를 집에 데리고 온 쓰레기 남편' 이 더 낫지 않아?"
#    맞다. 한국어 후킹은 **체언으로 끝날 때 오히려 세다** — `쓰레기 남편`,
#    `빚 6억`, `받는 사람은 불륜녀`. 끝맺음이 문제가 아니었다.
#    진짜 밋밋한 것들을 다시 보면 —
#      `집을 나가는 남편` `이혼 소송 기각` `앙심을 품다` `갑작스러운 죽음`
#    공통점은 **숫자도 없고 따옴표도 없고 센 말도 없다**는 것이다.
#    그래서 끝맺음은 그중 하나로만 보고, **셋 다 없을 때만** 밋밋하다고 본다.
HOOK_END = ("다", "요", "까", "나", "지", "네", "군", "라", "어", "아",
            '"', "?", "!", ".", "”")
# 그 자체로 손가락을 멈추게 하는 말 (판정·악행·반전)
HOOK_STRONG = ["쓰레기", "불륜", "상간", "바람", "배신", "뻔뻔", "막장",
               "파렴치", "몰래", "숨긴", "숨겨", "빼돌", "토해", "비웃",
               "우겼", "협박", "폭로", "내연", "죽었", "죽은", "버렸",
               "빚", "0원", "한 푼"]
# 흔해 빠져서 오히려 안 눌리는 말
HOOK_FLAT = ["에 대하여", "의 진실", "하는 이유", " 이야기", "의 전말",
             "충격", "경악", "소름"]


# ⭐⭐ 2026-08-20 — 플로우가 컷 프롬프트를 통째로 막았다:
#    "이 프롬프트는 **유명인의 동영상 생성**에 관한 Google 정책을 위반할
#     가능성이 있습니다."
#    실제 방송·배우를 가리키는 말이 겹치면 실존 인물을 만들라는 말로 읽힌다.
#    이건 영상이 **아예 안 나오는** 일이라 손볼 곳이 아니라 **반려**다.
#    (다만 우리가 자동으로 바꿔 주므로 실제로 반려까지 가는 일은 드물다)
POLICY_BAN = ["actor", "actress", "celebrity", "famous", "idol",
              "k-drama", "kdrama", "korean tv drama", "live-action drama",
              "lookalike", "look-alike", "resembling", "real person",
              "in the style of a famous"]


def policy_hits(t):
    """정책에 막히는 말을 골라 낸다."""
    low = str(t or "").lower()
    return sorted({w for w in POLICY_BAN
                   if re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", low)})


# ⭐⭐ 2026-08-21 운영자: "글자에 색을 조금 넣는 것도 좋을 것 같은데,
#    포인트 줄 있는 부분에는 색을 좀 넣어 보자. 그렇게 넣게끔 프롬프트가
#    작성되게 코드를 반영해 봐."
#    → 후킹에서 **가장 센 한 토막**을 별표로 감싼다. 화면에서는 그 토막만
#      금색으로 그린다. 유튜브 제목·설명·화면 목록에서는 별표를 떼어 낸다.
#        `보험금 *15억*도 그 여자 앞으로였다`
#    ⚠️ 두 토막 이상 칠하면 아무 데도 안 튄다. **한 토막만** 감싼다.
HOOK_HL = re.compile(r"\*([^*]+)\*")


def hook_plain(t):
    """별표를 떼어 낸 맨글자 (길이 세기·유튜브 제목·화면 목록에 쓴다)."""
    return HOOK_HL.sub(r"\1", str(t or ""))


def hook_runs(t):
    """`앞 *가운데* 뒤` → [("앞 ", False), ("가운데", True), (" 뒤", False)]."""
    out, last = [], 0
    for m in HOOK_HL.finditer(str(t or "")):
        if m.start() > last:
            out.append((t[last:m.start()], False))
        out.append((m.group(1), True))
        last = m.end()
    if last < len(str(t or "")):
        out.append((str(t)[last:], False))
    return [(x, e) for x, e in out if x]


# 숫자·돈은 그 자체로 세다. 표시가 없으면 여기서 자동으로 감싼다 (0원 수리).
HOOK_NUM = re.compile(r"(\d+\s*(?:억|만|천|원)?(?:\s*원)?|[일이삼사오육칠팔구십백천만억]+\s*억)")


def fix_hook_mark(doc):
    """후킹에 강조 표시가 없으면 **숫자 있는 토막**을 자동으로 감싼다."""
    n = 0
    for e in doc.get("episodes") or []:
        h = str(e.get("hook") or "")
        if not h.strip() or "*" in h:
            continue
        m = HOOK_NUM.search(h)
        if not m:
            continue
        e["hook"] = h[:m.start()] + "*" + m.group(1).strip() + "*" + h[m.end():]
        n += 1
    return n


def hook_warn(doc):
    """후킹이 비었거나 밋밋하면 알린다."""
    out = []
    for e in doc.get("episodes") or []:
        no = e.get("no")
        h = re.sub(r"\s+", " ", hook_plain(e.get("hook"))).strip()
        t = re.sub(r"\s+", " ", str(e.get("yt_title") or "")).strip()
        if not h:
            out.append(f"{no}화: 후킹(hook)이 비었다 — 화면 맨 위에 화 제목이 "
                       f"그대로 올라간다 ('{e.get('title')}')")
        else:
            if len(h) > HOOK_MAX:
                out.append(f"{no}화: 후킹이 {len(h)}자다 ({HOOK_MAX}자 넘음) — "
                           f"두 줄로 접혀 영상을 가린다")
            # 숫자·따옴표·센 말 **셋 다 없고** 끝맺음도 밋밋하면 그때가 진짜다
            has_num = bool(re.search(r"\d|억|만 원|한 푼", h))
            has_quote = '"' in h or "'" in h
            has_strong = any(w in h for w in HOOK_STRONG)
            if len(h) < HOOK_MIN_LEN:
                out.append(f"{no}화: 후킹이 {len(h)}자뿐이다 ('{h}') — "
                           f"누가 무엇을 했는지 안 그려진다 ({HOOK_MIN_LEN}자 이상)")
            elif not (h.endswith(HOOK_END) or has_num or has_quote or has_strong):
                out.append(f"{no}화: 후킹이 밋밋하다 ('{h}') — 숫자·센 말·"
                           f"따옴표 중 하나는 있어야 손가락이 멈춘다")
            for w in HOOK_FLAT:
                if w in h:
                    out.append(f"{no}화: 후킹에 밋밋한 말 '{w.strip()}' 이 있다")
        if not t:
            out.append(f"{no}화: 유튜브 제목(yt_title)이 비었다")
        elif len(t) > YT_TITLE_MAX:
            out.append(f"{no}화: 유튜브 제목이 {len(t)}자다 ({YT_TITLE_MAX}자 넘음)")
    return out


def policy_check(doc):
    """인물표까지 훑어 정책에 막히는 말을 찾는다."""
    bad = []
    for ch in doc.get("characters") or []:
        blob = " ".join(str(ch.get(k) or "") for k in
                        ("flow_prompt", "flow_sheet", "flow_desc", "outfit", "face_tag"))
        ph = policy_hits(blob)
        if ph:
            bad.append(f"인물 '{ch.get('name')}': 정책에 막히는 말 — {', '.join(ph)}")
    return bad


def soft(doc):
    """버릴 것까진 아니지만 사람이 한 번 봐야 할 곳."""
    out = (list(doc.get("_soft_extra") or []) + list(doc.get("_facing_fixed") or [])
           + list(doc.get("_touch_fixed") or []) + hook_warn(doc))
    names = all_names(doc)          # 한글 배역말 + 바꿔 넣은 영어 관계말
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
            act = next((l for l in (c.get("prompt") or "").split("\n")
                        if l.startswith("ACTION:")), "")
            hit = touch_hits(act, names)
            if hit:
                out.append(f"{e.get('no')}화 {c.get('n')}컷: 서로 몸이 닿는 동작 "
                           f"— {', '.join(sorted(set(hit)))} "
                           f"(손이 옷 속으로 녹아든다)")
            if True:
                for say in dia_says(c.get("prompt")):
                    for w in SPOKEN_BAN:
                        if w in say:
                            out.append(f"{e.get('no')}화 {c.get('n')}컷: 대사에 "
                                       f"'{w}' — 사람은 그렇게 말하지 않는다 "
                                       f'("{say}")')
    return out


# ⚠️ 2026-08-20 운영자: "본처가 내연녀한테 얘기를 하고 있는데, 대사가 '저 여자'
#    라고 지칭을 하고 있어."
#    맞은편에 있는 사람을 남 얘기하듯 부르면 장면이 통째로 어긋난다.
#    (1화 3컷 — 본처가 내연녀를 마주 보고 "저 여자가 이유였어?")
#    화면에 누가 있는지는 SUBJECT 로, 남녀는 flow_prompt 로 안다.
THIRD_F = ["저 여자", "그 여자", "저년", "그년"]
THIRD_M = ["저 남자", "그 남자", "저놈", "그놈", "저 새끼", "그 새끼"]
THIRD_ANY = ["저 사람", "그 사람", "저것들", "그것들", "저 인간", "그 인간"]


def gender(ch):
    t = (ch.get("flow_prompt") or "").lower()
    if "woman" in t or "female" in t:
        return "f"
    if "man" in t or "male" in t:
        return "m"
    return "?"


def facing_error(cut, chars):
    """맞은편에 있는 사람을 3인칭으로 부르는가.

    ⚠️ 처음 만든 검사가 **세 군데 중 두 군데를 잘못 잡았다.**
         2화 3컷  본처→남편  "평생 그 여자랑 떳떳하게 살지 마."
         14화 1컷 본처→내연녀 "죽던 날까지 그 사람 거였어."
       둘 다 **그 자리에 없는 사람** 얘기라 멀쩡한 대사다.

    그래서 이렇게 좁힌다 — 그 낱말이 가리킬 수 있는 사람이 **한 명도 밖에
    남아 있지 않을 때만** 잡는다.
      · "저 여자" → 이야기 속 여자가 **전부** 이 컷에 있으면 오류
      · "그 사람" → 등장인물이 **전부** 이 컷에 있으면 오류
    """
    lines = (cut.get("prompt") or "").split("\n")
    subj = next((l for l in lines if l.startswith("SUBJECT:")), "")
    named = [c for c in chars if (c.get("name") or "").strip()]
    here = [c for c in named if c["name"] in subj]
    if len(here) < 2:
        return []                       # 혼자 있는 컷은 남 얘기를 해도 된다

    def all_here(g=None):
        pool = [c for c in named if g is None or gender(c) == g]
        return bool(pool) and all(c in here for c in pool)

    hit = []
    for say in re.findall(r'"([^"]*)"', "\n".join(lines[slice(*dia_span(lines))])
                          if dia_span(lines)[0] is not None else ""):
        for w in THIRD_F:
            if w in say and all_here("f"):
                hit.append(w)
        for w in THIRD_M:
            if w in say and all_here("m"):
                hit.append(w)
        for w in THIRD_ANY:
            if w in say and all_here():
                hit.append(w)
    return sorted(set(hit))


# ── 검사 ────────────────────────────────────────────────
def check(doc):
    """규격을 어긴 곳을 전부 찾아 돌려준다. 하나라도 있으면 저장하지 않는다."""
    bad = []
    soft_extra = []            # 버릴 것까진 아니지만 알려 줄 것 (샷·장소)
    stiff_lines = 0            # 법률·서류 말투가 들어간 대사 줄 수
    stiff_hits = set()
    eps = doc.get("episodes") or []
    if len(eps) != EPISODES:
        bad.append(f"화 수가 {len(eps)}개다 (있어야 할 것 {EPISODES}개)")
    if len(doc.get("characters") or []) > 3:
        bad.append("등장인물이 3명을 넘는다")
    bad += policy_check(doc)
    names = all_names(doc)          # 한글 배역말 + 바꿔 넣은 영어 관계말

    for e in eps:
        no = e.get("no", "?")
        cuts = e.get("cuts") or []
        if len(cuts) != CUTS:
            bad.append(f"{no}화: 컷이 {len(cuts)}개다 (있어야 할 것 {CUTS}개)")
        if no != 1 and not (e.get("recap") or "").strip():
            bad.append(f"{no}화: 지난 줄거리(recap)가 비었다")
        if len(e.get("recap") or "") > RECAP_MAX:
            bad.append(f"{no}화: 지난 줄거리가 {RECAP_MAX}자를 넘는다 "
                       f"({len(e['recap'])}자)")

        talk = 0          # 이 화에서 두 사람이 주고받은 컷 수
        for c in cuts:
            n = c.get("n", "?")
            tag = f"{no}화 {n}컷"
            p = c.get("prompt") or ""

            want = ROLES[n - 1] if isinstance(n, int) and 1 <= n <= CUTS else None
            if want and c.get("role") != want:
                bad.append(f"{tag}: 역할이 '{c.get('role')}' 이다 (있어야 할 것 '{want}')")

            got = [l.split(":")[0] + ":" for l in p.split("\n")
                   if ":" in l and not l.startswith(DIA_INDENT)]
            got = [l for l in got if l not in LINES_OPT]     # VOICE 는 선택
            if got[:len(LINES)] != LINES:
                bad.append(f"{tag}: 6줄 규격이 아니다 — {got[:8]}")
            if not p.startswith(HEAD_FIX):
                bad.append(f"{tag}: 머리말이 없다 — 그대로 두면 붙여 넣을 때 "
                           f"주소로 읽혀 글자가 깨진다")
            if looks_like_url(p):
                bad.append(f"{tag}: 맨 앞이 '단어:' 라 주소로 읽힌다 "
                           f"({p.split(chr(10))[0][:24]})")
            for nm in names:
                if nm and re.search(rf"(?<![\w가-힣]){re.escape(nm)}\(", p):
                    bad.append(f"{tag}: 이름 뒤에 얼굴 설명을 붙였다 "
                               f"({nm}(…)) — 플로우가 '유명인 동영상 생성' 으로 "
                               f"거절한다. 얼굴은 캐릭터로 잡는다")
                    break
            ph = policy_hits(p)
            if ph:
                bad.append(f"{tag}: 정책에 막히는 말 — {', '.join(ph)} "
                           f"(플로우가 '유명인 동영상 생성' 으로 거절한다)")
            if AUDIO_FIX not in p and AUDIO_SILENT not in p:
                bad.append(f"{tag}: AUDIO 줄이 없다 — 그대로 두면 화면 밖 "
                           f"해설자가 또박또박 읽어 로봇처럼 들린다")
            if COLOR_FIX not in p:
                bad.append(f"{tag}: 색 지시가 고정 문구와 다르다 "
                           f"— 컷마다 색이 튀면 딴 작품처럼 보인다")
            if "CONTINUITY:" not in p:
                bad.append(f"{tag}: 앞 장면에서 이어진다는 지시가 없다")
            if STYLE_FIX not in p:
                bad.append(f"{tag}: STYLE 줄이 고정 문구와 다르다")
            # ⚠️ 예전엔 `endswith("focus.")` 였다. 고정 문구를 손보는 순간
            #    80컷이 통째로 걸렸다 — 문구를 글자로 베껴 두면 이렇게 된다.
            #    고정 문구 자체와 견준다.
            if not p.rstrip().endswith(AVOID_FIX):
                bad.append(f"{tag}: Avoid 줄로 끝나지 않는다")

            # ⭐ 글자가 나올 물건을 불렀는가 (영상에 글자 금지 — 운영자 지시)
            head = p.split("STYLE:")[0].lower()
            hit = text_bait(head)
            if hit:
                bad.append(f"{tag}: 글자가 나올 물건을 불렀다 — {', '.join(hit)}")

            # 한국어 대사 — 6초에 들어가는 양 (한 줄 · 총합 · 말하는 사람 수)
            f3 = facing_error(c, doc.get("characters") or [])
            if f3:
                bad.append(f"{tag}: 맞은편 사람을 '{', '.join(f3)}' 라고 부른다 "
                           f"— 앞에 두고 남 얘기하듯 말하면 장면이 어긋난다")

            says = dia_says(p)
            total = sum(syl(x) for x in says)
            if total > DIA_SYL_HARD:
                bad.append(f"{tag}: 대사가 다 합쳐 {total}음절이다 "
                           f"({DIA_SYL_HARD}음절을 넘으면 "
                           f"{total / EASY_SYL_PER_SEC:.1f}초라 {SEC}초에 못 넣는다)")
            elif total > DIA_SYL_MAX:
                soft_extra.append(f"{tag}: 대사가 {total}음절이다 "
                                  f"({DIA_SYL_MAX}음절이 알맞다 — 넘치면 급하게 쏟아내 "
                                  f"받침이 뭉개진다)")
            if len(says) > TALKERS_MAX:
                bad.append(f"{tag}: 한 컷에서 {len(says)}번 말한다 "
                           f"({TALKERS_MAX}번 이내 — 6초에 그 이상은 뭉개진다)")
            if says and total < DIA_SYL_MIN:
                bad.append(f"{tag}: 대사가 다 합쳐 {total}음절뿐이다 "
                           f"({DIA_SYL_MIN}음절 이상 — {total / SYL_PER_SEC:.1f}초라 {SEC}초가 "
                           f"거의 빈다) — {' / '.join(says)}")
            stiff_hits.update(w for x in says for w in STIFF if w in x)
            stiff_lines += sum(1 for x in says if any(w in x for w in STIFF))
            if len(says) >= 2:
                talk += 1
            if len(c.get("subtitle") or "") > SUB_MAX:
                bad.append(f"{tag}: 자막이 {SUB_MAX}자를 넘는다")
            # 지시대명사 — 컷은 하나씩 따로 만들어져 모델이 못 알아듣는다.
            # ⚠️ 2026-08-20 — 이 검사가 **우리 예시 대본까지 걸러냈다.**
            #    "시동생 holds out a folder; she does not take it." 처럼 앞에 이름이
            #    있으면 모델은 알아듣는다. 정말 위험한 것은 화면에 누가 있는지
            #    적는 SUBJECT 줄에 이름 없이 'the same woman' 만 적는 경우다.
            #    그래서 SUBJECT 줄만, 그것도 이름이 하나도 없을 때만 잡는다.
            subj = next((l for l in p.split("\n") if l.startswith("SUBJECT:")), "")
            if re.search(r"\bthe same\b|\bshe\b|\bhe\b", subj.lower()) and \
                    not any(nm and nm in subj for nm in names):
                bad.append(f"{tag}: SUBJECT 에 이름 없이 지시대명사를 썼다 "
                           f"— 누가 화면에 있는지 이름으로 적는다")

        # ⭐ 한 명이 혼잣말만 5번 하면 이야기가 안 굴러간다 (2026-08-20 손님 지적).
        #    맞섬·뒤집기 같은 컷은 반드시 주고받아야 장면이 앞으로 나간다.
        if cuts and talk < TALK_MIN:
            bad.append(f"{no}화: 두 사람이 주고받는 컷이 {talk}컷뿐이다 "
                       f"({TALK_MIN}컷 이상 — 혼잣말만 이으면 이야기가 안 굴러간다)")

    # ⭐ 아래 셋은 첫 화 완성본을 보고 찾은 것들 (2026-08-20).
    #    ⚠️ 전부 **손볼 곳**이 아니라 검사다 — 얼굴·장소가 튀면 영상이 못 쓰게 된다.
    #       다만 자동으로 고쳐지는 옷·얼굴표는 normalize 가 먼저 맞춰 준다.
    for e in eps:
        no = e.get("no", "?")
        cuts = e.get("cuts") or []
        shots, sets, subj = set(), set(), {}
        for c in cuts:
            lines = (c.get("prompt") or "").split("\n")
            sh = next((l for l in lines if l.startswith("SHOT:")), "")[5:].strip().lower()
            st = next((l for l in lines if l.startswith("SETTING:")), "")[8:].strip().lower()
            sj = next((l for l in lines if l.startswith("SUBJECT:")), "")[8:].strip()
            if sh:
                shots.add(re.split(r"[,.]", sh)[0].strip())
            if st:
                sets.add(re.split(r"[,.]", st)[0].strip())
            for nm in names:
                # ⚠️ `facing` 앞에서 끊지 않으면 두 사람이 나오는 줄에서
                #    상대방 옷까지 삼켜 **같은 옷을 다르다고** 읽는다.
                m = re.search(rf"{re.escape(nm)}(\([^)]*\))?\s+in\s+"
                              rf"([^,.]*?)(?=\s+facing\s|[,.]|$)", sj)
                if m and nm:
                    subj.setdefault(nm, set()).add(
                        ((m.group(1) or "") + "|" + m.group(2)).strip())
        # ⚠️ 샷·장소는 **버리지 않는다** — 이야기는 멀쩡한데 그림이 밋밋한 것뿐이라
        #    16화를 다시 사면서까지 막을 일이 아니다. 프롬프트가 시키고, 여기선 알린다.
        if len(cuts) >= CUTS:
            if len(shots) < 3:
                soft_extra.append(f"{no}화: 샷 크기가 {len(shots)}가지뿐이다 "
                                  f"(3가지 이상이면 덜 밋밋하다) — {sorted(shots)}")
            if len(sets) > 2:
                soft_extra.append(f"{no}화: 장소가 {len(sets)}곳이다 "
                                  f"(두 곳까지가 안 튄다) — {sorted(sets)}")
        for nm, v in subj.items():
            if len(v) > 1:
                bad.append(f"{no}화: '{nm}' 의 생김새·옷차림이 컷마다 다르다 "
                           f"({len(v)}가지) — 딴사람으로 나온다")

    # ⭐ 대사가 법률 설명을 대신 지고 있으면 말이 통째로 가짜가 된다
    #    (2026-08-20 손님: "말도 어색해. 구어체가 아닌 것 같고 실제 같지 않아.")
    #    법정 장면 한두 줄은 봐준다 — 대본 전체가 설명이 되는 것만 막는다.
    doc["_soft_extra"] = soft_extra
    if stiff_lines > STIFF_MAX:
        bad.append(f"대사 {stiff_lines}줄이 서류·판결문 말투다 "
                   f"({STIFF_MAX}줄까지만) — {', '.join(sorted(stiff_hits))} · "
                   f"사실은 설명 자막(caption)이 지고, 입은 감정만 말한다")
    return bad


def summary(doc, sid, case_id):
    cuts = sum(len(e.get("cuts") or []) for e in doc.get("episodes") or [])
    sec = cuts * SEC
    print(f"\n{sid} · 판례 {case_id} · 「{doc.get('title', '')}」")
    print(f"  {len(doc.get('episodes') or [])}화 × {CUTS}컷 × {SEC}초 "
          f"= 컷 {cuts}개 · 총 {sec}초 ({sec / 60:.1f}분)")
    print(f"  등장인물 {len(doc.get('characters') or [])}명 · "
          f"하루 45크레딧(무료 50) · 16일이면 롱폼 한 편")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="", help="판례 번호 (비우면 자동)")
    ap.add_argument("--check", default="", help="이미 만든 시리즈만 다시 검사 (0원)")
    ap.add_argument("--repair", action="store_true",
                    help="--check 와 함께 — 고친 결과를 파일에 **저장**한다 (0원)")
    ap.add_argument("--writer", default="", help="claude / gemini (기본: gemini)")
    args = ap.parse_args()

    SERIES_DIR.mkdir(parents=True, exist_ok=True)
    state = load(STATE, {})

    if args.check:
        doc = load(SERIES_DIR / f"{args.check}.json", None)
        if not doc:
            print(f"❌ {args.check} 가 없다", file=sys.stderr)
            return 2
        bad = check(normalize(doc))
        # ⭐ 고친 것을 저장하지 않으면 관리자 페이지는 **옛 프롬프트**를 그대로
        #    내보낸다. 1화를 이미 만든 뒤에 고친 것들(닿는 동작·얼굴 못·옷차림)이
        #    다음 화에 안 먹는 이유가 이것이었다.
        if args.repair:
            (SERIES_DIR / f"{args.check}.json").write_text(
                json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  💾 고친 결과를 {args.check}.json 에 저장했다")
        summary(doc, args.check, doc.get("case_id", ""))
        for b in bad:
            print(f"  ❌ {b}")
        print("\n" + ("❌ 규격에 안 맞는 곳 %d군데" % len(bad) if bad else "✅ 규격 통과"))
        for w in soft(doc):
            print(f"  ⚠️ 손볼 곳 — {w}")
        return 1 if bad else 0

    queue = load(QUEUE, [])
    row = (next((c for c in queue if c["case_id"] == args.case), None) if args.case
           else pick_case(queue, state))
    if not row:
        print("❌ 쓸 판례가 없다. [1. 재판 기록 모으기] 를 먼저 돌려라", file=sys.stderr)
        return 2

    sid = next_id(state)
    print(f"{sid} 만드는 중 — 판례 {row['case_id']} · {row.get('case_type', '')}")
    print(f"  {row.get('one_line', '')[:70]}")

    # ⭐ 글은 제미나이가 쓴다 (2026-08-18 운영자 지시)
    llm, who = writer(max_calls=6, prefer=(args.writer or "gemini"))
    body = prompts.fill(prompts.load("series_gen"), CASE_JSON=case_json(row))
    # ⚠️ 2026-08-20 — 대사가 길어지고 caption 칸이 생기면서 16화 JSON 이
    #    32,768 토큰을 넘어 잘렸다. 16화 × 5컷 × (프롬프트 7줄 + 자막 2종)
    #    이면 5만 토큰쯤 된다. 넉넉히 잡는다 — 안 쓰면 값도 안 나간다.
    doc = llm.json(body, tier="pro", max_output_tokens=65536, temperature=0.85,
                   label="시리즈", effort="high")

    doc = normalize(doc)
    doc["case_id"] = row["case_id"]
    doc["series_id"] = sid
    doc["spec"] = {"episodes": EPISODES, "cuts": CUTS, "sec": SEC}

    bad = check(doc)
    summary(doc, sid, row["case_id"])
    if bad:
        broken = SERIES_DIR / f"{sid}.broken.json"
        broken.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n❌ 규격에 안 맞는 곳 {len(bad)}군데 — 저장하지 않았다")
        for b in bad[:15]:
            print(f"  · {b}")
        if len(bad) > 15:
            print(f"  · … 외 {len(bad) - 15}군데")
        print(f"  (받은 것은 {broken.name} 에 남겨 뒀다)")
        return 1

    (SERIES_DIR / f"{sid}.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    # ⚠️ 2026-08-20 — 통과한 뒤에도 지난번 반려본이 그대로 남아 있어서, 내가
    #    **새 대본 대신 옛 반려본을 읽고** 결과가 안 바뀌었다고 잘못 읽었다.
    #    통과했으면 짝이 되는 반려본은 지운다(더 볼 이유가 없다).
    old = SERIES_DIR / f"{sid}.broken.json"
    if old.exists():
        old.unlink()
        print(f"  (지난 반려본 {old.name} 은 지웠다)")
    state[sid] = {"case_id": row["case_id"], "title": doc.get("title", ""),
                  "episodes": EPISODES, "made": 0, "writer": who}
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✅ {sid}.json 저장 — 매일 한 화씩 30초 영상을 만들면 된다")
    for w in soft(doc):
        print(f"  ⚠️ 손볼 곳 — {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
