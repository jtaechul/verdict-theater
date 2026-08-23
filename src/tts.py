#!/usr/bin/env python3
"""⭐ 한국어 목소리를 따로 만든다.

    python3 src/tts.py --say "당신 진짜 제정신이야?" --out /tmp/a.wav
    python3 src/tts.py --sample S001 --ep 1 --out build/voice.mp3

왜 목소리를 따로 만드나 (2026-08-21)
    영상 만드는 쪽(플로우)의 한국어가 원어민 수준이 아니다. 프롬프트로 할 수
    있는 것은 다 했는데도 "외국인이 어설프게 한국말 하는 소리"가 남았다.
    → 목소리를 영상에서 떼어내고, 한국어 전용 목소리를 **말하던 그 자리에**
      끼워 넣는다. 입은 이미 같은 한국어 대사로 움직이므로 입모양도 맞는다.

⭐⭐ 왜 엔진을 바꿨나 (2026-08-21 · 운영자: "그냥 기계가 읽어주는 놈 같다")
    구글 클라우드 TTS 로 바꿔 봤지만 여전히 기계 낭독이었다. 까닭이 하나가
    아니었다 —
      ① 엔진이 애초에 **낭독용**이다. 구글 클라우드 TTS 한국어 목소리는
         안내 방송·내비게이션을 읽으라고 만든 것이다. 어느 목소리를 골라도
         "배신당한 아내" 가 되지 않는다. ← 가장 큰 원인
      ② **감정을 전할 통로가 없다.** {"input": {"text": …}} — 글자만 던진다.
         화가 났는지 울먹이는지 비웃는지 알려 줄 자리가 규격에 아예 없다.
      ③ 가장 사람 같다는 Chirp3-HD 는 **말 속도·높낮이를 안 받는다.**
         그래서 좋은 목소리를 쓸수록 억양 조절이 오히려 사라졌다.
      ④ 목록 부르기가 한 번이라도 실패하면 **조용히 Neural2 로 되돌아간다.**
         되돌아갔는지 운영자가 알 방법이 화면에 없었다.
      ⑤ 한 마디씩 따로 만들어 붙이니 매 줄이 처음부터 다시 읽는 톤이 된다.

    → **제미나이 목소리(Gemini TTS)로 갈아탄다.** 이쪽은 대사와 함께
      *"이를 악물고 낮게 몰아붙이듯 말한다"* 같은 **연기 지시를 말로 적어
      보낼 수 있다.** ②③⑤가 한꺼번에 풀린다.
      열쇠도 이미 있는 GEMINI_API_KEY 를 그대로 쓴다 — 새로 만들 것이 없다.
      구글 클라우드 TTS 는 **되돌아갈 자리**로 남겨 둔다(①④ 대비).

값
    16화 전체 대사가 약 2,400자 ≒ 8분치 소리. 제미나이 목소리 기준으로
    16화를 통째로 만들어도 **수백 원**이다 (한 편이면 1원 남짓).
    구글 클라우드 TTS 로 되돌아가면 무료 한도(월 100만 자) 안이라 0원이다.

열쇠
    GEMINI_API_KEY  — 제미나이 목소리 (기본). 이미 대본 만들 때 쓰고 있다.
    GOOGLE_TTS_KEY  — 구글 클라우드 TTS (되돌아갈 자리).
    VOICE_ENGINE    — 'gemini' / 'google' 로 손수 고를 때만 (보통 안 건드린다).
    둘 다 없으면 소리를 안 바꾸고 원래 소리를 그대로 쓴다 (영상은 계속 나온다).
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

API = "https://texttospeech.googleapis.com/v1/text:synthesize"
GEM = "https://generativelanguage.googleapis.com/v1beta"

# 한국어 전용 목소리. 사람마다 다른 것을 준다.
#   ⚠️ 같은 목소리를 두 사람에게 주면 누가 말하는지 안 갈린다.
#   ⚠️ 열쇠가 없을 때(내 컴퓨터·시험) 쓸 **되돌아갈 자리**다.
#      실제로는 아래 best_voices() 가 구글에 물어 **가장 좋은 것**을 고른다.
VOICE_F = ["ko-KR-Neural2-A", "ko-KR-Neural2-B", "ko-KR-Wavenet-A"]
VOICE_M = ["ko-KR-Neural2-C", "ko-KR-Wavenet-C", "ko-KR-Wavenet-D"]

# ⭐⭐ 제미나이 목소리. 이름마다 성격이 다르다 — 막장 드라마에 맞는 것부터.
#    (제미나이 목소리는 언어를 안 가린다. 한국어 대사를 주면 한국어로 말한다)
GEM_F = ["Kore",        # 단단하고 야무지다 — 몰아붙이는 아내
         "Leda",        # 젊다 — 어린 쪽
         "Gacrux",      # 연륜 — 어머니뻘
         "Aoede", "Autonoe", "Callirrhoe", "Despina", "Erinome",
         "Achernar", "Laomedeia", "Sulafat", "Vindemiatrix", "Pulcherrima"]
GEM_M = ["Orus",        # 단단하다 — 버티는 남편
         "Algenib",     # 거칠다 — 막 나가는 쪽
         "Fenrir",      # 격하다 — 소리치는 쪽
         "Charon", "Iapetus", "Umbriel", "Algieba", "Enceladus",
         "Alnilam", "Schedar", "Achird", "Rasalgethi", "Sadaltager"]

# 모델 이름이 바뀌어도 따라가도록 **구글에 물어서** 고른다. 이건 못 물었을 때만.
GEM_TTS_FALLBACK = "gemini-2.5-flash-preview-tts"
_GEM_MODEL = None

# ⭐⭐ 2026-08-21 — 목소리 등급. 앞에 있을수록 사람 같다.
#    Neural2 는 한국어 원어민이긴 하지만 **아나운서처럼 밋밋하다.**
#    Chirp3-HD 는 훨씬 사람처럼 말한다 — 드라마 대사에는 이쪽이 맞다.
#    ⚠️ 어떤 이름이 있는지 외워 두지 않는다. 구글이 이름을 바꾸거나 새 등급을
#       내면 외워 둔 목록은 바로 낡는다. **구글에 물어서** 고른다.
TIERS = ["Chirp3-HD", "Chirp-HD", "Neural2", "Wavenet", "Standard"]
_VOICES = None

# ⚠️ 2026-08-22 — 1.35배까지 빨리 감았더니 발음이 뭉개졌다(운영자 지적).
#    한국어는 1.3배부터 자음이 무너진다. 조금 넘치는 편이 낫다.
RATE_MIN, RATE_MAX = 0.75, 1.28     # 이 밖으로 나가면 발음이 뭉개진다
PITCH = {"low": -2.0, "high": 2.0}


# ── 열쇠와 엔진 ─────────────────────────────────────────
def gkey():
    """구글 클라우드 TTS 열쇠 (되돌아갈 자리)."""
    return (os.environ.get("GOOGLE_TTS_KEY") or "").strip()


def gem_key():
    """제미나이 열쇠 (기본). 대본 만들 때 쓰는 것과 같은 열쇠다."""
    return (os.environ.get("GEMINI_API_KEY") or "").strip()


def tc_key():
    """타입캐스트 열쇠 (2026-08-23 운영자: "typecast 로 바꿔볼까? API 있음")."""
    return (os.environ.get("TYPECAST_API_KEY") or "").strip()


def engine():
    """지금 쓸 목소리 엔진.

    ⭐ 2026-08-23 — 발음 뭉개짐 때문에 **타입캐스트**를 맨 앞에 둔다.
       한국어 전용이라 발음이 또렷하다. 열쇠가 있으면 그쪽이 먼저다.
       (VOICE_ENGINE 으로 언제든 되돌릴 수 있다)
    """
    want = (os.environ.get("VOICE_ENGINE") or "").strip().lower()
    if want in ("typecast", "gemini", "google"):
        return want
    if tc_key():
        return "typecast"
    return "gemini" if gem_key() else "google"


def key():
    """지금 엔진으로 소리를 만들 수 있는가 (없으면 빈 문자열).

    ⚠️ 예전에는 이게 GOOGLE_TTS_KEY 하나만 봤다. 그대로 두면 제미나이
       열쇠만 있는 경우에 shorts.dub() 이 '열쇠 없음' 으로 판단해 원래
       소리를 그냥 써 버린다.
    """
    e = engine()
    if e == "typecast":
        return tc_key()
    return gem_key() if e == "gemini" else gkey()


def engine_note():
    """운영자에게 보여 줄 한 줄 — 지금 어떤 목소리를 쓰고 있는가."""
    if engine() == "typecast":
        return (f"타입캐스트 (한국어 전용 — 발음이 또렷하다)\n"
                f"   말투 결: {style_of()['name']}")
    if engine() == "gemini":
        return (f"제미나이 목소리 — 연기 지시를 함께 보낸다\n"
                f"   길: {route_note()}\n"
                f"   말투 결: {style_of()['name']}\n"
                f"   기본 목소리: 여자 {best_voices('FEMALE')[0]} · "
                f"남자 {best_voices('MALE')[0]} (45살 이상 배역은 나이 든 목소리)")
    f = best_voices("FEMALE")[0] if gkey() else VOICE_F[0]
    m = best_voices("MALE")[0] if gkey() else VOICE_M[0]
    return f"구글 클라우드 TTS — 여자 {f} · 남자 {m}"


# ── 구글 클라우드 TTS (되돌아갈 자리) ──────────────────────
def list_voices():
    """구글에 한국어 목소리 목록을 물어본다 (한 번만 묻고 기억한다)."""
    global _VOICES
    if _VOICES is not None:
        return _VOICES
    k = gkey()
    if not k:
        _VOICES = []
        return _VOICES
    try:
        url = ("https://texttospeech.googleapis.com/v1/voices"
               f"?languageCode=ko-KR&key={k}")
        with urllib.request.urlopen(url, timeout=30) as r:
            got = json.loads(r.read().decode("utf-8"))
            usage_add(model, got.get("usageMetadata"))
        _VOICES = [(v.get("name", ""), (v.get("ssmlGender") or "").upper())
                   for v in (got.get("voices") or [])
                   if str(v.get("name", "")).startswith("ko-KR")]
    except Exception:                                        # noqa: BLE001
        _VOICES = []
    return _VOICES


def rank(name):
    """등급이 앞설수록 작은 수 (골라 쓸 때 오름차순으로 쓴다)."""
    for i, t in enumerate(TIERS):
        if t in name:
            return i
    return len(TIERS)


# ⭐⭐ 2026-08-22 — 운영자가 **귀로 고른** 목소리가 있으면 그것이 맨 앞이다.
#    말투 결이 고르는 것보다 위다 — 사람이 직접 들어 보고 정한 것이기 때문.
# ⭐ 2026-08-22 — 운영자가 귀로 듣고 **확정**했다: "목소리는 아주 마음에 들어."
#    여자 Erinome · 남자 Iapetus. state/voice.json 에 담겨 있다.
#    ⚠️ 자동 판정(voice_judge)은 두 번 돌려 서로 다른 답을 냈다(일치도 0.52).
#       그러니 **이 파일을 자동 판정으로 덮어쓰지 않는다.** 사람이 정한 것이 위다.
def chosen():
    """골라 둔 목소리. {"f": "Erinome", "m": "Iapetus"} 꼴. 없으면 빈손."""
    f = Path(__file__).resolve().parent.parent / "state" / "voice.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        return {k: str(v) for k, v in d.items() if k in ("f", "m") and v}
    except Exception:                                        # noqa: BLE001
        return {}


def best_voices(gender):
    """그 성별에서 **가장 사람 같은** 목소리부터 차례로."""
    if engine() == "typecast":
        try:
            rows = tc_voices()
        except Exception:                                    # noqa: BLE001
            rows = []
        want = "f" if gender == "FEMALE" else "m"
        # 성별 표시가 있으면 그 성별만, 없으면(모르면) 다 보여 준다
        got = [v["id"] for v in rows if v["gender"] == want] or               [v["id"] for v in rows if not v["gender"]] or               [v["id"] for v in rows]
        pick = chosen().get("f" if gender == "FEMALE" else "m")
        if pick and pick in got:
            got.remove(pick)
            got.insert(0, pick)
        elif pick and any(v["id"] == pick for v in rows):
            got.insert(0, pick)
        return got or ["-"]
    if engine() == "gemini":
        got = list(GEM_F if gender == "FEMALE" else GEM_M)
        # 아래에 있는 것부터 앞으로 옮긴다 → 마지막에 옮긴 것이 맨 앞
        for want in (style_of()["voice_f" if gender == "FEMALE" else "voice_m"],
                     chosen().get("f" if gender == "FEMALE" else "m")):
            if want and want in got:
                got.remove(want)
                got.insert(0, want)
        return got
    got = [n for n, g in list_voices() if g == gender]
    if not got:
        return list(VOICE_F if gender == "FEMALE" else VOICE_M)
    return sorted(got, key=lambda n: (rank(n), n))


def is_female(ch):
    """인물 설명에서 성별을 읽는다 (woman 안에 man 이 있으니 낱말 경계로)."""
    blob = " ".join(str(ch.get(k) or "") for k in ("flow_prompt", "voice")).lower()
    return not re.search(r"\bman\b|\bmale\b|\bboy\b", blob)


def _speaker_keys(ch):
    """이 인물이 대사 줄에서 불리는 이름들 (본처 · Wife · wife …).

    ⚠️ `.title()` 을 쓰면 "Other Woman" 이 되는데 대사 줄의 이름표는
       "Other woman" 이다(첫 글자만 대문자). 그러면 못 찾는다.
    """
    keys = [(ch.get("name") or "").strip(),
            (ch.get("role_en") or "").strip()]
    short = re.sub(r"^the\s+", "", keys[1]).strip()
    keys.append(short[:1].upper() + short[1:] if short else "")
    return [k for k in keys if k]


def age_of(ch):
    """인물 설명에서 나이를 읽는다. 없으면 0."""
    m = re.search(r"(\d{1,2})\s*years?\s*old",
                  str(ch.get("flow_prompt") or ""))
    return int(m.group(1)) if m else 0


def persona_of(ch):
    """이 인물을 **몇 살, 어떤 목소리로** 읽어야 하는지 한 줄.

    ⭐ 2026-08-22 운영자: "주인공들 나이 목소리가 맞지 않아."
       본처 52·남편 55인데 목소리 지시에 나이가 한 글자도 없었다.
       같은 목소리라도 배역 나이를 알려 주면 훨씬 그 나이답게 읽는다.
    """
    age, f = age_of(ch), is_female(ch)
    sex = "여성" if f else "남성"
    if not age:
        return f"성인 {sex}"
    dec = age // 10 * 10
    if age >= 45:
        return (f"{dec}대 중년 {sex}, 나이에 맞게 "
                + ("원숙하고 차분한 목소리" if f else "낮고 묵직한 목소리"))
    return f"{dec}대 {sex}"


def pick_personas(chars):
    """인물표 → {이름: 배역 한 줄}. pick_voices 와 같은 이름 키를 쓴다."""
    out = {}
    for ch in chars or []:
        who = persona_of(ch)
        for k in _speaker_keys(ch):
            out[k] = who
    return out


# ⭐ 2026-08-22 — 45살 이상 배역에게 줄 **나이 든 목소리**.
#    운영자가 귀로 고른 것(Erinome·Iapetus)은 50대 배역엔 너무 젊게 들렸다.
#    목록 주석에 이미 적혀 있던 그 목소리들이다 (Gacrux "연륜 — 어머니뻘",
#    Algenib "거칠다"). 젊은 배역은 여전히 골라 둔 목소리를 쓴다.
MATURE_F = ["Gacrux", "Sulafat"]
MATURE_M = ["Algenib", "Alnilam"]


def pick_voices(chars):
    """인물표 → {이름: 목소리 이름}. 같은 목소리가 겹치지 않게.

    ⭐ 45살 이상 배역은 나이 든 목소리(MATURE_*)를 먼저 받는다.
    """
    vf, vm = best_voices("FEMALE"), best_voices("MALE")
    out, fi, mi, used = {}, 0, 0, set()
    for ch in chars or []:
        f = is_female(ch)
        # ⚠️⚠️ 2026-08-23 — 처음엔 엔진을 안 보고 나이 든 목소리를 끼웠다.
        #    깃허브(제미나이 열쇠 없음)는 구글 목소리(ko-KR-…)로 도는데,
        #    거기에 제미나이 이름(Gacrux)을 건네니 못 알아듣는다.
        #    내 컴퓨터엔 열쇠가 있어서 **로컬에선 또 안 드러났다.**
        #    나이 든 전용 목소리는 제미나이에만 있다 — 구글이면 기본 순서로.
        mature = ([v for v in (MATURE_F if f else MATURE_M) if v not in used]
                  if engine() == "gemini" else [])
        if age_of(ch) >= 45 and mature:
            v = mature[0]
        elif f:
            while vf[fi % len(vf)] in used and fi < len(vf) * 2:
                fi += 1
            v, fi = vf[fi % len(vf)], fi + 1
        else:
            while vm[mi % len(vm)] in used and mi < len(vm) * 2:
                mi += 1
            v, mi = vm[mi % len(vm)], mi + 1
        used.add(v)
        for k in _speaker_keys(ch):
            out[k] = v
    return out


def tone_of(text):
    """말투를 소리 높낮이로 (느낌표는 조금 높게, 마침표는 조금 낮게).

    ⚠️ 구글 클라우드 TTS 에서만 쓴다. 제미나이는 높낮이 숫자 대신
       **연기 지시(direct)** 로 말투를 정한다 — 그쪽이 훨씬 잘 먹는다.
    """
    t = str(text or "")
    if "!" in t or "?!" in t:
        return 1.5
    return 0.0


# ── ⭐ 연기 지시 (제미나이에만 있는 통로) ────────────────────
#    이게 이번 바꿈의 핵심이다. 같은 글자라도 어떻게 읽으라고 말해 주면
#    낭독이 연기가 된다. 구글 클라우드 TTS 에는 이 자리 자체가 없었다.
MOOD = [
    # (알아볼 말, 연기 지시)
    (r"미안|잘못했|제발|용서|어떻게 나한테|어떻게 나에게|눈물|울고|미치겠",
     "울음을 삼키느라 목이 메어, 떨리는 낮은 목소리로 힘겹게"),
    (r"미쳤|제정신|당장|꺼져|닥쳐|뻔뻔|쓰레기|짐승|어디서|감히|똑바로",
     "이를 악물고 화를 눌러 담아, 낮지만 서슬 퍼렇게"),
    (r"[!]",
     "감정이 터져 나와 목소리를 높여, 몰아붙이듯 세게"),
    (r"웃기|우스|그래서 뭐|어디 한번|잘났|대단하",
     "코웃음을 치며 비꼬듯, 여유 있는 척 차갑게"),
    (r"[?]",
     "믿기지 않는다는 듯 되묻듯이, 끝을 올려 날카롭게"),
]
MOOD_BASE = "감정을 눌러 담아, 차분하지만 무겁게"

# ⭐⭐ 2026-08-21 — 운영자: "한국사람 목소리 같긴해 근데 스타일은 좀 바꿔야할듯"
#    엔진 문제(외국인 소리)는 풀렸고, 남은 것은 **어떤 결로 연기하느냐**다.
#    ⚠️ mood() 와 층이 다르다 —
#       mood()  : 대사 **한 줄마다** 달라지는 결 (물음표면 되묻듯, 느낌표면 세게)
#       STYLES  : **작품 전체**에 걸리는 결 (막장이냐 담백하냐)
#    스타일이 결을 정해 주면 그것이 mood() 를 눌러 이긴다. 안 정해 주면
#    (`how`가 None) 예전처럼 줄마다 mood() 가 고른다.
STYLES = {
    "drama": {
        "name": "드라마 (기준)",
        "how": None,                    # 줄마다 mood() 가 정한다
        "add": None,
        "rate": 1.0,
        "voice_f": None, "voice_m": None,
    },
    "fierce": {
        "name": "격하게 (막장 톤)",
        # ⚠️⚠️ 2026-08-22 — 여기서 **두 번 헛디뎠다.**
        #    ① 처음엔 "격하게·날카롭게" 라고 썼는데 안전 기준에 자주 막혀서
        #       "**무대에서처럼** 크게 내지르고" 로 바꿨다. 막히는 건 풀렸는데,
        #       무대 발성이야말로 **더빙 목소리 그 자체**다. 운영자가 곧바로
        #       "여전히 외국인 같네" 했다. 안전 기준을 피하려던 말이
        #       소리를 망친 것이다.
        #    ② 줄마다 다르던 결을 **한 줄로 덮어썼다.** 세 마디가 다 같은
        #       지시로 읽히니 변화가 없어 더 기계 같아졌다.
        #    → 결은 줄마다의 mood() 를 **살리고**, 그 위에 세기만 얹는다.
        #      한국 드라마의 싸움은 내지르지 않는다. 낮게, 빠르게 몰아붙인다.
        "how": None,
        # ⚠️ 2026-08-22 운영자: "발음이 조금씩 뭉개져."
        #    여기 있던 "빠르게" 가 주범이다 — 빠르게 읽으라고 시키니
        #    자음이 뭉개진다. 세기는 유지하되 서두르지 말라고 바꾼다.
        "add": "감정을 더 세게 싣되 서두르지 않고",
        "rate": 1.0,
        # ⚠️ 목소리도 함께 바꿨던 것을 되돌린다. 운영자가 한국사람 같다고 한
        #    그 소리가 Orus 였다. 한 번에 둘을 바꾸면 무엇이 범인인지 모른다.
        "voice_f": "Kore", "voice_m": "Orus",
    },
    "dry": {
        "name": "담백하게 (쇼츠 템포)",
        "how": ("감정을 겉으로 터뜨리지 않고 낮게 눌러 담아 담담하게, "
                "군더더기 없이 조금 빠른 호흡으로"),
        "rate": 1.12,
        "voice_f": "Kore", "voice_m": "Orus",
    },
    "deep": {
        "name": "중후하게 (나이 든 목소리)",
        "how": None,
        "rate": 1.0,
        "voice_f": "Gacrux", "voice_m": "Algenib",
    },
}
# ⭐ 2026-08-21 — 운영자가 귀로 고른 결. "더 격하게 (막장 톤)".
#    바꾸려면 이 한 줄만 고치면 된다 (또는 VOICE_STYLE 로 그때그때).
STYLE_DEFAULT = "fierce"


def style_now():
    """지금 쓰는 말투 결의 이름. 모르는 값이 오면 기준으로 돌아간다."""
    k = (os.environ.get("VOICE_STYLE") or "").strip().lower()
    return k if k in STYLES else STYLE_DEFAULT


def style_of():
    return STYLES[style_now()]


def mood(text):
    """대사를 보고 **어떻게 읽어야 하는지** 정한다."""
    t = str(text or "")
    for pat, how in MOOD:
        if re.search(pat, t):
            return how
    return MOOD_BASE


def direct(text, who=None):
    """제미나이에 보낼 한 덩어리 — 연기 지시 + 대사.

    ⚠️ 지시를 **소리 내어 읽어 버리면** 견본이 통째로 망가진다. 구글이 권하는
       모양(지시 → 쌍점 → 대사)을 그대로 지킨다. 지시는 짧게, 대사는 큰따옴표
       안에 딱 한 번만 둔다. 진짜로 안 읽는지는 tools/tts_live_check.py 가
       **소리 길이를 재서** 확인한다 (지시까지 읽으면 길이가 두 배가 넘는다).
    (또박또박은 how_of 안에 이미 있다 — 여기서 또 적으면 겹말이 된다)
    """
    t = re.sub(r'^["“”]+|["“”]+$', "", str(text or "").strip())
    return (f"{how_of(t, who)} "
            f"다음 큰따옴표 안의 말만 그대로: \"{t}\"")


def how_of(text, who=None):
    """**연기 지시만** (대사는 빼고). `who` 는 배역 한 줄 (persona_of).

    ⚠️ 두 길이 규격이 다르다 —
       AI 스튜디오 쪽은 지시와 대사를 **한 덩어리**로 받는다 → direct()
       구글 클라우드 쪽은 지시(prompt)와 대사(text)를 **따로** 받는다 → how_of()
       그래서 한 곳에서 만들어 둘이 나눠 쓴다. 안 그러면 결을 바꿀 때
       한쪽만 바뀌어 어긋난다.
    """
    t = re.sub(r'^["“”]+|["“”]+$', "", str(text or "").strip())
    st = style_of()
    # ⚠️ 결이 `how` 로 **덮어쓰기**를 할 수도 있고, `add` 로 **얹기**만 할 수도
    #    있다. 얹기 쪽이 낫다 — 줄마다의 결(물음표면 되묻듯, 느낌표면 세게)이
    #    살아 있어야 세 마디가 다르게 들린다. 덮어쓰면 다 같은 소리가 된다.
    how = st["how"] or mood(t)
    if st.get("add"):
        how = f"{how}, {st['add']}"
    lead = "한국 드라마의 한 장면이다."
    if who:
        # ⭐ 2026-08-22 — 배역 나이를 알려 준다 ("주인공들 나이 목소리가 맞지 않아")
        lead += f" {who} 배역이다."
    # ⭐ 발음은 어느 길로 가든 또박또박 — "빠르게" 가 뭉개던 것을 여기서 되잡는다
    return (f"{lead} 서울 말씨로, {how} 말하되, "
            f"발음은 뭉개지지 않게 또박또박 말한다.")


# ── 제미나이 목소리 ────────────────────────────────────
def gem_models():
    """구글에 물어 **소리 낼 줄 아는 모델**을 찾는다 (이름이 바뀌어도 따라간다)."""
    k = gem_key()
    if not k:
        return []
    try:
        req = urllib.request.Request(f"{GEM}/models?key={k}&pageSize=200",
                                     headers={"User-Agent": "verdict-theater/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            got = json.loads(r.read().decode("utf-8"))
    except Exception:                                        # noqa: BLE001
        return []
    out = []
    for m in got.get("models") or []:
        name = str(m.get("name", "")).split("/", 1)[-1]
        if "tts" not in name:
            continue
        if "generateContent" not in (m.get("supportedGenerationMethods") or []):
            continue
        out.append(name)
    return out


def gem_pick():
    """쓸 목소리 모델 하나. flash(싼 쪽)를 먼저, 판 높은 것을 먼저."""
    global _GEM_MODEL
    if _GEM_MODEL:
        return _GEM_MODEL
    want = (os.environ.get("GEMINI_TTS_MODEL") or "").strip()
    if want:
        _GEM_MODEL = want
        return _GEM_MODEL
    got = gem_models()
    if not got:
        _GEM_MODEL = GEM_TTS_FALLBACK
        return _GEM_MODEL

    def ver(n):
        m = re.search(r"gemini-(\d+)(?:\.(\d+))?", n)
        return (int(m.group(1)), int(m.group(2) or 0)) if m else (0, 0)

    got.sort(key=lambda n: (ver(n), "flash" in n, -len(n)), reverse=True)
    _GEM_MODEL = got[0]
    return _GEM_MODEL


# ⭐⭐ 2026-08-21 — 같은 제미나이 목소리를 **구글 클라우드 쪽으로도** 부를 수 있다.
#    왜 이쪽이 중요한가: AI 스튜디오 무료 등급은 **하루 10번**이라 한 화도 못
#    만든다. 클라우드 쪽(GOOGLE_TTS_KEY)은 이미 결제가 붙어 있어 그 벽이 없다.
#    ⚠️ 추측이 아니라 깃허브 안에서 **직접 걸어 보고** 알아낸 규격이다
#       (tools/tts_route_probe.py). 잘못 부르면 구글이 이렇게 답한다 —
#         "Gemini models cannot be used with non-Gemini voices."
#           → model_name 을 제미나이로 두면 목소리 이름도 제미나이 것이어야 한다
#         "Prompt is only supported for Gemini TTS."
#           → 연기 지시(prompt)는 model_name 이 제미나이일 때만 받는다
CLOUD_GEM = "https://texttospeech.googleapis.com/v1beta1/text:synthesize"
_CLOUD_GEM_OK = None          # 모름 / True 된다 / False 안 된다 (한 번만 알아본다)


def cloud_model():
    return (os.environ.get("CLOUD_TTS_MODEL") or "gemini-2.5-flash-tts").strip()


# ── ⭐ 타입캐스트 (2026-08-23) ─────────────────────────
#    운영자: "발음이 아직도 좀 뭉개져. 구글 TTS 말고 typecast 로 바꿔볼까?"
#    한국어 전용 서비스라 발음이 또렷하다. 열쇠는 관리자 페이지에서 넣는다
#    (깃허브에 갈 일 없음). 값은 글자 수로 매겨진다.
TC_API = "https://api.typecast.ai"
_TC_V = {"list": None}


def tc_explain(code, body):
    """타입캐스트가 거절한 까닭을 쉬운 말로."""
    if code == 401:
        return "❌ 타입캐스트 열쇠가 잘못됐다. 관리자 페이지에서 열쇠를 다시 넣어라"
    if code == 402 or "credit" in body.lower():
        return "❌ 타입캐스트 잔액(크레딧)이 다 떨어졌다. typecast.ai 에서 충전해야 한다"
    if code == 429:
        return "❌ 타입캐스트를 잠깐 너무 많이 불렀다. 조금 뒤에 다시 하면 된다"
    return f"❌ 타입캐스트가 거절했다 ({code})"


def tc_voices():
    """쓸 수 있는 타입캐스트 목소리들. [{id, name, model, gender, emotions}]"""
    if _TC_V["list"] is not None:
        return _TC_V["list"]
    k = tc_key()
    if not k:
        raise RuntimeError("TYPECAST_API_KEY 가 없다")
    req = urllib.request.Request(f"{TC_API}/v1/voices",
                                 headers={"X-API-KEY": k})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            got = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(tc_explain(e.code, e.read().decode("utf-8", "replace")[:200])) from None
    # 겉모양이 배열일 수도, {"result": [...]}일 수도 있다 — 둘 다 받는다
    rows = got if isinstance(got, list) else (got.get("result") or got.get("voices") or [])
    out = []
    for v in rows:
        if not isinstance(v, dict):
            continue
        g = str(v.get("gender") or "").lower()
        out.append({
            "id": str(v.get("voice_id") or v.get("id") or ""),
            "name": str(v.get("voice_name") or v.get("name") or ""),
            "model": str(v.get("model") or "ssfm-v21"),
            "gender": ("f" if g.startswith(("f", "여")) else
                       "m" if g.startswith(("m", "남")) else ""),
            "emotions": [str(x) for x in (v.get("emotions") or [])],
        })
    _TC_V["list"] = [v for v in out if v["id"]]
    return _TC_V["list"]


def tc_voice_of(vid):
    try:
        return next((v for v in tc_voices() if v["id"] == vid), None)
    except Exception:                                        # noqa: BLE001
        return None


def tc_emotion(text):
    """대사를 보고 감정 preset 을 고른다 (타입캐스트는 글 지시 대신 preset)."""
    t = str(text or "")
    if re.search(r"미쳤|제정신|당장|꺼져|닥쳐|뻔뻔|쓰레기|어디서|감히|나가|못 살|화", t):
        emo = "angry"
    elif re.search(r"미안|잘못했|제발|용서|눈물|울|흑|힘들|아파|무서", t):
        emo = "sad"
    elif re.search(r"고마워|좋아|다행|하하|웃", t):
        emo = "happy"
    else:
        emo = "normal"
    inten = 2 if ("!" in t or "?!" in t) else 1
    return emo, inten


def typecast_say(text, voice, out):
    """타입캐스트로 한 마디. 만들어진 wav 경로를 돌려준다."""
    k = tc_key()
    if not k:
        raise RuntimeError("TYPECAST_API_KEY 가 없다")
    info = tc_voice_of(voice) or {}
    emo, inten = tc_emotion(text)
    if info.get("emotions") and emo not in info["emotions"]:
        emo = "normal" if "normal" in info["emotions"] else info["emotions"][0]
    body = {
        "voice_id": voice,
        "text": bare(text),
        "model": info.get("model") or "ssfm-v21",
        "language": "kor",
        "prompt": {"emotion_preset": emo, "emotion_intensity": inten},
        "output": {"audio_format": "wav", "audio_tempo": 1.0, "volume": 100},
    }
    count_call()
    bill_add("typecast", bare(text))
    req = urllib.request.Request(
        f"{TC_API}/v1/text-to-speech", data=json.dumps(body).encode("utf-8"),
        headers={"X-API-KEY": k, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")[:200]
        raise RuntimeError(f"{tc_explain(e.code, msg)}\n   (원문: {msg})") from None
    out = Path(out)
    tmpb = out.with_suffix(".bin")
    tmpb.write_bytes(raw)
    # 어떤 형식으로 오든 ffmpeg 가 읽어 48kHz wav 로 맞춘다
    r2 = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmpb),
                         "-ar", "48000", "-ac", "1", str(out)],
                        capture_output=True, text=True)
    tmpb.unlink(missing_ok=True)
    if r2.returncode != 0 or not out.exists():
        raise RuntimeError(f"타입캐스트 소리를 못 읽었다: {r2.stderr[:150]}")
    return out


def cloud_gem_say(text, voice, out, style=None, who=None):
    """구글 클라우드로 제미나이 목소리 한 마디 (연기 지시를 함께 보낸다)."""
    k = gkey()
    if not k:
        raise RuntimeError("GOOGLE_TTS_KEY 가 없다")
    body = {
        "input": {"text": bare(text), "prompt": style or how_of(text, who)},
        "voice": {"languageCode": "ko-KR", "name": voice,
                  "model_name": cloud_model()},
        "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 48000},
    }
    count_call()
    req = urllib.request.Request(
        f"{CLOUD_GEM}?key={k}", data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            got = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        msg = raw
        try:
            msg = json.loads(raw)["error"]["message"]
        except Exception:                                    # noqa: BLE001
            pass
        raise RuntimeError(msg[:300]) from None
    bill_add(cloud_model(), text)
    return _write(got, out)


# ⭐⭐ 2026-08-22 — 쓴 값을 장부에 남긴다.
#    무료 등급(하루 10번)에서 결제 계정으로 옮긴 순간부터 쓴 만큼 값이 나가는데,
#    장부에 한 줄도 안 남고 있었다. 그림값이 새어 나가던 것과 똑같은 자리다.
#
#    ⚠️ 한 마디마다 적지 않고 **모아서 한 줄로** 적는다. 한 마디는 1원도 안 되는데
#       줄마다 반올림하면 15줄짜리 한 화가 실제보다 훨씬 비싸게 적힌다.
_USED = {"chars": 0, "model": ""}

# ⭐⭐ 2026-08-22 운영자: "왜 이렇게 돈을 많이 쓰는 거야? 계속 빠져나가."
#    세어 보니 **상한이 사실상 없었다.**
#      한 마디 만들 때  : 모델 3개 x 말투 3가지 x 재시도 4번 = **최대 36번**
#      목소리 고르기 1회 : 소리 26개 x 36 = **최대 936번**
#    실패가 겹치면 조용히 수백 번을 부르고, 그게 다 돈이다.
#    → 한 번 실행에서 부를 수 있는 **총 횟수**를 못 박는다. 넘으면 멈춘다.
#      (많이 만드는 일은 CALL_CAP 을 올려서 부러 허락해야 한다)
_CALLS = {"n": 0}


def call_cap():
    try:
        return max(1, int(os.environ.get("TTS_CALL_CAP") or 80))
    except Exception:                                        # noqa: BLE001
        return 80


class CapReached(RuntimeError):
    """이번 실행에서 부를 수 있는 횟수를 다 썼다."""


# ⭐⭐ 2026-08-22 — 운영자가 실제 청구서를 보여 줬다. 28일에 **38,200원**.
#    나는 "16화 전체 210원" 이라고 말했다. **내 계산이 틀렸다.**
#    글자 수로 값을 매겼는데(100만 자당 30달러), 제미나이는 **토큰**으로 센다.
#    소리 1초에 토큰이 몇 개인지 나는 모른다 — 그래서 추정이 통째로 빗나갔다.
#    → 이제 **추측하지 않는다.** 구글이 응답에 실어 주는 usageMetadata 를
#      그대로 모아서, 실제 토큰 수로 값을 매긴다.
_USAGE = {"in": 0, "out": 0, "model": ""}


def usage_add(model, u):
    """구글이 알려 준 토큰 수를 그대로 모은다."""
    if not u:
        return
    _USAGE["in"] += int(u.get("promptTokenCount") or 0)
    _USAGE["out"] += int(u.get("candidatesTokenCount")
                         or u.get("responseTokenCount") or 0)
    if model:
        _USAGE["model"] = str(model)


def usage_so_far():
    return dict(_USAGE)


def count_call():
    _CALLS["n"] += 1
    if _CALLS["n"] > call_cap():
        raise CapReached(
            f"❌ 이번 실행에서 목소리를 {_CALLS['n'] - 1}번 불렀다 — "
            f"상한({call_cap()}번)에 걸려 멈춘다.\n"
            f"   부러 더 만들려면 TTS_CALL_CAP 을 올려라.")
    return _CALLS["n"]


def calls_so_far():
    return _CALLS["n"]


def bill_add(model, text):
    """만든 글자 수를 모아 둔다 (아직 장부에는 안 적는다)."""
    _USED["chars"] += len(str(text or ""))
    if model:
        _USED["model"] = str(model)


def bill_flush(note=""):
    """모아 둔 것을 장부에 한 줄로 적는다. 돌려주는 것은 원.

    ⚠️ 2026-08-22 — 글자 수로 매기던 것을 버린다. 구글이 알려 준 **토큰 수**가
       있으면 그것으로 매기고, 없을 때만 (글자 수로) 넉넉히 어림한다.
       내 어림이 실제의 몇십 분의 일이었다.
    """
    n, m = _USED["chars"], _USED["model"]
    u_in, u_out = _USAGE["in"], _USAGE["out"]
    if not n and not u_out:
        return 0.0
    _USED["chars"] = 0
    _USAGE["in"] = _USAGE["out"] = 0
    try:
        import cost as _c
        if u_out:
            won = _c.krw(m or _USAGE["model"], u_in, u_out)
            _c.record("목소리", won,
                      f"토큰 들어간 {u_in:,} · 나온 {u_out:,} · {m} {note}".strip())
            print(f"    (구글이 센 토큰: 들어간 {u_in:,} · 나온 {u_out:,})")
        else:
            won = _c.voice_krw(m, n)
            _c.record("목소리", won, f"{n}자(어림) · {m} {note}".strip())
        return won
    except Exception as e:                                   # noqa: BLE001
        print(f"    (목소리 값을 장부에 못 적었다: {e} — 제작은 계속한다)")
        return 0.0


def route_note():
    """지금 **어느 길로** 부르는가.

    ⭐ 이걸 화면에 적는 까닭: 두 길은 소리는 같은데 **한도가 하늘과 땅 차이**다.
       AI 스튜디오 길 — 무료 등급 하루 10번 (한 화도 못 만든다)
       구글 클라우드 길 — 결제 계정 기준, 하루 횟수 제한 없음
       어느 쪽으로 가고 있는지 모르면, 왜 갑자기 안 되는지 알 수가 없다.
    """
    if not gem_key() and not gkey():
        return "열쇠가 없다"
    if cloud_gem_ready():
        return f"구글 클라우드 ({cloud_model()}) — 하루 횟수 제한 없음"
    return "AI 스튜디오 — 무료 등급은 하루 10번뿐"


def cloud_gem_ready():
    """이 길이 열려 있는가. **한 번만** 알아보고 기억한다."""
    global _CLOUD_GEM_OK
    if _CLOUD_GEM_OK is not None or not gkey():
        return bool(_CLOUD_GEM_OK)
    import tempfile as _t
    try:
        cloud_gem_say("확인", best_voices("FEMALE")[0],
                      Path(_t.mkdtemp()) / "probe.wav")
        _CLOUD_GEM_OK = True
    except Exception as e:                                   # noqa: BLE001
        _CLOUD_GEM_OK = False
        m = str(e)
        if "aiplatform" in m or "Agent Platform" in m or "has not been used" in m:
            # ⚠️ 딱 하나만 켜면 되는 문제다. 무엇을 켜야 하는지 정확히 알려 준다.
            print("    ⚠️ 구글 클라우드 쪽 제미나이 목소리가 아직 안 열렸다.\n"
                  "       구글 클라우드 콘솔에서 **Vertex AI API"
                  "(aiplatform.googleapis.com)** 를 [사용] 하면 열린다.\n"
                  "       그때까지는 AI 스튜디오 쪽으로 부른다 "
                  "(무료 등급은 하루 10번이다)")
        else:
            print(f"    ⚠️ 구글 클라우드 쪽 제미나이 목소리를 못 쓴다 — {m[:120]}")
    return bool(_CLOUD_GEM_OK)


def gem_order():
    """쓸 모델을 차례대로. 고른 것이 안 되면 다음 것으로 넘어간다."""
    first = gem_pick()
    # ⚠️ pro 계열은 무료 한도가 0 이다(실제로 확인했다). 뒤로 민다.
    rest = sorted((m for m in gem_models() if m != first),
                  key=lambda n: ("pro" in n, n))
    return [first] + rest + ([GEM_TTS_FALLBACK]
                             if first != GEM_TTS_FALLBACK
                             and GEM_TTS_FALLBACK not in rest else [])


def _pcm_wav(pcm, path, rate=24000):
    """제미나이가 준 날것 소리(PCM)를 wav 로 감싼다.

    ⚠️ 제미나이는 wav 가 아니라 **머리말이 없는 날것**(16비트·홑소리)을 준다.
       그대로 파일에 쓰면 ffmpeg 가 못 읽는다. 머리말을 붙여 줘야 한다.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(rate))
        w.writeframes(pcm)
    return p


