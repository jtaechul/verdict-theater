#!/usr/bin/env python3
"""⭐ 미끼 쇼츠 — 긴 영상(본편)에 쓴 영상 조각으로 짓는 30초 세로 쇼츠 (2026-10-06 신설)

    python3 tools/teaser.py S96 plan               0원 — 편마다 박자표(말 · 영상 조각 · 길이) · 빠진 재료 · 값 어림
    python3 tools/teaser.py S96 preview --part 1   맛보기 0원 — 목소리 자리는 무음(글자 잣대 길이) · 화면은 진짜
                                                    → build/s90/teaser/S96/preview_part1.mp4 (만든 기록 안 남김)
    python3 tools/teaser.py S96 voice --part 1     나레이션 (같은 지문은 0원 · 한 편 약 50~110원 · 장부에 적는다)
    python3 tools/teaser.py S96 build --part 1     조립 0원 → build/s90/S96_part1.mp4 · .jpg (+ 만든 기록)
    python3 tools/teaser.py S96 sheet --part 1     검수 0원 — 첫 3초 · 박자마다 · 끊는 자리 · 끝 화면을 한 장에
                                                    (--preview : 맛보기 영상을 본다)

⭐⭐⭐ 2026-10-06 손님 (S95 본편을 올린 뒤 · 쇼츠 제안을 네 번 물리셨다):
    "되게 재미없어 보이는데 … 자극적으로 유인할 수 있게끔 궁금증을 유발하게끔 … 충격적인 내용이"
    "본 영상으로 유인할 만한 요소가 단 하나도 없는 것 같은데"
    "퀴즈 하지마 정답 본편 땡분 땡초 이런거 하지마 … 쇼킹해가지고서 처음 3초 동안은 절대 …
     건너뛰기 하지 않을 … 그런 상황을 부여하고 호기심 마지막까지 부여해서 본 영상으로 유입되게끔"
    → 짓는 법 (대본 data/series/S96.json 이 본보기):
      · 한 편에 **충격 하나** — 첫 화면(0.0초)부터 얼굴 + 목소리 + 서류 쪽지의 빨간 도장 한 줄이 '쾅'
        (검은 화면 없음 · 첫 장면에 이미 도장이 떠 있다가 0.1초에 내려찍힌다)
      · 끝까지 궁금하게 — 숫자는 서넛까지 · 30초 안팎 · **말 한복판에서 끊는다**(그 답은 본편에 있다)
      · 끝 화면 = 본편 썸네일 + 「이 이야기의 끝은 본편에서」 + 아래 영상 링크를 가리키는 화살표
      · 퀴즈 · "정답은 본편 몇 분 몇 초" 는 **쓰지 않는다** (check 가 막는다) · 판결문에 없는 일은 지어내지 않는다
      · 영상은 **새로 사지 않는다** — 본편 영상 조각(S95 video60 cNN.mp4)을 세로로 다시 짠다 (0원)
      · 대사는 본편 대사 영상의 소리 그대로(입이 맞는다) · 나레이션만 새로 만든다 (본편과 같은 성우)

세로 화면 (1080×1920)
    맨 위 — 채널 이름 · 「살아 계신 아버지 땅 등기부에」(첫 화면부터) + 작은 서류 쪽지 (첫 도장이 날아와 앉는다)
    가운데 — 본편 영상(16:9)을 1080×1000 으로 잘라 키운다 (컷마다 얼굴 자리 x·y · 천천히 다가간다)
             뒤는 같은 영상을 흐리고 어둡게 깐다 (검은 띠 없음)
    아래 — 자막 한 토막씩 (92px · 금색 말은 한 토막 안에) · 대사면 이름표(금색 막대)
    ⚠️ 아래 300px 은 쇼츠 단추·제목 자리라 비운다 (short90 SUB_BOT 과 같은 까닭)
"""
import argparse
import io
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))


def _sid_from_argv():
    for a in sys.argv[1:]:
        if re.fullmatch(r"[Ss]\d{1,4}", a):
            return a.upper()
    return ""


# ⚠️ short90 은 불러오는 순간 사건(VT_SID)을 잡는다 — 그 전에 정해 둔다
if _sid_from_argv():
    os.environ["VT_SID"] = _sid_from_argv()

from PIL import (Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter,  # noqa: E402
                 ImageFont)

import reuse                                                   # noqa: E402
import short90 as S9                                           # noqa: E402
import story90 as ST90                                         # noqa: E402

FORMAT = "teaser"
W, H, FPS = 1080, 1920, 30
OUT = ROOT / "build" / "s90"
FONT_SUB = S9.FONT_SUB                         # 나눔고딕 엑스트라볼드 (쇼츠 자막과 같다)
FONT_SERIF = S9.FONT_NAME                      # KoPub 바탕 볼드 (이름표 · 도장)
GOLD, GOLD_BRIGHT = S9.GOLD, S9.GOLD_BRIGHT
RED = (200, 28, 34)                            # 도장 인주색

# ── 자리 (세로) ────────────────────────────────────────────────
FG_Y, FG_W, FG_H = 440, 1080, 1000             # 본편 영상을 앉히는 칸
HEAD_Y = 196                                   # 맨 위 한 줄 (유튜브 앱 위 단추 180px 아래)
HEAD_SIZE = 50
HEAD_STAMP = 0.36                              # 맨 위에 앉는 쪽지 크기 (첫 도장 대비)
HEAD_STAMP_Y = 352
STAMP_W = 940                                  # 첫 도장(서류 쪽지) 너비 — 화면 1080 안에
SUB_Y = 1528                                   # 자막 가운데 (영상 칸 아래 · 쇼츠 단추 300px 위)
SUB_SIZE = 92
SUB_W = 900                                    # 오른쪽 좋아요·댓글 단추 줄을 피한다
TAG_Y = FG_Y + FG_H - 96                       # 대사 이름표 (영상 칸 왼쪽 아래)
MARK_Y, MARK_SIZE = 44, 34
STAMP_Y = FG_Y + int(FG_H * 0.70)              # 첫 도장 가운데 (얼굴 아래 · 가슴께)

# ── 시간 ──────────────────────────────────────────────────────
LEAD = 0.10                                    # 첫 말이 나오는 때 (도장이 앉는 순간과 같다)
GAP = 0.18                                     # 말과 말 사이 (미끼 쇼츠는 숨 가쁘게)
STAMP_IN = 0.10                                # 첫 장면에 떠 있던 도장이 내려찍히는 때
FLASH_SEC = 0.12                               # 찍힐 때 번쩍
SHAKE_SEC, SHAKE_PX = 0.42, 16                 # 찍힌 뒤 화면 흔들림
FLY_SEC = 0.36                                 # 도장이 맨 위로 날아가 앉는 시간
FLY_ARC = 300                                  # 날아갈 때 오른쪽으로 비켜 가는 폭 (얼굴을 안 덮는다)
STRETCH_MAX = 1.4                              # 영상이 모자라면 화면만 이만큼까지 느리게 (그다음은 멈춤)
TALK_PRE, TALK_POST = 0.08, 0.10               # 대사 소리 — 말 앞뒤로 남기는 숨
CLIFF_BLACK = 0.24                             # 말 한복판에서 끊은 뒤 까만 화면 (판사봉 '쾅')
END_SEC = 1.9                                  # 끝 화면
VOICE_DB = -16.0                               # 말소리 평균 크기 — 나레이션과 대사 영상 소리를 맞춘다
BGM_VOL = 0.30
SFX = ROOT / "assets" / "sfx"
BGM_DIR = ROOT / "assets" / "bgm"
NARR_VOICE = S9.VOICE["나레이션"]               # 본편과 같은 성우 (Alnilam)
WON_PER_CHAR = 0.5                             # 목소리 어림 (S95 실측 약 0.44원/자 · 넉넉히)

