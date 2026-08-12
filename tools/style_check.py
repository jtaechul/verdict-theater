#!/usr/bin/env python3
"""그림 프롬프트가 **실사**를 시키는지 본다. 인터넷 0회 · 0원 · 1초.

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

    채널 화풍은 **실사**다. 배경이 진짜 사진(픽사베이·픽셀스)이라 인물이
    애니면 한 화면에서 겉돈다. 이 검사가 그 결정을 지킨다.
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


# 실사를 시키는 말 / 애니를 부르는 말
REAL_KO = ("실사", "사진")
BAN_KO = ("애니", "일러스트", "만화", "수채화", "유화")
REAL_EN = ("photoreal", "photograph", "film still")
BAN_EN = ("anime", "cartoon", "manga", "illustration style", "watercolor")

print("① 인물 프롬프트가 실사를 시키는가 (7명 전부)")
for code in sorted(G.CHAR_LOOK):
    p = G.char_sheet_prompt(code)
    low = p.lower()
    if not any(w in p for w in REAL_KO) and not any(w in low for w in REAL_EN):
        bad(f"{code}: 화풍을 안 적었다 — 안 적으면 AI 는 애니를 그린다")
        continue
    hit = [w for w in BAN_KO if w in p and f"{w}가 아니" not in p and f"{w}·" not in p]
    hit += [w for w in BAN_EN if w in low]
    # '일러스트·애니가 아니다' 처럼 **금지하는 문장**은 걸리면 안 된다
    if hit and "아니다" not in p:
        bad(f"{code}: 애니를 부르는 말이 있다 — {hit}")
    else:
        print(f"   ✅ {code}")

print()
print("② 인물 프롬프트가 최고 화질을 요구하는가")
# 2026-08-12 실측: 제가 손님께 드린 프롬프트에는 해상도·디테일 지시가
# **하나도 없었다.** 배경 쪽에는 'High detail … at least 1920x1080' 이 있었는데.
for code in sorted(G.CHAR_LOOK):
    p = G.char_sheet_prompt(code)
    if "최고 화질" not in p and "고화질" not in p:
        bad(f"{code}: 화질 지시가 없다")
        break
else:
    print("   ✅ 7명 전부 최고 화질을 요구한다")

print()
print("③ 인물마다 옷 색이 다른가 (덮어쓰기가 되살아나지 않았는가)")
# 예전에 시트 프롬프트가 "의상은 남색 상의 + 검정 하의" 로 **전원을 덮어썼다.**
# 그래서 아버지와 차남이 같은 사람처럼 보였다.
for code, look in sorted(G.CHAR_LOOK.items()):
    p = G.char_sheet_prompt(code)
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
if not any(w in bp for w in REAL_KO):
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
    n = low.count("photorealistic")
    if n < 7:
        bad(f"실사 지시가 {n}곳뿐이다 — 7명 전부에 있어야 한다")
    import re
    for w in ("anime", "cartoon", "manga", "illustration"):
        # '금지' 문장 안에 있는 것은 정상이다 — 바로 앞에 not/no 가 붙은 것만 봐준다.
        # ('not a cartoon' 처럼 관사가 끼는 경우가 있어 낱말 수로 세면 틀린다)
        loose = [m.start() for m in re.finditer(w, low)
                 if not re.search(r"\b(not|no)\b[ a-z]{0,4}$", low[:m.start()])]
        if loose:
            bad(f"'{w}' 가 금지 문장 밖에서 {len(loose)}번 쓰였다")
    if low.count("at least") < 7:
        bad("해상도 지시(at least …)가 7명 전부에 있지 않다")
    if ok:
        print("   ✅ 7개 블록 전부 실사 + 해상도 지시가 있고, 애니를 부르지 않는다")

print()
print("─" * 52)
print("✅ 그림 화풍(실사): 정상" if ok else "❌ 그림 화풍(실사): 문제 있음")
sys.exit(0 if ok else 1)
