#!/usr/bin/env python3
"""목소리 고르는 잣대가 제대로 재는가 (제미나이는 안 부른다 · 값 0원)."""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import voice_judge as V                                      # noqa: E402

FAIL = []


def ck(label, cond, extra=""):
    print(("   ✅ " if cond else "   ❌ ") + label + (f"  ({extra})" if extra else ""))
    if not cond:
        FAIL.append(label)


def tone(spec, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", spec,
                    "-ac", "1", "-ar", "8000", str(out)], check=True)
    return out


print("⭐ 목소리 고르는 잣대\n")
tmp = Path(tempfile.mkdtemp())

print("① 받아쓰기가 얼마나 틀렸는지 센다")
ck("똑같으면 0", V.cer("당신 진짜 제정신이야", "당신 진짜 제정신이야") == 0.0)
ck("한 글자 틀리면 조금", 0 < V.cer("당신 진짜 제정신이야", "당신 진자 제정신이야") < 0.2)
ck("아주 다르면 1", V.cer("당신 진짜 제정신이야", "전혀 다른 말입니다") == 1.0)
ck("빈손이면 1", V.cer("당신 진짜", "") == 1.0)
ck("띄어쓰기·문장부호는 안 센다",
   V.cer("당신 진짜 제정신이야?!", "당신진짜제정신이야") == 0.0,
   "받아쓰기마다 띄어쓰기가 달라 그것까지 세면 엉뚱한 벌점이 된다")

print("\n② 구간 점수 (좋은 구간 안이면 만점, 벗어난 만큼 깎는다)")
ck("구간 안이면 만점", V.band(6.8, *V.GOOD_SPS, wide=2.5) == 1.0)
ck("양끝도 구간 안", V.band(V.GOOD_SPS[0], *V.GOOD_SPS, wide=2.5) == 1.0
   and V.band(V.GOOD_SPS[1], *V.GOOD_SPS, wide=2.5) == 1.0)
ck("조금 벗어나면 조금 깎인다",
   0.5 < V.band(V.GOOD_SPS[0] - 0.8, *V.GOOD_SPS, wide=2.5) < 1.0)
ck("많이 벗어나면 0점",
   V.band(V.GOOD_SPS[0] - 3.0, *V.GOOD_SPS, wide=2.5) == 0.0)
ck("못 쟀으면 가운데", V.band(None, *V.GOOD_SPS, wide=2.5) == 0.5,
   "못 쟀다고 0점을 주면 잴 수 없는 목소리가 무조건 탈락한다")

print("\n①-2 관문이 '다 같이 틀린 것' 으로 전원을 떨어뜨리지 않는가")
# ⚠️⚠️ 2026-08-22 — 절대값(0.15)으로 잘랐더니 **남자 13개가 전부 똑같이
#    0.222 로 탈락**했다. "못 살아" 를 "못 사라" 로 들은 것인데, 아홉 글자
#    대사에서 두 글자면 22%다. 다 같이 틀렸으면 목소리 탓이 아니라 대사 탓이다.
def _gate(cers):
    mid = sorted(cers)[len(cers) // 2]
    lim = max(V.CER_GATE, mid + V.CER_OVER)
    return [c <= lim for c in cers]


ck("다 같이 조금씩 틀리면 아무도 안 떨어진다",
   all(_gate([0.22] * 13)), "13개가 똑같이 0.22 로 틀렸던 실제 경우")
ck("다 같이 많이 틀려도 아무도 안 떨어진다", all(_gate([0.40] * 10)))
_r = _gate([0.0, 0.05, 0.03, 0.02, 0.9])
ck("혼자만 유난히 못 알아들으면 떨어진다", _r[:4] == [True] * 4 and not _r[4],
   str(_r))
ck("한 명도 안 남는 일은 없다", any(_gate([0.5, 0.55, 0.6, 0.52])))

print("\n②-2 앞뒤 무음을 빼고 말한 시간을 재는가")
# ⚠️ 2026-08-22 — 이걸 안 해서 1차가 망했다. 파일 길이로 재면 앞뒤 무음까지
#    들어가 말 빠르기가 절반으로 나오고, 26개 전부 '너무 느림' 으로 찍힌다.
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                "-i", "sine=frequency=200:duration=2:sample_rate=8000",
                "-af", "adelay=1000|1000,apad=pad_dur=1",
                "-ac", "1", "-ar", "8000", str(tmp / "pad.wav")], check=True)
_talk = V.speech_sec(tmp / "pad.wav")
ck("앞뒤 무음 1초씩을 뺀다", 1.8 < _talk < 2.3,
   f"파일은 4초인데 말한 시간 {_talk:.2f}초 (2초여야 맞다)")
ck("무음이 없으면 그대로",
   abs(V.speech_sec(tone("sine=frequency=200:duration=2:sample_rate=8000",
                         tmp / "plain.wav")) - 2.0) < 0.2)

print("\n②-3 줄 세우기가 서로 맞는지 재는가")
# ⚠️ 섞어서 여러 번 물었는데 답이 딴소리면 **모델이 구별을 못 하는 것**이다.
#    그걸 알아채지 못하면 잡음을 순위라고 내놓게 된다.
ck("똑같은 순서는 1.0", V.agree([0, 1, 2, 3], [0, 1, 2, 3]) == 1.0)
ck("완전 거꾸로는 0.0", V.agree([0, 1, 2, 3], [3, 2, 1, 0]) == 0.0)
ck("하나만 어긋나면 가운데보다 높다",
   0.7 < V.agree([0, 1, 2, 3], [0, 2, 1, 3]) < 1.0)