# 효과음 (파일, 소리 크기, 잘라 쓸 시작, 길이) — 봉우리 자리는 src/render.py 실측을 따른다
FX = {
    "stamp": ("stamp", 1.7, 0.0, 0.50),
    "hit": ("tr_act", 0.55, 0.40, 2.20),       # 0.5초 봉우리 → 앞을 잘라 도장 순간에 맞춘다
    "twist": ("tr_twist", 0.30, 0.15, 2.40),
    "paper": ("paper", 0.9, 0.0, 0.55),
    "gavel": ("gavel", 2.0, 0.0, 0.63),
    "boom": ("tr_flash_out", 0.70, 0.40, 1.60),
}


class TeaserError(RuntimeError):
    pass


# ── 대본 ──────────────────────────────────────────────────────
def doc_path(sid):
    return ROOT / "data" / "series" / f"{sid}.json"


def load(sid):
    f = doc_path(sid)
    if not f.exists():
        raise TeaserError(f"data/series/{sid}.json 이 없다")
    doc = json.loads(f.read_text(encoding="utf-8"))
    if doc.get("format") != FORMAT:
        raise TeaserError(f"{sid} 는 미끼 쇼츠 대본이 아니다 (format={doc.get('format')!r})")
    return doc


def source_doc(doc):
    """본편 대본 (영상 조각 · 대사 · 인물이 거기서 온다)."""
    f = doc_path(str(doc.get("source") or ""))
    if not f.exists():
        raise TeaserError(f"본편 대본 {f.name} 이 없다")
    return json.loads(f.read_text(encoding="utf-8"))


def parts_of(doc):
    return [dict(p) for p in doc.get("parts") or []]


def part_of(doc, no):
    for p in parts_of(doc):
        if int(p["no"]) == int(no):
            return p
    raise TeaserError(f"{no}편이 대본에 없다")


def part_cuts(doc, part):
    a, b = part["cuts"]
    return [c for c in doc["cuts"] if a <= c["n"] <= b]


def is_talk(c):
    return bool(c.get("talk"))


def text_of(c):
    return str(c["turns"][0][1])


QUIZ = re.compile(r"(정답|몇\s*분\s*몇\s*초|\d+\s*분\s*\d+\s*초|\d+:\d\d|퀴즈|맞혀)")


def check(doc):
    """대본 검사 (0원) — 어긋난 것들 [글]. 만들기 전에 늘 돈다."""
    bad = []
    try:
        src = source_doc(doc)
    except TeaserError as e:
        return [str(e)]
    by_n = {c["n"]: c for c in src.get("cuts") or []}
    seen = set()
    for c in doc.get("cuts") or []:
        n = c.get("n")
        if n in seen:
            bad.append(f"컷{n}: 번호가 겹친다")
        seen.add(n)
        if not c.get("turns") or not str(c["turns"][0][1]).strip():
            bad.append(f"컷{n}: 말이 없다")
            continue
        if str(c.get("text") or "") != text_of(c):
            bad.append(f"컷{n}: text 와 turns 의 말이 다르다")
        s = by_n.get(c.get("clip"))
        if not s:
            bad.append(f"컷{n}: 본편에 컷{c.get('clip')} 이 없다")
            continue
        if s.get("fig"):
            bad.append(f"컷{n}: 본편 컷{c['clip']} 은 그림 컷이다 (얼굴 영상만 쓴다)")
        if is_talk(c):
            # ⭐ 대사는 본편 대사 영상의 소리 그대로다 — 글이 한 글자라도 다르면 자막이 소리와 어긋난다
            if S9.is_narr(s):
                bad.append(f"컷{n}: 본편 컷{c['clip']} 은 나레이션 컷이다 (대사 영상이 아니다)")
            elif str(s["turns"][0][1]) != text_of(c):
                bad.append(f"컷{n}: 대사가 본편 컷{c['clip']} 과 다르다 — "
                           f"「{text_of(c)}」 vs 「{s['turns'][0][1]}」")
            if not c.get("tag"):
                bad.append(f"컷{n}: 대사인데 이름표(tag)가 없다")
        elif not S9.is_narr(s):
            # 나레이션을 입이 움직이는 대사 영상 위에 얹으면 남이 말하는 것처럼 보인다
            bad.append(f"컷{n}: 나레이션인데 본편 컷{c['clip']} 은 대사 영상이다 (입이 움직인다)")
        if QUIZ.search(text_of(c)):
            bad.append(f"컷{n}: 퀴즈 · '정답은 본편 몇 분 몇 초' 는 쓰지 않는다 (손님 2026-10-06)")
    for p in parts_of(doc):
        cs = part_cuts(doc, p)
        if not cs:
            bad.append(f"{p['no']}편: 컷이 없다")
            continue
        if not cs[-1].get("cliff"):
            bad.append(f"{p['no']}편: 마지막 컷이 말 한복판에서 끊기지 않는다 (cliff)")
        if any(c.get("cliff") for c in cs[:-1]):
            bad.append(f"{p['no']}편: 끊는 컷(cliff)은 마지막 컷 하나뿐이다")
        if not cs[0].get("stamp"):
            bad.append(f"{p['no']}편: 첫 컷에 도장(stamp)이 없다 — 첫 3초 충격")
        if is_talk(cs[0]):
            bad.append(f"{p['no']}편: 첫 컷은 나레이션이다 (도장과 함께 말이 0.1초에 나온다)")
        if not p.get("stamp") or not p.get("head") or not p.get("end"):
            bad.append(f"{p['no']}편: stamp · head · end 글이 다 있어야 한다")
        for k in ("stamp", "head", "end", "end_note"):
            v = p.get(k) or ""
            if QUIZ.search(" ".join(v) if isinstance(v, list) else str(v)):
                bad.append(f"{p['no']}편 {k}: 퀴즈 · 시각 안내는 쓰지 않는다")
    return bad


# ── 재료 ──────────────────────────────────────────────────────
def work(sid):
    d = OUT / "teaser" / sid
    d.mkdir(parents=True, exist_ok=True)
    return d


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise TeaserError(f"{cmd[0]} 실패:\n{p.stderr[-900:]}")
    return p.stdout


