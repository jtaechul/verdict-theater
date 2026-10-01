"""⭐ 이웃한 두 컷 그림이 **같은 구도로 보이는가** — 값 0원 (그림만 견준다)

⭐⭐⭐ 2026-10-01 손님 승인 — 반려동물 식당 쇼츠에서 가져온 것.
   구도표를 아무리 잘 짜도 그림 모델은 가끔 앞 컷과 거의 같은 화면을 그린다.
   같은 크기 · 같은 자리의 화면이 이어지면 컷이 '툭' 끊겨 보인다.
   → 그림이 나온 뒤 **눈으로 보듯** 이웃 컷끼리 견주고, 너무 닮았으면 그 컷만
     "앞 컷과 다르게" 한 번 다시 그린다 (한 편에 REDRAW_MAX 장까지).

재는 법 — 흑백으로 줄여(36×64) 살짝 흐리게 한 뒤 **밝기 무늬가 얼마나 겹치는가**
   (정규화 상관 · -1~1). 색·밝기 차이는 빼고 **화면 짜임**만 본다.

⚠️ 잣대는 진짜 그림으로 맞췄다 (S93 36장 · 630쌍, 2026-10-01 실측):
     같은 구도(문틀 앞에 선 사람 둘 · 같은 얼굴 클로즈업 둘)  0.58 ~ 0.62
     다른 구도(와이드 장례식장 ↔ 미디엄 인물 등)             0.52 이하
   반려동물 쪽 잣대(밝기 차이 < 20)는 우리 그림에 안 맞았다 — 우리 그림은 다
   어둡고 따뜻한 색이라 **전혀 다른 구도도 25~30** 으로 나와 가를 수가 없었다.
   이웃 컷 S93 최고값은 0.518 이라 옛 대본은 한 장도 안 걸린다 (그날 구도 겹침
   0곳과 맞는다).
"""
from pathlib import Path

SAME = 0.55              # 이 값 이상이면 '같은 구도로 보인다'
REDRAW_MAX = 2           # 한 편에 다시 그리는 그림 수 (장당 약 200원)


def _vec(path):
    from PIL import Image, ImageFilter
    im = Image.open(path).convert("L").resize((36, 64)).filter(
        ImageFilter.GaussianBlur(1.0))
    px = list(im.tobytes())
    m = sum(px) / len(px)
    sd = (sum((x - m) ** 2 for x in px) / len(px)) ** 0.5 or 1.0
    return [(x - m) / sd for x in px]


def likeness(a, b):
    """두 그림의 화면 짜임이 얼마나 닮았는가 (-1 ~ 1). 못 읽으면 None."""
    try:
        x, y = _vec(Path(a)), _vec(Path(b))
    except Exception:                                        # noqa: BLE001
        return None
    return sum(i * j for i, j in zip(x, y)) / len(x)


def same_look(a, b):
    v = likeness(a, b)
    return v is not None and v >= SAME
