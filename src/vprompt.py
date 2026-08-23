#!/usr/bin/env python3
"""컷 하나의 지시문을 **그림용 / 영상용**으로 고쳐 쓴다 (2026-08-23 신설).

왜 필요한가
    대본에 적힌 컷 지시문은 예전 방식(Veo 가 소리까지 만들던 때) 것이라
    쓸 수 없는 것이 섞여 있다. 실측·자문으로 확인한 세 가지를 기계적으로 고친다.

    ① 대사(DIALOGUE)·목소리(VOICE)·소리(AUDIO) 줄을 **통째로 뺀다**
       쌍따옴표 안의 한국어 대사를 그대로 두면 모델이 그걸 "화면에 글자로
       띄우라"는 뜻으로 읽어 자막을 태워 넣는다. 우리는 자막을 직접 얹으므로
       화면에 글자가 나오면 못 쓴다. 소리도 타입캐스트로 따로 넣으므로
       VOICE·AUDIO 는 토큰만 잡아먹는다.
    ② 거친 낱말을 순화한다
       furious · shouting · aggressive 가 겹치면 안전필터에 막힌다(응답이
       200 인데 영상이 비어 온다). 뜻은 살리고 표현만 바꾼다.
    ③ 화면에 글자를 막는 문구를 **맨 끝에** 붙인다
       negativePrompt 는 이 모델이 안 받는다(실측 400). 프롬프트 안에서만 막을
       수 있고, 맨 끝에 둔 것이 가장 세게 먹는다.
"""

import re

# ② 안전필터에 걸리기 쉬운 낱말 → 뜻은 같고 표현만 순한 것
SOFT = [
    (r"\bfurious(ly)?\b",        "with intense emotion"),
    (r"\bshouting\b",            "speaking loudly"),
    (r"\bshouts?\b",             "raises their voice"),
    (r"\bscream(s|ing)?\b",      "raises their voice"),
    (r"\baggressive(ly)?\b",     "emphatically"),
    (r"\bangry\b",               "serious"),
    (r"\banger\b",               "strong feeling"),
    (r"\brage\b",                "strong feeling"),
    (r"\bslaps?\b",              "sharply gestures at"),
    (r"\bgrabs?\b",              "reaches toward"),
    (r"\bviolent(ly)?\b",        "forcefully"),
    (r"\bthreaten(s|ing)?\b",    "warns"),
]

# ③ 화면 글자 막기 — 반드시 맨 끝. (자문·실측 모두 "끝이 가장 세다")
NO_TEXT = ("Absolutely no text, no letters, no subtitles, no captions, "
           "no watermarks, no speech bubbles, no typography anywhere on screen.")

# ⚠️⚠️ 2026-08-23 — 여기가 이번 사고의 자리다.
#    대사를 프롬프트에서 빼 버리니 Veo 가 **누가 언제 말하는지** 모르게 됐고,
#    "말하는 사람은 모두 계속 입을 움직여라" 만 남아 둘이 내내 입을 움직였다.
#    그 위에 목소리를 얹으니 당연히 안 맞았다.
#    운영자: "입이 움직이는 등장인물하고 목소리가 나오는 등장인물이 전혀 맞지 않아"
LIPS_NO_DIA = ("Everyone who speaks keeps their lips moving continuously and clearly "
               "throughout, as if talking, with visible jaw movement.")
LIPS_DIA = ("Each person's lips move ONLY while it is their own turn to speak, and "
            "stay closed and still while the other person is speaking; they take "
            "turns one after another and never speak at the same time.")

FRAME = ("Center-framed medium waist shot with the people kept close to the middle "
         "of the frame, because the sides will be cropped away.")

# ⭐ 배경은 **최대한 흐리게** (2026-08-23 운영자 확인 — 파이프라인 정리 때 정한 것을
#    내가 프롬프트에 안 넣어 배경이 아주 선명하게 나왔다).
#
#    왜 흐려야 하나 — 보기 좋아서만이 아니다.
#      ① 컷마다 배경 소품이 조금씩 달라지는 것이 눈에 안 띈다 (일관성이 가장 깨지기
#         쉬운 자리가 배경이다)
#      ② 세로 화면의 4:3 띠로 자를 때 배경이 잘려 나가는 것이 덜 티난다
#      ③ 시선이 인물 얼굴로 모인다 — 우리 이야기는 표정으로 간다
#
#    ⚠️ 대본의 STYLE 줄 맨 끝에 'shallow depth of field' 가 파묻혀 있었는데
#       그것만으로는 전혀 안 먹었다. 짧고 강하게, 따로 한 줄로 준다.
BLUR = ("The background is strongly out of focus and softly blurred throughout, "
        "heavy bokeh, only the people are sharp and in focus; keep background "
        "shapes as soft indistinct colour masses with no readable detail.")

