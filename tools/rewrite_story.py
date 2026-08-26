#!/usr/bin/env python3
"""이야기 데이터(data/series/S001_story.py) → 대본(S001.json). (0원 · 인터넷 0회)

왜 (2026-08-25 운영자)
    "대본 읽어봤는데 스토리가 전혀 이해가 안돼. 씬 앞뒤로 개연성이 없고
     전체적인 스토리가 잘 연결이 안돼."

    참고로 주신 DramaBox(세로 숏드라마) 형식을 찾아 우리 대본과 대조해 보니
    원인이 분명했다 — **16화에 사건이 하나도 없었다.**
      · 숏드라마 회차 구조: 훅 → 충돌 → 폭로 → **질문으로 끊기**
        ("cut on the question, not the answer")
      · 우리 대본: 16화 전부 말싸움이고, 16화 전부 '선언(답)' 으로 끝났다
      · 그래서 "다음 편을 볼 이유" 도, "이해할 이야기" 도 없었다

무엇을 하나
    ① 화마다 **폭로 하나**를 배정한다 (16화 = 16개 사건)
    ② 마지막 대사를 **질문**으로 끊는다 (완결하는 16화만 예외)
    ③ 사실(금액·날짜)을 **대사 안에 무기로** 넣는다 (설명체 금지)
    ④ 아내가 없는 화(3·4화)는 시청자만 먼저 아는 화로 표시한다

쓰는 법 — 이야기를 고칠 때는 data/series/S001_story.py 를 고치고 이걸 돌린다
    python3 tools/rewrite_story.py
"""
import importlib.util
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import charsheet as CS                                       # noqa: E402
import series as S                                           # noqa: E402

OUT = ROOT / "data" / "series" / "S001.json"
SRC = ROOT / "data" / "series" / "S001_story.py"

SYNC2 = (" Both people keep their lips moving in exact sync with the Korean lines "
         "they say.")
SYNC1 = (" The person keeps their lips moving in exact sync with the Korean lines "
         "they say.")


