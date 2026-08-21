#!/usr/bin/env python3
"""⭐ 목소리를 어느 길로 부르는 것이 되는지 **실제로 걸어 본다.** (값 1원 미만)

    python3 tools/tts_route_probe.py

왜 (2026-08-21)
    제미나이 목소리(AI 스튜디오 열쇠)는 소리가 좋은데 **무료 등급이 하루 10번**이다.
      quotaId = GenerateRequestsPerDayPerProjectPerModel-FreeTier, 값 10
    한 화가 대사 15줄쯤이라 무료로는 **한 화도 못 만든다.**

    그런데 같은 제미나이 목소리를 **구글 클라우드 TTS 쪽으로도** 부를 수 있는지가
    관건이다. 그쪽(GOOGLE_TTS_KEY)은 이미 결제 계정이 붙어 있으므로 하루 10번
    제한이 없다. 되기만 하면 운영자가 새로 할 일이 하나도 없다.

    ⚠️ 추측으로 코드를 짜지 않는다. **여기서 실제로 걸어 보고**, 되는 길만 쓴다.
    ⚠️ 내 컴퓨터에는 GOOGLE_TTS_KEY 가 없다. 그래서 깃허브 안에서 돌린다.
"""
import json
import os
import sys
import urllib.error
import urllib.request

K = (os.environ.get("GOOGLE_TTS_KEY") or "").strip()
LINE = "당신 진짜 제정신이야?!"
PROMPT = "한국 드라마의 한 장면이다. 무대에서처럼 목소리를 크게 내지르며 말한다."


def call(url, body=None):
    """돌려주는 것: (성공?, 한 줄 설명)"""
    try:
        if body is None:
            req = urllib.request.Request(url)
        else:
            req = urllib.request.Request(
                url, data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as r:
            got = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(raw)["error"]["message"]
        except Exception:                                    # noqa: BLE001
            msg = raw
        return False, f"HTTP {e.code} — {msg[:180]}"
    except Exception as e:                                   # noqa: BLE001
        return False, f"못 닿았다 — {e}"
    n = len(got.get("audioContent") or "")
    if n:
        return True, f"소리 {n * 3 // 4:,}바이트를 받았다"
    return True, f"{str(got)[:120]}"


if not K:
    print("❌ GOOGLE_TTS_KEY 가 없다 — 깃허브 안에서 돌려야 한다")
    sys.exit(1)

print("⭐ 어느 길이 되는지 실제로 걸어 본다\n")

# ① 클라우드 TTS 가 가진 한국어 목소리에 제미나이·Chirp3 가 있는가
print("① 구글 클라우드 TTS 가 가진 한국어 목소리")
for ver in ("v1", "v1beta1"):
    ok, why = call(f"https://texttospeech.googleapis.com/{ver}/voices"
                   f"?languageCode=ko-KR&key={K}")
    if not ok:
        print(f"   {ver}: ❌ {why}")
        continue
    try:
        req = urllib.request.Request(
            f"https://texttospeech.googleapis.com/{ver}/voices"
            f"?languageCode=ko-KR&key={K}")
        with urllib.request.urlopen(req, timeout=60) as r:
            vs = json.loads(r.read().decode("utf-8")).get("voices") or []
    except Exception:                                        # noqa: BLE001
        vs = []
    names = [v.get("name", "") for v in vs]
    fam = {}
    for n in names:
        key = "Chirp3-HD" if "Chirp3-HD" in n else (
            "Chirp-HD" if "Chirp" in n else n.split("-")[2] if n.count("-") > 2 else "?")
        fam[key] = fam.get(key, 0) + 1
    print(f"   {ver}: 모두 {len(names)}개 — {fam}")
    gem = [n for n in names if "gemini" in n.lower()]
    if gem:
        print(f"   ⭐ 제미나이 이름이 목록에 있다: {gem[:6]}")

# ② 연기 지시(prompt)를 받아 주는가 — 이것이 핵심이다
print("\n② 연기 지시(prompt)를 받아 주는 길이 있는가")
SHAPES = [
    ("A. v1beta1 · model_name=gemini-2.5-flash-tts · 이름 Kore",
     "v1beta1", {"input": {"text": LINE, "prompt": PROMPT},
                 "voice": {"languageCode": "ko-KR", "name": "Kore",
                           "model_name": "gemini-2.5-flash-tts"},
                 "audioConfig": {"audioEncoding": "LINEAR16"}}),
    ("B. v1beta1 · model_name=gemini-2.5-flash-tts · 이름 ko-KR-Chirp3-HD-Kore",
     "v1beta1", {"input": {"text": LINE, "prompt": PROMPT},
                 "voice": {"languageCode": "ko-KR",
                           "name": "ko-KR-Chirp3-HD-Kore",
                           "model_name": "gemini-2.5-flash-tts"},
                 "audioConfig": {"audioEncoding": "LINEAR16"}}),
    ("C. v1beta1 · 지시만 넣고 model_name 없음",
     "v1beta1", {"input": {"text": LINE, "prompt": PROMPT},
                 "voice": {"languageCode": "ko-KR",
                           "name": "ko-KR-Chirp3-HD-Kore"},
                 "audioConfig": {"audioEncoding": "LINEAR16"}}),
    ("D. v1 · Chirp3-HD · 지시 없음 (지금 되돌아갈 자리)",
     "v1", {"input": {"text": LINE},
            "voice": {"languageCode": "ko-KR", "name": "ko-KR-Chirp3-HD-Kore"},
            "audioConfig": {"audioEncoding": "LINEAR16"}}),
    ("E. v1 · Neural2 · 지시 없음 (가장 밋밋한 것)",
     "v1", {"input": {"text": LINE},
            "voice": {"languageCode": "ko-KR", "name": "ko-KR-Neural2-A"},
            "audioConfig": {"audioEncoding": "LINEAR16"}}),
]
won = []
for name, ver, body in SHAPES:
    ok, why = call(f"https://texttospeech.googleapis.com/{ver}/text:synthesize"
                   f"?key={K}", body)
    print(f"   {'✅' if ok else '❌'} {name}\n      {why}")
    if ok:
        won.append(name)

print("\n" + "─" * 56)
if won:
    print("되는 길:")
    for w in won:
        print(f"   · {w}")
else:
    print("되는 길이 하나도 없다")
