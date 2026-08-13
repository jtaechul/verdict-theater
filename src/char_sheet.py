#!/usr/bin/env python3
"""인물 컷아웃을 만든다 — **인물 한 명당 시트 한 장**.

    GEMINI_API_KEY=... python3 src/char_sheet.py data/scripts/EP001.json
    GEMINI_API_KEY=... python3 src/char_sheet.py data/scripts/EP001.json --only F70
    GEMINI_API_KEY=... python3 src/char_sheet.py data/scripts/EP001.json --plan   (부르지 않고 계획만)
    python3 src/char_sheet.py data/scripts/EP001.json --slice build/sheets/F70.png F70

왜 한 명당 한 장인가 — **동질성**
    포즈마다 따로 만들면 같은 인물의 얼굴이 매번 달라진다. 12분짜리 드라마에서
    주인공 얼굴이 컷마다 바뀌면 이야기가 성립하지 않는다.
    한 장 안에 필요한 포즈를 전부 넣으면 모델이 **한 사람을 그리는 문제**로 풀기 때문에
    얼굴이 유지된다. 호출도 인물 수만큼(7번)이면 끝난다.

어떻게 오려내나
    배경을 순수한 크로마 그린으로 칠하게 하고, 그 색을 지워 투명하게 만든다.
    그다음 **남은 덩어리를 찾아** 하나씩 떼어낸다.

    ⚠️ 격자선을 긋게 하고 3분의 1씩 잘라내는 방법은 쓰지 않는다.
       모델이 그리는 격자는 픽셀 단위로 정확하지 않아서, 조금만 밀려도 인물의
       팔다리가 잘려 나간다. 덩어리를 직접 찾으면 격자가 삐뚤어도 상관이 없다.

    맨 끝 칸은 일부러 비운다. 제미나이 로고가 오른쪽 아래에 찍히기 때문이다.
"""
import argparse
import base64
import json
import os
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import assets_gen as A  # noqa: E402
from llm import BASE, _post  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MODEL = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3-pro-image")
SIZE = os.environ.get("GEMINI_IMAGE_SIZE", "4K")

# 모델이 받아 주는 화면비. 격자에서 계산한 비율을 여기에 가장 가까운 것으로 맞춘다.
RATIOS = {"1:1": 1.0, "3:2": 1.5, "2:3": 2 / 3, "4:3": 4 / 3, "3:4": 0.75,
          "5:4": 1.25, "4:5": 0.8, "16:9": 16 / 9, "9:16": 9 / 16}

# 인물 생김새. 회차가 바뀌어도 같은 코드면 같은 사람이어야 한다.
LOOK = {
    "F50A": "a 60-year-old Korean woman, short permed dark hair with grey strands, "
            "tired kind eyes, thin face, wearing a light beige knit sweater and black trousers",
    "F50B": "a 50-year-old Korean woman, neat shoulder-length bob, sharp cool eyes, "
            "wearing a deep burgundy blouse and black trousers",
    "F70": "a 70-year-old Korean woman, white permed hair, deeply lined face, "
           "stooped shoulders, small frame, wearing a soft lilac vest over a white "
           "blouse and black trousers",
    "M50A": "a 50-year-old Korean man, short greying hair, square jaw, heavy build, "
            "wearing a navy suit jacket, white shirt and black trousers",
    "M50B": "a 48-year-old Korean man, receding hairline, thin face, tired eyes, "
            "wearing an olive-green zip-up jacket and dark trousers",
    "M70": "a 70-year-old Korean man, thin white hair, gaunt lean face, frail thin body, "
           "wearing a brown cardigan over a white shirt and grey trousers",
    "JUDGE": "a Korean judge in a black judicial robe with a white collar, "
             "middle-aged, composed, hair neatly combed",
}

# 칸마다 무엇을 그릴지. 표정 낱말과 프레이밍으로 나뉜다.
FRAME = {
    # ⚠️ '얼굴로 화면을 채워라' 라고 하면 모델이 **머리카락 위쪽을 잘라서** 그린다.
    #    (실측: 판사 얼굴을 두 번 뽑았는데 두 번 다 정수리가 평평하게 잘렸다.)
    #    '머리 전체가 여백과 함께 다 보이게' 로 못 박는다.
    # ⚠️ '쇄골 바로 아래에서 자른다' 로 뽑았더니 **턱이 그림 높이의 75~93%** 에 왔다.
    #    그 그림을 화면 바닥에 붙이면 턱이 바닥 근처라 자막이 얼굴을 덮고, 얼굴을 올리면
    #    몸통이 바닥에서 뜬다. 둘 다 사용자가 하지 말라고 한 것이다.
    #    → 턱 아래에 가슴이 충분히 있어야 한다. **턱을 그림 한가운데**로 못 박는다.
    # ⭐ 손님 요청(3번) — 어깨가 잘리지 않고, 상체가 화면 위쪽까지 올라오게.
    #    실측으로 찾은 원인: 기존 그림이 거의 **정사각형**(가로÷세로 0.82~1.06)이었다.
    #    어깨 너비와 그림 높이가 비슷해서, 화면에서 키우면 세로로 커지기 전에
    #    **가로가 먼저 꽉 차** 더 못 커진다. 세로 쇼츠에서는 인물이 화면 높이의
    #    48%밖에 안 됐다 — 상체가 중간 위로 못 올라오는 이유가 이것이다.
    #    → 허리까지 넣어 **세로로 긴 비율**로 만들고, 어깨 양옆에 여백을 둔다.
    #      그러면 가로에 안 막혀 더 커지고, 어깨가 잘릴 일도 없다.
    # ⭐ 어깨 여백을 **숫자로** 적는다. '넓은 여백' 이라고만 적어 두었더니
    #    어깨가 칸 끝까지 차서 옆 사람과 맞닿았다(LAYOUT 의 SPACING 주석 참고).
    "face": "a chest-up portrait in PORTRAIT orientation, clearly taller than it is "
            "wide. The WHOLE head including all the hair is visible with clear empty "
            "space above it. BOTH shoulders are drawn complete and end well inside the "
            "cell: the shoulder tips reach at most the middle 70% of the cell's width, "
            "leaving 15% or more pure green beyond each shoulder tip. "
            "The body is cut off just below the "
            "chest, and that cut edge runs straight and level across the picture. "
            "The chin sits near the vertical middle of the picture",
    "bust": "a waist-up shot in PORTRAIT orientation, clearly taller than it is wide. "
            "The whole head is visible with empty space above it. BOTH shoulders are "
            "drawn complete and end well inside the cell: the shoulder tips reach at "
            "most the middle 70% of the cell's width, leaving 15% or more pure green "
            "beyond each shoulder tip. The body is cut off at the waist, and that cut "
            "edge runs straight and level across the picture. "
            "The chin sits near the vertical middle",
    "full": "the entire body from head to feet, standing in the middle of the cell",
}
MOOD = {
    "neutral": "calm neutral expression, lips closed",
    "sad": "sorrowful expression, eyes lowered, brows drawn together",
    "anger": "angry expression, jaw set, brows down, mouth tight",
    "shock": "shocked expression, eyes wide, mouth slightly open",
    "cold": "cold distant expression, eyes narrowed, unreadable",
    "cry": "crying, tears on the cheeks, face crumpled",
}
BODY = {
    "stand": "standing straight, arms at the sides, facing the viewer",
    "walk": "walking forward, mid-stride, seen from the front",
    "sit": "sitting upright on a plain chair, hands on the knees",
    "sit_down": "collapsed sitting on the floor, shoulders slumped, head down",
    "back": "seen from behind, facing away from the viewer",
}


