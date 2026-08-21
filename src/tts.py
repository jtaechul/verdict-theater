#!/usr/bin/env python3
"""⭐ 한국어 목소리를 따로 만든다 (구글 클라우드 TTS).

    python3 src/tts.py --say "당신 진짜 제정신이야?" --out /tmp/a.wav

왜 (2026-08-21 운영자 지시)
    "또 실패야. 외국인 노동자가 어설픈 한국말 하는 것 같아 ㅠㅠ"

    실제로 만들어진 영상을 재 봤다 (1화 1컷, 6.02초) —
      0.00~0.98 무음 / 0.98~2.55 / 2.79~4.20 / 4.57~6.02
    **구조 지시는 완벽하게 먹었다.** 셋이 겹치지 않고 차례대로 말했다.
    남은 것은 **발음 하나**였고, 그건 프롬프트로 못 고친다 —
    영상 만드는 쪽의 한국어가 원어민 수준이 아니기 때문이다.
    (언어 명시·원어민·서울 억양·부정어 제거·대문자 태그·목소리 지정·
     겹침 제거·플로우 음성 해제 — 프롬프트로 할 수 있는 것은 다 했다)

    그래서 **고칠 자리를 바꾼다.** 목소리를 영상에서 떼어내고,
    한국어 전용 목소리를 **말하던 그 자리에** 끼워 넣는다.
    입은 이미 같은 한국어 대사로 움직이고 있으므로 입모양도 거의 맞는다.

값
    16화 전체 대사가 약 2,400자. 구글 무료 한도(월 100만 자) 안이라 **0원**이다.

열쇠
    GOOGLE_TTS_KEY — 구글 클라우드에서 만든 API 키 (깃허브 시크릿)
    없으면 소리를 안 바꾸고 원래 소리를 그대로 쓴다 (영상은 계속 나온다).
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://texttospeech.googleapis.com/v1/text:synthesize"

# 한국어 전용 목소리. 사람마다 다른 것을 준다.
#   ⚠️ 같은 목소리를 두 사람에게 주면 누가 말하는지 안 갈린다.
#   ⚠️ 열쇠가 없을 때(내 컴퓨터·시험) 쓸 **되돌아갈 자리**다.
#      실제로는 아래 best_voices() 가 구글에 물어 **가장 좋은 것**을 고른다.
VOICE_F = ["ko-KR-Neural2-A", "ko-KR-Neural2-B", "ko-KR-Wavenet-A"]
VOICE_M = ["ko-KR-Neural2-C", "ko-KR-Wavenet-C", "ko-KR-Wavenet-D"]

# ⭐⭐ 2026-08-21 — 목소리 등급. 앞에 있을수록 사람 같다.
#    Neural2 는 한국어 원어민이긴 하지만 **아나운서처럼 밋밋하다.**
#    Chirp3-HD 는 훨씬 사람처럼 말한다 — 드라마 대사에는 이쪽이 맞다.
#    ⚠️ 어떤 이름이 있는지 외워 두지 않는다. 구글이 이름을 바꾸거나 새 등급을
#       내면 외워 둔 목록은 바로 낡는다. **구글에 물어서** 고른다.
TIERS = ["Chirp3-HD", "Chirp-HD", "Neural2", "Wavenet", "Standard"]
_VOICES = None


def list_voices():
    """구글에 한국어 목소리 목록을 물어본다 (한 번만 묻고 기억한다)."""
    global _VOICES
    if _VOICES is not None:
        return _VOICES
    k = key()
    if not k:
        _VOICES = []
        return _VOICES
    try:
        url = ("https://texttospeech.googleapis.com/v1/voices"
               f"?languageCode=ko-KR&key={k}")
        with urllib.request.urlopen(url, timeout=30) as r:
            got = json.loads(r.read().decode("utf-8"))
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


def best_voices(gender):
    """그 성별에서 **가장 사람 같은** 목소리부터 차례로."""
    got = [n for n, g in list_voices() if g == gender]
    if not got:
        return list(VOICE_F if gender == "FEMALE" else VOICE_M)
    return sorted(got, key=lambda n: (rank(n), n))

RATE_MIN, RATE_MAX = 0.75, 1.35     # 이 밖으로 나가면 사람 소리가 아니게 된다
PITCH = {"low": -2.0, "high": 2.0}


def key():
    return (os.environ.get("GOOGLE_TTS_KEY") or "").strip()


def is_female(ch):
    """인물 설명에서 성별을 읽는다 (woman 안에 man 이 있으니 낱말 경계로)."""
    blob = " ".join(str(ch.get(k) or "") for k in ("flow_prompt", "voice")).lower()
    return not re.search(r"\bman\b|\bmale\b|\bboy\b", blob)


def pick_voices(chars):
    """인물표 → {이름: 구글 목소리 이름}. 같은 목소리가 겹치지 않게."""
    vf, vm = best_voices("FEMALE"), best_voices("MALE")
    out, fi, mi = {}, 0, 0
    for ch in chars or []:
        keys = [(ch.get("name") or "").strip(),
                (ch.get("role_en") or "").strip()]
        # ⚠️ `.title()` 을 쓰면 "Other Woman" 이 되는데 대사 줄의 이름표는
        #    "Other woman" 이다(첫 글자만 대문자). 그러면 못 찾는다.
        short = re.sub(r"^the\s+", "", keys[1]).strip()
        keys.append(short[:1].upper() + short[1:] if short else "")
        if is_female(ch):
            v, fi = vf[fi % len(vf)], fi + 1
        else:
            v, mi = vm[mi % len(vm)], mi + 1
        for k in keys:
            if k:
                out[k] = v
    return out


def tone_of(text):
    """말투를 소리 높낮이로 (느낌표는 조금 높게, 마침표는 조금 낮게)."""
    t = str(text or "")
    if "!" in t or "?!" in t:
        return 1.5
    return 0.0


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
    req = urllib.request.Request(
        f"{API}?key={k}", data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def say(text, voice="ko-KR-Neural2-A", rate=1.0, pitch=0.0, out=None):
    """한 마디를 소리로 만든다. 만들어진 wav 파일 경로를 돌려준다.

    ⚠️ 2026-08-21 — 여기에 explain() 을 **함수 한가운데 끼워 넣었다가**
       소리를 만들고 돌려주는 마지막 세 줄이 explain 안으로 딸려 들어가
       say() 가 None 을 돌려줬다. 깃허브 검사가 바로 잡아 줬다
       ('NoneType' object has no attribute 'stat').
       → 도우미 함수는 **쓰는 함수보다 위**에 둔다.
    """
    k = key()
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
        #    (속도를 못 맞춰도 목소리가 좋은 쪽이 낫다 — 자리 맞추기는
        #     room 여유로 이미 웬만큼 해결된다)
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
    return _write(got, out)


def _write(got, out):
    if "audioContent" not in got:
        raise RuntimeError(f"❌ 구글이 소리를 안 보냈다: {str(got)[:200]}")
    p = Path(out or "tts.wav")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(base64.b64decode(got["audioContent"]))
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


def say_to_fit(text, voice, seconds, out, pitch=0.0, room=None):
    """입이 움직인 시간에 맞춰 한 마디를 만들되, **급해지지 않게** 만든다.

    · `seconds` — 영상 속 사람의 입이 움직인 시간
    · `room`    — 다음 사람이 말하기 직전까지, **실제로 쓸 수 있는 시간**

    ⚠️ 2026-08-21 — 처음에는 `seconds` 에 딱 맞췄다. 그런데 영상 만드는 쪽이
       32음절을 4.4초에 쏟아내는 바람에(초당 7.3음절), 우리 목소리도 똑같이
       급해져 **애써 바꾼 보람이 없었다.**
       → 자연스럽게 읽은 길이가 `room` 안에 들어가면 **그대로 둔다.**
         넘칠 때만, 그것도 `room` 에 맞춰 조금만 빠르게 한다.
    """
    p = say(text, voice, 1.0, pitch, out)
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
        p = say(text, voice, rate, pitch, out)
        d = dur_of(p)
    if d > limit + 0.1:
        print(f"    ⚠️ 대사가 길어 {d - limit:.2f}초 넘친다 "
              f"— 대사를 조금 줄이면 좋다 (\"{str(text)[:14]}…\")")
    return p, d


# ⭐⭐ 2026-08-21 — 운영자가 구글 목소리를 **아직 한 번도 못 들었다.**
#    쇼츠는 5컷이 다 있어야 만들어지므로, 목소리를 확인하려면 영상 다섯 개를
#    먼저 뽑아야 했다. 되돌아오는 길이 너무 길다.
#    → 대본의 대사만으로 **견본 소리 한 개**를 만든다. 버튼 한 번, 1분이면 된다.
def sample(sid, no, out, gap=0.45):
    """대본에서 그 화 1컷 대사를 뽑아 견본 소리를 만든다."""
    import sys as _s
    _s.path.insert(0, str(Path(__file__).resolve().parent))
    import shorts as SH                                      # noqa: E402

    doc = json.loads((Path(__file__).resolve().parent.parent / "data" /
                      "series" / f"{sid}.json").read_text(encoding="utf-8"))
    ep = next((e for e in doc["episodes"] if int(e.get("no", 0)) == int(no)),
              None)
    if not ep:
        raise SystemExit(f"❌ {sid} 에 {no}화가 없다")
    voices = pick_voices(doc.get("characters"))
    turns = []
    for c in ep["cuts"]:
        turns += SH.dia_turns(c.get("prompt"))
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
        p = say(text, v, 1.0, tone_of(text), tmp / f"s{i}.wav")
        made.append(p)
        print(f"  🎙 {who} ({v}) — {text}")

    # 사이를 조금 띄워 이어 붙인다
    sil = tmp / "gap.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"anullsrc=r=48000:cl=stereo:d={gap}", str(sil)],
                   check=True)
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\nfile '{sil.resolve()}'\n"
                           for p in made), encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-ac", "2", "-b:a", "160k", str(out)],
                   check=True)
    return out


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--say", default="")
    a.add_argument("--sample", default="", help="예: S001 — 그 대본으로 견본 소리")
    a.add_argument("--ep", type=int, default=1)
    a.add_argument("--voice", default="ko-KR-Neural2-A")
    a.add_argument("--sec", type=float, default=0.0)
    a.add_argument("--out", default="tts.wav")
    g = a.parse_args()
    if not key():
        print("❌ GOOGLE_TTS_KEY 가 없다 (깃허브 시크릿에 넣어야 한다)",
              file=sys.stderr)
        return 2
    if g.sample:
        f, m = best_voices("FEMALE")[0], best_voices("MALE")[0]
        print(f"목소리 — 여자 {f} · 남자 {m}\n")
        p = sample(g.sample, g.ep, g.out)
        print(f"\n✅ {p} — {dur_of(p):.1f}초")
        return 0
    if not g.say:
        print("❌ --say 나 --sample 중 하나는 있어야 한다", file=sys.stderr)
        return 2
    if g.sec > 0:
        p, d = say_to_fit(g.say, g.voice, g.sec, g.out)
    else:
        p, d = say(g.say, g.voice, 1.0, 0.0, g.out), 0.0
        d = dur_of(p)
    print(f"✅ {p} — {d:.2f}초")
    return 0


if __name__ == "__main__":
    sys.exit(main())
