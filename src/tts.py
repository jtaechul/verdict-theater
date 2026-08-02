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
import json
import math
import os
import shutil
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

# 인물 코드 → 목소리 성격. 실제 음성 이름은 API가 주는 목록에서 고른다.
# 뒤 숫자는 **재생 배속**이다. 1.0 보다 크면 빠르게(음높이는 그대로).
#
# ⚠️ 예전 값은 1.0 / 0.92 / 0.90 이었다. 제미나이 TTS 기본 속도 자체가 느린데
#    거기서 더 늦춰 놓아, 사용자가 "목소리가 너무 느리다"고 했다.
#    같은 이유로 실제 영상이 대본 설계보다 본편 +7%, 쇼츠 +14~17% 길어졌다.
#    배속을 올리면 두 문제가 함께 풀린다 — 말이 자연스러워지고 길이도 규격에 맞는다.
#    노인·재판장은 원래 느린 것이 배역이므로 1.0 까지만 올린다.
VOICE_STYLE = {
    "narrator": ("차분하고 낮은 해설 목소리로, 담담하게", 1.12),
    "v_F50A":   ("60대 여성. 지치고 따뜻한 목소리로", 1.12),
    "v_F50B":   ("50대 여성. 차갑고 또박또박", 1.12),
    "v_M50A":   ("50대 남성. 사무적이고 냉랭하게", 1.12),
    "v_M50B":   ("50대 남성. 무심하게", 1.12),
    "v_F70":    ("70대 여성. 힘없고 느리게", 1.00),
    "v_M70":    ("70대 남성. 쉰 목소리로 느리게", 1.00),
    "v_JUDGE":  ("재판장. 무겁고 절제된 목소리로 또박또박", 1.00),
}

# Gemini TTS 목소리 이름. **인물마다 서로 다른 이름이어야 한다.**
#
# ⚠️ 예전에는 나레이터와 재판장이 **둘 다 Charon** 이었다. 해설과 판결 선고가
#    똑같은 목소리로 나와, 누가 말하는지 소리로는 구분되지 않았다.
#    실측(같은 대사·같은 모델로 목소리 높이를 잼):
#      Charon 106Hz · Algieba 85Hz · Enceladus 116Hz · Iapetus 131Hz
#      Orus 136Hz · Fenrir 114Hz · Rasalgethi 115Hz
#    재판장은 가장 낮은 Algieba 로 옮겼다 — 나레이터와 21Hz 벌어져 확실히 구분되고,
#    낮고 무거운 목소리가 배역에도 맞는다.
VOICE_NAME = {
    "narrator": "Charon", "v_F50A": "Aoede", "v_F50B": "Leda",
    "v_M50A": "Puck", "v_M50B": "Orus", "v_F70": "Kore",
    "v_M70": "Fenrir", "v_JUDGE": "Algieba",
}


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

def recipe(speaker, model):
    """이 컷을 '무엇으로 만들었는지' 한 줄. 하나라도 다르면 다시 만들어야 한다."""
    voice = VOICE_NAME.get(speaker, "Charon")
    _, speed = VOICE_STYLE.get(speaker, VOICE_STYLE["narrator"])
    return f"{model}|{voice}|{speed:.2f}"