def _rate_of(mime):
    m = re.search(r"rate=(\d+)", str(mime or ""))
    return int(m.group(1)) if m else 24000


# ⚠️ 2026-08-21 실제로 걸어 보고 알았다 — 같은 대사·같은 지시인데도 어떤
#    때는 "SAFETY" 로 막힌다(들쭉날쭉하다). 막장 드라마 대사라 그렇다.
#    ① 안전 기준을 드라마 대사 수준으로 낮춰 두고,
#    ② 그래도 막히면 **지시를 순하게 → 지시 없이** 로 물러서며 다시 만든다.
#    ③ 그래도 안 되면 다음 모델로 간다. 소리는 어떻게든 나오게 한다.
GEM_SAFE = [{"category": c, "threshold": "BLOCK_NONE"} for c in (
    "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT")]
GEM_TRIES = 2
WAIT_MAX = 45.0        # 한 번에 이보다 오래 쉬지는 않는다
WAIT_BUDGET = 150.0    # 한 마디에 쓰는 기다림을 다 합쳐 이만큼까지


def _wait_of(msg):
    """구글이 "Please retry in 17.8s" 라고 알려 준 시간을 읽는다."""
    m = (re.search(r"retry in ([\d.]+)s", str(msg))
         or re.search(r"retryDelay[\"\':\s]+([\d.]+)s", str(msg)))
    return min(WAIT_MAX, float(m.group(1)) + 1.0) if m else 5.0
