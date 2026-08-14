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
# ⚠️ 2026-08-14 실측 — 70% 로 잡았다가 **멀쩡한 시트가 걸렸다**(58.3%).
#    인물 12명을 크게 그리면 초록이 58% 까지 내려가는 것이 정상이다.
#    이 검사의 뜻은 '바탕이 초록이 맞는가' 이지 '초록이 많은가' 가 아니다.
#    합격 표본이 0장일 때 어림으로 잡은 숫자였다 — 실측으로 다시 잡는다.
MIN_GREEN_RATIO = 0.50             # 바탕이 이만큼은 초록이어야 한다
MAX_DIRT = 0.0005                  # 인물 밖 오염 0.05% 까지 봐준다

SLIM_RATIO = 8.0                   # 긴변/짧은변 이 이상이면 '막대·선'
SLIM_AREA = 2000                   # 그만한 넓이가 있을 때만 본다 (부스러기 제외)
BAR_SHORT, BAR_LONG = 60, 600      # 폭 60 이하 · 길이 600 이상 = 선
MIN_FILL = 0.22                    # 덩어리 채움률. 사람은 이보다 크고, 선이 붙으면 작아진다

MIN_GAP = 120                      # 인물 사이 최소 간격 (프롬프트 요구 200~250 의 절반)
MIN_EDGE = 100                     # 그림 가장자리 여백 (요구 200 의 절반)
MIN_LOGO_GAP = 100                 # 로고와 인물 사이

FRAG_AREA = 20000                  # 이보다 작으면 '파편' 으로 세지 않는다
FRAG_WARN = 3                      # 파편 3개까지 경고, 4개부터 불합격

HOLE_BAD = 30000                   # 몸 안 초록 구멍이 이보다 크면 불합격 (초록 옷)
HOLE_WARN = 2000

EDGE_MIX_OK, EDGE_MIX_WARN = 4.0, 7.0   # 경계 혼색 폭(px). 자르면 테두리로 남는다

# 시트 종류별 기대치
KINDS = {
    # 얼굴 6 + 상반신 6 = 12명, 가로 3명씩 4무리
    "face": {"n": 12, "bands": [3, 3, 3, 3],
             "h_range": (750, 1250), "w_max": 820, "name": "얼굴+상반신 시트"},
    # 전신 5명, 위 3 + 아래 2
    "full": {"n": 5, "bands": [3, 2],
             "h_range": (900, 2100), "w_max": 900, "name": "전신 시트"},
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
        limit = mask.shape[axis] * 0.55      # 그 방향 길이의 55% 넘게 퍼지면 의심
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
        g.add("G4", "인물 사이 최소 간격", f"{gap}px", f"{MIN_GAP}px 이상", gap >= MIN_GAP)

    # G5 ── 가장자리 여백 (머리·발 잘림)
    if bs:
        left = min(b[1] for b in bs)
        top = min(b[2] for b in bs)
        right = W - max(b[3] for b in bs)
        bot = H - max(b[4] for b in bs)
        worst = min(left, top, right, bot)
        g.add("G5", "그림 가장자리 여백(최소)", f"{worst}px", f"{MIN_EDGE}px 이상",
              worst >= MIN_EDGE)

    # G6 ── 하단 로고 자리를 비웠나
    inband = int(body[H - LOGO_BAND:, :].sum())
    g.add("G6", f"하단 {LOGO_BAND}px 안 인물 픽셀", f"{inband:,}", "0", inband == 0)

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
    if bs:
        hs = [b[4] - b[2] for b in bs]
        ws = [b[3] - b[1] for b in bs]
        lo, hi = spec["h_range"]
        g.add("G8", "인물 높이 범위", f"{min(hs)}~{max(hs)}px", f"{lo}~{hi}px",
              min(hs) >= lo and max(hs) <= hi)
        g.add("G8", "인물 최대 폭", f"{max(ws)}px", f"{spec['w_max']}px 이하",
              max(ws) <= spec["w_max"])

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
    return rc


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
    #    ⚠️ 자리 계산을 실제로 닫아 둔다 — 처음에 눈대중으로 놨다가 인물이
    #       화면 위로 삐져나가 '정상' 그림이 불합격으로 나왔다. 가짜 그림이
    #       규칙을 어기면 검사기를 시험하는 뜻이 없다.
    #       세로: 위 여백 700 + (900 × 4) + (사이 300 × 3) = 5200 ≤ 4804? 아니다.
    #             → 사람 높이 800, 사이 250 으로: 700 + 800×4 + 250×3 = 4650 ≤ 4804 ✓
    #       가로: 중심 560·1536·2512, 폭 560 → 양끝 여백 280, 사이 간격 416 ✓
    PH, PW, GAPY, TOP = 800, 560, 250, 700
    CX = (560, 1536, 2512)
    good = canvas()
    d = ImageDraw.Draw(good)
    for r in range(4):
        for c in range(3):
            person(d, CX[c], TOP + PH // 2 + r * (PH + GAPY), PW, PH)
    p1 = Path(tempfile.mkdtemp()) / "good.png"
    good.save(p1)

    # ② 인물 위로 회색 막대 (예전 마젠타 선이 하던 짓 그대로)
    #    맨 윗줄 사람들의 **가슴 높이**를 가로지르게 긋는다 — 붙어 버리는 경우다.
    bar = good.copy()
    ymid = TOP + PH // 2
    ImageDraw.Draw(bar).rectangle([100, ymid - 15, 2972, ymid + 15], fill=(120, 120, 120))
    p2 = p1.parent / "bar.png"
    bar.save(p2)

    # ③ 두 사람이 겹쳐 한 덩어리가 됨
    stick = canvas()
    d = ImageDraw.Draw(stick)
    for r in range(4):
        for c in range(3):
            x = CX[c] - (500 if (r, c) == (0, 1) else 0)
            person(d, x, TOP + PH // 2 + r * (PH + GAPY), PW, PH)
    p3 = p1.parent / "stick.png"
    stick.save(p3)

    print("=" * 60)
    print("⭐ 검사기 자기시험 — 가짜 그림 3장으로 이 코드가 맞는지 본다")
    print("=" * 60)
    for name, path, want in (("① 규칙대로 그린 것", p1, 0),
                             ("② 인물 위로 막대를 그은 것", p2, 1),
                             ("③ 두 사람이 붙은 것", p3, 1)):
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
