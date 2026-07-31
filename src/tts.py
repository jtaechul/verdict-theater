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

# 요청 사이 간격은 분당 요청 수(RPM)로 정한다.
# 제미나이 TTS 미리보기 모델의 분당 한도는 매우 낮다 — 보수적으로 잡는다.
# 등급이 올라가면 워크플로에서 TTS_RPM 만 올리면 된다.
TTS_RPM = max(1, int(os.environ.get("TTS_RPM", "10")))
THROTTLE = 60.0 / TTS_RPM

# 연속 실패가 이만큼 쌓이면 그만둔다.
# 컷마다 최대 150초(5+15+40+90)를 기다리므로, 113컷을 끝까지 가면 4시간이 넘어
# 작업 시간 제한(180분)에 걸려 통째로 취소된다. 그 전에 멈춰 원인을 알려주는 편이 낫다.
MAX_FAIL_STREAK = max(1, int(os.environ.get("TTS_MAX_FAIL_STREAK", "5")))

# 이 비율 미만으로 성공하면 발행 품질이 아니다. 소리 끊긴 영상이 나가는 것을 막는다.
MIN_OK_RATIO = float(os.environ.get("TTS_MIN_OK_RATIO", "0.9"))


def _retry_wait(e, default):
    """서버가 알려준 대기 시간을 읽는다. 헤더와 본문을 **둘 다** 본다.

    제미나이는 429 에 Retry-After 헤더를 안 붙이는 경우가 많고, 대신 본문에
    google.rpc.RetryInfo 를 넣어 보낸다:
        {"error":{"details":[{"@type":"...RetryInfo","retryDelay":"37s"}]}}
    헤더만 보면 이 값을 놓쳐, 서버가 37초를 기다리라는데 5초 만에 다시 쏘고
    또 429 를 받는다."""
    hdr = (getattr(e, "headers", None) or {}).get("Retry-After")
    if hdr:
        try:
            return max(default, int(float(hdr)))
        except (TypeError, ValueError):
            pass
    try:
        body = json.loads(e.read().decode("utf-8", "replace"))
        for d in (body.get("error", {}).get("details") or []):
            rd = d.get("retryDelay")
            if isinstance(rd, str) and rd.endswith("s"):
                return max(default, int(float(rd[:-1])) + 1)      # 1초 여유
    except Exception:
        pass
    return default


def _post_retry(url, payload, timeout=180, label=""):
    """429·5xx 는 기다렸다 다시 해본다.

    예전에는 재시도가 전혀 없어서, 속도 제한 한 번에 그 컷이 통째로 무음이 됐다."""
    for i in range(len(BACKOFF) + 1):
        try:
            return _post(url, payload, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code not in RETRYABLE or i >= len(BACKOFF):
                raise
            wait = _retry_wait(e, BACKOFF[i])
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
VOICE_STYLE = {
    "narrator": ("차분하고 낮은 해설 목소리로, 담담하게", 1.0),
    "v_F50A":   ("60대 여성. 지치고 따뜻한 목소리로", 1.0),
    "v_F50B":   ("50대 여성. 차갑고 또박또박", 1.0),
    "v_M50A":   ("50대 남성. 사무적이고 냉랭하게", 1.0),
    "v_M50B":   ("50대 남성. 무심하게", 1.0),
    "v_F70":    ("70대 여성. 힘없고 느리게", 0.92),
    "v_M70":    ("70대 남성. 쉰 목소리로 느리게", 0.92),
    "v_JUDGE":  ("재판장. 무겁고 절제된 목소리로 또박또박", 0.90),
}

# Gemini TTS 가 제공하는 목소리 이름(참고용 기본 배정).
# API가 다른 이름을 주면 아래 값 대신 목록에서 순서대로 배정한다.
VOICE_NAME = {
    "narrator": "Charon", "v_F50A": "Aoede", "v_F50B": "Leda",
    "v_M50A": "Puck", "v_M50B": "Orus", "v_F70": "Kore",
    "v_M70": "Fenrir", "v_JUDGE": "Charon",
}


def pick_tts_model(key):
    """음성을 낼 수 있는 모델을 API 목록에서 찾는다. 이름을 코드에 박지 않는다.

    ⚠️ 이것이 이번 실행의 **첫 API 호출**이라 속도 제한을 가장 먼저 맞는 자리다.
       재시도 없이 한 번에 포기하면 회차 전체가 무음이 된다."""
    override = os.environ.get("GEMINI_TTS_MODEL")
    if override:
        return override.strip()
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
            print(f"    (모델 목록 HTTP {e.code} — {w}초 기다렸다 다시 한다)")
            time.sleep(w)
        except OSError as e:
            if i >= len(BACKOFF):
                raise
            print(f"    (모델 목록 통신 오류 {type(e).__name__} — {BACKOFF[i]}초 뒤 다시)")
            time.sleep(BACKOFF[i])
    names = [m["name"].split("/", 1)[-1] for m in (data or {}).get("models", [])]
    cands = [n for n in names if "tts" in n.lower()]
    if not cands:
        return None
    cands.sort(key=lambda n: ("preview" in n, len(n)))
    return cands[0]


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


def synth_one(key, model, text, speaker, out_mp3):
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
    }, timeout=180, label=speaker)

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
    ap.add_argument("--silent", action="store_true", help="모델을 부르지 않고 무음만 만든다")
    args = ap.parse_args()

    # 없으면 여기서 분명히 말하고 멈춘다. 한참 뒤에 죽는 것보다 낫다.
    # 다만 --silent 는 외부 프로그램이 전혀 필요 없으므로 막지 않는다.
    if not args.silent:
        need_ffmpeg()

    doc = json.loads(Path(args.script).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cuts = [c for a in doc["acts"] for c in a["cuts"]]
    if args.limit:
        cuts = cuts[:args.limit]
        print(f"앞 {len(cuts)}컷만 만든다 (--limit {args.limit})")

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = None
    pick_err = None
    if not args.silent and key:
        try:
            model = pick_tts_model(key)
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

    print(f"음성 모델: {model} · 요청 간격 {THROTTLE:.1f}초(분당 {TTS_RPM}회)")
    ok = fail = 0
    streak = 0
    last_call = 0.0
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
        # 몰아치면 속도 제한에 걸린다. 요청 사이를 최소 THROTTLE 초 띄운다.
        gap = time.monotonic() - last_call
        if last_call and gap < THROTTLE:
            time.sleep(THROTTLE - gap)
        try:
            synth_one(key, model, text, c.get("speaker", "narrator"), p)
            ok += 1
            streak = 0
        except Exception as e:
            fail += 1
            streak += 1
            print(f"  {c['id']} 실패({type(e).__name__}) → 무음으로 대체")
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
        last_call = time.monotonic()
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(cuts)}  (성공 {ok} · 실패 {fail})")

    print(f"음성 {ok}개 · 실패 {fail}개 → {out}")

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