WAY_NOTE = ["", "연기 지시가 막혀 **순한 지시**로 다시 만들었다",
            "연기 지시가 막혀 **지시 없이** 만들었다"]


class _Busy(RuntimeError):
    """잠깐 너무 많이 불렀다 (429).

    ⚠️ 2026-08-21 실제로 걸어 보고 알았다 —
       · 무료 한도는 **1분에 10번**이다(gemini-3.1-flash-tts 기준).
         구글이 "Please retry in 17.8s" 라고 **얼마나 쉬면 되는지 알려 준다.**
         눈대중으로 2초·4초 쉬면 헛물만 켠다. 알려 준 만큼 쉰다.
       · `limit: 0` 이라고 오면 그 모델은 **무료로는 아예 못 쓴다**
         (gemini-2.5-pro-tts 가 그렇다). 기다릴 것 없이 다음 모델로 넘어간다.
    """

    def __init__(self, msg, wait=0.0, dead=False):
        super().__init__(msg)
        self.wait = float(wait)
        self.dead = bool(dead)


Busy = None            # 아래에서 _Busy 를 가리킨다 (바깥에서 쓰는 이름)


class _Blocked(RuntimeError):
    """안전 기준에 막혔다. 말투를 순하게 바꿔 다시 해 본다."""


Busy = _Busy           # 바깥에서 "한도 때문인가" 를 가려낼 때 쓴다


