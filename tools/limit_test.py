#!/usr/bin/env python3
"""버튼의 '최대 생성 개수' 가 실제 인원과 맞는지 본다. 인터넷 0회 · 0원 · 1초.

    python3 tools/limit_test.py

왜 이 검사가 있는가 (2026-08-12)
    [그림·소리 만들기] → '등장인물 전부' 의 상한 기본값이 **6** 이었다.
    그런데 배우는 **7명**이다. 그래서 버튼을 눌러도 한 명이 말없이 빠졌고,
    화면에는 "6개 생성" 만 찍혀 다 된 줄 알게 된다.

    돈을 막으려고 둔 상한이, 일을 반만 하게 만들고 그것을 숨기고 있었다.
    상한은 그대로 두되 **숫자를 사람 수에 맞추고, 잘릴 때는 크게 알린다.**

    배우가 늘거나 줄면 이 검사가 먼저 걸린다.
"""

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import assets_gen as G                                # noqa: E402

ok = True


def bad(msg):
    global ok
    ok = False
    print(f"   ❌ {msg}")


n = len(G.CHAR_LOOK)
print(f"① 버튼 기본 상한이 배우 수({n}명) 이상인가")
doc = yaml.safe_load((ROOT / ".github" / "workflows" / "build-assets.yml")
                     .read_text(encoding="utf-8"))
on = doc.get("on") if isinstance(doc.get("on"), dict) else doc.get(True)
spec = ((on or {}).get("workflow_dispatch") or {}).get("inputs", {}).get("limit", {})
raw = str(spec.get("default", ""))
if not raw.isdigit():
    bad(f"기본값을 못 읽었다: {raw!r}")
else:
    lim = int(raw)
    if lim == 0:
        print("   ✅ 0(무제한) — 다 만든다")
    elif lim < n:
        bad(f"기본 상한 {lim} < 배우 {n}명 — 눌러도 {n - lim}명이 빠진다")
    else:
        print(f"   ✅ 기본 상한 {lim} ≥ 배우 {n}명")

print()
print("② 상한에 걸려 잘릴 때 **크게 알리는가** (조용히 자르면 못 알아챈다)")
src = (ROOT / "src" / "assets_gen.py").read_text(encoding="utf-8")
i = src.find("if args.limit")
blk = src[i:i + 700] if i >= 0 else ""
if not blk:
    bad("상한 처리 코드를 못 찾았다")
elif "jobs[:args.limit]" in blk and "안 만든다" not in blk:
    bad("조용히 자른다 — 무엇이 빠졌는지 화면에 안 나온다")
else:
    print("   ✅ 무엇이 빠졌는지 이름까지 찍는다")

print()
print("③ 첫 생성에서는 판사도 함께 만드는가")
# FIXED_FACE 는 '회차마다 얼굴을 바꾸지 않는다' 는 뜻이지 '아예 안 만든다' 가 아니다.
# 이 둘을 헷갈리면 판사만 영원히 회색 실루엣으로 남는다.
j = src.find("if args.variant > 1:")
k = src.find("for code in codes:", j)
if j < 0 or k < 0:
    bad("판사 건너뛰기 코드를 못 찾았다")
else:
    guard = src[j:k]
    if "FIXED_FACE" not in guard:
        bad("판사 고정 처리가 없다")
    elif "args.variant > 1" not in src[max(0, j - 5):j + 30]:
        bad("첫 생성(variant=1)에서도 판사를 건너뛴다 — 판사가 영영 안 만들어진다")
    else:
        print("   ✅ 두 번째 벌부터만 건너뛴다 (첫 장은 판사도 만든다)")

print()
print("④ 배우 수와 시트 칸 수가 서로 맞는가")
poses = [c for c in G.CELL_ORDER if c]
if len(G.CELL_ORDER) != 18:
    bad(f"시트가 {len(G.CELL_ORDER)}칸이다 — 3열 6행 = 18칸이어야 한다")
elif G.CELL_ORDER[-1] is not None:
    bad("18번 칸이 비어 있지 않다 — 거기가 제미나이 워터마크 자리다")
else:
    print(f"   ✅ 18칸 중 {len(poses)}칸이 포즈, 마지막 1칸은 비움 "
          f"(배우 {n}명 × {len(poses)} = {n * len(poses)}장)")

print()
print("⑤ 시트 두 장이 **합쳐서** 필요한 포즈를 다 만드는가")
# ⚠️ 2026-08-14 — 시트를 얼굴12 + 전신5 두 장으로 나눴는데, 자르는 쪽은 여태
#    옛 17개짜리 이름표 하나만 쓰고 있었다. 그러면 12명짜리 시트에 17개를
#    짝지으려다 이름이 밀리고, "모자란다" 며 **격자 방식으로 물러선다** —
#    선이 없는 시트를 격자로 자르면 한 칸에 사람이 둘씩 들어간다(실측).
#    그림을 265원 주고 뽑은 **다음에야** 드러날 일이라 여기서 미리 막는다.
need = [c for c in G.CELL_ORDER if c]
got = G.SHEET_POSES["face"] + G.SHEET_POSES["full"]
if sorted(got) != sorted(need):
    miss = sorted(set(need) - set(got))
    extra = sorted(set(got) - set(need))
    bad("두 시트를 합쳐도 포즈가 안 맞는다"
        + (f" · 빠진 것 {miss}" if miss else "")
        + (f" · 없는 것 {extra}" if extra else ""))
