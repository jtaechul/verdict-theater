#!/usr/bin/env python3
"""⭐ 1분 전부 영상 드라마의 **카메라 계획** — 컷마다 렌즈 · 높이 · 움직임 (값 0원)

⭐⭐⭐ 2026-10-02 손님(참고 영상 두 편과 함께): "카메라나 인물 구도, 화면 구도도 이런 식으로
   좀 다채롭게 만들어봐." 두 영상은 컷마다 **렌즈·높이·움직임**이 확 바뀌었다 —
   차 안 시점 · 어안 · 낮은 앵글로 따라가기 · 하늘에서 내려다보기 · 앞에 물건을 걸친 구도.
   2분 드라마의 구도 계획(build_short90.plan_shots)은 화면 크기와 방향만 바꿨다.

정한 것 (손님 승인 2026-10-02)
   ① 컷마다 꼬리표 셋 — 렌즈(어안·광각·보통·망원) · 높이(하늘·위·눈높이·아래) ·
      움직임(내려오기·밀기·옆으로 따라가기·손에 든 흔들림·돌기·초점 옮기기·고정 …).
      **이웃한 두 컷은 셋 가운데 둘 이상이 달라야 한다** (MIN_DIFF).
   ② 장소가 바뀌면 그 장소의 첫 컷은 **어디인지 보여 주는 컷** — 바깥이면 하늘에서
      내려와 그 사람 얼굴에서 멈추고, 안이면 천장 높이에서 내려온다.
   ③ 특별한 시점(어안·돌리줌)은 한 편에 SPECIAL_MAX 번까지 — 돌리줌은 이야기가
      **뒤집히는 나레이션**(그런데·하지만…)에서만 쓴다.
   ④ 마지막 컷은 그 사람에게서 천천히 멀어진다 (바깥이면 하늘로 올라간다).
   ⑤ 대사 컷은 입이 또렷해야 한다 — 크게 움직이는 구도(돌기·어안·내려오기)는 안 쓴다.
   ⚠️ 얼굴은 언제나 또렷하게 (2026-10-01 핵심 규칙) — 멀리서 시작해도 **끝은 얼굴**이다.
   ⚠️ 무작위가 아니다. 같은 대본은 늘 같은 계획이다 (다시 지어도 같은 영상 지문 → 0원 재사용).
"""
import re

MIN_DIFF = 2
SPECIAL_MAX = 2
TAGS = ("lens", "height", "move")

LENS = {
    "wide": "wide-angle lens with a little natural perspective stretch at the edges",
    "normal": "natural normal lens",
    "tele": "long telephoto lens, compressed depth, the background melted into "
            "creamy soft blur",
    "fisheye": "extreme fisheye lens, the whole space bending around the edges of "
               "the frame",
}
HEIGHT = {
    "aerial": "starting from aerial drone height",
    "high": "camera above eye level looking down",
    "eye": "camera at eye level",
    "low": "camera below eye level looking up",
}
OUTDOOR = ("hillside", "mountain", "outdoor", "street", "garden", "field", "path",
           "forest", "yard", "road", "beach", "river", "rooftop", "park", "grave")
TWIST = ("그런데", "하지만", "그러나", "알고 보니", "뜻밖에")


def _s(key, kind, lens, height, move, text, cam, special=False, two=False,
       need=""):
    """구도 하나. cam = 시간표 네 마디 (시작 · 이어서 · 숨 고르기 · 멈춤)."""
    return {"key": key, "kind": kind, "lens": lens, "height": height, "move": move,
            "text": text, "cam": cam, "special": special, "two": two, "need": need}


# ── 장소 첫 컷 (어디인지 보여 주고, 끝은 그 사람 얼굴) ──────────────
EST_OUT = _s("est-aerial", "est", "wide", "aerial", "descend",
             "The shot opens on a high aerial view over the whole place and descends "
             "smoothly in one continuous move, ending at eye level on a medium shot of "
             "{main} with the face clear",
             ("high aerial view over the whole place, already descending slowly",
              "descending smoothly towards {main}",
              "easing down to eye level in front of {main}",
              "settled on a medium shot of {main}, the face clear, holding still"))