def dur_of(p):
    return S9.dur_of(p)


_SIZES = {}


def size_of(p):
    k = str(p)
    if k not in _SIZES:
        out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                   "stream=width,height", "-of", "csv=p=0:s=x", str(p)])
        _SIZES[k] = tuple(int(x) for x in out.strip().split("x")[:2])
    return _SIZES[k]


def clip_of(doc, c):
    """본편 영상 조각 — **처음 쓸 때 작업 칸으로 떠 둔다** (0원).
    ⚠️ build/s90/video60/cNN.mp4 는 사건이 함께 쓰는 자리라 다음 사건을 만들면 덮인다.
       본편 것(가로 16:9)인지 보고 떠 두면, 그다음부터는 떠 둔 것만 쓴다."""
    src = work(doc["sid"]) / "src"
    src.mkdir(exist_ok=True)
    mine = src / f"c{int(c['clip']):02d}.mp4"
    if mine.exists():
        return mine
    f = S9.video_dir() / f"c{int(c['clip']):02d}.mp4"
    if not f.exists():
        raise TeaserError(f"본편 영상 조각 {f.relative_to(ROOT)} 이 없다 — 본편을 먼저 만든다")
    w, h = size_of(f)
    if w <= h:
        raise TeaserError(f"{f.name} 이 세로 영상이다 ({w}×{h}) — 본편(가로)이 아닌 다른 사건 것이다")
    shutil.copy2(f, mine)
    return mine


def mean_db(p, ss=0.0, t=None):
    cmd = ["ffmpeg", "-v", "info", "-ss", f"{ss:.3f}", "-i", str(p)]
    if t:
        cmd += ["-t", f"{t:.3f}"]
    cmd += ["-vn", "-af", "volumedetect", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else VOICE_DB


def narr_say(doc):
    return str(doc.get("narr_say") or "긴장감 있는 사연을 전하는 낮고 묵직한 목소리로, 또렷하게")


def voice_sig(c, doc):
    return reuse.sig_of("teaser-narr", text_of(c), NARR_VOICE, S9.NARR_RATE, narr_say(doc))


def voice_file(doc, c):
    return work(doc["sid"]) / "voice" / f"v{c['n']:02d}.wav"


def voice_ok(doc, c):
    f = voice_file(doc, c)
    return f.exists() and reuse.can_reuse(f, voice_sig(c, doc))[0]


def trim_wav(w):
    """목소리 앞뒤 무음을 잘라 낸다 (drama60.trim_wav 와 같은 셈 · 여러 번 해도 같다)."""
    tmp = w.with_suffix(".trim.wav")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(w), "-af",
         "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03,"
         "areverse,silenceremove=start_periods=1:start_threshold=-45dB:"
         "start_silence=0.06,areverse", str(tmp)])
    if dur_of(tmp) > 0.3:
        tmp.replace(w)
    else:
        tmp.unlink(missing_ok=True)


def talk_span(clip):
    """대사 영상에서 말이 나는 구간 (시작, 끝) — **약한 끝소리까지** 넣는다.
    ⚠️ 2026-10-06 S96 1편 받아쓰기 — short90.speech_span(배경음과 봉우리 사이 20% 문턱)은
       「너무 늦으셨어요」 의 끝 「요」(-31~-37dB)를 말로 안 쳐서 2.0초에 끊었다 → 「늦으셨습니다」 로 들렸다.
       → 50ms 마다 크기를 재서 **배경음보다 8dB 큰 마지막 자리**까지 넣고 0.1초 숨을 더 둔다."""
    import array
    hz, win = 8000, 0.05
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(clip), "-vn", "-ac", "1", "-ar", str(hz),
                          "-f", "s16le", "-"], capture_output=True).stdout
    a = array.array("h")
    a.frombytes(raw[: len(raw) // 2 * 2])
    step = int(hz * win)
    db = []
    for i in range(0, len(a) - step + 1, step):
        ch = a[i:i + step]
        db.append(20 * math.log10(max(1.0, (sum(x * x for x in ch) / step) ** 0.5) / 32768))
    dur = dur_of(clip)
    if len(db) < 6:
        return 0.0, dur
    floor = sorted(db)[max(0, int(len(db) * 0.10))]
    on = [i for i, v in enumerate(db) if v >= floor + 8.0]
    if not on:
        return 0.0, dur
    beg = max(0.0, on[0] * win - TALK_PRE)
    fin = min(dur, (on[-1] + 1) * win + TALK_POST)
    return beg, fin


# ── 목소리 (값이 나간다) ───────────────────────────────────────
def step_voice(doc, part):
    cuts = [c for c in part_cuts(doc, part) if not is_talk(c)]
    need = [c for c in cuts if not voice_ok(doc, c)]
    chars = sum(ST90.chars(c) for c in need)
    print(f"■ {doc['sid']} {part['no']}편 나레이션 {len(cuts)}줄 — 새로 만들 것 {len(need)}줄 "
          f"({chars}자 · 약 {chars * WON_PER_CHAR:,.0f}원)")
    if not need:
        print("  (전부 그대로다 — 0원)")
        return 0
    import cost                                               # noqa: E402
    import tts                                                # 늦게 부른다(열쇠 필요)
    cost.guard_month(f"{doc['sid']} 쇼츠 {part['no']}편 나레이션")
    S9.voice_route_ok(tts, len(need))
    d = work(doc["sid"]) / "voice"
    d.mkdir(exist_ok=True)
    try:
        for c in need:
            out = voice_file(doc, c)
            t = text_of(c)
            # 지시가 있으면 구글이 권하는 모양 그대로 (지시 → 쌍점 → 큰따옴표) — short90._voices 와 같다
            style = f'{narr_say(doc)} 다음 큰따옴표 안의 말만 그대로: "{t}"'
            got = tts.say(t, NARR_VOICE, S9.NARR_RATE, 0.0, d / f"v{c['n']:02d}_raw.wav", style=style)
            if not got or not Path(got).exists():
                raise TeaserError(f"컷{c['n']} 나레이션을 못 만들었다")
            Path(got).replace(out)
            tts.unwrap_file(out)
            before = dur_of(out)
            trim_wav(out)
            reuse.stamp(out, voice_sig(c, doc))
            print(f"  ✅ 컷{c['n']:>2} {dur_of(out):.2f}초 (자르기 전 {before:.2f}초) — {t}")
    finally:
        won = tts.bill_flush(f"{doc['sid']} 쇼츠 {part['no']}편 나레이션")
        if won:
            print(f"■ 목소리 값 약 {won:,.0f}원 — 장부에 적었다")
    return 0


# ── 박자표 ────────────────────────────────────────────────────
def prep_audio(doc, part, preview=False):
    """컷마다 소리 조각 {n: (파일, 길이, 영상 시작)} — 나레이션은 1.28배로 감고 크기를 맞춘다 (0원).
    preview=True 면 목소리 없는 컷은 글자 잣대 길이의 무음으로 둔다."""
    mix = work(doc["sid"]) / ("mix_preview" if preview else "mix")
    mix.mkdir(exist_ok=True)
    k = ST90.speed_of(doc)
    got = {}
    for c in part_cuts(doc, part):
        n = c["n"]
        out, tmp = mix / f"a{n:02d}.wav", mix / f"a{n:02d}.raw.wav"
        if is_talk(c):
            clip = clip_of(doc, c)
            beg, fin = talk_span(clip)
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{beg:.3f}", "-t", f"{fin - beg:.3f}",
                 "-i", str(clip), "-vn", "-af", "aresample=48000,aformat=channel_layouts=stereo",
                 str(tmp)])
            level(tmp, out)
            got[n] = (out, dur_of(out), beg)
            continue
        v = voice_file(doc, c)
        if voice_ok(doc, c):
            run(["ffmpeg", "-y", "-v", "error", "-i", str(v), "-af",
                 f"aresample=48000,aformat=channel_layouts=stereo,{S9.tempo_filter(k)}", str(tmp)])
            level(tmp, out)
        elif preview:
            sec = ST90.char_sec(k) * ST90.chars(c) + 0.25
            run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                 "anullsrc=r=48000:cl=stereo", "-t", f"{sec:.3f}", str(out)])
        else:
            raise TeaserError(f"컷{n} 나레이션이 없다 — `teaser.py {doc['sid']} voice --part "
                              f"{part['no']}` 를 먼저 (또는 preview)")
        got[n] = (out, dur_of(out), float(c.get("at") or 0.0))
    return got


