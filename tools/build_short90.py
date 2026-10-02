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
import story90 as ST90                                       # noqa: E402
import talkplan                                              # noqa: E402

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
# ⭐⭐⭐ 2026-09-05 손님(화면 캡처): "1화에 관련 없는 등장인물의 이미지가
#    들어가 있어." 컷6 은 who 가 비어 있고 장면이 "a car is parked on a dark
#    street at night" 인데, 낯선 남녀 두 사람이 그려져 나왔다.
#    까닭은 **프롬프트가 세 줄에 걸쳐 사람을 그리라고 시키고** 있었기 때문이다 —
#      SHOT:    …. Nobody's face in frame.        ← 금지형. 모델은 흘려듣는다
#      FRAMING: … the person kept in the middle…  ← 사람을 가운데 두라고 시킴
#      CAMERA:  … only the people are sharp…      ← 또 사람을 요구
#    → 사람이 없는 컷에는 **사람이라는 낱말이 한 번도 안 나오는** 판을 쓴다.
FRAMING_NOBODY = ("FRAMING: vertical 9:16 portrait, filling the whole frame edge "
                  "to edge, the subject kept in the middle with a little room "
                  "above it.")
BLUR_NOBODY = ("The background is strongly out of focus and softly blurred, heavy "
               "bokeh, only the subject is sharp and in focus.")
COLOR = ("COLOR: warm neutral base, low overall contrast, slightly lifted blacks, "
         "soft amber light from the practical lamps, muted greens and cyans, "
         "natural unsaturated skin tones, the exact same colour grade in every shot "
         "of this story.")
# ⭐⭐⭐ 2026-09-05 (두 번째) — 사람 없는 컷에 **또** 낯선 남녀가 들어갔다.
#    앞서 SHOT·FRAMING·CAMERA 세 줄만 고쳤는데, 지문에는 사람을 부르는 말이
#    **네 군데 더** 있었다. 손님이 보내 주신 화면(컷6 "a car is parked on a
#    dark street at night")에 젊은 남녀 한 쌍이 그대로 서 있었다.
#      ① 머리줄  "invented **characters**"
#      ② COLOR   "natural unsaturated **skin tones**"
#      ③ STYLE   "natural **skin texture** · true-to-life **body** proportions"
#      ④ STYLE   "ordinary everyday Korean **faces** with unexaggerated features"
#    ⚠️ 내가 만든 검사(still_check)는 COLOR 앞까지만 보고 있었다 —
#       "색·화풍 줄은 사람 얘기가 아니다" 라고 적어 두고 넘겼는데, 바로 그 줄들이
#       사람을 부르고 있었다. 검사가 **지문 전체**를 보게 고쳤다.
HEAD_NOBODY = "Fictional scene, photoreal grounded drama."
COLOR_NOBODY = ("COLOR: warm neutral base, low overall contrast, slightly lifted "
                "blacks, soft amber light from the practical lamps, muted greens "
                "and cyans, the exact same colour grade in every shot of this story.")
STYLE_NOBODY = ("STYLE: a single photograph of one moment, photoreal look with "
                "natural surface texture and true-to-life proportions of the "
                "objects, muted desaturated palette, soft practical lighting, "
                "shallow depth of field, the same colour grade in every shot.")

NO_TEXT = ("ON SCREEN: no text, no letters, no subtitles, no captions, no watermark, "
           "no logo, no speech bubbles, no typography anywhere on screen.")


def load_story(path):
    if not path.exists():
        raise SystemExit(f"❌ 대본이 없습니다: {path.relative_to(ROOT)}\n"
                         f"   관리자 페이지에서 [이 사건으로 쇼츠 만들기] 를 "
                         f"먼저 누르십시오.")
    return json.loads(path.read_text(encoding="utf-8"))


# ⭐⭐⭐ 2026-09-30 — **2분 드라마** (story90 format="drama")
#    인물 참조가 **인물 시트에서 자른 칸**이다 — 한 칸에 한 사람이 가까이·전신
#    두 번 나온다. 지문에 그렇다고 적지 않으면 모델이 두 사람을 그린다
#    (tools/omni_test.py 에서 먼저 배웠다). main() 이 대본마다 켜고 끈다.
SHEET_REFS = False
TWICE = (" Each reference picture shows that person twice — a close view and a "
         "full-length view — and each is one single person.")


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
            f"exactly as they appear in their own reference image, {tail}."
            + (TWICE if SHEET_REFS else ""))


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


