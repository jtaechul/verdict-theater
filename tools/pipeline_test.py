#!/usr/bin/env python3
"""[영상 만들기] 하나로 그림까지 다 되는지 본다. 인터넷 0회 · 0원 · 1초.

    python3 tools/pipeline_test.py

왜 이 검사가 있는가 (2026-08-12)
    손님 지적: "내가 영상 만들기 누르면 이미지 생성이 진행 안 된 건 진행을
                시켜야 되고, 완료된 거는 그 영상에 반영을 하는 알고리즘이
                미리 구축이 되어 있었어야 되잖아."

    맞는 말이었고, **반쪽만 돼 있었다.**
      · '없는 것을 만드는' 쪽은 있었다 (assets_gen images --what char)
      · **'있는 것을 반영하는' 쪽이 없었다.** cmd_images 는 새로 만든 시트만
        잘랐다(process_sheet). 시트가 이미 있으면 생성을 건너뛰는데,
        건너뛰면 **자르지도 않았다.**
    그래서 손님이 제미나이에서 뽑은 시트를 올려도 컷아웃이 안 생기고,
    무결성 검사가 "인물 그림 81장이 빠졌다" 며 영영 막는다.

    올바른 순서는 셋이다.
        ① 있는 시트를 컷아웃으로 반영 (0원)
        ② 그러고도 없는 것만 새로 만들기 (값 나감)
        ③ 방금 만든 것도 반영
    이 검사는 그 순서가 워크플로에 실제로 그렇게 적혀 있는지 본다.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import assets_gen as G                                # noqa: E402

ok = True


def bad(msg):
    global ok
    ok = False
    print(f"   ❌ {msg}")


print("① '있는 시트를 반영하는' 명령이 있는가")
if not hasattr(G, "cmd_sync"):
    bad("assets_gen 에 sync 가 없다 — 올린 시트가 영상에 반영될 길이 없다")
else:
    src = (ROOT / "src" / "assets_gen.py").read_text(encoding="utf-8")
    if 'if args.cmd == "sync"' not in src:
        bad("sync 를 등록만 하고 갈래를 안 만들었다 — 조용히 check 가 돈다")
    else:
        print("   ✅ assets_gen.py sync")

print()
print("② [영상 만들기]가 그림 만들기 **전에** 반영을 먼저 하는가")
wf = (ROOT / ".github" / "workflows" / "produce.yml").read_text(encoding="utf-8")
i_sync = wf.find("assets_gen.py sync")
i_make = wf.find("assets_gen.py images --what char")
if i_sync < 0:
    bad("produce.yml 이 sync 를 안 부른다 — 올린 시트가 무시된다")
elif i_make < 0:
    bad("produce.yml 이 인물 그림을 안 만든다")
elif i_sync > i_make:
    bad("만들기가 반영보다 먼저다 — 있는 것을 두고 돈을 또 쓴다")
else:
    print("   ✅ 반영(0원) → 만들기(값) 순서다")

print()
print("③ 만든 뒤에도 한 번 더 반영하는가 (중간에 죽어도 다음이 이어받게)")
if wf.count("assets_gen.py sync") < 2:
    bad("만든 뒤 반영이 없다 — 자르다 죽으면 다음 실행도 못 이어받는다")
else:
    print("   ✅ 만들기 뒤에도 한 번 더 자른다")

print()
print("④ 인물 만들기에 상한을 걸지 않았는가 (걸면 배우가 말없이 빠진다)")
m = re.search(r"assets_gen\.py images --what char[^\n|]*", wf)
if m and "--limit" in m.group(0):
    bad(f"상한이 걸려 있다: {m.group(0).strip()} — 배우가 빠질 수 있다")
else:
    print("   ✅ 상한 없음 (배우 전원)")

print()
print("⑤ 그림이 빠지면 **영상을 안 만들고 멈추는가**")
# 회색 실루엣이 섞인 영상이 조용히 나가는 것이 가장 나쁘다.
if "::error::인물 그림" not in wf or "exit 1" not in wf:
    bad("인물이 빠져도 그냥 만든다 — 회색 실루엣이 나간다")
else:
    print("   ✅ 인물이 빠지면 멈춘다")

print()
print("⑥ 안내에 적힌 값이 지금 모델과 맞는가")
# 애니 + flash 로 내리면서 197원 → 57원이 됐다. 옛 숫자가 남아 있으면
# 손님이 '비싸다' 고 판단해 버튼을 안 누르게 된다.
stale = [n for n in ("197원",) if n in wf]
if stale:
    bad(f"옛 값이 남아 있다: {', '.join(stale)} (지금은 약 57원)")
else:
    print("   ✅ 57원 (애니 + flash)")

print()
print("⑦ [빠진 것 확인] 도 있는 시트를 먼저 반영하는가")
ba = (ROOT / ".github" / "workflows" / "build-assets.yml").read_text(encoding="utf-8")
if "assets_gen.py sync" not in ba:
    bad("build-assets 가 sync 를 안 부른다 — 시트를 올려도 계속 '빠졌다' 고 나온다")
else:
    print("   ✅ 확인 전에 반영한다")

print()
print("⑧ '전부 다 만들기' 가 진짜로 전부를 만드는가")
# ⚠️ 2026-08-12 손님: "각각 하나씩 만들어야 돼? 전부 다 만들기를 넣어줄 수도 있잖아."
#    넣었다. 그런데 이런 '한꺼번에' 버튼은 **나중에 반드시 뒤처진다** —
#    새 에셋 종류가 늘었는데 여기 한 줄을 안 넣으면, 버튼 이름만 '전부' 이고
#    실제로는 일부만 만든다. 그게 제일 나쁘다(다 된 줄 알게 된다).
i = ba.find('"전부 다 만들기"*)')
j = ba.find(';;', i)
blk = ba[i:j] if i >= 0 else ""
NEED = {
    "인물":     "images --what char",
    "배경":     "bg_fetch.py",
    "배경음악": "get_bgm.py",
    "효과음":   "assets_gen.py audio",
    "시트 반영": "assets_gen.py sync",
}
if not blk:
    bad("'전부 다 만들기' 갈래가 없다")
else:
    miss = [k for k, v in NEED.items() if v not in blk]
    if miss:
        bad(f"'전부' 인데 빠진 것: {', '.join(miss)}")
    else:
        print(f"   ✅ {' · '.join(NEED)} 전부 들어 있다")
    # 값이 드는 것이 맨 뒤여야 한다 — 앞에서 실패하면 돈이 안 나가게
    if blk.find("images --what char") < blk.find("bg_fetch.py"):
        bad("값이 드는 인물 만들기가 공짜 단계보다 앞에 있다 — 앞이 실패해도 돈이 나간다")
    else:
        print("   ✅ 값이 드는 인물 만들기가 맨 뒤다 (앞이 실패하면 돈이 안 나간다)")
    # 만든 뒤 반영이 있어야 컷아웃이 생긴다
    if blk.count("assets_gen.py sync") < 2:
        bad("만든 뒤 반영이 없다 — 시트만 생기고 컷아웃이 안 생긴다")
    else:
        print("   ✅ 만들기 앞뒤로 반영한다")

print()
print("─" * 52)
print("✅ 그림 절차: 정상" if ok else "❌ 그림 절차: 문제 있음")
sys.exit(0 if ok else 1)
