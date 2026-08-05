#!/usr/bin/env python3
"""인물 컷아웃에서 **뾰족하게 튀어나온 것**을 없앤다.

    python3 src/despike.py                     assets/char 전체를 고친다
    python3 src/despike.py --dry               고치지 않고 몇 개인지만 본다
    python3 src/despike.py --check             검사만 — 남아 있으면 실패로 끝낸다
    python3 src/despike.py --only M50A,M50B

세 가지 일을 한다 (셋 다 원인이 다르다)
    ① despike()         — 옆 사람에게서 딸려온 **가는 기둥 조각**
    ② flatten_bottom()  — 아래가 둥글게 마무리돼 어깨가 나왔다 들어가며 생긴
                          **좌우 삼각형 삐죽이**. 가장 넓은 줄에서 수평으로 자른다.
    ③ drop_fragments()  — 몸에서 **완전히 떨어져 나온 짙은 조각**.
                          테두리색으로 덮고, 불거진 실루엣을 몸 기준으로 되돌린다.

⚠️ ②만으로는 부족했다. ② 를 하고도 손님 화면에 뾰족한 것이 남아 ③ 을 만들었다.
   ③ 의 조각은 **흰 테두리 띠 안쪽**에 들어앉아 있어서, 알파(투명도)만 보면
   몸통과 한 덩어리로 보인다. 흰색을 빼고 봐야 갈라진다.

⚠️ 몇 번을 돌려도 결과가 같아야 한다 — 에셋 만들기·영상 만들기에서 매번 돈다.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
CHAR = ROOT / "assets" / "char"


def _rows(mask):
    """줄마다 (왼끝, 오른끝, 폭). 비어 있으면 (0,0,0)."""
    W, H = mask.size
    px = mask.load()
    out = []
    for y in range(H):
        xs = [x for x in range(W) if px[x, y]]
        out.append((min(xs), max(xs), max(xs) - min(xs) + 1) if xs else (0, 0, 0))
    return out


def shoulder_row(mask):
    """어깨가 시작되는 줄. 못 찾으면 None."""
    rows = _rows(mask)
    W, H = mask.size
    solid = [y for y, r in enumerate(rows) if r[2] > W * 0.04]
    if not solid:
        return None
    top, bot = solid[0], solid[-1]
    n = max(3, int((bot - top) * 0.16))
    probe = [rows[y][2] for y in range(top, min(H, top + n)) if rows[y][2]]
    if not probe:
        return None
    head_w = sorted(probe)[len(probe) // 2]
    for y in range(top + n, bot + 1):
        if rows[y][2] > head_w * 1.55:
            return y
    return None


def _components(mask, min_area):
    W, H = mask.size
    px = mask.load()
    seen = bytearray(W * H)
    out = []
    for sy in range(H):
        for sx in range(W):
            if seen[sy * W + sx] or px[sx, sy] < 128:
                continue
            stack = [(sx, sy)]
            pts = [sy * W + sx]
            seen[sy * W + sx] = 1
            while stack:
                x, y = stack.pop()
                for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if 0 <= nx < W and 0 <= ny < H and not seen[ny * W + nx] \
                            and px[nx, ny] >= 128:
                        seen[ny * W + nx] = 1
                        pts.append(ny * W + nx)
                        stack.append((nx, ny))
            if len(pts) >= min_area:
                out.append(pts)
    return out


def _runs(px, y, W):
    """한 줄에서 불투명한 구간들을 (시작, 끝) 으로 돌려준다."""
    out, st = [], None
    for x in range(W):
        on = px[x, y] >= 128
        if on and st is None:
            st = x
        elif not on and st is not None:
            out.append((st, x - 1)); st = None
    if st is not None:
        out.append((st, W - 1))
    return out


def despike(sp, scale=4, thin=25, back=29):
    """인물 옆에 남은 **칸 테두리 조각**(세로 기둥 + 아래 가로줄)을 지운다.

    ⚠️ 세 번 헛짚었다. 기록해 둔다.
       ① '어깨선 위쪽의 다른 덩어리' → 0장. 조각은 바닥부터 어깨까지 서 있다.
       ② '가장 큰 덩어리만 남기기' → 0장. 흰 테두리가 조각과 몸통을 이어 붙여 놓았다.
       ③ '가슴 높이에서 좌우 좁은 구간 잘라내기' → 0장. 아래쪽에서 조각과 몸통의
          x 범위가 겹쳐(자켓 아랫단과 같은 자리) 잘라내면 몸까지 잘린다.
    실제로 남은 것은 **가늘다**. 굵은 것만 남기고(깎았다 부풀리기) 그중 가장 큰 덩어리를
    고른 뒤, 그 둘레만큼만 되살리면 가는 조각은 돌아오지 않는다.
    목처럼 가는 부분은 조각보다 굵어서 살아남는다."""
    a = sp.getchannel("A")
    solid = a.point(lambda v: 255 if v > 128 else 0)
    sw, sh_ = max(1, sp.width // scale), max(1, sp.height // scale)
    small = solid.resize((sw, sh_), Image.BILINEAR).point(lambda v: 255 if v > 110 else 0)

    thick = small.filter(ImageFilter.MinFilter(thin)).filter(ImageFilter.MaxFilter(thin))
    comps = _components(thick, min_area=max(6, (sw * sh_) // 900))
    if not comps:
        return sp, 0
    comps.sort(key=len, reverse=True)

    buf = bytearray(sw * sh_)
    for i in comps[0]:
        buf[i] = 255
    core = Image.frombytes("L", (sw, sh_), bytes(buf)).filter(ImageFilter.MaxFilter(back))
    keep = core.resize(sp.size, Image.BILINEAR).point(lambda v: 255 if v > 90 else 0)
    keep = keep.filter(ImageFilter.GaussianBlur(2))

    before = sum(solid.histogram()[128:])
    out = sp.copy()
    out.putalpha(ImageChops.multiply(a, keep))
    after = sum(out.getchannel("A").point(lambda v: 255 if v > 128 else 0).histogram()[128:])
    if before and (before - after) / before < 0.004:      # 실질적으로 안 지워졌다
        return sp, 0
    bb = out.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
    return (out.crop(bb) if bb else out), max(1, len(comps) - 1)


# ── 어깨 좌우로 삐죽 튀어나온 것 ────────────────────────────
BOTTOM_ZONE = 0.30      # 아래 30% 안에서 '가장 넓은 줄' 을 찾는다
MAX_TRIM = 0.15         # 그래도 키의 15% 넘게는 자르지 않는다 (몸이 뭉텅 날아가면 안 된다)
MIN_BULGE = 0.03        # 폭 대비 3% 넘게 들어갔을 때만 손댄다


def _row_span(mask, y, W):
    """그 줄의 (왼끝, 오른끝, 폭). 비어 있으면 (0, 0, 0).

    한 줄씩 잘라 getbbox 를 쓴다 — 파이썬으로 픽셀을 하나씩 도는 것보다 훨씬 빠르다."""
    bb = mask.crop((0, y, W, y + 1)).getbbox()
    return (bb[0], bb[2] - 1, bb[2] - bb[0]) if bb else (0, 0, 0)


def flatten_bottom(sp):
    """어깨가 **불룩 나왔다가 다시 좁아지며** 생기는 좌우 삐죽이를 없앤다.

    무엇이 문제였나
        상반신(bust·face) 그림은 가슴께에서 끊긴 컷아웃이라, 아래로 갈수록
        어깨가 가장 넓은 채로 화면 밖으로 나가야 한다. 그런데 AI 가 만든 그림은
        아래를 **둥글게 마무리**해 놓았다 — 어깨에서 제일 넓어졌다가 바닥으로
        갈수록 다시 좁아진다. 거기에 흰 테두리가 둘러지면서 좌우 맨 끝이
        **뾰족한 삼각형**으로 튀어나와 보인다. 실측: 38장 중 29장이 그랬다.

    어떻게 없애나
        아래쪽에서 **가장 넓은 줄을 찾아 거기서 수평으로 자른다.**
        그러면 그 줄이 곧 바닥이 되어 어깨가 제일 넓은 채로 끝난다 —
        나왔다 들어가는 자리가 아예 없어지므로 삐죽이도 없다.
        **지우기만 하고 없는 픽셀을 지어내지 않는다.**

    ⚠️ 전신(full_*)에는 쓰지 않는다. 전신은 팔이 가장 넓고 발이 좁은 것이
       당연해서, 같은 규칙을 대면 **다리가 잘린다.** (부르는 쪽에서 거른다)"""
    a = sp.getchannel("A")
    W, H = sp.size
    mask = a.point(lambda v: 255 if v > 40 else 0)
    bb = mask.getbbox()
    if not bb:
        return sp, 0
    top, bot = bb[1], bb[3] - 1
    ink = bot - top
    if ink < 40:
        return sp, 0

    lo = max(top, bot - int(ink * BOTTOM_ZONE))
    span = {y: _row_span(mask, y, W) for y in range(lo, bot + 1)}
    zone = [y for y, s in span.items() if s[2]]
    if not zone:
        return sp, 0
    wy = max(zone, key=lambda y: span[y][2])
    if (span[wy][2] - span[bot][2]) / W <= MIN_BULGE:
        return sp, 0                      # 이미 아래로 갈수록 넓다 — 손댈 것 없다

    # ⚠️ 너무 많이 잘려야 한다면 **아예 손대지 않는다.** 두 가지 이유다.
    #    ① 그런 그림은 얼굴만 딴 컷이라, 제일 넓은 곳이 어깨가 아니라 **머리카락**이다.
    #       거기서 자르면 턱과 목이 날아간다 (실측: F50A/face_anger).
    #    ② 조금씩 잘라 두면 이 스크립트를 다시 돌릴 때마다 또 잘린다.
    #       에셋 만들기에서 매번 도는 스크립트라 **몇 번을 돌려도 결과가 같아야** 한다.
    if bot - wy > ink * MAX_TRIM:
        return sp, 0

    out = sp.crop((0, 0, W, wy + 1))
    nb = out.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
    return (out.crop(nb) if nb else out), bot - wy


# ── 몸에서 떨어져 나온 조각 ────────────────────────────────
FRAG_MAX = 0.02         # 몸통 넓이의 2% 아래면 '조각' 이다
FRAG_MIN_PX = 60        # 이보다 작은 티끌은 어차피 눈에 안 보인다
OUTLINE_R = 0.032       # 흰 테두리 두께(키 대비). render.CHAR_OUTLINE 과 맞춘다


def _content_mask(sp):
    """흰 테두리를 뺀 **알맹이**만 남긴 마스크.

    테두리가 조각과 몸통을 하얗게 이어 붙여 놓기 때문에, 알파(투명도)만 보면
    둘이 한 덩어리로 보인다. 흰색을 빼야 비로소 따로 떨어진 것이 드러난다."""
    r, g, b, a = sp.split()
    white = ImageChops.multiply(
        ImageChops.multiply(r.point(lambda v: 255 if v > 200 else 0),
                            g.point(lambda v: 255 if v > 200 else 0)),
        b.point(lambda v: 255 if v > 200 else 0))
    return ImageChops.subtract(a.point(lambda v: 255 if v > 128 else 0), white)


def _dilate(mask, radius):
    """마스크를 radius 만큼 **둥글게** 부풀린다.

    ⚠️ MaxFilter(정사각형)로 부풀리면 모서리가 각져서, 잘린 자리가 네모나게
       파여 보인다(실제로 그렇게 나와서 다시 만들었다). 흐림 + 문턱값이면
       둥글게 퍼져 어깨선과 나란한 매끈한 곡선이 된다."""
    return mask.filter(ImageFilter.GaussianBlur(radius * 0.62)) \
               .point(lambda v: 255 if v > 8 else 0)


def _outline_px(sp):
    """이 그림의 **흰 테두리 두께**를 직접 잰다 (픽셀).

    ⚠️ 코드에 박아 두면 안 된다. 실측해 보니 그림마다 다르고, 짐작했던 3% 가
       아니라 **7%(70픽셀)** 였다. 짐작으로 잘랐다가 테두리를 통째로 깎아
       11만 픽셀이 날아간 적이 있다. 그래서 매번 잰다.
    줄마다 '알파 끝 ~ 알맹이 끝' 거리를 재고 **가장 작은 값**들을 쓴다 —
    옆선이 비스듬한 줄은 실제보다 크게 나오므로, 가장 곧은 줄이 참값에 가깝다."""
    W, H = sp.size
    a = sp.getchannel("A").point(lambda v: 255 if v > 40 else 0)
    c = _content_mask(sp)
    gaps = []
    for y in range(H // 8, H - H // 12, max(1, H // 60)):
        ab = a.crop((0, y, W, y + 1)).getbbox()
        cb = c.crop((0, y, W, y + 1)).getbbox()
        if ab and cb:
            gaps += [cb[0] - ab[0], ab[2] - cb[2]]
    gaps = sorted(g for g in gaps if g > 0)
    if not gaps:
        return max(4, round(H * 0.03))
    return max(4, gaps[len(gaps) // 5])          # 아래쪽 20% 지점 값


def drop_fragments(sp):
    """몸에서 **떨어져 나온 조각**과 그 조각만 감싼 흰 테두리를 함께 지운다.

    무엇이 문제였나
        손님이 동그라미 쳐 보낸 것이 이것이다. 어깨를 수평으로 잘라 큰 삐죽이를
        없앤 뒤에도 **뾰족한 것이 남아** 있었다. 실측해 보니 M50B/bust_neutral
        왼쪽 아래에 **가로 14 · 세로 51 픽셀짜리 짙은 조각**이, 몸(x≥96)과 완전히
        떨어진 자리(x≤79)에 박혀 있었다. 인물 시트에서 옆 사람 옷자락이 딸려온 것이다.

    왜 지금까지 못 잡았나
        알파(투명도)만 보면 못 찾는다. **흰 테두리가 조각과 몸통을 이어 붙여**
        한 덩어리로 만들어 놓기 때문이다. 흰색을 빼고 봐야 비로소 갈라진다.
        기존 despike() 가 세 번 헛짚은 것도 같은 이유였다.

    어떻게 없애나
        ① 흰색을 뺀 알맹이만 남겨 덩어리를 센다 → 가장 큰 것이 몸통
        ② 몸통 넓이의 2% 도 안 되는 덩어리가 있으면 그것이 조각이다
        ③ 조각을 **테두리와 같은 흰색으로 덮는다** → 짙은 뾰족이가 사라진다
        ④ 알파를 **몸통에서 테두리 두께만큼 부풀린 자리**로 제한한다
           → 조각 때문에 밖으로 불거졌던 하얀 혹도 같이 없어진다

    ⚠️ 지우기만 해서는 안 된다. 테두리 두께를 재 보니 **70픽셀(키의 7%)** 이라,
       조각(몸에서 17픽셀 거리)은 **테두리 띠 안쪽**에 들어앉아 있었다.
       그래서 '조각 주변을 오려낸다' 는 방법은 통하지 않는다 — 덮어야 한다.
       (오려냈더니 실루엣이 네모나게 파여서 다시 만들었다.)

    한 번 덮으면 조각이 사라지므로 다시 돌려도 더 할 일이 없다(같은 결과)."""
    W, H = sp.size
    comps = _components(_content_mask(sp), min_area=FRAG_MIN_PX)
    if len(comps) < 2:
        return sp, 0
    comps.sort(key=len, reverse=True)
    frags = [c for c in comps[1:] if len(c) < len(comps[0]) * FRAG_MAX]
    if not frags:
        return sp, 0

    fbuf, bbuf = bytearray(W * H), bytearray(W * H)
    for c in frags:
        for i in c:
            fbuf[i] = 255
    for i in comps[0]:
        bbuf[i] = 255
    frag = Image.frombytes("L", (W, H), bytes(fbuf))
    bod = Image.frombytes("L", (W, H), bytes(bbuf))

    out = sp.copy()
    # ③ 조각을 테두리색으로 덮는다. 조금 넉넉히 덮어야 가장자리 어두운 테가 안 남는다.
    paint = _dilate(frag, max(3, round(H * 0.006)))
    out.paste(Image.new("RGBA", sp.size, (255, 255, 255, 255)), (0, 0), paint)
    out.putalpha(sp.getchannel("A"))

    # ④ 몸통을 테두리 두께만큼 부풀린 자리까지만 남긴다 (실측 두께 × 여유)
    keep = _dilate(bod, round(_outline_px(sp) * 1.25))
    out.putalpha(ImageChops.darker(out.getchannel("A"), keep))

    bb = out.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
    return (out.crop(bb) if bb else out), sum(len(c) for c in frags)


# ── 남은 뾰족이를 곡선으로 다듬기 ──────────────────────────
SMOOTH_R = 0.30         # 테두리 두께 대비 다듬는 반지름
SMOOTH_MIN = 200        # 이만큼도 안 깎이면 손대지 않은 것으로 본다


def smooth_edge(sp):
    """실루엣에 남은 **가는 뾰족이를 깎아 곡선으로** 만든다. 값이 들지 않는다.

    왜 안전한가 (이 함수의 근거)
        이 그림들의 실루엣은 **몸을 흰 테두리로 60~70픽셀 부풀린 모양**이다.
        그러니 실루엣에는 원래 **가는 부분이 있을 수 없다** — 머리카락 한 올도
        손가락도 그 두꺼운 테두리 안에 들어 있어 겉모양은 통통하다.
        따라서 테두리 두께의 3할(약 20픽셀)보다 가는 돌기는 **무조건 잘못 붙은 것**이다.
        그것만 깎으므로 사람 몸은 건드리지 않는다.

    어떻게
        '열기(opening)' — 깎았다가 같은 만큼 다시 부풀린다. 가는 돌기는 깎이는
        단계에서 끊어져 돌아오지 못하고, 두꺼운 몸통은 그대로 돌아온다.
        마지막에 원래 알파와 **겹치는 부분만** 남기므로 **없던 살이 붙지 않는다.**"""
    a = sp.getchannel("A")
    W, H = sp.size
    solid = a.point(lambda v: 255 if v > 40 else 0)
    r = max(3, round(_outline_px(sp) * SMOOTH_R))

    s = 4
    sw, sh = max(1, W // s), max(1, H // s)
    k = max(3, (r // s) * 2 + 1)
    small = solid.resize((sw, sh), Image.BILINEAR).point(lambda v: 255 if v > 110 else 0)
    opened = small.filter(ImageFilter.MinFilter(k)).filter(ImageFilter.MaxFilter(k))
    keep = opened.resize((W, H), Image.BILINEAR).point(lambda v: 255 if v > 90 else 0)
    keep = keep.filter(ImageFilter.GaussianBlur(max(1, r * 0.2)))   # 계단 자국을 눕힌다

    cut = ImageChops.subtract(solid, keep.point(lambda v: 255 if v > 40 else 0))
    n = sum(i * c for i, c in enumerate(cut.histogram())) // 255
    if n < SMOOTH_MIN:
        return sp, 0

    out = sp.copy()
    out.putalpha(ImageChops.darker(a, keep))
    bb = out.getchannel("A").point(lambda v: 255 if v > 20 else 0).getbbox()
    return (out.crop(bb) if bb else out), n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="지우지 않고 확인만")
    ap.add_argument("--only", default="", help="이 인물만 (쉼표로 구분)")
    # ⭐ 예방조치: 만들기 전에 한 번 더 확인하는 자리에서 쓴다.
    #    남은 것이 있으면 **실패로 끝내** 삐죽이가 영상까지 가지 못하게 막는다.
    ap.add_argument("--check", action="store_true",
                    help="고치지 않고 검사만 — 남은 것이 있으면 실패로 끝낸다")
    args = ap.parse_args()
    if args.check:
        args.dry = True

    files = sorted(CHAR.glob("*/*.png"))
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        files = [f for f in files if f.parent.name in want]

    total = flat = frag = smooth = 0
    for f in files:
        sp = Image.open(f).convert("RGBA")
        out, n = despike(sp)
        if n:
            total += 1
            print(f"  {f.parent.name}/{f.stem:14} 조각 {n}개 제거  {sp.size} → {out.size}")

        # ⭐ 전신(full_*)은 건드리지 않는다 — 팔이 넓고 발이 좁은 것이 정상이라
        #    같은 규칙을 대면 다리가 잘린다.
        if not f.name.startswith("full"):
            out2, cut = flatten_bottom(out)
            if cut:
                flat += 1
                print(f"  {f.parent.name}/{f.stem:14} 어깨 삐죽이 — 아래 {cut}줄 잘라냄"
                      f"  {out.size} → {out2.size}")
                out = out2

        # ⭐ 몸에서 떨어져 나온 짙은 조각 — 손님이 동그라미 쳐 보낸 바로 그것.
        #    전신에도 생기므로 포즈를 가리지 않고 본다.
        #
        #    ⚠️ **한 번으로 끝나지 않는다.** 큰 조각을 덮고 나면 그 뒤에 가려 있던
        #       작은 조각이 새로 드러난다(실측: 1회차 23장 → 2회차 1장 → 3회차 0장).
        #       한 번만 돌리면 남은 것이 그대로 영상까지 간다. 여기서 다 털어낸다.
        npx = 0
        for _ in range(4):
            out3, k = drop_fragments(out)
            if not k:
                break
            npx += k
            out = out3
        if npx:
            frag += 1
            print(f"  {f.parent.name}/{f.stem:14} 떨어져 나온 조각 {npx}px 덮음"
                  f"  {sp.size} → {out.size}")

        # ⭐ 마지막으로 남은 가는 뾰족이를 곡선으로 다듬는다 (값 0원).
        #    앞의 세 가지가 못 잡은 모양이 있어도 여기서 둥글게 눕힌다.
        out4, sn = smooth_edge(out)
        if sn:
            smooth += 1
            print(f"  {f.parent.name}/{f.stem:14} 뾰족이 {sn}px 를 곡선으로 다듬음")
            out = out4

        if (out.size != sp.size or out.tobytes() != sp.tobytes()) and not args.dry:
            out.save(f)

    print(f"\n어깨 조각 {total}장 · 어깨 삐죽이 {flat}장 · 떨어져 나온 조각 {frag}장"
          f" · 곡선 다듬기 {smooth}장 (전체 {len(files)}장)"
          + ("   [--dry — 저장하지 않았다]" if args.dry else ""))
    if args.check and (total or flat or frag or smooth):
        print("\n::error::인물 그림에 삐죽이·조각이 남아 있습니다."
              " `python3 src/despike.py` 를 돌려 고친 뒤 다시 시도하십시오.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