def still_prompt(c, prev=None, ctx=None):
    # ⭐⭐⭐ 2026-09-10 — 갈림길을 **who 가 아니라 '나레이션인가'** 로 바꾼다.
    #    손님: "나레이션 배경 이미지에 사람이 자꾸 들어가."
    #    나레이션 컷에 who 가 남아 있으면 사람 갈래로 가서 사람이 그려졌다.
    #    나레이션은 **장소·사물·빛**, 대사는 **사람** — 이 둘을 섞지 않는다.
    #    (원래 설계도 그랬다: 나레이션은 그림, 대사는 영상)
    # ⭐⭐⭐ 2026-10-01 손님: "나레이션컷에서도 등장인물 얼굴 나오는거로 반영해."
    #    → **2분 드라마만** 나레이션 컷에도 그 순간의 등장인물을 그린다(입은
    #      다문다). 옛 여러 편은 위 규칙 그대로다. 가르는 자리는 하나뿐이다
    #      (story90.still_who — 얼굴 참조·카메라 무빙도 같은 함수를 쓴다).
    drama = bool((ctx or {}).get("drama"))
    who = ST90.still_who(c, drama)
    if who and is_narr(c):
        # ⚠️ 등장인물 **외의** 사람이 묘사에 섞이면 그대로 막는다 (핵심 규칙)
        w = ST90.narr_people(c.get("scene"), {"format": ST90.DRAMA,
                                              "people": {x: {} for x in who}})
        if w:
            raise SystemExit(
                f"❌ 컷{c.get('n')}: 나레이션 화면 묘사에 등장인물이 아닌 사람이 "
                f"있습니다 — '{w[0]}'\n   {c.get('scene')}\n"
                f"   등장인물({', '.join(who)}) 이름으로만 적습니다 (값 0원).")
    if not who:
        # ⚠️⚠️ 마지막 관문. 나레이션 컷 화면 묘사가 사람을 부르고 있으면
        #    **조용히 그리지 않는다.** 얼굴 참조가 없어서 낯선 외국인이
        #    그려지고, 그 값(장당 132원)이 그대로 날아간다.
        #    규격 검사(story90.check)가 먼저 잡지만, 옛 대본이 이 길로
        #    들어올 수 있어 여기서 한 번 더 막는다.
        w = ST90.narr_people(c.get("scene"))
        if w:
            raise SystemExit(
                f"❌ 컷{c.get('n')}: 나레이션 컷 화면 묘사에 사람이 있습니다 "
                f"— '{w[0]}'\n   {c.get('scene')}\n"
                f"   나레이션 배경은 **장소·사물·빛**만 적습니다 "
                f"(얼굴 참조가 없어 낯선 외국인이 그려집니다).\n"
                f"   고치기: python3 tools/edit_line.py --sid <사건> "
                f"--cut {c.get('n')} --scene \"...\"   (값 0원)")
    elif not is_narr(c):
        # ⭐⭐⭐ 2026-09-12 손님: "장남이라고 해놓고선 등장인물이 아닌 사람이
        #    자꾸 나타나." 대사 컷 화면에 who 보다 사람이 많으면, 남는 사람은
        #    얼굴 참조가 없어 그림 모델이 지어낸다. 나레이션 쪽만 막아 두면
        #    **대사 쪽으로 샌다** — 실제로 샜다(S92 컷2·5·15·34).
        extra, heads = ST90.scene_extra(c)
        if extra:
            raise SystemExit(
                f"❌ 컷{c.get('n')}: 화면에 사람이 {len(heads)}명인데 등장인물"
                f"(who)은 {len(who)}명입니다 — {', '.join(who) or '없음'}\n"
                f"   {c.get('scene')}\n"
                f"   남는 사람은 얼굴 그림이 없어 **생판 남**이 그려집니다.\n"
                f"   ① 그 사람을 who 에 넣거나  ② 화면 묘사에서 빼 주십시오 "
                f"(둘 다 값 0원).")
    head = (S.HEAD_FIX if who else HEAD_NOBODY).rstrip(".")
    body = [head + ". A single still frame, vertical 9:16 portrait."]
    if who:
        body.append(people_of(who, still=True))
        # ⭐⭐⭐ 2026-09-20 — 여기가 **연출이 안 닿던 자리**다. 예전에는 컷이
        #    무엇이든 늘 같은 한 문장("허리 위로 잡아 모든 얼굴이 또렷하게")
        #    이었다. 36컷 구도가 전부 같으니 단조로울 수밖에 없었다.
        #    이제 영상과 **같은 구도표**(compose_of)를 읽는다. 움직임만 빠진다.
        shot, framing, cam = compose_of(c, prev, ctx, who)
        if drama:
            # ⭐ PEOPLE 줄과 **같은 이름**으로 부른다 (2분 드라마 · 2026-10-01).
            #    PEOPLE 은 WIFE 인데 SHOT 은 '아내' 면 모델이 두 사람으로 읽을 수 있다.
            for nm in sorted(who, key=len, reverse=True):
                shot = shot.replace(nm, EN.get(nm, nm))
        body += [shot + " Mouths closed, holding the moment.", framing, cam]
    else:
        # ⚠️ 2026-08-31 에 "이 줄이 낯선 남녀를 부르는 것 같다" 고 적어 두고
        #    **미뤘다.** 2026-09-05 에 손님이 실제로 그 화면을 보내 주셨다.
        #    이제 사람이라는 낱말이 한 번도 안 나오는 판으로 바꾼다 —
        #    "그리지 마" 가 아니라 **무엇을 그릴지만** 적는다.
        shot, framing, cam = compose_of(c, prev, ctx, who)
        body += [f"{shot} The place itself is the subject: the objects and the "
                 f"light fill the frame, quiet and empty.", framing, cam]
    body += ([COLOR, S.STYLE_STILL] if who else [COLOR_NOBODY, STYLE_NOBODY])
    body.append(NO_TEXT)
    return "\n".join(body)


# ⭐⭐⭐ 2026-10-01 — **증거 확대 화면** (해양생물 쇼츠의 '특징 줌인' · 손님 승인)
#    나레이션이 그 물건을 말하는 순간 이 그림으로 넘어갔다가 인물 얼굴로 돌아온다.
#    ⚠️ 물건만 그린다 — 사람이라는 낱말이 한 번도 안 나오는 판(HEAD/COLOR/STYLE
#       _NOBODY)을 쓴다. 2026-09-05 에 사람 판 한 줄 때문에 낯선 남녀가 그려졌다.
#    ⚠️ 글자가 그려지면 안 된다 — 서류·휴대폰도 글씨는 흐리게만.
def insert_prompt(thing):
    return "\n".join([
        HEAD_NOBODY.rstrip(".") + ". A single still frame, vertical 9:16 portrait.",
        f"SHOT: An extreme close-up insert of {thing}, filling the frame, the single "
        "most telling detail sharp and everything around it melting into soft blur. "
        "Any writing on it stays soft and unreadable.",
        FRAMING_NOBODY, "CAMERA: " + BLUR_NOBODY, COLOR_NOBODY, STYLE_NOBODY, NO_TEXT])


# 나레이션 컷용 소리 지시 — **아무도 말하지 않는다.**
# ⚠️ 여기서 사람이 말해 버리면 우리 나레이션과 목소리가 겹친다. 나레이션 컷은
#    올린 영상의 소리를 안 쓰고 우리 나레이션을 얹는다.
AUDIO_QUIET = ("AUDIO: nobody speaks and nobody moves their lips at any point; "
               "only the quiet room tone of the location, no music, no voice, "
               "no narration.")


# ── ⭐⭐⭐ 컷 성격에 따른 구도·카메라 무빙 (2026-09-17 손님 지시) ──────
#    손님이 연출 규칙표를 주시며 "우리 영상 제작 프롬프트에 반영해 달라" 하셨다.
#
#    그때까지 영상 프롬프트는 **모든 컷이 똑같았다** —
#      "Framed from the waist up …, static camera"
#    37컷이 전부 같은 구도에 무빙은 아예 없었다. 우스운 것은, **정지 그림에는**
#    컷마다 다른 켄번즈 무빙이 이미 들어가고 있었다는 점이다(short90.move_of).
#    그림이 영상보다 더 움직이고 있었다.
#
#    ⚠️ 받은 규칙표를 **그대로 쓰지 않았다.** 그 표는 사극(史劇)용이었다 —
#       횃불·짚가리·창살. 판결극장은 현대 법정극이라 횃불이 없다.
#       · 가져온 것 : 상황별 구도·무빙 3종, 눈선 상단 1/3, frame-in-frame
#       · 번역한 것 : 창살·기둥 → 블라인드·유리벽·문틀·서류더미
#       · 뺀 것     : `--ar 9:16`(미드저니 문법이다. Veo 는 ratio 파라미터로
#                     받고 우리는 이미 넘긴다. 프롬프트에 넣으면 글자로 읽혀
#                     화면에 뜰 수 있다 — NO_TEXT 로 막고 있는 바로 그것이다)
#                     `8k`(우리 금지어다. charsheet.PHOTO_WORDS 참고 —
#                     '사진 주문서' 로 읽혀 안전필터에 걸린 이력이 있다)
#                     Teal & Orange(손님이 '지금 색을 지킨다' 를 고르셨다.
#                     S90~S92 와 색이 튀면 한 채널로 안 보인다)
#
#    ⚠️ 나레이션 컷에는 **사람이라는 낱말이 한 번도 안 나와야** 한다.
#       그림 쪽은 2026-09-05 에 고쳤는데(FRAMING_NOBODY) 영상 쪽은 안 고쳐서,
#       빈 빈소 컷에 "the person kept in the middle" 이 들어가 있었다.
#       낯선 사람이 그려지던 바로 그 자리다 — 여기서 같이 고친다.
EYE_LINE = ("the eye line held about a third of the way down from the top of the "
            "vertical frame")
# 나레이션(장소) 컷은 같은 무빙만 이어지면 지루하다. 컷 번호로 **돌려 가며** 쓴다
# (무작위로 하면 다시 만들 때마다 화면이 달라져 0원 재사용이 깨진다).
NARR_MOVES = [
    "the camera pulling back in a very slow zoom out that opens up the space",
    "the camera pushing in almost imperceptibly slowly",
    "the camera drifting sideways in a slow steady lateral move",
]


