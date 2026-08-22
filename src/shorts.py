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
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import clip as C                                            # noqa: E402
import tts                                                  # noqa: E402

FONT_B = ROOT / "assets" / "fonts" / "KoPub_Dotum_Pro_Bold.otf"
FONT_M = ROOT / "assets" / "fonts" / "KoPub_Dotum_Pro_Medium.otf"
# ⭐⭐ 2026-08-21 운영자: "위쪽 후킹 문구는 글꼴도 바뀌어야 되고 크기도 더
#    커져야 될 것 같다."
#    맞다. 실제로 만든 것을 보니 후킹이 76px 짜리 보통 굵기라 **자막보다도
#    존재감이 없었다.** 후킹은 남느냐 떠나느냐를 가르는 한 줄인데 그랬다.
#    ⚠️ 저장소에 글꼴 파일을 넣어 둔다 — 깃허브 실행기에는 한글 글꼴이
#       아예 없어서, 시스템 글꼴에 기대면 네모(두부)로 나온다.
FONT_H = ROOT / "assets" / "fonts" / "NanumGothic_ExtraBold.ttf"

W, H = 1080, 1920                # 쇼츠 화면
VIDEO_Y, VIDEO_H = 520, 810      # 4:3 영상이 앉는 자리
MARK_Y, MARK_SIZE = 40, 38       # 우측 상단 채널 이름
# 후킹은 **상자에 꽉 차게** 키운다 — 아래 HOOK_MAX 부터 줄여 가며 맞춘다
HOOK_TOP, HOOK_BOT = 150, 470
HOOK_MAX, HOOK_MIN, HOOK_GAP = 132, 60, 1.18
SUB_TOP, SUB_BOT, SUB_SIZE = 1360, 1610, 68
SIDE = 64                        # 좌우 여백
GOLD = (198, 160, 74)
# ⭐ 후킹에서 별표로 감싼 토막에 넣을 색 (2026-08-21 운영자 지시).
#    채널 이름에 쓰는 GOLD 는 검은 바탕에서 132px 로 키우면 탁해 보인다.
#    한 톤 밝은 금색으로 쓴다 — 흰 글자 사이에서 확실히 튄다.
HOOK_HI = (255, 206, 84, 255)
DIM = (118, 122, 136, 255)   # 아직/이미 말한 줄
CHANNEL = "판결극장"


def syl(t):
    """실제로 소리 나는 글자만 (공백·쉼표는 시간을 안 잡아먹는다)."""
    return len(re.findall(r"[가-힣]", str(t or "")))


def voiced_spans(src, n, dur, lines=None):
    """**실제로 목소리가 난 자리** — 소리에서 직접 찾는다 (2026-08-20 운영자 지시).

    "자막은 사람마다 가라오케 식으로 하는 게 낫지 않냐?"

    말하는 시각을 우리는 모른다. 플로우가 알려주지 않는다. 그래서 **소리에서
    말이 끊기는 자리를 찾아** 사람 수만큼 토막을 낸다(만든 소리로 재보니
    0.02초 오차로 맞았다). 못 찾으면 **음절 수 비례**로 나눈다 — 긴 대사가
    긴 시간을 갖는 것이 그냥 똑같이 나누는 것보다 훨씬 가깝다.
    """
    if n == 1:
        return [(0.0, dur)]
    spans = []
    try:
        log = subprocess.run(
            ["ffmpeg", "-i", str(src), "-af", "silencedetect=n=-35dB:d=0.22",
             "-f", "null", "-"], capture_output=True, text=True).stderr
        cur = 0.0
        for m in re.finditer(r"silence_(start|end): ([\d.]+)", log):
            v = float(m.group(2))
            if m.group(1) == "start":
                if v - cur > 0.2:
                    spans.append([cur, v])
                cur = v
            else:
                cur = v
        if dur - cur > 0.2:
            spans.append([cur, dur])
    except Exception:                                        # noqa: BLE001
        spans = []

    if n <= 0:                    # 몇 토막인지 안 정했으면 **찾은 대로** 준다
        return [(a, b) for a, b in spans]
    # 토막이 사람 수보다 많으면, 사이가 가장 좁은 것부터 붙인다
    while len(spans) > n:
        gaps = [(spans[i + 1][0] - spans[i][1], i) for i in range(len(spans) - 1)]
        _, i = min(gaps)
        spans[i][1] = spans[i + 1][1]
        del spans[i + 1]

    if len(spans) != n:                                      # 못 찾았다 → 음절 수 비례
        return by_syllable(n, dur, spans_hint=None)
    return [(a, b) for a, b in spans]


