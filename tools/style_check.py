#!/usr/bin/env python3
"""그림 프롬프트의 화풍이 정해진 대로인지 본다 (인물=애니 · 배경=사진). 인터넷 0회 · 0원 · 1초.

    python3 tools/style_check.py

왜 이 검사가 있는가 (2026-08-12)
    손님 지적: "우리는 실사로 가기로 했는데 애니메이션으로 바꾼 거야?
                나한테 말도 안 하고?"

    맞는 지적이었다. 원인은 이랬다 —
      · 배경 프롬프트(docs/bg-prompts.md)는 18개 전부 'Photorealistic' 로
        못 박고 'Not an illustration, not anime' 까지 적어 뒀다.
      · 그런데 **인물 프롬프트에는 화풍이 한 글자도 없었다.** 그냥
        "캐릭터 시트 한 장" 이었다. '캐릭터 시트' 라고만 하면 AI 는 애니를 그린다.
      · 한쪽에만 적어 두면 이렇게 조용히 갈라진다. 눈으로는 못 잡는다.

    ⭐ 채널 화풍 (손님 결정 2026-08-12) — **인물은 애니, 배경은 사진**
         인물: 반실사 애니. 싼 flash 로도 쓸 만해 장당 197원 → 57원이 된다.
               회차마다 얼굴을 바꾸므로 벌 수만큼 그 차이가 곱해진다.
         배경: 사진 그대로. 픽사베이·픽셀스에서 0원으로 받는다.
       배경은 깔릴 때 14px 흐려지고 22% 어두워지므로 두 화풍이 안 겉돈다.
       다만 **눈 큰 소녀풍(모에)이면 반드시 겉돈다** — 그래서 그것도 막는다.

    이 검사는 어느 한쪽이 몰래 뒤집히는 것을 막는다. 화풍을 아예 안 적는 것도
    막는다 — 안 적으면 AI 가 알아서 정하고, 그게 이번 사고의 원인이었다.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import assets_gen as G                                # noqa: E402

ok = True


def bad(msg):
    global ok
    ok = False
    print(f"   ❌ {msg}")


# 인물 = 애니를 시켜야 한다 / 배경 = 실사를 시켜야 한다
CHAR_MUST = ("애니", "극화체", "그림")            # 인물 프롬프트에 있어야 하는 말
CHAR_BAN = ("실사 사진이다", "사진처럼")           # 인물 프롬프트에 있으면 안 되는 말
BG_MUST = ("실사", "사진")
# ⚠️ 2026-08-14 — 프롬프트를 다시 쓰면서 **같은 뜻을 다른 말로** 적었다.
#    옛말: "눈을 크게 그리거나 어려 보이게 만들지 않는다"
#    새말: "눈은 얼굴 가로폭의 5분의 1 이하 크기로, 실제 사람 눈 비율대로 그린다"
#    새말이 더 낫다(숫자라서 모델이 따르기 쉽다). 검사는 **뜻**을 보아야지
#    문구를 외워서는 안 된다 — 문구만 보면 좋아진 프롬프트를 불합격시킨다.
#    그래서 '이 중 하나라도 있으면 통과' 로 바꾼다.
MOE_BAN = ("눈을 크게", "어려 보이게", "실제 사람 눈 비율", "5분의 1 이하")

print("① 인물 프롬프트가 애니를 시키는가 (7명 전부)")
for code in sorted(G.CHAR_LOOK):
    p = G.char_sheet_prompt(code) + G.char_sheet_prompt(code, 'full')
    if not any(w in p for w in CHAR_MUST):
        bad(f"{code}: 화풍을 안 적었다 — 안 적으면 AI 가 알아서 정한다(이번 사고의 원인)")
    elif any(w in p for w in CHAR_BAN):
        bad(f"{code}: 인물에 실사를 시키고 있다 — 손님 결정은 '인물은 애니' 다")
    elif not any(w in p for w in MOE_BAN):
        # 눈 큰 소녀풍이 나오면 흐린 법정 사진 위에서 반드시 겉돈다
        bad(f"{code}: 모에풍을 막는 문장이 없다 — 배경 사진 위에서 겉돈다")
    else:
        print(f"   ✅ {code}")

print()
print("② 인물 프롬프트가 최고 화질을 요구하는가")
# 2026-08-12 실측: 제가 손님께 드린 프롬프트에는 해상도·디테일 지시가
# **하나도 없었다.** 배경 쪽에는 'High detail … at least 1920x1080' 이 있었는데.
for code in sorted(G.CHAR_LOOK):
    p = G.char_sheet_prompt(code) + G.char_sheet_prompt(code, 'full')
    # 옛말 "최고 화질" / 새말 "머리카락 한 올까지 또렷하게" — 뜻이 같다
    if not any(w in p for w in ("최고 화질", "고화질", "또렷하게 보이고",
                                "초점이 맞아", "한 올까지")):
        bad(f"{code}: 화질 지시가 없다")
        break
else:
    print("   ✅ 7명 전부 최고 화질을 요구한다")

print()
print("③ 인물마다 옷 색이 다른가 (덮어쓰기가 되살아나지 않았는가)")
# 예전에 시트 프롬프트가 "의상은 남색 상의 + 검정 하의" 로 **전원을 덮어썼다.**
# 그래서 아버지와 차남이 같은 사람처럼 보였다.
for code, look in sorted(G.CHAR_LOOK.items()):
    p = G.char_sheet_prompt(code) + G.char_sheet_prompt(code, 'full')
    if "인물 의상은" in p or "의상은 남색" in p:
        bad(f"{code}: 옷 색을 덮어쓰는 문장이 돌아왔다 — CHAR_LOOK 이 무의미해진다")
        break
else:
    colours = [look for look in G.CHAR_LOOK.values()]
    if len(set(colours)) != len(colours):
        bad("CHAR_LOOK 에 똑같은 차림이 둘 있다 — 멀리서 같은 사람으로 보인다")
    else:
        print(f"   ✅ {len(colours)}명 전부 다른 차림이고, 덮어쓰는 문장이 없다")

print()
print("④ 배경 프롬프트도 실사인가 (인물과 갈라지면 한 화면에서 겉돈다)")
bp = G.bg_prompt("court_room")
if not any(w in bp for w in BG_MUST):
    bad("배경 프롬프트에 실사 지시가 없다")
else:
    print("   ✅ 배경도 실사")

doc = ROOT / "docs" / "bg-prompts.md"
if doc.exists():
    t = doc.read_text(encoding="utf-8").lower()
    n_real = t.count("photorealistic")
    n_ban = t.count("not an illustration, not anime")
    if n_real < 18 or n_ban < 18:
        bad(f"docs/bg-prompts.md: 실사 {n_real}곳 · 애니금지 {n_ban}곳 (18개여야 한다)")
    else:
        print(f"   ✅ docs/bg-prompts.md 18개 전부 Photorealistic + 애니 금지")

print()
print("⑤ 손님께 드리는 인물 프롬프트 문서도 같은 화풍인가")
cd = ROOT / "docs" / "char-prompts.md"
if not cd.exists():
    bad("docs/char-prompts.md 가 없다 — 손님이 복사해 쓸 프롬프트가 저장소에 없다")
else:
    t = cd.read_text(encoding="utf-8")
    low = t.lower()
    for want, why in (("semi-realistic anime", "애니 지시"),
                      ("not a photograph", "실사 금지"),
                      ("no chibi, no moe", "모에 금지"),
                      ("at least", "해상도 지시"),
                      ("no heavy black outline", "굵은 검은 윤곽선 금지")):
        n = low.count(want)
        if n < 7:
            bad(f"{why}('{want}')가 {n}곳뿐이다 — 7명 전부에 있어야 한다")
    # 사진 용어가 인물 블록에 남아 있으면 화풍이 다시 섞인다
    for stale in ("photorealistic studio", "film grain", "85mm portrait lens",
                  "real photographs of a real person"):
        if stale in low:
            bad(f"사진 용어가 남아 있다: '{stale}'")
    if ok:
        print("   ✅ 7개 블록 전부 애니 + 모에 금지 + 해상도 지시가 있다")

print()
print("─" * 52)
print("✅ 그림 화풍(인물 애니 · 배경 사진): 정상" if ok
      else "❌ 그림 화풍(인물 애니 · 배경 사진): 문제 있음")
sys.exit(0 if ok else 1)