def load(path):
    spec = importlib.util.spec_from_file_location("story", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def settings(doc):
    """장소 앞머리 낱말 → 이미 써 둔 SETTING 줄.

    ⭐ 장소 묘사(왼쪽·가운데·오른쪽에 무엇이 있는지)는 이미 공들여 써 둔 것이
       있다. 그대로 물려받는다 — 다시 쓰면 좌우가 또 흔들린다.
    """
    out = {}
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
            st = next((l for l in c["prompt"].split("\n")
                       if l.startswith("SETTING:")), "")
            out.setdefault(S.cam_place(c).split(",")[0].strip(), st)
    return out


# 이야기 데이터의 짧은 장소 이름 → 대본 SETTING 의 장소 이름
PLACE = {
    "현관": "just inside the apartment entrance",
    "거실": "korean apartment living room",
    "법원복도": "court hallway",
    "카페": "upscale cafe",
    "새아파트": "modern apartment living room",
    "사무실": "office room",
    "병원복도밤": "hospital hallway",
    "장례식장": "funeral hall reception",
    "은행앞": "street outside a bank",
    "병원복도": "hospital corridor",
    "보험사앞": "outside an insurance company",
    "법무사앞": "street outside a law firm",
    "법원앞": "outside the courthouse",
    "법정": "courtroom interior",
    # ⭐ 2026-08-25 전면 재설계로 새로 생긴 장소 셋.
    #    옛 대본은 은행 앞·보험사 앞·법무사 앞처럼 **그 여자가 있을 이유가
    #    없는 길거리**에서 자꾸 마주쳤다. 이제는 아내가 혼자 가는 곳
    #    (은행 창구·변호사 사무실)과 집 안(부엌)이 따로 있다.
    "부엌": "korean apartment kitchen",
    "은행창구": "bank branch interior",
    "변호사사무실": "law office room",
}

# 옛 대본에 없던 장소라 물려받을 SETTING 이 없다 — 같은 꼴(왼쪽·가운데·
# 오른쪽)로 새로 쓴다. ⚠️ 글자가 나올 물건(paper·document·sign…)은 안 부른다.
NEW_SET = {
    "korean apartment kitchen":
        "SETTING: Korean apartment kitchen, evening, warm overhead light — a tall "
        "fridge and a narrow pantry shelf on the left, a small square dining table "
        "with two stools in the middle, a sink counter with a kettle and a dish "
        "rack on the right.",
    "bank branch interior":
        "SETTING: Bank branch interior, daytime, even fluorescent lighting — a row "
        "of waiting chairs along the left, a low teller counter with a small "
        "partition in the middle, a wall of plain steel lockers on the right.",
    "law office room":
        "SETTING: Law office room, daytime, soft desk lamp light — a tall shelf of "
        "dark binders along the left wall, a broad wooden desk with a closed laptop "
        "and a plain mug in the middle, a window with half-drawn blinds and two "
        "visitor chairs on the right.",
}


def who_list(cast):
    """Wife and Husband · Wife, Husband and Other woman — 영어로 이어 붙인다."""
    if len(cast) <= 1:
        return cast[0] if cast else ""
    return ", ".join(cast[:-1]) + " and " + cast[-1]


# ⭐⭐⭐ 2026-08-25 운영자: "너무 두 사람을 다 보여줄 필요는 없고, 필요할 때는
#    한 명만 줌인해서 그 한 명만 이야기하게 하는 것도 좋을 거 같아. 지금 보면
#    두 사람이 나와 있다 보니 씬이 너무 단조로워."
#    세어 보니 **48컷 중 47컷에 두 사람**이 나오고, 16화가 **전부 같은 순서**
#    (두 사람 → 어깨너머 → 클로즈업)였다. 한 번도 안 바뀌었다.
#    세로 드라마 작법도 같은 말을 한다 — "대사는 한 명씩 번갈아 잡고,
#    주고받는 느낌은 컷 전환이 지게 하라."
#    → ① 말하는 사람이 **한 명뿐인 컷은 무조건 클로즈업** (얼굴이 3배 커진다)
#      ② 샷 순서를 화마다 다르게 (이야기 파일의 `shots` 로 정한다)
LADDER = ["two", "ots", "close"]        # 안 정하면 쓰는 기본 순서


def shot_line(i, cast, face, other, ladder=None, says=None):
    """컷 자리마다 **다른 크기**로.

    ⭐⭐ SUBJECT 줄을 없앴으므로(옷은 기준 사진이 잡는다) **누가 화면에
       있는지**를 이 줄이 진다. 이름만 적고 옷은 안 적는다.
    """
    kinds = list(ladder or LADDER)
    want = kinds[i] if i < len(kinds) else kinds[-1]
    # 혼자 말하는 컷은 **언제나 얼굴**이다.
    # ⚠️ 2026-08-25 — 예전엔 `cast`(화면에 서 있는 사람) 로 셌다. 말은 안 해도
    #    옆에 서 있는 사람(extras) 이 있으면 두 명으로 세어져, 혼자 말하는
    #    컷에 어깨너머 샷이 붙었다(9화 1컷). **말한 사람 수**로 센다 —
    #    입 모양 지시(SYNC1)·AUDIO_ONE 도 이미 그 기준을 쓴다.
    if len(says if says is not None else cast) < 2:
        want = "close"
    if want == "close":
        return (f"SHOT: Close-up on {face}, static camera, framed from the "
                f"shoulders up so the whole face fills the frame, held for the "
                f"whole take.")
    if want == "ots":
        return (f"SHOT: Over-the-shoulder shot from behind {other}, seen from the "
                f"right of the room, with {face}'s face and upper body filling "
                f"most of the frame.")
    if True:
        # ⚠️ "faces read clearly" 라고 쓰면 안 된다. read 는 '글자를 읽는다' 로
        #    잡혀서, 컷 안에 서류·봉투가 있으면 통째로 반려된다(두 번째 실수다).
        kind = "two-shot" if len(cast) == 2 else "group shot"
        return (f"SHOT: Medium-wide {kind} of {who_list(cast)}, static camera, everyone "
                "framed from the waist up in the middle of the frame, close enough that "
                "every face stays clear. The movement is already under way in the very "
                "first frame — nothing is still at the start.")
    return (f"SHOT: Close-up on {face}, static camera, framed from the shoulders up so "
            f"the whole face fills the frame, held for the whole take.")


def main():
    story = load(SRC)
    old = json.loads(OUT.read_text(encoding="utf-8"))
    SET = {**settings(old), **NEW_SET}
    # ⚠️ 예전엔 세 사람을 손으로 박아 뒀다. 딸·변호사가 들어오자 그 자리에서
    #    KeyError 로 죽는다. 이야기 파일의 ORDER 를 그대로 쓴다.
    rank = {w: i for i, w in enumerate(story.ORDER)}
    audio = next((l for l in old["episodes"][0]["cuts"][0]["prompt"].split("\n")
                  if l.startswith("AUDIO:")), "")

    eps = []
    for e in story.EPS:
        cuts = []
        for i, (place, action, lines) in enumerate(e["cuts"]):
            says = sorted({w for w, _ in lines}, key=lambda w: rank[w])
            # ⭐ 말은 안 해도 화면에 서 있는 사람 (이야기 파일의 extras)
            extra = [w for w in (e.get("extras") or {}).get(i + 1, [])
                     if w not in says]
            cast = sorted(set(says) | set(extra), key=lambda w: rank[w])
            face = max(says, key=lambda w: sum(S.syl(t) for w2, t in lines if w2 == w))
            other = next((w for w in cast if w != face), face)
            ladder = e.get("shots")
            n_syl = sum(S.syl(t) for _, t in lines)
            sec = S.cut_sec(n_syl)

            # ⚠️ 2026-08-25 — "never overlapping" 처럼 **부정문으로 적지 않는다.**
            #    루미나 안전 검사기는 부정을 못 알아듣고 낱말만 본다.
            dia = ["DIALOGUE: [LANGUAGE: KOREAN] each person speaks in turn, one "
                   "voice at a time"]
            for k, (who, txt) in enumerate(lines):
                # 감정 낱말은 그 화에 정한 셋만 — 컷 안에서 점점 깊어진다
                m = e["words"][min(int(k / max(1, len(lines)) * 3), 2)]
                dia.append(f'{S.DIA_INDENT}{who} ({m}, in Korean): "{txt}"')

            # ⚠️ SUBJECT 줄은 **안 만든다** (2026-08-25 운영자 지시).
            #    옷·얼굴은 루미나 기준 사진이 잡는다. 여기 또 적으면 싸운다.
            body = [S.head_line(sec),
                    shot_line(i, cast, face, other, ladder, says),
                    S.FRAME_FIX,
                    # ⚠️ 입 모양 지시는 **말한 사람 수**를 따른다. 화면에
                    #    있는 사람 수로 세면, 혼자 말하는 컷에 "둘 다 입을
                    #    움직여라" 가 붙는다 (2026-08-25 실제로 그랬다).
                    "ACTION: " + action.strip().rstrip(".") + "."
                    + (SYNC2 if len(says) > 1 else SYNC1),
                    *dia,
                    "VOICE: " + "; ".join(story.VOICES[w] for w in says) + ".",
                    # ⚠️ AUDIO 도 **말한 사람 수**를 따라간다. 1화 1컷에서
                    #    통째로 복사해 오면 혼자 말하는 컷에 "the two people"
                    #    이 붙는다 (2026-08-25 실제로 그랬다).
                    # ⚠️ 2026-08-25 — 예전엔 여기서 문장을 **손으로 고쳐 썼다.**
                    #    검사기는 그 문장을 모르니 "AUDIO 줄이 없다" 로 걸렸고,
                    #    저장된 대본을 검사하는 검사가 없어서 깃허브는 초록불
                    #    이었다. 이제 규격 파일의 상수를 그대로 쓴다.
                    (audio if len(says) > 1 else S.AUDIO_ONE),
                    SET[PLACE[place]],
                    S.COLOR_FIX, S.STYLE_FIX, S.AVOID_FIX]
            cuts.append({
                "n": i + 1, "sec": sec,
                "role": S.ROLES[min(i, len(S.ROLES) - 1)],
                "subtitle": " / ".join(t for _, t in lines),
                "prompt": "\n".join(body),
            })
        eps.append({
            "no": e["no"], "title": e["title"], "recap": e.get("recap", ""),
            "hook": e["hook"], "yt_title": e["yt_title"],
            "mood": e["mood"], "when": e["when"],
            "reveal": e["reveal"], "must": e["must"],
            "irony": bool(e.get("irony")),
            # ⭐⭐ 씬 간 연결의 뼈대 — 이 화가 남긴 것(leaves)이 다음 화가
            #    시작되는 까닭(because)과 **글자 그대로 같아야** 한다.
            #    tools/story_check.py 가 이것을 검사한다.
            "because": e.get("because", ""),
            "leaves": e.get("leaves", ""),
            "quiet": bool(e.get("quiet")),
            "cuts": cuts,
        })

    doc = dict(old)
    # ⭐ 딸·변호사를 더한다. 이미 있으면 그대로 둔다(두 번 돌려도 안 늘어난다).
    chars = list(old.get("characters") or [])
    # ⚠️ 2026-08-25 — 처음엔 "이미 있으면 건너뛴다" 로 썼다. 그러자 **앞선
    #    실행이 남긴 낡은 기준 그림 프롬프트가 영영 안 고쳐졌다** (하지 말 것
    #    줄이 빠진 채로 남았다). 새 인물 자리는 **늘 다시 짓는다** — 문구를
    #    고치고 다시 돌리면 그대로 반영돼야 한다.
    names = {c.get("name") for c in story.NEW_CHARS}
    chars = [c for c in chars if c.get("name") not in names]
    for c in story.NEW_CHARS:
        c = dict(c)
        # ⭐ 기준 그림 프롬프트·설명은 **손으로 안 적는다.** charsheet 가
        #    배경·자세·화면잡기·빛·하지 말 것까지 한 벌로 지어 준다.
        #    (베껴 두면 문구를 고칠 때 사람마다 다른 그림체가 된다)
        c["flow_sheet"], c["flow_desc"] = CS.build(c)
        chars.append(c)
    doc["characters"] = chars
    doc["title"] = "바람난 남편이 빼돌린 32억"
    doc["episodes"] = eps
    doc["ledger"] = story.LEDGER
    S.fix_continuity(doc)
    S.fix_camera(doc)
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    for e in eps:
        print("%2d화 %-14s %s · %s · 컷 %s초 (합 %d초)"
              % (e["no"], e["title"], e["when"], e["mood"],
                 [c["sec"] for c in e["cuts"]], sum(c["sec"] for c in e["cuts"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
