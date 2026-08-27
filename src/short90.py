#!/usr/bin/env python3
"""⭐ 90초 한 편을 만든다 — 그림 + 나레이션 + 자막 (2026-08-27 신설).

    python3 src/short90.py stills          컷마다 그림 한 장 (세로 9:16)
    python3 src/short90.py voice           컷마다 소리 (나레이션·대사)
    python3 src/short90.py build           한 편으로 조립 → build/s90/S90_short.mp4
    python3 src/short90.py all             위 셋을 차례로

왜 16화가 아니라 한 편인가
    운영자 확정 — "90초로 만들어." 16화는 한 화에 사건이 하나뿐이라 "그래서
    뭔데" 를 16번 기다려야 했다. 한 편이면 5초 만에 32억이 나온다.

왜 Veo 를 안 쓰나 (기본값)
    운영자: "비오로 하기 돈아까우니까." 컷마다 영상을 만들면 90초에 7천 원이
    넘는다. **그림 한 장 + 나레이션**으로 만들면 같은 90초가 3천 원대다.
    손님이 보고 좋다고 한 참고 영상들도 전부 이 방식이다.
    대사 컷을 손으로 좋게 만들고 싶으면 S90.json 의 `veo` 프롬프트를 제미나이에
    붙여 만든 mp4 를 build/s90/clips/c07.mp4 로 넣어 두면 그 컷만 영상이 된다.

화면 (1080 × 1920 · 세로 꽉 채움)
    그림이 화면 전체 · 아주 느린 줌
    y 1300~1620  자막 (대사 컷은 위에 이름표)
    y 1620~1920  비움 — 유튜브 쇼츠 단추가 덮는 자리
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cost                                                  # noqa: E402
import reuse                                                 # noqa: E402
import still as ST                                           # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "data" / "series" / "S90.json"
OUT = ROOT / "build" / "s90"

W, H = 1080, 1920
FPS = 30
FONT_SUB = ROOT / "assets" / "fonts" / "NanumGothic_ExtraBold.ttf"
FONT_NAME = ROOT / "assets" / "fonts" / "KoPub_Batang_Pro_Bold.otf"

SUB_TOP, SUB_BOT = 1300, 1620    # 자막 칸 (아래 300px 은 쇼츠 단추 자리라 비운다)
SUB_MAX, SUB_MIN, SUB_LINES = 84, 58, 3
SUB_GAP = 1.24
SIDE = 60
NAME_Y, NAME_SIZE = 1218, 46
SCRIM_TOP = 1080                 # 여기부터 아래로 서서히 어두워진다
SCRIM_MAX = 0.88                 # 맨 아래 어두움 (0~1)
MARK_SIZE, MARK_Y = 34, 44
CHANNEL = "판결극장"
GOLD = (198, 160, 74, 255)
WHITE = (255, 255, 255, 255)
PAD = 0.55                       # 말이 끝난 뒤 남기는 여운(초)
ZOOM_TO = 1.10                   # 컷 하나 도는 동안 커지는 정도
ZOOM_SRC = 1.4                   # 줌 전에 그림을 키워 두는 배수 (떨림 방지)

# 목소리 — 사람마다 고정한다 (컷마다 달라지면 딴 사람이 된다)
VOICE = {
    "나레이션": "ko-KR-Neural2-C",
    "아내": "ko-KR-Neural2-A",
    "내연녀": "ko-KR-Neural2-B",
    "남편": "ko-KR-Wavenet-C",
    "변호사": "ko-KR-Wavenet-D",
    "딸": "ko-KR-Wavenet-A",
}
NARR_RATE = 1.02                 # 나레이션은 아주 조금 빠르게 (또박또박은 유지)


class Short90Error(RuntimeError):
    pass


def load():
    if not DOC.exists():
        raise Short90Error("data/series/S90.json 이 없다 — "
                           "python3 tools/build_short90.py 를 먼저 돌린다.")
    return json.loads(DOC.read_text(encoding="utf-8"))


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise Short90Error(f"ffmpeg 가 실패했다:\n{p.stderr[-900:]}")
    return p.stdout


def dur_of(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip() or 0)


# ── ① 그림 ────────────────────────────────────────────────────
# 화면 이름 ↔ 인물 카드 파일 이름 (카드에는 아내가 '본처' 로 적혀 있다)
ST_NAME = {"아내": "본처"}


def cards_dir():
    return OUT / "cards"


def stills(doc):
    d = OUT / "stills"
    d.mkdir(parents=True, exist_ok=True)
    print(f"■ 컷 그림 {len(doc['cuts'])}장 (세로 9:16 · 약 "
          f"{cost.image_krw(ST.MODEL, ST.SIZE) * len(doc['cuts']):,.0f}원)")
    made = 0
    for c in doc["cuts"]:
        out = d / f"c{c['n']:02d}.png"
        refs = [p for p in (ST.card_path(cards_dir(), ST_NAME.get(w, w))
                            for w in c.get("who") or []) if p.exists()]
        sig = reuse.sig_of(c["still"], *refs)
        ok, why = reuse.can_reuse(out, sig)
        print(f"  컷{c['n']:>2} {'·'.join(c.get('who') or []) or '—'}")
        if ok:
            print("    (그대로다 — 건너뛴다)")
            made += 1
            continue
        if why:
            print(f"    ⚠️ {why} — 다시 만든다")
        ST.gen(c["still"], out, refs=refs, ratio="9:16",
               seed=ST.seed_of("S90", c["n"]))
        reuse.stamp(out, sig)
        made += 1
    print(f"\n■ 그림 {made}/{len(doc['cuts'])}장")
    return 0 if made == len(doc["cuts"]) else 1


# ── ② 소리 ────────────────────────────────────────────────────
def voices(doc):
    import tts                                               # 늦게 부른다(열쇠 필요)
    d = OUT / "voice"
    d.mkdir(parents=True, exist_ok=True)
    print(f"■ 소리 {len(doc['cuts'])}줄")
    made = 0
    for c in doc["cuts"]:
        out = d / f"c{c['n']:02d}.wav"
        who = c["kind"]
        voice = VOICE.get(who) or VOICE["나레이션"]
        rate = NARR_RATE if who == "나레이션" else 1.0
        sig = reuse.sig_of(c["text"], voice, rate)
        ok, why = reuse.can_reuse(out, sig)
        print(f"  컷{c['n']:>2} [{who}] {c['text'][:30]}")
        if ok:
            print("    (그대로다 — 건너뛴다)")
            made += 1
            continue
        if why:
            print(f"    ⚠️ {why} — 다시 만든다")
        got = tts.say(c["text"], voice, rate, 0.0, out)
        if not got or not Path(got).exists():
            raise Short90Error(f"컷{c['n']} 소리를 못 만들었다")
        reuse.stamp(out, sig)
        made += 1
        print(f"    ✅ {out.name} ({dur_of(out):.1f}초)")
    print(f"\n■ 소리 {made}/{len(doc['cuts'])}줄")
    return 0 if made == len(doc["cuts"]) else 1


# ── ③ 자막 그림 ───────────────────────────────────────────────
def wrap(d, text, font, max_w):
    lines, cur = [], ""
    for word in str(text).split():
        t = (cur + " " + word).strip()
        if cur and d.textlength(t, font=font) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = t
    if cur:
        lines.append(cur)
    return lines


def fit(d, text, size_max, max_w, max_h):
    """칸에 들어갈 때까지 글자를 줄인다. 어르신용이라 SUB_MIN 아래로는 안 줄인다."""
    for size in range(size_max, SUB_MIN - 1, -2):
        f = ImageFont.truetype(str(FONT_SUB), size)
        lines = wrap(d, text, f, max_w)
        if len(lines) <= SUB_LINES and len(lines) * size * SUB_GAP <= max_h:
            return f, lines, size
    f = ImageFont.truetype(str(FONT_SUB), SUB_MIN)
    return f, wrap(d, text, f, max_w)[:SUB_LINES], SUB_MIN


def overlay(c, out):
    """컷 하나의 자막·이름표·채널 이름을 투명 그림 한 장으로 그린다."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # 아래쪽 어둡게 — 그림 위에 흰 글자를 얹어도 읽히게 (서서히 진해진다)
    scrim = Image.new("RGBA", (W, H - SCRIM_TOP), (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    # ⚠️ 맨 아래(1920)에서 가장 진해지게 두면 **자막이 있는 자리(1300~1620)가
    #    아직 옅다.** 밝은 그림 위에서 글자가 묻힌다 — 자막 칸 아래쪽에서
    #    이미 가장 진하도록 잡는다.
    span = H - SCRIM_TOP
    full = max(1, SUB_BOT - SCRIM_TOP)
    for y in range(span):
        a = int(255 * SCRIM_MAX * min(1.0, y / full) ** 1.2)
        sd.line([(0, y), (W, y)], fill=(0, 0, 0, a))
    img.alpha_composite(scrim, (0, SCRIM_TOP))

    d = ImageDraw.Draw(img)
    # 채널 이름 (오른쪽 위, 조용하게)
    mf = ImageFont.truetype(str(FONT_NAME), MARK_SIZE)
    d.text((W - SIDE, MARK_Y), CHANNEL, font=mf, fill=(255, 255, 255, 168),
           anchor="ra")

    # 이름표 — 대사 컷만 (나레이션은 말하는 사람이 없다)
    if c["kind"] != "나레이션":
        nf = ImageFont.truetype(str(FONT_NAME), NAME_SIZE)
        d.text((W // 2, NAME_Y), c["kind"], font=nf, fill=GOLD, anchor="ma")

    # 자막
    f, lines, size = fit(d, c["text"], SUB_MAX, W - SIDE * 2, SUB_BOT - SUB_TOP)
    step = size * SUB_GAP
    y = SUB_TOP + max(0, ((SUB_BOT - SUB_TOP) - len(lines) * step) / 2)
    for ln in lines:
        # 얇은 검은 테두리 — 밝은 그림 위에서도 글자가 안 묻힌다
        d.text((W // 2, y), ln, font=f, fill=WHITE, anchor="ma",
               stroke_width=4, stroke_fill=(0, 0, 0, 210))
        y += step
    img.save(out)
    return out


# ── ④ 조립 ────────────────────────────────────────────────────
def cut_video(c, still, voice, clip, ov, out):
    """컷 하나 → mp4. 손으로 만든 영상(clip)이 있으면 그것을 쓰고, 없으면 그림."""
    a = dur_of(voice)
    sec = max(float(c["sec"]), a + PAD)
    frames = max(2, int(round(sec * FPS)))
    if clip and Path(clip).exists():
        src = ["-i", str(clip)]
        vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
              f"crop={W}:{H},fps={FPS},trim=0:{sec:.3f},setpts=PTS-STARTPTS[bg];")
    else:
        src = ["-loop", "1", "-i", str(still)]
        # 조금 키운 뒤 아주 느리게 줌 — 원본 크기에서 바로 줌하면 덜덜 떨린다.
        # ⚠️ 2배로 키우면 컷 하나에 6초씩 걸려 23컷이 너무 느리다. 1.4배면
        #    1.10 배 줌까지 또렷하고 속도는 3분의 2다.
        sw, sh = int(W * ZOOM_SRC), int(H * ZOOM_SRC)
        step = (ZOOM_TO - 1) / frames
        # 컷마다 줌 방향을 바꾼다 — 스물세 컷이 다 같은 쪽으로 커지면 지겹다
        z = (f"min(1+{step:.6f}*on,{ZOOM_TO})" if c["n"] % 2 else
             f"max({ZOOM_TO}-{step:.6f}*on,1.0)")
        vf = (f"[0:v]scale={sw}:{sh}:force_original_aspect_ratio=increase,"
              f"crop={sw}:{sh},"
              f"zoompan=z='{z}':d={frames}:x='iw/2-(iw/zoom/2)'"
              f":y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS}[bg];")
    run(["ffmpeg", "-y", "-v", "error", *src, "-i", str(ov), "-i", str(voice),
         "-filter_complex", vf + "[bg][1:v]overlay=0:0:format=auto[v]",
         "-map", "[v]", "-map", "2:a", "-af", "apad",
         "-t", f"{sec:.3f}", "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
         "-shortest", str(out)])
    return sec


def build(doc):
    stills_d, voice_d = OUT / "stills", OUT / "voice"
    clips_d = OUT / "clips"
    parts_d = OUT / "parts"
    parts_d.mkdir(parents=True, exist_ok=True)
    (OUT / "ov").mkdir(parents=True, exist_ok=True)

    total, parts = 0.0, []
    print(f"■ 「{doc['title']}」 {len(doc['cuts'])}컷 조립")
    for c in doc["cuts"]:
        n = c["n"]
        still = stills_d / f"c{n:02d}.png"
        voice = voice_d / f"c{n:02d}.wav"
        clip = clips_d / f"c{n:02d}.mp4"
        if not still.exists() and not clip.exists():
            raise Short90Error(f"컷{n} 그림이 없다 — 먼저 stills 를 돌린다")
        if not voice.exists():
            raise Short90Error(f"컷{n} 소리가 없다 — 먼저 voice 를 돌린다")
        ov = overlay(c, OUT / "ov" / f"c{n:02d}.png")
        out = parts_d / f"c{n:02d}.mp4"
        sec = cut_video(c, still, voice, clip if clip.exists() else None, ov, out)
        total += sec
        parts.append(out)
        mark = "영상" if clip.exists() else "그림"
        print(f"  컷{n:>2} [{c['kind']:<4}] {sec:>5.2f}초 ({mark})")

    # ⚠️ concat 목록 안의 경로는 **목록 파일이 있는 자리 기준**이다. 파일 이름만
    #    적으면 옆 폴더에 있는 컷을 못 찾는다 (시험이 바로 잡아 줬다).
    lst = OUT / "parts.txt"
    lst.write_text("".join(f"file '{p.relative_to(OUT)}'\n" for p in parts),
                   encoding="utf-8")
    final = OUT / "S90_short.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(final)])
    got = dur_of(final)
    try:
        name = final.relative_to(ROOT)
    except ValueError:                     # 시험처럼 저장소 밖에 만들 때
        name = final
    print(f"\n■ {name} — {got:.1f}초 ({final.stat().st_size / 1e6:.1f}MB)")
    if got < 60 or got > 130:
        print(f"  ⚠️ 90초 편인데 {got:.0f}초다 — 대본 길이를 손봐야 한다")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["stills", "voice", "build", "all"])
    a = ap.parse_args()
    try:
        doc = load()
        if a.what in ("stills", "all"):
            if stills(doc):
                return 1
        if a.what in ("voice", "all"):
            if voices(doc):
                return 1
        if a.what in ("build", "all"):
            return build(doc)
        return 0
    except (Short90Error, ST.StillError, cost.MonthlyCapReached) as e:
        print(f"❌ {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