def is_reply(c, prev):
    """앞 컷과 **주고받는 중**인가 — 사람이 바뀌고 같은 자리에 있는가.

    ⚠️ 대립 장면은 우리 대본에서 '두 사람이 한 컷에' 가 아니라 **컷을 나눠
       주고받는** 모양으로 나온다(컷3 딸 → 컷4 아내). 한 컷 안의 사람 수만
       보면 오버 더 숄더가 **한 번도 안 걸린다** — 실제로 S93 이 그랬다.
    """
    if prev is None:
        return False
    a, b = c.get("who") or [], prev.get("who") or []
    if not a or not b or a == b:
        return False
    # 같은 자리인가 — 화면 묘사 뒤쪽(장소)이 같으면 한 자리로 본다.
    # ⚠️ **맨 뒤** " in " 에서 자른다. 앞에서 자르면 "hands folded in her lap
    #    in an empty funeral hall" 같은 줄이 "her lap in an empty…" 로 잘려
    #    같은 자리인데 다르다고 나온다(실제로 그래서 한 번도 안 걸렸다).
    def place(x):
        return str(x.get("scene") or "").rsplit(" in ", 1)[-1].strip()

    return place(c) == place(prev)


# ⭐ 앵글로 **힘의 관계**를 보여 준다 (2026-09-17 손님 선택).
#    이야기가 글이 아니라 그림으로 읽힌다 — 가진 쪽은 올려다보고, 밀려난 쪽은
#    내려다본다. 그리고 판결이 난 뒤(마지막 편)에는 **뒤집는다.**
#    ⚠️ 살짝만 준다. 세게 주면 만화가 된다.
POWER = {"내연녀": "low", "혼외자": "low", "아내": "high", "딸": "high"}
ANGLE = {
    "low": "shot from slightly below eye level so they look composed and in control",
    "high": "shot from slightly above eye level so they look worn down and small",
    "eye": "shot at eye level, level and plain",
}


def angle_of(name, flip=False):
    """그 사람을 어느 높이에서 잡을까. flip 이면 뒤집는다(판결 뒤)."""
    a = POWER.get(name, "eye")
    if flip and a in ("low", "high"):
        a = "high" if a == "low" else "low"
    return ANGLE[a]


# ⭐⭐⭐ 2026-09-20 손님: "카메라 구도가 아직도 너무 단조로운데 … 이게 지금
#    이미지만 나와서 이렇게 된 거예요?"
#
#    **그렇다.** 뜯어보니 연출(아래 구도표)이 **영상 프롬프트에만** 이어져
#    있었다. 그림 프롬프트는 36컷에 문구가 **둘뿐**이었다 —
#      21컷 "허리 위로 잡아 모든 얼굴이 또렷하게"
#      15컷 "장소 자체가 주인공, 조용히 비어 있게"
#    게다가 마지막 실행은 영상을 한 편도 안 샀다. 화면의 100%가 그림이므로
#    연출은 **한 프레임도 안 닿았다.** 컷마다 구도가 똑같으니 켄번즈를 아무리
#    걸어도 단조로울 수밖에 없다.
#
#    → 구도(compose_of)와 움직임(move_line)을 **갈라 놓는다.**
#      · 구도는 그림도 영상도 **같은 표**를 읽는다 (두 벌로 두면 한쪽만 좋아진다)
#      · 움직임은 영상에만 붙인다 — 그림은 움직일 수 없다
#
#    ⭐ 손님이 고르신 수트(Suits) 구도 셋을 더한다:
#      ① 유리 너머 · 창에 비친 얼굴  ② 문틀 · 블라인드로 가두기
#      ③ 뒷모습 · 실루엣 · 사람을 작게
#      (물건 클로즈업은 안 고르셨다 — 장소 컷에 이미 있던 것만 남긴다)
#
#    ⚠️ 컷 번호로 **돌려 쓴다.** 무작위로 하면 다시 만들 때마다 화면이 달라져
#       0원 재사용이 깨진다(같은 컷은 늘 같은 구도).
#    ⚠️⚠️ 장소 컷 글에는 **사람을 부르는 낱말이 한 번도 나오면 안 된다.**
#       2026-09-05 에 "그리지 마" 라고 적었다가 낯선 남녀가 두 번 그려져 나왔다.
#       실루엣도 **사물의** 실루엣으로만 적는다.

# ── 장소 컷 구도 (who 없음) — 여섯 갈래 ───────────────────────────
PLACE_SHOTS = [
    ("A cinematic wide shot of the place itself, deep depth of field, the "
     "whole room laid out", None),
    ("A tight macro insert of the single most telling object in this place, "
     "filling the frame", None),
    ("A low-angle medium view from near floor level looking up past the "
     "objects in the foreground", None),
    # ⭐ 유리 너머 · 반사 (수트의 서명 같은 화면)
    ("Shot through a pane of glass — a rain-streaked window or a glass door — "
     "with the room behind mirrored faintly on the surface, two layers laid "
     "over each other in one frame",
     "FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
     "the glass surface covering the whole frame, the reflection and what lies "
     "beyond it overlapping."),
    # ⭐ 문틀 액자
    ("Shot from the next room through an open doorway, the dark door frame "
     "closing in on all four sides and only the lit room beyond it visible",
     "FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
     "a frame-within-the-frame made by the doorway, the outer edges dark."),
    # ⭐ 역광 실루엣 (사물의 실루엣 — 사람 낱말을 쓰지 않는다)
    ("Backlit hard from a window so the objects in the foreground fall into "
     "flat dark shapes against the pale light, long slatted shadows from the "
     "blinds lying across the floor",
     "FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
     "the bright window high in the frame and the dark shapes below it."),
]

# ── 대사 컷 구도 (말하는 컷) — 특례 둘 + 세 갈래 ──────────────────
#    ⚠️ 말하는 컷에는 **뒷모습을 안 쓴다** — 입이 안 보이면 말하는 컷이 아니다.
TALK_SHOTS = [
    ("A medium shot tightening towards a close-up, {ang}, intense steady gaze",
     None),
    # ⭐ 유리 너머
    ("Shot through the glass wall or glass door of the room, {ang}, the glass "
     "catching a faint reflection of the corridor lights across their face",
     "FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
     "the glass between the camera and them, a faint reflection laid over "
     "their face, {eye}."),
    # ⭐ 문틀 · 블라인드
    ("Framed standing inside a doorway, {ang}, half-open blind slats throwing "
     "hard horizontal bars of shadow across their face and the wall",
     "FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
     "a frame-within-the-frame made by the doorway or the blinds, the outer "
     "edges dark, {eye}."),
    # ⭐ 사람을 작게 — 얼굴만 이어지면 숨이 막힌다. 공간을 한 번씩 보여 준다.
    ("A wide shot that leaves them small against the room, {ang}, the empty "
     "space around them carrying the weight",
     "FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
     "the person placed off to one side with the room open around them, "
     "{eye}."),
]

