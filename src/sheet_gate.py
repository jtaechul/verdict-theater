#!/usr/bin/env python3
"""⭐ 받은 인물 시트가 **쓸 수 있는 그림인지 자로 재서** 판정한다. 값 0원.

    python3 src/sheet_gate.py assets/sheets/M70.png --kind face   (얼굴+상반신 12명)
    python3 src/sheet_gate.py assets/sheets/M70.png --kind full   (전신 5명)
    python3 src/sheet_gate.py --selftest        가짜 그림으로 이 코드가 맞는지 시험

왜 이것부터 만드는가 (2026-08-13~14)
    손님: "니가 만든 명령 프롬프트가 문제가 있었던 게 맞지?" — 맞다.
    그런데 프롬프트가 부족했던 것보다 **받은 시트가 제대로 나왔는지 재보지 않은 것**이
    더 큰 잘못이었다. 재는 코드는 10줄이면 됐는데 그 10줄을 안 써서,
    목 잘린 인물이 영상에 나가고 자르는 코드를 일곱 번 고쳐 일곱 번 다 실패했다.

    ⭐ 그래서 순서를 뒤집는다. **재는 자를 먼저 만들고, 그다음에 돈을 쓴다.**

무엇이 바뀌었나 — 칸 선을 **안 긋는다**
    예전 시트는 마젠타 선으로 칸을 나눴다. 그런데 모델이 그 선을 **인물 머리 위로**
    그었고(실측 7장 전부 접촉률 1.2~1.9%), 선과 머리가 같은 픽셀이 되어
    지우면 머리가 없어지고 남기면 흰 막대가 됐다. 자르기로는 못 푸는 문제다.
    → 선을 아예 안 그리게 한다. 칸은 **넓은 초록 여백**으로만 나눈다.
      선이 없으면 선이 머리에 겹치는 사고가 **물리적으로 불가능**하다.

    ⚠️ 그 대가로 예전 도구는 쓸모가 없어진다.
       lines_touch_figures 는 마젠타가 없으니 영원히 0%만 돌려준다.
       그래서 **색에 기대지 않고** 선·막대·글자를 찾는 G2 를 새로 만든다.
       이게 이 검사의 핵심 방어선이다.

⚠️ 임계값의 출처를 반드시 밝힌다
    합격한 시트 표본이 아직 **0장**이다. 아래 숫자는 실패 표본(7장)과 산술에서
    끌어낸 공학적 추정치다. 시범 1장이 나오면 그 실측값으로 다시 잡아야 한다.
    (특히 G10 경계 혼색 폭, G2 세장비·채움률이 1순위)
"""
import argparse
import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ── 시트 규격 ───────────────────────────────────────────
W_EXP, H_EXP = 3072, 5504          # 4K · 9:16 로 요청했을 때 실제로 오는 크기
CHROMA = (0, 177, 64)              # #00B140
LOGO_BAND = 700                    # 하단 이만큼은 비워 둔다 (제미나이 로고 자리)

# ── 판정 기준 (숫자마다 근거를 옆에 적는다) ──────────────
GREEN_LOOSE = 60                   # 이 안이면 '초록 계열' 로 본다
GREEN_TIGHT = 20                   # 이 안이면 '순수 초록'
# ⚠️ 이 숫자를 두 번 옮겼다. 두 번째는 **까닭이 다르다** — 적어 둔다.
#    1차(0.70→0.50): 70% 로 잡았다가 멀쩡한 시트가 걸렸다(58.3%). 합격 표본이
#                    0장일 때 어림으로 잡은 값이었다.
#    2차(0.50→0.30): 0.50 도 여전히 **묻는 것이 틀린** 숫자였다. 이 검사가
#                    가려내야 하는 것은 "초록이 많은가" 가 아니라
#                    **"바탕이 초록이 맞는가"** — 곧 모델이 크로마키 대신
#                    방·거리 같은 배경을 그려 버렸는가다.
#                    실측으로 두 무리가 갈린다:
#                       바탕이 초록인 시트   46 ~ 58%   (인물이 클수록 낮다)
#                       배경을 그려 버린 시트  0 ~ 10%   (초록이 아예 없다)
#                    사이가 텅 비어 있으므로 30% 로 자른다. 46% 에 겨우 걸치는
#                    0.50 은 인물을 크게 그린 멀쩡한 시트를 계속 떨어뜨린다.
#    ⭐ 바탕이 초록인데 인물이 커서 초록이 준 것은 **잘못이 아니다.**
#       인물이 서로 붙었는지는 G3·G4·G7 이 따로 직접 잰다.
MIN_GREEN_RATIO = 0.30             # 이보다 낮으면 '바탕이 초록이 아니다'
MAX_DIRT = 0.0005                  # 인물 밖 오염 0.05% 까지 봐준다

