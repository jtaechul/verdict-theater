#!/usr/bin/env python3
"""나레이션 음성 만들기 (Gemini 다중 화자 TTS).

    python3 src/tts.py data/scripts/EP001.json --out build/voice
    python3 src/tts.py data/scripts/EP001.json --out build/voice --limit 5

왜 목소리를 나누나 (지침서 8번)
    나레이터가 대사까지 읽으면 인물 구분이 안 된다.
    대본의 `speaker` 가 `narrator` 면 해설 목소리, `v_M50A` 면 그 인물의 목소리로 읽는다.
    재판장은 10% 느리게 읽어 무게를 준다.

왜 컷마다 따로 만드나
    렌더링이 컷 단위로 돌아가고, 컷 길이를 '읽는 시간'에 맞춰야 말이 잘리지 않는다.
    한 덩어리로 만들면 어디서 끊어야 할지 알 수 없다.

⚠️ 확정되지 않은 부분
    지침서 12번이 "TTS 서비스 미정. Gemini 다중 화자 우선 검토"라고 적고 있다.
    이 파일은 Gemini 를 쓰되, **모델 이름을 박지 않고 API에 물어서 고른다.**
    쓸 수 있는 음성 모델이 없으면 무음 파일을 만들고 크게 경고한다.
    무음이어도 파이프라인은 끝까지 돈다 — 자막이 상시 노출이라 소리 없이도 따라갈 수 있다.
"""

import argparse
import base64
import bisect
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import BASE, LLMError, _post  # noqa: E402

# 속도 제한(429)에 걸렸을 때 기다리는 시간. 점점 늘린다.
BACKOFF = [5, 15, 40, 90]
RETRYABLE = (408, 429, 500, 502, 503, 504)

# 서버가 알려준 대기 시간을 따르되, **이 이상은 절대 기다리지 않는다.**
# 구글은 '분당 한도'와 '하루 한도'를 똑같이 429 로 알린다. 하루 치를 다 쓰면
# retryDelay 에 '78576초(21시간 46분) 뒤에 오라'고 답하는데, 그 말을 그대로 따르느라
# 음성 만들기가 밤새 멈춰 서 있었다. 화면에는 아무 오류도 없어서 원인 찾기가 더 어려웠다.
# 2분을 넘는 대기 요구는 '잠깐 밀렸다'가 아니라 '오늘 몫이 끝났다'는 뜻이다 — 바로 알린다.
MAX_RETRY_WAIT = max(10, int(os.environ.get("TTS_MAX_RETRY_WAIT", "120")))

# ⭐ **모델 하나당** 분당 몇 번까지 부를지. 실측 한도는 10 이다.
#    한도에 딱 붙이면(10) 조금만 흔들려도 넘고, 넘으면 재시도가 다음 분의 몫을
#    또 먹어 영영 안 풀린다 — 실제로 그렇게 30분을 버렸다. 여유를 두고 8 로 둔다.
PER_MODEL_RPM = max(1, int(os.environ.get("TTS_PER_MODEL_RPM", "8")))
PER_MODEL_GAP = 60.0 / PER_MODEL_RPM

# 연속 실패가 이만큼 쌓이면 그만둔다.
# 컷마다 최대 150초(5+15+40+90)를 기다리므로, 113컷을 끝까지 가면 4시간이 넘어
# 작업 시간 제한(180분)에 걸려 통째로 취소된다. 그 전에 멈춰 원인을 알려주는 편이 낫다.
MAX_FAIL_STREAK = max(1, int(os.environ.get("TTS_MAX_FAIL_STREAK", "5")))

# 이 비율 미만으로 성공하면 발행 품질이 아니다. 소리 끊긴 영상이 나가는 것을 막는다.
MIN_OK_RATIO = float(os.environ.get("TTS_MIN_OK_RATIO", "0.9"))

# 모든 음성 모델이 한도로 막혔을 때, 포기하기 전에 쉬었다 다시 해보는 횟수·시간.
# 실측: 세 모델이 전부 '오늘 몫 끝' 을 준 직후에도 2~3분 뒤에는 두 개가 다시 열렸다.
# 사람이 없는 GitHub Actions 실행에서 그냥 멈추면 그 회차는 그대로 끝난다.
MAX_COOLDOWNS = max(0, int(os.environ.get("TTS_MAX_COOLDOWNS", "3")))
COOLDOWN_SEC = max(10, int(os.environ.get("TTS_COOLDOWN_SEC", "120")))


def _retry_wait(e, default):
    """서버가 알려준 대기 시간을 읽는다. 헤더와 본문을 **둘 다** 본다.

    제미나이는 429 에 Retry-After 헤더를 안 붙이는 경우가 많고, 대신 본문에
    google.rpc.RetryInfo 를 넣어 보낸다:
        {"error":{"details":[{"@type":"...RetryInfo","retryDelay":"37s"}]}}
    헤더만 보면 이 값을 놓쳐, 서버가 37초를 기다리라는데 5초 만에 다시 쏘고
    또 429 를 받는다.

    다만 지시가 MAX_RETRY_WAIT 를 넘으면 기다리지 않고 **포기한다**(0 을 돌려준다).
    하루 한도가 바닥난 상황이라 몇 시간을 기다려도 이 실행 안에서는 풀리지 않는다."""
    want = None
    hdr = (getattr(e, "headers", None) or {}).get("Retry-After")
    if hdr:
        try:
            want = int(float(hdr))
        except (TypeError, ValueError):
            want = None
    if want is None:
        try:
            # ⚠️ 응답 본문은 **한 번만** 읽을 수 있다. quota_note 도 같은 본문을 봐야
            #    하므로 여기서 읽어 e._vt_body 에 담아 둔다. 안 그러면 둘 중 하나는
            #    빈손이 되어, '어떤 한도였는지' 를 영영 알 수 없다.
            raw = getattr(e, "_vt_body", None)
            if raw is None:
                raw = e.read().decode("utf-8", "replace")
                try:
                    e._vt_body = raw
                except Exception:
                    pass
            body = json.loads(raw)
            for d in (body.get("error", {}).get("details") or []):
                rd = d.get("retryDelay")
                if isinstance(rd, str) and rd.endswith("s"):
                    want = int(float(rd[:-1])) + 1                # 1초 여유
                    break
        except Exception:
            want = None
    if want is None:
        return default
    if want > MAX_RETRY_WAIT:
        return 0                    # 기다려봐야 소용없다 — 부른 쪽에서 바로 실패시킨다
    return max(default, want)


def _post_retry(url, payload, timeout=180, label="", rotate=False):
    """429·5xx 는 기다렸다 다시 해본다.

    예전에는 재시도가 전혀 없어서, 속도 제한 한 번에 그 컷이 통째로 무음이 됐다.

    rotate — 429 일 때 **여기서 기다리지 않고 곧바로 알린다.**
        한도는 모델마다 따로 걸린다(실측). 그러니 막힌 모델을 붙들고 60초씩
        네 번 자는 것은 4분을 그냥 버리는 짓이다. 부른 쪽(ModelPool)이
        그 모델만 쉬게 두고 **다른 모델로 즉시 갈아탄다.**
        5xx·통신 오류는 모델을 바꿔도 소용없으므로 예전대로 여기서 다시 해본다."""
    for i in range(len(BACKOFF) + 1):
        try:
            return _post(url, payload, timeout=timeout)
        except urllib.error.HTTPError as e:
            if rotate and e.code == 429:
                wait = _retry_wait(e, 60)           # 본문도 여기서 e._vt_body 에 담긴다
                if wait == 0:
                    raise QuotaExhausted(
                        f"{label}: 이 모델의 오늘 몫을 다 썼습니다(HTTP {e.code}).") from e
                e._vt_wait = wait
                raise
            if e.code not in RETRYABLE or i >= len(BACKOFF):
                raise
            wait = _retry_wait(e, BACKOFF[i])
            if wait == 0:
                # 서버가 '몇 시간 뒤에 오라' 고 했다. 하루 몫이 끝났다는 뜻이다.
                raise QuotaExhausted(
                    f"{label}: 오늘 쓸 수 있는 음성 생성량을 다 썼습니다(HTTP {e.code}). "
                    f"내일 한도가 초기화되거나, 결제 등급을 올리면 풀립니다.") from e
            print(f"    ({label} 속도 제한 HTTP {e.code} — {wait}초 기다렸다 다시 한다"
                  f" {i + 1}/{len(BACKOFF)})")
            time.sleep(wait)
        except (OSError, LLMError) as e:
            if i >= len(BACKOFF):
                raise
            print(f"    ({label} 통신 오류 {type(e).__name__} — {BACKOFF[i]}초 뒤 다시)")
            time.sleep(BACKOFF[i])
    raise LLMError(f"{label} 최종 실패")      # 위에서 반드시 raise 되므로 도달하지 않는다


def need_ffmpeg():
    """ffmpeg 가 없으면 여기서 분명히 말하고 멈춘다.

    예전에는 없는 채로 진행하다가 한참 뒤 FileNotFoundError 로 죽었다.
    로그만 보면 원인을 알 수 없었다.
    ⚠️ --silent 일 때는 부르지 않는다. 무음 만들기에 ffmpeg 는 필요 없다."""
    if shutil.which("ffmpeg"):
        return
    print("오류: ffmpeg 가 설치되어 있지 않습니다.", file=sys.stderr)
    print("      음성을 만들려면 ffmpeg 가 필요합니다.", file=sys.stderr)
    print("      GitHub Actions 에서는 '도구 준비' 단계가 설치합니다 —", file=sys.stderr)
    print("      그 단계를 확인하십시오.", file=sys.stderr)
    sys.exit(1)

# 인물 코드 → **연기 지시**. 실제 음성 이름은 아래 VOICE_NAME 에서 고른다.
# 뒤 숫자는 **재생 배속**이다. 1.0 보다 크면 빠르게(음높이는 그대로).
#
# ⭐⭐ 여기가 "목소리가 로봇 같다" 의 진짜 원인이었다 (손님 지적 → 실측으로 확인)
#
#    예전 지시문은 이랬다.
#      나레이터  "차분하고 낮은 해설 목소리로, **담담하게**"
#      장남      "50대 남성. **사무적**이고 냉랭하게"
#      차남      "50대 남성. **무심하게**"
#      F50B      "50대 여성. 차갑고 **또박또박**"
#      재판장    "무겁고 절제된 목소리로 **또박또박**"
#
#    담담·사무적·무심·또박또박 — **출연진 거의 전원에게 '감정을 빼고 한 글자씩
#    읽어라' 고 시키고 있었다.** 그것이 정확히 로봇 소리다.
#    목소리 이름을 네 개나 바꿔 들려드렸지만 넷 다 이상하다고 하신 이유가 이것이다 —
#    바꾼 것은 성대뿐이었고 연기 지시는 그대로였다.
#
#    이제 **어떤 사람이 어떤 상황에서 하는 말인지**를 적는다. 감정을 빼라고 하지 않는다.
#    실측(같은 대사·같은 목소리): 예전 지시문 5.7초 → 새 지시문 6.6초.
#    길어진 0.9초가 곧 **끊고 누르는 자리**다. 그것이 사람 말투다.
#
# ⚠️ 여기에 '또박또박' '담담하게' '사무적' '무심하게' 를 다시 넣지 마라.
#    셋 다 모델에게 억양을 지우라는 말이다.
#
# ⭐ 뒤의 배속(1.12)은 **손님이 귀로 듣고 고른 값**이다.
#    같은 대사를 배속 없는 것 / 1.12배속 두 가지로 만들어 들려드렸고
#    ("speed_check"), 배속을 건 쪽이 낫다고 하셨다. 임의로 1.0 으로 되돌리지 마라.
#    길이에도 영향이 있다 — 새 말투는 예전보다 느려서, 배속까지 빼면
#    한 편이 12.0분 설계 대비 약 14분이 된다(배속을 두면 12.7분).
# ⭐ 지시문 맨 앞에 **그 사람이 누구인지(몸)** 를 못 박는다 — 손님 지적(2026-08-06).
#
#    왜: 제미나이는 컷마다 따로 부르는 별개의 호출이라, 같은 목소리 이름을 줘도
#        **매번 조금씩 다른 사람**을 만들어 낸다. 예전 지시문은 '어떻게 말하는가'
#        (조용히·느리게)만 적혀 있고 '누구인가'(나이·성별·목소리 굵기)가 없었다.
#        그래서 모델이 매번 사람을 새로 상상했다.
#        손님 말씀 그대로다 — "한 캐릭터를 명확히 정해서 그 사람이 말하게 해야 한다."
#    ⚠️ 이 글을 고치면 조리법이 바뀌어 음성을 전부 다시 만든다(의도한 것이다).
BODY = {
    "narrator": "50대 남성. 낮고 두꺼운 중저음. 목이 굵고 울림이 깊다.",
    "v_F50A":   "예순두 살 여성. 중간 높이. 목소리에 세월이 배어 조금 갈라진다.",
    "v_F50B":   "쉰다섯 살 여성. 중간 높이. 맑지만 차갑고 단단하다.",
    "v_M50A":   "쉰 살 남성. 중간 높이의 또렷한 남자 목소리. 매끄럽고 차분하다.",
    "v_M50B":   "마흔여덟 살 남성. 형보다 조금 낮고 두툼하다. 울림이 무겁다.",
    "v_F70":    "일흔셋 여성. 높고 가늘다. 숨이 섞여 떨린다.",
    "v_M70":    "일흔다섯 남성. 낮고 쉬었다. 바람이 새는 소리가 섞인다.",
    "v_JUDGE":  "50대 남성. 낮고 단단한 중저음. 울림이 크고 또렷하다.",
}

VOICE_STYLE = {
    "narrator": ("한 가족에게 실제로 있었던 일을 들려주는 해설자다. "
                 "사연을 아는 사람이 조용히 이야기하듯, 문장 끝을 눌러 말한다.", 1.12),
    "v_F50A":   ("예순이 넘은 어머니. 오래 참아온 사람의 목소리다. "
                 "힘을 빼고 느리게, 배우가 연기하듯 말한다.", 1.12),
    "v_F50B":   ("쉰 줄 여자. 마음을 닫은 사람이 남을 대하듯 말한다. "
                 "목소리를 높이지 않지만 정이 없다.", 1.12),
    "v_M50A":   ("쉰 살 맏아들. 겉으로는 예의를 갖추지만 속으로는 이미 결론을 내려놓은 "
                 "사람이다. 서늘하고 느긋하게, 배우가 연기하듯 말한다.", 1.12),
    "v_M50B":   ("마흔여덟 동생. 형에게 눌려 살아온 사람이 참다 못해 말을 꺼낸다. "
                 "낮게 말하지만 속에 억울함이 배어 있다.", 1.12),
    "v_F70":    ("일흔이 넘은 할머니. 숨이 짧아 말끝이 흐려진다. "
                 "천천히, 기운 없이 말한다.", 1.00),
    "v_M70":    ("일흔이 넘은 아버지. 병으로 기운이 없고 목이 쉬었다. "
                 "천천히, 말끝을 흐리며 말한다.", 1.00),
    "v_JUDGE":  ("법정에서 판결문을 읽어 내려가는 재판장. 낮고 단단한 목소리로 "
                 "서두르지 않고, 한 마디마다 무게를 실어 말한다.", 1.00),
}

# Gemini TTS 목소리 이름. **인물마다 서로 다른 이름이어야 한다.**
#
# ⭐ 고르는 기준을 바꿨다 — 예전에는 **높이(Hz)만** 보고 골랐다.
#    그 결과 장남에게 구글이 "Upbeat(들뜬)" 이라고 밝힌 Puck 이 배정돼 있었다.
#    냉정한 맏아들 배역에 정확히 반대되는 목소리다. 손님이 "장남 목소리가 너무
#    어색하다" 고 한 것이 이것이다.
#    이제 **① 구글이 밝힌 목소리 성격이 배역과 맞는가 → ② 높이가 나이에 맞는가**
#    순서로 고른다.
#
# ⚠️ 높이는 **모델이 바뀌면 통째로 달라진다.** 아래 값은 전부
#    `gemini-3.1-flash-tts-preview`(등장인물) 기준이며, 나레이터만 2.5 기준이다.
#    실측 — 같은 Alnilam 이 2.5 에서 86Hz, 3.1 에서 186Hz 로 100Hz 나 벌어졌다.
#    **모델을 바꾸면 이 표를 반드시 다시 재야 한다.**
#
# 실측값 (새 지시문 · 각 인물의 실제 대사로 잼)
#   Algenib 120Hz · Algieba 121Hz · Schedar 129Hz · Enceladus 131Hz
#   Umbriel 134Hz · Rasalgethi 147Hz · Iapetus 151Hz · Orus 167Hz
#   Sulafat 198Hz · Vindemiatrix 198Hz · Erinome 200Hz · Gacrux 186Hz
#   Charon 82Hz (2.5 기준 — 나레이터)
# ⭐ 아래 다섯(해설·장남·차남·어머니·재판장)은 **손님이 실제로 듣고 확정한 값**이다
#    (cast_5_voices 샘플). 임의로 바꾸지 마라. 나머지 셋(F50B·F70·M70)은
#    EP001 에 대사가 없어 아직 귀로 확인하지 못했다 — 처음 쓰는 회차에서 들어보고 정한다.
VOICE_NAME = {
    "narrator": "Charon",       # Informative(설명하는) 82Hz  — 낮고 차분한 해설
    "v_F50A":   "Sulafat",      # Warm(따뜻한)      198Hz — 오래 참아온 어머니
    "v_F50B":   "Erinome",      # Clear(맑은)       200Hz — 정 없이 또렷한 여자
    "v_M50A":   "Algenib",      # Gravelly(걸걸한)  120Hz — 서늘한 맏아들
    "v_M50B":   "Schedar",      # Even(평탄한)      129Hz — 눌려 살아온 동생
    "v_F70":    "Vindemiatrix", # Gentle(부드러운)  198Hz — 기운 없는 할머니
    "v_M70":    "Enceladus",    # Breathy(숨섞인)   131Hz — 병든 노인의 쉰 목소리
    "v_JUDGE":  "Algieba",      # Smooth(매끄러운)  121Hz — 낮고 단단한 재판장
}


# 연기 지시에 들어가면 안 되는 말. 전부 '억양을 지워라' 는 뜻이다.
# 이것들이 들어 있으면 출연진이 통째로 로봇처럼 읽는다 — 손님이 실제로 겪은 일이다.
FLAT_WORDS = ("또박또박", "담담", "사무적", "무심하게", "감정 없이", "기계적")


def check_style():
    """연기 지시에 '감정 빼기' 말이 다시 섞이지 않았는지 본다.

    왜 코드로 막나 — 이 낱말들은 사람이 읽으면 '차분하게' 로만 보인다. 그런데
    모델에게는 **억양을 지우라는 명령**이다. 한 번 되돌아오면 영상을 다 만들고
    귀로 들어야만 알 수 있고, 그때는 음성 값이 이미 나간 뒤다."""
    bad = [f"{sp} '{w}'" for sp, (style, _s) in VOICE_STYLE.items()
           for w in FLAT_WORDS if w in style]
    dup = len(set(VOICE_NAME.values())) != len(VOICE_NAME)
    if bad:
        raise LLMError(
            "연기 지시에 억양을 지우는 말이 들어 있습니다: " + " / ".join(bad)
            + "\n  이 말들은 모델에게 '감정을 빼고 한 글자씩 읽어라' 는 뜻입니다."
            " 어떤 사람이 어떤 상황에서 하는 말인지로 바꾸십시오.")
    if dup:
        raise LLMError("두 인물이 같은 목소리 이름을 씁니다 — 소리로 구분되지 않습니다.")