DROP = ("DIALOGUE", "VOICE", "AUDIO")
DROP_KEEP_DIA = ("VOICE", "AUDIO")      # 대사는 남기고 소리 묘사만 뺄 때


def strip_lines(text, drop=None):
    """적힌 토막을 통째로 뺀다 (이어지는 들여쓴 줄까지)."""
    drop = drop or DROP
    out, skip = [], False
    for line in (text or "").splitlines():
        head = re.match(r"\s*([A-Z][A-Z ]{2,}):", line)
        if head:
            skip = head.group(1).strip() in drop
            if skip:
                continue
        elif skip:
            if line.strip() and (line.startswith(" ") or line.startswith("\t")):
                continue                      # 대사 줄들 — 계속 버린다
            skip = False
        if not skip:
            out.append(line)
    return "\n".join(out)


def soften(text):
    for pat, rep in SOFT:
        text = re.sub(pat, rep, text, flags=re.I)
    return text


def _tail(text, *parts):
    body = text.rstrip()
    # 원래 있던 Avoid: 줄은 남겨 두되, 우리 문구를 그 **뒤**에 둔다
    return "\n".join([body, *parts])


# 대사 줄을 빼고 나면 남은 문장이 없어진 대사를 가리키는 경우가 있다.
# ("the Korean lines they say" — 이제 그런 줄은 프롬프트에 없다)
DANGLING = [
    (r"in exact sync with the Korean lines they say", "as if speaking"),
    (r"with the Korean lines", "as if speaking"),
    (r"\bthe lines? (they|he|she) says?\b", "what they are saying"),
]


def video_prompt(cut_prompt, sec=None, dialogue=True):
    """Veo 로 보낼 지시문.

    dialogue=True 이면 **한국어 대사를 남긴다.** 남겨야 Veo 가 누가 언제
    말하는지 알고 그 사람만 입을 움직인다. 소리는 나중에 우리 한국어 목소리로
    갈아 끼우지만, **입 타이밍은 이 대사에서 나온다.**
    (2026-08-21 기록: 대사를 넣었을 때 셋이 겹치지 않고 차례대로 말했고
     경계도 0.98/2.79/4.57 로 깨끗했다. 남은 문제는 발음뿐이었다)"""
    body = soften(strip_lines(cut_prompt, DROP_KEEP_DIA if dialogue else DROP))
    for pat, rep in DANGLING:
        body = re.sub(pat, rep, body, flags=re.I)
    if sec:
        body = re.sub(r"\b\d+-second single continuous take",
                      f"{int(sec)}-second single continuous take", body)
    return _tail(body.rstrip(), FRAME, BLUR,
                 LIPS_DIA if dialogue else LIPS_NO_DIA, NO_TEXT)


def still_prompt(cut_prompt):
    """그 컷의 **첫 장면 스틸**을 그릴 지시문 (Veo 의 시작 프레임이 된다).

    움직임 지시(ACTION)는 남긴다 — 그 순간의 자세를 잡아 주기 때문이다.
    다만 '한 컷 이어가기' 같은 영상 전용 문구는 뺀다."""
    body = soften(strip_lines(cut_prompt))
    for pat, rep in DANGLING:
        body = re.sub(pat, rep, body, flags=re.I)
    body = re.sub(r"\b\d+-second single continuous take\.?", "A single still frame.", body)
    body = re.sub(r"one single continuous take, no cut, no scene change, ", "", body)
    return _tail(body.rstrip(), FRAME, BLUR, NO_TEXT)


# ⚠️⚠️ 2026-08-23 — Veo 가 받는 컷 길이는 **4·6·8초 셋뿐이다.**
#    구글의 거절 문구가 "Please provide a value between 4 and 8, inclusive" 라
#    처음에 '4~8 아무 정수' 로 읽었다가 7초를 보내 400 을 맞았다. 실측해 보니
#    5초·7초는 거절이고 4·6·8 만 받는다. 문구를 믿지 말고 실측을 믿는다.
OK_SEC = (4, 6, 8)


def seconds_for(subtitle, per_sec=4.6):
    """대사 길이에 맞는 컷 길이 — 받아 주는 값(4·6·8) 중에서 고른다.

    한국어는 1초에 약 4.6자다. 6초 컷에 9초짜리 대사를 얹으면 남는 3초 동안
    마지막 장면이 얼어붙어 방송 사고처럼 보인다. 대사가 길면 컷을 늘린다.
    ⚠️ 모자라는 쪽보다 **넉넉한 쪽**으로 올린다 — 영상이 짧으면 얼어붙지만
       길면 뒤가 조금 남을 뿐이라 눈에 덜 띈다."""
    chars = len(re.sub(r"[\s/]+", "", subtitle or ""))
    want = chars / per_sec + 0.8
    for s in OK_SEC:                       # 4 → 6 → 8 차례로, 처음 넘는 것
        if want <= s:
            return s
    return OK_SEC[-1]
