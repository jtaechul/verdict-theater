#!/usr/bin/env python3
"""⭐ 목소리 갈아 끼우기가 진짜로 되는지 본다. 0원 (열쇠 없이 돈다).

    python3 tools/dub_test.py

왜 (2026-08-21)
    영상 만드는 쪽의 한국어 발음을 프롬프트로는 못 고쳤다. 그래서 소리를
    **한국어 전용 목소리로 갈아 끼우기로** 했다. 그 갈아 끼우는 일이
    ① 원래 소리를 **완전히** 지우는가 (외국인 발음이 조금이라도 남으면 안 된다)
    ② 만든 목소리를 **말하던 그 자리에** 놓는가 (입모양이 어긋나면 안 된다)
    ③ 길이가 안 늘어나는가
    를 **진짜 소리 파일로** 확인한다. 열쇠 없이 돌 수 있게 가짜 목소리를 쓴다.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import shorts as S                                          # noqa: E402
import tts as T                                             # noqa: E402

FAIL = []


def ck(label, cond, extra=""):
    print(("   ✅ " if cond else "   ❌ ") + label + (f"  ({extra})" if extra else ""))
    if not cond:
        FAIL.append(label)


def run(*a):
    return subprocess.run(list(a), capture_output=True, text=True)


def silences(p):
    log = run("ffmpeg", "-hide_banner", "-i", str(p), "-af",
              "silencedetect=n=-35dB:d=0.20", "-f", "null", "/dev/null").stderr
    out = []
    for m in re.finditer(r"silence_(start|end): ([\d.]+)", log):
        out.append((m.group(1), float(m.group(2))))
    return out


def vol(p):
    log = run("ffmpeg", "-hide_banner", "-i", str(p), "-af", "volumedetect",
              "-f", "null", "/dev/null").stderr
    m = re.search(r"mean_volume: ([-\d.]+) dB", log)
    return float(m.group(1)) if m else 0.0


print("⭐ 목소리 갈아 끼우기 시험\n")
tmp = Path(tempfile.mkdtemp())

# 원본 흉내 — **실제로 만들어진 1화 1컷을 그대로 흉내 낸다** (2026-08-21 실측)
#   0.00~0.98 무음 / 0.98~2.55 말 / 2.79~4.20 말 / 4.57~6.02 말
REAL = [(0.98, 2.55), (2.79, 4.20), (4.57, 6.02)]
src = tmp / "src.mp4"
# 토막마다 소리 파일을 만들어 제자리에 얹는다 (dub 이 쓰는 것과 같은 방법)
_parts = []
for i, (a, b) in enumerate(REAL):
    w = tmp / f"t{i}.wav"
    run("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
        f"sine=frequency=300:duration={b - a:.2f}:sample_rate=48000",
        "-ac", "2", str(w))
    _parts.append((a, w))
_args = ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", "color=c=gray:s=320x180:d=6:r=24",
         "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
for _, w in _parts:
    _args += ["-i", str(w)]
_fil, _mix = [], "[1:a]"
for i, (a, _) in enumerate(_parts):
    _fil.append(f"[{i + 2}:a]adelay={int(a * 1000)}|{int(a * 1000)}[d{i}]")
    _mix += f"[d{i}]"
_fil.append(f"{_mix}amix=inputs={len(_parts) + 1}:normalize=0[a]")
_args += ["-filter_complex", ";".join(_fil), "-map", "0:v", "-map", "[a]",
          "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p",
          "-c:a", "aac", str(src)]
run(*_args)
ck("시험용 원본이 만들어진다", src.exists() and src.stat().st_size > 0)
_got = [round(v, 2) for k, v in silences(src) if k == "end"]
ck("원본이 실제 영상처럼 말 자리를 갖는다", len(_got) == 3, str(_got))

print("\n① 열쇠가 없으면 아무것도 안 하고 원래 소리를 그대로 쓴다")
ck("열쇠 없으면 False 를 준다 (영상은 계속 나온다)",
   S.dub(src, [("Wife", "가나다")], {}, tmp / "x.mp4", tmp) is False)

print("\n② 대사 줄에서 말하는 사람과 대사를 뽑는가")
pr = ('DIALOGUE: [LANGUAGE: KOREAN] each person speaks one after another\n'
      '  Wife (furious, in Korean): "당신 진짜 제정신이야?!"\n'
      '  Husband (annoyed, in Korean): "더는 숨 막혀서 못 살아."\n'
      '  Wife (shouting, in Korean): "누구 맘대로 집을 나가!"')
t = S.dia_turns(pr)
ck("세 마디를 말한 차례대로 뽑는다", len(t) == 3, str(t)[:60])
ck("말하는 사람이 맞다", [x[0] for x in t] == ["Wife", "Husband", "Wife"])
ck("말투 괄호는 떼어 낸다", t[0][1] == "당신 진짜 제정신이야?!", t[0][1])
ck("대사 없는 컷은 빈손", S.dia_turns("DIALOGUE: None.") == [])

print("\n③ 가짜 목소리로 **진짜 갈아 끼워** 본다 (열쇠 없이)")
real = [T.say, T.key]


def fake_say(text, voice="", rate=1.0, pitch=0.0, out=None):
    """가짜 목소리 — 글자 수만큼 긴 '삐' 소리."""
    sec = max(0.4, len(text) * 0.10 / max(0.5, float(rate)))
    p = Path(out or (tmp / "f.wav"))
    run("ffmpeg", "-v", "error", "-y", "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={sec:.2f}:sample_rate=48000",
        "-ac", "2", str(p))
    return p


T.say, T.key = fake_say, (lambda: "TEST")
out = tmp / "ko.mp4"
ok = S.dub(src, t, {"Wife": "ko-KR-Neural2-A", "Husband": "ko-KR-Neural2-C"},
           out, tmp)
T.say, T.key = real

ck("갈아 끼우기가 끝난다", ok is True)
if ok:
    ck("결과 파일이 생긴다", out.exists() and out.stat().st_size > 0)
    d = float(run("ffprobe", "-v", "error", "-show_entries", "format=duration",
                  "-of", "csv=p=0", str(out)).stdout.strip() or 0)
    ck("길이가 원본과 같다 (6초)", abs(d - 6.0) < 0.3, f"{d:.2f}초")
    sil = silences(out)
    starts = [v for k, v in sil if k == "end"]
    ck("소리가 실제로 들어갔다", vol(out) < -0.1 and vol(out) > -60,
       f"{vol(out):.1f} dB")
    ck("첫 목소리가 **원본이 말하던 자리**에서 시작한다",
       bool(starts) and abs(starts[0] - REAL[0][0]) < 0.35,
       f"{starts[0]:.2f}초 (원본 {REAL[0][0]}초)" if starts else "못 찾음")
    ck("목소리가 세 토막으로 갈린다 (사람마다 따로)", len(starts) == 3,
       f"{len(starts)}토막 — {[round(x, 2) for x in starts]}")
    ck("세 토막이 원본 자리와 거의 같다",
       len(starts) == 3 and all(abs(g - r[0]) < 0.35
                                for g, r in zip(starts, REAL)),
       f"{[round(x, 2) for x in starts]} vs {[r[0] for r in REAL]}")
    # ⭐ 외국인 발음이 조금이라도 남으면 안 된다 — 원본 소리를 완전히 지웠는가
    _q = [v for k, v in silences(out) if k == "start"]
    ck("원본 소리가 남아 있지 않다 (사이가 진짜 조용하다)",
       bool(_q) and len(_q) >= 2, f"{len(_q)}군데 조용함")

print("\n③-2 앞뒤 죽은 시간을 잘라 내는가 (제미나이 10초짜리도 쓸 수 있게)")
tight = S.trim_dead(src, tmp / "tight.mp4")
_td = float(run("ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "csv=p=0", str(tight)).stdout.strip() or 0)
ck("앞 무음이 잘린다", _td < 6.0 - 0.4, f"6.00초 → {_td:.2f}초")
ck("말은 하나도 안 잘린다",
   _td >= (REAL[-1][1] - REAL[0][0]), f"말한 구간 {REAL[-1][1] - REAL[0][0]:.2f}초 이상")
ck("첫 말 앞에 숨 쉴 자리를 남긴다", S.HEAD_PAD > 0)
ck("끝말 뒤에 여운을 남긴다", S.TAIL_PAD > S.HEAD_PAD)
_sil2 = [v for k, v in silences(tight) if k == "end"]
ck("자른 뒤에도 말 토막이 세 개다", len(_sil2) == 3,
   f"{[round(x, 2) for x in _sil2]}")
# 뒤에 긴 무음이 붙은 것(제미나이 10초짜리 흉내)도 잘리는가
long_src = tmp / "long.mp4"
run("ffmpeg", "-v", "error", "-y", "-i", str(src),
    "-af", "apad=whole_dur=10", "-t", "10",
    "-c:v", "copy", "-c:a", "aac", str(long_src))
_lt = S.trim_dead(long_src, tmp / "long_tight.mp4")
_ld = float(run("ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "csv=p=0", str(_lt)).stdout.strip() or 0)
ck("10초짜리 뒤 무음도 잘린다", _ld < 7.0, f"10.00초 → {_ld:.2f}초")

print("\n③-3 못 읽는 클립이 와도 30초짜리가 통째로 날아가지 않는가")
bad = tmp / "not_a_video.mp4"
bad.write_bytes("이건 영상이 아니다".encode("utf-8"))
ck("자르기가 죽지 않고 원본을 그대로 준다", S.trim_dead(bad, tmp / "b.mp4") == bad)
_r = real
T.say, T.key = fake_say, (lambda: "TEST")
ck("목소리 갈아 끼우기도 죽지 않고 False 를 준다",
   S.dub(bad, [("Wife", "가나다")], {}, tmp / "b2.mp4", tmp) is False)
T.say, T.key = _r

print("\n④ 시간에 맞춰 말 속도를 고치는가")
ck("속도가 사람 소리 범위 안에서만 움직인다",
   T.RATE_MIN >= 0.7 and T.RATE_MAX <= 1.5,
   f"{T.RATE_MIN}~{T.RATE_MAX}")

# ⭐ 2026-08-21 — 영상 쪽이 급하게 쏟아냈다고 우리 목소리까지 급해지면
#    애써 바꾼 보람이 없다. 쓸 수 있는 시간(room) 안이면 **그대로 둔다.**
_calls = []
_rs, _rk = T.say, T.key
T.key = lambda: "TEST"


def _spy(text, voice="", rate=1.0, pitch=0.0, out=None):
    _calls.append(round(float(rate), 3))
    return fake_say(text, voice, rate, pitch, out)


T.say = _spy
_calls.clear()
T.say_to_fit("가나다라마", "v", 0.5, tmp / "fit1.wav", room=3.0)
ck("여유가 있으면 자연스러운 속도 그대로 (다시 안 만든다)",
   _calls == [1.0], f"{_calls}")
_calls.clear()
T.say_to_fit("가나다라마바사아자차카타파하", "v", 0.4, tmp / "fit2.wav", room=0.6)
ck("정말 넘칠 때만 빠르게 한다", len(_calls) == 2 and _calls[1] > 1.0, f"{_calls}")
ck("빨라져도 사람 소리 범위를 안 넘는다 (2.3배 같은 값을 안 넘긴다)",
   all(T.RATE_MIN <= r <= T.RATE_MAX for r in _calls), f"{_calls}")
T.say, T.key = _rs, _rk
ck("느낌표가 있으면 조금 높게 읽는다", T.tone_of("나가!") > 0)
ck("보통 말은 그대로", T.tone_of("알았어.") == 0.0)

print("\n④-2 say() 가 **진짜로 소리 파일을 돌려주는가** (가짜 구글 응답으로)")
# ⚠️ 2026-08-21 — say() 한가운데에 도우미 함수를 끼워 넣었다가 마지막 세 줄이
#    딸려 들어가 **None 을 돌려줬다.** 깃허브가 잡아 주기 전까지 몰랐다.
#    이제 구글 응답을 흉내 내서 say() 를 **진짜로 불러** 본다.
import base64 as _b64                                       # noqa: E402
import io as _io                                            # noqa: E402
import urllib.request as _ur                                # noqa: E402


class _Resp(_io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


_wav = tmp / "canned.wav"
run("ffmpeg", "-v", "error", "-y", "-f", "lavfi",
    "-i", "sine=frequency=440:duration=0.5:sample_rate=48000", "-ac", "2",
    str(_wav))
_body = ('{"audioContent":"'
         + _b64.b64encode(_wav.read_bytes()).decode("ascii") + '"}')
_real_open, _real_key = _ur.urlopen, T.key
_ur.urlopen = lambda *a, **k: _Resp(_body.encode("utf-8"))
T.key = lambda: "TEST"
try:
    _got = T.say("확인", "ko-KR-Neural2-A", 1.0, 0.0, tmp / "said.wav")
    ck("say() 가 None 이 아니라 파일 경로를 돌려준다", _got is not None, str(_got))
    ck("그 파일이 진짜로 있다", _got is not None and Path(_got).exists())
    ck("빈 파일이 아니다", _got is not None and Path(_got).stat().st_size > 2000,
       f"{Path(_got).stat().st_size:,}바이트" if _got else "없음")
    ck("길이를 잴 수 있다", _got is not None and T.dur_of(_got) > 0.1,
       f"{T.dur_of(_got):.2f}초" if _got else "")
finally:
    _ur.urlopen, T.key = _real_open, _real_key

print("\n④-3 구글이 거절하면 **까닭을 쉬운 말로** 알려 주는가")
for code, msg, want in [
        (403, "Cloud Text-to-Speech API has not been used in project", "켜지 않았다"),
        (400, "API key not valid. Please pass a valid API key.", "열쇠가 잘못됐다"),
        (403, "This API method requires billing to be enabled", "결제 계정"),
        (403, "Requests from referer are blocked", "사용 제한"),
        (429, "Quota exceeded", "너무 많이")]:
    ck(f"{want} 를 알려 준다", want in T.explain(code, msg), T.explain(code, msg)[:40])

print("\n④-4 그림 모듈(PIL) 없이도 소리를 만들 수 있는가")
# ⚠️ 2026-08-21 — 목소리 견본 워크플로가 **첫 시도에 죽었다**:
#      ModuleNotFoundError: No module named 'PIL'
#    소리만 만드는 일인데 tts.sample() 이 shorts 를 들여왔고, shorts 가
#    그림 모듈을 끌고 왔다. 그 일에는 pillow 를 안 깔아 두었으니 당연히 죽는다.
#    → 대사 뽑기(dia_turns)를 대본 쪽으로 옮겼다. 다시 그러지 않게 **PIL 을
#      못 들여오게 막아 놓고** 진짜로 돌려 본다.
_blk = tmp / "noPIL"
(_blk / "PIL").mkdir(parents=True, exist_ok=True)
(_blk / "PIL" / "__init__.py").write_text(
    'raise ImportError("PIL 없음 (시험용으로 막아 두었다)")', encoding="utf-8")
_code = (
    "import sys, json;"
    "sys.path.insert(0, r'" + str(ROOT / 'src') + "');"
    "import tts, series;"
    "d=json.load(open(r'" + str(ROOT / 'data' / 'series' / 'S001.json') + "'));"
    "t=series.dia_turns(d['episodes'][0]['cuts'][0]['prompt']);"
    "print('OK', len(t), 'PIL' in sys.modules)"
)
_env = dict(**{k: v for k, v in __import__("os").environ.items()})
_env["PYTHONPATH"] = str(_blk)
_r = subprocess.run([sys.executable, "-c", _code], capture_output=True,
                    text=True, env=_env)
ck("PIL 을 막아 놔도 tts 가 열린다", _r.returncode == 0,
   (_r.stderr.strip().splitlines() or [""])[-1][:80])
ck("PIL 없이도 대사를 뽑는다", _r.stdout.startswith("OK 3"), _r.stdout.strip())
ck("소리 쪽이 그림 모듈을 안 끌어온다", "False" in _r.stdout, _r.stdout.strip())
_src = (ROOT / "src" / "tts.py").read_text(encoding="utf-8")
ck("tts.py 가 shorts 를 안 들여온다", "import shorts" not in _src)

print("\n④-5 소리·영상을 다루는 워크플로가 ffmpeg 를 깔아 두는가")
# ⚠️ 2026-08-21 — 목소리 견본이 **세 번째로** 죽었다. 이번 까닭은 ffmpeg 였다.
#    깃허브 실행기에는 기본으로 안 깔려 있는데, 소리 토막을 이어 붙이려면 필요하다.
#    (첫 번째는 PIL, 세 번째는 ffmpeg — 둘 다 "준비물을 안 깔았다" 는 같은 실수다)
NEEDS = ["src/shorts.py", "src/clip.py", "src/tts.py"]
for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
    txt = wf.read_text(encoding="utf-8")
    if not any(n in txt for n in NEEDS):
        continue
    ck(f"{wf.name} 이 ffmpeg 를 깔아 둔다", "ffmpeg" in txt,
       "소리·영상을 다루는데 준비물이 없다")

print("\n⑤ 사람마다 다른 목소리를 주는가")
chs = [{"name": "본처", "role_en": "the wife",
        "flow_prompt": "Korean woman, 52 years old."},
       {"name": "내연녀", "role_en": "the other woman",
        "flow_prompt": "Korean woman, 42 years old."},
       {"name": "남편", "role_en": "the husband",
        "flow_prompt": "Korean man, 55 years old."}]
v = T.pick_voices(chs)
ck("세 사람이 서로 다른 목소리", len({v["본처"], v["내연녀"], v["남편"]}) == 3,
   f'{v["본처"]} / {v["내연녀"]} / {v["남편"]}')
ck("남자는 남자 목소리", v["남편"] in T.VOICE_M, v["남편"])
ck("여자는 여자 목소리", v["본처"] in T.VOICE_F and v["내연녀"] in T.VOICE_F)
ck("대사 줄 이름표(Wife)로도 찾아진다", v.get("Wife") == v["본처"])
ck("'Other woman' 도 찾아진다 (Other Woman 아님)",
   v.get("Other woman") == v["내연녀"], str([k for k in v if " " in k]))

print("\n" + "─" * 52)
if FAIL:
    print(f"❌ 목소리 갈아 끼우기: {len(FAIL)}군데 틀렸다")
    for f in FAIL:
        print("   - " + f)
    sys.exit(1)
print("✅ 목소리 갈아 끼우기: 전부 통과")
