#!/usr/bin/env python3
"""자막이 **한 글자도 빠짐없이** 화면에 올라가는가 (0원 · 인터넷 0회).

왜 이 검사가 있는가 (2026-08-23)
    운영자: "자막 올리는 건 0원이니까 그 자막 올리는 부분들 제대로
             올라갔는지부터 확인해 봐."
    훑어보니 fit() 에 조용한 구멍이 있다 — 글자를 26px 까지 줄여도 줄 수를
    못 맞추면 **넘친 줄을 말없이 버린다**(ls[:max_lines]). 대사가 길면
    자막 뒷부분이 화면에서 사라져도 아무도 모른다.

무엇을 보나 — 시리즈 **전 회차 전 컷**을 실제 조립 코드로 재본다
    ① 토막내기(sub_chunks)가 글자를 흘리지 않는가 (다시 이으면 원문과 같은가)
    ② 토막마다 실제로 그려 보고, **그려진 줄을 다시 이으면** 토막과 같은가
       (여기서 fit() 의 '말없이 버리기'가 걸린다)
    ③ 시간 나누기(음절 비례)가 빈틈·역행 없이 컷을 다 덮는가
    ④ 글자가 실제로 화면에 찍히는가 (투명 그림이 아닌가)
"""
import json
import pathlib
import re
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import shorts as S                                           # noqa: E402
from PIL import Image, ImageDraw, ImageFont                  # noqa: E402

fails, warns = [], []


def norm(t):
    return re.sub(r"[\s/]+", "", str(t or ""))


def drawn_lines(chunk):
    """조립 코드와 똑같이 그 토막을 줄로 나눠 본다 (compose 의 자막 경로)."""
    img = Image.new("RGBA", (S.W, S.H))
    d = ImageDraw.Draw(img)
    f, ls = S.fit(d, chunk, S.FONT_M, S.SUB_SIZE, S.W - S.SIDE * 2, 2)
    return f, ls


def main():
    docs = sorted((ROOT / "data" / "series").glob("S*.json"))
    if not docs:
        print("시리즈 대본이 없다"); return 1
    total_cuts = total_chunks = 0
    min_font = 999
    for dp in docs:
        doc = json.loads(dp.read_text(encoding="utf-8"))
        for ep in doc.get("episodes") or []:
            for c in ep.get("cuts") or []:
                total_cuts += 1
                sub = c.get("subtitle") or ""
                where = f"{dp.stem} {ep.get('no')}화 {c.get('n')}컷"
                chunks, halved = S.sub_chunks(sub)
                # ① 토막내기가 글자를 흘리지 않는가
                if norm("".join(chunks)) != norm(sub):
                    fails.append(f"{where}: 토막내기에서 글자가 사라졌다 — "
                                 f"{chunks} ← {sub[:40]}")
                # ③ 음절 비례 시간이 컷을 다 덮는가
                sec = 8.0
                spans = S.by_syllable(len(chunks), sec, chunks)
                t = 0.0
                for a, b in spans:
                    if abs(a - t) > 1e-6 or b <= a:
                        fails.append(f"{where}: 시간 나누기에 빈틈/역행 ({spans})")
                        break
                    t = b
                else:
                    if abs(t - sec) > 1e-6:
                        fails.append(f"{where}: 시간이 컷 끝까지 안 간다 ({t})")
                # ② 그려진 줄을 다시 이으면 토막과 같은가
                for ch in chunks:
                    total_chunks += 1
                    f, ls = drawn_lines(ch)
                    min_font = min(min_font, f.size)
                    if norm("".join(ls)) != norm(ch):
                        fails.append(f"{where}: 화면에서 글자가 잘렸다 — "
                                     f"'{ch}' → {ls} ({f.size}px)")
                    if f.size < 40:
                        warns.append(f"{where}: 글자가 {f.size}px 까지 줄었다 — "
                                     f"폰에서 읽기 어렵다 ('{ch[:24]}…')")
    # ④ 실제로 찍히는가 — 표본 한 장
    doc = json.loads(docs[0].read_text(encoding="utf-8"))
    c1 = doc["episodes"][0]["cuts"][0]
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="subaudit-"))
    png = S.overlay_png("후킹 문구", S.sub_chunks(c1["subtitle"])[0][0],
                        tmp / "probe.png", "제목 · 1화")
    im = Image.open(png)
    band = im.crop((0, S.SUB_TOP, S.W, S.SUB_BOT))
    # 히스토그램으로 센다 — 바깥 꾸러미 없이, 경고 없이
    opaque = sum(band.getchannel("A").histogram()[41:])
    if opaque < 2000:
        fails.append(f"자막 띠에 글자가 안 찍혔다 (불투명 픽셀 {opaque}개)")

    print("=" * 62)
    print(f"자막 전수 검사 — 컷 {total_cuts}개 · 토막 {total_chunks}개 "
          f"(가장 작아진 글자 {min_font}px)")
    print("=" * 62)
    for w in warns[:8]:
        print(f"   ⚠️ {w}")
    if len(warns) > 8:
        print(f"   ⚠️ … 비슷한 경고 {len(warns) - 8}건 더")
    for x in fails:
        print(f"   ❌ {x}")
    print("-" * 62)
    if fails:
        print(f"❌ {len(fails)}가지 — 자막이 화면에서 사라지는 컷이 있다")
        return 1
    print("✅ 전 회차 전 컷의 자막이 한 글자도 빠짐없이 화면에 올라간다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
