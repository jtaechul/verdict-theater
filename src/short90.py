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


def turns_of(c):
    """이 컷에서 말하는 차례. 옛 대본(turns 없음)도 받아 준다."""
    if c.get("turns"):
        return [(w, t) for w, t in c["turns"]]
    return [(c.get("kind") or "나레이션", c.get("text") or "")]


def is_narr(c):
    return all(w == "나레이션" for w, _ in turns_of(c))


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


def has_audio(path):
    """이 영상에 소리가 붙어 있는가."""
    out = run(["ffprobe", "-v", "error", "-select_streams", "a",
               "-show_entries", "stream=codec_type", "-of",
               "default=nw=1:nk=1", str(path)])
    return "audio" in out


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
        turns = turns_of(c)
        plan = [(w, t, VOICE.get(w) or VOICE["나레이션"],
                 NARR_RATE if w == "나레이션" else 1.0) for w, t in turns]
        sig = reuse.sig_of(*[f"{w}|{t}|{v}|{r}" for w, t, v, r in plan])
        ok, why = reuse.can_reuse(out, sig)
        # ⚠️ 길이 기록이 없으면 자막을 맞출 수가 없다 → 그 컷만 다시 만든다
        if ok and not lens_of(out).exists():
            ok, why = False, "줄마다 길이 기록이 없다 — 자막을 못 맞춘다"
        print(f"  컷{c['n']:>2} [{'·'.join(w for w, _ in turns)}] {c['text'][:30]}")
        if ok:
            print("    (그대로다 — 건너뛴다)")
            made += 1
            continue
        if why:
            print(f"    ⚠️ {why} — 다시 만든다")
        # ⭐ 한 컷 안에서 두 사람이 주고받으면 목소리를 따로 만들어 이어 붙인다
        parts = []
        for i, (w, t, v, r) in enumerate(plan):
            one = d / f"c{c['n']:02d}_{i}.wav"
            got = tts.say(t, v, r, 0.0, one)
            if not got or not Path(got).exists():
                raise Short90Error(f"컷{c['n']} {w} 소리를 못 만들었다")
            parts.append(Path(got))
        # ⭐⭐ 2026-08-31 손님: "대사 목소리와 자막이 시간차가 발생."
        #    자막 바뀌는 때를 **글자 수로 짐작**하고 있었다. 그런데 실제로
        #    말하는 데 걸리는 시간은 글자 수와 안 맞는다(사람마다 속도가
        #    다르고 쉼도 있다). 게다가 컷 길이에는 여운(PAD)까지 들어 있어
        #    자막이 통째로 늘어났다 — 그래서 첫 줄이 오래 남고 둘째 줄이
        #    목소리보다 늦게 떴다.
        #    → 여기서 **줄마다 진짜 길이**를 재서 적어 둔다. 짐작을 없앤다.
        lens_of(out).write_text(
            json.dumps([round(dur_of(x), 3) for x in parts]), encoding="utf-8")
        if len(parts) == 1:
            parts[0].replace(out)
        else:
            lst = d / f"c{c['n']:02d}.txt"
            lst.write_text("".join(f"file '{x.name}'\n" for x in parts),
                           encoding="utf-8")
            run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                 "-i", str(lst), "-c", "copy", str(out)])
            for x in parts:
                x.unlink(missing_ok=True)
            lst.unlink(missing_ok=True)
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