def level(src, dst):
    """말소리 크기를 VOICE_DB 로 — **다 감고 난 뒤에** 잰다.
    ⚠️ 2026-10-06 — 감기 전에 재서 맞췄더니 나레이션이 대사보다 5dB 작게 나왔다
       (홑소리→두소리 바꿈 −3dB · 감기에서 −2dB). 마지막 모양에서 재야 맞는다."""
    g = max(-12.0, min(12.0, VOICE_DB - mean_db(src)))
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", f"volume={g:.2f}dB", str(dst)])
    Path(src).unlink(missing_ok=True)
    return g


def timeline(doc, part, pieces):
    """박자 [{c, t0, t1, at, a, src_at, audio}] · 끊는 때 · 끝 화면 시작 · 전체 길이."""
    segs, t = [], LEAD
    for i, c in enumerate(part_cuts(doc, part)):
        path, a, src_at = pieces[c["n"]]
        gap = 0.0 if c.get("cliff") else float(c.get("gap", GAP))
        # 첫 컷 화면은 0.0초부터 — 말(LEAD)보다 먼저 얼굴이 떠 있다
        t0 = 0.0 if i == 0 else t
        segs.append({"c": c, "t0": t0, "t1": t + a + gap, "at": t, "a": a,
                     "src_at": src_at - (t - t0), "audio": path})
        t = t + a + gap
    cliff = t
    end0 = cliff + CLIFF_BLACK
    return segs, cliff, end0, end0 + END_SEC


