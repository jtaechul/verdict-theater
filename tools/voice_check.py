#!/usr/bin/env python3
"""⭐ 대사 컷에서 **목소리가 안 나오는 일**이 없는지 본다. 값 0원 (API 를 안 쓴다).

    python3 tools/voice_check.py

손님(2026-09-12, 화면 캡처와 함께)
  "왜 대사 치는 부분인데 왜 음성 목소리가 안 나오는데."

까닭 — has_audio 는 **소리 트랙이 붙어 있는지**만 봤다.
  Veo 는 말을 안 하고 방 안 소리(room tone)만 담은 영상을 내보낼 때가 있다.
  우리는 지문에 "with only the quiet room tone of the location underneath"
  라고 **직접 시켜서** 그 배경음을 넣게 해 두었다. 트랙은 멀쩡히 있으니
  has_audio 는 통과 → cut_sec 이 "영상 안에서 말한다" 고 판단 → 우리 목소리를
  안 얹는다 → 그 컷이 **통째로 조용해진다.** 워크플로는 초록불이다.

  "있는가" 와 "쓸 만한가" 는 다른 물음이다. 예전에도 같은 모양으로 세 번
  당했다(옛 영상 주워 쓰기·옛 그림 주워 쓰기). 파일이 있다는 것은
  그 파일이 쓸 만하다는 뜻이 아니다.

⚠️ 이 시험은 **진짜 소리 파일**을 만들어서 잰다. 가짜(디지털 무음)로 재면
   늘 통과한다 — 2026-09-10 에 자막 시험이 바로 그래서 거짓말을 했다.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import short90 as S                                          # noqa: E402

bad = []


def ck(name, ok):
    print(("  ✅ " if ok else "  ❌ ") + name)
    if not ok:
        bad.append(name)


def sh(a):
    subprocess.run(a, check=True, capture_output=True)


def room(p, amp="0.02"):
    """방 안 소리만 있고 **말은 없는** 4초짜리 영상 (Veo 가 가끔 내놓는 것)."""
    sh(["ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=c=gray:s=128x128:d=4",
        "-f", "lavfi", "-i", f"anoisesrc=d=4:c=pink:a={amp}", "-t", "4",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(p)])


def talk(p, amp="0.02"):
    """같은 방 안 소리 위에 **가운데 1.5초 말소리**가 얹힌 영상."""
    sh(["ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=c=gray:s=128x128:d=4",
        "-f", "lavfi", "-i", f"anoisesrc=d=4:c=pink:a={amp}",
        "-f", "lavfi", "-i", "sine=f=220:d=1.5",
        "-filter_complex",
        "[2:a]adelay=1200|1200,apad=whole_dur=4,volume=0.6[v];"
        "[1:a][v]amix=inputs=2:duration=first[a]",
        "-map", "0:v", "-map", "[a]", "-t", "4",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(p)])


def mute(p):
    sh(["ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "color=c=gray:s=128x128:d=4", "-t", "4",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(p)])


def voice(p, sec=2.0):
    """우리 목소리 대신 쓸 소리 파일."""
    sh(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
        "-i", f"sine=f=300:d={sec}", "-c:a", "aac", str(p)])


def main():
    d = Path(tempfile.mkdtemp())
    R, T, M, V = d / "room.mp4", d / "talk.mp4", d / "mute.mp4", d / "v.m4a"
    room(R)
    talk(T)
    mute(M)
    voice(V)

    print("■ ① 말이 있는지 없는지 가려낸다")
    ck("방 안 소리만 있는 영상 — 소리 트랙은 **있다** (여기서 속았다)",
       S.has_audio(R) is True)
    ck("그런데 말은 없다 → has_speech 는 아니라고 한다",
       S.has_speech(R) is False)
    ck("진짜 말이 든 영상은 그렇다고 한다", S.has_speech(T) is True)
    ck("소리 트랙 자체가 없는 영상도 아니라고 한다", S.has_speech(M) is False)
    # 배경음이 크든 작든 똑같이 걸려야 한다 (고정 dB 로 재면 여기서 무너진다)
    R2, T2 = d / "room2.mp4", d / "talk2.mp4"
    room(R2, amp="0.15")
    talk(T2, amp="0.15")
    ck("배경음이 커도 — 말 없는 것은 없다고 한다", S.has_speech(R2) is False)
    ck("배경음이 커도 — 말 있는 것은 있다고 한다", S.has_speech(T2) is True)

    print("\n■ ② 조립이 그 판단대로 움직인다 (여기가 진짜 시험이다)")
    c = {"n": 1, "sec": 4.0, "who": ["아버지"],
         "turns": [["아버지", "그 큰돈을 네가 왜 다 빼간 것이냐."]],
         "say": ["70대 남성이, 조용하고 단단하게"], "scene": "the old man"}
    sec_r, use_r = S.cut_sec(c, V, R)
    sec_t, use_t = S.cut_sec(c, V, T)
    # ⚠️ has_audio 로 되돌리면 use_r 이 True 가 되어 **이 줄이 걸린다.**
    ck("말 없는 영상이면 → 우리 목소리를 얹는다", use_r is False)
    ck("말 있는 영상이면 → 영상 소리를 그대로 쓴다", use_t is True)
    ck("말 없는 영상일 때 컷 길이는 **우리 목소리**가 정한다",
       abs(sec_r - max(S.MIN_CUT, S.dur_of(V) / S.SPEED + S.PAD)) < 0.05)
    ck("말 있는 영상일 때 컷 길이는 **영상**이 정한다",
       abs(sec_t - S.dur_of(T)) < 0.05)

    print("\n■ ③ 나레이션 컷은 늘 우리 나레이션이다")
    nc = {"n": 2, "sec": 4.0, "who": [],
          "turns": [["나레이션", "소송이 시작됐습니다."]], "say": ["담담하게"],
          "scene": "an empty desk"}
    ck("영상 안에서 말을 해도 나레이션 컷은 우리 목소리를 쓴다",
       S.cut_sec(nc, V, T)[1] is False)

    print("\n■ ④ 만들자마자 보는 자리 — 값을 버리지 않는다")
    fn = (ROOT / "src" / "short90.py").read_text("utf-8")
    body = fn.split("def talkers(")[1].split("\ndef ")[0]
    ck("소리 트랙이 아예 없으면 그 파일은 버린다 (망가진 파일)",
       "if not has_audio(out):" in body and "out.unlink" in
       body.split("if not has_audio(out):")[1].split("continue")[0])
    ck("말만 없는 것은 **안 버린다** — 이미 낸 값(470원)이 날아가지 않게",
       "if not has_speech(out):" in body
       and "unlink" not in body.split("if not has_speech(out):")[1]
                              .split("talk_trim")[0])
    ck("화면 보고에서도 같은 잣대를 쓴다 (has_speech)",
       "has_speech(clip)" in fn and '"영상 (그 안에서 말한다)" if has_audio' not in fn)
    ck("자막을 맞추는 자와 **같은 자**로 잰다 (speech_span)",
       "speech_span(path)[1] is not None" in fn)

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 대사 목소리: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 대사 목소리: 영상이 말을 안 하면 우리 목소리가 대신 나간다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
