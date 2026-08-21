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

if not T.key():
    print("   ⏭  GOOGLE_TTS_KEY 가 없다 — 건너뛴다")
    print("      (열쇠가 없으면 영상의 원래 소리를 그대로 쓴다. 영상은 나온다)")
    sys.exit(0)

tmp = Path(tempfile.mkdtemp())
ok = True
for voice in (T.VOICE_F[0], T.VOICE_M[0]):
    out = tmp / f"{voice}.wav"
    try:
        p = T.say("확인", voice, 1.0, 0.0, out)
    except Exception as e:                                   # noqa: BLE001
        print(f"   ❌ {voice} 실패\n   {e}")
        ok = False
        break
    d = T.dur_of(p)
    size = p.stat().st_size
    good = d > 0.15 and size > 2000
    print(f"   {'✅' if good else '❌'} {voice} — {d:.2f}초 · {size:,}바이트")
    ok = ok and good

print("\n" + "─" * 52)
if not ok:
    print("❌ 한국어 목소리를 못 만든다. 위 까닭대로 고친 뒤 다시 밀어 넣어라")
    sys.exit(1)
print("✅ 한국어 목소리 열쇠가 살아 있다 — 이제 쇼츠에 자동으로 얹힌다")
