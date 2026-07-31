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
import struct
import subprocess
import sys
import time
import urllib.error
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import BASE, LLMError, _post  # noqa: E402

# 속도 제한(429)에 걸렸을 때 기다리는 시간. 점점 늘린다.
BACKOFF = [5, 15, 40, 90]
THROTTLE = 1.2      # 요청 사이 최소 간격(초). 몰아치면 429 가 난다


def _post_retry(url, payload, timeout=180, label=""):
    """429·5xx 는 기다렸다 다시 해본다.

    예전에는 재시도가 전혀 없어서, 속도 제한 한 번에 그 컷이 통째로 무음이 됐다.
    음성은 컷마다 따로 만들므로 몇 초 기다리는 것으로 대부분 회복된다."""
    last = None
    for i in range(len(BACKOFF) + 1):
        try:
            return _post(url, payload, timeout=timeout)
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (408, 429, 500, 502, 503, 504) or i >= len(BACKOFF):
                raise
            # 서버가 "이만큼 기다려라" 고 알려주면 그 말을 따른다
            wait = BACKOFF[i]
            hdr = (e.headers or {}).get("Retry-After") if e.headers else None
            if hdr:
                try:
                    wait = max(wait, int(float(hdr)))
                except ValueError:
                    pass
            print(f"    ({label} 속도 제한 HTTP {e.code} — {wait}초 기다렸다 다시 한다"
                  f" {i + 1}/{len(BACKOFF)})")
            time.sleep(wait)
        except (OSError, LLMError) as e:
            last = e
            if i >= len(BACKOFF):
                raise
            print(f"    ({label} 통신 오류 {type(e).__name__} — {BACKOFF[i]}초 뒤 다시)")
            time.sleep(BACKOFF[i])
    raise last


def need_ffmpeg():
    """ffmpeg 가 없으면 여기서 분명히 말하고 멈춘다.

    예전에는 없는 채로 진행하다가 한참 뒤 FileNotFoundError 로 죽었다.
    로그만 보면 원인을 알 수 없었다."""
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
    """음성을 낼 수 있는 모델을 API 목록에서 찾는다. 이름을 코드에 박지 않는다."""
    override = os.environ.get("GEMINI_TTS_MODEL")
    if override:
        return override.strip()
    import urllib.request
    req = urllib.request.Request(f"{BASE}/models?key={key}&pageSize=200")
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))
    names = [m["name"].split("/", 1)[-1] for m in data.get("models", [])]
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

    af = f"atempo={speed:.3f}" if abs(speed - 1.0) > 0.01 else "anull"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp),
                    "-af", af, "-b:a", "160k", str(out_mp3)], check=True)
    tmp.unlink(missing_ok=True)
    return out_mp3


def silent(out_mp3, sec):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"anullsrc=r=24000:cl=mono", "-t", f"{sec:.2f}",
                    "-b:a", "96k", str(out_mp3)], check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--out", default="build/voice")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--silent", action="store_true", help="모델을 부르지 않고 무음만 만든다")
    args = ap.parse_args()

    need_ffmpeg()        # 없으면 여기서 분명히 말하고 멈춘다. 한참 뒤에 죽는 것보다 낫다.

    doc = json.loads(Path(args.script).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cuts = [c for a in doc["acts"] for c in a["cuts"]]
    if args.limit:
        cuts = cuts[:args.limit]
        print(f"앞 {len(cuts)}컷만 만든다 (--limit {args.limit})")

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    model = None
    if not args.silent and key:
        try:
            model = pick_tts_model(key)
        except Exception as e:
            print(f"모델 목록 조회 실패: {e}")

    if not model:
        why = "GEMINI_API_KEY 가 없다" if not key else "쓸 수 있는 음성 모델이 없다"
        if args.silent:
            why = "--silent 지정"
        print(f"⚠️ 무음으로 만든다 ({why}).")
        print("   자막이 상시 노출이라 파이프라인은 끝까지 돌지만, 발행 전에 반드시 음성을 넣어야 한다.")
        for c in cuts:
            silent(out / f"{c['id']}.mp3", float(c.get("sec", 6.0)) - 0.6)
        print(f"무음 {len(cuts)}개 생성: {out}")
        return 0

    print(f"음성 모델: {model}")
    ok = fail = 0
    last_call = 0.0
    for i, c in enumerate(cuts):
        p = out / f"{c['id']}.mp3"
        if p.exists():
            ok += 1
            continue
        text = (c.get("text") or "").strip()
        if not text:
            silent(p, 1.0)
            continue
        # 몰아치면 속도 제한에 걸린다. 요청 사이를 최소 THROTTLE 초 띄운다.
        gap = time.monotonic() - last_call
        if last_call and gap < THROTTLE:
            time.sleep(THROTTLE - gap)
        try:
            synth_one(key, model, text, c.get("speaker", "narrator"), p)
            ok += 1
        except Exception as e:
            fail += 1
            print(f"  {c['id']} 실패({type(e).__name__}) → 무음으로 대체")
            silent(p, float(c.get("sec", 6.0)) - 0.6)
        last_call = time.monotonic()
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(cuts)}  (성공 {ok} · 실패 {fail})")

    print(f"음성 {ok}개 · 실패 {fail}개 → {out}")

    # 대부분이 무음이면 그것은 "영상이 나왔다" 가 아니라 "음성이 통째로 실패했다" 이다.
    # 예전에는 여기서 0 을 돌려줘서, 12분 내내 무음인 영상이 성공으로 올라갈 수 있었다.
    total = ok + fail
    if total and fail / total > 0.5:
        print("", file=sys.stderr)
        print(f"오류: {total}컷 중 {fail}컷이 음성 생성에 실패했습니다.", file=sys.stderr)
        print("      이대로 만들면 대사가 거의 없는 영상이 됩니다.", file=sys.stderr)
        print("      흔한 원인: 제미나이 API 사용량 한도 초과, 또는 결제 미등록.", file=sys.stderr)
        print("      소리 없이 화면만 확인하려면 나레이션을 '무음으로 시험' 으로", file=sys.stderr)
        print("      고른 뒤 다시 실행하십시오.", file=sys.stderr)
        return 1
    if fail:
        print("⚠️ 실패한 컷은 무음이다. 그 자리에서 소리가 끊긴다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
