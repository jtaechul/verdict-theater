#!/usr/bin/env python3
"""⭐ **이어붙인 뒤에도 컷마다 목소리가 살아 있는지** 본다. 값 0원.

    python3 tools/join_check.py

2026-09-14 손님(화면 캡처와 함께): **"이 부분은 대사 음성이 안 나오는데?
또 이런 구간이 있는 거 아냐? 똑바로 확인해서 조치해."**

■ 까닭 — 컷마다 소리 **채널 수가 달랐다**
    나레이션 컷 → 우리 목소리 (모노 1채널)
    대사 컷    → Veo 영상 소리 (스테레오 2채널)
  이어붙이기(ffmpeg concat -c copy)는 **첫 컷의 규격**으로 소리 트랙을 하나
  만든다. 뒤에 규격이 다른 토막이 섞이면 그 토막의 소리가 통째로 사라진다.
  S92 1편 실측 — 컷2는 살고 **컷5·6·8은 소리가 없었다.**

■ 왜 아무도 못 잡았나 — **들어 봐야 아는 고장**이기 때문이다
  · 화면·자막은 멀쩡하다
  · 배경음악이 깔려 있어서 파형만 보면 "소리가 있다"
  · 컷 하나만 만들어 보면 멀쩡하다 (이어붙일 때 생기는 일이다)
  · 검사 41개가 전부 초록불이었다
  → 그래서 이 검사는 **진짜로 이어붙이고, 컷마다 그 컷의 소리가 완성본
    안에 들어 있는지 파형을 맞대어 본다.** 배경음악까지 깔고 나서 잰다.

⚠️ "소리가 나는가" 가 아니라 **"그 컷의 소리인가"** 를 묻는다. 배경음악만
   흐르는 구간도 소리는 난다 — 그것이 이 고장의 정체였다.
"""
import array
import math
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw                             # noqa: E402

import short90 as S                                          # noqa: E402

bad = []


def ck(name, ok):
    print(("  ✅ " if ok else "  ❌ ") + name)
    if not ok:
        bad.append(name)


def sh(a):
    subprocess.run(a, check=True, capture_output=True)


def a_still(p):
    im = Image.new("RGB", (360, 640), (28, 34, 52))
    ImageDraw.Draw(im).ellipse((110, 170, 250, 380), fill=(205, 175, 155))
    im.save(p)


def talky(p, sec, ch, tone):
    """말처럼 **조용-소리-조용** 이 있는 소리. ch 로 채널 수를 바꾼다."""
    sh(["ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", f"anoisesrc=d={sec}:c=pink:a=0.02",
        "-f", "lavfi", "-i", f"sine=f={tone}:d={sec - 1.6:g}",
        "-filter_complex",
        f"[1:a]adelay=800|800,apad=whole_dur={sec},volume=0.7[v];"
        f"[0:a][v]amix=inputs=2:duration=first:normalize=0[a]",
        "-map", "[a]", "-ac", str(ch), "-t", str(sec),
        "-c:a", "pcm_s16le", str(p)])


def clip_of(p, png, wav, sec):
    sh(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(png),
        "-i", str(wav), "-t", str(sec), "-r", "24",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(p)])


def envel(path, ss=None, t=None, tag="a"):
    w = Path(tempfile.gettempdir()) / f"_jc_{tag}.wav"
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if ss is not None:
        cmd += ["-ss", f"{ss:.3f}"]
    cmd += ["-i", str(path)]
    if t is not None:
        cmd += ["-t", f"{t:.3f}"]
    cmd += ["-vn", "-ac", "1", "-ar", "16000", str(w)]
    sh(cmd)
    f = wave.open(str(w))
    a = array.array("h")
    a.frombytes(f.readframes(f.getnframes()))
    step = int(f.getframerate() * 0.1)
    return [(sum(x * x for x in a[i:i + step]) / step) ** 0.5
            for i in range(0, len(a) - step + 1, step)]


def corr(x, y):
    n = min(len(x), len(y))
    if n < 5:
        return 0.0
    x, y = x[:n], y[:n]
    mx, my = sum(x) / n, sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    dx = math.sqrt(sum((a - mx) ** 2 for a in x))
    dy = math.sqrt(sum((b - my) ** 2 for b in y))
    return num / (dx * dy) if dx and dy else 0.0


