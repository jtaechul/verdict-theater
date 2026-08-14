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
import tempfile
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
import cost                        # noqa: E402  그림값을 장부에 남기고 한도로 막는다
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
# 옛 격자 방식으로 되돌리고 싶을 때만 1 로 둔다 (지금은 덩어리 방식이 기본이다).
FORCE_GRID_SLICE = os.environ.get("VT_GRID_SLICE", "") == "1"
# 스티커·콜라주 느낌의 컷아웃. 잡지에서 오려 붙인 것처럼 보이게 한다.
OUTLINE_RATIO = 0.028          # 흰 테두리 두께 = 인물 높이의 2.8%
# ⚠️ 2026-08-13 — 손님: "하얀 띠 끝이 거칠거칠해." 찢은 종이 느낌을 내려고 일부러
#    잡음을 섞고 있었는데, 화면에서 4배로 늘리니 '손으로 오린 맛' 이 아니라
#    그냥 **지저분한 계단**으로 보였다. 껐다. (되살리려면 True 로만 바꾸면 된다)
TORN_EDGE = False              # 가장자리를 불규칙하게 (지금은 끔 — 거칠어 보인다)
SMOOTH_EDGE = True             # 가장자리 계단을 지운다 (반투명 한두 픽셀로 메움)
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


def lines_touch_figures(sheet):
    """칸 선이 **인물에 닿아 있는가** → (닿은 비율, 나쁜가). 0원.

    ⭐ 2026-08-13 손님: "애시당초 선은 마젠타로 긋고 배경을 초록으로 만들었으면
       이런 일이 없었을 텐데 왜 자꾸 반복되는 거야?"

       **색은 처음부터 그렇게 하고 있었다.** 마젠타 선 · 초록 배경이 맞다.
       빠져 있던 것은 색이 아니라 **어디에 그으라는 말**이었다.
       "3열 6행 격자" 라고만 시켜 놓으니 모델이 인물 위로도 선을 그었다.
       선이 머리에 겹치면 지워도 남겨도 안 되는 상태가 된다 — 같은 픽셀이라서.

       그래서 이제 **잰다.** 규칙만 적어 두고 지켜졌는지 안 재면,
       안 지켜진 채로 그대로 다음 단계로 넘어간다. 그게 반복의 진짜 까닭이다.
       (실측: 지금 시트 7장 전부 1.2~1.9% 가 닿아 있다 — 전부 나쁜 시트다)"""
    import numpy as np
    a = np.asarray(sheet.convert("RGB")).astype(int)
    r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    mag = (r > 100) & (b > 100) & (g < np.minimum(r, b) - 40)
    green = (g > 90) & (g > r + 40) & (g > b + 40)
    body = ~mag & ~green
    if body.sum() == 0 or mag.sum() == 0:
        return 0.0, False
    near = np.asarray(Image.fromarray((mag * 255).astype(np.uint8))
                      .filter(ImageFilter.MaxFilter(7))) > 60
    ratio = float((near & body).sum() / body.sum())
    return ratio, ratio > 0.005


