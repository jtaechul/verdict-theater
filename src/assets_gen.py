#!/usr/bin/env python3
"""에셋 만들기 — 캐릭터 컷아웃 · 배경 · 소리.

    python3 src/assets_gen.py sheet assets/sheets/F50A.png F50A   시트 한 장 → 컷아웃 17개
    python3 src/assets_gen.py images --what bg --limit 4          배경 생성 (모델 호출)
    python3 src/assets_gen.py images --what char --code F50B      캐릭터 시트 생성
    python3 src/assets_gen.py audio                               앰비언스·효과음 (비용 0원)
    python3 src/assets_gen.py check                               빠진 에셋 목록

이 파일이 하는 일은 셋이다.

1. **시트 후처리** — 3열 6행짜리 큰 그림 한 장을 인물 컷아웃 17개로 자른다.
   API 없이 도는 순수 계산이라 지금 바로 검증할 수 있다.
2. **이미지 생성** — 캐릭터 시트와 배경을 모델로 만든다.
3. **소리 만들기** — 앰비언스와 일부 효과음은 **합성으로 만든다. 비용 0원.**
   룸톤은 원래 저역 잡음이라 합성이 오히려 깨끗하다.
"""

import argparse
import base64
import json
import os
import subprocess
import sys
from pathlib import Path


# ⭐ Pillow(그림 라이브러리)가 없어도 **이 파일을 읽는 것 자체는 되어야 한다.**
#
#    이 파일에는 그림 그리는 코드 말고도 CHAR_LOOK 같은 '글자 자료'가 들어 있고,
#    대본 만들기(script.py)는 그 자료 한 줄만 가져다 쓴다. 그런데 맨 윗줄에서
#    Pillow 를 부르면, Pillow 를 깔지 않는 워크플로에서는 **자료를 읽으려다
#    파일 전체가 죽는다.**
#
#    2026-08-10 에 실제로 그렇게 EP002 가 날아갔다. 컷 120개를 19분에 걸쳐
#    다 만들어 놓고, 3단계 보강에서 이 줄 하나 때문에 통째로 중단됐다.
#    (같은 사고가 youtube-upload 에서도 한 번 있었다 — 그때는 워크플로에
#     Pillow 설치를 한 줄 넣어 막았지만, 워크플로가 늘 때마다 또 터진다.
#     이번엔 원인 쪽을 고쳐 다시는 안 생기게 한다.)
#
#    → 없으면 없는 대로 두고, **정말 그림을 그릴 때만** 소리내어 멈춘다.
try:
    from PIL import Image, ImageChops, ImageFilter
except ModuleNotFoundError:                        # pragma: no cover - 환경에 따라 다름
    class _NoPillow:
        def __getattr__(self, name):
            raise ModuleNotFoundError(
                "Pillow(그림 라이브러리)가 설치돼 있지 않다.\n"
                "  그림을 만드는 워크플로에는 다음 한 줄이 있어야 한다:\n"
                "    python3 -m pip install --quiet Pillow"
            )
    Image = ImageChops = ImageFilter = _NoPillow()

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import BASE, _get, _post  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

# ⭐ 제미나이에게 그림을 시킬 때의 **색 약속** — 온 저장소가 이 두 색만 쓴다.
#
#    배경 = 크로마 그린 · 칸을 나누는 선 = 마젠타.
#    둘 다 '사람이 아닌 것' 이라 오려낼 때 한꺼번에 지운다.
#
#    ⚠️ 왜 선을 마젠타로 하는가 — 같은 시트를 세 번 뽑아 재본 결과다
#         "격자선을 그리지 마라"        → 검은 줄 (1,3,0) 을 그었다.
#                                        잘라내면 6장 중 5장에 검은 선이 남았다
#         "그리더라도 배경과 같은 초록"  → 절반만 초록. 안 보이는 선을 그리라는
#                                        모순된 지시라 모델이 버틴다
#         "마젠타로 그려라"             → **검은 줄 0개.** 따를 수 있는 지시라 따른다
#    그리고 마젠타는 사진 안 어디에도 없다 — 피부·남색 양복·검은 법복·흰 셔츠·흰머리
#    무엇도 '초록이 가장 낮고 빨강·파랑이 둘 다 높다' 를 만족하지 못한다.
#    검정은 옷과 겹쳐 골라낼 수가 없었다. 그것이 그동안 실패한 진짜 이유다.
CHROMA = (0, 0xB1, 0x40)      # 크로마 그린. 실측 오차 5 이내로 균일
CHROMA_TOL = 60
MAGENTA = (0xFF, 0x00, 0xFF)  # 칸을 나누는 선. 배경과 함께 지워진다


def is_magenta(r, g, b):
    """마젠타인가. 사진 속 어떤 것도 여기 걸리지 않는다 — 실측으로 확인."""
    return r > 100 and b > 100 and g < min(r, b) - 40


# 이미지 프롬프트에 항상 들어가는 색 약속.
# **한 곳에서 고치면 모든 이미지 생성에 반영되게** 여기 모아 둔다.
COLOUR_RULE_KO = (
    "- 배경 전체를 순수한 크로마 그린 #00B140 단색으로 채운다\n"
    "- 칸을 나누는 선은 순수 마젠타 #FF00FF 로 12픽셀 굵기로 긋는다\n"
    "- 사람 바깥에 쓰는 색은 이 둘뿐이다. 검정·회색·흰색 테두리나 선은 절대 그리지 않는다\n"
)
COLOUR_RULE_EN = (
    "  - The background is a FLAT PURE CHROMA GREEN #00B140 everywhere.\n"
    "  - Separate the cells with straight lines of PURE MAGENTA #FF00FF, about\n"
    "    12 pixels thick, drawn edge to edge across the whole image.\n"
    "  - ⚠️ ABSOLUTE RULE ON COLOUR: outside the people there are only two colours —\n"
    "    the chroma green #00B140 background and those magenta #FF00FF divider\n"
    "    lines. NEVER draw a black, grey or white border, frame or line anywhere.\n"
)
COLS, ROWS = 3, 6
GRID_TRIM = 4                  # 격자선 안쪽으로 이 만큼 잘라낸다
# 스티커·콜라주 느낌의 컷아웃. 잡지에서 오려 붙인 것처럼 보이게 한다.
OUTLINE_RATIO = 0.028          # 흰 테두리 두께 = 인물 높이의 2.8%
TORN_EDGE = True               # 가장자리를 불규칙하게 (매끈하면 기계로 오린 티가 난다)
SHADOW = True                  # 테두리 아래 그림자 → 배경에서 떠오른다
UPSCALE = 4