# ── ⭐ 이번 실행에 든 값 ────────────────────────────────
#
# 손님 지적: "제미나이 토큰이 2만원이 넘는다. TTS 에 이렇게 많이 쓰는 게 이해가 안 된다."
#
# 그때까지 **아무도 실제 값을 몰랐다.** 짐작으로만 이야기하고 있었다.
# API 응답에 `usageMetadata` 로 정확한 토큰 수가 오는데 그냥 버리고 있었다.
# 이제 실행이 끝날 때마다 몇 회·몇 토큰·대략 얼마인지 찍는다.
#
# 실측 (대사 34자 한 컷)
#     입력  88 토큰(글자)  ·  출력  269 토큰(소리)   → 소리 1초당 약 41 토큰
# 한 편(144컷·4,181자) 기준 약 45,000 토큰 ≈ **500원**.
# 즉 TTS 는 한 편에 500원짜리다 — 2만원의 원인이 아니다(그림 쪽이다).
TTS_USD_IN = float(os.environ.get("TTS_USD_IN", "0.50"))     # 입력 100만 토큰당 달러
TTS_USD_OUT = float(os.environ.get("TTS_USD_OUT", "10.0"))   # 오디오 100만 토큰당 달러
USD_KRW = float(os.environ.get("USD_KRW", "1470"))


class Spend:
    """이번 실행에서 쓴 토큰을 센다. 값이 눈에 보여야 줄일 수 있다."""

    def __init__(self):
        self.calls = self.tin = self.tout = 0

    def add(self, usage):
        if not usage:
            return
        self.calls += 1
        self.tin += int(usage.get("promptTokenCount") or 0)
        for d in (usage.get("candidatesTokensDetails") or []):
            if d.get("modality") == "AUDIO":
                self.tout += int(d.get("tokenCount") or 0)

    def won(self):
        return (self.tin / 1e6 * TTS_USD_IN + self.tout / 1e6 * TTS_USD_OUT) * USD_KRW

    def line(self):
        if not self.calls:
            return "이번 실행에서 새로 만든 음성 없음 — 값 0원 (전부 재사용)"
        return (f"이번 실행 음성 {self.calls}회 · 글자 {self.tin:,}토큰 + "
                f"소리 {self.tout:,}토큰 → 약 {self.won():,.0f}원")


SPEND = Spend()


def quota_note(e):
    """429 본문에서 **어떤 한도**에 걸렸는지 읽어 사람이 읽는 한 줄로.

    ⚠️ 이걸 안 읽어서 지금까지 원인을 계속 추측했다 — '분당인가 하루인가',
       '무료 등급인가 유료인가' 를 로그만 보고는 알 수가 없었다.
       구글은 본문에 QuotaFailure 로 정확히 적어 보낸다:
         {"error":{"details":[{"@type":"...QuotaFailure","violations":[
            {"quotaId":"GenerateRequestsPerDayPerProjectPerModel-FreeTier", ...}]}]}}
       'PerDay' 면 오늘은 안 풀리고, 'FreeTier' 면 결제가 안 걸린 열쇠라는 뜻이다."""
    raw = getattr(e, "_vt_body", "") or ""
    if not raw:
        return ""
    try:
        body = json.loads(raw)
    except Exception:
        return raw[:160].replace("\n", " ")
    ids = []
    for d in (body.get("error", {}).get("details") or []):
        for v in (d.get("violations") or []):
            q = v.get("quotaId") or v.get("quotaMetric") or ""
            if q:
                ids.append(q)
    if not ids:
        return (body.get("error", {}).get("message", "") or "")[:160]
    flat = " ".join(ids).lower().replace("_", "").replace("-", "")
    note = " · ".join(ids[:3])
    if "freetier" in flat:
        note += "   ← 무료 등급입니다 (결제가 걸린 열쇠가 아닙니다)"
    if "perday" in flat:
        note += "   ← 하루 한도라 오늘은 안 풀립니다"
    elif "perminute" in flat:
        note += "   ← 분당 한도라 천천히 하면 풀립니다"
    return note


class ModelPool:
    """음성 모델을 **돌려쓴다.** 한도가 모델별로 따로 걸리기 때문이다.

    ⭐ 실측으로 확인한 것 (서버가 429 본문에 그대로 적어 보낸다)
           quotaId  : GenerateRequestsPerMinutePerProjectPerModel
           quotaValue: 10          ← 모델 하나당 **분당 10회**
           model    : gemini-3.1-flash-tts
       그리고 A 모델이 막힌 그 순간 B 모델은 5/5 성공했다 — **따로 센다.**

    ⚠️ 그래서 예전 설정이 위험했다. 워크플로가 TTS_RPM=10 으로 **한도에 딱 붙여**
       한 모델만 두들겼다. 여유가 0 이라 조금만 흔들려도 넘고, 넘으면 재시도가
       다음 분의 몫을 또 먹어 **영영 안 풀린다.**
       실측: 16컷 성공 뒤 30분 내내 429, 114컷 중 22컷에서 중단.

    이제 이렇게 한다
        · 모델마다 분당 PER_MODEL_RPM(기본 8, 한도 10보다 낮게) 로 **따로** 센다
        · 한 모델이 429 면 그 모델만 잠시 쉬게 두고 **다른 모델로 즉시 넘어간다**
        · 값싼 flash 를 먼저 다 쓰고, 비싼 pro 는 예비로만 둔다(acquire 참고)
        · 전부 쉬는 중이면 가장 빨리 풀리는 모델까지만 기다린다
      실측(EP001 앞 30컷): flash 15·14컷 / pro 0컷 / 실패 0 / 2분 11초.
      114컷 기준 약 9분이면 끝난다."""

    def __init__(self, models):
        self.models = list(models)
        self.next_ok = {m: 0.0 for m in self.models}      # 이 시각 뒤에 쓸 수 있다
        # 값싼 무리(flash)와 비싼 무리(pro)를 가른다. 숫자가 작을수록 싸다.
        self.tier = {m: (0 if "flash" in m.lower() else 1) for m in self.models}

    def acquire(self):
        """지금 쓸 수 있는 모델. 없으면 풀릴 때까지 기다렸다 돌려준다.

        ⭐ **싼 것을 끝까지 먼저 쓴다.**
           그냥 '가장 한가한 모델' 을 고르면 비싼 pro 가 3분의 1을 가져간다 —
           실측으로 40컷이 13·13·13 으로 갈렸다. pro TTS 는 flash 보다 몇 배 비싸다.
           그래서 순서를 이렇게 둔다.
             ① 지금 바로 쓸 수 있는 flash 가 있으면 그것
             ② 없어도 flash 가 **평소 간격(7.5초) 안에** 풀릴 것 같으면 기다린다
                — 잠깐 기다리는 편이 pro 값을 무는 것보다 싸다
             ③ 그래도 안 되면(=flash 가 429 로 길게 묶였다) 그때 pro 가 나선다
           결과: 평소에는 pro 를 한 컷도 안 쓰고, 진짜 막혔을 때만 예비로 쓴다."""
        now = time.monotonic()
        pick = wait = None
        for tier in sorted(set(self.tier[m] for m in self.models)):
            group = [m for m in self.models if self.tier[m] == tier]
            ready = [m for m in group if self.next_ok[m] <= now]
            if ready:
                pick, wait = ready[0], 0.0
                break
            soon = min(group, key=lambda x: self.next_ok[x])
            w = self.next_ok[soon] - now
            if w <= PER_MODEL_GAP + 0.5:     # 평소 간격일 뿐이다 → 기다린다
                pick, wait = soon, w
                break
        if pick is None:                     # 전부 길게 묶였다 → 가장 빨리 풀리는 것
            pick = min(self.models, key=lambda x: self.next_ok[x])
            wait = self.next_ok[pick] - now
        if wait > 0:
            time.sleep(min(wait, MAX_RETRY_WAIT))
        self.next_ok[pick] = time.monotonic() + PER_MODEL_GAP
        return pick

    def penalize(self, model, seconds):
        """이 모델은 이만큼 쉬게 둔다 (서버가 알려준 시간)."""
        self.next_ok[model] = max(self.next_ok.get(model, 0.0),
                                  time.monotonic() + max(1.0, seconds))

    def alive(self):
        return bool(self.models)

    def wait_for(self, model):
        """**이 모델이** 쓸 수 있을 때까지 기다린다. 다른 모델로 바꾸지 않는다.

        ⭐ 인물마다 모델이 고정돼 있기 때문이다(pin_models 참고).
           한도에 걸렸다고 다른 모델로 갈아타면 그 인물 목소리가 도중에 바뀐다 —
           실측으로 같은 목소리 이름이 모델에 따라 113Hz ~ 157Hz 로 나온다.
           사람 귀에는 '다른 사람', 심하면 '남자가 여자로' 들린다.
           목소리가 바뀌는 것보다 몇 초 기다리는 편이 낫다."""
        if model not in self.next_ok:
            return None                     # 이미 빠진 모델이다
        wait = self.next_ok[model] - time.monotonic()
        if wait > 0:
            time.sleep(min(wait, MAX_RETRY_WAIT))
        self.next_ok[model] = time.monotonic() + PER_MODEL_GAP
        return model

    def drop(self, model):
        """오늘 몫이 끝난 모델은 아예 뺀다."""
        if model in self.models:
            self.models.remove(model)
            self.next_ok.pop(model, None)


class QuotaExhausted(LLMError):
    """오늘 쓸 수 있는 몫을 다 썼다. 기다려도 이 실행 안에서는 풀리지 않는다."""


# ─────────────────────────────────────────────────────────────────────
# 목소리를 인물별로 **고정**하는 장치
#
# 손님 지적: "장남 목소리가 중간에 여자로 바뀌고 계속 달라진다."
# 실측으로 확인한 원인 세 가지 — 전부 여기서 막는다.
#
#   ① 모델이 달라지면 같은 목소리 이름도 다른 사람이 된다
#      같은 대사·같은 이름(Puck)인데
#        gemini-3.1-flash-tts-preview  157Hz   ← 여자로 들릴 높이
#        gemini-2.5-flash-preview-tts  122Hz
#        gemini-2.5-pro-preview-tts    113Hz
#      → 인물마다 모델을 하나로 못 박는다(pin_models). 한도에 걸려도 갈아타지 않는다.
#
#   ② 지난 실행에서 만든 음성이 섞인다
#      워크플로가 build/voice 를 캐시로 되살리는데, 예전에는 다른 모델로 만든
#      파일이 그대로 남아 새 파일과 한 영상 안에 섞였다. 44Hz 가 튄다.
#      → 컷마다 '어떤 조리법(모델·목소리·배속)으로 만들었는지' 를 적어 두고,
#        조리법이 다르면 지우고 다시 만든다(prune_stale).
#
#   ③ 같은 모델 안에서도 대사 감정에 따라 흔들린다 (실측 108~132Hz, 폭 24Hz)
#      지시문으로 "음높이를 바꾸지 말라"고 해도 안 잡혔다(폭 23Hz, 차이 없음).
#      → 다 만든 뒤 인물별 중앙값으로 끌어당긴다(normalize_pitch).
# ─────────────────────────────────────────────────────────────────────

def recipe(speaker, model, text="", way=None):
    """이 컷을 '무엇으로 만들었는지' 한 줄. 하나라도 다르면 다시 만들어야 한다.

    ⚠️ **대사 자체가 들어가야 한다.**
       예전에는 모델·목소리·배속만 적었다. 그래서 대본의 대사를 고쳐도 조리법이
       같아 보였고, 캐시에 있던 **옛 대사 음성이 그대로 재사용**됐다.
       화면 자막은 새 대사인데 소리는 옛 대사 — 눈과 귀가 어긋난다.
       (워크플로가 build/voice 를 캐시로 되살리므로 실제로 일어날 수 있다.)

    ⚠️ **연기 지시(VOICE_STYLE)도 들어가야 한다.**
       지시문 한 줄이 말투를 통째로 바꾼다(실측: 같은 대사가 5.7초 → 6.6초).
       그런데 예전에는 모델·목소리·배속·대사만 적어서, **지시문만 고치면
       조리법이 그대로**였고 캐시에 있던 옛 말투가 그대로 재사용됐다.
       '로봇 같다' 를 고쳐 놓고도 옛 소리가 나가는 일이 생긴다."""
    voice = VOICE_NAME.get(speaker, "Charon")
    speed = VOICE_STYLE.get(speaker, VOICE_STYLE["narrator"])[1]
    style = persona(speaker)          # ⭐ '누구인지' 까지 포함된 글로 해시한다
    h = hashlib.sha1(((text or "").strip() + "\x00" + style)
                     .encode("utf-8")).hexdigest()[:10]
    # ⚠️ **만드는 방식**도 조리법에 들어간다.
    #    2026-08-06 에 '컷마다 따로 부르기' → '묶어서 한 번에 읽히기' 로 바꿨다.
    #    이 표시가 없으면, 방식을 바꿔도 조리법이 같아 보여서 **옛 방식으로 만든
    #    음성이 그대로 재사용된다** — 바꾼 보람이 하나도 없다.
    #    (같은 이유로 대사·지시문도 여기 들어간다. 위 설명 참고)
    # g4 (2026-08-07): 자르는 지점 계산을 고쳤다(긴 쉼 기준). g3 시절 음성은
    # **뒷문장이 옆 컷으로 넘어간 채** 보관돼 있어서, 표시를 올려 전부 새로 만든다.
    # 지시문·목소리는 그대로다 — 소리 톤은 안 바뀌고 잘리는 자리만 바로잡힌다.
    #
    # g5 (2026-08-08): '긴 쉼' 방식도 A1-18("바쁘잖니. 네가…")에서 빗나갔다 —
    # 배우가 줄 안에서 줄 사이보다 길게 쉬었다. 쉼·글자 함께 보기(_pick_best)로
    # 고치고 표시를 올린다. ⭐ 이번에는 '한 통 원본'이 보관돼 있으므로
    # **새로 부르지 않고 다시 자르기만 한다 — 0원** (지난번 650원과 다른 점).
    #
    # ⭐ way 인자(2026-08-08): 컷마다 따로 만든 음성은 **자르기와 무관하다** —
    #    한 통을 자른 적이 없기 때문이다. 그래서 따로 만든 컷은 way="s1" 로 적는다.
    #    다음에 자르기를 또 고쳐 g4→g5 로 올려도 s1 컷은 지워지지 않는다.
    #    (묶어 만든 컷은 잘린 자리가 파일에 박혀 있으므로 g표시를 그대로 따른다)
    if way is None:
        way = "g5" if GROUP_ON else "s1"
    return f"{model}|{voice}|{speed:.2f}|{h}|{way}"


# 등장인물(대사)에 쓸 모델의 **선호 순서**. 목록 순서가 아니라 이 순서를 따른다.
# 맨 앞이 등장인물 몫이고, 맨 뒤가 나레이터 몫이다(pin_models 참고).
#
# ⭐ 3.1 을 앞으로 옮겼다 — 등장인물에게 새 모델을 준다.
#    예전에는 2.5 가 앞이었다. 3.1 을 뺀 이유가 "같은 목소리(Puck)가 157Hz 로
#    너무 높다" 였는데, 그것은 **높이 하나만 보고 내린 결정**이었다. 표현력은
#    재보지도 않았다. 실측해 보니 3.1 이 억양과 쉼을 훨씬 잘 만든다
#    (같은 대사 5.7초 → 6.4초 — 늘어난 만큼이 끊고 누르는 자리다).
#    높이 문제는 **그 모델에 맞는 목소리를 고르면** 풀린다(VOICE_NAME 참고).
#
# ⚠️ 왜 둘로 나누나 — 하루 한도가 **모델마다 따로** 100회다. 한 편이 약 144회이므로
#    전원을 한 모델에 몰면 한도에 걸린다. 나레이터 64컷 + 등장인물 50컷으로
#    갈라야 둘 다 100회 아래로 들어간다.
#    연기가 필요한 쪽(등장인물)이 좋은 모델을 갖고, 해설은 2.5 로도 충분하다.
CHAR_MODEL_ORDER = ["gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts"]

# ⭐⭐ 해설(나레이터) 목소리 모델 — **이름으로 못 박는다. 자리로 고르지 않는다.**
#
#    ❗ 여기가 "해설 목소리가 자꾸 바뀐다" 의 원인이었다.
#       예전 코드는 `pin["narrator"] = order[-1]` — 즉 **"목록의 맨 뒤 모델"** 이었다.
#       그런데 그 목록은 실행할 때마다 구글 API 에 물어서 받아온다(tts_models).
#       걸러내는 조건이 '이름에 tts 가 들어가면 전부' 라서, 구글이 새 preview 모델을
#       하나 내놓거나 하나 내리기만 해도 **맨 뒤가 바뀌고 = 해설 모델이 바뀌었다.**
#       목소리 이름은 'Charon' 으로 똑같은데 모델이 다르면 음높이·말맛이 달라진다
#       (실측: 같은 이름이 모델에 따라 86Hz ↔ 186Hz). 그래서 딴 사람으로 들렸다.
#
#    ❗ 값도 여기서 샜다. 조리법(recipe)에 모델 이름이 들어가므로 해설 모델이 바뀌면
#       prune_stale 이 **쌓아 둔 해설 음성 64컷을 통째로 지우고 다시 만든다.**
#       회차를 다시 돌릴 때마다 64회분을 새로 물어낸 셈이다.
#
#    이제 이름을 못 박는다. 목록이 어떻게 바뀌든 해설은 이 모델만 쓴다.
#    2.5 인 이유는 위 주석대로 — 연기가 필요한 등장인물이 좋은 쪽(3.1)을 갖고,
#    해설은 2.5 로 충분하다. 하루 한도도 모델별로 갈려 둘 다 100회 아래로 들어간다.
NARRATOR_MODEL = "gemini-2.5-flash-preview-tts"


class NarratorModelMissing(LLMError):
    """해설 목소리 모델을 오늘 쓸 수 없다. **다른 모델로 대신 만들지 않는다.**

    대신 만들면 그 회차만 해설이 딴 사람이 되고, 다음 회차에 원래 모델이 돌아오면
    또 원래대로 바뀐다. 손님이 겪은 '해설 목소리가 자꾸 바뀐다' 가 이 왕복이다."""


def _pref(models):
    """CHAR_MODEL_ORDER 에 적힌 순서대로. 목록에 없는 모델은 뒤에 붙인다."""
    known = [m for m in CHAR_MODEL_ORDER if m in models]
    return known + [m for m in models if m not in known]


