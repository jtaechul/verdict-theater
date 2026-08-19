#!/usr/bin/env python3
"""자로 재는 음성 검사가 제대로 재는지 본다. 인터넷 0회 · 0원 · 1초.

    python3 tools/voice_len_test.py

왜 이 검사가 있는가 (2026-08-11)
    영상 만들기가 40분을 돌다 죽었다. 원인은 음성이 아니었다 —
    **음성 119컷은 전부 멀쩡히 만들어져 있었다.**

    막은 것은 '받아쓰기 대조' 였다. 컷 mp3 10개를 이어 붙여 800KB 를 통째로
    구글에 보내고 "받아 적어 봐라" 하는 검사인데, 큰 멀티모달 요청은 구글이
    용량이 빠듯할 때 가장 먼저 거절하는 모양이라 HTTP 503 이 줄줄이 났다.
    그리고 같은 800KB 를 네 번씩 다시 보내며 30분을 버렸다.

    손님 지적: "구글 서버 죽었다고 영상 제작 안 할 거야?"  맞는 말이었다.
    그 검사가 잡으려는 것은 '대사의 머리/꼬리가 잘렸나' — **길이 문제**다.
    길이는 ffprobe 로 공짜로, 즉시, 인터넷 없이 잰다.

⚠️ '글자당 몇 초' 를 숫자로 박지 않는다 — 그것도 짐작이다.
   한 통 안의 컷끼리 견준다(같은 사람이 같은 속도로 이어 읽었으므로).
   그래서 목소리를 바꾸든 배속을 바꾸든 따라온다. 아래 ③ 이 그것을 지킨다.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import tts                                           # noqa: E402

ok = True
DUR = {}


def bad(msg):
    global ok
    ok = False
    print(f"   ❌ {msg}")


class Out:
    """build/voice 흉내. 진짜 파일은 만들지 않는다."""

    def __truediv__(self, name):
        return pathlib.Path("/tmp/_voice_len_test") / name


LINES = [
    "그 사람은 이미 오래전에 집을 나가 있었다",
    "저는 이십 년을 그 집에서 살았습니다",
    "손등에는 겨울마다 마늘 냄새가 배어 있었습니다",
    "그래도 선희 씨는 그 집을 떠나지 않았습니다",
    "법원이 남편의 청구를 물리친 그날이었습니다",
]


def check(durs, pre="A"):
    global DUR
    cuts = [{"id": f"{pre}{i + 1}", "text": t}
            for i, t in enumerate(LINES)]
    DUR = {c["id"]: d for c, d in zip(cuts, durs)}
    return [c["id"] for c in tts.check_lengths(cuts, Out())]


# 진짜 mp3 없이 시험한다 — '길이 재기' 와 '파일 있나' 만 갈아 끼운다
tts._duration = lambda p: DUR.get(pathlib.Path(str(p)).stem, 0.0)
_real_exists = pathlib.Path.exists
pathlib.Path.exists = lambda self: True

try:
    print("① 전부 고르게 읽힌 통")
    got = check([3.2, 2.9, 3.5, 3.3, 3.3])
    if got:
        bad(f"멀쩡한 통에서 {got} 을 잘렸다고 했다 — 헛경보다")
    else:
        print("   ✅ 아무것도 안 걸렸다")

    print()
    print("② 한 컷의 꼬리가 잘린 통 (자막 21자인데 소리 0.9초)")
    got = check([3.2, 2.9, 0.9, 3.3, 3.3])
    if got != ["A3"]:
        bad(f"A3 하나만 걸려야 하는데 {got} 이 걸렸다")
    else:
        print("   ✅ A3 만 정확히 걸렸다")

    print()
    print("③ 통째로 빠른 배속 — 고르게 짧다 (걸리면 안 된다)")
    got = check([2.1, 1.9, 2.3, 2.2, 2.2], pre="B")
    if got:
        bad(f"배속만 빠른 멀쩡한 통에서 {got} 이 걸렸다 — "
            "글자당 초를 숫자로 박아 두면 이렇게 된다")
    else:
        print("   ✅ 안 걸렸다 (통 안에서 서로 견주므로 배속에 안 흔들린다)")

    print()
    print("④ 사실상 무음인 컷")
    got = check([3.2, 0.05, 3.5, 3.3, 3.3], pre="C")
    if got != ["C2"]:
        bad(f"C2 하나만 걸려야 하는데 {got} 이 걸렸다")
    else:
        print("   ✅ C2 만 정확히 걸렸다")

    print()
    print("⑤ 인터넷을 한 번도 안 쓴다")
    src = (ROOT / "src" / "tts.py").read_text(encoding="utf-8")
    i = src.index("def check_lengths(")
    body = src[i:src.index("\ndef ", i + 10)]
    for word in ("_post", "requests", "urlopen", "transcribe", "generateContent"):
        if word in body:
            bad(f"check_lengths 안에서 '{word}' 를 쓴다 — 인터넷에 기대면 안 된다")
    else:
        print("   ✅ 부르는 것은 ffprobe 뿐이다 (값 0원 · 구글과 무관)")

    print()
    print("⑥ 판정 권한이 자로 재는 쪽에 있는가")
    j = src.index("def check_batch(")
    cb = src[j:src.index("\n    bad = {}", j)]
    if "return hard" not in cb:
        bad("check_batch 가 자로 잰 결과를 돌려주지 않는다")
    elif "return heard" in cb or "return [c for c, t in zip" in cb:
        bad("받아쓰기 결과가 아직도 판정한다 — 구글이 죽으면 또 막힌다")
    else:
        print("   ✅ 받아쓰기는 참고만 하고, 막는 것은 자로 잰 결과뿐이다")
finally:
    pathlib.Path.exists = _real_exists

print()
print("─" * 52)
print("✅ 자로 재는 음성 검사: 정상" if ok else "❌ 자로 재는 음성 검사: 문제 있음")
sys.exit(0 if ok else 1)