# 시트 18칸의 순서. 18번(우하단)은 워터마크 자리라 비워 둔다.
CELL_ORDER = [
    "face_neutral", "face_sad", "face_anger",
    "face_shock", "face_cold", "face_cry",
    "bust_neutral", "bust_sad", "bust_anger",
    "bust_shock", "bust_cold", "bust_cry",
    "full_stand", "full_walk", "full_sit",
    "full_back", "full_sit_down", None,
]


# ── 1. 시트 후처리 ───────────────────────────────────────
def _lines(mask, thr=0.80, edge=0.03):
    """마젠타가 **한 줄을 거의 가득 채운** 자리를 격자선으로 본다.

    ⚠️ 임계값을 높게 잡는 것이 핵심이다. 격자선은 그림 끝에서 끝까지 이어지지만
       인물이 입은 자주색·연보라 옷은 그렇지 않다. 낮게 잡으면 옷이 선으로
       잘못 잡힌다(실측: 0.5 로 하면 F70 이 7열, M50B 가 8열로 세어졌다).
    가장자리(양 끝 3%)는 시트 테두리이므로 경계에서 뺀다."""
    n = len(mask)
    on = mask > thr
    out, start = [], None
    for i, v in enumerate(list(on) + [False]):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start + i) // 2)
            start = None
    return [c for c in out if edge * n < c < (1 - edge) * n]


def sheet_grid(img):
    """이 시트의 **진짜 칸 경계**를 찾는다 → (세로경계들, 가로경계들) 또는 None.

    ⚠️ 2026-08-12 — 여기가 없어서 영상이 통째로 망가졌다. 사정은 이렇다.
       ① 코드는 3열 6행을 **못박아** 두고 있었는데, 제미나이가 그린 시트 7장 중
          6장이 **6열 3행(가로)** 이었다. 칸 경계를 통째로 빗나가 얼굴 반쪽·
          몸통 중간이 잘려 나왔다 — 머리 없는 인물이 그대로 영상에 들어갔다.
       ② 배치를 비율로 알아내 균등 분할해 봤더니 그것도 부족했다. 칸 높이가
          **균등하지 않기 때문**이다 (M50A 실측: 가로선이 232·469 인데
          균등이면 256·512 여야 한다). 그래서 첫 줄 컷에 아랫줄 사람의 머리가
          딸려 들어와 목 밑에 **가로 막대기**로 나왔다.
       → 짐작하지 않는다. 그려진 선을 **직접 찾아** 그 자리에서 자른다.

    18칸(3x6 또는 6x3)이 안 나오면 None 을 돌려준다. 그 시트는 배치가
    제멋대로라 자를 수 없다 — 다시 만드는 편이 낫다(호출한 쪽이 알린다)."""
    import numpy as np
    a = np.asarray(img.convert("RGB")).astype(int)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mag = (r > 100) & (b > 100) & (g < np.minimum(r, b) - 40)
    vs = _lines(mag.mean(axis=0))          # 세로선 → 열을 가른다
    hs = _lines(mag.mean(axis=1))          # 가로선 → 행을 가른다
    if (len(vs) + 1, len(hs) + 1) in ((COLS, ROWS), (ROWS, COLS)):
        return vs, hs
    return None


def sheet_layout(size):
    """선을 못 찾았을 때 쓰는 **차선책** — 가로세로 비율로 배치를 짐작한다.

    18칸을 3열 6행으로 펴면 세로로 길고, 6열 3행으로 펴면 가로로 길다."""
    W, H = size
    return (COLS, ROWS) if W < H else (ROWS, COLS)


def slice_sheet(img):
    """시트를 18칸으로 자른다. **그려진 격자선을 찾아 그 자리에서** 자른다.

    선을 못 찾으면 비율로 짐작해 균등 분할한다(그때는 칸이 조금 어긋날 수 있다)."""
    W, H = img.size
    grid = sheet_grid(img)
    if grid:
        vs, hs = grid
        xs = [0] + list(vs) + [W]
        ys = [0] + list(hs) + [H]
    else:
        cols, rows = sheet_layout(img.size)
        xs = [round(W * i / cols) for i in range(cols + 1)]
        ys = [round(H * i / rows) for i in range(rows + 1)]
    cells = []
    for r in range(len(ys) - 1):
        for c in range(len(xs) - 1):
            # 선 자체가 컷에 딸려 들어오지 않게 안쪽으로 조금 물러난다.
            t = max(GRID_TRIM, round(min(xs[c + 1] - xs[c], ys[r + 1] - ys[r]) * 0.02))
            cells.append(img.crop((xs[c] + t, ys[r] + t,
                                   xs[c + 1] - t, ys[r + 1] - t)))
    return cells


