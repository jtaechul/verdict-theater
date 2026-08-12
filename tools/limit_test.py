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
print("─" * 52)
print("✅ 생성 상한: 정상" if ok else "❌ 생성 상한: 문제 있음")
sys.exit(0 if ok else 1)