def pin_models(speakers, models):
    """인물 → 쓸 모델. **한 인물은 끝까지 한 모델만 쓴다.**

    나레이터가 전체의 절반을 넘는다(113컷 중 62컷). 그래서 나레이터에게
    모델 하나를 통째로 주고, 등장인물들이 남은 모델을 나눠 쓴다.
    이렇게 해야 한 모델에 몰리지 않아 분당 한도에도 걸리지 않는다.
      실측 배분 — 나레이터 62컷 ÷ 8분 = 분당 7.5회, 인물 51컷 = 분당 6.1회.
      둘 다 모델당 한도(분당 10, 우리 설정 8) 아래다.

    등장인물이 **좋은 쪽**을 가져간다. 나레이터는 해설이라 음높이가 조금 높아도
    어색하지 않지만, 등장인물은 나이·성별이 정해져 있어 어긋나면 바로 들킨다.

    ⭐ **누구에게도 '모르는 모델' 을 못 박지 않는다.**
       구글이 API 목록에 새 preview 모델을 끼워 넣으면 예전 코드는 그것을 그대로
       배정했다. 회차마다 목소리가 갈아치워진 이유다. 이제 못 박는 후보는
       우리가 이름을 아는 모델(CHAR_MODEL_ORDER)뿐이다 — 모르는 모델은 풀 안에
       남아 **비상시 대타로만** 쓰인다."""
    if not models:
        return {}
    order = _pref(models)
    # 아는 모델만 못 박기 후보로 쓴다. 하나도 없으면 어쩔 수 없이 있는 대로.
    known = [m for m in order if m in CHAR_MODEL_ORDER] or order
    pin = {}
    rest = sorted(s for s in speakers if s != "narrator")

    if "narrator" in speakers:
        # ⭐ 자리(order[-1])가 아니라 **이름**으로 고른다. 목록이 흔들려도 안 바뀐다.
        #
        # ⭐ 없으면 **대타를 세우지 않고 멈춘다.** 이것이 이 함수의 핵심 약속이다.
        #    대타를 세우면 그 회차만 해설이 딴 사람이 되고, 다음에 원래 모델이
        #    돌아오면 또 원래 목소리로 바뀐다 — 손님이 겪은 "자꾸 바뀐다" 가 바로
        #    이 왕복이다. 게다가 바뀔 때마다 해설 64컷을 다시 만들어 값까지 나간다.
        #    잠깐 못 만드는 편이, 딴 목소리로 만들어 놓고 다시 만드는 것보다 싸고 낫다.
        if NARRATOR_MODEL not in known:
            raise NarratorModelMissing(
                f"해설 목소리 모델({NARRATOR_MODEL})을 오늘은 쓸 수 없습니다.\n"
                f"      오늘 쓸 수 있는 모델: {', '.join(known) or '없음'}\n"
                "      다른 모델로 대신 만들면 해설 목소리가 딴 사람이 되므로 만들지 않았습니다.\n"
                "      보통 몇 시간 뒤면 돌아옵니다 — '3. 영상 만들기' 를 나중에 다시 눌러주십시오.\n"
                "      (이미 만들어 둔 음성은 그대로 있어, 다시 눌러도 값이 더 들지 않습니다.)")
        pin["narrator"] = NARRATOR_MODEL

    # 등장인물은 해설이 쓰는 모델을 빼고 나눠 쓴다 (하루 한도가 모델별이라 갈라야 한다).
    others = [m for m in known if m != pin.get("narrator")] or known
    for i, s in enumerate(rest):
        pin[s] = others[i % len(others)]
    return pin


def prune_stale(out, cuts, pin):
    """조리법이 달라진 컷은 지운다. **다른 실행에서 만든 음성이 섞이는 것을 막는다.**

    지우면 아래 본 순환이 그 컷만 새로 만든다. 나머지는 그대로 재사용하므로
    돈이 더 들지 않는다 — 바뀐 것만 다시 만든다."""
    book = out / "recipe.json"
    old = {}
    try:
        old = json.loads(book.read_text(encoding="utf-8"))
    except Exception:
        old = {}
    # ⭐ 높이 기록(pitch.json)도 같이 지운다.
    #    이제 pitch.json 은 '다시 읽혀 봤지만 안 돼서 포기한 컷' 만 담는다.
    #    소리를 새로 만들면 그 포기 기록은 옛 소리에 대한 판정이라 뜻이 없다 —
    #    새 소리는 한 번 더 시도해 볼 자격이 있으므로 같이 지운다.
    #    (2026-08-06 이전에는 '괜찮음' 기록이었고, 그것 때문에 H05 가 영원히
    #     검사에서 빠졌다. 지금은 판단에 아예 안 쓴다 — normalize_pitch 설명 참조.)
    pbook = out / "pitch.json"
    try:
        pdone = json.loads(pbook.read_text(encoding="utf-8"))
    except Exception:
        pdone = {}
    tbook = out / "timbre.json"
    try:
        tdone = json.loads(tbook.read_text(encoding="utf-8"))
    except Exception:
        tdone = {}

    killed = 0
    for c in cuts:
        cid = c.get("id")
        p = out / f"{cid}.mp3"
        if not p.exists():
            continue
        speaker = c.get("speaker", "narrator")
        # 두 가지 적힘새를 다 인정한다 — 묶어 만든 컷(g표시)과 따로 만든 컷(s1).
        # 따로 만든 컷은 자르기와 무관하므로, 자르기 표시가 g4→g5 로 올라가도
        # 지우지 않는다(지우면 멀쩡한 음성을 돈 주고 또 만든다).
        model_ = pin.get(speaker, "")
        text_ = c.get("text") or ""
        if old.get(cid) not in (recipe(speaker, model_, text_),
                                recipe(speaker, model_, text_, way="s1")):
            p.unlink()
            p.with_suffix(".silent").unlink(missing_ok=True)
            old.pop(cid, None)
            pdone.pop(cid, None)
            tdone.pop(cid, None)
            killed += 1
    if killed:
        print(f"  지난 실행의 음성 {killed}컷이 지금 설정과 달라 지웠다 — 그 컷만 다시 만든다")
        book.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
        if pbook.exists():
            pbook.write_text(json.dumps(pdone, ensure_ascii=False), encoding="utf-8")
        if tbook.exists():
            tbook.write_text(json.dumps(tdone, ensure_ascii=False), encoding="utf-8")
    return old


def pick_tts_model(key):
    """쓸 수 있는 음성 모델 하나. (호환용 — 목록이 필요하면 tts_models 를 쓴다)"""
    ms = tts_models(key)
    return ms[0] if ms else None


def tts_models(key):
    """음성을 낼 수 있는 모델을 **싼 것부터 순서대로** 돌려준다.

    한 개가 아니라 목록인 이유: 하루 한도는 모델마다 따로 센다.
    쓰던 모델이 바닥나면 다음 모델로 갈아타 그 회차를 끝낼 수 있다.

    ⚠️ 이것이 이번 실행의 **첫 API 호출**이라 속도 제한을 가장 먼저 맞는 자리다.
       재시도 없이 한 번에 포기하면 회차 전체가 무음이 된다."""
    override = os.environ.get("GEMINI_TTS_MODEL")
    if override:
        return [override.strip()]
    url = f"{BASE}/models?key={key}&pageSize=200"
    data = None
    for i in range(len(BACKOFF) + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "verdict-theater/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            if e.code not in RETRYABLE or i >= len(BACKOFF):
                raise
            w = _retry_wait(e, BACKOFF[i])
            if w == 0:
                raise LLMError(
                    f"모델 목록: 오늘 몫을 다 썼습니다(HTTP {e.code})") from e
            print(f"    (모델 목록 HTTP {e.code} — {w}초 기다렸다 다시 한다)")
            time.sleep(w)
        except OSError as e:
            if i >= len(BACKOFF):
                raise
            print(f"    (모델 목록 통신 오류 {type(e).__name__} — {BACKOFF[i]}초 뒤 다시)")
            time.sleep(BACKOFF[i])
    names = [m["name"].split("/", 1)[-1] for m in (data or {}).get("models", [])]
    cands = [n for n in names if "tts" in n.lower()]
    cands.sort(key=_tts_rank)
    return cands


def _tts_rank(name):
    """음성 모델 우선순위. **싼 것부터 고른다.**

    예전에는 이름 길이로 정렬해서 `gemini-2.5-pro-preview-tts` 가 뽑혔다.
    pro 는 flash 보다 몇 배 비싸고 하루 한도도 훨씬 빡빡하다. 113컷을 만들다
    한도가 바닥나 실행이 통째로 멈췄다. 나레이션은 한 컷이 한두 문장뿐이라
    flash 로 충분하다 — 값이 몇 배 싸고 한도도 넉넉하다."""
    low = name.lower()
    ver = 0.0
    for tok in low.replace("-", " ").split():
        try:
            ver = max(ver, float(tok))          # 'gemini-3.1-flash-tts' → 3.1
        except ValueError:
            pass
    return (0 if "flash" in low else 1,         # flash 우선
            -ver,                                # 같은 등급이면 최신 판
            len(name))


def pcm_to_wav(pcm, path, rate=24000, channels=1, width=2):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(pcm)


def rate_from_mime(mime):
    """audio/L16;codec=pcm;rate=24000 형태에서 표본율을 뽑는다."""
    for part in (mime or "").split(";"):
        part = part.strip()
        if part.startswith("rate="):
            try:
                return int(part.split("=", 1)[1])
            except ValueError:
                pass
    return 24000


def persona(speaker):
    """그 인물이 **누구인지 + 어떻게 말하는지**. 한 곳에서만 만든다.

    한 곳에서 만들어야 하는 이유: 컷마다 만들 때와 묶어서 만들 때 이 글이 다르면
    같은 인물인데 두 방식의 목소리가 달라진다 — 이어 붙이면 바로 티가 난다."""
    style, _ = VOICE_STYLE.get(speaker, VOICE_STYLE["narrator"])
    body = BODY.get(speaker, "")
    head = f"너는 처음부터 끝까지 **같은 한 사람**이다. {body}" if body else ""
    return f"{head}\n{style}".strip()


def synth_one(key, model, text, speaker, out_mp3, rotate=False):
    style, speed = persona(speaker), VOICE_STYLE.get(
        speaker, VOICE_STYLE["narrator"])[1]
    voice = VOICE_NAME.get(speaker, "Charon")
    # ⭐ '읽어라' 가 아니라 '말해라' 다.
    #    '읽어라' 는 글을 낭독하라는 뜻이라 모델이 또박또박 읽어 버린다.
    #    실측으로 이 한 낱말까지 바꿨을 때 억양이 살아났다.
    prompt = (f"{style}\n"
              f"다른 말을 덧붙이지 말고, 아래 대사만 그대로 말해라:\n{text}")

    res = _post_retry(f"{BASE}/models/{model}:generateContent?key={key}", {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
            },
        },
    }, timeout=180, label=speaker, rotate=rotate)

    SPEND.add(res.get("usageMetadata"))

    parts = (res.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    blob = next((p["inlineData"] for p in parts if "inlineData" in p), None)
    if not blob:
        raise LLMError("음성 데이터가 오지 않았다")

    pcm = base64.b64decode(blob["data"])
    rate = rate_from_mime(blob.get("mimeType"))
    tmp = out_mp3.with_suffix(".wav")
    pcm_to_wav(pcm, tmp, rate=rate)
    out_mp3.with_suffix(".silent").unlink(missing_ok=True)   # 진짜 음성이 생겼다

    if not shutil.which("ffmpeg"):
        # 속도 조절과 mp3 인코딩을 건너뛰고 WAV 를 그대로 쓴다.
        # 소리가 나는 것이 재생 속도보다 중요하다.
        tmp.replace(out_mp3)
        return out_mp3

    af = f"atempo={speed:.3f}" if abs(speed - 1.0) > 0.01 else "anull"
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp),
                        "-af", af, "-b:a", "160k", str(out_mp3)], check=True)
    finally:
        tmp.unlink(missing_ok=True)     # 실패해도 24kHz PCM 찌꺼기를 남기지 않는다
    return out_mp3



def _daily_dead(err):
    """이 오류가 '하루 몫 소진' 인가. 분당 한도와 구분해야 한다."""
    src = err.__cause__ if getattr(err, "__cause__", None) is not None else err
    raw = getattr(src, "_vt_body", "") or ""
    return isinstance(err, QuotaExhausted) or "PerDay" in raw


def _all_models_dead(key, pool):
    """남은 모델을 한 번씩 두드려 본다.

    전부 하루 몫이 끝났으면 **가장 빨리 풀리는 시간(초)** 을, 하나라도 살아 있으면
    None 을 돌려준다. 거절된 요청은 한도를 깎지 않으므로 두드려 봐도 손해가 없다."""
    soonest = None
    for m in list(pool.models):
        url = f"{BASE}/models/{m}:generateContent?key={key}"
        payload = {"contents": [{"role": "user", "parts": [{"text": "네."}]}],
                   "generationConfig": {"responseModalities": ["AUDIO"],
                                        "speechConfig": {"voiceConfig": {
                                            "prebuiltVoiceConfig": {"voiceName": "Charon"}}}}}
        try:
            _post(url, payload, timeout=60)
            return None                      # 하나라도 살아 있다 → 계속 진행
        except urllib.error.HTTPError as e:
            raw = ""
            try:
                raw = e.read().decode("utf-8", "replace")
                e._vt_body = raw
            except Exception:
                pass
            if e.code != 429 or "PerDay" not in raw:
                return None                  # 하루 한도가 아니다 → 계속 진행
            for d in (json.loads(raw).get("error", {}).get("details") or []):
                rd = d.get("retryDelay")
                if isinstance(rd, str) and rd.endswith("s"):
                    v = float(rd[:-1])
                    soonest = v if soonest is None else min(soonest, v)
        except Exception:
            return None                      # 통신 문제일 수 있다 → 섣불리 멈추지 않는다
    return soonest


def make_one(pool, key, text, speaker, path, tries=0, pinned=None):
    """한 컷을 만든다. 성공하면 (None, 쓴 모델), 실패하면 (마지막 오류, None).

    pinned — 이 인물에게 못 박힌 모델. 주어지면 **그 모델만 쓴다.**
        429 가 나도 다른 모델로 갈아타지 않고 풀릴 때까지 기다린다.
        갈아타면 그 인물 목소리가 도중에 바뀌기 때문이다(실측 113~157Hz).
        그 모델의 **하루 몫이 끝났을 때만** 어쩔 수 없이 다른 모델로 넘어가고,
        부른 쪽이 그것을 보고 그 인물 컷을 전부 다시 만든다.

    pinned 가 없으면(쇼츠 등) 남은 모델을 돌아가며 두드린다 —
    한 컷이 무음이 되면 그 자리에서 소리가 끊기기 때문이다."""
    tries = tries or max(2, len(pool.models) + 1)
    last = None
    dead = QuotaExhausted("쓸 수 있는 음성 모델이 남지 않았습니다.")
    for _ in range(tries):
        if not pool.alive():
            # ⚠️ 쓸 모델이 하나도 없다. 여기서 그냥 빠져나가면 last 가 None 이라
            #    **부른 쪽이 '성공' 으로 읽는다.** 실제로 그렇게 돼서, 소리 파일이
            #    만들어지지도 않은 컷 3개가 성공으로 세어졌다(로그의 '모델별: None 3컷').
            #    성공률 검사가 그만큼 헐거워져 소리 빈 영상이 통과할 뻔했다.
            last = last or dead
            break
        if pinned:
            model = pool.wait_for(pinned)
            # ⭐ **해설은 대타를 세우지 않는다.**
            #    못 박은 모델이 죽었을 때 다른 모델로 만들면 해설이 그 자리부터
            #    딴 사람이 된다. 부른 쪽이 그것을 보고 해설 64컷을 통째로 다시
            #    만드는데(switched 처리), 그러면 ① 그 회차 해설이 지난 회차와
            #    다른 목소리가 되고 ② 64회분 값이 또 나간다.
            #    해설만은 여기서 실패로 두고, 위쪽 한도 처리가 실행을 멈추게 한다.
            if model is None and speaker == "narrator":
                last = last or QuotaExhausted(
                    f"해설 목소리 모델({pinned})의 오늘 몫이 끝났습니다. "
                    "다른 모델로 대신 만들면 해설 목소리가 바뀌므로 만들지 않습니다.")
                break
            if model is None:
                model = pool.acquire()
        else:
            model = pool.acquire()
        if model is None:
            last = last or dead
            break
        try:
            synth_one(key, model, text, speaker, path, rotate=True)
            return None, model
        except QuotaExhausted as e:
            last = e
            pool.drop(model)
            print(f"    {model} 오늘 몫이 끝났다 → 뺀다"
                  f" (남은 모델 {len(pool.models)}개)")
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                wait = getattr(e, "_vt_wait", None) or _retry_wait(e, 60)
                pool.penalize(model, wait)
                print(f"    {model} 분당 한도 — {int(wait)}초 쉬게 두고 다른 모델로")
            else:
                pool.penalize(model, 10)
        except Exception as e:                 # 통신 오류·빈 응답 등
            last = e
            pool.penalize(model, 5)
    return last, None


# ── ⭐ 한 번에 이어서 읽히기 — 목소리를 하나로 유지하는 **뿌리 해결** ──────────
#
# 무엇이 문제였나 (2026-08-06 확정)
#   컷 하나하나가 제미나이를 **따로 부르는 별개의 호출**이다. 그래서 같은 모델·같은
#   목소리를 지정해도 호출마다 조금씩 **다른 사람**이 만들어진다.
#   손님이 H04·H05·A1-01 세 줄을 나란히 듣고 "셋 다 목소리가 다르다" 고 하셨다.
#   그때 H05 의 음높이는 이미 맞춰 둔 뒤였다(136.8Hz → 83.3Hz, 앞뒤 평균 81.6Hz).
#   **높이를 맞췄는데도 다른 사람으로 들렸다** — 그러면 원인은 높이가 아니다.
#
# 왜 후보정으로는 절대 못 고치나
#   사람이 '누구 목소리인지' 알아듣는 것은 높이가 아니라 **울림(포먼트)** 이다.
#   목구멍·입 모양이 만드는 소리의 색이고, 사람마다 고정이다. 노래를 높게 부르든
#   낮게 부르든 그 사람인 줄 아는 이유가 이것이다.
#   이미 만들어진 소리에서 **다른 사람을 같은 사람으로 바꿀 수는 없다.**
#   음높이 맞추기·음색 EQ 는 전부 이 벽 앞에서 멈춘다. 이틀을 여기 썼고 다 빗나갔다.
#
# 그래서 만드는 쪽을 바꾼다
#   한 번의 호출 안에서는 모델이 **같은 사람을 유지**한다. 그러니 인물별로 여러 줄을
#   한 통에 이어서 읽힌 뒤, 무음을 찾아 도로 컷마다 잘라 쓴다.
#     지금    해설 64번 호출 → 조금씩 다른 64명
#     바꾸면  해설  4번 호출 → 한 통 안에서는 완전히 같은 사람
#
# ⚠️ 자르는 지점이 어긋나면 자막과 소리가 통째로 밀린다 — 영상이 못 쓰게 된다.
#    그래서 **자른 뒤 반드시 검사**하고, 하나라도 이상하면 그 묶음은 통째로 버리고
#    예전 방식(컷마다 따로)으로 되돌린다. 되돌리면 값이 조금 더 들 뿐, 영상은 멀쩡하다.
GROUP_ON = os.environ.get("TTS_GROUP", "1").strip().lower() \
    not in ("0", "off", "no", "false")
GROUP_MAX_CHARS = int(os.environ.get("TTS_GROUP_CHARS", "700"))   # 한 통에 넣을 최대 글자
GROUP_MAX_LINES = int(os.environ.get("TTS_GROUP_LINES", "20"))    # 한 통에 넣을 최대 줄


def plan_groups(cuts, out, everything=False):
    """아직 안 만든 컷을 **인물별로, 대본 차례대로** 묶는다.

    차례를 지키는 이유: 영상에서 바로 이어 붙는 줄들이 같은 통에 들어가야 한다.
    손님이 지적한 H05→A1-01 이 그런 자리다(막은 다르지만 화면에서는 연속이다).
    글자 수로 끊으므로 실제로 훅+1막 해설이 한 통에 들어간다.

    everything=True 면 이미 만든 컷도 포함해 **대본 전체의 묶음 설계도**를 돌려준다.
    (컷이 어느 통에서 나왔는지 이름표를 붙일 때 쓴다 — map_groups 참조)"""
    cur, groups = {}, []

    def flush(sp):
        g = cur.pop(sp, None)
        if g:
            groups.append((sp, g))

    part = {}          # 인물별로 '지금 담고 있는 묶음이 어느 편 것인지'

    for c in cuts:
        sp = c.get("speaker", "narrator")
        text = (c.get("text") or "").strip()
        if not text:
            continue
        p = out / f"{c['id']}.mp3"
        if not everything and p.exists() and not p.with_suffix(".silent").exists():
            continue                       # 이미 있는 컷은 건드리지 않는다
        # ⭐ 2026-08-08 손님 지적: "쇼츠는 자막하고 나레이션이 하나도 안 맞아."
        #    원인은 **쇼츠 3편의 해설 20줄을 한 통에 몰아 만든 것**이었다.
        #    한 통을 20조각으로 자르는데, 경계 하나만 어긋나면 그 뒤가 **전부 한 칸씩
        #    밀린다** — 자막은 4번인데 소리는 3번이 나오는 식이라 말이 안 이어진다.
        #    이제 편이 바뀌면 통을 끊는다(_grp). 한 편은 해설 8줄이라 훨씬 안전하고,
        #    어긋나도 그 편 하나로 피해가 갇힌다. (편끼리는 따로 보는 영상이라
        #    통이 달라져도 상관없다)
        grp = c.get("_grp")
        if sp in cur and part.get(sp) != grp:
            flush(sp)
        part[sp] = grp
        g = cur.setdefault(sp, [])
        if g and (sum(len(x[1]) for x in g) + len(text) > GROUP_MAX_CHARS
                  or len(g) >= GROUP_MAX_LINES):
            flush(sp)
            g = cur.setdefault(sp, [])
        g.append((c["id"], text))
    for sp in list(cur):
        flush(sp)
    # 두 줄 이상인 묶음만 뜻이 있다. 한 줄짜리는 예전 방식과 같으므로 그냥 둔다.
    return [(sp, g) for sp, g in groups if len(g) >= 2]