def sheet_ok(img):
    """이 시트를 **제대로 자를 수 있는가** → (되는가, 까닭).

    ⚠️ 2026-08-12 — 이 검사가 없어서 머리 없는 인물이 영상까지 나갔다.
       제미나이가 시트를 늘 시킨 대로 그리지는 않는다. 실측 7장 중 2장(F70·M50B)은
       왼쪽은 3열 4행, 오른쪽은 칸 크기가 제각각인 **비균등 배치**로 그려 왔다.
       그런 시트는 어떻게 잘라도 한 칸에 두 사람이 들어간다 — 다시 만드는 수밖에 없다.

    판정 기준 둘. 짐작이 아니라 잘라 보고 잰다.
      ① 17칸에 인물이 들어 있는가 (18번째는 비어 있어야 정상)
      ② 한 칸에 **덩어리가 하나**인가 — 둘이면 옆칸·아랫칸이 딸려 온 것이다
    """
    import numpy as np
    cells = slice_sheet(img)
    if len(cells) != COLS * ROWS:
        return False, f"{len(cells)}칸으로 잘린다 (18칸이어야 한다)"
    empty, split = [], []
    for i, c in enumerate(cells[:17]):
        a = np.asarray(drop_chroma(c).getchannel("A"))
        if (a > 16).mean() <= 0.05:
            empty.append(i + 1)
            continue
        rows = (a > 16).sum(axis=1) > a.shape[1] * 0.01
        n, prev = 0, False
        for v in rows:
            if v and not prev:
                n += 1
            prev = v
        if n >= 2:
            split.append(i + 1)
    if empty:
        return False, f"{len(empty)}칸이 비어 있다 (칸 {empty[:6]})"
    if split:
        return False, (f"{len(split)}칸에 사람이 둘씩 들어간다 (칸 {split[:6]}) — "
                       "시트 배치가 제멋대로다")
    return True, "17칸 정상"


def drop_chroma(cell):
    """'사람이 아닌 색' 을 지워 투명하게 만든다 — 크로마 그린과 **마젠타**.

    마젠타는 칸을 나누는 선의 색이다. 배경과 같은 취급으로 여기서 함께 지우면,
    선이 컷아웃에 딸려 나갈 일이 아예 없어진다."""
    cell = cell.convert("RGBA")
    px = cell.load()
    W, H = cell.size
    for y in range(H):
        for x in range(W):
            r, g, b, a = px[x, y]
            green = (abs(r - CHROMA[0]) < CHROMA_TOL and abs(g - CHROMA[1]) < CHROMA_TOL
                     and abs(b - CHROMA[2]) < CHROMA_TOL and g > r + 40 and g > b + 20)
            if green or is_magenta(r, g, b):
                px[x, y] = (r, g, b, 0)
            # ⚠️ 2026-08-12 — 위 조건만으로는 **가장자리의 초록이 남는다.**
            #    그림 가장자리는 인물 색과 배경 초록이 섞인 중간색(안티앨리어싱)이라
            #    '순수 초록' 검사를 통과하지 못한다. 그래서 머리카락 둘레에 얇은
            #    초록 실선이 남았고, 그 위에 흰 테두리를 두르니 더 도드라졌다.
            #    → 초록이 확실히 우세한 픽셀은 남은 초록기를 **빼서** 중화한다.
            elif g > r + 18 and g > b + 18:
                k = min(g - r, g - b)            # 얼마나 초록에 물들었나
                px[x, y] = (r, max(0, g - k), b, a)
    return cell


def trim_alpha(img, pad=6):
    box = img.getchannel("A").getbbox()
    if not box:
        return None
    l, t, r, b = box
    return img.crop((max(0, l - pad), max(0, t - pad),
                     min(img.width, r + pad), min(img.height, b + pad)))


def white_outline(img, thickness=OUTLINE_RATIO, torn=TORN_EDGE, shadow=SHADOW):
    """인물 둘레에 **두껍고 불규칙한 흰 테두리**를 두르고 그림자를 깐다.

    스티커·콜라주 방식이다. 잡지에서 사진을 가위로 오려 종이에 붙인 것처럼 보이게 한다.
    이게 없으면 인물이 배경에 그냥 얹힌 것처럼 보여 '오려 붙인 티'가 난다.

    세 겹으로 만든다.
      1. 그림자 — 테두리를 흐리게 하고 아래로 조금 내려 깐다. 인물이 배경에서 떠오른다
      2. 흰 테두리 — 가장자리를 일부러 불규칙하게 만든다. 매끈하면 기계로 오린 티가 난다
      3. 인물 — 맨 위

    두께는 인물 높이의 2.8%. 얇으면 블러 배경에 묻히고, 두꺼우면 유치해진다."""
    w = max(3, int(img.height * thickness))
    pad = w * 4                                   # 테두리와 그림자가 잘리지 않게 여백을 준다
    canvas = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    canvas.alpha_composite(img, (pad, pad))
    alpha = canvas.getchannel("A")

    # ── 1) 테두리 모양 만들기 ──
    grown = alpha.filter(ImageFilter.MaxFilter(w * 2 + 1))
    grown = grown.point(lambda v: 255 if v > 8 else 0)

    if torn:
        # 찢은 종이 느낌. 부드럽게 번지게 한 뒤 잡음을 섞어 다시 자르면
        # 가장자리가 들쭉날쭉해진다. 매끈한 곡선보다 손으로 오린 느낌이 난다.
        soft = grown.filter(ImageFilter.GaussianBlur(w * 0.55))
        noise = Image.effect_noise(canvas.size, 46).filter(
            ImageFilter.GaussianBlur(max(1.0, w * 0.30)))
        mixed = ImageChops.add(soft, noise, scale=1.0, offset=-118)
        grown = mixed.point(lambda v: 255 if v > 128 else 0)
        # 잡음 때문에 생긴 작은 점들을 메운다
        grown = grown.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
        grown = ImageChops.lighter(grown, alpha.point(lambda v: 255 if v > 8 else 0))

    out = Image.new("RGBA", canvas.size, (0, 0, 0, 0))

    # ── 2) 그림자 ──
    if shadow:
        blur = grown.filter(ImageFilter.GaussianBlur(w * 1.1))
        sh = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        sh.putalpha(blur.point(lambda v: int(v * 0.42)))
        off = max(2, int(w * 0.55))
        out.alpha_composite(sh, (0, 0))
        shifted = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        shifted.paste(sh, (int(off * 0.35), off))
        out = Image.alpha_composite(out, shifted)

    # ── 3) 흰 테두리 → 인물 ──
    white = Image.new("RGBA", canvas.size, (255, 255, 255, 255))
    white.putalpha(grown)
    out = Image.alpha_composite(out, white)
    out = Image.alpha_composite(out, canvas)

    return trim_alpha(out, pad=2) or out


