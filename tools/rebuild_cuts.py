#!/usr/bin/env python3
"""이미 써 둔 대본을 **10초 × 3컷 + 화마다 감정 하나** 로 다시 짠다. (0원)

왜 (2026-08-24 운영자)
    "지금 에피소드에 컷이 다섯 개라고 하면 그 컷별로 연결된다는 느낌이 안 들어.
     배경이 계속 바뀌어 버리니깐 연결이 안 되고, 감정선도 한 에피소드에서
     너무 많이 바뀌어. … 영상을 한 번에 십 초씩, 세 컷으로 만드는 건 어때?"

무엇을 하나 — **대사는 한 글자도 안 버린다.**
    ① 한 화의 대사를 차례대로 쭉 편다
    ② 같은 장소끼리 묶는다 (장소가 바뀌면 컷도 갈린다)
    ③ 음절이 고르게 갈리도록 3덩어리(장소가 여럿이면 4)로 나눈다
    ④ 덩어리마다 컷 하나를 새로 쓴다 — 길이는 음절 수로 계산(6~10초)
    ⑤ 감정 낱말은 **그 화에 정해 둔 세 개**만 쓴다 (한 화 = 한 감정선)
    ⑥ 첫 컷만 둘이 나란히, 나머지는 어깨 너머로 한 명씩 번갈아

쓰는 법 (혼자 도는 프로그램이 아니라 사람이 한 번 돌리는 도구다)
    python3 tools/rebuild_cuts.py
"""
import itertools
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import series as S                                           # noqa: E402

P = ROOT / "data" / "series" / "S001.json"

# ⭐ 화마다 감정 하나 — 세 낱말은 그 감정이 **깊어지는 순서**다.
#    예전엔 컷마다 다른 낱말을 40가지 넘게 써서 한 화 안에서 감정이 튀었다.
MOOD = {
    1: ("믿기지 않음", ["numb", "shaken", "breaking"]),
    2: ("억눌린 분노", ["tight", "hard", "furious"]),
    3: ("차가운 계산", ["cool", "clipped", "icy"]),
    4: ("들뜬 뻔뻔함", ["airy", "smug", "brazen"]),
    5: ("무너짐", ["stunned", "trembling", "wailing"]),
    6: ("치미는 모욕", ["cold", "stung", "seething"]),
    7: ("절박함", ["worn", "pleading", "desperate"]),
    8: ("맞부딪힘", ["level", "sharp", "blazing"]),
    9: ("기막힘", ["flat", "incredulous", "outraged"]),
    10: ("벼른 결심", ["quiet", "firm", "unyielding"]),
    11: ("비웃음과 오기", ["mocking", "stung", "defiant"]),
    12: ("팽팽함", ["measured", "pressing", "heated"]),
    13: ("무너지는 거짓말", ["smooth", "faltering", "cornered"]),
    14: ("뻗대기", ["assured", "insistent", "shrill"]),
    15: ("조롱과 버팀", ["sneering", "steady", "immovable"]),
    16: ("담담한 승리", ["low", "steady", "released"]),
}
WEARS = {
    "Wife": "the wife wearing a dusty-blue wool cardigan over a white round-neck top",
    "Husband": ("the husband wearing an olive-green cotton work jacket over a grey "
                "crewneck, with dark charcoal trousers"),
    "Other woman": ("the other woman wearing a deep wine-red sleeveless dress with a "
                    "thin gold necklace"),
}
VOICES = {
    "Wife": ("Wife — a warm mid-range woman's voice in her fifties, native Korean "
             "speaker, weary and a little breathy, trails off at the end of a sentence"),
    "Husband": ("Husband — a low, slightly gravelly man's voice in his fifties, native "
                "Korean speaker, clipped and impatient, drops in volume at the end"),
    "Other woman": ("Other woman — a clear woman's voice in her forties, native Korean "
                    "speaker, cool and unhurried, with a small lilt at the end"),
}
SYNC2 = (" Both people keep their lips moving in exact sync with the Korean lines "
         "they say.")
