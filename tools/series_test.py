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
    return (S.HEAD_FIX + "\n"
            "SHOT: Medium two-shot, static camera.\n"
            "SUBJECT: 시동생 in a black suit facing 며느리 in black mourning hanbok.\n"
            "ACTION: 시동생 holds out a closed folder toward 며느리.\n"
            f"DIALOGUE: {dialogue}\n"
            "SETTING: Korean funeral hall reception room, evening, dim light.\n"
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
import json, re
raw = (ROOT / "prompts" / "series_gen.md").read_text(encoding="utf-8")
ex = json.loads('"' + raw.split('"prompt": "')[1].split('"\n')[0] + '"')
d = good_doc()
for n in range(S.CUTS):
    d["episodes"][0]["cuts"][n]["prompt"] = ex
ck("프롬프트 파일의 예시 컷이 통과한다", S.check(d) == [], str(S.check(d))[:80])

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

# face_tag 는 이름 뒤에 똑같이 붙는다
d = good_doc()
d["characters"] = [{"name": "시동생", "face_tag": "50s, square face"},
                   {"name": "며느리", "face_tag": "50s, oval face"}]
S.fix_outfits(d)
subj = [l for l in d["episodes"][0]["cuts"][0]["prompt"].split("\n")
        if l.startswith("SUBJECT:")][0]
ck("얼굴표가 이름 뒤에 붙는다", "시동생(50s, square face)" in subj, subj[:60])
ck("두 번 붙지 않는다", subj.count("(50s, square face)") == 1)

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
for k in ("POSE:", "FRAMING:", "BACKGROUND:", "LIGHT:", "LOOK:", "Avoid:"):
    ck(f"{k} 가 들어간다", k in sheet)
ck("빈 배경을 못 박는다", "completely empty" in sheet)
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
dia = [l for l in d["episodes"][0]["cuts"][0]["prompt"].split("\n")
       if l.startswith("DIALOGUE:")][0]
ck("우리가 '당신' 으로 고쳐 준다", "당신이 이유였어" in dia, dia[10:52])
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
   S.DIA_SYL_MAX <= S.SPEAK_SEC * S.SYL_PER_SEC,
   f"{S.DIA_SYL_MAX / S.SYL_PER_SEC:.1f}초 · 초당 {S.SYL_PER_SEC}음절")
ck(f"{S.SEC}초를 8할 넘게 채우는가 (예전엔 절반이 비었다)",
   S.DIA_SYL_MAX / S.SYL_PER_SEC >= S.SEC * 0.8,
   f"{S.DIA_SYL_MAX / S.SYL_PER_SEC / S.SEC * 100:.0f}%")
# ⚠️ 말하기 속도는 눈대중으로 정하면 안 된다 (5.5 로 잡았다가 6초 중 1.3초를 버렸다)
ck("말하기 속도가 실측 범위 안인가", 6.0 <= S.SYL_PER_SEC <= 7.0,
   f"초당 {S.SYL_PER_SEC}음절")
ck("음절 세기가 공백·쉼표를 빼는가", S.syl("여기가 어디라고 뻔뻔하게 와?") == 12,
   f"{S.syl('여기가 어디라고 뻔뻔하게 와?')}음절 (글자로는 16자)")

print("\n" + "─" * 52)
print(f"❌ 시리즈 검사기: {len(FAIL)}가지 실패" if FAIL else "✅ 시리즈 검사기: 전부 통과")
sys.exit(1 if FAIL else 0)