def process_sheet(sheet_path, code, outdir=None, upscale=UPSCALE,
                  outline=OUTLINE_RATIO, torn=TORN_EDGE, shadow=SHADOW):
    """시트 한 장 → 컷아웃 17개.

    시트 생성 → 슬라이싱 → 크로마키 제거 → **스티커 테두리 + 그림자** → 4배 업스케일 → 저장
    """
    outdir = Path(outdir or (ASSETS / "char" / code))
    outdir.mkdir(parents=True, exist_ok=True)
    img = Image.open(sheet_path).convert("RGBA")
    cells = slice_sheet(img)
    made = []
    for i, (cell, name) in enumerate(zip(cells, CELL_ORDER)):
        if name is None:
            continue
        cut = trim_alpha(drop_chroma(cell))
        if cut is None:
            print(f"  {i + 1:2d}번 칸 비어 있음 → {name} 건너뜀")
            continue
        cut = white_outline(cut, thickness=outline, torn=torn, shadow=shadow)
        if upscale > 1:
            cut = cut.resize((cut.width * upscale, cut.height * upscale), Image.LANCZOS)
        p = outdir / f"{name}.png"
        cut.save(p)
        made.append(p)
    print(f"{code}: 컷아웃 {len(made)}개 → {outdir}")
    return made


# ── 2. 이미지 생성 ───────────────────────────────────────
BG_PROMPTS = {
    "funeral": "한국의 장례식장", "medical": "한국의 병원",
    "home": "한국 서민 아파트", "court": "한국 법원",
    "office": "한국의 사무 공간", "daily": "한국의 동네",
    "etc": "한국의 일상 공간",
}
BG_PLACE = {
    "funeral_reception": "접객실, 낮은 조명과 흰 국화", "funeral_hall": "긴 복도",
    "funeral_altar": "영정이 놓인 제단 앞", "funeral_parking": "밤의 주차장",
    "medical_room_single": "1인 병실", "medical_room_shared": "다인 병실",
    "medical_nursing_hall": "요양원 복도", "medical_waiting": "병원 대기실",
    "home_living_day": "낮의 거실", "home_living_night": "밤의 거실",
    "home_kitchen": "부엌", "home_entrance": "현관", "home_bedroom": "안방",
    "home_closet": "옷장 앞", "court_exterior": "법원 건물 외부",
    "court_room": "법정 내부", "court_hall": "법원 복도",
    "office_lawyer": "변호사 사무실", "office_registry": "등기소 창구",
    "office_community": "주민센터", "office_bank": "은행 창구",
    "daily_market": "시장 골목", "daily_sidedish": "반찬가게",
    "daily_restaurant": "백반 식당", "daily_cafe": "동네 카페",
    "daily_park": "공원 벤치", "etc_columbarium": "납골당",
    "etc_country_yard": "시골 마당", "etc_busstop": "버스정류장",
    "etc_alley_night": "밤의 골목길",
}

CHAR_LOOK = {
    # ⚠️ **인물마다 옷 색이 달라야 한다.** 예전에는 일곱 명이 전부 남색이었다.
    #    그래서 아버지(M70)와 차남(M50B)이 멀리서 같은 사람으로 보였다 —
    #    손님이 "아버지랑 차남이랑 얼굴이 똑같다" 고 지적한 것이 이것이다.
    #    얼굴만으로는 부족하다. 50~60대 시청자는 **옷 색으로 인물을 기억한다.**
    "F50A": "60대 한국 여성, 짧은 파마머리, 지친 눈, 연한 베이지 니트",
    "F50B": "50대 한국 여성, 단정한 단발, 날카로운 눈매, 짙은 자주색 블라우스",
    "M50A": "50대 한국 남성, 희끗한 짧은 머리, 남색 정장",
    "M50B": "50대 한국 남성, 벗어진 이마, 올리브색 점퍼",
    "F70": "70대 한국 여성, 흰 파마머리, 굽은 어깨, 연보라 조끼에 흰 블라우스",
    "M70": "70대 한국 남성, 흰 머리, 마른 체구, 갈색 카디건에 흰 셔츠",
    "JUDGE": "한국 판사, 검은 법복",
}