# ── 나레이션인데 인물이 선 컷 — 네 갈래 (입은 다문다) ─────────────
CAST_NARR_SHOTS = [
    ("A wide shot that leaves the person small in the space, {ang}",
     "FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
     "the person placed off to one side with the empty room around them, "
     "{eye}."),
    # ⭐ 뒷모습 · 실루엣
    ("Shot from behind them, hard backlight from the window ahead turning "
     "them into a dark shape, their face not visible at all, the shoulders "
     "and the room telling it instead",
     "FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
     "their back filling the lower half and the lit room beyond."),
    # ⭐ 유리 너머
    ("Shot through a glass door or a night window, {ang}, their face and the "
     "reflection of the room laid over each other on the glass",
     "FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
     "the glass between the camera and them, {eye}."),
    # ⭐ 문틀 액자
    ("Seen from the next room through an open doorway, {ang}, the dark door "
     "frame closing in on all four sides",
     "FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
     "a frame-within-the-frame made by the doorway, the outer edges dark, "
     "{eye}."),
]

FRAMING_MID = ("FRAMING: vertical 9:16 portrait, filling the whole frame edge "
               "to edge, the person kept in the middle, " + EYE_LINE + ".")


# ── ⭐⭐⭐ 2026-10-01 — **2분 드라마 구도 설계** (손님 승인) ─────────────
#    반려동물 식당 쇼츠 · 해양생물 쇼츠에서 가져온 것:
#      ① 구도마다 **화면 크기(size)·방향(dir)** 꼬리표를 단다 — 이웃한 두 컷은
#         **둘 다** 달라야 한다 (같은 구도가 이어지면 컷이 끊겨 보인다).
#         예전엔 표마다 컷 번호로 돌려 써서, 표가 다른 두 컷이 '유리 너머 →
#         유리 너머' 로 이어질 수 있었다 (S93: 36컷 중 15컷이 유리·문틀).
#      ② 유리 너머·문틀 같은 **특수 구도는 한 편에 SPECIAL_MAX 번까지**
#         (해양생물 쪽 '단면 상자 구도 최대 2장면' 과 같은 생각).
#      ③ 나레이션 컷도 **얼굴이 또렷한 구도**만 (손님 지시 2026-10-01 —
#         뒷모습·실루엣·작게 담는 와이드는 2분 드라마에서 뺀다).
#      ④ 그림과 옴니 영상이 **같은 계획**을 읽는다 (잣대 한 벌).
#    ⚠️ 계획은 대본 차례로만 정해진다 — 무작위가 아니다. 같은 대본은 늘 같은
#       구도라 다시 지어도 그림을 0원으로 다시 쓴다.
#    ⚠️ 옛 여러 편 형식은 손대지 않는다 (위 표 · 컷 번호로 돌려 쓰기 그대로).
SPECIAL_MAX = 4
FR_FACE = ("FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
           "the face near the middle of the frame, clearly visible and sharp, {eye}.")
FR_FACE_WIDE = ("FRAMING: vertical 9:16 portrait, filling the whole frame edge to "
                "edge, seen from the knees up with the room around them, the face "
                "near the middle and clearly readable, {eye}.")
FR_GLASS = ("FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
            "the glass between the camera and them, a faint reflection laid over "
            "the scene, the face near the middle and clearly readable, {eye}.")
FR_DOOR = ("FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
           "a frame-within-the-frame made by the doorway, the outer edges dark, "
           "the face near the middle and clearly readable, {eye}.")
FR_TWO = ("FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
          "both faces clearly visible and sharp, {eye}.")
FR_OTS = ("FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
          "the speaking face clearly visible and sharp past the soft near "
          "shoulder, {eye}.")
FR_TIGHT = ("FRAMING: vertical 9:16 portrait, filling the whole frame edge to edge, "
            "the face filling much of the frame, {eye}.")


def _shot(key, size, dir_, text, framing, moves, special=False):
    return {"key": key, "size": size, "dir": dir_, "text": text,
            "framing": framing, "moves": list(moves), "special": special}


# 한 사람 (나레이션 · 대사 공통) — 얼굴이 또렷한 것만
FACE_SHOTS = [
    _shot("mid-front", "medium", "front",
          "A medium shot from the waist up, the camera facing them almost "
          "straight on, {ang}", FR_FACE, ("push", "drift", "pull")),
    _shot("close-3q", "close", "three-quarter",
          "A close-up of the face and shoulders in three-quarter view, {ang}",
          FR_FACE, ("push", "hold", "drift")),
    _shot("wide-3q", "wide", "three-quarter",
          "A medium-wide shot from the knees up in three-quarter view with the "
          "room open around them, {ang}", FR_FACE_WIDE, ("push", "drift")),
    _shot("mid-profile", "medium", "profile",
          "A medium shot in clean side profile, {ang}, the profile of the face "
          "sharp against the soft room", FR_FACE, ("drift", "push")),
    _shot("close-front", "close", "front",
          "A close-up of the face straight on, {ang}, intense steady gaze",
          FR_FACE, ("push", "hold")),
    _shot("glass", "medium", "through",
          "Shot through the glass wall or glass door of the room, {ang}, the glass "
          "catching a faint reflection of the lights across them", FR_GLASS,
          ("drift", "push"), special=True),
    _shot("wide-front", "wide", "front",
          "A medium-wide shot from the knees up, facing them straight on in the "
          "middle of the room, {ang}", FR_FACE_WIDE, ("push", "pull")),
    _shot("close-profile", "close", "profile",
          "A close-up in side profile, {ang}, the eye and the line of the jaw "
          "sharp", FR_FACE, ("hold", "drift")),
    _shot("doorway", "wide", "through",
          "Framed standing inside a doorway seen from the next room, {ang}, "
          "half-open blind slats throwing soft bars of shadow across the wall",
          FR_DOOR, ("push", "drift"), special=True),
]
# 두 사람이 한 화면 (나레이션) — 두 얼굴 다
TWO_SHOTS = [
    _shot("two-mid", "medium", "front",
          "A two-shot at medium distance, both of them facing the camera at a "
          "slight angle, {ang}", FR_TWO, ("push", "drift")),
    _shot("two-profile", "medium", "profile",
          "A two-shot in side view across the space between them, both faces "
          "in profile, {ang}", FR_TWO, ("drift", "push")),
    _shot("two-wide", "wide", "three-quarter",
          "A medium-wide two-shot in three-quarter view with the room around "
          "them, {ang}", FR_TWO, ("push", "pull")),
    _shot("two-glass", "medium", "through",
          "A two-shot seen through a glass partition, {ang}, a faint reflection "
          "of the lights laid over the glass", FR_TWO, ("drift",), special=True),
]
# 두 사람이 한 화면 (대사) — 말하는 얼굴이 또렷해야 입모양이 산다
OTS_SHOTS = [
    _shot("ots-mid", "medium", "ots",
          "An over-the-shoulder shot past {other}, the near shoulder soft in the "
          "foreground framing {speaker}, {ang}", FR_OTS, ("push", "drift", "hold")),
    _shot("ots-close", "close", "ots",
          "A close over-the-shoulder shot past {other}, the near shoulder a soft "
          "blur at the edge, {speaker}'s face filling the frame, {ang}", FR_OTS,
          ("hold", "push")),
    _shot("two-mid", "medium", "front",
          "A two-shot at medium distance, {speaker} facing the camera at a slight "
          "angle and {other} turned towards them, {ang}", FR_TWO, ("push", "drift")),
]
# 결정적 순간 — 얼굴만 크게, 카메라는 멈춘다
CLIMAX_SHOT = _shot("climax", "close", "front", "A tight close-up on the face, {ang}",
                    FR_TIGHT, ("hold",))