def keep_main_blob(img, erode=5):
    """**이 칸의 주인공 하나만 남긴다.** 격자선 막대와 옆칸 조각을 떼어 낸다.

    ⚠️ 2026-08-13 손님 지적 셋이 **전부 이 한 가지 때문이었다.**
       "① 사각 테두리가 남아있어 ② 오른쪽 캐릭터가 아래로 잘려 있어
        ③ 하얀 띠 끝이 거칠거칠해"

       잘라낸 칸 안에 인물만 있는 게 아니라 **격자선 막대**와 **옆칸 사람의
       조각**이 같이 들어 있었다. 실측:
         M70/full_stand   본인 80.3% + 세로막대(480x3856px) 19.7%
         F70/face_cry     본인 옆에 옆칸 머리카락 조각 + 세로막대
       그런데 이 경로에는 **덩어리 하나만 남기는 단계가 아예 없었다**
       (char_sheet.py 에는 있는데 지금 쓰는 assets_gen 경로에만 빠져 있었다).

       그래서 이렇게 됐다.
         · 막대에도 흰 테두리가 둘러져 → 화면의 **사각 테두리**
         · 인물 상자가 막대까지 포함해 커져서, 그 상자에 맞춰 크기를 정하면
           **사람이 작아지고 아래로 밀린다**
         · 막대의 곧은 직선에 찢은 종이 테두리가 둘러져 **거칠어 보인다**

    어떻게 떼어 내나
       알파(사람이 있는 자리)를 조금 깎으면 막대와 사람이 붙어 있던 얇은
       다리가 끊어진다. 그때 **가장 큰 덩어리 하나만** 고르고 다시 부풀린다.
       격자선은 아무리 길어도 얇아서 깎으면 먼저 끊어지고, 넓이로도 진다."""
    import numpy as np
    a = np.asarray(img.getchannel("A"))
    if a.max() < 8:
        return img
    step = max(1, min(a.shape) // 160)          # 빠르게 보려고 줄여서 본다
    m = a[::step, ::step] > 40
    if m.sum() == 0:
        return img
    # 얇은 다리를 끊는다 (막대와 사람이 닿아 있는 경우)
    k = max(1, erode // step) if step > 1 else erode
    if k >= 1:
        e = m.copy()
        for _ in range(k):
            e[1:, :] &= m[:-1, :]
            e[:-1, :] &= m[1:, :]
            e[:, 1:] &= m[:, :-1]
            e[:, :-1] &= m[:, 1:]
            m2 = e.copy()
            e = m2
        core = e if e.sum() else m
    else:
        core = m
    # 가장 큰 덩어리 찾기
    from collections import deque
    lab = np.zeros(core.shape, np.int32)
    best, best_n = None, 0
    cur = 0
    for y in range(core.shape[0]):
        for x in range(core.shape[1]):
            if core[y, x] and not lab[y, x]:
                cur += 1
                q = deque([(y, x)])
                lab[y, x] = cur
                n = 0
                while q:
                    cy, cx = q.popleft()
                    n += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if (0 <= ny < core.shape[0] and 0 <= nx < core.shape[1]
                                and core[ny, nx] and not lab[ny, nx]):
                            lab[ny, nx] = cur
                            q.append((ny, nx))
                if n > best_n:
                    best_n, best = n, cur
    if best is None:
        return img
    keep = lab == best
    if keep.sum() == core.sum():        # 덩어리가 하나뿐이면 손대지 않는다
        return img
    # 깎은 만큼 다시 부풀려 원래 두께로 돌린다 (넉넉히)
    grow = keep.copy()
    for _ in range(k + 3):
        g = grow.copy()
        g[1:, :] |= grow[:-1, :]
        g[:-1, :] |= grow[1:, :]
        g[:, 1:] |= grow[:, :-1]
        g[:, :-1] |= grow[:, 1:]
        grow = g
    mask = Image.fromarray((grow * 255).astype(np.uint8)).resize(
        img.size, Image.BILINEAR).filter(ImageFilter.GaussianBlur(1.5))
    out = img.copy()
    out.putalpha(ImageChops.multiply(img.getchannel("A"), mask))
    return out


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

    # ⭐ 가장자리를 **매끄럽게** 한다 (2026-08-13 손님: "하얀 띠 끝이 거칠거칠해.
    #    이건 강제로 매끄럽게 처리가 가능하지 않나?" — 가능하다. 이렇게 한다).
    #
    #    위에서 `255 아니면 0` 으로 딱 잘라 버려서 가장자리가 **1비트 계단**이 된다.
    #    거기에 화면에서 4배로 늘리니 계단이 그대로 4배가 되어 눈에 튄다.
    #    번지게 한 뒤 가운데(128)에서 다시 자르되, **자르지 않고 기울기를 남긴다** —
    #    반투명한 한두 픽셀이 계단을 메워 준다(안티에일리어싱).
    if SMOOTH_EDGE:
        s = max(1.0, w * 0.28)
        grown = grown.filter(ImageFilter.GaussianBlur(s))
        # 0~255 를 그대로 두면 테두리가 흐물해진다. 가운데를 기준으로 **가파르게**
        # 세우되 양 끝 몇 단계는 남겨 둔다 — 그 몇 단계가 계단을 지운다.
        lo, hi = 108, 148
        grown = grown.point(lambda v: 0 if v <= lo else (255 if v >= hi else
                                                        int((v - lo) * 255 / (hi - lo))))

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

    # ⭐ 2026-08-13 — **격자로 자르지 않는다. 덩어리를 찾아 오려낸다.**
    #
    #    손님 지적 셋이 전부 여기서 나왔다.
    #      "① 사각 테두리가 남아있어 ② 오른쪽 캐릭터가 아래로 잘려 있어
    #       ③ 하얀 띠 끝이 거칠거칠해"
    #
    #    까닭: 4K 시트의 실제 배치가 **3열 6행이 아니다.** 실측(M70) —
    #      1~4행은 3칸씩(얼굴·상반신 12개)인데
    #      5~6행은 **4칸**이고 전신 서기는 두 행을 통째로 쓴다.
    #    그런데 여기서는 3열 6행 균등으로 우겨서 나눴다. 위쪽 12칸은 우연히
    #    맞고 아래쪽은 전부 어긋나, 한 칸에 **옆 사람 + 격자선 막대**가 같이
    #    들어갔다. 그 막대에도 흰 테두리가 둘러지니 화면에 사각 테두리가 되고,
    #    인물 상자가 막대까지 포함해 커지니 사람이 작아져 아래로 밀렸다.
    #
    #    격자를 맞히려 애쓸 일이 아니다. **격자를 안 보면 된다.**
    #    char_sheet.py 가 이미 그렇게 한다 — 배경 초록을 지우고 남은 덩어리를
    #    하나씩 떼어낸 뒤, 어느 덩어리가 어느 포즈인지 값싼 모델에게 눈으로
    #    확인시킨다(인물당 한 번). 실측: M70 4K 시트에서 **17/17 정확**.
    #
    #    ⚠️ 확인할 열쇠가 없으면 순서대로 짝지어야 하는데, 배치가 제멋대로면
    #       그건 또 어긋난다. 그때만 옛 격자 방식으로 물러선다.
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key and not FORCE_GRID_SLICE:
        try:
            import char_sheet as CS          # 여기서 부른다 (서로 부르는 꼴을 피한다)
            poses = [c for c in CELL_ORDER if c]
            cols, rows = CS.grid_for(len(poses))
            CS.slice_sheet(str(sheet_path), code, poses, cols, rows,
                           outdir=outdir, key=key)
            made = sorted(outdir.glob("*.png"))
            if len(made) >= len(poses) - 2:      # 두어 개 빠지는 건 감수한다
                print(f"{code}: 컷아웃 {len(made)}개 → {outdir} (덩어리 방식)")
                return made
            print(f"  ⚠️ 덩어리 방식으로 {len(made)}개밖에 못 만들었다 — 격자 방식으로 다시 한다")
        except Exception as e:                  # noqa: BLE001
            print(f"  ⚠️ 덩어리 방식 실패({type(e).__name__}: {e}) — 격자 방식으로 간다")

    img = Image.open(sheet_path).convert("RGBA")
    cells = slice_sheet(img)
    made = []
    for i, (cell, name) in enumerate(zip(cells, CELL_ORDER)):
        if name is None:
            continue
        # ⭐ 격자선 막대·옆칸 조각을 떼어 내고 **주인공 하나만** 남긴다.
        #    이 한 줄이 없어서 사각 테두리·인물 축소·거친 가장자리가 다 생겼다.
        cut = trim_alpha(keep_main_blob(drop_chroma(cell)))
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


# ⭐ 그림 크기와 가로세로 비율은 **프롬프트가 아니라 API 로 정한다** (2026-08-12).
#
#    손님 지적: "프롬프트에 해상도를 최대로 높여서 제작하도록 수정하면 되잖아?"
#    → 프롬프트로는 **안 된다는 것이 실측으로 확인됐다.** docs/char-prompts.md 의
#      블록 7개에는 `at least 2048 x 4096 pixels` 가 전부 적혀 있는데,
#      나온 시트 7장은 예외 없이 1.05~1.08 MP 였다(비율만 다르고 픽셀 총량은 같다).
#      모델은 프롬프트의 크기 지시를 무시하고 자기 기본값으로 낸다.
#
#    ⚠️ 그런데 **API 로는 된다.** src/char_sheet.py 가 이미 그렇게 부르고 있었다 —
#       `imageConfig: {aspectRatio, imageSize}`. 이쪽 경로만 그걸 안 보내고 있었다.
#       한 장에 18칸을 우겨넣는데 그 한 장이 1MP 라, 칸 하나가 228x224 밖에 안 되고
#       그 안의 전신 인물은 **105x302** 였다. 그걸 화면에서 800px 로 늘려 쓰니
#       흐리고 계단이 보이는 것이 당연했다. 장수를 늘려 돈을 더 쓸 일이 아니라,
#       **같은 한 장을 크게 받으면 되는 일**이었다.
#
#    비율도 같이 정한다. 이걸 안 보내서 시트가 가로로도 세로로도 제멋대로 나왔고,
#    그래서 자르기가 어긋나 머리 없는 인물이 나왔다.
#
#    ⚠️ 2026-08-13 — 여기에 `1:2` 를 적었다가 **HTTP 400 으로 전부 거절당했다.**
#       3열 6행이니 1:2 가 맞다고 계산했는데, 구글이 받아 주는 값이 정해져 있고
#       거기에 1:2 가 없다. 실측한 목록(400 응답 본문에 적혀 온다)이 RATIO_ALL 이다.
#       계산한 비율을 **받아 주는 값 가운데 가장 가까운 것**으로 맞춰야 한다.
RATIO_ALL = {                       # 구글이 받아 주는 값 (2026-08-13 400 본문에서 실측)
    "1:1": 1.0, "1:4": 0.25, "1:8": 0.125, "2:3": 2 / 3, "3:2": 1.5,
    "3:4": 0.75, "4:1": 4.0, "4:3": 4 / 3, "4:5": 0.8, "5:4": 1.25,
    "8:1": 8.0, "9:16": 9 / 16, "16:9": 16 / 9, "21:9": 21 / 9,
}
# 그중에서도 **모델이 실제로 잘 그리는** 흔한 모양만 쓴다. 1:4·1:8 같은 극단은
# 받아는 주지만 격자를 엉망으로 그린다 — 칸이 어긋나면 또 머리가 잘려 나온다.
RATIO_SAFE = ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9"]


def sheet_ratio(cols=None, rows=None):
    """COLS x ROWS 시트에 맞는 화면비를 **받아 주는 값 중에서** 고른다.

    칸을 정사각형에 가깝게 두는 것이 기준이다(전신은 세로로 길고 얼굴은 정사각에
    가까우니 그 중간이 안전하다). 3열 6행이면 0.5 → `9:16`(0.5625) 이 뽑힌다.

    실측 근거: 시킨 대로 3열 6행으로 그려진 유일한 시트 F50A 가 720x1456 = 0.495
    였다. 받아 주는 값 가운데 그 0.495 에 가장 가까운 것이 바로 9:16 이다."""
    cols = cols or COLS
    rows = rows or ROWS
    want = cols / rows
    return min(RATIO_SAFE, key=lambda k: abs(RATIO_ALL[k] - want))


# 인물 시트는 한 장을 18칸으로 쪼개 쓴다. 그래서 **크게 받아야** 한 칸이 쓸 만해진다.
#   1MP(지금) → 칸 228x224 → 전신 인물 105x302 를 화면 800px 로 늘림 (흐릴 수밖에)
#   2K        → 칸 약 512x448  → 전신 약 400px  (2배 늘림)
#   4K        → 칸 약 1024x896 → 전신 약 800px  (늘리지 않음) ← 화면에 쓰는 크기와 같다
IMAGE_SIZE = os.environ.get("GEMINI_IMAGE_SIZE", "4K")
# 배경은 한 장을 통째로 쓰고 게다가 흐리게 깔리므로 크게 받을 까닭이 없다.
IMAGE_SIZE_BG = os.environ.get("GEMINI_IMAGE_SIZE_BG", "2K")
IMAGE_RATIO = os.environ.get("GEMINI_IMAGE_RATIO", sheet_ratio())
IMAGE_RATIO_BG = os.environ.get("GEMINI_IMAGE_RATIO_BG", "16:9")


# ⭐ 한 번 누를 때 그림에 쓸 수 있는 최대 금액 (원).
#    인물 7명을 4K 로 다 만들어도 약 1,900원이므로 2,500원이면 정상 실행은
#    통과하고, 무언가 잘못 돌아 계속 만들기 시작하면 거기서 멈춘다.
#    ⚠️ 한도는 **실제 드는 값보다 조금만 위**에 있어야 뜻이 있다.
IMAGE_RUN_KRW = float(os.environ.get("VT_IMAGE_RUN_KRW", "2500"))
_img_run_krw = 0.0          # 이번 실행에서 그림에 쓴 값 (원)


class RunCapReached(RuntimeError):
    """이번 실행의 그림값 한도를 다 썼다."""


class QuotaBlocked(RuntimeError):
    """구글이 그림 만들기를 **아예** 안 받아 주는 상태(한도 0). 기다려도 안 된다."""


def quota_blocked(err):
    """429 가 **분당 제한**인지 **아예 0**인지 가린다.

    ⚠️ 2026-08-13 실측 — 이 둘은 완전히 다른 일인데 겉모습이 똑같다.
       분당 제한이면 잠깐 뒤 다시 하면 되지만, `limit: 0` 은 그 모델이 무료로는
       **하루 0장**이라는 뜻이라 내일도 안 된다(결제를 걸어야 열린다).
       구분하지 못하면 손님이 되는 줄 알고 버튼을 계속 헛눌러야 한다."""
    t = str(err)
    return "limit: 0" in t or "limit 0" in t


def gen_image(key, model, prompt, out_path, size=None, ratio=None):
    """그림 한 장을 받아 저장한다. **크기와 비율을 API 로 요청한다.**

    ⚠️ 모델마다 받아 주는 것이 다르다. 요청이 거절당하면 조건을 한 단계씩
       내려 가며 다시 부른다 — 끝내 안 되면 예전처럼 기본 크기로라도 받는다.
       (한 번의 실패로 그림을 통째로 못 만드는 일이 없게)"""
    base = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    size = size or IMAGE_SIZE
    ratio = ratio or IMAGE_RATIO
    if ratio not in RATIO_ALL:
        # ⚠️ 2026-08-13 — 받아 주지 않는 값(1:2)을 보내 400 으로 전부 거절당했다.
        #    보내기 전에 여기서 걸러 **가장 가까운 값으로 바꿔 준다.**
        near = min(RATIO_SAFE, key=lambda k: abs(RATIO_ALL[k] - _as_num(ratio)))
        print(f"      ⚠️ 구글이 '{ratio}' 는 안 받는다 → '{near}' 로 바꿔 보낸다")
        ratio = near
    tries = [
        {"responseModalities": ["IMAGE"],
         "imageConfig": {"aspectRatio": ratio, "imageSize": size}},
        {"responseModalities": ["IMAGE"], "imageConfig": {"imageSize": size}},
        {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": ratio}},
        {"responseModalities": ["IMAGE", "TEXT"]},          # 예전 방식 (마지막 보루)
    ]
    # ⭐ 부르기 **전에** 돈을 막는다 (2026-08-13). 여기가 통째로 비어 있었다 —
    #    그림값은 장부에도 안 남고 한도에도 안 걸렸다. 무료 한도가 0이라
    #    아무것도 안 만들어지던 동안엔 안 드러났는데, 결제를 걸면 그 순간부터
    #    **그림값만 한도 밖에서 새어 나간다.**
    guess = cost.image_krw(model, size)
    if cost.month_total() + guess > cost.MONTH_KRW:
        raise cost.MonthlyCapReached(
            f"이번 달 한도({cost.MONTH_KRW:,.0f}원)에 걸렸습니다. "
            f"지금까지 {cost.month_total():,.0f}원 썼고 이 그림이 약 {guess:,.0f}원입니다.")
    global _img_run_krw
    if _img_run_krw + guess > IMAGE_RUN_KRW:
        raise RunCapReached(
            f"이번 실행의 그림값 한도({IMAGE_RUN_KRW:,.0f}원)에 걸렸습니다. "
            f"이미 약 {_img_run_krw:,.0f}원 썼습니다.")

    last = None
    for i, cfg in enumerate(tries):
        try:
            res = _post(f"{BASE}/models/{model}:generateContent?key={key}",
                        {**base, "generationConfig": cfg}, timeout=600)
            parts = (res.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
            blob = next((p["inlineData"] for p in parts if "inlineData" in p), None)
            if not blob:
                last = RuntimeError("이미지가 오지 않았다")
                continue
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(base64.b64decode(blob["data"]))
            # 실제로 몇 픽셀로 왔는지 **매번 찍는다.** 요청이 먹혔는지 눈으로 안다.
            try:
                w, h = Image.open(out_path).size
                want = "요청대로" if i == 0 else f"{i}단계 낮춰서"
                print(f"      크기 {w}x{h} = {w * h / 1e6:.2f} MP ({want})")
            except Exception:
                pass
            # ⭐ 값을 장부에 남기고, 구글이 실제로 무엇을 셌는지도 같이 찍는다.
            #    usageMetadata 가 진짜 청구 근거다 — 이걸 보고 cost.IMAGE_USD 의
            #    추정값을 실측값으로 고쳐야 장부가 맞는다.
            um = res.get("usageMetadata") or {}
            _img_run_krw += guess
            cost.record("image", guess, f"{model} {size} {ratio} {out_path.name}")
            print(f"      값 약 {guess:,.0f}원 (이번 실행 누적 {_img_run_krw:,.0f}원 "
                  f"/ 한도 {IMAGE_RUN_KRW:,.0f}원)")
            if um:
                print(f"      구글이 센 것: {um}")
            return out_path
        except Exception as e:
            last = e
            if quota_blocked(e):
                # 하루 한도가 0 이다 — 조건을 낮춰도, 내일 다시 해도 안 된다.
                raise QuotaBlocked(str(e)) from None
            if "429" in str(e) or "quota" in str(e).lower():
                raise                                   # 할당량은 낮춰도 안 된다
    raise last or RuntimeError("이미지를 받지 못했다")


def _as_num(ratio):
    try:
        a, b = str(ratio).split(":")
        return float(a) / float(b)
    except Exception:
        return 1.0


BILLING_HELP = (
    "\n" + "─" * 60 + "\n"
    "❌ 구글이 **그림 만들기**를 안 받아 줍니다 (하루 한도 0).\n"
    "\n"
    "   무엇이 문제인가\n"
    "     열쇠(GEMINI_API_KEY)는 멀쩡합니다. 글자(대본) 만들기는 지금도 됩니다.\n"
    "     다만 그림 모델 세 가지가 전부 '무료로는 하루 0장' 상태입니다.\n"
    "     → 잠깐 밀린 것이 아니라서 **기다려도, 내일 다시 눌러도 안 됩니다.**\n"
    "\n"
    "   어떻게 푸나 (둘 중 하나)\n"
    "     ① 구글 AI 스튜디오에서 그 열쇠의 프로젝트에 **결제를 걸어 둡니다.**\n"
    "        https://aistudio.google.com/apikey 에서 열쇠의 프로젝트를 눌러\n"
    "        'Set up Billing' 을 하면 그림 모델이 열립니다.\n"
    "     ② 결제를 안 걸겠다면 인물 그림은 **지금 있는 것을 계속 씁니다.**\n"
    "        소리와 배경 사진은 원래 0원이라 이것과 상관없이 잘 만들어집니다.\n"
    + "─" * 60)


def bg_prompt(code):
    fam = code.split("_")[0]
    place = BG_PLACE.get(code, code)
    return (f"{BG_PROMPTS.get(fam, '한국의 공간')} — {place}. "
            "사진처럼 사실적인 실내/실외 배경. **사람이 등장하지 않는다.** "
            "글자·간판·상표가 보이지 않게. 차분하고 약간 어두운 색조. "
            "가로 16:9 구도, 중앙을 비워 인물을 세울 자리를 남긴다.")


# ⭐⭐ 2026-08-14 — 시트 프롬프트를 통째로 다시 썼다. **칸 선을 안 긋는다.**
#
#    까닭 (손님: "니가 만든 명령 프롬프트가 문제가 있었던 게 맞지?" — 맞다)
#      옛 프롬프트는 격자 지시가 "3열 6행 = 18칸 격자" 한 줄뿐이었다. 그래서
#        · 위 4줄은 3칸인데 아래 2줄은 4칸으로 그려졌고 (균등 격자가 아니었다)
#        · 마젠타 칸 선이 **인물 머리 위로** 그어졌다 (7장 전부 1.2~1.9 퍼센트 접촉)
#      선과 머리가 같은 픽셀이 되면 지워도 남겨도 안 된다. 자르기 7가지가 전멸했다.
#
#    ⭐ 그래서 선을 요구하지 않는다. 칸은 **넓은 초록 여백**으로만 나눈다.
#       선이 없으면 선이 머리에 겹치는 사고가 **물리적으로 불가능**하다.
#       자르는 코드는 이미 덩어리 방식이라 선이 필요 없었다.
#
#    ⭐ 배치를 **미리 산술로 닫았다.** 옛 프롬프트의 더 깊은 잘못은
#       "요구한 배치가 캔버스에 실제로 들어가는지 아무도 계산하지 않은 것" 이다.
#       3열 6행에 18칸을 넣으면 전신 인물 높이가 770px 밖에 안 나오는데
#       거기에 "얼굴은 크게 + 여백 넉넉히" 를 겹쳐 시켰다. 산술적으로 불가능했다.
#         시트1: 위여백 700 + (950 x 4무리) + (사이 200 x 3) = 4620 <= 4804 (된다)
#         시트2: 서기 1700px — 옛 770px 의 2.2배
#
#    ⚠️ 한 장에 18칸 대신 **두 장**으로 나눈다 (얼굴6+상반신6 / 전신5).
#       칸이 적어야 여백이 넉넉해진다. 인물당 265원 x 2 = 530원.
#
#    ⚠️ 만든 뒤에는 반드시 src/sheet_gate.py 로 잰다. 규칙만 적고 지켜졌는지
#       안 재면 안 지켜진 채로 다음 단계로 넘어간다 — 그게 반복의 진짜 까닭이었다.
SHEET_FACE = """한국 드라마 분위기의, 손으로 그린 반실사 극화체 애니메이션 그림 한 장이다. 가로 3072픽셀, 세로 5504픽셀. 넓은 초록 바탕 위에 같은 사람 한 명이 서로 멀리 떨어져 열두 번 그려져 있다.

[사람]
{LOOK}
열두 번 모두 같은 한 사람이다. 얼굴 생김새, 주름 자리, 머리 모양과 색, 눈 색, 옷과 옷 색이 열두 번 모두 똑같다. 달라지는 것은 표정 하나뿐이다.
사람의 몸·머리카락·옷은 서로 맞닿아 끊긴 데 없는 하나의 실루엣을 이룬다. 머리카락은 몸에 붙은 한 덩어리로 그린다. 몸에서 떨어져 나온 조각을 만들지 않는다.
옷과 머리카락은 불투명하다.
두 팔은 몸통 앞이나 옆에 붙이고, 옆으로 벌리지 않는다. 두 손은 비어 있다.

[바탕]
바탕 전체는 #00B140 초록 한 가지 값으로 완전히 평평하게 칠한다. 왼쪽 위부터 오른쪽 아래까지 밝기가 똑같다.
사람의 실루엣 바깥은 첫 픽셀부터 마지막 픽셀까지 전부 #00B140 초록이다. 사람이 아닌 것은 하나도 그리지 않는다.
사람의 실루엣 경계에서 색은 2픽셀 안에서 딱 바뀐다. 경계는 또렷하고 단단하다.
사람의 피부·머리카락·눈·옷·단추·장신구는 초록에서 먼 색으로 칠한다(베이지, 크림, 흰색, 회색, 검정, 남색, 갈색, 팥색, 붉은 계열). 초록·연두·민트·청록은 바탕에만 쓴다.

[놓이는 자리]
열두 사람은 위에서 아래로 네 무리로 나뉜다. 한 무리는 가로로 나란한 세 사람이고, 세 사람은 각각 왼쪽·가운데·오른쪽에 놓인다. 네 무리 모두 정확히 세 사람이고, 그림 전체에 사람은 정확히 열둘이다.
위 두 무리(여섯 사람)는 얼굴을 크게 그린 것이고, 아래 두 무리(여섯 사람)는 허리 위까지 그린 것이다.
이미지 맨 아래쪽 900픽셀 높이만큼은 사람이 하나도 들어오지 않는, 초록만 있는 곳이다. 머리카락 한 올, 옷자락 하나도 그 아래로 내려오지 않는다.
사람과 사람 사이에는 300픽셀 이상 폭의 초록이 이어진다. 좌우 이웃끼리도, 위아래 무리끼리도 그렇다. 열두 사람은 서로 완전히 떨어져 있어 어디에서도 닿지 않는다.
어떤 사람도 이미지의 위·아래·왼쪽·오른쪽 끝에서 300픽셀 이상 안쪽에 있다. 머리 꼭대기 위에도 300픽셀 이상의 초록이 있다.

[크기]
아래 픽셀 값은 **지켜야 하는 크기**다. 더 크게도, 더 작게도 그리지 않는다.
얼굴을 크게 그린 여섯 사람: 머리 꼭대기부터 목 아래까지가 세로 **760픽셀**이다(그림 세로의 약 14%). 780픽셀보다 크면 안 되고 750픽셀보다 작아도 안 된다. 어깨는 그리지 않는다. 좌우 폭은 520픽셀을 넘지 않는다. 여섯 사람의 머리 크기가 서로 똑같다.
허리 위까지 그린 여섯 사람: 머리 꼭대기부터 허리까지가 세로 **760픽셀**이다(그림 세로의 약 14%). 780픽셀보다 크면 안 되고 750픽셀보다 작아도 안 된다. 두 어깨가 다 보인다. 허리 아래는 그리지 않으며, 잘린 단면을 표현하지 않고 자연스럽게 마무리한다. 좌우 폭은 560픽셀을 넘지 않는다. 여섯 사람의 머리 크기와 어깨 폭이 서로 똑같다.
열두 사람 모두 정면을 본다. 고개 기울기와 어깨 각도가 열두 번 모두 같다.

[표정 — 왼쪽에서 오른쪽으로, 위 무리부터 아래 무리로]
첫째 무리: 무표정 · 슬픔 · 분노
둘째 무리: 놀람 · 냉담 · 울음
셋째 무리: 무표정 · 슬픔 · 분노
넷째 무리: 놀람 · 냉담 · 울음

무표정: 입을 다물고 얼굴 근육이 편안히 풀려 있다. 시선은 정면이다.
슬픔: 눈썹 안쪽 끝이 위로 올라가고, 눈꼬리와 입꼬리가 내려가며, 눈 아래가 촉촉하다. 눈물은 흐르지 않는다.
분노: 눈썹 안쪽 끝이 아래로 내려가고, 콧등에 주름이 잡히며, 아래턱에 힘이 들어가 입을 앙다문다.
놀람: 눈꺼풀이 위아래로 크게 열려 흰자가 넓게 보이고, 눈썹이 위로 올라가며, 입이 조금 벌어진다. 눈알 자체의 크기는 다른 다섯 번과 같다.
냉담: 얼굴 근육을 거의 쓰지 않고 입은 곧게 다물려 있다. 눈꺼풀이 살짝 내려와 있고 시선만 차갑게 정면을 응시한다.
울음: 눈물이 두 뺨을 타고 흐르는 젖은 자국으로 보이고, 눈이 붉게 젖으며, 입이 아래로 일그러진다. 눈물방울이 얼굴에서 떨어져 나오지 않는다.

[그림체]
손으로 그린 셀 애니메이션 그림이다.
인체 비율은 실제 성인 그대로 7~8등신이다.
{LOOK}에 적힌 나이가 피부결·주름·눈매·어깨 모양·살집에 그대로 드러난다.
눈은 얼굴 가로폭의 5분의 1 이하 크기로, 실제 사람 눈 비율대로 그린다.
색은 채도가 낮은 차분한 톤이다. 명암은 2~3단계의 부드러운 셀 셰이딩이다.
윤곽은 그 부위 고유색보다 한두 단계 어두운 같은 계열 색으로 얇고 또렷하게 정리한다.
빛은 정면에서 고르고 부드럽게 들어온다.
주름 하나하나와 머리카락 한 올까지 또렷하게 보이고, 그림 전체가 초점이 맞아 있다."""

SHEET_FULL = """한국 드라마 분위기의, 손으로 그린 반실사 극화체 애니메이션 그림 한 장이다. 가로 3072픽셀, 세로 5504픽셀. 넓은 초록 바탕 위에 같은 사람 한 명이 서로 멀리 떨어져 다섯 번, 머리부터 발끝까지 전부 보이게 그려져 있다.

[같은 사람 유지]
이 요청에는 같은 사람의 허리 위 그림 한 장이 참고로 붙어 있다. 붙어 있는 그림과 완전히 같은 사람, 완전히 같은 옷을 그린다. 얼굴 생김새·주름 자리·머리 모양과 색·피부 톤·나이 인상·옷의 종류와 색을 그대로 따른다.
참고 그림에서 가져오는 것은 사람의 생김새와 옷차림뿐이다. 참고 그림의 놓인 자리, 크기, 그려진 사람 수는 따라 하지 않는다. 자리와 크기는 아래에 적힌 대로만 한다.

[사람]
{LOOK}
다섯 번 모두 같은 한 사람이다. 얼굴 생김새, 머리 모양과 색, 눈 색, 옷과 옷 색, 신발이 다섯 번 모두 똑같다. 달라지는 것은 자세 하나뿐이다.
사람의 몸·머리카락·옷·신발은 서로 맞닿아 끊긴 데 없는 하나의 실루엣을 이룬다. 머리카락은 몸에 붙은 한 덩어리로 그린다. 몸에서 떨어져 나온 조각을 만들지 않는다.
옷과 머리카락은 불투명하다. 두 손은 비어 있다.

[바탕]
바탕 전체는 #00B140 초록 한 가지 값으로 완전히 평평하게 칠한다. 왼쪽 위부터 오른쪽 아래까지 밝기가 똑같다.
사람의 실루엣 바깥은 첫 픽셀부터 마지막 픽셀까지 전부 #00B140 초록이다. 사람이 아닌 것은 하나도 그리지 않는다. 발밑에도 초록이 그대로 이어진다.
사람의 실루엣 경계에서 색은 2픽셀 안에서 딱 바뀐다. 경계는 또렷하고 단단하다.
사람의 피부·머리카락·눈·옷·신발·단추는 초록에서 먼 색으로 칠한다(베이지, 크림, 흰색, 회색, 검정, 남색, 갈색, 팥색, 붉은 계열). 초록·연두·민트·청록은 바탕에만 쓴다.

[놓이는 자리]
다섯 사람은 위아래 두 무리로 나뉜다. 위 무리는 가로로 나란한 세 사람이고 각각 왼쪽·가운데·오른쪽에 놓인다. 아래 무리는 두 사람이다. 그림 전체에 사람은 정확히 다섯이고, 여섯 이상 그리지 않는다.
이미지 맨 아래쪽 900픽셀 높이만큼은 사람이 하나도 들어오지 않는, 초록만 있는 곳이다. 아래 무리 두 사람의 발 아래로도 400픽셀 이상의 초록이 더 이어진다.
사람과 사람 사이에는 350픽셀 이상 폭의 초록이 이어진다. 좌우 이웃끼리도, 위아래 무리끼리도 그렇다. 다섯 사람은 서로 완전히 떨어져 있어 팔·다리·머리카락·옷자락 어디에서도 닿지 않는다.
어떤 사람도 이미지의 위·아래·왼쪽·오른쪽 끝에서 300픽셀 이상 안쪽에 있다. 머리 꼭대기 위에도, 발끝 아래에도 300픽셀 이상의 초록이 있다.

[크기]
아래 픽셀 값은 **지켜야 하는 크기**다. 더 크게도, 더 작게도 그리지 않는다.
다섯 사람은 모두 같은 몸 크기로 그린다. 머리 크기가 다섯 번 모두 똑같다.
똑바로 서 있는 사람은 머리 꼭대기부터 발바닥까지가 세로 **1400픽셀**이다(그림 세로의 약 25%). 1500픽셀보다 크면 안 되고 1300픽셀보다 작아도 안 된다.
앉거나 주저앉은 사람은 몸 크기가 같으므로 자세 때문에 자연히 더 낮아진다. 억지로 확대하거나 축소하지 않는다.
한 사람의 좌우 폭은 560픽셀을 넘지 않는다.

[다섯 자세]
위 무리 왼쪽 — 똑바로 서기: 정면을 보고 선다. 두 발은 어깨너비로 벌리고, 두 팔은 몸통에서 손바닥 하나만큼 떨어뜨려 자연스럽게 내린다. 머리 꼭대기부터 발바닥까지 다 보인다.
위 무리 가운데 — 걷기: 옆에서 살짝 비스듬히 본 각도로 한 걸음 막 내딛는 순간이다. 보폭은 크지 않고, 두 팔은 몸에 가깝게 앞뒤로 조금만 벌어진다. 앞발과 뒷발이 모두 보인다.
위 무리 오른쪽 — 뒷모습으로 서기: 뒤통수와 등과 발뒤꿈치가 보인다. 머리카락이 덮인 뒤통수가 또렷하게 보인다. 두 발은 어깨너비로 벌리고 똑바로 선다.
아래 무리 왼쪽 — 의자에 앉기: 정면을 보고 등을 펴고 앉는다. 무릎은 직각이고 두 발바닥이 나란히 놓인다. 엉덩이가 무릎과 비슷한 높이에 있다. 의자와 소품은 그리지 않고 사람만 그린다.
아래 무리 오른쪽 — 바닥에 주저앉기: 엉덩이가 바닥에 닿고, 두 무릎을 굽혀 몸 앞으로 모으며, 고개를 아래로 숙이고 등을 둥글게 만다. 두 손은 무릎이나 몸 가까이 둔다. 앉은 자세보다 훨씬 낮고 웅크린 모습이다.

[표정]
다섯 번 모두 담담하고 평온한 표정이다.

[그림체]
손으로 그린 셀 애니메이션 그림이다.
인체 비율은 실제 성인 그대로 7~8등신이다.
{LOOK}에 적힌 나이가 피부결·주름·눈매·어깨 모양·자세·살집에 그대로 드러난다.
눈은 얼굴 가로폭의 5분의 1 이하 크기로, 실제 사람 눈 비율대로 그린다.
색은 채도가 낮은 차분한 톤이다. 명암은 2~3단계의 부드러운 셀 셰이딩이다.
윤곽은 그 부위 고유색보다 한두 단계 어두운 같은 계열 색으로 얇고 또렷하게 정리한다.
빛은 정면에서 고르고 부드럽게 들어온다.
옷 주름 하나하나와 머리카락 한 올까지 또렷하게 보이고, 그림 전체가 초점이 맞아 있다."""


def char_sheet_prompt(code, kind="face"):
    """인물 시트 프롬프트. kind='face' 얼굴6+상반신6 · 'full' 전신5."""
    look = CHAR_LOOK.get(code, "한국 중년")
    base = SHEET_FACE if kind == "face" else SHEET_FULL
    return base.replace("{LOOK}", look)


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
        # ⭐ 2026-08-14 — 인물 하나가 **시트 두 장**이다 (얼굴6+상반신6 / 전신5).
        #    한 장에 18칸을 우겨넣던 것이 배치 붕괴의 뿌리였다. 칸이 적어야
        #    여백이 넉넉해지고, 전신 인물이 770px -> 1700px 로 커진다.
        #    파일 이름: M70.png(얼굴+상반신) · M70_full.png(전신)
        for code in codes:
            base = code if args.variant <= 1 else f"{code}-{args.variant}"
            for kind, suffix in (("face", ""), ("full", "_full")):
                if getattr(args, "kind", "") and args.kind != kind:
                    continue
                name = base + suffix
                p = ASSETS / "sheets" / f"{name}.png"
                if not p.exists() or args.force:
                    jobs.append(("char", name, p, char_sheet_prompt(code, kind)))
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
    blocked = None
    for kind, code, path, prompt in jobs:
        try:
            m = models.get(kind) or models.get("char") or models.get("bg")
            gen_image(key, m, prompt, path,
                      size=IMAGE_SIZE_BG if kind == "bg" else IMAGE_SIZE,
                      ratio=IMAGE_RATIO_BG if kind == "bg" else IMAGE_RATIO)
            made += 1
            print(f"  {kind} {code} → {path.name}  ({m})")
            if kind == "char":
                # ⭐⭐ 2026-08-14 — **만든 즉시 잰다.** 이 세 줄이 없어서 하루가 날아갔다.
                #    나쁜 시트를 자르려고 코드를 일곱 번 고쳤고 일곱 번 다 실패했다.
                #    시트가 나쁘면 자르기로는 못 고친다 — 받은 자리에서 멈춰야 한다.
                #    (규칙만 적고 지켜졌는지 안 재는 것이 반복의 진짜 까닭이었다)
                import sheet_gate
                sk = "full" if path.stem.endswith("_full") else "face"
                if sheet_gate.check(path, sk) != 0:
                    bad = ASSETS / "sheets" / "bad"
                    bad.mkdir(parents=True, exist_ok=True)
                    path.rename(bad / path.name)
                    print(f"  ⚠️ {code} 시트가 검사에 걸려 **컷아웃을 만들지 않는다.**")
                    print(f"     원본은 assets/sheets/bad/{path.name} 에 두었다.")
                    made -= 1
                    continue
                process_sheet(path, code.replace("_full", ""))
        except QuotaBlocked as e:
            # ⚠️ 2026-08-13 — 여기서 **바로 멈춘다.** 하루 한도가 0 이면 남은
            #    6장을 더 두드려 봐야 똑같이 거절당한다(4단계씩 28번 헛수고).
            blocked = e
            print(f"  {kind} {code} 실패: 하루 한도 0")
            break
        except Exception as e:
            print(f"  {kind} {code} 실패: {type(e).__name__}: {e}")
    print(f"\n완료 {made}/{len(jobs)}")
    if blocked:
        print(BILLING_HELP)
    # ⚠️ 2026-08-13 — 예전에는 한 장도 못 만들어도 0(성공)으로 끝났다.
    #    깃허브 화면에는 **초록 체크**가 뜨고 손님은 다 된 줄 안다. 그러면 안 된다.
    #    한 장이라도 만들었으면 성공, 하나도 못 만들었으면 실패로 알린다.
    if made == 0 and jobs:
        return 3 if blocked else 1
    return 0


def cmd_probe(_args):
    """그림을 **만들 수 있는 상태인지만** 두드려 본다.

    ⚠️ 2026-08-13 에 이것이 없어서 손님이 헛수고를 할 뻔했다. [기본 3가지] 를
       누르면 소리·배경까지 다 끝내고 **마지막에** 인물에서 막히는데, 그마저
       `|| true` 로 삼켜져 깃허브에는 초록 체크가 떴다. 다 된 줄 알게 된다.
       그래서 값이 나가기 전에 **먼저 물어볼 수 있는 버튼**을 만든다.

    값: 막혀 있으면 **0원**(거절당하면 돈이 안 나간다). 열려 있으면 시험용
        그림 한 장 값(약 57원)이 나가고, 그 한 장으로 크기가 얼마나 오는지까지
        같이 알 수 있다 — 이게 사실 확인하려던 바로 그것이다."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("❌ GEMINI_API_KEY 가 없다.")
        return 2
    print("그림을 만들 수 있는 상태인지 확인합니다 (막혀 있으면 0원).")
    print(f"  요청할 조건 — 크기 {IMAGE_SIZE} · 비율 {IMAGE_RATIO}"
          f" (인물 시트 {COLS}열 {ROWS}행에 맞춘 값)")
    out = Path(tempfile.gettempdir()) / "probe.png"
    for kind in ("char", "bg"):
        model = pick_image_model(key, kind)
        if not model:
            print(f"  {kind}: 쓸 모델을 못 찾았다")
            continue
        try:
            gen_image(key, model, "A plain red circle on a white background.", out,
                      size=IMAGE_SIZE_BG if kind == "bg" else IMAGE_SIZE,
                      ratio=IMAGE_RATIO_BG if kind == "bg" else IMAGE_RATIO)
            print(f"  ✅ {kind}: {model} — 만들 수 있습니다")
        except QuotaBlocked:
            print(f"  ❌ {kind}: {model} — 하루 한도 0 (막혀 있습니다)")
            print(BILLING_HELP)
            return 3
        except Exception as e:
            print(f"  ⚠️ {kind}: {model} — {type(e).__name__}: {str(e)[:200]}")
            return 1
    print("\n그림 만들기: 열려 있습니다. [기본 3가지] 를 눌러도 됩니다.")
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
    #
    # ⭐ 규칙 (2026-08-13) — **`sine=` 을 쓰지 마십시오.**
    #    순수음(sine)은 어떻게 손질해도 '삑' 이나 '웅' 으로 들린다. 자연에 순수음은
    #    없다 — 진짜 소리는 전부 잡음이 섞여 있다. 이 표에 sine 으로 만든 것이
    #    넷 있었고, 손님이 그 넷을 전부 귀로 듣고 빼 달라고 하셨다.
    #        monitor 880Hz · clock 1400Hz · phone 1000Hz · heartbeat 52Hz
    #    (tools/sfx_test.py 가 이 표에 sine 이 들어오면 실패시킨다)
    #
    # ⚠️ clock·phone·heartbeat 를 **다시 넣지 마십시오.**
    #    2026-08-13 손님: "시계초침 소리같이 '척척척척척' 이런 소리가 나는데
    #                      매우 어울리지 않고 어색하고 겉도는 느낌이야."
    #    clock 은 2026-08-09 에도 같은 지적을 받아 파일을 지웠는데, **만드는 법이
    #    여기 남아 있어서** [소리 (비용 0원)] 버튼 한 번에 되살아났다. 게다가
    #    되살아난 파일은 검사(is_beep)까지 빠져나갔다 — 옛 파일은 2초여서 걸렸는데
    #    새로 만들어진 것은 4초라 '한 높이에 몰린 정도' 가 0.1% 로 떨어졌다.
    #    그래서 **만드는 법 자체를 없앤다.** 지우는 것만으로는 부족했다.
    #
    # ⚠️ footsteps·monitor 도 마찬가지로 넣지 마십시오.
    #      footsteps  갈색 잡음 저역통과 → 발소리가 아니라 둔탁한 '툭'
    #                 (2026-08-12: "41초 부근 효과음 이상한 거잖아. 들어가지 않게 해")
    #      monitor    880Hz 순수음 → 그 소리가 곧 "삑 삑"
    #                 (2026-08-09: 6분30초의 그 소리)
    #    진짜 녹음이 필요하면 [효과음 받아오기 (Freesound)] 로 받으십시오(0원).
    "gavel":     "anoisesrc=c=white:d=0.09:a=0.9,lowpass=f=900,volume=1.4,apad=pad_dur=0.5",
    "paper":     "anoisesrc=c=white:d=0.5:a=0.25,highpass=f=1800,volume=0.9",
    "tear":      "anoisesrc=c=white:d=0.8:a=0.35,highpass=f=1200,volume=1.0",
    "door":      "anoisesrc=c=brown:d=0.3:a=0.5,lowpass=f=400,volume=1.2,apad=pad_dur=0.4",
    "stamp":     "anoisesrc=c=white:d=0.07:a=0.8,lowpass=f=600,volume=1.3,apad=pad_dur=0.4",
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


# 시트 한 장이 이만큼은 되어야 한 칸(18분의 1)이 쓸 만해진다.
# 2K(9:16) 가 약 4.1MP 이므로 그보다 조금 낮게 잡아 여유를 둔다.
MIN_SHEET_MP = 3.5


def sheet_report():
    """시트가 **작아서 흐린 것**을 찾아 알린다. 값 0원.

    ⚠️ 2026-08-13 — 이게 없어서 '두 번 일' 이 날 뻔했다. 시트는 있기만 하면
       빠진 것으로 안 잡히므로, 1MP 짜리 옛날 시트 5장이 그대로 남아 있어도
       아무 데도 안 나온다. 그러면 나중에 못 쓰는 2장만 다시 만들게 되고,
       한 영상 안에서 어떤 배우는 또렷하고 어떤 배우는 흐려진다.
       **한 번에 다 바꿔야 한다는 것을 여기서 알려 준다.**"""
    small = []
    for p in sorted((ASSETS / "sheets").rglob("*.png")):
        if "old" in p.parts:                 # 되돌리려고 남겨 둔 옛 시트는 세지 않는다
            continue
        try:
            w, h = Image.open(p).size
        except Exception:
            continue
        mp = w * h / 1e6
        if mp < MIN_SHEET_MP:
            small.append((p, w, h, mp))
    if not small:
        return
    print(f"\n⚠️ 흐린 시트 {len(small)}장 (한 장이 {MIN_SHEET_MP}MP 는 돼야 합니다)")
    for p, w, h, mp in small:
        c, r = sheet_layout((w, h))          # 가로로 그려진 시트는 6열 3행이다
        print(f"   {p.relative_to(ROOT)}  {w}x{h} = {mp:.2f}MP"
              f"  → 칸 하나 약 {round(w / c)}x{round(h / r)}")
    print("   이 시트로 만든 인물은 화면에서 늘려 쓰기 때문에 흐리게 보입니다.")
    print("   ⭐ 다시 만들 때는 **한꺼번에 전부** 만드십시오. 몇 장만 바꾸면"
          " 한 영상 안에서 또렷한 배우와 흐린 배우가 섞입니다.")


def cmd_check(args):
    mf = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
    need = mf["required_files"]
    missing = [f for f in need if not (ROOT / f).exists()]
    have = len(need) - len(missing)
    print(f"에셋 {have}/{len(need)}개 준비됨")
    sheet_report()
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
    # ⭐ 인물 하나가 시트 두 장이다. 시범으로 한 장만 뽑을 때 쓴다.
    i.add_argument("--kind", choices=["face", "full"], default="",
                   help="face=얼굴6+상반신6 · full=전신5 (비우면 둘 다)")

    a = sub.add_parser("audio", help="앰비언스·효과음 합성 (비용 0원)")
    a.add_argument("--force", action="store_true")

    sub.add_parser("check", help="빠진 에셋 목록")
    sub.add_parser("probe", help="그림을 만들 수 있는 상태인지만 확인 (막혀 있으면 0원)")

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
    if args.cmd == "probe":
        return cmd_probe(args)
    return cmd_check(args)


if __name__ == "__main__":
    sys.exit(main())