SLIM_RATIO = 8.0                   # 긴변/짧은변 이 이상이면 '막대·선'
SLIM_AREA = 2000                   # 그만한 넓이가 있을 때만 본다 (부스러기 제외)
BAR_SHORT, BAR_LONG = 60, 600      # 폭 60 이하 · 길이 600 이상 = 선
MIN_FILL = 0.22                    # 덩어리 채움률. 사람은 이보다 크고, 선이 붙으면 작아진다

MIN_GAP = 120                      # 인물 사이 최소 간격 (실측 136~288px 로 지켜진다)
# ⚠️ 자를 때 실제로 필요한 여백은 얼마인가. 덩어리를 찾아 오려내므로 인물과
#    그림 끝 사이에 **초록이 한 줄이라도** 있으면 자를 수 있다. 흰 테두리(약
#    10px)와 여유를 얹어 24px 로 잡는다. 100px 은 근거 없이 크게 부른 값이었다
#    (실측: 멀쩡한 시트의 가장 좁은 옆 여백이 56~64px 이었는데 안 잘렸다).
EDGE_OK = 24                       # 이만큼만 있으면 안전하게 잘린다
MIN_EDGE = EDGE_OK                 # (옛 이름 — 밖에서 쓰는 곳이 있어 남겨 둔다)
MIN_LOGO_GAP = 100                 # 로고와 인물 사이

FRAG_AREA = 20000                  # 이보다 작으면 '파편' 으로 세지 않는다
FRAG_WARN = 3                      # 파편 3개까지 경고, 4개부터 불합격

HOLE_BAD = 30000                   # 몸 안 초록 구멍이 이보다 크면 불합격 (초록 옷)
HOLE_WARN = 2000

EDGE_MIX_OK, EDGE_MIX_WARN = 4.0, 7.0   # 경계 혼색 폭(px). 자르면 테두리로 남는다

# ⭐ 모델이 실제로 어떻게 그리는가 (2026-08-14 · 시트 두 장을 재서 알아낸 법칙)
#
#    프롬프트에 픽셀 숫자를 적는 것은 **아무 소용이 없다.** 증거:
#        요구 세로 950 → 실제  992~1168      요구 세로 760 → 실제 1160~1264
#        요구 폭  620 → 실제  768~840        요구 폭  520 → 실제  752~760
#        요구 폭  720 → 실제      840        요구 폭  560 → 실제  880~888
#    **작게 적었더니 오히려 더 크게 그렸다.** 숫자는 읽히지 않는다.
#
#    대신 모델은 늘 이렇게 한다 — **화면을 칸(cols×rows)으로 나누고 칸을 채운다.**
#        칸 크기 = 3072/열 × 5504/줄
#        인물 크기 = 칸 × 0.72 ~ 0.92     (두 장 모두 이 안에 들어온다)
#    3열 4줄이면 칸이 1024×1376 이고, 실측 폭 752~888(0.73~0.87) ·
#    세로 992~1264(0.72~0.92) 로 딱 맞는다.
#
#    그래서 기대치를 **손으로 적지 않고 이 법칙으로 계산한다.** 프롬프트 숫자를
#    바꿔도 기대치가 따라오지 않는 어긋남이 애초에 생길 수 없다.
FILL_LO = 0.68                     # 칸을 최소 이만큼은 채워야 한다 (실측 0.72~0.92)

# ⭐ 위·아래 한계를 나누는 원칙 (2026-08-14 에 정리)
#    **직접 잰 것은 불합격, 어림으로 대신 잰 것은 한계를 넉넉히.**
#    - 아래 한계(너무 작다)   : 이걸 재는 검사가 여기 말고 없다 → 딱 잡는다
#    - 위 한계(너무 크다)     : 사람이 붙었는지는 G3·G4·G7 이 **직접** 잰다.
#                              여기서는 "제 칸을 넘었는가" 만 본다 — 칸을 넘으면
#                              옆 사람 자리를 뺏은 것이니 그건 진짜 잘못이다.
#    예전엔 위 한계를 820·1250 으로 **손으로 적어** 두었는데, 근거가 없었고
#    실제로 멀쩡한 시트(폭 888 · 키 1264)를 두 번 떨어뜨렸다.


def _spec(n, bands, name, face_rows=0, fill_lo=FILL_LO):
    rows, cols = len(bands), max(bands)
    tw, th = W_EXP / cols, H_EXP / rows
    return {"n": n, "bands": bands, "name": name, "face_rows": face_rows,
            "h_range": (int(th * fill_lo), int(th)),   # 위 한계 = 제 칸 높이
            "w_max": int(tw),                          # 위 한계 = 제 칸 폭
            "tile": (int(tw), int(th))}


