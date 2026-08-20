#!/usr/bin/env python3
"""⭐ 쇼츠 한 편을 조립한다 — 위에 후킹 문구, 가운데 영상, 아래 자막.

    python3 src/shorts.py S001 1 --clips 받은클립폴더/ --out build/
    python3 src/shorts.py --demo 클립.mp4 --hook "..." --sub "..."   (한 컷만 미리보기)

화면 배치 (2026-08-20 운영자 지시: "상단 검은 빈 프레임에는 후킹 문구,
아래쪽 검은 빈 프레임에는 자막")

    ┌───────────────── 1080 × 1920 (쇼츠) ─────────────────┐
    │                                        판결극장  ← 우측 상단 │  y 40
    │                                                       │
    │            후 킹  문 구  (크게, 최대 3줄)               │  y 150~470
    │                                                       │
    ├───────────────────────────────────────────────────────┤  y 520
    │                                                       │
    │              영상 4:3  (1080 × 810)                    │
    │                                                       │
    ├───────────────────────────────────────────────────────┤  y 1330
    │              자 막  (최대 3줄)                          │  y 1370~1600
    │                                                       │
    │        (이 아래는 유튜브 단추가 덮는 자리 — 비워 둔다)      │  y 1600~
    └───────────────────────────────────────────────────────┘

왜 이렇게 나눴나
    · 영상은 4:3 이라 폭을 꽉 채우면 세로 810px 이다. 남는 1110px 을 위아래로
      나눠 쓴다.
    · 자막을 화면 맨 아래에 두면 **유튜브 쇼츠의 제목·좋아요 단추에 가린다.**
      아래 320px 은 비워 두고 자막은 영상 바로 밑에 붙인다.
    · 후킹 문구는 처음 1초에 남느냐 떠나느냐를 가른다 — 가장 크게 둔다.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import clip as C                                            # noqa: E402

FONT_B = ROOT / "assets" / "fonts" / "KoPub_Dotum_Pro_Bold.otf"
FONT_M = ROOT / "assets" / "fonts" / "KoPub_Dotum_Pro_Medium.otf"

W, H = 1080, 1920                # 쇼츠 화면
VIDEO_Y, VIDEO_H = 520, 810      # 4:3 영상이 앉는 자리
MARK_Y, MARK_SIZE = 40, 38       # 우측 상단 채널 이름
HOOK_TOP, HOOK_BOT, HOOK_SIZE = 150, 470, 76
SUB_TOP, SUB_BOT, SUB_SIZE = 1360, 1610, 58
SIDE = 64                        # 좌우 여백
GOLD = (198, 160, 74)
CHANNEL = "판결극장"


def wrap(draw, text, font, max_w):
    """글자 폭을 실제로 재서 줄을 나눈다 (한국어는 어절 단위로 끊는다)."""
    words, lines, cur = str(text or "").split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit(draw, text, path, size, max_w, max_lines, split_slash=False):
    """줄 수 안에 들어갈 때까지 글자를 줄인다. (글꼴, 줄들) 을 준다.

    split_slash — 자막은 `A대사 / B대사 / A대사` 꼴로 온다. 한 덩어리로 이어
    붙이면 누가 한 말인지 안 보이고 읽기도 나쁘다. **말한 사람마다 줄을 바꾼다.**
    """
    parts = [x.strip() for x in str(text or "").split(" / ")] if split_slash \
        else [str(text or "")]
    parts = [x for x in parts if x]
    while size >= 26:
        f = ImageFont.truetype(str(path), size)
        ls = []
        for x in parts:
            ls += wrap(draw, x, f, max_w)
        if len(ls) <= max_lines:
            return f, ls
        size -= 4
    return f, ls[:max_lines]


def block(d, lines, font, top, bottom, fill, gap=1.28):
    """정해진 칸 안에서 가운데 맞춰 그린다."""
    lh = int(font.size * gap)
    total = lh * len(lines)
    y = top + max(0, (bottom - top - total) // 2)
    for l in lines:
        x = (W - d.textlength(l, font=font)) / 2
        d.text((x, y), l, font=font, fill=fill)
        y += lh


def overlay_png(hook, sub, out):
    """글자만 있는 투명 그림 한 장 (영상 위에 얹는다)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    mark = ImageFont.truetype(str(FONT_B), MARK_SIZE)
    d.text((W - SIDE - d.textlength(CHANNEL, font=mark), MARK_Y),
           CHANNEL, font=mark, fill=GOLD + (255,))

    if str(hook or "").strip():
        f, ls = fit(d, hook, FONT_B, HOOK_SIZE, W - SIDE * 2, 3)
        block(d, ls, f, HOOK_TOP, HOOK_BOT, (255, 255, 255, 255))

    if str(sub or "").strip():
        f, ls = fit(d, sub, FONT_M, SUB_SIZE, W - SIDE * 2, 4, split_slash=True)
        block(d, ls, f, SUB_TOP, SUB_BOT, (233, 233, 239, 255))

    img.save(out)
    return out