SYNC1 = (" The person keeps their lips moving in exact sync with the Korean lines "
         "they say.")


def gl(c, k):
    return next((l for l in c["prompt"].split("\n") if l.startswith(k)), "")


def cast_of(c):
    """그 컷 화면에 **있는** 사람들 (말을 안 해도 서 있는 사람 포함).

    ⚠️ 말한 사람만으로 SUBJECT 를 다시 쓰면 **말 없이 서 있는 사람이 사라진다.**
       1화 1컷에서 아내가 "이 여자 누구야" 라고 하는데 정작 그 여자가 화면에
       없어지는 사고가 났다. 원래 컷의 SUBJECT 를 그대로 물려받는다.
    """
    sub = gl(c, "SUBJECT:")
    return [w for w in WEARS if WEARS[w] in sub]


def syl(t):
    return len(re.findall(r"[가-힣]", str(t or "")))


def split_even(items, k):
    """음절이 고르게 갈리도록 k 덩어리로 자른다 (차례는 절대 안 바꾼다).

    ⚠️ 처음엔 '누적 음절이 1/3 지점에 가장 가까운 자리' 로 잘랐다.
       그렇게 하면 앞에서 한 번 어긋난 것을 뒤가 뒤집어쓴다 —
       5화가 58 / 16 / 61 음절로 갈려 가운데 컷은 텅 비고 끝 컷은 넘쳤다.
       **가장 큰 덩어리가 가장 작아지는 자리**를 다 따져서 고른다
       (같으면 셋이 고른 쪽). 대사가 15줄 안쪽이라 다 따져도 순식간이다.
    """
    if k <= 1 or len(items) <= 1:
        return [items]
    k = min(k, len(items))
    sy = [syl(f["txt"]) for f in items]
    n, mean = len(items), sum(sy) / k
    best, arg = None, None
    for spots in itertools.combinations(range(1, n), k - 1):
        b = [0, *spots, n]
        sums = [sum(sy[b[i]:b[i + 1]]) for i in range(k)]
        key = (max(sums), sum((s - mean) ** 2 for s in sums))
        if best is None or key < best:
            best, arg = key, b
    return [items[arg[i]:arg[i + 1]] for i in range(k)]