elif len(got) != len(set(got)):
    bad("두 시트에 같은 포즈가 겹쳐 들어 있다 — 한쪽이 다른 쪽을 덮어쓴다")
else:
    print(f"   ✅ 얼굴 {len(G.SHEET_POSES['face'])} + 전신 "
          f"{len(G.SHEET_POSES['full'])} = {len(got)}개, 필요한 것과 똑같다")

# 검사기가 세는 사람 수와 이름표 개수가 같아야 한다
import sheet_gate as SG                                    # noqa: E402
for k in ("face", "full"):
    if SG.KINDS[k]["n"] != len(G.SHEET_POSES[k]):
        bad(f"{k}: 검사기는 {SG.KINDS[k]['n']}명을 세는데 이름표는 "
            f"{len(G.SHEET_POSES[k])}개다")
    else:
        print(f"   ✅ {k}: 검사기가 세는 {SG.KINDS[k]['n']}명과 이름표 개수가 같다")

# 이름표 차례가 **프롬프트에 적은 차례**와 같아야 한다
# (확인할 열쇠가 없으면 이 차례대로 짝지어지므로, 어긋나면 이름이 통째로 밀린다)
ORDER_WORDS = {
    "face": ["무표정", "슬픔", "분노", "놀람", "냉담", "울음"],
    "full": ["똑바로 서기", "걷기", "뒷모습", "의자에 앉기", "바닥에 주저앉기"],
}
for k, words in ORDER_WORDS.items():
    p = G.char_sheet_prompt("M70", k)
    at = [p.find(w) for w in words]
    if -1 in at:
        bad(f"{k} 프롬프트에서 '{words[at.index(-1)]}' 를 못 찾았다")
    elif at != sorted(at):
        bad(f"{k} 프롬프트의 차례가 이름표 차례와 다르다 — 열쇠가 없으면 이름이 밀린다")
    else:
        print(f"   ✅ {k}: 프롬프트에 적힌 차례와 이름표 차례가 같다")

print()
print("⑥ 새 시트를 **격자로 자르려 들지 않는가** (선이 없는데 격자로 자르면 어긋난다)")
ag = (ROOT / "src" / "assets_gen.py").read_text(encoding="utf-8")
fn = ag[ag.index("def process_sheet("):ag.index("\ndef ", ag.index("def process_sheet(") + 10)]
if "kind in SHEET_POSES" not in fn or "raise RuntimeError" not in fn:
    bad("덩어리 방식이 실패하면 새 시트도 격자로 자르러 간다 — 반드시 어긋난다")
else:
    print("   ✅ 새 시트는 덩어리 방식이 실패하면 **멈춘다** (컷아웃을 안 만든다)")
if "glob(\"*.png\")" in fn.split("if kind in SHEET_POSES")[0]:
    bad("만든 개수를 폴더의 png 수로 센다 — 두 시트가 한 폴더를 써서 서로 속인다")
else:
    print("   ✅ 이번에 실제로 만든 것만 센다 (폴더 개수로 세지 않는다)")

print()
print("⑦ 저장소에 있는 시트를 **옛것/새것으로 바르게 가리는가**")
# ⚠️ 2026-08-14 — 처음엔 '18칸이 딱 맞는가' 로 갈랐는데, 선이 멀쩡히 있는 옛 시트
#    F70·M50B 가 18칸이 안 떨어져 **새 시트로 오해**됐다. 그러면 17명짜리 시트에
#    12개 이름표가 붙어 이름이 통째로 밀린다. 이제는 '선이 있는가' 를 잰다.
from PIL import Image                                      # noqa: E402
sheets = sorted((ROOT / "assets" / "sheets").glob("*.png"))
if not sheets:
    print("   (시트가 없어 건너뜀)")
for sp in sheets:
    k = G.sheet_kind(sp)
    try:
        grid = G.sheet_grid(Image.open(sp).convert("RGBA"))
    except Exception:                                       # noqa: BLE001
        grid = None
    if k == "face" and grid:
        bad(f"{sp.name}: 격자가 잡히는데 '새 시트' 로 봤다 — 이름표가 밀린다")
    else:
        n = len(G.SHEET_POSES.get(k) or [c for c in G.CELL_ORDER if c])
        print(f"   ✅ {sp.name:14s} → {k or '옛 격자 시트'} (포즈 {n}개)")

print()
print("─" * 52)
print("✅ 생성 상한: 정상" if ok else "❌ 생성 상한: 문제 있음")
sys.exit(0 if ok else 1)
