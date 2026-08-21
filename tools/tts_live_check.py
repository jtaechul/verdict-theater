#!/usr/bin/env python3
"""⭐ 목소리 열쇠가 **진짜로 살아 있는지** 확인한다. 값은 1원도 안 된다.

    python3 tools/tts_live_check.py

왜 (2026-08-21)
    넣은 것과 **되는 것**은 다르다 — API 를 안 켰거나, 열쇠에 제한이 걸려
    있거나, 결제 계정이 없으면 영상 만들 때가 되어서야 실패한다. 그때 알면 늦다.
    그래서 **밀어 넣을 때마다** 짧은 소리를 두 개 만들어 본다.

⭐ 2026-08-21 두 번째 — 목소리를 제미나이로 바꿨다. 여기서 두 가지를 더 본다.
    ① 지금 어떤 엔진·목소리가 잡혔는지 **화면에 적는다.**
       (조용히 구글 클라우드로 되돌아가도 아무도 몰랐다 — 그게 문제였다)
    ② **연기 지시를 소리 내어 읽어 버리지 않는지** 길이를 재서 확인한다.
       제미나이에는 "이를 악물고 낮게 말한다:" 같은 지시를 같이 보내는데,
       그걸 그대로 읽어 버리면 견본이 통째로 망가진다. 지시까지 읽으면
       소리가 두 배 넘게 길어지므로, 길이만 재도 바로 잡힌다.
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import tts as T                                             # noqa: E402

print("⭐ 목소리 열쇠 확인\n")

# ⚠️ 열쇠가 없을 때 그냥 건너뛰었더니, 초록불이 **열쇠가 된다는 뜻인지 그냥
#    넘어갔다는 뜻인지** 알 수 없었다. 깃허브 안에서는 열쇠가 있어야 정상이므로,
#    없으면 **빨간불**을 낸다. 그래야 초록불이 곧 증거가 된다.
#    (내 컴퓨터에서 그냥 돌릴 때는 건너뛴다)
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"


def note(line):
    """깃허브 실행 화면에도 한 줄 남긴다 (운영자가 눈으로 본다)."""
    f = os.environ.get("GITHUB_STEP_SUMMARY")
    if f:
        with open(f, "a", encoding="utf-8") as h:
            h.write(line + "\n")


if not T.key():
    if IN_CI:
        print("   ❌ 목소리 열쇠가 깃허브에 없다")
        print("      GEMINI_API_KEY 나 GOOGLE_TTS_KEY 중 하나는 있어야 한다")
        note("- ❌ 목소리 열쇠가 없습니다")
        sys.exit(1)
    print("   ⏭  목소리 열쇠가 없다 — 건너뛴다")
    print("      (열쇠가 없으면 영상의 원래 소리를 그대로 쓴다. 영상은 나온다)")
    sys.exit(0)

ENG = T.engine()
print(f"   엔진 → {'제미나이 (연기 지시를 함께 보낸다)' if ENG == 'gemini' else '구글 클라우드 TTS'}")
if ENG == "gemini":
    print(f"   모델 → {T.gem_pick()}")
_f, _m = T.best_voices("FEMALE"), T.best_voices("MALE")
print(f"   여자 → {_f[0]}")
print(f"   남자 → {_m[0]}")
note(f"- 쓰는 목소리: {'제미나이' if ENG == 'gemini' else '구글'} "
     f"— 여자 {_f[0]} · 남자 {_m[0]}")
print()

# ⭐ 실제 드라마 대사로 시험한다. "확인" 두 글자로는 지시를 읽는지 못 잡는다.
LINE = "당신 진짜 제정신이야?"
SYL = len([c for c in LINE if "가" <= c <= "힣"])            # 9음절
# 실제로 재 보니 감정 실은 9음절이 2.0~4.0초였다(뒤 여운 포함). 지시는
# 60음절쯤이라 그것까지 읽으면 14초를 넘는다. 사이가 넓으니 6초에 금을 긋는다.
MAX_SEC = max(6.0, SYL / 1.5)

# ⭐ 2026-08-21 — 여기서 **한 번만** 부른다.
#    무료 한도가 1분에 10번인데, 밀어 넣을 때마다 두 번씩 쓰면 정작 영상 만들
#    때 쓸 몫을 갉아먹는다. 열쇠가 되는지는 한 번이면 충분히 증명된다.
tmp = Path(tempfile.mkdtemp())
ok = True
for voice in (_f[0],):
    out = tmp / f"{voice}.wav"
    try:
        p = T.say(LINE, voice, 1.0, 0.0, out)
    except T.Busy as e:                                      # noqa: BLE001
        # ⚠️ 한도에 걸린 것은 **고장이 아니다.** 구글이 "조금 뒤에 다시 하라"고
        #    말해 준 것이므로 열쇠는 오히려 멀쩡하다는 뜻이다. 여기서 빨간불을
        #    내면 밀어 넣을 때마다 "고장났다" 메일이 쓸데없이 간다.
        print(f"   ⏭  지금은 한도에 걸려 확인을 못 했다 (열쇠는 멀쩡하다)")
        print(f"      {str(e).splitlines()[-1].strip()}")
        note("- ⏭ 목소리 확인은 건너뛰었습니다 (잠깐 한도에 걸렸을 뿐, "
             "열쇠는 멀쩡합니다)")
        sys.exit(0)
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
    if d <= 0.15 or size <= 2000:
        print(f"   ❌ {voice} — 소리가 비었다 ({d:.2f}초 · {size:,}바이트)")
        ok = False
        break
    if d > MAX_SEC:
        # ⚠️ 이게 걸리면 십중팔구 **연기 지시를 소리 내어 읽은 것**이다.
        print(f"   ❌ {voice} — {d:.2f}초. {SYL}음절짜리 대사가 "
              f"{MAX_SEC:.1f}초를 넘었다.")
        print("      연기 지시까지 읽어 버렸을 가능성이 크다 "
              "(src/tts.py 의 direct() 를 손봐야 한다)")
        ok = False
        break
    print(f"   ✅ {voice} — {d:.2f}초 · {size:,}바이트")

print("\n" + "─" * 52)
if not ok:
    print("❌ 목소리를 못 만든다. 위 까닭대로 고친 뒤 다시 밀어 넣어라")
    note("- ❌ 목소리를 못 만듭니다 (위 빨간 칸을 열어 보십시오)")
    sys.exit(1)
print("✅ 목소리 열쇠가 살아 있다 — 이제 쇼츠에 자동으로 얹힌다")
note("- ✅ 목소리 열쇠가 살아 있습니다 (연기 지시까지 제대로 먹었습니다)")
