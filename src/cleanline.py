#!/usr/bin/env python3
"""컷아웃 가장자리에 남은 **검은 칸 선**을 벗겨낸다. 그리고 잘린 머리를 되살린다.

    python3 src/cleanline.py --dry     무엇을 할지만 본다
    python3 src/cleanline.py           실제로 고쳐 저장한다
    python3 src/cleanline.py --only JUDGE,M50A

무엇이 문제였나
    인물 시트의 칸 경계선(검은 줄)이 인물과 함께 딸려 나왔다. 흰 테두리가 그 위에
    둘러지면서 좌·우·아래에 검은 줄이 박힌 채로 남았다.
    앞서 `blackbar.py` 는 **아래쪽 가로 띠**만 처리했다 — 좌우 세로 선은 그대로였다.

옷의 검정과 어떻게 구분하나 — 실측
    칸 선  : (0, 0, 0)          완전한 검정
    남색 양복: (30, 31, 49)
    검은 법복: (39, 35, 42)
    그래서 **가장 밝은 채널이 22 미만**인 것만 선으로 본다. 옷은 절대 걸리지 않는다.

어떻게 벗기나
    가장자리에서 한 겹씩 안으로 들어가며, 그 겹이 완전한 검정이면 지운다.
    검정이 아닌 겹(피부·셔츠·머리카락)을 만나면 즉시 멈춘다.
    그래서 선의 두께만큼만 정확히 벗겨진다.

머리 잘림
    시트를 자를 때 얼굴 컷의 정수리가 평평하게 잘린 것이 있다. 실루엣 맨 윗줄이
    넓으면(둥근 머리가 아니라 일자로 잘렸으면) 잘린 것이다.
    같은 인물의 **상반신 그림에서 얼굴만 오려** 대신 쓴다 — 새로 만들지 않는다.
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import assets_gen as A  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CHAR = ROOT / "assets" / "char"

PURE = 22        # 가장 밝은 채널이 이 값 미만이면 '칸 선' (실측: 옷은 30~49)
MAX_PEEL = 12    # 바깥에서 이만큼까지만 본다. 선은 몇 픽셀이고, 여기까지는
                 # 설령 머리카락을 조금 깎아도 화면에서 보이지 않는다.
BLACK_LINE = 0.60  # 그 줄의 불투명한 점 중 완전한 검정이 이 비율 이상이면 선이다
FLAT_TOP = 0.34  # 맨 윗줄 폭이 최대 폭의 이 비율을 넘으면 머리가 잘린 것


def strip_outline(sp, white_at=238):
    """흰 스티커 테두리를 벗긴다 — 바깥에서 흰색을 타고 들어가며 지운다."""
    pad = 2
    W, H = sp.width + pad * 2, sp.height + pad * 2
    big = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    big.paste(sp, (pad, pad))
    r, g, b = big.convert("RGB").split()
    a = big.getchannel("A")
    near_white = ImageChops.multiply(
        ImageChops.multiply(r.point(lambda v: 255 if v >= white_at else 0),
                            g.point(lambda v: 255 if v >= white_at else 0)),
        b.point(lambda v: 255 if v >= white_at else 0))
    outside = ImageChops.lighter(a.point(lambda v: 255 if v < 128 else 0), near_white)
    ImageDraw.floodfill(outside, (0, 0), 90, thresh=0)
    ring = outside.point(lambda v: 255 if v == 90 else 0)
    keep = ImageChops.subtract(a, ring)
    out = big.copy()
    out.putalpha(keep)
    bb = keep.point(lambda v: 255 if v > 40 else 0).getbbox()
    return out.crop(bb) if bb else out


def peel_black(sp):
    """가장자리에 **직선으로 늘어선** 검은 줄만 벗긴다. → (바뀐 그림, 벗긴 줄 수)

    ⚠️ 처음에는 '가장자리에서 완전한 검정을 한 겹씩 벗기기' 로 했는데,
       검은 곱슬머리가 함께 벗겨져 30겹까지 파고들었다(실측).
       칸 선은 **바깥 끝에서 곧게 뻗은 한 줄**이고 머리카락은 들쭉날쭉하다.
       그래서 바깥 줄(열·행) 단위로만 보고, 그 줄의 불투명한 점 대부분이
       완전한 검정이면서 길게 이어질 때만 지운다."""
    r, g, b = sp.convert("RGB").split()
    pure = ImageChops.multiply(
        ImageChops.multiply(r.point(lambda v: 255 if v < PURE else 0),
                            g.point(lambda v: 255 if v < PURE else 0)),
        b.point(lambda v: 255 if v < PURE else 0))
    a = sp.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    W, H = sp.size
    ap, pp = a.load(), pure.load()

    def line(kind, i):
        """그 줄의 (불투명 점 수, 그중 완전한 검정 수, 이어진 길이)"""
        rng = range(H) if kind in ("L", "R") else range(W)
        on = [j for j in rng if (ap[i, j] if kind in ("L", "R") else ap[j, i])]
        if not on:
            return 0, 0, 0
        blk = sum(1 for j in on
                  if (pp[i, j] if kind in ("L", "R") else pp[j, i]))
        return len(on), blk, on[-1] - on[0] + 1

    # ⚠️ '길게 이어져야 한다' 는 조건을 넣었다가 판사 왼쪽 선을 놓쳤다.
    #    실측: x=2~3 열이 94% 완전검정인데 길이는 그림 높이의 13%뿐이었다
    #    (얼굴 컷이라 법복이 아래 일부에만 있기 때문). 길이 조건을 뺀다.
    #    대신 바깥 12픽셀까지만 본다 — 그 안쪽은 사람이다.
    cut = {"L": 0, "R": 0, "T": 0, "B": 0}
    for kind, idx in (("L", range(W)), ("R", range(W - 1, -1, -1)),
                      ("T", range(H)), ("B", range(H - 1, -1, -1))):
        deepest = 0
        for k, i in enumerate(idx):
            if k >= MAX_PEEL:
                break
            n_on, n_blk, _ = line(kind, i)
            if n_on == 0:
                continue
            if n_blk >= n_on * BLACK_LINE:
                deepest = k + 1          # 여기까지(포함) 지운다
        cut[kind] = deepest

    total = sum(1 for v in cut.values() if v)
    if not any(cut.values()):
        return sp, 0
    keep = Image.new("L", sp.size, 0)
    ImageDraw.Draw(keep).rectangle(
        [cut["L"], cut["T"], W - 1 - cut["R"], H - 1 - cut["B"]], fill=255)
    out = sp.copy()
    out.putalpha(ImageChops.multiply(sp.getchannel("A"), keep))
    trimmed = A.trim_alpha(out)
    return (trimmed if trimmed is not None else out), sum(cut.values())


def head_cut(sp):
    """정수리가 평평하게 잘렸는가. (실루엣 맨 윗줄이 넓으면 잘린 것)"""
    a = sp.getchannel("A").point(lambda v: 255 if v > 150 else 0)
    W, H = a.size
    px = a.load()
    step = max(1, W // 200)
    widths = []
    for y in range(H):
        xs = [x for x in range(0, W, step) if px[x, y]]
        widths.append((max(xs) - min(xs) + step) if xs else 0)
    solid = [w for w in widths if w]
    if not solid:
        return False
    first = next(w for w in widths if w)
    return first > max(solid) * FLAT_TOP


def face_from_bust(code, mood):
    """같은 인물의 상반신에서 얼굴만 오려 온다. 없으면 None."""
    from render import POSE_ALT
    for m in (mood,) + tuple(POSE_ALT.get(mood, ())):
        p = CHAR / code / f"bust_{m}.png"
        if not p.exists():
            continue
        plain = strip_outline(Image.open(p).convert("RGBA"))
        plain, _ = peel_black(plain)
        a = plain.getchannel("A").point(lambda v: 255 if v > 150 else 0)
        W, H = a.size
        px = a.load()
        step = max(1, W // 160)
        widths = []
        for y in range(H):
            xs = [x for x in range(0, W, step) if px[x, y]]
            widths.append((max(xs) - min(xs) + step) if xs else 0)
        solid = [y for y, w in enumerate(widths) if w > W * 0.04]
        if not solid:
            continue
        top, bot = solid[0], solid[-1]
        n = max(4, int((bot - top) * 0.16))
        probe = [w for w in widths[top:top + n] if w]
        head_w = sorted(probe)[len(probe) // 2] if probe else W
        sh = next((y for y in range(top + n, bot + 1) if widths[y] > head_w * 1.55), None)
        cut_at = int(min(H, (sh or int(H * 0.55)) + ((sh or int(H * 0.55)) - top) * 0.22))
        face = A.trim_alpha(plain.crop((0, 0, W, cut_at)))
        if face is not None:
            return face, m
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    files = sorted(CHAR.glob("*/*.png"))
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        files = [f for f in files if f.parent.name in want]

    n_peel = n_head = 0
    for f in files:
        code, pose = f.parent.name, f.stem
        plain = strip_outline(Image.open(f).convert("RGBA"))
        plain, peeled = peel_black(plain)

        rebuilt = None
        if pose.startswith("face_") and head_cut(plain):
            got, used = face_from_bust(code, pose.split("_", 1)[1])
            if got is not None:
                rebuilt = got
                print(f"  {code}/{pose:14} 머리 잘림 → bust_{used} 에서 얼굴을 오려 대신함")
                n_head += 1
        if peeled:
            print(f"  {code}/{pose:14} 검은 선 {peeled}겹 벗김")
            n_peel += 1
        if not peeled and rebuilt is None:
            continue
        if not args.dry:
            A.white_outline(rebuilt if rebuilt is not None else plain).save(f)

    print(f"\n검은 선 {n_peel}장 · 머리 되살림 {n_head}장 (전체 {len(files)}장)"
          + ("   [--dry — 저장하지 않았다]" if args.dry else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
