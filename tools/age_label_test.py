#!/usr/bin/env python3
"""2026-08-22 운영자 지적 두 가지가 고쳐진 채로 **유지되는가**.

    python3 tools/age_label_test.py     인터넷 0회 · 0원 · 몇 초

지적 ① "동영상이 몇 화인지, 드라마 제목이 뭔지가 안 나와 있어.
        화면 최상단 좌측이나 이런 곳에 들어와야 될 거 같아."
지적 ② "나레이션 발음이 조금씩 뭉개지고, 주인공들 나이 목소리가 맞지 않아."

②의 뿌리는 세 갈래였다 — 다발로 본다:
    · 말투 결(fierce)에 "빠르게" 가 박혀 있었다 → 자음이 뭉개진다
    · 자리에 맞추려 1.35배까지 빨리 감았다 → 또 뭉개진다
    · 배역이 52·55살인데 목소리 지시에 나이가 한 글자도 없었고,
      목소리도 젊은 것(Erinome·Iapetus)이었다
"""

import io
import json
import pathlib
import re
import sys
from contextlib import redirect_stdout

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import tts                                                   # noqa: E402
import shorts as S                                           # noqa: E402
from PIL import Image                                        # noqa: E402

bad = 0


def ck(what, cond, why=""):
    global bad
    if cond:
        print(f"   ✅ {what}")
    else:
        print(f"   ❌ {what}" + (f"  ({why})" if why else ""))
        bad = 1


doc = json.loads((ROOT / "data" / "series" / "S001.json").read_text(encoding="utf-8"))
chars = doc["characters"]