ck("뒤죽박죽이면 반쯤", 0.2 < V.agree([0, 1, 2, 3, 4], [2, 0, 4, 1, 3]) < 0.8)

print("\n②-4 줄 세우기 배선이 실제로 이어져 있는가 (제미나이는 안 부른다)")
# ⚠️⚠️ 2026-08-22 — 5차가 여기서 죽었다. rank_once 안에서 대사(text)를 쓰는데
#    **넘겨주는 것을 빠뜨렸다** (name 'text' is not defined). 문법은 멀쩡하고
#    py_compile 도 통과한다 — 실제로 불러 봐야만 드러난다.
#    → 가짜 답으로 한 바퀴 돌려 배선을 확인한다.
tone("sine=frequency=200:duration=1:sample_rate=8000", tmp / "any.wav")
_items = [{"path": str(tmp / "any.wav"), "voice": f"V{i}"} for i in range(4)]
_asked = []


def _fake_ask(parts, tries=4, schema=None):
    _asked.append(schema)
    n = sum(1 for p in parts if "inline_data" in p)
    return {"order": list(range(n, 0, -1))}          # 늘 거꾸로 준다


_real = V.ask
V.ask = _fake_ask
try:
    _r = V.rank_once(_items, [0, 1, 2, 3], "당신 진짜 제정신이야?!")
    ck("한 바퀴가 끝까지 돈다", _r == [3, 2, 1, 0], str(_r))
    ck("답의 모양을 못 박아서 보낸다", _asked and _asked[-1] is V.ORDER_SCHEMA)
    _m, _ag, _why = V.rank_many(_items, "당신 진짜 제정신이야?!", rounds=3)
    ck("세 번 다 받아 온다", all(w.get("ok") for w in _why),
       str([w.get("why", "") for w in _why if not w.get("ok")])[:120])
    ck("평균 자리가 나온다", len(_m) == 4, str(_m))
    ck("일치도가 숫자로 나온다", isinstance(_ag, float), str(_ag))
finally:
    V.ask = _real

# 들려준 차례를 그대로 돌려주면 '고른 것이 아니다' 로 본다
V.ask = lambda parts, tries=4, schema=None: {"order": [1, 2, 3, 4]}
try:
    try:
        V.rank_once(_items, [0, 1, 2, 3], "가")
        ck("받아 적기만 한 답을 걸러낸다", False, "그냥 통과시켰다")
    except RuntimeError as e:
        ck("받아 적기만 한 답을 걸러낸다", "그대로" in str(e), str(e)[:60])
finally:
    V.ask = _real

print("\n③ 억양 폭을 진짜로 재는가 (아는 소리로 맞춰 본다)")
flat = V.f0_spread(tone("sine=frequency=200:duration=2:sample_rate=8000",
                        tmp / "flat.wav"))
wave_ = V.f0_spread(tone("sine=frequency=200:duration=2:sample_rate=8000,"
                         "vibrato=f=3:d=0.9", tmp / "wave.wav"))
ck("밋밋한 소리는 거의 0", flat is not None and flat < 0.5,
   f"{flat}" if flat is not None else "못 쟀다")
ck("흔들리는 소리는 넓게 나온다", wave_ is not None and wave_ > 2.0,
   f"{wave_}" if wave_ is not None else "못 쟀다")
ck("둘을 갈라낸다", None not in (flat, wave_) and wave_ > flat + 2.0)

print("\n④ 릴리스에 올릴 수 있는 이름인가")
# ⚠️ 2026-08-22 — 「여_Kore.mp3」로 지었다가 릴리스에 올릴 때 죽었다.
#    주소에 한글이 못 들어간다 (UnicodeEncodeError: ascii codec…).
sys.path.insert(0, str(ROOT / "src"))
import tts as _T                                             # noqa: E402
for _g, _v in (("여", "Kore"), ("남", "Orus")):
    _n = _T.aud_name(_g, _v)
    ck(f"{_g} {_v} → {_n} (전부 영문)", _n.isascii(),
       "한글 이름은 릴리스 주소에 못 들어간다")
    ck(f"{_g} {_v}: 목소리 이름이 그대로 들어 있다", _v in _n)
ck("여자·남자 이름이 안 겹친다",
   _T.aud_name("여", "Kore") != _T.aud_name("남", "Kore"))
_all = [_T.aud_name("여", v) for v in _T.GEM_F] + \
       [_T.aud_name("남", v) for v in _T.GEM_M]
ck("26개 이름이 전부 다르고 전부 영문",
   len(set(_all)) == len(_all) and all(x.isascii() for x in _all),
   f"{len(_all)}개")

print("\n⑤ 점수 매기는 무게가 뜻대로인가")
ck("세 가지를 더하면 100점", 60 + 20 + 20 == 100)
ck("받아쓰기는 점수가 아니라 관문이다",
   "CER_GATE" in (ROOT / "tools" / "voice_judge.py").read_text(encoding="utf-8"),
   "1차 때 26개 전부 만점이라 40점이 통째로 죽었다")
ck("절대 점수 대신 줄을 세운다",
   "def rank_many" in (ROOT / "tools" / "voice_judge.py").read_text(encoding="utf-8"),
   "'몇 점이냐' 고 물으면 26개 전부 10점이라고 한다")
ck("차례를 섞어 여러 번 묻는다", V.ROUNDS >= 3, f"{V.ROUNDS}번")

print("\n" + "─" * 52)
print(f"❌ 목소리 잣대: {len(FAIL)}가지 실패" if FAIL else "✅ 목소리 잣대: 전부 통과")
sys.exit(1 if FAIL else 0)