# ⭐ 그림 종류마다 **다른 모델**을 쓴다 (손님 선택 · 2026-08-04)
#
# 손님 지적: "편당 비용이 이렇게 비싼 건 말이 안 된다."
# 실측해 보니 값의 대부분은 음성이 아니라 **그림**이었다(음성은 편당 약 500원).
#
# ⚠️ 그런데 비싼 모델이 뽑힌 것은 **의도가 아니라 사고**였다.
#    예전 코드는 `cands.sort(key=lambda n: ("preview" in n, len(n)))` —
#    "미리보기 아닌 것 중 이름 짧은 것" 이었다. '안정판을 고르자' 는 뜻이었는데
#    하필 이름이 가장 짧은 것이 **가장 비싼 gemini-3-pro-image** 였다.
#    목소리를 성격 대신 '높이' 만 보고 골랐던 것과 똑같은 실수다.
#
# 이제 종류별로 이름을 적어 둔다. 자동 정렬에 맡기지 않는다.
#   배경 — 화면에서 **14px 블러 + 22% 어둡게** 처리해 깔개로만 쓴다.
#          비싼 모델로 만들어도 차이가 보이지 않는다 → 싼 flash 로 내린다.
#   인물 — 2026-08-12 손님 결정으로 **애니 화풍**이 되면서 flash 로 내렸다.
#          까닭: 실사 얼굴은 싼 모델로 뽑으면 피부가 뭉개지고 눈이 어긋나 못 쓴다.
#          애니는 면과 선이라 flash 로도 멀쩡하다. 장당 197원 → 57원 (3.5배).
#          손님 지적: "애니메이션 화풍이면 같은 비용으로 훨씬 더 많은 등장인물
#          이미지를 고화질로 뽑을 수 있어, 없어?" — 맞는 말이고, 그 절약이
#          실제로 생기는 자리가 바로 이 줄이다. 회차마다 얼굴을 바꾸기로 했으므로
#          벌 수가 늘수록 이 차이가 그대로 곱해진다.
#          ⚠️ 다시 실사로 돌아간다면 이 줄도 pro 로 되돌려야 한다.
# ⚠️ 회차가 바뀌어도 얼굴을 바꾸지 않는 인물 (2026-08-12 손님 지시).
#    같은 법정, 같은 재판장이 채널의 얼굴이다. 재판장이 매번 다른 사람이면
#    "같은 법정에서 이어지는 이야기" 라는 느낌이 깨진다.
FIXED_FACE = {"JUDGE"}

IMAGE_MODEL_ORDER = {
    "bg":   ["gemini-3.1-flash-image", "gemini-2.5-flash-image",
             "gemini-3.1-flash-lite-image"],
    "char": ["gemini-3.1-flash-image", "gemini-2.5-flash-image",
             "gemini-3-pro-image"],
}


def pick_image_model(key, kind="char"):
    """이 종류의 그림을 만들 모델. 없으면 None.

    환경변수로 덮어쓸 수 있다 — 전체는 `GEMINI_IMAGE_MODEL`,
    배경만은 `GEMINI_IMAGE_MODEL_BG`."""
    override = (os.environ.get(f"GEMINI_IMAGE_MODEL_{kind.upper()}")
                or os.environ.get("GEMINI_IMAGE_MODEL"))
    if override:
        return override.strip()
    data = _get(f"{BASE}/models?key={key}&pageSize=200")
    names = [m["name"].split("/", 1)[-1] for m in data.get("models", [])]
    have = {n for n in names if "image" in n.lower() and "embed" not in n.lower()}
    for want in IMAGE_MODEL_ORDER.get(kind, []):
        if want in have:
            return want
    # 적어 둔 것이 하나도 없을 때만 자동으로 고른다. 그때도 **싼 쪽 먼저**.
    cands = sorted(have, key=lambda n: (0 if "flash" in n else 1, "preview" in n, len(n)))
    return cands[0] if cands else None


def gen_image(key, model, prompt, out_path):
    res = _post(f"{BASE}/models/{model}:generateContent?key={key}", {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
    }, timeout=300)
    parts = (res.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    blob = next((p["inlineData"] for p in parts if "inlineData" in p), None)
    if not blob:
        raise RuntimeError("이미지가 오지 않았다")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(blob["data"]))
    return out_path


def bg_prompt(code):
    fam = code.split("_")[0]
    place = BG_PLACE.get(code, code)
    return (f"{BG_PROMPTS.get(fam, '한국의 공간')} — {place}. "
            "사진처럼 사실적인 실내/실외 배경. **사람이 등장하지 않는다.** "
            "글자·간판·상표가 보이지 않게. 차분하고 약간 어두운 색조. "
            "가로 16:9 구도, 중앙을 비워 인물을 세울 자리를 남긴다.")


