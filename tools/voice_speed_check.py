#!/usr/bin/env python3
"""⭐ 인물 목소리(나이·성별·톤 고정) · 말 빠르기(1.28배 · 뭉개짐 방지) — 값 0원

    python3 tools/voice_speed_check.py

2026-10-02 손님: "1.28배로 가자 그리고 발음 뭉개지지 않게끔 … 코드에 넣고"
                 "등장인물별로 목소리 섞이지 않게 … 나이 성별 톤 부분은 핵심 규칙에"
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import short90 as S9                                          # noqa: E402
import story90 as T                                           # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


print("⭐ 목소리 · 빠르기 점검\n")
print("① 말 빠르기")
ck("조립 배속은 1.28", S9.SPEED == 1.28, str(S9.SPEED))
ck("상한은 tts 의 상한과 같다 (1.28)", S9.SPEED_MAX == 1.28)
os.environ.pop("VOICE_STYLE", None)
ck("기본 결이면 조립에서 1.28배를 그대로 건다", abs(S9.speed() - 1.28) < 1e-9, str(S9.speed()))
os.environ["VOICE_STYLE"] = "dry"                       # 만들 때 1.12배
tot = S9.speed() * S9.baked_rate()
ck("만들 때 빨라진 결이면 조립 배속을 줄여 합계가 1.28 을 넘지 않는다 (겹쳐 감기 금지)",
   abs(tot - 1.28) < 1e-6 and S9.speed() < 1.28, f"{S9.speed():.3f} × {S9.baked_rate()}")
os.environ.pop("VOICE_STYLE", None)
src = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
ck("조립은 tempo_filter 한 곳으로만 건다 (atempo 를 따로 박지 않는다)",
   "atempo={SPEED" not in src and "tempo_filter(speed())" in src)
f = S9.tempo_filter(1.28)
ck("자음을 살리는 감기 (rubberband · crisp · 높낮이 그대로)",
   ("rubberband" in f and "transients=crisp" in f and "formant=preserved" in f)
   or (not S9.has_rubberband() and f.startswith("atempo=")), f)
with tempfile.TemporaryDirectory() as t:
    a, b = Path(t) / "a.wav", Path(t) / "b.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "sine=frequency=300:duration=4", "-ar", "48000", str(a)], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(a), "-af", f, str(b)],
                   check=True)
    got = S9.dur_of(b)
    ck("실제로 1.28배 짧아진다", abs(got - 4 / 1.28) < 0.05, f"{got:.3f}초")
bs = (ROOT / "tools" / "build_short90.py").read_text(encoding="utf-8")
ck("옴니 대사 지시에 '또박또박' 이 들어 있다",
   "crisp and clearly articulated" in bs and "clearly articulated" in src)

print("\n② 인물 목소리 — 나이 · 성별 · 톤 고정")
cast = [
    {"name": "어머니", "sex": "여", "age": 78,
     "voice": "a warm mid-range woman's voice in her seventies, native Korean "
              "speaker, weary and a little breathy"},
    {"name": "아들", "sex": "남", "age": 52,
     "voice": "a woman's voice in her thirties, native Korean speaker"},
    {"name": "며느리", "sex": "여", "age": 48, "voice": ""},
    {"name": "사위", "sex": "남", "age": 55, "voice": "low gravelly, impatient"},
    {"name": "딸", "sex": "여", "age": 45,
     "voice": "a clear woman's voice in her forties, native Korean speaker, "
              "cool and unhurried"},
]
fixed = T.fix_voices(cast)
by = {q["name"]: q["voice"] for q in fixed}
ck("제대로 적힌 줄은 그대로 둔다", by["어머니"] == cast[0]["voice"], by["어머니"])
ck("성별·나이대가 틀린 줄은 인물표대로 고친다 (52세 남자)",
   "man's voice in his fifties" in by["아들"] and "woman" not in by["아들"], by["아들"])
ck("빈 줄은 나이·성별·기본 톤으로 채운다", "woman's voice in her forties" in by["며느리"]
   and by["며느리"].split("native Korean speaker, ")[1].strip(), by["며느리"])
ck("모자란 줄의 결(톤)은 살린다", "impatient" in by["사위"], by["사위"])
for nm, v in by.items():
    low = v.lower()
    ck(f"{nm}: 성별 · 나이대 · 한국어 원어민 · 톤 네 가지를 다 갖춘다",
       re.search(r"\b(wo)?man's voice in (his|her) \w+ies\b", low) is not None
       and "native korean speaker, " in low and low.split("native korean speaker, ")[1], v)
ck("사람마다 목소리 줄이 다르다", len(set(by.values())) == len(by))
ck("같은 성별·나이대 둘째는 결을 하나 더 붙여 갈라 놓는다",
   any(x in by["사위"] for x in T.VOICE_SPLIT) and any(x in by["딸"] for x in T.VOICE_SPLIT))
ck("여러 번 돌려도 같다", [q["voice"] for q in T.fix_voices(fixed)] == [q["voice"] for q in fixed])
ck("넘겨받은 인물표는 건드리지 않는다", cast[2]["voice"] == "")
d = T.shape_drama({"cuts": [], "cast": [dict(x) for x in cast]})
ck("2분 드라마 꼴 맞추기(shape_drama)가 목소리를 고정한다",
   [p["voice"] for p in d["cast"]] == [q["voice"] for q in fixed])
ck("옴니 대사 컷은 고정된 목소리 줄을 쓴다 (아무 목소리로 넘어가지 않는다)",
   "ST90.fix_voices(chars)" in bs and "ST90.voice_line(ch)" in bs
   and "a natural native Korean voice'}" not in bs)

print("─" * 56)
if bad:
    print(f"❌ {len(bad)}개 걸렸습니다 — 고치고 다시")
    sys.exit(1)
print("✅ 목소리: 나이·성별·톤 고정 · 빠르기: 1.28배 한 번만 · 자음 살리기")