def overlay(c, out, turn=None):
    """컷 하나(또는 그 안의 한 차례)의 자막·이름표를 투명 그림으로 그린다."""
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

    who, text = turn if turn else ("나레이션" if is_narr(c) else c["kind"], c["text"])

    # 이름표 — 대사만 (나레이션은 말하는 사람이 없다)
    if who != "나레이션":
        nf = ImageFont.truetype(str(FONT_NAME), NAME_SIZE)
        d.text((W // 2, NAME_Y), who, font=nf, fill=GOLD, anchor="ma")

    # 자막
    f, lines, size = fit(d, text, SUB_MAX, W - SIDE * 2, SUB_BOT - SUB_TOP)
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
def lens_of(wav):
    """그 컷의 **줄마다 소리 길이**를 적어 둔 자리 (자막을 맞추는 데 쓴다)."""
    return Path(wav).with_suffix(".len.json")


def syl(t):
    """한국어 글자 수 (자막이 떠 있을 시간을 나누는 잣대)."""
    return max(1, len([x for x in str(t) if not x.isspace()]))


def sub_windows(c, sec, voice):
    """자막 한 줄씩 **언제부터 언제까지** 떠 있을지.

    ⭐⭐ 2026-08-31 손님: "대사 목소리와 자막이 시간차가 발생."
       예전에는 **글자 수로 짐작**해 컷 길이를 나눴다. 두 군데가 어긋난다 —
         ① 글자 수와 실제 말하는 시간은 안 맞는다 (속도·쉼이 사람마다 다르다)
         ② 컷 길이(sec)에는 말이 끝난 뒤의 여운(PAD)과 대본에 적힌 넉넉한
            초까지 들어 있다. 그 비율로 나누면 자막이 **통째로 늘어나서**
            첫 줄이 오래 남고 둘째 줄이 목소리보다 늦게 뜬다.
       이제 소리를 만들 때 적어 둔 **줄마다 진짜 길이**로 나눈다.
       (voice 가 None 이면 — 올린 영상의 소리를 쓰는 컷 — 옛 방식으로 돌아간다)
    """
    turns = turns_of(c)
    real = []
    if voice:
        f = lens_of(voice)
        if f.exists():
            try:
                got = json.loads(f.read_text(encoding="utf-8"))
                if isinstance(got, list) and len(got) == len(turns):
                    real = [float(x) for x in got]
            except Exception:                                # noqa: BLE001
                real = []
    at, t0 = [], 0.0
    if real:
        for i, d in enumerate(real):
            # 마지막 줄은 여운까지 끌고 간다 (말이 끝나도 글은 남아 있어야 한다)
            t1 = sec if i == len(real) - 1 else min(sec, t0 + d)
            at.append((t0, t1))
            t0 = t1
    else:
        tot = sum(syl(t) for _, t in turns)
        for i, (_, t) in enumerate(turns):
            t1 = sec if i == len(turns) - 1 else t0 + sec * syl(t) / tot
            at.append((t0, t1))
            t0 = t1
    return at


def cut_video(c, still, voice, clip, ovs, out):
    """컷 하나 → mp4. 손으로 만든 영상(clip)이 있으면 그것을 쓰고, 없으면 그림.

    ⭐⭐ 2026-08-27 손님: "이미지는 중간중간 섞여 있고 동영상도 있어야 돼."
       그래서 소리를 누가 낼지도 컷마다 갈린다 —
         · **대사 컷 + 올린 영상** → 그 영상 안에서 사람이 한국어로 말한다.
           우리 목소리를 덮어씌우면 입과 소리가 어긋난다 → **영상 소리를 쓴다**
         · **나레이션 컷** → 화면에서 아무도 말하지 않는다 → **우리 나레이션**
           (영상을 올렸어도 그 소리는 안 쓴다. 그래야 나레이션이 안 묻힌다)
    """
    clip = Path(clip) if clip and Path(clip).exists() else None
    talks = not is_narr(c)
    use_clip_audio = bool(clip and talks and has_audio(clip))
    if use_clip_audio:
        # ⚠️ 말하는 길이는 **영상이 정한다.** 대본의 초에 맞춰 늘이거나 줄이면
        #    말이 잘리거나 같은 말이 두 번 나온다. 컷 길이 = 영상 길이.
        sec = dur_of(clip)
        snd = []                      # 소리는 영상(0번) 안에 있다
        amap = "0:a"
        loop = []                     # 늘일 일이 없으니 되돌려 잇지 않는다
    else:
        sec = max(float(c["sec"]), dur_of(voice) + PAD)
        snd = ["-i", str(voice)]      # 0=화면 · 1=자막 · 2=우리 목소리
        amap = "2:a"
        loop = ["-stream_loop", "-1"] if clip else []
    frames = max(2, int(round(sec * FPS)))
    if clip:
        # ⚠️ 올린 영상이 컷보다 짧으면 마지막 그림이 얼어붙는다 — 되돌려 잇는다
        src = [*loop, "-i", str(clip)]
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
    # ⭐ 한 컷 안에서 두 사람이 주고받으면 **자막도 차례대로** 바뀌어야 한다.
    #
    # ⭐⭐ 2026-08-31 손님: "대사 목소리와 자막이 시간차가 발생."
    #    예전에는 **글자 수로 짐작**해 컷 길이를 나눴다. 두 군데가 어긋난다 —
    #      ① 글자 수와 실제 말하는 시간은 안 맞는다 (사람마다 속도·쉼이 다르다)
    #      ② 컷 길이(sec)에는 말이 끝난 뒤의 여운(PAD)과 대본에 적힌 넉넉한
    #         초까지 들어 있어, 그 비율로 나누면 자막이 통째로 늘어난다.
    #         → 첫 줄이 오래 남고, 둘째 줄이 목소리보다 **늦게** 뜬다.
    #    이제 소리를 만들 때 적어 둔 **줄마다 진짜 길이**로 나눈다.
    #    (올린 영상의 소리를 쓰는 컷은 우리 목소리가 아니므로 옛 방식 그대로)
    turns = turns_of(c)
    at = sub_windows(c, sec, None if use_clip_audio else voice)
    chain = "[bg]"
    for i, (a, b) in enumerate(at):
        nxt = f"[v{i}]" if i < len(at) - 1 else "[v]"
        chain_in = chain
        vf += (f"{chain_in}[{i + 1}:v]overlay=0:0:format=auto"
               f":enable='between(t,{a:.3f},{b:.3f})'{nxt};")
        chain = nxt
    vf = vf.rstrip(";")
    ovin = []
    for o in ovs:
        ovin += ["-i", str(o)]
    # 소리 입력 번호는 화면(0) + 자막 장수 뒤부터다
    if amap != "0:a":
        amap = f"{1 + len(ovs)}:a"
    run(["ffmpeg", "-y", "-v", "error", *src, *ovin, *snd,
         "-filter_complex", vf,
         "-map", "[v]", "-map", amap, "-af", "apad",
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
        ovs = [overlay(c, OUT / "ov" / f"c{n:02d}_{i}.png", t)
               for i, t in enumerate(turns_of(c))]
        out = parts_d / f"c{n:02d}.mp4"
        sec = cut_video(c, still, voice, clip if clip.exists() else None, ovs, out)
        total += sec
        parts.append(out)
        if not clip.exists():
            mark = "그림"
        elif is_narr(c):
            mark = "영상 + 우리 나레이션"
        else:
            mark = "영상 (그 안에서 말한다)" if has_audio(clip) else "영상 + 우리 목소리"
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