EST_IN = _s("est-crane", "est", "wide", "high", "crane",
            "The shot starts high near the ceiling looking down across the room and "
            "cranes down in one smooth move to {main} at eye level, the face clear",
            ("high near the ceiling looking down across the room, already moving",
             "craning down smoothly towards {main}",
             "the crane slowing as it reaches eye level",
             "settled at eye level on {main}, the face clear, holding still"))

EST_DOOR = _s("est-door", "est", "normal", "eye", "through",
              "The shot starts outside the room looking in through the open doorway "
              "and moves slowly through it towards {main}, the face clear",
              ("outside the room looking in through the open doorway, already moving",
               "moving slowly through the doorway towards {main}",
               "slowing inside the room", "settled on {main}, the face clear, holding"))
EST_PAN = _s("est-pan", "est", "wide", "low", "pan",
             "The shot starts low on the quiet far side of the room and pans slowly "
             "across to find {main}, the face clear",
             ("low on the quiet far side of the room, starting a slow pan",
              "panning slowly across the room", "finding {main}",
              "settled on {main}, the face clear, holding"))
EST_INS = [EST_IN, EST_DOOR, EST_PAN]

# ── 나레이션 컷 (사람은 입을 다문다) ───────────────────────────────
NARR = [
    _s("n-track", "narr", "tele", "eye", "track",
       "A long-lens shot tracking sideways alongside {main} at a slow steady pace, "
       "the foreground sliding past in soft blur, {main}'s face clear",
       ("tracking sideways alongside {main}", "still tracking at the same slow pace",
        "the tracking slowing", "slowing to a stop with {main}'s face clear")),
    _s("n-high", "narr", "normal", "high", "push",
       "A high-angle shot looking down at {main}, slowly pushing in until the face "
       "fills the upper part of the frame",
       ("looking down at {main} from above, starting a slow push-in",
        "the push-in continuing towards {main}'s face", "the push-in slowing",
        "settled close on {main}'s face from above, holding")),
    _s("n-low", "narr", "wide", "low", "static",
       "A low-angle wide-lens shot from below looking up at {main}, the ceiling or "
       "sky above them, the camera locked off",
       ("locked off low, looking up at {main}", "still locked off",
        "still locked off", "still locked off until the end")),
    _s("n-arc", "narr", "normal", "eye", "arc",
       "A slow arc around {main} from side profile to a three-quarter front view",
       ("starting a slow arc around {main} from side profile",
        "the arc continuing around {main}", "the arc slowing",
        "settled on a three-quarter front view of {main}'s face, holding")),
    _s("n-rack", "narr", "tele", "eye", "rack",
       "A long-lens shot with the focus pulling from {fg} soft in the near foreground "
       "to {main}'s face sharp behind it",
       ("{fg} sharp in the near foreground, {main} soft behind",
        "the focus pulling slowly from {fg} to {main}",
        "{main}'s face coming sharp", "holding on {main}'s face, sharp")),
    _s("n-handheld", "narr", "normal", "eye", "handheld",
       "A handheld shot backing away in front of {main} as they move, the camera "
       "breathing slightly, {main}'s face clear",
       ("handheld, backing away in front of {main}", "following {main}'s pace",
        "the camera breathing slightly", "slowing to a gentle stop on {main}'s face")),
    _s("n-dolly-zoom", "narr", "normal", "eye", "zoom",
       "A slow dolly-zoom on {main}: the camera eases forward while the background "
       "seems to stretch away behind them, a quiet sense of vertigo",
       ("starting a slow dolly-zoom on {main}",
        "the background stretching away behind {main}",
        "the vertigo slowing", "settled on {main}'s face, holding"),
       special=True, need="twist"),
    _s("n-fisheye", "narr", "fisheye", "low", "static",
       "A very wide fisheye shot from low and close, {main}'s face large near the "
       "lens and the whole space bending around the edges",
       ("locked off close and low on {main}", "still locked off",
        "still locked off", "still locked off until the end"),
       special=True, need="one"),
]

