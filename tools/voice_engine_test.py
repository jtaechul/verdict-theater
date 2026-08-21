#!/usr/bin/env python3
"""⭐ 목소리 엔진이 제대로 갈렸는지 확인한다 (인터넷 없이, 값 0원).

    python3 tools/voice_engine_test.py

왜 (2026-08-21 · 운영자: "이거 진짜 그냥 기계가 읽어주는 놈 같다. 당장 바꿔.")
    목소리를 구글 클라우드 TTS 에서 **제미나이**로 갈아탔다. 제미나이는 대사와
    함께 "이를 악물고 낮게 몰아붙이듯 말한다" 같은 **연기 지시**를 받는다.

    갈아타면서 조용히 깨질 수 있는 자리가 여럿이다 —
      · 열쇠 보는 자리가 GOOGLE_TTS_KEY 하나만 보면, 제미나이 열쇠만 있을 때
        "열쇠 없음" 으로 판단해 원래(외국인 같은) 소리를 그냥 써 버린다
      · 되돌아갈 목소리 이름이 ko-KR-… 로 박혀 있으면 제미나이에 그 이름을
        넘겨 400 이 난다
      · 연기 지시가 대사와 섞이면 지시를 소리 내어 읽어 버린다
    여기서 그 자리들을 인터넷 없이 미리 밟아 본다.
"""
import os
import re
import sys
import tempfile
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import tts as T                                             # noqa: E402

fail = []


def ck(cond, what, why=""):
    print(f"  {'✅' if cond else '❌'} {what}")
    if not cond:
        if why:
            print(f"      {why}")
        fail.append(what)


def env(**kw):
    """환경변수를 잠깐 바꿔 준다 (원래대로 되돌린다)."""
    old = {k: os.environ.get(k) for k in kw}

    class _C:
        def __enter__(self):
            for k, v in kw.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        def __exit__(self, *a):
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    return _C()


print("⭐ 목소리 엔진 확인\n")

# ── ① 어떤 엔진을 고르는가 ─────────────────────────────
print("① 엔진 고르기")
with env(GEMINI_API_KEY="x", GOOGLE_TTS_KEY="y", VOICE_ENGINE=None):
    ck(T.engine() == "gemini", "둘 다 있으면 제미나이를 쓴다")
    ck(T.key() == "x", "열쇠도 제미나이 것을 준다")
with env(GEMINI_API_KEY=None, GOOGLE_TTS_KEY="y", VOICE_ENGINE=None):
    ck(T.engine() == "google", "제미나이 열쇠가 없으면 구글로 되돌아간다")
    ck(T.key() == "y", "그때 열쇠는 구글 것")
with env(GEMINI_API_KEY="x", GOOGLE_TTS_KEY=None, VOICE_ENGINE="google"):
    ck(T.engine() == "google", "VOICE_ENGINE 으로 손수 고를 수 있다")
with env(GEMINI_API_KEY=None, GOOGLE_TTS_KEY=None, VOICE_ENGINE=None):
    ck(T.key() == "", "열쇠가 하나도 없으면 빈손 (원래 소리를 쓴다)")

# ── ② 목소리 이름이 엔진에 맞는가 ────────────────────
print("\n② 목소리 이름")
with env(GEMINI_API_KEY="x", GOOGLE_TTS_KEY=None, VOICE_ENGINE=None):
    f, m = T.best_voices("FEMALE"), T.best_voices("MALE")
    ck(f and not f[0].startswith("ko-KR-"), "제미나이일 때 제미나이 이름을 준다",
       f"받은 것: {f[:2]}")
    ck(m and not m[0].startswith("ko-KR-"), "남자도 마찬가지", f"받은 것: {m[:2]}")
    ck(not (set(f) & set(m)), "여자·남자 목소리가 겹치지 않는다")
with env(GEMINI_API_KEY=None, GOOGLE_TTS_KEY=None, VOICE_ENGINE="google"):
    f = T.best_voices("FEMALE")
    ck(f and f[0].startswith("ko-KR-"), "구글일 때는 ko-KR- 이름을 준다",
       f"받은 것: {f[:2]}")

