#!/usr/bin/env python3
"""⭐ 쇼츠 한 사건 대본을 짓는다 — data/series/<SID>.json (0원 · 인터넷 0회)

    python3 tools/build_short90.py          (S90)
    python3 tools/build_short90.py S91      (다른 사건)

⭐⭐ 2026-09-01 손님: "앞으로 영상을 계속 만들어나가고 계속 올려야 되는데
   이런 식으로 관리자 페이지를 구성하면 지속 가능하지 않거든."
   맞다. 예전엔 대본이 **손으로 쓴 파이썬 파일**(S90_story.py)이라 사건이
   늘 때마다 사람이 파이썬을 써야 했다 — 손님은 파이썬을 못 쓰신다.
   → 대본을 **데이터 파일**(data/series/<SID>.story.json)로 옮겼다.
     기계가 지을 수 있고(src/story90.py), 사건이 늘어도 이 도구는 그대로다.

무엇을 짓나
    data/series/<SID>.story.json 의 컷들에 **컷마다 완결된 프롬프트 두 벌**을 붙인다.
      still — 그림 한 장 (세로 9:16). 우리 시스템이 이걸로 만든다
      veo   — 영상 한 컷 (세로 9:16). 손님이 제미나이에서 손으로 만들 때 쓴다.
              **스물세 컷 전부** 만들어 둔다 — 어느 컷을 영상으로 할지는 손님이
              고르고, 안 고른 컷만 그림으로 간다 (그림과 영상이 섞인다)

⚠️ 사람 생김새·옷은 **여기서 안 적는다.** data/series/S001.json 의 인물 카드
   글(charsheet 가 지은 것)에서 뽑아 쓴다. 두 곳에 적으면 한쪽만 고쳐서
   사람이 컷마다 달라진다 — 실제로 화풍이 그렇게 갈렸다.
⚠️ 화풍 문구도 글자로 안 베낀다. src/series.py 의 고정 줄을 가져다 쓴다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import series as S                                           # noqa: E402

SERIES = ROOT / "data" / "series"
BASE = SERIES / "S001.json"          # 인물 카드 글은 여기 한 곳뿐이다


def paths(sid):
    """사건 하나가 쓰는 파일 세 벌."""
    return (SERIES / f"{sid}.story.json",     # 손으로/기계가 쓴 대본
            SERIES / f"{sid}.json",           # 프롬프트까지 붙인 것
            SERIES / f"{sid}.meta.json")      # 유튜브에 올릴 글 (편마다)

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

# ⚠️⚠️⚠️ 2026-08-28 손님: "위아래 이미지는 왜 나중에 네가 크롭을 하고 검정색으로
#    가리면 되지, 왜 프롬프트부터 위아래 그림에 생성이 안 되도록 작업을 해."
#    맞다. 예전엔 "아래 5분의 1은 비워 둬라(자막이 앉는다)" 고 시켰는데, 그러면
#    **화면의 20%를 버리고 그리는 것**이다. 자막은 우리가 다 만든 뒤에 어두운 띠를
#    덮어 얹는다(src/short90.py 의 scrim). 그림은 **화면을 꽉 채워** 받는다.
FRAMING = ("FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
           "the person kept in the middle with a little room above the head.")
BLUR = ("The background is strongly out of focus and softly blurred, heavy bokeh, "
        "only the people are sharp and in focus.")
COLOR = ("COLOR: warm neutral base, low overall contrast, slightly lifted blacks, "
         "soft amber light from the practical lamps, muted greens and cyans, "
         "natural unsaturated skin tones, the exact same colour grade in every shot "
         "of this story.")
NO_TEXT = ("ON SCREEN: no text, no letters, no subtitles, no captions, no watermark, "
           "no logo, no speech bubbles, no typography anywhere on screen.")


def load_story(path):
    if not path.exists():
        raise SystemExit(f"❌ 대본이 없습니다: {path.relative_to(ROOT)}\n"
                         f"   관리자 페이지에서 [이 사건으로 쇼츠 만들기] 를 "
                         f"먼저 누르십시오.")
    return json.loads(path.read_text(encoding="utf-8"))


def people_of(names, still=False):
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
    # 그림 한 장에는 "첫 프레임부터 끝 프레임까지" 라는 영상 말이 뜻이 없다.
    # 대신 **이야기 내내 같은 사람** 이라고 못을 박는다 (컷마다 얼굴이 달라지면 끝이다)
    tail = ("the same person in every shot of this story" if still
            else "unchanged from the first frame to the last")
    return (f"PEOPLE: the reference images show, in order, {lst}. Keep each person "
            f"exactly as they appear in their own reference image, {tail}.")


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


def check_say(story):
    """연기 지시(say)가 **한 줄도 안 빠졌는지**.

    ⚠️ 빠뜨리면 그 줄만 밋밋하게 읽힌다 — 그런데 화면으로는 안 보인다.
       그래서 한 줄이라도 비면 아예 못 만들게 막는다.
    """
    bad = []
    for c in story["cuts"]:
        say = c.get("say") or []
        if len(say) != len(c["turns"]) or any(not str(x).strip() for x in say):
            bad.append(c["n"])
    if bad:
        raise SystemExit(f"❌ 연기 지시(say)가 대사 줄 수와 안 맞습니다: 컷 {bad}")


def check_scrub(story):
    """가릴 자리가 성한지 — 네 값이 0~1 사이여야 하고 거꾸로면 안 된다."""
    for c in story["cuts"]:
        b = (c.get("scrub") or {}).get("box")
        if b is None:
            continue
        if len(b) != 4 or not all(0.0 <= float(x) <= 1.0 for x in b):
            raise SystemExit(f"❌ 컷{c['n']} 가릴 자리가 0~1 밖입니다: {b}")
        if not (b[0] < b[2] and b[1] < b[3]):
            raise SystemExit(f"❌ 컷{c['n']} 가릴 자리가 거꾸로입니다: {b}")


def check_parts(story):
    """편 나누기가 성한지 — 컷을 빠뜨리거나 겹치면 여기서 막는다.

    ⚠️ 이걸 안 보면 '2편에 컷이 하나 빠진 영상' 이 조용히 나온다.
       영상은 멀쩡해 보이고 이야기만 끊긴다 — 눈으로는 못 잡는다.
    """
    parts = story.get("parts") or []
    if not parts:
        raise SystemExit("❌ 편 나누기(parts)가 없습니다")
    ns = [c["n"] for c in story["cuts"]]
    seen, out = [], []
    for p in parts:
        a, b = p["cuts"]
        if a > b:
            raise SystemExit(f"❌ {p['no']}편 컷 범위가 거꾸로입니다: {a}~{b}")
        got = [n for n in ns if a <= n <= b]
        if not got:
            raise SystemExit(f"❌ {p['no']}편에 컷이 하나도 없습니다: {a}~{b}")
        seen += got
        for k in ("yt_title", "card"):
            if not p.get(k):
                raise SystemExit(f"❌ {p['no']}편에 {k} 가 없습니다")
        if len(p["card"]) != 2:
            raise SystemExit(f"❌ {p['no']}편 화면 제목(card)은 두 줄이어야 합니다")
    if sorted(seen) != sorted(ns):
        miss = sorted(set(ns) - set(seen))
        dup = sorted(n for n in set(seen) if seen.count(n) > 1)
        raise SystemExit(f"❌ 편 나누기가 컷을 놓쳤습니다 — 빠진 컷 {miss} · "
                         f"겹친 컷 {dup}")


def still_prompt(c):
    who = c.get("who") or []
    body = [S.HEAD_FIX.rstrip(".") + ". A single still frame, vertical 9:16 portrait."]
    if who:
        body.append(people_of(who, still=True))
        body.append(f"SHOT: {c['scene']}. Framed from the waist up so every face "
                    f"stays clear, mouths closed, holding the moment.")
    else:
        # ⚠️ 2026-08-31 — 이 줄은 "Nobody's face in frame" 이라는 **부정문**이다.
        #    우리 규칙에 이미 적혀 있듯(series.RISKY 주석) 그림 모델은 "하지 마"
        #    를 잘 못 읽고 오히려 그 낱말을 그려 넣는다. 18컷에 낯선 남녀가
        #    들어간 원인 중 하나로 의심된다.
        #    ⚠️ 다만 지금 고치지 않는다 — 이 줄을 바꾸면 멀쩡한 16컷까지 지문이
        #       달라져 다시 그려지고 132원이 더 나간다. 손님 확인 뒤에 함께 고친다.
        body.append(f"SHOT: {c['scene']}. Nobody's face in frame.")
    body += [FRAMING, "CAMERA: " + BLUR, COLOR, S.STYLE_STILL, NO_TEXT]
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
                + (" Framed from the waist up so everyone stays clear, static"
                   if who else " Static") + " camera. The movement is already "
                "under way in the very first frame.")
    body.append("FRAMING: vertical 9:16 portrait, filling the whole frame edge to "
                "edge, " + ("the people" if who else "the subject")
                + " kept in the middle of the frame.")
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


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sid = (argv[0] if argv else "S90").strip().upper()
    # ⚠️ 모양을 좁게 본다. 엉뚱한 글자가 사건 이름으로 들어오면 저장소의
    #    엉뚱한 자리를 읽거나 알 수 없는 오류로 죽는다.
    if not re.fullmatch(r"S\d{1,4}", sid):
        raise SystemExit(f"❌ 사건 번호가 이상합니다: {sid!r} (S90 처럼 적습니다)")
    story_p, out_p, meta_p = paths(sid)
    story = load_story(story_p)

    base = json.loads(BASE.read_text(encoding="utf-8"))
    have = {c.get("name") for c in (base.get("characters") or [])}
    missing = [k for k in set(CARD.values()) if k not in have]
    if missing:
        print(f"❌ 인물 카드가 없다: {', '.join(missing)}")
        return 1

    check_say(story)
    check_parts(story)
    check_scrub(story)
    cuts = []
    for c in story["cuts"]:
        c = dict(c)
        c["turns"] = [tuple(t) for t in c["turns"]]
        cuts.append({
            "n": c["n"], "kind": kind_of(c), "sec": c["sec"],
            "narr": is_narr(c),
            "turns": [list(t) for t in c["turns"]],
            "who": c.get("who") or [], "text": text_of(c), "scene": c["scene"],
            # ⭐ 줄마다 **어떻게 읽을지** (2026-08-31). 목소리 만들 때 같이 보낸다
            "say": list(c.get("say") or []),
            # ⭐ 2026-09-01 — 앞머리 나레이션은 **다른 컷 그림을 그대로 쓴다**.
            #    화면 묘사(scene)와 나오는 사람(who)이 똑같으므로 지문도 똑같아지고,
            #    src/short90.py 의 salvage 가 그것을 알아보고 옮겨 쓴다 → 0원.
            "still_of": c.get("still_of"),
            # ⭐ 상표를 흐리게 가릴 자리 — **컷에 붙여 둔다**(2026-09-01).
            #    예전엔 따로 파일(S90.scrub.json)에 컷 번호로 적어 두었는데,
            #    편을 나누며 번호가 밀리자 엉뚱한 컷을 가리킬 뻔했다.
            "scrub": c.get("scrub"),
            "still": still_prompt(c),
            "veo": veo_prompt(c),
            "flow": flow_prompt(c),
        })
    doc = {"sid": sid, "case_id": story.get("case_id", ""),
           "title": story["title"], "hook": story.get("hook", ""),
           "series_label": story.get("series_label") or story["title"],
           "parts": [dict(x) for x in story["parts"]],
           # ⭐ 2026-09-04 — 사건마다 사람이 다르다. 이 사건이 더 세운 사람
           #    (장남·며느리 등)의 나이대·성별을 조립 쪽으로 넘긴다.
           #    안 넘기면 그 사람이 나레이션 목소리로 말한다.
           "people": dict(story.get("people") or {}),
           "cuts": cuts,
           "characters": base.get("characters") or []}
    out_p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")

    # ⭐⭐ 2026-08-31 손님: "유튜브 업로드 버튼이 아직도 없어."
    #    만들어 두긴 했는데 **릴리스에 있는 meta.json 이 있어야만** 칸이
    #    떴다. → 올릴 글을 **대본 옆에 같이 둔다.** 영상을 안 만들어도 늘 있다.
    #    ⚠️ 셈법은 여전히 src/ytmeta.py 한 곳뿐이다 (여기서 부르기만 한다).
    sys.path.insert(0, str(ROOT / "src"))
    import ytmeta                                            # noqa: E402
    meta_p.write_text(json.dumps(ytmeta.meta90(doc), ensure_ascii=False,
                                 indent=1) + "\n", encoding="utf-8")

    # ⭐ 사건·편 칸을 상태 파일에 만들어 둔다 — 관리자 페이지가 이것만 읽는다.
    #   (올린 기록은 건드리지 않는다. 지우면 같은 영상을 두 번 올리게 된다)
    import shortstate                                        # noqa: E402
    shortstate.from_doc(doc)

    narr = sum(1 for c in cuts if c["narr"])
    print(f"■ {out_p.relative_to(ROOT)} — {len(cuts)}컷 "
          f"(나레이션 {narr} · 대사 {len(cuts) - narr}) · {len(doc['parts'])}편")
    for p in doc["parts"]:
        a, b = p["cuts"]
        mine = [c for c in cuts if a <= c["n"] <= b]
        print(f"\n  ── {p['no']}편 · 컷{a}~{b} ({len(mine)}컷) "
              f"— {p['card'][0]} / {p['card'][1]}")
        print(f"     제목: {p['yt_title']}")
        for c in mine:
            who = "·".join(c["who"]) or "—"
            tag = " (그림 재사용)" if c.get("still_of") else ""
            print(f"     {c['n']:>2} [{c['kind']:<4}] {who:<12} "
                  f"{c['text'][:30]}{tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