# 시트 종류별 기대치 (face_rows = 위에서 몇 줄이 '얼굴' 인가 — 얼굴은 잘리면 안 된다)
KINDS = {
    # 얼굴 6 + 상반신 6 = 12명, 가로 3명씩 4무리 (위 2줄이 얼굴)
    #   열둘이 **다 같은 크기**로 그려지므로 아래 한계를 칸의 68% 로 바짝 잡아도 된다.
    "face": _spec(12, [3, 3, 3, 3], "얼굴+상반신 시트", face_rows=2),
    # 전신 5명, 위 3 + 아래 2 (얼굴 줄 없음 — 전신은 밑변에 닿아도 발만 평평해진다)
    #
    # ⚠️⚠️ 아래 한계를 얼굴 시트보다 **훨씬 낮게** 잡는다. 다섯 자세 가운데
    #      **의자에 앉기**와 **바닥에 주저앉기**는 프롬프트가 일부러
    #      "자세 때문에 자연히 더 낮아진다" 고 시킨 것이라, 선 사람의 절반쯤 된다.
    #      얼굴 시트와 같은 68%(1871px)로 재면 **똑바로 그려진 시트가 앉은 자세
    #      때문에 떨어진다.** 그 한 줄 때문에 265원이 날아갈 뻔했다.
    #      ⭐ 아직 전신 시트 표본이 0장이므로 이 값은 **예측**이다. 첫 장을 받으면
    #         실측으로 다시 잡는다. 다만 '앉으면 낮아진다' 는 우리가 시킨 것이라
    #         틀릴 수 없고, 조각·부스러기는 35%(≈963px)로도 충분히 걸러진다.
    "full": _spec(5, [3, 2], "전신 시트", face_rows=0, fill_lo=0.35),
}


class Gate:
    """검사 결과를 모은다. 하나라도 실패하면 불합격."""

    def __init__(self):
        self.rows = []
        self.fatal = False

    def add(self, code, name, got, want, ok, warn=False):
        self.rows.append((code, name, str(got), str(want), ok, warn))
        if not ok and not warn:
            self.fatal = True
        return ok

    def report(self):
        print(f"{'':4s} {'무엇을 재나':30s} {'잰 값':>16s} {'기준':>16s}  판정")
        print("─" * 88)
        for code, name, got, want, ok, warn in self.rows:
            mark = "✅" if ok else ("⚠️ 경고" if warn else "❌ 불합격")
            print(f"{code:4s} {name:30s} {got:>16s} {want:>16s}  {mark}")
        print("─" * 88)
        bad = [r for r in self.rows if not r[4] and not r[5]]
        if bad:
            print(f"❌ 불합격 — {len(bad)}가지가 기준에 못 미칩니다")
            for code, name, got, want, _o, _w in bad:
                print(f"   {code} {name}: {got} (기준 {want})")
        else:
            warns = [r for r in self.rows if r[5] and not r[4]]
            print("✅ 합격" + (f" (경고 {len(warns)}건 — 사람 눈으로 한 번 보십시오)" if warns else ""))
        return 1 if self.fatal else 0


# ── 픽셀 재기 ───────────────────────────────────────────
def masks(im):
    """→ (초록느슨, 초록엄격, 몸) 세 장의 참/거짓 지도."""
    import numpy as np
    a = np.asarray(im.convert("RGB")).astype(int)
    d = np.abs(a - np.array(CHROMA)).max(axis=2)
    loose = d <= GREEN_LOOSE
    tight = d <= GREEN_TIGHT
    return loose, tight, ~loose


def blobs(body, min_area=FRAG_AREA, step=8):
    """몸 지도에서 덩어리를 찾는다 → [(넓이, x0,y0,x1,y1)] (원본 좌표)."""
    import numpy as np
    small = body[::step, ::step]
    lab = np.zeros(small.shape, np.int32)
    out = []
    cur = 0
    for y in range(small.shape[0]):
        for x in range(small.shape[1]):
            if small[y, x] and not lab[y, x]:
                cur += 1
                q = deque([(y, x)])
                lab[y, x] = cur
                xs, ys = [], []
                while q:
                    cy, cx = q.popleft()
                    xs.append(cx)
                    ys.append(cy)
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = cy + dy, cx + dx
                        if (0 <= ny < small.shape[0] and 0 <= nx < small.shape[1]
                                and small[ny, nx] and not lab[ny, nx]):
                            lab[ny, nx] = cur
                            q.append((ny, nx))
                area = len(xs) * step * step
                if area >= min_area:
                    out.append((area, min(xs) * step, min(ys) * step,
                                (max(xs) + 1) * step, (max(ys) + 1) * step))
    out.sort(key=lambda b: (b[2], b[1]))
    return out


