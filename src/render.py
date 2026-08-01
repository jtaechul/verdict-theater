#!/usr/bin/env python3
"""대본 → 영상. 컷아웃 합성 + FFmpeg.

    python3 src/render.py data/scripts/EP001.json --out build/
    python3 src/render.py data/scripts/EP001.json --out build/ --shorts
    python3 src/render.py data/scripts/EP001.json --out build/ --limit 6   (앞 6컷만 시험)

만드는 방식 (지침서 8번)

    블러 처리한 배경 (JPG)
      + 흰 테두리 입힌 인물 컷아웃 (PNG, 알파)
      + 정보 그래픽 (코드가 그림)
      + 자막
      + 나레이션 TTS + 음악 + 앰비언스 + 효과음

화면을 두 겹으로 나눈다

    움직이는 겹 — 배경 + 인물. 느린 확대와 미세 진동이 걸린다
    고정된 겹 — 그래픽 + 자막. 흔들리면 읽기 어려우므로 절대 움직이지 않는다

    정지 이미지의 최대 약점이 '죽어 있어 보이는 것'인데, 배경만 천천히 밀어도 크게 달라진다.
    비용 0원.

에셋이 없으면
    캐릭터·배경·소리가 아직 없어도 **대체물(실루엣·무음)로 끝까지 돌려본다.**
    파이프라인이 도는지 먼저 확인해야 에셋에 돈을 쓸 수 있다.
    대체물을 쓴 경우 화면 구석에 표시가 찍히고 마지막에 경고를 낸다.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import graphics as G  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

W16, H16 = 1920, 1080
W9, H9 = 1080, 1920
FPS = 30

# 대체물을 몇 개나 썼는지 — 마지막에 보고한다
MISSING = {"char": set(), "bg": set(), "audio": set()}


def run(cmd, quiet=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"명령 실패: {' '.join(cmd[:6])}…\n{r.stderr[-1500:]}")
    return r


def ffprobe_dur(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)])
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


# ── 에셋 찾기 (없으면 대체물) ─────────────────────────────
def bg_path(code):
    p = ASSETS / "bg" / f"{code}.jpg"
    if p.exists():
        return p
    MISSING["bg"].add(code)
    return None


def char_path(code, pose):
    p = ASSETS / "char" / code / f"{pose}.png"
    if p.exists():
        return p
    MISSING["char"].add(f"{code}/{pose}")
    return None


def audio_path(kind, code):
    name = code.replace("amb_", "").replace("sfx_", "")
    p = ASSETS / kind / f"{name}.mp3"
    if p.exists():
        return p
    MISSING["audio"].add(f"{kind}/{name}")
    return None


# 대체물에 코드 이름을 찍을지. 개발 중 배치를 확인할 때만 켠다.
#   VT_DEBUG_LABELS=1 python3 src/render.py …
DEBUG_LABELS = os.environ.get("VT_DEBUG_LABELS", "") not in ("", "0", "false")


def placeholder_bg(code, W, H, flashback):
    """배경이 없을 때 쓰는 대체 그림.

    예전에는 단색 위에 `[대체 배경] home_kitchen` 이라고 크게 찍어, 화면이
    '아직 안 만든 개발 화면' 으로 보였다. 에셋이 없어도 **완성된 영상처럼** 보이게 한다.
    장면 계열마다 색을 달리해 장면이 바뀐 것은 그대로 알 수 있다."""
    fam = code.split("_")[0]
    tone = {"funeral": (44, 42, 50), "medical": (40, 54, 60), "home": (60, 50, 42),
            "court": (38, 43, 58), "office": (48, 51, 57), "daily": (58, 52, 44),
            "etc": (42, 47, 45)}.get(fam, (46, 47, 54))

    # 위가 조금 밝고 아래로 어두워지는 결. 단색보다 공간처럼 보인다
    grad = Image.new("L", (1, H))
    gp = grad.load()
    for y in range(H):
        gp[0, y] = int(255 * (1.0 - 0.55 * (y / max(1, H - 1)) ** 1.1))
    img = Image.new("RGB", (W, H), tone)
    img = Image.composite(img, Image.new("RGB", (W, H), (0, 0, 0)),
                          grad.resize((W, H)))

    # 인물 뒤쪽에 은은한 조명 하나. 화면 가운데가 살아난다
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse(
        [int(W * 0.22), int(-H * 0.10), int(W * 0.78), int(H * 0.78)], fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(int(min(W, H) * 0.16)))
    img = Image.composite(Image.new("RGB", (W, H), tuple(min(255, c + 40) for c in tone)),
                          img, glow)

    if DEBUG_LABELS:
        d = ImageDraw.Draw(img)
        f = G.font(int(H * 0.020))
        d.text((int(W * 0.02), int(H * 0.955)), code, font=f, fill=(110, 112, 120))
    return img.convert("RGBA")


def placeholder_char(code, pose, H):
    """인물 컷아웃이 없을 때 쓰는 실루엣.

    예전에는 '동그라미 + 모서리 둥근 네모' 위에 `M50A / face_cold` 를 찍어 놓아
    사람이 아니라 표지판처럼 보였다. 어깨선을 넣은 사람 모양으로 바꾸고
    가장자리를 부드럽게 눌러, 배경에서 뜬 인물처럼 읽히게 한다."""
    h = int(H * 0.72)
    w = int(h * 0.46)
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)

    head_r = int(w * 0.19)
    cx = w // 2
    head_cy = int(h * 0.12)
    d.ellipse([cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r], fill=255)
    d.rectangle([cx - int(head_r * 0.44), head_cy, cx + int(head_r * 0.44),
                 head_cy + int(head_r * 1.35)], fill=255)                  # 목 — 짧게
    # 어깨가 사람 실루엣을 만든다. 좁으면 장기말처럼 보인다
    sh_y = head_cy + int(head_r * 1.30)
    d.ellipse([cx - int(w * 0.42), sh_y - int(h * 0.015),
               cx + int(w * 0.42), sh_y + int(h * 0.13)], fill=255)        # 어깨 곡선
    d.polygon([(cx - int(w * 0.42), sh_y + int(h * 0.055)),
               (cx + int(w * 0.42), sh_y + int(h * 0.055)),
               (cx + int(w * 0.38), h),
               (cx - int(w * 0.38), h)], fill=255)                         # 몸통
    mask = mask.filter(ImageFilter.GaussianBlur(3))

    body = (150, 154, 166) if code.startswith("F") else (128, 134, 150)
    img = Image.new("RGBA", (w, h), body + (0,))
    img.putalpha(mask)

    # 위가 밝고 아래로 어두워지는 결 — 납작한 색면으로 보이지 않게
    shade = Image.new("L", (1, h))
    sp = shade.load()
    for y in range(h):
        sp[0, y] = int(255 * (1.0 - 0.45 * (y / max(1, h - 1))))
    lit = Image.new("RGBA", (w, h), body + (255,))
    dark = Image.new("RGBA", (w, h), tuple(int(c * 0.55) for c in body) + (255,))
    img = Image.composite(lit, dark, shade.resize((w, h)))
    img.putalpha(mask)

    if DEBUG_LABELS:
        dd = ImageDraw.Draw(img)
        f = G.font(int(h * 0.035))
        dd.text((int(w * 0.06), int(h * 0.94)), f"{code} {pose}", font=f, fill=(40, 42, 50, 200))
    return img


# ── 한 컷의 두 겹 만들기 ──────────────────────────────────
# 화면 위쪽을 통째로 쓰는 정보 카드. 이 위에 인물 얼굴이 겹치면 얼굴이 가려진다.
WIDE_GFX = {"amount", "timeline", "family"}

# 인물이 차지할 수 있는 최대 가로 비율. 세로 쇼츠에서 인물을 1.35배 키우기 때문에
# 옆으로 넓은 컷아웃은 이 제한이 없으면 좌우가 잘린다.
CHAR_MAX_W = 0.86

# 확대 연출(zoompan)이 매 프레임 가장자리를 깎아내는 최대 비율.
# ZOOM_MAX 까지 확대되므로 각 변에서 (1 - 1/ZOOM_MAX)/2 만큼 사라진다.
ZOOM_START = 1.0            # 첫 프레임은 **자르지 않는다** (예전 1.02 는 시작부터 2% 손실)
ZOOM_MAX = 1.05
ZOOM_EDGE = (1 - 1 / ZOOM_MAX) / 2


def build_plates(cut, W, H, vertical=False, top_line=""):
    """움직이는 겹(배경+인물)과 고정된 겹(그래픽+자막)을 만든다."""
    code = cut.get("bg", "")
    p = bg_path(code)
    if p:
        move = G.prepare_bg(p, W, H, flashback=bool(cut.get("flashback")))
    else:
        move = placeholder_bg(code, W, H, cut.get("flashback"))
        if cut.get("flashback"):
            move = G._vignette(move.convert("RGB"), 0.5).convert("RGBA")

    # 그래픽을 먼저 그려 실제로 차지한 아래끝을 잰다.
    # 이걸 안 하면 연표·가족관계도 카드가 인물의 **얼굴을 통째로 덮는다**
    # — 화면에는 목 아래 몸통만 기둥처럼 남는다.
    gfx = G.render_gfx(cut.get("gfx"), W, H)
    gfx_bottom = 0
    if gfx and (cut.get("gfx") or {}).get("type") in WIDE_GFX:
        bb = gfx.getbbox()
        gfx_bottom = bb[3] if bb else 0

    chars = cut.get("chars") or []
    if vertical and len(chars) > 1:
        chars = chars[:1]                       # 세로는 한 명만. 두 명이면 화면이 죽는다

    for c in chars:
        ccode, pose = c.get("code", ""), c.get("pose", "")
        cp = char_path(ccode, pose)
        sprite = Image.open(cp).convert("RGBA") if cp else placeholder_char(ccode, pose, H)

        scale = float(c.get("scale", 1.0)) * (1.35 if vertical else 1.0)
        target_h = int(H * 0.72 * scale)
        if gfx_bottom:
            # 카드 아래로 인물을 내린다. 정보 카드가 뜬 순간에는 카드가 주인공이고
            # 인물은 배경으로 물러나는 것이 맞다.
            room = H - int(H * 0.06) - (gfx_bottom + int(H * 0.03))
            target_h = max(int(H * 0.24), min(target_h, room))
        ratio = target_h / sprite.height
        sw = max(1, int(sprite.width * ratio))
        # 가로로도 화면을 넘지 않게 한 번 더 줄인다.
        # 세로 쇼츠(1080폭)에서 인물을 1.35배로 키우므로, 옆으로 넓은 컷아웃은
        # 그냥 두면 좌우가 잘려 나간다. 높이만 맞추면 안 된다.
        if sw > W * CHAR_MAX_W:
            k = (W * CHAR_MAX_W) / sw
            sw, target_h = max(1, int(sw * k)), max(1, int(target_h * k))
        sprite = sprite.resize((sw, target_h), Image.LANCZOS)

        if vertical:
            pos_y = float(c.get("pos_y", 0.38))
            x = (W - sprite.width) // 2
            y = int(H * pos_y) - int(sprite.height * 0.18)
        else:
            slot = {"left": 0.27, "center": 0.5, "right": 0.73}.get(c.get("pos", "center"), 0.5)
            x = int(W * slot) - sprite.width // 2
            y = H - sprite.height - int(H * 0.06)
        # 확대 연출이 가장자리를 깎아내므로, 그 몫만큼 안쪽에 세운다
        edge = int(min(W, H) * ZOOM_EDGE)
        x = min(max(x, edge - sprite.width // 4), W - sprite.width - edge + sprite.width // 4)
        move.alpha_composite(sprite, (max(0, x), max(0, y)))

    static = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if gfx:
        static = Image.alpha_composite(static, gfx)
    static = G.draw_subtitle(static, cut.get("text", ""), vertical=vertical)
    if top_line:
        static = G.draw_top_line(static, top_line)
    return move, static


# ── 컷 하나를 영상 조각으로 ──────────────────────────────
def render_cut(cut, dur, workdir, idx, W, H, vertical=False, top_line=""):
    move, static = build_plates(cut, W, H, vertical, top_line=top_line)
    mp = workdir / f"m{idx:03d}.png"
    sp = workdir / f"s{idx:03d}.png"
    move.convert("RGB").save(mp)
    static.save(sp)

    frames = max(2, int(dur * FPS))
    # 느린 확대 + 아주 약한 숨쉬기. 정지 이미지가 죽어 보이는 것을 막는다.
    # ⚠️ 예전에는 1.02 에서 시작해 **첫 프레임부터 화면의 2% 를 잘라먹었다.**
    #    1.0 에서 시작하면 첫 프레임은 원본 그대로다. 숨쉬기 진폭만큼은
    #    1.0 아래로 내려가지 않게 바닥을 깔아 둔다(zoompan 은 z<1 을 1 로 자른다).
    span = ZOOM_MAX - ZOOM_START - 0.004
    zexpr = f"{ZOOM_START + 0.004:.4f}+{span:.4f}*(on/{frames})+0.004*sin(on/26)"
    vf = (f"[0:v]scale={W * 2}:{H * 2},"
          f"zoompan=z='{zexpr}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
          f"s={W}x{H}:fps={FPS}[bg];[bg][1:v]overlay=0:0,format=yuv420p[v]")

    out = workdir / f"v{idx:03d}.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error",
         "-loop", "1", "-i", str(mp), "-loop", "1", "-i", str(sp),
         "-filter_complex", vf, "-map", "[v]", "-t", f"{dur:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", str(FPS),
         str(out)])
    return out


# ── 소리 크기 맞추기 ─────────────────────────────────────
# 효과음·앰비언스 원본은 파일마다 크기가 제각각이다.
#   실측  효과음 -19.4 ~ -41.6 dB · 앰비언스 -47.9 ~ -54.3 dB · 나레이션 -16 dB
# 예전에는 여기에 **고정 배율**(효과음 0.5, 앰비언스 0.22)만 곱했다. 그 결과
#   효과음이 목소리보다 9~32 dB 작아져 **하나도 들리지 않았고**,
#   앰비언스는 44 dB 이상 작아져 아예 없는 것과 같았다.
# 배율이 아니라 **목표 크기**를 정하고, 파일마다 필요한 만큼 올리거나 내린다.
TARGET_DB = {
    "sfx": -22.0,       # 목소리(-16)보다 6 dB 아래 — 또렷이 들리되 말을 덮지 않는다
    "amb": -36.0,       # 20 dB 아래 — 공간이 느껴지는 정도
    "bgm": -30.0,       # 14 dB 아래 — 말 밑에 깔리는 정도
}
_db_cache = {}


def mean_db(path):
    """파일의 평균 음량(dB). 한 번만 재고 기억해 둔다."""
    key = str(path)
    if key not in _db_cache:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", key,
                            "-af", "volumedetect", "-f", "null", "-"],
                           capture_output=True, text=True)
        m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
        _db_cache[key] = float(m.group(1)) if m else -30.0
    return _db_cache[key]


def gain_db(path, kind):
    """이 파일을 목표 크기로 맞추는 데 필요한 dB. 지나친 증폭은 막는다."""
    return max(-24.0, min(24.0, TARGET_DB[kind] - mean_db(path)))


# ── 소리 ────────────────────────────────────────────────
def build_audio(doc, durs, workdir, narration_dir=None):
    """나레이션 + 앰비언스 + 효과음 + 음악을 하나로 섞는다.

    ⚠️ **무음 구간을 만들지 않는다.** 완전한 무음은 '죽은 소리'로 들려 이탈을 부른다.
    앰비언스가 없으면 아주 작은 방 소리를 합성해서라도 깔아둔다."""
    cuts = [c for a in doc["acts"] for c in a["cuts"]]
    parts = []

    for i, (cut, dur) in enumerate(zip(cuts, durs)):
        # ⚠️ 조각을 **WAV(무압축)** 로 만든다. 예전에는 컷마다 AAC 로 압축해 이어붙였는데,
        #    AAC 프레임 경계가 컷 경계와 안 맞아 이음매마다 '틱' 소리가 났다.
        #    실측(조각 3개를 예전 방식으로 붙임): 가장 큰 파형 도약이 정확히 이음매에 나타났다.
        #    114컷이면 그 소리가 114번 난다 — 사용자가 들은 '치지직' 이 이것이다.
        seg = workdir / f"a{i:03d}.wav"
        inputs, filters, mixn = [], [], 0

        amb = audio_path("amb", cut.get("amb", "amb_home"))
        if amb:
            inputs += ["-stream_loop", "-1", "-i", str(amb)]
            filters.append(f"[{mixn}:a]atrim=0:{dur:.3f},"
                           f"volume={gain_db(amb, 'amb'):.1f}dB[a{mixn}]")
        else:
            # 앰비언스 음원이 없을 때 까는 '방 소리'.
            # ⚠️ 예전에는 a=0.006 그대로였는데, 나레이션이 무음이던 회차에서
            #    마지막 loudnorm 이 이 잡음만 -14 LUFS 까지 끌어올려
            #    영상 내내 '치지직' 소리만 나왔다. 낮추고 고음을 깎아 방 울림처럼 만든다.
            inputs += ["-f", "lavfi", "-i", f"anoisesrc=d={dur:.3f}:c=brown:a=0.0025"]
            filters.append(f"[{mixn}:a]lowpass=f=900,volume=1.0[a{mixn}]")
        mixn += 1

        nar = None
        if narration_dir:
            # 쇼츠는 컷 id 가 본편과 다르다(S1-01 ↔ H01). nar_id 로 찾을 자리를 지정한다.
            cand = Path(narration_dir) / f"{cut.get('nar_id', cut['id'])}.mp3"
            if cand.exists():
                nar = cand
        if nar:
            inputs += ["-i", str(nar)]
            filters.append(f"[{mixn}:a]adelay=250|250,volume=1.0[a{mixn}]")
            mixn += 1

        sfx = audio_path("sfx", cut["sfx"]) if cut.get("sfx") else None
        if sfx:
            inputs += ["-i", str(sfx)]
            filters.append(f"[{mixn}:a]adelay=120|120,"
                           f"volume={gain_db(sfx, 'sfx'):.1f}dB[a{mixn}]")
            mixn += 1

        # 조각 양 끝에 8ms 페이드. 파형이 0 에서 시작해 0 으로 끝나야 이음매가 조용하다.
        fade = min(0.008, dur / 4)
        mix = "".join(f"[a{k}]" for k in range(mixn))
        fc = (";".join(filters) +
              f";{mix}amix=inputs={mixn}:duration=first:dropout_transition=0,"
              f"apad,atrim=0:{dur:.3f},"
              f"afade=t=in:st=0:d={fade:.4f},"
              f"afade=t=out:st={max(0.0, dur - fade):.4f}:d={fade:.4f}[out]")
        run(["ffmpeg", "-y", "-loglevel", "error", *inputs,
             "-filter_complex", fc, "-map", "[out]",
             "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(seg)])
        parts.append(seg)

    lst = workdir / "alist.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    body = workdir / "voice.wav"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(body)])

    # 막별 음악을 이어 붙인다
    music = build_music(doc, durs, workdir)
    mixed = workdir / "mixed.wav"
    if music:
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(body), "-i", str(music),
             "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first[out]",
             "-map", "[out]", "-c:a", "pcm_s16le", "-ar", "48000", str(mixed)])
    else:
        mixed = body

    final = workdir / "audio.m4a"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mixed),
         "-af", loudnorm_af(mixed), "-c:a", "aac", "-b:a", "192k", str(final)])
    return final


def loudnorm_af(path):
    """음량을 -14 LUFS 로 맞추는 필터. **이득을 한 번만, 일정하게** 건다.

    ⚠️ 예전에는 `loudnorm` 을 그냥 썼다. loudnorm 은 구간마다 이득을 다르게 주는데,
    조용한 구간에서 이득을 크게 올리는 바람에 **잡음 바닥이 통째로 끌려 올라왔다.**
    실측: 거의 무음인 갈색 잡음만 넣었더니 최대 음량의 86%까지 증폭됐다.
    사용자가 들은 '치지직' 의 나머지 절반이 이것이다.

    `linear=true` 로 고정할 수 있을 것 같지만, 측정된 음량 폭이 목표(LRA)를 넘으면
    ffmpeg 가 **말없이 다시 구간별 모드로 돌아간다.** 실측으로 확인했다 —
    말과 침묵이 섞인 소리는 폭이 크므로 거의 항상 그 경우다.

    그래서 loudnorm 은 **재는 데만** 쓰고, 실제로는 `volume` 로 일정 이득을 한 번 걸고
    `alimiter` 로 봉우리만 눌러 준다. 말이 있는 곳과 조용한 곳의 차이가 그대로 유지된다.

    소리가 거의 없는 파일(나레이션이 통째로 실패한 경우)은 **올리지 않는다.**
    올리면 12분 내내 잡음만 커진 영상이 나간다."""
    target, ceiling = -14.0, -1.5
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
                        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    m = re.search(r"\{[^{}]*input_i[^{}]*\}", r.stderr, re.S)
    if not m:
        return f"alimiter=limit={ceiling}dB"
    try:
        d = json.loads(m.group(0))
        measured = float(d["input_i"])
    except Exception:
        return f"alimiter=limit={ceiling}dB"

    if measured < -45.0:
        # 사실상 무음이다. 여기서 이득을 걸면 잡음만 키운다.
        print(f"    ⚠️ 소리가 거의 없다({measured:.1f} LUFS). 음량을 올리지 않는다 —"
              f" 나레이션이 제대로 만들어졌는지 확인이 필요하다.")
        return f"alimiter=limit={ceiling}dB"

    gain = max(-12.0, min(18.0, target - measured))
    return f"volume={gain:.2f}dB,alimiter=limit={ceiling}dB"


def build_music(doc, durs, workdir):
    """막마다 정해진 음악을 그 막 길이만큼 깔고 교차 페이드로 잇는다."""
    segs, i = [], 0
    for act in doc["acts"]:
        n = len(act["cuts"])
        alen = sum(durs[i:i + n])
        i += n
        p = audio_path("bgm", act.get("bgm", "hook"))
        if not p or alen <= 0:
            continue
        s = workdir / f"m_{act['id']}.m4a"
        run(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", str(p),
             "-t", f"{alen:.3f}", "-af",
             f"afade=t=in:st=0:d=1.2,afade=t=out:st={max(0, alen - 1.5):.3f}:d=1.5",
             "-c:a", "aac", "-b:a", "160k", str(s)])
        segs.append(s)
    if not segs:
        return None
    lst = workdir / "mlist.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in segs), encoding="utf-8")
    out = workdir / "music.m4a"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(out)])
    return out


# ── 본체 ────────────────────────────────────────────────
def cut_durations(doc, narration_dir=None):
    """컷 길이를 정한다.

    나레이션이 있으면 **읽는 시간이 기준**이다. 대본의 초는 설계값일 뿐이라
    실제 음성보다 짧으면 말이 잘린다. 문장 사이 쉼 0.4~0.8초를 붙인다(지침서 8번)."""
    durs = []
    for act in doc["acts"]:
        for c in act["cuts"]:
            d = float(c.get("sec", 6.0))
            if narration_dir:
                p = Path(narration_dir) / f"{c.get('nar_id', c['id'])}.mp3"
                if p.exists():
                    d = max(d, ffprobe_dur(p) + 0.6)
            durs.append(round(d, 3))
    return durs


def make_outro_cut(last_cut, text, sec=4.2):
    """쇼츠 마무리 컷. 본문 마지막 컷의 배경을 그대로 쓴다.

    새 배경을 만들면 갑자기 장면이 튀어 '따로 붙인 티'가 난다.
    같은 배경에 마무리 문장만 얹어 자연스럽게 닫는다."""
    c = json.loads(json.dumps(last_cut))
    c["id"] = last_cut["id"] + "-out"
    c["sec"] = sec
    c["text"] = text
    c["gfx"] = None
    c["sfx"] = None
    c["speaker"] = "narrator"
    c["blackout"] = True
    c["chars"] = []                      # 마무리는 글자만. 인물이 남으면 시선이 흩어진다
    return c


def render(doc, outdir, vertical=False, cut_ids=None, narration_dir=None,
           limit=0, name="longform", short=None):
    outdir = Path(outdir)
    work = outdir / f"work_{name}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    W, H = (W9, H9) if vertical else (W16, H16)
    all_cuts = [c for a in doc["acts"] for c in a["cuts"]]
    durs_all = cut_durations(doc, narration_dir)

    if cut_ids:
        keep = [(c, d) for c, d in zip(all_cuts, durs_all) if c["id"] in cut_ids]
    else:
        keep = list(zip(all_cuts, durs_all))
    if limit:
        keep = keep[:limit]

    # 쇼츠는 전용 마무리 문장이 화면에 들어가야 규격(35~50초)을 채운다.
    # 대본은 그 시간을 est_sec 에 이미 계산해 두었다.
    outro_cut = None
    if short and short.get("outro_line") and keep:
        outro_cut = make_outro_cut(keep[-1][0], short["outro_line"])
        keep = keep + [(outro_cut, outro_cut["sec"])]

    print(f"  {name}: 컷 {len(keep)}개 · {sum(d for _, d in keep):.1f}초 · {W}x{H}")
    segs = []
    intro = (short or {}).get("intro_line", "")
    for i, (cut, dur) in enumerate(keep):
        # 넘기다 걸린 사람은 아무것도 모른다. 첫 화면에 한 줄로 상황을 알려준다.
        segs.append(render_cut(cut, dur, work, i, W, H, vertical,
                               top_line=intro if (i == 0 and intro) else ""))
        if (i + 1) % 20 == 0:
            print(f"    {i + 1}/{len(keep)}컷")

    lst = work / "vlist.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in segs), encoding="utf-8")
    silent = work / "video.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(silent)])

    # 소리는 막별 음악을 깔아야 하므로 '고른 컷만 남긴 대본'을 다시 만들어 넘긴다.
    # 막 순서와 컷 순서가 keep 과 같아야 길이가 어긋나지 않는다.
    kept_ids = {id(c) for c, _ in keep}
    sub = {"acts": []}
    for act in doc["acts"]:
        picked = [c for c in act["cuts"] if id(c) in kept_ids]
        if picked:
            sub["acts"].append({**act, "cuts": picked})
    if outro_cut is not None and sub["acts"]:
        sub["acts"][-1]["cuts"] = sub["acts"][-1]["cuts"] + [outro_cut]
    audio = build_audio(sub, [d for _, d in keep], work, narration_dir)

    final = outdir / f"{name}.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(audio),
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)])
    shutil.rmtree(work, ignore_errors=True)
    print(f"  → {final.name}  {final.stat().st_size / 1e6:.1f}MB  {ffprobe_dur(final):.1f}초")
    return final


def shorts_doc(short):
    """쇼츠 대본 1편을 render() 가 먹을 수 있는 대본 모양으로 바꾼다.

    ⚠️ 여기가 **쇼츠가 규격보다 길어지던 원인**이었다.
    `shorts_gen.md` 는 세로 화면에 맞춰 컷을 다시 쓴다 — 대사를 짧게 줄이고
    ("어머니, 제가 받을 몫이 비잖아요. 법대로 하시죠." → "어머니, 법대로 하시죠.")
    인물도 한 명만 남기고 `sec` 도 다시 잡는다. 그런데 렌더러는 그 결과를 버리고
    `from` 이 가리키는 **본편 컷**을 그대로 세로로 그렸다.
    그래서 쇼츠 대본이 39초로 잡아도 실제 영상은 68초가 나왔다(규격 35~50초).

    컷 모양도 다르다 — 본편은 `chars`(여러 명 + pos), 쇼츠는 `char`(한 명 + pos_y).
    나레이션 파일 이름도 본편 컷 id 를 따르므로 `nar_id` 로 연결해 둔다.

    쇼츠 전용 음성이 아직 없으면 None 을 돌려준다. 그때는 본편 컷을 쓰는 옛 방식으로
    돌아간다 — 짧아진 자막에 긴 음성이 붙어 어긋나느니, 길어도 맞는 편이 낫다."""
    cuts = short.get("cuts") or []
    if not cuts or not any(c.get("from") for c in cuts):
        return None                      # 구간 지정만 있는 초안 — 다시 쓴 컷이 아니다

    out = []
    for i, c in enumerate(cuts):
        ch = c.get("char")
        n = {
            "id": c.get("id") or f"S{i:02d}",
            "nar_id": c.get("id") or c.get("from"),
            "sec": float(c.get("sec", 4.0)),
            "bg": c.get("bg", ""),
            "flashback": bool(c.get("flashback")),
            "chars": [ch] if isinstance(ch, dict) else (c.get("chars") or []),
            "speaker": c.get("speaker", "narrator"),
            "text": c.get("text", ""),
            "gfx": c.get("gfx"),
            "sfx": c.get("sfx"),
            "amb": c.get("amb", "amb_home"),
            "blackout": i == len(cuts) - 1,
        }
        out.append(n)
    return {"acts": [{"id": f"short{short.get('no')}", "bgm": short.get("bgm", "hook"),
                      "cuts": out}]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--out", default="build")
    ap.add_argument("--shorts", action="store_true", help="쇼츠 3편도 만든다")
    ap.add_argument("--limit", type=int, default=0, help="앞 N컷만 (시험용)")
    ap.add_argument("--narration", default="", help="TTS mp3 폴더 ({컷id}.mp3)")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        print("❌ ffmpeg 가 없다. GitHub Actions ubuntu 러너에는 기본 설치되어 있다.")
        return 2

    sp = Path(args.script)
    doc = json.loads(sp.read_text(encoding="utf-8"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    nar = args.narration or None

    print(f"렌더링: {sp.name}")
    render(doc, out, vertical=False, narration_dir=nar, limit=args.limit, name="longform")

    if args.shorts and args.limit:
        # --limit 은 "배관이 도는지 빨리 보자" 는 뜻이다. 그런데 쇼츠는 --limit 을 받지 않아
        # 3편(약 150초)을 통째로 만든다. 4컷짜리 시험에서 쇼츠가 몇 배 더 오래 걸린다.
        # 시험할 때는 건너뛴다 — 쇼츠는 어차피 같은 컷을 세로로 다시 그리는 것이다.
        print(f"  쇼츠는 건너뛴다 (--limit {args.limit} — 배관 시험 중)")
    elif args.shorts:
        # 쇼츠 구간은 두 곳에 있을 수 있다.
        #   1) shorts_gen.md 가 만든 별도 파일 — 세로 재배치까지 끝난 완성본
        #   2) script_gen.md 가 대본 안에 남긴 shorts[] — 구간 지정만 있는 초안
        # 1번이 없다고 쇼츠를 통째로 건너뛰면 안 된다. 2번으로도 만들 수 있다.
        shp = sp.parent / (sp.stem + ".shorts.json")
        if shp.exists():
            shorts = json.loads(shp.read_text(encoding="utf-8")).get("shorts", [])
            src = "쇼츠 대본"
        else:
            shorts = doc.get("shorts", [])
            src = "본 대본의 구간 지정 (쇼츠 대본이 없어 대신 씀)"
        if not shorts:
            print("  쇼츠 구간 정보가 어디에도 없다. 건너뛴다.")
        else:
            print(f"  쇼츠 {len(shorts)}편 — 출처: {src}")
            for s in shorts:
                sdoc = shorts_doc(s)
                if sdoc:
                    # 쇼츠 대본이 세로용으로 **다시 쓴 컷**을 그대로 쓴다.
                    render(sdoc, out, vertical=True, narration_dir=nar,
                           name=f"short{s.get('no')}", short=s)
                    continue
                ids = [c.get("from") or c.get("id") for c in s.get("cuts", [])] \
                    or s.get("cut_ids", [])
                if not ids:
                    print(f"  쇼츠 {s.get('no')}번: 가리키는 컷이 없다. 건너뛴다.")
                    continue
                render(doc, out, vertical=True, cut_ids=set(ids),
                       narration_dir=nar, name=f"short{s.get('no')}", short=s)

    if any(MISSING.values()):
        print("\n⚠️ 대체물을 쓴 에셋이 있다. 실제 발행 전에 반드시 만들어야 한다.")
        for k, v in MISSING.items():
            if v:
                sample = ", ".join(sorted(v)[:5])
                print(f"  {k}: {len(v)}종 — {sample}{' …' if len(v) > 5 else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