def speech_spans(src, n, dur, lines=None):
    """자막을 켜 둘 시간. **말이 끊긴 사이에도 자막은 켜 둔다.**

    ⚠️ 소리를 놓을 때 이걸 쓰면 안 된다 — 첫 토막이 0초부터로 늘어나 있어서
       목소리가 **말하지도 않는 자리**에서 시작한다(실제로 그렇게 나왔다).
       소리를 놓을 때는 위의 `voiced_spans` 를 쓴다.
    """
    spans = voiced_spans(src, n, dur, lines)
    out = []
    for i, (a, b) in enumerate(spans):
        end = spans[i + 1][0] if i + 1 < len(spans) else dur
        out.append((0.0 if i == 0 else a, end))
    return out


def by_syllable(n, dur, lines=None, spans_hint=None):
    """음절 수에 비례해 시간을 나눈다 (소리에서 못 찾았을 때)."""
    w = [max(1, syl(x)) for x in (lines or [])] or [1] * n
    w = (w + [1] * n)[:n]
    tot = sum(w)
    out, t = [], 0.0
    for i, x in enumerate(w):
        end = dur if i == n - 1 else t + dur * x / tot
        out.append((t, end))
        t = end
    return out


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


def runs_of(t):
    """`앞 *가운데* 뒤` → [("앞 ", False), ("가운데", True), (" 뒤", False)]."""
    out, last, t = [], 0, str(t or "")
    for m in re.finditer(r"\*([^*]+)\*", t):
        if m.start() > last:
            out.append((t[last:m.start()], False))
        out.append((m.group(1), True))
        last = m.end()
    if last < len(t):
        out.append((t[last:], False))
    return [(x, e) for x, e in out if x] or [(t, False)]


def wrap_runs(d, runs, f, max_w):
    """토막(강조/보통)을 지킨 채 줄바꿈한다. 한 줄 = [(글자, 강조인가), …].

    ⚠️ 처음에는 낱말 단위로 잘랐다가 **띄어쓰기가 사라지고** 줄이 엉뚱하게
       갈렸다(`보험금15억도 그` / `여자 앞으로였다`). 강조 토막이 낱말
       한가운데를 가르기 때문이다(`*15억*도`). 그래서 **글자 단위**로 재고
       띄어쓰기에서만 줄을 바꾼다.
    """
    ch = [(c, e) for text, e in runs for c in str(text)]
    out, i = [], 0
    while i < len(ch):
        j, last_sp = i, -1
        while j < len(ch):
            w = d.textlength("".join(c for c, _ in ch[i:j + 1]), font=f)
            if w > max_w and j > i:
                break
            if ch[j][0] == " ":
                last_sp = j
            j += 1
        if j >= len(ch):
            out.append(ch[i:])
            break
        if last_sp > i:
            out.append(ch[i:last_sp])
            i = last_sp + 1
        else:
            out.append(ch[i:j])
            i = j
    lines = []
    for seg in out:
        while seg and seg[0][0] == " ":
            seg = seg[1:]
        while seg and seg[-1][0] == " ":
            seg = seg[:-1]
        merged = []
        for c, e in seg:
            if merged and merged[-1][1] == e:
                merged[-1] = (merged[-1][0] + c, e)
            else:
                merged.append((c, e))
        if merged:
            lines.append(merged)
    return lines or [[("", False)]]