def bare(text):
    """따옴표만 벗긴 맨 대사."""
    return re.sub(r'^["“”]+|["“”]+$', "", str(text or "").strip())


def flat(text):
    """지시를 거의 없앤 마지막 수단.

    ⚠️ 대사만 덜렁 던지면 안 된다. 실제로 걸어 보니 2.5 모델이 이렇게 거절했다 —
       "Model tried to generate text, but it should only be used for TTS."
       아무 지시가 없으면 모델이 **읽는 대신 대답하려 든다.**
       그래서 '읽어라' 한 마디는 끝까지 남긴다.
    """
    return f'다음 말을 그대로 소리 내어 읽어라: "{bare(text)}"'


def soft(text):
    """순한 지시 (센 낱말을 뺀다)."""
    return f'한국어 대사다. 감정을 실어 또박또박 읽는다: "{bare(text)}"'


def _gem_once(model, prompt, voice, safe=True):
    count_call()
    """제미나이를 한 번 부른다. (날것 소리, 빠르기) 를 돌려준다."""
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}},
            },
        },
    }
    if safe:
        body["safetySettings"] = GEM_SAFE
    req = urllib.request.Request(
        f"{GEM}/models/{model}:generateContent?key={gem_key()}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "User-Agent": "verdict-theater/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            got = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        msg = raw
        try:
            msg = json.loads(raw)["error"]["message"]
        except Exception:                                    # noqa: BLE001
            pass
        if e.code == 429:
            # ⚠️ 하루치인지 분당인지는 message 가 아니라 details 의 quotaId 에만
            #    적혀 있다. 가려내려면 받은 몸통 전체를 봐야 한다.
            day = "PerDay" in raw
            raise _Busy(gem_explain(429, raw if day else msg),
                        _wait_of(msg), "limit: 0" in msg or day) from None
        # 안전 기준을 모르는 모델이면 그것만 빼고 딱 한 번 다시
        if e.code == 400 and safe and "safety" in raw.lower():
            return _gem_once(model, prompt, voice, safe=False)
        raise RuntimeError(f"{gem_explain(e.code, msg)}\n"
                           f"   (구글이 보낸 말: {msg[:200]})") from None
    cand = (got.get("candidates") or [{}])[0]
    try:
        part = cand["content"]["parts"][0]["inlineData"]
    except Exception:                                        # noqa: BLE001
        raise _Blocked(f"제미나이가 소리를 안 보냈다 "
                       f"(까닭: {cand.get('finishReason') or '모름'})") from None
    return base64.b64decode(part["data"]), _rate_of(part.get("mimeType"))


def gem_say(text, voice, out, style=None, who=None):
    """제미나이로 한 마디. **연기 지시를 함께 보낸다.**

    막히면 지시를 순하게 → 지시 없이 → 다음 모델 순으로 물러서며 다시 만든다.
    """
    if not gem_key():
        raise RuntimeError("GEMINI_API_KEY 가 없다")
    ways = [style or direct(text, who), soft(text), flat(text)]
    why, spent, busy = "까닭을 못 받았다", 0.0, False
    for model in gem_order():
        dead = False
        for lvl, prompt in enumerate(ways):
            for t in range(GEM_TRIES):
                try:
                    pcm, rate = _gem_once(model, prompt, voice)
                except _Busy as e:
                    why, busy = str(e), True
                    if e.dead:                # 이 모델은 무료로 못 쓴다
                        dead = True
                        break
                    if spent + e.wait > WAIT_BUDGET:
                        break                 # 너무 오래 기다렸다 — 다음으로
                    if e.wait >= 1.0:
                        print(f"    ⏳ 한도에 걸렸다 — {e.wait:.0f}초 쉬었다 "
                              f"다시 한다")
                    time.sleep(e.wait)
                    spent += e.wait
                    continue
                except _Blocked as e:
                    why, busy = str(e), False
                    break                     # 말투를 순하게 바꿔 다시
                except RuntimeError as e:
                    why, dead, busy = str(e), True, False
                    break
                if lvl:
                    print(f"    ⚠️ {WAY_NOTE[lvl]}")
                bill_add(model, text)
                return _pcm_wav(pcm, out, rate)
            if dead:
                break
    # ⚠️ **한도에 걸린 것**과 **진짜로 고장난 것**은 다르다. 섞어 놓으면
    #    밀어 넣을 때마다 하는 확인이 한도 때문에 빨간불이 되고, 운영자에게
    #    "고장났다" 는 메일이 쓸데없이 간다. 갈라서 알린다.
    if busy:
        raise _Busy(f"❌ 한도에 걸려 소리를 못 만들었다 (열쇠는 멀쩡하다)\n"
                    f"   {why}")
    raise RuntimeError(f"❌ 제미나이가 소리를 못 만들었다\n   {why}")


def gem_explain(code, msg):
    """제미나이가 거절한 까닭을 쉬운 말로."""
    m = str(msg or "").lower()
    if "not found" in m or "is not supported" in m or code == 404:
        return ("❌ 목소리 모델을 못 찾았다. 열쇠가 **AI 스튜디오** 것인지 "
                "확인한다 (aistudio.google.com 에서 만든 열쇠라야 한다)")
    if "api key not valid" in m or "api_key_invalid" in m:
        return ("❌ 열쇠가 잘못됐다. 깃허브 시크릿 GEMINI_API_KEY 를 "
                "다시 확인한다 (AIza… 로 시작한다)")
    if "perday" in m.replace(" ", "") or "per day" in m:
        # ⚠️ 2026-08-21 실제로 확인했다 —
        #    quotaId = GenerateRequestsPerDayPerProjectPerModel-FreeTier, 값 10.
        #    **하루에 10번**이다. "조금 뒤에 다시" 는 거짓말이 된다.
        #    한 화가 대사 15줄쯤이므로 무료 등급으로는 한 화도 못 만든다.
        return ("❌ **오늘 몫을 다 썼다.** 무료 등급은 이 목소리 모델을 "
                "하루 10번까지만 준다.\n"
                "   한 화가 대사 15줄쯤이라 무료로는 한 화도 못 만든다 — "
                "결제 계정을 연결해야 한다")
    if "quota" in m or "rate limit" in m or code == 429:
        return "❌ 잠깐 너무 많이 불렀다. 조금 뒤에 다시 하면 된다"
    if "billing" in m:
        return "❌ 결제 계정을 연결해야 이 모델을 쓸 수 있다"
    if "permission" in m or code == 403:
        return ("❌ 열쇠에 이 모델 쓸 권한이 없다. 열쇠 제한을 '없음' 으로 "
                "두거나 Generative Language API 를 켠다")
    return f"❌ 제미나이가 거절했다 (HTTP {code})"


# ── 구글 클라우드 TTS 부르기 ────────────────────────────
def explain(code, msg):
    """구글이 거절한 까닭을 쉬운 말로."""
    m = str(msg or "").lower()
    if "has not been used" in m or "disabled" in m or "service_disabled" in m:
        return ("❌ Text-to-Speech API 를 아직 **켜지 않았다.**\n"
                "   구글 클라우드 콘솔에서 'Cloud Text-to-Speech API' 를 찾아 "
                "[사용] 을 누르면 된다")
    if "api key not valid" in m or "api_key_invalid" in m or code == 400:
        return ("❌ 열쇠가 잘못됐다. 깃허브 시크릿 GOOGLE_TTS_KEY 에 "
                "붙여 넣은 값을 다시 확인한다 (AIza… 로 시작한다)")
    if "billing" in m:
        return ("❌ 결제 계정을 연결해야 한다. 무료 한도(월 100만 자) 안에서는 "
                "청구되지 않지만 계정 연결 자체는 필요하다")
    if "referer" in m or "restrict" in m or "blocked" in m:
        return ("❌ 열쇠에 사용 제한(웹사이트·IP)이 걸려 있다. "
                "제한을 '없음' 으로 두거나 API 제한만 걸어야 한다")
    if code == 429:
        return "❌ 잠깐 너무 많이 불렀다. 조금 뒤에 다시 하면 된다"
    return f"❌ 구글이 거절했다 (HTTP {code})"


def _post(k, body):
    count_call()
    req = urllib.request.Request(
        f"{API}?key={k}", data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _write(got, out):
    if "audioContent" not in got:
        raise RuntimeError(f"❌ 구글이 소리를 안 보냈다: {str(got)[:200]}")
    p = Path(out or "tts.wav")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(base64.b64decode(got["audioContent"]))
    return p


def google_say(text, voice, rate, pitch, out):
    """구글 클라우드 TTS 로 한 마디 (되돌아갈 자리)."""
    k = gkey()
    if not k:
        raise RuntimeError("GOOGLE_TTS_KEY 가 없다")
    cfg = {
        "input": {"text": str(text or "")},
        "voice": {"languageCode": "ko-KR", "name": voice},
        "audioConfig": {
            "audioEncoding": "LINEAR16",
            "sampleRateHertz": 48000,
            "speakingRate": max(RATE_MIN, min(RATE_MAX, float(rate))),
            "pitch": float(pitch),
        },
    }
    try:
        got = _post(k, cfg)
    except urllib.error.HTTPError as e:
        # ⚠️ 가장 사람 같은 목소리(Chirp3-HD)는 말 속도·높낮이를 안 받아 준다.
        #    그것 때문에 거절당하면 **그 두 가지만 빼고** 다시 부른다.
        raw0 = e.read().decode("utf-8", "replace")
        if e.code == 400 and ("speakingRate" in raw0 or "pitch" in raw0
                              or "audio_config" in raw0.lower()):
            cfg["audioConfig"] = {"audioEncoding": "LINEAR16",
                                  "sampleRateHertz": 48000}
            try:
                got = _post(k, cfg)
            except urllib.error.HTTPError as e2:
                e, raw0 = e2, e2.read().decode("utf-8", "replace")
            else:
                bill_add(voice, text)
                return _write(got, out)
        msg = raw0
        # ⚠️ 구글이 왜 거절했는지 그대로 알려 준다. 안 그러면 "실패" 세 글자만
        #    남아 운영자가 무엇을 고쳐야 할지 알 수 없다.
        try:
            msg = json.loads(msg)["error"]["message"]
        except Exception:                                    # noqa: BLE001
            pass
        raise RuntimeError(f"{explain(e.code, msg)}\n"
                           f"   (구글이 보낸 말: {msg[:200]})")
    bill_add(voice, text)
    return _write(got, out)


def _tempo(src, factor, out):
    """소리를 빠르게/느리게 (목소리 높이는 그대로 둔다).

    ⚠️ 제미나이 목소리는 '말 속도' 를 숫자로 못 받는다. 자리를 맞춰야 할 때는
       만들어 놓고 **여기서** 늘리고 줄인다. atempo 는 높이를 안 건드리므로
       다람쥐 소리가 되지 않는다.
    """
    f = max(0.5, min(2.0, float(factor)))
    if abs(f - 1.0) <= 0.04:
        return Path(src)
    out = Path(out)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src),
                        "-filter:a", f"atempo={f:.3f}", str(out)],
                       capture_output=True, text=True)
    return out if r.returncode == 0 and out.exists() else Path(src)


