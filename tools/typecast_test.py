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
        rows = [
            {"voice_id": "tc_f1", "voice_name": "지수", "model": "ssfm-v21",
             "gender": "female", "emotions": ["normal", "angry", "sad"]},
            {"voice_id": "tc_m1", "voice_name": "철수", "model": "ssfm-v21",
             "gender": "male", "emotions": ["normal", "angry"]},
            {"voice_id": "tc_u1", "voice_name": "몰라", "model": "ssfm-v21",
             "emotions": ["normal"]},
        ]
        # 추천 시험용 — 여럿 더 (나이 표시 포함, 어린이 하나)
        for i in range(2, 9):
            rows.append({"voice_id": f"tc_f{i}", "voice_name": f"여{i}",
                         "model": "ssfm-v21", "gender": "female",
                         "age": ("middle-aged" if i in (2, 3) else "young-adult"),
                         "emotions": ["normal"]})
            rows.append({"voice_id": f"tc_m{i}", "voice_name": f"남{i}",
                         "model": "ssfm-v21", "gender": "male",
                         "age": ("middle-aged" if i in (2, 3) else "young-adult"),
                         "emotions": ["normal"]})
        rows.append({"voice_id": "tc_kid", "voice_name": "꼬마",
                     "model": "ssfm-v21", "gender": "female", "age": "child",
                     "emotions": ["normal"]})
        return _R(json.dumps({"result": rows}).encode("utf-8"))
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
    ck("목소리를 다 읽었다", len(rows) == 18, str(len(rows)))
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
    ck("줄마다 어느 엔진인지 적힌다 (옛 견본과 안 섞이게)",
       all(r.get("engine") == "typecast" for r in rows))

    print("⑧ 인물별 추천 — 1125개를 다 만들지 않는다")
    import json as _j
    doc = _j.loads((ROOT / "data" / "series" / "S001.json")
                   .read_text(encoding="utf-8"))
    rec = tts.tc_recommend(doc["characters"], per=4)
    ck("인물마다 추천이 온다", set(rec) == {"본처", "내연녀", "남편"}, str(set(rec)))
    ck("인물마다 4개뿐이다 (전부가 아니라)",
       all(len(v) == 4 for v in rec.values()),
       str({k: len(v) for k, v in rec.items()}))
    ck("남편 후보는 남자 목소리다",
       all(v["gender"] == "m" for v in rec["남편"]))
    ck("본처(52) 후보는 나이 든 목소리가 앞에 온다",
       rec["본처"][0]["age"] == "middle-aged", rec["본처"][0])
    ck("어린이 목소리는 후보에 없다",
       all(v["id"] != "tc_kid" for vs in rec.values() for v in vs))
    _ids = [v["id"] for vs in rec.values() for v in vs]
    ck("인물끼리 목소리가 안 겹친다", len(_ids) == len(set(_ids)))

    print("⑨ 인물별 견본 — 실제 대사로, 몇 개만")
    CALLS.clear()
    aud2 = d / "aud2"
    with redirect_stdout(io.StringIO()):
        tts.tc_audition_cast(aud2, doc, per=2)
    rows2 = json.loads((aud2 / "list.json").read_text(encoding="utf-8"))
    ck("견본이 인물수×2개다", len(rows2) == 6, str(len(rows2)))
    ck("줄마다 인물·대사·이름표가 있다",
       all(r["kind"] == "cast" and r["char"] and r["line"] and r["label"]
           for r in rows2))
    _mine = [c for c in CALLS if c["url"].endswith("text-to-speech")]
    ck("만들기 호출이 6번뿐이다 (1125번이 아니라)", len(_mine) == 6, str(len(_mine)))
    # ⚠️ 본처의 실제 첫 대사가 **우연히** 시험 문장과 같은 문장이다
    #    ("당신 진짜 제정신이야?!"). ≠시험문장 으로 재면 헛경보가 난다.
    #    대본에서 직접 뽑아 **그 문장 그대로인지** 잰다.
    import series as _SC
    _first = next(t for w, t in _SC.dia_turns(
        doc["episodes"][0]["cuts"][0]["prompt"]) if w == "Wife")
    ck("본처 견본은 본처의 실제 첫 대사다",
       all(r["line"] == _first for r in rows2 if r["char"] == "본처"),
       str([r["line"] for r in rows2 if r["char"] == "본처"][:1]))
    _hus = next(t for ep in doc["episodes"] for c in ep["cuts"]
                for w, t in _SC.dia_turns(c["prompt"]) if w == "Husband")
    ck("남편 견본도 남편의 실제 첫 대사다",
       all(r["line"] == _hus for r in rows2 if r["char"] == "남편"),
       str([r["line"] for r in rows2 if r["char"] == "남편"][:1]))

    print("⑩ 인물별로 고른 것이 실제 배정에 이긴다")
    import tempfile as _tf
    _vf = ROOT / "state" / "voice.json"
    _bak = _vf.read_text(encoding="utf-8") if _vf.exists() else None
    try:
        _vf.write_text(_j.dumps({"cast": {"본처": "tc_f5", "남편": "tc_m5"}},
                                ensure_ascii=False), encoding="utf-8")
        V2 = tts.pick_voices(doc["characters"])
        ck("본처는 고른 목소리를 쓴다", V2.get("본처") == "tc_f5", V2.get("본처"))
        ck("남편도 고른 목소리를 쓴다", V2.get("Husband") == "tc_m5")
        ck("안 고른 내연녀는 추천 순서대로", V2.get("내연녀") not in ("tc_f5", "tc_m5"))
    finally:
        if _bak is None:
            _vf.unlink(missing_ok=True)
        else:
            _vf.write_text(_bak, encoding="utf-8")

urllib.request.urlopen = _real
os.environ.pop("TYPECAST_API_KEY", None)
tts._TC_V["list"] = None

print("────────────────────────────────────────────────────")
print("❌ 타입캐스트: 걸린 것이 있다" if bad else "✅ 타입캐스트: 배선이 성하다")
sys.exit(bad)