def group_prompt(speaker, lines):
    """묶어 읽히기에 보내는 글(지시문 + 대사 전문)을 만든다.

    따로 뗀 이유: 잘 만들어진 '한 통 원본'(_master_*.mp3)을 보관해 두고 다음
    실행에서 다시 쓰려면, **무엇으로 만든 원본인지**를 이름표(master_sig)에
    새겨야 한다. 통의 소리를 결정하는 것이 바로 이 글이므로, 글을 만드는 곳을
    한 군데로 모아 이름표와 실제 요청이 절대 어긋나지 않게 한다."""
    body = "\n\n".join(t for _, t in lines)
    # ⭐ '문장 사이에 쉬어라' 를 분명히 시킨다. 그 쉼이 나중에 자르는 자리가 된다.
    #    번호를 붙이지 말라고 못 박는다 — 붙이면 "일번" 을 소리 내어 읽어 버린다.
    # ⭐ 2026-08-07 손님 지적 — **한 통에 만들면서 줄마다 다르게 연기하라고 시키면 안 된다.**
    #    예전 지시문에는 "배우가 연기하듯", "문장 끝을 눌러" 같은 연기 주문이 들어 있었다.
    #    그러면 모델이 **줄마다 새로 해석**한다. 특히 물음표로 끝나는 줄(H05)에서
    #    톤을 확 올려 버린다 — 한 통에 만들어도 그 줄만 다른 사람처럼 들린 이유다.
    #    묶어 만드는 목적은 **한 사람을 유지하는 것**이지 연기를 시키는 것이 아니다.
    #    그래서 여기서는 '누구인지'만 주고, 나머지는 **고르게 읽으라**고만 한다.
    who = BODY.get(speaker, "")
    return ("\n".join(x for x in (
        f"너는 {who}" if who else "",
        "아래 대사들을 위에서부터 차례대로 말해라.",
        "⚠️ 처음부터 끝까지 **같은 목소리, 같은 높이, 같은 크기, 같은 속도**로 말해라.",
        # ⭐ 2026-08-07 손님 확인: **이 문장 그대로 만든 것을 귀로 듣고 통과시키셨다.**
        #    ("와 드디어 똑같아졌다") 그래서 손대지 않는다.
        #
        #    나는 이 문장을 '말끝만 올려라' 로 고치려 했다. 손님 지적이 이론적으로는
        #    맞기 때문이다(한국어에서 물음표 말끝을 올리는 것은 자연스럽다).
        #    그런데 **실제로 귀로 확인된 것은 이 문장**이고, 고친 쪽은 확인된 적이 없다.
        #    귀로 통과한 것을 이론으로 바꾸지 않는다 — 그러다 세 번 빗나갔다.
        #    (바꾸고 싶으면 25원짜리 시험으로 먼저 들어보고 바꾼다)
        "줄마다 감정을 다르게 싣지 마라. 물음표로 끝나는 줄도 톤을 올리지 마라.",
        "대사와 대사 사이에는 반드시 1초 이상 충분히 쉬어라.",
        "번호나 다른 말을 덧붙이지 말고, 대사만 그대로 말해라:",
    ) if x) + f"\n{body}")


def master_sig(speaker, model, lines):
    """'한 통 원본' 보관본의 이름표. 통의 소리를 결정하는 재료 — 모델·목소리·배속·
    보낸 글(지시문+대사 전문) — 를 전부 녹여 만든다. 하나라도 다르면 이름이 달라져
    재사용되지 않는다.

    ⚠️ 자르는 방식(recipe 의 way 표시)은 **일부러 뺀다.** 원본 한 통은 자르기 전
       소리라서 자르는 방식과 무관하다. 그래서 나중에 자르기를 또 고치더라도
       (g4→g5) 보관해 둔 원본을 그대로 꺼내 **다시 자르기만 하면 된다 — 0원.**
       2026-08-08 g3→g4 때는 원본을 지워 버린 탓에 자르기만 고치고도 한 편을
       통째로 새로 만들어야 했다(약 650원). 그 값이 다시는 안 나가게 하는 장치다."""
    voice = VOICE_NAME.get(speaker, "Charon")
    speed = VOICE_STYLE.get(speaker, VOICE_STYLE["narrator"])[1]
    raw = f"{model}|{voice}|{speed:.2f}|{group_prompt(speaker, lines)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def synth_group(key, model, lines, speaker, out_mp3, rotate=False):
    """여러 줄을 **한 번에** 읽혀 mp3 한 개로 받는다. (자르기는 split_group 이 한다)"""
    speed = VOICE_STYLE.get(speaker, VOICE_STYLE["narrator"])[1]
    voice = VOICE_NAME.get(speaker, "Charon")
    prompt = group_prompt(speaker, lines)

    res = _post_retry(f"{BASE}/models/{model}:generateContent?key={key}", {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
            },
        },
    }, timeout=300, label=f"{speaker}×{len(lines)}", rotate=rotate)

    SPEND.add(res.get("usageMetadata"))
    parts = (res.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    blob = next((p["inlineData"] for p in parts if "inlineData" in p), None)
    if not blob:
        raise LLMError("음성 데이터가 오지 않았다")

    pcm = base64.b64decode(blob["data"])
    tmp = out_mp3.with_suffix(".wav")
    pcm_to_wav(pcm, tmp, rate=rate_from_mime(blob.get("mimeType")))
    if not shutil.which("ffmpeg"):
        tmp.replace(out_mp3)
        return out_mp3
    # 배속은 **자르기 전에** 통째로 건다. 컷마다 따로 걸던 것과 결과가 같아야 한다.
    af = f"atempo={speed:.3f}" if abs(speed - 1.0) > 0.01 else "anull"
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp),
                        "-af", af, "-b:a", "160k", str(out_mp3)], check=True)
    finally:
        tmp.unlink(missing_ok=True)
    return out_mp3


def _silences(path, noise_db, min_dur):
    """무음 구간 목록 — (한가운데 시각, 길이). 여기가 자를 후보다.

    길이를 같이 돌려주는 이유: 자를 자리를 **쉼의 길이로** 고르기 때문이다
    (아래 split_group 설명 참조). 긴 쉼 = 줄 사이, 짧은 쉼 = 줄 안."""
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
                            "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}",
                            "-f", "null", "-"],
                           capture_output=True, text=True, timeout=300)
    except Exception:
        return []
    out, start = [], None
    for m in re.finditer(r"silence_(start|end):\s*(-?[\d.]+)", r.stderr):
        if m.group(1) == "start":
            start = float(m.group(2))
        elif start is not None:
            end = float(m.group(2))
            out.append(((start + end) / 2.0, end - start))
            start = None
    return out


def _pick_cuts(cands, want, total, fracs):
    """(예비용) 후보 무음 중 want 개를 **글자 수로 기대한 자리**에 가장 가깝게 고른다.

    ⚠️ 2026-08-07 사고로 **예비 수단으로 강등**됐다. 왜인지 반드시 기억할 것.
       이 계산의 '기대 자리' 는 글자 수 비율 × 전체 길이다. 그런데 전체 길이에는
       **문장 사이 쉼이 들어 있다** (19줄이면 쉼만 약 18초). 쉼을 무시한 기대 자리는
       뒤로 갈수록 실제보다 앞으로 밀리고, 그러면 줄 **안의** 쉼("괜찮아요. ↕ 형은…")
       이 경계로 뽑힌다 → 뒷부분이 옆 컷으로 넘어간다.
       실제로 그렇게 됐다 — 자막은 다 떠 있는데 소리는 뒷문장이 없었다.
       이제 1차 선택은 **쉼의 길이**로 한다(아래 _pick_by_pause). 이 함수는
       길이로 못 가릴 때(쉼 길이가 고만고만할 때)만 나선다."""
    n = len(cands)
    if n < want or want <= 0:
        return None
    INF = float("inf")
    pos = [c[0] for c in cands]
    dp = [[INF] * n for _ in range(want)]
    bk = [[-1] * n for _ in range(want)]
    for i in range(n):
        dp[0][i] = abs(pos[i] - fracs[0] * total)
    for j in range(1, want):
        best, bi = INF, -1
        for i in range(n):
            if i > 0 and dp[j - 1][i - 1] < best:
                best, bi = dp[j - 1][i - 1], i - 1
            if best < INF:
                dp[j][i] = best + abs(pos[i] - fracs[j] * total)
                bk[j][i] = bi
    end = min(range(n), key=lambda i: dp[want - 1][i])
    if dp[want - 1][end] == INF:
        return None
    picked, i = [0] * want, end
    for j in range(want - 1, -1, -1):
        picked[j] = i
        i = bk[j][i]
    return [cands[k] for k in picked]


def _pick_best(cands, want, total, chars):
    """자를 자리 고르기 1차 — **쉼의 길이와 글자 분량을 함께** 본다.

    왜 (2026-08-08 · A1-18 "너희 형은 바쁘잖니. 네가 고생이 많다." 사고):
      '가장 긴 쉼'만 보면, 배우가 줄 **안**의 마침표에서 줄 사이보다 길게
      쉬어 버린 경우(연기) 그 자리를 경계로 뽑는다 → 뒷문장이 옆 컷으로 넘어간다.
      '글자 위치 짐작'만 보면 쉼 시간을 무시해 딴 사고가 난다(_pick_cuts 참조).
      그래서 둘을 합친다: 도막마다 (쉼을 뺀) **말 시간 ÷ 글자 수**가 고르게
      나오는 나눔 가운데, **긴 쉼을 자르는 자리로 쓰는** 쪽을 고른다.
      말이 빨라지고 느려져도(실측 1.6배) 글자 맞춤이 무너지지 않도록,
      벌점은 비율의 로그로 재고 쉼 보너스가 동률을 가른다."""
    m = len(cands)
    if m < want or want <= 0:
        return None
    share = [c / (sum(chars) or 1) for c in chars]
    tot_speech = max(0.5, total - sum(d for _, d in cands))
    ts = [c[0] for c in cands]
    cum = [0.0]
    for _, d in cands:
        cum.append(cum[-1] + d)

    def speech(a, da, b, db):
        i, j = bisect.bisect_right(ts, a), bisect.bisect_left(ts, b)
        return max(0.05, (b - a) - (cum[j] - cum[i]) - da / 2.0 - db / 2.0)

    def pen(a, da, b, db, k):
        return abs(math.log(speech(a, da, b, db)
                            / max(0.05, share[k] * tot_speech)))

    BONUS = 1.0          # 쉼 1초(log1p≈0.69)가 글자 벌점 0.69 만큼의 값어치
    INF = float("inf")
    dp = [[INF] * m for _ in range(want)]
    bk = [[-1] * m for _ in range(want)]
    for j in range(m):
        t, d = cands[j]
        dp[0][j] = pen(0.0, 0.0, t, d, 0) - BONUS * math.log1p(d)
    for i in range(1, want):
        for j in range(i, m):
            t, d = cands[j]
            for k in range(i - 1, j):
                if dp[i - 1][k] >= INF:
                    continue
                v = (dp[i - 1][k] + pen(cands[k][0], cands[k][1], t, d, i)
                     - BONUS * math.log1p(d))
                if v < dp[i][j]:
                    dp[i][j], bk[i][j] = v, k
    best, bj = INF, -1
    for j in range(want - 1, m):
        if dp[want - 1][j] >= INF:
            continue
        v = dp[want - 1][j] + pen(cands[j][0], cands[j][1], total, 0.0, want)
        if v < best:
            best, bj = v, j
    if bj < 0:
        return None
    picked, j = [], bj
    for i in range(want - 1, -1, -1):
        picked.append(cands[j])
        j = bk[i][j]
    picked.reverse()
    return picked


def _pick_by_pause(cands, want):
    """자를 자리를 **쉼의 길이**로 고른다 — 가장 긴 쉼 want 개.

    왜 이것이 1차인가: 모델에게 '대사 사이에는 1초 이상 쉬어라' 고 시킨다.
    그래서 줄 **사이** 쉼은 길고, 줄 **안** 쉼(마침표·쉼표)은 짧다.
    길이로 고르면 위치를 짐작할 필요가 아예 없다 — 말이 빨라지든 느려지든
    긴 쉼은 긴 쉼이다. (위치 짐작이 어떻게 사고를 냈는지는 _pick_cuts 참조)"""
    if len(cands) < want or want <= 0:
        return None
    top = sorted(cands, key=lambda c: -c[1])[:want]
    return sorted(top, key=lambda c: c[0])       # 시간 순으로 되돌린다


def _check_segs(segs, chars, lines, why):
    """잘린 도막들이 말이 되는지. 걸리면 이유를 찍고 False.

    글자당 시간은 **쉼을 뺀 말 시간**으로 잰다. 도막 길이에는 양끝 쉼의 절반씩이
    들어 있어서, 짧은 줄일수록 쉼이 상대적으로 커져 예전 검사(도막 길이 기준)는
    문턱을 넉넉히(45~220%) 풀어야 했고, 그 틈으로 잘못 잘린 도막이 통과했다."""
    n = len(chars)
    if any(b - a < 0.4 for (a, b, _l, _r) in segs):
        print(f"      너무 짧은 도막이 생겼다({n}줄) — {why}")
        return False
    per = []
    for (a, b, lp, rp), ch in zip(segs, chars):
        speech = (b - a) - (lp + rp) / 2.0       # 양끝 쉼의 내 몫(절반)을 뺀다
        per.append(max(0.05, speech) / max(1, ch))
    mid = statistics.median(per)
    bad = [i for i, v in enumerate(per) if not (0.5 * mid <= v <= 2.0 * mid)]
    if bad:
        who = ", ".join(lines[i][0] for i in bad[:3])
        print(f"      길이가 글자 수와 안 맞는 도막이 있다({who}) — {why}")
        return False
    # ⭐ 이웃 짝 검사 (2026-08-08 · A1-18 사고가 이 검사를 빠져나가 영상까지 갔다):
    #    뒷문장이 옆 컷으로 넘어가면 **모자란 도막 + 남아도는 옆 도막**이 짝으로
    #    생긴다. 각각은 위의 넉넉한 띠(50~200%) 안에 들 수 있지만(실측 52%·155%),
    #    바로 이웃한 두 도막이 반대 방향으로 함께 벗어나는 일은 정상 낭독에는 없다
    #    (말 빠르기 들쭉날쭉은 67%·133% 수준 — 시험 7 기준). 짝으로 보면 잡힌다.
    for i in range(len(per) - 1):
        lo, hi = min(per[i], per[i + 1]), max(per[i], per[i + 1])
        if lo < 0.62 * mid and hi > 1.45 * mid:
            print(f"      이웃 도막 길이가 서로 어긋난다"
                  f"({lines[i][0]}·{lines[i + 1][0]}) — {why}")
            return False
    return True


# 잘라낸 도막의 **앞뒤 빈 소리를 잘라낸다.**
#   자르는 자리는 쉼의 한가운데다. 그래서 그냥 자르면 도막 앞뒤에 0.5초씩 빈 소리가
#   붙는다. 그대로 두면 컷이 시작되고 나서 한참 뒤에 말이 시작돼 화면과 어긋난다.
#   컷마다 따로 만든 음성은 곧바로 말이 시작되므로, 거기에 맞춘다.
#   앞은 0.10초, 뒤는 0.15초만 남긴다(딱 붙이면 말머리가 잘린 것처럼 들린다).
TRIM_EDGE = (
    "silenceremove=start_periods=1:start_silence=0.10:start_threshold=-45dB:detection=peak,"
    "areverse,"
    "silenceremove=start_periods=1:start_silence=0.15:start_threshold=-45dB:detection=peak,"
    "areverse"
)


def split_group(big, lines, out):
    """한 통으로 받은 소리를 **컷마다 잘라** 낸다. 못 믿겠으면 None 을 돌려준다.

    검사 (하나라도 걸리면 통째로 버린다 — 어긋난 자막보다 값 조금 더 쓰는 것이 낫다)
      ① 자를 자리를 필요한 만큼 못 찾으면 실패
      ② 도막 하나가 0.4초보다 짧으면 실패 (말이 잘렸다는 뜻)
      ③ 글자당 길이가 가운뎃값의 45%~220% 를 벗어나면 실패 (엉뚱한 데서 잘랐다)"""
    total = _duration(big)
    if total <= 0:
        return None
    n = len(lines)
    chars = [len(t) for _, t in lines]
    tot_ch = sum(chars) or 1
    acc, fracs = 0, []
    for k in range(n - 1):
        acc += chars[k]
        fracs.append(acc / tot_ch)

    # 무음 기준을 넉넉한 쪽부터 좁혀 가며 후보를 찾는다. 모델이 시킨 만큼
    # 길게 안 쉬는 경우가 있어, 한 가지 기준만 쓰면 그때마다 실패한다.
    #
    # 고르는 순서 (2026-08-07 사고 후):
    #   1차 — **가장 긴 쉼** n-1개 (줄 사이 쉼은 1초 이상으로 시켰으니 제일 길다)
    #   2차 — 글자 수 위치 짐작 (쉼 길이가 고만고만해서 1차로 못 가릴 때만)
    # 어느 쪽이든 **쉼을 뺀 말 시간**으로 글자당 길이를 검사해 통과해야 쓴다.
    segs = None
    for noise, dur in ((-35, 0.45), (-35, 0.30), (-30, 0.25), (-40, 0.25), (-30, 0.18)):
        # 파일 맨 앞·뒤에 붙은 무음은 자를 자리가 아니다. 한가운데(c[0])만 보면
        # 긴 꼬리 무음(예: 끝에 2초)이 후보로 들어와 '가장 긴 쉼' 으로 뽑힌다 —
        # 그러면 마지막 줄이 빈 도막이 된다. 무음의 **양 끝**이 파일 안쪽에
        # 있는 것만 후보로 삼는다.
        cands = [c for c in _silences(big, noise, dur)
                 if c[0] - c[1] / 2 > 0.15 and c[0] + c[1] / 2 < total - 0.15]
        for how, picked in (("쉼·글자 맞춤", _pick_best(cands, n - 1, total, chars)),
                            ("긴 쉼", _pick_by_pause(cands, n - 1)),
                            ("위치 짐작", _pick_cuts(cands, n - 1, total, fracs))):
            if not picked:
                continue
            bounds = [(0.0, 0.0)] + picked + [(total, 0.0)]
            try_segs = [(bounds[k][0], bounds[k + 1][0],
                         bounds[k][1], bounds[k + 1][1]) for k in range(n)]
            if _check_segs(try_segs, chars, lines, f"{how} 후보는 버린다"):
                segs = try_segs
                break
        if segs:
            break
    if segs is None:
        print(f"      자를 자리를 못 찾았다({n}줄) — 이 묶음은 컷마다 따로 만든다")
        return None

    made = []
    for (cid, _t), (a, b, _lp, _rp) in zip(lines, segs):
        p = out / f"{cid}.mp3"
        try:
            # ⚠️ -ss/-t 는 반드시 **-i 앞**에 둔다. 뒤에 두면 잘라내기가 필터보다
            #    나중에 일어나, 앞뒤 빈 소리 잘라내기가 도막이 아니라 **파일 전체**에
            #    걸린다(실측으로 걸렸다 — 도막 길이가 하나도 안 줄었다).
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                            "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(big),
                            "-af", TRIM_EDGE,
                            "-b:a", "160k", str(p)], check=True, timeout=120)
            # ⭐ **잘라낸 도막에 소리가 진짜 들어 있는지 확인한다.**
            #    앞뒤 빈 소리 잘라내기(TRIM_EDGE)가 도막을 통째로 먹어 버릴 수 있다 —
            #    모델이 그 줄을 웅얼거리거나 건너뛰면 그 구간이 거의 무음이기 때문이다.
            #    그러면 **자막은 뜨는데 목소리가 안 나오는 컷**이 된다. 최악이다.
            #    길이만 보면 안 된다. 무음도 길이는 있다 — 크기까지 잰다.
            got = _duration(p)
            db = _mean_db(p)
            if got < 0.35 or db is None or db < -50:
                raise LLMError(f"도막에 소리가 없다({got:.2f}초"
                               f"{'' if db is None else f' · {db:.0f}dB'})")
            p.with_suffix(".silent").unlink(missing_ok=True)
            made.append(cid)
        except Exception as e:
            for x in made:                 # 반쯤 만들다 만 것을 남기지 않는다
                (out / f"{x}.mp3").unlink(missing_ok=True)
            p.unlink(missing_ok=True)      # 만들다 만 이 컷도 지운다
            print(f"      {cid} 도막이 쓸 수 없다({e}) — 이 묶음은 컷마다 따로 만든다")
            return None
    return made


