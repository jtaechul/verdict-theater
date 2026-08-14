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
elif "인물 위로 회색 막대" not in src or "상반신이 밑변에 닿은" not in src:
    bad("자기시험에 '막대를 그은 가짜 그림' 이 없다 — 가장 중요한 실패다")
else:
    print("   ✅ 가짜 그림 6장(정상·막대·붙음·얼굴잘림·밑변닿음·로고)으로 스스로를 시험한다")

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
print("⑦ ⭐ **잘 나온 시트를 계속 통과시키는가** (기준을 조이다 좋은 걸 버리지 않게)")
# ⚠️ 2026-08-14 — 여기 있던 검사는 "프롬프트에 적은 픽셀 숫자대로 그리면 통과하는가"
#    를 산수로 풀고 있었다. **그 전제가 틀렸다.** 모델은 픽셀 숫자를 읽지 않는다:
#        요구 세로 950 → 실제  992~1168 | 요구 세로 760 → 실제 1160~1264
#        요구  폭 620 → 실제  768~840  | 요구  폭 520 → 실제  752~760
#    작게 적었더니 오히려 더 크게 그렸다. 그 산수는 통과했는데 진짜 시트는
#    떨어졌으니, 있으나 마나가 아니라 **틀린 답을 자신 있게 알려 주는 자**였다.
#
#    산수 대신 **실물**로 지킨다. 잘 나온 시트가 저장소에 있으므로, 그것이
#    계속 통과하는지만 보면 된다. 누가 기준을 조여 좋은 시트를 떨어뜨리면
#    (2026-08-14 에 두 번 그랬다) 여기서 바로 걸린다.
GOOD = ROOT / "assets" / "sheets" / "M70.png"
if not GOOD.exists():
    print(f"   (기준 시트 {GOOD.name} 가 없어 건너뜀)")
elif SG is None:
    bad("검사기가 없어 기준 시트를 재지 못한다")
else:
    kind = G.sheet_kind(GOOD)
    if kind is None:
        print(f"   (기준 시트가 옛 격자 시트라 건너뜀)")
    elif SG.check(GOOD, kind, verbose=False) != 0:
        bad(f"{GOOD.name} 은 눈으로 확인한 **잘 나온 시트**인데 불합격이 나온다 "
            "— 기준이 너무 빡빡해졌다. 자세한 까닭은 "
            f"`python3 src/sheet_gate.py {GOOD.relative_to(ROOT)} --kind {kind}`")
    else:
        print(f"   ✅ {GOOD.name}(눈으로 확인한 좋은 시트)이 통과한다")

print()
print("⑧ 기대치를 **손으로 적지 않고 칸에서 계산**하는가")
# ⚠️ 폭 820 · 키 1250 을 손으로 적어 뒀다가 멀쩡한 시트(폭 888 · 키 1264)를
#    두 번 떨어뜨렸다. 근거 없이 적은 숫자였다. 이제는 칸 크기에서 계산한다 —
#    그래야 줄·열이 바뀌어도 기대치가 저절로 따라온다.
sg_src = (ROOT / "src" / "sheet_gate.py").read_text(encoding="utf-8")
if "def _spec(" not in sg_src or '"w_max": int(tw)' not in sg_src:
    bad("기대치를 칸에서 계산하지 않는다 — 숫자를 손으로 적으면 또 어긋난다")
else:
    for k, s in SG.KINDS.items():
        tw, th = s["tile"]
        if s["w_max"] != tw or s["h_range"][1] != th:
            bad(f"{k}: 위 한계가 칸 크기와 다르다")
        else:
            print(f"   ✅ {k}: 칸 {tw}x{th} 에서 계산 "
                  f"(키 {s['h_range'][0]}~{s['h_range'][1]} · 폭 ≤{s['w_max']})")

print()
print("⑨ 아직 있지도 않은 것을 피하느라 화면을 버리지 않는가")
# ⚠️ 하단 700px 을 '제미나이 로고 자리' 로 비워 두라고 시켰는데, 시트 아홉 장을
#    다 들여다보니 **로고는 하나도 없었다.** 옛 시트 구석의 비초록 4~7% 는
#    우리가 그으라고 시킨 마젠타 격자선이었다. 없는 것을 피하려고 화면 5분의
#    1을 버렸고, 그 때문에 멀쩡한 시트가 두 번 떨어졌다.
if "LOGO_BAND" in sg_src and "하단 {LOGO_BAND}px 안 인물 픽셀" in sg_src:
    bad("아직도 하단 밴드를 비우라고 요구한다 — 그 자리에 로고는 없다")
else:
    print("   ✅ 밴드를 미리 버리지 않고, 로고 같은 덩어리가 있으면 그때 잡는다")

print()
print("─" * 52)
print("✅ 시트 검사 장치: 정상" if ok else "❌ 시트 검사 장치: 문제 있음")
sys.exit(0 if ok else 1)
