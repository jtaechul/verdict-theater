#!/usr/bin/env python3
"""타입캐스트 갈아타기가 제대로 배선됐는가 — 인터넷 없이, 가짜 응답으로.

    python3 tools/typecast_test.py     인터넷 0회 · 0원 · 몇 초

왜 (2026-08-23)
    운영자: "발음이 아직도 좀 뭉개져. 구글 TTS 말고 typecast 로 바꿔볼까?"
    열쇠가 있으면 타입캐스트가 맨 앞이 되고, 실패하면 **크게 알리고**
    제미나이로 물러선다. 그 갈림길들을 진짜 인터넷 없이 다 걸어 본다.
"""

import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import urllib.request
from contextlib import redirect_stdout

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import tts                                                   # noqa: E402

bad = 0


def ck(what, cond, why=""):
    global bad
    if cond:
        print(f"   ✅ {what}")
    else:
        print(f"   ❌ {what}" + (f"  ({why})" if why else ""))
        bad = 1


# ── 가짜 타입캐스트 서버 ────────────────────────────────
CALLS = []
WAV = None      # 아래에서 진짜 무음 wav 를 만들어 담는다


class _R(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_open(req, timeout=0):
    url = req.full_url if hasattr(req, "full_url") else str(req)
    hdr = {k.lower(): v for k, v in getattr(req, "headers", {}).items()}
    body = json.loads(req.data.decode("utf-8")) if getattr(req, "data", None) else None
    CALLS.append({"url": url, "hdr": hdr, "body": body})
    if url.endswith("/v1/voices"):
        return _R(json.dumps({"result": [
            {"voice_id": "tc_f1", "voice_name": "지수", "model": "ssfm-v21",
             "gender": "female", "emotions": ["normal", "angry", "sad"]},
            {"voice_id": "tc_m1", "voice_name": "철수", "model": "ssfm-v21",
             "gender": "male", "emotions": ["normal", "angry"]},
            {"voice_id": "tc_u1", "voice_name": "몰라", "model": "ssfm-v21",
             "emotions": ["normal"]},
        ]}).encode("utf-8"))
    if url.endswith("/v1/text-to-speech"):
        return _R(WAV)
    raise AssertionError(f"모르는 주소: {url}")


print("⭐ 타입캐스트 갈아타기")
os.environ["TYPECAST_API_KEY"] = "tk_test"
os.environ.pop("VOICE_ENGINE", None)
tts._TC_V["list"] = None
_real = urllib.request.urlopen
urllib.request.urlopen = fake_open

with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=0.5:sample_rate=24000",
                    str(d / "fake.wav")], check=True)
    WAV = (d / "fake.wav").read_bytes()

    print("① 열쇠가 있으면 타입캐스트가 맨 앞")
    ck("엔진이 타입캐스트다", tts.engine() == "typecast")
    ck("key() 도 타입캐스트 열쇠를 본다", tts.key() == "tk_test")
    os.environ["VOICE_ENGINE"] = "gemini"
    ck("VOICE_ENGINE 으로 되돌릴 수 있다", tts.engine() == "gemini")
    os.environ.pop("VOICE_ENGINE", None)

    print("② 목소리 목록을 읽는다")
    rows = tts.tc_voices()
    ck("세 목소리를 읽었다", len(rows) == 3)
    ck("성별을 알아본다", rows[0]["gender"] == "f" and rows[1]["gender"] == "m")
    ck("성별 모름도 죽지 않는다", rows[2]["gender"] == "")
    ck("여자 목록은 여자 먼저", tts.best_voices("FEMALE")[0] == "tc_f1")
    ck("남자 목록은 남자 먼저", tts.best_voices("MALE")[0] == "tc_m1")

    print("③ 감정을 preset 으로 바꾼다")
    ck("화난 말 → angry", tts.tc_emotion("당장 나가!") == ("angry", 2))
    ck("슬픈 말 → sad", tts.tc_emotion("미안해요")[0] == "sad")
    ck("보통 말 → normal", tts.tc_emotion("서류 여기 있어요") == ("normal", 1))

    print("④ 한 마디를 만들어 본다 (가짜 서버)")
    CALLS.clear()
    p = tts.say("당장 나가!", "tc_f1", 1.0, 0.0, d / "out.wav")
    ck("소리 파일이 나온다", p and pathlib.Path(p).exists() and
       pathlib.Path(p).stat().st_size > 1000)
    call = next(c for c in CALLS if c["url"].endswith("text-to-speech"))
    ck("열쇠를 머리글로 보낸다", call["hdr"].get("x-api-key") == "tk_test",
       str(call["hdr"]))
    ck("목소리·모델·한국어를 보낸다",
       call["body"]["voice_id"] == "tc_f1"
       and call["body"]["model"] == "ssfm-v21"
       and call["body"]["language"] == "kor")
    ck("감정 preset 을 보낸다",
       call["body"]["prompt"] == {"emotion_preset": "angry", "emotion_intensity": 2})
    ck("wav 로 달라고 한다", call["body"]["output"]["audio_format"] == "wav")

    print("⑤ 그 목소리가 못 하는 감정이면 되는 것으로 바꾼다")
    CALLS.clear()
    tts.say("미안해요", "tc_m1", 1.0, 0.0, d / "out2.wav")   # 철수는 sad 가 없다
    call = next(c for c in CALLS if c["url"].endswith("text-to-speech"))
    ck("sad 대신 normal 로 보낸다",
       call["body"]["prompt"]["emotion_preset"] == "normal", str(call["body"]["prompt"]))

    print("⑥ 실패하면 크게 알리고 제미나이로 물러선다")

    def boom(req, timeout=0):
        if str(getattr(req, "full_url", req)).endswith("text-to-speech"):
            raise urllib.error.HTTPError(req.full_url, 402, "no credit", {},
                                         io.BytesIO(b"credit exhausted"))
        return fake_open(req, timeout)
    import urllib.error
    urllib.request.urlopen = boom
    os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY") or "g_test"
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            tts.say("한 마디", "tc_f1", 1.0, 0.0, d / "out3.wav")
    except Exception:                                        # noqa: BLE001
        pass                    # 제미나이 가짜 서버까지는 안 만든다 — 알림만 본다
    ck("실패를 조용히 삼키지 않는다", "타입캐스트 실패" in buf.getvalue(),
       buf.getvalue()[:120])
    ck("잔액이 다 떨어졌다고 쉬운 말로", "잔액" in buf.getvalue() or "크레딧" in buf.getvalue())
    urllib.request.urlopen = fake_open

    print("⑦ 전부 들어보기(오디션)가 타입캐스트 목소리로 돈다")
    tts._TC_V["list"] = None
    aud = d / "aud"
    with redirect_stdout(io.StringIO()):
        made = tts.audition(aud)
    rows = json.loads((aud / "list.json").read_text(encoding="utf-8"))
    ck("목소리마다 견본이 생긴다", len([r for r in rows if r["sex"] == "여"]) >= 2)
    ck("성별 모름은 여·남 양쪽에 얹힌다 (값은 한 번만 낸다)",
       sum(1 for r in rows if r["voice"] == "tc_u1") == 2
       and len({r["file"] for r in rows if r["voice"] == "tc_u1"}) == 1)
    ck("화면에 보일 한글 이름표가 있다",
       any(r.get("label") == "지수" for r in rows))
    ck("파일 이름은 영문이다", all(r["file"].isascii() for r in rows))

urllib.request.urlopen = _real
os.environ.pop("TYPECAST_API_KEY", None)
tts._TC_V["list"] = None

print("────────────────────────────────────────────────────")
print("❌ 타입캐스트: 걸린 것이 있다" if bad else "✅ 타입캐스트: 배선이 성하다")
sys.exit(bad)
