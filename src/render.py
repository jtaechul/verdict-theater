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
import math
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import graphics as G  # noqa: E402
import timelabel as TL  # noqa: E402

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


# 표정이 비슷한 것끼리. 딱 맞는 포즈가 없을 때 **같은 화각의 다른 표정**으로 대신한다.
POSE_ALT = {
    "anger": ("cold", "shock", "neutral"),
    "cold": ("neutral", "anger"),
    "shock": ("anger", "neutral"),
    "sad": ("cry", "neutral"),
    "cry": ("sad", "neutral"),
    "neutral": ("cold", "sad"),
    "stand": ("walk",), "walk": ("stand",),
    "sit": ("sit_down", "stand"), "sit_down": ("sit",), "back": ("stand",),
}


# ⭐ **머리가 잘려 나간 그림은 쓰지 않는다.**
#    실측: assets/char/M50A/full_back.png 은 시트를 자를 때 목 위가 통째로 날아가
#    **머리 없는 양복 상반신**만 남아 있었다. 그런데도 렌더러는 아무 말 없이 그것을
#    화면에 세웠고, A2-09·A4-09 두 컷이 마네킹 같은 몸통으로 나갔다.
#    파일이 있으니 '있다' 고 판단한 것이 문제였다 — 있는 것과 쓸 만한 것은 다르다.
#
#    가리는 법: 머리 폭 ÷ 그림에서 가장 넓은 줄. 머리가 있으면 어깨가 훨씬 넓어
#    이 값이 작다(실측 full_·bust_ 24장 전부 0.66 이하). 머리가 없으면 맨 위가
#    곧 어깨라 1 에 가깝다(full_back 0.86).
#    얼굴 컷(face_)은 머리가 곧 가장 넓은 부분이라(0.95) 검사에서 뺀다.
HEADLESS_RATIO = 0.75
_headless = {}


def is_headless(path, pose):
    """머리가 잘려 나간 그림인가. 한 번만 재고 기억해 둔다."""
    if pose.split("_")[0] == "face":
        return False
    key = str(path)
    if key not in _headless:
        s = Image.open(path).convert("RGBA")
        widest = max(_row_widths(s)[0] or [1]) or 1
        _headless[key] = head_width(s, pose) / widest > HEADLESS_RATIO
    return _headless[key]


def char_path(code, pose):
    p = ASSETS / "char" / code / f"{pose}.png"
    if p.exists() and not is_headless(p, pose):
        return p
    if p.exists():
        MISSING["char"].add(f"{code}/{pose} — 머리가 잘린 그림이라 쓰지 않는다")

    # ⚠️ 없다고 곧바로 회색 실루엣으로 떨어뜨리지 않는다.
    #    시트를 만들 때 모델이 칸 하나를 덜 그리는 일이 있는데(실측: 12칸 중 11명),
    #    그 한 컷만 회색 그림자로 나오면 **같은 인물이 갑자기 실루엣이 된다.**
    #    같은 화각의 가까운 표정으로 대신하면 시청자는 눈치채지 못한다.
    kind, _, mood = pose.partition("_")
    for alt in POSE_ALT.get(mood, ()):
        q = ASSETS / "char" / code / f"{kind}_{alt}.png"
        if q.exists() and not is_headless(q, f"{kind}_{alt}"):
            MISSING["char"].add(f"{code}/{pose} → {kind}_{alt} 로 대신")
            return q
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

# ── 무대와 자막 띠 ───────────────────────────────────────
# ⭐ 화면을 둘로 나눈다.
#      **무대** — 배경과 인물이 사는 곳
#      **띠**   — 그 아래 검은 칸. 자막만 들어간다
#
#    왜 이렇게 바꾸나 (손님 제안)
#      예전에는 자막이 화면 위에 떠 있어서 얼굴을 덮었다. 그것을 피하려고
#      인물 크기와 자막 위치를 컷마다 계산하는 장치가 붙어 있었고,
#      그래도 136컷에서 자막이 얼굴을 가로질렀다.
#      띠를 두면 **그 문제가 통째로 사라진다.** 자막 자리가 고정이라 계산이 없다.
#      덤으로 인물의 잘린 아래 단면이 띠에 가려져 깔끔해진다.
#
#    세로 쇼츠는 무대를 **정방형**으로 만든다(손님 지정).
#    1080 폭이면 무대도 1080 높이 — 남는 아래 35%가 통째로 자막 띠가 된다.
# ⭐ 말하는 사람 강조 (손님 제안 5번)
#    "이야기하는 사람이 더 커진다" 는 아이디어를 **뒤집어** 넣는다.
#    말하는 사람을 키우면 인물이 이미 무대를 꽉 채우고 있어 어깨가 잘린다 —
#    손님이 세 번 하지 말라고 한 바로 그 일이다.
#    그래서 **듣는 사람을 줄이고 어둡게** 한다. 말하는 사람은 손대지 않는다.
#    결과는 같으면서(말하는 쪽이 앞으로 나와 보인다) 잘릴 위험이 0 이다.
LISTEN_SCALE = 0.88         # 듣는 사람 크기
LISTEN_DIM = 0.72           # 듣는 사람 밝기
BAND = 0.22                 # 가로 본편 — 아래 띠 높이(화면 대비)
TOP_STRIP_V = 0.09          # 세로 쇼츠 — 위쪽 띠(상단 문구 자리)


def stage_box(W, H, vertical):
    """배경·인물이 사는 영역 (위, 아래). 그 밖은 검은 띠."""
    if vertical:
        y0 = int(H * TOP_STRIP_V)
        return y0, min(H, y0 + W)          # 정방형 무대
    return 0, int(H * (1 - BAND))

# ⭐ 화면 아래 경계에 닿는 인물은 **경계에서 그냥 잘라낸다.**
#    예전에는 화면 아래에서 6% 띄우고 흰 테두리를 사방에 두른 채로 세웠다.
#    그러면 인물이 벽에 붙인 스티커처럼 떠 보인다 — 방송 화면은 그렇게 하지 않는다.
#    인물의 실제 아래끝을 화면 바닥에 딱 맞추면, 흰 테두리와 그림자는 화면 밖으로
#    밀려나 보이지 않고 인물은 화면에 심긴 것처럼 보인다.
#
#    ⚠️ 얼마나 내릴지는 **그림마다 재서 정한다.** 처음에 4.5% 로 어림잡았더니
#       흰 테두리가 화면 바닥에서 20픽셀 위에 그대로 남았다(실측).
#       그림마다 테두리·그림자가 차지하는 몫이 달라 고정값으로는 맞출 수 없다.
#    아래 10% 안에 들어오는 인물만 이렇게 처리한다. 화면 가운데 떠 있는 인물은
#    원래대로 테두리를 두른 채 둔다 — 거기서 자르면 잘린 티만 난다.
CHAR_BOTTOM_ZONE = 0.10
CHAR_OUTLINE = 0.030        # 흰 테두리 두께(인물 키 대비). assets_gen 의 2.8% + 여유


# ⭐ 인물 얼굴이 오는 자리 — 화면 높이의 몇 지점인가.
#    예전에는 인물을 화면 **바닥에 맞춰** 세웠다. 그러면 얼굴이 아래로 밀려서
#    자막이 입과 턱을 덮었다. 얼굴은 화면 한가운데쯤 와야 한다.
#    (자막이 아래 3분의 1을 쓰므로 정확히 0.5 보다 조금 위가 '가운데'로 보인다.)
HEAD_Y = 0.44               # 가로 화면
HEAD_Y_V = 0.34             # 세로 쇼츠 — 자막 덩어리가 더 크다
HEAD_MAX_UP = 1.35          # 아래가 비면 이만큼까지 키운다 (아래 설명 참조)