print("① 화면 왼쪽 위 「시리즈 제목 · n화」")
import tempfile
with tempfile.TemporaryDirectory() as d:
    d = pathlib.Path(d)
    label = f"{doc['title']} · 1화"

    def left_top_pixels(png):
        img = Image.open(png)
        # 왼쪽 위 (라벨 자리): x SIDE~절반, y MARK_Y~MARK_Y+50
        box = img.crop((S.SIDE, S.MARK_Y, S.W // 2, S.MARK_Y + 50))
        return sum(1 for px in box.getdata() if px[3] > 0)

    with_l = S.overlay_png("후킹", "자막", d / "a.png", label)
    without = S.overlay_png("후킹", "자막", d / "b.png", None)
    ck("라벨을 주면 왼쪽 위에 글자가 그려진다", left_top_pixels(with_l) > 500,
       f"픽셀 {left_top_pixels(with_l)}개")
    ck("라벨이 없으면 왼쪽 위가 빈다", left_top_pixels(without) == 0)

    # 아주 긴 제목도 채널 이름(오른쪽 위 '판결극장')을 침범하면 안 된다
    img = Image.open(S.overlay_png("후킹", "자막", d / "c.png", "제목" * 30 + " · 16화"))
    from PIL import ImageDraw, ImageFont
    mk = ImageFont.truetype(str(S.FONT_B), S.MARK_SIZE)
    mark_w = ImageDraw.Draw(img).textlength(S.CHANNEL, font=mk)
    gap = img.crop((int(S.W - S.SIDE - mark_w - 30), S.MARK_Y,
                    int(S.W - S.SIDE - mark_w - 4), S.MARK_Y + 50))
    ck("아주 긴 제목도 채널 이름을 침범하지 않는다",
       sum(1 for px in gap.getdata() if px[3] > 0) == 0,
       "길면 줄이고 …로 자른다")

# 배선: 만드는 두 길(한 화 · 한 컷 시험) 모두 라벨을 넘긴다
src = (ROOT / "src" / "shorts.py").read_text(encoding="utf-8")
ck("한 화 만들 때 라벨을 넘긴다", src.count("label=label") >= 2)
ck("라벨은 「제목 · n화」 꼴이다", "· {int(no)}화" in src)

print()
print("② 발음 뭉개짐 — 세 갈래 다")
ck("말투 결에 '빠르게' 가 없다",
   all("빠르게" not in (st.get("add") or "") and "빠르게" not in (st.get("how") or "")
       for k, st in tts.STYLES.items() if k != "dry"),
   "빠르게 읽으라고 시키면 자음이 뭉개진다")
ck("지시문이 또박또박을 요구한다", "또박또박" in tts.how_of("아무 말"))
ck("빨리감기 상한을 1.3배 아래로 묶었다", tts.RATE_MAX <= 1.30,
   f"지금 {tts.RATE_MAX}배 — 1.3배부터 자음이 무너진다")

print()
print("③ 배역 나이가 목소리에 실리는가")
P = tts.pick_personas(chars)
V = tts.pick_voices(chars)
ck("본처(52)는 50대 중년 여성으로 읽는다", "50대 중년 여성" in (P.get("본처") or ""))
ck("남편(55)은 50대 중년 남성으로 읽는다", "50대 중년 남성" in (P.get("남편") or ""))
ck("내연녀(42)는 40대로 읽는다", "40대" in (P.get("내연녀") or ""))
ck("대사 줄 이름(Wife·Husband)으로도 찾아진다",
   P.get("Wife") == P.get("본처") and P.get("Husband") == P.get("남편"))
ck("지시문에 배역이 실린다", "50대 중년 여성" in tts.how_of("말", P["본처"]))
d1 = tts.direct("집을 나가!", P["남편"])
ck("한 덩어리 지시에도 배역이 실린다", "50대 중년 남성" in d1)
ck("대사는 큰따옴표 안에 딱 한 번", d1.count('"') == 2, d1)

print()
print("④ 45살 이상 배역은 나이 든 목소리를 받는가")
ck("본처(52) → 나이 든 여성 목소리", V.get("본처") in tts.MATURE_F, V.get("본처"))
ck("남편(55) → 나이 든 남성 목소리", V.get("남편") in tts.MATURE_M, V.get("남편"))
ck("내연녀(42)는 골라 둔 젊은 목소리 그대로", V.get("내연녀") not in tts.MATURE_F,
   V.get("내연녀"))
ck("여자 둘의 목소리가 겹치지 않는다", V.get("본처") != V.get("내연녀"))
# 나이가 아예 없는 인물표(옛 대본)도 죽지 않는다
old = [{"name": "여자", "role_en": "Woman", "flow_prompt": "Korean woman"},
       {"name": "남자", "role_en": "Man", "flow_prompt": "Korean man"}]
ck("나이 없는 옛 대본도 그대로 돈다",
   bool(tts.pick_voices(old)) and tts.pick_personas(old).get("여자") == "성인 여성")

print()
print("⑤ 실제 갈아 끼우는 자리(dub)까지 배역이 가는가")
ck("dub 이 배역을 받는다", "personas=None" in src and "who=pe" in src)
ck("한 화·한 컷 시험 둘 다 배역을 넘긴다", src.count(", personas)") >= 2)
tsrc = (ROOT / "src" / "tts.py").read_text(encoding="utf-8")
ck("두 엔진 길(AI스튜디오·클라우드) 모두 배역이 간다",
   "direct(text, who)" in tsrc and "how_of(text, who)" in tsrc)
ck("견본(들어보기)도 같은 배역으로 만든다", "who=pe" in tsrc,
   "들어본 것과 실제가 다르면 고르는 의미가 없다")

print()
print("⑥ 자막 경계에서 두 토막이 겹치지 않는가")
# between(t,a,b) 는 양 끝을 포함한다 — 앞 토막을 반 프레임 일찍 꺼야 한다
ck("앞 토막을 반 프레임 일찍 끈다", "EN_EPS" in src and "b - EN_EPS" in src,
   "경계 프레임에 자막 두 개가 겹쳐 보인다 (실제 프레임에서 발견)")
ck("머리말이 실제 배정을 배역별로 적는다", "배역: {nm}" in src,
   "머리말은 Erinome 라 적혔는데 실제는 Gacrux 가 말하고 있었다")

print("────────────────────────────────────────────────────")
print("❌ 나이·발음·라벨: 걸린 것이 있다" if bad else "✅ 나이·발음·라벨: 전부 제자리다")
sys.exit(bad)
