#!/usr/bin/env python3
"""⭐ 시리즈 대본 검사기가 진짜로 잡는지 본다. 0원 · 인터넷 0회.

    python3 tools/series_test.py

왜 (2026-08-18)
    검사기를 만들어 놓고 그 검사기가 맞는지 안 재면 같은 실수다. 규격을 어긴
    가짜 대본을 넣어 **정확히 그것만** 잡아내는지 확인한다.
    특히 운영자가 못 박은 세 가지를 지키는지 본다 —
    ① 매 화 첫 컷은 후킹 ② 영상에 글자 금지 ③ 6줄 규격.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import series as S                                          # noqa: E402

FAIL = []


def ck(label, cond, extra=""):
    print(("   ✅ " if cond else "   ❌ ") + label + (f"  ({extra})" if extra else ""))
    if not cond:
        FAIL.append(label)


TALK = ('시동생 (cold): "이 집, 오늘 안에 비워 주세요." / '
        '며느리 (trembling): "그이 장례가 어제였어요. 지금 그 말이 나와요?"')


SOLO = ('시동생 says in Korean, calm: "이 집, 오늘 안에 비워 주세요. 더 드릴 말씀도 기다려 드릴 생각도 없습니다."')


def good_prompt(dialogue=SOLO):
    # ⭐ FRAMING 도 시스템이 붙이는 고정 줄이다 (2026-08-24 · 코드에서 가져온다)
    return (S.HEAD_FIX + "\n"
            "SHOT: Medium two-shot, static camera.\n"
            + S.FRAME_FIX + "\n"
            "SUBJECT: 시동생 in a black suit facing 며느리 in black mourning hanbok.\n"
            "ACTION: 시동생 holds out a closed folder toward 며느리.\n"
            f"DIALOGUE: {dialogue}\n"
            + S.AUDIO_FIX + "\n"
            + "SETTING: Korean funeral hall reception room, evening, dim light.\n"
            # 아래 두 줄도 시스템이 붙이는 고정 줄이다 (코드에서 가져온다)
            + S.CONT_FIRST + "\n" + S.COLOR_FIX + "\n"
            + S.STYLE_FIX + "\n" + S.AVOID_FIX)


def good_doc():
    eps = []
    for i in range(1, S.EPISODES + 1):
        eps.append({
            "no": i, "title": f"{i}화", "recap": "" if i == 1 else "지난 이야기 한 줄",
            # 후킹·유튜브 제목은 모델이 반드시 내야 하는 칸이다 (2026-08-20)
            "hook": f"{i}화에서 통장이 비어 있었다",
            "yt_title": f"{i}화 — 남편이 통장을 비우고 집을 나갔습니다",
            "cuts": [{"n": n, "role": S.ROLES[n - 1], "subtitle": '"짧은 자막"',
                      # 3·4컷은 주고받는다 — 혼잣말만 이으면 이야기가 안 굴러간다
                      "prompt": good_prompt(TALK) if n in (3, 4)
                      else (good_prompt() if n == 1 else good_prompt("None."))}
                     for n in range(1, S.CUTS + 1)],
        })
    return {"title": "시험", "case_id": "1", "characters": [{"name": "며느리"}],
            "episodes": eps}


print("⭐ 시리즈 대본 검사기 시험\n")
print("① 규격에 맞는 대본은 그냥 통과하는가")
ck("문제 0건", S.check(good_doc()) == [], f"{len(S.check(good_doc()))}건")

print("\n② 운영자가 못 박은 것을 어기면 잡는가")
d = good_doc()
d["episodes"][3]["cuts"][0]["role"] = "상황"
ck("첫 컷이 후킹이 아니면 잡는다", any("후킹" in b for b in S.check(d)))

d = good_doc()
d["episodes"][2]["cuts"][1]["prompt"] = good_prompt().replace(
    "a closed folder", "a newspaper")
ck("그 자체가 글자인 것(newspaper)은 무조건 잡는다",
   any("글자가 나올 물건" in b for b in S.check(d)))

d = good_doc()
d["episodes"][2]["cuts"][1]["prompt"] = good_prompt().replace(
    "holds out a closed folder toward 며느리", "reads a letter aloud")
ck("종이라도 '읽는' 장면이면 잡는다", any("글자가 나올 물건" in b for b in S.check(d)))

# ⚠️ 두 번 연속으로 이것 때문에 멀쩡한 대본을 잃었다 (phone → paper).
#    건네주기만 하는 것은 **반드시 통과해야 한다.**
for w in ["paper", "phone", "document", "envelope", "book"]:
    d = good_doc()
    d["episodes"][2]["cuts"][1]["prompt"] = good_prompt().replace(
        "a closed folder", f"a closed {w}")
    ck(f"그냥 건네는 {w} 은 통과시킨다", S.check(d) == [], str(S.check(d))[:60])

d = good_doc()
d["episodes"][0]["cuts"][2]["prompt"] = "SHOT: close-up.\nACTION: nothing.\n"
ck("6줄 규격이 아니면 잡는다", any("6줄 규격" in b for b in S.check(d)))

d = good_doc()
d["episodes"][1]["cuts"][0]["prompt"] = good_prompt().replace(
    S.STYLE_FIX, "STYLE: cinematic, moody, film grain.")
ck("STYLE 고정 문구가 바뀌면 잡는다", any("STYLE" in b for b in S.check(d)))

print("\n③ 길이·개수 규칙")
d = good_doc()
d["episodes"] = d["episodes"][:12]
ck("16화가 아니면 잡는다", any("화 수가" in b for b in S.check(d)))

d = good_doc()
d["episodes"][5]["cuts"] = d["episodes"][5]["cuts"][:3]
ck("5컷이 아니면 잡는다", any("컷이 3개" in b for b in S.check(d)))

d = good_doc()
d["episodes"][0]["cuts"][0]["prompt"] = good_prompt(
    '시동생 says in Korean: "이 집은 이제 전부 저희 것이니 오늘 안에 짐을 싸서 지금 당장 나가 주셔야 하겠습니다. 더는 드릴 말씀이 없습니다."')
ck(f"대사가 {S.DIA_SYL_MAX}음절을 넘으면 잡는다", any("음절이다" in b for b in S.check(d)))

# ⚠️ 한 글자 차이로 멀쩡한 대사 둘을 막았다. 실제로 나왔던 그 대사를 넣어 둔다.
d = good_doc()
d["episodes"][0]["cuts"][0]["prompt"] = good_prompt(
    '본처 says in Korean, firm: "몰래 빼돌린 건 몇 년이 지나도 안 없어져. '
    '끝까지 다 받아낼 거니까 기다려."')
ck("실제 드라마 대사 길이는 통과시킨다", S.check(d) == [], str(S.check(d))[:70])

d = good_doc()
d["episodes"][4]["recap"] = ""
ck("2화부터 지난 줄거리가 비면 잡는다", any("지난 줄거리" in b for b in S.check(d)))

d = good_doc()
d["episodes"][7]["cuts"][4]["prompt"] = good_prompt("None.").replace(
    "SUBJECT: 시동생 in a black suit facing 며느리 in black mourning hanbok.",
    "SUBJECT: the same woman in a black coat.")
ck("SUBJECT 에 이름 없이 가리키면 잡는다", any("지시대명사" in b for b in S.check(d)))

# ⚠️ 우리 예시 대본이 바로 이 검사에 걸렸다. 앞에 이름이 있으면 통과해야 한다.
d = good_doc()
d["episodes"][7]["cuts"][4]["prompt"] = good_prompt("None.").replace(
    "toward 며느리.", "toward 며느리; she does not take it.")
ck("앞에 이름이 있는 she 는 통과시킨다", S.check(d) == [], str(S.check(d))[:60])

print("\n⑤ 우리가 모델에게 준 예시가 우리 검사를 통과하는가")
import json
import re
raw = (ROOT / "prompts" / "series_gen.md").read_text(encoding="utf-8")
ex = json.loads('"' + raw.split('"prompt": "')[1].split('"\n')[0] + '"')
d = good_doc()
for n in range(S.CUTS):
    d["episodes"][0]["cuts"][n]["prompt"] = ex
# ⚠️ VOICE·AUDIO 줄은 **우리가 붙이는 것**이라 예시에는 없다 (프롬프트에도
#    "우리가 붙인다" 라고 적어 두었다). 실제 길과 똑같이 고쳐 준 뒤에 잰다.
ck("프롬프트 파일의 예시 컷이 통과한다", S.check(S.normalize(d)) == [],
   str(S.check(S.normalize(d)))[:80])

# 고정 문구를 아예 빠뜨려도 우리가 채워 넣는다 (버리지 않는다)
d = good_doc()
d["episodes"][3]["cuts"][1]["prompt"] = "\n".join(
    l for l in good_prompt("None.").split("\n")
    if not l.startswith(("STYLE:", "Avoid:")))
ck("STYLE·Avoid 줄이 없으면 우리가 채운다", S.check(S.normalize(d)) == [],
   str(S.check(S.normalize(d)))[:60])

# 대사 없는 컷에서 DIALOGUE 줄을 통째로 빠뜨리는 일이 있다 — 빈칸만 채운다
d = good_doc()
d["episodes"][5]["cuts"][4]["prompt"] = "\n".join(
    l for l in good_prompt("None.").split("\n") if not l.startswith("DIALOGUE:"))
ck("DIALOGUE 줄이 없으면 우리가 채운다", S.check(S.normalize(d)) == [],
   str(S.check(S.normalize(d)))[:60])

# 줄 순서만 바뀐 것으로 16화를 다시 살 수는 없다
d = good_doc()
d["episodes"][6]["cuts"][0]["prompt"] = good_prompt("None.").replace(
    S.STYLE_FIX + "\nAvoid:", "Avoid:").rstrip() + "\n" + S.STYLE_FIX
ck("Avoid 가 맨 끝이 아니면 우리가 옮긴다", S.check(S.normalize(d)) == [],
   str(S.check(S.normalize(d)))[:60])

print("\n⑩ 컷마다 옷이 바뀌지 않게 맞추는가 (2026-08-20 · 실제 영상에서 확인)")
d = good_doc()
d["characters"] = [{"name": "며느리", "outfit": "a black mourning hanbok"},
                   {"name": "시동생", "outfit": "a charcoal suit"}]
d["episodes"][0]["cuts"][1]["prompt"] = good_prompt("None.").replace(
    "SUBJECT: 시동생 in a black suit facing 며느리 in black mourning hanbok.",
    "SUBJECT: 며느리 in a beige cardigan.")
S.fix_outfits(d)
subj = next(l for l in d["episodes"][0]["cuts"][1]["prompt"].split("\n")
            if l.startswith("SUBJECT:"))
ck("옷차림이 인물표대로 갈아 끼워진다", "a black mourning hanbok" in subj, subj[:64])
ck("두 사람이 나오는 줄도 각자 옷으로 바뀐다",
   "a charcoal suit" in d["episodes"][0]["cuts"][0]["prompt"]
   and "a black mourning hanbok" in d["episodes"][0]["cuts"][0]["prompt"])
d2 = good_doc()          # outfit 이 없는 옛 대본은 건드리지 않는다
before = d2["episodes"][0]["cuts"][0]["prompt"]
S.fix_outfits(d2)
ck("옷차림을 안 정한 옛 대본은 그대로 둔다",
   d2["episodes"][0]["cuts"][0]["prompt"] == before)

print("\n⑪ 첫 영상에서 본 것들이 프롬프트·검사에 실제로 들어갔는가")
pr = (ROOT / "prompts" / "series_gen.md").read_text(encoding="utf-8")
for k, why in [("face_tag", "얼굴이 컷마다 다른 배우로 나왔다"),
               ("outfit", "옷 색이 컷마다 바뀌었다"),
               ("hook", "맨 위 문구가 제목이라 밋밋했다"),
               ("몸이 닿는", "손가락이 옷 속으로 녹아들었다"),
               ("SHOT` 을 컷마다 다르게", "샷이 다 비슷해 밋밋했다"),
               ("SETTING` 은 한 화에 두 곳까지", "장소가 갑자기 튀었다")]:
    ck(f"프롬프트에 들어갔다 — {why}", k in pr, k)

# 같은 인물이 컷마다 다른 옷이면 잡는다
d = good_doc()
d["episodes"][0]["cuts"][1]["prompt"] = good_prompt("None.").replace(
    "SUBJECT: 시동생 in a black suit facing 며느리 in black mourning hanbok.",
    "SUBJECT: 며느리 in a beige coat.")
ck("한 화 안에서 옷이 다르면 잡는다",
   any("컷마다 다르다" in b for b in S.check(d)),
   next((b[:44] for b in S.check(d) if "컷마다" in b), "안 잡음"))
ck("normalize 가 먼저 맞춰 주면 통과한다", S.check(S.normalize(good_doc())) == [],
   str(S.check(S.normalize(good_doc())))[:60])

# 옷은 **화마다** 맞춘다 (16화 전체가 아니라)
d = good_doc()
for c in d["episodes"][0]["cuts"]:
    c["prompt"] = c["prompt"].replace("in a black suit", "in a casual jacket")
S.fix_outfits(d)
ck("1화 옷을 뒷화 옷으로 덮어쓰지 않는다",
   "casual jacket" in d["episodes"][0]["cuts"][0]["prompt"]
   and "black suit" in d["episodes"][1]["cuts"][0]["prompt"])

# ⭐⭐ 2026-08-20 — 한때 face_tag 를 이름 뒤에 박았다. 그랬더니 플로우가
#    **80컷을 전부 거절했다**: "유명인의 동영상 생성에 관한 정책을 위반할
#    가능성이 있습니다." 기계는 `시동생(50s, square face)` 를
#    '시동생이라는 사람, 50대, 이 얼굴' 로 읽는다 — 실존 인물을 찍어 달라는 말.
#    얼굴은 **플로우 캐릭터(기준 사진)** 가 잡는 몫이다. 컷에는 적지 않는다.
#    → 박아 둔 것이 있으면 떼어 낸다.
d = good_doc()
d["characters"] = [{"name": "시동생", "face_tag": "50s, square face"},
                   {"name": "며느리", "face_tag": "50s, oval face"}]
for c in d["episodes"][0]["cuts"]:
    c["prompt"] = c["prompt"].replace(
        "SUBJECT: 시동생 in a black suit facing 며느리",
        "SUBJECT: 시동생(50s, square face) in a black suit facing 며느리")
ck("얼굴을 박아 둔 컷을 반려한다", any("유명인" in b for b in S.check(d)),
   str(S.check(d))[:70])
S.fix_outfits(d)
subj = [l for l in d["episodes"][0]["cuts"][0]["prompt"].split("\n")
        if l.startswith("SUBJECT:")][0]
ck("얼굴표를 이름 뒤에서 떼어 낸다", "(50s, square face)" not in subj, subj[:64])
ck("이름과 옷차림은 그대로 둔다", "시동생" in subj and "black suit" in subj)
ck("떼어 낸 뒤에는 검사가 조용하다", not any("유명인" in b for b in S.check(d)))

# 샷·장소는 알려만 준다 (버리지 않는다)
d = good_doc()
for e in d["episodes"]:
    for c in e["cuts"]:
        c["prompt"] = c["prompt"].replace("SHOT: Medium two-shot, static camera.",
                                          "SHOT: Medium shot, static camera.")
S.check(d)
ck("샷이 단조로우면 알려 준다", any("샷 크기" in w for w in S.soft(d)))
ck("그렇다고 16화를 버리지는 않는다 (샷)", S.check(d) == [], str(S.check(d))[:60])

print("\n⑭ 인물 기준 사진 프롬프트를 풀세트로 채우는가 (2026-08-20 운영자 지시)")
import charsheet as CS
sheet, desc = CS.build({"name": "본처",
                        "flow_prompt": "Korean woman, 52 years old, oval face, "
                                       "tired eyes. Photorealistic, natural skin "
                                       "texture, Korean TV drama realism.",
                        "outfit": "a moss-green cardigan",
                        "face_tag": "52, oval face"})
ck("짧은 옛 설명도 풀세트로 늘어난다", len(sheet.split()) >= 90, f"{len(sheet.split())}낱말")
# ⚠️ 줄 이름을 글자로 베껴 두면 이름을 손보는 순간 시험이 깨진다
#    (FRAMING → FRAME 으로 바꿨을 때 실제로 깨졌다). **코드에서 가져온다.**
import charsheet as _CS                                     # noqa: E402
for label, txt in [("자세", _CS.POSE), ("화면 잡기", _CS.FRAME),
                   ("배경", _CS.BACKDROP), ("빛", _CS.LIGHT),
                   ("화풍", _CS.LOOK), ("하지 말 것", _CS.AVOID)]:
    ck(f"{label} 를 못 박는다", txt in sheet, txt[:34])
ck("빈 배경을 못 박는다", "no furniture, no props" in sheet)
ck("옷차림이 들어간다", "moss-green cardigan" in sheet)
ck("옛 화풍 문구는 지운다", "Photorealistic, natural skin texture, Korean TV" not in sheet)
ck("캐릭터 설명은 짧게 따로", 0 < len(desc.split()) <= 40 and desc.startswith("본처 —"), desc[:52])

d = good_doc()
d["characters"] = [{"name": "며느리", "flow_prompt": "Korean woman, 50 years old, oval face."}]
S.normalize(d)
ck("대본에 자동으로 채워진다", bool(d["characters"][0].get("flow_sheet")))
ck("설명도 함께 채워진다", bool(d["characters"][0].get("flow_desc")))
before = d["characters"][0]["flow_sheet"]
S.normalize(d)
ck("이미 있으면 덮어쓰지 않는다", d["characters"][0]["flow_sheet"] == before)

_pr = (ROOT / "prompts" / "series_gen.md").read_text(encoding="utf-8")
ck("프롬프트가 생김새를 빠짐없이 적으라고 한다",
   "얼굴형" in _pr and "머리" in _pr and "표정" in _pr)

print("\n⑬ 고정 문구를 글자로 베껴 두지 않았는가")
# ⚠️ 2026-08-20 — STYLE·Avoid 를 손봤더니 시험과 프롬프트 예시가 옛 글자를
#    베껴 두고 있어 80컷이 통째로 걸렸다. 코드에서 가져오는지 확인한다.
_t = (ROOT / "tools" / "series_test.py").read_text(encoding="utf-8")
ck("시험이 Avoid 를 코드에서 가져온다", "S.AVOID_FIX" in _t)
_p = (ROOT / "prompts" / "series_gen.md").read_text(encoding="utf-8")
ck("프롬프트 예시가 지금 머리말과 같다", S.HEAD_FIX in _p, S.HEAD_FIX)
ck("프롬프트 예시가 지금 STYLE 과 같다", S.STYLE_FIX[7:40] in _p, S.STYLE_FIX[7:40])
ck("프롬프트 예시가 지금 Avoid 와 같다", S.AVOID_FIX[7:40] in _p)
ck("고정 문구에 '한 번에 찍기' 가 들어 있다",
   "single continuous take" in S.STYLE_FIX and "no scene change" in S.STYLE_FIX)
ck("고정 문구에 '중간에 옷·얼굴 바뀜 금지' 가 들어 있다",
   "changing clothes or face mid-shot" in S.AVOID_FIX)

# ⭐ 2026-08-21 — 화풍을 반실사 그림체로 바꿨다 (운영자 지시)
import charsheet as _CS2                                    # noqa: E402
ck("컷 화풍이 그림체다", "illustration" in S.STYLE_FIX.lower(), S.STYLE_FIX[60:110])
ck("만화가 아니라 반실사다",
   "semi-realistic" in S.STYLE_FIX.lower()
   and "rather than cartoon exaggeration" in S.STYLE_FIX.lower())
ck("인물 그림도 **같은 화풍**이다 (따로 놀면 얼굴이 안 잡힌다)",
   "illustration" in _CS2.LOOK.lower() and "semi-realistic" in _CS2.LOOK.lower(),
   _CS2.LOOK[:50])
# ⚠️ 반대편 목록에 그림체를 막는 말이 남아 있으면 바라는 것을 스스로 막는다
for _w in ("cartoon", "illustration", "anime", "drawing"):
    ck(f"하지 마라 목록에 '{_w}' 가 없다", _w not in _CS2.AVOID.lower(),
       _CS2.AVOID[-70:])
ck("과장된 비례는 여전히 막는다", "chibi" in _CS2.AVOID.lower())
ck("사진을 부르는 말은 그대로 떼어 낸다",
   "photorealistic" in _CS2.PHOTO_WORDS and "photograph" in _CS2.PHOTO_WORDS)

print("\n⑬-2 붙여 넣을 때 주소로 읽히지 않는가 (2026-08-20 · 두 번째 사고)")
# ⚠️ `SHOT:` 으로 시작하면 붙여 넣는 쪽이 `shot:` 을 주소 이름으로 읽어
#    글자가 통째로 %20 · %EB.. 로 깨진다. 실제로 운영자가 두 번 겪었다.
ck("머리말에 콜론이 없다", ":" not in S.HEAD_FIX, S.HEAD_FIX)
ck("머리말이 있으면 주소로 안 읽힌다", not S.looks_like_url(good_prompt()))
ck("머리말이 없으면 주소로 읽힌다",
   S.looks_like_url(good_prompt().split("\n", 1)[1]))
d = good_doc()
for e in d["episodes"]:
    for c in e["cuts"]:
        c["prompt"] = c["prompt"].split("\n", 1)[1]        # 머리말을 뗀다
ck("머리말이 빠진 대본을 검사가 잡는다", any("주소" in b or "머리말" in b
                                        for b in S.check(d)), str(S.check(d))[:60])
ck("고쳐 주면 머리말이 되살아난다",
   all(c["prompt"].startswith(S.HEAD_FIX)
       for e in S.normalize(d)["episodes"] for c in e["cuts"]))
ck("고친 뒤에는 검사가 조용하다", S.check(d) == [], str(S.check(d))[:60])

print("\n⑬-4 목소리 지시가 붙는가 (2026-08-20 운영자: '나레이션이 로봇 같다')")
# ⚠️ 소리에 관한 지시가 한 줄도 없으면 영상 만드는 쪽은 **또박또박 읽는
#    낭독**을 고른다. 게다가 화면 밖 해설자 목소리로 얹히는 일도 잦다.
d = S.normalize(good_doc())
c1 = d["episodes"][0]["cuts"][0]["prompt"]
ck("AUDIO 줄이 붙는다", "AUDIO:" in c1)
# ⭐ 제미나이 자문 2번 뒤로는 **바라는 것만** 적는다 (no ~ 는 역효과).
ck("화면 속 사람이 직접 말한다고 적는다", "say the lines themselves" in c1)
ck("입모양을 맞추라고 한다", "lips moving in sync" in c1)
ck("그 자리에서 하는 말이라고 적는다", "real spontaneous speech" in c1)
ck("들리는 소리를 짚어 준다", "only the quiet room tone" in c1)
ck("대사 있는 컷에 VOICE 줄이 붙는다",
   any("VOICE:" in c["prompt"] for e in d["episodes"] for c in e["cuts"]))
sil = [c["prompt"] for e in d["episodes"] for c in e["cuts"]
       if "DIALOGUE: None." in c["prompt"]]
if sil:
    ck("대사 없는 컷은 조용한 AUDIO 를 쓴다", S.AUDIO_SILENT in sil[0])
    ck("대사 없는 컷엔 VOICE 를 안 붙인다", "VOICE:" not in sil[0])
ck("두 번 돌려도 줄이 안 늘어난다",
   S.normalize(d)["episodes"][0]["cuts"][0]["prompt"].count("AUDIO:") == 1)
ck("AUDIO 줄이 없으면 반려한다",
   any("AUDIO" in b for b in S.check(
       {**d, "episodes": [{**d["episodes"][0], "cuts": [
           {**d["episodes"][0]["cuts"][0],
            "prompt": c1.replace(S.AUDIO_FIX + "\n", "")}]}]})))
# ⭐ 고정 문구 한 낱말이 80컷을 통째로 막은 적이 **세 번** 있다 —
#      `on screen` 의 screen · `between words` 의 words · `read every…` 의 read
#    그래서 이제 **모든 고정 문구를 한꺼번에** 본다. 하나라도 늘면 여기서 잡힌다.
FIXED = [("머리말", S.HEAD_FIX), ("STYLE", S.STYLE_FIX), ("Avoid", S.AVOID_FIX),
         ("AUDIO", S.AUDIO_FIX), ("조용한 AUDIO", S.AUDIO_SILENT),
         ("COLOR", S.COLOR_FIX), ("이어짐", S.CONT_FIRST),
         ("입모양", S.LIPSYNC), ("화면 잡기", S.FRAMING),
         ("한국어 표시", S.DIA_LANG), ("차례대로", S.DIA_ORDER)]
for _nm, _tx in FIXED:
    _low = str(_tx).lower()
    _hard = [w for w in S.TEXT_HARD if re.search(rf"\b{w}\b", _low)]
    # Avoid 줄은 '이런 것 넣지 마라' 는 목록이라, 그 낱말이 들어 있는 것이
    # **정상이다** (documents with visible writing 처럼). 검사에서 뺀다.
    if _nm == "Avoid":
        _hard = []
    ck(f"{_nm} 고정 문구가 '글자 나올 물건' 검사에 안 걸린다", not _hard, str(_hard))
    _rd = ([] if _nm == "Avoid"
           else [w for w in S.READING if re.search(rf"\b{w}\b", _low)])
    ck(f"{_nm} 고정 문구에 '읽는 말' 이 없다", not _rd, str(_rd))
    ck(f"{_nm} 고정 문구가 정책 검사에 안 걸린다", not S.policy_hits(_tx),
       str(S.policy_hits(_tx)))
ck("목소리가 사람마다 다르게 나온다",
   S.voice_of({"flow_prompt": "Korean man, 55 years old, agitated expression."})
   != S.voice_of({"flow_prompt": "Korean woman, 42 years old, confident eyes."}))
# ⭐ 2026-08-20 운영자: "외국인이 한국말하는 것처럼 들린다."
#    지시가 전부 영어라 영어 목소리로 한글을 더듬더듬 읽었다.
ck("대사 바로 옆에 대문자 한국어 표시를 붙인다", S.DIA_LANG in c1, S.DIA_LANG)
_dl = S.normalize(good_doc())
_dl["episodes"][0]["cuts"][0]["prompt"] = good_prompt(
    '본처 (furious): "당신 진짜 제정신이야?" / 남편 (annoyed): "더는 숨 막혀서 못 살아."')
S.fix_lipsync(_dl)
S.fix_dialogue_lang(_dl)
_d1 = S.dia_text(_dl["episodes"][0]["cuts"][0]["prompt"])
ck("말투 괄호마다 in Korean 을 붙인다", _d1.count("in Korean)") == 2, _d1[:90])
ck("한 사람에 한 줄로 나눈다", len(_d1.split("\n")) == 3, _d1.count("\n"))
S.fix_dialogue_lang(_dl)
ck("두 번 붙여도 안 겹친다",
   S.dia_text(_dl["episodes"][0]["cuts"][0]["prompt"]).count("in Korean)") == 2)
ck("두 번 붙여도 줄이 안 늘어난다",
   len(S.dia_text(_dl["episodes"][0]["cuts"][0]["prompt"]).split("\n")) == 3)
ck("차례대로 말하라고 못 박는다", S.DIA_ORDER in _d1)
ck("입모양 맞추기가 ACTION 에 있다",
   S.LIPSYNC.strip() in next(l for l in
                             _dl["episodes"][0]["cuts"][0]["prompt"].split("\n")
                             if l.startswith("ACTION:")))
ck("AUDIO 에 서울 억양을 못 박는다", "standard Seoul intonation" in c1)
# ⭐ 제미나이 자문 2번 — `no foreign accent` 는 오히려 foreign 을 불러들인다.
#    소리에 관한 것은 **바라는 것만** 적는다.
for w in ("no foreign", "no english", "no narrator", "no voice-over",
          "no background music", "no sound effects"):
    ck(f"하지 말라는 말이 없다 — {w}", w not in (S.AUDIO_FIX + S.AUDIO_SILENT).lower())
ck("바라는 것만 적어 같은 뜻을 담는다",
   "only the quiet room tone" in S.AUDIO_FIX
   and "say the lines themselves" in S.AUDIO_FIX)
ck("소리 지르는 말은 ?! 로 끝난다",
   S.add_breath("진짜 해보자는 거지?", "shouting") == "진짜 해보자는 거지?!")
ck("보통 말투는 그대로 둔다",
   S.add_breath("진짜 해보자는 거지?", "calm") == "진짜 해보자는 거지?")
ck("감탄사 뒤에 쉼표를 넣는다",
   S.add_breath("그럼 어떻게 할 건데?", "calm") == "그럼, 어떻게 할 건데?")
# ⚠️ 꾸미는 말에 쉼표를 넣으면 뜻이 망가진다 — 실제로 두 곳을 망쳤었다
ck("'당신 명의로' 에는 쉼표를 안 넣는다",
   S.add_breath("당신 명의로 다 해놨어.", "calm") == "당신 명의로 다 해놨어.")
ck("'자기 혼자' 에도 쉼표를 안 넣는다",
   S.add_breath("자기 혼자 떨어졌다고요.", "calm") == "자기 혼자 떨어졌다고요.")
ck("짧은 말에는 쉼표를 안 넣는다",
   S.add_breath("그래 알았어.", "calm") == "그래 알았어.")
ck("목소리에도 한국어가 모국어라고 적는다",
   "native Korean speaker" in S.voice_of({"flow_prompt": "Korean man, 55 years old."}))
ck("두 번 돌려도 한국어 못이 겹치지 않는다",
   S.normalize(d)["episodes"][0]["cuts"][0]["prompt"].count(S.DIA_LANG) == 1)
ck("대사 없는 컷에는 한국어 못을 안 붙인다",
   all(S.DIA_LANG not in c["prompt"] for e in d["episodes"] for c in e["cuts"]
       if "DIALOGUE: None." in c["prompt"]))
ck("한국어 못이 다른 검사에 안 걸린다",
   not [w for w in S.TEXT_HARD if re.search(rf"\b{w}\b", S.DIA_LANG.lower())]
   and not S.policy_hits(S.DIA_LANG))

ck("인물표에 적어 둔 목소리를 그대로 쓴다",
   S.voice_of({"voice": "a whispery voice"}) == "a whispery voice")
ck("프롬프트 규칙에도 voice 가 적혀 있다",
   "voice" in (ROOT / "prompts" / "series_gen.md").read_text(encoding="utf-8"))

print("\n⑬-5 컷끼리 이어지고 색이 통일되는가 (2026-08-20 운영자 지시)")
d5 = S.normalize(good_doc())
p1 = d5["episodes"][0]["cuts"][0]["prompt"]
p2 = d5["episodes"][0]["cuts"][1]["prompt"]
p3 = d5["episodes"][1]["cuts"][0]["prompt"]
ck("모든 컷에 색 지시가 있다",
   all(S.COLOR_FIX in c["prompt"] for e in d5["episodes"] for c in e["cuts"]))
ck("색 지시가 컷마다 글자 하나 안 다르다",
   len({[l for l in c["prompt"].split("\n") if l.startswith("COLOR:")][0]
        for e in d5["episodes"] for c in e["cuts"]}) == 1)
ck("색 지시가 없으면 반려한다",
   any("색 지시" in b for b in S.check(
       {**d5, "episodes": [{**d5["episodes"][0], "cuts": [
           {**d5["episodes"][0]["cuts"][0],
            "prompt": p1.replace(S.COLOR_FIX + "\n", "")}]}]})))
ck("맨 첫 컷은 '첫 장면' 이라고 적는다", S.CONT_FIRST in p1)
ck("같은 화 다음 컷은 '이어진다' 고 적는다", "continues straight on" in p2, )
ck("앞 컷에서 무엇이 있었는지 적어 준다",
   "steps in front" in p2 or "holds out" in p2, p2.split("CONTINUITY:")[1][:60])
ck("화가 넘어가면 '같은 이야기의 뒷날' 로 적는다",
   "same continuing story" in p3)
ck("모든 컷에 이어짐 지시가 있다",
   all("CONTINUITY:" in c["prompt"] for e in d5["episodes"] for c in e["cuts"]))
ck("두 번 돌려도 이어짐·색이 겹치지 않는다",
   S.normalize(d5)["episodes"][0]["cuts"][0]["prompt"].count("CONTINUITY:") == 1
   and d5["episodes"][0]["cuts"][0]["prompt"].count("COLOR:") == 1)
ck("색·이어짐 지시가 다른 검사에 안 걸린다",
   not S.policy_hits(S.COLOR_FIX + S.CONT_FIRST)
   and not [w for w in S.TEXT_HARD
            if re.search(rf"\b{w}\b", (S.COLOR_FIX + S.CONT_FIRST).lower())])
# ⭐ 플로우에서 목소리를 미리 고르면 프롬프트가 안 먹는다 → 인물 정보에도 넣는다
ck("인물표에 목소리가 박힌다",
   all((c.get("voice") or "").strip() for c in d5["characters"]))
ck("인물 설명 칸에도 목소리가 실린다",
   all("speaks with" in (c.get("flow_desc") or "") for c in d5["characters"]),
   (d5["characters"][0].get("flow_desc") or "")[-60:])

print("\n⑬-3 정책에 막히는 말이 없는가 (2026-08-20 · 플로우가 실제로 거절했다)")
# ⚠️ 플로우: "이 프롬프트는 유명인의 동영상 생성에 관한 정책을 위반할 가능성이…"
#    `Live-action Korean drama` + `Korean TV drama realism` + `actor` 가 겹쳐
#    "실존 배우로 드라마를 다시 만들어 달라" 로 읽혔다.
import charsheet as _C                                      # noqa: E402
for nm, txt in (("머리말", S.HEAD_FIX), ("STYLE", S.STYLE_FIX),
                ("Avoid", S.AVOID_FIX), ("인물 LOOK", _C.LOOK),
                ("인물 Avoid", _C.AVOID), ("인물 자세", _C.POSE)):
    ck(f"{nm} 고정 문구가 깨끗하다", not S.policy_hits(txt), str(S.policy_hits(txt)))
ck("배우를 가리키는 말을 잡는다", S.policy_hits("swapping in a different actor.") == ["actor"])
ck("유명인을 가리키는 말을 잡는다", "famous" in S.policy_hits("a famous Korean actress"))
ck("드라마 이름을 가리키는 말을 잡는다",
   S.policy_hits("Korean TV drama realism") == ["korean tv drama"])
ck("'stares' 를 'star' 로 잘못 잡지 않는다", not S.policy_hits("she stares at him"))
d = good_doc()
d["episodes"][0]["cuts"][0]["prompt"] = good_prompt().replace(
    "different person.", "different actor.")
ck("정책에 막히는 컷은 **반려**한다", any("정책" in b for b in S.check(d)),
   str(S.check(d))[:70])
d2 = good_doc()
d2["characters"][0]["flow_prompt"] = "Korean woman, looks like a famous actress."
ck("인물표에 있어도 반려한다", any("정책" in b for b in S.check(d2)))
ck("인물 설명을 안전한 말로 바꿔 준다",
   not S.policy_hits(_C.scrub("Korean TV drama realism, like a Korean actress")),
   _C.scrub("Korean TV drama realism, like a Korean actress"))
ck("예전 문구로 만든 인물표는 다시 만든다",
   _C.stale({"flow_sheet": "LOOK: photorealistic live-action photograph.",
             "flow_desc": "x"}))
_ch = {"name": "본처", "flow_prompt": "Korean woman, 52 years old, oval face, "
       "dark brown hair in a low bun. Photorealistic."}
_sheet, _desc = _C.build(_ch)
ck("지금 문구로 만든 인물표는 그냥 둔다",
   not _C.stale({"flow_sheet": _sheet, "flow_desc": _desc}))
ck("새로 만든 인물표에도 막히는 말이 없다",
   not S.policy_hits(_sheet + _desc), str(S.policy_hits(_sheet + _desc)))
ck("새 인물표가 '지어낸 사람' 이라고 먼저 밝힌다",
   "fictional" in _sheet.split("\n")[0].lower(), _sheet.split("\n")[0])

print("\n⑫ 눈앞의 사람을 남 부르듯 하지 않는가 (2026-08-20 · 실제 영상)")
CH = [{"name": "본처", "flow_prompt": "Korean woman, 52 years old, …"},
      {"name": "내연녀", "flow_prompt": "Korean woman, 42 years old, …"},
      {"name": "남편", "flow_prompt": "Korean man, 55 years old, …"}]


def cut(subj, dia):
    return {"n": 1, "prompt": f"SUBJECT: {subj}\nDIALOGUE: {dia}"}


ck("마주 본 사람을 '저 여자' 라고 하면 잡는다",
   facing := S.facing_error(
       cut("본처 in a cardigan facing 내연녀 in a red dress.",
           '본처: "저 여자가 이유였어?"'), CH), str(facing))
ck("자리에 없는 사람 얘기는 안 잡는다 (2화 3컷 같은 것)",
   S.facing_error(cut("본처 in a blouse facing 남편 in a suit.",
                      '본처: "평생 그 여자랑 살지 마."'), CH) == [])
ck("죽은 사람을 '그 사람' 이라 해도 안 잡는다 (14화 1컷 같은 것)",
   S.facing_error(cut("내연녀 in a dress facing 본처 in a suit.",
                      '본처: "죽던 날까지 그 사람 거였어."'), CH) == [])
ck("혼자 있는 컷은 남 얘기를 해도 된다",
   S.facing_error(cut("본처 in a cardigan.", '본처: "저 여자가 문제야."'), CH) == [])

d = good_doc()
d["characters"] = CH
d["episodes"][0]["cuts"][0]["prompt"] = (
    "SHOT: Medium two-shot, static camera.\n"
    "SUBJECT: 본처 in a cardigan facing 내연녀 in a red dress.\n"
    "ACTION: 본처 stares.\n"
    'DIALOGUE: 본처: "저 여자가 이유였어? 대체 언제부터 그런 거야?"\n'
    "SETTING: hallway, evening.\n" + S.STYLE_FIX + "\n" + S.AVOID_FIX)
d["episodes"][0]["cuts"][0]["subtitle"] = '"저 여자가 이유였어?"'
S.normalize(d)
# 대사는 여러 줄이 되었으므로 **덩어리**에서 본다
dia = S.dia_text(d["episodes"][0]["cuts"][0]["prompt"])
ck("우리가 '당신' 으로 고쳐 준다", "당신이 이유였어" in dia, dia[-52:])
ck("자막도 같이 고친다", "당신" in d["episodes"][0]["cuts"][0]["subtitle"])
ck("고친 것을 반드시 알려 준다", any("당신" in w for w in S.soft(d)))

print("\n⑧ 사람이 실제로 하는 말인가 (2026-08-20 손님: '말도 어색해')")
d = good_doc()
STIFF_SAY = ['"대법원 판례상 사망보험금은 전부 내 거라고 나왔어. 더 할 말 있으면 해 봐."',
             '"악의적 증여는 시효랑 상관없이 다 돌려받을 수 있다고 했어. 알아두라고."',
             '"한정승인 하면 상속재산은 그대로 남는다고 변호사가 그러더라고. 진짜야."',
             '"유류분 반환청구 할 거야, 나도 받을 몫이 분명히 있으니까. 각오하고 있어."',
             '"그건 고유재산이라 상속액에 안 들어간다고 했잖아. 왜 자꾸 우기는 거야?"',
             '"물가상승률 반영해서 다시 계산하면 액수가 완전히 달라진다고. 알겠어?"']
for i, say in enumerate(STIFF_SAY):
    d["episodes"][i]["cuts"][0]["prompt"] = good_prompt('본처 says: ' + say)
hit = S.check(d)
ck("대사가 통째로 서류 말투면 잡는다", any("서류·판결문 말투" in b for b in hit),
   next((b[:52] for b in hit if "서류" in b), ""))

# 법정 장면에서 한두 줄 나오는 것까지 막으면 안 된다 (돈만 나간다)
d = good_doc()
for i, say in enumerate(STIFF_SAY[:2]):
    d["episodes"][i]["cuts"][0]["prompt"] = good_prompt('본처 says: ' + say)
ck("한두 줄 섞인 것은 봐준다", S.check(d) == [], str(S.check(d))[:70])

print("\n⑦ 대사 — 6초를 꽉 채우고 주고받는가 (2026-08-20 손님 지적)")
d = good_doc()
d["episodes"][3]["cuts"][0]["prompt"] = good_prompt('본처 says: "너지?"')
ck(f"대사가 {S.DIA_SYL_MIN}음절에 못 미치면 잡는다 (6초가 빈다)",
   any("거의 빈다" in b for b in S.check(d)))

d = good_doc()
for n in (3, 4):
    d["episodes"][6]["cuts"][n - 1]["prompt"] = good_prompt("None.")
ck("한 화에 주고받는 컷이 모자라면 잡는다",
   any("주고받는 컷" in b for b in S.check(d)))

d = good_doc()
d["episodes"][2]["cuts"][2]["prompt"] = good_prompt(
    '시동생 (cold): "이 집은 이제 전부 저희 것이니 오늘 안에 나가 주십시오." / '
    '며느리 (trembling): "그이 관 앞에서 무슨 소리를 하시는 겁니까, 지금. '
    '부끄럽지도 않으세요?"')
ck(f"한 컷 대사 총합이 {S.DIA_SYL_MAX}음절을 넘으면 잡는다",
   any("음절이다" in b for b in S.check(d)))

d = good_doc()
d["episodes"][2]["cuts"][2]["prompt"] = good_prompt(
    '시동생: "나가." / 며느리: "싫어." / 시어머니: "그만." / 아들: "왜요."')
ck(f"한 컷에 {S.TALKERS_MAX}번 넘게 말하면 잡는다",
   any("번 말한다" in b for b in S.check(d)))

ck("두 사람이 주고받는 멀쩡한 컷은 통과시킨다", S.check(good_doc()) == [],
   str(S.check(good_doc()))[:70])

print("\n⑥ 손볼 곳은 알려 주되, 그것 때문에 버리지는 않는가")
d = good_doc()
d["episodes"][2]["cuts"][0]["prompt"] = good_prompt(
    '본처 says in Korean: "내연녀 집에서 떨어져 죽었다고요? '
    '그게 말이 되는 소립니까? 다시 말해 봐요."')
ck("대사에 배역 딱지가 있으면 알려 준다", any("내연녀" in w for w in S.soft(d)))
ck("그렇다고 16화를 버리지는 않는다", S.check(d) == [], str(S.check(d))[:60])

d = good_doc()
ck("멀쩡한 대본에는 손볼 곳이 없다", S.soft(d) == [], str(S.soft(d))[:60])

# ⭐ 2026-08-20 — 첫 실제 영상에서 여자 손가락이 남자 옷 속으로 녹아들었다.
d = good_doc()
d["episodes"][1]["cuts"][0]["prompt"] = good_prompt().replace(
    "ACTION: 시동생 holds out a closed folder toward 며느리.",
    "ACTION: 며느리 grabs 시동생 by the arm firmly.")
ck("서로 몸이 닿는 동작을 알려 준다", any("몸이 닿는" in w for w in S.soft(d)),
   next((w[:46] for w in S.soft(d) if "몸이 닿는" in w), ""))
ck("그렇다고 16화를 버리지는 않는다 (접촉)", S.check(d) == [], str(S.check(d))[:60])

# 혼자 하는 몸짓은 걸리면 안 된다 (닿지 않으므로 오류가 안 난다)
for act in ["며느리 clenches her fists tightly.",
            "며느리 steps in front of 시동생, blocking his way.",
            "며느리 slams her palm on the table.",
            "며느리 reaches out but stops short."]:
    d = good_doc()
    d["episodes"][1]["cuts"][0]["prompt"] = good_prompt().replace(
        "ACTION: 시동생 holds out a closed folder toward 며느리.", "ACTION: " + act)
    ck(f"혼자 하는 몸짓은 그냥 둔다 — {act[:26]}…",
       not any("몸이 닿는" in w for w in S.soft(d)))

print("\n⑨ 통과하면 지난 반려본을 치우는가 (2026-08-20 — 옛 파일을 새 것으로 잘못 읽었다)")
import inspect
src = inspect.getsource(S.main)
ck("통과 자리에서 .broken.json 을 지운다",
   "broken.json" in src and ".unlink()" in src)

print("\n④ 규격 숫자가 실제 운영 조건과 맞는가")
ck("6초 × 5컷 = 30초", S.SEC * S.CUTS == 30, f"{S.SEC}×{S.CUTS}")
ck("16화 × 30초 = 8분 (롱폼 한 편)", S.EPISODES * S.SEC * S.CUTS == 480)
ck("하루 크레딧 45 ≤ 무료 50", S.CUTS * S.SEC * 1.5 <= 50, f"{S.CUTS * S.SEC * 1.5:.0f}크레딧")
# 한국어는 초당 약 5자. 6초 클립에서 앞뒤 숨 쉴 틈을 빼면 약 5.5초를 말한다.
# 한국어 드라마 대사는 초당 5~6음절. 6초 중 5.5초를 말한다.
ck(f"대사 {S.DIA_SYL_MAX}음절이 {S.SEC}초에 들어가는가",
   S.DIA_SYL_MAX <= S.SPEAK_SEC * S.EASY_SYL_PER_SEC,
   f"{S.DIA_SYL_MAX / S.EASY_SYL_PER_SEC:.1f}초 · 초당 {S.EASY_SYL_PER_SEC}음절")
# ⚠️ 예전에는 **6초 전체**를 얼마나 채우는지 쟀다. 그런데 실제 영상을 재 보니
#    앞 1초는 소리가 안 난다(모델이 그냥 버린다). 그 1초까지 채우라고 밀어붙인
#    결과가 초당 7.2음절 — 받침이 뭉개지는 속도였다.
#    → **말할 수 있는 시간(SPEAK_SEC)** 을 얼마나 채우는지로 잰다.
ck(f"말할 수 있는 {S.SPEAK_SEC}초를 8할 넘게 채우는가 (예전엔 절반이 비었다)",
   S.DIA_SYL_MAX / S.EASY_SYL_PER_SEC >= S.SPEAK_SEC * 0.8,
   f"{S.DIA_SYL_MAX / S.EASY_SYL_PER_SEC / S.SPEAK_SEC * 100:.0f}%")
ck("급하게 쏟아내는 속도가 아닌가 (실측 초당 7.2는 너무 빨랐다)",
   S.EASY_SYL_PER_SEC <= 6.2, f"초당 {S.EASY_SYL_PER_SEC}음절")
ck("앞머리 버려지는 시간을 빼고 잡는가", S.SPEAK_SEC == S.SEC - S.DEAD_HEAD,
   f"{S.SEC} - {S.DEAD_HEAD} = {S.SPEAK_SEC}초")
ck("진짜 못 말할 길이만 반려한다", S.DIA_SYL_HARD > S.DIA_SYL_MAX,
   f"알맞음 {S.DIA_SYL_MAX} · 반려 {S.DIA_SYL_HARD} 넘을 때")
# ⚠️ 말하기 속도는 눈대중으로 정하면 안 된다 (5.5 로 잡았다가 6초 중 1.3초를 버렸다)
ck("말하기 속도가 실측 범위 안인가", 6.0 <= S.SYL_PER_SEC <= 7.0,
   f"초당 {S.SYL_PER_SEC}음절")
ck("음절 세기가 공백·쉼표를 빼는가", S.syl("여기가 어디라고 뻔뻔하게 와?") == 12,
   f"{S.syl('여기가 어디라고 뻔뻔하게 와?')}음절 (글자로는 16자)")

# ⑩ 옷과 배경이 컷 사이에서 안 바뀌는가 (2026-08-22 운영자 지적)
#
# ⚠️ 운영자: "프롬프트에서 자꾸 옷이랑 뒤에 배경이 바뀌어."
#    CONTINUITY 줄은 이미 "same clothes, same room" 이라고 말하고 있었다.
#    **플로우는 앞 컷을 기억하지 못하므로 그 말은 아무 정보도 못 준다.**
#    까닭은 말이 뭉뚱그려진 것이었다 — `a casual jacket` 은 아무 자켓이나 된다.
#    → 색·소재·가구까지 못 박고, 그 글자가 컷 사이에 **똑같은지** 본다.
print("\n⑩ 옷과 배경이 컷 사이에서 안 바뀌는가")
_doc = json.loads((ROOT / "data" / "series" / "S001.json").read_text(encoding="utf-8"))


def _line(cut, tag):
    return next((l for l in (cut.get("prompt") or "").split("\n")
                 if l.startswith(tag)), "")


_vague = []
_by_place, _by_who = {}, {}
for _e in _doc.get("episodes") or []:
    for _c in _e.get("cuts") or []:
        _su, _st = _line(_c, "SUBJECT:"), _line(_c, "SETTING:")
        if S.VAGUE.search(_su):
            _vague.append(f"{_e.get('no')}화 {_c['n']}컷: {_su[:60]}")
        # 같은 장소 → SETTING 이 글자 그대로 같아야 한다
        _key = _st.split("—")[0].strip().lower()
        _by_place.setdefault(_key, set()).add(_st)
        # 같은 인물 → 그 화 안에서 옷 글자가 같아야 한다
        # ⚠️ 여기서 ` facing ` 을 넘어가면 안 된다. 옷 설명이 **다음 사람까지**
        #    삼켜서, 같은 옷인데도 다르다고 나온다 (fix_outfits 주석에 적혀 있던
        #    바로 그 실수를 시험에서 되풀이했다).
        for _m in re.finditer(
                # ⭐ 2026-08-24 — 한 컷에 세 사람이 나오면 `;` 로 나열한다.
                #    거기서도 끊어 줘야 앞사람 옷이 뒷사람 것까지 삼키지 않는다.
                r"\b(?:the )?(\w[\w ]*?) wearing (.+?)(?=\s+facing\b|;|\.$|$)",
                _su):
            _by_who.setdefault((_e.get("no"), _m.group(1).strip()), set()).add(
                _m.group(2).strip())

ck("뭉뚱그린 옷차림이 안 남아 있다", not _vague,
   "; ".join(_vague[:2]) + " — 'casual jacket' 은 매번 다른 자켓이 된다")
_bad_p = {k: v for k, v in _by_place.items() if k and len(v) > 1}
ck("같은 장소는 늘 똑같이 적혀 있다", not _bad_p,
   f"{list(_bad_p)[:2]} — 글자가 다르면 다른 방이 나온다")
_bad_w = {k: v for k, v in _by_who.items() if len(v) > 1}
ck("한 화 안에서 같은 사람은 같은 옷", not _bad_w, str(list(_bad_w)[:2]))
ck("옷을 정한 인물이 실제로 있다", len(_by_who) >= 3, f"{len(_by_who)}명")

# ⚠️ 얼굴·나이는 절대 안 적는다 — 유명인 정책에 다섯 번 막혔던 자리다
for _e in _doc.get("episodes") or []:
    for _c in _e.get("cuts") or []:
        _h = S.policy_hits(_c.get("prompt") or "")
        if _h:
            ck(f"{_e.get('no')}화 {_c['n']}컷: 정책에 걸릴 말이 없다", False, str(_h))
            break
    else:
        continue
    break
else:
    ck("옷·가구를 적어도 정책에 걸릴 말은 안 들어갔다", True)


print("\n" + "─" * 52)
print(f"❌ 시리즈 검사기: {len(FAIL)}가지 실패" if FAIL else "✅ 시리즈 검사기: 전부 통과")
sys.exit(1 if FAIL else 0)
