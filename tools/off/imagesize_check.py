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
# 머리 없는 인물이 나왔다.
#
# ⚠️ 2026-08-13 — 여기가 한때 "1:2 여야 한다" 였다. 3열 6행이니 계산은 맞는데
#    **구글이 1:2 를 안 받는다.** 그대로 올렸으면 그림 만들기가 전부 HTTP 400 으로
#    거절당했을 것이다. 그래서 이제 두 가지를 같이 본다 —
#      ⓐ 받아 주는 값인가 (RATIO_ALL 은 400 응답 본문에서 실측한 목록이다)
#      ⓑ 시트 모양(COLS x ROWS)에 가장 가까운 값인가
if "aspectRatio" not in fn:
    bad("aspectRatio 를 안 보낸다 — 시트가 가로로 나오면 자르기가 어긋난다")
elif G.IMAGE_RATIO not in G.RATIO_ALL:
    bad(f"'{G.IMAGE_RATIO}' 는 구글이 **안 받는 값**이다 (HTTP 400). "
        f"받아 주는 값: {', '.join(sorted(G.RATIO_ALL))}")
elif G.IMAGE_RATIO != G.sheet_ratio():
    bad(f"비율이 {G.IMAGE_RATIO} 다 — {G.COLS}열 {G.ROWS}행이면 "
        f"{G.sheet_ratio()} 가 가장 가깝다")
else:
    print(f"   ✅ aspectRatio = {G.IMAGE_RATIO} "
          f"({G.COLS}열 {G.ROWS}행 = 세로로 길다 · 구글이 받아 주는 값)")

print()
print("②-2 **받아 주지 않는 값**을 보내려 하면 스스로 바꿔 보내는가")
# 나중에 COLS/ROWS 를 바꾸면 계산값이 또 목록 밖으로 나갈 수 있다. 그때
# 400 으로 통째로 죽지 않게, 보내기 직전에 가장 가까운 값으로 갈아 끼운다.
if "RATIO_ALL" not in fn:
    bad("보내기 전에 목록과 맞춰 보지 않는다 — 목록 밖 값이면 400 으로 전부 죽는다")
else:
    print("   ✅ 목록에 없으면 가장 가까운 값으로 바꿔 보낸다")

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
print("⑥ 구글이 그림을 **막아 놓았을 때 크게 알리는가** (조용히 초록불 금지)")
# ⚠️ 2026-08-13 실측 — 그림 모델 셋이 전부 '무료로는 하루 0장' 이었다.
#    그런데 ① gen_image 는 429 의 **본문을 버려서** 왜인지 알 수 없었고
#       ② cmd_images 는 한 장도 못 만들어도 0(성공)으로 끝났고
#       ③ 워크플로는 그것을 `|| true` 로 삼켰다.
#    셋이 겹쳐 **깃허브에 초록 체크가 뜨고 인물 그림은 한 장도 없는** 상태가 됐다.
#    손님은 다 된 줄 알고 다음 단계를 누르게 된다. 그 조합을 여기서 막는다.
llm = (ROOT / "src" / "llm.py").read_text(encoding="utf-8")
if "e.read()" not in llm:
    bad("실패 본문을 버린다 — 429 가 '분당 제한'인지 '한도 0'인지 알 수가 없다")
elif "key=" not in llm.split("def _detail")[1][:900]:
    bad("실패 본문을 그대로 찍는다 — 열쇠가 새어 나갈 수 있다")
else:
    print("   ✅ 왜 거절당했는지 본문을 붙여 준다 (열쇠는 지우고)")

if not hasattr(G, "QuotaBlocked") or not hasattr(G, "quota_blocked"):
    bad("'한도 0' 을 따로 구분하지 않는다 — 기다리면 될 줄 알고 계속 헛누른다")
elif not G.quota_blocked("... limit: 0, model: x") or G.quota_blocked("limit: 60"):
    bad("'한도 0' 판정이 틀렸다")
else:
    print("   ✅ '분당 밀림'과 '하루 한도 0'을 구분한다")

img = src[src.index("def cmd_images("):src.index("\ndef ", src.index("def cmd_images(") + 10)]
if "made == 0" not in img:
    bad("한 장도 못 만들어도 성공으로 끝난다 — 초록 체크만 보고 다 된 줄 안다")
else:
    print("   ✅ 한 장도 못 만들면 실패로 끝난다")

wf = (ROOT / ".github" / "workflows" / "build-assets.yml").read_text(encoding="utf-8")
if "images --what char || true" in wf:
    bad("워크플로가 인물 실패를 `|| true` 로 삼킨다")
elif "char.rc" not in wf:
    bad("인물이 만들어졌는지 결과 화면에 안 적는다")
else:
    print("   ✅ 인물이 막히면 결과 화면 맨 위에 크게 적는다")

if "그림 만들기 되는지 확인" not in wf or not hasattr(G, "cmd_probe"):
    bad("값이 나가기 전에 미리 확인할 버튼이 없다")
else:
    print("   ✅ 값이 나가기 전에 0원으로 미리 확인하는 버튼이 있다")

print()
print("─" * 52)
print("✅ 그림 크기 요청: 정상" if ok else "❌ 그림 크기 요청: 문제 있음")
sys.exit(0 if ok else 1)