def _duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except (ValueError, AttributeError):
        return 0.0


def _one_group(pool, key, sp, lines, out, pin, book, depth=0, gbook=None):
    """묶음 하나를 만들어 자른다. 실패하면 **반으로 쪼개 한 번만 더** 해 본다.

    왜 반으로 쪼개나
        한 번에 받을 수 있는 소리 길이에 한도가 있을 수 있다. 그 한도에 걸리면
        소리가 도중에 끊겨 오고, 검사에서 걸러진다. 그때 그냥 포기하면
        컷마다 따로 만들기로 되돌아가 **목소리가 다시 흩어진다.**
        반으로 줄이면 대개 들어간다 — 목소리를 지키는 쪽이 훨씬 낫다.
        (한도가 아니라 딴 이유로 실패한 것이면 반쪽도 실패하고, 그때 되돌아간다)"""
    model = pin.get(sp)
    if not model:
        return set()
    name = "해설" if sp == "narrator" else sp
    tag = str(lines[0][0]).replace("/", "_")
    big = out / f"_group_{tag}_{depth}.mp3"
    keep = out / f"_master_{master_sig(sp, model, lines)}.mp3"

    # ⭐ 0원 경로 — 지난 실행이 보관해 둔 '한 통 원본'이 있으면 **부르지 않는다.**
    #    자르는 방식만 바뀌어 컷을 전부 다시 만들어야 할 때가 여기에 해당한다.
    #    원본은 자르기 전 소리라 그대로 쓸 수 있고, 다시 자르기만 하면 된다.
    if keep.exists():
        try:
            shutil.copyfile(keep, big)
            made = split_group(big, lines, out)
        except Exception:
            made = None
        big.unlink(missing_ok=True)
        if made:
            for cid, text in lines:
                book[cid] = recipe(sp, model, text)
                if gbook is not None:
                    gbook[cid] = keep.stem[len("_master_"):]
            print(f"    {name} 보관된 원본을 다시 잘라 {len(made)}컷"
                  f" ({lines[0][0]} ~ {lines[-1][0]}) — 새로 부르지 않음(0원)")
            return set(made)
        # 보관본이 안 잘리면(파일이 상했거나 검사가 세졌거나) 지우고 새로 받는다.
        keep.unlink(missing_ok=True)
        print(f"    {name} 보관된 원본이 안 잘려 새로 받는다")

    err = None
    for _ in range(2):
        try:
            if pool.wait_for(model) is None:
                raise LLMError("이 모델의 오늘 몫이 끝났다")
            synth_group(key, model, lines, sp, big)
            err = None
            break
        except Exception as e:
            err = e
            pool.penalize(model, 5)
    made = None
    if err is None:
        made = split_group(big, lines, out)
    else:
        print(f"    {name} {len(lines)}줄 묶음을 못 받았다({type(err).__name__})")

    if made:
        # ⭐ 잘 잘린 통의 원본은 지우지 않고 캐시에 보관한다(_master_*.mp3).
        #    g3→g4 자르기 수리 때 원본이 없어서 한 편을 통째로 새로 만들었다(약 650원).
        #    보관해 두면 다음 수리부터는 다시 자르기만 하면 된다 — 0원.
        #    ⚠️ 검사(split_group)에 **통과한 통만** 보관한다. 떨어진 통을 보관하면
        #    다음 실행마다 그 통으로 또 떨어지는 것을 되풀이하기 때문이다.
        big.replace(keep)
        for cid, text in lines:
            book[cid] = recipe(sp, model, text)
            if gbook is not None:
                gbook[cid] = keep.stem[len("_master_"):]
        print(f"    {name} {len(made)}컷을 한 통으로 만들어 잘랐다"
              f" ({lines[0][0]} ~ {lines[-1][0]})")
        return set(made)
    big.unlink(missing_ok=True)

    if depth < 1 and len(lines) >= 4:
        half = len(lines) // 2
        print(f"    {name} {len(lines)}줄을 {half}+{len(lines) - half} 로 쪼개 다시 해 본다")
        got = _one_group(pool, key, sp, lines[:half], out, pin, book, depth + 1, gbook)
        got |= _one_group(pool, key, sp, lines[half:], out, pin, book, depth + 1, gbook)
        return got
    print(f"    {name} {lines[0][0]}~{lines[-1][0]} 는 컷마다 따로 만든다")
    return set()


def make_groups(pool, key, cuts, out, pin, book, gbook=None):
    """묶음마다 한 번씩 불러 만들고 잘라 넣는다. 성공한 컷 이름을 돌려준다.

    실패한 묶음은 **아무것도 남기지 않는다.** 그러면 뒤따르는 컷마다 만들기가
    없는 컷만 예전 방식으로 채운다 — 영상은 어떤 경우에도 온전하다."""
    if not GROUP_ON or not shutil.which("ffmpeg"):
        return set()
    groups = plan_groups(cuts, out)
    if not groups:
        return set()
    n_lines = sum(len(g) for _, g in groups)
    # ⭐ **작은 묶음부터 시도한다.** 값을 아끼기 위해서다.
    #    묶어 읽기가 이 모델에서 아예 안 통하면 앞의 두 묶음에서 드러난다(아래 miss).
    #    그 두 번을 20줄짜리(약 100초)로 태우면 120원이 날아가고, 5줄짜리(약 20초)로
    #    태우면 25원이면 끝난다. **못 쓰는 것을 알아내는 값**을 최대한 싸게 만든다.
    groups.sort(key=lambda g: sum(len(t) for _, t in g[1]))
    print(f"  한 번에 이어서 읽히기: {len(groups)}묶음 · {n_lines}컷"
          f" — 한 통 안에서는 목소리가 안 바뀐다 (작은 묶음부터)")

    # ⚠️ **값이 새는 것을 막는 안전장치.**
    #    묶어 읽기가 이 모델에서 아예 안 통하는 경우(자를 만큼 안 쉬어 준다든지),
    #    8묶음을 전부 시도하면 8번 값을 다 쓰고 **그 뒤에 컷마다 또 만든다** —
    #    한 편 값을 두 번 내는 셈이다. 한 묶음이 100초짜리라 결코 싸지 않다.
    #    그래서 **연속 두 묶음이 통째로 실패하면 그만둔다.** 낭비를 두 번으로 막고,
    #    나머지는 예전 방식(컷마다)이 조용히 맡는다.
    done, miss = set(), 0
    for sp, lines in groups:
        if miss >= 2:
            print(f"    {'해설' if sp == 'narrator' else sp} {len(lines)}줄 —"
                  " 앞의 두 묶음이 잇따라 실패해 더 시도하지 않는다 (값 아끼기)")
            continue
        got = _one_group(pool, key, sp, lines, out, pin, book, gbook=gbook)
        miss = 0 if got else miss + 1
        done |= got
    if done:
        print(f"  한 번에 읽히기로 {len(done)}컷 완성"
              f" (컷마다 따로 만든 것은 {n_lines - len(done)}컷)")
    return done


# ─────────────────────────────────────────────────────────────────────
# 컷 → 통(take) 이름표 (groups.json)
#
# 2026-08-08 실패의 교훈: 목소리 검사가 컷 단위로만 재서, **같은 통에서 나온
# 컷의 억양**(H02 +4.6반음)까지 '다른 사람'으로 오판해 실행을 막았다.
# "한 통 안은 같은 목소리" 는 만든 방식이 보장하는 사실이므로, 어느 컷이
# 어느 통에서 나왔는지를 파일로 남겨 검사기(voiceguard)와 아래 맞추기가 쓴다.
# ─────────────────────────────────────────────────────────────────────

def load_groups(out):
    try:
        return json.loads((out / "groups.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def map_groups(cuts, out, pin, gbook):
    """모든 컷에 '어느 통에서 나왔는지'(master_sig)를 붙여 groups.json 에 남긴다.

    근거가 있는 것만 적는다 —
      ① 이번 실행이 직접 만든 컷(gbook)          : 확실
      ② 지난 실행이 남긴 기록(groups.json)        : 확실
      ③ 보관된 원본(_master_*.mp3)이 있는 묶음    : 원본이 곧 증거
    근거 없는 컷(컷마다 따로 만든 것)은 적지 않는다 — 그 컷은 저 혼자 한 통이다.
    ③에서 반쪽 통도 본다: _one_group 은 실패 시 딱 한 번 반으로 쪼개므로,
    통짜 원본이 없으면 앞반쪽·뒷반쪽 원본을 찾아 본다."""
    gmap = load_groups(out)
    gmap.update(gbook or {})
    for sp, lines in plan_groups(cuts, out, everything=True):
        model = pin.get(sp)
        if not model:
            continue
        parts = []
        if (out / f"_master_{master_sig(sp, model, lines)}.mp3").exists():
            parts = [lines]
        elif len(lines) >= 4:
            half = len(lines) // 2
            parts = [lines[:half], lines[half:]]
        for part in parts:
            sig = master_sig(sp, model, part)
            if (out / f"_master_{sig}.mp3").exists():
                for cid, _ in part:
                    gmap.setdefault(cid, sig)
    try:
        (out / "groups.json").write_text(json.dumps(gmap, ensure_ascii=False),
                                         encoding="utf-8")
    except Exception:
        pass
    return gmap


# 해설 통끼리 허용하는 높이 차. 검사기(voiceguard)의 SPREAD 문턱과 같아야 한다 —
# 여기서 이만큼 못 맞추면 검사기가 막고, 여기서 맞추면 검사기가 통과시킨다.
ALIGN_SPREAD = float(os.environ.get("VT_ALIGN_SPREAD", "5.0"))
ALIGN_TRIES = int(os.environ.get("VT_ALIGN_TRIES", "2"))


def align_narrator(pool, key, cuts, out, pin, book, gmap):
    """해설 통(take)끼리 목소리 높이가 벌어졌으면 **가장 벗어난 통만** 다시 읽힌다.

    왜 통 단위인가
        한 통 안은 같은 목소리다(만든 방식이 보장). 통끼리는 호출이 달라서
        어긋날 수 있다 — 2026-08-08 실측: 해설 통 하나가 다른 통들보다 높아
        전체 폭 5.1반음으로 검사가 멈췄다. 컷 하나만 다시 만들면 목소리가
        더 흩어진다(옛 병). 그래서 통째로만 다시 읽힌다.
    돈
        보통 0원(이미 맞으면 재지 않고 끝). 벌어졌을 때만 통당 한 번 호출
        (약 30~60원), 최대 ALIGN_TRIES 번. **다시 읽혀서 오히려 더 벌어지면
        예전 통을 되살린다** — 시도해서 더 나빠지는 일은 없다.
    """
    if not GROUP_ON or ALIGN_TRIES <= 0 or not key:
        return
    # 지난 실행이 도중에 죽어 남긴 챙겨두기 폴더가 있으면 지운다
    shutil.rmtree(out / "_align_bak", ignore_errors=True)
    narr = [c for c in cuts if c.get("speaker", "narrator") == "narrator"
            and (c.get("text") or "").strip()]
    text_of = {c["id"]: c["text"].strip() for c in narr}
    f0 = {}

    def hz(cid):
        if cid not in f0:
            p = out / f"{cid}.mp3"
            f0[cid] = measure_f0(p) if (
                p.exists() and not p.with_suffix(".silent").exists()) else None
        return f0[cid]

    def takes(m):
        """통별 (컷 목록, 높이 가운뎃값). 2컷 이상 잰 통만 — 1컷 통은 억양에 흔들린다."""
        got = {}
        for c in narr:
            sig = m.get(c["id"])
            if sig:
                got.setdefault(sig, []).append(c["id"])
        meds = {}
        for sig, cids in got.items():
            vals = [v for v in (hz(c) for c in cids) if v]
            if len(vals) >= 2:
                meds[sig] = (cids, statistics.median(vals))
        return meds

    def spread_of(meds):
        if len(meds) < 2:
            return 0.0
        vals = [12.0 * math.log2(v) for _, v in meds.values()]
        return max(vals) - min(vals)

    meds = takes(gmap)
    spread = spread_of(meds)
    if len(meds) < 2 or spread <= ALIGN_SPREAD:
        if len(meds) >= 2:
            print(f"  해설 통 맞추기: {len(meds)}통 폭 {spread:.1f}반음 — 손댈 것 없음")
        return

    order = {c["id"]: i for i, c in enumerate(narr)}
    for t in range(ALIGN_TRIES):
        # 다시 읽힐 통 고르기: **다른 통들의 가운데**에서 가장 벗어난 통.
        # (자기를 뺀 나머지 기준이라야 공정하다 — 통이 2개뿐이면 서로 똑같이
        #  벗어난 것이 되므로, 대본에서 나중에 나오는 통을 고른다: 앞 통이
        #  이미 들려준 목소리가 기준이 되는 편이 자연스럽다)
        def _off(kv):
            others = [v for s2, (_, v) in meds.items() if s2 != kv[0]]
            return abs(12.0 * math.log2(kv[1][1] / statistics.median(others)))
        # 반올림해서 견주는 이유: 통이 2개면 서로의 벗어남이 수학적으로 같은데,
        # 소수점 끝자리가 달라 동점 처리가 안 되면 앞 통을 고르는 수가 있다.
        sig, (cids, med) = max(
            meds.items(), key=lambda kv: (round(_off(kv), 3), order.get(kv[1][0][0], 0)))
        center = statistics.median(
            v for s2, (_, v) in meds.items() if s2 != sig)
        off = 12.0 * math.log2(med / center)
        print(f"  해설 통 맞추기: 전체 폭 {spread:.1f}반음 — "
              f"{cids[0]}~{cids[-1]} 통({off:+.1f}반음)을 다시 읽힌다 ({t + 1}/{ALIGN_TRIES})")

        # 예전 통을 챙겨 둔다 — 새 통이 더 나쁘면 되돌린다
        bak = out / "_align_bak"
        bak.mkdir(exist_ok=True)
        master = out / f"_master_{sig}.mp3"
        saved = []
        for f in [out / f"{c}.mp3" for c in cids] + [master]:
            if f.exists():
                f.replace(bak / f.name)
                saved.append(f.name)
        for c in cids:
            gmap.pop(c, None)
            f0.pop(c, None)

        masters_before = {p.name for p in out.glob("_master_*.mp3")}
        newg = {}
        lines = [(c, text_of[c]) for c in cids if c in text_of]
        made = _one_group(pool, key, "narrator", lines, out, pin, book, gbook=newg)

        ok_new = False
        if made and len(made) == len(lines):
            cand = dict(gmap)
            cand.update(newg)
            meds2 = takes(cand)
            spread2 = spread_of(meds2)
            if spread2 < spread - 0.1:
                ok_new = True
                gmap.update(newg)
                meds, spread = meds2, spread2
                print(f"    새 통이 더 낫다 — 폭 {spread:.1f}반음")

        if not ok_new:
            # 새 통을 지우고 예전 통을 되살린다 (더 나빠지지는 않는다)
            for c in cids:
                (out / f"{c}.mp3").unlink(missing_ok=True)
                (out / f"{c}.mp3").with_suffix(".silent").unlink(missing_ok=True)
                gmap.pop(c, None)
                f0.pop(c, None)
            for p in out.glob("_master_*.mp3"):
                if p.name not in masters_before:
                    p.unlink(missing_ok=True)
            for name in saved:
                (bak / name).replace(out / name)
            for c in cids:
                gmap[c] = sig
            for c, txt in lines:
                book[c] = recipe("narrator", pin.get("narrator"), txt)
            print(f"    새 통이 더 낫지 않다 — 예전 통을 그대로 둔다 (폭 {spread:.1f}반음)")

        shutil.rmtree(bak, ignore_errors=True)
        if spread <= ALIGN_SPREAD:
            break

    try:
        (out / "groups.json").write_text(json.dumps(gmap, ensure_ascii=False),
                                         encoding="utf-8")
    except Exception:
        pass
    if spread > ALIGN_SPREAD:
        print(f"  ⚠️ 해설 통 폭이 아직 {spread:.1f}반음이다 — 검사기가 알려줄 것이다")


# ─────────────────────────────────────────────────────────────────────
# 받아쓰기 대조 (2026-08-08 손님 지시: "나레이션 누락되는 거 없도록")
#
# 지금까지의 자르기 검사는 전부 **길이로 짐작**한다 — 그래서 A1-19(g3),
# A1-18(g4) 두 번이나 "자막엔 있는데 소리엔 없는 문장"이 빠져나가 영상까지 갔다.
# 여기서는 만든 소리를 AI에게 **받아 적게 해 대본과 글자로 대조**한다.
# 내용을 직접 확인하는 것이라 이 사고 유형을 원천에서 잡는다.
# 값: 통마다 한 번씩 묶어 부르므로 한 편에 약 3~5원.
# ─────────────────────────────────────────────────────────────────────

STT_ON = os.environ.get("VT_STT", "1").strip().lower() \
    not in ("", "0", "off", "no", "false")
STT_MODEL = os.environ.get("VT_STT_MODEL", "gemini-2.5-flash")
STT_GAP = 1.5              # 조각 사이에 넣는 무음(초) — 경계 표시
STT_FIX_MAX = 2            # 한 실행에서 통째로 다시 만드는 통의 최대 수 (돈 제한)


def transcribe_pieces(key, files):
    """조각 mp3 들을 무음으로 이어 붙여 **한 번에** 받아 적게 한다.

    돌려주는 것: 조각별 받아 적은 글(파일 수와 같은 길이) 또는 None(전사 실패).
    조각마다 따로 부르면 145번 호출이라 속도 제한에 걸린다 — 그래서 묶는다."""
    if not files:
        return []
    tmp = files[0].parent / "_stt_batch.mp3"
    ins, chain, k = [], [], 0
    for i, p in enumerate(files):
        if i:
            ins += ["-f", "lavfi", "-t", f"{STT_GAP}",
                    "-i", "anullsrc=r=24000:cl=mono"]
            chain.append(f"[{k}:a]")
            k += 1
        ins += ["-i", str(p)]
        chain.append(f"[{k}:a]")
        k += 1
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + ins +
                       ["-filter_complex",
                        "".join(chain) + f"concat=n={k}:v=0:a=1[a]",
                        "-map", "[a]", "-b:a", "96k", str(tmp)],
                       check=True, timeout=300)
        blob = base64.b64encode(tmp.read_bytes()).decode("ascii")
    except Exception:
        return None
    finally:
        tmp.unlink(missing_ok=True)

    prompt = (f"첨부한 음성은 한국어 문장 조각 {len(files)}개를 무음으로 나눠 이어"
              " 붙인 것이다. 각 조각을 들리는 그대로 받아 적어라."
              " 조각마다 정확히 한 줄씩, 순서대로, 번호나 다른 말 없이 적어라.")
    try:
        res = _post_retry(
            f"{BASE}/models/{STT_MODEL}:generateContent?key={key}",
            {"contents": [{"role": "user", "parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": "audio/mp3", "data": blob}}]}]},
            timeout=300, label=f"받아쓰기×{len(files)}")
    except Exception:
        return None
    SPEND.add(res.get("usageMetadata"))
    parts = (res.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts)
    got = [re.sub(r"^\s*\d+[.)]\s*", "", ln).strip()
           for ln in text.splitlines() if ln.strip()]
    if len(got) != len(files):
        # 조각 수가 안 맞으면 반으로 쪼개 다시 — 그래도 안 되면 포기(None)
        if len(files) >= 2:
            h = len(files) // 2
            a = transcribe_pieces(key, files[:h])
            b = transcribe_pieces(key, files[h:])
            if a is not None and b is not None:
                return a + b
        return None
    return got