def cell_text(pose):
    """포즈 이름을 그림 지시문으로 바꾼다. full_sit_down 처럼 밑줄이 둘인 것도 받는다."""
    kind, _, rest = pose.partition("_")
    if kind == "full":
        return f"{FRAME['full']}, {BODY.get(rest, rest)}, neutral expression"
    return f"{FRAME.get(kind, kind)}, {MOOD.get(rest, rest)}"


def grid_for(n):
    """포즈 n개를 담을 격자 (열, 행). 맨 끝 칸 하나는 반드시 비워 둔다.

    비워 두는 이유: 제미나이 로고가 오른쪽 아래에 찍힌다. 거기에 인물이 있으면
    로고가 얼굴 위에 얹힌다."""
    need = n + 1
    best = None
    for cols in (2, 3, 4):
        rows = -(-need // cols)
        # 칸 하나를 세로 3:4 로 보고 시트 전체 비율을 잰다. 1:1 에 가까울수록 좋다
        ratio = (cols * 3) / (rows * 4)
        score = abs(ratio - 1.0) + (cols * rows - need) * 0.05
        if best is None or score < best[0]:
            best = (score, cols, rows)
    return best[1], best[2]


def nearest_ratio(cols, rows):
    want = (cols * 3) / (rows * 4)
    return min(RATIOS, key=lambda k: abs(RATIOS[k] - want))


def sheet_prompt(code, poses, cols, rows):
    look = LOOK.get(code, "a middle-aged Korean person")
    lines = [f"  cell {i + 1}: {cell_text(p)}" for i, p in enumerate(poses)]
    blanks = cols * rows - len(poses)
    return (
        f"A character reference sheet of ONE single person: {look}.\n"
        f"Photorealistic, evenly lit studio lighting, natural skin, realistic proportions.\n\n"
        f"LAYOUT — obey exactly:\n"
        f"  - Arrange the figures in a {cols} by {rows} grid, reading left to right, top to bottom.\n"
        f"  - Draw NO labels, NO text, NO numbers, NO captions.\n"
        # ⭐ 색 약속은 assets_gen 에 한 벌만 둔다. 여기서 따로 쓰면 언젠가 어긋난다.
        + A.COLOUR_RULE_EN +
        # ⭐ 칸 선은 **금지하지 말고 시킨다.** 실측으로 확인한 결론이다.
        #      "그리지 마라"            → 검은 줄 (1,1,1) 을 그었다
        #      "그리더라도 초록으로"     → 둘 중 하나만 초록. 안 보이는 선을 그리라는
        #                                 모순된 지시라 모델이 버틴다
        #      "마젠타로 그려라"         → **검은 줄 0개.** 따를 수 있는 지시라 따른다
        #    마젠타는 사진 안 어디에도 없다 — 피부·남색 양복·검은 법복·흰 셔츠·흰머리
        #    무엇도 '초록이 가장 낮고 빨강·파랑이 둘 다 높다' 를 만족하지 않는다.
        #    그래서 잘라내기 전에 degrid 가 확실히 골라 지운다.
        # ⭐ 여백은 **숫자로** 못 박는다.
        #    예전에는 "a clear band of pure green", "a wide empty margin" 처럼
        #    말로만 적었다. '넓게' 가 얼마인지 모델이 알 수 없으니 지켜질 리가 없다.
        #    실제로 인물들이 어깨를 맞대고 나왔고, 잘라낼 때 억지로 갈라내느라
        #    **옆 사람 옷자락 조각**이 딸려와 화면에 뾰족이로 나왔다(23장).
        #    그래서 ① 몇 %인지 ② 무엇이 가장 넓은 부분인지 ③ 안 맞으면 무엇을
        #    포기해야 하는지 ④ 이 그림이 나중에 어떻게 쓰이는지 를 전부 적는다.
        f"  - SPACING — this is a hard requirement, not a preference:\n"
        f"    · Each figure must fit inside the MIDDLE 70% of its own cell's width.\n"
        f"      That leaves at least 15% of the cell width as pure green on the figure's\n"
        f"      left AND at least 15% as pure green on its right.\n"
        f"    · The SHOULDERS are the widest part of a person. Draw both shoulders complete,\n"
        f"      and make sure pure green is visible beyond BOTH shoulder tips.\n"
        f"      Hands, elbows and hair count as part of the figure's width too.\n"
        f"    · No two figures may come closer to each other than that green gap.\n"
        f"      Nothing of one figure may ever enter a neighbouring figure's cell.\n"
        f"    · If a figure does not fit with that much green around it, DRAW IT SMALLER.\n"
        f"      Never crop it, never shift it to the edge, never shrink the green gap.\n"
        f"  - WHY this matters: this sheet is cut apart automatically along the pure green.\n"
        f"    If two figures touch, the cutter slices through both and each one keeps a\n"
        f"    torn scrap of its neighbour. A generous green gap is more important than\n"
        f"    figure size — always choose the gap.\n"
        f"  - ⚠️ EVERY figure is COMPLETE and fully inside its own cell, with pure green visible on all\n"
        f"    four sides of it. Never let a head, hair, shoulder or hand touch or run off the edge of\n"
        f"    the image or of its cell. For close-ups, the whole head including all the hair must fit\n"
        f"    with green space around it — zoom out rather than crop.\n"
        f"  - Cast NO shadow on the background. No floor, no ground, no props except a plain chair when sitting.\n"
        f"  - The last {blanks} cell(s) at the bottom right are EMPTY — pure green, no figure.\n\n"
        f"CELLS:\n" + "\n".join(lines) + "\n\n"
        f"CONSISTENCY — this is the most important rule:\n"
        f"  Every cell shows THE SAME PERSON. Identical face, identical hair, identical clothes,\n"
        f"  identical age and body type in all cells. Only the framing and expression change.\n"
        f"  Clothing is navy on top and black below in every cell — never grey, never brown.\n"
    )


def gen_sheet(key, prompt, out_path, cols, rows):
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": nearest_ratio(cols, rows), "imageSize": SIZE},
        },
    }
    res = _post(f"{BASE}/models/{MODEL}:generateContent?key={key}", body, timeout=600)
    parts = (res.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    blob = next((p["inlineData"] for p in parts if "inlineData" in p), None)
    if not blob:
        raise RuntimeError(f"이미지가 오지 않았다: {json.dumps(res)[:400]}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(blob["data"]))
    return out_path


# 오려낸 뒤 작업할 최대 높이(픽셀).
# ⚠️ 4K 시트에서 인물 하나가 2400픽셀이 넘는데, 흰 테두리를 두르는 형태 연산은
#    높이가 커질수록 급격히 느려진다(실측: 1200px 6.7초 → 2400px 은 분 단위).
#    렌더러가 인물을 쓰는 최대 크기는 세로 쇼츠에서 약 1050픽셀이다.
#    1200픽셀로 줄여 놓고 작업하면 화질 손해 없이 수십 배 빨라진다.
WORK_H = 1200


# ── 칸 선 지우기 (시트 단계에서 · 자르기 전에) ─────────────
#
# ⭐ 칸 선 문제의 전말 — 실제로 뽑아서 재보고 알아낸 것
#
#    ① 제미나이는 "격자선을 그리지 마라" 라고 써도 **그린다.** 뽑아 재보니 칸 사이에
#       (1,1,1) · (2,7,1) 짜리 검은 줄이 있었다. 배경은 (0,174,77) 초록인데도.
#       '캐릭터 시트' 라는 개념에 칸 테두리가 워낙 강하게 붙어 있어 금지어가 안 통한다.
#
#    ② "그리더라도 배경과 같은 초록으로" → **절반만 통했다.** 하나는 초록이 됐고
#       하나는 검은 채였다. 안 보이는 선을 그리라는 모순된 지시라 모델이 버틴다.
#
#    ③ ⭐ **"마젠타로 그려라" → 검은 줄 0개.** 금지하지 말고 **시켜야** 한다.
#       모델이 그리고 싶어 하는 선을, 사진 안에 절대 없는 색으로 그리게 한다.
#       (사람 피부·남색 양복·검은 법복·흰 셔츠·흰머리 어디에도 마젠타는 없다)
#       이제 프롬프트가 그렇게 시킨다 — sheet_prompt() 참조.
#
#    ④ 그래도 지우는 단계는 남긴다. 모델이 언제 또 검게 그릴지 모르기 때문이다.
#       **자르기 전**이어야 한다 — 잘라낸 뒤에는 선이 옷에 붙어 법복·니트·구두와
#       구분이 불가능하다(그 방식으로 다섯 번 실패했다).
#       시트에서는 선이 그림을 처음부터 끝까지 관통한다. 실측:
#           칸 선이 있는 줄 : 100%      가장 어두운 옷 : 21.7%
#       한 번도 겹치지 않아 안전하게 가를 수 있다.
GRID_DARK = 20      # 가장 밝은 채널이 이 값 미만이면 '어두운 점'
                    # ⚠️ 40 으로 잡았다가 **일부만 초록으로 나온 칸선을 놓쳤다.**
                    #    실측(문턱 40): 그 칸선 70% · 가장 어두운 옷 39% — 여유가 없다.
                    #    문턱 20 에서는 옷이 최대 21.7% 로 떨어지고 칸선은 100% 그대로다.
GRID_SPAN = 0.45    # 그 줄의 이 비율 이상이 걸리면 칸 선
                    # 실측(문턱 20): 칸선 100% · 칸선 아닌 곳 최대 21.7% — 2배 여유
GRID_THICK = 0.02   # 그림 폭·높이의 이 비율보다 두꺼우면 선이 아니다


def _is_mag(p):
    """마젠타인가 — 판정은 assets_gen 에 한 벌만 둔다."""
    return A.is_magenta(p[0], p[1], p[2])


def degrid(img):
    """시트에 그어진 칸 선을 **배경 초록으로 덮는다.** → (고친 시트, 지운 줄 수)

    초록으로 덮으면 바로 다음 단계의 크로마 키가 배경과 함께 통째로 걷어낸다.
    인물에 딸려 나갈 여지가 아예 없어진다."""
    im = img.convert("RGB")
    W, H = im.size
    px = im.load()
    sy = max(1, H // 600)
    sx = max(1, W // 600)

    # 칸 선은 **검거나(모델이 제멋대로 그린 것) 마젠타(우리가 시킨 것)** 다.
    # 둘 다 여기서 배경 초록으로 덮으면 바로 다음 크로마 키가 통째로 걷어낸다.
    def hit(p):
        return max(p[0], p[1], p[2]) < GRID_DARK or _is_mag(p)

    cols = [x for x in range(W)
            if sum(1 for y in range(0, H, sy) if hit(px[x, y]))
            >= len(range(0, H, sy)) * GRID_SPAN]
    rows = [y for y in range(H)
            if sum(1 for x in range(0, W, sx) if hit(px[x, y]))
            >= len(range(0, W, sx)) * GRID_SPAN]

    def thin_groups(idx, limit):
        """이어진 덩어리로 묶고, 얇은 것만 돌려준다 (두꺼우면 선이 아니다)"""
        out, i = [], 0
        while i < len(idx):
            j = i
            while j + 1 < len(idx) and idx[j + 1] == idx[j] + 1:
                j += 1
            if idx[j] - idx[i] + 1 <= limit:
                out.append((idx[i], idx[j]))
            i = j + 1
        return out

    gc = thin_groups(cols, max(4, int(W * GRID_THICK)))
    gr = thin_groups(rows, max(4, int(H * GRID_THICK)))
    if not gc and not gr:
        return img, 0

    out = img.convert("RGBA")
    pad = 2                       # 선 가장자리의 흐릿한 곳까지 함께 덮는다

    # ⚠️ 2026-08-13 — 여기가 선을 **배경 초록으로 덮고** 있었다. 선이 초록 위에만
    #    있으면 옳지만, 실측한 시트에서는 선이 **인물의 몸통을 가로질러** 지나갔다.
    #    그러면 초록으로 덮은 자리가 크로마 키에 걷혀 **몸에 투명한 틈**이 뚫리고,
    #    흰 테두리(white_outline)가 그 틈을 따라 둘러쳐져 **허리를 가로지르는
    #    흰 막대**가 되어 나왔다. (F70 full_stand·full_walk·full_sit 실측)
    #
    #    그래서 덮지 않고 **메운다.** 선 바로 바깥의 두 색을 가져와 이어 붙인다.
    #      · 선이 초록 위를 지나면 → 양쪽이 초록이라 초록으로 메워진다 (전과 같다)
    #      · 선이 몸 위를 지나면   → 양쪽이 옷·살색이라 몸이 이어진다 (틈이 안 생긴다)
    #    ⚠️ 다만 **전부 메우면 안 된다.** 선이 초록 위를 지나는 자리까지 메우면
    #       옆 사람과 이어져 **한 덩어리가 되어 버린다** (실측: M50B 가 덩어리
    #       23개 → 19개로 줄고 5포즈를 잃었다). 선은 칸을 나누는 담이기도 하다.
    #       그래서 **한 줄 한 줄이 아니라 점 하나하나**를 보고 정한다.
    #         · 양옆이 둘 다 초록 → 그대로 초록 (담을 남긴다)
    #         · 한쪽이라도 몸    → 양옆 색을 이어 붙인다 (몸을 잇는다)
    #
    #    ⚠️⚠️ 2026-08-13 — 여기를 '한쪽이라도 초록이면 초록으로 덮는다' 로
    #       바꿨다가 **인물 셋의 목이 잘렸다**(M70 full_back·full_sit·full_walk).
    #       까닭: 모델이 **머리 꼭대기 위로 격자선을 긋는다.** 그 선은 위가 초록,
    #       아래가 머리카락이다. '한쪽이라도 초록이면 초록' 이면 **머리 꼭대기가
    #       통째로 지워지고**, 그 자리에서 덩어리가 끊겨 목 아래만 남는다.
    #       손님: "미친놈아 이건 목이 잘렸잖아" — 맞는 지적이다.
    #
    #       ⭐ 규칙: **의심스러우면 지우지 말고 이어 붙인다.**
    #          잘못 이어 붙이면 작은 막대 토막이 남을 뿐이지만,
    #          잘못 지우면 **사람의 머리가 없어진다.** 둘의 무게가 다르다.
    #          (막대 토막은 아래 목 검사와 keep_main_blob 이 줄여 준다)
    base = out.copy()
    green = tuple(A.CHROMA)

    def _is_green(px):
        r, g, b = px[0], px[1], px[2]
        return g > 90 and g > r + 40 and g > b + 40

    d = ImageDraw.Draw(out)
    bp = base.load()
    for a, b in gc:                                   # 세로선
        x0, x1 = max(0, a - pad), min(W - 1, b + pad)
        lx, rx = max(0, x0 - 1), min(W - 1, x1 + 1)
        for y in range(H):
            lc, rc = bp[lx, y], bp[rx, y]
            if _is_green(lc) and _is_green(rc):
                d.line([(x0, y), (x1, y)], fill=green + (255,))
            else:
                mid = tuple((lc[i] + rc[i]) // 2 for i in range(3))
                d.line([(x0, y), (x1, y)], fill=mid + (255,))
    bp = out.load()                                   # 세로선 결과를 반영해 다시 읽는다
    for a, b in gr:                                   # 가로선
        y0, y1 = max(0, a - pad), min(H - 1, b + pad)
        ty, by = max(0, y0 - 1), min(H - 1, y1 + 1)
        for x in range(W):
            tc, bc = bp[x, ty], bp[x, by]
            if _is_green(tc) and _is_green(bc):
                d.line([(x, y0), (x, y1)], fill=green + (255,))
            else:
                mid = tuple((tc[i] + bc[i]) // 2 for i in range(3))
                d.line([(x, y0), (x, y1)], fill=mid + (255,))
    return out, len(gc) + len(gr)


def fast_key(img):
    """크로마 그린을 지운다. 픽셀을 하나씩 훑지 않고 채널 연산으로 한 번에 한다.

    (assets_gen.drop_chroma 는 파이썬 반복문이라 4K 시트에서 6초가 걸린다.
     여기서는 같은 판정을 밴드 연산으로 옮겨 0.1초 안에 끝낸다.)

    초록 걷어내기만으로는 머리카락 가장자리에 초록 기운이 남는다.
    남긴 픽셀에서 초록을 눌러(despill) 그 테두리를 없앤다."""
    img = img.convert("RGB")
    r, g, b = img.split()
    green = ImageChops.multiply(
        ImageChops.multiply(
            ImageChops.subtract(g, r).point(lambda v: 255 if v > 40 else 0),
            ImageChops.subtract(g, b).point(lambda v: 255 if v > 20 else 0)),
        ImageChops.multiply(
            r.point(lambda v: 255 if v < A.CHROMA[0] + A.CHROMA_TOL else 0),
            g.point(lambda v: 255 if abs(v - A.CHROMA[1]) < A.CHROMA_TOL else 0)))

    # ⭐ 마젠타(칸을 나누는 선)도 배경과 똑같이 지운다.
    #    '사람이 아닌 색' 은 초록과 마젠타 둘뿐이라는 약속이 여기서 완성된다.
    #    빨강·파랑이 둘 다 높고 초록이 그보다 40 이상 낮은 곳 — 사진에는 없는 조건이다.
    lo = ImageChops.darker(r, b)
    mag = ImageChops.multiply(
        ImageChops.multiply(r.point(lambda v: 255 if v > 100 else 0),
                            b.point(lambda v: 255 if v > 100 else 0)),
        ImageChops.subtract(lo, g).point(lambda v: 255 if v > 40 else 0))
    alpha = ImageChops.invert(ImageChops.lighter(green, mag))

    # 초록 누르기 — g 가 r·b 평균보다 튀는 만큼만 깎는다
    rb = ImageChops.add(r, b, scale=2.0)
    g2 = ImageChops.darker(g, ImageChops.add(rb, Image.new("L", g.size, 12)))
    out = Image.merge("RGBA", (r, g2, b, alpha))
    return out


# ── 덩어리 찾아 떼어내기 ──────────────────────────────────
def components(mask, min_area):
    """불투명한 점들이 이어진 덩어리마다 (왼,위,오른,아래) 를 돌려준다.

    재귀 없이 스택으로 훑는다 — 인물 하나가 수십만 픽셀이라 재귀로는 스택이 넘친다."""
    W, H = mask.size
    px = mask.load()
    seen = bytearray(W * H)
    boxes = []
    for sy in range(H):
        for sx in range(W):
            if seen[sy * W + sx] or px[sx, sy] < 128:
                continue
            stack = [(sx, sy)]
            pts = [sy * W + sx]
            seen[sy * W + sx] = 1
            x0 = x1 = sx
            y0 = y1 = sy
            area = 0
            while stack:
                x, y = stack.pop()
                area += 1
                if x < x0: x0 = x
                if x > x1: x1 = x
                if y < y0: y0 = y
                if y > y1: y1 = y
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < W and 0 <= ny < H and not seen[ny * W + nx] \
                            and px[nx, ny] >= 128:
                        seen[ny * W + nx] = 1
                        pts.append(ny * W + nx)
                        stack.append((nx, ny))
            if area >= min_area:
                boxes.append((x0, y0, x1 + 1, y1 + 1, area, pts))
    return boxes


def split_wide(mask, box, cell_w, want):
    """가로로 붙어 버린 덩어리를 세로 골짜기에서 쪼갠다.

    ⚠️ 깎아내기(erosion)만으로는 안 되는 경우가 있다. 실측: M50A 시트에서 한 줄의
       얼굴 세 개가 어깨까지 서로 닿아 있어, 25까지 깎아도 한 덩어리로 남았다.
       이럴 때는 세로 방향으로 픽셀을 세어 **가장 비어 있는 세로줄**에서 자른다.
       사람과 사람 사이는 반드시 그 줄이 가장 비어 있다."""
    x0, y0, x1, y1 = box
    w = x1 - x0
    k = max(1, min(want, round(w / max(1, cell_w))))
    if k < 2:
        return [box]
    px = mask.crop(box).load()
    colsum = [sum(1 for y in range(y1 - y0) if px[x, y] > 128) for x in range(w)]
    cuts = []
    step = w / k
    for i in range(1, k):
        centre = round(step * i)
        lo, hi = max(1, centre - round(step * 0.30)), min(w - 1, centre + round(step * 0.30))
        if hi <= lo:
            continue
        cuts.append(min(range(lo, hi), key=lambda x: colsum[x]))
    edges = [0] + sorted(cuts) + [w]
    return [(x0 + edges[i], y0, x0 + edges[i + 1], y1) for i in range(len(edges) - 1)]


SMALL_PART = 0.55      # 이만큼보다 작으면 '떨어져 나온 조각(머리·손)' 으로 본다


def _reattach(base, boxes):
    """깎다가 떨어져 나온 머리·손을 **원래 몸에 도로 붙인다.**

    base   깎기 **전** 알파(원본 연결 상태)
    boxes  깎은 뒤 찾은 덩어리들 [(x0,y0,x1,y1,area,points), ...]

    원본에서 한 덩어리인 것끼리 묶고, 그 안에서 가장 큰 것이 압도적이면
    나머지를 거기에 합친다. 엇비슷하면 서로 다른 사람이므로 그대로 둔다."""
    if len(boxes) < 2:
        return boxes
    orig = components(base, min_area=1)          # 깎기 전의 진짜 연결 상태
    if not orig:
        return boxes
    owner = {}                                   # 원본 덩어리 번호 → 깎은 덩어리 목록
    for oi, ob in enumerate(orig):
        pts = set(ob[5])
        for bi, bb in enumerate(boxes):
            if bb[5] and len(pts.intersection(bb[5])) > len(bb[5]) * 0.5:
                owner.setdefault(oi, []).append(bi)
    out, dropped = list(boxes), set()
    for _oi, group in owner.items():
        if len(group) < 2:
            continue
        group.sort(key=lambda i: boxes[i][4], reverse=True)
        head, rest = group[0], group[1:]
        big = boxes[head][4]
        joined = [i for i in rest if boxes[i][4] < big * SMALL_PART]
        if not joined:
            continue                              # 엇비슷하다 = 서로 다른 사람
        pts = list(boxes[head][5])
        for i in joined:
            pts += list(boxes[i][5])
            dropped.add(i)
        xs = [p % base.width for p in pts]
        ys = [p // base.width for p in pts]
        out[head] = (min(xs), min(ys), max(xs) + 1, max(ys) + 1, len(pts), pts)
        names = ", ".join(str(i + 1) for i in joined)
        print(f"    (깎다가 떨어진 조각 {names} 번을 몸에 도로 붙였다 — 목 잘림 방지)")
    return [b for i, b in enumerate(out) if i not in dropped]


def find_figures(sheet, cols, rows, scale=8, want=0):
    """시트에서 인물 덩어리들을 찾아 왼→오른쪽, 위→아래 순서로 돌려준다.

    `want` 개를 찾을 때까지 **깎는 정도를 키워 가며 다시 시도한다.**
    ⚠️ 고정값 하나로는 안 된다 — 같은 프롬프트로 만든 시트인데도 인물끼리
       거의 붙어 나오는 경우가 있어(실측: 판사 시트에서 2명이 1덩어리로 잡혔다)
       실선을 지울 만큼 깎아도 모자랄 때가 있다."""
    keyed = fast_key(sheet)
    base = keyed.getchannel("A").resize(
        (max(1, keyed.width // scale), max(1, keyed.height // scale)), Image.BILINEAR)
    base = base.point(lambda v: 255 if v > 96 else 0)

    best = None
    for k in (5, 9, 13, 19, 25):
        small = base.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))
        cell_area = (small.width / cols) * (small.height / rows)
        got = components(small, min_area=int(cell_area * 0.03))
        if best is None or len(got) > len(best[1]):
            best = (k, got, small)
        if want and len(got) >= want:
            best = (k, got, small)
            break
    k, boxes, small = best
    if k > 5:
        print(f"    (덩어리가 붙어 있어 {k} 만큼 깎아서 떼어냈다)")
    # 깎았다 부풀리는 '열기(opening)' 로 칸 경계의 옅은 실선을 지운다.
    # 그 선은 초록으로 판정되지 않아서, 그냥 두면 인물들을 전부 이어 버린다.
    if not boxes:
        return keyed, []

    # ⭐⭐ 2026-08-13 — **잘려 나간 머리를 도로 붙인다.** (손님: "이건 목이 잘렸잖아")
    #
    #    위에서 붙은 인물을 떼려고 최대 25(줄인 그림에서)만큼 깎는다. 그런데
    #    원래 크기로는 그게 **200픽셀**이다. 목은 그보다 얇다. 그래서 인물을
    #    떼기 전에 **목이 먼저 끊어지고**, 떨어진 머리는 따로 한 덩어리가 된다.
    #    (실측: M70 full_back·full_sit·full_walk 셋이 목 아래만 남았다)
    #
    #    더 나쁜 것은 **그게 성공처럼 보였다는 점**이다. 위 반복문은 덩어리가
    #    `want` 개가 될 때까지 깎는 정도를 키우는데, 머리가 떨어지면 덩어리 수가
    #    늘어난다 — 즉 **머리를 자를수록 목표를 채운 것처럼 보인다.**
    #
    #    바로잡는 기준은 하나다. **깎기 전 원본에서 이어져 있었으면 한 사람이다.**
    #    깎는 것은 '붙은 두 사람을 가릴' 때만 쓰고, 최종 판단은 원본이 한다.
    #    원본에서 한 덩어리인데 깎은 뒤 여럿으로 갈렸다면,
    #      · 크기가 엇비슷하면  → 서로 다른 사람이다 (그대로 둔다)
    #      · 하나가 압도적이면  → 머리·손이 떨어진 것이다 (도로 붙인다)
    # (한때 _reattach() 로 떨어진 조각을 도로 붙여 봤다. 그런데 이 시트는
    #  칸 사이가 너무 좁아 원본에서 **아래 칸 사람들까지 한 덩어리**라,
    #  붙였더니 옆 사람이 통째로 딸려 왔다. 실측으로 확인하고 뺐다.
    #  ⭐ 진짜 해결은 여기가 아니라 **시트를 제대로 그리게 하는 것**이다 —
    #     칸마다 넉넉한 여백, 인물에 닿지 않는 격자선. char_sheet_prompt 참조.)

    # 줄로 묶는다 — 세로 가운데가 비슷한 것끼리 한 줄
    boxes.sort(key=lambda b: (b[1] + b[3]) / 2)
    band = small.height / rows * 0.6
    lines, cur = [], [boxes[0]]
    for b in boxes[1:]:
        if (b[1] + b[3]) / 2 - (cur[-1][1] + cur[-1][3]) / 2 > band:
            lines.append(cur); cur = [b]
        else:
            cur.append(b)
    lines.append(cur)

    # 가로로 붙어 버린 줄을 쪼갠다 (위 split_wide 설명 참조)
    if want and sum(len(l) for l in lines) < want:
        cell_w = small.width / cols
        for li, ln in enumerate(lines):
            fixed = []
            for b in ln:
                parts = split_wide(small, b[:4], cell_w, want)
                if len(parts) == 1:
                    fixed.append(b)
                    continue
                for q in parts:
                    pts = [i for i in b[5]
                           if q[0] <= (i % small.width) < q[2]]
                    if len(pts) <= (cell_w * cell_w * 0.04):
                        continue
                    # ⚠️ 세로로 자른 자리에는 **옆 사람의 어깨 조각이 조금 남는다.**
                    #    (실측: 김성일 컷아웃 오른쪽에 흰 갈고리 모양이 붙어 나왔다.)
                    #    잘라낸 조각 안에서 다시 덩어리를 찾아 **가장 큰 것만** 남긴다.
                    #    남의 조각은 본인과 떨어져 있으므로 이걸로 깨끗이 사라진다.
                    buf = bytearray(small.width * small.height)
                    for i in pts:
                        buf[i] = 255
                    sub = Image.frombytes("L", small.size, bytes(buf))
                    # 옆 사람과 **어깨가 맞닿아** 조각이 붙어 있는 경우가 있다.
                    # 얇게 깎으면 그 다리가 끊어져 남의 조각이 따로 떨어진다.
                    # 가장 큰 것만 남기고 다시 부풀려 원래 두께로 돌린다.
                    thin = sub.filter(ImageFilter.MinFilter(7))
                    inner = components(thin, min_area=1)
                    if inner:
                        big = max(inner, key=lambda c: c[4])
                        buf2 = bytearray(small.width * small.height)
                        for i in big[5]:
                            buf2[i] = 255
                        grown = Image.frombytes("L", small.size, bytes(buf2)) \
                            .filter(ImageFilter.MaxFilter(9))
                        gp = grown.load()
                        pts = [i for i in pts
                               if gp[i % small.width, i // small.width] > 128]
                    xs = [i % small.width for i in pts]
                    ys = [i // small.width for i in pts]
                    fixed.append((min(xs), min(ys), max(xs) + 1, max(ys) + 1,
                                  len(pts), pts))
            lines[li] = fixed
        n = sum(len(l) for l in lines)
        print(f"    (붙어 있던 줄을 쪼개 {n}개로 늘렸다)")

    out = []
    pad = scale * 3                      # 깎아낸 몫 + 여유. trim_alpha 가 뒤에서 다시 조인다
    for ln in lines:
        for b in sorted(ln, key=lambda b: b[0]):
            x0, y0, x1, y1 = (v * scale for v in b[:4])
            box = (max(0, x0 - pad), max(0, y0 - pad),
                   min(keyed.width, x1 + pad), min(keyed.height, y1 + pad))
            # ⭐ 이 덩어리에 속한 점들만 남긴 본을 만든다.
            #    ⚠️ 상자만 잘라내면 **칸 경계의 옅은 실선이 같이 딸려온다.**
            #       (실측: 판사 컷아웃 왼쪽·아래에 흰 'ㄴ' 자 줄이 그대로 붙어 나왔고,
            #        그 줄 때문에 상자가 커져 얼굴이 작게 렌더링됐다.)
            #       덩어리에 속한 점만 남기면 실선도, 옆 칸 부스러기도 따라오지 않는다.
            buf = bytearray(small.width * small.height)
            for i in b[5]:
                buf[i] = 255
            m = Image.frombytes("L", small.size, bytes(buf))
            m = m.filter(ImageFilter.MaxFilter(k))          # 깎아낸 만큼 되돌린다
            out.append((box, m))
    return keyed, out


# ── 어느 덩어리가 어느 포즈인지 확인 ─────────────────────
# ⚠️ 순서대로 짝지으면 안 된다. 모델이 요청한 칸 수보다 **적게 그리는 일이 있다**
#    (실측: M50A 는 12칸을 요청했는데 11명만 그렸다). 하나가 비면 그 뒤가 전부 한 칸씩
#    밀려서, '슬픔' 자리에 '놀람' 얼굴이 저장된다. 화면에 그대로 나가는 사고다.
#    그래서 떼어낸 덩어리들을 번호 붙여 한 장으로 만들고, 값싼 모델에게
#    "몇 번이 어느 포즈인가" 를 묻는다. 인물당 한 번이면 된다.
LABEL_MODEL = os.environ.get("CHAR_LABEL_MODEL", "gemini-3.1-flash-lite")


def label_figures(keyed, figs, poses, key):
    """덩어리 번호 → 포즈 이름. 확인에 실패하면 None(순서대로 짝짓기로 되돌아간다)."""
    import io
    tiles = []
    for box, blob in figs:
        cut = keyed.crop(box)
        m = blob.crop((box[0] // 8, box[1] // 8, -(-box[2] // 8), -(-box[3] // 8)))
        cut.putalpha(ImageChops.multiply(cut.getchannel("A"),
                                         m.resize(cut.size, Image.BILINEAR)))
        cut = A.trim_alpha(cut) or cut
        bg = Image.new("RGB", cut.size, (240, 240, 240))
        bg.paste(cut, (0, 0), cut)
        tiles.append(bg)

    tw = 300
    th = max(1, max(round(t.height * tw / t.width) for t in tiles))
    cols = min(6, len(tiles))
    rows = -(-len(tiles) // cols)
    sheet = Image.new("RGB", (cols * tw, rows * (th + 26)), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(tiles):
        x, y = (i % cols) * tw, (i // cols) * (th + 26)
        t2 = t.resize((tw, min(th, max(1, round(t.height * tw / t.width)))), Image.LANCZOS)
        sheet.paste(t2, (x, y))
        d.text((x + 6, y + th + 5), f"#{i + 1}", fill=(0, 0, 0))
    buf = io.BytesIO()
    sheet.save(buf, format="JPEG", quality=80)

    opts = "\n".join(f"  {p} = {cell_text(p)}" for p in poses)
    prompt = (
        f"This sheet shows {len(tiles)} numbered cut-outs of the same person.\n"
        f"Match each number to exactly one of these pose names:\n{opts}\n\n"
        "Rules: 'face' = head fills the frame; 'bust' = head and shoulders/chest; "
        "'full' = whole body including legs.\n"
        "Each name may be used at most once. If no cut-out fits a name, leave that name out.\n"
        "\n"
        # ⭐ 2026-08-13 — 목이 잘렸는지도 **같은 호출에서 같이 묻는다.**
        #    값은 0원 더 안 든다. 손님: "미친놈아 이건 목이 잘렸잖아."
        #    자로 재는 방법(폭 프로필)도 해 봤는데 머리 있는 것 0.55 · 잘린 것 0.66
        #    으로 여유가 너무 좁아 믿을 수 없었다. 그림을 보는 눈에게 직접 묻는
        #    것이 가장 확실하고, 어차피 부르는 김이라 공짜다.
        "ALSO report broken cut-outs. A cut-out is BROKEN if the head is missing or\n"
        "sliced off — the top of the skull cut flat, or only the body below the neck.\n"
        "A back view still counts as having a head (you see hair from behind).\n"
        'Answer with JSON only: {"poses": {"1": "<pose name>", ...}, '
        '"headless": [<numbers whose head is missing>]}'
    )
    body = {"contents": [{"role": "user", "parts": [
        {"text": prompt},
        {"inlineData": {"mimeType": "image/jpeg",
                        "data": base64.b64encode(buf.getvalue()).decode()}}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    try:
        res = _post(f"{BASE}/models/{LABEL_MODEL}:generateContent?key={key}", body, timeout=180)
        txt = "".join(pt.get("text", "") for pt
                      in res["candidates"][0]["content"]["parts"])
        ans = json.loads(txt)
    except Exception as e:
        print(f"    확인 실패({e}) — 순서대로 짝짓는다")
        return None
    # 옛 모양({"1": "face_neutral"})도 그대로 읽는다 — 모델이 가끔 그렇게 답한다.
    pos = ans.get("poses") if isinstance(ans.get("poses"), dict) else ans
    bad = set()
    for n in (ans.get("headless") or []):
        try:
            bad.add(int(n) - 1)
        except (TypeError, ValueError):
            continue
    out = {}
    for k, v in pos.items():
        try:
            i = int(k) - 1
        except ValueError:
            continue
        if 0 <= i < len(figs) and v in poses and v not in out.values():
            out[i] = v
    if bad:
        # ⭐ 목이 잘린 것은 **저장하지 않는다.** 빠진 것이 낫다 —
        #    빠지면 무결성 검사가 막아 주지만, 목 잘린 채로 들어가면 그대로 방송된다.
        drop = sorted(out[i] for i in bad if i in out)
        for i in bad:
            out.pop(i, None)
        if drop:
            print(f"    ⚠️ 목이 잘려 **버린다**: {', '.join(drop)}")
    return out or None


def slice_sheet(sheet_path, code, poses, cols, rows, outdir=None, save_debug=None,
                key=""):
    sheet = Image.open(sheet_path).convert("RGBA")
    # ⭐ 자르기 **전에** 칸 선을 배경 초록으로 덮는다. 여기서 안 지우면
    #    잘린 뒤에는 옷과 붙어 버려 두 번 다시 안전하게 지울 수 없다.
    sheet, n_grid = degrid(sheet)
    if n_grid:
        print(f"    칸 선 {n_grid}줄을 배경색으로 덮었다 (자르기 전)")
    keyed, figs = find_figures(sheet, cols, rows, want=len(poses))
    print(f"    시트 {sheet.width}x{sheet.height} · 덩어리 {len(figs)}개 발견 (필요 {len(poses)}개)")

    names = None
    if key and figs:
        names = label_figures(keyed, figs, poses, key)
        if names:
            print("    확인: " + " · ".join(f"#{i + 1}={n}" for i, n in sorted(names.items())))

    if save_debug:
        from PIL import ImageDraw
        dbg = Image.new("RGB", sheet.size, (20, 20, 24))
        dbg.paste(keyed.convert("RGB"), (0, 0), keyed.getchannel("A"))
        d = ImageDraw.Draw(dbg)
        for i, ((x0, y0, x1, y1), _m) in enumerate(figs):
            d.rectangle([x0, y0, x1, y1], outline=(220, 60, 60), width=6)
            d.text((x0 + 10, y0 + 10), str(i + 1), fill=(255, 255, 255))
        dbg.save(save_debug, quality=80)

    outdir = Path(outdir or (ROOT / "assets" / "char" / code))
    outdir.mkdir(parents=True, exist_ok=True)
    made = []
    pairs = ([(names[i], figs[i]) for i in sorted(names)] if names
             else list(zip(poses, figs)))
    for pose, (box, blob) in pairs:
        cut = keyed.crop(box)
        # 덩어리 본을 원래 크기로 늘려 알파에 곱한다 → 이 인물만 남는다
        m = blob.crop((box[0] // 8, box[1] // 8, -(-box[2] // 8), -(-box[3] // 8)))
        m = m.resize(cut.size, Image.BILINEAR)
        cut.putalpha(ImageChops.multiply(cut.getchannel("A"), m))
        cut = A.trim_alpha(cut)
        if cut is None:
            continue
        if cut.height > WORK_H:                       # 위 WORK_H 설명 참조
            k = WORK_H / cut.height
            cut = cut.resize((max(1, round(cut.width * k)), WORK_H), Image.LANCZOS)
        cut = A.white_outline(cut)
        cut.save(outdir / f"{pose}.png")
        made.append(pose)
    missing = [p for p in poses if p not in made]
    print(f"    {len(made)}개 저장" + (f" · 못 만든 것: {', '.join(missing)}" if missing else ""))
    return made, missing


# ── 한 장에 한 포즈 (격자 없이) ───────────────────────────
# ⚠️ 격자 시트는 **자르다가 망가진다.** 실측: M50A 12포즈 중 7장이 못 쓰게 나왔다 —
#    상반신 4장에 칸 테두리 기둥이 붙었고, 전신 3장은 자르는 선이 목을 지나
#    **머리가 통째로 사라졌다.** 자를 것이 없으면 잘못 자를 일도 없다.
#    같은 사람인지는 **이미 잘 나온 그림을 참고로 함께 넣어** 지킨다.
def gen_one(key, code, pose, ref_path, out_path):
    """한 장에 한 포즈. ref_path 가 None 이면 참고 그림 없이 처음부터 만든다."""
    import base64
    ref = base64.b64encode(Path(ref_path).read_bytes()).decode() if ref_path else None
    look = LOOK.get(code, "a middle-aged Korean person")
    same = ("Draw THE SAME PERSON as in the reference image — identical face, hair, "
            "age and build.\n" if ref else "Draw one person.\n")
    prompt = (
        f"{same}"
        f"He is {look}.\n\n"
        f"New picture: {cell_text(pose)}\n\n"
        f"RULES:\n"
        f"  - Background is FLAT PURE CHROMA GREEN #00B140 everywhere, nothing else.\n"
        # 한 장에 한 포즈라 칸 선이 있을 이유가 없다. 그래도 모델이 액자를 두르는
        # 버릇이 있어, 굳이 그린다면 마젠타로 그리게 해 둔다 (오려낼 때 함께 지워진다).
        f"  - If you draw any frame or border at all it MUST be pure magenta #FF00FF,\n"
        f"    never black, never grey, never white.\n"
        f"  - ONE person only. Centred, complete, with clear green margin on all four sides.\n"
        f"  - The whole head including all hair must be inside the frame. Never crop the head.\n"
        f"  - No text, no numbers, no borders, no frame lines, no grid, no labels, no watermark.\n"
        f"  - No shadow on the background, no floor, no props except a plain chair when sitting.\n"
        f"  - Photorealistic, even studio lighting. Navy on top, black below.\n")
    parts = [{"text": prompt}]
    if ref:
        parts.append({"inlineData": {"mimeType": "image/png", "data": ref}})
    body = {"contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"responseModalities": ["IMAGE"],
                             "imageConfig": {"aspectRatio": "3:4" if pose.startswith("full") else "1:1",
                                             "imageSize": "2K"}}}
    res = _post(f"{BASE}/models/{MODEL}:generateContent?key={key}", body, timeout=600)
    parts = (res.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    blob = next((p["inlineData"] for p in parts if "inlineData" in p), None)
    if not blob:
        raise RuntimeError(f"이미지가 오지 않았다: {json.dumps(res)[:300]}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(blob["data"]))
    return out_path


def cut_one(raw_path, code, pose, outdir=None):
    """한 장짜리 그림에서 인물만 오려 흰 테두리를 두른다."""
    img = Image.open(raw_path).convert("RGBA")
    keyed = fast_key(img)
    small = keyed.getchannel("A").resize((img.width // 8, img.height // 8), Image.BILINEAR)
    small = small.point(lambda v: 255 if v > 96 else 0)
    small = small.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))
    comps = components(small, min_area=(small.width * small.height) // 200)
    if not comps:
        return None
    big = max(comps, key=lambda c: c[4])
    buf = bytearray(small.width * small.height)
    for i in big[5]:
        buf[i] = 255
    m = Image.frombytes("L", small.size, bytes(buf)).filter(ImageFilter.MaxFilter(5))
    keyed.putalpha(ImageChops.multiply(keyed.getchannel("A"),
                                       m.resize(keyed.size, Image.BILINEAR)))
    cut = A.trim_alpha(keyed)
    if cut is None:
        return None
    if cut.height > WORK_H:
        k = WORK_H / cut.height
        cut = cut.resize((max(1, round(cut.width * k)), WORK_H), Image.LANCZOS)
    cut = A.white_outline(cut)
    outdir = Path(outdir or (ROOT / "assets" / "char" / code))
    outdir.mkdir(parents=True, exist_ok=True)
    p = outdir / f"{pose}.png"
    cut.save(p)
    return p


def poses_from_script(path):
    """대본(본편+쇼츠)이 실제로 쓰는 인물·포즈만 모은다. 안 쓰는 것은 만들지 않는다."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    need = {}
    for a in doc["acts"]:
        for c in a["cuts"]:
            for ch in (c.get("chars") or []):
                need.setdefault(ch.get("code", ""), set()).add(ch.get("pose", ""))
    sp = Path(path).parent / (Path(path).stem + ".shorts.json")
    if sp.exists():
        sh = json.loads(sp.read_text(encoding="utf-8"))
        for s in sh.get("shorts", []):
            for c in (s.get("cuts") or []):
                ch = c.get("char")
                if ch:
                    need.setdefault(ch.get("code", ""), set()).add(ch.get("pose", ""))
    # 얼굴 → 상반신 → 전신 순서로 늘어놓는다. 비슷한 것끼리 붙어 있어야 모델이 헷갈리지 않는다
    order = {"face": 0, "bust": 1, "full": 2}
    return {k: sorted(v, key=lambda p: (order.get(p.split("_")[0], 9), p))
            for k, v in sorted(need.items()) if k}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--only", default="", help="이 인물만 (쉼표로 여러 명)")
    ap.add_argument("--plan", action="store_true", help="모델을 부르지 않고 계획만 본다")
    ap.add_argument("--grid", action="store_true",
                    help="옛 격자 시트 방식 (권하지 않음 — 칸 선이 딸려 나온다)")
    ap.add_argument("--sheets", default="build/sheets", help="시트 원본을 둘 곳")
    ap.add_argument("--slice", nargs=2, metavar=("SHEET", "CODE"),
                    help="이미 있는 시트를 자르기만 한다")
    ap.add_argument("--redo", default="",
                    help="망가진 포즈만 한 장씩 다시 만든다. 예: M50A:bust_cold,full_stand")
    ap.add_argument("--ref", default="", help="--redo 가 참고할 그림 (기본: 그 인물의 face_ 하나)")
    args = ap.parse_args()

    need = poses_from_script(args.script)
    if args.slice:
        code = args.slice[1]
        poses = need[code]
        cols, rows = grid_for(len(poses))
        slice_sheet(args.slice[0], code, poses, cols, rows,
                    save_debug=Path(args.sheets) / f"{code}_check.jpg",
                    key=os.environ.get("GEMINI_API_KEY", "").strip())
        return 0

    if args.redo:
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            print("GEMINI_API_KEY 가 없다.", file=sys.stderr)
            return 2
        code, _, plist = args.redo.partition(":")
        poses = [p.strip() for p in plist.split(",") if p.strip()]
        ref = Path(args.ref) if args.ref else None
        if not ref:
            cands = sorted((ROOT / "assets" / "char" / code).glob("face_*.png")) or \
                    sorted((ROOT / "assets" / "char" / code).glob("*.png"))
            ref = cands[0] if cands else None
        if not ref:
            print(f"{code}: 참고할 그림이 없다", file=sys.stderr)
            return 2
        print(f"{code} — 참고 그림 {ref.name} · 다시 만들 포즈 {len(poses)}개")
        raw_dir = Path(args.sheets) / "single"
        ok = 0
        for pose in poses:
            print(f"  {pose} …")
            try:
                rp = gen_one(key, code, pose, ref, raw_dir / f"{code}_{pose}.png")
                out = cut_one(rp, code, pose)
                print(f"    → {out.name if out else '오려내기 실패'}")
                ok += bool(out)
            except Exception as e:
                print(f"    실패: {e}")
        print(f"\n{ok}/{len(poses)}개 다시 만들었다")
        return 0 if ok == len(poses) else 1

    only = {c.strip() for c in args.only.split(",") if c.strip()}
    if only:
        need = {k: v for k, v in need.items() if k in only}

    n_pose = sum(len(v) for v in need.values())
    print(f"인물 {len(need)}명 · 포즈 {n_pose}개 · 모델 {MODEL} ({SIZE})")
    for code, poses in need.items():
        if args.grid:
            cols, rows = grid_for(len(poses))
            print(f"  {code:6} 포즈 {len(poses):2}개 → {cols}x{rows} 격자 "
                  f"({nearest_ratio(cols, rows)}) : {' '.join(poses)}")
        else:
            print(f"  {code:6} 포즈 {len(poses):2}개 → 한 장씩 : {' '.join(poses)}")
    if args.plan:
        calls = len(need) if args.grid else n_pose
        print(f"\n계획만 보았다. 실제 호출은 {calls}번"
              + (" (격자 — 권하지 않음)." if args.grid else " (한 장에 한 포즈)."))
        return 0

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("GEMINI_API_KEY 가 없다.", file=sys.stderr)
        return 2

    raw_dir = Path(args.sheets) / "single"

    # ⭐ **한 장에 한 포즈.** 격자 시트는 쓰지 않는다.
    #
    #    격자로 뽑으면 칸 경계선(검은 줄)이 인물과 함께 잘려 나온다. 그 선을 나중에
    #    지우려고 다섯 번 시도했고 다섯 번 다 틀렸다 — 밝기로 가르면 옷을 갉아먹고,
    #    모양으로 가르면 법복 주름과 구분이 안 됐다. 실측: 판사 상반신 왼쪽에
    #    404픽셀짜리 인쇄선이 끝까지 남았다.
    #    자를 것이 없으면 잘못 자를 일도 없다. **선이 생기는 원인을 없앤다.**
    #
    #    같은 사람인지는 첫 포즈를 참고 그림으로 함께 넣어 지킨다.
    #    (--grid 를 주면 옛 격자 방식으로 돌아가지만 권하지 않는다)
    if args.grid:
        print("⚠️ 격자 시트 방식입니다. 칸 선이 인물에 딸려 나올 수 있습니다.")
        sheets = Path(args.sheets)
        ok, bad = 0, []
        for code, poses in need.items():
            cols, rows = grid_for(len(poses))
            print(f"\n{code} — 시트 만드는 중…")
            try:
                p = gen_sheet(key, sheet_prompt(code, poses, cols, rows),
                              sheets / f"{code}.png", cols, rows)
            except Exception as e:
                print(f"    실패: {e}")
                bad.append(code)
                continue
            made, missing = slice_sheet(p, code, poses, cols, rows,
                                        save_debug=sheets / f"{code}_check.jpg", key=key)
            if missing:
                bad.append(code)
            ok += len(made)
        print(f"\n컷아웃 {ok}개 완성" + (f" · 다시 해야 할 인물: {', '.join(bad)}" if bad else ""))
        return 1 if bad else 0

    ok, bad = 0, []
    for code, poses in need.items():
        print(f"\n{code} — 포즈 {len(poses)}개를 한 장씩 만든다")
        # 이미 잘 나온 그림이 있으면 그것을 얼굴 기준으로 삼는다 (돈이 덜 든다)
        have = sorted((ROOT / "assets" / "char" / code).glob("*.png"))
        ref = have[0] if have else None
        for i, pose in enumerate(poses):
            print(f"  {pose} …" + ("" if ref else "  (첫 장 — 참고 그림 없이)"))
            try:
                rp = gen_one(key, code, pose, ref, raw_dir / f"{code}_{pose}.png")
                out = cut_one(rp, code, pose)
                if out:
                    ok += 1
                    if ref is None:
                        ref = out          # 첫 장을 이후 포즈의 얼굴 기준으로 쓴다
                    print(f"    → {out.name}")
                else:
                    bad.append(f"{code}/{pose}")
                    print("    오려내기 실패")
            except Exception as e:
                bad.append(f"{code}/{pose}")
                print(f"    실패: {e}")

    print(f"\n컷아웃 {ok}개 완성" + (f" · 다시 해야 할 것: {', '.join(bad)}" if bad else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
