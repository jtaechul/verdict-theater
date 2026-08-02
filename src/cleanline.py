#!/usr/bin/env python3
"""컷아웃 가장자리에 남은 **검은 칸 선**을 벗겨낸다. 그리고 잘린 머리를 되살린다.

    python3 src/cleanline.py --dry     무엇을 할지만 본다
    python3 src/cleanline.py           실제로 고쳐 저장한다
    python3 src/cleanline.py --only JUDGE,M50A

무엇이 문제였나
    인물 시트의 칸 경계선(검은 줄)이 인물과 함께 딸려 나왔다. 흰 테두리가 그 위에
    둘러지면서 좌·우·아래에 검은 줄이 박힌 채로 남았다.
    앞서 `blackbar.py` 는 **아래쪽 가로 띠**만 처리했다 — 좌우 세로 선은 그대로였다.

칸 선은 이렇게 생겼다 — 실측 (이정임 face_sad, 흰 테두리를 벗긴 뒤 아래에서 위로)
    아래 11겹 : 폭 7px 짜리 **가시** (순검정)
    그 위 1겹 : 밝은 실오라기
    그 위  6겹 : **폭 710/841 이 98~100% 순검정** ← 이것이 칸 선
    그 아래    : 옷 (순검정 비율 0.8~8%)

어떻게 가르나 — **밝기만으로는 절대 못 가른다**
    니트·법복도 골 사이가 새까맣다. 밝기로만 지우면 옷이 갉아먹힌다(실제로 겪었다).
    그래서 **모양**으로 가른다 — ① 실루엣을 가로지를 것(가장 넓은 줄의 절반 이상)
    ② 그 줄의 95% 이상이 순검정일 것 ③ 얇을 것.
    구두(폭의 28%)·법복(가장 밝은 채널 42 라 순검정 아님)은 걸리지 않는다.
    바깥 12겹은 가시라 폭이 1% 뿐 — **건너뛰고 안쪽까지 봐야** 진짜 선을 만난다.

두 번 돌려도 안전하다
    지우고 나면 그 자리에 옷(순검정 아님)이 드러나므로 다음 번에는 아무것도 안 지운다.
    실측으로 확인했다 — 두 번째 실행 0장.

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

PURE = 22          # 가장 밝은 채널이 이 값 미만이면 순검정 (실측: 옷은 30~49)
MAX_PEEL = 30      # 바깥에서 이만큼까지만 본다 (실측: 가시 11겹 + 선 6겹이라 12로는 모자랐다)
LINE_SPAN = 0.50   # 실루엣에서 가장 넓은 줄의 이 비율은 넘어야 '가로지르는 선'
LINE_BLACK = 0.95  # 그 줄의 이 비율 이상이 순검정이어야 선 (실측: 선 98~100% · 옷 0.8~8%)
LINE_MAX_THICK = 12  # 이보다 두꺼우면 선이 아니라 검은 옷이다
FLAT_TOP = 0.34  # 맨 윗줄 폭이 최대 폭의 이 비율을 넘으면 머리가 잘린 것
CHIN_AT = 0.55   # 되살린 얼굴에서 턱이 와야 할 높이 비율 (아래에 가슴이 남도록)


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
    """실루엣에 붙어 있는 **얇은 검정**(칸 선)만 지운다. → (바뀐 그림, 지운 점 수)

    ⚠️ 앞서 두 가지 방법이 다 틀렸다.
       ① 가장자리에서 완전검정을 한 겹씩 벗기기 → 검은 곱슬머리를 30겹까지 먹었다.
       ② 바깥 줄(행·열) 단위로 보고 12줄까지만 벗기기 → **거의 다 놓쳤다.**
          실측: 이정임 7장에 아직 선이 남아 있었다. 칸 선은 반듯한 가로줄이 아니라
          실루엣 밖으로 삐져나온 **얇은 조각**이라(폭 1px 짜리 가시도 있었다)
          '한 줄이 통째로 검다' 는 가정 자체가 틀렸다.

    ⚠️ ③ '검정을 타고 흘러 들어가며 얇은 것만 지우기' 도 해 봤는데 **옷을 갉아먹었다.**
          니트·법복의 골 사이가 28 보다 어두워서 실오라기처럼 이어졌기 때문이다.
          밝기만으로는 칸 선과 검은 옷을 절대 가를 수 없다.

    지금 방식 — 실측한 **모양**으로 가른다.
       테두리를 벗기고 아래에서 위로 재어 보니 이렇게 생겼다(이정임 face_sad):
         아래 11겹 : 폭 7px 짜리 **가시** (순검정)
         그 위 1겹 : 밝은 실오라기
         그 위 6겹 : **폭 710/841 이 98~100% 순검정** ← 이게 칸 선이다
         그 아래   : 옷 (순검정 비율 0.8~8%)
       그래서 조건은 셋이다 — ① 실루엣 폭을 가로지를 것(가장 넓은 줄의 절반 이상)
       ② 그 줄의 95% 이상이 순검정일 것 ③ 얇을 것.
       구두·법복은 ①이나 ②에서 걸러진다 (실측: 뒷모습 구두는 폭의 28%,
       법복은 가장 밝은 채널이 42 라 순검정이 아니다).
       ⚠️ 가시 때문에 바깥 12겹은 폭이 1% 밖에 안 된다 — 거기서 멈추면 안 되고
          **건너뛰고 계속 안쪽을 봐야** 진짜 선을 만난다. 예전 코드가 여기서 멈췄다."""
    r, g, b = sp.convert("RGB").split()
    pure = ImageChops.multiply(
        ImageChops.multiply(r.point(lambda v: 255 if v < PURE else 0),
                            g.point(lambda v: 255 if v < PURE else 0)),
        b.point(lambda v: 255 if v < PURE else 0))
    a = sp.getchannel("A").point(lambda v: 255 if v > 128 else 0)
    W, H = sp.size
    ap, pp = a.load(), pure.load()

    def scan(kind, i):
        """그 줄의 (불투명 점 수, 그중 순검정 수)"""
        if kind in ("L", "R"):
            on = [j for j in range(H) if ap[i, j]]
            return len(on), sum(1 for j in on if pp[i, j])
        on = [j for j in range(W) if ap[j, i]]
        return len(on), sum(1 for j in on if pp[j, i])

    cut = {}
    for kind, idx in (("L", range(W)), ("R", range(W - 1, -1, -1)),
                      ("T", range(H)), ("B", range(H - 1, -1, -1))):
        n_lines = W if kind in ("L", "R") else H
        widest = max([scan(kind, i)[0]
                      for i in range(0, n_lines, max(1, n_lines // 60))] + [1])
        deepest, run = 0, 0
        for k, i in enumerate(idx):
            if k >= MAX_PEEL:
                break
            n_on, n_blk = scan(kind, i)
            if n_on < widest * LINE_SPAN:
                run = 0
                continue                      # 가시·자투리 — 건너뛰고 계속 안쪽을 본다
            if n_blk >= n_on * LINE_BLACK:
                run += 1
                if run <= LINE_MAX_THICK:     # 두꺼우면 선이 아니라 검은 옷이다
                    deepest = k + 1
            else:
                run = 0
        cut[kind] = deepest

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
        # ⚠️ 예전에는 어깨선 바로 아래(+22%)에서 잘랐다. 그러면 **머리만 남는다** —
        #    실측: 그렇게 만든 M50B 얼굴 4장은 턱이 그림 높이의 93% 에 있었다.
        #    그 그림을 화면 바닥에 붙이면 턱이 바닥이라 자막이 얼굴을 덮는다.
        #    턱 아래에 가슴이 남도록, **턱이 그림 한가운데(55%)** 에 오게 자른다.
        #    가슴이 모자라면 아래 min() 이 알아서 자르지 않고 통째로 쓴다.
        chin = sh or int(H * 0.55)
        cut_at = int(min(H, (chin - top) / CHIN_AT + top))
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
            print(f"  {code}/{pose:14} 검은 선 {peeled:,}점 지움")
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