def _norm_ko(s):
    return re.sub(r"[^가-힣a-zA-Z0-9]", "", s or "")


def _piece_ok(expected, got):
    """받아 적은 글에 대사의 **머리와 꼬리**가 다 있는지. 조금 다르게 적힌 것은 봐준다.

    꼬리가 없으면 = 뒷문장이 옆 컷으로 넘어갔다(A1-18 사고).
    머리가 다르면 = 옆 컷의 꼬리가 이 컷 머리에 붙었다(같은 사고의 반대쪽)."""
    import difflib
    e, g = _norm_ko(expected), _norm_ko(got)
    if not e:
        return True
    if not g:
        return False
    tail = e[-6:]
    tail_ok = tail in g[-(len(tail) + 8):] or difflib.SequenceMatcher(
        None, tail, g[-(len(tail) + 4):]).ratio() >= 0.5
    head = e[:6]
    head_ok = head in g[:len(head) + 8] or difflib.SequenceMatcher(
        None, head, g[:len(head) + 4]).ratio() >= 0.5
    return tail_ok and head_ok


def stt_verify(pool, key, cuts, out, pin, book, gmap):
    """모든 컷을 받아 적어 대본과 대조한다. 어긋난 통은 통째로 다시 만든다.

    돌려주는 것: True = 영상으로 가도 된다 / False = 사람이 봐야 한다(렌더링 중단).
    전사 자체가 안 되면(모델 장애·키 없음) **막지 않고** 크게 알린다 —
    '확인 못 함'으로 영상 전체를 세우면 장애 때마다 발이 묶이기 때문이다."""
    if not STT_ON or not key:
        return True
    todo = [c for c in cuts if (c.get("text") or "").strip()
            and (out / f"{c['id']}.mp3").exists()
            and not (out / f"{c['id']}.silent").exists()]
    if not todo:
        return True

    def batches(items):
        """통(take)별로 묶고, 이름표 없는 컷은 10개씩 묶는다."""
        by_sig, solo, order = {}, [], []
        for c in items:
            sig = gmap.get(c["id"])
            if sig:
                if sig not in by_sig:
                    order.append(sig)
                by_sig.setdefault(sig, []).append(c)
            else:
                solo.append(c)
        got = [(sig, by_sig[sig]) for sig in order]
        for i in range(0, len(solo), 10):
            got.append((None, solo[i:i + 10]))
        return got

    def check_batch(sig, group):
        files = [out / f"{c['id']}.mp3" for c in group]
        texts = transcribe_pieces(key, files)
        if texts is None:
            return None
        return [c for c, t in zip(group, texts)
                if not _piece_ok(c.get("text", ""), t)]

    bad, unread = {}, 0
    n_checked = 0
    for sig, group in batches(todo):
        miss = check_batch(sig, group)
        if miss is None:
            unread += len(group)
            continue
        n_checked += len(group)
        if miss:
            bad[sig] = (group, miss)
    if unread:
        print(f"  ⚠️ 받아쓰기 대조: {unread}컷은 전사가 안 돼 확인 못 했다")
    if not bad:
        if n_checked:
            print(f"  받아쓰기 대조: {n_checked}컷 전부 대본과 맞다")
        return True

    for sig, (group, miss) in bad.items():
        print(f"  ⚠️ 받아쓰기 대조: {', '.join(c['id'] for c in miss)} —"
              " 대사의 머리/꼬리가 소리에 없다")

    # ── 자동 수선: 어긋난 통은 **통째로 새로 읽혀** 다시 자른다 ──
    #    (원본 통도 지운다 — 그 통의 소리·자름을 더는 믿을 수 없다.
    #     낱개로 고치면 목소리가 흩어지는 옛 병이 재발한다. 통 값 약 30~60원.)
    still = []
    fixed = 0
    for sig, (group, miss) in bad.items():
        if fixed >= STT_FIX_MAX:
            still += [c["id"] for c in miss]
            continue
        fixed += 1
        sp = group[0].get("speaker", "narrator")
        lines = [(c["id"], c["text"].strip()) for c in group]
        name = "해설" if sp == "narrator" else sp
        print(f"    {name} {lines[0][0]}~{lines[-1][0]} 통을 새로 읽혀 다시 맞춘다"
              f" ({fixed}/{STT_FIX_MAX})")
        for cid, _ in lines:
            (out / f"{cid}.mp3").unlink(missing_ok=True)
            gmap.pop(cid, None)
        if sig:
            (out / f"_master_{sig}.mp3").unlink(missing_ok=True)
        newg = {}
        _one_group(pool, key, sp, lines, out, pin, book, gbook=newg)
        gmap.update(newg)
        # 통으로 못 만든 컷은 낱개로 채운다 (없는 것보다 낫다)
        for c in group:
            p = out / f"{c['id']}.mp3"
            if not p.exists():
                e, m2 = make_one(pool, key, c["text"].strip(), sp, p,
                                 pinned=pin.get(sp))
                if e is None:
                    book[c["id"]] = recipe(sp, m2, c["text"].strip(), way="s1")
        holes = [c["id"] for c in group if not (out / f"{c['id']}.mp3").exists()]
        if holes:
            still += holes                 # 소리 자체를 못 만들었다 — 사람이 봐야 한다
            continue
        miss2 = check_batch(sig, group)
        if miss2 is None:
            print("    다시 만든 통은 전사가 안 돼 확인 못 했다 — 그대로 쓴다")
        elif miss2:
            # ⭐ 마지막 수단 — 그 컷만 **혼자 따로** 만든다.
            #    한 줄만 읽히면 자를 일이 없으므로, 자르기 때문에 문장이 잘리는
            #    일이 원천적으로 불가능하다. 목소리가 그 한 컷만 살짝 달라질 수는
            #    있지만(같은 모델·같은 목소리라 큰 차이는 아니다), **자막에 있는
            #    말이 소리에 없는 것보다는 훨씬 낫다.**
            #    이 길이 있어서 '받아쓰기 대조 때문에 영상이 아예 안 나오는' 일이 없다.
            fixed_alone = []
            for c in miss2:
                pth = out / f"{c['id']}.mp3"
                pth.unlink(missing_ok=True)
                pth.with_suffix(".silent").unlink(missing_ok=True)
                gmap.pop(c["id"], None)
                e, m2 = make_one(pool, key, c["text"].strip(), sp, pth,
                                 pinned=pin.get(sp))
                if e is None:
                    book[c["id"]] = recipe(sp, m2, c["text"].strip(), way="s1")
                    fixed_alone.append(c)
                else:
                    still.append(c["id"])
            if fixed_alone:
                print(f"    {', '.join(c['id'] for c in fixed_alone)} 는"
                      " 그 컷만 혼자 다시 만들었다 (자를 일이 없어 문장이 안 잘린다)")
                miss3 = check_batch(None, fixed_alone)
                if miss3:
                    print(f"    ⚠️ {', '.join(c['id'] for c in miss3)} 는 혼자 만들어도"
                          " 받아쓰기가 안 맞는다 — 전사가 흐린 것으로 보고 그대로 쓴다")

    try:
        (out / "groups.json").write_text(json.dumps(gmap, ensure_ascii=False),
                                         encoding="utf-8")
    except Exception:
        pass
    if still:
        # 여기까지 왔다는 것은 **소리를 아예 못 만든** 컷이 있다는 뜻이다
        # (한도 초과·통신 실패 등). 그 자리는 무음이 되므로 멈추는 편이 낫다.
        print("", file=sys.stderr)
        print(f"오류: {len(still)}컷의 소리를 만들지 못했습니다"
              f" ({', '.join(still[:6])}).", file=sys.stderr)
        print("      그대로 만들면 그 자리에서 소리가 끊깁니다. 렌더링을 멈춥니다.",
              file=sys.stderr)
        return False
    print("  받아쓰기 대조: 수선 후 전부 대본과 맞다")
    return True


def measure_f0(path):
    """목소리 높이(Hz) 중앙값. 못 재면 None.

    자기상관(autocorrelation) — 소리 파형이 자기 자신과 몇 칸 뒤에서 가장 닮았는지를
    보고 한 주기의 길이를 알아내는 방법이다. 그 길이의 역수가 목소리 높이다."""
    try:
        import numpy as np
    except ImportError:
        return None
    tmp = str(path) + ".f0.wav"
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path),
                        "-ac", "1", "-ar", "16000", tmp],
                       check=True, capture_output=True, timeout=60)
        with wave.open(tmp) as f:
            x = np.frombuffer(f.readframes(f.getnframes()), "<i2").astype(float)
    except Exception:
        return None
    finally:
        Path(tmp).unlink(missing_ok=True)
    sr, N, got = 16000, 1024, []
    for i in range(0, max(0, len(x) - N), N // 2):
        fr = x[i:i + N]
        if float(np.sqrt((fr ** 2).mean())) < 400:      # 무음·숨소리는 건너뛴다
            continue
        fr = fr - fr.mean()
        ac = np.correlate(fr, fr, "full")[N - 1:]
        lo, hi = sr // 300, sr // 70                    # 사람 목소리 범위(70~300Hz)
        if hi >= len(ac) or ac[0] <= 0:
            continue
        pk = lo + int(np.argmax(ac[lo:hi]))
        if ac[pk] > 0.3 * ac[0]:
            got.append(sr / pk)
    return float(np.median(got)) if len(got) >= 3 else None


# 인물별 가운뎃값에서 이만큼(반음) 넘게 벗어난 컷만 손본다.
#
# ⚠️ 2026-08-06: 1.0 → 2.0 으로 올렸다. 왜인지 반드시 기억할 것.
#    1.0 으로 뒀더니 **114컷 중 64컷**이 음높이 가공을 거쳤다(실측). 절반이 넘는다.
#    그런데 실제로 잰 자연스러운 흔들림 폭은 ±1.7반음이었다 — 즉 멀쩡한 컷을
#    무더기로 손대고 있었다. 손댄 컷과 안 댄 컷이 섞이면 **가공 흔적의 차이**가
#    새로 생겨, 고치려던 것과 똑같은 문제를 내가 만들어 낸다.
#    이제 잰 값(±1.7반음) 밖으로 나간 것만 손본다.
PITCH_TOL = float(os.environ.get("TTS_PITCH_TOL", "2.0"))

# ⭐⭐ 2026-08-07 손님 명령: **"다른 효과 넣지 말고 그냥 한번에 생성만 하라."**
#
#   왜 이 명령이 나왔나 — 손님이 정확히 짚으셨다.
#     지난 시험에서 H05 는 새로 만들었고 A1-15 는 안 만들었다. 그래서 A1-15 에는
#     **내가 어제 기계로 음을 옮긴 흔적**이 그대로 남았다.
#     손님: "A1-15 만 특정효과가 들어가서 이상해. H05 부분과 A1 부분 목소리가 달라."
#     맞는 말이다. **손댄 컷과 안 댄 컷이 섞이는 것 자체가 목소리를 다르게 만든다.**
#
#   묶어서 한 통에 만들면 그 안에서는 이미 같은 사람이다. 거기에 기계 손질을 더하면
#   고치는 것이 아니라 **새로 어긋나게 만드는 것**이다. 그래서 끈다.
#   벗어난 컷은 손대지 않고 voiceguard 가 이름을 찍어 알려 준다 — 그러면 그 줄만
#   다시 만들면 된다. 소리를 만지는 것보다 다시 만드는 것이 항상 낫다.
PITCH_FIX = os.environ.get("TTS_PITCH_FIX", "0").strip().lower() \
    not in ("", "0", "off", "no", "false")
# 이만큼(반음) 넘게 벗어난 컷은 **음을 옮기기 전에 먼저 다시 읽힌다.**
#   실측(2026-08-06, EP001 해설 64컷): 가운뎃값 83.8Hz 인데 H05 가 136.8Hz —
#   +8.5반음이다. 12반음이 한 옥타브이니 거의 한 옥타브 위, 그냥 다른 사람 목소리다.
#   이런 것은 다시 읽히는 편이 가장 자연스럽다(컷당 약 3원).
PITCH_REDO = float(os.environ.get("TTS_PITCH_REDO", "3.0"))
PITCH_REDO_TRIES = max(0, int(os.environ.get("TTS_PITCH_REDO_TRIES", "2")))
# 한 실행에서 다시 읽힐 수 있는 최대 컷 수(값 폭주 방지).
#   음색 쪽과 달리 여기서는 몫이 떨어져도 **아무 일도 안 일어나지 않는다** —
#   못 읽힌 컷은 아래 ②(공짜 후보정)에서 끝까지 눌러 맞춘다. 그래서 안전하다.
PITCH_MAX_REDO = max(0, int(os.environ.get("TTS_PITCH_MAX_REDO", "4")))


def _pitch_filter(ratio):
    """음높이를 ratio 배로 옮기는 ffmpeg 필터. **길이는 그대로 둔다.**

    두 가지 방법이 있고, 둘은 결과가 아주 다르다.

    rubberband  목소리 굵기(포먼트 — 성대가 아니라 입·목구멍이 만드는 울림)를
                그대로 두고 음높이만 옮긴다. 같은 사람이 낮게 말하는 소리가 된다.
    asetrate    테이프를 느리게 감는 것과 같다. 음높이와 함께 굵기까지 끌려간다.
                그래서 내리면 목소리가 굵다 못해 먹먹해지고, 올리면 얇아진다.

    ⭐ 지금까지 asetrate 만 썼다. 그래서 '음을 많이 옮기면 기계 소리가 난다' 며
       최대 2반음으로 묶어 뒀고, 8.5반음 튄 컷은 손도 못 댔다.
       rubberband 는 우분투 ffmpeg 에 이미 들어 있다(실측 확인: 137Hz→85Hz,
       길이 4.056초 → 4.056초 그대로). 있으면 이쪽을 쓴다."""
    if _has_rubberband():
        return f"rubberband=pitch={ratio:.5f}:formant=preserved"
    return (f"asetrate=24000*{ratio:.5f},aresample=24000,"
            f"atempo={1 / ratio:.5f}")


_RUBBERBAND = None


def _has_rubberband():
    """이 컴퓨터의 ffmpeg 에 rubberband 가 들어 있나. 한 번만 확인하고 기억한다."""
    global _RUBBERBAND
    if _RUBBERBAND is None:
        try:
            r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                               capture_output=True, text=True, timeout=30)
            _RUBBERBAND = " rubberband " in r.stdout
        except Exception:
            _RUBBERBAND = False
    return _RUBBERBAND


def _pitch_max():
    """한 컷을 최대 몇 반음까지 옮겨도 되나. **2반음.**

    ⚠️ 2026-08-06: 12반음(사실상 무제한)에서 2반음으로 되돌렸다. 왜인지 꼭 기억할 것.
       rubberband 가 목소리 굵기를 지켜 주니 크게 옮겨도 된다고 봤다. **틀렸다.**
       실측: H05 를 8.6반음 내렸더니(137Hz → 83Hz) 손님이 듣고
       "그냥 목소리가 기괴하게 들린다" 고 하셨다. 숫자는 맞췄는데 소리를 망친 것이다.
       굵기를 지킨다는 것은 '많이 옮겨도 된다' 는 뜻이 아니다 — 많이 옮기면
       기계로 만진 티가 그대로 난다.

       이제 **사람이 못 알아채는 만큼만** 옮긴다. 그보다 크게 벗어난 컷은
       억지로 끌어내리지 않는다. 다시 읽히거나, 그래도 안 되면
       voiceguard 가 영상 제작을 막고 어느 컷인지 알려준다.
       튀는 목소리보다 **망가진 목소리가 더 나쁘다.**"""
    return float(os.environ.get("TTS_PITCH_MAX", "2.0"))


# ── 음색(얇고 하이톤) 이 튀는 컷 다시 읽히기 ────────────────
#
# ⭐ 손님이 세 번 지적했다: "해설이 중간에 한 번씩 **얇고 하이톤**으로 나온다."
#
#    왜 후보정만으로는 안 되나
#      렌더링에서 저음·고음 균형을 인물 평균 쪽으로 당기지만 **최대 ±4dB** 이다.
#      그보다 크게 벗어난 컷은 억지로 당기면 소리가 뭉개진다.
#      제미나이가 그 한 줄만 다르게 읽어 버린 것이므로 **다시 읽히는 것이 정답**이다.
#      (음높이가 크게 튄 컷을 다시 읽히는 장치가 이미 있다 — 같은 방식이다.)
#
# ⚠️ 값이 든다. 그래서 **한 실행에 최대 MAX_REDO 컷만** 다시 읽는다.
#    중앙값이 잘못 잡혀 64컷을 통째로 다시 읽는 일이 없어야 한다.
TONE_LOW, TONE_HIGH = 300, 3500
TONE_REDO = float(os.environ.get("TTS_TONE_REDO", "2.5"))   # 이만큼(dB) 벗어나면 다시 읽는다
TONE_REDO_TRIES = max(0, int(os.environ.get("TTS_TONE_REDO_TRIES", "2")))
TONE_MAX_REDO = max(0, int(os.environ.get("TTS_TONE_MAX_REDO", "6")))

# ⭐ 2026-08-06 손님 선택: **끈다.** 켜려면 TTS_TIMBRE_RETAKE=1.
#
#    왜 껐나 — 측정으로 판명됐다.
#      · 손님이 세 번 지적한 컷(H05)의 음색 숫자는 **정상**이었다(저음 +0.1, 고음 +0.2).
#        문제는 음색이 아니라 음높이(+8.5반음)였다. 이 장치는 엉뚱한 곳을 고치고 있었다.
#      · 효과도 들쭉날쭉했다. 실측: H04 는 6.4dB→0.8dB 로 좋아졌지만
#        A1-17 은 6.6dB→6.1dB 로 사실상 그대로였다(값만 나갔다).
#      · 값이 계속 나갔다. 누를 때마다 본편 6컷 + 쇼츠 6컷 = 약 35원씩, 매번.
#    음색 보정 자체가 없어지는 것은 아니다 — 렌더링(render.py set_voice_gains)에서
#    저음·고음 균형을 **값 0원으로** 계속 맞춘다. 여기서 끄는 것은 '다시 읽히기' 뿐이다.
TIMBRE_RETAKE = os.environ.get("TTS_TIMBRE_RETAKE", "0").strip().lower() \
    not in ("", "0", "off", "no", "false")


