#!/usr/bin/env python3
"""⭐ 컷 그림 **오른쪽 아래 워터마크**를 지운다. 값 0원.

    python3 tools/wipe_mark.py build/s90/stills

손님(2026-09-05): "이미지 우측 하단에 재미난 워터마크가 살짝 보이거든?
지금 화면이 어두워도 살짝 보여."

그림 모델이 오른쪽 아래 모서리에 자기 표시를 찍는다. 어두운 화면에서도
보이고, 영상으로 만들면 그대로 따라 들어간다.

⚠️ 왜 잘라내지 않는가
   잘라내면 화면 아래가 통째로 날아간다. 이 저장소는 이미 그 길을 접었다
   (2026-08-28 손님: "왜 크롭을 하고 검정색으로 가리면 되지"). 게다가 자막이
   앉는 자리(1300~1620)와 가까워, 잘라 늘리면 자막 자리가 밀린다.

⚠️ 왜 까맣게 덮지 않는가
   까만 네모는 "가렸다" 가 눈에 보인다. 우리 화풍은 배경이 **원래 흐리다**
   (heavy bokeh). 그러니 그 자리를 **주변 색으로 뭉개면** 아무도 못 알아본다.

어떻게
   ⚠️ **흐리기만 해서는 안 지워진다.** 밝은 글자를 흐리면 번질 뿐 밝기가
      남는다 (실측: 235 → 146. 여전히 뿌옇게 보인다).
   → 표시 **바로 위**의 깨끗한 자리를 떠다가 위아래로 뒤집어 덮는다.
     뒤집으면 이음매에서 무늬가 이어져 티가 안 난다. 그 위에 살짝 흐림을
     얹고, 가장자리를 부드럽게 섞어(feather) 경계선을 없앤다.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

# 1080×1920 기준 — 오른쪽 아래에서 이만큼. 비율로 잡아 크기가 바뀌어도 따라간다.
MARK_W = 0.20          # 가로 20% (1080 기준 216px)
MARK_H = 0.09          # 세로 9% (1920 기준 173px)
FEATHER = 0.35         # 상자 크기의 이만큼을 부드럽게 섞는다
BLUR = 8               # 떠 온 조각을 살짝만 흐린다 (무늬는 남긴다)


def box_of(w, h):
    bw, bh = int(w * MARK_W), int(h * MARK_H)
    return (w - bw, h - bh, w, h)


def wipe(path):
    """한 장에서 표시를 지운다. 못 읽는 파일이면 None 을 돌려준다.

    ⚠️ 그림 하나가 깨졌다고 만들기 전체를 죽이지 않는다 (상표 가리기와 같은
       태도다). 시험은 가짜 파일을 쓰기도 한다.
    """
    try:
        im = Image.open(path).convert("RGB")
    except Exception as e:                                   # noqa: BLE001
        print(f"  ⚠️ {Path(path).name} 을(를) 못 읽었다 ({e}) — 건너뛴다")
        return None
    w, h = im.size
    x0, y0, x1, y1 = box_of(w, h)             # ← 반드시 **꽉** 덮을 자리
    bw, bh = x1 - x0, y1 - y0
    # ⚠️ 부드럽게 섞는 띠는 덮을 자리 **바깥**에 둔다. 안쪽에 두면 그 띠가
    #    반투명이라 표시가 비쳐 보인다 (실측: 235 → 195. 여전히 보였다).
    f = max(4, int(min(bw, bh) * FEATHER))
    px0, py0 = max(0, x0 - f), max(0, y0 - f)
    pw, ph = x1 - px0, y1 - py0

    # 표시 **위쪽**의 깨끗한 자리를 떠다가 위아래로 뒤집어 덮는다.
    # 뒤집는 까닭 — 이음매에서 무늬가 그대로 이어져 티가 안 난다.
    src_y0 = max(0, py0 - ph)
    src = im.crop((px0, src_y0, x1, py0)).transpose(Image.FLIP_TOP_BOTTOM)
    if src.size != (pw, ph):                  # 위가 모자라면 늘려 쓴다
        src = src.resize((pw, ph))
    src = src.filter(ImageFilter.GaussianBlur(BLUR))

    # 탈(mask) — 덮을 자리는 꽉 차고, 바깥 띠에서만 옅어진다
    m = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(m).rectangle((x0 - px0, y0 - py0, pw, ph), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(max(2, f // 2)))

    im.paste(src, (px0, py0), m)
    im.save(path)
    return (x0, y0, x1, y1)


def main_dir(d):
    """그 폴더의 컷 그림에서 표시를 다 지운다. 조립 쪽에서도 부른다."""
    d = Path(d)
    if not d.is_dir():
        print(f"■ {d} 가 없습니다 — 지울 것이 없습니다")
        return 0
    n = 0
    for f in sorted(d.glob("c*.png")):
        if wipe(f) is not None:
            n += 1
    if n:
        print(f"■ 오른쪽 아래 표시를 지웠습니다 — {n}장 (값 0원)")
        print(f"   자리: 오른쪽에서 {MARK_W * 100:.0f}% · 아래에서 "
              f"{MARK_H * 100:.0f}% (가장자리는 부드럽게 섞음)")
    else:
        print("■ 지울 그림이 없습니다")
    return 0


def main():
    return main_dir(sys.argv[1] if len(sys.argv) > 1 else "build/s90/stills")


if __name__ == "__main__":
    raise SystemExit(main())
