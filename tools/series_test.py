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