VERDICT_WORDS = ("판결", "선고", "법원은", "재판부")


def drama_flip_from(cuts):
    """2분 드라마는 한 편이다 — 판결이 나오는 나레이션부터 앵글을 뒤집는다.

    ⚠️ 옛 여러 편은 '마지막 편부터' 뒤집었다. 2분 드라마에 그 셈을 그대로 쓰면
       편이 하나라 **첫 컷부터 전부** 뒤집혀 있었다 (가진 쪽을 내려다봤다).
    """
    half = len(cuts) // 2
    for i, c in enumerate(cuts):
        if i < half or not is_narr(c):
            continue
        if any(w in text_of(c) for w in VERDICT_WORDS):
            return int(c["n"])
    return 10 ** 9


def plan_shots(cuts, climax=()):
    """2분 드라마 구도 계획 — 컷마다 구도 하나 (위 ① ~ ④).

    고르는 법: 그 컷에 맞는 표에서, 컷 번호만큼 돌린 차례로 보며
      ㉠ 앞 컷과 크기·방향이 **둘 다** 다르고 ㉡ 특수 구도는 한도 안인 것 중
      ㉢ 이번 편에서 **덜 쓴 것**을 고른다. 없으면 하나만 달라도 되게 푼다.
    움직임도 앞 컷과 다르게 고른다 (같은 움직임이 이어지면 안 움직여 보인다).
    """
    out, prev, used, special = [], None, {}, 0
    for c in cuts:
        who = ST90.still_who(c, True)
        talks = not is_narr(c)
        if not who:
            out.append(None)
            prev = None
            continue
        if talks and int(c["n"]) in set(climax):
            pool = [CLIMAX_SHOT]
        elif talks and len(who) >= 2:
            pool = OTS_SHOTS
        elif len(who) >= 2:
            pool = TWO_SHOTS
        else:
            pool = FACE_SHOTS
        k = (int(c["n"]) - 1) % len(pool)
        order = pool[k:] + pool[:k]

        def dir_of(s):
            # 어깨 너머는 **말하는 사람**마다 방향이 다르다 (주고받기는 거울상)
            return f"ots:{c['turns'][0][0]}" if s["dir"] == "ots" else s["dir"]

        def room(s):
            return not (s["special"] and special >= SPECIAL_MAX)

        def both(s):
            return prev is None or (s["size"] != prev["size"]
                                    and dir_of(s) != prev["dir"])

        def either(s):
            return prev is None or (s["size"] != prev["size"]
                                    or dir_of(s) != prev["dir"])

        cand = ([s for s in order if room(s) and both(s)]
                or [s for s in order if room(s) and either(s)]
                or [s for s in order if room(s)] or order)
        pick = min(cand, key=lambda s: (used.get(s["key"], 0), order.index(s)))
        used[pick["key"]] = used.get(pick["key"], 0) + 1
        special += 1 if pick["special"] else 0
        mv_prev = prev["move"] if prev else None
        moves = pick["moves"]
        mk = (int(c["n"]) - 1) % len(moves)
        mvs = moves[mk:] + moves[:mk]
        move = next((m for m in mvs if m != mv_prev), mvs[0])
        one = {"key": pick["key"], "size": pick["size"], "dir": dir_of(pick),
               "special": pick["special"], "move": move,
               "text": pick["text"], "framing": pick["framing"]}
        out.append(one)
        prev = one
    return out


# 움직임 이름 → 영상 지문 한 마디 (2분 드라마)
DRAMA_MOVE = {
    "push": "the camera pushing in very slowly and smoothly",
    "pull": "the camera pulling back very slowly and smoothly",
    "drift": "the camera drifting sideways in one slow steady move",
    "hold": ("the camera locked off completely still on a tripod, so that only "
             "the face moves"),
}


def compose_of(c, prev=None, ctx=None, who=None):
    """이 컷의 (구도 한 문장, FRAMING, CAMERA). **움직임은 안 들어간다.**

    그림도 영상도 이 표를 읽는다 — 두 벌로 두면 한쪽만 좋아진다(실제로
    영상 쪽만 좋아져 있었다. 위 설명 참고).

    ⚠️⚠️ who 를 **부르는 쪽이 정해 준다.** 그림 쪽은 나레이션 컷이면 who 가
       있어도 장소 갈래로 보낸다(2026-09-10 · "나레이션 배경에 사람이 자꾸
       들어가"). 여기서 c["who"] 를 그냥 읽으면 **잣대가 두 벌**이 되어,
       장소 갈래로 보낸 컷에 사람 구도가 얹힌다 — 실제로 그렇게 됐고
       still_check 가 "mouths · people · person" 으로 잡았다.
    """
    who = (c.get("who") or []) if who is None else who
    scene = c["scene"]
    ctx = ctx or {}
    n = int(c.get("n") or 1) - 1      # 번호 없는 조각도 안 죽게
    pick = ctx.get("pick")
    if pick and who:
        # ⭐ 2분 드라마 — 구도 계획(plan_shots)이 정한 것을 그대로 쓴다
        speaker = str((c.get("turns") or [[who[0], ""]])[0][0])
        if speaker not in who:
            speaker = who[0]
        other = next((w for w in who if w != speaker), "")
        fill = {"ang": angle_of(speaker, ctx.get("flip")), "eye": EYE_LINE,
                "speaker": speaker, "other": other}
        return (f"SHOT: {scene}. {pick['text'].format(**fill)}.",
                pick["framing"].format(**fill), "CAMERA: " + BLUR)
    if not who:
        shot, fr = PLACE_SHOTS[n % len(PLACE_SHOTS)]
        return (f"SHOT: {scene}. {shot}.", fr or FRAMING_NOBODY,
                "CAMERA: " + BLUR_NOBODY)

    ang = angle_of(who[0], ctx.get("flip"))
    fill = {"ang": ang, "eye": EYE_LINE}
    if not ctx.get("talks"):
        # ② 나레이션인데 **등장인물이 서 있는** 컷 (2026-09-17 손님 지시)
        #    빈 방만 이어지면 드라마로 안 보인다. 얼굴 기준이 붙어 있으므로
        #    낯선 사람이 나올 일이 없다.
        shot, fr = CAST_NARR_SHOTS[n % len(CAST_NARR_SHOTS)]
        return (f"SHOT: {scene}. {shot.format(**fill)}. They do not speak; "
                f"mouths stay closed.", fr.format(**fill), "CAMERA: " + BLUR)
    if len(who) >= 2 or is_reply(c, prev):
        # ③ 대립 · 주고받음 — 오버 더 숄더
        return (f"SHOT: {scene}. An over-the-shoulder shot past the listener, "
                f"the near shoulder soft in the foreground framing the speaker, "
                f"{ang}.",
                f"FRAMING: vertical 9:16 portrait, filling the whole frame edge "
                f"to edge, frame-in-frame composition using the doorway, blinds "
                f"or glass partition of the room, {EYE_LINE}.",
                "CAMERA: " + BLUR)
    if ctx.get("climax"):
        # ④ 결정적 순간 — 얼굴만 크게
        return (f"SHOT: {scene}. A tight close-up on the face, {ang}.",
                f"FRAMING: vertical 9:16 portrait, filling the whole frame edge "
                f"to edge, the face filling much of the frame, {EYE_LINE}.",
                "CAMERA: " + BLUR)
    shot, fr = TALK_SHOTS[n % len(TALK_SHOTS)]
    return (f"SHOT: {scene}. {shot.format(**fill)}.",
            (fr or FRAMING_MID).format(**fill) if fr else FRAMING_MID,
            "CAMERA: " + BLUR)