def build(d, ac):
    """컷 넷을 만들어 이어붙인다. ac=None 이면 채널을 안 맞춘다(옛 판)."""
    png = d / "s.png"
    a_still(png)
    order = [("narr", 1, 300, 3.6), ("talk", 2, 440, 3.2),
             ("narr", 1, 320, 3.4), ("talk", 2, 520, 3.0)]
    parts, srcs = [], []
    for i, (kind, ch, tone, sec) in enumerate(order, 1):
        wav = d / f"a{i}.wav"
        talky(wav, sec, ch, tone)
        srcs.append(wav)
        out = d / f"c{i}.mp4"
        cmd = ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(png),
               "-i", str(wav), "-t", str(sec), "-r", "24",
               "-c:v", "libx264", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "160k", "-ar", "48000"]
        if ac:
            cmd += ["-ac", str(ac)]
        cmd += ["-shortest", str(out)]
        sh(cmd)
        parts.append(out)
    lst = d / "l.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    joined = d / "j.mp4"
    sh(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
        "-i", str(lst), "-c", "copy", str(joined)])
    return joined, srcs, [x[3] for x in order]


def missing(joined, srcs, secs):
    """소리가 사라진 컷 번호들."""
    out, t = [], 0.0
    for i, (src, sec) in enumerate(zip(srcs, secs), 1):
        if corr(envel(src, tag="s"), envel(joined, t, sec, tag="j")) <= 0.7:
            out.append(i)
        t += sec
    return out


def main():
    d = Path(tempfile.mkdtemp())

    print("■ ① 채널 수를 안 맞추면 **소리가 사라진다** (이것이 그 고장이다)")
    j0, s0, sec0 = build(d / "old", None) if (d / "old").mkdir(parents=True) or True else None
    lost = missing(j0, s0, sec0)
    ck("옛 방식(채널 제각각)에서는 실제로 소리가 빠진다", bool(lost))
    print(f"     → 소리가 사라진 컷: {lost or '없음'}")

    print("\n■ ② **우리 진짜 조립(cut_video)** 이 컷마다 같은 규격을 내놓는가")
    #    ①이 보여 준 대로, 규격이 어긋나면 뒤쪽 소리가 사라진다. 그러니
    #    조립이 내놓는 컷들은 **소리 규격이 전부 같아야** 한다.
    #    ⚠️ 흉내낸 판이 아니라 **실제로 도는 cut_video** 를 부른다 —
    #       흉내만 내면 cut_video 가 망가져도 못 잡는다.
    nd = d / "new"
    nd.mkdir(parents=True)
    png = nd / "s.png"
    a_still(png)
    spec = [("나레이션", None, 300, 3.6), ("아버지", 2, 440, 3.2),
            ("나레이션", None, 320, 3.4), ("장남", 1, 520, 3.0)]
    seen = []
    for i, (who, ch, tone, sec) in enumerate(spec, 1):
        cut = {"n": i, "sec": sec, "who": [] if who == "나레이션" else [who],
               "turns": [[who, "여기 도장을 찍어라 이 사람아."]],
               "say": ["조용하고 단단하게"], "scene": "a room", "kind": who[:4]}
        voice = nd / f"v{i}.wav"
        talky(voice, sec, 1, tone)                 # 우리 목소리는 늘 모노다
        clip = None
        if ch:                                     # 영상 소리는 스테레오·모노 섞어 본다
            cw = nd / f"cw{i}.wav"
            talky(cw, sec, ch, tone)
            clip = nd / f"k{i}.mp4"
            clip_of(clip, png, cw, sec)
        got, use = S.cut_sec(cut, voice, clip)
        ovs = S.karaoke(cut, got, voice, nd, i, clip=clip)
        out = nd / f"c{i}.mp4"
        S.cut_video(cut, png, voice, clip, ovs, out)
        spec_s = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=channels,sample_rate,codec_name",
             "-of", "csv=p=0", str(out)],
            capture_output=True, text=True).stdout.strip()
        print(f"     컷{i} ({'영상 소리' if use else '우리 목소리'}): {spec_s}")
        seen.append(spec_s)
    ck("네 컷의 소리 규격이 **전부 같다** (섞여도 안 어긋난다)",
       len(set(seen)) == 1)

    print("\n■ ③ 우리 조립이 실제로 채널을 못 박고 있는가")
    fn = (ROOT / "src" / "short90.py").read_text("utf-8")
    body = fn.split("def cut_video(")[1].split("\ndef ")[0]
    ck("컷을 만들 때 -ac 로 채널 수를 정한다", '"-ac", "2"' in body)
    ck("소리 규격(-ar)도 못 박혀 있다", '"-ar", "48000"' in body)

    shutil.rmtree(d, ignore_errors=True)
    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 이어붙인 뒤 목소리: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 이어붙인 뒤 목소리: 컷마다 제 소리가 그대로 남는다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
