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
import struct
import subprocess
import sys
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import BASE, LLMError, _post  # noqa: E402

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

    res = _post(f"{BASE}/models/{model}:generateContent?key={key}", {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}
            },
        },
    }, timeout=180)

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

    doc = json.loads(Path(args.script).read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cuts = [c for a in doc["acts"] for c in a["cuts"]]
    if args.limit:
        cuts = cuts[:args.limit]

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
    for i, c in enumerate(cuts):
        p = out / f"{c['id']}.mp3"
        if p.exists():
            ok += 1
            continue
        text = (c.get("text") or "").strip()
        if not text:
            silent(p, 1.0)
            continue
        try:
            synth_one(key, model, text, c.get("speaker", "narrator"), p)
            ok += 1
        except Exception as e:
            fail += 1
            print(f"  {c['id']} 실패({type(e).__name__}) → 무음으로 대체")
            silent(p, float(c.get("sec", 6.0)) - 0.6)
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(cuts)}")

    print(f"음성 {ok}개 · 실패 {fail}개 → {out}")
    if fail:
        print("⚠️ 실패한 컷은 무음이다. 그 자리에서 소리가 끊긴다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