# ── 움직임 — **영상에만** 붙는다 (그림은 움직일 수 없다) ──────────
MOVE_PLACE = [
    "the camera pulling back in a very slow zoom out that opens up the space",
    "the camera pushing in almost imperceptibly slowly",
    "the camera drifting sideways in a slow steady lateral move",
    "the camera easing sideways so the reflection slides across the glass",
    "the camera stepping through the doorway in a very slow push in",
    "the camera holding still while only the light shifts",
]
MOVE_TALK = [
    "the camera in a slow dramatic zoom in on the face",
    "the camera panning slowly and horizontally",
    "the camera holding still and only breathing slightly",
]


def move_line(c, ctx=None):
    """이 컷을 영상으로 살 때 붙일 **움직임** 한 마디."""
    ctx = ctx or {}
    n = int(c.get("n") or 1) - 1      # 번호 없는 조각도 안 죽게
    if ctx.get("pick"):
        # ⭐ 2분 드라마 — 움직임도 구도 계획이 정한다 (앞 컷과 다르게)
        return DRAMA_MOVE[ctx["pick"]["move"]]
    if ctx.get("climax"):
        # ⭐ 결정적 순간엔 **카메라를 멈춘다.** 전부 움직이면 오히려 싸구려다.
        return ("the camera locked off completely still on a tripod with no "
                "move at all, so that only the face moves")
    ring = MOVE_PLACE if not (c.get("who") or []) else MOVE_TALK
    return ring[n % len(ring)]


def shot_of(c, prev=None, ctx=None):
    """영상용 (SHOT, FRAMING, CAMERA) — 구도에 움직임을 얹은 것."""
    shot, framing, cam = compose_of(c, prev, ctx)
    mv = move_line(c, ctx)
    # ⚠️ **멈춘 샷에는 "이미 움직이고 있다" 를 붙이지 않는다.** 한 문장 안에서
    #    "카메라를 멈춘다" 와 "움직임이 첫 프레임부터 진행 중이다" 가 부딪치면
    #    모델은 둘 중 하나를 버린다 — 대개 멈추라는 쪽을 버린다.
    #    (결정적 순간 락오프도 그동안 이 모순을 달고 있었다)
    start = ("" if ("locked off" in mv or "holding still" in mv)
             else " The movement is already under way in the very first frame.")
    return (f"{shot.rstrip('.')}, {mv}.{start}", framing, cam)


def veo_prompt(c, prev=None, ctx=None):
    """그 컷을 손으로 만들 때 쓸 영상 프롬프트 (제미나이에 그대로 붙인다).

    ⭐ 2026-08-27 손님: "이미지는 중간중간 섞여 있고 동영상도 있어야 돼."
       맞다. 그래서 **스물세 컷 전부** 영상 프롬프트를 만들어 둔다 — 어느 컷을
       영상으로 올릴지는 손님이 고른다. 안 올린 컷만 그림으로 간다.
    """
    who = c.get("who") or []
    talks = not is_narr(c)
    speaker = kind_of(c)
    sec = veo_sec(c)
    shot, framing, cam = shot_of(c, prev, ctx)
    body = [f"{S.HEAD_FIX} {sec}-second single continuous take, "
            f"vertical portrait format (9 x 16)."]
    if who:
        body.append(people_of(who))
    body.append(shot)
    body.append(framing)
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
    body += [cam, COLOR, S.STYLE_FIX, NO_TEXT]
    return "\n".join(body)


# ── ⭐⭐⭐ 2분 드라마 — 인물과 대사 영상 지문 (2026-09-30) ────────────
def cast_characters(story):
    """대본이 정한 인물(cast) → characters (인물 시트·목소리가 읽는 꼴).

    ⚠️ 옛 여러 편은 characters 를 S001 한 곳에서 가져온다(기본 다섯).
       2분 드라마는 사건마다 인물이 다르다 — 대본이 정한 것을 그대로 쓴다.
       (S92 는 사건 인물이 장남·차남인데 characters 는 기본 다섯이었다)"""
    out = []
    for p in story.get("cast") or []:
        sex = "man" if str(p.get("sex") or "").strip() == "남" else "woman"
        age = p.get("age")
        face, build, wear, voice = (str(p.get(k) or "").strip().rstrip(".")
                                    for k in ("face", "build", "wear", "voice"))
        out.append({
            "name": p["name"], "role_en": p.get("role_en") or p["name"],
            "sex": p.get("sex"), "age": age,
            "flow_prompt": f"Korean {sex}, {age} years old, {face}.",
            "flow_sheet": "\n".join([f"FACE AND HAIR: {face}.",
                                     f"BUILD: {build}.", f"WEARING: {wear}."]),
            "face_tag": f"{age}, {face}"[:90],
            "voice": voice, "body": build, "outfit": wear,
        })
    return out


OMNI_HEAD = ("A short fictional drama scene. Every character is invented for this "
             "story and resembles nobody.")
OMNI_STYLE = ("STYLE: naturalistic cinematic drama, soft film grain, muted "
              "desaturated palette, soft practical lighting, shallow depth of field.")
# ⭐⭐⭐ 2026-10-01 — 옴니 대사 컷에 **초 단위 카메라** (해양생물 쇼츠에서 · 손님 승인).
#    예전 시간표에는 '몇 초에 무슨 말' 만 있고 카메라는 SHOT 줄 한 마디였다.
#    해양생물 쪽 실측 — 뭉뚱그려 적으면 AI 가 방향·구도를 멋대로 해석했다.
#    → 구간마다 카메라가 **어디서 어디로** 가는지 적는다. 말이 시작될 때 움직임이
#      붙고, 숨 쉬는 틈에 한 박자 늦추고, 끝에서는 **멈춰 선다** (컷 끝에서
#      흐트러지지 않게 · 다음 컷으로 깨끗하게 넘어가게).
#    ⚠️ 움직임은 한 컷에 **한 방향 한 번**이다 (크게 움직이면 배경이 무너진다 —
#       반려동물 식당 쇼츠 실측). 무엇을 할지는 구도 계획(plan_shots)이 정한다.
OMNI_CAM = {
    "push": ("starts a very slow push-in from the opening framing",
             "the slow push-in continues towards {role}'s face",
             "the push-in slows for a beat",
             "settles to a stop on a slightly closer framing of {role} and holds"),
    "pull": ("starts a very slow pull-back from the opening framing",
             "the slow pull-back continues, a little more of the room opening up "
             "around {role}",
             "the pull-back slows for a beat",
             "settles to a stop and holds"),
    "drift": ("starts one slow sideways drift",
              "the sideways drift continues with {role} clearly in view",
              "the drift slows for a beat",
              "settles to a stop and holds on {role}"),
    "hold": ("locked off completely still on a tripod",
             "still locked off while only {role}'s face moves",
             "still locked off",
             "still locked off until the end"),
}