def compose(src, hook, sub, out, tmp):
    """받은 클립 한 개 → 쇼츠 한 컷 (워터마크 지우고 4:3 자르고 글자 얹기)."""
    src, out, tmp = Path(src), Path(out), Path(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    vw, vh, sec = C.probe(src)
    mx, my, mw, mh = C.mark_box(vw, vh)
    cx, cy, cw, ch = C.crop_box(vw, vh)
    png = overlay_png(hook, sub, tmp / f"{src.stem}_txt.png")

    vf = (f"[1:v]delogo=x={mx}:y={my}:w={mw}:h={mh},"
          f"crop={cw}:{ch}:{cx}:{cy},scale={W}:{VIDEO_H}[v];"
          f"[0:v][v]overlay=0:{VIDEO_Y}[bg];"
          f"[bg][2:v]overlay=0:0[o]")
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r=24:d={sec:.3f}",
           "-i", str(src), "-i", str(png),
           "-filter_complex", vf, "-map", "[o]", "-map", "1:a?",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
           "-shortest", "-movflags", "+faststart", str(out)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패:\n{p.stderr[:600]}")
    return out


def hook_of(ep, doc):
    """이 화의 후킹 문구. 없으면 화 제목, 그것도 없으면 시리즈 제목."""
    return (str(ep.get("hook") or "").strip()
            or str(ep.get("title") or "").strip()
            or str(doc.get("title") or "").strip())


def episode(sid, no, clips_dir, out_dir):
    """한 화(5컷)를 모아 30초 쇼츠 하나로."""
    doc = json.loads((ROOT / "data" / "series" / f"{sid}.json").read_text(encoding="utf-8"))
    ep = next((e for e in doc["episodes"] if int(e.get("no", 0)) == int(no)), None)
    if not ep:
        raise SystemExit(f"❌ {sid} 에 {no}화가 없다")
    clips_dir, out_dir = Path(clips_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / "_tmp"
    hook = hook_of(ep, doc)
    print(f"{sid} {no}화 「{ep.get('title','')}」")
    print(f"  후킹 문구: {hook}")

    parts = []
    for c in ep["cuts"]:
        n = int(c["n"])
        src = next((p for p in sorted(clips_dir.glob(f"*c{n:03d}*.mp4"))), None)
        if not src:
            raise SystemExit(f"❌ {n}컷 클립이 없다 ({clips_dir}/*c{n:03d}*.mp4)")
        d = compose(src, hook, c.get("subtitle"), tmp / f"cut{n}.mp4", tmp)
        parts.append(d)
        print(f"  ✅ {n}컷 — {src.name}")

    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    final = out_dir / f"{sid}_ep{int(no):02d}_short.mp4"
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(lst), "-c", "copy", "-movflags", "+faststart",
                        str(final)], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"이어 붙이기 실패:\n{p.stderr[:400]}")
    print(f"\n✅ {final.name} — {len(parts)}컷 · {len(parts) * 6}초")
    return final


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sid", nargs="?", default="")
    ap.add_argument("no", nargs="?", default="")
    ap.add_argument("--clips", default="build/clips")
    ap.add_argument("--out", default="build/shorts")
    ap.add_argument("--demo", default="", help="클립 하나로 배치만 미리 본다")
    ap.add_argument("--hook", default="")
    ap.add_argument("--sub", default="")
    a = ap.parse_args()
    if a.demo:
        out = Path(a.out) / (Path(a.demo).stem + "_short.mp4")
        out.parent.mkdir(parents=True, exist_ok=True)
        compose(a.demo, a.hook, a.sub, out, Path(a.out) / "_tmp")
        print(f"✅ {out}")
        return 0
    if not a.sid or not a.no:
        ap.error("시리즈 번호와 화 번호를 달라 (예: S001 1)")
    episode(a.sid, a.no, a.clips, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