def char_sheet_prompt(code):
    return (
        # ⚠️ 2026-08-12 — 여기에 **화풍이 한 글자도 없었다.** 그냥 "캐릭터 시트" 였다.
        #    화풍을 안 적으면 AI 가 알아서 정한다. 그래서 손님 모르게 애니가 나왔고
        #    "말도 안 하고 애니메이션으로 바꾸냐" 는 지적을 받았다. **반드시 적는다.**
        #
        # ⭐ 채널 화풍 (손님 결정 2026-08-12)
        #      인물 = 애니 (반실사 극화체)   배경 = 사진 그대로
        #    까닭: 애니는 싼 flash 모델로도 쓸 만해 장당 197원 → 57원이 된다.
        #          회차마다 얼굴을 바꾸기로 했으므로 벌 수만큼 그 차이가 곱해진다.
        #
        # ⚠️ **사진 배경 위에 얹힌다**는 것이 이 화풍의 전제다. 그래서 아무 애니나
        #    안 된다. 눈 큰 소녀풍(모에)으로 나오면 흐린 법정 사진 위에서 겉돈다.
        #      - 실제 사람 비율(7~8등신), 나온 나이 그대로. 예쁘게 만들지 않는다
        #      - 배경 팔레트(회색·남색·베이지)에 맞춘 낮은 채도
        #      - 굵은 검은 윤곽선 금지 — 보기에도 튀고, 검은 옷과 붙어 오려낼 때 딸려 온다
        f"한국 드라마 분위기의 반실사 애니메이션 인물 시트 한 장. "
        f"{CHAR_LOOK.get(code, '한국 중년')}.\n"
        "손으로 그린 극화체 애니메이션 그림이다. 사진이 아니다.\n"
        "실제 사람 비율(7~8등신)에 적힌 나이 그대로. 눈을 크게 그리거나 "
        "어려 보이게 만들지 않는다. 채도가 낮은 차분한 색으로 칠한다.\n"
        "굵은 검은 윤곽선을 두르지 않는다.\n"
        "규격을 정확히 지켜라.\n"
        # ⚠️ 여기가 검은 칸 선의 **최초 발원지**였다 — 예전에는 이 자리에
        #    "격자선은 검은색 3px" 이라고 **직접 시키고** 있었다.
        #    검은 선은 검은 옷과 구분이 안 돼서 오려낼 때 딸려 나온다.
        + COLOUR_RULE_KO +
        "- 3열 6행 = 18칸 격자\n"
        # ⚠️ 예전에 여기 "의상은 남색 상의 + 검정 하의" 가 박혀 있었다. 그러면
        #    CHAR_LOOK 이 인물마다 정해 둔 옷 색(베이지·자주·올리브·연보라·갈색)을
        #    **전부 덮어써서 일곱 명이 같은 옷을 입는다.** 손님이 "아버지랑 차남이랑
        #    똑같다" 고 한 그 문제가 그대로 돌아온다. 옷 색은 CHAR_LOOK 이 정한다.
        "- 위에 적힌 그 인물의 옷차림 그대로. 18칸에서 옷이 바뀌지 않는다\n"
        "- 바닥 그림자를 그리지 않는다\n"
        "- 18번 칸(오른쪽 맨 아래)은 인물 없이 비워 둔다\n"
        "칸 순서: 1~6 얼굴 클로즈업(무표정·슬픔·분노·놀람·냉담·울음), "
        "7~12 상반신(같은 순서), 13~17 전신(서기·걷기·앉기·뒷모습·주저앉기), 18 빈 칸\n"
        "같은 인물의 얼굴이 18칸에서 완전히 동일해야 한다. "
        "고르고 부드러운 정면 빛, 부드러운 셀 셰이딩. 주름·머리카락 결까지 "
        "살아 있는 최고 화질. 선이 또렷하고, 흐릿하거나 뭉개진 곳이 없어야 한다. "
        "글자·번호·설명·워터마크를 넣지 않는다."
    )


def cmd_images(args):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("❌ GEMINI_API_KEY 가 없다. 이미지 생성은 열쇠가 필요하다.")
        return 2
    # 배경과 인물은 **다른 모델**을 쓴다 (IMAGE_MODEL_ORDER 설명 참고).
    models = {k: pick_image_model(key, k) for k in ("bg", "char")}
    if not any(models.values()):
        print("❌ 이미지를 만들 수 있는 모델을 찾지 못했다.")
        print("   GEMINI_IMAGE_MODEL 환경변수로 모델 이름을 직접 지정할 수 있다.")
        return 2
    print(f"이미지 모델 — 배경 {models['bg']} · 인물 {models['char']}")

    jobs = []
    if args.what in ("bg", "all"):
        for code in BG_PLACE:
            p = ASSETS / "bg" / f"{code}.jpg"
            if not p.exists() or args.force:
                jobs.append(("bg", code, p, bg_prompt(code)))
    if args.what in ("char", "all"):
        codes = [args.code] if args.code else list(CHAR_LOOK)
        # ⭐ 두 번째 얼굴(벌) 만들기 — 회차마다 얼굴이 바뀌게 하려는 것이다.
        #    (2026-08-12 손님: "왜 저기에 그냥 모형이 들어가 있어?")
        #    ⚠️ 판사는 만들지 않는다. 같은 법정, 같은 재판장이 채널의 얼굴이다(손님 지시).
        if args.variant > 1:
            skipped = [c for c in codes if c in FIXED_FACE]
            codes = [c for c in codes if c not in FIXED_FACE]
            if skipped:
                print(f"  {', '.join(skipped)} 는 두 번째 얼굴을 만들지 않는다 "
                      f"(회차가 바뀌어도 그대로 두기로 했다)")
        for code in codes:
            name = code if args.variant <= 1 else f"{code}-{args.variant}"
            p = ASSETS / "sheets" / f"{name}.png"
            if not p.exists() or args.force:
                jobs.append(("char", name, p, char_sheet_prompt(code)))
    if args.limit and len(jobs) > args.limit:
        # ⚠️ 조용히 자르지 않는다. 2026-08-12 실측: 버튼의 기본 상한이 6인데
        #    인물은 7명이라, [등장인물 전부] 를 눌러도 **한 명이 말없이 빠졌다.**
        #    화면에는 "6개 생성" 만 찍혀서 다 된 줄 알게 된다.
        dropped = [c for _k, c, _p, _pr in jobs[args.limit:]]
        print(f"⚠️ 상한({args.limit})에 걸려 {len(dropped)}개를 **안 만든다**: "
              f"{', '.join(dropped)}")
        print(f"   전부 만들려면 상한을 {len(jobs)} 이상으로 올리십시오 (0 이면 무제한).")
        jobs = jobs[:args.limit]
    if not jobs:
        print("만들 것이 없다. 이미 다 있거나 --force 가 필요하다.")
        return 0

    print(f"{len(jobs)}개 생성")
    made = 0
    for kind, code, path, prompt in jobs:
        try:
            m = models.get(kind) or models.get("char") or models.get("bg")
            gen_image(key, m, prompt, path)
            made += 1
            print(f"  {kind} {code} → {path.name}  ({m})")
            if kind == "char":
                process_sheet(path, code)
        except Exception as e:
            print(f"  {kind} {code} 실패: {type(e).__name__}: {e}")
    print(f"\n완료 {made}/{len(jobs)}")
    return 0