def omni_timeline(role, text, sec, listener="", move=None):
    """[0.0-0.6s] 처럼 초를 박는다 (옴니 문서가 권하는 적기).
    ⚠️ 빠르기·숨·문장 나누기는 **talkplan 한 곳**의 값이다 — 산 길이(omni_sec)와
       초 표가 다른 잣대를 쓰면 표가 산 길이를 넘어 말이 잘린다.
    move 를 주면 구간마다 카메라 한 마디를 붙인다 (OMNI_CAM · 2026-10-01)."""
    cam = OMNI_CAM.get(move or "")

    def cm(k):
        return f" Camera: {cam[k].format(role=role)}." if cam else ""

    ss = talkplan.omni_sentences(text)
    rows = [f"[0.0-{talkplan.OMNI_LEAD:.1f}s] silent, {role} holds the moment"
            + (f" while {listener} listens with lips closed" if listener else "")
            + "." + cm(0)]
    t = talkplan.OMNI_LEAD
    for i, one in enumerate(ss):
        k = len(re.sub(r"[\s…·.,!?\"'~]", "", one)) / talkplan.OMNI_CHARS_PER_SEC
        rows.append(f"[{t:.1f}-{t + k:.1f}s] {role} says in Korean: \"{one}\""
                    + cm(1))
        t += k
        if i + 1 < len(ss):
            rows.append(f"[{t:.1f}-{t + talkplan.OMNI_PAUSE:.1f}s] one short breath."
                        + cm(2))
            t += talkplan.OMNI_PAUSE
    rows.append(f"[{t:.1f}-{float(sec):.1f}s] silent, lips closed, {role} holds the "
                "look until the end." + cm(3))
    return rows


