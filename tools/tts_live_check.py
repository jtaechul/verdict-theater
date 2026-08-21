#!/usr/bin/env python3
"""⭐ 한국어 목소리 열쇠가 **진짜로 살아 있는지** 확인한다. 0원(석 자만 만든다).

    python3 tools/tts_live_check.py

왜 (2026-08-21)
    운영자가 GOOGLE_TTS_KEY 를 깃허브에 넣었다. 그런데 넣은 것과 **되는 것**은
    다르다 — API 를 안 켰거나, 열쇠에 제한이 걸려 있거나, 결제 계정이 없으면
    영상 만들 때가 되어서야 실패한다. 그때 알면 늦다.
    그래서 **밀어 넣을 때마다** 석 자짜리 소리를 한 번 만들어 본다.
    (석 자면 무료 한도 100만 자 중 0.0003%다. 값은 0원이다)

    ⚠️ 열쇠가 아예 없으면 **그냥 건너뛴다** — 열쇠 없이도 영상은 나오기 때문이다.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import tts as T                                             # noqa: E402

print("⭐ 한국어 목소리 열쇠 확인\n")

# ⚠️ 2026-08-21 — 열쇠가 없을 때 그냥 건너뛰었더니, 초록불이 **열쇠가 된다는
#    뜻인지 그냥 넘어갔다는 뜻인지** 알 수 없었다. 깃허브 안에서는 열쇠가
#    있어야 정상이므로, 없으면 **빨간불**을 낸다. 그래야 초록불이 곧 증거가 된다.
#    (내 컴퓨터에서 그냥 돌릴 때는 예전처럼 건너뛴다)
import os                                                   # noqa: E402
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"


def note(line):
    """깃허브 실행 화면에도 한 줄 남긴다 (운영자가 눈으로 본다)."""
    f = os.environ.get("GITHUB_STEP_SUMMARY")
    if f:
        with open(f, "a", encoding="utf-8") as h:
            h.write(line + "\n")


if not T.key():
    if IN_CI:
        print("   ❌ GOOGLE_TTS_KEY 가 깃허브에 없다")
        print("      시크릿 이름이 정확히 GOOGLE_TTS_KEY 인지 확인한다")
        note("- ❌ 한국어 목소리 열쇠가 없습니다")
        sys.exit(1)
    print("   ⏭  GOOGLE_TTS_KEY 가 없다 — 건너뛴다")
    print("      (열쇠가 없으면 영상의 원래 소리를 그대로 쓴다. 영상은 나온다)")
    sys.exit(0)

tmp = Path(tempfile.mkdtemp())

# ⭐ 2026-08-21 — 어떤 목소리를 쓰게 되는지 **눈으로 보이게** 남긴다.
#    Neural2 는 원어민이지만 아나운서처럼 밋밋하고, Chirp3-HD 는 훨씬
#    사람처럼 말한다. 무엇이 잡혔는지 모르면 품질 이야기를 할 수가 없다.
_all = T.list_voices()
print(f"   구글이 가진 한국어 목소리 {len(_all)}개")
_f, _m = T.best_voices("FEMALE"), T.best_voices("MALE")
print(f"   여자 → {_f[0]}")
print(f"   남자 → {_m[0]}")
note(f"- 쓰는 목소리: 여자 {_f[0]} · 남자 {_m[0]}")
print()

ok = True
for voice in (_f[0], _m[0]):
    out = tmp / f"{voice}.wav"
    try:
        p = T.say("확인", voice, 1.0, 0.0, out)
    except Exception as e:                                   # noqa: BLE001
        print(f"   ❌ {voice} 실패\n   {e}")
        ok = False
        break
    if p is None or not Path(p).exists():
        print(f"   ❌ {voice} — 소리 파일이 안 만들어졌다 (say 가 빈손을 줬다)")
        ok = False
        break
    d = T.dur_of(p)
    size = Path(p).stat().st_size
    good = d > 0.15 and size > 2000
    print(f"   {'✅' if good else '❌'} {voice} — {d:.2f}초 · {size:,}바이트")
    ok = ok and good

print("\n" + "─" * 52)
if not ok:
    print("❌ 한국어 목소리를 못 만든다. 위 까닭대로 고친 뒤 다시 밀어 넣어라")
    note("- ❌ 한국어 목소리를 못 만듭니다 (위 빨간 칸을 열어 보십시오)")
    sys.exit(1)
print("✅ 한국어 목소리 열쇠가 살아 있다 — 이제 쇼츠에 자동으로 얹힌다")
note("- ✅ 한국어 목소리 열쇠가 살아 있습니다 (구글이 소리를 만들어 줬습니다)")
