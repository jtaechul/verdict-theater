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
    python3 tools/drama60.py S94 all      check → cast → voice → clips → figs → build 를 차례로

    설명 드라마(대본 style="explainer" · 판결극장 기본 짜임) 짓는 법:
    .claude/skills/verdict-explainer/SKILL.md (본보기 대본 data/series/S94.story.json)

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
    """같은 장면인가 — 화면 묘사 · 나오는 사람 · 대사(대사 컷만). 컷 번호·길이는 안 본다."""
    line = c["turns"][0][1] if is_talk(c) else ""
    return reuse.sig_of("v60", c.get("scene") or "", "|".join(c.get("who") or []), line)


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
    global GAP, RES
    GAP = S9.gap_of(doc)
    S9.PAD = GAP                   # 조립(cut_sec)과 같은 값으로 컷 길이를 센다
    RES = res_of(doc, res)
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
def narr_len(c):
    """나레이션이 화면에 머무는 길이(초) — 앞뒤 무음을 자른 목소리 ÷ 배속 + 여운.
    목소리가 아직 없으면 글자 잣대로 어림한다."""
    w = S9.OUT / "voice" / f"c{c['n']:02d}.wav"
    if w.exists():
        return S9.dur_of(w) / S9.speed() + GAP
    return ST90.SEC60_PER_CHAR * ST90.chars(c) + GAP + 0.3


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
    rows = [
        head,
        f"{OMNI_HEAD} Vertical 9:16, exactly {sec} seconds, one single continuous shot "
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
        rows.append("FRAMING: vertical 9:16 portrait, filling the whole frame edge to "
                    f"edge; wherever the person is in view, {fill['main']}'s face is "
                    "clearly readable.")
    elif talks:
        rows.append("FRAMING: vertical 9:16 portrait, filling the whole frame edge to "
                    f"edge, {fill['speaker']}'s face and lips clearly visible and "
                    f"sharp, {EYE_LINE}.")
    else:
        rows.append("FRAMING: vertical 9:16 portrait, filling the whole frame edge to "
                    f"edge, {fill['main']}'s face clearly visible and sharp, "
                    f"{EYE_LINE}.")
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
    rows += [COLOR, STYLE, NO_TEXT, REF_ONLY]
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
    # ⭐ 낮은 화질로 산 영상을 720p 로 다시 살 때도 **구도는 그대로** 둔다 (손님이 본 그 화면)
    pinned = {i: (have.get(i) or lib.get(vkey(c)))["shot"] for i, c in enumerate(real)
              if have.get(i) or (lib.get(vkey(c)) or {}).get("shot")}
    shots = camera60.plan(real, pinned)
    rows = {}
    for i, (c, sh) in enumerate(zip(real, shots)):
        e = have.get(i)
        sec = e["sec"] if e else omni_sec(c)
        refs = [card(w) for w in (c.get("who") or []) if w in by]
        rows[c["n"]] = {"n": c["n"], "shot": sh, "sec": sec,
                        "prompt": e["prompt"] if e else prompt(c, sh, sec, by),
                        "refs": refs, "krw": 0 if e else omni.est_krw(sec, RES),
                        "talk": is_talk(c), "lib": e, "key": vkey(c), "fig": False}
    out = [rows.get(c["n"]) or {"n": c["n"], "shot": FIG_SHOT, "sec": 0, "prompt": "",
                                "refs": [], "krw": 0, "talk": False, "lib": None,
                                "key": "", "fig": True}
           for c in doc["cuts"]]
    bad = camera60.check(real, shots)
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
    return (sum(r["sec"] for r in rows if not r.get("fig") and not r["lib"]),
            sum(r["krw"] for r in rows))


def run_cap():
    """옴니 한 번 실행 한도 — 드라마는 손님이 승인한 한 편 한도(16,000원 · 2026-09-30).
    720p 한 편(영상 약 1만 2천 원)이 8,000원 기본 한도에서 반쪽만 사고 멈추지 않게.
    VT_RUN_KRW 를 따로 주면 그 값이 이긴다."""
    return cost.RUN_KRW if os.environ.get("VT_RUN_KRW") else max(cost.RUN_KRW, cost.DRAMA_RUN_KRW)


def show_plan(doc, rows, bad, full=False):
    print(f"■ {doc['sid']} 「{doc['title']}」 — 전부 영상 드라마 · 옴니 {RES} 9:16 · "
          f"{len(rows)}컷")
    for c, r in zip(doc["cuts"], rows):
        s = r["shot"]
        if r.get("fig"):
            print(f"  {c['n']:>2} 그림 — 「{c['fig'].get('id')}」 직접 그림 0원 · {c['text'][:26]}")
            continue
        hold = (r["lib"] or {}).get("hold") or 0
        print(f"  {c['n']:>2} {'대사' if r['talk'] else '나레'} {r['sec']:>2}초 "
              f"{s['key']:<13} {s['lens']:<7} {s['height']:<6} {s['move']:<9} "
              f"{'창고 0원 ' if r['lib'] else ''}"
              f"{f'(끝 {hold:.1f}초 멈춤) ' if hold > 0.05 else ''}{c['text'][:26]}")
    tot = sum(r["sec"] for r in rows if not r["lib"] and not r.get("fig"))
    krw = sum(r["krw"] for r in rows)
    print(f"  ─ 새로 살 옴니 {tot}초 · 약 {krw:,.0f}원 · {RES} "
          f"(창고에서 다시 쓰는 컷 {sum(1 for r in rows if r['lib'])}개는 0원)")
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
#    네 변 **모두**에 움직이지 않는 단색 띠가 있을 때만 안쪽을 9:16 으로 잘라 쓴다
#    (하늘처럼 위쪽만 고른 화면을 테두리로 잘못 보고 자르지 않게).
FRAME_MIN = 0.02


def frame_box(raw):
    """테두리 안쪽 (w, h, x, y) — 360×640 기준. 테두리가 없으면 None."""
    from PIL import Image, ImageChops, ImageStat
    dur = S9.dur_of(raw)
    if dur <= 0.3:
        return None
    ims = []
    for f in (0.2, 0.5, 0.8):
        r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{dur * f:.2f}", "-i", str(raw),
                            "-frames:v", "1", "-vf", "scale=360:640", "-f", "image2pipe",
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
    if min(top, bot) < h * FRAME_MIN or min(left, right) < w * FRAME_MIN:
        return None
    iw, ih = w - left - right, h - top - bot
    cw, ch = min(iw, ih * 9 // 16), min(ih, iw * 16 // 9)
    cw, ch = cw - cw % 2, ch - ch % 2
    return cw, ch, left + (iw - cw) // 2, top + (ih - ch) // 2


def size_of(raw):
    """영상 (가로, 세로) — 360p 는 360×640, 720p 는 720×1280."""
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height", "-of", "csv=p=0:s=x", str(raw)],
                       capture_output=True, text=True)
    try:
        w, h = (int(x) for x in r.stdout.strip().split("x")[:2])
        return w, h
    except ValueError:
        return 360, 640


def crop_of(raw):
    """테두리 안쪽만 잘라 **원래 크기**로 — 상자는 360×640 에서 재고 영상 크기만큼 곱한다
    (720p 영상을 360 기준 자리로 자르면 엉뚱한 곳이 잘린다)."""
    b = frame_box(raw)
    if not b:
        return ""
    w, h = size_of(raw)
    k = w / 360.0
    cw, ch, x, y = (int(round(v * k)) for v in b)
    return f"crop={cw // 2 * 2}:{ch // 2 * 2}:{x}:{y},scale={w}:{h},"


def post_talk(raw, out):
    """대사 컷 — 말 앞뒤만 남기고 화면·소리를 함께 1.28배로 (입이 안 어긋난다)."""
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
                          task="reference_to_video", res=RES)
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
                             "scene": c.get("scene"), "who": c.get("who") or [], "res": RES}
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
    need = [r["n"] for r in rows if not r.get("fig") and not r["lib"]
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
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(buy, c, r, by, d, lib): c["n"]
                    for c, r in zip(doc["cuts"], rows)
                    if not r.get("fig") and (not only or c["n"] in only)}
            for f in futs:
                n = futs[f]
                try:
                    _n, note = f.result()
                    print(f"  ✅ 컷{n:>2} {note}")
                except (omni.OmniError, cost.MonthlyCapReached) as e:
                    fails.append(n)
                    print(f"  ❌ 컷{n:>2} {str(e)[:220]}")
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
            or any((story.get(k) or "") != (doc.get(k) or "") for k in ("style", "res")))


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
    tw_, th_, cols, lab = 216, 384, 6, 40
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
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sid")
    ap.add_argument("what", choices=["check", "plan", "cast", "voice", "clips", "figs", "build",
                                     "sheet", "all"])
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