def omni_prompt(c, prev, ctx, sec, chars, first=True):
    """대사 컷 하나를 옴니 플래시가 **입모양+대사**로 말하는 영상 지문.

    그림 역할은 맨 앞에 적는다 (옴니 문서):
      first=True  — Image1 = 그 컷 그림(첫 장면) · Image2… = 화면 인물의 시트 칸
      first=False — 안전 검사에 걸렸을 때 한 번 더: 칸만 참조로 (첫 장면 없음)
    ⚠️ 옷·생김새를 적지 않는다 — 참조 그림이 잡는다 (series.wear_bait).
    ⚠️ 목소리는 인물 한 줄(cast.voice)로 **고정**이다 — 손님: "등장인물별 성우
       코드, 속도, 톤 사전 설정해." 옴니는 소리 참조를 못 받으므로(공식 문서)
       같은 설명을 매 컷 똑같이 넣는 것이 고정하는 길이다."""
    who = list(c.get("who") or [])
    w, text = c["turns"][0]
    by = {x.get("name"): x for x in ST90.fix_voices(chars)}

    def en(nm):
        return str((by.get(nm) or {}).get("role_en") or EN.get(nm, nm))

    refs = [f"<IMAGE_REF_{i}>" for i in range(len(who))]
    if first:
        head = ("[# Sources <FIRST_FRAME>@Image1] [# References "
                + " ".join(f"{r}@Image{i + 2}" for i, r in enumerate(refs)) + "]")
    else:
        head = ("[# References "
                + " ".join(f"{r}@Image{i + 1}" for i, r in enumerate(refs)) + "]")
    role = en(w)
    others = [en(x) for x in who if x != w]
    cast = " and ".join(f"{en(x)} {r}" for x, r in zip(who, refs))
    one = len(who) == 1
    # ⭐ 구도 계획이 있으면(2분 드라마) 움직임은 시간표에 구간마다 적는다 —
    #    SHOT 줄에도 적으면 두 지시가 겹친다 (한 줄은 '줌인', 시간표는 '옆으로').
    pick = (ctx or {}).get("pick")
    if pick:
        shot, framing, cam = compose_of(c, prev, ctx)
    else:
        shot, framing, cam = shot_of(c, prev, ctx)
    for nm in sorted({x for x in who + [w]}, key=len, reverse=True):
        shot = shot.replace(nm, en(nm))
    say = "; ".join(str(x) for x in (c.get("say") or []) if str(x).strip())
    ch = by.get(w) or {}
    rows = [
        head,
        f"{OMNI_HEAD} Vertical 9:16, exactly {sec} seconds, one single continuous "
        "shot from the first frame to the last.",
        f"CAST: {cast} {'is the only person' if one else 'are the only people'} in "
        "this scene, each looking exactly like their own reference the whole time. "
        "Each reference shows that person twice — a close view and a full-length "
        "view — one single person.",
        shot, framing,
        "TIMELINE:",
        *omni_timeline(role, text, sec, " and ".join(others),
                       move=pick["move"] if pick else None),
        f"DIALOGUE: [LANGUAGE: KOREAN] only {role} speaks, in natural fluent everyday "
        "Korean with standard Seoul intonation, at a brisk natural conversational "
        "pace with every consonant and syllable crisp and clearly articulated, "
        f"lips moving in sync with every syllable. {role} says these exact "
        f"words once and nothing more: \"{text}\"",
        f"VOICE: {role} — {ST90.voice_line(ch)}."
        + (f" Delivery (Korean note): {say}." if say else ""),
        f"SOUND: {role}'s voice with quiet room tone underneath, and nothing else.",
        cam, COLOR, OMNI_STYLE, NO_TEXT,
        ("Use Image1 as the starting frame. Use the other images as references for "
         "the people." if first else
         "Use the given images only as references for how the people look; the "
         "video opens on a fresh shot of the scene."),
    ]
    return "\n".join(r for r in rows if r)


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
    # ⭐ 2026-09-30 — 2분 드라마면 인물 참조가 시트 칸이다 (위 SHEET_REFS)
    global SHEET_REFS
    drama = str(story.get("format") or "") == talkplan.DRAMA
    SHEET_REFS = drama
    chars = cast_characters(story) if drama else None

    base = json.loads(BASE.read_text(encoding="utf-8"))
    have = {c.get("name") for c in (base.get("characters") or [])}
    missing = [k for k in set(CARD.values()) if k not in have]
    if missing:
        print(f"❌ 인물 카드가 없다: {', '.join(missing)}")
        return 1

    check_say(story)
    check_parts(story)
    check_scrub(story)
    # ⭐ 편마다 **마지막 대사 컷**을 찾아 둔다 — 거기서는 카메라를 멈춘다
    #    (결정적 순간 락오프 · 2026-09-17 손님 선택). 전부 움직이면 싸구려다.
    climax = set()
    parts_all = story.get("parts") or []
    for p_ in parts_all:
        a_, b_ = p_["cuts"]
        talky = [x["n"] for x in story["cuts"]
                 if a_ <= x["n"] <= b_ and not is_narr(x)]
        if talky:
            climax.add(talky[-1])
    # 판결이 난 뒤(마지막 편)에는 힘의 관계가 뒤집힌다 — 앵글도 뒤집는다
    last_a = parts_all[-1]["cuts"][0] if parts_all else 10 ** 9
    # ⭐ 2분 드라마는 한 편이라 '마지막 편' 이 곧 전부다 — 판결 나레이션부터 뒤집는다
    if drama:
        last_a = drama_flip_from(story["cuts"])
    # ⭐⭐⭐ 2026-10-01 — 2분 드라마 구도 계획 (크기·방향 · 이웃 컷 둘 다 다르게)
    picks = plan_shots(story["cuts"], climax) if drama else [None] * len(story["cuts"])

    cuts = []
    prev = None                       # 주고받는 대사를 알아보려고 앞 컷을 쥔다
    for c, pick in zip(story["cuts"], picks):
        c = dict(c)
        c["turns"] = [tuple(t) for t in c["turns"]]
        shot_ctx = {"talks": not is_narr(c), "climax": c["n"] in climax,
                    "flip": c["n"] >= last_a, "drama": drama, "pick": pick}
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
            # ⚠️ 그림과 영상이 **같은 prev·ctx** 를 받아야 같은 구도가 나온다.
            #    (그림만 맨몸으로 부르면 구도표가 늘 첫 갈래로 떨어진다)
            "still": still_prompt(c, prev, shot_ctx),
            "veo": veo_prompt(c, prev, shot_ctx),
            "flow": flow_prompt(c),
        })
        if pick:
            # ⭐ 조립(카메라 무빙)과 검사가 읽는다 — 그림·영상과 같은 계획
            cuts[-1]["shot"] = {k: pick[k] for k in ("key", "size", "dir", "move")}
        ins = c.get("insert") if drama else None
        if ins and ins.get("word") and ins.get("thing"):
            cuts[-1]["insert"] = {"word": ins["word"], "thing": ins["thing"],
                                  "still": insert_prompt(ins["thing"])}
        # ⭐ 2분 드라마 — 대사 컷(한 사람 한 줄)은 옴니 영상 지문도 함께 짓는다
        if drama and not is_narr(c) and len(c["turns"]) == 1:
            sec_o = talkplan.omni_sec(c["turns"][0][1])
            cuts[-1]["omni_sec"] = sec_o
            cuts[-1]["omni"] = omni_prompt(c, prev, shot_ctx, sec_o, chars)
            cuts[-1]["omni_ref"] = omni_prompt(c, prev, shot_ctx, sec_o, chars,
                                               first=False)
        prev = c
    doc = {"sid": sid, "case_id": story.get("case_id", ""),
           "title": story["title"], "hook": story.get("hook", ""),
           "series_label": story.get("series_label") or story["title"],
           "parts": [dict(x) for x in story["parts"]],
           # ⭐ 2026-09-04 — 사건마다 사람이 다르다. 이 사건이 더 세운 사람
           #    (장남·며느리 등)의 나이대·성별을 조립 쪽으로 넘긴다.
           #    안 넘기면 그 사람이 나레이션 목소리로 말한다.
           "people": dict(story.get("people") or {}),
           "cuts": cuts,
           "characters": (chars if drama else base.get("characters") or [])}
    if drama:
        doc["format"] = talkplan.DRAMA
        doc["cast"] = list(story.get("cast") or [])
        # ⭐ 1분 전부 영상 (2026-10-02) — 모든 컷이 옴니 영상 · 조립이 틈을 잘라 붙인다
        if story.get("all_video"):
            doc["all_video"] = True
            for cut, sc in zip(cuts, story["cuts"]):
                cut["place"] = str(sc.get("place") or "")
                # ⭐ 그림 컷(관계도·연표 · 0원)과 화면 위 대목 표시 (2026-10-02 · S94 v5)
                for k in ("fig", "chapter"):
                    if sc.get(k):
                        cut[k] = sc[k]
            # ⭐ 말 사이 쉼 · 이름표 「이름 (관계)」 · 끝 화면 글 · 그림 설계 (손님 확정)
            for k in ("gap", "name_first", "end_note", "figs"):
                if story.get(k) is not None:
                    doc[k] = story[k]
    # ⭐⭐⭐ 2026-09-10 — 화면이 값을 **스스로 세지 않게** 여기서 찍어 둔다.
    #    화면은 `706원 × 편 수` 로 어림하고 있었다("편마다 한 컷" 시절 셈).
    #    대사 컷 전부를 영상으로 바꾸자 화면이 2,824원이라 적고 실제로는
    #    12,936원이 나가게 됐다 — 값을 보고 승인하는 사람에게 거짓말이다.
    #    세는 자리를 하나(src/talkplan.py)로 두고, 화면은 이 값을 읽는다.
    if drama:
        # ⭐ 대사 영상은 옴니 값으로 센다 (cost.py 단가표 한 곳) — 화면이 이 값을 읽는다
        import cost                                          # noqa: E402
        import omni                                          # noqa: E402
        import still as STL                                  # noqa: E402
        import lookalike                                     # noqa: E402
        rate = cost.video_krw(omni.MODEL, 1) / cost.USD_KRW
        doc["talk"] = talkplan.plan(doc, krw_per_sec=rate, usd_krw=cost.USD_KRW)
        uniq = len({c["still"] for c in cuts})
        one = cost.image_krw(STL.MODEL, STL.SIZE)
        # ⭐ 증거 확대 그림도 그림이다 — 값에 넣는다 (2026-10-01)
        ins_n = len({c["insert"]["still"] for c in cuts if c.get("insert")})
        img = one * (uniq + ins_n)
        sheet = cost.image_krw(STL.MODEL, "4K")
        # ⭐ 이웃 컷이 닮아 다시 그릴 수 있는 몫 (많아야 REDRAW_MAX 장) — **최대값**을 적는다
        redraw = one * lookalike.REDRAW_MAX
        doc["talk"]["drama"] = {
            "talk_n": doc["talk"]["n"], "talk_krw": doc["talk"]["krw"],
            "stills": uniq, "inserts": ins_n, "still_krw": round(img),
            "sheet_krw": round(sheet), "redraw_krw": round(redraw),
            # ⭐ 그림 먼저(①) · 영상(②) 을 따로 누르므로 값도 따로 적는다
            "pic_krw": round(img + sheet + redraw),
            "krw": round(doc["talk"]["krw"] + img + sheet),
        }
    else:
        doc["talk"] = talkplan.plan(doc)
    # ⭐ 대본 글이 바뀌면 '만든 길이' 기록을 지운다 — 낡은 숫자를 보고
    #    판단하면 60초를 넘긴 편을 그대로 올리게 된다.
    import hashlib
    sig = hashlib.sha1(json.dumps(
        [[t for t in (c.get("turns") or [])] for c in cuts],
        ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
    out_p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")

    # ⭐⭐ 2026-08-31 손님: "유튜브 업로드 버튼이 아직도 없어."
    #    만들어 두긴 했는데 **릴리스에 있는 meta.json 이 있어야만** 칸이
    #    떴다. → 올릴 글을 **대본 옆에 같이 둔다.** 영상을 안 만들어도 늘 있다.
    #    ⚠️ 셈법은 여전히 src/ytmeta.py 한 곳뿐이다 (여기서 부르기만 한다).
    sys.path.insert(0, str(ROOT / "src"))
    import ytmeta                                            # noqa: E402
    import shortstate                                        # noqa: E402
    if shortstate.mark_script(sid, sig):
        print("  ⚠️ 대본 글이 바뀌었습니다 — 만든 길이 기록을 지웠습니다 "
              "(낡은 숫자로 60초 벽을 잘못 판단하지 않도록).")
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