def _mean_db(path, af=""):
    """평균 음량(dB). af 를 주면 그 필터를 건 뒤의 크기를 잰다. 못 재면 None."""
    chain = (af + "," if af else "") + "volumedetect"
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
                            "-af", chain, "-f", "null", "-"],
                           capture_output=True, text=True, timeout=120)
    except Exception:
        return None
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else None


def tone_of(path):
    """그 소리의 (저음 비중, 고음 비중) — 전체 크기 대비 dB. 못 재면 None.

    저음이 낮고 고음이 높을수록 '얇고 하이톤' 으로 들린다."""
    full = _mean_db(path)
    if full is None or full < -60:
        return None
    lo = _mean_db(path, f"lowpass=f={TONE_LOW}")
    hi = _mean_db(path, f"highpass=f={TONE_HIGH}")
    if lo is None or hi is None:
        return None
    return (lo - full, hi - full)


def normalize_timbre(out, cuts, retake=None):
    """음색이 크게 튄 컷을 **같은 목소리로 다시 읽힌다.** (기본값: 꺼짐)

    두 번 실행해도 안전하다 — 살펴본 컷은 timbre.json 에 적어 두고 건너뛴다."""
    if not TIMBRE_RETAKE:
        # 조용히 넘어가지 않는다. 꺼져 있다는 것이 기록에 남아야 나중에 헷갈리지 않는다.
        print("  음색 다시 읽기: 꺼져 있다 (렌더링에서 값 0원으로 보정한다)")
        return
    if not shutil.which("ffmpeg") or retake is None or TONE_REDO_TRIES == 0:
        return
    book = out / "timbre.json"
    try:
        done = json.loads(book.read_text(encoding="utf-8"))
    except Exception:
        done = {}

    by = {}
    for c in cuts:
        cid, sp = c.get("id"), c.get("speaker", "narrator")
        p = out / f"{cid}.mp3"
        if not p.exists() or p.with_suffix(".silent").exists():
            continue
        if not (c.get("text") or "").strip():
            continue
        t = done.get(cid) or tone_of(p)
        if t:
            by.setdefault(sp, []).append((cid, p, float(t[0]), float(t[1])))

    if not by:
        print("  ⚠️ 목소리 음색을 재지 못했다 — 음색 고르기를 건너뛴다")
        return

    redone = budget = 0
    for sp, items in sorted(by.items()):
        if len(items) < 5:                 # 표본이 적으면 중앙값을 못 믿는다
            for cid, _p, lo, hi in items:
                done[cid] = [lo, hi]
            continue
        mlo = statistics.median(x[2] for x in items)
        mhi = statistics.median(x[3] for x in items)
        name = "해설" if sp == "narrator" else sp
        for cid, p, lo, hi in items:
            gap = max(abs(lo - mlo), abs(hi - mhi))
            if cid in done or gap <= TONE_REDO:
                done[cid] = [lo, hi]
                continue
            if budget >= TONE_MAX_REDO:
                print(f"    {cid} 도 음색이 튀지만 이번 실행 몫({TONE_MAX_REDO}컷)을"
                      " 다 써서 넘어간다 — 다음에 다시 누르면 이어서 손본다")
                continue
            why = "얇고 높다" if (lo < mlo and hi > mhi) else "치우쳤다"
            best, best_gap = None, gap
            for _ in range(TONE_REDO_TRIES):
                budget += 1
                if not retake(cid):
                    break
                got = tone_of(p)
                if not got:
                    break
                g2 = max(abs(got[0] - mlo), abs(got[1] - mhi))
                if g2 < best_gap:
                    best, best_gap = got, g2
                if g2 <= TONE_REDO:
                    break
            if best_gap < gap:
                redone += 1
                print(f"    {cid} ({name}) 음색이 {why}(차이 {gap:.1f}dB)"
                      f" → 다시 읽혀 {best_gap:.1f}dB 로 줄였다")
            done[cid] = list(best) if best else [lo, hi]

    try:
        book.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    if redone:
        print(f"  목소리 음색 고르기: {redone}컷을 다시 읽혔다")
    else:
        print(f"  목소리 음색: {sum(len(v) for v in by.values())}컷 다 쟀다 — 크게 튄 것 없음")


