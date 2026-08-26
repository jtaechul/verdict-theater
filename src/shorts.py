#!/usr/bin/env python3
"""⭐ 쇼츠 한 편을 조립한다 — 16:9 원본을 4:3 으로 잘라 가운데 띠에.

    python3 src/shorts.py S001 1 --clips 받은클립폴더/ --out build/
    python3 src/shorts.py --demo 클립.mp4 --hook "..." --sub "..."   (한 컷만 미리보기)

화면 배치 (2026-08-24 기준)

    ┌───────────────── 1080 × 1920 (쇼츠) ─────────────────┐
    │ 제목 · n화                              판결극장       │  y 0~110
    │                                                       │
    │        후 킹  문 구  — **처음부터 끝까지**              │  y 132~424
    │        (마지막 컷에서만 「다음 화 — 제목」 + 구독으로)     │
    │                                                       │
    ├───────────────────────────────────────────────────────┤  y 460
    │        영상 4:3 (1080×810) — 16:9 을 가운데서 잘라 넣음   │
    ├───────────────────────────────────────────────────────┤  y 1270
    │        「아내」 이름표                                   │  y 1300
    │        자 막  (크게, 최대 3줄)                          │  ~1620
    │                                                       │
    │        (이 아래는 유튜브 단추가 덮는 자리 — 비워 둔다)     │  y 1620~
    └───────────────────────────────────────────────────────┘

왜 이렇게 나눴나
    · 운영자가 루미나에서 **16:9 로 만들어** 올린다. 여기서 4:3 으로 가운데를
      잘라 띠에 넣는다. 좌우 12.5%씩이 날아가면서 루미나 "AI" 표시(왼쪽 위)도
      **같이 잘려 나간다** — 따로 덮거나 지울 필요가 없다.
    · 후킹은 **비어 있는 검은 칸**에 앉는다. 가릴 얼굴이 없으니 내내 띄운다.
      도중에 들어온 사람도 무슨 이야기인지 바로 안다.
    · 마지막 컷에서는 그 자리가 「다음 화 — 제목」 + 구독 알약으로 바뀐다.
      영상을 하나도 안 가리고, 2.6초가 아니라 **컷 하나 내내** 보인다.
    · 자막을 화면 맨 아래에 두면 유튜브 단추에 가린다 → 아래 300px 은 비운다.
    · 자막 위에 「아내」「남편」「그 여자」 **색 이름표**를 붙인다 — 사람이 셋인데
      누가 말하는지 몰라 이야기에서 튕겨 나가던 문제(1화 이탈률 60%)를 잡는다.

⚠️ 루미나에 넣을 때 지켜야 할 것 (프롬프트에 적어 두었다)
    · **인물과 중요한 것은 화면 가운데 75% 안에** — 좌우 끝은 잘려 나간다.
    · **와이드샷 금지** — 4:3 으로 자르면 인물이 세로 배치보다 2.3배 작아진다.
      가장 넓어도 '무릎 위'(medium-wide)까지만.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import clip as C                                            # noqa: E402
import tts                                                  # noqa: E402

FONT_B = ROOT / "assets" / "fonts" / "KoPub_Dotum_Pro_Bold.otf"
FONT_M = ROOT / "assets" / "fonts" / "KoPub_Dotum_Pro_Medium.otf"
# ⭐⭐ 2026-08-21 운영자: "위쪽 후킹 문구는 글꼴도 바뀌어야 되고 크기도 더
#    커져야 될 것 같다."
#    맞다. 실제로 만든 것을 보니 후킹이 76px 짜리 보통 굵기라 **자막보다도
#    존재감이 없었다.** 후킹은 남느냐 떠나느냐를 가르는 한 줄인데 그랬다.
#    ⚠️ 저장소에 글꼴 파일을 넣어 둔다 — 깃허브 실행기에는 한글 글꼴이
#       아예 없어서, 시스템 글꼴에 기대면 네모(두부)로 나온다.
FONT_H = ROOT / "assets" / "fonts" / "NanumGothic_ExtraBold.ttf"
# ⭐ 이름표는 **바탕체(명조)** 로 쓴다 — 굵은 고딕은 드라마가 아니라
#    앱 화면처럼 보인다 (2026-08-24 운영자: "색이름표 디자인 너무 구려").
FONT_SERIF = ROOT / "assets" / "fonts" / "KoPub_Batang_Pro_Bold.otf"

W, H = 1080, 1920                # 쇼츠 화면

# ⭐⭐⭐ 2026-08-24 대개편 — **16:9 로 받아 4:3 으로 잘라 가운데 띠에** 넣는다.
#
#    운영자: "야 그냥 예전처럼 16:9로 제작할테니 여기서 4:3으로 잘라.
#             그리고 위에 후킹문구를 계속 띄워놓은건 어때?"
#
#    이 둘은 한 몸이다. 세로(9:16) 통째 배치에서는 영상이 화면을 꽉 채우니
#    후킹 글자가 **얼굴 위에** 얹혔다 — 그래서 3초만 띄우게 막아 뒀었다.
#    띠 배치로 돌아오면 후킹이 앉는 자리가 **원래 비어 있는 검은 칸**이다.
#    가릴 얼굴이 없으니 **내내 띄워도 잃는 것이 하나도 없다.** 오히려
#    도중에 들어온 사람도 무슨 이야기인지 바로 안다(내용 파악 문제에 직접 듣는다).
#
#    화면 배치 (1080 × 1920)
#      y    0~110   제목·회차(좌) · 판결극장(우)
#      y  132~424   **후킹 — 처음부터 끝까지** (마지막 컷에서만 다음 화 안내로 바뀐다)
#      y  460~1270  영상 4:3 (1080×810) — 16:9 원본을 가운데서 잘라 넣는다
#      y 1300~1620  자막 (이름표 + 대사)
#      y 1620~1920  비움 — 유튜브 쇼츠 단추가 덮는 자리
#
#    ⚠️ 얼굴 크기: 16:9 를 4:3 으로 자르면 인물이 세로 배치보다 2.3배 작아진다.
#       그래서 루미나 프롬프트에서 **와이드샷을 쓰지 않는다**(아래 SHOT 사다리).
#    ⚠️ 잘라 낼 때 좌우 12.5%씩이 날아간다. 루미나에 **인물과 중요한 것은
#       화면 가운데 75% 안에** 두라고 적어 둔다.
#    ⚠️ 루미나 "AI" 표시는 왼쪽 위 4~6% 자리에 찍힌다 → 가운데 자르기에
#       **같이 잘려 나간다.** 혹시 남으면 CROP_SHIFT_X 를 조금 올린다.
LAYOUT = "band"                  # 16:9 → 4:3 으로 잘라 가운데 띠에
VID_TOP, VID_H = 460, 810        # 영상 자리 (1080 × 810)
CROP_SHIFT_X = 0                 # 자르는 창을 오른쪽으로 미는 픽셀 (워터마크가 남으면 올린다)
MARK_Y, MARK_SIZE = 40, 38       # 우측 상단 채널 이름
# ⭐ 2026-08-22 운영자: "몇 화인지, 드라마 제목이 뭔지가 안 나와 있어.
#    화면 최상단 좌측이나 이런 곳에 들어와야 될 거 같아."
LABEL_SIZE, LABEL_MIN = 34, 24   # 좌측 상단 제목·회차
# 후킹은 **위 검은 칸에 꽉 차게** 키운다 — HOOK_MAX 부터 줄여 가며 맞춘다
HOOK_TOP, HOOK_BOT = 120, 440   # 위 검은 칸 (영상은 460 부터 — 안 겹친다)
HOOK_MAX, HOOK_MIN, HOOK_GAP = 132, 60, 1.18
HOOK_SCRIM = 0                   # 검은 칸 위라 어두운 판이 필요 없다 (0 = 안 깐다)
# ⭐ HOOK_SEC = 0 이면 **내내 켜 둔다**(지금 배치). 0 보다 크면 그 초만 띄우고
#    부드럽게 사라진다(영상 위에 얹던 세로 배치용 — 되돌릴 때를 위해 남겨 둔다).
HOOK_SEC = 0
HOOK_FADE = 0.5                  # 사라질 때 부드럽게 (뚝 끊기면 눈에 거슬린다)
# 자막은 **아래 검은 띠 안**에 들어간다 (2026-08-23 운영자 지시)
# ⭐ 운영자: "어르신들이 보는 건데 밑에 영상 자막은 좀 더 커야 되지 않을까?"
#    맞는 말이다. 62 → 84px 로 키웠다(화면 폭의 7.8%). 폰을 팔 뻗어 보는
#    거리에서도 읽힌다. 두 줄이 들어가도록 아래 띠도 300 → 360 으로 늘렸다.
# ⚠️ 글자가 칸을 못 맞추면 fit() 이 줄여 버린다. 어르신용이므로 **62 아래로는
#    안 줄인다** — 그보다 길면 줄을 늘리는 쪽이 낫다(SUB_LINES).
SUB_TOP, SUB_BOT, SUB_SIZE = 1300, 1620, 84
SUB_MIN, SUB_LINES = 62, 3
# ⭐⭐ 2026-08-24 — 자막에 **누가 말하는지** 를 붙인다.
#    1화 이탈률 60%를 파고들다 찾은 것: 1화에 사람이 셋 나오는데 이름도
#    화자 표시도 하나도 없었다. 3컷에서 처음 보는 여자가 갑자기 말을
#    시작하니 "얘가 누구지?" 하는 순간 이야기에서 튕겨 나간다.
#    → 자막 위에 카톡 말풍선처럼 **색 이름표**를 붙인다. 어르신도 한눈에 안다.
#    ⚠️ 대본 속 이름은 영어(Wife/Husband/Other woman)다. 모르는 이름이면
#       **아무것도 안 붙인다** — 틀린 이름을 붙이는 것보다 없는 편이 낫다.
WHO_KO = {
    "wife": ("아내", (226, 196, 142)),          # 바랜 호박
    "husband": ("남편", (150, 178, 200)),       # 강청
    "other woman": ("그 여자", (206, 146, 150)),  # 마른 장미
    # ⭐ 2026-08-25 — 딸이 들어왔다. 이름표가 없으면 어르신은 "얘가 누구지"
    #    하다가 이야기에서 튕겨 나간다 (1화 이탈률 60%의 원인이 그거였다).
    "daughter": ("딸", (176, 168, 200)),        # 바랜 라일락
    "lawyer": ("변호사", (150, 190, 168)),
    "judge": ("재판장", (196, 196, 206)),
}
# 시안 1 — 이름을 **세로로 세우고** 왼쪽에 머리카락 같은 가는 선을 세운다.
#   · 채워진 상자가 없다 (상자가 싸구려로 보이던 원인)
#   · 색은 원색이 아니라 **필름톤으로 눌렀다** — 바랜 호박 · 강청 · 마른 장미
NAME_SIZE = 52                   # 이름 글자 크기 (어르신용)
NAME_RULE = 6                    # **세로 막대** 굵기 — 세로인 것은 막대뿐이다
NAME_X = 24                      # 막대와 이름 사이
NAME_GAP = 18                    # 이름 줄과 자막 사이
SIDE = 64                        # 좌우 여백

# ⭐⭐ 2026-08-25 — **때(시점) 도장.** 운영자: "씬 앞뒤로 개연성이 없다."
#    까닭 하나가 이것이었다 — 이 사건은 2012년부터 2020년까지 **8년**짜리인데
#    화면에 때가 한 번도 안 나온다. 3화와 5화 사이에 3년이 흐르는 것을
#    아무도 모른다. 그래서 화가 바뀔 때마다 "언제 얘기지?" 가 된다.
#    자막 칸 **이름표 오른쪽이 늘 비어 있어서** 거기에 앉힌다 — 후킹도
#    영상도 자막도 하나도 안 뺏는다 (실측으로 765~830px 이 남는다).
STAMP_SIZE = 40                  # 때 도장 글자 크기 (자막보다 확실히 작게)
STAMP_SEC = 3.0                  # 첫 컷 앞 몇 초만 (그 뒤엔 사라진다)
STAMP_FADE = 0.6
STAMP_COLOR = (168, 172, 186, 255)   # 흐린 회색 — 자막을 안 이긴다
GOLD = (198, 160, 74)
# ⭐ 후킹에서 별표로 감싼 토막에 넣을 색 (2026-08-21 운영자 지시).
#    채널 이름에 쓰는 GOLD 는 검은 바탕에서 132px 로 키우면 탁해 보인다.
#    한 톤 밝은 금색으로 쓴다 — 흰 글자 사이에서 확실히 튄다.
HOOK_HI = (255, 206, 84, 255)
DIM = (118, 122, 136, 255)   # 아직/이미 말한 줄
CHANNEL = "판결극장"


def syl(t):
    """실제로 소리 나는 글자만 (공백·쉼표는 시간을 안 잡아먹는다)."""
    return len(re.findall(r"[가-힣]", str(t or "")))


def voiced_spans(src, n, dur, lines=None):
    """**실제로 목소리가 난 자리** — 소리에서 직접 찾는다 (2026-08-20 운영자 지시).

    "자막은 사람마다 가라오케 식으로 하는 게 낫지 않냐?"

    말하는 시각을 우리는 모른다. 플로우가 알려주지 않는다. 그래서 **소리에서
    말이 끊기는 자리를 찾아** 사람 수만큼 토막을 낸다(만든 소리로 재보니
    0.02초 오차로 맞았다). 못 찾으면 **음절 수 비례**로 나눈다 — 긴 대사가
    긴 시간을 갖는 것이 그냥 똑같이 나누는 것보다 훨씬 가깝다.
    """
    if n == 1:
        return [(0.0, dur)]
    spans = []
    try:
        log = subprocess.run(
            ["ffmpeg", "-i", str(src), "-af", "silencedetect=n=-35dB:d=0.22",
             "-f", "null", "-"], capture_output=True, text=True).stderr
        cur = 0.0
        for m in re.finditer(r"silence_(start|end): ([\d.]+)", log):
            v = float(m.group(2))
            if m.group(1) == "start":
                if v - cur > 0.2:
                    spans.append([cur, v])
                cur = v
            else:
                cur = v
        if dur - cur > 0.2:
            spans.append([cur, dur])
    except Exception:                                        # noqa: BLE001
        spans = []

    if n <= 0:                    # 몇 토막인지 안 정했으면 **찾은 대로** 준다
        return [(a, b) for a, b in spans]
    # 토막이 사람 수보다 많으면, 사이가 가장 좁은 것부터 붙인다
    while len(spans) > n:
        gaps = [(spans[i + 1][0] - spans[i][1], i) for i in range(len(spans) - 1)]
        _, i = min(gaps)
        spans[i][1] = spans[i + 1][1]
        del spans[i + 1]

    if len(spans) != n:                                      # 못 찾았다 → 음절 수 비례
        return by_syllable(n, dur, spans_hint=None)
    return [(a, b) for a, b in spans]


def speech_spans(src, n, dur, lines=None):
    """자막을 켜 둘 시간. **말이 끊긴 사이에도 자막은 켜 둔다.**

    ⚠️ 소리를 놓을 때 이걸 쓰면 안 된다 — 첫 토막이 0초부터로 늘어나 있어서
       목소리가 **말하지도 않는 자리**에서 시작한다(실제로 그렇게 나왔다).
       소리를 놓을 때는 위의 `voiced_spans` 를 쓴다.
    """
    spans = voiced_spans(src, n, dur, lines)
    out = []
    for i, (a, b) in enumerate(spans):
        end = spans[i + 1][0] if i + 1 < len(spans) else dur
        out.append((0.0 if i == 0 else a, end))
    return out


def by_syllable(n, dur, lines=None, spans_hint=None):
    """음절 수에 비례해 시간을 나눈다 (소리에서 못 찾았을 때)."""
    w = [max(1, syl(x)) for x in (lines or [])] or [1] * n
    w = (w + [1] * n)[:n]
    tot = sum(w)
    out, t = [], 0.0
    for i, x in enumerate(w):
        end = dur if i == n - 1 else t + dur * x / tot
        out.append((t, end))
        t = end
    return out


def wrap(draw, text, font, max_w):
    """글자 폭을 실제로 재서 줄을 나눈다 (한국어는 어절 단위로 끊는다)."""
    words, lines, cur = str(text or "").split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit(draw, text, path, size, max_w, max_lines, split_slash=False, min_size=26):
    """줄 수 안에 들어갈 때까지 글자를 줄인다. (글꼴, 줄들) 을 준다.

    split_slash — 자막은 `A대사 / B대사 / A대사` 꼴로 온다. 한 덩어리로 이어
    붙이면 누가 한 말인지 안 보이고 읽기도 나쁘다. **말한 사람마다 줄을 바꾼다.**
    """
    parts = [x.strip() for x in str(text or "").split(" / ")] if split_slash \
        else [str(text or "")]
    parts = [x for x in parts if x]
    while size >= min_size:
        f = ImageFont.truetype(str(path), size)
        ls = []
        for x in parts:
            ls += wrap(draw, x, f, max_w)
        if len(ls) <= max_lines:
            return f, ls
        size -= 4
    return f, ls[:max_lines]


def runs_of(t):
    """`앞 *가운데* 뒤` → [("앞 ", False), ("가운데", True), (" 뒤", False)]."""
    out, last, t = [], 0, str(t or "")
    for m in re.finditer(r"\*([^*]+)\*", t):
        if m.start() > last:
            out.append((t[last:m.start()], False))
        out.append((m.group(1), True))
        last = m.end()
    if last < len(t):
        out.append((t[last:], False))
    return [(x, e) for x, e in out if x] or [(t, False)]


def wrap_runs(d, runs, f, max_w):
    """토막(강조/보통)을 지킨 채 줄바꿈한다. 한 줄 = [(글자, 강조인가), …].

    ⚠️ 처음에는 낱말 단위로 잘랐다가 **띄어쓰기가 사라지고** 줄이 엉뚱하게
       갈렸다(`보험금15억도 그` / `여자 앞으로였다`). 강조 토막이 낱말
       한가운데를 가르기 때문이다(`*15억*도`). 그래서 **글자 단위**로 재고
       띄어쓰기에서만 줄을 바꾼다.
    """
    ch = [(c, e) for text, e in runs for c in str(text)]
    out, i = [], 0
    while i < len(ch):
        j, last_sp = i, -1
        while j < len(ch):
            w = d.textlength("".join(c for c, _ in ch[i:j + 1]), font=f)
            if w > max_w and j > i:
                break
            if ch[j][0] == " ":
                last_sp = j
            j += 1
        if j >= len(ch):
            out.append(ch[i:])
            break
        if last_sp > i:
            out.append(ch[i:last_sp])
            i = last_sp + 1
        else:
            out.append(ch[i:j])
            i = j
    lines = []
    for seg in out:
        while seg and seg[0][0] == " ":
            seg = seg[1:]
        while seg and seg[-1][0] == " ":
            seg = seg[:-1]
        merged = []
        for c, e in seg:
            if merged and merged[-1][1] == e:
                merged[-1] = (merged[-1][0] + c, e)
            else:
                merged.append((c, e))
        if merged:
            lines.append(merged)
    return lines or [[("", False)]]


def block_runs(d, lines, font, top, bottom, fill, hi, gap):
    """토막마다 색을 달리해 가운데 맞춰 그린다."""
    lh = int(font.size * gap)
    y = top + max(0, (bottom - top - lh * len(lines)) // 2)
    for ln in lines:
        wsum = sum(d.textlength(x, font=font) for x, _ in ln)
        x = (W - wsum) / 2
        for text, emph in ln:
            d.text((x, y), text, font=font, fill=(hi if emph else fill))
            x += d.textlength(text, font=font)
        y += lh


def fit_box_runs(d, text, path, max_w, max_h, big, small, gap, max_lines):
    """강조 토막을 지킨 채 **상자에 꽉 차는 가장 큰 크기**를 찾는다."""
    runs = runs_of(text)
    f = ImageFont.truetype(str(path), small)
    got = wrap_runs(d, runs, f, max_w)
    for size in range(int(big), int(small) - 1, -2):
        f2 = ImageFont.truetype(str(path), size)
        ls = wrap_runs(d, runs, f2, max_w)
        if len(ls) > max_lines:
            continue
        if len(ls) * int(size * gap) <= max_h:
            return f2, ls
    return f, got[:max_lines]


def fit_box(draw, text, path, max_w, max_h, big, small, gap, max_lines):
    """**상자에 꽉 차는 가장 큰 크기**를 찾는다 (후킹용).

    ⚠️ fit() 은 정해진 크기에서 **줄이기만** 한다. 후킹은 반대로 키워야 한다 —
       짧은 후킹은 크게, 긴 후킹은 알아서 작게. 너비·줄 수·**상자 높이**를
       모두 보고 들어가는 가장 큰 크기를 고른다.
    """
    t = str(text or "")
    f = ImageFont.truetype(str(path), small)
    ls = wrap(draw, t, f, max_w)
    for size in range(int(big), int(small) - 1, -2):
        f2 = ImageFont.truetype(str(path), size)
        got = wrap(draw, t, f2, max_w)
        if len(got) > max_lines:
            continue
        if len(got) * int(size * gap) <= max_h:
            return f2, got
    return f, ls[:max_lines]


def fit_owned(draw, parts, path, size, max_w, max_lines):
    """사람별 대사 목록 → (글꼴, 화면에 그릴 줄들, 줄마다 누구 말인지).

    한 사람 대사가 길어 두 줄로 접히면 **그 두 줄이 같이 켜져야** 한다.
    그래서 줄마다 임자 번호를 함께 돌려준다."""
    while size >= 26:
        f = ImageFont.truetype(str(path), size)
        ls, owner = [], []
        for i, x in enumerate(parts):
            for l in wrap(draw, x, f, max_w):
                ls.append(l)
                owner.append(i)
        if len(ls) <= max_lines:
            return f, ls, owner
        size -= 4
    return f, ls[:max_lines], owner[:max_lines]


def block(d, lines, font, top, bottom, fill, gap=1.28, live=None, dim=None,
          x0=0, x1=W, align="center"):
    """정해진 칸 안에서 가운데 맞춰 그린다.

    live — 지금 말하는 사람의 줄 번호. 그 줄만 밝게, 나머지는 흐리게 그린다
           (2026-08-20 운영자: "자막은 사람마다 가라오케 식으로").
           줄 전체를 미리 보여주되 **읽을 자리를 눈이 놓치지 않게** 한다.
    """
    lh = int(font.size * gap)
    total = lh * len(lines)
    y = top + max(0, (bottom - top - total) // 2)
    for i, l in enumerate(lines):
        c = fill if (live is None or i == live) else (dim or DIM)
        x = x0 if align == "left" \
            else x0 + (x1 - x0 - d.textlength(l, font=font)) / 2
        d.text((x, y), l, font=font, fill=c)
        y += lh


def _runs(w):
    """[9, 11, 8] → [(0,9), (9,20), (20,28)] — 이어지는 몫으로 바꾼다."""
    out, t = [], 0
    for x in w:
        out.append((t, t + x))
        t += x
    return out


def sub_lines(sub):
    """자막을 말한 사람마다 한 줄로 나눈다."""
    return [x.strip() for x in str(sub or "").split(" / ") if x.strip()]


SPLIT_OVER = 16          # 이보다 길면 한 사람 말도 끊어서 띄운다 (음절)
# ⭐⭐ 2026-08-24 — 컷이 10초로 길어지면서 한 사람이 45음절을 내리 말하는
#    자리가 생겼다. 그 한 마디를 통째로 화면에 올리려다 fit() 이 **넘친 줄을
#    말없이 버려**, 자막 뒷부분이 화면에서 사라졌다(11군데).
#    → 한 토막이 이 길이를 넘지 않게 **끝까지 쪼갠다.**
CHUNK_MAX = 22           # 한 번에 띄우는 토막의 최대 음절 (두 줄에 넉넉히 들어간다)
RUNT = 8                 # 이보다 짧은 토막은 옆에 붙인다 (혼자 깜빡이면 읽기 나쁘다)


def _cut_words(s):
    """한 문장이 너무 길면 **띄어쓰기에서** 고르게 갈라 낸다 (될 때까지)."""
    s = s.strip()
    if syl(s) <= CHUNK_MAX:
        return [s]
    spots = [m.end() for m in re.finditer(r"\s+", s)]
    spots = [i for i in spots if 1 < i < len(s) - 1]
    if not spots:
        return [s]
    total = syl(s)
    bp = min(spots, key=lambda i: abs(syl(s[:i]) - (total - syl(s[:i]))))
    return _cut_words(s[:bp]) + _cut_words(s[bp:])


def halve(t):
    """긴 대사를 읽기 좋은 토막으로 끊는다.

    ⚠️ 처음엔 '가운데에서 반으로' 잘랐는데 9음절 + 19음절 처럼 치우쳤다.
       한 문장을 억지로 자르는 것보다 **문장 단위로 끊는 쪽**이 자연스럽고
       토막마다 말이 온전하다. 문장이 하나뿐이고 길면 띄어쓰기에서 가른다.

    ⚠️ 2026-08-24 — 예전엔 **두 토막까지만** 갈랐다. 45음절짜리 대사가
       22음절씩 두 토막이 되어도 화면에 다 안 들어가 뒷부분이 사라졌다.
       이제 **어느 토막도 CHUNK_MAX 를 안 넘을 때까지** 쪼갠다.
    """
    t = t.strip()
    if syl(t) <= SPLIT_OVER:
        return [t]

    # ① 문장 단위 (마침표·물음표·느낌표 뒤) → ② 그래도 길면 띄어쓰기에서
    sent = [x.strip() for x in re.split(r"(?<=[.!?…])\s+", t) if x.strip()]
    small = []
    for s in (sent or [t]):
        small += _cut_words(s)

    # ③ **너무 짧은** 토막만 옆에 붙인다 — 한두 마디가 깜빡이면 읽기 나쁘다.
    #    ⚠️ 들어가는 대로 다 붙이면 문장 단위로 끊은 뜻이 사라진다
    #       (세 문장짜리 혼잣말이 두 토막으로 뭉쳤다).
    out = []
    for s in small:
        runt = out and (syl(out[-1]) < RUNT or syl(s) < RUNT)
        if runt and syl(out[-1]) + syl(s) <= CHUNK_MAX:
            out[-1] += " " + s
        else:
            out.append(s)
    return out


def who_ko(who):
    """대본 속 화자 이름 → (화면에 쓸 한국어 이름, 색). 모르면 None."""
    k = re.sub(r"^the\s+", "", str(who or "").strip()).lower()
    return WHO_KO.get(k)


def name_column(d, label, color, top):
    """자막 왼쪽 위 — **가는 세로 막대 + 가로로 쓴 이름**. 그린 높이를 준다.

    ⭐⭐ 2026-08-24 운영자가 고른 안(①) — 세로인 것은 **막대뿐**이고 이름은
       가로로 쓴다. 채워진 상자가 없고, 글꼴은 바탕체(명조), 색은 필름톤.
    """
    f = ImageFont.truetype(str(FONT_SERIF), NAME_SIZE)
    bb = d.textbbox((0, 0), str(label or ""), font=f)
    h = (bb[3] - bb[1]) + 10
    d.rectangle([SIDE, top, SIDE + NAME_RULE, top + h], fill=tuple(color))
    d.text((SIDE + NAME_X, top - bb[1] + 5), str(label or ""), font=f,
           fill=tuple(color))
    return h


def sub_chunks(sub):
    """화면에 **한 번에 하나씩** 띄울 토막들.

    ⚠️ 2026-08-20 운영자: "가라오케 자막은 저렇게 모든 대사가 한 번에 다 뜨지
       않아. 해당 인물만 뜨게 하거나 반 문장씩 뜨게 하거나."
       맞다. 세 줄을 다 띄워 놓고 밝기만 바꾸면 화면이 글자로 꽉 차고,
       아직 안 한 말까지 미리 보여 김이 샌다.

    · 여러 사람이 주고받는 컷 → **말하는 사람 것만** 한 줄씩
    · 한 사람이 길게 말하는 컷 → **반 문장씩** 나눠서

    ⚠️ 2026-08-24 — 예전엔 **한 사람만 말하는 컷**에서만 잘랐다. 컷이
       10초로 길어지자 "A가 45음절 / B가 8음절" 같은 컷이 생겼고, A의 긴
       말이 통째로 올라가다 화면에서 뒷부분이 잘렸다(11군데).
       → 어느 사람 말이든 길면 자른다.

    돌려주는 것 — (토막들, 토막마다 **몇 번째 사람의 말인지**).
    이름표를 토막에 짝지어 붙이는 데 쓴다.
    """
    parts = sub_lines(sub)
    chunks, owners = [], []
    for i, one in enumerate(parts):
        for h in (halve(one) if syl(one) > SPLIT_OVER else [one]):
            chunks.append(h)
            owners.append(i)
    return chunks, owners


def draw_label(d, label, mark_w):
    """왼쪽 위에 「시리즈 제목 · n화」. 채널 이름과 겹치지 않는 너비만 쓴다."""
    room = W - SIDE * 2 - mark_w - 36
    size = LABEL_SIZE
    f = ImageFont.truetype(str(FONT_B), size)
    while d.textlength(label, font=f) > room and size > LABEL_MIN:
        size -= 2
        f = ImageFont.truetype(str(FONT_B), size)
    while label and d.textlength(label + "…", font=f) > room and size <= LABEL_MIN:
        label = label[:-1]
        if d.textlength(label + "…", font=f) <= room:
            label += "…"
            break
    d.text((SIDE, MARK_Y + (MARK_SIZE - size) // 2), label,
           font=f, fill=(206, 208, 216, 255))


def draw_end(d, big, small):
    """**위 칸(후킹 자리)** 에 「다음 화 — 제목」 + 구독 알약을 그린다.

    ⭐⭐ 2026-08-24 — 예전엔 영상 위에 마지막 2.6초만 겹쳤다. 띠 배치로
       돌아오면서 위 칸이 통째로 비므로 **마지막 컷 내내** 여기에 띄운다.
         · 영상을 하나도 안 가린다 (예전엔 얼굴 자리를 덮었다)
         · 2.6초 → 컷 하나 내내(6초쯤)로 늘어 **보는 사람이 두 배 이상** 된다
         · 길이는 그대로라 시청률 손해가 없다
    """
    f, ls = fit(d, big, FONT_B, END_BIG, W - SIDE * 2, 2, min_size=52)
    block(d, ls, f, HOOK_TOP, HOOK_TOP + 150, (255, 255, 255, 255))
    # ⭐ 구독 유도는 '문장'이 아니라 **'누르고 싶은 단추'** 로 보여야 손이 간다
    #    (2026-08-24 운영자: "폰트를 바꿔볼까? 밋밋해").
    #    금색 알약 안에 굵은 검은 글씨 — 시스템 이모지는 안 쓴다.
    padx, pady = END_PILL_PAD
    f2 = ImageFont.truetype(str(FONT_H), END_SMALL)
    while f2.size > 30 and d.textlength(small, font=f2) > W - SIDE * 2 - padx * 2:
        f2 = ImageFont.truetype(str(FONT_H), f2.size - 2)
    bb = d.textbbox((0, 0), small, font=f2)
    bw = (bb[2] - bb[0]) + padx * 2
    bh = (bb[3] - bb[1]) + pady * 2
    bx = (W - bw) / 2
    by = min(HOOK_TOP + 166, HOOK_BOT - bh)
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=bh / 2, fill=HOOK_HI)
    d.text((bx + bw / 2, by + bh / 2), small, font=f2,
           fill=(26, 21, 12, 255), anchor="mm")


def draw_preview(img, d, tag, big, pill):
    """**영상 칸만** 반투명 검정으로 덮고 가운데에 다음 화 예고를 그린다.

    tag  — 「다음 화 예고」 (작게, 금색)
    big  — 다음 화 **후킹** (제목보다 세다 — 이미 자극적으로 뽑아 둔 한 줄)
    pill — 구독 알약 안 글자
    """
    ov = Image.new("RGBA", (W, VID_H), (0, 0, 0, int(255 * PREV_DARK)))
    img.alpha_composite(ov, (0, VID_TOP))
    cy = VID_TOP + VID_H // 2
    f0 = ImageFont.truetype(str(FONT_H), PREV_TAG)
    w0 = d.textlength(tag, font=f0)
    d.text(((W - w0) / 2, cy - 210), tag, font=f0, fill=GOLD + (255,))
    f, ls = fit(d, big, FONT_B, PREV_BIG, W - SIDE * 2 - 40, 3, min_size=54)
    block(d, ls, f, cy - 140, cy + 120, (255, 255, 255, 255), gap=1.24)
    f2 = ImageFont.truetype(str(FONT_H), PREV_PILL)
    bb = d.textbbox((0, 0), pill, font=f2)
    bw, bh = (bb[2] - bb[0]) + 96, (bb[3] - bb[1]) + 52
    bx, by = (W - bw) / 2, cy + 160
    d.rounded_rectangle([bx, by, bx + bw, by + bh], radius=bh / 2, fill=HOOK_HI)
    d.text((bx + bw / 2, by + bh / 2), pill, font=f2, fill=(26, 21, 12, 255),
           anchor="mm")


def speech_end(src, dur):
    """그 클립에서 **말이 끝나는 시각**. 못 찾으면 끝에서 1.6초 앞."""
    try:
        got = voiced_spans(src, 0, dur)
        if got:
            return min(float(got[-1][1]), dur)
    except Exception:                                        # noqa: BLE001
        pass
    return max(0.0, dur - 1.6)


def draw_stamp(d, text):
    """자막 칸 **오른쪽 위**에 때를 작게 적는다 (예: 2013년 8월)."""
    f = ImageFont.truetype(str(FONT_M), STAMP_SIZE)
    w = d.textlength(str(text), font=f)
    d.text((W - SIDE - w, SUB_TOP + 6), str(text), font=f, fill=STAMP_COLOR)


def overlay_png(hook, chunk, out, label=None, parts="all", who=None, end=None,
                stamp="", preview=None):
    """글자만 있는 투명 그림 한 장 (영상 위에 얹는다).

    chunk — 지금 화면에 띄울 자막 **한 토막**. 나머지는 안 그린다
            (2026-08-20 운영자: "모든 대사가 한 번에 다 뜨지 않아").
    label — 왼쪽 위 「시리즈 제목 · n화」 (2026-08-22 운영자 지시).
    end   — 마지막 컷이면 (다음 화 제목, 구독 안내). 후킹 대신 이것을 띄운다.
    """
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # ⚠️⚠️ 2026-08-23 — parts 로 나눠 그린다.
    #    "frame" = 제목·채널명·후킹(또는 끝 안내) → 컷 내내 **늘** 켜 둔다
    #    "sub"   = 자막만                        → 말하는 동안만 켠다
    #    한 장에 다 그리면, 자막 조각 사이의 반 프레임 틈에서 **틀까지 통째로
    #    사라진다.** 운영자: "검은 띠가 짧게 없어졌다 나타나기를 반복해."
    want_frame = parts in ("all", "frame")
    want_hook = parts in ("all", "frame", "hook") if not HOOK_SEC \
        else parts in ("all", "hook")
    want_sub = parts in ("all", "sub")
    want_stamp = parts in ("all", "stamp")
    want_prev = parts in ("all", "preview")

    if want_prev and preview:
        draw_preview(img, d, *preview)

    if want_stamp and str(stamp or "").strip():
        draw_stamp(d, str(stamp).strip())

    if want_frame:
        # ⭐ 2026-08-24 띠 배치 — 바탕이 통째로 검은색이라 **띠를 따로 안 그린다.**
        #    영상은 y460~1270 에만 깔리고 나머지는 원래 검은 자리다.
        mark = ImageFont.truetype(str(FONT_B), MARK_SIZE)
        mark_w = d.textlength(CHANNEL, font=mark)
        d.text((W - SIDE - mark_w, MARK_Y),
               CHANNEL, font=mark, fill=GOLD + (255,))
        if str(label or "").strip():
            draw_label(d, str(label).strip(), mark_w)

    # ⭐ 마지막 컷이면 위 칸에 후킹 대신 「다음 화 — 제목」 + 구독 알약
    if want_frame and end:
        draw_end(d, end[0], end[1])
    elif want_hook and str(hook or "").strip():
        if HOOK_SCRIM:
            # 영상 위에 얹을 때만 필요하다 (띠 배치에서는 검은 칸이라 0)
            top, bot = 0, HOOK_BOT + 90
            scrim = Image.new("RGBA", (W, bot - top), (0, 0, 0, 0))
            sd = ImageDraw.Draw(scrim)
            for y in range(bot - top):
                k = y / max(1, bot - top - 1)
                sd.line([(0, y), (W, y)],
                        fill=(0, 0, 0, int(HOOK_SCRIM * (1 - k) ** 1.6)))
            img.alpha_composite(scrim, (0, top))
        # ⭐ `*…*` 로 감싼 토막만 금색으로 (2026-08-21 운영자 지시)
        f, ls = fit_box_runs(d, hook, FONT_H, W - SIDE * 2,
                             HOOK_BOT - HOOK_TOP, HOOK_MAX, HOOK_MIN,
                             HOOK_GAP, 3)
        block_runs(d, ls, f, HOOK_TOP, HOOK_BOT, (255, 255, 255, 255),
                   HOOK_HI, HOOK_GAP)

    if want_sub and str(chunk or "").strip():
        # ⭐ 이름은 자막 **왼쪽 위**에 — 세로 막대 + 가로로 쓴 이름
        top = SUB_TOP
        wk = who_ko(who)
        if wk:
            top += name_column(d, wk[0], wk[1], SUB_TOP) + NAME_GAP
        # 한 토막만 있으니 크게 쓸 수 있다 — 폰에서 읽기 훨씬 낫다
        # ⭐ 어르신용 — 글자를 작게 줄이는 대신 **줄을 늘린다**.
        f, ls = fit(d, chunk, FONT_M, SUB_SIZE, W - SIDE * 2, 2, min_size=SUB_MIN)
        if len(ls) > 2 or f.size < SUB_MIN:
            f, ls = fit(d, chunk, FONT_M, SUB_SIZE, W - SIDE * 2, SUB_LINES,
                        min_size=SUB_MIN)
        # ⭐ 자막도 이름과 **같은 왼쪽 선**에 맞춘다 (2026-08-24 운영자 지시 그림)
        block(d, ls, f, top, SUB_BOT, (245, 245, 250, 255),
              x0=SIDE, x1=W - SIDE, align="left" if wk else "center")

    img.save(out)
    return out


LOUD_TARGET = -20.0     # 컷마다 맞출 평균 소리 크기(dB)
PEAK_LIMIT = -1.0       # 이보다 커지면 소리가 깨진다


def mean_db(path, ss=0.0, t=0.0):
    """그 토막의 평균 소리 크기(dB). 못 재면 None."""
    args = ["ffmpeg", "-hide_banner"]
    if ss:
        args += ["-ss", f"{float(ss):.3f}"]
    if t:
        args += ["-t", f"{float(t):.3f}"]
    args += ["-i", str(path), "-map", "0:a", "-af", "volumedetect",
             "-f", "null", "-"]
    err = subprocess.run(args, capture_output=True, text=True).stderr
    m = re.search(r"mean_volume: ([-\d.]+)", err)
    return float(m.group(1)) if m else None


def gain_for(src):
    """이 클립을 얼마나 키우거나 줄여야 다른 컷과 소리가 같아지는가.

    ⚠️ 2026-08-20 — 1화 완성본을 재보니 컷마다 평균 소리가
         -18.6 / -26.1 / -25.0 / -19.8 / -19.4 dB
       로 **7.5dB 나 차이났다.** 2·3컷만 확 작아 볼륨이 들쭉날쭉했다.
       플로우가 컷마다 따로 만들어 주므로 저절로는 안 맞는다.

    소리를 눌러 짜는(compressor) 대신 **크기만 옮긴다** — 원래 강약은 그대로
    두고, 다만 커져서 깨질 것 같으면 그만큼만 올린다.
    """
    err = subprocess.run(["ffmpeg", "-v", "info", "-i", str(src),
                          "-af", "volumedetect", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = re.search(r"mean_volume: ([-\d.]+)", err)
    x = re.search(r"max_volume: ([-\d.]+)", err)
    if not m:
        return 0.0
    mean, peak = float(m.group(1)), float(x.group(1)) if x else 0.0
    g = LOUD_TARGET - mean
    if peak + g > PEAK_LIMIT:
        g = PEAK_LIMIT - peak
    return round(g, 2)


# ⭐⭐ 2026-08-21 — **죽은 시간을 잘라 낸다.**
#    운영자가 같은 프롬프트를 제미나이에 넣어 받은 영상을 재 봤다 (10.005초):
#      0.00~1.13 무음 / 1.13~2.50 / 2.83~4.29 / 4.66~6.20 / **6.20~10.00 무음**
#    말한 시간은 4.37초 — 플로우 6초짜리(4.43초)와 **거의 같다.**
#    10초라서 천천히 말한 것이 아니라 **뒤에 3.8초를 그냥 비워 둔 것**이다.
#    (그러니 컷을 10초로 늘리는 것은 소용이 없다. 자연스러움의 차이는
#     길이가 아니라 목소리 모델 쪽에서 온다.)
#
#    → 앞뒤 죽은 시간을 잘라 내면 **10초짜리도 그대로 쓸 수 있고**,
#      플로우 6초짜리도 앞 1초가 사라져 훨씬 촘촘해진다.
HEAD_PAD = 0.25        # 첫 말 앞에 남겨 둘 숨
TAIL_PAD = 0.45        # 끝말 뒤에 남겨 둘 여운


def trim_dead(src, out, turns=0):
    """앞뒤로 말이 없는 시간을 잘라 낸다. 자를 것이 없으면 원본을 그대로.

    turns — 대본에 적힌 대사가 몇 마디인지. 주면 **그보다 많은 말은 지어낸
    것으로 보고 뒤를 잘라 낸다** (2026-08-23 운영자: 5컷 끝에 대본에 없는
    나레이션이 하나 더 나왔다 — 지어낸 말이라 자막이 없다)."""
    src, out = Path(src), Path(out)
    # ⚠️ 자르기는 **있으면 좋은 것**이지 없으면 안 되는 것이 아니다.
    #    클립을 못 읽는다고 여기서 죽으면 30초짜리 하나가 통째로 날아간다.
    #    못 하면 조용히 원본을 그대로 쓴다.
    try:
        dur = C.probe(src)[2]
        spans = voiced_spans(src, 0, dur)  # 있는 대로 다 찾는다
    except Exception:                                        # noqa: BLE001
        return src
    if not spans:
        return src
    if turns and len(spans) > turns:
        # ⚠️ 한 문장 안의 짧은 숨(0.45초 미만)은 한 마디로 붙여 센다 —
        #    안 붙이면 진짜 대사가 두 토막으로 세어져 뒤가 잘려 나간다.
        glued = [list(spans[0])]
        for a2, b2 in spans[1:]:
            if a2 - glued[-1][1] < 0.45:
                glued[-1][1] = b2
            else:
                glued.append([a2, b2])
        if len(glued) > turns and dur - glued[turns - 1][1] > 0.8:
            cut = len(spans) - len(glued[:turns])
            print(f"    ✂️ 대본에 없는 말 {len(glued) - turns}마디를 잘라 낸다 "
                  f"(대본 {turns}마디 · 소리에서 {len(glued)}마디)")
            spans = [s2 for s2 in spans if s2[1] <= glued[turns - 1][1] + 0.01]
    a = max(0.0, spans[0][0] - HEAD_PAD)
    b = min(dur, spans[-1][1] + TAIL_PAD)
    if b - a < 1.0 or (a < 0.15 and dur - b < 0.15):
        return src                          # 자를 것이 없다
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-i", str(src),
         "-t", f"{b - a:.3f}", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
         str(out)], capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        return src
    print(f"    ✂️ 죽은 시간을 잘랐다 — {dur:.2f}초 → {b - a:.2f}초 "
          f"(앞 {a:.2f}초 · 뒤 {dur - b:.2f}초)")
    return out


# ⭐⭐ 2026-08-21 — 목소리를 **한국어 전용**으로 갈아 끼운다.
#    운영자: "외국인 노동자가 어설픈 한국말 하는 것 같아 ㅠㅠ"
#    영상 만드는 쪽의 한국어 발음은 프롬프트로 못 고친다(다 해 봤다).
#    다행히 실제 영상을 재 보니 **말하는 자리가 정확히 잡힌다** —
#      0.98~2.55 / 2.79~4.20 / 4.57~6.02
#    그 자리에 같은 대사를 한국어 목소리로 만들어 그대로 끼워 넣는다.
#    입은 이미 같은 한국어 대사로 움직이므로 입모양도 거의 맞는다.
#    ⚠️ 열쇠가 없으면 **아무것도 안 하고 원래 소리를 그대로 쓴다.**
#       (영상이 안 나오는 것보다 낫다)
# ⚠️ dia_turns 는 **대본 쪽(series.py)** 에 있다. 여기 두었더니 소리만
#    만드는 일에서 shorts 를 들여와야 했고, 그때 PIL 이 없다고 죽었다.
from series import dia_turns                                # noqa: E402,F401

# ⭐ 2026-08-23 — 소리를 갈아 끼우지 않고 **구글이 만든 소리를 그대로** 두는 길.
#    운영자에게 두 판(구글 소리 / 우리 목소리)을 같은 영상으로 들려드리기 위한 것이다.
#    영상은 한 번만 만들면 되므로 두 판을 만들어도 영상값은 0원이 더 든다.
def keep_audio():
    """원본 소리를 그대로 둘 것인가. **기본이 '그대로 둔다' 이다.**

    ⭐ 2026-08-23 운영자 지시 — 루미나가 만든 나레이션을 그대로 쓴다.
       "원본영상 나래이션을 쓸꺼라 typecast나 제미나이 api tts도 없애야 해."
       예전 기본값은 '갈아 끼운다' 였다. 플로우 영상의 한국어 발음이 어눌해서
       우리 목소리로 덮던 시절의 값인데, 루미나는 발음이 멀쩡하다.
       굳이 갈아 끼우려면 KEEP_AUDIO=0 을 준다."""
    v = os.environ.get("KEEP_AUDIO", "").strip().lower()
    return v not in ("0", "no", "false")


def dub(src, turns, voices, out, tmp, personas=None):
    if keep_audio():
        print("  🔊 구글이 만든 소리를 그대로 둔다 (KEEP_AUDIO)")
        return False
    """클립의 소리를 한국어 목소리로 갈아 끼운다. 못 하면 False.

    personas — {말하는이: "50대 중년 남성…"} (tts.pick_personas).
    ⭐ 2026-08-22 운영자: "주인공들 나이 목소리가 맞지 않아."
      목소리 지시에 배역 나이를 실어 보낸다.
    """
    if not turns or not tts.key():
        return False
    try:
        dur = C.probe(src)[2]
    except Exception:                                        # noqa: BLE001
        return False                       # 못 읽으면 원래 소리를 그대로 쓴다
    # ⚠️ 자막용(speech_spans)이 아니라 **실제로 말한 자리**를 써야 한다.
    #    자막용은 첫 토막이 0초부터로 늘어나 있어서, 그걸 쓰면 목소리가
    #    말하지도 않는 앞머리에서 시작한다 (실제로 그렇게 나왔다).
    spans = voiced_spans(src, len(turns), dur, [t for _, t in turns])
    if len(spans) != len(turns):
        spans = by_syllable(len(turns), dur, [t for _, t in turns])
    tmp.mkdir(parents=True, exist_ok=True)
    made = []
    for i, ((who, text), (a, b)) in enumerate(zip(turns, spans)):
        v = (voices.get(who) or voices.get(who.lower())
             or tts.best_voices("FEMALE")[0])
        pe = (personas or {}).get(who) or (personas or {}).get(who.lower())
        # ⭐ 2026-08-21 — **입이 움직인 시간에 억지로 우겨넣지 않는다.**
        #    영상 만드는 쪽은 32음절을 4.4초에 쏟아냈다(초당 7.3음절).
        #    거기에 딱 맞추면 우리 한국어 목소리도 똑같이 급해져서, 애써
        #    바꾼 보람이 없다. 다음 사람이 말하기 직전까지가 **쓸 수 있는 시간**
        #    이므로, 말이 끊긴 사이까지 빌려 쓴다.
        room = (spans[i + 1][0] if i + 1 < len(spans) else dur) - a - 0.05
        try:
            p, d = tts.say_to_fit(text, v, max(0.6, b - a),
                                  tmp / f"{src.stem}_v{i}.wav",
                                  tts.tone_of(text), room=max(0.6, room),
                                  who=pe)
        except Exception as e:                               # noqa: BLE001
            print(f"    ⚠️ 목소리 만들기 실패 ({e}) — 원래 소리를 쓴다")
            return False
        made.append((a, p, d))
        print(f"    🎙 {who}" + (f"({pe.split(',')[0]})" if pe else "")
              + f": {text[:18]}…  {a:.2f}초부터 {d:.2f}초")

    # ⭐⭐ 2026-08-22 — **원본이 말하던 크기에 맞춘다.**
    #    맞추지 않으면 우리 목소리만 동떨어진 크기로 얹혀서, 장면에 안 앉고
    #    나중에 덧붙인 소리처럼 들린다 (더빙처럼 들리는 까닭 중 하나다).
    #    이 클립은 원본이 말할 때 -13~-16dB 였다.
    tgt = None
    _d = [mean_db(src, a, b - a) for a, b in spans]
    _d = [x for x in _d if x is not None and x > -60]
    if _d:
        tgt = sum(_d) / len(_d)

    # 원래 소리는 **완전히 지우고**, 만든 목소리를 제자리에 얹는다
    args = ["ffmpeg", "-v", "error", "-y", "-i", str(src)]
    for _, p, _ in made:
        args += ["-i", str(p)]
    fil = [f"[0:a]volume=0,apad[bed]"]
    mix = "[bed]"
    for i, (a, _p, _) in enumerate(made):
        # ⚠️ 크게 올리다 깨지면 더 나쁘다. 올리고 내리는 폭을 묶어 둔다.
        g = 0.0
        if tgt is not None:
            own = mean_db(_p)
            if own is not None and own > -60:
                g = max(-10.0, min(10.0, tgt - own))
        vol = f"volume={g:.1f}dB," if abs(g) > 0.3 else ""
        fil.append(f"[{i + 1}:a]{vol}aresample=48000,"
                   f"aformat=sample_fmts=fltp:channel_layouts=stereo,"
                   f"adelay={int(a * 1000)}|{int(a * 1000)}[d{i}]")
        mix += f"[d{i}]"
    fil.append(f"{mix}amix=inputs={len(made) + 1}:normalize=0:"
               f"duration=first[mixed]")
    # ⚠️⚠️ 2026-08-23 운영자: "말이 동영상이 끊기니까 말도 중간에 끊겨버려."
    #    여기서 `-t dur` 로 **클립 길이에서 뚝 잘랐다.** 대사가 자연스러운
    #    속도로 클립보다 길어지는 것은 허용해 놓고(say_to_fit 의 '넘친다'),
    #    잘라 버리면 마지막 말이 중간에서 끊긴다.
    #    → 말이 끝날 때까지 **끝 화면을 붙잡아 둔다** (마지막 프레임 정지).
    #      입은 잠깐 멈추지만 말이 잘리는 것보다 훨씬 낫다.
    need = max(a + d for a, _p, d in made) + 0.12
    if need > dur + 0.05:
        hold = need - dur
        print(f"    ⏸ 말이 길어 끝 화면을 {hold:.1f}초 잡아 둔다 — 말을 자르지 않는다")
        fil.append(f"[0:v]tpad=stop_mode=clone:stop_duration={hold:.3f}[vx]")
        args += ["-filter_complex", ";".join(fil),
                 "-map", "[vx]", "-map", "[mixed]",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                 "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "160k",
                 "-t", f"{need:.3f}", str(out)]
    else:
        args += ["-filter_complex", ";".join(fil),
                 "-map", "0:v", "-map", "[mixed]",
                 "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
                 "-t", f"{dur:.3f}", str(out)]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"    ⚠️ 소리 갈아 끼우기 실패 — 원래 소리를 쓴다\n{r.stderr[:200]}")
        return False
    return True


# ⭐⭐ 2026-08-23 — 마지막에 「다음 화에 계속」 + 구독 안내 (운영자 아이디어).
#
#    ⚠️ 다만 **뒤에 따로 붙이지 않는다.** 쇼츠는 끝나면 곧바로 처음으로 되감긴다.
#       뒤에 2~3초짜리 정지 화면을 덧붙이면 그 구간은 거의 아무도 안 보고
#       빠져나가, '평균 시청률' 이 그만큼 깎인다(유튜브가 이 값으로 노출을
#       정한다). 그래서 **마지막 컷의 끝 2.6초 위에 겹쳐서** 띄운다.
#       길이가 안 늘어나므로 시청률 손해가 없다.
#
#    ⚠️ 그리고 「다음 화에 계속」 만 쓰지 않는다. **다음 화 제목을 같이 보여 주는
#       쪽이 훨씬 세다** — '무슨 일이 벌어지는지' 가 궁금해야 다음 편을 찾는다.
#       구독 안내는 그 아래 작은 줄로 한 번만 (두 화면으로 나누면 둘 다 흐려진다).
# ⭐⭐⭐ 2026-08-25 운영자: "만든 영상이 끝나면 다음화 예고 문구를 화면
#    중간에 띄워주고, 그 화면이 반투명 검정색으로 바뀌고… 드라마 보면
#    다음 화 안내하잖아."
#    맞는 방향인데 **화면 전체**를 덮으면 위 칸의 후킹까지 어두워진다
#    (운영자는 "후킹은 끝까지 유지" 라고도 하셨다 — 둘이 부딪힌다).
#    → 위아래 띠는 **원래 검은색**이므로 **영상 칸만** 어둡게 하면
#      화면 전체가 고르게 어두워 보이면서 후킹은 위에서 그대로 밝다.
#    ⚠️ 길이는 1초도 안 늘린다. 쇼츠는 뒤에 붙이면 평균 시청률이 깎인다
#       (30초 미만은 65%가 확산 기준). 마지막 컷 **위에 겹친다.**
PREV_DARK = 0.82                 # 영상 칸을 얼마나 어둡게 (0~1)
PREV_SEC = 2.2                   # 마지막에 띄우는 시간 (최대)
PREV_FADE = 0.5                  # 서서히 어두워지는 시간
PREV_LEAD = 0.15                 # 마지막 말이 끝나고 이만큼 뒤에 시작한다
PREV_TAG, PREV_BIG, PREV_PILL = 44, 82, 44

END_SEC = 2.6                    # (옛 방식) 끝 안내를 띄우는 시간
END_BIG, END_SMALL = 76, 46      # 큰 줄 · 알약 안 글자 크기
END_PILL_PAD = (48, 26)          # 알약 좌우 · 위아래 여백
END_TOP = HOOK_TOP               # 끝 안내도 **위 칸**(후킹 자리)에 그린다


def end_card(doc, no):
    """(옛 방식) 위 칸에 띄우던 두 줄. 지금은 preview_card 를 쓴다."""
    big, _, small = preview_card(doc, no)
    return big, small


def hook_plain(t):
    """별표를 떼어 낸 맨글자. (`*센 말*` 은 색 넣을 자리 표시라 화면엔 안 나온다)

    ⚠️ 같은 함수가 series.py 에도 있다. 여기서 series 를 들여오면 조립할 때
       대본 모듈이 통째로 딸려 온다 — 한 줄짜리라 그냥 둔다.
    """
    return re.sub(r"\*([^*]+)\*", r"\1", str(t or "")).strip()


def preview_card(doc, no):
    """마지막에 **화면 가운데**에 띄울 세 줄. (작은 머리말, 큰 줄, 알약)

    ⭐⭐ 큰 줄은 다음 화의 **제목이 아니라 후킹**이다.
       제목("이혼 소송 기각")은 목차처럼 밋밋하고, 후킹("바람피운 놈이 걸었다가
       기각당했다")은 이미 손가락을 멈추게 하려고 뽑아 둔 한 줄이다.
    """
    eps = doc.get("episodes") or []
    nxt = next((e for e in eps if int(e.get("no", 0)) == int(no) + 1), None)
    if nxt:
        big = hook_plain(nxt.get("hook")) or str(nxt.get("title") or "").strip()
        return "다음 화 예고", big or "다음 화에 계속", "구독하고 내일 이어 보기"
    return "완 결", "여기까지 보셨다면 1화부터 정주행해 보세요", "구독하고 정주행"


def audio_sec(src):
    """그 파일의 **소리** 길이(초). 소리가 없으면 0.

    ⚠️ 2026-08-23 — 영상 길이만 보고 -shortest 로 잘랐더니 **나레이션 끝이
       날아갔다.** 루미나 클립은 소리가 영상보다 조금 긴 것이 있다.
       운영자: "영상 및 나레이션이 뒷부분이 남아있는 상태에서 끊겼어."
    """
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=duration", "-of", "csv=p=0", str(src)],
            capture_output=True, text=True).stdout.strip()
        return float(out) if out and out != "N/A" else 0.0
    except Exception:                                        # noqa: BLE001
        return 0.0


def crop_43(vw, vh):
    """받은 영상을 **4:3 으로 가운데서 잘라 낼 창**. (폭, 높이, 왼쪽x, 위y)

    ⭐⭐ 2026-08-24 운영자: "그냥 예전처럼 16:9로 제작할테니 여기서 4:3으로 잘라."
       · 16:9 (가로가 김) → **좌우를 12.5%씩** 버린다. 루미나 "AI" 표시가
         왼쪽 위 4~6% 자리라 여기서 같이 잘려 나간다.
       · 4:3 보다 세로가 긴 것(예전 세로 클립)이 들어와도 죽지 않게,
         그때는 **위아래를 자른다 — 얼굴이 있는 위쪽을 살린다.**
    """
    if vw * 3 >= vh * 4:                 # 가로가 4:3 보다 넓다 → 좌우를 자른다
        cw = min(vw, int(round(vh * 4 / 3)))
        cw -= cw % 2
        x = (vw - cw) // 2 + CROP_SHIFT_X
        x = max(0, min(x, vw - cw))
        return cw, vh - vh % 2, x, 0
    ch = int(round(vw * 3 / 4))          # 세로가 더 길다 → 위아래를 자른다
    ch -= ch % 2
    y = max(0, (vh - ch) // 3)           # 가운데보다 조금 위 — 얼굴을 지킨다
    return vw - vw % 2, ch, 0, y


def compose(src, hook, sub, out, tmp, label=None, end=None,
            hook_sec=HOOK_SEC, whos=None, stamp="", preview=None):
    """받은 클립 한 개 → 쇼츠 한 컷 (자르지 않고 폭에 맞춰 깔고 글자 얹기)."""
    src, out, tmp = Path(src), Path(out), Path(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    vw, vh, vsec = C.probe(src)
    asec = audio_sec(src)
    # ⭐ 둘 중 **긴 쪽**에 맞춘다. 짧은 쪽에 맞추면 남은 것이 잘려 나간다.
    sec = max(vsec, asec)
    hold = max(0.0, asec - vsec)         # 소리가 더 길면 마지막 화면을 붙잡는다
    cw, ch, cx, cy = crop_43(vw, vh)     # 16:9 → 4:3 가운데 잘라 내기

    # ⭐ 자막은 **한 토막씩** 뜬다 (말하는 사람 것만 / 긴 대사는 반 문장씩).
    #    말하는 시각은 소리에서 찾는다.
    chunks, owners = sub_chunks(sub)
    parts = sub_lines(sub)
    people = len(parts)

    def share(base, mine):
        """한 사람 몫의 시간을 그 사람 토막들에 **음절 수대로** 나눈다."""
        tot = max(1, sum(syl(x) for x in mine))
        a0, b0 = base
        return [(a0 + (b0 - a0) * a / tot, a0 + (b0 - a0) * b / tot)
                for a, b in _runs([syl(x) for x in mine])]

    if people <= 1:
        # 한 사람이 길게 말하는 컷 — 그 사람이 말하는 동안을 음절 수로 나눈다
        spans = share(speech_spans(src, 1, sec)[0], chunks)
    else:
        # 사람마다 말하는 동안을 먼저 찾고, 그 안에서 토막끼리 다시 나눈다
        pspans = speech_spans(src, people, sec)
        if len(pspans) != people:
            pspans = by_syllable(people, sec, parts)
        spans = []
        for i in range(people):
            spans += share(pspans[i], [c for c, w in zip(chunks, owners) if w == i])
        if len(spans) != len(chunks):
            spans = by_syllable(len(chunks), sec, chunks)
    spans[-1] = (spans[-1][0], sec)          # 마지막은 끝까지 남긴다
    # ⭐ 틀(제목·채널명·후킹 또는 끝 안내)은 **한 장으로 늘 켜 둔다.**
    #    조각조각 얹으면 자막 조각 사이 반 프레임 틈에서 통째로 깜빡인다.
    #    ⭐⭐ 2026-08-24 띠 배치 — 후킹은 **검은 칸**에 앉으므로 가릴 얼굴이
    #       없다. 그래서 다시 틀에 넣어 **내내** 켜 둔다(HOOK_SEC = 0).
    #       마지막 컷에서는 그 자리에 「다음 화 — 제목」 + 구독 알약이 대신 뜬다.
    imgs = [overlay_png(hook if not HOOK_SEC else "", "",
                        tmp / f"{src.stem}_frame.png", label,
                        parts="frame", end=end)]
    hook_i = None
    if HOOK_SEC and str(hook or "").strip() and float(hook_sec) > 0:
        hook_i = len(imgs)
        imgs.append(overlay_png(hook, "", tmp / f"{src.stem}_hook.png",
                                None, parts="hook"))
    # ⭐ 다음 화 예고 — 마지막 말이 끝난 뒤 **영상 칸만** 어두워진다.
    prev_i = None
    if preview:
        prev_i = len(imgs)
        imgs.append(overlay_png("", "", tmp / f"{src.stem}_prev.png", None,
                                parts="preview", preview=preview))
    stamp_i = None
    if str(stamp or "").strip():
        stamp_i = len(imgs)
        imgs.append(overlay_png("", "", tmp / f"{src.stem}_stamp.png", None,
                                parts="stamp", stamp=stamp))
    sub_i = len(imgs)
    # ⭐ 토막마다 **누가 한 말인지** 짝지어 준다 (2026-08-24).
    #    한 사람 대사를 반으로 쪼갠 컷(halved)은 두 토막 다 같은 사람이다.
    ws = list(whos or [])
    if len(ws) == people:
        ws = [ws[w] for w in owners]       # 쪼갠 토막도 **원래 말한 사람**을 따라간다
    if len(ws) != len(chunks):
        ws = [None] * len(chunks)          # 수가 안 맞으면 아무것도 안 붙인다
    pngs = [overlay_png("", c, tmp / f"{src.stem}_txt{i}.png", None,
                        parts="sub", who=(ws[i] if i < len(ws) else None))
            for i, c in enumerate(chunks or [""])]
    imgs += pngs

    # ⭐⭐ 2026-08-24 — 16:9 로 받아 **4:3 으로 가운데를 잘라** 띠에 넣는다.
    #    좌우 12.5%씩이 날아가면서 루미나 "AI" 표시(왼쪽 위)도 같이 잘린다.
    # 소리가 영상보다 길면 마지막 화면을 그만큼 붙잡아 둔다(뚝 끊기지 않게)
    tpad = f",tpad=stop_mode=clone:stop_duration={hold + 0.05:.3f}" if hold > 0.02 else ""
    vf = [f"[1:v]crop={cw}:{ch}:{cx}:{cy},scale={W}:{VID_H}{tpad}[v]",
          f"[0:v][v]overlay=0:{VID_TOP}[b]",
          # 틀은 enable 없이 통째로 얹는다 → 한 프레임도 안 사라진다
          f"[b][2:v]overlay=0:0[s0]"]
    # ⭐ 후킹 — 앞 hook_sec 초만. 끝에서 부드럽게 사라진다(뚝 끊기면 거슬린다).
    cur = "[s0]"
    if hook_i is not None:
        hs = min(float(hook_sec), sec)
        fs = max(0.0, hs - HOOK_FADE)
        vf.append(f"[{2 + hook_i}:v]format=rgba,"
                  f"fade=t=out:st={fs:.3f}:d={min(HOOK_FADE, hs):.3f}:alpha=1[hk]")
        vf.append(f"{cur}[hk]overlay=0:0:enable='between(t,0,{hs:.3f})'[h0]")
        cur = "[h0]"
    # ⚠️ 2026-08-22 — between(t,a,b) 는 양 끝을 **포함**한다. 앞 토막이 2.0에
    #    끝나고 뒤 토막이 2.0에 시작하면, 딱 그 순간의 한 프레임에 **둘 다**
    #    켜져 자막이 겹쳐 보인다 (실제 프레임에서 발견). 앞 토막을 반 프레임
    #    일찍 끈다.
    # ⭐ 때 도장 — 첫 컷 앞 몇 초만. 끝에서 부드럽게 사라진다.
    if stamp_i is not None:
        ss = min(STAMP_SEC, sec)
        fs = max(0.0, ss - STAMP_FADE)
        vf.append(f"[{2 + stamp_i}:v]format=rgba,"
                  f"fade=t=out:st={fs:.3f}:d={min(STAMP_FADE, ss):.3f}:alpha=1[st]")
        vf.append(f"{cur}[st]overlay=0:0:enable='between(t,0,{ss:.3f})'[sp]")
        cur = "[sp]"

    # ⭐ 예고는 **말이 끝난 뒤**에 뜬다 (대사를 안 가린다). 길이는 그대로다.
    if prev_i is not None:
        ps = min(max(speech_end(src, sec) + PREV_LEAD, sec - PREV_SEC),
                 max(0.0, sec - 1.2))
        vf.append(f"[{2 + prev_i}:v]format=rgba,"
                  f"fade=t=in:st={ps:.3f}:d={min(PREV_FADE, max(0.1, sec - ps)):.3f}"
                  f":alpha=1[pv]")
        vf.append(f"{cur}[pv]overlay=0:0:enable='gte(t,{ps:.3f})'[pw]")
        cur = "[pw]"

    EN_EPS = 0.021                       # 24fps 반 프레임
    for i in range(len(pngs)):
        a, b = spans[i] if i < len(spans) else (0.0, sec)
        last = (i == len(pngs) - 1)
        if not last:
            b = max(a, b - EN_EPS)
        tag = "[o]" if last else f"[t{i}]"
        en = "" if len(pngs) == 1 else f":enable='between(t,{a:.3f},{b:.3f})'"
        vf.append(f"{cur}[{2 + sub_i + i}:v]overlay=0:0{en}{tag}")
        cur = tag
    # ⭐ 끝 안내는 **틀 그림 안**(위 칸)에 이미 들어가 있다 — 컷 내내 켜져 있고
    #    영상을 하나도 안 가린다. 길이도 그대로다.
    last_tag = "[o]"

    cmd = ["ffmpeg", "-v", "error", "-y",
           # 바탕은 넉넉하게 — 바탕이 짧으면 그것이 끝을 결정해 잘린다
           "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r=24:d={sec + 1:.3f}",
           "-i", str(src)]
    for k, q in enumerate(imgs):
        # ⚠️ 후킹만 **영상처럼** 넣는다(-loop). 그림 한 장은 프레임이 하나뿐이라
        #    fade(서서히 사라지기)가 안 걸린다 — 늘려 줘야 걸린다.
        if (hook_i is not None and k == hook_i) or k in (stamp_i, prev_i):
            cmd += ["-loop", "1", "-framerate", "24", "-t", f"{sec + 1:.3f}"]
        cmd += ["-i", str(q)]
    # 소리: 컷마다 크기를 맞추고, 앞뒤 0.05초를 부드럽게 (이어 붙일 때 '툭' 소리 방지)
    g = gain_for(src)
    af = (f"volume={g}dB,afade=t=in:st=0:d=0.05,"
          f"afade=t=out:st={max(0, sec - 0.05):.3f}:d=0.05")
    cmd += ["-filter_complex", ";".join(vf), "-map", last_tag, "-map", "1:a?",
            "-af", af,
            "-c:v", "libx264", "-preset", "medium", "-crf", "19",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            # ⚠️ -shortest 는 **가장 짧은 입력**에서 끊는다. 바탕·영상·소리 중
            #    하나라도 짧으면 거기서 잘린다(나레이션이 날아간 원인).
            #    길이를 우리가 정해 준다 — 영상·소리 중 긴 쪽.
            "-t", f"{sec:.3f}", "-movflags", "+faststart", str(out)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패:\n{p.stderr[:600]}")
    return out


def hook_of(ep, doc):
    """이 화의 후킹 문구. 없으면 화 제목, 그것도 없으면 시리즈 제목."""
    return (str(ep.get("hook") or "").strip()
            or str(ep.get("title") or "").strip()
            or str(doc.get("title") or "").strip())


STOP = {"the", "a", "an", "at", "in", "on", "of", "to", "her", "his", "and",
        "with", "by", "from", "into", "over", "as", "is", "it", "for"}


def words(t):
    """영어 낱말만 뽑고 꼬리를 떼어 맞춰 본다 (glaring↔glares, shakes↔shake)."""
    out = set()
    for w in re.findall(r"[A-Za-z]+", str(t or "").lower()):
        if len(w) < 3 or w in STOP:
            continue
        for suf in ("ingly", "ing", "edly", "ed", "ly", "es", "s"):
            if len(w) > len(suf) + 2 and w.endswith(suf):
                w = w[: -len(suf)]
                break
        out.add(w)
    return out


def pick_clips(d, n, cuts=None):
    """받은 파일들을 컷 번호에 맞춘다.

    플로우에서 내려받은 이름은 제각각이라 한 가지 규칙만 믿으면 안 된다.
      ① 이름 안에 c001 · c1 같은 컷 번호가 있으면 그것으로 (가장 확실)
      ② 없으면 **파일 이름과 컷 내용을 맞춰** 짝짓는다.
      ③ 그래도 못 정한 것은 남은 것끼리 순서대로

    ⚠️ 2026-08-20 — 처음엔 ②가 없이 '이름 순서대로' 였는데, 실제로 올라온
       플로우 파일 이름이 이랬다:
         Husband_aggressively_shakes_off…   ← 2컷
         Man_glaring_coldly…                ← 4컷
         Wife_confronts_husband_at_home…    ← 1컷
         Woman_clenches_fists_determinedly… ← 5컷
         Woman_smirks_at_another_woman…     ← 3컷
       이름 순서대로 붙이면 2·4·1·5·3 — **통째로 어긋난다.**
       다행히 플로우는 우리가 쓴 ACTION 을 보고 이름을 짓는다
       (shakes off · glaring coldly · clenches fists · smirks). 그 낱말을 맞춘다.
    """
    d = Path(d)
    vids = sorted([p for p in d.rglob("*") if p.suffix.lower() in
                   (".mp4", ".mov", ".m4v", ".webm") and not p.name.startswith("._")])
    out = {}
    for p in vids:
        # ⚠️⚠️ 2026-08-23 — **뒤에서부터** 찾는다. 앞에서 찾으면 파일 이름 앞에
        #    붙는 무작위 글자(1bac78f9- · c9a12b- · abc7-)의 c+숫자를 컷 번호로
        #    잘못 읽어 **컷이 뒤바뀐다.** 실제로 2컷과 3컷이 바뀌는 것을 잡았다.
        #    진짜 번호는 늘 이름 끝에 있다 (D001_E01_C01 · ..._c3 · cut2).
        ms = list(re.finditer(r"c(?:ut)?[ _-]?(\d{1,3})(?!\d)", p.stem, re.I))
        for m in reversed(ms):
            k = int(m.group(1))
            if 1 <= k <= n and k not in out:
                out[k] = p
                break

    left_f = [p for p in vids if p not in out.values()]
    left_k = [k for k in range(1, n + 1) if k not in out]

    # ② 이름과 컷 내용을 맞춘다
    if cuts and left_f and left_k:
        key = {}
        for c in cuts:
            k = int(c.get("n", 0))
            lines = str(c.get("prompt") or "").split("\n")
            act = next((l for l in lines if l.startswith("ACTION:")), "")
            shot = next((l for l in lines if l.startswith("SHOT:")), "")
            key[k] = words(act) | words(shot)
        pairs = sorted(
            ((len(key.get(k, set()) & words(f.stem)), k, f)
             for k in left_k for f in left_f), reverse=True,
            key=lambda x: (x[0], -x[1]))
        for sc, k, f in pairs:
            if sc <= 0 or k not in left_k or f not in left_f:
                continue
            out[k] = f
            left_k.remove(k)
            left_f.remove(f)

    # ③ 남은 것끼리 순서대로
    for k in list(left_k):
        if left_f:
            f = left_f.pop(0)
            out[k] = f
            # ⚠️ 2026-08-22 — 여기까지 온 것은 **번호도 이름도 못 맞춘** 것이다.
            #    남은 것을 그냥 순서대로 붙이므로 순서가 틀릴 수 있다.
            #    그런데 틀려도 영상은 멀쩡히 나온다 — 자막만 엉뚱한 장면에
            #    붙는다. 조용히 넘어가면 아무도 모르고 그대로 올라간다.
            print(f"  ⚠️ {k}컷은 이름으로 못 맞춰 남은 것을 그냥 붙였다 "
                  f"({f.name}) — 장면과 자막이 맞는지 꼭 보십시오")
    return out


def episode(sid, no, clips_dir, out_dir):
    """한 화(5컷)를 모아 30초 쇼츠 하나로."""
    doc = json.loads((ROOT / "data" / "series" / f"{sid}.json").read_text(encoding="utf-8"))
    ep = next((e for e in doc["episodes"] if int(e.get("no", 0)) == int(no)), None)
    if not ep:
        raise SystemExit(f"❌ {sid} 에 {no}화가 없다")
    clips_dir, out_dir = Path(clips_dir), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / "_tmp"
    hook = hook_of(ep, doc)
    print(f"{sid} {no}화 「{ep.get('title','')}」")
    print(f"  후킹 문구: {hook}")

    files = pick_clips(clips_dir, len(ep["cuts"]), ep["cuts"])
    voices = tts.pick_voices(doc.get("characters"))
    personas = tts.pick_personas(doc.get("characters"))
    # 왼쪽 위 「시리즈 제목 · n화」 (2026-08-22 운영자 지시)
    label = f"{str(doc.get('title') or '').strip()} · {int(no)}화"
    if keep_audio():
        pass          # 구글 소리 그대로 — "갈아 끼운다" 인사말을 찍으면 거짓말이 된다
    elif tts.key():
        print(f"  🎙 목소리를 갈아 끼운다 — {tts.engine_note()}")
        # ⚠️ 위 한 줄은 **기본값**이다. 실제 배정은 배역 나이에 따라 다르다.
        #    (2026-08-22 — 머리말은 Erinome·Iapetus 라고 적혔는데 실제로는
        #     Gacrux·Algenib 가 말하고 있었다. 화면이 거짓말하면 안 된다.)
        for ch in doc.get("characters") or []:
            nm = (ch.get("name") or "").strip()
            if nm:
                print(f"   배역: {nm} → {voices.get(nm)} ({personas.get(nm)})")
    else:
        print("  (목소리 열쇠가 없어 원래 소리를 그대로 쓴다 —\n           GEMINI_API_KEY 나 GOOGLE_TTS_KEY 가 있어야 한다)")
    parts = []
    for c in ep["cuts"]:
        n = int(c["n"])
        src = files.get(n)
        if not src:
            raise SystemExit(f"❌ {n}컷 클립이 없다 ({clips_dir})")
        # ⭐ ① 앞뒤 죽은 시간을 먼저 잘라 낸다 (플로우 6초짜리의 앞 1초 무음,
        #      제미나이 10초짜리의 뒤 3.8초 무음이 그대로 나가면 안 된다)
        # ⚠️⚠️ 2026-08-23 — 원본 소리를 그대로 쓸 때(루미나)는 **자르지 않는다.**
        #    trim_dead 는 예전 Veo 가 대본에 없는 말을 지어내 채우던 것을
        #    잘라내려고 만든 것이다. 루미나 나레이션은 전부 진짜 대사인데,
        #    '말 토막이 대사 수보다 많다' 는 이유로 **진짜 대사를 잘라냈다.**
        #    운영자: "영상 및 나레이션이 뒷부분이 남아있는 상태에서 끊겼어."
        #    컷 길이는 루미나에서 운영자가 정한다 — 우리가 손댈 일이 아니다.
        if not keep_audio():
            src = trim_dead(src, tmp / f"cut{n}_tight.mp4",
                            turns=len(dia_turns(c.get("prompt"))))
        # ⭐ ② 소리를 갈아 끼우고, ③ 그 다음에 자막·크롭을 얹는다.
        #    (자막이 **말하는 자리**를 소리에서 찾으므로 순서가 중요하다)
        dubbed = tmp / f"cut{n}_ko.mp4"
        if dub(src, dia_turns(c.get("prompt")), voices, dubbed, tmp, personas):
            src = dubbed
        # ⭐⭐ 2026-08-24 띠 배치 — 후킹은 **모든 컷에 내내** 띄운다.
        #    위 검은 칸에 앉으므로 가릴 얼굴이 없다. 도중에 들어온 사람도
        #    무슨 이야기인지 바로 안다(운영자: "후킹문구를 계속 띄워놓은건 어때?").
        #    ⚠️ 세로 통짜 배치로 되돌릴 때(HOOK_SEC > 0)는 얼굴을 덮으므로
        #       예전처럼 **첫 컷 앞 몇 초만** 나가게 자동으로 갈린다.
        # ⭐ 마지막 컷에서는 그 자리가 「다음 화 — 제목」 + 구독 알약으로 바뀐다
        first_cut = (c is ep["cuts"][0])
        last_cut = (c is ep["cuts"][-1])
        # ⭐ 때 도장 — **첫 컷 앞 3초**에만. 8년짜리 사건이라 언제 얘기인지를
        #    안 알려 주면 화가 바뀔 때마다 시청자가 길을 잃는다 (2026-08-25).
        # ⭐⭐ 2026-08-25 — 후킹은 **마지막 컷까지 그대로** 위 칸에 둔다
        #    (운영자: "후킹 문구는 끝날 때까지 계속 유지").
        #    다음 화 예고는 위 칸이 아니라 **화면 가운데**에, 마지막 말이
        #    끝난 뒤 영상 칸만 어두워지면서 뜬다.
        d = compose(src, hook if (not HOOK_SEC or first_cut) else "",
                    c.get("subtitle"), tmp / f"cut{n}.mp4", tmp, label=label,
                    whos=[w for w, _ in dia_turns(c.get("prompt"))],
                    stamp=(ep.get("when") or "") if first_cut else "",
                    preview=preview_card(doc, no) if last_cut else None)
        parts.append(d)
        print(f"  ✅ {n}컷 ← {files[n].name}  (소리 {gain_for(src):+.1f}dB)")

    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    final = out_dir / f"{sid}_ep{int(no):02d}_short.mp4"
    p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                        "-i", str(lst), "-c", "copy", "-movflags", "+faststart",
                        str(final)], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"이어 붙이기 실패:\n{p.stderr[:400]}")
    total = sum(C.probe(p)[2] for p in parts)
    # ⭐ 2026-08-23 운영자: "각 영상이 전부 6초는 아니니까 전체 영상 길이도
    #    잘 파악해야 돼." — 컷 길이는 전부 실측(probe)으로 재고 있고, 여기서
    #    **합계**를 검사한다. 60초를 넘으면 유튜브가 쇼츠로 안 태운다.
    if total > 59.5:
        print(f"\n⚠️⚠️ 전체 {total:.1f}초 — 60초를 넘으면 유튜브가 **쇼츠로 안 태웁니다.**"
              f"\n     루미나에서 컷을 줄이거나 대사를 짧게 해 주십시오.")
    elif total < 12:
        print(f"\n⚠️ 전체 {total:.1f}초 — 너무 짧습니다. 컷이 빠지지 않았는지 확인하십시오.")
    won = tts.bill_flush(f"{sid} {no}화")
    print(f"\n✅ {final.name} — {len(parts)}컷 · {total:.1f}초"
          + (f" · 목소리 값 {won:.0f}원" if won else ""))
    return final


def one(clip, sid, no, cut, hook, sub, out_dir):
    """클립 **하나**로 쇼츠를 만들어 본다 — 한 화 만들 때와 똑같은 차례로.

    ⚠️⚠️ 2026-08-21 사고 — 예전에 여기서 compose() 만 불렀다. 그러면 소리를
       **안 갈아 끼운다.** 그런데 화면은 멀쩡히 나오니 다 된 줄 알고 운영자에게
       보냈고, 운영자는 한동안 플로우가 만든 외국인 같은 소리를 듣고 있었다.
       미리보기가 진짜와 다른 길로 가면, 미리보기는 거짓말이 된다.
       → 여기서도 episode() 와 **똑같이** ① 잘라내기 ② 소리 갈아 끼우기
         ③ 자막·크롭 을 다 한다.
    """
    clip = Path(clip)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = out_dir / "_tmp"
    turns, voices, personas, label = [], {}, {}, None
    if sid and no and cut:
        # 대본에서 이 컷의 후킹·자막·대사를 그대로 가져온다
        doc = json.loads((ROOT / "data" / "series" / f"{sid}.json")
                         .read_text(encoding="utf-8"))
        ep = next((e for e in doc["episodes"]
                   if int(e.get("no", 0)) == int(no)), None)
        if not ep:
            raise SystemExit(f"❌ {sid} 에 {no}화가 없다")
        c = next((x for x in ep["cuts"] if int(x["n"]) == int(cut)), None)
        if not c:
            raise SystemExit(f"❌ {no}화에 {cut}컷이 없다")
        hook = hook or hook_of(ep, doc)
        sub = sub or c.get("subtitle") or ""
        turns = dia_turns(c.get("prompt"))
        voices = tts.pick_voices(doc.get("characters"))
        personas = tts.pick_personas(doc.get("characters"))
        label = f"{str(doc.get('title') or '').strip()} · {int(no)}화"
        print(f"{sid} {no}화 {cut}컷 「{ep.get('title','')}」")
    print(f"  후킹 문구: {hook}")
    for who, text in turns:
        print(f"    {who}: {text}")

    # ⭐ ① 앞뒤 죽은 시간부터 잘라 낸다 (대사 수를 알면 지어낸 말도 잘라 낸다)
    src = clip if keep_audio() else trim_dead(clip, tmp / "tight.mp4",
                                              turns=len(turns))
    # ⭐ ② 소리를 갈아 끼운다
    if not turns:
        print("  ⚠️ 대사를 못 찾아 **원래 소리를 그대로 쓴다.**\n"
              "     --sid S001 --no 1 --cut 1 처럼 어느 컷인지 알려 주면 갈아 끼운다")
    elif keep_audio():
        print("  🔊 구글이 만든 소리를 그대로 둔다 (KEEP_AUDIO)")
    elif not tts.key():
        print("  ⚠️ 목소리 열쇠가 없어 **원래 소리를 그대로 쓴다** —\n"
              "     GEMINI_API_KEY 나 GOOGLE_TTS_KEY 가 있어야 한다")
    else:
        print(f"  🎙 목소리를 갈아 끼운다 — {tts.engine_note()}")
        dubbed = tmp / "ko.mp4"
        if dub(src, turns, voices, dubbed, tmp, personas):
            src = dubbed
        else:
            print("  ⚠️ 갈아 끼우기가 안 됐다 — 원래 소리가 그대로 나간다")
    # ⭐ ③ 그 다음에 자막·크롭을 얹는다
    out = out_dir / (clip.stem + "_short.mp4")
    compose(src, hook, sub, out, tmp, label=label,
            whos=[w for w, _ in turns])
    won = tts.bill_flush(f"{sid or '?'} {no or '?'}화 {cut or '?'}컷 시험")
    print(f"\n✅ {out} — {C.probe(out)[2]:.1f}초 · 소리 {gain_for(out):+.1f}dB"
          + (f" · 목소리 값 {won:.0f}원" if won else ""))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sid", nargs="?", default="")
    ap.add_argument("no", nargs="?", default="")
    ap.add_argument("--clips", default="build/clips")
    ap.add_argument("--out", default="build/shorts")
    ap.add_argument("--demo", default="", help="클립 하나로 쇼츠를 만들어 본다")
    ap.add_argument("--cut", default="", help="--demo 때 몇 컷인지 (대사를 가져온다)")
    ap.add_argument("--hook", default="")
    ap.add_argument("--sub", default="")
    a = ap.parse_args()
    if a.demo:
        return one(a.demo, a.sid, a.no, a.cut, a.hook, a.sub, a.out)
    if not a.sid or not a.no:
        ap.error("시리즈 번호와 화 번호를 달라 (예: S001 1)")
    episode(a.sid, a.no, a.clips, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
