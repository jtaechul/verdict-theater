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
SKIP = []


def skip(why):
    """건너뛴 검사는 **끝에 크게 적는다.**

    ⚠️ 2026-08-12 — 이것 때문에 사고가 났다. 이 파일의 검사 넷은 ffmpeg·numpy 가
       없으면 조용히 건너뛰는데, 개발하는 자리에는 numpy 가 없었다. 그래서
       "✅ 효과음 규칙 모두 통과" 를 보고 올렸는데 깃허브에서는 그 검사가 실제로
       돌아 **두 번 연달아 빨간 X** 가 났다. 통과와 '안 해 봄' 은 다른 것이다.
    """
    SKIP.append(why)
    print(f"  (건너뜀 — {why})")


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
    skip("ffmpeg 나 numpy 가 없어 소리를 잴 수 없습니다")
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
    skip("소리를 잴 수 없거나 볼 파일이 없습니다")
else:
    beeps = [p.stem for p in sorted(A.SFX_DIR.glob("*.mp3")) if Q.is_beep(p)]
    print(f"  아직 가짜인 것: {', '.join(beeps) if beeps else '없음'}")
    # 있어도 실패로 보지 않는다 — 아래 [3]이 '깔리지 않는다' 를 보장하기 때문이다.

print("\n[3] 삑 소리는 절대 깔리지 않는다 (가장 중요한 규칙)")
if not (HAVE_FFMPEG and HAVE_NUMPY):
    skip("소리를 잴 수 없거나 볼 파일이 없습니다")
else:
    for p in sorted(A.SFX_DIR.glob("*.mp3")):
        if Q.is_beep(p):
            eq(A.have(p.stem), False, f"'{p.stem}' 은 못 쓴다")
    # 빼 달라고 한 소리(BANNED_SFX)는 삑이 아니어도 못 쓰는 게 **맞다** — 뺀다.
    real = [p.stem for p in sorted(A.SFX_DIR.glob("*.mp3"))
            if not Q.is_beep(p) and not p.stem.startswith("tr_")
            and p.stem not in A.BANNED_SFX]
    eq(all(A.have(n) for n in real), True, f"진짜 소리 {len(real)}개는 쓸 수 있다")

print("\n[4] 이미 깔려 있는 삑 소리는 떼어 낸다")
if not (HAVE_FFMPEG and HAVE_NUMPY):
    skip("소리를 잴 수 없거나 볼 파일이 없습니다")
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

print("\n[5-2] 빼 달라고 한 소리를 **다시 만들 방법이 남아 있지 않은가**")
# ⚠️ 2026-08-12 — 파일만 지우고 '만드는 법' 을 남겨 뒀더니, [소리 (비용 0원)]
#    버튼 한 번이면 되살아나는 상태였다. 지우는 것으로는 부족하다.
sys.path.insert(0, str(HERE.parent / "src"))
import assets_gen as G  # noqa: E402
for nm in sorted(A.BANNED_SFX | {"monitor"}):
    eq(nm in G.SFX_RECIPE or nm in G.AMB_RECIPE, False, f"'{nm}' 만드는 법이 없다")

print("\n[5-3] 빼 달라고 한 소리는 파일이 멀쩡해도 안 쓴다")
# footsteps 는 삑이 아니라 둔탁한 잡음이라 is_beep 로는 안 걸린다.
for nm in sorted(A.BANNED_SFX):
    eq(A.have(nm), False, f"'{nm}' 은 파일이 있어도 못 쓴다")

print("\n[6] 대본이 쓰는 효과음 이름이 실제 파일과 맞는가")
names = set(words) | {n for v in A.BY_BG.values() for n in v}
missing = [n for n in sorted(names) if not (A.SFX_DIR / f"{n}.mp3").exists()]
eq(missing, [], f"이름 {len(names)}개 모두 파일이 있다")

print("\n[7] 못 재는 상황에서는 막지 않는다 (멀쩡한 소리까지 없애지 않게)")
eq(Q.is_beep("/그런/파일/없음.mp3"), False, "잴 수 없으면 통과시킨다")

print("\n[8] 저장해 둔 대본에 삑 소리가 남아 있지 않은가")
# ⚠️ 2026-08-12 — 여기가 **EP001 만** 보고 있었다. 그래서 EP002 에 남아 있던
#    footsteps 4컷을 아무도 못 잡았다. 회차가 늘 때마다 이 줄을 고쳐야 하는
#    검사는 반드시 언젠가 뒤처진다. 이제 있는 대본을 **전부** 훑는다.
import json  # noqa: E402
SC = HERE.parent / "data" / "scripts"
docs = sorted(SC.glob("EP*.json")) if SC.is_dir() else []
docs = [p for p in docs if not p.name.endswith((".eval.json", ".shorts.json"))]
if docs and HAVE_FFMPEG and HAVE_NUMPY:
    for p in docs:
        doc = json.loads(p.read_text(encoding="utf-8"))
        eq(A.strip_beeps(doc, check=True), [], f"{p.stem} 에 삑 소리 없음")
else:
    skip("소리를 잴 수 없거나 볼 파일이 없습니다")

print()
if FAIL:
    print(f"❌ {len(FAIL)}가지 틀렸습니다")
    for f in FAIL:
        print("   -", f)
    sys.exit(1)
if SKIP:
    # '통과' 라고 적지 않는다. 안 해 본 것을 통과라고 부르면 그 말을 믿고 올리게 된다.
    print(f"⚠️  건너뛴 검사 {len(SKIP)}개 — 이 결과는 **완전하지 않습니다**")
    for s in dict.fromkeys(SKIP):
        print(f"   - {s}")
    print("   깃허브(자체 점검)에서는 전부 돌아갑니다. 거기 초록불을 보고 판단하십시오.")
else:
    print("✅ 효과음 규칙 모두 통과")
