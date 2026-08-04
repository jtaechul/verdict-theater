#!/usr/bin/env python3
"""썸네일 만들기 — 대본에서 글자와 인물을 뽑아 **한 장** 만든다.

    python3 src/thumb.py data/scripts/EP001.json --out build/thumb.jpg

왜 필요한가
    썸네일은 조회수의 절반이다. 그런데 지금까지 **만드는 길이 아예 없었다.**
    `tools/thumb_mock.py` 는 EP001 의 글자·인물이 코드에 박혀 있는 시안이라
    회차가 바뀌면 손으로 고쳐야 했다. 손님은 폰만 쓰므로 손으로 고칠 수 없다.
    이 파일은 **대본만 있으면 회차가 뭐든 알아서** 만든다.

참고 채널 6곳의 썸네일에서 읽어낸 문법 (전부 지킨다)
    · 큰 글씨가 **화면 폭의 90%를 꽉 채운다.** 이것이 가장 큰 차이였다 —
      예전 시안은 55% 라 폰에서 작고 얌전해 보였다.
    · 테두리를 **아주 두껍게.** 글자 굵기의 20% 이상.
    · 인물마다 **노란 딱지**를 바로 옆에 붙인다 — (장남) (어머니).
      누가 누구인지 0.5초 안에 알아야 한다.
    · 인물은 둘, **표정이 대비**되게.

우리만의 차별점
    참고 채널들은 '막장 상황' 을 판다. 우리는 **"그래서 얼마를 물어냈나"** 를 판다.
    큰 줄에 반드시 **금액**이 들어간다. 그래서 대본의 `amount` 그래픽을 그대로 쓴다.

유튜브 규격
    1280×720 · JPEG · **2MB 이하** (유튜브 상한). 넘으면 품질을 낮춰 다시 저장한다.
"""

import argparse
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
BATANG = ROOT / "assets/fonts/KoPub_Batang_Pro_Bold.otf"

W, H = 1280, 720
MAX_BYTES = 2 * 1024 * 1024          # 유튜브 썸네일 상한

INK = (10, 11, 16)
YELLOW = (255, 216, 64)
BORDER = 11
FADE_FROM = 430                      # 이 줄부터 어두워지기 시작 (얼굴 아래)
FADE_TO = 572                        # 여기부터는 완전히 어둡다 — 인물 아래 단면이 잠긴다

# 큰 줄에 쓸 표정 — 돈을 토해낸 쪽은 놀라고, 받은 쪽은 운다.
# 대본이 어떤 인물을 쓰든 이 순서로 고른다.
FACE_LOSER = ("face_shock", "face_anger", "face_cold", "bust_shock", "bust_anger")
FACE_WINNER = ("face_cry", "face_sad", "bust_sad", "face_shock")


def font(size):
    return ImageFont.truetype(str(BATANG), size)


def fit(text, target_w, lo=40, hi=190):
    """글자가 target_w 를 꽉 채우는 크기를 찾는다. 참고 이미지의 핵심."""
    best = lo
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    while lo <= hi:
        mid = (lo + hi) // 2
        if d.textlength(text, font=font(mid)) <= target_w:
            best, lo = mid, mid + 1
        else:
            hi = mid - 1
    return font(best)


def backdrop(code):
    p = ROOT / f"assets/bg/{code}.jpg"
    if p.exists():
        bg = Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(11))
    else:
        bg = Image.new("RGB", (W, H), (30, 32, 40))
    return Image.blend(bg, Image.new("RGB", (W, H), INK), 0.42).convert("RGBA")


