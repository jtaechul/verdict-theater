#!/usr/bin/env python3
"""⭐ 전부 영상 드라마 · 설명 드라마 — 모든 컷을 옴니 9:16 영상(360p · 720p 고른다) 또는 그림 컷으로 (2026-10-02 신설)

    python3 tools/drama60.py S94 check    값 0원 — 대본 검사 (설명 드라마 규칙 · 그림 맞물림 · 대본↔제작본)
    python3 tools/drama60.py S94 plan     값 0원 — 카메라 계획 · 컷 길이 · 영상 지문 · 값 어림
    python3 tools/drama60.py S94 cast     인물 시트 한 장 (약 265원 · 지문이 같으면 0원)
    python3 tools/drama60.py S94 voice    나레이션 목소리 (같으면 0원) + 앞뒤 무음 자르기 (0원)
    python3 tools/drama60.py S94 clips    컷마다 옴니 영상 (360p 1초 약 55원 · 720p 약 154원 · 같으면 0원)
                                          --no-buy: 창고에 없는 컷이 있으면 사지 않고 멈춘다 (0원 보장)
                                          --res 720p: 이번만 그 화질로 (늘 그렇게 하려면 대본 res)
    python3 tools/drama60.py S94 figs     그림 컷(관계도·쟁점·판결 등)을 직접 그린다 (0원 · src/diagram60.py)
    python3 tools/drama60.py S94 build    조립 (0원) → build/s90/<사건>_part1.mp4
    python3 tools/drama60.py S94 sheet    완성 영상 검수 (0원) — 컷마다 한 장 + 컷 시간표
                                          --at 1:36 : 손님이 짚은 시각이 몇 번 컷인지
    python3 tools/drama60.py S95 meta     긴 영상 올릴 글에 설명란 대목 + 자막 파일(.srt) (0원 · build 가 저절로)
    python3 tools/drama60.py S95 preview  맛보기 (0원) — 목소리는 무음 · 얼굴 영상은 자리 표시 · 그림은 진짜
                                          → build/preview/<사건>/ (진짜 제작 자리·상태·장부를 안 건드린다)
    python3 tools/drama60.py S94 all      check → cast → voice → clips → figs → build 를 차례로

    설명 드라마(대본 style="explainer" · 판결극장 기본 짜임) 짓는 법:
    .claude/skills/verdict-explainer/SKILL.md (본보기 대본 쇼츠 data/series/S94.story.json · 긴 영상 S95.story.json)

⭐⭐⭐ 2026-10-02 손님:
    "1분이면 이미지 필요 없이 그냥 전체 다 영상으로 가고 나레이션이던 대화이던 영상으로"
    "대사 사이사이에 쉬는 공간 없이 … 충분하게 이해시킬 수 있을 만큼 풍부해야"
    "화소는 360p … 9대16 비율로 만들어. 처음부터." · "1.28배로 가자"
    "카메라나 인물 구도, 화면 구도도 이런 식으로 좀 다채롭게"
    "실제로 우리가 업로드할 영상 같은 경우에는 720p 또는 360p를 선택할 수 있도록" (→ 대본 res · --res)

어떻게 도나
    · 인물은 시트 한 장에서 잘라 쓴다 (2분 드라마와 같다 · src/castsheet.py).
    · 그림 컷(대본 컷의 fig)은 옴니를 안 산다 — 직접 그린 관계도·쟁점·판결 그림 (0원).
    · 컷마다 옴니 reference_to_video — 그 컷에 나오는 사람의 시트 칸만 참조로 넣는다.
    · 카메라는 src/camera60.py 가 정한다 (렌즈 · 높이 · 움직임 — 이웃 컷은 둘 이상 다르게).
    · 대사 컷: 옴니가 입을 맞춰 직접 말한다 (목소리 = 인물표 한 줄 고정 · 나이·성별·톤).
      말 앞뒤 무음을 잘라 내고 **화면과 소리를 함께** 1.28배로 감는다 (입이 안 어긋난다).
    · 나레이션 컷: 사람은 입을 다물고, 성우 목소리(앞뒤 무음을 자른 것)를 얹는다.
      영상이 나레이션보다 짧으면 화면만 살짝 느리게 늘인다 (되돌려 잇지 않는다).
    · 조립은 src/short90.py build 그대로 (자막 · 이름표 · 배경음악) — 말 사이 쉼은 대본 gap
      (설명 드라마 0.5초 · 없으면 0.12초).
    · 같은 지문은 다시 안 산다 (src/reuse.py — 0원). 값은 전부 장부에 적힌다.
    · ⭐ 대본 layout="long"(긴 영상 · 2026-10-05)이면 옴니도 **가로 16:9** 로 사고, 조립·그림도
      가로(1920×1080)다. 세로 쇼츠는 예전과 한 글자도 안 바뀐다 (지문·창고 열쇠 그대로).
"""
import argparse
import json
import math
import os
import io
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
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

import camera60                                               # noqa: E402
import castsheet                                              # noqa: E402
import cost                                                   # noqa: E402
import omni                                                   # noqa: E402
import reuse                                                  # noqa: E402
import short90 as S9                                          # noqa: E402
import story90 as ST90                                        # noqa: E402
import talkplan                                               # noqa: E402

# ⭐⭐⭐ 옴니 영상 화질 — 2026-10-02 손님: "실제로 우리가 업로드할 영상 같은 경우에는 720p 또는
#    360p를 선택할 수 있도록". 대본 res(없으면 360p)를 따르고, --res 가 이긴다 (load() 가 정한다).
#    720p 는 1초 약 154원 · 360p 약 55원. 조립 화면은 어느 쪽이든 1080×1920.
RES_CHOICES = ST90.RES_CHOICES
RES = ST90.RES_DEFAULT
SEC_MIN, SEC_MAX = 4, 10           # 옴니 한 토막 (talkplan.OMNI_MIN_SEC/OMNI_MAX_SEC 와 같다)
NARR_MARGIN = 0.35                 # 나레이션보다 영상을 이만큼 넉넉히 산다
STRETCH_MAX = 1.4                  # 영상이 모자라면 화면만 이만큼까지 느리게 늘인다
# ⭐ 창고 영상을 **다시 쓸 때**는 조금 더 늘이고(1.6배), 그래도 모자라면 마지막 장면에서
#    멈춰 선다 — 새로 사지 않는다 (2026-10-02 · S94 v5 · 손님: "살릴 수 있는 영상은 최대한 살리고")
STRETCH_REUSE = 1.6
SQUEEZE_MIN = 0.75                 # 끝이 얼굴인 움직임은 화면을 이만큼까지 빠르게 담는다
# 카메라가 **움직여 얼굴에서 멈추는** 구도 — 나레이션이 먼저 끝나면 그 멈춤이 잘려 나간다
# (S94 컷9: 법정을 훑다가 땅주인을 찾기 전에 컷이 넘어가 빈 법정만 2초 보였다)
LAND_MOVES = ("descend", "crane", "pan", "through", "rise", "pull", "zoom", "arc", "push")
TALK_LEAD, TALK_TAIL = 0.10, 0.25  # 대사 컷 — 말 앞뒤로 남기는 숨(초) · 끝소리가 약해 뒤를 넉넉히
WORKERS = 3                        # 옴니를 한 번에 몇 개씩
RETRY_429 = 3

EYE_LINE = ("the eye line held about a third of the way down from the top of the "
            "vertical frame")
OMNI_HEAD = ("A short fictional drama scene. Every character is invented for this "
             "story and resembles nobody.")
COLOR = ("COLOR: warm neutral base, low overall contrast, slightly lifted blacks, "
         "muted greens and cyans, natural unsaturated skin tones, the exact same "
         "colour grade in every shot of this story.")
STYLE = ("STYLE: naturalistic cinematic drama, soft film grain, muted desaturated "
         "palette, soft natural light.")
NO_TEXT = ("ON SCREEN: no text, no letters, no subtitles, no captions, no watermark, "
           "no logo, no speech bubbles, no typography anywhere on screen.")
REF_ONLY = ("Use the given images only as references for how the people look; the "
            "video opens on a fresh shot of the scene.")

_lock = threading.Lock()
GAP = S9.PAD_TIGHT                 # 말 사이 쉼 — load() 가 대본(gap)에서 정한다
# ⭐ 옴니 영상 꼴 — 세로 쇼츠 9:16 · 가로 긴 영상 16:9 (load() 가 대본 layout 에서 정한다)
RATIO = "9:16"
EYE_LINE_WIDE = ("the eye line held about a third of the way down from the top of the "
                 "frame")
# ⚠️ 2026-10-06 S95 첫 시험 컷(컷4) — 「Horizontal 16:9 widescreen」 「cinematic drama」 로 지었더니
#    옴니가 1280×720 안에 **위아래 검은 띠(레터박스 · 각 약 10%)** 를 넣었다. 와이드스크린 · 시네마틱이
#    극장 화면비를 부른다 → 가로는 「full-frame 16:9」 · 「TV 드라마」 로 바라는 것만 적는다 (세로는 그대로)
STYLE_WIDE = ("STYLE: naturalistic Korean TV drama look in a full-frame 16:9 picture, soft film grain, "
              "muted desaturated palette, soft natural light.")
NO_BUY = False                     # --no-buy : 창고에 없는 컷이 있으면 사지 말고 멈춘다


def vdir():
    return S9.video_dir()


# ── ⭐ 영상 창고 — 같은 장면은 다시 안 산다 (2026-10-02) ─────────────────
#    손님: "처음보는 사람이 보아도 스토리 전개를 이해하고 공감할 수 있도록" → 대본을 고쳐
#    컷 차례·나레이션 길이가 바뀌었다. 컷 번호로 영상을 찾으면 15컷을 통째로 다시 사야 한다.
#    → **화면 묘사 · 나오는 사람 · (대사 컷이면) 대사**가 같으면 같은 영상이다. 창고에서 꺼내
#      그 구도 그대로 쓰고(카메라 계획에 고정), 길이는 늘이기·줄이기로 맞춘다 (0원).
LIB = "library.json"


