#!/usr/bin/env python3
"""효과음 규칙을 검사한다. 값 0원 · 인터넷 없이 돈다.

    python3 tools/sfx_test.py

왜 (2026-08-09 손님 지적: 6분30초~6분32초의 "삑 삑")
    그 자리에 깔린 `clock.mp3` 는 시계 소리가 아니라 1400Hz 전자음이었다.
    같은 가짜가 넷이었고 본편에서 12번 울렸다.
    **가짜 소리가 다시는 영상에 깔리지 않는지** 여기서 지킨다.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import add_sfx as A  # noqa: E402
import sfx_quality as Q  # noqa: E402

FAIL = []


def eq(got, want, what):
    if got != want:
        FAIL.append(f"{what}: 기대 {want!r} · 실제 {got!r}")
        print(f"  ✗ {what}: 기대 {want!r} · 실제 {got!r}")
    else:
        print(f"  ✓ {what}")


HAVE_FFMPEG = bool(shutil.which("ffmpeg"))
try:
    import numpy  # noqa: F401
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


def make(path, filt, sec=2.0):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", filt,
                    "-t", str(sec), "-b:a", "128k", str(path)], check=True)


print("\n[1] 기계가 만든 삑 소리를 잡아내는가")
if not (HAVE_FFMPEG and HAVE_NUMPY):
    print("  (건너뜀 — ffmpeg 나 numpy 가 없어 소리를 잴 수 없습니다)")
else:
    d = Path(tempfile.mkdtemp())
    make(d / "beep1400.mp3", "sine=frequency=1400")      # 6분30초의 그 소리
    make(d / "beep880.mp3", "sine=frequency=880")
    make(d / "hum52.mp3", "sine=frequency=52")
    make(d / "noise.mp3", "anoisesrc=color=brown")        # 진짜 소리에 가까운 잡음
    eq(Q.is_beep(d / "beep1400.mp3"), True, "1400Hz 순수음 = 삑")
    eq(Q.is_beep(d / "beep880.mp3"), True, "880Hz 순수음 = 삑")
    eq(Q.is_beep(d / "hum52.mp3"), True, "52Hz 순수음 = 삑")
    eq(Q.is_beep(d / "noise.mp3"), False, "넓게 퍼진 소리 = 진짜")

print("\n[2] 저장소에 있는 효과음 가운데 삑이 남아 있는지 (보고만 한다)")
if not (HAVE_FFMPEG and HAVE_NUMPY):
    print("  (건너뜀)")
else:
    beeps = [p.stem for p in sorted(A.SFX_DIR.glob("*.mp3")) if Q.is_beep(p)]
    print(f"  아직 가짜인 것: {', '.join(beeps) if beeps else '없음'}")
    # 있어도 실패로 보지 않는다 — 아래 [3]이 '깔리지 않는다' 를 보장하기 때문이다.

print("\n[3] 삑 소리는 절대 깔리지 않는다 (가장 중요한 규칙)")
if not (HAVE_FFMPEG and HAVE_NUMPY):
    print("  (건너뜀)")
else:
    for p in sorted(A.SFX_DIR.glob("*.mp3")):
        if Q.is_beep(p):
            eq(A.have(p.stem), False, f"'{p.stem}' 은 못 쓴다")
    real = [p.stem for p in sorted(A.SFX_DIR.glob("*.mp3"))
            if not Q.is_beep(p) and not p.stem.startswith("tr_")]
    eq(all(A.have(n) for n in real), True, f"진짜 소리 {len(real)}개는 쓸 수 있다")

print("\n[4] 이미 깔려 있는 삑 소리는 떼어 낸다")
if not (HAVE_FFMPEG and HAVE_NUMPY):
    print("  (건너뜀)")
else:
    beeps = [p.stem for p in sorted(A.SFX_DIR.glob("*.mp3")) if Q.is_beep(p)]
    if beeps:
        doc = {"acts": [{"cuts": [
            {"id": "T1", "sfx": f"sfx_{beeps[0]}"},
            {"id": "T2", "sfx": "sfx_paper"},
        ]}]}
        pulled = A.strip_beeps(doc)
        eq([i for i, _ in pulled], ["T1"], "가짜만 떼어 낸다")
        eq(doc["acts"][0]["cuts"][0]["sfx"], None, "가짜 자리는 비워진다")
        eq(doc["acts"][0]["cuts"][1]["sfx"], "sfx_paper", "진짜는 그대로 둔다")
    else:
        print("  (가짜가 하나도 없어 건너뜁니다 — 좋은 상태입니다)")

print("\n[5] 심전도 기계음은 아예 쓰지 않는다 (그 소리가 곧 '삑 삑')")
words = [n for _w, n in A.BY_WORD]
eq("monitor" in words, False, "낱말 표에 monitor 없음")
eq(any("monitor" in v for v in A.BY_BG.values()), False, "배경 표에 monitor 없음")
eq((A.SFX_DIR / "monitor.mp3").exists(), False, "monitor.mp3 파일도 없음")

print("\n[6] 대본이 쓰는 효과음 이름이 실제 파일과 맞는가")
names = set(words) | {n for v in A.BY_BG.values() for n in v}
missing = [n for n in sorted(names) if not (A.SFX_DIR / f"{n}.mp3").exists()]
eq(missing, [], f"이름 {len(names)}개 모두 파일이 있다")

print("\n[7] 못 재는 상황에서는 막지 않는다 (멀쩡한 소리까지 없애지 않게)")
eq(Q.is_beep("/그런/파일/없음.mp3"), False, "잴 수 없으면 통과시킨다")

print("\n[8] EP001 대본에 삑 소리가 남아 있지 않은가")
import json  # noqa: E402
p = HERE.parent / "data" / "scripts" / "EP001.json"
if p.exists() and HAVE_FFMPEG and HAVE_NUMPY:
    doc = json.loads(p.read_text(encoding="utf-8"))
    left = A.strip_beeps(doc, check=True)
    eq(left, [], "EP001 에 삑 소리 없음")
else:
    print("  (건너뜀)")

print()
if FAIL:
    print(f"❌ {len(FAIL)}가지 틀렸습니다")
    for f in FAIL:
        print("   -", f)
    sys.exit(1)
print("✅ 효과음 규칙 모두 통과")
