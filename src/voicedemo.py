#!/usr/bin/env python3
"""고친 목소리를 **귀로 확인할 수 있는 비교 영상**을 만든다.

    # ① 고치기 전 소리를 챙겨 둔다
    python3 src/voicedemo.py data/scripts/EP001.json --stage before
    # ② (그 사이에 tts.py 가 목소리를 고친다)
    # ③ 앞뒤를 나란히 붙인 비교 영상을 만든다
    python3 src/voicedemo.py data/scripts/EP001.json --stage build --out build/voicecheck.mp4

왜 필요한가
    "고쳤다" 는 말만으로는 아무 소용이 없다. 손님은 **귀로 확인**하셔야 한다.
    그런데 손님에게는 폰밖에 없어서 mp3 파일을 하나씩 눌러 들을 수가 없다.
    그래서 관리자 페이지에서 그냥 재생 버튼만 누르면 되도록 **영상(mp4)** 으로 만든다.

무엇이 담기나 (튀는 컷 하나당 두 도막)
    도막 1  고치기 전 : 앞 해설 → **문제의 컷(고치기 전)** → 뒤 해설
    도막 2  고친 후   : 앞 해설 → **문제의 컷(고친 후)**   → 뒤 해설
    같은 앞뒤 문장을 두 번 듣게 해서, 가운데 한 줄만 튀는지 아닌지를
    **직접 견주어** 판단하실 수 있게 한다. 화면에는 지금 어느 쪽인지 크게 띄운다.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tts import measure_f0                      # noqa: E402
from graphics import font_path                  # noqa: E402
from PIL import Image, ImageDraw, ImageFont      # noqa: E402

W, H = 1280, 720
BG, FG, DIM, GOLD = (16, 17, 22), (238, 240, 246), (150, 154, 170), (226, 178, 84)
GAP = 0.35                                       # 문장 사이 쉼(초)


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True, timeout=600)


def flat_cuts(doc):
    return [c for a in doc.get("acts", []) for c in a.get("cuts", [])]


def neighbours(cuts, target, n=1):
    """같은 인물의 **바로 앞·뒤 대사**를 고른다. 견줄 기준이 되어야 하므로 같은 인물이어야 한다."""
    ids = [c["id"] for c in cuts]
    if target not in ids:
        return [], None, []
    i = ids.index(target)
    sp = cuts[i].get("speaker", "narrator")
    before, after = [], []
    for j in range(i - 1, -1, -1):
        if cuts[j].get("speaker") == sp and (cuts[j].get("text") or "").strip():
            before.insert(0, cuts[j])
            if len(before) >= n:
                break
    for j in range(i + 1, len(cuts)):
        if cuts[j].get("speaker") == sp and (cuts[j].get("text") or "").strip():
            after.append(cuts[j])
            if len(after) >= n:
                break
    return before, cuts[i], after


def wrap(draw, text, fnt, width):
    out, line = [], ""
    for ch in text:
        if draw.textlength(line + ch, font=fnt) > width and line:
            out.append(line)
            line = ch
        else:
            line += ch
    if line:
        out.append(line)
    return out


def card(png, title, sub, lines, hot, note):
    """도막 하나를 설명하는 화면. 지금 무엇을 듣고 있는지 글로 크게 알려 준다."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    fp = font_path()
    big = ImageFont.truetype(fp, 76)
    mid = ImageFont.truetype(fp, 34)
    sml = ImageFont.truetype(fp, 27)
    tiny = ImageFont.truetype(fp, 23)

    d.text((70, 62), title, font=big, fill=GOLD if "후" in title else FG)
    d.text((70, 158), sub, font=mid, fill=DIM)
    d.line((70, 214, W - 70, 214), fill=(52, 54, 64), width=2)

    y = 250
    for cid, text in lines:
        on = cid == hot
        col = GOLD if on else DIM
        d.text((70, y), ("▶ " if on else "   ") + cid, font=sml, fill=col)
        for ln in wrap(d, text, sml, W - 300):
            d.text((250, y), ln, font=sml, fill=FG if on else DIM)
            y += 38
        if on:
            d.text((250, y), "↑ 이 한 줄이 문제였던 부분입니다", font=tiny, fill=GOLD)
            y += 34
        y += 22

    d.text((70, H - 78), note, font=tiny, fill=DIM)
    img.save(png)