def person(base, code, poses, height, cx, bottom):
    """인물 한 명. bottom > H 면 아래 잘린 단면이 화면 밖으로 나간다.

    포즈는 **여러 개를 후보로 받아** 실제로 있는 첫 번째를 쓴다 —
    회차마다 대본이 쓰는 포즈가 달라서, 하나로 못 박으면 그림이 빈다."""
    for pose in poses:
        p = ROOT / f"assets/char/{code}/{pose}.png"
        if not p.exists():
            continue
        im = Image.open(p).convert("RGBA")
        box = im.getchannel("A").getbbox()
        if box:
            im = im.crop(box)
        r = height / im.height
        im = im.resize((round(im.width * r), round(height)), Image.LANCZOS)
        base.alpha_composite(im, (round(cx - im.width / 2), round(bottom - im.height)))
        return True
    return False


def tag(d, text, cx, y):
    """인물 옆 노란 딱지 — (장남) (어머니)."""
    f = font(52)
    t = f"({text})"
    d.text((cx - d.textlength(t, font=f) / 2, y), t, font=f,
           fill=YELLOW, stroke_width=11, stroke_fill=INK)


def darken_bottom(base):
    """얼굴 아래를 어둡게 깔아 글자를 세운다. 인물의 잘린 단면도 여기 잠긴다."""
    grad = Image.new("L", (1, H), 0)
    px = grad.load()
    for y in range(H):
        if y < FADE_FROM:
            px[0, y] = 0
        elif y >= FADE_TO:
            px[0, y] = 235
        else:
            px[0, y] = round(235 * (y - FADE_FROM) / (FADE_TO - FADE_FROM))
    shade = Image.new("RGBA", (W, H), INK + (255,))
    shade.putalpha(grad.resize((W, H)))
    return Image.alpha_composite(base, shade)


# ── 대본에서 재료를 뽑는다 ───────────────────────────────
def money_line(doc):
    """큰 줄 — **금액**. 이 채널이 파는 것이다.

    대본의 `amount` 그래픽을 그대로 쓴다. 회차마다 딱 한 번 나오도록 되어 있어
    (validate_script.MAX_AMOUNT_GFX) 고르는 데 헷갈릴 일이 없다."""
    for act in doc.get("acts", []):
        for cut in act.get("cuts", []):
            g = cut.get("gfx") or {}
            if g.get("type") == "amount" and g.get("value"):
                return f"{g['value']} 토해냈다"
    used = (doc.get("anonymization", {}) or {}).get("amounts_used") or []
    if used:
        return f"{used[0].get('value')} 토해냈다"
    return "법원이 판단했습니다"


def hook_line(doc, variant=0):
    """작은 줄 — 상황. 제목 후보에서 고른다.

    ⭐ `variant` 는 **'다시 만들기' 버튼**을 위한 것이다. 같은 그림만 다시 나오면
       버튼이 아무 소용이 없다. 대본은 제목 후보를 3개 들고 있으므로
       그중 어느 것을 쓸지 돌려 가며 고른다 — 문구가 바뀌면 인상이 크게 달라진다.
    짧은 것부터 쓴다. 길면 글씨가 작아져 폰에서 안 읽힌다."""
    cands = [t for t in (doc.get("meta", {}).get("title_candidates") or []) if t]
    if cands:
        cands = sorted(cands, key=len)
        return cands[variant % len(cands)]
    return (doc.get("meta", {}).get("logline") or "")[:24]


def cast(doc):
    """세울 인물 둘 — (진 쪽, 이긴 쪽). 없으면 있는 대로.

    누가 졌는지는 대본이 따로 적지 않는다. 그래서 **말을 가장 많이 한 인물**을
    사건의 중심으로 보고, 그 사람과 상대(가장 많이 말한 다른 인물)를 세운다.
    상속 사건은 거의 언제나 '요구한 쪽 vs 지킨 쪽' 구도라 이것으로 맞는다."""
    from collections import Counter
    n = Counter()
    for act in doc.get("acts", []):
        for cut in act.get("cuts", []):
            sp = cut.get("speaker") or ""
            if sp.startswith("v_") and sp != "v_JUDGE" and (cut.get("text") or "").strip():
                n[sp[2:]] += 1
    role = {c.get("code"): (c.get("role") or c.get("name") or "")
            for c in (doc.get("characters") or [])}
    top = [c for c, _k in n.most_common() if c in role][:2]
    if len(top) < 2:                      # 대사가 한 명뿐 — 명단에서 채운다
        for c in role:
            if c not in top and c != "JUDGE":
                top.append(c)
            if len(top) == 2:
                break
    return [(c, role.get(c, "")) for c in top[:2]]


