#!/usr/bin/env python3
"""배역과 목소리가 맞는지 보는 검사를 **검사한다.** 값 0원 · 인터넷 없이 돈다.

    python3 tools/voice_test_cast.py

왜 (2026-08-09 손님: "나중에도 이러면 어떡해.")
    같은 실수를 세 번 했다 — Puck(들뜬) · Algenib(쉰 목소리) · Gacrux(186Hz 여자 음역).
    이제 tts.check_voice_pitch() 가 만들기 전에 막는다.
    **그 막는 장치가 살아 있는지** 여기서 지킨다. 장치가 조용히 고장 나면
    또 한 편(400~700원·40분)을 버리고 손님이 귀로 찾아내셔야 한다.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import tts  # noqa: E402

FAIL = []


def check(name, ok, detail=""):
    if ok:
        print(f"  ✓ {name}")
    else:
        FAIL.append(f"{name}{' — ' + detail if detail else ''}")
        print(f"  ✗ {name}{' — ' + detail if detail else ''}")


def stops(table, pitch=None):
    """그 배정으로 멈추는가."""
    old_t, old_n = tts.voice_table, dict(tts.VOICE_NAME)
    tts.voice_table = lambda: table
    try:
        import render
        old_p = dict(render.VOICE_PITCH)
        render.VOICE_PITCH.clear()
        render.VOICE_PITCH.update(pitch or {})
    except Exception:
        old_p = None
    try:
        tts.check_voice_pitch()
        return False
    except Exception:
        return True
    finally:
        tts.voice_table = old_t
        tts.VOICE_NAME.clear()
        tts.VOICE_NAME.update(old_n)
        if old_p is not None:
            render.VOICE_PITCH.clear()
            render.VOICE_PITCH.update(old_p)


def table(**hz):
    """{배역이름: Hz} → 검사가 읽는 표 (목소리 이름은 지금 것을 그대로 쓴다)."""
    return {tts.VOICE_NAME[sp]: {"hz": v} for sp, v in hz.items()}


BASE = dict(narrator=82, v_M50A=125, v_M50B=140, v_M70=131,
            v_JUDGE=121, v_F50A=198, v_F50B=180, v_F70=205)

print("\n[1] 멀쩡한 배정은 통과한다")
check("남자는 남자 음역, 여자는 여자 음역", not stops(table(**BASE)))

print("\n[2] 이번에 실제로 있었던 일 — 남자 배역에 여자 음역")
bad = dict(BASE, v_M50A=186)                       # Gacrux
check("장남 186Hz 면 멈춘다", stops(table(**bad)),
      "이것을 못 잡아서 손님이 영상을 다 보고 지적하셨다")

print("\n[3] 반대도 잡는다 — 여자 배역에 남자 음역")
check("어머니 120Hz 면 멈춘다", stops(table(**dict(BASE, v_F50A=120))))

print("\n[4] 애매한 구간은 멈추지 않는다 (귀로 판단하실 몫)")
check("장남 158Hz 는 경고만", not stops(table(**dict(BASE, v_M50A=158))))

print("\n[5] 뒤에서 낮춘 것을 계산에 넣는다")
check("186Hz 라도 5반음 낮추면(139Hz) 통과",
      not stops(table(**dict(BASE, v_M50A=186)), pitch={"v_M50A": -5.0}),
      "시청자가 실제로 듣는 소리로 판단해야 한다")
check("186Hz 를 1반음만 낮추면(176Hz) 여전히 멈춘다",
      stops(table(**dict(BASE, v_M50A=186)), pitch={"v_M50A": -1.0}))

print("\n[6] 일부러 넘길 길이 있다")
os.environ["VT_VOICE_SKIP"] = "1"
check("VT_VOICE_SKIP=1 이면 진행된다", not stops(table(**dict(BASE, v_M50A=186))))
os.environ.pop("VT_VOICE_SKIP", None)
check("끄면 다시 멈춘다", stops(table(**dict(BASE, v_M50A=186))))

print("\n[7] 표가 없으면 막지 않는다 (멀쩡한 작업을 세우지 않는다)")
check("빈 표면 그냥 지나간다", not stops({}))

print("\n[8] 지금 저장소의 높이표가 읽히는가")
t = tts.voice_table()
check("data/voices.json 을 읽는다", len(t) >= 10, f"{len(t)}개")
check("장남 목소리 높이를 안다", tts.VOICE_NAME["v_M50A"] in t,
      f"{tts.VOICE_NAME['v_M50A']} 가 표에 없다")

print("\n[9] 검사가 실제로 불리는가 (연결이 끊기면 있으나 마나다)")
src = (ROOT / "src" / "tts.py").read_text(encoding="utf-8")
check("check_style 이 check_voice_pitch 를 부른다",
      "check_voice_pitch()" in src.split("def check_style")[1])

print()
if FAIL:
    print(f"❌ {len(FAIL)}가지 틀렸습니다")
    for f in FAIL:
        print("   -", f)
    sys.exit(1)
print("✅ 배역-목소리 검사 모두 통과")