# ⚠️ shorts.py 가 되돌아갈 자리로 ko-KR- 이름을 박아 두면, 제미나이를 쓸 때
#    그 이름이 그대로 넘어가 400 이 난다. 소스에서 직접 막는다.
sh = (ROOT / "src" / "shorts.py").read_text(encoding="utf-8")
ck("tts.VOICE_F[" not in sh and "tts.VOICE_M[" not in sh,
   "shorts.py 가 구글 목소리 이름을 박아 두지 않는다",
   "tts.best_voices(...) 로 받아야 엔진에 맞는 이름이 온다")

# ── ③ 사람마다 다른 목소리인가 ───────────────────────
print("\n③ 사람마다 다른 목소리")
CHARS = [
    {"name": "정미경", "role_en": "the wife", "flow_prompt": "a Korean woman in her late thirties"},
    {"name": "박성호", "role_en": "the husband", "flow_prompt": "a Korean man in his forties"},
    {"name": "유하늘", "role_en": "the other woman", "flow_prompt": "a Korean woman in her early thirties"},
]
with env(GEMINI_API_KEY="x", GOOGLE_TTS_KEY=None, VOICE_ENGINE=None):
    v = T.pick_voices(CHARS)
    ck(len({v["정미경"], v["박성호"], v["유하늘"]}) == 3,
       "세 사람이 서로 다른 목소리를 받는다", str(v))
    ck(v.get("Wife") == v.get("정미경"), "대사 줄 이름표(Wife)로도 찾아진다")
    ck(v.get("Other woman") == v.get("유하늘"),
       "두 낱말짜리 이름표(Other woman)도 찾아진다")
    ck(v["정미경"] in T.GEM_F and v["박성호"] in T.GEM_M,
       "여자는 여자 목소리, 남자는 남자 목소리")

# ── ④ 연기 지시 (이번 바꿈의 핵심) ───────────────────
print("\n④ 연기 지시")
CASES = [
    ("여보, 미안해. 내가 잘못했어.", "울음"),
    ("당신 진짜 미쳤어!", "이를 악물"),
    ("그래서 뭐 어쩌라고. 잘났다 정말.", "코웃음"),
    ("지금 그걸 말이라고 해?", "되묻"),
    ("그 사람 이름은 내가 안다.", "차분"),
]
seen = set()
for line, want in CASES:
    d = T.direct(line)
    seen.add(T.mood(line))
    ck(want in d, f"「{line[:12]}」 → 「{want}」 쪽으로 읽힌다", d[:80])

ck(len(seen) == len(CASES), "다섯 가지 말투가 서로 다르게 나온다",
   f"나온 말투 {len(seen)}가지")

LINE = "당신 진짜 제정신이야?"
d = T.direct(LINE)
ck(d.count(LINE) == 1, "대사가 지시 안에 딱 한 번만 들어간다")
ck(d.rstrip().endswith(f'"{LINE}"'), "대사가 맨 뒤 큰따옴표 안에 있다", d[-40:])
ck("\n" not in d, "지시가 여러 줄로 쪼개지지 않는다")
ck(len(d) < 200, f"지시가 너무 길지 않다 ({len(d)}자)")
ck(T.direct('"' + LINE + '"') == d, "이미 따옴표가 붙어 있어도 겹치지 않는다")
# ⚠️ 지시가 대사보다 지나치게 길면 모델이 지시를 본문으로 착각하기 쉽다
ck(len(d) - len(LINE) < 140, "지시가 대사에 비해 지나치게 길지 않다")