# ── 3. 소리 만들기 (합성 · 비용 0원) ─────────────────────
AMB_RECIPE = {
    # 장소별 공기음. 룸톤은 원래 저역 잡음이라 합성이 오히려 깨끗하다.
    "home":     "anoisesrc=c=brown:a=0.05,lowpass=f=320,volume=0.5",
    "hospital": "anoisesrc=c=brown:a=0.04,lowpass=f=500,highpass=f=90,volume=0.5",
    "court":    "anoisesrc=c=brown:a=0.035,lowpass=f=260,volume=0.5",
    "funeral":  "anoisesrc=c=brown:a=0.03,lowpass=f=220,volume=0.45",
    "street":   "anoisesrc=c=pink:a=0.05,lowpass=f=900,highpass=f=120,volume=0.45",
}
SFX_RECIPE = {
    # 합성으로 그럴듯하게 나오는 것만. 나머지는 무료 음원을 넣어야 한다.
    "heartbeat": "sine=f=52:d=2,atempo=1,volume=1.2,"
                 "atrim=0:2,asetrate=44100,aformat=channel_layouts=mono",
    "clock":     "sine=f=1400:d=0.02,apad=pad_dur=0.98,aloop=loop=5:size=44100,volume=0.7",
    "gavel":     "anoisesrc=c=white:d=0.09:a=0.9,lowpass=f=900,volume=1.4,apad=pad_dur=0.5",
    "paper":     "anoisesrc=c=white:d=0.5:a=0.25,highpass=f=1800,volume=0.9",
    "tear":      "anoisesrc=c=white:d=0.8:a=0.35,highpass=f=1200,volume=1.0",
    # ⚠️ 여기에 footsteps·monitor 를 **다시 넣지 마십시오.** 손님이 귀로 듣고
    #    두 번 빼 달라고 한 소리다. 만드는 법이 여기 남아 있으면 [소리 (비용 0원)]
    #    버튼 한 번에 되살아난다 — 실제로 그래서 영상에 들어갔다.
    #      footsteps  갈색 잡음 저역통과 → 발소리가 아니라 둔탁한 '툭'
    #                 (2026-08-12: "41초 부근 효과음 이상한 거잖아. 들어가지 않게 해")
    #      monitor    880Hz 순수음 → 그 소리가 곧 "삑 삑"
    #                 (2026-08-09: 6분30초의 그 소리)
    #    진짜 녹음이 필요하면 [효과음 받아오기 (Freesound)] 로 받으십시오(0원).
    "door":      "anoisesrc=c=brown:d=0.3:a=0.5,lowpass=f=400,volume=1.2,apad=pad_dur=0.4",
    "stamp":     "anoisesrc=c=white:d=0.07:a=0.8,lowpass=f=600,volume=1.3,apad=pad_dur=0.4",
    "phone":     "sine=f=1000:d=0.4,apad=pad_dur=0.3,aloop=loop=3:size=44100,volume=0.8",
}


def synth(kind, name, recipe, seconds, force=False):
    out = ASSETS / kind / f"{name}.mp3"
    if out.exists() and not force:
        return None
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-f", "lavfi", "-i", recipe, "-t", f"{seconds}",
                        "-ac", "1", "-ar", "44100", "-b:a", "128k", str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  {kind}/{name} 실패: {r.stderr.strip()[-160:]}")
        return None
    return out


def cmd_audio(args):
    made = 0
    print("앰비언스 5종 (장소별 공기음)")
    for name, recipe in AMB_RECIPE.items():
        if synth("amb", name, recipe, 30, args.force):
            made += 1
            print(f"  amb/{name}.mp3")
    print("\n효과음 10종")
    for name, recipe in SFX_RECIPE.items():
        if synth("sfx", name, recipe, 2, args.force):
            made += 1
            print(f"  sfx/{name}.mp3")
    print(f"\n합성 {made}개 · 비용 0원")
    print("\n⚠️ 음악 8트랙은 합성으로 만들 수 없다.")
    print("   지침서 8번대로 미리 만들어 `assets/bgm/{코드}.mp3` 로 넣어야 한다.")
    print("   코드: hook past care reveal conflict court verdict outro")
    print("   회차마다 만들지 않는다 — 톤이 튀면 시리즈물에서 치명적이다.")
    return 0


