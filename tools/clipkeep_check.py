#!/usr/bin/env python3
"""⭐ **이미 산 대사 영상을 헛되이 다시 사지 않는지** 본다. 값 0원.

    python3 tools/clipkeep_check.py

2026-09-13 — 손님: "이미 산 영상을 안 산다고 했는데 정말 맞아?"
확인해 보니 **아니었다.** 열네 개가 전부 다시 사질 참이었다 (6,821원).

까닭이 둘이었다 —
  ① 표시 지우기(tools/wipe_mark.py)가 stills 를 돌릴 때마다 **모든 그림
     파일을 다시 저장**했다. 그림은 똑같은데 바이트가 매번 달라진다
     (실측: 5,308,933 → 5,306,751 → 또 다름).
     대사 영상 지문에는 **그 그림의 바이트**가 들어간다. 그래서 그림을 한
     장도 안 그린 실행에서도 영상 열네 개가 통째로 "안 맞는 것"이 됐다.
     → 지운 그림에는 표시(.wiped)를 남기고 **한 번만** 지운다.
  ② 그것만 고쳐서는 **이미 사 둔 것**을 못 살린다. 이미 여러 번 덧지워져
     바이트가 달라져 있기 때문이다.
     → 지문을 "무슨 말을 하는가"와 "어느 그림에서 나왔는가" **두 토막**으로
       나누고, 뒤 토막이 어긋나면 **영상 첫 장면과 그림을 눈으로 견준다.**
       같은 그림이면 살리고(0원), 정말 다른 그림이면 다시 산다.

⚠️ 이 검사는 **진짜 그림·진짜 영상 파일**을 만들어서 잰다.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw                             # noqa: E402

import short90 as S                                          # noqa: E402
import reuse                                                 # noqa: E402
import wipe_mark                                             # noqa: E402

bad = []


def ck(name, ok):
    print(("  ✅ " if ok else "  ❌ ") + name)
    if not ok:
        bad.append(name)


def a_picture(p, shift=0):
    """세로 그림 한 장 (shift 를 주면 **정말 다른 그림**이 된다)."""
    im = Image.new("RGB", (360, 640), (30 + shift, 40, 60))
    d = ImageDraw.Draw(im)
    for i in range(0, 640, 24):
        d.rectangle((0, i, 360, i + 12), fill=(90 + shift, 70, 50))
    d.ellipse((90 + shift * 2, 150, 270 + shift * 2, 360), fill=(210, 180, 160))
    im.save(p)


def a_clip(p, png, sec=4.0):
    """그 그림에서 나온 것처럼 보이는 영상 (첫 장면 = 그 그림)."""
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(png),
                    "-f", "lavfi", "-i", f"anoisesrc=d={sec}:c=pink:a=0.02",
                    "-t", str(sec), "-r", "24", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(p)], check=True)


CUT = {"n": 7, "sec": 4.0, "who": ["아버지"],
       "turns": [["아버지", "그 큰돈을 네가 왜 다 빼간 것이냐."]],
       "say": ["70대 남성이, 조용하고 단단하게"],
       "veo": "A 4-second single continuous take. SHOT: the old man.",
       "still": "the old man"}


def main():
    d = Path(tempfile.mkdtemp())

    print("■ ① 표시 지우기가 그림을 **한 번만** 건드린다")
    w = d / "wipe"
    w.mkdir()
    a_picture(w / "c07.png")
    hs = []
    for _ in range(3):
        wipe_mark.main_dir(w)
        hs.append(reuse.sig_of((w / "c07.png").read_bytes().hex()))
    ck("두 번째부터는 그림 파일을 손대지 않는다", len(set(hs)) == 1)
    ck("지웠다는 표시를 남긴다", (w / "c07.wiped").exists())
    # 새로 그리면 표시를 지워 다시 지우게 해야 한다
    fn = (ROOT / "src" / "short90.py").read_text("utf-8")
    body = fn.split("def stills(")[1].split("\ndef ")[0]
    ck("새로 그리면 그 표시를 지운다 (다시 지우게)",
       '.with_suffix(".wiped").unlink' in body)

    print("\n■ ② 지문이 두 토막이다 (말 / 그림)")
    still = d / "c07.png"
    a_picture(still)
    sig = S.talk_sig(CUT, 4, still)
    ck("지문에 점이 있어 앞뒤를 가를 수 있다", sig.count(".") == 1)
    other = d / "c07b.png"
    a_picture(other, shift=90)
    ck("그림이 다르면 뒤 토막만 달라진다",
       S.talk_sig(CUT, 4, other).split(".")[0] == sig.split(".")[0]
       and S.talk_sig(CUT, 4, other).split(".")[1] != sig.split(".")[1])

    print("\n■ ③ 바이트만 달라진 그림 — **살린다** (여기가 4,700원짜리다)")
    clip = d / "c07.mp4"
    a_clip(clip, still)
    reuse.stamp(clip, sig)
    wipe_mark.wipe(still)                       # 그림 파일을 한 번 더 저장
    ck("그림 바이트가 실제로 달라졌다",
       S.talk_sig(CUT, 4, still) != sig)
    ok, why = S.talk_ok(CUT, clip, still)
    ck("그래도 이 영상은 그대로 쓴다 (0원)", ok)
    ck("살린 뒤에는 새 지문으로 다시 적어 둔다",
       reuse.sig_file(clip).read_text("utf-8").strip()
       == S.talk_sig(CUT, 4, still))

    print("\n■ ④ 정말 다른 그림 — **다시 산다**")
    clip2 = d / "c08.mp4"
    a_clip(clip2, still)
    reuse.stamp(clip2, S.talk_sig(CUT, 4, still))
    ok2, _ = S.talk_ok(CUT, clip2, other)       # 딴 그림을 들이민다
    ck("그림이 바뀌었으면 안 쓴다", not ok2)

    print("\n■ ⑤ 대사가 바뀌면 — 그림이 같아도 **안 쓴다**")
    #    입과 말이 어긋나기 때문이다. 그림만 보고 살리면 이걸 놓친다.
    clip3 = d / "c09.mp4"
    a_clip(clip3, still)
    reuse.stamp(clip3, S.talk_sig(CUT, 4, still))
    said = dict(CUT)
    said["turns"] = [["아버지", "네가 어찌 그럴 수가 있느냐 말이다."]]
    said["veo"] = "A 4-second single continuous take. SHOT: the old man. NEW LINE."
    ok3, _ = S.talk_ok(said, clip3, still)
    ck("대사가 달라지면 안 쓴다", not ok3)

    print("\n■ ⑥ 옛 지문(한 토막)도 살릴 수 있다 — 다만 길이가 말이 될 때만")
    clip4 = d / "c10.mp4"
    a_clip(clip4, still, sec=3.4)               # 뒤를 잘라 둔 것처럼 짧게
    reuse.stamp(clip4, "0123456789abcdef")      # 옛 한 토막 지문
    ok4, _ = S.talk_ok(CUT, clip4, still)
    ck("산 초보다 짧은 것은 살린다 (뒤를 잘라 둔 것이다)", ok4)
    clip5 = d / "c11.mp4"
    a_clip(clip5, still, sec=8.0)               # 옛 8초 통짜
    reuse.stamp(clip5, "0123456789abcdef")
    ok5, _ = S.talk_ok(CUT, clip5, still)
    ck("산 초보다 긴 옛 통짜는 안 쓴다", not ok5)

    shutil.rmtree(d, ignore_errors=True)
    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 산 영상 지키기: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 산 영상 지키기: 같은 그림이면 그대로 쓰고, 바뀐 것만 다시 산다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
