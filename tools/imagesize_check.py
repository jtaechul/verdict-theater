#!/usr/bin/env python3
"""그림 크기·비율을 **API 로** 요청하는지 본다. 인터넷 0회 · 0원 · 1초.

    python3 tools/imagesize_check.py

왜 이 검사가 있는가 (2026-08-12)
    손님 지적: "화질이 너무 안 좋아. 티가 나."  그리고
              "프롬프트에 해상도를 최대로 높여서 제작하도록 수정하면 되잖아?"

    실측한 사실 둘.
      ① **프롬프트로는 안 된다.** docs/char-prompts.md 블록 7개에
         `at least 2048 x 4096 pixels` 가 전부 적혀 있는데, 나온 시트 7장은
         예외 없이 1.05~1.08 MP 였다. 모델은 프롬프트의 크기 지시를 무시한다.
      ② **API 로는 된다.** src/char_sheet.py 가 이미 `imageConfig` 로
         `aspectRatio` 와 `imageSize` 를 보내고 있었다. 그런데 정작 지금 쓰는
         경로(assets_gen.gen_image)만 그걸 **안 보내고 있었다.**

    그래서 1MP 한 장에 18칸을 우겨넣었고, 칸 하나가 228x224,
    그 안의 전신 인물은 **105x302** 였다. 그것을 화면에서 800px 로 늘려 썼다.
    장수를 늘려 돈을 더 쓸 일이 아니라, 같은 한 장을 크게 받으면 되는 일이었다.

    이 검사는 그 요청이 되살아나지 않고 계속 붙어 있는지 지킨다.
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


src = (ROOT / "src" / "assets_gen.py").read_text(encoding="utf-8")
fn = src[src.index("def gen_image("):src.index("\ndef ", src.index("def gen_image(") + 10)]

print("① 그림을 부를 때 **크기**를 요청하는가")
if "imageSize" not in fn:
    bad("imageSize 를 안 보낸다 — 모델이 기본값(1MP)으로 낸다. "
        "18칸으로 나누면 칸 하나가 228px 밖에 안 된다")
else:
    print(f"   ✅ imageSize = {G.IMAGE_SIZE}")

print()
print("② **가로세로 비율**도 요청하는가")
# 이걸 안 보내서 시트가 가로로도 세로로도 제멋대로 나왔고, 자르기가 어긋나
# 머리 없는 인물이 나왔다. 3열 6행이면 1:2 다.
if "aspectRatio" not in fn:
    bad("aspectRatio 를 안 보낸다 — 시트가 가로로 나오면 자르기가 어긋난다")
elif G.IMAGE_RATIO != "1:2":
    bad(f"비율이 {G.IMAGE_RATIO} 다 — 3열 6행 시트는 1:2 여야 한다")
else:
    print(f"   ✅ aspectRatio = {G.IMAGE_RATIO} (3열 6행 = 세로로 길다)")

print()
print("③ 요청이 거절당해도 그림은 받아 오는가 (한 번 실패로 통째로 못 만들면 안 된다)")
if "tries" not in fn or fn.count("responseModalities") < 2:
    bad("물러설 길이 없다 — 모델이 imageConfig 를 안 받으면 그림을 못 만든다")
elif '"429"' not in fn:
    bad("할당량 초과(429)까지 되풀이한다 — 그때는 낮춰도 안 되므로 바로 멈춰야 한다")
else:
    print("   ✅ 조건을 한 단계씩 낮춰 다시 부르고, 할당량 초과는 바로 멈춘다")

print()
print("④ 실제로 몇 픽셀로 왔는지 **화면에 찍는가**")
# 요청이 먹혔는지는 결과를 봐야 안다. 안 찍으면 또 조용히 1MP 로 돌아간다.
if "MP" not in fn:
    bad("받은 크기를 안 찍는다 — 요청이 먹혔는지 알 수가 없다")
else:
    print("   ✅ 매번 'NNNNxNNNN = N.NN MP' 로 찍는다")

print()
print("⑤ 프롬프트의 해상도 문구가 크기를 정하지 **않는다**고 적혀 있는가")
doc = ROOT / "docs" / "char-prompts.md"
if doc.exists():
    t = doc.read_text(encoding="utf-8")
    if "해상도는 프롬프트로 못 정한다" not in t:
        bad("문서에 안 적혀 있다 — 나중에 또 프롬프트를 고치려 든다")
    else:
        print("   ✅ 적혀 있다 (같은 착각을 되풀이하지 않게)")

print()
print("─" * 52)
print("✅ 그림 크기 요청: 정상" if ok else "❌ 그림 크기 요청: 문제 있음")
sys.exit(0 if ok else 1)
