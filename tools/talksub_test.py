#!/usr/bin/env python3
"""⭐⭐⭐ **대사 영상의 소리와 자막이 맞는가** — 진짜 소리를 만들어 재 본다.

    python3 tools/talksub_test.py       인터넷 0회 · 0원 · 몇 초

⭐⭐⭐ 2026-09-10 손님: **"대사 음성이랑 자막이랑 안 맞게 제작되는 오류가
   발생해."**

   까닭은 셋이었다.
     ① 말의 **시작**을 아무도 안 쟀다. talk_trim 은 뒤에 남는 침묵만 잘랐고,
        앞에 있는 침묵(배우가 숨 쉬고 입을 떼기까지)은 손도 안 댔다.
     ② 그래서 자막 창이 **컷 전체 (0 ~ 끝)** 로 잡혔다. 대사 컷은 우리 목소리
        파일이 없어(영상 안에서 배우가 말한다) sub_windows 가 짐작 갈래로
        떨어지고, 말차례가 하나면 그냥 (0, sec) 을 돌려준다.
     ③ 그 창을 낱말 수로 나누니, 조용한 앞구간까지 자막이 나눠 가져
        낱말이 하나같이 목소리보다 **먼저** 켜진다. 앞이 밀리면 끝까지 밀린다.

   이 시험은 글을 안 읽는다. **말이 늦게 시작하는 소리를 진짜로 만들어**
   (앞 1.2초 무음 → 2초 소리 → 뒤 1.5초 무음) 자막 창이 그 소리를 따라가는지
   본다. 되돌리면 반드시 걸린다.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import short90 as S9                                         # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def make_clip(out, quiet_head, talk, quiet_tail, room=0.02):
    """앞뒤가 조용하고 가운데만 소리 나는 영상 한 개 (ffmpeg 로 만든다).

    ⚠️⚠️⚠️ 2026-09-10 — `room` 이 이 시험의 **핵심**이다.
       처음에는 앞뒤를 **디지털 무음**(aevalsrc=0)으로 두었다. 그러면
       ffmpeg 의 silencedetect(-35dB 고정)가 무조건 찾아내므로, 잰다는
       코드가 실제로는 못 재고 있어도 시험은 늘 초록불이었다.
       진짜 Veo 영상에는 **방 안 소리가 늘 깔려 있다** — 우리가 지문에
       "with only the quiet room tone of the location underneath" 라고
       시켜서 넣은 것이다. 그 소리가 -35dB 보다 크면 옛 방식은 조용한
       구간을 하나도 못 찾았고, 자막이 컷 전체에 퍼졌다.
       그래서 손님이 고쳤다는 말을 듣고도 **또 어긋난 영상을 보셨다.**
       → 시험은 늘 **방 안 소리를 깔고** 잰다. 쉬운 시험은 없는 것을
         있다고 말해 준다.
    """
    total = quiet_head + talk + quiet_tail
    q = f"aevalsrc={room}*random(0)" if room else "aevalsrc=0"
    af = (f"{q}:d={quiet_head}[a0];"
          f"sine=frequency=440:duration={talk}[a1];"
          f"{q}:d={quiet_tail}[a2];"
          f"[a0][a1][a2]concat=n=3:v=0:a=1[a]")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", f"color=c=black:s=256x456:d={total}:r=12",
         "-filter_complex", af, "-map", "0:v", "-map", "[a]",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-t", f"{total}", str(out)],
        check=True, capture_output=True)
    return total


def main():
    print("⭐ 대사 영상: 소리와 자막이 맞는가 (진짜 소리를 만들어 잰다)\n")
    tmp = Path(tempfile.mkdtemp())
    clip = tmp / "c05.mp4"
    HEAD, TALK, TAIL = 1.2, 2.0, 1.5
    sec = make_clip(clip, HEAD, TALK, TAIL)
    print(f"   시험용 영상: 앞 {HEAD}초 조용 · {TALK}초 말 · 뒤 {TAIL}초 조용 "
          f"(모두 {sec:.1f}초)")

    print("\n① -0 **방 안 소리가 깔려 있어도** 재는가 (진짜 영상이 그렇다)")
    for room, name in ((0.0, "무음"), (0.003, "아주 조용"),
                       (0.02, "보통 방 안 소리"), (0.06, "제법 큰 방 안 소리")):
        cx = tmp / f"room_{room}.mp4"
        make_clip(cx, HEAD, TALK, TAIL, room=room)
        b2, f2 = S9.speech_span(cx)
        ok2 = abs(b2 - HEAD) <= 0.35 and f2 is not None and abs(f2 - (HEAD + TALK)) <= 0.35
        ck(f"{name}: 시작 {b2:.2f}초 · 끝 {f2 if f2 is None else round(f2, 2)}초", ok2,
           f"진짜는 {HEAD}~{HEAD + TALK}초 — 고정 dB 로 재면 배경음에 묻힌다")

    print("\n① 말이 **언제 시작하고 언제 끝나는지** 재는가")
    beg, fin = S9.speech_span(clip)
    ck(f"시작을 맞게 잰다 (잰 값 {beg:.2f}초 · 진짜 {HEAD}초)",
       abs(beg - HEAD) <= 0.35, f"{beg:.2f} vs {HEAD}")
    ck(f"끝을 맞게 잰다 (잰 값 {fin if fin is None else round(fin, 2)}초 "
       f"· 진짜 {HEAD + TALK}초)",
       fin is not None and abs(fin - (HEAD + TALK)) <= 0.35, str(fin))

    print("\n② 자막 창이 **말이 나는 구간**에 맞는가")
    S9._SPAN_CACHE.clear()
    cut = {"n": 5, "who": ["장남"],
           "turns": [["장남", "형이 다 가져갔잖아 우리 몫은 돌려줘"]],
           "say": ["담담하게"]}
    wins = S9.sub_windows(cut, sec, None, clip)
    a, b = wins[0]
    ck(f"자막이 0초가 아니라 말이 시작할 때 켜진다 (켜지는 때 {a:.2f}초)",
       a >= HEAD - 0.35, f"{a:.2f}초 — 0초에 켜지면 말보다 {HEAD}초 앞선다")
    ck(f"자막이 말 끝 무렵에 꺼진다 (꺼지는 때 {b:.2f}초)",
       b <= HEAD + TALK + S9.SUB_TAIL + 0.35,
       f"{b:.2f}초 — 컷 끝({sec:.1f}초)까지 남으면 {TAIL}초를 더 떠 있다")

    print("\n③ 낱말 자막이 말하는 동안에만 나오는가")
    ovs = S9.karaoke(cut, sec, None, tmp / "ov", 5, clip=clip)
    spans = [(x[1], x[2]) for x in ovs]
    early = [t for t, _ in spans if t < HEAD - 0.35]
    late = [t for _, t in spans if t > HEAD + TALK + S9.SUB_TAIL + 0.35]
    ck(f"말보다 먼저 켜지는 낱말이 없다 ({len(spans)}장)",
       not early, f"{len(early)}장이 {HEAD}초 전에 켜진다")
    ck("말 끝난 뒤까지 남는 낱말이 없다", not late, f"{len(late)}장이 늦게 꺼진다")

    print("\n④ 우리 목소리를 쓰는 컷은 예전 그대로다 (0초부터)")
    S9._SPAN_CACHE.clear()
    w2 = S9.sub_windows(cut, 6.0, None, None)
    ck("영상이 없으면 컷 전체를 쓴다", w2 == [(0.0, 6.0)], str(w2))

    print("\n⑤ 잘못 잰 소리에는 손대지 않는다 (자막이 아예 안 뜨면 더 나쁘다)")
    S9._SPAN_CACHE.clear()
    mute = tmp / "c06.mp4"
    make_clip(mute, 0.1, 0.1, 3.0)          # 말이랄 게 없는 소리
    a2, b2 = S9.clip_span(mute, 3.2)
    ck("말을 못 찾으면 컷 전체로 돌아간다", (a2, b2) == (0.0, 3.2), f"{a2},{b2}")

    print("\n⑥ 뒤에 남는 침묵을 **진짜로** 잘라 내는가")
    # ⚠️⚠️ 2026-09-10 — 이 자리는 2026-08-31 에 "고쳤다" 고 적혀 있었지만
    #    speech_end 가 늘 None 을 돌려줘 **한 번도 안 잘랐다**(죽은 코드).
    #    글이 아니라 **파일 길이가 실제로 줄었는지**로 본다.
    S9._SPAN_CACHE.clear()
    cut2 = tmp / "c07.mp4"
    total = make_clip(cut2, 0.3, 2.0, 3.0)      # 뒤 3초가 통째로 조용
    before = S9.dur_of(cut2)
    did = S9.talk_trim(cut2, total)
    after = S9.dur_of(cut2)
    ck("잘랐다고 알려 준다", did, "speech_end 가 None 이면 여기서 늘 False 다")
    ck(f"파일이 실제로 짧아졌다 ({before:.1f}초 → {after:.1f}초)",
       after < before - 1.5, f"{before:.2f} → {after:.2f}")
    ck(f"말 끝 + 여운 만큼만 남는다 (약 {0.3 + 2.0 + S9.TALK_TAIL:.2f}초)",
       abs(after - (0.3 + 2.0 + S9.TALK_TAIL)) <= 0.5, f"{after:.2f}초")

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 대사 자막 맞춤: {len(bad)}군데")
        for x in bad:
            print(f"     {x}")
        return 1
    print("✅ 대사 자막 맞춤: 말이 시작할 때 켜지고 · 끝날 때 꺼진다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