# ── 대사 컷 (입이 또렷하게 — 크게 안 움직인다) ───────────────────────
TALK = [
    _s("t-close-tele", "talk", "tele", "eye", "static",
       "A close-up of {speaker}'s face with a long lens, the background melted into "
       "soft blur, the camera locked off",
       ("locked off on {speaker}'s face", "still locked off", "still locked off",
        "still locked off until the end")),
    _s("t-low-mid", "talk", "normal", "low", "push",
       "A slightly low-angle medium shot of {speaker} from the chest up, pushing in "
       "very slowly",
       ("slightly low on {speaker}, starting a very slow push-in",
        "the slow push-in continuing", "the push-in slowing for a beat",
        "settled a little closer on {speaker}, holding")),
    _s("t-ots", "talk", "tele", "eye", "drift",
       "An over-the-shoulder shot past {other}'s soft near shoulder, framing "
       "{speaker}'s face",
       ("over {other}'s shoulder on {speaker}, starting one slow sideways drift",
        "the drift continuing with {speaker}'s face clear", "the drift slowing",
        "settled, holding on {speaker}'s face"), two=True),
    _s("t-high-close", "talk", "normal", "high", "static",
       "A slightly high-angle close-up of {speaker} looking up, the camera locked off",
       ("locked off slightly above {speaker}", "still locked off", "still locked off",
        "still locked off until the end")),
    _s("t-profile", "talk", "tele", "eye", "drift",
       "A close side-profile shot of {speaker} with a long lens, the lips clear",
       ("on {speaker}'s profile, starting one slow drift",
        "the drift continuing, the lips clear", "the drift slowing",
        "settled, holding on {speaker}'s profile")),
    _s("t-wide-two", "talk", "wide", "eye", "static",
       "A wide-angle two-shot with {speaker} close to the lens and {other} further "
       "back in the frame, both faces clear",
       ("locked off on both of them", "still locked off", "still locked off",
        "still locked off until the end"), two=True),
    _s("t-handheld", "talk", "normal", "eye", "handheld",
       "A handheld close-up of {speaker}, the camera breathing slightly",
       ("handheld close on {speaker}", "the camera breathing slightly",
        "the camera breathing slightly", "steadying on {speaker}'s face")),
]

# ── 마지막 컷 (그 사람에게서 천천히 멀어진다) ────────────────────────
END_OUT = _s("e-rise", "end", "wide", "aerial", "rise",
             "The shot begins on a medium shot of {main}, the face clear, and rises "
             "slowly and smoothly into a high aerial view of the whole place",
             ("on a medium shot of {main}, the face clear, starting to rise",
              "rising slowly and smoothly", "rising higher over the place",
              "high above the whole place, holding"))
END_IN = _s("e-pull", "end", "normal", "high", "pull",
            "The shot begins close on {main}'s face and pulls back and up slowly "
            "until {main} sits small in the quiet room",
            ("close on {main}'s face, starting to pull back",
             "pulling back and up slowly", "still pulling back",
             "settled high and wide, holding"))

ALL = [EST_OUT, *EST_INS, *NARR, *TALK, END_OUT, END_IN]


def is_outdoor(scene):
    low = str(scene or "").lower()
    return any(re.search(rf"\b{w}", low) for w in OUTDOOR)


def is_twist(c):
    t = str(((c.get("turns") or [["", ""]])[0])[1]).strip()
    return any(t.startswith(w) for w in TWIST)


def diff(a, b):
    """두 구도의 꼬리표가 몇 개 다른가 (렌즈 · 높이 · 움직임)."""
    if not a or not b:
        return len(TAGS)
    return sum(1 for k in TAGS if a[k] != b[k])


def _talks(c):
    return any(w != "나레이션" for w, _ in (c.get("turns") or []))