def block_runs(d, lines, font, top, bottom, fill, hi, gap):
    """토막마다 색을 달리해 가운데 맞춰 그린다."""
    lh = int(font.size * gap)
    y = top + max(0, (bottom - top - lh * len(lines)) // 2)
    for ln in lines:
        wsum = sum(d.textlength(x, font=font) for x, _ in ln)
        x = (W - wsum) / 2
        for text, emph in ln:
            d.text((x, y), text, font=font, fill=(hi if emph else fill))
            x += d.textlength(text, font=font)
        y += lh


def fit_box_runs(d, text, path, max_w, max_h, big, small, gap, max_lines):
    """강조 토막을 지킨 채 **상자에 꽉 차는 가장 큰 크기**를 찾는다."""
    runs = runs_of(text)
    f = ImageFont.truetype(str(path), small)
    got = wrap_runs(d, runs, f, max_w)
    for size in range(int(big), int(small) - 1, -2):
        f2 = ImageFont.truetype(str(path), size)
        ls = wrap_runs(d, runs, f2, max_w)
        if len(ls) > max_lines:
            continue
        if len(ls) * int(size * gap) <= max_h:
            return f2, ls
    return f, got[:max_lines]


def fit_box(draw, text, path, max_w, max_h, big, small, gap, max_lines):
    """**상자에 꽉 차는 가장 큰 크기**를 찾는다 (후킹용).

    ⚠️ fit() 은 정해진 크기에서 **줄이기만** 한다. 후킹은 반대로 키워야 한다 —
       짧은 후킹은 크게, 긴 후킹은 알아서 작게. 너비·줄 수·**상자 높이**를
       모두 보고 들어가는 가장 큰 크기를 고른다.
    """
    t = str(text or "")
    f = ImageFont.truetype(str(path), small)
    ls = wrap(draw, t, f, max_w)
    for size in range(int(big), int(small) - 1, -2):
        f2 = ImageFont.truetype(str(path), size)
        got = wrap(draw, t, f2, max_w)
        if len(got) > max_lines:
            continue
        if len(got) * int(size * gap) <= max_h:
            return f2, got
    return f, ls[:max_lines]


def fit_owned(draw, parts, path, size, max_w, max_lines):
    """사람별 대사 목록 → (글꼴, 화면에 그릴 줄들, 줄마다 누구 말인지).

    한 사람 대사가 길어 두 줄로 접히면 **그 두 줄이 같이 켜져야** 한다.
    그래서 줄마다 임자 번호를 함께 돌려준다."""
    while size >= 26:
        f = ImageFont.truetype(str(path), size)
        ls, owner = [], []
        for i, x in enumerate(parts):
            for l in wrap(draw, x, f, max_w):
                ls.append(l)
                owner.append(i)
        if len(ls) <= max_lines:
            return f, ls, owner
        size -= 4
    return f, ls[:max_lines], owner[:max_lines]


def block(d, lines, font, top, bottom, fill, gap=1.28, live=None, dim=None):
    """정해진 칸 안에서 가운데 맞춰 그린다.

    live — 지금 말하는 사람의 줄 번호. 그 줄만 밝게, 나머지는 흐리게 그린다
           (2026-08-20 운영자: "자막은 사람마다 가라오케 식으로").
           줄 전체를 미리 보여주되 **읽을 자리를 눈이 놓치지 않게** 한다.
    """
    lh = int(font.size * gap)
    total = lh * len(lines)
    y = top + max(0, (bottom - top - total) // 2)
    for i, l in enumerate(lines):
        c = fill if (live is None or i == live) else (dim or DIM)
        x = (W - d.textlength(l, font=font)) / 2
        d.text((x, y), l, font=font, fill=c)
        y += lh


def _runs(w):
    """[9, 11, 8] → [(0,9), (9,20), (20,28)] — 이어지는 몫으로 바꾼다."""
    out, t = [], 0
    for x in w:
        out.append((t, t + x))
        t += x
    return out


def sub_lines(sub):
    """자막을 말한 사람마다 한 줄로 나눈다."""
    return [x.strip() for x in str(sub or "").split(" / ") if x.strip()]


SPLIT_OVER = 16          # 이보다 길면 한 사람 말도 반으로 끊어 띄운다 (음절)


def halve(t):
    """긴 대사를 읽기 좋은 토막으로 끊는다.

    ⚠️ 처음엔 '가운데에서 반으로' 잘랐는데 9음절 + 19음절 처럼 치우쳤다.
       한 문장을 억지로 자르는 것보다 **문장 단위로 끊는 쪽**이 자연스럽고
       토막마다 말이 온전하다. 문장이 하나뿐이고 길면 그때만 반으로 가른다.
    """
    t = t.strip()
    if syl(t) <= SPLIT_OVER:
        return [t]

    # ① 문장 단위 (마침표·물음표·느낌표 뒤)
    sent = [x.strip() for x in re.split(r"(?<=[.!?…])\s+", t) if x.strip()]
    if len(sent) >= 2:
        return sent[:3] if len(sent) <= 3 else [
            " ".join(sent[:len(sent) // 2]), " ".join(sent[len(sent) // 2:])]

    # ② 문장이 하나뿐 → 소리 나는 양이 고르게 갈리는 띄어쓰기에서
    total = syl(t)
    spots = [m.end() for m in re.finditer(r"\s+", t)]
    spots = [i for i in spots if 1 < i < len(t) - 1]
    if not spots:
        return [t]
    bp = min(spots, key=lambda i: abs(syl(t[:i]) - (total - syl(t[:i]))))
    return [t[:bp].strip(), t[bp:].strip()]


def sub_chunks(sub):
    """화면에 **한 번에 하나씩** 띄울 토막들.

    ⚠️ 2026-08-20 운영자: "가라오케 자막은 저렇게 모든 대사가 한 번에 다 뜨지
       않아. 해당 인물만 뜨게 하거나 반 문장씩 뜨게 하거나."
       맞다. 세 줄을 다 띄워 놓고 밝기만 바꾸면 화면이 글자로 꽉 차고,
       아직 안 한 말까지 미리 보여 김이 샌다.

    · 여러 사람이 주고받는 컷 → **말하는 사람 것만** 한 줄씩
    · 한 사람이 길게 말하는 컷 → **반 문장씩** 두 토막으로
    """
    parts = sub_lines(sub)
    if len(parts) == 1 and syl(parts[0]) > SPLIT_OVER:
        return halve(parts[0]), True
    return parts, False


def overlay_png(hook, chunk, out):
    """글자만 있는 투명 그림 한 장 (영상 위에 얹는다).

    chunk — 지금 화면에 띄울 자막 **한 토막**. 나머지는 안 그린다
            (2026-08-20 운영자: "모든 대사가 한 번에 다 뜨지 않아").
    """
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    mark = ImageFont.truetype(str(FONT_B), MARK_SIZE)
    d.text((W - SIDE - d.textlength(CHANNEL, font=mark), MARK_Y),
           CHANNEL, font=mark, fill=GOLD + (255,))

    if str(hook or "").strip():
        # ⭐ `*…*` 로 감싼 토막만 금색으로 (2026-08-21 운영자 지시)
        f, ls = fit_box_runs(d, hook, FONT_H, W - SIDE * 2,
                             HOOK_BOT - HOOK_TOP, HOOK_MAX, HOOK_MIN,
                             HOOK_GAP, 3)
        block_runs(d, ls, f, HOOK_TOP, HOOK_BOT, (255, 255, 255, 255),
                   HOOK_HI, HOOK_GAP)

    if str(chunk or "").strip():
        # 한 토막만 있으니 크게 쓸 수 있다 — 폰에서 읽기 훨씬 낫다
        f, ls = fit(d, chunk, FONT_M, SUB_SIZE, W - SIDE * 2, 2)
        block(d, ls, f, SUB_TOP, SUB_BOT, (245, 245, 250, 255))

    img.save(out)
    return out


LOUD_TARGET = -20.0     # 컷마다 맞출 평균 소리 크기(dB)
PEAK_LIMIT = -1.0       # 이보다 커지면 소리가 깨진다


def mean_db(path, ss=0.0, t=0.0):
    """그 토막의 평균 소리 크기(dB). 못 재면 None."""
    args = ["ffmpeg", "-hide_banner"]
    if ss:
        args += ["-ss", f"{float(ss):.3f}"]
    if t:
        args += ["-t", f"{float(t):.3f}"]
    args += ["-i", str(path), "-map", "0:a", "-af", "volumedetect",
             "-f", "null", "-"]
    err = subprocess.run(args, capture_output=True, text=True).stderr
    m = re.search(r"mean_volume: ([-\d.]+)", err)
    return float(m.group(1)) if m else None


def gain_for(src):
    """이 클립을 얼마나 키우거나 줄여야 다른 컷과 소리가 같아지는가.

    ⚠️ 2026-08-20 — 1화 완성본을 재보니 컷마다 평균 소리가
         -18.6 / -26.1 / -25.0 / -19.8 / -19.4 dB
       로 **7.5dB 나 차이났다.** 2·3컷만 확 작아 볼륨이 들쭉날쭉했다.
       플로우가 컷마다 따로 만들어 주므로 저절로는 안 맞는다.

    소리를 눌러 짜는(compressor) 대신 **크기만 옮긴다** — 원래 강약은 그대로
    두고, 다만 커져서 깨질 것 같으면 그만큼만 올린다.
    """
    err = subprocess.run(["ffmpeg", "-v", "info", "-i", str(src),
                          "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.search(r"mean_volume: ([-\d.]+)", err)
    x = re.search(r"max_volume: ([-\d.]+)", err)
    if not m:
        return 0.0
    mean, peak = float(m.group(1)), float(x.group(1)) if x else 0.0
    g = LOUD_TARGET - mean
    if peak + g > PEAK_LIMIT:
        g = PEAK_LIMIT - peak
    return round(g, 2)


# ⭐⭐ 2026-08-21 — **죽은 시간을 잘라 낸다.**
#    운영자가 같은 프롬프트를 제미나이에 넣어 받은 영상을 재 봤다 (10.005초):
#      0.00~1.13 무음 / 1.13~2.50 / 2.83~4.29 / 4.66~6.20 / **6.20~10.00 무음**
#    말한 시간은 4.37초 — 플로우 6초짜리(4.43초)와 **거의 같다.**
#    10초라서 천천히 말한 것이 아니라 **뒤에 3.8초를 그냥 비워 둔 것**이다.
#    (그러니 컷을 10초로 늘리는 것은 소용이 없다. 자연스러움의 차이는
#     길이가 아니라 목소리 모델 쪽에서 온다.)
#
#    → 앞뒤 죽은 시간을 잘라 내면 **10초짜리도 그대로 쓸 수 있고**,
#      플로우 6초짜리도 앞 1초가 사라져 훨씬 촘촘해진다.
HEAD_PAD = 0.25        # 첫 말 앞에 남겨 둘 숨
TAIL_PAD = 0.45        # 끝말 뒤에 남겨 둘 여운


def trim_dead(src, out):
    """앞뒤로 말이 없는 시간을 잘라 낸다. 자를 것이 없으면 원본을 그대로."""
    src, out = Path(src), Path(out)
    # ⚠️ 자르기는 **있으면 좋은 것**이지 없으면 안 되는 것이 아니다.
    #    클립을 못 읽는다고 여기서 죽으면 30초짜리 하나가 통째로 날아간다.
    #    못 하면 조용히 원본을 그대로 쓴다.
    try:
        dur = C.probe(src)[2]
        spans = voiced_spans(src, 0, dur)  # 있는 대로 다 찾는다
    except Exception:                                        # noqa: BLE001
        return src
    if not spans:
        return src
    a = max(0.0, spans[0][0] - HEAD_PAD)
    b = min(dur, spans[-1][1] + TAIL_PAD)
    if b - a < 1.0 or (a < 0.15 and dur - b < 0.15):
        return src                          # 자를 것이 없다
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", str(src),
         "-t", f"{b - a:.3f}", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
         str(out)], capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        return src
    print(f"    ✂️ 죽은 시간을 잘랐다 — {dur:.2f}초 → {b - a:.2f}초 "
          f"(앞 {a:.2f}초 · 뒤 {dur - b:.2f}초)")
    return out


# ⭐⭐ 2026-08-21 — 목소리를 **한국어 전용**으로 갈아 끼운다.
#    운영자: "외국인 노동자가 어설픈 한국말 하는 것 같아 ㅠㅠ"
#    영상 만드는 쪽의 한국어 발음은 프롬프트로 못 고친다(다 해 봤다).
#    다행히 실제 영상을 재 보니 **말하는 자리가 정확히 잡힌다** —
#      0.98~2.55 / 2.79~4.20 / 4.57~6.02
#    그 자리에 같은 대사를 한국어 목소리로 만들어 그대로 끼워 넣는다.
#    입은 이미 같은 한국어 대사로 움직이므로 입모양도 거의 맞는다.
#    ⚠️ 열쇠가 없으면 **아무것도 안 하고 원래 소리를 그대로 쓴다.**
#       (영상이 안 나오는 것보다 낫다)
# ⚠️ dia_turns 는 **대본 쪽(series.py)** 에 있다. 여기 두었더니 소리만
#    만드는 일에서 shorts 를 들여와야 했고, 그때 PIL 이 없다고 죽었다.
from series import dia_turns                                # noqa: E402,F401

def dub(src, turns, voices, out, tmp):
    """클립의 소리를 한국어 목소리로 갈아 끼운다. 못 하면 False."""
    if not turns or not tts.key():
        return False
    try:
        dur = C.probe(src)[2]
    except Exception:                                        # noqa: BLE001
        return False                       # 못 읽으면 원래 소리를 그대로 쓴다
    # ⚠️ 자막용(speech_spans)이 아니라 **실제로 말한 자리**를 써야 한다.
    #    자막용은 첫 토막이 0초부터로 늘어나 있어서, 그걸 쓰면 목소리가
    #    말하지도 않는 앞머리에서 시작한다 (실제로 그렇게 나왔다).
    spans = voiced_spans(src, len(turns), dur, [t for _, t in turns])
    if len(spans) != len(turns):
        spans = by_syllable(len(turns), dur, [t for _, t in turns])
    tmp.mkdir(parents=True, exist_ok=True)
    made = []
    for i, ((who, text), (a, b)) in enumerate(zip(turns, spans)):
        v = (voices.get(who) or voices.get(who.lower())
             or tts.best_voices("FEMALE")[0])
        # ⭐ 2026-08-21 — **입이 움직인 시간에 억지로 우겨넣지 않는다.**
        #    영상 만드는 쪽은 32음절을 4.4초에 쏟아냈다(초당 7.3음절).
        #    거기에 딱 맞추면 우리 한국어 목소리도 똑같이 급해져서, 애써
        #    바꾼 보람이 없다. 다음 사람이 말하기 직전까지가 **쓸 수 있는 시간**
        #    이므로, 말이 끊긴 사이까지 빌려 쓴다.
        room = (spans[i + 1][0] if i + 1 < len(spans) else dur) - a - 0.05
        try:
            p, d = tts.say_to_fit(text, v, max(0.6, b - a),
                                  tmp / f"{src.stem}_v{i}.wav",
                                  tts.tone_of(text), room=max(0.6, room))
        except Exception as e:                               # noqa: BLE001
            print(f"    ⚠️ 목소리 만들기 실패 ({e}) — 원래 소리를 쓴다")
            return False
        made.append((a, p, d))
        print(f"    🎙 {who}: {text[:18]}…  {a:.2f}초부터 {d:.2f}초")

    # ⭐⭐ 2026-08-22 — **원본이 말하던 크기에 맞춘다.**
    #    맞추지 않으면 우리 목소리만 동떨어진 크기로 얹혀서, 장면에 안 앉고
    #    나중에 덧붙인 소리처럼 들린다 (더빙처럼 들리는 까닭 중 하나다).
    #    이 클립은 원본이 말할 때 -13~-16dB 였다.
    tgt = None
    _d = [mean_db(src, a, b - a) for a, b in spans]
    _d = [x for x in _d if x is not None and x > -60]
    if _d:
        tgt = sum(_d) / len(_d)

    # 원래 소리는 **완전히 지우고**, 만든 목소리를 제자리에 얹는다
    args = ["ffmpeg", "-v", "error", "-y", "-i", str(src)]
    for _, p, _ in made:
        args += ["-i", str(p)]
    fil = [f"[0:a]volume=0,apad[bed]"]
    mix = "[bed]"
    for i, (a, _p, _) in enumerate(made):
        # ⚠️ 크게 올리다 깨지면 더 나쁘다. 올리고 내리는 폭을 묶어 둔다.
        g = 0.0
        if tgt is not None:
            own = mean_db(_p)
            if own is not None and own > -60:
                g = max(-10.0, min(10.0, tgt - own))
        vol = f"volume={g:.1f}dB," if abs(g) > 0.3 else ""
        fil.append(f"[{i + 1}:a]{vol}aresample=48000,"
                   f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
                   f"adelay={int(a * 1000)}|{int(a * 1000)}[d{i}]")
        mix += f"[d{i}]"
    fil.append(f"{mix}amix=inputs={len(made) + 1}:normalize=0:"
               f"duration=first[mixed]")
    args += ["-filter_complex", ";".join(fil),
             "-map", "0:v", "-map", "[mixed]",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
             "-t", f"{dur:.3f}", str(out)]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    ⚠️ 소리 갈아 끼우기 실패 — 원래 소리를 쓴다\n{r.stderr[:200]}")
        return False
    return True


def compose(src, hook, sub, out, tmp):
    """받은 클립 한 개 → 쇼츠 한 컷 (워터마크 지우고 4:3 자르고 글자 얹기)."""
    src, out, tmp = Path(src), Path(out), Path(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    vw, vh, sec = C.probe(src)
    mx, my, mw, mh = C.mark_box(vw, vh)
    cx, cy, cw, ch = C.crop_box(vw, vh)

    # ⭐ 자막은 **한 토막씩** 뜬다 (말하는 사람 것만 / 긴 대사는 반 문장씩).
    #    말하는 시각은 소리에서 찾는다.
    chunks, halved = sub_chunks(sub)
    people = len(sub_lines(sub))
    if halved:
        # 한 사람이 길게 말하는 컷 — 그 사람이 말하는 동안을 음절 수로 나눈다
        base = speech_spans(src, 1, sec)[0]
        spans = [(base[0] + (base[1] - base[0]) * a / max(1, sum(map(syl, chunks))),
                  base[0] + (base[1] - base[0]) * b / max(1, sum(map(syl, chunks))))
                 for a, b in _runs([syl(c) for c in chunks])]
    else:
        spans = speech_spans(src, people, sec)
        if len(spans) != len(chunks):
            spans = by_syllable(len(chunks), sec, chunks)
    spans[-1] = (spans[-1][0], sec)          # 마지막은 끝까지 남긴다
    pngs = [overlay_png(hook, c, tmp / f"{src.stem}_txt{i}.png")
            for i, c in enumerate(chunks or [""])]

    vf = [f"[1:v]delogo=x={mx}:y={my}:w={mw}:h={mh},"
          f"crop={cw}:{ch}:{cx}:{cy},scale={W}:{VIDEO_H}[v]",
          f"[0:v][v]overlay=0:{VIDEO_Y}[s0]"]
    for i in range(len(pngs)):
        a, b = spans[i] if i < len(spans) else (0.0, sec)
        last = (i == len(pngs) - 1)
        tag = "[o]" if last else f"[s{i + 1}]"
        en = "" if len(pngs) == 1 else f":enable='between(t,{a:.3f},{b:.3f})'"
        vf.append(f"[s{i}][{i + 2}:v]overlay=0:0{en}{tag}")
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r=24:d={sec:.3f}",
           "-i", str(src)]
    for q in pngs:
        cmd += ["-i", str(q)]
    # 소리: 컷마다 크기를 맞추고, 앞뒤 0.05초를 부드럽게 (이어 붙일 때 '툭' 소리 방지)
    g = gain_for(src)
    af = (f"volume={g}dB,afade=t=in:st=0:d=0.05,"
          f"afade=t=out:st={max(0, sec - 0.05):.3f}:d=0.05")
    cmd += ["-filter_complex", ";".join(vf), "-map", "[o]", "-map", "1:a?",
            "-af", af,
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


STOP = {"the", "a", "an", "at", "in", "on", "of", "to", "her", "his", "and",
        "with", "by", "from", "into", "over", "as", "is", "it", "for"}


def words(t):
    """영어 낱말만 뽑고 꼬리를 떼어 맞춰 본다 (glaring↔glares, shakes↔shake)."""
    out = set()
    for w in re.findall(r"[A-Za-z]+", str(t or "").lower()):
        if len(w) < 3 or w in STOP:
            continue
        for suf in ("ingly", "ing", "edly", "ed", "ly", "es", "s"):
            if len(w) > len(suf) + 2 and w.endswith(suf):
                w = w[: -len(suf)]
                break
        out.add(w)
    return out


def pick_clips(d, n, cuts=None):
    """받은 파일들을 컷 번호에 맞춘다.

    플로우에서 내려받은 이름은 제각각이라 한 가지 규칙만 믿으면 안 된다.
      ① 이름 안에 c001 · c1 같은 컷 번호가 있으면 그것으로 (가장 확실)
      ② 없으면 **파일 이름과 컷 내용을 맞춰** 짝짓는다.
      ③ 그래도 못 정한 것은 남은 것끼리 순서대로

    ⚠️ 2026-08-20 — 처음엔 ②가 없이 '이름 순서대로' 였는데, 실제로 올라온
       플로우 파일 이름이 이랬다:
         Husband_aggressively_shakes_off…   ← 2컷
         Man_glaring_coldly…                ← 4컷
         Wife_confronts_husband_at_home…    ← 1컷
         Woman_clenches_fists_determinedly… ← 5컷
         Woman_smirks_at_another_woman…     ← 3컷
       이름 순서대로 붙이면 2·4·1·5·3 — **통째로 어긋난다.**
       다행히 플로우는 우리가 쓴 ACTION 을 보고 이름을 짓는다
       (shakes off · glaring coldly · clenches fists · smirks). 그 낱말을 맞춘다.
    """
    d = Path(d)
    vids = sorted([p for p in d.rglob("*") if p.suffix.lower() in
                   (".mp4", ".mov", ".m4v", ".webm") and not p.name.startswith("._")])
    out = {}
    for p in vids:
        m = re.search(r"c(?:ut)?[ _-]?(\d{1,3})(?!\d)", p.stem, re.I)
        if m:
            k = int(m.group(1))
            if 1 <= k <= n and k not in out:
                out[k] = p

    left_f = [p for p in vids if p not in out.values()]
    left_k = [k for k in range(1, n + 1) if k not in out]

    # ② 이름과 컷 내용을 맞춘다
    if cuts and left_f and left_k:
        key = {}
        for c in cuts:
            k = int(c.get("n", 0))
            lines = str(c.get("prompt") or "").split("\n")
            act = next((l for l in lines if l.startswith("ACTION:")), "")
            shot = next((l for l in lines if l.startswith("SHOT:")), "")
            key[k] = words(act) | words(shot)
        pairs = sorted(
            ((len(key.get(k, set()) & words(f.stem)), k, f)
             for k in left_k for f in left_f), reverse=True,
            key=lambda x: (x[0], -x[1]))
        for sc, k, f in pairs:
            if sc <= 0 or k not in left_k or f not in left_f:
                continue
            out[k] = f
            left_k.remove(k)
            left_f.remove(f)

    # ③ 남은 것끼리 순서대로
    for k in list(left_k):
        if left_f:
            out[k] = left_f.pop(0)
    return out


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

    files = pick_clips(clips_dir, len(ep["cuts"]), ep["cuts"])
    voices = tts.pick_voices(doc.get("characters"))
    if tts.key():
        print(f"  🎙 목소리를 갈아 끼운다 — {tts.engine_note()}")
    else:
        print("  (목소리 열쇠가 없어 원래 소리를 그대로 쓴다 —\n           GEMINI_API_KEY 나 GOOGLE_TTS_KEY 가 있어야 한다)")
    parts = []
    for c in ep["cuts"]:
        n = int(c["n"])
        src = files.get(n)
        if not src:
            raise SystemExit(f"❌ {n}컷 클립이 없다 ({clips_dir})")
        # ⭐ ① 앞뒤 죽은 시간을 먼저 잘라 낸다 (플로우 6초짜리의 앞 1초 무음,
        #      제미나이 10초짜리의 뒤 3.8초 무음이 그대로 나가면 안 된다)
        src = trim_dead(src, tmp / f"cut{n}_tight.mp4")
        # ⭐ ② 소리를 갈아 끼우고, ③ 그 다음에 자막·크롭을 얹는다.
        #    (자막이 **말하는 자리**를 소리에서 찾으므로 순서가 중요하다)
        dubbed = tmp / f"cut{n}_ko.mp4"
        if dub(src, dia_turns(c.get("prompt")), voices, dubbed, tmp):
            src = dubbed
        d = compose(src, hook, c.get("subtitle"), tmp / f"cut{n}.mp4", tmp)
        parts.append(d)
        print(f"  ✅ {n}컷 ← {files[n].name}  (소리 {gain_for(src):+.1f}dB)")

    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    final = out_dir / f"{sid}_ep{int(no):02d}_short.mp4"
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(lst), "-c", "copy", "-movflags", "+faststart",
                        str(final)], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"이어 붙이기 실패:\n{p.stderr[:400]}")
    total = sum(C.probe(p)[2] for p in parts)
    won = tts.bill_flush(f"{sid} {no}화")
    print(f"\n✅ {final.name} — {len(parts)}컷 · {total:.1f}초"
          + (f" · 목소리 값 {won:.0f}원" if won else ""))
    return final


def one(clip, sid, no, cut, hook, sub, out_dir):
    """클립 **하나**로 쇼츠를 만들어 본다 — 한 화 만들 때와 똑같은 차례로.

    ⚠️⚠️ 2026-08-21 사고 — 예전에 여기서 compose() 만 불렀다. 그러면 소리를
       **안 갈아 끼운다.** 그런데 화면은 멀쩡히 나오니 다 된 줄 알고 운영자에게
       보냈고, 운영자는 한동안 플로우가 만든 외국인 같은 소리를 듣고 있었다.
       미리보기가 진짜와 다른 길로 가면, 미리보기는 거짓말이 된다.
       → 여기서도 episode() 와 **똑같이** ① 잘라내기 ② 소리 갈아 끼우기
         ③ 자막·크롭 을 다 한다.
    """
    clip = Path(clip)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / "_tmp"
    turns, voices = [], {}
    if sid and no and cut:
        # 대본에서 이 컷의 후킹·자막·대사를 그대로 가져온다
        doc = json.loads((ROOT / "data" / "series" / f"{sid}.json")
                         .read_text(encoding="utf-8"))
        ep = next((e for e in doc["episodes"]
                   if int(e.get("no", 0)) == int(no)), None)
        if not ep:
            raise SystemExit(f"❌ {sid} 에 {no}화가 없다")
        c = next((x for x in ep["cuts"] if int(x["n"]) == int(cut)), None)
        if not c:
            raise SystemExit(f"❌ {no}화에 {cut}컷이 없다")
        hook = hook or hook_of(ep, doc)
        sub = sub or c.get("subtitle") or ""
        turns = dia_turns(c.get("prompt"))
        voices = tts.pick_voices(doc.get("characters"))
        print(f"{sid} {no}화 {cut}컷 「{ep.get('title','')}」")
    print(f"  후킹 문구: {hook}")
    for who, text in turns:
        print(f"    {who}: {text}")

    # ⭐ ① 앞뒤 죽은 시간부터 잘라 낸다
    src = trim_dead(clip, tmp / "tight.mp4")
    # ⭐ ② 소리를 갈아 끼운다
    if not turns:
        print("  ⚠️ 대사를 못 찾아 **원래 소리를 그대로 쓴다.**\n"
              "     --sid S001 --no 1 --cut 1 처럼 어느 컷인지 알려 주면 갈아 끼운다")
    elif not tts.key():
        print("  ⚠️ 목소리 열쇠가 없어 **원래 소리를 그대로 쓴다** —\n"
              "     GEMINI_API_KEY 나 GOOGLE_TTS_KEY 가 있어야 한다")
    else:
        print(f"  🎙 목소리를 갈아 끼운다 — {tts.engine_note()}")
        dubbed = tmp / "ko.mp4"
        if dub(src, turns, voices, dubbed, tmp):
            src = dubbed
        else:
            print("  ⚠️ 갈아 끼우기가 안 됐다 — 원래 소리가 그대로 나간다")
    # ⭐ ③ 그 다음에 자막·크롭을 얹는다
    out = out_dir / (clip.stem + "_short.mp4")
    compose(src, hook, sub, out, tmp)
    won = tts.bill_flush(f"{sid or '?'} {no or '?'}화 {cut or '?'}컷 시험")
    print(f"\n✅ {out} — {C.probe(out)[2]:.1f}초 · 소리 {gain_for(out):+.1f}dB"
          + (f" · 목소리 값 {won:.0f}원" if won else ""))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sid", nargs="?", default="")
    ap.add_argument("no", nargs="?", default="")
    ap.add_argument("--clips", default="build/clips")
    ap.add_argument("--out", default="build/shorts")
    ap.add_argument("--demo", default="", help="클립 하나로 쇼츠를 만들어 본다")
    ap.add_argument("--cut", default="", help="--demo 때 몇 컷인지 (대사를 가져온다)")
    ap.add_argument("--hook", default="")
    ap.add_argument("--sub", default="")
    a = ap.parse_args()
    if a.demo:
        return one(a.demo, a.sid, a.no, a.cut, a.hook, a.sub, a.out)
    if not a.sid or not a.no:
        ap.error("시리즈 번호와 화 번호를 달라 (예: S001 1)")
    episode(a.sid, a.no, a.clips, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
