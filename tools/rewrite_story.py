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


def shot_line(i, cast, face, other):
    """컷 자리마다 **다른 크기**로 — 두 사람 → 어깨 너머 → 얼굴.

    ⭐⭐ 2026-08-25 — SUBJECT 줄을 없앴으므로(옷은 기준 사진이 잡는다)
       **누가 화면에 있는지**를 이 줄이 진다. 이름만 적고 옷은 안 적는다.
    """
    if i == 0 and len(cast) >= 2:
        # ⚠️ "faces read clearly" 라고 쓰면 안 된다. read 는 '글자를 읽는다' 로
        #    잡혀서, 컷 안에 서류·봉투가 있으면 통째로 반려된다(두 번째 실수다).
        kind = "two-shot" if len(cast) == 2 else "group shot"
        return (f"SHOT: Medium-wide {kind} of {who_list(cast)}, static camera, everyone "
                "framed from the waist up in the middle of the frame, close enough that "
                "every face stays clear. The movement is already under way in the very "
                "first frame — nothing is still at the start.")
    if i == 1 and len(cast) >= 2:
        return (f"SHOT: Over-the-shoulder shot from behind {other}, seen from the right "
                f"of the room, with {face}'s face and upper body filling most of the "
                f"frame.")
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
            cast = says                       # 화면에 있는 사람 = 말하는 사람
            face = max(says, key=lambda w: sum(S.syl(t) for w2, t in lines if w2 == w))
            other = next((w for w in cast if w != face), face)
            n_syl = sum(S.syl(t) for _, t in lines)
            sec = S.cut_sec(n_syl)

            dia = ["DIALOGUE: [LANGUAGE: KOREAN] each person speaks one after another, "
                   "never overlapping"]
            for k, (who, txt) in enumerate(lines):
                # 감정 낱말은 그 화에 정한 셋만 — 컷 안에서 점점 깊어진다
                m = e["words"][min(int(k / max(1, len(lines)) * 3), 2)]
                dia.append(f'{S.DIA_INDENT}{who} ({m}, in Korean): "{txt}"')

            # ⚠️ SUBJECT 줄은 **안 만든다** (2026-08-25 운영자 지시).
            #    옷·얼굴은 루미나 기준 사진이 잡는다. 여기 또 적으면 싸운다.
            body = [S.head_line(sec),
                    shot_line(i, cast, face, other),
                    S.FRAME_FIX,
                    "ACTION: " + action.strip().rstrip(".") + "."
                    + (SYNC2 if len(cast) > 1 else SYNC1),
                    *dia,
                    "VOICE: " + "; ".join(story.VOICES[w] for w in says) + ".",
                    audio, SET[PLACE[place]],
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