# ── ④-2 막히거나 한도에 걸렸을 때 물러서는가 ─────────
#    ⚠️ 이건 머리로 지어낸 시험이 아니다. 진짜로 걸어 보고 겪은 것만 담았다 —
#       · 같은 대사가 어떤 때는 SAFETY 로 막혔다 (막장 드라마 대사라 그렇다)
#       · 무료 한도는 1분에 10번, 구글이 "retry in 17.8s" 라고 알려 준다
#       · pro 계열은 무료 한도가 **0** 이라 기다려도 소용이 없다
#       · 대사만 덜렁 던지면 2.5 모델이 "읽는 대신 대답하려 했다" 며 거절했다
print("\n④-2 막혔을 때 물러서는가")
ck(T._wait_of("Please retry in 17.799746857s.") == 18.799746857,
   "구글이 알려 준 만큼 쉰다 (눈대중으로 안 쉰다)")
ck(T._wait_of("아무 말 없음") == 5.0, "안 알려 주면 5초만 쉰다")
ck(T._wait_of("Please retry in 999s.") == T.WAIT_MAX,
   "터무니없이 길면 상한까지만")
ck('"' in T.flat("안녕") and "읽어라" in T.flat("안녕"),
   "마지막 수단에도 '읽어라' 는 남긴다",
   "아무 지시도 없으면 모델이 읽는 대신 대답하려 든다 (실제로 400 이 났다)")

_calls = []


def _fake(model, prompt, voice, safe=True):
    _calls.append((model, prompt[:12]))
    n = len(_calls)
    if n == 1:
        raise T._Blocked("SAFETY")                     # 첫 지시가 막힌다
    if n == 2:
        raise T._Busy("한도", wait=0.01)                # 순한 지시는 한도에 걸린다
    return b"\x00\x01" * 1000, 24000                  # 쉬었다 다시 하니 된다


_ro, _rk, _rm = T._gem_once, T.gem_key, T.gem_order
T._gem_once, T.gem_key, T.gem_order = _fake, (lambda: "K"), (lambda: ["m1", "m2"])
try:
    _p = T.gem_say("당신 진짜 미쳤어!", "Kore", tempfile.mktemp(suffix=".wav"))
    ck(_p is not None and Path(_p).exists(), "막혀도 결국 소리를 만들어 낸다")
    ck(len(_calls) == 3, f"막힘→순한 지시, 한도→쉬었다 다시 (부른 횟수 {len(_calls)})")
    ck(_calls[0][0] == _calls[1][0] == "m1", "쓸데없이 모델부터 갈아타지 않는다")
finally:
    T._gem_once, T.gem_key, T.gem_order = _ro, _rk, _rm

_calls2 = []


def _dead(model, prompt, voice, safe=True):
    _calls2.append(model)
    if model == "m1":
        raise T._Busy("한도 0", wait=30.0, dead=True)   # 무료로 못 쓰는 모델
    return b"\x00\x01" * 1000, 24000


_ro, _rk, _rm = T._gem_once, T.gem_key, T.gem_order
T._gem_once, T.gem_key, T.gem_order = _dead, (lambda: "K"), (lambda: ["m1", "m2"])
try:
    _t0 = time.time()
    T.gem_say("가나다", "Kore", tempfile.mktemp(suffix=".wav"))
    ck(time.time() - _t0 < 5.0, "한도가 0 인 모델은 기다리지 않고 바로 넘어간다",
       f"{time.time() - _t0:.1f}초 걸렸다")
    ck(_calls2.count("m1") == 1, "그 모델을 되풀이해 부르지 않는다", str(_calls2))
finally:
    T._gem_once, T.gem_key, T.gem_order = _ro, _rk, _rm

