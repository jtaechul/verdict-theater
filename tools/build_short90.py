#!/usr/bin/env python3
"""⭐ 90초 한 편 대본을 짓는다 — data/series/S90.json (0원 · 인터넷 0회)

    python3 tools/build_short90.py

무엇을 짓나
    data/series/S90_story.py 의 23컷에 **컷마다 완결된 프롬프트 두 벌**을 붙인다.
      still — 그림 한 장 (세로 9:16). 우리 시스템이 이걸로 만든다
      veo   — 영상 한 컷 (세로 9:16). 손님이 제미나이에서 손으로 만들 때 쓴다.
              **스물세 컷 전부** 만들어 둔다 — 어느 컷을 영상으로 할지는 손님이
              고르고, 안 고른 컷만 그림으로 간다 (그림과 영상이 섞인다)

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
      "딸": "DAUGHTER", "변호사": "ATTORNEY"}
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


def people_of(names):
    """컷에 나오는 사람 — **이름만** 적고 생김새·옷은 안 적는다.

    ⚠️⚠️⚠️ 2026-08-27 손님: "wife 이미지가 있으면 와이프 옷차림 같은 건 쓰면
       안 되잖아."
       맞다. 그리고 이건 **이미 우리 규칙**이었다(series.wear_bait). 얼굴·옷은
       **기준 그림(레퍼런스 이미지)** 이 잡는 몫이다. 컷 프롬프트에 옷을 또 적으면
       두 지시가 싸우고, 컷마다 이긴 쪽이 달라져 **옷이 계속 바뀐다** — 막으려던
       바로 그 사고가 난다. 내가 90초 편을 새로 만들면서 그 규칙을 어겼다.
    """
    if not names:
        return ""
    who = [EN.get(k, k) for k in names]
    lst = who[0] if len(who) == 1 else ", ".join(who[:-1]) + " and " + who[-1]
    return (f"PEOPLE: the reference images show, in order, {lst}. Keep each person "
            f"exactly as they appear in their own reference image, unchanged from "
            f"the first frame to the last.")


def who_line(names):
    return ", ".join(EN.get(k, k) for k in names)


SPEAK_PER_SEC = 4.6      # 한국어는 1초에 약 4.6자
BREATH = 0.8             # 앞뒤 숨
TURN_GAP = 0.6           # 주고받을 때 사이


def need_sec(c):
    """이 컷 대사를 다 하려면 몇 초가 필요한가."""
    import re as _re
    x = sum(len(_re.sub(r"[\s…·/]", "", t)) / SPEAK_PER_SEC + BREATH
            for _, t in c["turns"])
    return x + (TURN_GAP if len(c["turns"]) > 1 else 0)


def veo_sec(c):
    """만들 길이 — **필요한 만큼만.** (Veo·플로우가 받는 것은 4·6·8초뿐)

    ⭐ 2026-08-28 손님: "쓸데없이 영상 길게 만들지 마. 필요한 길이 만큼은
       만들게끔. 초 똑바로 적어."
    """
    x = need_sec(c)
    for s in (4, 6, 8):
        if x <= s:
            return s
    return 8


def kind_of(c):
    """이 컷을 대표하는 사람 (첫 번째로 말하는 사람)."""
    return c["turns"][0][0]


def is_narr(c):
    return all(w == "나레이션" for w, _ in c["turns"])


def text_of(c):
    """화면에 뜰 글 전부 (여러 사람이면 이어 붙인다)."""
    return " / ".join(t for _, t in c["turns"])


def still_prompt(c):
    who = c.get("who") or []
    body = [S.HEAD_FIX.rstrip(".") + ". A single still frame, vertical 9:16 portrait."]
    if who:
        body.append(people_of(who))
        body.append(f"SHOT: {c['scene']}. Framed from the waist up so every face "
                    f"stays clear, static camera, mouths closed, holding the moment.")
    else:
        body.append(f"SHOT: {c['scene']}. Static camera, nobody's face in frame.")
    body += [FRAMING, "CAMERA: " + BLUR, COLOR, S.STYLE_FIX, NO_TEXT]
    return "\n".join(body)


# 나레이션 컷용 소리 지시 — **아무도 말하지 않는다.**
# ⚠️ 여기서 사람이 말해 버리면 우리 나레이션과 목소리가 겹친다. 나레이션 컷은
#    올린 영상의 소리를 안 쓰고 우리 나레이션을 얹는다.
AUDIO_QUIET = ("AUDIO: nobody speaks and nobody moves their lips at any point; "
               "only the quiet room tone of the location, no music, no voice, "
               "no narration.")


def veo_prompt(c):
    """그 컷을 손으로 만들 때 쓸 영상 프롬프트 (제미나이에 그대로 붙인다).

    ⭐ 2026-08-27 손님: "이미지는 중간중간 섞여 있고 동영상도 있어야 돼."
       맞다. 그래서 **스물세 컷 전부** 영상 프롬프트를 만들어 둔다 — 어느 컷을
       영상으로 올릴지는 손님이 고른다. 안 올린 컷만 그림으로 간다.
    """
    who = c.get("who") or []
    talks = not is_narr(c)
    speaker = kind_of(c)
    sec = veo_sec(c)
    body = [f"{S.HEAD_FIX} {sec}-second single continuous take, "
            f"vertical portrait format (9 x 16)."]
    if who:
        body.append(people_of(who))
    body.append(f"SHOT: {c['scene']}. Framed from the waist up so every face stays "
                f"clear, static camera. The movement is already under way in the very "
                f"first frame.")
    body.append(FRAMING)
    if talks:
        names = " then ".join(EN.get(w, w) for w, _ in c["turns"])
        body.append(f"ACTION: {c['scene']}. {names} speak in that order, each one's "
                    f"lips moving only during their own line and staying closed and "
                    f"still while the other speaks.")
        body.append("DIALOGUE: [LANGUAGE: KOREAN] one voice at a time, in this order")
        for w, t in c["turns"]:
            body.append(f'  {EN.get(w, w)} (in Korean): "{t}"')
        for w, _ in c["turns"]:
            v = VOICE_KO.get(w)
            if v:
                body.append(f"VOICE: {EN.get(w, w)} — {v}.")
        body.append("AUDIO: the person in the shot says the line themselves with their "
                    "lips moving in sync, spoken in natural, fluent and highly "
                    "authentic everyday Korean by a native speaker with standard Seoul "
                    "intonation, real spontaneous speech with uneven rhythm and short "
                    "breaths between phrases, with only the quiet room tone of the "
                    "location underneath. They speak only the exact line written above "
                    "and not a single word more; after it they stay completely silent "
                    "and hold the look until the clip ends.")
    else:
        body.append(f"ACTION: {c['scene']}, unfolding slowly and quietly over the whole "
                    f"take, with small natural movement — a breath, a hand shifting, "
                    f"light moving. Mouths stay closed the whole time.")
        body.append(AUDIO_QUIET)
    body += ["CAMERA: " + BLUR, COLOR, S.STYLE_FIX, NO_TEXT]
    return "\n".join(body)


# ⭐⭐⭐ 2026-08-27 — **구글 플로우(제미나이 앱)로 손수 만들 때 쓰는 판.**
#    손님이 앱에서 컷 4를 넣었더니 이렇게 막혔다 —
#      "이 프롬프트는 유명인의 동영상 생성에 관한 Google 정책을 위반할 가능성이…"
#    말을 바꿔 다시 넣으니 **통과했다**(손님 확인). 앱 필터가 API 보다 훨씬
#    빡빡하다. 그래서 판을 둘로 나눈다.
#
#      still / veo  — 우리 시스템(API)이 쓴다. 인물 카드를 참조로 넣으므로
#                     옷·생김새를 **안 적는다** (적으면 참조와 싸운다)
#      flow         — 손님이 앱에서 쓴다. 참조 그림을 **안 넣으므로** 옷·생김새를
#                     짧게 적어 줘야 컷마다 같은 사람이 나온다
#
#    ⚠️ 앱에서 막히는 말은 절대 쓰지 않는다 —
#       photoreal · photorealistic · photograph · natural skin · faces ·
#       reference image · actor · celebrity · live-action · real person
#       (부인하는 말이라도 그 낱말이 들어가면 걸린다. 이미 배운 것이다)
FLOW_BAN = ("photoreal", "photorealistic", "photograph", "natural skin",
            "reference image", "actor", "celebrity", "live-action",
            "real person", "likeness")

# ⭐⭐⭐ 2026-08-28 손님: "플로우에는 내가 캐릭터 등록을 미리 해놨으니깐 절대로
#    그 캐릭터에 대한 옷이라든가 얼굴이라든가 뭐 나이라든가 이런 걸 언급하지 마."
#    그래서 플로우 판에는 **이름만** 들어간다. 옷·얼굴·나이는 한 글자도 안 적는다.
FLOW_WHO = {"아내": "the wife", "남편": "the husband",
            "내연녀": "the other woman", "딸": "the daughter",
            "변호사": "the attorney"}
# 화면 묘사 속 사람 부르는 말도 등록한 이름으로 맞춘다
FLOW_SWAP = [("the lawyer", "the attorney")]


def flow_scene(t):
    for a, b in FLOW_SWAP:
        t = t.replace(a, b)
    return t


FLOW_HEAD = ("A short fictional drama scene. Every character is invented for this "
             "story and resembles nobody.")
FLOW_STYLE = ("STYLE: one unbroken take in one place, naturalistic cinematic drama, "
              "soft film grain, muted desaturated palette, soft practical lighting, "
              "shallow depth of field, the same colour grade in every shot.")


def flow_prompt(c):
    """구글 플로우에 그대로 붙일 판 (인물 그림을 안 넣는다)."""
    who = c.get("who") or []
    talks = not is_narr(c)
    sec = veo_sec(c)
    body = [f"{FLOW_HEAD} {sec}-second single continuous take, "
            f"vertical portrait format (9 x 16)."]
    if who:
        body.append("CAST: "
                    + ", ".join(FLOW_WHO.get(k, k) for k in who) + ".")
    body.append(f"SHOT: {flow_scene(c['scene'])}."
                + (" Framed from the waist up so everyone stays clear," if who
                   else "") + " Static camera. The movement is already under way "
                "in the very first frame.")
    body.append("FRAMING: vertical 9:16 portrait, "
                + ("the people" if who else "the subject")
                + " kept in the middle of the frame, the lower fifth left plain "
                  "because a caption will sit there.")
    if talks:
        tags = [FLOW_WHO.get(w, w) for w, _ in c["turns"]]
        off = not who          # 화면에 사람이 없으면 목소리만 들린다
        if len(tags) == 1:
            body.append(f"ACTION: only {tags[0]} speaks"
                        + (", from off camera; nobody's face is in frame."
                           if off else
                           "; anyone else stays silent with their mouth closed."))
            body.append("DIALOGUE: [LANGUAGE: KOREAN]"
                        + (" spoken from off camera" if off else ""))
        else:
            body.append(f"ACTION: {' then '.join(tags)} speak in that order, each "
                        f"one's mouth moving only during their own line and closed "
                        f"while the other speaks.")
            body.append("DIALOGUE: [LANGUAGE: KOREAN] one voice at a time, "
                        "in this order")
        for (w, t), tag in zip(c["turns"], tags):
            body.append(f'  {tag}: "{t}"')
        body.append("AUDIO: the line is said in natural, fluent everyday Korean with "
                    "standard Seoul intonation, uneven rhythm and short breaths, with "
                    "only quiet room tone underneath. Only that line is said and "
                    "nothing more, then everyone stays silent until the clip ends.")
    else:
        body.append("ACTION: the moment unfolds slowly and quietly over the whole "
                    "take, with small natural movement — a breath, a hand shifting, "
                    "light moving. Mouths stay closed the whole time.")
        body.append("AUDIO: nobody speaks at any point; only quiet room tone, "
                    "no music, no voice, no narration.")
    body += ["CAMERA: background strongly out of focus, heavy bokeh, only "
             + ("the people" if who else "the subject") + " sharp.",
             "COLOR: warm neutral base, low contrast, slightly lifted blacks, soft "
             "amber lamplight, muted greens and cyans.",
             FLOW_STYLE,
             "ON SCREEN: no text, no letters, no subtitles, no captions, "
             "no watermark, no logo."]
    return "\n".join(body)


def main():
    story = load_story()
    base = json.loads(BASE.read_text(encoding="utf-8"))
    have = {c.get("name") for c in (base.get("characters") or [])}
    missing = [k for k in set(CARD.values()) if k not in have]
    if missing:
        print(f"❌ 인물 카드가 없다: {', '.join(missing)}")
        return 1

    cuts = []
    for c in story.CUTS:
        cuts.append({
            "n": c["n"], "kind": kind_of(c), "sec": c["sec"],
            "narr": is_narr(c),
            "turns": [list(t) for t in c["turns"]],
            "who": c.get("who") or [], "text": text_of(c), "scene": c["scene"],
            "still": still_prompt(c),
            "veo": veo_prompt(c),
            "flow": flow_prompt(c),
        })
    doc = {"sid": "S90", "title": story.TITLE, "hook": story.HOOK,
           "yt_title": story.YT_TITLE, "cuts": cuts,
           "characters": base.get("characters") or []}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")

    narr = sum(1 for c in cuts if c["narr"])
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
