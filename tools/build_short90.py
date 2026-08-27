#!/usr/bin/env python3
"""⭐ 90초 한 편 대본을 짓는다 — data/series/S90.json (0원 · 인터넷 0회)

    python3 tools/build_short90.py

무엇을 짓나
    data/series/S90_story.py 의 23컷에 **컷마다 완결된 프롬프트 두 벌**을 붙인다.
      still — 그림 한 장 (세로 9:16). 우리 시스템이 이걸로 만든다
      veo   — 영상 한 컷 (세로 9:16). 손님이 제미나이에서 손으로 만들 때 쓴다
                (대사 컷만. 나레이션 컷은 그림 한 장이면 된다)

⚠️ 사람 생김새·옷은 **여기서 안 적는다.** data/series/S001.json 의 인물 카드
   글(charsheet 가 지은 것)에서 뽑아 쓴다. 두 곳에 적으면 한쪽만 고쳐서
   사람이 컷마다 달라진다 — 실제로 화풍이 그렇게 갈렸다.
⚠️ 화풍 문구도 글자로 안 베낀다. src/series.py 의 고정 줄을 가져다 쓴다.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import series as S                                           # noqa: E402

STORY = ROOT / "data" / "series" / "S90_story.py"
BASE = ROOT / "data" / "series" / "S001.json"
OUT = ROOT / "data" / "series" / "S90.json"

# 화면에 뜨는 이름표 ↔ 프롬프트에 쓰는 영어 이름
EN = {"아내": "WIFE", "남편": "HUSBAND", "내연녀": "OTHER WOMAN",
      "딸": "DAUGHTER", "변호사": "LAWYER"}
# 인물 카드에서는 아내를 '본처' 라고 적어 두었다
CARD = {"아내": "본처", "남편": "남편", "내연녀": "내연녀",
        "딸": "딸", "변호사": "변호사"}

VOICE_KO = {
    "아내": "a warm mid-range woman's voice in her fifties, native Korean speaker, "
            "weary and a little breathy, trails off at the end of a sentence",
    "남편": "a low, slightly gravelly man's voice in his fifties, native Korean "
            "speaker, clipped and impatient, drops in volume at the end",
    "내연녀": "a clear woman's voice in her late thirties, native Korean speaker, "
             "cool and unhurried, with a small lilt at the end",
}

FRAMING = ("FRAMING: vertical 9:16 portrait, the person kept in the middle of the "
           "frame with a little room above the head, and the lower fifth of the "
           "frame left plain and uncluttered because a caption will sit there.")
BLUR = ("The background is strongly out of focus and softly blurred, heavy bokeh, "
        "only the people are sharp and in focus.")
COLOR = ("COLOR: warm neutral base, low overall contrast, slightly lifted blacks, "
         "soft amber light from the practical lamps, muted greens and cyans, "
         "natural unsaturated skin tones, the exact same colour grade in every shot "
         "of this story.")
NO_TEXT = ("ON SCREEN: no text, no letters, no subtitles, no captions, no watermark, "
           "no logo, no speech bubbles, no typography anywhere on screen.")


def load_story():
    spec = importlib.util.spec_from_file_location("s90", STORY)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def person_line(sheet):
    """인물 카드 글 → 한 줄짜리 생김새·옷 설명 (컷 프롬프트에 넣을 것)."""
    got = {}
    for ln in (sheet or "").splitlines():
        m = re.match(r"(FACE AND HAIR|BUILD|WEARING):\s*(.+?)\.?\s*$", ln)
        if m:
            got[m.group(1)] = m.group(2).strip(" .")
    bits = [got.get("FACE AND HAIR"), got.get("BUILD")]
    if got.get("WEARING"):
        bits.append("wearing " + got["WEARING"])
    return ", ".join(b for b in bits if b)


def people_of(names, look):
    out = []
    for ko in names:
        line = look.get(CARD.get(ko, ko))
        if line:
            out.append(f"{EN.get(ko, ko)} — {line}.")
    return " ".join(out)


def who_line(names):
    return ", ".join(EN.get(k, k) for k in names)


def still_prompt(c, look):
    who = c.get("who") or []
    body = [S.HEAD_FIX.rstrip(".") + ". A single still frame, vertical 9:16 portrait."]
    if who:
        body.append("PEOPLE: " + people_of(who, look))
        body.append(f"SHOT: {c['scene']}. Framed from the waist up so every face "
                    f"stays clear, static camera, mouths closed, holding the moment.")
    else:
        body.append(f"SHOT: {c['scene']}. Static camera, nobody's face in frame.")
    body += [FRAMING, "CAMERA: " + BLUR, COLOR, S.STYLE_FIX, NO_TEXT]
    return "\n".join(body)


def veo_prompt(c, look):
    """대사 컷을 손으로 만들 때 쓸 영상 프롬프트 (제미나이에 그대로 붙인다)."""
    who = c.get("who") or []
    speaker = c["kind"]
    sec = 4 if c["sec"] <= 4 else (6 if c["sec"] <= 6 else 8)
    body = [f"{S.HEAD_FIX} {sec}-second single continuous take, "
            f"vertical portrait format (9 x 16)."]
    if who:
        body.append("PEOPLE: " + people_of(who, look))
    body.append(f"SHOT: {c['scene']}. Framed from the waist up so every face stays "
                f"clear, static camera. The movement is already under way in the very "
                f"first frame.")
    body.append(FRAMING)
    body.append(f"ACTION: {c['scene']}. {EN.get(speaker, speaker)}'s lips move in exact "
                f"sync with the Korean line below; nobody else speaks or moves their "
                f"lips.")
    body.append("DIALOGUE: [LANGUAGE: KOREAN] one voice only")
    body.append(f'  {EN.get(speaker, speaker)} (in Korean): "{c["text"]}"')
    v = VOICE_KO.get(speaker)
    if v:
        body.append(f"VOICE: {EN.get(speaker, speaker)} — {v}.")
    body.append("AUDIO: the person in the shot says the line themselves with their lips "
                "moving in sync, spoken in natural, fluent and highly authentic everyday "
                "Korean by a native speaker with standard Seoul intonation, real "
                "spontaneous speech with uneven rhythm and short breaths between "
                "phrases, with only the quiet room tone of the location underneath. "
                "They speak only the exact line written above and not a single word "
                "more; after it they stay completely silent and hold the look until "
                "the clip ends.")
    body += ["CAMERA: " + BLUR, COLOR, S.STYLE_FIX, NO_TEXT]
    return "\n".join(body)


def main():
    story = load_story()
    base = json.loads(BASE.read_text(encoding="utf-8"))
    look = {c.get("name"): person_line(c.get("flow_sheet"))
            for c in (base.get("characters") or [])}
    missing = [k for k in set(CARD.values()) if not look.get(k)]
    if missing:
        print(f"❌ 인물 카드 글이 없다: {', '.join(missing)}")
        return 1

    cuts = []
    for c in story.CUTS:
        cuts.append({
            "n": c["n"], "kind": c["kind"], "sec": c["sec"],
            "who": c.get("who") or [], "text": c["text"], "scene": c["scene"],
            "still": still_prompt(c, look),
            "veo": veo_prompt(c, look) if c["kind"] != "나레이션" else "",
        })
    doc = {"sid": "S90", "title": story.TITLE, "hook": story.HOOK,
           "yt_title": story.YT_TITLE, "cuts": cuts,
           "characters": base.get("characters") or []}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")

    narr = sum(1 for c in cuts if c["kind"] == "나레이션")
    print(f"■ {OUT.relative_to(ROOT)} — {len(cuts)}컷 "
          f"(나레이션 {narr} · 대사 {len(cuts) - narr}) · 최소 "
          f"{sum(c['sec'] for c in cuts):.0f}초")
    for c in cuts:
        who = "·".join(c["who"]) or "—"
        print(f"  {c['n']:>2} [{c['kind']:<4}] {c['sec']:>4.1f}초 {who:<14} "
              f"{c['text'][:34]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
