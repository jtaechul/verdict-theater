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


def good_prompt(dialogue='시동생 says in Korean, calm: "이 집, 이제 저희 겁니다."'):
    return ("SHOT: Medium two-shot, static camera.\n"
            "SUBJECT: 시동생 in a black suit facing 며느리 in black mourning hanbok.\n"
            "ACTION: 시동생 holds out a closed folder toward 며느리.\n"
            f"DIALOGUE: {dialogue}\n"
            "SETTING: Korean funeral hall reception room, evening, dim light.\n"
            + S.STYLE_FIX + "\n"
            "Avoid: on-screen text, signage, documents with visible writing, "
            "screens, extra people in focus.")


def good_doc():
    eps = []
    for i in range(1, S.EPISODES + 1):
        eps.append({
            "no": i, "title": f"{i}화", "recap": "" if i == 1 else "지난 이야기 한 줄",
            "cuts": [{"n": n, "role": S.ROLES[n - 1], "subtitle": '"짧은 자막"',
                      "prompt": good_prompt() if n == 1
                      else good_prompt("None.")} for n in range(1, S.CUTS + 1)],
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
    '시동생 says in Korean: "이 집은 이제 저희 것이니 나가 주셔야 하겠습니다."')
ck(f"대사가 {S.DIA_MAX}자를 넘으면 잡는다", any("대사가" in b for b in S.check(d)))

d = good_doc()
d["episodes"][4]["recap"] = ""
ck("2화부터 지난 줄거리가 비면 잡는다", any("지난 줄거리" in b for b in S.check(d)))

d = good_doc()
d["episodes"][7]["cuts"][2]["prompt"] = good_prompt("None.").replace(
    "SUBJECT: 시동생 in a black suit facing 며느리 in black mourning hanbok.",
    "SUBJECT: the same woman in a black coat.")
ck("SUBJECT 에 이름 없이 가리키면 잡는다", any("지시대명사" in b for b in S.check(d)))

# ⚠️ 우리 예시 대본이 바로 이 검사에 걸렸다. 앞에 이름이 있으면 통과해야 한다.
d = good_doc()
d["episodes"][7]["cuts"][2]["prompt"] = good_prompt("None.").replace(
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

print("\n④ 규격 숫자가 실제 운영 조건과 맞는가")
ck("6초 × 5컷 = 30초", S.SEC * S.CUTS == 30, f"{S.SEC}×{S.CUTS}")
ck("16화 × 30초 = 8분 (롱폼 한 편)", S.EPISODES * S.SEC * S.CUTS == 480)
ck("하루 크레딧 45 ≤ 무료 50", S.CUTS * S.SEC * 1.5 <= 50, f"{S.CUTS * S.SEC * 1.5:.0f}크레딧")

print("\n" + "─" * 52)
print(f"❌ 시리즈 검사기: {len(FAIL)}가지 실패" if FAIL else "✅ 시리즈 검사기: 전부 통과")
sys.exit(1 if FAIL else 0)