def say(text, voice=None, rate=1.0, pitch=0.0, out=None, style=None,
        who=None):
    """한 마디를 소리로 만든다. 만들어진 wav 파일 경로를 돌려준다.

    목소리 이름이 `ko-KR-…` 이면 구글 클라우드 TTS, 아니면 제미나이다.

    ⚠️ 2026-08-21 — 여기에 explain() 을 **함수 한가운데 끼워 넣었다가**
       소리를 만들고 돌려주는 마지막 세 줄이 explain 안으로 딸려 들어가
       say() 가 None 을 돌려줬다. 깃허브 검사가 바로 잡아 줬다
       ('NoneType' object has no attribute 'stat').
       → 도우미 함수는 **쓰는 함수보다 위**에 둔다.
    """
    if not voice:
        voice = best_voices("FEMALE")[0]
    out = Path(out or "tts.wav")
    if str(voice).startswith("ko-KR-"):
        return google_say(text, voice, rate, pitch, out)
    # ⭐ 2026-08-23 — 타입캐스트가 먼저다 (발음 뭉개짐 때문에 갈아탔다)
    if engine() == "typecast":
        eff2 = max(RATE_MIN, min(RATE_MAX, float(rate) * style_of()["rate"]))
        try:
            return _after(typecast_say(text, voice, out), eff2, out)
        except CapReached:
            raise
        except Exception as e:                               # noqa: BLE001
            # ⚠️ 조용히 물러서지 않는다 — 왜 다른 소리가 나는지 알아야 한다
            print(f"    ⚠️ 타입캐스트 실패 → 제미나이로 물러선다\n"
                  f"       ({str(e).splitlines()[0][:100]})")
            if not gem_key() and not gkey():
                raise
            voice = (best_voices("MALE") if voice in GEM_M
                     else best_voices("FEMALE"))[0]
    # ⚠️ 말투 결이 정한 빠르기와, 자리를 맞추려고 say_to_fit() 이 보내는
    #    빠르기는 **층이 다르다.** 더하지 말고 곱해야 한다. 다만 곱한 값도
    #    사람 소리로 들리는 범위(RATE_MAX)를 넘기지 않는다.
    eff = max(RATE_MIN, min(RATE_MAX, float(rate) * style_of()["rate"]))
    # ⭐ 클라우드 길이 열려 있으면 그쪽을 **먼저** 쓴다 — 하루 10번 벽이 없다.
    if cloud_gem_ready():
        try:
            return _after(cloud_gem_say(text, voice, out, style, who), eff, out)
        except Exception as e:                               # noqa: BLE001
            print(f"    ⚠️ 클라우드 쪽 실패 → AI 스튜디오 쪽으로 간다 "
                  f"({str(e).splitlines()[0][:90]})")
    try:
        p = gem_say(text, voice, out, style, who)
    except Exception as e:                                   # noqa: BLE001
        # ⚠️ 제미나이가 끝내 안 되면 구글 클라우드로 물러선다. **소리 없이
        #    넘어가면 영상의 원래(외국인 같은) 소리가 그대로 나가기 때문**이다.
        #    다만 조용히 물러서지 않는다 — 화면에 크게 적는다. 예전에 조용히
        #    되돌아간 탓에 왜 어색한지 아무도 몰랐다.
        if not gkey():
            raise
        alt = (best_voices("MALE") if voice in GEM_M else best_voices("FEMALE"))[0]
        print(f"    ⚠️ 제미나이 목소리 실패 → 구글 클라우드({alt})로 물러선다\n"
              f"       ({str(e).splitlines()[0]})")
        return google_say(text, alt, rate, pitch, out)
    return _after(p, eff, out)


