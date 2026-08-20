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


TALK = ('시동생 (cold): "이 집, 이제 저희 겁니다." / '
        '며느리 (trembling): "무슨 소리예요."')


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
    '시동생 says in Korean: "이 집은 이제 저희 것이니 나가 주셔야 하겠습니다."')
ck(f"대사가 {S.DIA_MAX}자를 넘으면 잡는다", any("대사가" in b for b in S.check(d)))

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

print("\n⑦ 대사 — 6초를 꽉 채우고 주고받는가 (2026-08-20 손님 지적)")
d = good_doc()
for n in (3, 4):
    d["episodes"][6]["cuts"][n - 1]["prompt"] = good_prompt("None.")
ck("한 화에 주고받는 컷이 모자라면 잡는다",
   any("주고받는 컷" in b for b in S.check(d)))

d = good_doc()
d["episodes"][2]["cuts"][2]["prompt"] = good_prompt(
    '시동생 (cold): "이 집은 이제 전부 저희 것입니다." / '
    '며느리 (trembling): "그이 관 앞에서 무슨 소리를 하시는 겁니까."')
ck(f"한 컷 대사 총합이 {S.DIA_TOTAL}자를 넘으면 잡는다",
   any("다 합치면" in b for b in S.check(d)))

d = good_doc()
d["episodes"][2]["cuts"][2]["prompt"] = good_prompt(
    '시동생: "나가." / 며느리: "싫어." / 시어머니: "그만."')
ck(f"한 컷에 {S.TALKERS_MAX}번 넘게 말하면 잡는다",
   any("번 말한다" in b for b in S.check(d)))

ck("두 사람이 주고받는 멀쩡한 컷은 통과시킨다", S.check(good_doc()) == [],
   str(S.check(good_doc()))[:70])

print("\n⑥ 손볼 곳은 알려 주되, 그것 때문에 버리지는 않는가")
d = good_doc()
d["episodes"][2]["cuts"][0]["prompt"] = good_prompt(
    '본처 says in Korean: "내연녀 집에서 죽었다고요?"')
ck("대사에 배역 딱지가 있으면 알려 준다", any("내연녀" in w for w in S.soft(d)))
ck("그렇다고 16화를 버리지는 않는다", S.check(d) == [], str(S.check(d))[:60])

d = good_doc()
ck("멀쩡한 대본에는 손볼 곳이 없다", S.soft(d) == [], str(S.soft(d))[:60])

print("\n④ 규격 숫자가 실제 운영 조건과 맞는가")
ck("6초 × 5컷 = 30초", S.SEC * S.CUTS == 30, f"{S.SEC}×{S.CUTS}")
ck("16화 × 30초 = 8분 (롱폼 한 편)", S.EPISODES * S.SEC * S.CUTS == 480)
ck("하루 크레딧 45 ≤ 무료 50", S.CUTS * S.SEC * 1.5 <= 50, f"{S.CUTS * S.SEC * 1.5:.0f}크레딧")
# 한국어는 초당 약 5자. 6초 클립에서 앞뒤 숨 쉴 틈을 빼면 약 5.5초를 말한다.
ck(f"한 컷 대사 {S.DIA_TOTAL}자가 {S.SEC}초에 들어가는가",
   S.DIA_TOTAL <= (S.SEC - 0.5) * 5.2, f"{S.DIA_TOTAL}자 ≈ {S.DIA_TOTAL/5:.1f}초")
ck("두 사람이 나눠 말할 만큼은 되는가", S.DIA_TOTAL >= 24, f"각 {S.DIA_TOTAL//2}자씩")

print("\n" + "─" * 52)
print(f"❌ 시리즈 검사기: {len(FAIL)}가지 실패" if FAIL else "✅ 시리즈 검사기: 전부 통과")
sys.exit(1 if FAIL else 0)