def lib_path():
    return vdir() / LIB


def load_lib():
    f = lib_path()
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def save_lib(lib):
    lib_path().parent.mkdir(parents=True, exist_ok=True)
    lib_path().write_text(json.dumps(lib, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")


def vkey(c):
    """같은 장면인가 — 화면 묘사 · 나오는 사람 · 대사(대사 컷만). 컷 번호·길이는 안 본다.
    가로(16:9) 영상은 열쇠에 꼴을 붙인다 — 세로로 산 영상을 가로 영상에 다시 쓰지 않게
    (세로 열쇠는 예전 그대로라 이미 산 창고가 그대로 맞는다)."""
    line = c["turns"][0][1] if is_talk(c) else ""
    wide = ("16:9",) if RATIO != "9:16" else ()
    return reuse.sig_of("v60", c.get("scene") or "", "|".join(c.get("who") or []), line, *wide)


def res_of(doc, asked=""):
    """옴니 영상 화질 — --res 가 이기고, 없으면 대본 res, 그것도 없으면 360p."""
    r = str(asked or (doc or {}).get("res") or ST90.RES_DEFAULT).strip().lower()
    if r not in RES_CHOICES:
        raise SystemExit(f"❌ 화질은 {' 또는 '.join(RES_CHOICES)} 가운데 하나다 (받은 것: {r})")
    return r


def rank(r):
    """화질 높낮이 — 창고 영상은 고른 화질 **이상**일 때만 다시 쓴다."""
    r = str(r or ST90.RES_DEFAULT).lower()
    return RES_CHOICES.index(r) if r in RES_CHOICES else 0


def load(sid, res=""):
    f = ROOT / "data" / "series" / f"{sid}.json"
    if not f.exists():
        raise SystemExit(f"❌ data/series/{sid}.json 이 없다 — "
                         f"python3 tools/build_short90.py {sid} 를 먼저 돌린다")
    doc = json.loads(f.read_text(encoding="utf-8"))
    if not doc.get("all_video"):
        raise SystemExit(f"❌ {sid} 는 1분 전부 영상 대본이 아니다 (all_video 가 없다)")
    global GAP, RES, RATIO
    GAP = S9.gap_of(doc)
    S9.PAD = GAP                   # 조립(cut_sec)과 같은 값으로 컷 길이를 센다
    RES = res_of(doc, res)
    # ⭐ 세로 쇼츠 / 가로 긴 영상 — 조립·그림(diagram60)·옴니가 같은 꼴을 쓴다
    RATIO = "16:9" if S9.use_layout(doc) == "long" else "9:16"
    CUR["doc"] = doc
    return doc


def cast_of(doc):
    """인물표 (목소리는 나이·성별·톤이 고정된 줄로)."""
    return {p["name"]: p for p in ST90.fix_voices(doc.get("cast") or [])}


def role(by, nm):
    return str((by.get(nm) or {}).get("role_en") or nm)


def english(text, by):
    out = str(text or "")
    for nm in sorted(by, key=len, reverse=True):
        out = out.replace(nm, role(by, nm))
    return out


def card(nm):
    return S9.cards_dir() / f"{castsheet.ALIAS.get(nm, nm)}.png"


def is_talk(c):
    return not S9.is_narr(c)


def is_fig(c):
    """그림 컷 — 관계도·연표 등 우리가 직접 그린다 (옴니 안 씀 · 0원 · src/diagram60.py)."""
    return bool(c.get("fig"))


# ── 길이 ─────────────────────────────────────────────────────────
CUR = {}                           # load() 가 지금 대본을 둔다 (목소리 지문을 맞춰 보려고)


def voice_file(c):
    """그 컷 목소리 파일 — **지금 대본의 그 컷 것일 때만** (아니면 None).
    ⚠️ 2026-10-05 — 만드는 자리(build/s90)는 사건이 함께 쓴다. S95 목소리를 만들기 전에 값을 셌더니
       S94 목소리(컷1~30) 길이로 영상 길이를 재서 105초 · 16,207원이 나왔다(글자 잣대로는 91초 · 14,046원).
       → 목소리 지문(short90.voice_plan)이 맞는 것만 믿는다. 대본 없이 부르면(시험) 예전처럼 있는 대로."""
    w = S9.OUT / "voice" / f"c{c['n']:02d}.wav"
    if not w.exists():
        return None
    doc = CUR.get("doc")
    if doc is not None and not reuse.can_reuse(w, S9.voice_plan(c, doc)[0])[0]:
        return None
    return w


def narr_len(c):
    """나레이션이 화면에 머무는 길이(초) — 앞뒤 무음을 자른 목소리 ÷ 배속 + 여운.
    목소리가 아직 없으면(또는 다른 대본 것이면) 글자 잣대로 어림한다."""
    w = voice_file(c)
    if w:
        return S9.dur_of(w) / S9.speed() + GAP
    return ST90.char_sec(S9.speed()) * ST90.chars(c) + GAP + 0.3


def omni_sec(c):
    if is_talk(c):
        return talkplan.omni_sec(c["turns"][0][1])
    need = narr_len(c) + NARR_MARGIN
    return int(min(SEC_MAX, max(SEC_MIN, math.ceil(need))))


# ── 영상 지문 ─────────────────────────────────────────────────────
def timeline_narr(cam, sec, fill):
    t1, t2, t3 = round(min(1.0, sec * 0.2), 1), round(sec * 0.55, 1), round(sec * 0.8, 1)
    f = [x.format(**fill) for x in cam]
    return [f"[0.0-{t1:.1f}s] Camera: {f[0]}. The action in SHOT is already under "
            "way; every mouth stays closed.",
            f"[{t1:.1f}-{t2:.1f}s] Camera: {f[1]}. The action continues naturally and "
            "calmly; lips stay closed.",
            f"[{t2:.1f}-{t3:.1f}s] Camera: {f[2]}.",
            f"[{t3:.1f}-{float(sec):.1f}s] Camera: {f[3]}."]


def timeline_talk(cam, sec, text, who_role, listener, fill):
    f = [x.format(**fill) for x in cam]
    ss = talkplan.omni_sentences(text)
    cap = who_role[:1].upper() + who_role[1:]
    rows = [f"[0.0-{talkplan.OMNI_LEAD:.1f}s] {cap} draws a quick breath"
            + (f" while {listener} listens with lips closed" if listener else "")
            + f". Camera: {f[0]}."]
    t = talkplan.OMNI_LEAD
    for i, one in enumerate(ss):
        k = len(re.sub(r"[\s…·.,!?\"'~]", "", one)) / talkplan.OMNI_CHARS_PER_SEC
        rows.append(f"[{t:.1f}-{t + k:.1f}s] {cap} says in Korean: \"{one}\" "
                    f"Camera: {f[1]}.")
        t += k
        if i + 1 < len(ss):
            rows.append(f"[{t:.1f}-{t + talkplan.OMNI_PAUSE:.1f}s] One short breath. "
                        f"Camera: {f[2]}.")
            t += talkplan.OMNI_PAUSE
    rows.append(f"[{t:.1f}-{float(sec):.1f}s] Silent, lips closed, {who_role} holds "
                f"the look until the end. Camera: {f[3]}.")
    return rows


def prompt(c, shot, sec, by):
    who = [w for w in (c.get("who") or []) if w in by]
    refs = [f"<IMAGE_REF_{i}>" for i in range(len(who))]
    head = ("[# References " + " ".join(f"{r}@Image{i + 1}" for i, r in enumerate(refs))
            + "]")
    one = len(who) == 1
    cast = " and ".join(f"{role(by, w)} {r}" for w, r in zip(who, refs))
    talks = is_talk(c)
    speaker = c["turns"][0][0] if talks else (who[0] if who else "")
    other = next((w for w in who if w != speaker), "")
    fill = {"main": role(by, who[0]) if who else "the scene",
            "speaker": role(by, speaker), "other": role(by, other) if other else "",
            "fg": (f"{role(by, other)}'s shoulder" if other
                   else "a detail of the scene")}
    scene = english(c.get("scene"), by).rstrip(".")
    lens = camera60.LENS[shot["lens"]]
    height = camera60.HEIGHT[shot["height"]]
    # ⚠️ 세로 지문은 한 글자도 안 바꾼다 — 이미 산 영상의 지문(창고 · adopt)이 그대로 맞아야 한다
    wide = RATIO == "16:9"
    shape = ("Full-frame landscape 16:9 video, the picture reaching all four edges of the frame"
             if wide else "Vertical 9:16")
    frame = ("full-frame landscape 16:9 picture" if wide else "vertical 9:16 portrait")
    eye = EYE_LINE_WIDE if wide else EYE_LINE
    rows = [
        head,
        f"{OMNI_HEAD} {shape}, exactly {sec} seconds, one single continuous shot "
        "from the first frame to the last.",
        (f"CAST: {cast} is the only person in this scene, looking exactly like the "
         "reference the whole time. The reference shows that person twice — a close "
         "view and a full-length view — one single person." if one else
         f"CAST: {cast} are the only people in this scene, each looking exactly like "
         "their own reference the whole time. Each reference shows that person twice "
         "— a close view and a full-length view — one single person."),
        f"SHOT: {scene}. {shot['text'].format(**fill)}.",
    ]
    if shot["kind"] in ("est", "end"):
        rows.append(f"FRAMING: {frame}, filling the whole frame edge to "
                    f"edge; wherever the person is in view, {fill['main']}'s face is "
                    "clearly readable.")
    elif talks:
        rows.append(f"FRAMING: {frame}, filling the whole frame edge to "
                    f"edge, {fill['speaker']}'s face and lips clearly visible and "
                    f"sharp, {eye}.")
    else:
        rows.append(f"FRAMING: {frame}, filling the whole frame edge to "
                    f"edge, {fill['main']}'s face clearly visible and sharp, "
                    f"{eye}.")
    rows.append(f"CAMERA: {lens}, {height}.")
    rows.append("TIMELINE:")
    if talks:
        text = c["turns"][0][1]
        p = by.get(speaker) or {}
        say = "; ".join(str(x) for x in (c.get("say") or []) if str(x).strip())
        rows += timeline_talk(shot["cam"], sec, text, fill["speaker"], fill["other"],
                              fill)
        rows += [
            f"DIALOGUE: [LANGUAGE: KOREAN] only {fill['speaker']} speaks, in natural "
            "fluent everyday Korean with standard Seoul intonation, at a brisk natural "
            "conversational pace with every consonant and syllable crisp and clearly "
            "articulated, lips moving in sync with every syllable. "
            f"{fill['speaker'][:1].upper() + fill['speaker'][1:]} says these exact "
            "words once and nothing more: "
            f"\"{text}\"",
            f"VOICE: {fill['speaker']} — {ST90.voice_line(p)}."
            + (f" Delivery (Korean note): {say}." if say else ""),
            f"SOUND: {fill['speaker']}'s voice with the quiet ambient sound of the "
            "place underneath, and nothing else.",
        ]
    else:
        rows += timeline_narr(shot["cam"], sec, fill)
        rows += ["ACTION: nobody speaks at any point; every mouth stays closed the "
                 "whole time.",
                 "SOUND: only the quiet ambient sound of the place, with no voices "
                 "and no music."]
    rows += [COLOR, STYLE_WIDE if wide else STYLE, NO_TEXT, REF_ONLY]
    return "\n".join(r for r in rows if r)


def stock(c, lib):
    """창고에 이 장면이 있으면 그 칸, 아니면 None.

    ⚠️ 예전에는 늘여도(1.4배) 나레이션보다 짧으면 **새로 샀다.** 2026-10-02 손님이 "살릴 수
       있는 영상은 최대한 살리고" 하셨다 → 1.6배까지 늘이고, 그래도 모자란 만큼은 마지막
       장면에서 멈춰 선다(hold). 몇 초 멈추는지는 계획표에 찍힌다."""
    e = lib.get(vkey(c))
    if not e or not (vdir() / e["raw"]).exists():
        return None
    # ⭐ 고른 화질보다 낮게 산 영상은 안 쓴다 — 720p 영상에 360p 컷이 섞이면 그 컷만 흐리다.
    #    (창고에 옛 화질 표시가 없으면 360p 로 산 것이다 — 2026-10-02 까지는 360p 뿐이었다)
    if rank(e.get("res")) < rank(RES):
        return None
    if not is_talk(c):
        short = narr_len(c) + 0.05 - S9.dur_of(vdir() / e["raw"]) * STRETCH_REUSE
        e = dict(e, hold=round(max(0.0, short), 2))
    return e


FIG_SHOT = {"key": "그림", "kind": "fig", "lens": "-", "height": "-", "move": "-",
            "special": False}


def plan(doc, lib=None, quiet=False):
    """컷마다 {n, shot, sec, prompt, refs, krw, lib} — 값 0원.
    그림 컷(fig)은 옴니를 안 사므로 카메라 계획에서 빼고 따로 줄을 세운다."""
    by = cast_of(doc)
    lib = load_lib() if lib is None else lib
    real = [c for c in doc["cuts"] if not is_fig(c)]
    have = {i: stock(c, lib) for i, c in enumerate(real)}
    # ⭐ 같은 장면의 나레이션 컷이 한 편에 두 번 이상 나오면 **한 번만 산다** (2026-10-05 · S95)
    #    예전에는 컷마다 따로 사서 같은 영상 값을 두세 번 냈다 (S95 긴 영상: 나레이션 16컷 중 6컷).
    #    뒤 컷은 앞 컷이 산 영상을 창고에서 다시 쓴다(구도도 같다). 대사 컷은 입모양이 달라 따로 산다.
    first, dup = {}, {}
    for i, c in enumerate(real):
        if have.get(i) or is_talk(c):
            continue
        dup_i = first.setdefault(vkey(c), i)
        if dup_i != i:
            dup[i] = dup_i
    # ⭐ 낮은 화질로 산 영상을 720p 로 다시 살 때도 **구도는 그대로** 둔다 (손님이 본 그 화면)
    pinned = {i: (have.get(i) or lib.get(vkey(c)))["shot"] for i, c in enumerate(real)
              if have.get(i) or (lib.get(vkey(c)) or {}).get("shot")}
    # ⭐ 앞 컷 구도를 고를 때 **그 영상을 다시 쓰는 뒤 컷의 이웃**도 보게 한다 (2026-10-06 · S95 컷38)
    tie = {}
    for i, j in dup.items():
        tie.setdefault(j, []).append(i)
    shots = camera60.plan(real, pinned, tie)
    if dup:
        # 앞 컷과 뒤 컷을 **둘 다** 앞 컷 구도에 못 박는다 — 뒤만 박으면 다시 짤 때 앞 컷 구도가 바뀐다
        for i, j in dup.items():
            pinned.setdefault(j, shots[j])
            pinned[i] = pinned[j]
        shots = camera60.plan(real, pinned, tie)
    rows = {}
    for i, (c, sh) in enumerate(zip(real, shots)):
        e = have.get(i)
        j = dup.get(i)
        sec = e["sec"] if e else omni_sec(real[j] if j is not None else c)
        refs = [card(w) for w in (c.get("who") or []) if w in by]
        rows[c["n"]] = {"n": c["n"], "shot": sh, "sec": sec,
                        "prompt": e["prompt"] if e else prompt(real[j] if j is not None else c,
                                                               sh, sec, by),
                        "refs": refs, "krw": 0 if (e or j is not None) else omni.est_krw(sec, RES),
                        "talk": is_talk(c), "lib": e, "key": vkey(c), "fig": False,
                        "dup_of": real[j]["n"] if j is not None else None}
    out = [rows.get(c["n"]) or {"n": c["n"], "shot": FIG_SHOT, "sec": 0, "prompt": "",
                                "refs": [], "krw": 0, "talk": False, "lib": None,
                                "key": "", "fig": True}
           for c in doc["cuts"]]
    bad = camera60.check(real, shots, reuse=set(dup))      # 같은 장면 다시 쓰기는 특별 시점을 두 번 안 센다
    # ⚠️ 구도가 전부 정해져 있으면(이미 산 영상 · 화질만 올려 다시 사는 영상) 구도 규칙은
    #    알리기만 한다 — 손님이 이미 본 화면이라 막을 까닭이 없다
    if bad and len(pinned) == len(real):
        for b in ([] if quiet else bad):
            print(f"  ℹ️ (이미 정해진 구도라 그대로 씀) {b}")
        bad = []
    return out, bad


def price(doc, res, lib=None):
    """그 화질로 만들면 (새로 살 초, 값) — 창고에 그 화질 이상이 있는 컷은 0원 (0원 · 어림)."""
    global RES
    keep, RES = RES, res
    try:
        rows, _ = plan(doc, lib, quiet=True)
    finally:
        RES = keep
    return (sum(r["sec"] for r in rows if not r.get("fig") and not r["lib"] and not r.get("dup_of")),
            sum(r["krw"] for r in rows))


def run_cap():
    """옴니 한 번 실행 한도 — 드라마는 손님이 승인한 한 편 한도(16,000원 · 2026-09-30).
    720p 한 편(영상 약 1만 2천 원)이 8,000원 기본 한도에서 반쪽만 사고 멈추지 않게.
    VT_RUN_KRW 를 따로 주면 그 값이 이긴다."""
    return cost.RUN_KRW if os.environ.get("VT_RUN_KRW") else max(cost.RUN_KRW, cost.DRAMA_RUN_KRW)


def show_plan(doc, rows, bad, full=False):
    print(f"■ {doc['sid']} 「{doc['title']}」 — 전부 영상 드라마 · 옴니 {RES} {RATIO} · "
          f"{len(rows)}컷")
    for c, r in zip(doc["cuts"], rows):
        s = r["shot"]
        if r.get("fig"):
            print(f"  {c['n']:>2} 그림 — 「{c['fig'].get('id')}」 직접 그림 0원 · {c['text'][:26]}")
            continue
        hold = (r["lib"] or {}).get("hold") or 0
        same = f"컷{r['dup_of']} 영상 다시 씀 0원 " if r.get("dup_of") else ""
        print(f"  {c['n']:>2} {'대사' if r['talk'] else '나레'} {r['sec']:>2}초 "
              f"{s['key']:<13} {s['lens']:<7} {s['height']:<6} {s['move']:<9} "
              f"{'창고 0원 ' if r['lib'] else ''}{same}"
              f"{f'(끝 {hold:.1f}초 멈춤) ' if hold > 0.05 else ''}{c['text'][:26]}")
    tot = sum(r["sec"] for r in rows if not r["lib"] and not r.get("fig") and not r.get("dup_of"))
    krw = sum(r["krw"] for r in rows)
    print(f"  ─ 새로 살 옴니 {tot}초 · 약 {krw:,.0f}원 · {RES} "
          f"(창고에서 다시 쓰는 컷 {sum(1 for r in rows if r['lib'])}개 · "
          f"같은 장면 다시 쓰는 컷 {sum(1 for r in rows if r.get('dup_of'))}개는 0원)")
    # ⭐ 화질은 손님이 고른다 — 다른 화질로 만들면 얼마인지 늘 같이 보인다
    for alt in RES_CHOICES:
        if alt != RES:
            t2, k2 = price(doc, alt)
            print(f"    · {alt} 로 만들면: 새로 살 옴니 {t2}초 · 약 {k2:,.0f}원 "
                  f"(--res {alt} · 대본 res 에 적으면 늘 그 화질)")
    if krw > run_cap():
        print(f"  ⚠️ 한 번 실행 한도 {run_cap():,.0f}원을 넘는다 — 한도에서 멈추면 다시 돌린다 "
              f"(산 컷은 창고에 남아 없는 것만 산다)")
    for b in bad:
        print(f"  ⚠️ {b}")
    if full:
        for r in rows:
            print(f"\n── 컷{r['n']} ({r['sec']}초 · 참조 {len(r['refs'])}장) ──\n"
                  f"{r['prompt']}")
    return krw


# ── 단계 ─────────────────────────────────────────────────────────
def step_cast(sid):
    return castsheet.make(sid, S9.cards_dir())


def trim_wav(w):
    """목소리 앞뒤 무음을 잘라 낸다 (앞 0.03초 · 뒤 0.06초만 남긴다). 여러 번 해도 같다."""
    tmp = w.with_suffix(".trim.wav")
    S9.run(["ffmpeg", "-y", "-v", "error", "-i", str(w), "-af",
            "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03,"
            "areverse,silenceremove=start_periods=1:start_threshold=-45dB:"
            "start_silence=0.06,areverse", str(tmp)])
    if S9.dur_of(tmp) > 0.3:
        tmp.replace(w)
    else:
        tmp.unlink(missing_ok=True)


def step_voice(doc):
    if S9.voices(doc):
        return 1
    import tts                                               # 늦게 부른다(열쇠 필요)
    for c in doc["cuts"]:
        w = S9.OUT / "voice" / f"c{c['n']:02d}.wav"
        # ⚠️ wav 안에 wav 가 한 겹 더 든 옛 파일 — 머리말이 '틱', 끝 출처 글이 잡음이 된다
        if tts.unwrap_file(w):
            print(f"  🔧 컷{c['n']:>2} 목소리 속 wav 한 겹을 벗겼다 (틱·끝 잡음 제거 · 0원)")
        if not S9.is_narr(c):
            continue
        before = S9.dur_of(w)
        trim_wav(w)
        after = S9.dur_of(w)
        S9.lens_of(w).write_text(json.dumps([round(after, 3)]), encoding="utf-8")
        print(f"  ✂️ 컷{c['n']:>2} 목소리 {before:.2f}초 → {after:.2f}초 (앞뒤 무음)")
    return 0


# ⭐ 2026-10-02 — 옴니가 가끔 **액자 속 그림**을 만든다 (S94 컷1: 위아래 약 10% · 좌우 약 4%
#    옅은 하늘색 테두리 · 카메라가 움직여도 테두리는 그대로). 첫 컷이라 바로 눈에 띄었다.
#    네 변 **모두**에 움직이지 않는 단색 띠가 있을 때만 안쪽을 영상 꼴(9:16 · 16:9)로 잘라 쓴다
#    (하늘처럼 위쪽만 고른 화면을 테두리로 잘못 보고 자르지 않게).
FRAME_MIN = 0.02


def probe_wh():
    """테두리를 재는 크기 — 세로 360×640 · 가로 640×360."""
    return (640, 360) if RATIO == "16:9" else (360, 640)


def frame_box(raw):
    """테두리 안쪽 (w, h, x, y) — probe_wh() 크기 기준. 테두리가 없으면 None."""
    from PIL import Image, ImageChops, ImageStat
    dur = S9.dur_of(raw)
    if dur <= 0.3:
        return None
    pw, ph = probe_wh()
    ims = []
    for f in (0.2, 0.5, 0.8):
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{dur * f:.2f}", "-i", str(raw),
                            "-frames:v", "1", "-vf", f"scale={pw}:{ph}", "-f", "image2pipe",
                            "-vcodec", "png", "-"], capture_output=True)
        if not r.stdout:
            return None
        ims.append(Image.open(io.BytesIO(r.stdout)).convert("L"))
    w, h = ims[0].size
    moved = ImageChops.lighter(ImageChops.difference(ims[0], ims[1]),
                               ImageChops.difference(ims[1], ims[2]))
    mid = ims[1]

    def still_flat(box):
        # 테두리는 **안 움직이고**(앞뒤 장면 차이 < 4) 거의 한 색이다(위아래로 옅은
        # 그러데이션은 있어 표준편차 16 까지 본다). 화면 안쪽은 차이가 30 넘게 난다.
        return (ImageStat.Stat(moved.crop(box)).mean[0] < 4.0
                and ImageStat.Stat(mid.crop(box)).stddev[0] < 16.0)

    def run(n, box_of):
        k = 0
        while k < n // 3 and still_flat(box_of(k)):
            k += 1
        return k

    top = run(h, lambda k: (0, k, w, k + 1))
    bot = run(h, lambda k: (0, h - 1 - k, w, h - k))
    left = run(w, lambda k: (k, 0, k + 1, h))
    right = run(w, lambda k: (w - 1 - k, 0, w - k, h))
    if RATIO == "16:9":
        # ⭐ 가로 영상 — 위아래 띠(레터박스)만 있어도 잘라 낸다 (S95 컷4 · 위아래 각 약 10%).
        #    안쪽이 16:9 보다 넓으므로 양옆을 조금 덜어 16:9 로 맞추고 원래 크기로 키운다.
        #    중간에 걷히는 띠도 잡는다 (dark_bars · S95 컷20)
        dt, db = dark_bars(raw, dur, w, h)
        top, bot = max(top, dt), max(bot, db)
        if min(top, bot) < h * FRAME_MIN:
            return None
        if min(left, right) < w * FRAME_MIN:
            left = right = 0
    elif min(top, bot) < h * FRAME_MIN or min(left, right) < w * FRAME_MIN:
        return None
    iw, ih = w - left - right, h - top - bot
    if RATIO == "16:9":
        cw, ch = min(iw, ih * 16 // 9), min(ih, iw * 9 // 16)
    else:
        cw, ch = min(iw, ih * 9 // 16), min(ih, iw * 16 // 9)
    cw, ch = cw - cw % 2, ch - ch % 2
    return cw, ch, left + (iw - cw) // 2, top + (ih - ch) // 2


def dark_bars(raw, dur, pw, ph, n=9):
    """가로 영상의 **까만 띠**(레터박스) 줄 수 (위, 아래) — 장면 n 장에서 세어 가장 큰 값 (0원).
    ⭐ 2026-10-06 S95 컷20: 앞 2.5초는 위아래 각 104줄(화면의 14%)이 까맣다가 4초에 다 걷혔다.
       frame_box 의 '안 움직이는 테두리' 검사는 띠가 걷히는 동안 그 자리가 움직여 못 잡았다
       → 띠가 있는 동안의 안쪽으로 **영상 전체**를 자른다 (걷힌 뒤에도 같은 자리 · 화면이 안 튄다).
    ⚠️ 위아래가 거의 같을 때만 띠로 본다 — 어두운 천장이나 바닥 한쪽을 띠로 잘못 보지 않게."""
    from PIL import Image, ImageStat
    top = bot = 0
    for k in range(n):
        at = dur * (0.03 + 0.94 * k / (n - 1))
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{at:.2f}", "-i", str(raw),
                            "-frames:v", "1", "-vf", f"scale={pw}:{ph}", "-f", "image2pipe",
                            "-vcodec", "png", "-"], capture_output=True)
        if not r.stdout:
            continue
        im = Image.open(io.BytesIO(r.stdout)).convert("L")
        w, h = im.size

        def black(y):
            st = ImageStat.Stat(im.crop((0, y, w, y + 1)))
            return st.mean[0] < 14 and st.stddev[0] < 6        # 거의 0 으로 고른 까만 줄

        t = next((y for y in range(h // 3) if not black(y)), h // 3)
        b = next((y for y in range(h // 3) if not black(h - 1 - y)), h // 3)
        if min(t, b) >= h * FRAME_MIN and abs(t - b) <= h * 0.03:
            top, bot = max(top, t), max(bot, b)
    return top, bot


def size_of(raw):
    """영상 (가로, 세로) — 세로 360p 는 360×640 · 720p 는 720×1280 (가로는 뒤집힌 꼴)."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height", "-of", "csv=p=0:s=x", str(raw)],
                       capture_output=True, text=True)
    try:
        w, h = (int(x) for x in r.stdout.strip().split("x")[:2])
        return w, h
    except ValueError:
        return probe_wh()


def crop_of(raw):
    """테두리 안쪽만 잘라 **원래 크기**로 — 상자는 probe_wh() 크기에서 재고 영상 크기만큼 곱한다
    (720p 영상을 360 기준 자리로 자르면 엉뚱한 곳이 잘린다)."""
    b = frame_box(raw)
    if not b:
        return ""
    w, h = size_of(raw)
    k = w / float(probe_wh()[0])
    cw, ch, x, y = (int(round(v * k)) for v in b)
    return f"crop={cw // 2 * 2}:{ch // 2 * 2}:{x}:{y},scale={w}:{h},"


BAR_MOVE = 0.02                                # 띠 두께가 화면 높이의 2% 넘게 바뀌면 '걷히는 띠'


def bar_track(raw):
    """프레임마다 위·아래 까만 줄 수 [(위, 아래)…] — probe_wh() 크기 · 위아래가 거의 같을 때만 띠 (0원)."""
    from PIL import Image, ImageStat
    pw, ph = probe_wh()
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(raw), "-vf", f"scale={pw}:{ph},format=gray",
                        "-f", "rawvideo", "-"], capture_output=True)
    n, out = pw * ph, []
    for k in range(len(r.stdout) // n):
        im = Image.frombytes("L", (pw, ph), r.stdout[k * n:(k + 1) * n])

        def black(y):
            st = ImageStat.Stat(im.crop((0, y, pw, y + 1)))
            return st.mean[0] < 14 and st.stddev[0] < 6

        t = next((y for y in range(ph // 3) if not black(y)), ph // 3)
        b = next((y for y in range(ph // 3) if not black(ph - 1 - y)), ph // 3)
        out.append((t, b) if t and b and abs(t - b) <= ph * 0.03 else (0, 0))
    return out


def unbar(raw):
    """⭐ 중간에 걷히는 까만 띠 → 띠가 있는 동안만 **그만큼 확대**하고, 걷히면 원래 화면 그대로 (0원).
    2026-10-06 S95 컷20: 앞 2.5초는 위아래 각 104줄이 까맣다가 4초에 다 걷혔다. 띠 안쪽 한 자리로
    영상 전체를 자르면 띠가 걷힌 끝 장면에서 남편 머리 위와 아내 얼굴이 잘렸다.
    → 프레임마다 띠 두께를 재어 그 안쪽만 화면 가득 키운다 (띠가 걷히면 카메라가 물러나는 것처럼 보인다).
    돌려주는 것: 띠를 지운 영상(소리는 그대로) · 가로 영상이 아니거나 띠가 안 움직이면 None."""
    if RATIO != "16:9":
        return None
    raw = Path(raw)
    out = raw.with_name(raw.stem + "_unbar.mp4")
    if out.exists() and out.stat().st_mtime >= raw.stat().st_mtime:
        return out
    track = bar_track(raw)
    if not track:
        return None
    pw, ph = probe_wh()
    big = max(max(t, b) for t, b in track)
    if big < ph * FRAME_MIN or min(max(t, b) for t, b in track) > big - ph * BAR_MOVE:
        return None                            # 띠가 없거나 늘 같다 → crop_of 가 한 자리로 자른다
    from PIL import Image
    w, h = size_of(raw)
    k = h / float(ph)
    m = len(track)
    # 앞뒤 2프레임 가운데 가장 두꺼운 띠 + 여유 2줄 — 한 프레임도 까만 줄이 안 비친다
    tops = [max(track[j][0] for j in range(max(0, i - 2), min(m, i + 3))) for i in range(m)]
    bots = [max(track[j][1] for j in range(max(0, i - 2), min(m, i + 3))) for i in range(m)]
    fps = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=r_frame_rate", "-of", "csv=p=0", str(raw)],
                         capture_output=True, text=True).stdout.strip() or "24"
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(raw), "-f", "rawvideo",
                            "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"{w}x{h}", "-r", fps, "-i", "-", "-i", str(raw),
                            "-map", "0:v", "-map", "1:a?", "-c:v", "libx264", "-preset", "veryfast",
                            "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "copy", str(out)],
                           stdin=subprocess.PIPE)
    size, i = w * h * 3, 0
    while True:
        buf = dec.stdout.read(size)
        if len(buf) < size:
            break
        im = Image.frombytes("RGB", (w, h), buf)
        j = min(i, m - 1)
        t = (tops[j] + 2) * k if tops[j] else 0.0
        b = (bots[j] + 2) * k if bots[j] else 0.0
        ih = h - t - b
        iw = w * ih / h
        x0 = (w - iw) / 2
        if t or b:
            im = im.resize((w, h), Image.LANCZOS, box=(x0, t, x0 + iw, t + ih))
        enc.stdin.write(im.tobytes())
        i += 1
    enc.stdin.close()
    dec.wait()
    if enc.wait() != 0 or not out.exists():
        out.unlink(missing_ok=True)
        return None
    return out


def post_talk(raw, out):
    """대사 컷 — 말 앞뒤만 남기고 화면·소리를 함께 1.28배로 (입이 안 어긋난다)."""
    raw = unbar(raw) or raw                    # 가로 영상 — 중간에 걷히는 까만 띠는 그만큼만 확대
    dur = S9.dur_of(raw)
    beg, fin = S9.speech_span(raw)
    beg = max(0.0, (beg or 0.0) - TALK_LEAD)
    k = min(S9.SPEED, S9.SPEED_MAX)
    # ⭐ 말 뒤 쉼 — 감은 뒤에 gap 초가 되도록 (기본은 TALK_TAIL · S94 v5 0.5초)
    fin = min(dur, (fin or dur) + max(TALK_TAIL, GAP * k))
    S9.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-filter_complex",
            f"[0:v]{crop_of(raw)}trim={beg:.3f}:{fin:.3f},setpts=(PTS-STARTPTS)/{k:.4f}[v];"
            f"[0:a]atrim={beg:.3f}:{fin:.3f},asetpts=PTS-STARTPTS,"
            f"{S9.tempo_filter(k)}[a]",
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-ar", "48000", "-ac", "2", str(out)])
    return f"말 {beg:.2f}~{fin:.2f}초 → {S9.dur_of(out):.2f}초"


def post_narr(raw, out, need, land=False, stretch=STRETCH_MAX):
    """나레이션 컷 — 소리는 안 쓴다. 나레이션보다 짧으면 화면만 살짝 느리게 늘인다.
    land=True(움직여 얼굴에서 멈추는 구도)면 길 때 화면을 조금 빠르게 담아 **멈춘 얼굴까지** 보인다."""
    moving = unbar(raw)                        # 가로 영상 — 중간에 걷히는 까만 띠는 그만큼만 확대
    raw = moving or raw
    dur = S9.dur_of(raw)
    if dur >= need:
        k = max(SQUEEZE_MIN, need / max(0.1, dur)) if land else 1.0
    else:
        k = min(stretch, need / max(0.1, dur))
    cr = crop_of(raw)
    # ⭐ 늘여도 모자라면 마지막 장면에서 멈춰 선다 (되돌려 이으면 장면이 튄다)
    hold = max(0.0, need - dur * k)
    pad = f",tpad=stop_mode=clone:stop_duration={hold + 0.1:.2f}" if hold > 0.02 else ""
    S9.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-an", "-vf",
            f"{cr}setpts={k:.4f}*PTS{pad}", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "18", "-pix_fmt", "yuv420p", str(out)])
    got = S9.dur_of(out)
    note = f"영상 {dur:.2f}초" + (f" → 느리게 {got:.2f}초" if k > 1.0 else
                                 f" → 빠르게 {got:.2f}초 (멈춘 얼굴까지)" if k < 1.0 else "")
    if hold > 0.02:
        note += f" · 끝 {hold:.1f}초 멈춤"
    if got + 0.05 < need:
        note += f" ⚠️ 나레이션 {need:.2f}초보다 짧다"
    if cr:
        note += " · 액자 테두리를 잘라 냈다"
    if moving:
        note += " · 걷히는 까만 띠를 그만큼만 확대해 지웠다"
    return note


def buy(c, r, by, d, lib):
    """한 컷을 산다 (창고에 있으면 0원). 돌려주는 것: (컷 번호, 글)"""
    if r["lib"]:
        raw = d / r["lib"]["raw"]
        ok = True
    else:
        # 360p 는 옛 이름 그대로 · 다른 화질은 이름에 화질을 붙여 낮은 화질 파일을 덮지 않는다
        raw = d / "raw" / (f"v_{r['key']}.mp4" if RES == ST90.RES_DEFAULT
                           else f"v_{r['key']}_{RES}.mp4")
        ok = False
    if not ok:
        tries = 0
        while True:
            try:
                omni.make(r["prompt"], r["refs"], raw, r["sec"],
                          task="reference_to_video", res=RES, ratio=RATIO)
                break
            except omni.OmniFiltered:
                raise
            except omni.OmniError as e:
                if "한도" in str(e) and tries < RETRY_429:
                    tries += 1
                    time.sleep(25 * tries)
                    continue
                raise
        with _lock:
            lib[r["key"]] = {"raw": str(raw.relative_to(d)), "shot": r["shot"],
                             "sec": r["sec"], "prompt": r["prompt"], "n": c["n"],
                             "scene": c.get("scene"), "who": c.get("who") or [], "res": RES,
                             "ratio": RATIO}
            save_lib(lib)
        how = "새로 삼"
    else:
        how = "창고에서 다시 씀 · 0원"
    out = d / f"c{c['n']:02d}.mp4"
    if r["talk"]:
        note = post_talk(raw, out)
    else:
        sh = r["shot"]
        note = post_narr(raw, out, narr_len(c) + 0.05,
                         land=sh["kind"] in ("est", "end") or sh["move"] in LAND_MOVES,
                         stretch=STRETCH_REUSE if r["lib"] else STRETCH_MAX)
    return c["n"], f"{how} · {note}"


def adopt(doc):
    """옛 방식(컷 번호 raw/cNN.mp4 + 지문 .sig)으로 산 영상을 창고로 옮긴다 (0원 · 여러 번 해도 같다).
    지문이 **지금 대본의 그 컷과 맞는 것만** 옮긴다 — 엉뚱한 컷 영상이 섞이지 않게."""
    d = vdir()
    lib = load_lib()
    real = [c for c in doc["cuts"] if not is_fig(c)]
    shots = camera60.plan(real)
    by = cast_of(doc)
    moved = 0
    for c, sh in zip(real, shots):
        raw = d / "raw" / f"c{c['n']:02d}.mp4"
        if not raw.exists():
            continue
        sec = omni_sec(c)
        p = prompt(c, sh, sec, by)
        refs = [card(w) for w in (c.get("who") or []) if w in by]
        ok, _ = reuse.can_reuse(raw, reuse.sig_of(p, sec, RES, *refs))
        k = vkey(c)
        if not ok or k in lib:
            continue
        dst = d / "raw" / f"v_{k}.mp4"
        raw.replace(dst)
        reuse.sig_file(raw).unlink(missing_ok=True)
        lib[k] = {"raw": str(dst.relative_to(d)), "shot": sh, "sec": sec, "prompt": p,
                  "n": c["n"], "scene": c.get("scene"), "who": c.get("who") or [], "res": RES}
        moved += 1
    if moved:
        save_lib(lib)
        print(f"■ 옛 컷 영상 {moved}개를 창고로 옮겼다 (0원)")
    return moved


def step_clips(doc, only=None):
    adopt(doc)
    lib = load_lib()
    rows, bad = plan(doc, lib)
    if bad:
        print("❌ 카메라 계획이 규칙에 안 맞는다 — 사지 않는다")
        for b in bad:
            print(f"   · {b}")
        return 1
    miss = sorted({p.name for r in rows for p in r["refs"] if not p.exists()})
    if miss:
        print(f"❌ 인물 카드가 없다: {', '.join(miss)} — `cast` 를 먼저 돌린다 (사지 않는다)")
        return 1
    by = cast_of(doc)
    d = vdir()
    (d / "raw").mkdir(parents=True, exist_ok=True)
    show_plan(doc, rows, bad)
    need = [r["n"] for r in rows if not r.get("fig") and not r["lib"] and not r.get("dup_of")
            and (not only or r["n"] in only)]
    if NO_BUY and need:
        print(f"❌ --no-buy — 창고에 없는 컷 {need} 이 있다 (사지 않고 멈춘다)")
        return 1
    omni.CALL_CAP = len(rows) + 6
    cost.RUN_KRW = run_cap()                   # 드라마 한 편 한도 (720p 도 한 번에 끝나게)
    rec = cost.record

    def locked(*a, **k):
        with _lock:
            return rec(*a, **k)

    cost.record = locked                       # 여러 컷을 함께 사도 장부가 안 엉킨다
    spent0 = cost.month_total()
    fails = []
    try:
        mine = [(c, r) for c, r in zip(doc["cuts"], rows)
                if not r.get("fig") and (not only or c["n"] in only)]
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(buy, c, r, by, d, lib): c["n"] for c, r in mine if not r.get("dup_of")}
            for f in futs:
                n = futs[f]
                try:
                    _n, note = f.result()
                    print(f"  ✅ 컷{n:>2} {note}")
                except (omni.OmniError, cost.MonthlyCapReached) as e:
                    fails.append(n)
                    print(f"  ❌ 컷{n:>2} {str(e)[:220]}")
        # 같은 장면 컷은 앞 컷이 산 영상을 창고에서 다시 쓴다 (0원 · 앞 컷이 못 샀으면 같이 못 산다)
        for c, r in mine:
            if not r.get("dup_of"):
                continue
            e = lib.get(r["key"])
            if not e:
                fails.append(c["n"])
                print(f"  ❌ 컷{c['n']:>2} 앞 컷{r['dup_of']} 영상이 없다 — 다시 돌리면 같이 산다")
                continue
            short = narr_len(c) + 0.05 - S9.dur_of(d / e["raw"]) * STRETCH_REUSE
            _n, note = buy(c, dict(r, lib=dict(e, hold=round(max(0.0, short), 2))), by, d, lib)
            print(f"  ✅ 컷{c['n']:>2} {note} (컷{r['dup_of']} 과 같은 장면)")
    finally:
        cost.record = rec
    print(f"■ 이번에 쓴 돈 약 {cost.month_total() - spent0:,.0f}원 "
          f"(이번 달 {cost.month_total():,.0f}원 / {cost.MONTH_KRW:,.0f}원)")
    if fails:
        print(f"❌ 못 산 컷: {fails} — 다시 돌리면 **없는 것만** 산다 (산 것은 0원)")
        return 1
    return 0


def step_figs(doc):
    """그림 컷 → 영상 (값 0원). 목소리 길이를 알아야 컷 길이가 정해지므로 voice 뒤에 돈다."""
    import diagram60                                          # noqa: E402
    figs = [c for c in doc["cuts"] if is_fig(c)]
    if not figs:
        return 0
    miss = [c["n"] for c in figs if not (S9.OUT / "voice" / f"c{c['n']:02d}.wav").exists()]
    if miss:
        print(f"❌ 목소리가 없는 그림 컷: {miss} — `voice` 를 먼저 돌린다")
        return 1
    print(f"■ 그림 컷 {len(figs)}개 — 직접 그린다 (0원)")
    for c in figs:
        sec, _ = S9.cut_sec(c, S9.OUT / "voice" / f"c{c['n']:02d}.wav", None)
        out = vdir() / f"c{c['n']:02d}.mp4"
        diagram60.render(doc, c, sec + 0.25, out)
        print(f"  ✅ 컷{c['n']:>2} 「{c['fig']['id']}」 {sec:.2f}초 → {out.name}")
    return 0


def stale(story, doc):
    """대본(.story.json)을 고치고 build_short90 을 안 돌렸는가 — 제작은 제작본(.json)을 읽는다."""
    def key(d):
        return [(c.get("n"), c.get("turns"), c.get("fig"), c.get("chapter") or "",
                 list(c.get("who") or [])) for c in d.get("cuts") or []]
    return (key(story) != key(doc) or (story.get("figs") or {}) != (doc.get("figs") or {})
            or any((story.get(k) or "") != (doc.get(k) or "")
                   for k in ("style", "res", "layout", "amount_scale")))


def step_check(sid, doc):
    """대본 검사 (0원) — 규격 · 드라마 · 설명 드라마(화면 속 사람 = 나레이션 · 이름 + 씨 ·
    헷갈리는 말 · 대목 표시 · 그림 맞물림). 목소리(값)를 만들기 **전에** 돈다."""
    f = ROOT / "data" / "series" / f"{sid}.story.json"
    if f.exists():
        story = json.loads(f.read_text(encoding="utf-8"))
        bad = ST90.check(story)
        if stale(story, doc):
            bad.append(f"data/series/{sid}.json 이 대본과 다르다 — "
                       f"python3 tools/build_short90.py {sid} 를 다시 돌린다")
    else:
        import diagram60                                      # noqa: E402
        bad = diagram60.validate(doc)
    kind = "설명 드라마" if ST90.is_explainer(doc) else "전부 영상 드라마"
    if bad:
        print(f"❌ {sid} 대본 검사 ({kind}) — {len(bad)}군데")
        for b in bad:
            print(f"   · {b}")
        return 1
    secs = ST90.part_sec(doc["cuts"], doc)
    print(f"✅ {sid} 대본 검사 통과 ({kind} · {len(doc['cuts'])}컷 · 잣대 약 {secs:.0f}초 · 옴니 {RES})")
    return 0


def timetable(doc, durs):
    """[(컷, 시작, 끝, 종류, 말)] — 완성 영상에서 컷마다 몇 초부터 몇 초까지인가."""
    out, t = [], 0.0
    for c, d in zip(doc["cuts"], durs):
        kind = "그림" if is_fig(c) else ("대사" if is_talk(c) else "나레이션")
        out.append((c["n"], t, t + d, kind, str(c["turns"][0][1])))
        t += d
    return out


def mmss(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def secs_of(s):
    """'1:36' · '1분 36초' · '96' → 96.0"""
    m = re.fullmatch(r"\s*(?:(\d+)\s*(?::|분)\s*)?(\d+(?:\.\d+)?)\s*초?\s*", str(s))
    if not m:
        raise SystemExit(f"❌ 시각을 못 읽었다: {s} (예: 1:36)")
    return int(m.group(1) or 0) * 60 + float(m.group(2))


def cut_at(rows, t):
    return next((r for r in rows if r[1] <= t < r[2]), rows[-1] if rows else None)


def step_sheet(doc, at=""):
    """완성 영상 검수 (0원) — 컷마다 한가운데 한 장을 모은 그림 + 컷 시간표.
    손님이 "1분 36초" 처럼 시각으로 짚으면 --at 1:36 으로 몇 번 컷인지 바로 찾는다
    (S94 v5: 1:36 = 컷18 · 땅주인 얼굴 위에 법 원칙 나레이션 — 화면 속 사람과 말이 어긋났다)."""
    from PIL import Image, ImageDraw, ImageFont
    final = S9.part_file(doc, 1)
    parts = [S9.OUT / "parts" / f"c{c['n']:02d}.mp4" for c in doc["cuts"]]
    if not final.exists() or not all(p.exists() for p in parts):
        print("❌ 완성 영상이나 컷 조각이 없다 — `build` 를 먼저 돌린다")
        return 1
    durs = [S9.dur_of(p) for p in parts]
    got = S9.dur_of(final)
    endc = S9.OUT / "parts" / "end.mp4"           # 긴 영상 끝 화면 (컷이 아니다)
    if S9.LAYOUT == "long" and endc.exists():
        got -= S9.dur_of(endc)
    if abs(sum(durs) - got) > 0.5:
        print(f"❌ 컷 조각 합({sum(durs):.1f}초)이 완성 영상({got:.1f}초)과 다르다 — "
              f"다른 사건을 조립한 조각이다. `build` 를 다시 돌린다")
        return 1
    rows = timetable(doc, durs)
    lines = [f"컷{n:>2}  {mmss(a)}~{mmss(b)}  {k:<4}  {t[:34]}" for n, a, b, k, t in rows]
    sid = doc.get("sid") or S9.SID
    (S9.OUT / f"{sid}_cuts.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if at:
        for s in at.split(","):
            r = cut_at(rows, secs_of(s))
            print(f"■ {s.strip()} → 컷{r[0]} ({mmss(r[1])}~{mmss(r[2])} · {r[3]}) 「{r[4]}」")
        return 0
    print("\n".join(lines))
    # 세로 216×384 6칸 · 가로 384×216 5칸
    tw_, th_, cols, lab = (384, 216, 5, 40) if S9.LAYOUT == "long" else (216, 384, 6, 40)
    rows_n = math.ceil(len(rows) / cols)
    sheet = Image.new("RGB", (cols * (tw_ + 8) + 8, rows_n * (th_ + lab + 8) + 8), (16, 18, 24))
    fnt = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "KoPub_Dotum_Pro_Medium.otf"), 24)
    d = ImageDraw.Draw(sheet)
    for i, (n, a, b, k, _t) in enumerate(rows):
        mid = a + (b - a) * 0.55
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{mid:.2f}", "-i", str(final),
                            "-frames:v", "1", "-vf", f"scale={tw_}:{th_}", "-f", "image2pipe",
                            "-vcodec", "png", "-"], capture_output=True)
        x, y = 8 + (i % cols) * (tw_ + 8), 8 + (i // cols) * (th_ + lab + 8)
        if r.stdout:
            sheet.paste(Image.open(io.BytesIO(r.stdout)).convert("RGB"), (x, y + lab))
        d.text((x + 4, y + 6), f"컷{n} {mmss(a)} {k}", font=fnt,
               fill=(232, 197, 112) if k == "그림" else (236, 236, 236))
    out = S9.OUT / f"{sid}_sheet.jpg"
    sheet.save(out, quality=88)
    print(f"■ 검수 그림 {out.relative_to(ROOT)} · 시간표 {sid}_cuts.txt (0원)")
    return 0


# ── ⭐ 맛보기 (0원 · 2026-10-05) ─────────────────────────────────
#    손님께 드린 약속: "돈을 쓰기 전에 볼 수 있도록, 목소리 대신 무음을 넣은 '맛보기 영상'".
#    · 목소리 = 무음 (나레이션 글자 수 × 잣대 · 1.28배로 감기 전 길이) — 자막은 글자 비율로 흐른다
#    · 얼굴 영상 = 자리 표시 화면 (누가 나오는지 · 대사/나레이션 · 같은 장면을 다시 쓰는 컷)
#    · 그림 컷은 진짜로 그린다 (diagram60) · 조립(자막·이름표·대목·제목·끝 화면·음악)도 진짜 그대로
#    · 자리는 build/preview/<사건> — 진짜 제작 자리(build/s90)·상태 파일(state/)·장부를 안 건드린다.
#      옴니·목소리(돈 드는 것)는 부르지 않는다.
PREVIEW_DIR = ROOT / "build" / "preview"
PREVIEW_RATE = 24000


def preview_len(c):
    """그 컷 목소리 길이(초 · 배속으로 감기 **전**) — 글자 잣대로 어림한다."""
    return max(0.6, ST90.char_sec(S9.speed()) * ST90.chars(c) * S9.speed())


def silent_wav(c, out):
    """무음 목소리 + 줄마다 길이(.len.json · 자막이 그 비율로 흐른다)."""
    import wave
    sec = preview_len(c)
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(PREVIEW_RATE)
        w.writeframes(b"\x00\x00" * int(round(sec * PREVIEW_RATE)))
    turns = S9.turns_of(c)
    n = [max(1, len(re.sub(r"\s", "", str(t)))) for _, t in turns]
    S9.lens_of(out).write_text(json.dumps([round(sec * k / sum(n), 3) for k in n]),
                               encoding="utf-8")
    return sec


def placeholder(doc, c, r, by, out):
    """얼굴 영상 자리 표시 화면 → 2초 영상 (조립이 컷 길이만큼 되돌려 잇는다 · 0원)."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    W, H = S9.W, S9.H
    k = H / 1080.0 if W > H else W / 1080.0          # 글씨 배율 (가로 1 · 세로도 1)
    im = Image.new("RGB", (W, H), (28, 32, 42))
    lay = Image.new("RGB", (W, H), (0, 0, 0))
    ImageDraw.Draw(lay).ellipse((W * 0.12, H * 0.05, W * 0.88, H * 0.95), fill=(46, 52, 66))
    im = Image.blend(im, lay.filter(ImageFilter.GaussianBlur(int(H * 0.12))), 0.55)
    d = ImageDraw.Draw(im)
    fb = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "KoPub_Dotum_Pro_Bold.otf"), int(46 * k))
    fm = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "KoPub_Dotum_Pro_Medium.otf"), int(32 * k))
    labels = S9.labels_of(doc)
    who = [w for w in (c.get("who") or []) if w in by]
    # 사람 윤곽 — 머리 + 어깨 (이름표·자막 자리 위 · 화면 위쪽 3분의 2 안)
    top = H * (0.30 if W > H else 0.26)
    rad = H * (0.085 if W > H else 0.05)
    xs = [W * (i + 1) / (len(who) + 1) for i in range(len(who))]
    for x, w in zip(xs, who):
        d.ellipse((x - rad, top - rad, x + rad, top + rad), fill=(92, 98, 114))
        d.pieslice((x - rad * 2.0, top + rad * 1.15, x + rad * 2.0, top + rad * 5.0), 180, 360,
                   fill=(92, 98, 114))
        d.text((x, top + rad * 3.35), labels.get(w) or w, font=fm, fill=(236, 233, 226), anchor="mm")
    head = "얼굴 영상 자리 — 대사" if is_talk(c) else "얼굴 영상 자리 — 나레이션"
    d.text((W / 2, H * 0.115), head, font=fb, fill=(232, 197, 112), anchor="mm")
    sub = (f"컷{c['n']} · 컷{r['dup_of']} 과 같은 영상을 다시 씀 (0원)" if r.get("dup_of")
           else f"컷{c['n']} · {r['sec']}초 영상을 살 자리 · 약 {omni.est_krw(r['sec'], RES):,.0f}원 ({RES})")
    d.text((W / 2, H * 0.115 + 62 * k), sub, font=fm, fill=(200, 204, 212), anchor="mm")
    if not who:
        d.text((W / 2, H * 0.40), "장소 화면 (사람 없음)", font=fb, fill=(150, 155, 166), anchor="mm")
    png = out.with_suffix(".png")
    im.save(png)
    S9.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(png), "-t", "2", "-r",
            str(S9.FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", str(out)])
    png.unlink(missing_ok=True)


def step_preview(sid, doc):
    """맛보기 영상 (0원) → build/preview/<사건>/<사건>_part1.mp4 + 컷마다 한 장 검수 그림."""
    S9.OUT = PREVIEW_DIR / sid
    S9.PREVIEW = True                         # 조립이 상태 파일(만든 기록)을 안 건드린다
    S9.OUT.mkdir(parents=True, exist_ok=True)
    by = cast_of(doc)
    rows, _bad = plan(doc, lib={}, quiet=True)
    print(f"■ {sid} 맛보기 (0원) — 목소리는 무음 · 얼굴 영상은 자리 표시 · 그림 컷은 진짜 · "
          f"→ {S9.OUT.relative_to(ROOT)}")
    vdir().mkdir(parents=True, exist_ok=True)
    tot = 0.0
    for c, r in zip(doc["cuts"], rows):
        tot += silent_wav(c, S9.OUT / "voice" / f"c{c['n']:02d}.wav")
        if not r.get("fig"):
            placeholder(doc, c, r, by, vdir() / f"c{c['n']:02d}.mp4")
    print(f"  무음 목소리 {len(rows)}컷 (약 {tot / S9.speed():.0f}초) · 자리 표시 화면 "
          f"{sum(1 for r in rows if not r.get('fig'))}컷")
    if step_figs(doc):
        return 1
    rc = S9.build(doc)
    if rc:
        return rc
    final = S9.part_file(doc, 1)
    print(f"■ 맛보기 영상 {final.relative_to(ROOT)} · {S9.dur_of(final):.1f}초 · 0원")
    return step_sheet(doc)


def srt_ts(t):
    ms = int(round(max(0.0, t) * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    return f"{h:02d}:{m:02d}:{rem // 1000:02d},{rem % 1000:03d}"


def srt_pieces(text, a, b):
    """한 컷의 말 → [(시작, 끝, 글)] — 문장마다 나누고 **글자 수만큼** 시간을 나눈다 (0원).
    ⭐ 2026-10-06 (S95): 한 컷 말이 80자까지 한 줄로 들어가 자막을 켜면 화면 아래가 세 줄로 찼다."""
    parts = [x.strip() for x in re.split(r"(?<=[.?!])\s+", str(text).strip()) if x.strip()]
    if len(parts) <= 1:
        return [(a, b, str(text).strip())]
    n = sum(len(x) for x in parts)
    out, t = [], a
    for i, x in enumerate(parts):
        e = b if i == len(parts) - 1 else t + (b - a) * len(x) / n
        out.append((t, e, x))
        t = e
    return out


def step_meta(doc):
    """⭐ 긴 영상 올릴 글에 **설명란 대목**을 넣고 **자막 파일**(.srt)을 만든다 (0원 · 2026-10-06 · S95).
    완성 영상의 컷 조각 길이로 시각을 잰다 — build 뒤에 돈다 (build 가 끝에 저절로 부른다).
    · 대목: 대본 yt_chapters (ytmeta.chapter_lines · 유튜브 규칙 0:00 · 셋 이상 · 10초 이상)
    · 자막: 컷마다 그 컷의 말 (화면 자막은 영상에 박혀 유튜브가 못 읽는다 → 검색에 걸리게)
    ⚠️ build_short90 을 다시 돌리면 올릴 글이 대목 없이 다시 써진다 — 그때는 이것을 다시 돌린다."""
    import ytmeta                                             # noqa: E402
    parts = [S9.OUT / "parts" / f"c{c['n']:02d}.mp4" for c in doc["cuts"]]
    if not all(p.exists() for p in parts):
        print("❌ 컷 조각이 없다 — `build` 를 먼저 돌린다")
        return 1
    durs = [S9.dur_of(p) for p in parts]
    rows = timetable(doc, durs)
    starts = {n: a for n, a, _b, _k, _t in rows}
    total = S9.dur_of(S9.part_file(doc, 1))
    meta = ytmeta.meta90(doc, starts, total)
    chap = ytmeta.chapter_lines(doc, starts, total)
    f = ROOT / "data" / "series" / f"{doc['sid']}.meta.json"
    f.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    lines, i = [], 0
    for n, a, b, _k, t in rows:
        for pa, pb, x in srt_pieces(t, a, b):
            i += 1
            lines += [str(i), f"{srt_ts(pa)} --> {srt_ts(max(pa + 0.3, pb - 0.05))}", x, ""]
    srt = S9.part_file(doc, 1).with_suffix(".srt")
    srt.write_text("\n".join(lines), encoding="utf-8")
    print(f"■ 올릴 글 대목 {len(chap)}개 → {f.relative_to(ROOT)} · 자막 {i}줄 → "
          f"{srt.relative_to(ROOT)} (0원)")
    for x in chap:
        print(f"   {x}")
    th = thumb_long(doc, S9.part_thumb(doc, 1))
    if th:
        print(f"■ 긴 영상 썸네일 {th.relative_to(ROOT)} ({th.stat().st_size / 1000:.0f}KB · 0원)")
    return 0


# ⭐ 긴 영상 썸네일 (0원 · 2026-10-06 · S95) — 쇼츠처럼 첫 화면을 그대로 자르지 않는다.
#    긴 영상은 검색·추천 목록에서 **썸네일이 클릭을 정한다**(쇼츠 피드는 썸네일을 안 쓴다).
#    오른쪽에 그 사건 사람의 얼굴(대본 thumb.cut 컷 영상의 한 장면 · 자막·이름표 없는 원본),
#    왼쪽에 큰 글 두 줄(흰 글 + 금색 글 · 굵은 검은 테두리). 1280×720 · 2MB 아래.
THUMB_W, THUMB_H = 1280, 720


def thumb_frame(doc):
    """썸네일 바탕 한 장 (자막 없는 컷 영상에서) — 대본 thumb = {"cut": 컷, "at": 0~1}."""
    from PIL import Image
    th = doc.get("thumb") or {}
    n = int(th.get("cut") or next(c["n"] for c in doc["cuts"] if not is_fig(c)))
    clip = vdir() / f"c{n:02d}.mp4"
    if not clip.exists():
        return None
    at = S9.dur_of(clip) * float(th.get("at") if th.get("at") is not None else 0.5)
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{at:.2f}", "-i", str(clip), "-frames:v", "1",
                        "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    return Image.open(io.BytesIO(r.stdout)).convert("RGB") if r.stdout else None


THUMB_FACE_AT = (0.74, 0.42)                   # 썸네일에서 얼굴 가운데가 올 자리 (오른쪽 · 글은 왼쪽)


def thumb_long(doc, out, bg=None):
    """긴 영상 썸네일 → out (jpg). bg 를 안 주면 thumb_frame.
    대본 thumb = {"cut", "at", "face": [가로, 세로](바탕 장면에서 얼굴 가운데 · 0~1),
                  "zoom": 확대(1~2), "place": [가로, 세로](썸네일에서 얼굴이 올 자리 · 기본 THUMB_FACE_AT),
                  "text": [줄1, 줄2]}
    ⭐ 2026-10-06 (S95): 컷 영상이 이미 16:9 라 '가운데 자리'를 옮겨도 얼굴이 안 움직였다
       (시안 셋 모두 글이 얼굴을 덮었다) → 얼굴 쪽을 조금 키워 **오른쪽**(THUMB_FACE_AT)에 두고
       글은 왼쪽 56% 안에 쓴다."""
    from PIL import Image, ImageDraw, ImageFont
    bg = bg or thumb_frame(doc)
    if bg is None:
        return None
    th = doc.get("thumb") or {}
    src = bg.convert("RGB")
    sw, sh = src.size
    z = min(2.0, max(1.0, float(th.get("zoom") or 1.0)))
    cw = min(sw, sh * THUMB_W / THUMB_H) / z
    ch = cw * THUMB_H / THUMB_W
    fx, fy = (float(v) for v in (th.get("face") or (0.62, 0.40)))
    px, py = (float(v) for v in (th.get("place") or THUMB_FACE_AT))
    x0 = min(fx * sw - px * cw, sw - cw)
    y0 = min(max(0.0, fy * sh - py * ch), sh - ch)
    if x0 >= 0:
        im = src.resize((THUMB_W, THUMB_H), Image.LANCZOS, box=(x0, y0, x0 + cw, y0 + ch))
    else:
        # ⭐ 얼굴이 장면 왼쪽에 가까워 오른쪽 자리까지 못 민다 → 모자라는 왼쪽은 어두운 바탕으로 잇고
        #    장면 왼쪽 끝은 부드럽게 녹인다 (그 자리는 어차피 글 밑 어두운 그늘이다)
        vw = int(round((x0 + cw) * THUMB_W / cw))
        part = src.resize((vw, THUMB_H), Image.LANCZOS, box=(0, y0, x0 + cw, y0 + ch))
        im = Image.new("RGB", (THUMB_W, THUMB_H), (6, 8, 12))
        feather = max(1, min(vw, 260))
        mask = Image.new("L", (vw, 1))
        mask.putdata([min(255, int(255 * (i / feather) ** 1.5)) for i in range(vw)])
        im.paste(part, (THUMB_W - vw, 0), mask.resize((vw, THUMB_H)))
    shade = Image.new("L", (THUMB_W, 1))
    shade.putdata([int(225 * max(0.0, 1 - x / (THUMB_W * 0.66)) ** 1.15) for x in range(THUMB_W)])
    im.paste((6, 8, 12), (0, 0), shade.resize((THUMB_W, THUMB_H)))
    d = ImageDraw.Draw(im)
    lines = [str(x) for x in (th.get("text")
                              or (doc.get("parts") or [{}])[0].get("card") or []) if str(x).strip()][:2]
    fpath = str(ROOT / "assets" / "fonts" / "NanumGothic_ExtraBold.ttf")
    max_w, left = THUMB_W * 0.56, 58
    size = 140
    while size > 64:
        f = ImageFont.truetype(fpath, size)
        if all(d.textlength(x, font=f) <= max_w for x in lines):
            break
        size -= 4
    f = ImageFont.truetype(fpath, size)
    gap = int(size * 1.22)
    y0 = THUMB_H / 2 - gap * (len(lines) - 1) / 2 + 20
    for i, x in enumerate(lines):
        col = (255, 255, 255) if i == 0 else (240, 200, 96)
        d.text((left, y0 + i * gap), x, font=f, fill=col, anchor="lm",
               stroke_width=max(6, size // 14), stroke_fill=(0, 0, 0))
    mf = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "KoPub_Batang_Pro_Bold.otf"), 38)
    d.text((left, 62), S9.CHANNEL, font=mf, fill=(232, 197, 112), anchor="lm",
           stroke_width=3, stroke_fill=(0, 0, 0))
    d.line([(left, 92), (left + 150, 92)], fill=(198, 160, 74), width=3)
    out = Path(out)
    for q in (92, 86, 78, 70):
        im.save(out, quality=q)
        if out.stat().st_size <= S9.THUMB_MAX_BYTES:
            break
    return out


def step_build(doc):
    miss = [c["n"] for c in doc["cuts"] if not (vdir() / f"c{c['n']:02d}.mp4").exists()]
    if miss:
        print(f"❌ 영상이 없는 컷: {miss} — `clips` 를 먼저 돌린다")
        return 1
    rc = S9.build(doc)
    if rc:
        return rc
    final = S9.part_file(doc, 1)
    got = S9.dur_of(final)
    print(f"■ 다 됐다 — {final.relative_to(ROOT)} · {got:.1f}초")
    if got > talkplan.part_max_sec(doc):
        print(f"⚠️ {got:.1f}초 — 벽({talkplan.part_max_sec(doc):.0f}초)을 넘었다")
        return 1
    if S9.LAYOUT == "long" and not S9.PREVIEW:
        return step_meta(doc)                  # 긴 영상 — 설명란 대목 + 자막 파일 (0원)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sid")
    ap.add_argument("what", choices=["check", "plan", "cast", "voice", "clips", "figs", "build",
                                     "sheet", "meta", "preview", "all"])
    ap.add_argument("--no-buy", action="store_true",
                    help="clips — 창고에 없는 컷이 있으면 사지 않고 멈춘다 (0원 보장)")
    ap.add_argument("--full", action="store_true", help="plan — 영상 지문까지 다 보인다")
    ap.add_argument("--only", default="", help="clips — 이 컷만 (예: 2 또는 2,5) · 먼저 한 컷 시험")
    ap.add_argument("--at", default="", help="sheet — 이 시각이 몇 번 컷인지 (예: 1:36 또는 1:36,2:05)")
    ap.add_argument("--res", default="", choices=("",) + RES_CHOICES,
                    help="plan·clips — 옴니 영상 화질 (360p 싸게 · 720p 선명하게). "
                         "비우면 대본 res, 그것도 없으면 360p")
    a = ap.parse_args()
    global NO_BUY
    NO_BUY = a.no_buy
    sid = a.sid.upper()
    doc = load(sid, a.res)
    if a.what == "check":
        return step_check(sid, doc)
    if a.what == "sheet":
        return step_sheet(doc, a.at)
    if a.what == "meta":
        return step_meta(doc)
    if a.what == "preview":
        # ⭐ 값 0원 — 대본 검사를 먼저 본다 (걸린 대본으로 맛보기를 만들면 헛걸음이다)
        return step_check(sid, doc) or step_preview(sid, doc)
    if a.what == "plan":
        rows, bad = plan(doc)
        show_plan(doc, rows, bad, full=a.full)
        return 1 if bad else 0
    # ⭐ 값을 쓰기 전에 대본부터 본다 — 걸린 채로 목소리·영상을 사면 고칠 때 또 산다
    if a.what == "all" and step_check(sid, doc):
        return 1
    if a.what in ("cast", "all") and step_cast(sid):
        return 1
    if a.what in ("voice", "all") and step_voice(doc):
        return 1
    only = {int(x) for x in a.only.replace(" ", "").split(",") if x}
    if a.what in ("clips", "all") and step_clips(doc, only):
        return 1
    if a.what in ("figs", "all") and step_figs(doc):
        return 1
    if a.what in ("build", "all") and step_build(doc):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