def segment(work, tag, mp3s, png, out_mp4):
    """그림 한 장 + 이어 붙인 소리 = 도막 영상 하나."""
    sil = work / "sil.mp3"
    if not sil.exists():
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", "anullsrc=r=24000:cl=mono", "-t", str(GAP), "-b:a", "160k", str(sil)])
    seq = []
    for i, m in enumerate(mp3s):
        if i:
            seq.append(sil)
        seq.append(m)
    # concat **필터**를 쓴다(데머서가 아니라). 파일마다 표본율이 달라도 안전하다.
    cmd = ["ffmpeg", "-v", "error", "-y"]
    for s in seq:
        cmd += ["-i", str(s)]
    chain = "".join(f"[{i}:a]" for i in range(len(seq))) + f"concat=n={len(seq)}:v=0:a=1[a]"
    voice = work / f"{tag}.mp3"
    run(cmd + ["-filter_complex", chain, "-map", "[a]", "-b:a", "160k", str(voice)])
    run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(png), "-i", str(voice),
         "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", "12",
         "-c:a", "aac", "-b:a", "192k", "-shortest", str(out_mp4)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--voice", default="build/voice")
    ap.add_argument("--keep", default="build/demo_before")
    ap.add_argument("--cut", default="H05,A1-15")
    ap.add_argument("--stage", choices=("before", "build"), required=True)
    ap.add_argument("--out", default="build/voicecheck.mp4")
    a = ap.parse_args()

    doc = json.loads(Path(a.script).read_text(encoding="utf-8"))
    cuts = flat_cuts(doc)
    vdir, keep = Path(a.voice), Path(a.keep)
    targets = [s.strip() for s in a.cut.split(",") if s.strip()]

    # ── ① 고치기 전 소리를 챙겨 둔다 ──
    if a.stage == "before":
        keep.mkdir(parents=True, exist_ok=True)
        n = 0
        for t in targets:
            before, cut, after = neighbours(cuts, t)
            for c in before + ([cut] if cut else []) + after:
                src = vdir / f"{c['id']}.mp3"
                if src.exists():
                    shutil.copyfile(src, keep / f"{c['id']}.mp3")
                    n += 1
            if cut:
                hz = measure_f0(vdir / f"{t}.mp3") if (vdir / f"{t}.mp3").exists() else None
                print(f"  {t} 고치기 전 높이: {hz:.1f}Hz" if hz else f"  {t} 높이를 못 쟀다")
        print(f"고치기 전 소리 {n}컷을 챙겨 뒀다 → {keep}")
        return 0

    # ── ② 비교 영상을 만든다 ──
    if not keep.is_dir():
        print(f"❌ 고치기 전 소리가 없다: {keep}")
        return 2
    work = Path(a.out).parent / "demo_work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)

    parts = []
    for t in targets:
        before, cut, after = neighbours(cuts, t)
        if cut is None:
            print(f"⚠️ {t} 를 대본에서 못 찾았다 — 건너뛴다")
            continue
        row = before + [cut] + after
        lines = [(c["id"], (c.get("text") or "").strip()) for c in row]
        old_hz = measure_f0(keep / f"{t}.mp3") if (keep / f"{t}.mp3").exists() else None
        new_hz = measure_f0(vdir / f"{t}.mp3") if (vdir / f"{t}.mp3").exists() else None
        others = [measure_f0(vdir / f"{c['id']}.mp3") for c in before + after]
        others = [h for h in others if h]
        base = sum(others) / len(others) if others else None

        def note(hz):
            if not hz or not base:
                return "앞뒤 문장과 견주어 들어 보십시오."
            return (f"이 도막의 가운데 줄 {hz:.0f}Hz · 앞뒤 문장 평균 {base:.0f}Hz"
                    f" (차이가 작을수록 같은 사람으로 들립니다)")

        for tag, src, title, sub in (
                ("old", keep, "고치기 전", f"{t} — 손님이 지적하신 그 부분"),
                ("new", vdir, "고친 후", f"{t} — 같은 문장을 다시")):
            png = work / f"{t}_{tag}.png"
            hz = old_hz if tag == "old" else new_hz
            card(png, title, sub, lines, t, note(hz))
            mp3s = []
            for c in row:
                # 가운데 한 줄만 그 시점의 것을 쓰고, 앞뒤는 지금 것을 쓴다
                # (앞뒤는 손댄 적이 없으므로 어느 쪽이든 같다).
                d = src if c["id"] == t else vdir
                p = d / f"{c['id']}.mp3"
                if not p.exists():
                    p = vdir / f"{c['id']}.mp3"
                if p.exists():
                    mp3s.append(p)
            if not mp3s:
                continue
            mp4 = work / f"{t}_{tag}.mp4"
            segment(work, f"{t}_{tag}", mp3s, png, mp4)
            parts.append(mp4)

        if old_hz and new_hz:
            print(f"  {t}  {old_hz:.1f}Hz → {new_hz:.1f}Hz"
                  f"{f' (앞뒤 평균 {base:.1f}Hz)' if base else ''}")

    if not parts:
        print("❌ 만들 도막이 없다")
        return 2

    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-c", "copy", str(out)])
    sec = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(out)], capture_output=True, text=True)
    print(f"비교 영상 {len(parts)}도막 · {float(sec.stdout.strip()):.0f}초 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