# 등장인물(대사)에 쓸 모델의 **선호 순서**. 목록 순서가 아니라 이 순서를 따른다.
#
# ⚠️ 왜 이름을 박아 두나 — 자동 정렬에 맡기면 모델이 하나 추가되는 것만으로
#    다음 회차 인물 목소리가 통째로 달라진다. 실측으로 고른 순서를 적어 둔다.
#    같은 목소리(Puck)로 "50대 남성" 대사를 읽혔을 때:
#      gemini-2.5-flash-preview-tts  122Hz  ← 50대 남성으로 들린다
#      gemini-3.1-flash-tts-preview  157Hz  ← 너무 높다. 여자로 들릴 수 있다
#    그래서 대사는 2.5-flash 를 먼저 쓰고, 나레이터에게 나머지를 준다.
CHAR_MODEL_ORDER = ["gemini-2.5-flash-preview-tts", "gemini-3.1-flash-tts-preview"]


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
    어색하지 않지만, 등장인물은 나이·성별이 정해져 있어 어긋나면 바로 들킨다."""
    if not models:
        return {}
    order = _pref(models)
    pin = {}
    rest = [s for s in speakers if s != "narrator"]
    if "narrator" in speakers and len(order) > 1:
        pin["narrator"] = order[-1]            # 나레이터는 뒤쪽 모델
        others = order[:-1]
    else:
        if "narrator" in speakers:
            pin["narrator"] = order[0]         # 모델이 하나뿐 — 같이 쓸 수밖에 없다
        others = order
    for i, s in enumerate(sorted(rest)):
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
    killed = 0
    for c in cuts:
        cid = c.get("id")
        p = out / f"{cid}.mp3"
        if not p.exists():
            continue
        speaker = c.get("speaker", "narrator")
        want = recipe(speaker, pin.get(speaker, ""))
        if old.get(cid) != want:
            p.unlink()
            p.with_suffix(".silent").unlink(missing_ok=True)
            old.pop(cid, None)
            killed += 1
    if killed:
        print(f"  지난 실행의 음성 {killed}컷이 지금 설정과 달라 지웠다 — 그 컷만 다시 만든다")
        book.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
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


def synth_one(key, model, text, speaker, out_mp3, rotate=False):
    style, speed = VOICE_STYLE.get(speaker, VOICE_STYLE["narrator"])
    voice = VOICE_NAME.get(speaker, "Charon")
    prompt = f"{style} 읽어라. 다른 말을 덧붙이지 말고 다음 문장만 읽어라:\n{text}"

    res = _post_retry(f"{BASE}/models/{model}:generateContent?key={key}", {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
            },
        },
    }, timeout=180, label=speaker, rotate=rotate)

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
    for _ in range(tries):
        if not pool.alive():
            break
        model = (pool.wait_for(pinned) or pool.acquire()) if pinned else pool.acquire()
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


# 인물별 중앙값에서 이만큼(반음) 넘게 벗어난 컷만 손본다. 그 이하는 사람이 못 느낀다.
PITCH_TOL = float(os.environ.get("TTS_PITCH_TOL", "1.0"))
# 손보더라도 이 이상은 절대 안 옮긴다. 많이 옮기면 목소리가 기계처럼 변한다.
PITCH_MAX = float(os.environ.get("TTS_PITCH_MAX", "2.0"))
# 이만큼(반음) 넘게 벗어난 컷은 **음을 옮기지 않고 다시 만든다.**
#   실측: 장남 대사 하나가 174Hz 로 나왔다(다른 대사는 110Hz 안팎). 62Hz 차이다.
#   이런 것은 억지로 내리면(최대 2반음) 155Hz 에 그쳐 여전히 튀고, 소리도 뭉개진다.
#   모델에게 그 한 줄만 다시 읽히면 대개 제 높이로 나온다 — 한 번 부르는 값이면 된다.
PITCH_REDO = float(os.environ.get("TTS_PITCH_REDO", "3.0"))
PITCH_REDO_TRIES = max(0, int(os.environ.get("TTS_PITCH_REDO_TRIES", "2")))


def normalize_pitch(out, cuts, retake=None):
    """인물마다 목소리 높이를 **중앙값으로 맞춘다.**

    왜 필요한가
        같은 모델·같은 목소리인데도 대사의 감정에 따라 높이가 흔들린다
        (실측: 장남 6개 대사가 108~132Hz, 폭 24Hz). 대화 중에 이만큼 오르내리면
        같은 사람으로 안 들린다. 지시문으로는 안 잡혔다(폭 23Hz — 차이 없음).

    어떻게
        컷마다 높이를 재고, 그 인물의 중앙값에서 반음(PITCH_TOL) 넘게 벗어난 것만
        중앙값 쪽으로 끌어당긴다. 최대 2반음까지만 — 그 이상 옮기면 기계 소리가 난다.
        ffmpeg 의 asetrate 로 음을 옮기고 atempo 로 길이를 되돌려, **길이는 그대로**다.
        (길이가 변하면 자막·컷 길이와 어긋난다.)

    두 번 실행해도 안전하다 — 손본 컷은 pitch.json 에 적어 두고 건너뛴다."""
    if not shutil.which("ffmpeg"):
        return
    try:
        import numpy  # noqa: F401
    except ImportError:
        # 조용히 넘어가면 목소리가 흔들린 채로 발행된다. 분명히 말한다.
        print("  ⚠️ numpy 가 없어 목소리 높이 고르기를 건너뛴다"
              " (인물 목소리가 컷마다 흔들릴 수 있다)")
        return
    book = out / "pitch.json"
    done = {}
    try:
        done = json.loads(book.read_text(encoding="utf-8"))
    except Exception:
        done = {}

    by_speaker = {}
    for c in cuts:
        cid, sp = c.get("id"), c.get("speaker", "narrator")
        p = out / f"{cid}.mp3"
        if not p.exists() or p.with_suffix(".silent").exists():
            continue                       # 무음은 잴 것이 없다
        if not (c.get("text") or "").strip():
            continue
        hz = done.get(cid) or measure_f0(p)
        if hz:
            by_speaker.setdefault(sp, []).append((cid, p, hz))

    if not by_speaker:
        return
    import statistics

    def off(hz, mid):
        """중앙값에서 몇 반음 벗어났나."""
        return 12.0 * math.log2(hz / mid) if hz > 0 and mid > 0 else 0.0

    redone = fixed = 0
    for sp, items in by_speaker.items():
        if len(items) < 3:                 # 표본이 적으면 중앙값을 못 믿는다
            continue
        mid = statistics.median(h for _, _, h in items)

        # ① 크게 튄 컷은 **다시 읽힌다.** 음을 억지로 옮기는 것보다 자연스럽다.
        if retake is not None:
            fresh = []
            for cid, p, hz in items:
                if cid in done or abs(off(hz, mid)) <= PITCH_REDO:
                    fresh.append((cid, p, hz))
                    continue
                # ⚠️ 다시 읽히기 전에 **원본을 챙겨 둔다.**
                #    다시 만들기가 실패하면(한도 소진 등) 그 컷이 통째로 사라진다 —
                #    조금 튀는 목소리보다 소리가 아예 없는 것이 훨씬 나쁘다.
                keep = p.with_suffix(".keep")
                shutil.copyfile(p, keep)
                best, best_hz = None, hz
                for _ in range(PITCH_REDO_TRIES):
                    p.unlink(missing_ok=True)
                    if not retake(cid):
                        break
                    got = measure_f0(p)
                    if not got:
                        break
                    if abs(off(got, mid)) < abs(off(best_hz, mid)):
                        best, best_hz = got, got
                    if abs(off(got, mid)) <= PITCH_TOL:
                        break
                if not p.exists() or best is None:
                    keep.replace(p)            # 원본을 되돌린다
                    best, best_hz = None, hz
                else:
                    keep.unlink(missing_ok=True)
                if best is not None:
                    redone += 1
                    print(f"    {cid} ({sp}) 목소리가 {hz:.0f}Hz 로 크게 튀어 다시 읽혔다"
                          f" → {best_hz:.0f}Hz (인물 중앙값 {mid:.0f}Hz)")
                fresh.append((cid, p, best_hz))
            items = fresh
            mid = statistics.median(h for _, _, h in items)

        # ② 남은 잔잔한 흔들림은 음을 조금 옮겨 맞춘다(최대 2반음).
        for cid, p, hz in items:
            if cid in done:
                continue                   # 이미 손본 컷
            semitone = off(hz, mid)
            if abs(semitone) <= PITCH_TOL:
                done[cid] = hz             # 손댈 필요 없음. 다시 재지 않게 적어 둔다
                continue
            move = max(-PITCH_MAX, min(PITCH_MAX, -semitone))
            r = 2 ** (move / 12.0)
            tmp = p.with_suffix(".fix.mp3")
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error", "-i", str(p), "-af",
                     f"asetrate=24000*{r:.5f},aresample=24000,atempo={1 / r:.5f}",
                     "-b:a", "160k", str(tmp)], check=True, timeout=120)
                tmp.replace(p)
                done[cid] = hz * r
                fixed += 1
            except Exception:
                tmp.unlink(missing_ok=True)
    if redone:
        print(f"  목소리가 튄 {redone}컷을 다시 읽혔다")
    if fixed:
        print(f"  목소리 높이 고르기: {fixed}컷을 인물 중앙값 쪽으로 당겼다")
    try:
        book.write_text(json.dumps(done, ensure_ascii=False), encoding="utf-8")
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
        cuts = [c for s_ in sh.get("shorts", []) for c in (s_.get("cuts") or [])]
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
    pin = pin_models(speakers, cheap or pool.models)
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
            book[probe["id"]] = recipe(pspeak, used)
        else:
            note = quota_note(err.__cause__ if err.__cause__ is not None else err)
            print(f"  ⚠️ 열쇠 확인 실패({type(err).__name__})"
                  + (f" — {note}" if note else ""))
            print("     GEMINI_API_KEY 가 결제 걸린 프로젝트의 열쇠인지 확인하십시오.")
            (out / f"{probe['id']}.mp3").unlink(missing_ok=True)

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
            book[c["id"]] = recipe(speaker, _used)
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
        stale = [c for c in mine if book.get(c["id"]) != recipe(sp, pin[sp])]
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
                book[c["id"]] = recipe(sp, m2)
                if keep:
                    keep.unlink(missing_ok=True)
            elif keep:
                keep.replace(p)                # 예전 음성이라도 살려 둔다
            else:
                silent(p, float(c.get("sec", 6.0)) - 0.6)

    try:
        (out / "recipe.json").write_text(json.dumps(book, ensure_ascii=False),
                                         encoding="utf-8")
    except Exception:
        pass

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
            book[cid] = recipe(sp, m2)
            return True
        return False

    normalize_pitch(out, cuts, retake=retake)
    try:
        (out / "recipe.json").write_text(json.dumps(book, ensure_ascii=False),
                                         encoding="utf-8")
    except Exception:
        pass

    print(f"음성 {ok}개 · 실패 {fail}개 → {out}")
    if used:
        # 한쪽 모델만 두들기면 다시 429 가 난다. 골고루 갔는지 여기서 바로 보인다.
        print("  모델별: " + " · ".join(f"{m} {n}컷" for m, n in used.items()))

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