def _after(p, eff, out):
    """만든 소리에 결이 정한 빠르기를 입힌다."""
    if abs(eff - 1.0) > 0.04:
        q = _tempo(p, eff, out.with_name(out.stem + "_t" + out.suffix))
        if q != p:
            return q
    return p


def dur_of(p):
    """소리 길이(초)."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def say_to_fit(text, voice, seconds, out, pitch=0.0, room=None, who=None):
    """입이 움직인 시간에 맞춰 한 마디를 만들되, **급해지지 않게** 만든다.

    · `seconds` — 영상 속 사람의 입이 움직인 시간
    · `room`    — 다음 사람이 말하기 직전까지, **실제로 쓸 수 있는 시간**

    ⚠️ 2026-08-21 — 처음에는 `seconds` 에 딱 맞췄다. 그런데 영상 만드는 쪽이
       32음절을 4.4초에 쏟아내는 바람에(초당 7.3음절), 우리 목소리도 똑같이
       급해져 **애써 바꾼 보람이 없었다.**
       → 자연스럽게 읽은 길이가 `room` 안에 들어가면 **그대로 둔다.**
         넘칠 때만, 그것도 `room` 에 맞춰 조금만 빠르게 한다.
    """
    p = say(text, voice, 1.0, pitch, out, who=who)
    d = dur_of(p)
    if d <= 0 or seconds <= 0:
        return p, d
    limit = max(float(seconds), float(room or seconds))
    if d <= limit:
        return p, d                 # 자연스러운 속도로 이미 들어간다 — 그대로
    # ⚠️ 여기서 속도를 안 자르면 2.3배 같은 값을 그대로 넘긴다. say() 안에서
    #    잘리기는 하지만, **자른 뒤 얼마나 넘치는지** 알 수 없게 된다.
    #    사람 소리로 들리는 범위를 넘느니 조금 넘치게 두는 편이 낫다.
    rate = min(RATE_MAX, max(RATE_MIN, d / limit))
    if abs(rate - 1.0) > 0.04:
        p = say(text, voice, rate, pitch, out, who=who)
        d = dur_of(p)
    if d > limit + 0.1:
        print(f"    ⚠️ 대사가 길어 {d - limit:.2f}초 넘친다 "
              f"— 대사를 조금 줄이면 좋다 (\"{str(text)[:14]}…\")")
    return p, d


# ⭐⭐ 2026-08-21 — 운영자가 목소리를 **아직 한 번도 못 들었다.**
#    쇼츠는 5컷이 다 있어야 만들어지므로, 목소리를 확인하려면 영상 다섯 개를
#    먼저 뽑아야 했다. 되돌아오는 길이 너무 길다.
#    → 대본의 대사만으로 **견본 소리 한 개**를 만든다. 버튼 한 번, 1분이면 된다.
# ⭐⭐ 2026-08-22 — 운영자: "얘 안 돼요. 목소리네 그냥."
#    말투를 아무리 손봐도 안 되면, 남은 것은 **목소리 그 자체**다.
#    그런데 우리는 26개 중 **두 개(Kore·Orus)만** 써 봤다. 나머지 24개를
#    한 번도 안 들어 보고 "제미나이 목소리는 이렇다" 고 단정하고 있었다.
#    → 같은 대사를 **모든 목소리로** 한 번씩 만들어, 귀로 고르게 한다.
#    값: 26개 × 13자 = 340자쯤 → 15원 안팎.
AUD_F = "당신 진짜 제정신이야?!"
AUD_M = "더는 숨 막혀서 못 살아."


def aud_name(sex, voice):
    """들어볼 소리 파일 이름.

    ⚠️ 2026-08-22 — 「여_Kore.mp3」로 지었다가 릴리스에 올릴 때 죽었다.
       주소에 한글이 못 들어간다 (UnicodeEncodeError: ascii codec…).
       → **파일 이름은 영문**으로. 한글은 화면에 보여 줄 때만 쓴다.
    """
    return f"{'f' if sex == '여' else 'm'}_{voice}.mp3"


def audition(out_dir, only=""):
    """쓸 수 있는 목소리 전부로 같은 대사를 한 번씩 만든다.

    돌려주는 것: [(목소리이름, 남/여, 파일), …]
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    want = [w.strip() for w in str(only or "").split(",") if w.strip()]
    if engine() == "typecast":
        # 성별 표시가 있으면 그 칸으로, 모르면 **양쪽에 다** 보여 준다
        # (한 번만 만들고 목록에 두 줄로 얹는다 — 값이 두 배로 안 든다)
        jobs = []
        for v in tc_voices():
            if v["gender"] == "f":
                jobs.append((v["id"], "여", AUD_F, v["name"]))
            elif v["gender"] == "m":
                jobs.append((v["id"], "남", AUD_M, v["name"]))
            else:
                jobs.append((v["id"], "?", AUD_F, v["name"]))
    else:
        jobs = ([(v, "여", AUD_F, v) for v in GEM_F]
                + [(v, "남", AUD_M, v) for v in GEM_M])
    if want:
        jobs = [j for j in jobs if j[0] in want]
    made = []
    print(f"⭐ 목소리 {len(jobs)}개를 같은 대사로 만들어 본다\n")
    for i, (v, g, text, label) in enumerate(jobs, 1):
        gg = g if g in ("여", "남") else "여"
        f = out_dir / aud_name(gg, v)
        try:
            w = say(text, v, 1.0, 0.0, out_dir / f"_{v}.wav")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(w),
                            "-c:a", "libmp3lame", "-b:a", "160k", str(f)],
                           check=True)
            made.append((v, gg, f, label))
            # 성별을 모르는 목소리는 **남자 칸에도** 같은 파일로 얹는다
            if g == "?":
                made.append((v, "남", f, label))
            print(f"  [{i:2d}/{len(jobs)}] ✅ {g} {label or v}")
        except Exception as e:                               # noqa: BLE001
            print(f"  [{i:2d}/{len(jobs)}] ❌ {g} {label or v} — {str(e).splitlines()[0][:70]}")
    won = bill_flush("목소리 고르기")
    print(f"\n✅ {len(made)}개를 만들었다" + (f" · 값 {won:.0f}원" if won else ""))
    # ⭐ 어느 엔진으로 만든 견본인지 줄마다 적는다 — 화면이 다른 엔진의
    #    옛 견본을 현재 것인 양 보여 주지 않게 (2026-08-23 운영자 지적)
    (out_dir / "list.json").write_text(
        json.dumps([{"voice": v, "sex": g, "file": f.name,
                     "label": (label if label != v else ""),
                     "engine": engine()}
                    for v, g, f, label in made],
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return made


def sample(sid, no, out, gap=0.45):
    """대본에서 그 화 1컷 대사를 뽑아 견본 소리를 만든다."""
    import sys as _s
    _s.path.insert(0, str(Path(__file__).resolve().parent))
    # ⚠️ shorts 를 들여오면 안 된다 — 그림 모듈(PIL)까지 딸려 와서, 소리만
    #    만드는 자리에서 "No module named 'PIL'" 로 죽는다 (실제로 그랬다).
    import series as SC                                      # noqa: E402

    doc = json.loads((Path(__file__).resolve().parent.parent / "data" /
                      "series" / f"{sid}.json").read_text(encoding="utf-8"))
    ep = next((e for e in doc["episodes"] if int(e.get("no", 0)) == int(no)),
              None)
    if not ep:
        raise SystemExit(f"❌ {sid} 에 {no}화가 없다")
    voices = pick_voices(doc.get("characters"))
    personas = pick_personas(doc.get("characters"))
    turns = []
    for c in ep["cuts"]:
        turns += SC.dia_turns(c.get("prompt"))
        if len(turns) >= 4:
            break
    if not turns:
        raise SystemExit("❌ 대사가 없다")
    turns = turns[:4]

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.parent / "_voice"
    tmp.mkdir(exist_ok=True)
    made = []
    for i, (who, text) in enumerate(turns):
        v = voices.get(who) or best_voices("FEMALE")[0]
        pe = personas.get(who)
        p = say(text, v, 1.0, tone_of(text), tmp / f"s{i}.wav", who=pe)
        made.append(p)
        print(f"  🎙 {who} ({v}" + (f" · {pe}" if pe else "") + f") — {text}")
        if engine() == "gemini":
            # ⚠️ 실제로 보내는 지시 그대로를 적는다. 다르게 적으면
            #    화면과 실제가 어긋난다 (한 번 겪었다).
            print(f"      연기 지시: {how_of(text, pe)}")

    # 사이를 조금 띄워 이어 붙인다.
    # ⚠️ 예전에는 concat 목록 파일을 썼는데, 그건 **모든 조각의 소리 규격이
    #    똑같아야** 한다. 제미나이는 24000Hz 홑소리, 구글은 48000Hz 라 서로
    #    안 맞는다. 그래서 규격을 맞춰 주는 filter 쪽으로 바꾼다.
    args = ["ffmpeg", "-v", "error", "-y"]
    for p in made:
        args += ["-i", str(p)]
    fil, tag = [], ""
    for i in range(len(made)):
        fil.append(f"[{i}:a]aresample=48000,"
                   f"aformat=sample_fmts=s16:channel_layouts=mono,"
                   f"apad=pad_dur={gap}[a{i}]")
        tag += f"[a{i}]"
    fil.append(f"{tag}concat=n={len(made)}:v=0:a=1[out]")
    args += ["-filter_complex", ";".join(fil), "-map", "[out]",
             "-c:a", "libmp3lame", "-b:a", "160k", str(out)]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"❌ 소리를 못 이어 붙였다\n{r.stderr[:300]}")

    # 어떤 목소리로 만들었는지 옆에 적어 둔다 — 관리자 페이지가 이걸 보여 준다.
    who_v = ", ".join(f"{w}={voices.get(w) or '?'}" for w, _ in turns)
    won = bill_flush(f"{sid} {no}화 견본")
    if won:
        print(f"  💰 목소리 값 {won:.1f}원")
    (out.parent / "voice.txt").write_text(
        f"{engine_note()}\n{who_v}\n"
        + (f"이 견본에 든 값 {won:.1f}원\n" if won else ""), encoding="utf-8")
    return out


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--say", default="")
    a.add_argument("--sample", default="", help="예: S001 — 그 대본으로 견본 소리")
    a.add_argument("--ep", type=int, default=1)
    a.add_argument("--voice", default="")
    a.add_argument("--sec", type=float, default=0.0)
    a.add_argument("--out", default="tts.wav")
    a.add_argument("--audition", default="", help="목소리 전부를 들어볼 곳")
    a.add_argument("--only", default="", help="이 목소리들만 (쉼표로)")
    g = a.parse_args()
    if not key():
        print("❌ 목소리 열쇠가 없다 — GEMINI_API_KEY 나 GOOGLE_TTS_KEY 중\n"
              "   하나는 깃허브 시크릿에 있어야 한다", file=sys.stderr)
        return 2
    print(f"목소리 — {engine_note()}\n")
    if g.audition:
        audition(g.audition, g.only)
        return 0
    if g.sample:
        p = sample(g.sample, g.ep, g.out)
        print(f"\n✅ {p} — {dur_of(p):.1f}초")
        return 0
    if not g.say:
        print("❌ --say 나 --sample 중 하나는 있어야 한다", file=sys.stderr)
        return 2
    voice = g.voice or best_voices("FEMALE")[0]
    if g.sec > 0:
        p, d = say_to_fit(g.say, voice, g.sec, g.out)
    else:
        p = say(g.say, voice, 1.0, 0.0, g.out)
        d = dur_of(p)
    print(f"✅ {p} — {d:.2f}초")
    return 0


if __name__ == "__main__":
    sys.exit(main())