def save_timeline(f, segs, cliff, end0, total):
    f.write_text(json.dumps(
        [{"n": s["c"]["n"], "t0": round(s["t0"], 3), "t1": round(s["t1"], 3), "at": round(s["at"], 3),
          "a": round(s["a"], 3), "clip": s["c"]["clip"]} for s in segs]
        + [{"cliff": round(cliff, 3), "end": round(end0, 3), "total": round(total, 3)}],
        ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


# ── 그리기 ────────────────────────────────────────────────────
_FONTS = {}


def font(path, size):
    k = (str(path), int(size))
    if k not in _FONTS:
        _FONTS[k] = ImageFont.truetype(str(path), int(size))
    return _FONTS[k]


def text_w(text, f):
    return ImageDraw.Draw(Image.new("L", (4, 4))).textlength(text, font=f)


def ease(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def stamp_img(lines):
    """첫 화면 '쾅' — 크림색 서류 쪽지 위에 찍힌 빨간 도장 (RGBA).
    ⚠️ 2026-10-06 맛보기 — 빨간 글만 얹었더니 아들의 남색 양복 위에서 흐린 물자국처럼 묻혔다.
       종이 쪽지를 깔아야 빨간 글이 튀고 '서류에 적힌 한 줄' 로 읽힌다 (맨 위에 작게 앉아도 읽힌다)."""
    f1, f2 = font(FONT_SERIF, 80), font(FONT_SERIF, 118)
    w1, w2 = text_w(lines[0], f1), text_w(lines[-1], f2)
    pad_x, pad_y, gap = 58, 40, 20
    bw = int(max(w1, w2) + pad_x * 2)
    bh = int(80 + gap + 118 + pad_y * 2 + 14)
    m = Image.new("L", (bw, bh), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle([5, 5, bw - 6, bh - 6], radius=14, outline=255, width=12)
    d.rounded_rectangle([25, 25, bw - 26, bh - 26], radius=8, outline=255, width=5)
    # 바탕체 굵기를 같은 색 테두리로 더 올린다 (인주가 두껍게 묻은 글)
    d.text((bw / 2, pad_y + 6), lines[0], font=f1, fill=255, anchor="ma",
           stroke_width=2, stroke_fill=255)
    d.text((bw / 2, pad_y + 6 + 80 + gap), lines[-1], font=f2, fill=255, anchor="ma",
           stroke_width=3, stroke_fill=255)
    # 인주 얼룩 — 고정된 씨앗으로 군데군데 아주 조금만 옅게 (읽히는 것이 먼저 · 매번 같은 도장)
    rnd = random.Random(1969)
    speck = Image.new("L", (bw // 3, bh // 3), 255)
    sd = ImageDraw.Draw(speck)
    for _ in range(int(bw * bh / 2600)):
        x, y = rnd.randrange(speck.width), rnd.randrange(speck.height)
        r = rnd.choice((1, 1, 2))
        sd.ellipse([x - r, y - r, x + r, y + r], fill=rnd.randrange(130, 215))
    speck = speck.resize((bw, bh), Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.0))
    ink = ImageChops.multiply(m, speck).point(lambda v: int(v * 0.97))
    st = Image.new("RGBA", (bw, bh), RED + (0,))
    st.putalpha(ink)
    st = st.rotate(5, resample=Image.BICUBIC, expand=True)
    # 서류 쪽지 — 크림색 · 옅은 칸 줄 · 그림자
    pw, ph = st.width + 80, st.height + 56
    paper = Image.new("RGBA", (pw + 60, ph + 60), (0, 0, 0, 0))
    sh = Image.new("L", paper.size, 0)
    ImageDraw.Draw(sh).rounded_rectangle([34, 40, pw + 30, ph + 36], radius=10, fill=170)
    paper.paste((0, 0, 0, 255), (0, 0), sh.filter(ImageFilter.GaussianBlur(16)))
    pd = ImageDraw.Draw(paper)
    pd.rounded_rectangle([30, 30, pw + 30, ph + 30], radius=10, fill=(246, 240, 226, 250),
                         outline=(205, 196, 176, 255), width=2)
    for k in range(1, 4):
        y = 30 + ph * k / 4
        pd.line([(52, y), (pw + 8, y)], fill=(190, 182, 164, 150), width=2)
    pd.line([(30 + pw * 0.16, 44), (30 + pw * 0.16, ph + 16)], fill=(190, 182, 164, 120), width=2)
    paper.alpha_composite(st, (int(30 + (pw - st.width) / 2), int(30 + (ph - st.height) / 2)))
    out = paper.rotate(-3, resample=Image.BICUBIC, expand=True)
    # 화면 너비 안에 — 첫 장면에서 조금 크게 떠 있어도 양옆이 안 잘린다
    return out.resize((STAMP_W, int(out.height * STAMP_W / out.width)), Image.LANCZOS)


KEEP = ""                                # 금색 말 안의 띄어쓰기 — 자막 토막이 그 말을 안 가른다


def hot_words(text, gold):
    """그 줄에서 금색으로 칠할 낱말 번호들 — 금색 말(띄어쓰기 · 문장부호는 안 본다)의 글자가 든 낱말 전부."""
    words = text.split()
    flat = [re.sub(r"[\s,.?!…]", "", w) for w in words]
    owner = [i for i, w in enumerate(flat) for _ in w]
    joined = "".join(flat)
    hot = set()
    for g in gold or []:
        gs = re.sub(r"[\s,.?!…]", "", g)
        k = joined.find(gs) if gs else -1
        while k >= 0:
            hot.update(owner[k:k + len(gs)])
            k = joined.find(gs, k + 1)
    return hot


def chunks(text, gold=()):
    """자막 토막 [글] — 금색 말은 한 토막 안에 둔다 (「12년 / 묵은 편지」 처럼 안 갈린다)."""
    t = text
    for g in sorted(gold or [], key=len, reverse=True):
        if " " in g and g in t:
            t = t.replace(g, g.replace(" ", KEEP))
    return [x.replace(KEEP, " ") for x in S9.chunks_of(t, max_w=SUB_W)]


def sub_windows(seg):
    """자막 토막마다 (낱말들, 금색 번호들, 시작, 끝) — 말이 나는 동안을 글자 수로 나눈다
    (끝 토막은 컷 끝까지)."""
    text, gold = text_of(seg["c"]), list(seg["c"].get("gold") or [])
    hot = hot_words(text, gold)
    ch = chunks(text, gold)
    tot = sum(S9.syl(x) for x in ch)
    t, k, out = seg["at"], 0, []
    for i, x in enumerate(ch):
        ws = x.split()
        t1 = seg["t1"] if i == len(ch) - 1 else t + seg["a"] * S9.syl(x) / tot
        out.append((ws, {j - k for j in hot if k <= j < k + len(ws)}, t, t1))
        t, k = t1, k + len(ws)
    return out


def sub_img(words, hot):
    """자막 한 토막 (RGBA · 글자 자리만) — hot 에 든 낱말은 금색."""
    f = font(FONT_SUB, SUB_SIZE)
    sp = text_w(" ", f)
    wide = sum(text_w(w, f) for w in words) + sp * (len(words) - 1)
    pad = 14
    im = Image.new("RGBA", (int(wide + pad * 2), int(SUB_SIZE * 1.45)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = pad
    for i, w in enumerate(words):
        d.text((x, SUB_SIZE * 1.05), w, font=f, fill=GOLD_BRIGHT if i in hot else S9.WHITE,
               anchor="ls", stroke_width=5, stroke_fill=(0, 0, 0, 225))
        x += text_w(w, f) + sp
    return im


def tag_img(label):
    f = font(FONT_SERIF, 58)
    tw = text_w(label, f)
    im = Image.new("RGBA", (int(tw + 60), 90), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    box = d.textbbox((34, 62), label, font=f, anchor="ls")
    d.rectangle([4, box[1] - 7, 11, box[3] + 7], fill=GOLD)
    d.text((34, 62), label, font=f, fill=GOLD_BRIGHT, anchor="ls",
           stroke_width=3, stroke_fill=(0, 0, 0, 210))
    return im


def chrome_img():
    """늘 떠 있는 것 — 채널 이름 · 영상 칸 위아래 금색 가는 줄 · 영상 칸 가장자리 그늘."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((W - 60, MARK_Y), S9.CHANNEL, font=font(FONT_SERIF, MARK_SIZE),
           fill=(255, 255, 255, 168), anchor="ra")
    for y in range(28):                                   # 영상 칸 위아래가 바탕에 스며든다
        a = int(150 * (1 - y / 28) ** 2)
        d.line([(0, FG_Y + y), (W, FG_Y + y)], fill=(0, 0, 0, a))
        d.line([(0, FG_Y + FG_H - 1 - y), (W, FG_Y + FG_H - 1 - y)], fill=(0, 0, 0, a))
    d.line([(0, FG_Y), (W, FG_Y)], fill=GOLD[:3] + (120,), width=2)
    d.line([(0, FG_Y + FG_H - 2), (W, FG_Y + FG_H - 2)], fill=GOLD[:3] + (120,), width=2)
    return im


def head_img(part, stamp):
    """맨 위 — (한 줄 글 그림, 작은 쪽지 그림). 한 줄은 첫 화면부터 늘 · 쪽지는 첫 도장이 날아와 앉은 뒤."""
    line = Image.new("RGBA", (W, FG_Y), (0, 0, 0, 0))
    d = ImageDraw.Draw(line)
    for y in range(FG_Y):                                  # 위쪽을 조금 어둡게 (글이 읽히게)
        d.line([(0, y), (W, y)], fill=(0, 0, 0, int(110 * (1 - y / FG_Y))))
    d.text((W / 2, HEAD_Y), " ".join(part["head"]), font=font(FONT_SUB, HEAD_SIZE),
           fill=(255, 255, 255, 245), anchor="mt", stroke_width=4, stroke_fill=(0, 0, 0, 200))
    small = stamp.resize((int(stamp.width * HEAD_STAMP), int(stamp.height * HEAD_STAMP)),
                         Image.LANCZOS)
    return line, small


def end_img(doc, part):
    """끝 화면 — 본편 썸네일 + 「이 이야기의 끝은 본편에서」 + 아래 영상 링크 안내 (화살표는 따로)."""
    th = OUT / f"{doc['source']}_part1.jpg"
    if not th.exists():
        raise TeaserError(f"본편 썸네일 {th.relative_to(ROOT)} 이 없다")
    t = Image.open(th).convert("RGB")
    sh = t.height
    rw = int(sh * W / H)
    bg = t.resize((54, 96), Image.BILINEAR, box=((t.width - rw) // 2, 0, (t.width + rw) // 2, sh))
    bg = ImageEnhance.Brightness(bg.filter(ImageFilter.GaussianBlur(2.2))).enhance(0.30)
    im = bg.resize((W, H), Image.BICUBIC).convert("RGBA")
    d = ImageDraw.Draw(im)
    a, b = part["end"][0], part["end"][-1]
    d.text((W / 2, 520), a, font=font(FONT_SUB, 64), fill=(255, 255, 255, 240), anchor="ms",
           stroke_width=4, stroke_fill=(0, 0, 0, 200))
    d.text((W / 2, 664), b, font=font(FONT_SUB, 118), fill=GOLD_BRIGHT, anchor="ms",
           stroke_width=6, stroke_fill=(0, 0, 0, 210))
    cw = 940
    card = t.resize((cw, int(cw * t.height / t.width)), Image.LANCZOS)
    cy = 740
    shadow = Image.new("RGBA", (card.width + 60, card.height + 60), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([30, 30, card.width + 30, card.height + 30], fill=(0, 0, 0, 170))
    shadow = shadow.filter(ImageFilter.GaussianBlur(14))
    im.alpha_composite(shadow, (int(W / 2 - card.width / 2 - 30), cy - 22))
    im.paste(card, (int(W / 2 - card.width / 2), cy))
    d = ImageDraw.Draw(im)
    d.rectangle([W / 2 - card.width / 2 - 3, cy - 3, W / 2 + card.width / 2 + 2, cy + card.height + 2],
                outline=GOLD, width=4)
    note = str(part.get("end_note") or "")
    if note:
        d.text((W / 2, cy + card.height + 98), note, font=font(FONT_SUB, 46),
               fill=(255, 255, 255, 235), anchor="ms", stroke_width=3, stroke_fill=(0, 0, 0, 200))
    d.text((W - 60, MARK_Y), S9.CHANNEL, font=font(FONT_SERIF, MARK_SIZE),
           fill=(255, 255, 255, 168), anchor="ra")
    return im.convert("RGB"), cy + card.height + 140


def arrow_img():
    """아래를 가리키는 금색 화살표 (그린 것 · 이모지 아님)."""
    im = Image.new("RGBA", (120, 150), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([48, 6, 72, 92], fill=GOLD_BRIGHT)
    d.polygon([(14, 84), (106, 84), (60, 144)], fill=GOLD_BRIGHT)
    return im


def bg_of(im):
    """뒷바탕 — 같은 장면을 아주 흐리고 어둡게 (검은 띠 대신)."""
    sw, sh = im.size
    rw = sh * W / H
    x0 = (sw - rw) / 2
    small = im.resize((54, 96), Image.BILINEAR, box=(x0, 0, x0 + rw, sh))
    small = ImageEnhance.Brightness(small.filter(ImageFilter.GaussianBlur(2.0))).enhance(0.36)
    return small.resize((W, H), Image.BICUBIC)


def fg_of(im, z, cx, cy):
    """영상 칸 — (cx, cy) 를 가운데로 z 배 다가가 1080×1000 으로 (화면 밖으로는 안 나간다)."""
    sw, sh = im.size
    rh = sh / max(1.0, z)
    rw = rh * FG_W / FG_H
    if rw > sw:
        rw, rh = sw, sw * FG_H / FG_W
    x0 = min(max(cx * sw - rw / 2, 0), sw - rw)
    y0 = min(max(cy * sh - rh / 2, 0), sh - rh)
    s = rw / FG_W
    return im.transform((FG_W, FG_H), Image.AFFINE, (s, 0, x0, 0, s, y0), Image.BICUBIC)


def lerp(v, u):
    if isinstance(v, (list, tuple)):
        a, b = float(v[0]), float(v[-1])
        return a + (b - a) * u
    return float(v)


def frames_of(clip, at, need, n, stretch=STRETCH_MAX):
    """영상 조각에서 n 장 (FPS) — 모자라면 느리게(stretch 까지), 그래도 모자라면 끝 장면에 멈춘다."""
    dur = dur_of(clip)
    at = max(0.0, min(at, dur - 0.05))
    avail = max(0.05, dur - at)
    k = 1.0 if avail >= need else min(stretch, need / avail)
    hold = max(0.0, need - avail * k)
    vf = f"setpts={k:.5f}*(PTS-STARTPTS),fps={FPS}"
    if hold > 0.001:
        vf += f",tpad=stop_mode=clone:stop_duration={hold + 0.5:.2f}"
    sw, sh = size_of(clip)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{at:.3f}", "-i", str(clip), "-an",
                          "-vf", vf, "-frames:v", str(n), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    size, last = sw * sh * 3, None
    for _ in range(n):
        buf = p.stdout.read(size)
        if len(buf) == size:
            last = Image.frombytes("RGB", (sw, sh), buf)
        if last is None:
            last = Image.new("RGB", (sw, sh), (0, 0, 0))
        yield last
    p.stdout.close()
    p.wait()


def shake_at(t):
    u = t - STAMP_IN
    if u < 0 or u > SHAKE_SEC:
        return 0, 0
    a = SHAKE_PX * math.exp(-u * 9.0)
    return (int(round(a * 0.45 * math.sin(u * 2 * math.pi * 23))),
            int(round(a * math.sin(u * 2 * math.pi * 17))))


def stamp_at(t, fly0, big_c, small_c):
    """첫 도장의 (크기, 가운데) — 첫 장면부터 떠 있다가 STAMP_IN 에 내려찍히고, fly0 부터 맨 위로."""
    if t < STAMP_IN:
        return 1.12 - 0.12 * (t / STAMP_IN) ** 2, big_c
    if t < fly0:
        return 1.0 + 0.02 * (t - STAMP_IN), big_c
    # 먼저 작아지고(앞 절반) 위로 간다 — 큰 쪽지가 얼굴을 덮고 지나가지 않게 (2026-10-06 맛보기)
    u = (t - fly0) / FLY_SEC
    v, z = ease(u), ease(min(1.0, u * 2.0))
    s0 = 1.0 + 0.02 * (fly0 - STAMP_IN)
    # 곧장 올라가면 얼굴(가운데) 위를 지난다 → 오른쪽으로 둥글게 돌아 올라간다
    return (s0 * (1 - z) + HEAD_STAMP * z,
            (big_c[0] + FLY_ARC * math.sin(math.pi * v), big_c[1] + (small_c[1] - big_c[1]) * v))


def render(doc, part, segs, cliff, end0, total, out_mp4):
    """화면만 (소리 없이) → out_mp4. 프레임마다 PIL 로 짠다 (0원)."""
    stamp = stamp_img(part["stamp"])
    head, slip = head_img(part, stamp)
    slip_xy = (int(W / 2 - slip.width / 2), int(HEAD_STAMP_Y - slip.height / 2))
    white = Image.new("RGB", (W, H), (255, 255, 255))
    chrome = chrome_img()
    endpic, arrow_y = end_img(doc, part)
    arrow = arrow_img()
    subs, tags = {}, {}
    fly_end = segs[0]["t1"]
    fly0 = fly_end - FLY_SEC
    big_c, small_c = (W / 2, STAMP_Y), (W / 2, HEAD_STAMP_Y)
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                            "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", str(out_mp4)], stdin=subprocess.PIPE)
    nf_total = int(round(total * FPS))
    fi = 0
    try:
        for seg in segs:
            c = seg["c"]
            f0 = int(round(seg["t0"] * FPS))
            f1 = int(round((cliff if c.get("cliff") else seg["t1"]) * FPS))
            n = max(1, f1 - f0)
            stretch = 1.0 if is_talk(c) else STRETCH_MAX      # 대사는 입이 맞아야 한다 — 안 늘인다
            wins = sub_windows(seg)
            for j, im in enumerate(frames_of(clip_of(doc, c), seg["src_at"], n / FPS, n, stretch)):
                t = (f0 + j) / FPS
                u = ease(j / max(1, n - 1))
                fr = bg_of(im)
                dx, dy = shake_at(t) if c.get("stamp") else (0, 0)
                fr.paste(fg_of(im, lerp(c.get("zoom", 1.0), u), lerp(c.get("x", 0.5), u),
                               lerp(c.get("y", 0.45), u)), (dx, FG_Y + dy))
                fr.paste(chrome, (0, 0), chrome)
                # 맨 위 — 한 줄은 첫 화면부터 · 작은 쪽지는 첫 도장이 날아와 앉은 뒤
                fr.paste(head, (0, 0), head)
                landed = not c.get("stamp") or t >= fly_end - 0.04
                if landed:
                    fr.paste(slip, slip_xy, slip)
                else:
                    s, (cx, cy) = stamp_at(t, fly0, big_c, small_c)
                    st = stamp.resize((max(2, int(stamp.width * s)), max(2, int(stamp.height * s))),
                                      Image.BICUBIC)
                    fr.paste(st, (int(cx - st.width / 2) + dx, int(cy - st.height / 2) + dy), st)
                    if STAMP_IN <= t < STAMP_IN + FLASH_SEC:      # 찍히는 순간 번쩍
                        fr = Image.blend(fr, white, 0.26 * (1 - (t - STAMP_IN) / FLASH_SEC))
                if is_talk(c):                                    # 대사 이름표
                    if c["n"] not in tags:
                        tags[c["n"]] = tag_img(str(c["tag"]))
                    fr.paste(tags[c["n"]], (56, TAG_Y), tags[c["n"]])
                for ws, hot, a, b in wins:                        # 자막 한 토막
                    if a - 0.02 <= t < b:
                        key = (" ".join(ws), tuple(sorted(hot)))
                        if key not in subs:
                            subs[key] = sub_img(ws, hot)
                        sb = subs[key]
                        fr.paste(sb, (int(W / 2 - sb.width / 2), int(SUB_Y - SUB_SIZE * 0.72)), sb)
                        break
                enc.stdin.write(fr.tobytes())
                fi += 1
        # 말 한복판에서 끊는다 → 까만 화면 (판사봉) → 끝 화면
        black = Image.new("RGB", (W, H), (0, 0, 0))
        for _ in range(max(0, int(round(end0 * FPS)) - fi)):
            enc.stdin.write(black.tobytes())
            fi += 1
        for j in range(max(0, nf_total - fi)):
            t = j / FPS
            fr = endpic.copy()
            bob = int(10 * math.sin(t * 2 * math.pi * 1.6))
            fr.paste(arrow, (int(W / 2 - arrow.width / 2), arrow_y + bob), arrow)
            if t < 0.22:
                fr = Image.blend(black, fr, ease(t / 0.22))
            enc.stdin.write(fr.tobytes())
            fi += 1
    finally:
        enc.stdin.close()
        rc = enc.wait()
    if rc != 0 or not Path(out_mp4).exists():
        raise TeaserError("화면 조립(ffmpeg)이 실패했다")
    return fi


def fx_list(segs, cliff):
    """효과음 [(이름, 때)] — 도장 '쾅' · (컷마다 적은 것) · 끊는 순간 판사봉."""
    out = [("stamp", STAMP_IN - 0.03), ("hit", max(0.0, STAMP_IN - 0.10))]
    for seg in segs:
        for name, dt in seg["c"].get("sfx") or []:
            out.append((name, seg["t0"] + float(dt)))
    out += [("gavel", cliff + 0.01), ("boom", cliff)]
    return out


def mix_audio(doc, segs, cliff, total, out_wav):
    """말 + 배경음악(말이 나오면 눌린다 · 끊는 순간 뚝) + 효과음 → out_wav (0원)."""
    ins, fl, voice, fx = [], [], [], []
    for seg in segs:
        ins += ["-i", str(seg["audio"])]
        i = len(ins) // 2 - 1
        ms = int(round(seg["at"] * 1000))
        fl.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{i}]")
        voice.append(f"[v{i}]")
    ins += ["-i", str(BGM_DIR / f"{doc.get('bgm') or 'hook'}.mp3")]
    ib = len(ins) // 2 - 1
    for k, (name, at) in enumerate(fx_list(segs, cliff)):
        f, vol, ss, ln = FX[name]
        ins += ["-i", str(SFX / f"{f}.mp3")]
        i = len(ins) // 2 - 1
        ms = max(0, int(round(at * 1000)))
        fl.append(f"[{i}:a]atrim={ss:.3f}:{ss + ln:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
                  f"aformat=channel_layouts=stereo,volume={vol:.2f},"
                  f"afade=t=out:st={max(0.0, ln - 0.25):.2f}:d=0.25,adelay={ms}|{ms}[x{k}]")
        fx.append(f"[x{k}]")
    fl.append(f"{''.join(voice)}amix=inputs={len(voice)}:normalize=0:duration=longest,"
              f"apad=whole_dur={total:.3f},atrim=0:{total:.3f},asplit=2[vo][vk]")
    fl.append(f"[{ib}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{cliff:.3f},"
              f"asetpts=PTS-STARTPTS,volume={BGM_VOL:.2f},afade=t=in:st=0:d=0.25,"
              f"afade=t=out:st={max(0.0, cliff - 0.05):.3f}:d=0.05,apad=whole_dur={total:.3f}[bed]")
    fl.append("[bed][vk]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=380[duck]")
    fl.append(f"[vo][duck]{''.join(fx)}amix=inputs={2 + len(fx)}:normalize=0:duration=first,"
              f"alimiter=limit=0.95[a]")
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(fl), "-map", "[a]",
         "-ar", "48000", "-ac", "2", "-t", f"{total:.3f}", str(out_wav)])
    return out_wav


def step_build(doc, part, preview=False):
    sid, no = doc["sid"], int(part["no"])
    bad = check(doc)
    if bad:
        raise TeaserError("대본이 어긋난다:\n   · " + "\n   · ".join(bad))
    pieces = prep_audio(doc, part, preview=preview)
    segs, cliff, end0, total = timeline(doc, part, pieces)
    wk = work(sid)
    pre = "preview_" if preview else ""
    v, a = wk / f"{pre}part{no}_v.mp4", wk / f"{pre}part{no}_a.wav"
    final = (wk / f"preview_part{no}.mp4") if preview else (OUT / f"{sid}_part{no}.mp4")
    print(f"■ {sid} {no}편 조립{' (맛보기 · 목소리 자리는 무음)' if preview else ''} — "
          f"{len(segs)}박자 · 끊는 때 {cliff:.2f}초 · 전체 {total:.2f}초")
    nf = render(doc, part, segs, cliff, end0, total, v)
    mix_audio(doc, segs, cliff, total, a)
    run(["ffmpeg", "-y", "-v", "error", "-i", str(v), "-i", str(a), "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart",
         "-t", f"{total:.3f}", str(final)])
    save_timeline(wk / f"{pre}part{no}_timeline.json", segs, cliff, end0, total)
    sec = dur_of(final)
    print(f"  ✅ {final.relative_to(ROOT)} — {sec:.2f}초 · {nf}장 · "
          f"{final.stat().st_size / 1048576:.1f}MB")
    if preview:
        return final
    thumb = OUT / f"{sid}_part{no}.jpg"
    for q in (2, 5, 9):
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{float(part.get('thumb_at') or 0.62):.2f}",
             "-i", str(final), "-frames:v", "1", "-q:v", str(q), str(thumb)])
        if thumb.stat().st_size <= S9.THUMB_MAX_BYTES:
            break
    import shortstate                                          # noqa: E402
    import talkplan                                            # noqa: E402
    shortstate.from_doc(doc, wall=talkplan.part_max_sec(doc))
    shortstate.mark_made(sid, no, sec, [])
    print(f"  ✅ 썸네일 {thumb.relative_to(ROOT)} · 만든 기록 state/shorts.json ({sec:.1f}초)")
    return final


def step_plan(doc):
    bad = check(doc)
    k = ST90.speed_of(doc)
    for p in parts_of(doc):
        print(f"\n■ {doc['sid']} {p['no']}편 「{p.get('yt_title', '')}」")
        print(f"  첫 화면 도장: {' / '.join(p['stamp'])} · 맨 위: {' '.join(p['head'])}")
        t, need = LEAD, 0
        for c in part_cuts(doc, p):
            if is_talk(c):
                try:
                    beg, fin = talk_span(clip_of(doc, c))
                    a = fin - beg
                except TeaserError as e:
                    print(f"  ❌ {e}")
                    a = 2.5
                kind = f"대사({c.get('tag')})"
            else:
                ok = voice_ok(doc, c)
                a = (dur_of(voice_file(doc, c)) / k) if ok else ST90.char_sec(k) * ST90.chars(c) + 0.25
                need += 0 if ok else ST90.chars(c)
                kind = "나레이션" + ("" if ok else "(어림)")
            gap = 0.0 if c.get("cliff") else float(c.get("gap", GAP))
            print(f"  {t:5.1f}초  컷{c['n']:>2} 본편 c{c['clip']:<3} {kind:<12} {a:4.1f}초  {text_of(c)}"
                  + ("   ← 여기서 끊는다" if c.get("cliff") else ""))
            t += a + gap
        print(f"  {t:5.1f}초  (까만 화면 {CLIFF_BLACK}초 · 판사봉) → 끝 화면 {END_SEC}초: "
              f"{' '.join(p['end'])} · {p.get('end_note', '')}")
        print(f"  ≈ {t + CLIFF_BLACK + END_SEC:.1f}초 · 새 나레이션 {need}자 ≈ {need * WON_PER_CHAR:,.0f}원 "
              f"(영상은 본편 조각 · 0원)")
    if bad:
        print("\n❌ 대본이 어긋난다:")
        for b in bad:
            print(f"   · {b}")
        return 1
    print("\n✅ 대본 검사 통과 (본편 대사와 글이 같다 · 첫 컷 도장 · 끝 컷 끊기 · 퀴즈/시각 안내 없음)")
    return 0


def step_sheet(doc, part, preview=False):
    """완성 영상 검수 — 정한 시각들의 화면을 한 장에 (0원)."""
    sid, no = doc["sid"], int(part["no"])
    mp4, tl = OUT / f"{sid}_part{no}.mp4", work(sid) / f"part{no}_timeline.json"
    if preview or not mp4.exists():
        mp4, tl = work(sid) / f"preview_part{no}.mp4", work(sid) / f"preview_part{no}_timeline.json"
    if not mp4.exists():
        raise TeaserError("영상이 없다 — build 또는 preview 를 먼저")
    total = dur_of(mp4)
    ats = [0.0, 0.05, 0.12, 0.2, 0.6, 1.5]
    if tl.exists():
        rows = json.loads(tl.read_text(encoding="utf-8"))
        ats += [round(rows[0]["t1"] - FLY_SEC / 2, 2), round(rows[0]["t1"] + 0.1, 2)]
        ats += [round((r["t0"] + r["t1"]) / 2, 2) for r in rows[1:] if "t0" in r]
        last = rows[-1]
        ats += [last["cliff"] - 0.1, last["cliff"] + 0.1, last["end"] + 0.3, total - 0.1]
    else:
        ats += [total * k for k in (0.3, 0.5, 0.7, 0.85, 0.97)]
    tw, th, cols = 270, 480, 6
    rows_n = math.ceil(len(ats) / cols)
    sheet = Image.new("RGB", (tw * cols, (th + 30) * rows_n), (14, 14, 14))
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(ats):
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.2f}", "-i", str(mp4),
                            "-frames:v", "1", "-vf", f"scale={tw}:{th}", "-f", "image2pipe",
                            "-vcodec", "png", "-"], capture_output=True)
        x, y = (i % cols) * tw, (i // cols) * (th + 30)
        if r.stdout:
            sheet.paste(Image.open(io.BytesIO(r.stdout)).convert("RGB"), (x, y + 30))
        d.text((x + 6, y + 4), f"{t:.2f}초", font=font(FONT_SUB, 20), fill=(255, 220, 120))
    out = work(sid) / f"{'preview_' if mp4.name.startswith('preview') else ''}part{no}_sheet.jpg"
    sheet.save(out, quality=88)
    print(out)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sid")
    ap.add_argument("what", choices=["plan", "voice", "build", "preview", "sheet"])
    ap.add_argument("--part", default="1")
    ap.add_argument("--preview", action="store_true", help="sheet — 맛보기 영상을 본다")
    a = ap.parse_args()
    try:
        doc = load(a.sid.upper())
        if a.what == "plan":
            return step_plan(doc)
        part = part_of(doc, a.part)
        if a.what == "voice":
            bad = check(doc)
            if bad:
                raise TeaserError("대본이 어긋난다 — 목소리를 만들지 않는다:\n   · " + "\n   · ".join(bad))
            return step_voice(doc, part)
        if a.what == "preview":
            step_build(doc, part, preview=True)
        elif a.what == "build":
            step_build(doc, part)
        elif a.what == "sheet":
            step_sheet(doc, part, preview=a.preview)
    except TeaserError as e:
        print(f"❌ {e}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
