#!/usr/bin/env python3
"""⭐ 닿는 동작 고치기 · 얼굴 못 · 후킹 검사가 제대로 도는지 본다. 0원.

    python3 tools/touch_hook_test.py

왜 (2026-08-20)
    ① 첫 영상에서 **여자 손가락이 남자 옷 속으로 녹아들었다.**
       닿는 동작을 우리가 안 닿는 동작으로 바꾸게 했는데, 처음 만든 것이
       **물건까지 바꿔 버려** 문장이 망가졌다 —
         `slams his hand on the table` → `slams his sets the table down…`
         `hugs the keys`              → `stands close to the, arms at…`
       그래서 **상대가 사람일 때만** 바꾸도록 고쳤다. 다시 망가지면 안 된다.
    ② 첫 영상에서 남편 얼굴이 컷마다 달랐다 → 이름 뒤에 얼굴 못을 박는다.
    ③ 운영자: "제목이랑 후킹 좀 더 자극적으로 뽑아. 자꾸 점잔 빼지 말고."
       → 후킹이 비었거나 밋밋하면 알려야 한다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import series as S                                          # noqa: E402
import charsheet as C                                       # noqa: E402

FAIL = []


def ck(label, cond, extra=""):
    print(("   ✅ " if cond else "   ❌ ") + label + (f"  ({extra})" if extra else ""))
    if not cond:
        FAIL.append(label)


NAMES = ["본처", "내연녀", "남편"]


def doc_with(actions):
    return {
        "characters": [
            {"name": "본처", "flow_prompt": "Korean woman, 52 years old, oval face, "
             "tired eyes, dark brown hair in a low bun. Photorealistic."},
            {"name": "내연녀", "flow_prompt": "Korean woman, 42 years old, sharp "
             "V-line face, long wavy dyed brown hair. Photorealistic."},
            {"name": "남편", "flow_prompt": "Korean man, 55 years old, square face, "
             "short neatly parted black hair. Photorealistic."},
        ],
        "episodes": [{"no": 1, "hook": "남편이 통장을 비우고 집을 나갔다",
                      "yt_title": "바람난 남편이 통장을 비우고 집을 나갔습니다",
                      "cuts": [{"n": i + 1, "prompt": f"SHOT: Medium two-shot.\n"
                                f"SUBJECT: 본처 in a cardigan facing 남편 in a jacket.\n"
                                f"ACTION: {a}\nDIALOGUE: None.\n"
                                f"SETTING: Korean apartment living room."}
                               for i, a in enumerate(actions)]}],
    }


print("⭐ 닿는 동작 · 얼굴 못 · 후킹 시험\n")

print("① 사람에게 닿는 것은 바꾼다")
d = doc_with(["본처 grabs 남편 by the arm firmly.",
              "남편 shakes off her hand aggressively.",
              "남편 hands over a bunch of keys to her.",
              "본처 grabs her shoulders in shock."])
S.fix_touch(d)
got = [next(l for l in c["prompt"].split("\n") if l.startswith("ACTION:"))[8:].strip()
       for c in d["episodes"][0]["cuts"]]
for g in got:
    print("      " + g)
ck("팔을 잡는 것이 막아서는 것으로 바뀐다", "blocking the way" in got[0])
ck("바꾼 뒤에 태도말이 겹치지 않는다",
   "firmly" not in got[0] and "aggressively" not in got[1], got[1])
ck("건네주는 것이 내려놓는 것으로 바뀐다",
   got[2].startswith("남편 sets the") and "keys" in got[2], got[2])
ck("어깨(복수)도 제대로 바뀐다", "stops short in shock" in got[3], got[3])
for g in got:
    ck(f"문장이 안 망가졌다 — {g[:34]}",
       " sets the table down and steps b" not in g and " to the," not in g)

print("\n② 물건에 닿는 것은 **그대로 둔다** (오히려 권장한다)")
keep = ["남편 slams his hand on the table.",
        "내연녀 hugs the keys tightly to her chest.",
        "본처 holds her bag tightly, looking resolute.",
        "본처 shakes her head firmly.",
        "내연녀 pulls her hair in frustration.",
        "남편 holds a phone to his ear.",
        "본처 shakes a closed envelope at her."]
d2 = doc_with(keep)
S.fix_touch(d2)
for want, c in zip(keep, d2["episodes"][0]["cuts"]):
    got1 = next(l for l in c["prompt"].split("\n") if l.startswith("ACTION:"))[8:].strip()
    ck(f"그대로다 — {want[:36]}", got1 == want, got1)

print("\n③ 손볼 곳 알림도 사람일 때만 나온다")
ck("팔을 잡으면 알린다", bool(S.touch_hits("ACTION: 본처 grabs 남편 by the arm.", NAMES)))
ck("밀면 알린다", bool(S.touch_hits("ACTION: 남편 pushes her.", NAMES)))
ck("손목을 잡으면 알린다", bool(S.touch_hits("ACTION: 본처 grabs her wrist.", NAMES)))
for a in keep:
    ck(f"헛알림이 없다 — {a[:36]}", not S.touch_hits("ACTION: " + a, NAMES),
       str(S.touch_hits("ACTION: " + a, NAMES)))

print("\n④ 얼굴 못 (이름 뒤 괄호)")
d3 = doc_with(["본처 stands still."])
C.fill(d3)
tags = {c["name"]: c.get("face_tag") for c in d3["characters"]}
for nm, ft in tags.items():
    ck(f"{nm} 얼굴 못이 생겼다", bool(ft), str(ft))
    ck(f"{nm} 얼굴 못이 {C.FACE_MAX}자 이내다", len(ft or "") <= C.FACE_MAX,
       f"{len(ft or '')}자")
S.fix_outfits(d3)
sub = next(l for l in d3["episodes"][0]["cuts"][0]["prompt"].split("\n")
           if l.startswith("SUBJECT:"))
print("      " + sub)
# ⭐⭐ 2026-08-20 — 여기에 얼굴을 박았더니 플로우가 80컷을 전부 거절했다.
#    "유명인의 동영상 생성에 관한 정책을 위반할 가능성이 있습니다."
#    기계는 `남편(55, square face…)` 를 '남편이라는 사람, 55살, 이 얼굴' 로
#    읽는다. 얼굴은 플로우 캐릭터가 잡는 몫이고 컷에는 **적지 않는다.**
ck("컷 프롬프트 이름 뒤에 얼굴을 안 붙인다",
   "본처(" not in sub and "남편(" not in sub, sub[:70])
ck("이름과 옷차림은 그대로 남는다", "본처" in sub and "남편" in sub)

d3b = doc_with(["본처 stands still."])
d3b["episodes"][0]["cuts"][0]["prompt"] = d3b["episodes"][0]["cuts"][0]["prompt"].replace(
    "SUBJECT: 본처 in a cardigan facing 남편 in a jacket.",
    "SUBJECT: 본처(52, oval face, low bun) in a cardigan "
    "facing 남편(55, square face) in a jacket.")
ck("얼굴을 박아 둔 컷을 검사가 잡는다",
   any("유명인" in b for b in S.check(d3b)), str(S.check(d3b))[:70])
S.fix_outfits(d3b)
sub_b = next(l for l in d3b["episodes"][0]["cuts"][0]["prompt"].split("\n")
             if l.startswith("SUBJECT:"))
ck("고쳐 주면 얼굴이 떼어진다", "(" not in sub_b, sub_b[:70])

print("\n④-2 한 줄에 같은 사람을 두 번 적은 SUBJECT")
d4 = doc_with(["본처 stands still."])
d4["episodes"][0]["cuts"][0]["prompt"] = (
    "SHOT: Medium two-shot.\n"
    "SUBJECT: 남편 in a black suit facing 본처 in a grey blouse "
    "facing 남편 in a black suit.\n"
    "ACTION: 본처 stands still.\nDIALOGUE: None.\n"
    "SETTING: Korean apartment living room.")
S.fix_subject_dup(d4)
sub4 = next(l for l in d4["episodes"][0]["cuts"][0]["prompt"].split("\n")
            if l.startswith("SUBJECT:"))
print("      " + sub4)
ck("같은 사람이 한 번만 남는다", sub4.count("남편") == 1, sub4)
ck("상대는 지우지 않는다", "본처" in sub4)
ck("마침표가 살아 있다", sub4.endswith("."))
n4 = S.fix_subject_dup(d4)
ck("두 번 돌려도 더 안 바뀐다", n4 == 0, f"{n4}줄")

print("\n④-3 한글 배역말을 영어 관계말로 바꾸는가 (2026-08-20 · 세 번째 사고)")
# ⚠️ 얼굴 설명을 다 뺐는데도 플로우가 막았다. 기계는 `남편` 이 무슨 뜻인지
#    몰라 **사람 이름**으로 읽는다 → 유명인 검사에 걸린다.
d5 = doc_with(["본처 steps in front of 남편, blocking the way."])
d5["episodes"][0]["cuts"][0]["prompt"] = (
    "SHOT: Medium two-shot.\n"
    "SUBJECT: 본처 in a cardigan facing 남편 in a jacket.\n"
    "ACTION: 본처 steps in front of 남편, blocking the way.\n"
    'DIALOGUE: 본처 (furious): "당신 진짜 제정신이야?"\n'
    "SETTING: Korean apartment living room.")
S.fix_names(d5)
pr5 = d5["episodes"][0]["cuts"][0]["prompt"]
for l in pr5.split("\n"):
    print("      " + l)
ck("SUBJECT 가 영어 관계말이 된다", "the wife" in pr5 and "the husband" in pr5)
ck("한글 배역말이 대사 밖에 안 남는다",
   not any(n in l for l in pr5.split("\n") for n in ("본처", "남편")
           if not l.startswith("DIALOGUE:")),
   pr5.split("\n")[1])
ck("따옴표 안 대사는 한국어 그대로다", '"당신 진짜 제정신이야?"' in pr5)
ck("말하는 사람 이름표도 영어가 된다", "the wife (furious)" in pr5, pr5.split("\n")[3][:40])
ck("두 번 돌려도 더 안 바뀐다", S.fix_names(d5) == 0)
ck("배역말 표를 남긴다", d5.get("_name_map", {}).get("본처") == "the wife")
d6 = doc_with(["본처 stands still."])
d6["characters"].append({"name": "동업자", "flow_prompt": "Korean man, 60 years old."})
ck("표에 없는 배역도 영어로 바꾼다",
   S.name_map(d6).get("동업자") == "the business partner", str(S.name_map(d6)))

print("\n⑤ 후킹 검사")
ok = doc_with(["본처 stands still."])
ck("제대로 된 후킹은 조용하다", not S.hook_warn(ok), str(S.hook_warn(ok)))
bad = doc_with(["본처 stands still."])
bad["episodes"][0]["hook"] = ""
ck("후킹이 비면 알린다", any("비었다" in w for w in S.hook_warn(bad)))
bad2 = doc_with(["본처 stands still."])
bad2["episodes"][0]["hook"] = "집을 나가는 남편"
ck("상태로 끝나면 알린다", any("상태로 끝났다" in w for w in S.hook_warn(bad2)),
   str(S.hook_warn(bad2)))
bad3 = doc_with(["본처 stands still."])
bad3["episodes"][0]["hook"] = "남편이 집을 나간 충격 진실 이야기다"
ck("밋밋한 말을 알린다", any("밋밋한" in w for w in S.hook_warn(bad3)))
bad4 = doc_with(["본처 stands still."])
bad4["episodes"][0]["hook"] = "가" * (S.HOOK_MAX + 1) + "다"
ck("너무 길면 알린다", any("넘음" in w for w in S.hook_warn(bad4)))
bad5 = doc_with(["본처 stands still."])
bad5["episodes"][0]["yt_title"] = ""
ck("유튜브 제목이 비면 알린다", any("yt_title" in w for w in S.hook_warn(bad5)))

print("\n⑥ 실제 대본(S001)으로도 조용한가")
p = ROOT / "data" / "series" / "S001.json"
if p.exists():
    real = json.loads(p.read_text(encoding="utf-8"))
    ck("16화 모두 후킹이 있다",
       all((e.get("hook") or "").strip() for e in real["episodes"]))
    ck("16화 모두 유튜브 제목이 있다",
       all((e.get("yt_title") or "").strip() for e in real["episodes"]))
    ck("후킹 알림이 하나도 없다", not S.hook_warn(real), str(S.hook_warn(real)[:2]))
    names = [c["name"] for c in real["characters"]]
    left = [f"{e['no']}-{c['n']}" for e in real["episodes"] for c in e["cuts"]
            for l in c["prompt"].split("\n") if l.startswith("ACTION:")
            and S.touch_hits(l, names)]
    ck("사람에게 닿는 컷이 하나도 없다", not left, " ".join(left))
    dup = [f"{e['no']}-{c['n']}" for e in real["episodes"] for c in e["cuts"]
           for l in c["prompt"].split("\n")
           if l.startswith("SUBJECT:") and l.count(" facing ") > 1]
    ck("한 줄에 같은 사람을 두 번 적은 곳이 없다", not dup, " ".join(dup))
    ck("컷에 얼굴을 적어 둔 곳이 없다 (정책에 막힌다)",
       not [1 for e in real["episodes"] for c in e["cuts"]
            for l in c["prompt"].split("\n") if l.startswith("SUBJECT:")
            and any(re.search(rf"(?<![\w가-힣]){re.escape(n)}\(", l) for n in names)])
    ko = [c["name"] for c in real["characters"]]
    ck("컷 프롬프트 대사 밖에 한글 배역말이 없다",
       not [1 for e in real["episodes"] for c in e["cuts"]
            for l in c["prompt"].split("\n")
            if not l.startswith("DIALOGUE:") and any(n in l for n in ko)])
    ck("모든 컷이 머리말로 시작한다",
       all(c["prompt"].startswith(S.HEAD_FIX)
           for e in real["episodes"] for c in e["cuts"]))
    ck("머리말이 겹쳐 들어간 컷이 없다",
       all(c["prompt"].count(S.HEAD_FIX) == 1
           for e in real["episodes"] for c in e["cuts"]))
else:
    print("   (S001 이 없어 건너뛴다)")

print("\n" + "─" * 52)
if FAIL:
    print(f"❌ 닿는 동작·후킹: {len(FAIL)}군데 틀렸다")
    for f in FAIL:
        print("   - " + f)
    sys.exit(1)
print("✅ 닿는 동작·후킹: 전부 통과")
