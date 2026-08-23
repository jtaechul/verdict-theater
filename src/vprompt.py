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

# 입은 움직이되 소리는 우리가 넣는다 — 눈에 보이는 것만 시킨다
LIPS = ("Everyone who speaks keeps their lips moving continuously and clearly "
        "throughout, as if talking, with visible jaw movement.")

FRAME = ("Center-framed medium waist shot with the people kept close to the middle "
         "of the frame, because the sides will be cropped away.")

DROP = ("DIALOGUE", "VOICE", "AUDIO")


def strip_lines(text):
    """DIALOGUE·VOICE·AUDIO 토막을 통째로 뺀다 (이어지는 들여쓴 줄까지)."""
    out, skip = [], False
    for line in (text or "").splitlines():
        head = re.match(r"\s*([A-Z][A-Z ]{2,}):", line)
        if head:
            skip = head.group(1).strip() in DROP
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


def video_prompt(cut_prompt, sec=None):
    """Veo 로 보낼 지시문. sec 를 주면 머리말의 초도 그 값으로 고친다."""
    body = soften(strip_lines(cut_prompt))
    for pat, rep in DANGLING:
        body = re.sub(pat, rep, body, flags=re.I)
    if sec:
        body = re.sub(r"\b\d+-second single continuous take",
                      f"{int(sec)}-second single continuous take", body)
    return _tail(body.rstrip(), FRAME, LIPS, NO_TEXT)


def still_prompt(cut_prompt):
    """그 컷의 **첫 장면 스틸**을 그릴 지시문 (Veo 의 시작 프레임이 된다).

    움직임 지시(ACTION)는 남긴다 — 그 순간의 자세를 잡아 주기 때문이다.
    다만 '한 컷 이어가기' 같은 영상 전용 문구는 뺀다."""
    body = soften(strip_lines(cut_prompt))
    for pat, rep in DANGLING:
        body = re.sub(pat, rep, body, flags=re.I)
    body = re.sub(r"\b\d+-second single continuous take\.?", "A single still frame.", body)
    body = re.sub(r"one single continuous take, no cut, no scene change, ", "", body)
    return _tail(body.rstrip(), FRAME, NO_TEXT)


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