# ── 4. 무결성 검사 ───────────────────────────────────────
def cmd_sync(args):
    """있는 시트를 컷아웃으로 **반영한다.** 만들지 않는다 — 값 0원.

    ⚠️ 2026-08-12 — 여기가 비어 있어서 파이프라인이 막혀 있었다.
       손님 지적: "이미지 생성이 완료된 거는 그 영상에 반영을 하는 알고리즘이
                   미리 구축이 되어 있었어야 되잖아."

       맞는 말이었다. cmd_images 는 **새로 만든 시트만** 잘랐다(process_sheet).
       시트가 이미 있으면 `if not p.exists()` 로 생성을 건너뛰는데,
       **건너뛰면 자르지도 않았다.** 그래서 이런 상황이 영영 안 풀린다.
         · 손님이 제미나이에서 뽑은 시트를 저장소에 직접 올린 경우
         · 지난 실행이 시트는 만들어 커밋했는데 자르다 죽은 경우
       둘 다 시트는 있는데 컷아웃이 없으니 무결성 검사가 계속 막는다.

    이제 [영상 만들기]가 그림을 만들기 **전에** 이것부터 돌린다.
    있는 것을 먼저 반영하고, 그러고도 없는 것만 새로 만든다."""
    sheets = sorted((ASSETS / "sheets").glob("*.png"))
    if not sheets:
        print("시트가 없다. 반영할 것이 없다.")
        return 0
    import hashlib
    done, skip, fail, resliced = 0, 0, [], []
    for sp in sheets:
        name = sp.stem                       # F50A 또는 F50A-2
        outdir = ASSETS / "char" / name
        have = sorted(outdir.glob("*.png"))
        want = len([c for c in CELL_ORDER if c])
        # ⚠️ 2026-08-12 — 여기가 **파일 시각**으로 판단하고 있었다. 그래서 사고가 났다.
        #    깃허브는 실행 때마다 저장소를 새로 내려받아 모든 파일 시각이 그때가 되고,
        #    같은 이름으로 덮어써도 폴더 시각은 안 바뀐다. 결과: 매 실행 "다시 자름" —
        #    에셋 만들기가 다듬어 둔(despike) 컷아웃을 [영상 만들기]가 매번
        #    다듬기 전 상태로 되돌렸고, 배치 검사가 "삐죽이가 남았다" 며 막았다.
        #    시각은 CI 에서 거짓말을 한다. **시트 내용의 지문**으로 판단한다.
        #    지문은 컷아웃 폴더에 .from_sheet 로 남기고 저장소에 같이 커밋된다.
        sheet_id = hashlib.sha256(sp.read_bytes()).hexdigest()[:16]
        marker = outdir / ".from_sheet"
        same = marker.exists() and marker.read_text(encoding="utf-8").strip() == sheet_id
        if len(have) >= want and same and not args.force:
            skip += 1
            continue
        # ⭐ 자르기 전에 **자를 수 있는 시트인지** 본다 (2026-08-12).
        #    못 자를 시트를 억지로 자르면 머리 없는 인물이 나온다.
        #    그런 시트는 옆으로 치워 둔다 — 그러면 다음 '없는 인물 만들기' 가
        #    시트가 없다고 보고 **자동으로 다시 그린다**(한 장 약 57원).
        try:
            good, why = sheet_ok(Image.open(sp).convert("RGBA"))
        except Exception as e:
            good, why = False, f"열지 못했다: {e}"
        if not good:
            junk = ASSETS / "sheets" / "bad"
            junk.mkdir(parents=True, exist_ok=True)
            sp.rename(junk / sp.name)
            print(f"  {name}: 이 시트로는 못 자른다 — {why}")
            print(f"        → sheets/bad/ 로 치웠다. 다시 그리면 채워진다.")
            fail.append(name)
            continue
        try:
            made = process_sheet(sp, name)
            print(f"  {name}: 컷아웃 {len(made)}개 만듦 "
                  f"({'새 시트' if not have else '다시 자름'})")
            marker.write_text(sheet_id + "\n", encoding="utf-8")
            done += 1
            resliced.append(name)
        except Exception as e:
            print(f"  {name}: 자르기 실패 — {type(e).__name__}: {e}")
            fail.append(name)
    # ⚠️ 2026-08-12 — 여기서 다듬기(despike)를 부르던 것을 **뺐다**(손님 선택).
    #    다듬기가 그림을 최대 78% 까지 갉아먹었다. 자세한 사정은 워크플로 주석 참고.
    #    이제 자른 그대로가 최종본이다.
    print(f"시트 {len(sheets)}장 · 반영 {done} · 그대로 {skip}"
          + (f" · 실패 {', '.join(fail)}" if fail else ""))
    return 1 if fail else 0


def cmd_check(args):
    mf = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
    need = mf["required_files"]
    missing = [f for f in need if not (ROOT / f).exists()]
    have = len(need) - len(missing)
    print(f"에셋 {have}/{len(need)}개 준비됨")
    if not missing:
        print("전부 있다. 렌더링 가능.")
        return 0
    by = {}
    for f in missing:
        by.setdefault(f.split("/")[1], []).append(f)
    print("\n빠진 것")
    for k, v in sorted(by.items(), key=lambda x: -len(x[1])):
        print(f"  {k:10s} {len(v):4d}개  예) {Path(v[0]).name}")
    print("\n빠진 에셋은 렌더링에서 대체물(실루엣·무음)로 채워진다.")
    print("파이프라인은 돌지만 발행할 수 있는 품질이 아니다.")
    return 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    y = sub.add_parser("sync", help="있는 시트를 컷아웃으로 반영한다 (값 0원)")
    y.add_argument("--force", action="store_true", help="이미 잘린 것도 다시 자른다")

    s = sub.add_parser("sheet", help="시트 한 장 → 컷아웃 17개")
    s.add_argument("path")
    s.add_argument("code")
    s.add_argument("--upscale", type=int, default=UPSCALE)
    s.add_argument("--outline", type=float, default=OUTLINE_RATIO,
                   help=f"흰 테두리 두께 = 인물 높이 대비 비율 (기본 {OUTLINE_RATIO})")
    s.add_argument("--smooth", action="store_true", help="가장자리를 매끈하게 (찢은 느낌 끄기)")
    s.add_argument("--no-shadow", action="store_true", help="그림자 끄기")

    i = sub.add_parser("images", help="캐릭터 시트·배경 생성")
    i.add_argument("--what", choices=["bg", "char", "all"], default="all")
    i.add_argument("--code", default="")
    i.add_argument("--variant", type=int, default=1,
                   help="몇 번째 얼굴(벌)을 만들지. 2 면 assets/char/F50A-2/ 로 들어가고 "
                        "회차마다 번갈아 쓴다. 판사는 만들지 않는다")
    i.add_argument("--limit", type=int, default=0)
    i.add_argument("--force", action="store_true")

    a = sub.add_parser("audio", help="앰비언스·효과음 합성 (비용 0원)")
    a.add_argument("--force", action="store_true")

    sub.add_parser("check", help="빠진 에셋 목록")

    args = ap.parse_args()
    if args.cmd == "sheet":
        process_sheet(args.path, args.code, upscale=args.upscale,
                      outline=args.outline, torn=not args.smooth,
                      shadow=not args.no_shadow)
        return 0
    if args.cmd == "sync":
        return cmd_sync(args)
    if args.cmd == "images":
        return cmd_images(args)
    if args.cmd == "audio":
        return cmd_audio(args)
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