def plan(cuts, pinned=None):
    """컷마다 구도 하나 — [{key, kind, lens, height, move, text, cam, special}…].

    고르는 차례: 마지막 나레이션 → 끝 구도 · 뒤집히는 나레이션 → 돌리줌 먼저 ·
    장소에 **처음** 온 나레이션 → 어디인지 보여 주는 구도 · 나머지 → 대사/나레이션 표.
    표 안에서는 ㉠ 앞 컷과 꼬리표가 둘 이상 다르고 ㉡ 덜 쓴 것을 고른다.

    pinned = {컷 차례: 구도} — **이미 산 영상**의 구도는 그대로 둔다 (다시 안 산다 · 0원).
    그 옆 컷은 고정된 이웃과도 둘 이상 다르게 고른다."""
    pinned = pinned or {}
    out, prev, used, special, seen = [], None, {}, 0, set()
    special = sum(1 for s in pinned.values() if s.get("special"))
    last = len(cuts) - 1
    for i, c in enumerate(cuts):
        if i in pinned:
            pick = pinned[i]
            seen.add(str(c.get("place") or "") or f"#{i}")
            used[pick["key"]] = used.get(pick["key"], 0) + 1
            out.append(dict(pick))
            prev = pick
            continue
        nxt = pinned.get(i + 1)
        who = list(c.get("who") or [])
        place = str(c.get("place") or "") or f"#{i}"
        outdoor = is_outdoor(c.get("scene"))
        first_visit = place not in seen
        seen.add(place)
        talks = _talks(c)
        twist = not talks and is_twist(c)
        if i == last and not talks:
            pool = [END_OUT if outdoor else END_IN]
        elif twist:
            pool = NARR
        elif first_visit and not talks:
            pool = [EST_OUT] if outdoor else EST_INS
        else:
            pool = TALK if talks else NARR
        k = (int(c.get("n") or i + 1) - 1) % len(pool)
        order = pool[k:] + pool[:k]

        def fits(s):
            if s["two"] and len(who) < 2:
                return False
            if s["special"] and special >= SPECIAL_MAX:
                return False
            if s["need"] == "twist" and not twist:
                return False
            if s["need"] == "one" and len(who) != 1:
                return False
            if s["move"] == "handheld" and not talks and \
                    "walk" not in str(c.get("scene") or "").lower():
                return False
            if s["move"] == "rack" and not talks and len(who) < 2:
                return False
            return True

        cand = [s for s in order if fits(s)] or order
        if twist and any(s["need"] == "twist" for s in cand):
            pick = next(s for s in cand if s["need"] == "twist")
        else:
            good = [s for s in cand if diff(s, prev) >= MIN_DIFF and
                    (prev is None or s["key"] != prev["key"]) and
                    (nxt is None or diff(s, nxt) >= MIN_DIFF)] or \
                   [s for s in cand if diff(s, prev) >= MIN_DIFF and
                    (prev is None or s["key"] != prev["key"])] or cand
            pick = min(good, key=lambda s: (used.get(s["key"], 0), order.index(s)))
        used[pick["key"]] = used.get(pick["key"], 0) + 1
        special += 1 if pick["special"] else 0
        out.append(dict(pick))
        prev = pick
    return out


def check(cuts, shots, reuse=()):
    """계획이 규칙을 지키는가 — 어긋난 곳 글 목록 (비면 통과).

    reuse = 앞 컷 영상을 **다시 쓰는** 컷 차례들 (drama60 같은 장면 한 번만 사기) — 같은 영상이라
            특별한 시점 수에 두 번 세지 않는다.
    ⭐ 긴 영상(2026-10-05 · S95): 두 얼굴 컷 사이에 그림 컷이 끼면(컷 번호가 1 넘게 벌어지면)
       화면에서 이웃이 아니다 — 이웃 규칙(MIN_DIFF)은 **화면에서 바로 붙는** 컷끼리만 본다.
       (그림 컷 여섯 장 너머의 얼굴 컷끼리 구도가 비슷하다고 사기를 막았다)"""
    bad = []
    for i in range(1, len(shots)):
        a, b = cuts[i - 1].get("n"), cuts[i].get("n")
        if a is not None and b is not None and int(b) - int(a) > 1:
            continue
        if diff(shots[i - 1], shots[i]) < MIN_DIFF:
            bad.append(f"컷{cuts[i].get('n')}: 앞 컷과 렌즈·높이·움직임이 "
                       f"{3 - diff(shots[i - 1], shots[i])}개나 같다")
    sp = sum(1 for i, s in enumerate(shots) if s["special"] and i not in set(reuse))
    if sp > SPECIAL_MAX:
        bad.append(f"특별한 시점이 {sp}번이다 — {SPECIAL_MAX}번까지")
    for c, s in zip(cuts, shots):
        if _talks(c) and s["move"] in ("arc", "descend", "crane", "rise", "zoom"):
            bad.append(f"컷{c.get('n')}: 대사 컷인데 크게 움직인다 ({s['key']})")
        if s["lens"] == "fisheye" and _talks(c):
            bad.append(f"컷{c.get('n')}: 대사 컷에 어안 렌즈")
    return bad