def court_bg(doc):
    """법정 배경을 고른다. 판결 컷(4막)이 쓰는 배경이 가장 어울린다."""
    for act in doc.get("acts", []):
        if act.get("id") != "act4":
            continue
        for cut in act.get("cuts", []):
            if cut.get("bg"):
                return cut["bg"]
    for act in doc.get("acts", []):
        for cut in act.get("cuts", []):
            if str(cut.get("bg", "")).startswith("court"):
                return cut["bg"]
    return "court_hall"


def build(doc, variant=0):
    base = backdrop(court_bg(doc))
    people = cast(doc)
    # 왼쪽 = 이긴 쪽(운다) · 오른쪽 = 진 쪽(놀란다). 표정이 대비돼야 눈에 걸린다.
    spots = [(320, 648, 640, FACE_WINNER), (960, 656, 680, FACE_LOSER)]
    placed = []
    for (code, name), (cx, bottom, height, poses) in zip(people, spots):
        if person(base, code, poses, height, cx, bottom):
            placed.append((name, cx))

    base = darken_bottom(base)
    d = ImageDraw.Draw(base)
    for name, cx in placed:
        tag(d, name, cx, 18)

    inner = round(W * 0.90)
    small, big = hook_line(doc, variant), money_line(doc)
    fs = fit(small, round(inner * 0.72), 30, 62)
    fb = fit(big, inner, 60, 128)
    ys = 470
    d.text((W / 2 - d.textlength(small, font=fs) / 2, ys), small, font=fs,
           fill=(226, 222, 214), stroke_width=8, stroke_fill=INK)
    yb = ys + fs.size + 22
    d.text((W / 2 - d.textlength(big, font=fb) / 2, yb), big, font=fb,
           fill=(255, 255, 255), stroke_width=round(fb.size * 0.20), stroke_fill=INK)

    # 채널 딱지
    fc = font(26)
    t = "판결극장"
    tw = d.textlength(t, font=fc)
    d.rectangle([W - tw - 46, 16, W - 16, 16 + 40], fill=INK + (235,))
    d.text((W - tw - 31, 22), t, font=fc, fill=(236, 232, 224))

    d.rectangle([0, 0, W - 1, H - 1], outline=INK, width=BORDER)
    return base.convert("RGB")


def save(img, path):
    """유튜브 상한(2MB) 안에 들어가게 저장한다. 넘으면 품질을 낮춰 다시 시도."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for q in (92, 86, 80, 72, 64):
        img.save(path, "JPEG", quality=q, optimize=True, progressive=True)
        if path.stat().st_size <= MAX_BYTES:
            return q
    return q


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--out", default="build/thumb.jpg")
    ap.add_argument("--variant", type=int, default=0,
                    help="문구 고르기 (0·1·2). '다시 만들기' 가 바꿔 부른다")
    a = ap.parse_args()
    if not BATANG.exists():
        print(f"❌ 바탕체 폰트가 없다: {BATANG}", file=sys.stderr)
        return 1
    doc = json.loads(Path(a.script).read_text(encoding="utf-8"))
    img = build(doc, a.variant)
    q = save(img, a.out)
    p = Path(a.out)
    print(f"썸네일 → {p}  {W}x{H}  {p.stat().st_size / 1024:.0f}KB (품질 {q})")
    print(f"  작은 줄: {hook_line(doc, a.variant)}  (문구 {a.variant})")
    print(f"  큰 줄  : {money_line(doc)}")
    print(f"  인물   : {', '.join(f'{c}({r})' for c, r in cast(doc))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