def normalize_pitch(out, cuts, retake=None):
    """인물마다 목소리 높이를 **가운뎃값으로 맞춘다.**

    왜 필요한가
        컷 하나하나가 제미나이를 따로 부르는 별개의 호출이라, 같은 모델·같은 목소리를
        지정해도 높이가 호출마다 흔들린다. 실측(2026-08-06, EP001 해설 64컷):
        가운뎃값 83.8Hz, 보통 컷은 ±1.7반음 안인데 **H05 한 컷만 136.8Hz(+8.5반음)** 였다.
        12반음이 한 옥타브이니 거의 한 옥타브 위 — 듣는 사람에게는 그냥 다른 사람이다.

    ⭐ 왜 예전 코드는 이걸 못 잡았나 (2026-08-06 원인 규명 · 같은 실수 반복 금지)
        장치는 이미 있었다. 3반음 넘으면 다시 읽히고 1반음 넘으면 음을 옮기게 돼 있었다.
        그런데 제작 기록에는 `목소리 높이: 114컷 다 쟀다` 뒤로 **고쳤다는 줄이 한 줄도
        없었다.** 재고도 하나도 안 고친 것이다. 이유가 셋이었다.
          ① `pitch.json` 수첩에 한 번 적힌 컷은 `if cid in done: continue` 로
             **파일을 열어보지도 않고 영원히 건너뛰었다.** H05 가 여기 걸렸다.
          ② 게다가 높이를 잴 때도 `done.get(cid) or measure_f0(p)` 로 **수첩의 옛
             숫자를 먼저 썼다.** 소리를 새로 만들어도 옛 숫자로 판단했다.
          ③ 어렵게 통과해도 최대 2반음까지만 옮길 수 있었다. 8.5반음짜리는
             6.5반음이 남아 여전히 다른 사람 목소리다.
        그래서 이렇게 바꿨다.
          ① **수첩을 판단에 쓰지 않는다. 매번 실제 파일을 다시 잰다.**
             (수첩은 '다시 읽히다 실패해서 포기한 컷' 만 적어 둔다 — 그 컷을 매 실행
              다시 읽히면 값만 나가기 때문이다. 판단에는 절대 안 쓴다.)
          ② 손볼 폭 제한을 푼다 — rubberband 는 굵기를 지키므로 크게 옮겨도 된다.
          ③ 많이 튄 컷부터 손본다. 예전 음색 쪽은 컷 번호 순으로 돌다가 몫을 다 써서
             **정작 손님이 지적한 컷에 닿지도 못했다.** 같은 실수를 여기서 반복 안 한다.

    어떻게 (손님 선택 2026-08-06: "다시 읽히고, 안 되면 눌러 맞추기")
        ① 3반음(PITCH_REDO) 넘게 튄 컷은 **그 줄만 새로 읽힌다** (컷당 약 3원).
           가장 많이 튄 컷부터, 한 실행에 최대 PITCH_MAX_REDO 컷까지.
        ② 그러고도 1반음(PITCH_TOL) 넘게 남은 컷은 **음을 옮겨 가운뎃값에 맞춘다.**
           값 0원 — 이미 만들어 둔 파일만 손본다. 길이는 그대로라 자막이 안 밀린다.
        ②가 항상 받쳐 주므로 ①이 실패하든 몫이 떨어지든 **문제가 남지 않는다.**

    두 번 실행해도 안전하다 — 맞춘 컷은 다음 실행에서 가운뎃값으로 측정되어 손대지 않는다."""
    if not shutil.which("ffmpeg"):
        return
    try:
        import numpy  # noqa: F401
    except ImportError:
        # 조용히 넘어가면 목소리가 흔들린 채로 발행된다. 분명히 말한다.
        print("  ⚠️ numpy 가 없어 목소리 높이 고르기를 건너뛴다"
              " (인물 목소리가 컷마다 흔들릴 수 있다)")
        return

    # 수첩 — **판단에는 안 쓴다.** 다시 읽히다 실패해 포기한 컷만 적는다.
    #        (안 적으면 그 컷을 누를 때마다 다시 읽혀 값이 계속 나간다.)
    book = out / "pitch.json"
    try:
        gave_up = json.loads(book.read_text(encoding="utf-8"))
    except Exception:
        gave_up = {}
    if not isinstance(gave_up, dict):
        gave_up = {}
    # 옛 형식({컷: 숫자})은 '괜찮다고 적어 둔 기록' 이라 이제 뜻이 없다 — 버린다.
    gave_up = {k: v for k, v in gave_up.items() if isinstance(v, dict)}

    by_speaker = {}
    tried = 0
    for c in cuts:
        cid, sp = c.get("id"), c.get("speaker", "narrator")
        p = out / f"{cid}.mp3"
        if not p.exists() or p.with_suffix(".silent").exists():
            continue                       # 무음은 잴 것이 없다
        if not (c.get("text") or "").strip():
            continue
        tried += 1
        hz = measure_f0(p)                 # ⭐ 언제나 실제 파일을 다시 잰다
        if hz:
            by_speaker.setdefault(sp, []).append([cid, p, hz])

    # ⭐ **몇 컷을 실제로 쟀는지 반드시 찍는다.**
    #    예전에는 고칠 것이 없어도, 아예 못 재도 **똑같이 아무 말이 없었다.**
    #    그래서 기록만 보고는 '높이는 괜찮았다' 인지 '높이를 안 봤다' 인지
    #    구별할 수 없었다. 실제로 이것 때문에 원인을 한 번 잘못 짚었다.
    got = sum(len(v) for v in by_speaker.values())
    if got < tried:
        print(f"  ⚠️ 목소리 높이: {tried}컷 중 {got}컷만 쟀다"
              f" — 못 잰 {tried - got}컷은 높이 고르기에서 빠진다")
    elif got:
        way = "굵기를 지키며" if _has_rubberband() else "(rubberband 없음 — 최대 2반음만)"
        print(f"  목소리 높이: {got}컷 다 쟀다 {way}")

    if not PITCH_FIX:
        print("  음높이 손대기: 꺼져 있다"
          " (소리를 만지지 않는다 — 벗어난 컷은 목소리 검사가 알려 준다)")
    if not by_speaker:
        return
    import statistics

    def off(hz, mid):
        """가운뎃값에서 몇 반음 벗어났나."""
        return 12.0 * math.log2(hz / mid) if hz > 0 and mid > 0 else 0.0

    limit = _pitch_max()
    redone = fixed = budget = 0
    worst = []

    # ⭐ **인물 순서가 아니라 '얼마나 벗어났는가' 순서로 손본다.**
    #
    #    2026-08-06 실측 사고 — 이번 실행 몫이 4컷인데, 인물 순서대로 돌다가
    #    맨 앞 인물(장남)이 그 4컷을 다 써 버렸다. 그래서 **이 회차에서 가장 많이
    #    벗어난 컷이자 손님이 세 번 지적한 H05(+8.6반음)** 는 다시 읽히지도 못하고
    #    억지로 음만 옮겨져 "기괴한 소리" 가 됐다.
    #    음색 쪽에서 똑같은 실수를 했고 다시는 안 하겠다고 적어 뒀는데, 여기서 또 했다.
    #    이제 **회차 전체에서 가장 심한 컷부터** 몫을 쓴다.
    order = []
    for sp, items in by_speaker.items():
        if len(items) < 3:                 # 표본이 적으면 가운뎃값을 못 믿는다
            continue
        mid0 = statistics.median(h for _, _, h in items)
        order.append((max(abs(off(h, mid0)) for _, _, h in items), sp))
    order.sort(reverse=True)

    for _, sp in order:
        items = by_speaker[sp]
        name = "해설" if sp == "narrator" else sp
        mid = statistics.median(h for _, _, h in items)

        # ── ① 크게 튄 컷은 다시 읽힌다 — **기본: 끔** (PITCH_FIX 켤 때만) ──
        #
        # ⭐ 2026-08-07 실측 사고로 껐다. 왜인지 반드시 기억할 것.
        #   묶어 읽기가 들어온 뒤에는 한 통 안의 컷들이 **이미 같은 사람**이다.
        #   그 안에서 높이가 벌어지는 것은 연기다 — 애원하는 대사는 높고,
        #   차갑게 말하는 대사는 낮다. 배우는 원래 그렇게 읽는다.
        #   그런데 이 장치가 그 '연기 컷' 을 튀었다고 보고 **한 줄씩 따로** 다시
        #   읽혔다. 따로 부르면 다른 사람이 되는 것이 바로 우리가 고친 병이다.
        #   실측: 장남 A3-06 을 따로 다시 읽혔더니 그 컷이 회차 최악(-7.7반음)이 됐다.
        #   고치는 장치가 병을 도로 옮기고 있었다. 값도 매번 나갔다.
        if retake is not None and PITCH_REDO_TRIES and PITCH_FIX:
            for it in sorted(items, key=lambda x: -abs(off(x[2], mid))):
                cid, p, hz = it
                gap = abs(off(hz, mid))
                if gap <= PITCH_REDO:
                    break                  # 정렬돼 있으니 여기서부터는 다 괜찮다
                if cid in gave_up:
                    continue               # 전에 다시 읽혀 봤지만 안 됐다 → ②에 맡긴다
                if budget >= PITCH_MAX_REDO:
                    print(f"    {cid} ({name}) 도 {off(hz, mid):+.1f}반음 튀지만 이번 실행"
                          f" 몫({PITCH_MAX_REDO}컷)을 다 썼다 → 음을 옮겨 맞춘다(0원)")
                    continue
                # ⚠️ 다시 읽히기 전에 **원본을 챙겨 둔다.**
                #    다시 만들기가 실패하면(한도 소진 등) 그 컷이 통째로 사라진다 —
                #    조금 튀는 목소리보다 소리가 아예 없는 것이 훨씬 나쁘다.
                keep = p.with_suffix(".keep")
                shutil.copyfile(p, keep)
                best_hz = None
                for _ in range(PITCH_REDO_TRIES):
                    budget += 1
                    p.unlink(missing_ok=True)
                    if not retake(cid):
                        break
                    fresh = measure_f0(p)
                    if not fresh:
                        break
                    if best_hz is None or abs(off(fresh, mid)) < abs(off(best_hz, mid)):
                        best_hz = fresh
                    if abs(off(fresh, mid)) <= PITCH_TOL:
                        break
                if not p.exists() or best_hz is None or \
                        abs(off(best_hz, mid)) >= abs(off(hz, mid)):
                    keep.replace(p)                    # 원본이 그나마 낫다 → 되돌린다
                    gave_up[cid] = {"hz": round(hz, 1)}
                    print(f"    {cid} ({name}) {hz:.0f}Hz({off(hz, mid):+.1f}반음) —"
                          f" 다시 읽혀도 나아지지 않았다 → 음을 옮겨 맞춘다(0원)")
                    continue
                keep.unlink(missing_ok=True)
                redone += 1
                print(f"    {cid} ({name}) {hz:.0f}Hz({off(hz, mid):+.1f}반음) 로 크게 튀어"
                      f" 다시 읽혔다 → {best_hz:.0f}Hz({off(best_hz, mid):+.1f}반음)")
                if abs(off(best_hz, mid)) > PITCH_REDO:
                    gave_up[cid] = {"hz": round(best_hz, 1)}   # 아직 크다 → 그만 부른다
                it[2] = best_hz
            mid = statistics.median(h for _, _, h in items)

        # ── ② 남은 흔들림은 음을 옮겨 가운뎃값에 맞춘다 (기본: 끔) ──
        if not PITCH_FIX:
            continue
        for cid, p, hz in items:
            semitone = off(hz, mid)
            if abs(semitone) <= PITCH_TOL:
                continue                   # 사람이 못 느끼는 차이다. 손대면 손해다
            if abs(semitone) > PITCH_TOL + limit:
                # ⭐ 너무 많이 벗어났다 → **손대지 않는다.**
                #    2반음만 끌어내려 봐야 여전히 튀고, 기계로 만진 티만 더해진다.
                #    (실측: 8.6반음짜리를 억지로 옮겼더니 "기괴하다" 는 말을 들었다)
                #    이런 컷은 voiceguard 가 잡아 영상 제작 자체를 막는다.
                print(f"    ⚠️ {cid} ({name}) {hz:.0f}Hz({semitone:+.1f}반음) —"
                      " 너무 많이 벗어나 손대지 않는다 (억지로 옮기면 소리가 망가진다)")
                continue
            move = max(-limit, min(limit, -semitone))
            ratio = 2 ** (move / 12.0)
            tmp = p.with_suffix(".fix.mp3")
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error", "-i", str(p),
                     "-af", _pitch_filter(ratio), "-b:a", "160k", str(tmp)],
                    check=True, timeout=120)
                tmp.replace(p)
                fixed += 1
                worst.append((abs(semitone), cid, name, hz, hz * ratio))
            except Exception:
                tmp.unlink(missing_ok=True)
                print(f"    ⚠️ {cid} ({name}) 음 옮기기에 실패했다 — 그대로 둔다")

    if redone:
        print(f"  목소리가 크게 튄 {redone}컷을 다시 읽혔다")
    if fixed:
        print(f"  목소리 높이 고르기: {fixed}컷을 가운뎃값 쪽으로 옮겼다")
        for gap, cid, name, a, b in sorted(worst, reverse=True)[:3]:
            print(f"    {cid} ({name}) {a:.0f}Hz → {b:.0f}Hz ({gap:.1f}반음 옮김)")
    if not redone and not fixed and got:
        print("  목소리 높이: 가운뎃값에서 1반음 넘게 벗어난 컷이 없다 — 손댈 것 없음")
    try:
        book.write_text(json.dumps(gave_up, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def silent(out_mp3, sec, marker=True):
    """무음 파일. **ffmpeg 를 부르지 않는다.**

    여기는 '음성 생성이 실패했을 때 가는 길' 이다. 그 길에서 또 외부 프로그램을
    부르면, ffmpeg 가 없는 환경에서는 대체 경로마저 죽어 실행 전체가 무너진다.
    실제로 그렇게 죽었다 — FileNotFoundError: 'ffmpeg'.

    확장자는 .mp3 이지만 내용은 WAV 다. ffmpeg·ffprobe 는 확장자가 아니라
    내용을 보고 형식을 판별하므로 render.py 가 그대로 읽는다(실측 확인함).

    marker — 대사가 없어 일부러 비운 컷은 False. 실패해서 때운 컷은 True 로 두어
             다음 실행에서 다시 시도하게 한다."""
    rate = 24000
    frames = max(1, int(rate * max(0.2, float(sec))))
    pcm_to_wav(b"\x00\x00" * frames, out_mp3, rate=rate)      # 16비트 mono 의 0 = 무음
    mark = out_mp3.with_suffix(".silent")
    if marker:
        mark.write_text("1", encoding="utf-8")
    else:
        mark.unlink(missing_ok=True)
    return out_mp3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--out", default="build/voice")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", default="",
                    help="이 컷들만 만든다(쉼표로 구분). 시연 영상 만들 때 쓴다")
    ap.add_argument("--silent", action="store_true", help="모델을 부르지 않고 무음만 만든다")
    ap.add_argument("--shorts", action="store_true",
                    help="쇼츠 대본({대본}.shorts.json)의 나레이션을 만든다")
    args = ap.parse_args()

    # 없으면 여기서 분명히 말하고 멈춘다. 한참 뒤에 죽는 것보다 낫다.
    # 다만 --silent 는 외부 프로그램이 전혀 필요 없으므로 막지 않는다.
    if not args.silent:
        need_ffmpeg()

    # 연기 지시가 다시 '감정 빼기' 로 돌아가지 않았는지 — 돈 쓰기 전에 본다.
    try:
        check_style()
    except LLMError as e:
        print("", file=sys.stderr)
        print(f"오류: {e}", file=sys.stderr)
        return 1

    sp = Path(args.script)
    doc = json.loads(sp.read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.shorts:
        # 쇼츠는 본편과 **대사가 다르다.** 세로 화면에 맞춰 짧게 다시 쓰기 때문이다.
        #   본편 H01 "어머니, 제가 받을 몫이 비잖아요. 법대로 하시죠."
        #   쇼츠 S1-01 "어머니, 법대로 하시죠."
        # 본편 음성을 그대로 붙이면 자막과 소리가 어긋난다. 따로 만들어야 한다.
        shp = sp.parent / (sp.stem + ".shorts.json")
        if not shp.exists():
            print(f"쇼츠 대본이 없다: {shp}")
            return 2
        sh = json.loads(shp.read_text(encoding="utf-8"))
        # ⭐ 편 번호를 붙인다 — 한 통이 **여러 편에 걸치지 않게** 하려는 것이다
        #    (위 plan_groups 의 _grp 설명 참조)
        cuts = [dict(c, _grp=i) for i, s_ in enumerate(sh.get("shorts", []))
                for c in (s_.get("cuts") or [])]
        cuts = [c for c in cuts if c.get("id")]
        print(f"쇼츠 대본의 나레이션 {len(cuts)}컷을 만든다")
    else:
        cuts = [c for a in doc["acts"] for c in a["cuts"]]
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        cuts = [c for c in cuts if c.get("id") in want]
        print(f"고른 {len(cuts)}컷만 만든다 (--only)")
    if args.limit:
        cuts = cuts[:args.limit]
        print(f"앞 {len(cuts)}컷만 만든다 (--limit {args.limit})")

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = None
    all_models = []
    pick_err = None
    if not args.silent and key:
        try:
            all_models = tts_models(key)
            model = all_models[0] if all_models else None
        except Exception as e:
            pick_err = e
            print(f"모델 목록 조회 실패: {e}")

    if not model:
        # ⚠️ '일부러 무음' 과 '실패해서 무음' 을 가른다.
        #    키는 있는데 조회가 실패한 것(429·일시 장애)까지 무음으로 넘기면,
        #    12분 내내 소리 없는 영상이 '성공' 으로 유튜브에 올라간다.
        #    아래 실패율 검사보다 위에 있는 경로라, 여기서 막지 않으면 검사가 아예 안 돈다.
        if pick_err is not None:
            print("", file=sys.stderr)
            print(f"오류: 음성 모델 목록을 받지 못했습니다 — {pick_err}", file=sys.stderr)
            print("      흔한 원인: 제미나이 API 사용량 한도 초과(429), 결제 미등록.", file=sys.stderr)
            print("      소리 없이 화면만 확인하려면 나레이션을 '무음으로 시험' 으로", file=sys.stderr)
            print("      고른 뒤 다시 실행하십시오.", file=sys.stderr)
            return 1
        why = "GEMINI_API_KEY 가 없다" if not key else "쓸 수 있는 음성 모델이 없다"
        if args.silent:
            why = "--silent 지정"
        print(f"⚠️ 무음으로 만든다 ({why}).")
        print("   자막이 상시 노출이라 파이프라인은 끝까지 돌지만, 발행 전에 반드시 음성을 넣어야 한다.")
        for c in cuts:
            # 의도한 무음이다. 표시를 남기지 않는다 — 다시 시도할 것이 아니다.
            silent(out / f"{c['id']}.mp3", float(c.get("sec", 6.0)) - 0.6, marker=False)
        print(f"무음 {len(cuts)}개 생성: {out}")
        return 0

    cooldowns = 0
    pool = ModelPool(all_models or [model])
    cheap = [m for m in pool.models if pool.tier[m] == 0]
    spare = [m for m in pool.models if pool.tier[m] != 0]
    print(f"음성 모델 {len(pool.models)}개 — 싼 것부터 쓴다")
    print(f"  주력(flash) {len(cheap)}개: {' · '.join(cheap) or '없음'}")
    if spare:
        print(f"  예비(pro)  {len(spare)}개: {' · '.join(spare)}"
              "  ← 주력이 한도에 막혔을 때만 나선다")
    print(f"  모델당 분당 {PER_MODEL_RPM}회 (실측 한도 10) → 주력만으로 분당 "
          f"약 {PER_MODEL_RPM * max(1, len(cheap))}회")

    # ⭐ 인물마다 모델을 **못 박는다.** 같은 목소리 이름이라도 모델이 다르면
    #    다른 사람으로 들린다(실측 113~157Hz). 여기서 정한 짝은 끝까지 안 바뀐다.
    speakers = sorted({c.get("speaker", "narrator") for c in cuts})
    try:
        pin = pin_models(speakers, cheap or pool.models)
    except NarratorModelMissing as e:
        # 여기서 멈추는 편이 낫다. 딴 목소리로 만들어 놓으면 손님이 영상을 보고
        # 다시 만들라고 할 텐데, 그때 값이 두 번 나간다.
        print("", file=sys.stderr)
        print(f"오류: {e}", file=sys.stderr)
        return 1
    print("  인물별 고정 목소리 —")
    for s in speakers:
        print(f"    {s:10s} {VOICE_NAME.get(s, 'Charon'):10s} {pin.get(s, '?')}")
    # 지난 실행에서 다른 설정으로 만든 음성이 섞이지 않게 지운다.
    book = prune_stale(out, cuts, pin)

    # ⭐ 시작 전에 열쇠를 한 번 두드려 본다.
    #    실측: 열쇠가 막힌 상태로 시작해 **30분을 버리고** 실패했다(114컷 중 22컷).
    #    한 컷만 미리 만들어 보면 10초 안에 알 수 있고, 그 한 컷도 버리지 않고 쓴다.
    #    실패해도 여기서 멈추지는 않는다 — 아래 본 순환이 모델 갈아타기·쉬었다 하기를
    #    이미 하므로, 여기서는 **원인만 분명히 찍고** 넘긴다.
    probe = next((c for c in cuts
                  if (c.get("text") or "").strip()
                  and not (out / f"{c['id']}.mp3").exists()), None)
    if probe is not None:
        # ⚠️ 여기서도 **그 인물에게 못 박힌 모델**을 써야 한다.
        #    예전에는 아무 모델이나 썼다. 그래서 그 한 컷만 다른 목소리로 만들어져,
        #    영상에서 딱 한 번 목소리가 튀었다(실측: 장남 첫 대사만 125Hz, 나머지 99~112Hz).
        #    손님이 지적한 "중간에 목소리가 바뀐다" 가 바로 이것이다.
        pspeak = probe.get("speaker", "narrator")
        err, used = make_one(pool, key, probe["text"].strip(), pspeak,
                             out / f"{probe['id']}.mp3", tries=1,
                             pinned=pin.get(pspeak))
        if err is None:
            print(f"  열쇠 확인: 정상 ({used})")
            # ⭐ 묶어서 읽힐 때는 **이 한 컷을 버린다.**
            #    이것만 혼자 만들어진 컷이라, 같은 인물의 나머지 줄과 목소리가 다르다.
            #    바로 위 설명에 적힌 사고("첫 대사만 125Hz")와 똑같은 일이 된다.
            #    한 번 더 부르는 값(약 3원)이 들지만, 첫 대사가 튀는 것보다 훨씬 낫다.
            if GROUP_ON:
                (out / f"{probe['id']}.mp3").unlink(missing_ok=True)
            else:
                book[probe["id"]] = recipe(pspeak, used, probe.get("text") or "",
                                           way="s1")
        else:
            note = quota_note(err.__cause__ if err.__cause__ is not None else err)
            print(f"  ⚠️ 열쇠 확인 실패({type(err).__name__})"
                  + (f" — {note}" if note else ""))
            (out / f"{probe['id']}.mp3").unlink(missing_ok=True)

            # ⭐ **하루 몫이 끝났으면 여기서 멈춘다.**
            #    예전에는 그대로 114컷을 돌았다. 전부 무음으로 때워지는데도 컷마다
            #    기다리느라 30분 넘게 돌다가, 소리가 절반 빈 영상이 나왔다.
            #    남은 모델까지 한 번씩 두드려 보고, 전부 막혔으면 **언제 풀리는지**
            #    분 단위로 알려주고 끝낸다. 다시 눌러야 할 시각을 알 수 있어야 한다.
            if _daily_dead(err):
                wait = _all_models_dead(key, pool)
                if wait is not None:
                    print("", file=sys.stderr)
                    print("오류: 오늘 쓸 수 있는 음성 생성량을 다 썼습니다.", file=sys.stderr)
                    print(f"      약 {max(1, round(wait / 60))}분 뒤에 한도가 초기화됩니다."
                          " 그때 다시 실행하십시오.", file=sys.stderr)
                    print("      (모델별 하루 한도 — flash 100회씩, pro 50회."
                          " 한 편에 약 144회가 듭니다)", file=sys.stderr)
                    return 1
            print("     GEMINI_API_KEY 가 결제 걸린 프로젝트의 열쇠인지 확인하십시오.")

    # ⭐ **먼저 묶어서 한 번에 읽힌다.** 이것이 목소리를 하나로 유지하는 뿌리 해결이다.
    #    실패한 묶음은 아무것도 안 남기므로, 바로 아래 '컷마다 만들기' 가 그 컷들을
    #    예전 방식으로 채운다. 어떤 경우에도 영상은 온전하다.
    gbook = {}      # 이번 실행이 만든 컷 → 어느 통에서 나왔나 (groups.json 재료)
    try:
        make_groups(pool, key, cuts, out, pin, book, gbook)
    except Exception as e:                 # 여기서 죽으면 음성이 통째로 안 나온다
        print(f"  ⚠️ 한 번에 읽히기가 실패했다({type(e).__name__}) — 컷마다 따로 만든다")

    ok = fail = 0
    streak = 0
    used = {}             # 모델별로 몇 컷을 만들었나 (골고루 갔는지 눈으로 확인)
    switched = set()      # 도중에 모델이 바뀐 인물 — 끝나고 통째로 다시 만든다
    quota_shown = False   # '어떤 한도인지' 는 한 번만 찍는다
    for i, c in enumerate(cuts):
        p = out / f"{c['id']}.mp3"
        if p.exists():
            if p.with_suffix(".silent").exists():
                # 지난 실행에서 실패해 무음으로 때운 컷이다. 성공으로 세면 안 된다 —
                # 그러면 실패율 검사가 꺼져 절반이 무음인 영상이 통과한다. 지우고 다시 한다.
                p.unlink()
                p.with_suffix(".silent").unlink(missing_ok=True)
            else:
                ok += 1
                continue
        text = (c.get("text") or "").strip()
        if not text:
            silent(p, 1.0, marker=False)     # 대사 없는 컷 — 의도된 무음이라 실패가 아니다
            ok += 1
            continue
        # ⭐ 이 인물에게 못 박힌 모델로만 만든다. 한도에 걸려도 갈아타지 않고 기다린다.
        speaker = c.get("speaker", "narrator")
        err, _used = make_one(pool, key, text, speaker, p, pinned=pin.get(speaker))

        if err is not None and not pool.alive() and cooldowns < MAX_COOLDOWNS:
            # 모든 모델이 막혔다. 실측해 보니 잠시 뒤 다시 열리는 경우가 있다.
            # 사람이 없는 GitHub Actions 실행에서 그냥 멈추면 그 회차는 그대로 끝난다.
            cooldowns += 1
            print(f"  모든 음성 모델이 막혔다 — {COOLDOWN_SEC}초 쉬었다 다시 한다"
                  f" ({cooldowns}/{MAX_COOLDOWNS})")
            time.sleep(COOLDOWN_SEC)
            pool = ModelPool(all_models)
            err, _used = make_one(pool, key, text, speaker, p, pinned=pin.get(speaker))

        if err is None:
            ok += 1
            streak = 0
            used[_used] = used.get(_used, 0) + 1
            book[c["id"]] = recipe(speaker, _used, text, way="s1")
            if _used != pin.get(speaker):
                # 못 박은 모델이 죽어 다른 모델로 만들어졌다. 그대로 두면 이 인물
                # 목소리가 도중에 바뀐다 — 아래에서 이 인물 컷을 전부 다시 만든다.
                print(f"  ⚠️ {speaker} 가 {pin.get(speaker)} → {_used} 로 바뀌었다")
                pin[speaker] = _used
                switched.add(speaker)
        else:
            src = err.__cause__ if err.__cause__ is not None else err
            if not quota_shown:
                note = quota_note(src)
                if note:
                    print(f"      걸린 한도: {note}")
                    quota_shown = True
            fail += 1
            streak += 1
            print(f"  {c['id']} 실패({type(err).__name__}) → 무음으로 대체")
            silent(p, float(c.get("sec", 6.0)) - 0.6)
            if streak >= MAX_FAIL_STREAK:
                # 할당량이 끝난 것을 113컷 내내 확인할 필요가 없다.
                # 컷마다 최대 150초를 기다리므로 끝까지 가면 작업 시간 제한에 걸려
                # 통째로 취소된다 — 그러면 아래 실패율 검사도 못 돈다.
                print("", file=sys.stderr)
                print(f"오류: {streak}컷 연속으로 음성 생성에 실패했습니다. 여기서 멈춥니다.",
                      file=sys.stderr)
                print("      한 컷마다 최대 150초를 기다리므로, 끝까지 가면", file=sys.stderr)
                print("      작업 시간 제한(180분)에 걸려 통째로 취소됩니다.", file=sys.stderr)
                print("      흔한 원인: 제미나이 API 사용량 한도 초과, 결제 미등록.", file=sys.stderr)
                print(f"      (성공 {ok} · 실패 {fail} · 남은 컷 {len(cuts) - i - 1})",
                      file=sys.stderr)
                return 1
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(cuts)}  (성공 {ok} · 실패 {fail})")

    # ⭐ 도중에 모델이 바뀐 인물은 **그 인물 컷을 전부 다시 만든다.**
    #    앞부분과 뒷부분이 다른 목소리로 남으면, 손님이 지적한 바로 그 증상
    #    ("중간에 장남 목소리가 여자로 바뀐다")이 그대로 나온다.
    for sp in sorted(switched):
        mine = [c for c in cuts
                if c.get("speaker", "narrator") == sp and (c.get("text") or "").strip()]
        stale = [c for c in mine
                 if book.get(c["id"]) not in (
                     recipe(sp, pin[sp], c.get("text") or ""),
                     recipe(sp, pin[sp], c.get("text") or "", way="s1"))]
        if not stale:
            continue
        print(f"  {sp} 목소리를 {pin[sp]} 로 통일한다 — {len(stale)}컷 다시 만듦")
        for c in stale:
            p = out / f"{c['id']}.mp3"
            # ⚠️ 원본을 챙겨 두고 지운다. 다시 만들기가 실패하면 되돌린다 —
            #    목소리가 조금 다른 것보다 그 자리가 무음이 되는 것이 훨씬 나쁘다.
            keep = p.with_suffix(".keep") if p.exists() else None
            if keep:
                shutil.copyfile(p, keep)
            p.unlink(missing_ok=True)
            p.with_suffix(".silent").unlink(missing_ok=True)
            err, m2 = make_one(pool, key, c["text"].strip(), sp, p, pinned=pin[sp])
            if err is None:
                book[c["id"]] = recipe(sp, m2, c.get("text") or "", way="s1")
                if keep:
                    keep.unlink(missing_ok=True)
            elif keep:
                keep.replace(p)                # 예전 음성이라도 살려 둔다
            else:
                silent(p, float(c.get("sec", 6.0)) - 0.6)

    # ⭐ 컷마다 '어느 통에서 나왔는지' 를 남기고, 해설 통끼리 높이를 맞춘다.
    #    2026-08-08: 검사기가 통 하나 높았던 해설(폭 5.1반음)을 막아 실행이
    #    실패했다. 여기서 미리 재고, 벌어진 통만 소액으로 다시 읽혀 맞춘다.
    gmap = {}
    try:
        gmap = map_groups(cuts, out, pin, gbook)
        align_narrator(pool, key, cuts, out, pin, book, gmap)
    except Exception as e:
        print(f"  ⚠️ 해설 통 맞추기를 건너뛴다({type(e).__name__})")

    # ⭐ 받아쓰기 대조 — 자막에 있는 문장이 소리에도 다 있는지 **내용으로** 확인.
    #    어긋난 통은 여기서 다시 만들고, 그래도 안 맞으면 렌더링 전에 멈춘다.
    stt_ok = True
    try:
        stt_ok = stt_verify(pool, key, cuts, out, pin, book, gmap)
    except Exception as e:
        print(f"  ⚠️ 받아쓰기 대조를 건너뛴다({type(e).__name__})")

    try:
        (out / "recipe.json").write_text(json.dumps(book, ensure_ascii=False),
                                         encoding="utf-8")
    except Exception:
        pass
    if not stt_ok:
        return 1                # 조리법·이름표는 적어 뒀다 — 보관함은 그대로 산다

    # ⭐ 마지막으로 인물마다 목소리 높이를 고른다. 같은 모델·같은 목소리인데도
    #    대사 감정에 따라 24Hz 씩 흔들려(실측) 같은 사람으로 안 들리기 때문이다.
    by_id = {c["id"]: c for c in cuts}

    def retake(cid):
        """크게 튄 컷을 **같은 모델·같은 목소리로** 다시 읽힌다."""
        c = by_id.get(cid)
        if c is None:
            return False
        sp = c.get("speaker", "narrator")
        e, m2 = make_one(pool, key, (c.get("text") or "").strip(), sp,
                         out / f"{cid}.mp3", tries=1, pinned=pin.get(sp))
        if e is None:
            book[cid] = recipe(sp, m2, (c.get("text") or "").strip(), way="s1")
            return True
        return False

    normalize_pitch(out, cuts, retake=retake)
    normalize_timbre(out, cuts, retake=retake)
    try:
        (out / "recipe.json").write_text(json.dumps(book, ensure_ascii=False),
                                         encoding="utf-8")
    except Exception:
        pass

    print(f"음성 {ok}개 · 실패 {fail}개 → {out}")
    if used:
        # 한쪽 모델만 두들기면 다시 429 가 난다. 골고루 갔는지 여기서 바로 보인다.
        print("  모델별: " + " · ".join(f"{m} {n}컷" for m, n in used.items()))
    # ⭐ 값을 찍는다. 재사용이 잘 되고 있는지 이 한 줄로 바로 보인다.
    reused = ok - SPEND.calls
    print(f"  💰 {SPEND.line()}")
    if reused > 0:
        print(f"     (만들어 둔 음성 {reused}컷을 그대로 다시 썼다 — 그만큼 값이 안 나갔다)")

    # 소리가 자주 끊기면 그것은 "영상이 나왔다" 가 아니라 "음성이 실패했다" 이다.
    # 예전에는 여기서 0 을 돌려줘서, 소리 없는 영상이 성공으로 올라갈 수 있었다.
    total = ok + fail
    if total and (ok / total) < MIN_OK_RATIO:
        print("", file=sys.stderr)
        print(f"오류: {total}컷 중 {fail}컷이 음성 생성에 실패했습니다 "
              f"(성공률 {ok / total:.0%}, 기준 {MIN_OK_RATIO:.0%}).", file=sys.stderr)
        print("      이대로 만들면 중간중간 소리가 끊기는 영상이 됩니다.", file=sys.stderr)
        print("      흔한 원인: 제미나이 API 사용량 한도 초과, 또는 결제 미등록.", file=sys.stderr)
        print("      소리 없이 화면만 확인하려면 나레이션을 '무음으로 시험' 으로", file=sys.stderr)
        print("      고른 뒤 다시 실행하십시오.", file=sys.stderr)
        return 1
    if fail:
        print("⚠️ 실패한 컷은 무음이다. 그 자리에서 소리가 끊긴다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