def check(path, kind="face", verbose=True):
    from PIL import Image
    import numpy as np
    spec = KINDS[kind]
    g = Gate()
    im = Image.open(path)

    # G0 ── 규격. 여기가 어긋나면 아래 절대 픽셀 기준이 전부 무의미해진다.
    g.add("G0", "그림 크기", f"{im.width}x{im.height}", f"{W_EXP}x{H_EXP}",
          (im.width, im.height) == (W_EXP, H_EXP))
    if g.fatal:
        g.report()
        print("   → 크기가 다르면 아래 픽셀 기준이 전부 어긋납니다. 여기서 멈춥니다.")
        return 1
    W, H = im.size

    loose, tight, body = masks(im)
    g.add("G1", "바탕이 초록인 비율", f"{loose.mean() * 100:.1f}%",
          f"{MIN_GREEN_RATIO * 100:.0f}% 이상", loose.mean() >= MIN_GREEN_RATIO)

    bs = blobs(body)
    n = len(bs)
    g.add("G3", "인물 덩어리 개수", n, spec["n"], n == spec["n"])

    # G2 ── ⭐ 색에 기대지 않고 선·막대·글자를 찾는다. 이 검사의 핵심.
    slim = sum(1 for a, x0, y0, x1, y1 in bs
               if a >= SLIM_AREA
               and max(x1 - x0, y1 - y0) / max(1, min(x1 - x0, y1 - y0)) >= SLIM_RATIO)
    bar = sum(1 for _a, x0, y0, x1, y1 in bs
              if min(x1 - x0, y1 - y0) <= BAR_SHORT and max(x1 - x0, y1 - y0) >= BAR_LONG)
    fills = [a / max(1, (x1 - x0) * (y1 - y0)) for a, x0, y0, x1, y1 in bs]
    worst_fill = min(fills) if fills else 0.0
    g.add("G2", "가늘고 긴 덩어리(선·막대)", slim, "0개", slim == 0)
    g.add("G2", "길쭉한 줄", bar, "0개", bar == 0)
    g.add("G2", "덩어리 채움률(최저)", f"{worst_fill:.2f}", f"{MIN_FILL} 이상",
          worst_fill >= MIN_FILL)

    # ⭐⭐ G2-b ── **사람을 가로지르는 줄**을 직접 찾는다.
    #    ⚠️ 자기시험이 찾아낸 구멍이다. 위의 '가늘고 긴 덩어리' 검사는
    #       막대가 **사람과 붙어 버리면 못 잡는다** — 붙는 순간 그 덩어리는
    #       더 이상 가늘지 않기 때문이다. 그런데 예전 사고가 정확히 그 경우였다
    #       (마젠타 선이 머리 위에 겹쳐 그려짐). 그래서 따로 잰다.
    #
    #    어떻게 — 가로 한 줄씩 '몸 픽셀이 얼마나 넓게 퍼져 있나' 를 본다.
    #    사람만 있으면 한 줄의 몸 픽셀은 사람 폭만큼만 퍼진다. 줄이 그어져 있으면
    #    그 줄에서 갑자기 화면 폭 전체로 퍼진다. 세로 줄도 같은 방법으로 본다.
    def spanning(mask, axis):
        cover = mask.sum(axis=axis)          # 줄마다 몸 픽셀 수
        # ⚠️ 여기서 가로·세로를 바꿔 쓰면 기준이 엉뚱해져 **영원히 안 걸린다.**
        #    (실제로 처음에 shape[1-axis] 로 잘못 써서, 막대가 뻔히 그어져 있는데도
        #     0개로 나왔다. 자기시험이 아니었으면 그대로 올릴 뻔했다.)
        #    axis=1 이면 가로로 더한 것이니 기준은 **가로 길이(W)** = shape[1] = shape[axis].
        # ⚠️⚠️ 2026-08-14 (2차) — 55% 는 **너무 헐거웠다.** 전신 시트에서 멀쩡한
        #    그림이 "세로줄 2개" 로 걸렸다. 까닭이 분명하다 — 위에 선 사람의
        #    바짓가랑이와 아래 앉은 사람의 다리가 **같은 세로줄에 겹쳐 놓이면**
        #    그 열의 몸 픽셀이 2400+1400=3800(69%)이 되고, 폭은 다리라 얇다.
        #    곧 '얇고 길다' 는 조건에 **사람 다리가 그대로 걸린다.**
        #    (얼굴 시트에선 안 걸렸다 — 얼굴은 얇고 길지 않기 때문)
        #    잡으려는 것은 격자선이고, 격자선은 그림 끝에서 끝까지 간다.
        #    실측: 진짜 막대 93.5% · 사람 다리 겹침 69%. 그 사이인 90% 로 자른다.
        limit = mask.shape[axis] * 0.90      # 끝에서 끝까지 가야 '줄' 로 본다
        wide = np.where(cover > limit)[0]
        if len(wide) == 0:
            return 0, 0
        # 이어진 구간으로 묶어, **얇은** 구간만 줄로 본다 (두꺼우면 사람 무리다)
        runs, s = [], wide[0]
        for i in range(1, len(wide)):
            if wide[i] != wide[i - 1] + 1:
                runs.append((s, wide[i - 1]))
                s = wide[i]
        runs.append((s, wide[-1]))
        thin = [r for r in runs if r[1] - r[0] + 1 <= 80]
        return len(thin), int(max((r[1] - r[0] + 1 for r in thin), default=0))

    hline, hthick = spanning(body, 1)        # 가로줄
    vline, vthick = spanning(body, 0)        # 세로줄
    g.add("G2b", "사람을 가로지르는 가로줄", f"{hline}개",
          "0개", hline == 0)
    g.add("G2b", "사람을 가로지르는 세로줄", f"{vline}개",
          "0개", vline == 0)

    # G4 ── 인물끼리 붙었나
    gap = 10 ** 9
    for i in range(len(bs)):
        for j in range(i + 1, len(bs)):
            _a, ax0, ay0, ax1, ay1 = bs[i]
            _b, bx0, by0, bx1, by1 = bs[j]
            dx = max(0, max(ax0 - bx1, bx0 - ax1))
            dy = max(0, max(ay0 - by1, by0 - ay1))
            gap = min(gap, int((dx ** 2 + dy ** 2) ** 0.5))
    if len(bs) >= 2:
        # ⚠️ 2026-08-14 (2차) — 120px 을 못 넘겼다고 **멀쩡한 전신 시트를 떨어뜨렸다**
        #    (실측 80px). 120 은 얼굴 시트 열두 명이 반듯한 격자로 놓일 때 잡은
        #    값인데, 전신은 걷는 자세의 앞발처럼 **자세 때문에** 자연히 가까워진다.
        #    이 검사가 진짜 막아야 하는 것은 '둘이 한 덩어리로 붙는 것' 인데,
        #    그건 G3(개수)·G7(무리별 인원)이 **직접** 잰다. 여기는 어림이다.
        #    → 자를 수 없을 만큼 붙었을 때만 불합격(24px, 자를 때 필요한 최소),
        #      120px 에 못 미치면 경고로만 알린다.
        g.add("G4", "인물 사이 최소 간격", f"{gap}px",
              f"{EDGE_OK}px 이상 (넉넉히는 {MIN_GAP})",
              gap >= MIN_GAP, warn=gap >= EDGE_OK)

    # G5 ── 잘렸나 (가장자리 여백이 아니라 **잘림**을 잰다)
    #
    # ⚠️ 2026-08-14 — 처음엔 '네 변 모두 100px 이상 비워라' 로 쟀다. 그러다
    #    **멀쩡한 시트를 떨어뜨렸다.** 실측한 사실 둘이 그 기준을 무너뜨린다.
    #      ① 모델은 화면을 칸으로 나눠 **밑변까지 꽉 채워 그린다.** 두 장 다
    #         맨 아랫줄이 밑변에 딱 닿았다. 픽셀 숫자를 아무리 적어도 안 바뀐다
    #         (950→1168, 760→1264. 작게 적었더니 오히려 더 크게 그렸다).
    #      ② 그런데 **맨 아랫줄은 상반신**이다. 상반신은 원래 허리에서 평평하게
    #         끝나는 그림이라, 밑변에 닿아도 잘린 티가 나지 않는다.
    #         실제로 잘라 눈으로 확인했다 — 열두 장 모두 멀쩡했다.
    #
    #    그러니 물어야 할 것은 '여백이 있는가' 가 아니라 **'잘리면 안 될 것이
    #    잘렸는가'** 다. 얼굴은 어느 변에도 닿으면 안 되고(닿으면 머리·턱이
    #    날아간다), 상반신·전신은 **밑변만** 닿아도 된다.
    if bs:
        n_face = spec.get("face_rows", 0) * (spec["bands"][0] if spec["bands"] else 0)
        worst_bad = None
        for i, (_a, x0, y0, x1, y1) in enumerate(bs):
            is_face = i < n_face
            room = {"왼쪽": x0, "위": y0, "오른쪽": W - x1}
            if is_face:
                room["아래"] = H - y1     # 얼굴은 턱이 잘리면 안 되니 밑변도 본다
            # 상반신·전신은 밑변을 안 본다 — 원래 허리·발에서 평평하게 끝나는
            # 그림이라 밑변에 닿아도 잘린 티가 없다(2026-08-14 눈으로 확인).
            for side, px in room.items():
                if px < EDGE_OK and (worst_bad is None or px < worst_bad[1]):
                    worst_bad = (f"{i + 1}번 {side}", px, is_face)
        if worst_bad:
            g.add("G5", "잘린 인물", f"{worst_bad[0]} {worst_bad[1]}px",
                  f"{EDGE_OK}px 이상", False)
        else:
            g.add("G5", "잘린 인물", "없음", f"각 변 {EDGE_OK}px 이상", True)

    # G6 ── 인물 말고 **딴 것**이 들어와 있나 (로고·글자·상표)
    #
    # ⚠️ 2026-08-14 — 여기는 원래 '하단 700px 을 비워라' 였다. 제미나이가 거기에
    #    로고를 찍는다고 **짐작**하고 만든 자리다. 시트 아홉 장의 아래쪽을 전부
    #    들여다봤더니 **로고는 하나도 없었다.** 옛 시트 구석의 비초록 4~7% 는
    #    로고가 아니라 우리가 그으라고 시킨 **마젠타 격자선**이었다.
    #    없는 것을 피하려고 화면 5분의 1을 버리고 있었고, 그것 때문에 멀쩡한
    #    시트가 두 번 떨어졌다. 짐작을 지우고 **진짜 두려운 것**을 잰다 —
    #    인물이 아닌 덩어리가 끼어들었는가. (그것이 로고든 글자든 잡힌다)
    #    ⚠️ 처음 쓴 코드는 **한 번도 울릴 수 없는 죽은 검사**였다. 덩어리를 다시
    #       찾아 `bs` 안에 들었는지 봤는데, 그 둘이 같은 목록이라 늘 "들었다" 가
    #       나왔다. 자기시험이 그 자리에서 잡아 줬다(⑥ 이 통과로 나옴).
    #       제대로 묻는다 — **사람 크기에 한참 못 미치는 덩어리가 있는가.**
    #       로고·글자는 사람보다 훨씬 작다. 실측: 사람 75만px · 로고 4.6만px.
    areas = sorted(b[0] for b in bs)
    med = areas[len(areas) // 2] if areas else 0
    odd = [b for b in bs if med and b[0] < med * 0.35]
    g.add("G6", "사람 아닌 덩어리(로고·글자)", f"{len(odd)}개", "0개", not odd)

    # G7 ── 무리 구성 (가로로 몇 명씩)
    bands, cur = [], []
    last = None
    for b in bs:
        mid = (b[2] + b[4]) // 2
        if last is not None and mid - last > (H / (len(spec["bands"]) * 2)):
            bands.append(cur)
            cur = []
        cur.append(b)
        last = mid
    if cur:
        bands.append(cur)
    got_bands = [len(x) for x in bands]
    g.add("G7", "무리별 인원", str(got_bands), str(spec["bands"]),
          got_bands == spec["bands"])

    # G8 ── 인물 크기
    #
    # ⭐ 위·아래 한계의 무게가 다르다 (2026-08-14 · 두 번 데이고 정리했다)
    #      아래 한계(너무 작다)  → **불합격.** 컷아웃 화질을 이걸로만 지킨다.
    #      위 한계(너무 크다)    → **경고.** '옆 사람 자리를 뺏었나' 를 어림으로
    #                              보는 것인데, 그건 G3(개수)·G7(무리)·G4(간격)이
    #                              직접 잰다. 실제로 이 어림 때문에 멀쩡한 시트를
    #                              세 번 떨어뜨렸다 — 얼굴 폭 888(기준 820) ·
    #                              키 1264(기준 1250) · 전신 폭 1056(기준 1024).
    #                              셋 다 눈으로 보면 아무 문제가 없었다.
    if bs:
        hs = [b[4] - b[2] for b in bs]
        ws = [b[3] - b[1] for b in bs]
        lo, hi = spec["h_range"]
        g.add("G8", "인물 높이 범위", f"{min(hs)}~{max(hs)}px", f"{lo}~{hi}px",
              min(hs) >= lo and max(hs) <= hi, warn=min(hs) >= lo)
        g.add("G8", "인물 최대 폭", f"{max(ws)}px", f"{spec['w_max']}px 이하",
              max(ws) <= spec["w_max"], warn=True)

    # G9 ── 몸 안에 뚫린 초록 구멍 (초록 옷이 배경으로 먹힌 것)
    holes = blobs(loose, min_area=HOLE_WARN)
    inner = [h for h in holes
             if any(b[1] < h[1] and b[2] < h[2] and b[3] > h[3] and b[4] > h[4] for b in bs)]
    big_hole = max((h[0] for h in inner), default=0)
    g.add("G9", "몸 안 초록 구멍(가장 큰 것)", f"{big_hole:,}px",
          f"{HOLE_BAD:,}px 미만", big_hole < HOLE_BAD)

    # G10 ── 경계 혼색 폭. 자른 뒤 테두리가 남을지 미리 본다.
    # ⚠️ 2026-08-14 — 처음에 `혼색픽셀 / sqrt(몸픽셀)` 로 어림했다가 21.5px 라는
    #    말도 안 되는 값이 나왔다(눈으로 보면 경계는 또렷하다). 단위가 안 맞는
    #    엉터리 식이었다. 제대로 잰다 — **혼색 넓이 ÷ 둘레 길이 = 띠의 폭**.
    #    둘레는 몸 마스크를 1픽셀 부풀린 것과의 차이로 구한다.
    from PIL import ImageFilter as _F
    bimg = Image.fromarray((body * 255).astype("uint8"))
    grown1 = np.asarray(bimg.filter(_F.MaxFilter(3))) > 128
    perim = int((grown1 & ~body).sum())
    edge = int((loose & ~tight).sum())
    per = edge / max(1, perim)
    g.add("G10", "경계 혼색 폭", f"{per:.1f}px",
          f"{EDGE_MIX_OK} 이하", per <= EDGE_MIX_OK, warn=per <= EDGE_MIX_WARN)

    if verbose:
        print(f"\n[{spec['name']}] {Path(path).name}  {W}x{H}\n")
    rc = g.report()
    if verbose and bs:
        print()
        print("인물 덩어리 목록 (위→아래, 왼→오른쪽)")
        for i, (a, x0, y0, x1, y1) in enumerate(bs, 1):
            print(f"  {i:2d}. {x1 - x0:4d}x{y1 - y0:4d}px  at ({x0:4d},{y0:4d})")

    # ⭐⭐ 표본이 아직 없는 종류는 **막지 않고 알리기만 한다** (2026-08-14)
    #
    #    이날 하루에 좋은 시트를 세 번 떨어뜨렸다. 뿌리는 늘 같았다 —
    #    **합격한 그림을 한 장도 못 본 채로 채점표를 먼저 썼다.**
    #    로고 밴드 700px(로고는 없었다) · 폭 820(진짜는 888) · 초록 50%(진짜는 46)
    #    · 간격 120(전신은 80이 정상) — 전부 눈대중이었고 전부 틀렸다.
    #
    #    그러니 그 종류의 **사람이 확인한 시트가 하나도 없을 때는** 이 자를
    #    믿으면 안 된다. 그때는 불합격을 내지 않고 크게 알리기만 한다.
    #    (나쁜 그림이 새어 나가도 목 잘림 검사와 [영상 만들기]가 다시 막는다)
    #    한 장이라도 assets/sheets/ 에 살아남으면 = 사람이 보고 받아들인 것이므로
    #    그때부터 이 자가 진짜로 막는다.
    if rc != 0 and not proven(kind):
        print()
        print("=" * 68)
        print(f"⚠️ 이 종류({kind})는 **사람이 확인한 시트가 아직 한 장도 없습니다.**")
        print("   그래서 위 기준은 눈대중일 수 있습니다 — 실제로 2026-08-14 에")
        print("   좋은 시트를 세 번 떨어뜨렸습니다(로고 밴드·폭·초록 비율).")
        print("   **막지 않고 넘깁니다. 그림을 눈으로 보고 판단하십시오.**")
        print("=" * 68)
        return 0
    return rc


def proven(kind):
    """이 종류의 시트가 assets/sheets/ 에 살아 있는가 = 사람이 보고 받아들였는가."""
    d = Path(__file__).resolve().parent.parent / "assets" / "sheets"
    if not d.is_dir():
        return False
    for p in d.glob("*.png"):
        if (kind == "full") == p.stem.endswith("_full"):
            return True
    return False


# ── ⭐ 이 코드가 진짜 맞는지 가짜 그림으로 시험한다 ────────
def selftest():
    """가짜 그림 셋으로 **검사기가 제대로 판정하는지** 먼저 시험한다.

    ⚠️ 이 시험 없이 265원을 쓰면 안 된다. 검사기가 틀렸으면 그 돈이 또 헛돈다.
       ① 규칙대로 그린 것            → 통과해야 한다
       ② 인물 위로 회색 막대를 그은 것 → G2 에서 반드시 걸려야 한다
       ③ 인물 둘을 붙여 놓은 것       → G3·G4 에서 걸려야 한다
    """
    from PIL import Image, ImageDraw
    import tempfile
    ok = True

    def canvas():
        return Image.new("RGB", (W_EXP, H_EXP), CHROMA)

    def person(d, cx, cy, w, h, fill=(40, 40, 48)):
        d.ellipse([cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2], fill=fill)

    # ① 정상: 3명씩 4무리 = 12명
    #    ⚠️ 가짜 그림은 **모델이 실제로 그리는 대로** 놓아야 뜻이 있다. 예전엔
    #       프롬프트에 적은 숫자대로 놓았는데, 모델은 그 숫자를 안 읽는다.
    #       그래서 진짜 시트와 딴판인 그림으로 검사기를 시험하고 있었다.
    #       이제는 실측한 법칙 그대로 — **칸을 나누고 칸의 85% 를 채운다.**
    TW, TH = KINDS["face"]["tile"]                  # 1024 × 1376
    PW, PH = int(TW * 0.80), int(TH * 0.85)         # 819 × 1169
    CX = [int((c + 0.5) * TW) for c in range(3)]    # 512 · 1536 · 2560
    CY = [int((r + 0.5) * TH) for r in range(4)]    # 688 · 2064 · 3440 · 4816
    good = canvas()
    d = ImageDraw.Draw(good)
    for r in range(4):
        for c in range(3):
            person(d, CX[c], CY[r], PW, PH)
    p1 = Path(tempfile.mkdtemp()) / "good.png"
    good.save(p1)

    # ② 인물 위로 회색 막대 (예전 마젠타 선이 하던 짓 그대로)
    #    맨 윗줄 사람들의 **가슴 높이**를 가로지르게 긋는다 — 붙어 버리는 경우다.
    bar = good.copy()
    ImageDraw.Draw(bar).rectangle([100, CY[0] - 15, 2972, CY[0] + 15], fill=(120, 120, 120))
    p2 = p1.parent / "bar.png"
    bar.save(p2)

    # ③ 두 사람이 겹쳐 한 덩어리가 됨
    stick = canvas()
    d = ImageDraw.Draw(stick)
    for r in range(4):
        for c in range(3):
            person(d, CX[c] - (500 if (r, c) == (0, 1) else 0), CY[r], PW, PH)
    p3 = p1.parent / "stick.png"
    stick.save(p3)

    # ④ **얼굴이 윗변에 잘린 것** → 걸려야 한다 (머리 꼭대기가 날아간다)
    #    2026-08-14 에 G5 를 '여백' 에서 '잘림' 으로 바꾸면서 새로 넣었다.
    cutface = canvas()
    d = ImageDraw.Draw(cutface)
    for r in range(4):
        for c in range(3):
            cy = CY[r] - (PH // 2 + 40 if r == 0 else 0)   # 윗줄만 위로 밀어 자른다
            person(d, CX[c], cy, PW, PH)
    p4 = p1.parent / "cutface.png"
    cutface.save(p4)

    # ⑤ **상반신이 밑변에 닿은 것** → 통과해야 한다
    #    이것이 2026-08-14 에 멀쩡한 시트를 두 번 떨어뜨린 바로 그 모양이다.
    #    잘라서 눈으로 봤더니 열두 장 다 멀쩡했다 — 검사기가 틀렸던 것이다.
    touch = canvas()
    d = ImageDraw.Draw(touch)
    for r in range(4):
        for c in range(3):
            cy = (H_EXP - PH // 2) if r == 3 else CY[r]     # 아랫줄을 밑변에 붙인다
            person(d, CX[c], cy, PW, PH)
    p5 = p1.parent / "touch.png"
    touch.save(p5)

    # ⑥ **인물 아닌 덩어리(로고·글자)** → 걸려야 한다
    #    옛 G6 은 '하단 700px 을 비워라' 였는데, 그건 있지도 않은 로고를 피하려고
    #    화면 5분의 1을 버리는 규칙이었다. 이제 로고 자체를 찾는다.
    #    ⚠️ 처음엔 오른쪽 아래 구석에 그렸는데 **거기 사람이 있었다** — 로고가
    #       사람과 한 덩어리로 붙어 버려 시험이 헛돌았다. 사람이 없는 자리,
    #       곧 첫 줄과 둘째 줄 **사이의 빈 초록**에 놓는다.
    logo = good.copy()
    ymid = (CY[0] + PH // 2 + CY[1] - PH // 2) // 2      # 두 줄 사이 한가운데
    ImageDraw.Draw(logo).rectangle([1200, ymid - 48, 1900, ymid + 48],
                                   fill=(230, 230, 235))
    p6 = p1.parent / "logo.png"
    logo.save(p6)

    print("=" * 60)
    print("⭐ 검사기 자기시험 — 가짜 그림 6장으로 이 코드가 맞는지 본다")
    print("=" * 60)
    for name, path, want in (("① 규칙대로 그린 것", p1, 0),
                             ("② 인물 위로 막대를 그은 것", p2, 1),
                             ("③ 두 사람이 붙은 것", p3, 1),
                             ("④ 얼굴이 윗변에 잘린 것", p4, 1),
                             ("⑤ 상반신이 밑변에 닿은 것", p5, 0),
                             ("⑥ 로고 같은 덩어리가 낀 것", p6, 1)):
        print(f"\n──── {name} (기대: {'통과' if want == 0 else '불합격'})")
        got = check(path, "face", verbose=False)
        if got != want:
            ok = False
            print(f"   ❌ 검사기가 틀렸다 — {'통과' if got == 0 else '불합격'} 이 나왔다")
        else:
            print("   ✅ 검사기가 제대로 판정했다")

    print()
    print("=" * 60)
    print("✅ 검사기 자기시험 통과 — 이제 진짜 시트를 재도 된다"
          if ok else
          "❌ 검사기가 틀렸다 — 고치기 전에는 그림에 돈을 쓰지 마십시오")
    print("=" * 60)
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet", nargs="?", help="잴 시트 png")
    ap.add_argument("--kind", choices=list(KINDS), default="face")
    ap.add_argument("--selftest", action="store_true", help="가짜 그림으로 검사기를 시험한다")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.sheet:
        ap.error("잴 시트를 적거나 --selftest 를 쓰십시오")
    return check(a.sheet, a.kind)


if __name__ == "__main__":
    sys.exit(main())