def main():
    doc = json.loads(P.read_text(encoding="utf-8"))
    audio = gl(doc["episodes"][0]["cuts"][0], "AUDIO:")
    rank = S.cam_rank(doc)
    report = []

    for e in doc["episodes"]:
        no = int(e["no"])
        key, words = MOOD[no]

        # ① 대사를 쭉 편다 (장소·움직임을 달고)
        flat = []
        for c in e["cuts"]:
            place, st = S.cam_place(c), gl(c, "SETTING:")
            act = re.sub(r"\s*(Both people|The person) keep.*$", "", gl(c, "ACTION:"))
            cast = cast_of(c)
            for who, txt in S.dia_turns(c["prompt"]):
                flat.append({"who": who, "txt": txt, "place": place,
                             "set": st, "act": act, "cast": cast})

        # ② 같은 장소끼리 묶는다
        runs = []
        for f in flat:
            if runs and runs[-1][0]["place"] == f["place"]:
                runs[-1].append(f)
            else:
                runs.append([f])

        # ③ 음절 비례로 컷 수를 장소에 나눠 준다
        want = max(S.CUTS, len(runs))
        tot = sum(syl(f["txt"]) for f in flat)
        share, left = [], want
        for i, r in enumerate(runs):
            k = round(want * sum(syl(f["txt"]) for f in r) / max(1, tot))
            k = max(1, min(k, left - (len(runs) - 1 - i)))
            share.append(k)
            left -= k
        share[-1] += left
        groups = []
        for r, k in zip(runs, share):
            groups += split_even(r, k)

        # ⭐ 같은 사람이 잇달아 말하면 **한 마디로 합친다** — 나눠 두면 화면에
        #    같은 이름표가 두 번 뜨고 말이 뚝뚝 끊긴다.
        #    ⚠️ 합치는 것은 **덩어리를 나눈 뒤**다. 먼저 합치면 40음절짜리
        #       덩어리가 생겨 자를 자리가 없어진다(5화가 16음절 컷이 된 까닭).
        packed = []
        for g in groups:
            one = []
            for f in g:
                if one and one[-1]["who"] == f["who"]:
                    one[-1]["txt"] = one[-1]["txt"].rstrip() + " " + f["txt"].lstrip()
                else:
                    one.append(dict(f))
            packed.append(one)
        groups = packed

        # ④ 덩어리마다 컷 하나
        cuts, n_all, seen = [], sum(len(g) for g in groups), 0
        for i, g in enumerate(groups):
            says = sorted({f["who"] for f in g}, key=lambda w: rank.get(w, 99))
            # 화면에 있는 사람 = 말한 사람 + 원래 컷에 서 있던 사람
            who = sorted({w for f in g for w in f["cast"]} | set(says),
                         key=lambda w: rank.get(w, 99))
            face = max(says, key=lambda w: sum(syl(f["txt"]) for f in g
                                               if f["who"] == w))
            other = next((w for w in who if w != face), face)
            if i == 0 and len(who) >= 2:
                shot = ("SHOT: Medium-wide two-shot, static camera, both people "
                        "framed from the waist up in the middle of the frame, close "
                        "enough that both faces read clearly. The movement is already "
                        "under way in the very first frame — nothing is still at the "
                        "start.")
            elif len(who) >= 2:
                side = "left" if i % 2 else "right"
                shot = (f"SHOT: Over-the-shoulder shot from behind {other}, seen from "
                        f"the {side} of the room, with {face}'s face and upper body "
                        f"filling most of the frame.")
            else:
                shot = (f"SHOT: Medium close-up, static camera, {face} framed from the "
                        f"chest up, held for the whole take.")
            # ⚠️ 한 줄에 facing 을 두 번 적으면 안 된다 (검사가 잡는다).
            #    셋이 나오면 맨 앞 사람이 둘째를 마주 보고, 나머지는 `;` 로 잇는다.
            if len(who) == 1:
                subj = "SUBJECT: " + WEARS[who[0]] + "."
            else:
                subj = ("SUBJECT: " + WEARS[who[0]] + " facing " + WEARS[who[1]]
                        + "".join("; " + WEARS[w] for w in who[2:]) + ".")
            dia = ["DIALOGUE: [LANGUAGE: KOREAN] each person speaks one after "
                   "another, never overlapping"]
            for f in g:
                m = words[min(int(seen / max(1, n_all) * 3), 2)]
                dia.append(f'{S.DIA_INDENT}{f["who"]} ({m}, in Korean): "{f["txt"]}"')
                seen += 1
            sec = S.cut_sec(sum(syl(f["txt"]) for f in g))
            body = [S.head_line(sec), shot, S.FRAME_FIX, subj,
                    "ACTION: " + g[0]["act"][8:].strip()
                    + (SYNC2 if len(who) > 1 else SYNC1),
                    *dia,
                    "VOICE: " + "; ".join(VOICES[w] for w in says) + ".",
                    audio, g[0]["set"], S.COLOR_FIX, S.STYLE_FIX, S.AVOID_FIX]
            cuts.append({
                "n": i + 1, "sec": sec,
                "role": S.ROLES[min(i, len(S.ROLES) - 1)],
                "subtitle": " / ".join(f["txt"] for f in g),
                "prompt": "\n".join(body),
            })
        e["cuts"] = cuts
        e["mood"] = key
        report.append((no, key, [sum(syl(f["txt"]) for f in g) for g in groups],
                       [c["sec"] for c in cuts]))

    S.fix_continuity(doc)
    S.fix_camera(doc)
    P.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                 encoding="utf-8")
    for no, key, sy, secs in report:
        print("%2d화 [%-8s] 컷 %d개 · 음절 %s · 초 %s (합 %d초)"
              % (no, key, len(sy), sy, secs, sum(secs)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