# ── ④-3 한도와 고장을 갈라서 알리는가 ────────────────
#    ⚠️ 섞어 놓으면 밀어 넣을 때마다 하는 확인이 **한도 때문에** 빨간불이 되고,
#       운영자에게 "고장났다" 는 메일이 쓸데없이 간다. 실제로 그랬다.
print("\n④-3 한도와 고장을 갈라서 알리는가")
_ro, _rk, _rm = T._gem_once, T.gem_key, T.gem_order
T.gem_key, T.gem_order = (lambda: "K"), (lambda: ["m1"])
try:
    T._gem_once = lambda *a, **k: (_ for _ in ()).throw(T._Busy("한도", wait=0.01))
    try:
        T.gem_say("가", "Kore", tempfile.mktemp(suffix=".wav"))
        ck(False, "한도로 끝내 못 만들면 Busy 를 던진다", "아무것도 안 던졌다")
    except T.Busy:
        ck(True, "한도로 끝내 못 만들면 Busy 를 던진다")
    except Exception as e:                                   # noqa: BLE001
        ck(False, "한도로 끝내 못 만들면 Busy 를 던진다", type(e).__name__)

    T._gem_once = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("열쇠가 틀렸다"))
    try:
        T.gem_say("가", "Kore", tempfile.mktemp(suffix=".wav"))
        ck(False, "진짜 고장은 Busy 가 아니다", "아무것도 안 던졌다")
    except T.Busy:
        ck(False, "진짜 고장은 Busy 가 아니다", "Busy 로 잘못 알린다")
    except RuntimeError:
        ck(True, "진짜 고장은 Busy 가 아니다")
finally:
    T._gem_once, T.gem_key, T.gem_order = _ro, _rk, _rm

_lc = (ROOT / "tools" / "tts_live_check.py").read_text(encoding="utf-8")
ck("except T.Busy" in _lc and "sys.exit(0)" in _lc,
   "밀어 넣을 때 하는 확인이 한도를 '고장' 으로 안 본다",
   "한도로 빨간불이 나면 쓸데없는 실패 메일이 간다")
ck("for voice in (_f[0],):" in _lc,
   "밀어 넣을 때 하는 확인이 목소리를 한 번만 부른다",
   "무료 한도가 1분에 10번뿐이라 아껴 써야 한다")

# ── ⑤ 어디로 부르러 가는가 ──────────────────────────
print("\n⑤ 부르러 가는 곳")
went = []
T.google_say = lambda *a, **k: went.append("google") or Path("x")
T.gem_say = lambda *a, **k: went.append("gemini") or Path("x")
T.say("가", "ko-KR-Neural2-A", 1.0, 0.0, "/tmp/x.wav")
T.say("가", "Kore", 1.0, 0.0, "/tmp/x.wav")
ck(went == ["google", "gemini"],
   "ko-KR- 이름은 구글로, 그 밖은 제미나이로 간다", str(went))

# ── ⑥ 제미나이가 준 날것 소리를 wav 로 감싸는가 ──────
print("\n⑥ 날것 소리 감싸기")
tmp = Path(tempfile.mkdtemp())
p = T._pcm_wav(b"\x00\x01" * 24000, tmp / "a.wav", 24000)
with wave.open(str(p), "rb") as w:
    ck(w.getnchannels() == 1 and w.getsampwidth() == 2
       and w.getframerate() == 24000 and w.getnframes() == 24000,
       "24000Hz 홑소리 wav 로 제대로 감싼다")
ck(T._rate_of("audio/L16;codec=pcm;rate=24000") == 24000, "소리 빠르기를 읽는다")
ck(T._rate_of("") == 24000, "안 적혀 있으면 24000 으로 본다")

# ── ⑦ 워크플로가 열쇠를 넘겨 주는가 ─────────────────
print("\n⑦ 워크플로가 열쇠를 넘겨 주는가")
for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
    txt = wf.read_text(encoding="utf-8")
    uses = re.search(r"src/(tts|shorts)\.py", txt)
    if not uses:
        continue
    ck("GEMINI_API_KEY" in txt,
       f"{wf.name} 이 GEMINI_API_KEY 를 넘긴다",
       "안 넘기면 조용히 옛날(외국인 같은) 소리로 되돌아간다")

print("\n" + "─" * 52)
if fail:
    print(f"❌ {len(fail)}군데가 어긋난다")
    for f in fail:
        print(f"   · {f}")
    sys.exit(1)
print("✅ 목소리 엔진이 제미나이로 제대로 갈렸다")