def head_center(sprite):
    """컷아웃에서 **얼굴 한가운데**가 위에서 몇 픽셀인지 잰다.

    실루엣의 줄별 폭을 재서 폭이 갑자기 넓어지는 곳(어깨선)을 찾는다.
    머리 꼭대기와 어깨선의 가운데가 얼굴 중심이다.
    얼굴만 있는 그림(face_*)은 어깨가 없으므로 그림의 한가운데가 된다.

    포즈 이름으로 어림잡지 않고 그림을 재는 이유: 같은 bust 라도 인물마다
    머리 크기와 어깨 폭이 달라 고정 비율로는 어긋난다."""
    a = sprite.getchannel("A").point(lambda v: 255 if v > 200 else 0)
    W, H = a.size
    px = a.load()
    step = max(1, W // 160)
    widths = []
    for y in range(H):
        xs = [x for x in range(0, W, step) if px[x, y]]
        widths.append((max(xs) - min(xs) + step) if xs else 0)
    solid = [y for y, w in enumerate(widths) if w > W * 0.04]
    if not solid:
        return H // 2
    top, bot = solid[0], solid[-1]
    n = max(4, int((bot - top) * 0.16))
    probe = [w for w in widths[top:top + n] if w]
    head_w = sorted(probe)[len(probe) // 2] if probe else W
    for y in range(top + n, bot + 1):
        if widths[y] > head_w * 1.55:
            return (top + y) // 2
    return (top + bot) // 2


def chin_y(sprite):
    """컷아웃에서 **턱 아래끝**이 위에서 몇 픽셀인지. 자막이 여기 위로 오면 안 된다."""
    a = sprite.getchannel("A").point(lambda v: 255 if v > 200 else 0)
    W, H = a.size
    px = a.load()
    step = max(1, W // 160)
    widths = []
    for y in range(H):
        xs = [x for x in range(0, W, step) if px[x, y]]
        widths.append((max(xs) - min(xs) + step) if xs else 0)
    solid = [y for y, w in enumerate(widths) if w > W * 0.04]
    if not solid:
        return H
    top, bot = solid[0], solid[-1]
    n = max(4, int((bot - top) * 0.16))
    probe = [w for w in widths[top:top + n] if w]
    head_w = sorted(probe)[len(probe) // 2] if probe else W
    for y in range(top + n, bot + 1):
        if widths[y] > head_w * 1.55:
            return y                      # 어깨가 시작되는 곳 = 턱 아래
    return bot                            # 얼굴만 있는 그림 — 그림 아래끝이 턱이다


# ⭐ 머리 크기를 재는 구간 — 그림 맨 위에서 이 비율만큼이 '머리' 다.
#    포즈 종류로 구간만 정하고, **크기는 실제로 잰다.**
#    (얼굴 컷은 머리가 화면을 거의 채우고, 전신은 머리가 위쪽 15% 안에 있다.)
HEAD_WINDOW = {"face": 0.34, "bust": 0.30, "full": 0.14}


def _row_widths(sprite):
    """실루엣의 줄별 가로 폭과 (맨 위, 맨 아래) 줄. 여러 곳에서 함께 쓴다."""
    a = sprite.getchannel("A").point(lambda v: 255 if v > 200 else 0)
    W, H = a.size
    px = a.load()
    step = max(1, W // 160)
    ws = []
    for y in range(H):
        xs = [x for x in range(0, W, step) if px[x, y]]
        ws.append((max(xs) - min(xs) + step) if xs else 0)
    solid = [y for y, w in enumerate(ws) if w > W * 0.04]
    return (ws, solid[0], solid[-1]) if solid else (ws, 0, H - 1)


def head_width(sprite, pose):
    """머리의 **가로 폭**(픽셀). 두 사람이 '같은 크기로 서 있다' 는 것은 결국
    머리 크기가 같다는 뜻이다.

    ⭐ 왜 '턱 위치' 가 아니라 '머리 폭' 인가 (실측으로 갈아탄 이유)
       예전에는 머리 높이(그림 위 ~ 턱)로 크기를 맞췄다. 그런데 턱을 찾는 방법이
       **줄 폭이 갑자기 넓어지는 곳** 이라서, 곱슬머리처럼 위가 넓게 퍼진 그림에서는
       이마를 턱으로 잘못 잡았다. 38장을 전부 그려 확인한 결과
         · 얼굴 컷 4장에서 이마에 선이 그였고
         · 전신 7장에서 정수리에 선이 그였으며
         · 상반신 8장은 아예 못 찾아 그림 맨 아래를 턱으로 삼았다
       그 잘못된 값으로 크기를 맞추니, 한 화면에서 어머니 머리가 아들 머리의
       **세 배**로 나왔다(A1-30). 폭은 그림 위쪽 구간에서 가장 넓은 줄 하나만
       고르면 되므로 훨씬 안전하다 — 38장 전부 머리 한가운데에 맞았다."""
    ws, top, bot = _row_widths(sprite)
    n = max(4, int((bot - top) * HEAD_WINDOW.get(pose.split("_")[0], 0.30)))
    return max(ws[top:top + n] or [1]) or 1


def top_pad(sprite):
    """그림 맨 위에서 **인물(흰 테두리 포함)이 시작되기까지** 비어 있는 픽셀.

    컷아웃 PNG 위쪽에는 옅은 그림자만 있는 투명한 띠가 있다. 이걸 인물의 키로
    잘못 세면, 화면 위가 남아도는데도 '더 키우면 머리가 잘린다' 고 판단해 버린다."""
    box = sprite.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
    return box[1] if box else 0


def bottom_bleed(sprite):
    """이 그림을 화면 바닥에 맞추려면 얼마나 더 내려야 하는지(픽셀).

    ① PNG 맨 아래에는 반투명한 그림자만 있는 띠가 있다 — 그만큼 내린다
    ② 그 위의 흰 테두리도 화면 밖으로 밀어낸다
    남는 것은 인물의 진짜 아래끝이고, 그것이 화면 바닥에 딱 걸린다."""
    box = sprite.getchannel("A").point(lambda v: 255 if v > 200 else 0).getbbox()
    solid_bottom = box[3] if box else sprite.height
    return (sprite.height - solid_bottom) + round(sprite.height * CHAR_OUTLINE) + 2


def ink_rect(sprite):
    """이 그림에서 **눈에 보이는 부분**의 네모 (x0, y0, x1, y1).

    흰 테두리까지 포함한다 — 두 인물의 테두리가 서로 닿기만 해도 겹쳐 보이기 때문이다.
    아주 옅은 그림자(알파 40 미만)는 뺀다. 그것까지 세면 그림 전체가 잡혀
    "언제나 겹친다" 가 되어 검사가 헛돈다."""
    box = sprite.getchannel("A").point(lambda v: 255 if v > 40 else 0).getbbox()
    return box or (0, 0, sprite.width, sprite.height)

# 확대 연출(zoompan)이 매 프레임 가장자리를 깎아내는 최대 비율.
# ZOOM_MAX 까지 확대되므로 각 변에서 (1 - 1/ZOOM_MAX)/2 만큼 사라진다.
ZOOM_START = 1.0            # 첫 프레임은 **자르지 않는다** (예전 1.02 는 시작부터 2% 손실)
ZOOM_MAX = 1.05
ZOOM_EDGE = (1 - 1 / ZOOM_MAX) / 2

PLACE_LOG = None            # 검수 스크립트가 [] 를 넣으면 인물 배치 결과를 여기 쌓는다


def _solve_char(c, cut, W, H, vertical, gfx_bottom, banded=False):
    """인물 한 명의 **크기**를 푼다. (자리는 build_plates 가 바닥에 붙인다)

    ⭐ 상반신·얼굴은 크기와 자리를 **함께** 풀어야 한다.
       따로 정하면 조건이 서로를 깨뜨린다 — 얼굴을 가운데 두면 아래가 안 닿고,
       아래를 닿게 하면 자막이 얼굴을 덮고, 키우면 머리가 화면 위로 나간다.
       (실측: 26장 중 9장이 화면 바닥에 닿지 않았다.)
       그래서 '인물의 진짜 아래끝을 화면 바닥에 붙인다' 를 고정해 놓고,
       나머지 세 조건을 **키의 상·하한**으로 바꿔 한 번에 만족시킨다."""
    ccode, pose = c.get("code", ""), c.get("pose", "")
    cp = char_path(ccode, pose)
    sprite = Image.open(cp).convert("RGBA") if cp else placeholder_char(ccode, pose, H)

    scale = float(c.get("scale", 1.0)) * (1.35 if vertical else 1.0)
    # ⭐ 띠가 있으면 무대가 짧아진 대신 **자막을 피할 필요가 없다.**
    #    예전 비율(0.72)을 그대로 쓰면 무대 위가 휑하게 빈다 — 더 채운다.
    target_h = int(H * (0.90 if banded else 0.72) * scale)
    room = H
    if gfx_bottom:
        # 카드 아래로 인물을 내린다. 정보 카드가 뜬 순간에는 카드가 주인공이고
        # 인물은 배경으로 물러나는 것이 맞다.
        room = H - int(H * 0.06) - (gfx_bottom + int(H * 0.03))
        target_h = max(int(H * 0.24), min(target_h, room))
    kind = pose.split("_")[0]
    edge = int(min(W, H) * ZOOM_EDGE) + 4          # 확대 연출이 깎아내는 몫 + 여유

    h0 = sprite.height
    f_pad = top_pad(sprite) / h0                   # 그림 위쪽의 빈 띠
    f_chin = chin_y(sprite) / h0
    cap = target_h

    if kind in ("bust", "face"):
        f_bleed = bottom_bleed(sprite) / h0        # 아래쪽 흰 테두리가 차지하는 몫
        body = max(0.05, 1.0 - f_bleed)            # 그림에서 '인물 아래끝' 까지의 비율
        # ⭐ 자막 띠가 있으면 자막이 무대 밖에 있다 — 얼굴을 덮을 수가 없다.
        #    그래서 '자막을 피할 최소 키' 라는 굴레가 통째로 사라진다.
        #    (이 굴레 때문에 인물이 필요 이상으로 커지고 컷마다 크기가 튀었다.)
        if banded:
            lo = 0.0
        else:
            sub_top = G.subtitle_top(cut.get("text", ""), W, H, vertical)
            m = int(H * 0.015)
            lo = (H - sub_top + m) / max(0.02, body - f_chin)
        # 머리가 화면 위로 안 나갈 최대 키.
        # ⚠️ 예전엔 `(H-edge)/body` 였다 — 위쪽 빈 띠를 인물 키로 세는 바람에
        #    화면 위가 100px 넘게 비어 있는데도 더 못 키우고, 그래서 자막이
        #    턱을 스쳤다(실측: 가로 1건). 빈 띠만큼 더 키울 수 있다.
        hi = (H - edge) / max(0.05, body - f_pad)
        # ⚠️ 좌우 상한에는 뒤의 CHAR_MAX_W 축소까지 **미리** 넣어야 한다.
        #    빼먹었더니 여기서 정한 키를 뒤에서 다시 줄여 262건 중 186건이
        #    바닥에서 떠 버렸다(실측). 나중에 줄일 값은 여기서 함께 풀어야 한다.
        room_w = min(W - 2 * edge, W * CHAR_MAX_W)
        wide = room_w * h0 / max(1, sprite.width)           # 좌우가 안 잘릴 최대 키
        cap = min(hi, wide)                                 # 더 키울 수 있는 한계
        target_h = int(max(lo, min(target_h, cap)) if lo <= cap else cap)

    # hw — 그림 높이 1픽셀당 머리 폭. 화면에 나올 머리 폭은 `키 × hw` 다.
    return {"code": ccode, "pose": pose, "sprite": sprite, "kind": kind,
            "edge": edge, "target_h": target_h, "cap": cap, "room": room,
            "hw": head_width(sprite, pose) / max(1, h0)}


# ── ⭐ 인물이 서로 겹치지 않게 하는 장치 ────────────────────
#
# 실제로 일어난 일 (손님이 화면을 캡처해 보내 확인)
#   대본 A1-03 이 아버지와 어머니를 **둘 다 `pos:"left"`** 로 적었다.
#   렌더러는 적힌 대로 두 사람을 같은 자리에 세웠고, 뒤에 선 아버지는
#   어머니 뒤로 완전히 사라진 채 **흰 테두리만 머리 둘레에 남았다.**
#   화면에는 '머리가 두 겹인 어머니' 가 나왔고, 이름표는 '김재복 · 아버지' 였다.
#   같은 실수가 A1-09 · A1-11 에도 있었다 (center+center, right+right).
#
# 고치는 방법은 두 겹이다.
#   1) **자리 배정** — 겹치는 pos 를 받으면 적힌 대로 세우지 않고 고르게 흩는다
#   2) **실측 후 재배치** — 자리가 달라도 그림이 넓으면 여전히 닿는다.
#      다 키운 뒤 보이는 폭을 재서, 겹치면 떼어 놓고 그래도 안 되면 함께 줄인다
# 대본이 틀려도 화면은 틀리지 않는다 — 검사기(validate_script)는 대본을 따로 잡는다.
SLOT_X = {"left": 0.27, "center": 0.5, "right": 0.73}
# 인원수별 기본 자리. 2명은 기존 left/right 와 **같은 값**이라, 제대로 적힌 대본은
# 배치가 한 픽셀도 바뀌지 않는다.
SLOT_SPREAD = {1: (0.5,), 2: (0.27, 0.73), 3: (0.17, 0.5, 0.83)}
CHAR_GAP = 0.030            # 두 인물 사이에 최소로 두는 틈 (화면 폭 대비)


def assign_slots(chars, vertical):
    """각 인물이 설 가로 자리(화면 폭 대비 비율)를 정한다.

    pos 가 서로 다르게 제대로 적혀 있으면 **그대로** 쓴다.
    하나라도 겹치거나 비어 있으면 적힌 좌→우 순서만 지킨 채 고르게 흩는다."""
    n = len(chars)
    if vertical or n <= 1:
        return [0.5] * n
    want = [c.get("pos") for c in chars]
    named = [w for w in want if w in SLOT_X]
    if len(named) == n and len(set(named)) == n:
        return [SLOT_X[w] for w in want]

    base = SLOT_SPREAD.get(n) or tuple(
        0.5 + (i - (n - 1) / 2) * (0.66 / max(1, n - 1)) for i in range(n))
    # 적힌 자리의 좌→오른 순서는 지킨다. 같은 자리끼리는 대본에 적힌 순서대로.
    rank = sorted(range(n), key=lambda i: (SLOT_X.get(want[i], 0.5), i))
    out = [0.5] * n
    for k, i in enumerate(rank):
        out[i] = base[k]
    return out


def solve_row(spans, W, edge, gap):
    """보이는 폭들(왼→오른 순)을 한 줄에 겹치지 않게 앉힌다.

    돌려주는 것 — (모두에게 곱할 축소 배율, [보이는 부분의 왼쪽 끝, …])
    다 합쳐도 자리가 모자라면 **다 같이** 줄인다. 한쪽만 줄이면 머리 크기가 어긋난다."""
    room = W - 2 * edge
    need = sum(spans) + gap * (len(spans) - 1)
    k = 1.0
    if need > room:
        k = max(0.35, (room - gap * (len(spans) - 1)) / max(1.0, sum(spans)))
        spans = [s * k for s in spans]
        need = sum(spans) + gap * (len(spans) - 1)
    x = edge + (room - need) / 2
    lefts = []
    for s in spans:
        lefts.append(x)
        x += s + gap
    return k, lefts


# ⭐ 이름표를 **그 사람 옆에** 붙이기 위한 배역 명단 (이름 → 인물 코드).
#    이름표에는 '김성훈' 이라고 이름만 적혀 있고, 컷에는 'M50B' 라고 코드만 있다.
#    둘을 잇는 다리가 없으면 이름표가 누구 것인지 렌더러가 알 수 없어서,
#    늘 화면 왼쪽에 붙였다 — 그래서 **오른쪽에 선 차남의 이름표가 왼쪽 어머니 옆에**
#    붙는 일이 생겼다(손님 화면 캡처). main() 이 대본을 읽을 때 채워 둔다.
CAST = {}


def set_cast(doc):
    """대본의 배역 명단으로 '이름 → 코드' 다리를 놓는다."""
    CAST.clear()
    for ch in (doc.get("characters") or []):
        nm = str(ch.get("nametag") or ch.get("name") or "").split("·")[0].strip()
        if nm and ch.get("code"):
            CAST[nm] = ch["code"]
    return CAST


def fix_time_labels(doc):
    """회상 시점 자막이 **그림과 어긋나면** 안전한 말로 바꾼다.

    2026-08-09 손님 지적: 화면 위에는 '아버지 생전' 인데 인물은 지금 나이 그대로였다.
    젊은 시절 그림이 없으므로 시대를 못 박는 자막은 쓸 수 없다
    (규칙은 `src/timelabel.py` 한곳에 모아 뒀다).

    ⚠️ 대본 검사에서 걸러도 여기서 **한 번 더** 본다. 사람이 손으로 고친 대본이나
       규칙이 생기기 전에 만들어 둔 옛 대본이 검사를 거치지 않고 화면까지 갈 수 있다."""
    changed = []
    for a in doc.get("acts", []) or []:
        for c in a.get("cuts", []) or []:
            old = (c.get("flashback_label") or "").strip()
            if not old:
                continue
            new = TL.safe_label(c, doc)
            if new != old:
                c["flashback_label"] = new
                changed.append((c.get("id"), old, new))
    for cid, old, new in changed:
        print(f"  시점 자막 고침 {cid}: '{old}' → '{new}'"
              f"  (그림이 그 나이가 아니다)")
    return changed


def tag_owner(spec, chars):
    """이름표가 가리키는 인물의 코드. 알 수 없으면 None."""
    if not spec or spec.get("type") != "nametag":
        return None
    on = [c.get("code") for c in chars]
    code = CAST.get(str(spec.get("text", "")).split("·")[0].strip())
    if code and code in on:
        return code
    return on[0] if len(on) == 1 else None


def decollide(placed, W, gap, reseat):
    """다 키워 놓은 인물들이 **실제로 겹치는지 재서** 겹치면 떼어 놓는다.

    자리(pos)를 서로 다르게 줘도 그림이 넓으면 여전히 닿는다 — 흰 테두리끼리
    스치기만 해도 화면에서는 한 덩어리로 보인다. 그래서 마지막에 한 번 더 잰다.
    떼어 놓을 자리가 모자라면 **다 같이** 줄인다(한쪽만 줄이면 머리 크기가 어긋난다)."""
    if len(placed) < 2:
        return
    for q in placed:
        r = ink_rect(q["sprite"])
        q["_vis"] = (q["x"] + r[0], q["x"] + r[2])
    seq = sorted(placed, key=lambda q: q["_vis"][0])
    if all(seq[k]["_vis"][1] + gap <= seq[k + 1]["_vis"][0] for k in range(len(seq) - 1)):
        return                                  # 이미 안 겹친다 — 한 픽셀도 손대지 않는다

    edge = max(q["edge"] for q in placed)
    k, lefts = solve_row([q["_vis"][1] - q["_vis"][0] for q in seq], W, edge, gap)
    for q, left in zip(seq, lefts):
        if k < 0.999:
            s = q["sprite"]
            q["sprite"] = s.resize((max(1, round(s.width * k)),
                                    max(1, round(s.height * k))), Image.LANCZOS)
            q["y"] = reseat(q["sprite"], q["kind"])
        q["x"] = int(round(left - ink_rect(q["sprite"])[0]))
    for q in placed:
        q.pop("_vis", None)


def nametag_align(spec, chars, placed, W, H, bottom=None):
    """이름표를 화면 **왼쪽·오른쪽 중 어디**에 붙일지 정한다.

    두 가지를 재서 고른다.
      1) 그 자리에 두면 **다른 인물을 가리는가** (많이 가리는 쪽은 탈락)
      2) 같으면 **이름표 주인에게 더 가까운 쪽**

    주인 본인을 조금 덮는 것은 상관없다 — 자기 이름표다. 남을 덮으면 그 사람 이름으로
    읽힌다. 실제로 그래서 차남의 이름표가 어머니 이름표로 보였다."""
    owner = tag_owner(spec, chars)
    if owner is None or not placed:
        return "left"
    tw, th = G.nametag_size(spec.get("text", ""), W, H)
    base = bottom if bottom else round(H * (0.50 if H > W else 0.655))
    top = base - th
    m = round(W * G.NAMETAG_MARGIN)

    who = next((q for q in placed if q["code"] == owner), None)
    others = [q for q in placed if q is not who]

    def score(x0):
        x1 = x0 + tw
        hide = sum(max(0, min(x1, o["rect"][2]) - max(x0, o["rect"][0]))
                   for o in others if o["rect"][3] > top and o["rect"][1] < base)
        near = (abs((x0 + x1) / 2 - (who["rect"][0] + who["rect"][2]) / 2)
                if who else 0)
        return hide, near

    left, right = score(m), score(max(m, W - m - tw))
    # ⚠️ **왼쪽이 기본이다.** 컷마다 이름표가 좌우로 옮겨 다니면 시청자가 눈으로
    #    찾아야 한다 — 방송 자막은 늘 같은 자리에 있어야 읽힌다.
    #    그래서 오른쪽으로는 '확실히 나을 때만' 옮긴다. 화면 한 명뿐인 컷처럼
    #    좌우가 비슷하면 왼쪽에 그대로 둔다.
    if right[0] < left[0] or (right[0] == left[0] and right[1] < left[1] - W * 0.10):
        return "right"
    return "left"


def pick_one(cut, chars):
    """세로 쇼츠는 한 명만 세운다 — **누구를 남길지** 고른다.

    ⚠️ 예전에는 무조건 첫 번째(chars[0])를 남겼다. 그래서 이름표가 두 번째 인물을
       가리키는 컷에서는 **이름표에 적힌 사람이 화면에서 사라진 채** 엉뚱한 사람 옆에
       이름이 붙었다(A4-01: 화면엔 장남, 이름표는 '재판장').
    ① 이름표에 적힌 사람  ② 말하는 사람  ③ 그래도 없으면 첫 번째"""
    want = tag_owner(cut.get("gfx"), chars)
    if not want:
        sp = cut.get("speaker") or "narrator"
        if sp not in ("narrator", ""):
            want = sp[2:] if sp.startswith("v_") else sp
    for c in chars:
        if c.get("code") == want:
            return [c]
    return chars[:1]


def _stage_plates(cut, W, H, vertical=False, top_line="", banded=False):
    """**무대 한 판**을 그린다. banded 면 자막은 그리지 않는다(띠가 맡는다)."""
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
        chars = pick_one(cut, chars)            # 세로는 한 명만. 두 명이면 화면이 죽는다
    head_top, face_bottom = H, 0                # 실제로 앉힌 인물의 위·아래 얼굴선

    # ⭐ 같은 컷에 선 사람들은 **머리 크기가 같아야** 한다.
    #    아래에서 '자막을 피할 최소 키(lo)' 로 크기를 정하는데, 그 값은 그림마다
    #    가슴이 얼마나 담겼느냐에 따라 크게 달라진다. 그대로 두면 한 화면에서
    #    한 사람은 크고 한 사람은 절반만 하게 나온다(실측: 판사 옆 김성일).
    #    그래서 먼저 각자 풀고, **가장 큰 머리에 나머지를 맞춘다.**
    plan = [_solve_char(c, cut, W, H, vertical, gfx_bottom, banded) for c in chars]
    fit = [p for p in plan if p["hw"] > 0]
    if len(fit) > 1:
        # 각자 '뜻한 머리 폭' 과 '낼 수 있는 가장 큰 머리 폭'
        want_px = [p["target_h"] * p["hw"] for p in fit]
        cap_px = [p["cap"] * p["hw"] for p in fit]
        # ⭐ 모두가 낼 수 있는 가장 큰 머리에 맞춘다. 그 값을 '원래 뜻한 범위' 안으로
        #    한 번 더 눌러, 아무도 필요 이상으로 커지거나 작아지지 않게 한다.
        want = max(min(want_px), min(min(cap_px), max(want_px)))
        for p in fit:
            new = min(p["cap"], want / p["hw"])
            # ⚠️ **줄이는 것은 자막 띠가 있을 때만** 한다. 띠가 없으면 자막이 화면 위에
            #    떠 있어서, 인물을 줄이면 자막이 얼굴을 덮는다.
            #    (지금 본편·쇼츠 둘 다 띠를 쓰므로 사실상 늘 줄일 수 있다.)
            p["target_h"] = int(new if banded else max(p["target_h"], new))

    # ⭐ 말하는 사람과 듣는 사람을 가른다.
    #    듣는 사람을 **먼저** 그려 뒤로 보내고, 조금 줄이고 어둡게 한다.
    sp = cut.get("speaker") or "narrator"
    talker = sp[2:] if sp.startswith("v_") else (sp if sp != "narrator" else None)
    on = [x.get("code") for x in chars]
    solo = (talker in on) and len(chars) > 1        # 화면에 말하는 사람이 있고 둘 이상일 때만
    order = sorted(range(len(chars)),
                   key=lambda i: chars[i].get("code") == talker)   # 듣는 사람 먼저

    # ⭐ 자리는 대본이 적은 대로 쓰되, **겹치면 흩는다** (assign_slots 설명 참조).
    slots = assign_slots(chars, vertical)

    def seat(sprite, kind, avoid_gfx=False):
        """이 그림을 무대에 앉힐 y. 아래끝을 바닥에 붙이는 것이 원칙이다."""
        if kind == "full":
            # 전신은 발이 화면 바닥에 닿아야 한다. 얼굴을 가운데로 끌어올리면 다리가 잘린다.
            y = H - sprite.height - int(H * 0.06)
            if y + sprite.height >= H - int(H * CHAR_BOTTOM_ZONE):
                y = H - sprite.height + bottom_bleed(sprite)
        else:
            # 인물의 진짜 아래끝(흰 테두리 제외)을 화면 바닥에 붙인다
            y = H - sprite.height + bottom_bleed(sprite)
        # 세로에서는 위쪽 정보 카드를 피해야 한다
        if avoid_gfx and vertical and gfx_bottom and y < gfx_bottom + int(H * 0.035):
            y = gfx_bottom + int(H * 0.035)
        return y

    # ── ① 각자 크기와 자리를 푼다. 아직 그리지 않는다 ──────────
    #    ⚠️ 예전에는 여기서 곧바로 그렸다. 그래서 두 사람이 겹쳐도 알 방법이 없었다 —
    #       먼저 그린 사람은 이미 배경에 박혀 있었기 때문이다.
    #       다 풀어 놓고 재 본 뒤에 그려야 겹침을 고칠 수 있다.
    placed = []
    for i, c in enumerate(chars):
        p = plan[i]
        ccode, pose, sprite = p["code"], p["pose"], p["sprite"]
        target_h, kind = p["target_h"], p["kind"]
        listening = solo and ccode != talker
        if listening:
            target_h = max(1, int(target_h * LISTEN_SCALE))

        ratio = target_h / sprite.height
        sw = max(1, int(sprite.width * ratio))
        # 가로로도 화면을 넘지 않게 한 번 더 줄인다.
        # 세로 쇼츠(1080폭)에서 인물을 1.35배로 키우므로, 옆으로 넓은 컷아웃은
        # 그냥 두면 좌우가 잘려 나간다. 높이만 맞추면 안 된다.
        if sw > W * CHAR_MAX_W:
            k = (W * CHAR_MAX_W) / sw
            sw, target_h = max(1, int(sw * k)), max(1, int(target_h * k))
        sprite = sprite.resize((sw, target_h), Image.LANCZOS)

        edge = int(min(W, H) * ZOOM_EDGE) + 4      # 확대 연출이 깎아내는 몫 + 여유

        x = ((W - sprite.width) // 2 if vertical
             else int(W * slots[i]) - sprite.width // 2)
        y = seat(sprite, kind, avoid_gfx=True)

        # ⭐ 머리 위와 좌우는 **절대 자르지 않는다.**
        #    ⚠️ 예전 가로 배치는 `edge - sprite.width // 4` 로 클램프해서
        #       인물 폭의 4분의 1까지 화면 밖으로 나가는 것을 **허용**하고 있었다.
        #       그래서 좌우에 세운 인물의 어깨와 팔이 잘려 나갔다.
        #    넓거나 높아서 안 들어가면 자르지 않고 **줄여서** 넣는다.
        #    ⚠️ 높이 상한은 위쪽 **빈 띠**를 빼고 재야 한다. 그냥 `H - edge` 로 재면
        #       위가 남아도는데도 줄여 버려서, 방금 푼 크기를 여기서 다시 깎는다.
        #       (실측: 그 바람에 가로 1건에서 자막이 턱을 9px 덮었다.)
        room_w = W - 2 * edge
        vis_h = sprite.height - top_pad(sprite) - bottom_bleed(sprite)   # 화면에 들어가야 할 몫
        room_h = (H - edge) * sprite.height / max(1, vis_h)
        if sprite.width > room_w or (kind != "full" and sprite.height > room_h):
            k = min(room_w / sprite.width,
                    room_h / sprite.height if kind != "full" else 1.0)
            sprite = sprite.resize((max(1, round(sprite.width * k)),
                                    max(1, round(sprite.height * k))), Image.LANCZOS)
            y = seat(sprite, kind)
            x = (W - sprite.width) // 2 if vertical else x

        # 안전망 — 전신은 자막이 얼굴을 덮으면 위로 올린다.
        # ⚠️ 상반신·얼굴에는 쓰지 않는다. 위로 올리면 아래끝이 바닥에서 떠 버리는데,
        #    "전신이 아닌 이상 아래끝은 화면 바닥에 닿아야 한다" 가 더 우선이다.
        #    (얼굴이 자막에 덮이지 않는 것은 이미 위에서 최소 키 `lo` 로 풀었다.)
        if kind == "full":
            sub_top = G.subtitle_top(cut.get("text", ""), W, H, vertical)
            over = (y + chin_y(sprite)) - (sub_top - int(H * 0.015))
            if over > 0 and y - over >= edge:
                y -= over

        x = min(max(x, edge), max(edge, W - sprite.width - edge))
        y = max(y, edge)                            # 머리 위가 잘리지 않게

        # ⭐ 마지막으로 한 번 더 바닥에 붙인다. 위 클램프들이 인물을 들어 올렸을 수 있다.
        if kind != "full":
            y = max(edge, H - sprite.height + bottom_bleed(sprite))

        placed.append(dict(code=ccode, pose=pose, sprite=sprite, kind=kind,
                           edge=edge, x=x, y=y, listening=listening))

    # ── ② 서로 겹치면 떼어 놓는다 ────────────────────────────
    decollide(placed, W, round(W * CHAR_GAP), lambda s, k: seat(s, k))
    for q in placed:                                # 눈에 보이는 네모(이름표 자리 계산용)
        r = ink_rect(q["sprite"])
        q["rect"] = (q["x"] + r[0], q["y"] + r[1], q["x"] + r[2], q["y"] + r[3])

    # ── ③ 그린다. 듣는 사람을 먼저 그려 뒤로 보낸다 ────────────
    for i in order:
        q = placed[i]
        sprite, x, y = q["sprite"], q["x"], q["y"]

        # 화면 밖으로 나가는 부분은 여기서 잘라낸다.
        # alpha_composite 는 대상 밖으로 나가는 그림을 받지 않으므로 미리 맞춰 준다.
        if PLACE_LOG is not None:                   # 검수용 — 평소에는 None 이라 비용 0
            # ⚠️ 여기 W·H 는 **무대 캔버스** 크기다(자막 띠를 뺀 높이).
            #    검수 스크립트는 반드시 이 H 로 재야 한다. 화면 전체 높이로 재면
            #    띠 높이(238px)만큼 "인물이 떠 있다" 는 헛경보가 컷마다 나온다.
            PLACE_LOG.append(dict(
                code=q["code"], pose=q["pose"], W=W, H=H, x=x, y=y,
                w=sprite.width, h=sprite.height,
                bleed=bottom_bleed(sprite), edge=q["edge"],
                chin=chin_y(sprite), banded=banded, rect=q["rect"],
                head=head_width(sprite, q["pose"]),   # 화면에 나온 머리 폭
                listening=q["listening"],
                # 띠가 있으면 자막이 무대 밖이라 얼굴을 덮을 수가 없다.
                sub_top=(None if banded else
                         G.subtitle_top(cut.get("text", ""), W, H, vertical))))

        if q["listening"]:
            # 밝기만 낮춘다. 알파는 그대로 둬야 흰 테두리가 반투명해지지 않는다.
            rgb = ImageEnhance.Brightness(sprite.convert("RGB")).enhance(LISTEN_DIM)
            dim = rgb.convert("RGBA")
            dim.putalpha(sprite.getchannel("A"))
            sprite = dim

        sx, sy = max(0, x), max(0, y)
        cx0, cy0 = sx - x, sy - y
        cx1 = min(sprite.width, cx0 + (W - sx))
        cy1 = min(sprite.height, cy0 + (H - sy))
        if cx1 > cx0 and cy1 > cy0:
            move.alpha_composite(sprite.crop((cx0, cy0, cx1, cy1)), (sx, sy))

        head_top = min(head_top, y)
        face_bottom = max(face_bottom, y + chin_y(sprite))

    # ⭐ 이름표를 **그 사람 쪽**에 다시 그린다.
    #    맨 위에서 그릴 때는 인물을 아직 안 앉혀서 누가 어디 섰는지 알 수 없었다.
    #    이제 실제 배치를 알므로, 남을 가리지 않으면서 주인에게 가까운 쪽을 고른다.
    spec = cut.get("gfx") or {}
    nt_align = "left"
    if spec.get("type") == "nametag" and placed:
        nt_align = nametag_align(spec, chars, placed, W, H)
        if nt_align != "left":
            moved = G.render_gfx({**spec, "_align": nt_align}, W, H)
            if moved is not None:
                gfx = moved

    # 그래픽과 자막을 **따로** 돌려준다.
    # 둘을 한 장으로 합치면 함께 움직일 수밖에 없는데, 자막은 절대 움직이면 안 되고
    # (읽는 중에 흔들리면 놓친다) 카드는 나타날 때 살짝 움직여야 생기가 산다.
    gfx_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if gfx:
        gfx_layer = Image.alpha_composite(gfx_layer, gfx)
    if top_line:
        gfx_layer = G.draw_top_line(gfx_layer, top_line)

    # ⭐ 세로 쇼츠에서만: 자막이 얼굴을 가로지르면 자막을 **머리 위**로 올린다.
    #    세로 화면(1080 폭)에서는 인물 폭이 화면 폭에 막혀 키가 화면의 45% 밖에 안 된다.
    #    그 인물을 바닥에 붙이면 얼굴이 화면 아래 절반에 오는데, 쇼츠는 유튜브 UI 때문에
    #    자막을 바닥에서 20% 띄워야 해서 자막이 딱 얼굴 위를 지난다.
    #    좌우를 자르는 것도, 인물을 띄우는 것도 금지이므로 **자막이 비켜난다.**
    #    (가로 본편은 인물이 크게 들어가므로 이 일이 생기지 않는다 — 실측 0건)
    sub_top_over = None
    text = cut.get("text", "")
    # ⭐ 쌓는 순서는 **위에서부터 자막 → 이름표 → 인물**이다.
    #    이름표는 그 인물이 누구인지 알려주는 딱지다. 딱지는 붙일 대상 옆에 있어야
    #    한다 — 인물에서 멀면 누구 이름인지 헷갈린다.
    #    자막은 읽는 글이라 인물과 떨어져도 상관없다. 그래서 자막이 위로 간다.
    name_h = (G.nametag_block(spec.get("text", ""), W, H)
              if vertical and spec.get("type") == "nametag" else 0)
    if (not banded) and vertical and text and face_bottom > G.subtitle_top(text, W, H, True):
        block = G.subtitle_block(text, W, H, True)
        floor_ = (gfx_bottom + int(H * 0.03)) if gfx_bottom else int(H * 0.06)
        # ⚠️ 위쪽 한 줄(쇼츠 상단 문구)도 바닥선에 넣는다.
        #    안 넣었더니 자막이 위로 올라가다 상단 문구를 덮었다(실측 6컷).
        if top_line:
            tb = G.draw_top_line(Image.new("RGBA", (W, H), (0, 0, 0, 0)),
                                 top_line).getbbox()
            if tb:
                floor_ = max(floor_, tb[3] + int(H * 0.030))
        # 자막 그늘은 글자 위로 더 번진다. 그만큼도 바닥선에서 띄운다.
        floor_ += int(G.fit_subtitle(text, W, H, True)[1] * 1.1)
        # 이름표가 들어갈 자리를 **미리 비워 두고** 자막은 그 위로 올린다.
        reserve = (name_h + int(H * 0.045)) if name_h else 0
        want = max(floor_, head_top - block - reserve - int(H * 0.035))
        if want + block <= face_bottom - int(H * 0.02):
            sub_top_over = want

    if PLACE_LOG is not None:
        for r in PLACE_LOG:
            r.setdefault("sub_moved", sub_top_over)

    sub_layer = (Image.new("RGBA", (W, H), (0, 0, 0, 0)) if banded
                 else G.draw_subtitle(Image.new("RGBA", (W, H), (0, 0, 0, 0)),
                                      text, vertical=vertical, top=sub_top_over,
                                      speaker=cut.get("speaker")))

    # ⭐ 이름표를 **인물 머리 바로 위**로 내린다 (자막과 인물 사이).
    #    기본 자리(세로 화면 높이의 50%)에 두면 올라온 자막과 정면으로 겹쳐
    #    '김성일 · 50세 · 장남' 이 통째로 가려졌다(손님 화면 캡처로 확인).
    #
    # ⚠️ 자막의 '차지 영역' 은 글자만이 아니다. 뒤에 깔리는 **그늘 띠**가 글자보다
    #    위아래로 더 넓다. 그래서 좌표를 계산하지 않고 **다 그린 자막을 직접 재서**
    #    그 아래에 놓는다. 계산으로 짐작했다가 6컷이 그대로 겹쳤다.
    if sub_top_over is not None and spec.get("type") == "nametag":
        sb = sub_layer.getbbox()
        if sb:
            need = name_h
            want = head_top - int(H * 0.018)                 # 인물 머리 바로 위
            if want - need < sb[3] + int(H * 0.012):         # 자막 그늘과 닿으면
                want = sb[3] + int(H * 0.012) + need         #   그늘 바로 아래로
            if want - need >= int(H * 0.04) and want <= H:
                # 옮긴 뒤에도 **어느 쪽에 붙일지**는 다시 잰다 — 높이가 달라지면
                # 옆 사람과 겹치는 범위도 달라진다.
                moved = G.render_gfx(
                    {**spec, "_bottom": int(want),
                     "_align": nametag_align(spec, chars, placed, W, H, bottom=int(want))},
                    W, H)
                if moved is not None:
                    gfx_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                    gfx_layer = Image.alpha_composite(gfx_layer, moved)
                    if top_line:
                        gfx_layer = G.draw_top_line(gfx_layer, top_line)

    # 회상으로 들어가는 컷에는 **언제인지**를 화면 가운데 잠깐 띄운다.
    # 색만 세피아로 바뀌면 어르신 시청자는 '화면이 이상해졌다' 로 본다.
    # 대본이 flashback_label 을 채워야 나온다(없으면 조용히 건너뛴다).
    when = (cut.get("flashback_label") or "").strip()
    if when and cut.get("flashback"):
        # ⚠️ 자막이 위로 올라온 컷에서는 시점 자막 기본 자리(H의 30%)와 겹친다.
        #    실측: A1-01 에서 '정임 씨는 40년을…' 이 시점 자막을 덮었다.
        #    그럴 때는 시점 자막을 **자막 그늘 위**로 올린다.
        cy = None
        if sub_top_over is not None:
            sb = sub_layer.getbbox()
            if sb:
                cy = max(int(H * 0.09), sb[1] - int(H * 0.055))
        # 인물 머리 꼭대기 — 시점 자막이 이 아래로 내려오면 얼굴을 가로지른다.
        ink_top = min((q["rect"][1] for q in placed), default=None)
        gfx_layer = G.draw_time_caption(
            gfx_layer, when, cy=cy,
            avoid=None if ink_top is None else ink_top - int(H * 0.012))

    return move, gfx_layer, sub_layer


def build_plates(cut, W, H, vertical=False, top_line=""):
    """한 컷의 세 겹을 만든다 — 움직이는 겹(배경+인물) · 고정된 겹(그래픽) · 자막.

    ⭐ 무대와 자막 띠를 나눈다(stage_box 참고).
       무대는 **자기 크기의 캔버스**에 그대로 그린 뒤 통째로 붙인다.
       그래야 '아래끝을 바닥에 붙인다', '좌우·머리 위를 자르지 않는다',
       '같은 컷의 머리 크기를 맞춘다' 같은 규칙을 하나도 안 고치고 그대로 쓴다.

    ⚠️ 검은 띠는 **고정된 겹**에 그린다. 움직이는 겹에 그리면 확대 연출(zoompan)에
       같이 확대돼 띠가 흔들리고, 무대 내용이 띠 위로 삐져나온다."""
    y0, y1 = stage_box(W, H, vertical)
    if (y0, y1) == (0, H):
        return _stage_plates(cut, W, H, vertical, top_line)        # 띠 없음(예전 방식)

    sh = y1 - y0
    s_move, s_gfx, _ = _stage_plates(cut, W, sh, vertical, top_line="", banded=True)

    move = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    move.paste(s_move.convert("RGBA"), (0, y0))

    gfx = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gfx.paste(s_gfx, (0, y0))
    # 띠를 덮는다. 확대 연출이 무대를 넘치게 해도 여기서 잘린다.
    bar = ImageDraw.Draw(gfx)
    if y0 > 0:
        bar.rectangle((0, 0, W, y0 - 1), fill=(0, 0, 0, 255))
    if y1 < H:
        bar.rectangle((0, y1, W, H), fill=(0, 0, 0, 255))
    # 무대와 띠 사이는 **선을 긋지 않는다.**
    # 붉은 줄을 그어 봤더니 촌스러웠다(손님 지적). 대신 무대 아래쪽을 짧게
    # 어둡게 죽여 띠로 자연스럽게 이어지게 한다 — 경계가 눈에 안 띈다.
    hem = max(6, round(H * 0.030))
    grad = Image.new("L", (1, hem))
    gp = grad.load()
    for i in range(hem):
        gp[0, i] = round(255 * (i / max(1, hem - 1)) ** 1.6)
    hemlay = Image.new("RGBA", (W, hem), (0, 0, 0, 255))
    hemlay.putalpha(grad.resize((W, hem), Image.BILINEAR))
    gfx.alpha_composite(hemlay, (0, max(0, y1 - hem)))
    if top_line:
        gfx = G.draw_top_line(gfx, top_line, box=(0, 0, W, y0))

    sub = G.draw_subtitle(Image.new("RGBA", (W, H), (0, 0, 0, 0)),
                          cut.get("text", ""), vertical=vertical,
                          speaker=cut.get("speaker"), band=(y1, H))
    return move, gfx, sub


# ── 컷 하나를 영상 조각으로 ──────────────────────────────
# ── 화면 전환 ────────────────────────────────────────────
# 예전에는 113개 컷 경계가 **전부 하드컷**이었다. 배경이 42번 바뀌고 회상을 8번
# 드나드는데 바뀌는 순간이 없어서, 어르신 시청자는 그냥 화면이 이상해진 것으로 본다.
# 대본은 막 끝마다 `blackout` 표시를 남겨 두었는데 렌더러가 **읽지도 않고 있었다.**
#
# 값이 거의 안 드는 방식(암전·플래시)만 쓴다. 진짜 크로스 디졸브는 두 장면을 겹쳐
# 다시 인코딩해야 해서 렌더링이 1.5~2배로 늘어난다 — 얻는 것에 비해 너무 비싸다.
# ⚠️ 손님 요청으로 **전부 길게** 잡았다("조금 더 전환 효과가 있었으면").
#    예전 값은 절반이라 눈에 잘 안 띄었다 — 특히 배경 교체(0.18초)는
#    깜빡임 수준이라 장면이 바뀐 줄 모르고 지나갔다.
#    다만 무한정 늘리면 12분에서 전환에만 40초 넘게 쓴다. 아래가 상한이다.
ACT_OUT = 0.80      # 막이 끝날 때 검게 잠긴다
ACT_IN = 0.70       # 다음 막이 검은 화면에서 열린다
FLASH_IN = 0.60     # 회상으로 들어갈 때 — 흰 빛에서 열린다
FLASH_OUT = 0.50    # 현재로 돌아올 때 — 흰 빛에서 짧게
SCENE_DIP = 0.28    # 배경이 바뀔 때 — 짧게 어두웠다 열린다


def transitions(cuts):
    """컷마다 시작·끝에 걸 전환을 정한다. (들어올 때, 나갈 때)

    우선순위가 있다 — 한 경계에 여러 조건이 겹치면 **큰 것 하나만** 쓴다.
    막 전환 > 회상 드나듦 > 배경 교체. 겹쳐 걸면 화면이 정신없어진다."""
    out = []
    prev_fb = prev_bg = None
    prev_black = False
    for c in cuts:
        fb, bg = bool(c.get("flashback")), c.get("bg")
        t_in = None
        if prev_black:
            t_in = ("black", ACT_IN)
        elif prev_fb is not None and fb != prev_fb:
            t_in = ("white", FLASH_IN if fb else FLASH_OUT)
        elif prev_bg is not None and bg != prev_bg:
            t_in = ("black", SCENE_DIP)
        out.append((t_in, ("black", ACT_OUT) if c.get("blackout") else None))
        prev_fb, prev_bg, prev_black = fb, bg, bool(c.get("blackout"))
    return out


def drop_repeat_nametags(keep):
    """**직전에 소개한 사람과 같으면 이름표를 다시 띄우지 않는다.**

    ⭐ 손님 지적: "말할 때마다 장남을 소개하고, 다음 컷도 장남인데 또 이름표에
                   이펙트를 준다. 직전에 나온 사람과 같으면 넣을 필요가 없다."
       맞는 말이다. 이름표는 **누구인지 알려주는 소개**다. 방금 소개한 사람을
       바로 또 소개하면 정보가 아니라 방해다. 게다가 이름표는 왼쪽에서 미끄러져
       들어오는 연출이 붙어 있어, 같은 사람에게 연달아 붙으면 계속 덜컹거린다.

    언제 다시 띄우나
      · 사이에 **다른 사람**이 소개되었을 때만. 그때는 헷갈리므로 다시 알려준다.
      ⚠️ 배경이 바뀌어도 다시 띄우지 않는다. 쇼츠는 컷마다 배경이 바뀌는데
         (실측: 쇼츠 10컷이 배경 8종) 배경으로 판단하면 장남 → 장남이 그대로
         두 번 다 뜬다. 손님이 지적한 것이 정확히 그 경우다.
    """
    out, last, n = [], None, 0
    for cut, dur in keep:
        g = cut.get("gfx") or {}
        who = (str(g.get("text", "")).split("·")[0].strip()
               if g.get("type") == "nametag" else None)
        if who and who == last:
            cut = {**cut, "gfx": None}
            n += 1
        elif who:
            last = who
        out.append((cut, dur))
    return out, n


# 등장 연출 시간(초). 짧게 — 길면 정보를 읽기 시작하는 시점이 늦어진다.
GFX_IN = 0.38
SUB_IN = 0.16

_LOGO_PNG = {}


def logo_png(workdir, W, H, vertical, blank=False):
    """채널 로고 겹을 **한 번만** 그려 파일로 두고, 모든 컷이 그 파일을 쓴다.

    ⭐ 손님 지적: "컷 바뀔 때마다 계속 새로 이펙트를 줘서 새로 띄우지 말고
                   한번 나온 거 가만히 냅둬."
       맞는 말이다. 예전에는 로고를 그래픽 겹(gfx)에 같이 그렸는데, 그 겹은
       컷마다 **떠오르며 나타나는 연출**(fade + 살짝 올라옴)을 받는다.
       그래서 로고가 컷마다 다시 떠올랐다.
       이제 로고만 **따로 된 겹**으로 빼서 페이드도 움직임도 주지 않는다.
       장면 전환(검은 화면으로 잠기는 것)에는 같이 잠긴다 — 그건 화면 전체가
       어두워지는 것이라 로고만 떠 있으면 오히려 이상하다."""
    key = (str(workdir), W, H, bool(vertical), bool(blank))
    if key not in _LOGO_PNG:
        if blank:
            # ⭐ 2026-08-08 손님 지적: "쇼츠 영상 위에 글씨가 겹치잖아!!!"
            #    쇼츠 첫 컷은 위 검은 띠에 **상황 한 줄**(장례식날 전달된 소장)을
            #    앉힌다. 그런데 채널 이름(판결극장)도 같은 띠 한가운데에 그려서
            #    글자 두 개가 그대로 포개졌다. 띠 높이가 165픽셀이라 둘이 못 들어간다.
            #    → 상황 한 줄이 있는 컷에서는 **채널 이름을 그리지 않는다.**
            #      (그 컷은 2~3초뿐이고, 나머지 컷에는 채널 이름이 그대로 나온다)
            lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            p = Path(workdir) / f"logo_blank_{W}x{H}.png"
        else:
            y0, _y1 = stage_box(W, H, vertical)
            lay = G.draw_logo(Image.new("RGBA", (W, H), (0, 0, 0, 0)),
                              W, H, vertical=vertical, band=y0)
            p = Path(workdir) / f"logo_{W}x{H}.png"
        lay.save(p)
        _LOGO_PNG[key] = p
    return _LOGO_PNG[key]


def render_cut(cut, dur, workdir, idx, W, H, vertical=False, top_line="", trans=(None, None)):
    move, gfx_layer, sub_layer = build_plates(cut, W, H, vertical, top_line=top_line)
    mp = workdir / f"m{idx:03d}.png"
    gp = workdir / f"g{idx:03d}.png"
    sp = workdir / f"s{idx:03d}.png"
    move.convert("RGB").save(mp)
    gfx_layer.save(gp)
    sub_layer.save(sp)
    # 상황 한 줄이 띠에 들어가는 컷에서는 채널 이름을 빼 겹침을 막는다
    lp = logo_png(workdir, W, H, vertical, blank=bool(top_line))

    frames = max(2, int(dur * FPS))
    # 느린 확대 + 아주 약한 숨쉬기. 정지 이미지가 죽어 보이는 것을 막는다.
    # ⚠️ 예전에는 1.02 에서 시작해 **첫 프레임부터 화면의 2% 를 잘라먹었다.**
    #    1.0 에서 시작하면 첫 프레임은 원본 그대로다. 숨쉬기 진폭만큼은
    #    1.0 아래로 내려가지 않게 바닥을 깔아 둔다(zoompan 은 z<1 을 1 로 자른다).
    span = ZOOM_MAX - ZOOM_START - 0.004
    zexpr = f"{ZOOM_START + 0.004:.4f}+{span:.4f}*(on/{frames})+0.004*sin(on/26)"
    vf = (f"[0:v]scale={W * 2}:{H * 2},"
          f"zoompan=z='{zexpr}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
          f"s={W}x{H}:fps={FPS}[v]")

    # ⭐ 등장 연출.
    #    이름표는 **왼쪽에서 미끄러져 들어오고**(방송 로워서드가 쓰는 방식),
    #    나머지 카드는 **살짝 아래에서 떠오르며** 나타난다.
    #    자막은 움직이지 않는다 — 위치가 흔들리면 읽다가 놓친다. 페이드만 짧게.
    gtype = (cut.get("gfx") or {}).get("type")
    if gtype == "nametag":
        gx = f"-(w*0.16)*max(0\,1-t/{GFX_IN})"
        gy = "0"
    else:
        gx = "0"
        gy = f"-(h*0.022)*max(0\,1-t/{GFX_IN})"

    vf += (f";[2:v]format=rgba,fade=t=in:st=0:d={GFX_IN}:alpha=1[g]"
           f";[v][g]overlay=x='{gx}':y='{gy}'[vg]"
           f";[3:v]format=rgba,fade=t=in:st=0:d={SUB_IN}:alpha=1[s]"
           f";[vg][s]overlay=0:0[vs]"
           # ⭐ 로고 — 페이드도 움직임도 **없다.** 컷이 바뀌어도 그 자리에 가만히 있다.
           f";[4:v]format=rgba[l]"
           f";[vs][l]overlay=0:0[vt]")

    # 전환은 **맨 마지막에** 건다. 자막·그래픽까지 전부 합쳐진 뒤라야
    # 화면 전체가 함께 잠기고 함께 열린다.
    t_in, t_out = trans
    fades = []
    if t_in:
        color, d_ = t_in
        fades.append(f"fade=t=in:st=0:d={min(d_, dur / 2):.3f}:color={color}")
    if t_out:
        color, d_ = t_out
        d_ = min(d_, dur / 2)
        fades.append(f"fade=t=out:st={max(0.0, dur - d_):.3f}:d={d_:.3f}:color={color}")
    vf += f";[vt]{','.join(fades)},format=yuv420p[vo]" if fades \
        else ";[vt]format=yuv420p[vo]"

    out = workdir / f"v{idx:03d}.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error",
         "-loop", "1", "-i", str(mp), "-loop", "1", "-i", str(gp),
         "-loop", "1", "-i", str(gp), "-loop", "1", "-i", str(sp),
         "-loop", "1", "-i", str(lp),
         "-filter_complex", vf, "-map", "[vo]", "-t", f"{dur:.3f}",
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
    # ⭐ 손님 지적: "배경음악 볼륨 좀 낮춰. 목소리가 잘 안 들려."
    #    -30 → -36 (목소리 -16 보다 **20 dB 아래**). 6 dB 를 더 내렸다 —
    #    사람 귀에는 소리 크기가 대략 절반으로 줄어든 정도다.
    #    앰비언스(-36)와 같은 자리로 내려 '있는 줄 알지만 말을 안 가리는' 선이다.
    "bgm": -36.0,       # 20 dB 아래 — 말 밑에 조용히 깔리는 정도
    "tr": -20.0,        # 전환음 — 4 dB 아래. 말이 아직 시작 전이라 조금 더 커도 된다
}
_db_cache = {}


def mean_db(path, ss=0.0, t=0.0, af=""):
    """파일(또는 그 일부)의 평균 음량(dB). 한 번만 재고 기억해 둔다.

    `ss`·`t` 를 주면 그 구간만 잰다. 전환음은 파일 전체가 아니라 잘라 쓰는 구간의
    크기를 맞춰야 하기 때문이다 — 앞뒤 여백까지 넣어 재면 실제보다 작게 나온다.
    `af` 를 주면 그 필터를 건 뒤의 크기를 잰다(고음이 얼마나 되는지 잴 때 쓴다)."""
    key = (str(path), round(ss, 3), round(t, 3), af)
    if key not in _db_cache:
        cmd = ["ffmpeg", "-hide_banner", "-nostats"]
        if ss:
            cmd += ["-ss", f"{ss:.3f}"]
        if t:
            cmd += ["-t", f"{t:.3f}"]
        chain = (af + "," if af else "") + "volumedetect"
        r = subprocess.run(cmd + ["-i", str(path), "-af", chain,
                                  "-f", "null", "-"], capture_output=True, text=True)
        m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
        _db_cache[key] = float(m.group(1)) if m else -30.0
    return _db_cache[key]


# ── ⭐ 영상이 시작하자마자 나던 "치지직" ────────────────────
#
# 손님 지적: "왜 자꾸 최초 영상 시작할 때 치지직 거리는 소리가 나는 거야?"
#
# 실측으로 잡았다. 완성된 소리의 첫 2초를 0.1초 단위로 갈라 재 보니
#     0.0~0.3초   5kHz 위 에너지  0.5~1.4%   ← 조용하다
#     0.4~0.9초   5kHz 위 에너지  52~63%     ← **여기가 '치지직' 이다**
#     1.0초~      5kHz 위 에너지  1.8~2.5%   ← 다시 조용해진다
# 0.42초는 첫 컷의 효과음(sfx_paper)이 들어오도록 되어 있던 자리다.
#
# 음원 자체가 문제였다 — 효과음 14개를 전부 재 보니
#     paper 80.9% · tear 79.1%   ← 사실상 '쉬익' 하는 잡음이다
#     나머지 12개는 전부 39% 이하
# 예전 처리(highshelf 5kHz -8dB)로는 71%까지밖에 못 내렸다. 턱없이 모자랐다.
#
# 두 가지를 함께 고친다.
#   ① 잡음스러운 음원만 **재서 골라내** 4kHz 저역통과를 두 번 건다 (71% → 15%)
#      파일을 재서 정하므로, 나중에 좋은 음원으로 갈아 끼우면 필터가 저절로 풀린다
#   ② 첫 컷의 효과음은 **여는 페이드(0.7초)가 끝난 뒤**에 낸다
HISS_ABOVE = 5000           # 이 주파수 위를 '고음' 으로 본다
HISS_SHARE = 0.55           # 고음이 이 몫을 넘으면 '쉬익' 소리로 본다
TAME_HISS = "lowpass=f=4000,lowpass=f=4000"     # 쉬익 소리용 (실측 71% → 15%)
TAME_NORM = "highshelf=f=5000:g=-8"             # 보통 효과음 — 날만 살짝 죽인다
OPEN_SFX_DELAY = 900        # 첫 컷 효과음을 이만큼(ms) 늦춘다. OPEN_FADE 뒤로 보낸다


def hiss_share(path):
    """이 소리의 에너지 중 고음(5kHz 위)이 차지하는 몫 (0~1).

    ⚠️ numpy 없이 **ffmpeg 만으로** 잰다. 저역통과를 걸기 전후의 음량 차이가 곧 몫이다.
       렌더링 쪽에는 numpy 가 없을 수 있어서, 있다고 가정하면 검사가 조용히 꺼진다."""
    full = mean_db(path)
    low = mean_db(path, af=f"lowpass=f={HISS_ABOVE},lowpass=f={HISS_ABOVE}")
    return max(0.0, min(1.0, 1.0 - 10 ** ((low - full) / 10.0)))


def tame_sfx(path):
    """이 효과음에 걸 필터. **파일을 재서** 정한다 — 이름으로 짐작하지 않는다."""
    return TAME_HISS if hiss_share(path) > HISS_SHARE else TAME_NORM


def gain_db(path, kind, ss=0.0, t=0.0):
    """이 파일을 목표 크기로 맞추는 데 필요한 dB. 지나친 증폭은 막는다."""
    return max(-24.0, min(24.0, TARGET_DB[kind] - mean_db(path, ss, t)))


# ── 전환음 ───────────────────────────────────────────────
# 화면만 바뀌어서는 부족하다. 50~60대 시청자는 **소리가 나야** 장면이 넘어간 것을 알아챈다.
# 올려주신 음원 4종을 전환 종류에 맞춰 건다. 각 음원의 봉우리 위치를 실측해 잘라 쓴다.
#   tr_act        0.5초에 타격(-6 dB) 뒤 긴 여운   → 막이 열릴 때
#   tr_flash_out  0.5초에 타격 뒤 빠른 감쇠         → 현재로 돌아올 때
#   tr_flash_in   1.5~2.0초에 정점까지 **차오름**   → 회상으로 들어갈 때
#   tr_twist      0.25~2.0초 지속                  → 반전이 드러나는 컷
# ⭐ tr_flash_in 만 다르게 쓴다. 차오르는 소리를 도착한 뒤에 틀면 앞뒤가 뒤집힌다.
#    **앞 컷 끝**에 걸어 정점이 경계(흰 플래시)에 딱 맞게 하고, 도착한 컷에는 여운만 남긴다.
TR_TAIL = 0.35                          # 전환음 끝을 이만큼 부드럽게 내린다
OPEN_FADE = 0.7                         # 영상 맨 앞을 무음에서 올리는 시간(초)
TR_IN = {                               # 도착한 컷 머리에 건다: (파일, 잘라낼 시작, 길이)
    ("black", ACT_IN): ("tr_act", 0.30, 2.60),
    ("white", FLASH_OUT): ("tr_flash_out", 0.30, 1.70),
}
TR_PRE = ("tr_flash_in", 0.20, 1.90)    # 회상 직전 — 앞 컷 끝에서 차오른다
TR_LAND = ("tr_flash_in", 2.10, 2.20)   # 회상에 도착한 뒤 남는 여운
TR_TWIST = ("tr_twist", 0.15, 2.60)     # 반전 컷 — 전환이 따로 없을 때만


def transition_sounds(cuts, durs):
    """컷마다 깔 전환음 목록. → [[(경로, 잘라낼 시작, 길이, 지연초), …], …]

    배경만 바뀌는 짧은 암전(0.18초)에는 소리를 넣지 않는다. 42번이나 되기 때문에
    다 넣으면 영상 내내 '슉슉' 소리만 난다."""
    out = [[] for _ in cuts]
    for i, (cut, (t_in, _)) in enumerate(zip(cuts, transitions(cuts))):
        spec = TR_IN.get(t_in)
        if spec:
            # ⚠️ **맨 첫 컷에는 막 전환음을 넣지 않는다.**
            #    t=0 은 '넘어온' 자리가 아니라 '시작하는' 자리다. 넘어오는 소리를
            #    영상이 열리자마자 틀면 전환이 아니라 잡음으로 들린다.
            #    실측: tr_act 는 앞 300ms 안에 최대치(1.000)까지 치솟는데,
            #    같은 순간 첫 컷의 종이 효과음(고음 81%)과 앰비언스가 함께 터져
            #    "치시시시직" 으로 들렸다. 첫 컷은 조용히 연다.
            if i == 0:
                continue
            p = audio_path("sfx", spec[0])
            if p:
                out[i].append((p, spec[1], spec[2], 0.0))
        elif t_in == ("white", FLASH_IN):
            name, ss, ln = TR_PRE
            p = audio_path("sfx", name)
            if p and i:
                # 앞 컷이 짧으면 **뒤쪽(정점)을 남기고** 앞을 잘라낸다.
                ln_ = min(ln, durs[i - 1])
                out[i - 1].append((p, ss + (ln - ln_), ln_, durs[i - 1] - ln_))
            lp = audio_path("sfx", TR_LAND[0])
            if lp:
                out[i].append((lp, TR_LAND[1], TR_LAND[2], 0.0))
        elif cut.get("tag") == "twist":
            p = audio_path("sfx", TR_TWIST[0])
            if p:
                out[i].append((p, TR_TWIST[1], TR_TWIST[2], 0.0))
    return out


# ── 소리 ────────────────────────────────────────────────
# ── 인물별 목소리 크기 고르기 ──────────────────────────────
# ⭐ **왜 필요한가** — 지금까지 나레이션을 volume=1.0 으로, 즉 **손도 안 대고**
#    그대로 섞고 있었다. 제미나이는 같은 모델·같은 목소리로 불러도 컷마다
#    크기가 들쭉날쭉하게 나온다. 그러면 같은 사람인데 **가까웠다 멀어졌다**
#    하는 것처럼 들려서, 손님 귀에는 '목소리가 중간중간 바뀐다' 로 느껴진다.
#
# ⭐ **인물마다 따로** 맞춘다. 전부 같은 크기로 밀어 버리면 힘없는 노인과
#    소리치는 장남이 같은 크기가 되어 연기가 죽는다. 그 인물의 **자기 평균**에
#    맞추면, 인물 사이의 차이는 남고 한 인물 안의 흔들림만 사라진다.
#
# ⭐ 값이 0원이다 — 이미 만들어 둔 소리의 볼륨만 조절한다. 다시 만들지 않는다.
VOICE_GAIN_MAX = 6.0        # 한 컷을 이만큼(dB) 넘게는 올리거나 내리지 않는다
VOICE_GAIN_MIN = 0.3        # 이보다 작은 차이는 귀에 안 들린다 — 손대지 않는다
_GAIN = {}                  # {컷id: 보정값 dB}


# ── 목소리 **음색(톤)** 고르기 ─────────────────────────────
# ⭐ 손님 지적(컷 H05): "이 부분 해설이 **얇고 하이톤**으로 갑자기 다르다."
#
#    크기를 맞춰도 이건 안 고쳐진다. **얇다 = 음색** 문제이지 크기가 아니다.
#    음높이(f0)도 아니다 — 높이는 이미 반음 안으로 맞춰 두었다(normalize_pitch).
#    같은 사람이라도 **저음이 빠지고 고음이 세면** '얇고 하이톤' 으로 들린다.
#    제미나이는 같은 목소리로 불러도 컷마다 이 균형이 달라진다.
#
#    그래서 컷마다 저음·고음이 전체 대비 얼마나 되는지 재고, 그 인물의 평균
#    균형 쪽으로 당긴다. 이미 만들어 둔 소리를 손보는 것이라 **값이 0원**이다.
TONE_LOW = 300              # 이 아래를 '저음' 으로 본다 (Hz)
TONE_HIGH = 3500            # 이 위를 '고음' 으로 본다 (Hz)
# ⭐ 2026-08-07 손님 명령으로 **0 = 끔**. 컷마다 저음·고음을 다르게 손보면
#    손댄 컷과 안 댄 컷이 서로 달라진다 — 고치려던 바로 그 문제를 만든다.
#    묶어 만들면 한 통 안에서는 이미 음색이 같으므로 손볼 이유도 없다.
TONE_MAX = float(os.environ.get("VT_TONE_MAX", "0"))
TONE_MIN = 0.8              # 이보다 작은 차이는 귀에 안 들린다
_TONE = {}                  # {컷id: ffmpeg 필터 문자열}

# ⭐ 전체 배속 (2026-08-08 손님 지시: "지금보다 1.2배 더 빠르게").
#    음성은 이미 만들 때 1.12배로 빨라져 있고, 여기서 **조립할 때** 1.2배를
#    더 건다(합계 약 1.34배). 높낮이는 안 변한다(atempo 는 박자만 바꾼다).
#    ⚠️ 여기서 거는 이유: 만들 때 배속을 바꾸면 조리법이 바뀌어 음성 전체를
#    다시 사야 한다(약 650원). 조립 단계는 이미 산 소리를 그대로 쓰므로 0원이고,
#    마음에 안 들면 이 숫자만 고쳐 다시 조립하면 된다.
#    컷 길이(대본 초)도 같은 비율로 줄여 화면 전환까지 함께 빨라진다.
#
# ⚠️⚠️ 2026-08-08 손님: "발음이 뭉개진다." 맞는 지적이고 내 잘못이다.
#    목소리를 만들 때 이미 1.12배로 빠르게 돌리는데, 그 위에 여기서 1.2배를
#    또 얹어 **합계 1.34배**가 됐다. 소리를 빠르게 늘리는 처리를 두 번 겹쳐
#    걸면 자음이 뭉개진다 — 속도만 보고 음질을 안 들어본 결과다.
#    손님 선택(선택지 제시 후): **합계 1.2배**로 낮춘다.
#    그래서 여기서 거는 값은 1.2 가 아니라 1.2 ÷ 1.12 = 약 1.071 이다.
#    (VT_TEMPO 에 넣는 숫자는 '합계로 몇 배냐' 이고, 나눗셈은 코드가 한다)
SPEECH_SPEED = 1.12                    # 목소리를 만들 때 이미 걸려 있는 배속
TEMPO_TOTAL = max(0.5, min(2.0, float(os.environ.get("VT_TEMPO", "1.2"))))
TEMPO = TEMPO_TOTAL / SPEECH_SPEED     # 렌더링에서 **더** 걸 배속


def _tone_filter(g_low, g_high):
    parts = []
    if abs(g_low) >= TONE_MIN:
        parts.append(f"bass=g={g_low:.1f}:f={TONE_LOW}:w=0.7")
    if abs(g_high) >= TONE_MIN:
        parts.append(f"treble=g={g_high:.1f}:f={TONE_HIGH}:w=0.7")
    return ",".join(parts)


# ── 인물별 목소리 높이 내리기 (반음 단위 · 마이너스면 낮아진다) ──────────────
#
# 왜 (2026-08-09 손님: "장남 목소리 너무 가늘고 여자 같아서
#                      조금 더 묵직하고 아저씨 같고 걸걸한 목소리로 바꿔야 될 것 같은데")
#     맞는 지적이고 **내 잘못이다.** 장남에게 준 Gacrux 는 실측 **186Hz** 로,
#     어머니(198Hz)·할머니(198Hz)·여자(200Hz) 옆자리다. 남자들(120~131Hz)과는
#     60Hz 넘게 떨어져 있다. 구글이 붙인 'Mature(원숙한)' 라는 **설명만 보고
#     같은 파일에 적혀 있는 높이표를 안 봤다.**
#
# 왜 여기서 고치나 — **값이 0원이기 때문이다.**
#     목소리 이름을 바꾸면 그 인물 대사를 전부 다시 사야 한다. 여기서 하는 것은
#     **이미 산 소리를 조립할 때 손보는 것**이라 몇 번을 고쳐도 0원이다.
#     그래서 얼마나 내릴지도 짐작하지 않고 **여러 단계로 만들어 귀로 고르실 수 있다.**
#
# 얼마나 내릴 수 있나 (정직하게)
#     186Hz 를 남자 음역(125Hz쯤)까지 내리려면 약 7반음이다. 그만큼 내리면
#     소리가 늘어진 듯 부자연스러워진다. 3~4반음(150Hz쯤)이 자연스러운 한계다.
#     즉 이 방법으로는 **'조금 더 묵직하게' 까지는 되지만 '완전히 다른 사람' 은 안 된다.**
#     그 이상이 필요하면 목소리 이름을 바꿔야 하고, 그때는 값이 든다.
VOICE_PITCH = {
    # 장남만 손댄다 (손님 선택: "장남만 건드리기")
    "v_M50A": float(os.environ.get("VT_PITCH_M50A", "-3.0")),
}

_RUBBERBAND = None


def have_rubberband():
    """음높이만 바꾸는 좋은 필터가 이 컴퓨터 ffmpeg 에 들어 있는가.

    없어도 된다 — 없으면 '천천히 틀어 낮추고 빠르기를 되돌리는' 옛 방법을 쓴다."""
    global _RUBBERBAND
    if _RUBBERBAND is None:
        try:
            out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                                 capture_output=True, text=True, check=True).stdout
            _RUBBERBAND = " rubberband " in out
        except Exception:
            _RUBBERBAND = False
    return _RUBBERBAND


def _pitch_filter(semitones):
    """목소리를 반음 단위로 내린다(마이너스면 낮아진다). **길이는 그대로다.**

    ⚠️ 소리를 통째로 느리게 틀면 음이 낮아지지만 말이 늘어진다. 그래서 낮춘 만큼
       빠르기를 되돌려 길이를 맞춘다. 이러면 성대뿐 아니라 **울림통까지 커진 것처럼**
       들려서, 단순히 음만 낮춘 것보다 '덩치 큰 아저씨' 에 가깝다.
    ⚠️ 파일마다 표본율이 달라도 되게 44100 으로 먼저 맞춘 뒤 손댄다."""
    if abs(semitones) < 0.25:
        return ""
    k = 2.0 ** (semitones / 12.0)
    if have_rubberband():
        return f"rubberband=pitch={k:.5f}"
    return (f"aresample=44100,asetrate={int(44100 * k)},"
            f"aresample=44100,atempo={1.0 / k:.5f}")


def set_voice_gains(doc, narration_dir):
    """컷마다 **음색과 볼륨**을 얼마나 손볼지 미리 계산해 둔다.

    본편 대본 기준으로 한 번만 계산한다. 쇼츠는 같은 소리 파일을 쓰므로
    (nar_id 로 이어진다) 여기서 정한 값을 그대로 쓴다.

    순서가 중요하다 — **음색을 먼저 맞추고, 그 결과의 크기를 다시 재서** 볼륨을
    맞춘다. 음색을 건드리면 전체 크기도 조금 달라지기 때문이다."""
    _GAIN.clear()
    _TONE.clear()
    if not narration_dir:
        return

    # ① 컷마다 저음·고음이 전체 대비 얼마나 되는지 잰다
    raw = {}
    for act in doc.get("acts", []):
        for c in act.get("cuts", []):
            if not (c.get("text") or "").strip():
                continue
            p = Path(narration_dir) / f"{c.get('nar_id', c['id'])}.mp3"
            if not p.exists() or p.with_suffix(".silent").exists():
                continue
            db = mean_db(p)
            if db is None or db < -60:        # 무음에 가까운 것은 기준에서 뺀다
                continue
            lo = mean_db(p, af=f"lowpass=f={TONE_LOW}") - db
            hi = mean_db(p, af=f"highpass=f={TONE_HIGH}") - db
            raw.setdefault(c.get("speaker", "narrator"), []).append((c["id"], p, db, lo, hi))

    # ⚠️ mean_db 는 **재기에 실패해도 조용히 -30.0 을 돌려준다.** 그러면 모든 컷이
    #    똑같아 보여 '고를 것이 없다' 로 지나간다 — 안 재고 통과시키는 셈이다.
    #    이 프로젝트에서 이런 조용한 실패로 원인을 두 번 잘못 짚었다. 여기서 막는다.
    allv = [d for items in raw.values() for _, _, d, _, _ in items]
    if allv and len(set(round(d, 1) for d in allv)) == 1:
        print(f"  ⚠️ 목소리를 재지 못했습니다 ({len(allv)}컷이 전부 {allv[0]:.1f}dB)"
              " — 크기·음색 고르기를 건너뜁니다")
        _GAIN.clear()
        _TONE.clear()
        return

    for sp, raws in sorted(raw.items()):
        # ⭐ 그 인물의 목소리를 낮출 것인가 (장남 — 손님 지적).
        #    음색·크기를 재기 **전에** 붙인다. 낮추면 크기도 달라지므로,
        #    낮춘 뒤의 소리를 재야 크기 맞추기가 맞아떨어진다.
        pf = _pitch_filter(VOICE_PITCH.get(sp, 0.0))
        if pf:
            print(f"  목소리 낮추기 — {sp} {VOICE_PITCH[sp]:+.1f}반음"
                  f" ({'좋은 방법' if have_rubberband() else '옛 방법'})")

        # ② 인물의 '평균 음색' 을 정하고, 컷마다 그쪽으로 당긴다
        mlo = sorted(x[3] for x in raws)[len(raws) // 2]
        mhi = sorted(x[4] for x in raws)[len(raws) // 2]
        odd = []
        for cid, p, db, lo, hi in raws:
            gl = max(-TONE_MAX, min(TONE_MAX, mlo - lo))
            gh = max(-TONE_MAX, min(TONE_MAX, mhi - hi))
            f = ",".join(x for x in (pf, _tone_filter(gl, gh)) if x)
            if f:
                _TONE[cid] = f
                odd.append((abs(gl) + abs(gh), cid, gl, gh))

        # ③ 음색을 맞춘 **뒤의** 크기를 다시 재서 볼륨을 맞춘다
        items = [(cid, mean_db(p, af=_TONE[cid]) if cid in _TONE else db)
                 for cid, p, db, lo, hi in raws]
        vals = sorted(d for _, d in items)
        mid = vals[len(vals) // 2]
        spread = vals[int(len(vals) * 0.9)] - vals[int(len(vals) * 0.1)] if len(vals) >= 5 else 0.0
        n = 0
        for cid, db in items:
            g = max(-VOICE_GAIN_MAX, min(VOICE_GAIN_MAX, mid - db))
            if abs(g) >= VOICE_GAIN_MIN:
                _GAIN[cid] = g
                n += 1
        name = "해설" if sp == "narrator" else sp
        print(f"  목소리 고르기 — {name:8s} {len(items):3d}컷"
              f"  크기 가운데 {mid:6.1f}dB 폭 {spread:4.1f}dB → {n}컷"
              f" · 음색 {len(odd)}컷")
        # ⭐ **가장 튀는 컷을 이름으로 찍는다.** 손님이 "이 부분" 이라고 짚었을 때
        #    기록에서 바로 찾을 수 있어야 한다. H05 처럼 눈으로 확인하려는 것이다.
        for _, cid, gl, gh in sorted(odd, reverse=True)[:3]:
            why = []
            if gl >= TONE_MIN:
                why.append("저음이 빠져 얇았음")
            elif gl <= -TONE_MIN:
                why.append("저음이 과했음")
            if gh <= -TONE_MIN:
                why.append("고음이 세서 날카로웠음")
            elif gh >= TONE_MIN:
                why.append("고음이 죽어 먹먹했음")
            print(f"      {cid:8s} 저음 {gl:+.1f}dB 고음 {gh:+.1f}dB"
                  f"  ({' · '.join(why) or '조정'})")


def build_audio(doc, durs, workdir, narration_dir=None):
    """나레이션 + 앰비언스 + 효과음 + 음악을 하나로 섞는다.

    ⚠️ **무음 구간을 만들지 않는다.** 완전한 무음은 '죽은 소리'로 들려 이탈을 부른다.
    앰비언스가 없으면 아주 작은 방 소리를 합성해서라도 깔아둔다."""
    cuts = [c for a in doc["acts"] for c in a["cuts"]]
    trs = transition_sounds(cuts, durs)
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
            # ⭐ volume=1.0 (손 안 댐) 이었다. 이제 그 인물의 평균 크기에 맞춘다.
            g = _GAIN.get(cut.get("nar_id", cut["id"]), 0.0)
            inputs += ["-i", str(nar)]
            # 음색을 먼저 맞추고 그다음 크기를 맞춘다 (set_voice_gains 와 같은 순서)
            tone = _TONE.get(cut.get("nar_id", cut["id"]), "")
            tempo = f"atempo={TEMPO:.3f}," if abs(TEMPO - 1.0) > 0.001 else ""
            filters.append(f"[{mixn}:a]{tempo}adelay=250|250,"
                           + (tone + "," if tone else "")
                           + f"volume={g:+.1f}dB[a{mixn}]")
            mixn += 1

        sfx = audio_path("sfx", cut["sfx"]) if cut.get("sfx") else None
        if sfx:
            # ⭐ 필터를 **파일마다 재서** 정한다 (tame_sfx 위 설명 참고).
            #    종이·종이찢는 소리는 에너지의 80%가 5kHz 위라 사실상 잡음이다.
            #    예전에는 전부 같은 shelf 하나로 처리해 71% 밖에 못 내렸고,
            #    그것이 영상 시작 0.4초의 "치지직" 이었다.
            # ⚠️ 첫 컷은 **여는 페이드가 끝난 뒤**로 늦춘다. 예전 420ms 는 페이드
            #    한가운데라, 소리가 커지는 도중에 잡음이 겹쳐 더 거슬렸다.
            delay = OPEN_SFX_DELAY if i == 0 else 120
            inputs += ["-i", str(sfx)]
            filters.append(f"[{mixn}:a]{tame_sfx(sfx)},adelay={delay}|{delay},"
                           f"volume={gain_db(sfx, 'sfx'):.1f}dB[a{mixn}]")
            mixn += 1

        # 전환음. 지연 없이 컷 머리에 붙인다 — 화면이 열리는 순간과 같이 나야 한다.
        # (나레이션은 250ms 뒤에 시작하므로 말과 겹치지 않는다.)
        for p, ss, ln, delay in trs[i]:
            ln = min(ln, max(0.10, dur - delay))
            inputs += ["-ss", f"{ss:.3f}", "-t", f"{ln:.3f}", "-i", str(p)]
            f = (f"[{mixn}:a]volume={gain_db(p, 'tr', ss, ln):.1f}dB,"
                 f"afade=t=out:st={max(0.0, ln - TR_TAIL):.3f}:d={min(TR_TAIL, ln):.3f}")
            if delay > 0.001:
                f += f",adelay={int(delay * 1000)}|{int(delay * 1000)}"
            filters.append(f + f"[a{mixn}]")
            mixn += 1

        # 조각 양 끝에 8ms 페이드. 파형이 0 에서 시작해 0 으로 끝나야 이음매가 조용하다.
        fade = min(0.008, dur / 4)
        mix = "".join(f"[a{k}]" for k in range(mixn))
        # ⚠️ `normalize=0` 이 꼭 필요하다. amix 는 기본으로 **입력 개수만큼 나눈다.**
        #    실측: 같은 소리를 입력 1개→4개로 늘리면 -33 → -45 dB 로 줄었다.
        #    그래서 예전에는 효과음이 있는 컷에서만 목소리가 3.5 dB 작아졌고,
        #    전환음까지 넣으면 막이 바뀔 때마다 목소리가 6 dB 씩 꺼지게 된다.
        #    이제 크기는 위에서 dB 로 직접 정하고, 봉우리만 리미터로 눌러 준다.
        fc = (";".join(filters) +
              f";{mix}amix=inputs={mixn}:duration=first:dropout_transition=0:normalize=0,"
              f"volume=-3dB,alimiter=limit=-1.0dB:level=disabled,"
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
        # 여기도 normalize=0. 켜 두면 목소리가 6 dB 깎이고 음악은 이미 -30 dB 로
        # 맞춰 둔 것이 또 깎여, 애써 잡은 균형이 무너진다.
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(body), "-i", str(music),
             "-filter_complex",
             "[0:a][1:a]amix=inputs=2:duration=first:normalize=0,"
             "alimiter=limit=-1.0dB:level=disabled[out]",
             "-map", "[out]", "-c:a", "pcm_s16le", "-ar", "48000", str(mixed)])
    else:
        mixed = body

    # ⭐ 영상 맨 앞 0.7초는 무음에서 서서히 올라온다.
    #    예전에는 t=0 에 앰비언스·효과음·전환음이 **동시에 최대치로** 시작했다.
    #    사용자가 들은 "치시시시직" 이 이것이다. 어떤 소리든 0 에서 올라오면
    #    그 순간 귀에 거슬리는 것이 없다 — 방송에서 늘 하는 처리다.
    final = workdir / "audio.m4a"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mixed),
         "-af", loudnorm_af(mixed) + f",afade=t=in:st=0:d={OPEN_FADE:.2f}",
         "-c:a", "aac", "-b:a", "192k", str(final)])
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
        return f"alimiter=limit={ceiling}dB:level=disabled"
    try:
        d = json.loads(m.group(0))
        measured = float(d["input_i"])
    except Exception:
        return f"alimiter=limit={ceiling}dB:level=disabled"

    if measured < -45.0:
        # 사실상 무음이다. 여기서 이득을 걸면 잡음만 키운다.
        print(f"    ⚠️ 소리가 거의 없다({measured:.1f} LUFS). 음량을 올리지 않는다 —"
              f" 나레이션이 제대로 만들어졌는지 확인이 필요하다.")
        return f"alimiter=limit={ceiling}dB:level=disabled"

    gain = max(-12.0, min(18.0, target - measured))
    return f"volume={gain:.2f}dB,alimiter=limit={ceiling}dB:level=disabled"


MUSIC_XFADE = 3.0       # 음악이 한 바퀴 돌 때 겹쳐 넘기는 시간(초)
MUSIC_TAIL = 5.0        # 곡 끝의 제 페이드아웃은 잘라낸다 (아래 ⚠️ 참조)
MUSIC_MAX_LOOP = 12     # 안전장치. 이보다 많이 돌 일은 없다


def build_music(doc, durs, workdir):
    """막마다 정해진 음악을 그 막 길이만큼 깔고 교차 페이드로 잇는다.

    ⚠️ 음악 한 곡이 2분인데 막은 3~4분이다. 그냥 이어 붙이면 **곡이 뚝 끊겼다가
       처음부터 다시 시작하는 소리**가 그대로 들린다. 한 바퀴 돌 때마다 3초씩
       겹쳐 넘겨(acrossfade) 이음매를 지운다.

    ⚠️ 크기도 맞춘다. 예전에는 원본 그대로 깔고 마지막에 목소리와 반반으로 섞었다.
       올려주신 곡들은 -14.3 dB — **목소리(-16)보다 크다.** 그대로 두면 음악이
       대사를 덮는다. 목표(-30 dB)로 내려 대사 밑에 깔리게 한다."""
    segs, i = [], 0
    for act in doc["acts"]:
        n = len(act["cuts"])
        alen = sum(durs[i:i + n])
        i += n
        p = audio_path("bgm", act.get("bgm", "hook"))
        if not p or alen <= 0:
            continue

        # ⚠️ 곡 끝 4~5초는 곡 자신이 페이드아웃하는 구간이다(실측: 112초 -14.7 dB →
        #    116초 -45.7 dB). 그 위에 겹쳐 넘기면 이음매마다 음악이 **푹 꺼진다**
        #    (실측 -49.6 dB). 꼬리를 잘라내고 제 소리가 살아 있는 데서 넘긴다.
        one = ffprobe_dur(p)
        body = one - MUSIC_TAIL if one > MUSIC_TAIL + MUSIC_XFADE + 1 else one
        loops = 1
        if body > MUSIC_XFADE + 1 and body < alen:
            loops = min(MUSIC_MAX_LOOP,
                        1 + math.ceil((alen - body) / (body - MUSIC_XFADE)))
        inputs, fc, prev = [], "", "[0:a]"
        for k in range(loops):
            inputs += ["-t", f"{body:.3f}", "-i", str(p)]
        for k in range(1, loops):
            tag = "[mx]" if k == loops - 1 else f"[x{k}]"
            fc += f"{prev}[{k}:a]acrossfade=d={MUSIC_XFADE}:c1=tri:c2=tri{tag};"
            prev = tag
        if loops == 1:
            fc = "[0:a]anull[mx];"
        fc += (f"[mx]atrim=0:{alen:.3f},volume={gain_db(p, 'bgm'):.1f}dB,"
               f"afade=t=in:st=0:d=1.2,"
               f"afade=t=out:st={max(0, alen - 1.5):.3f}:d=1.5[out]")

        s = workdir / f"m_{act['id']}.m4a"
        run(["ffmpeg", "-y", "-loglevel", "error", *inputs,
             "-filter_complex", fc, "-map", "[out]",
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
            # 배속(TEMPO)만큼 대본 초도 줄인다 — 말만 빨라지고 화면이 그대로면
            # 컷 뒤가 빈 채로 남아 오히려 늘어진다. 쉼 0.6초는 그대로 둔다.
            d = float(c.get("sec", 6.0)) / TEMPO
            if narration_dir:
                p = Path(narration_dir) / f"{c.get('nar_id', c['id'])}.mp3"
                if p.exists():
                    d = max(d, ffprobe_dur(p) / TEMPO + 0.6)
            durs.append(round(d, 3))
    return durs


def same_line(a, b):
    """두 문장이 **사실상 같은 말인지** 본다 (마침표·물음표·공백 차이는 무시).

    대본이 넣은 마무리 문장과 렌더러가 붙이려는 문장이 같은지 가리는 데 쓴다.
    글자 그대로 비교하면 마침표 하나 차이로 '다르다' 가 되어 또 두 번 나온다."""
    def n(s):
        return re.sub(r"[\s.!?…·,\"'‘’“”]", "", s or "")
    return bool(n(a)) and n(a) == n(b)


def needs_outro(last_text, outro_line):
    """마무리 컷을 **따로 붙여야 하는지** 판단한다. 렌더러와 검사기가 같이 쓴다.

    ⭐ 판단 규칙을 두 군데에 따로 적으면 언젠가 서로 달라져서 또 새어 나간다.
       그래서 여기 한 곳에만 둔다."""
    return bool(outro_line) and not same_line(last_text, outro_line)


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


def subdoc_for(doc, keep):
    """소리를 만들 때 넘길 '고른 컷만 남긴 대본'. 컷 순서·개수가 keep 과 똑같아야 한다.

    ⚠️⚠️ 2026-08-08 — 여기가 "쇼츠 자막과 나레이션이 하나도 안 맞는다" 의 진짜 원인이었다.
       예전에는 `id(c)`(파이썬이 붙인 메모리 번호)로 골랐다. 그런데 바로 앞에서
       drop_repeat_nametags 가 이름표를 지울 때 컷을 **사본**으로 바꾼다
       (`{**cut, "gfx": None}`). 사본은 메모리 번호가 달라 이 걸러내기에서 통째로
       빠졌다. 실측(쇼츠 1편): 컷 10개인데 **소리 조각이 7개**만 만들어졌고,
       빠진 자리부터 소리가 앞으로 당겨져 자막과 소리가 끝까지 어긋났다
       (영상 35.7초 계획 → 25.7초로 나옴). 손님이 "S1-04는 나레이션이 아예 안 나온다",
       "앞뒤 개연성이 없다" 고 한 것이 이것이다.
       이제 keep 에 있는 컷을 **그대로** 쓰고, 막은 컷 id 로 되찾는다."""
    act_of = {c["id"]: i for i, a in enumerate(doc["acts"]) for c in a["cuts"]}
    sub, cur, bucket = {"acts": []}, None, []
    for c, _d in keep:
        ai = act_of.get(c.get("id"), cur if cur is not None else 0)
        if bucket and ai != cur:
            sub["acts"].append({**doc["acts"][cur], "cuts": bucket})
            bucket = []
        cur = ai
        bucket.append(c)
    if bucket:
        sub["acts"].append({**doc["acts"][cur], "cuts": bucket})

    n_cut = sum(len(a["cuts"]) for a in sub["acts"])
    if n_cut != len(keep):                 # 다시는 조용히 어긋나지 않게 여기서 멈춘다
        raise SystemExit(f"소리에 넘길 컷 수가 안 맞는다: {n_cut} vs {len(keep)}")
    return sub


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

    keep, dropped = drop_repeat_nametags(keep)
    if dropped:
        print(f"    (직전과 같은 사람 이름표 {dropped}개는 다시 띄우지 않는다)")

    # 쇼츠는 전용 마무리 문장이 화면에 들어가야 규격(35~50초)을 채운다.
    # 대본은 그 시간을 est_sec 에 이미 계산해 두었다.
    #
    # ⚠️ **여기가 "마지막 자막이 두 번 나온다" 의 원인이었다.**
    #    예전에는 조건 없이 마무리 컷을 하나 더 붙였다. 그런데 대본 쪽이 바뀌어
    #    이제는 **마무리 문장을 진짜 컷으로(S1-10) 이미 넣어 준다.**
    #    그래서 같은 문장이 두 번 나왔다 — 대본이 넣은 것 + 여기서 붙인 것.
    #    (실측: S1-10 "결말은 본편에서 확인하세요." + S1-10-out 같은 문장)
    #    대본에 이미 있으면 붙이지 않는다. 없는 옛 대본을 위해 붙이는 길은 남긴다.
    outro_cut = None
    if short and short.get("outro_line") and keep:
        if needs_outro(keep[-1][0].get("text"), short["outro_line"]):
            outro_cut = make_outro_cut(keep[-1][0], short["outro_line"])
            keep = keep + [(outro_cut, outro_cut["sec"])]
        else:
            print("    (마무리 문장이 대본에 이미 있어 따로 붙이지 않는다)")

    print(f"  {name}: 컷 {len(keep)}개 · {sum(d for _, d in keep):.1f}초 · {W}x{H}")
    segs = []
    intro = (short or {}).get("intro_line", "")
    trs = transitions([c for c, _ in keep])
    for i, (cut, dur) in enumerate(keep):
        # 넘기다 걸린 사람은 아무것도 모른다. 첫 화면에 한 줄로 상황을 알려준다.
        segs.append(render_cut(cut, dur, work, i, W, H, vertical,
                               top_line=intro if (i == 0 and intro) else "",
                               trans=trs[i]))
        if (i + 1) % 20 == 0:
            print(f"    {i + 1}/{len(keep)}컷")

    lst = work / "vlist.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in segs), encoding="utf-8")
    silent = work / "video.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(silent)])

    # 소리는 막별 음악을 깔아야 하므로 '고른 컷만 남긴 대본'을 다시 만들어 넘긴다.
    # 막 순서와 컷 순서가 keep 과 **정확히 같아야** 소리와 그림이 안 어긋난다.
    #
    # ⚠️⚠️ 2026-08-08 — 여기가 "쇼츠 자막과 나레이션이 하나도 안 맞는다" 의 진짜 원인이었다.
    #    예전에는 `id(c)`(파이썬이 붙인 메모리 번호)로 골랐다. 그런데 바로 위
    #    drop_repeat_nametags 가 이름표를 지울 때 컷을 **사본**으로 바꾼다
    #    (`{**cut, "gfx": None}`). 사본은 메모리 번호가 달라 이 걸러내기에서 통째로
    #    빠졌다. 실측(쇼츠 1편): 컷 10개인데 **소리 조각이 7개**만 만들어졌고,
    #    빠진 자리부터 소리가 앞으로 당겨져 **자막과 소리가 끝까지 어긋났다.**
    #    (손님: "S1-04는 나레이션이 아예 안 나온다", "앞뒤 개연성이 없다")
    #    이제 keep 에 있는 컷을 **그대로** 쓰고, 막은 컷 id 로 되찾는다.
    sub = subdoc_for(doc, keep)
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
    # ⭐ 영상 하나만 다시 만들기 (관리자 페이지의 '이 영상만 다시 만들기' 버튼).
    #    한 편이 마음에 안 들 때 네 개를 다 다시 만들면 50분이 걸린다.
    #    쇼츠 한 편만 다시 만들면 5분이면 끝난다.
    ap.add_argument("--only", default="",
                    help="하나만 만든다: longform / short1 / short2 / short3")
    args = ap.parse_args()

    if not shutil.which("ffmpeg"):
        print("❌ ffmpeg 가 없다. GitHub Actions ubuntu 러너에는 기본 설치되어 있다.")
        return 2

    sp = Path(args.script)
    doc = json.loads(sp.read_text(encoding="utf-8"))
    # 이름표를 그 사람 옆에 붙이려면 '이름 → 인물 코드' 다리가 필요하다.
    # 쇼츠 대본에는 배역 명단이 없으므로 여기서 한 번 채워 둔다.
    set_cast(doc)
    # ⭐ 회상 시점 자막이 그림과 어긋나지 않게 **그리기 직전에** 한 번 더 손본다.
    #    ('아버지 생전' 인데 화면에는 지금 나이 그대로 — 2026-08-09 손님 지적)
    fix_time_labels(doc)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    nar = args.narration or None

    # ⭐ 본편·쇼츠를 그리기 **전에** 한 번만 계산한다. 4번 그리면서 4번 재면 낭비다.
    set_voice_gains(doc, nar)

    only = (args.only or "").strip()
    if only and only not in ("longform", "short1", "short2", "short3"):
        print(f"❌ --only 값이 잘못됐다: {only}")
        return 2
    print(f"렌더링: {sp.name}" + (f"  ({only} 만)" if only else ""))
    if not only or only == "longform":
        render(doc, out, vertical=False, narration_dir=nar, limit=args.limit,
               name="longform")

    if only == "longform":
        return 0
    if only:
        args.shorts = True          # 쇼츠 하나만 지정했으면 쇼츠 경로로 들어간다
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
                if only and f"short{s.get('no')}" != only:
                    continue
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
