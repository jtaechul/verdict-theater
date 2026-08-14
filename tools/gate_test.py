#!/usr/bin/env python3
"""⭐ **시트를 만든 뒤 반드시 재는가**를 지킨다. 인터넷 0회 · 0원 · 몇 초.

    python3 tools/gate_test.py

왜 이 검사가 있는가 (2026-08-14)
    손님: "니가 만든 명령 프롬프트가 문제가 있었던 게 맞지?" — 맞았다.
    그런데 프롬프트가 부족했던 것보다 **받은 시트를 재보지 않은 것**이 더 큰
    잘못이었다. 재는 코드는 열 줄이면 됐는데 그 열 줄을 안 써서
    목 잘린 인물이 방송에 나가고, 자르는 코드를 일곱 번 고쳐 일곱 번 다 실패했다.

    ⭐ 핵심규칙(CLAUDE.md): **프롬프트에 규칙을 적었으면 지켜졌는지 재는 코드도
       같이 만든다. 못 재는 규칙은 규칙이 아니라 희망이다.**
    이 검사가 그 규칙이 코드에서 살아 있는지를 지킨다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

ok = True


def bad(msg):
    global ok
    ok = False
    print(f"   ❌ {msg}")


print("① 시트를 재는 자(sheet_gate)가 있는가")
try:
    import sheet_gate as SG
    print(f"   ✅ 있다 (기준 {len([x for x in dir(SG) if x.isupper()])}개)")
except Exception as e:                                  # noqa: BLE001
    bad(f"없거나 깨졌다: {e}")
    SG = None

print()
print("② ⭐ 그 자가 **진짜 맞는지 스스로 시험**하는가 (가짜 그림으로)")
# ⚠️ 자를 만들어 놓고 그 자가 맞는지 안 재면 같은 실수다. 실제로 처음 만든 자는
#    가로·세로를 바꿔 써서 막대가 뻔히 그어져 있는데도 0개로 나왔다.
#    자기시험이 그것을 잡았다. 이 기능이 사라지면 안 된다.
src = (ROOT / "src" / "sheet_gate.py").read_text(encoding="utf-8") if SG else ""
if "def selftest" not in src:
    bad("자기시험이 없다 — 자가 틀려도 아무도 모른다")
elif "인물 위로 회색 막대" not in src:
    bad("자기시험에 '막대를 그은 가짜 그림' 이 없다 — 가장 중요한 실패다")
else:
    print("   ✅ 가짜 그림 3장(정상·막대·붙음)으로 스스로를 시험한다")

print()
print("③ ⭐ 사람을 **가로지르는 줄**을 잡는가 (붙어 버려도)")
# ⚠️ '가늘고 긴 덩어리' 검사만으로는 못 잡는다. 막대가 사람과 붙는 순간
#    그 덩어리는 더 이상 가늘지 않다. 그런데 예전 사고가 정확히 그 경우였다.
if "def spanning" not in src:
    bad("가로지르는 줄을 따로 재지 않는다 — 붙어 버린 선을 놓친다")
elif "mask.shape[axis]" not in src:
    bad("가로·세로 기준이 뒤집혀 있다 — 그러면 영원히 0개만 나온다")
else:
    print("   ✅ 줄마다 몸 픽셀이 얼마나 퍼졌는지 재서 잡는다")

print()
print("④ 시트를 만든 **직후** 재는가 (나중에 재면 이미 늦다)")
ag = (ROOT / "src" / "assets_gen.py").read_text(encoding="utf-8")
fn = ag[ag.index("def cmd_images("):]
fn = fn[:fn.index("\ndef ", 10)]
if "sheet_gate" not in fn:
    bad("만들고 나서 안 잰다 — 나쁜 시트가 그대로 컷아웃까지 간다")
elif "process_sheet" in fn and fn.index("sheet_gate") > fn.index("process_sheet"):
    bad("자르고 나서 잰다 — 순서가 거꾸로다. 자르기 전에 재야 한다")
else:
    print("   ✅ 만든 즉시 재고, 걸리면 자르지 않는다")

if "bad" not in fn or "rename" not in fn:
    bad("걸린 시트를 치워 두지 않는다 — 다음 실행에서 또 쓰게 된다")
else:
    print("   ✅ 걸린 시트는 assets/sheets/bad/ 로 치운다")

print()
print("⑤ 프롬프트가 **칸 선을 요구하지 않는가** (선이 없으면 사고도 없다)")
# ⚠️ 선이 인물 머리에 겹쳐 그려져 목이 잘렸다. 선과 머리가 같은 픽셀이라
#    지워도 남겨도 안 됐다. 그래서 선을 아예 요구하지 않기로 했다.
import assets_gen as G                                  # noqa: E402
for kind in ("face", "full"):
    p = G.char_sheet_prompt("M70", kind)
    for word in ("마젠타", "격자", "칸을 나누는", "칸 선"):
        if word in p:
            bad(f"{kind} 프롬프트에 '{word}' 가 남아 있다 — 선을 부르는 말이다")
    if "{LOOK}" in p:
        bad(f"{kind} 프롬프트에 {{LOOK}} 이 안 채워졌다")
else:
    if ok:
        print("   ✅ 두 프롬프트 모두 선을 요구하지 않는다")

print()
print("⑥ 인물 하나가 **두 장**으로 나뉘어 있는가 (한 장에 18칸이 붕괴의 뿌리였다)")
if 'char_sheet_prompt(code, kind)' not in ag:
    bad("시트 종류를 안 나눈다 — 한 장에 18칸을 다시 우겨넣게 된다")
elif '"_full"' not in ag:
    bad("전신 시트 파일 이름 규칙이 없다")
else:
    print("   ✅ 얼굴6+상반신6 / 전신5 두 장으로 나눈다")

print()
print("⑦ 프롬프트에 적은 숫자대로 그리면 **검사를 통과하는가** (산수로 미리 본다)")
# ⚠️ 2026-08-14 — 265원짜리 시범 시트가 넷에서 걸렸다(간격 88 · 가장자리 64 ·
#    밴드 92px 침범 · 폭 840). 뿌리는 프롬프트 숫자와 검사 기준이 **서로 안 맞는
#    것**이었는데, 그걸 아무도 안 재고 있었다. 그림을 뽑아 봐야만 알 수 있었으니
#    확인 한 번에 265원이 든 셈이다.
#
#    이제는 종이 위에서 먼저 푼다. 프롬프트에 적힌 숫자를 그대로 읽어
#    **두 끝**을 다 넣어 본다:
#      ⓐ 모델이 시킨 대로 그렸을 때 (숫자 그대로)
#      ⓑ 모델이 크게 그렸을 때 (실측 1.23배 — 시범 시트에서 잰 값)
#    두 경우 모두 검사(G4 간격 · G5 가장자리 · G6 밴드 · G8 크기)를 지나야 한다.
import re                                              # noqa: E402
import sheet_gate as SG                                # noqa: E402

OVER = 1.23        # 실측: 세로 950 요구 → 1168 · 폭 720 요구 → 840
EDGE_SHARE = 0.12  # 실측: 남는 가로 폭 552 중 가장자리로 간 것 64 = 12%


def num(text, pat, label):
    m = re.search(pat, text)
    if not m:
        bad(f"프롬프트에서 '{label}' 숫자를 못 찾았다 — 산수를 할 수 없다")
        return None
    return int(m.group(1))


for kind in ("face", "full"):
    p = G.char_sheet_prompt("M70", kind)
    K = SG.KINDS[kind]
    rows, cols = len(K["bands"]), max(K["bands"])

    band = num(p, r"맨 아래쪽 (\d+)픽셀", "하단 밴드")
    edge_w = num(p, r"끝에서 (\d+)픽셀 이상", "가장자리 여백")
    hs = [int(x) for x in re.findall(r"세로 \*\*(\d+)픽셀\*\*", p)]
    ws = [int(x) for x in re.findall(r"폭은 (\d+)픽셀을 넘지 않는다", p)]
    if band is None or edge_w is None or not hs or not ws:
        continue

    h_ask, w_ask = max(hs), max(ws)
    for name, f in (("시킨 대로", 1.0), (f"{OVER}배 크게", OVER)):
        h, w = h_ask * f, w_ask * f

        # 세로 — 위 여백과 하단 밴드를 뺀 자리를 줄들이 나눠 쓴다
        room_v = SG.H_EXP - edge_w - band
        gap_v = (room_v - rows * h) / max(1, rows - 1)
        # 가로 — 남는 폭을 가장자리 둘과 사이 간격들이 나눠 갖는다.
        #        모델은 가장자리를 가장 야박하게 준다(실측 12%씩).
        slack_h = SG.W_EXP - cols * w
        edge_got = slack_h * EDGE_SHARE
        gap_h = (slack_h - 2 * edge_got) / max(1, cols - 1)

        lo, hi = K["h_range"]
        probs = []
        if gap_v < SG.MIN_GAP or gap_h < SG.MIN_GAP:
            probs.append(f"G4 간격 세로{gap_v:.0f}·가로{gap_h:.0f}(≥{SG.MIN_GAP})")
        if edge_got < SG.MIN_EDGE:
            probs.append(f"G5 가장자리 {edge_got:.0f}(≥{SG.MIN_EDGE})")
        if gap_v < 0:
            probs.append(f"G6 하단 밴드 침범 — 줄이 안 들어간다")
        if not (lo <= h <= hi):
            probs.append(f"G8 키 {h:.0f}(기준 {lo}~{hi})")
        if w > K["w_max"]:
            probs.append(f"G8 폭 {w:.0f}(기준 {K['w_max']} 이하)")

        if probs:
            bad(f"{kind} · {name} 그리면 걸린다: " + " · ".join(probs))
        else:
            print(f"   ✅ {kind} · {name}: 간격 세로{gap_v:.0f}·가로{gap_h:.0f} · "
                  f"가장자리{edge_got:.0f} · 키{h:.0f} · 폭{w:.0f}")

    # 요구하는 밴드가 재는 밴드보다 커야 넘쳐도 버틸 여유가 생긴다
    if band <= SG.LOGO_BAND:
        bad(f"{kind}: 하단 밴드를 {band} 요구하고 {SG.LOGO_BAND} 로 잰다 — "
            "여유가 0이라 조금만 넘쳐도 걸린다")
    else:
        print(f"   ✅ {kind}: 밴드를 {band} 요구하고 {SG.LOGO_BAND} 로 잰다 "
              f"— {band - SG.LOGO_BAND}px 이 버텨 준다")

print()
print("─" * 52)
print("✅ 시트 검사 장치: 정상" if ok else "❌ 시트 검사 장치: 문제 있음")
sys.exit(0 if ok else 1)
