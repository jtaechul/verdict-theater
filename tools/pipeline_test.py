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
print("⑧ 기본 선택지가 필요한 셋을 다 만드는가 (그리고 그것이 기본값인가)")
# ⚠️ 2026-08-12 손님: "각각 하나씩 만들어야 돼? 전부 다 만들기를 넣어줄 수도 있잖아."
#    넣었다. 그런데 이런 '한꺼번에' 버튼은 **나중에 반드시 뒤처진다** —
#    새 에셋 종류가 늘었는데 여기 한 줄을 안 넣으면, 버튼 이름만 '전부' 이고
#    실제로는 일부만 만든다. 그게 제일 나쁘다(다 된 줄 알게 된다).
i = ba.find('"기본 3가지"*)')
j = ba.find(';;', i)
blk = ba[i:j] if i >= 0 else ""
# 손님이 정한 셋 (2026-08-12): 효과음 · 등장인물 · 배경사진.
# 시트 반영은 '넷째 항목' 이 아니라 등장인물을 쓸 수 있게 만드는 배관이다 —
# 이것이 빠지면 시트만 생기고 컷아웃이 안 생겨 영상이 안 나온다.
# ⚠️ 배경음악은 일부러 뺐다. 8곡이 다 차 있고 전용 버튼이 따로 있다.
NEED = {
    "효과음":    "assets_gen.py audio",
    "등장인물":  "images --what char",
    "배경사진":  "bg_fetch.py",
    "시트 반영": "assets_gen.py sync",
}
# 이 선택지가 **기본값**이어야 한다. 손님이 열자마자 이것이 골라져 있어야
# 하나씩 일곱 번 누르는 일이 안 생긴다.
import yaml                                          # noqa: E402
_d = yaml.safe_load(ba)
_on = _d.get("on") if isinstance(_d.get("on"), dict) else _d.get(True)
_def = str((((_on or {}).get("workflow_dispatch") or {})
            .get("inputs", {}).get("what", {})).get("default", ""))
if not _def.startswith("기본 3가지"):
    bad(f"기본값이 '{_def}' 다 — 열자마자 골라져 있어야 하는 것은 '기본 3가지' 다")
else:
    print(f"   ✅ 기본값 = {_def}")

if not blk:
    bad("'기본 3가지' 갈래가 없다")
else:
    miss = [k for k, v in NEED.items() if v not in blk]
    if miss:
        bad(f"기본 선택지에 빠진 것: {', '.join(miss)}")
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
print("⑨ sync 가 시각이 아니라 **내용 지문**으로 판단하는가")
# ⚠️ 2026-08-12 실패의 뿌리. 깃허브는 매 실행 저장소를 새로 받아 파일 시각이
#    무의미하고, 같은 이름으로 덮어쓰면 폴더 시각이 안 바뀐다. 시각으로 판단하면
#    매 실행 "다시 자름" — 다듬어 둔 그림을 되돌려 배치 검사가 막았다.
if "st_mtime" in src[src.index("def cmd_sync"):src.index("def cmd_check")]:
    bad("sync 가 아직 파일 시각을 본다 — CI 에서 시각은 거짓말을 한다")
elif ".from_sheet" not in src:
    bad("시트 지문(.from_sheet)이 없다 — 매 실행 다시 자르게 된다")
else:
    print("   ✅ 시트 내용의 지문(.from_sheet)으로 판단한다")

print()
print("⑩ 다듬기(despike)가 남는 것이 없어질 때까지 도는가")
# 실측: 새 컷아웃 119장이 31 → 11 → 1 → 0, 다섯 번에야 수렴했다.
# 한 번만 돌면 --check 가 남은 것을 잡아 영상 만들기가 멈춘다.
dp = (ROOT / "src" / "despike.py").read_text(encoding="utf-8")
if "MAX_PASS" not in dp or "for pass_n in range" not in dp:
    bad("despike 가 한 번만 돈다 — 잘라낸 단면에서 새 삐죽이가 드러나 검사에 걸린다")
else:
    print("   ✅ 수렴할 때까지 돈다 (상한 8회)")

print()
print("⑪ sync 가 다시 자른 것을 **그 자리에서** 다듬는가")
# 자르기와 다듬기가 떨어져 있으면 순서 사고가 난다 — 다듬기 뒤에 다시 잘라 버린
# 것이 2026-08-12 의 실패다. sync 안에 붙어 있어야 순서를 틀릴 수가 없다.
sy = src[src.index("def cmd_sync"):src.index("def cmd_check")]
if "despike.py" not in sy:
    bad("sync 가 자르기만 하고 다듬지 않는다 — 어디서 불리느냐에 따라 또 터진다")
else:
    print("   ✅ 자른 직후 다듬는다 (순서를 틀릴 수 없다)")

print()
print("─" * 52)
print("✅ 그림 절차: 정상" if ok else "❌ 그림 절차: 문제 있음")
sys.exit(0 if ok else 1)
