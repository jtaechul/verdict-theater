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


def shot_line(i, cast, face, other, ladder=None):
    """컷 자리마다 **다른 크기**로.

    ⭐⭐ SUBJECT 줄을 없앴으므로(옷은 기준 사진이 잡는다) **누가 화면에
       있는지**를 이 줄이 진다. 이름만 적고 옷은 안 적는다.
    """
    kinds = list(ladder or LADDER)
    want = kinds[i] if i < len(kinds) else kinds[-1]
    # 혼자 말하는 컷은 **언제나 얼굴**이다 — 두 사람 샷을 쓸 수가 없다
    if len(cast) < 2:
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
    SET = settings(old)
    rank = {"Wife": 0, "Husband": 1, "Other woman": 2}
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
                    shot_line(i, cast, face, other, ladder),
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
                    (audio if len(says) > 1 else
                     audio.replace("the two people in the shot say the lines "
                                   "themselves",
                                   "the person in the shot says the lines "
                                   "themselves")
                          .replace("each person speaking one after another so "
                                   "every word stays clear",
                                   "every word stays clear")),
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
            "cuts": cuts,
        })

    doc = dict(old)
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
