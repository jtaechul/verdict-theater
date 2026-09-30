#!/usr/bin/env python3
"""⭐ 등장인물 전부를 **한 장에** 나란히 그리는 인물 시트 (2026-09-30 신설).

    python3 src/castsheet.py S93                     값 0원 — 시트 프롬프트만 보여 준다
    python3 src/castsheet.py S93 --crop 시트.png      칸 자르기만 (값 0원)

왜 (2026-09-30 손님)
    "이미지를 따로 제작하면 등장인물이 꼬여서 안 돼. 등장인물 6명 이내로 하고
     한 이미지로 제작해서 해당 구획의 등장인물을 각각 스토리보드와 영상에
     적용하도록 하는 건 어때?"
    인물 카드를 한 명씩 따로 뽑으면 모델이 매번 새 얼굴을 지어내서, 내연녀와
    딸이 똑같이 나온 적이 있다. 한 장에 나란히 그리면 모델이 **서로 다르게**
    그려야 하는 문제로 푼다. 같은 날 손님이 플로우에서 이 틀로 뽑아 보셨고
    다섯 얼굴이 뚜렷이 달랐다. (영상은 플로우에서 막혀 API 로 옮겼다 — src/omni.py)

지켜야 할 것
    · 여자끼리 붙이지 않는다 — 립스틱·머리색이 옆 사람에게 번진다. 남녀를 번갈아 둔다
    · 칸을 자를 때 모델이 그은 선을 믿지 않는다. src/char_sheet.py 의 교훈 그대로 —
      "모델이 그리는 격자는 픽셀 단위로 정확하지 않다". 빈 세로줄을 **직접 찾고**,
      못 찾으면 똑같이 나눈다
    · 시트 프롬프트는 인물을 **정하는** 글이라 옷·얼굴을 적는다 (컷 프롬프트와 반대 —
      컷에서는 이 시트를 잘라 참조로 넣으므로 옷·얼굴을 안 적는다).
      그래도 안전 검사 낱말(series.RISKY)은 쓰지 않는다
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MAX_CAST = 6            # 손님이 정한 상한 — 한 장에 여섯 명까지
# 컷에는 '아내', 인물 목록에는 '본처' 로 적힌다 (관리자 페이지 CARD_NAME 과 같다)
ALIAS = {"아내": "본처"}


def _field(sheet, key):
    m = re.search(rf"^{key}:\s*(.+)$", str(sheet or ""), re.M)
    return m.group(1).strip().rstrip(".") if m else ""


def sex_age(ch):
    """('woman' | 'man', 나이 또는 None) — flow_prompt 첫머리에서 읽는다."""
    head = f"{ch.get('flow_prompt') or ''} {ch.get('flow_sheet') or ''}"
    m = re.search(r"Korean (woman|man)\b(?:,\s*(\d{1,2}) years old)?", head)
    if not m:
        return None, None
    return m.group(1), (int(m.group(2)) if m.group(2) else None)


def char_of(doc, who):
    """컷의 이름('아내')으로 인물 목록의 그 사람('본처')을 찾는다."""
    chars = doc.get("characters") or []
    for name in (who, ALIAS.get(who)):
        for ch in chars:
            if name and ch.get("name") == name:
                return ch
    return None


def people(doc, first=()):
    """시트에 그릴 사람들 — 화면에 나오는 사람(first)을 먼저, 여섯 명까지."""
    chars = [c for c in (doc.get("characters") or []) if sex_age(c)[0]]
    want = [char_of(doc, w) for w in first]
    head = [c for c in want if c]
    rest = [c for c in chars if c not in head]
    return (head + rest)[:MAX_CAST]


def order(ps):
    """세우는 차례 — 같은 성별이 붙으면 화장·머리색이 옆 사람에게 번진다.
    그래서 **남녀를 번갈아** 세우고, 여자 셋·남자 하나처럼 어쩔 수 없이
    붙어야 하면 **나이가 가장 먼 둘**을 붙인다 (예전에 내연녀·딸이 똑같이
    나왔다 — 비슷한 둘이 붙는 것이 가장 나쁘다).
    여섯 명까지라 모든 차례(720가지)를 다 재 본다 — 같으면 원래 차례가 이긴다."""
    import itertools

    def pen(seq):
        out = 0
        for x, y in zip(seq, seq[1:]):
            sx, ax = sex_age(x)
            sy, ay = sex_age(y)
            if sx == sy:
                gap = abs((ax or 40) - (ay or 40))
                out += 100 + max(0, 30 - gap)
        return out

    best, score = list(ps), None
    for seq in itertools.permutations(ps):
        p = pen(seq)
        if score is None or p < score:
            best, score = list(seq), p
    return best


def _who(ch):
    return str(ch.get("role_en") or ch.get("name") or "a person").strip()


def column(i, n, ch):
    sex, age = sex_age(ch)
    sheet = ch.get("flow_sheet") or ""
    where = "far left" if i == 0 else ("far right" if i == n - 1 else "")
    label = f"COLUMN {i + 1}" + (f", {where}" if where else "")
    bits = [f"Korean {sex}" + (f", {age}" if age else "")]
    for key in ("FACE AND HAIR", "BUILD", "WEARING"):
        v = _field(sheet, key)
        if v:
            bits.append(v[0].upper() + v[1:])
    return f"{label} — {_who(ch)}: " + ". ".join(bits) + "."


def prompt(ps):
    """시트 한 장을 뽑는 글. ps 는 order() 를 거친 차례 그대로 왼쪽부터 선다."""
    n = len(ps)
    cols = [column(i, n, ch) for i, ch in enumerate(ps)]
    women = [p for p in ps if sex_age(p)[0] == "woman"]
    diff = (f"DIFFERENCE: {n} clearly different people who look nothing alike, each "
            "with their own face shape, eyes, nose, jaw and hairline.")
    if len(women) >= 2:
        diff += (" The women read instantly as different people: "
                 + "; ".join(f"{_who(p)} — {p.get('face_tag') or ''}".strip(" —")
                             for p in women) + ".")
    return "\n".join([
        "A character line-up sheet for a short fictional drama. Every character "
        "is invented for this story and resembles nobody.",
        f"FORMAT: one single landscape image, 16:9, very high detail, divided into "
        f"{n} equal vertical columns separated by thin white gaps. Each column "
        "belongs to one person and shows that same person two ways: top half — a "
        "close view of the head and shoulders, the face large and clear, facing "
        "straight ahead; bottom half — the same person standing full length from "
        "head to shoes, facing straight ahead, arms relaxed at the sides. Mouths "
        "closed, calm neutral expression.",
        *cols,
        diff,
        "BACKGROUND: the same plain flat light-grey wall in every column, no "
        "furniture, no props, no scenery.",
        f"LIGHT: soft even light from the front on all {n}, no hard shadows, no "
        "coloured light.",
        "STYLE: naturalistic cinematic drama look, true-to-life body proportions, "
        "ordinary everyday Korean people with unexaggerated features, soft film "
        "grain, muted desaturated colours.",
        "ON SCREEN: no text, no letters, no numbers, no names, no labels, no "
        "watermark, no logo.",
    ])


def bg_share(im):
    """세로줄마다 '배경인 점의 비율' (0~1). 흰 틈·밝은 회색 벽이 배경이다.
    ⚠️ 너무 줄여서 보면 가는 틈이 옆 옷 색에 섞여 사라진다 — 폭 1,000점 안팎으로 본다
       (손님의 플로우 시트로 재 보니 4배로 줄이면 틈이 0.58~0.86 까지 흐려졌다)."""
    step = max(1, im.width // 1000)
    small = im.resize((max(1, im.width // step), max(1, im.height // step)))
    w, h = small.size
    px = small.load()
    out = []
    for x in range(w):
        bg = 0
        for y in range(h):
            r, g, b = px[x, y][:3]
            if min(r, g, b) >= 170 and max(r, g, b) - min(r, g, b) <= 18:
                bg += 1
        out.append(bg / h)
    return out


GAP_MIN = 0.80      # 칸 경계로 믿을 만큼 비어 있는 줄 (플로우 시트 실측 0.80~0.96)


def cuts_of(share, n, width):
    """'똑같이 나눴을 때의 자리' 둘레에서 **가장 비어 있는 줄**을 칸 경계로 쓴다.
    하나라도 흐릿하거나(GAP_MIN 미만) 칸 폭이 크게 어긋나면 None — 그때는
    똑같이 나눈다. 모델이 그은 선이 조금 삐뚤어도 사람을 자르지 않게 하려는 것이다."""
    w = len(share)
    if n < 2 or w < n * 4:
        return None
    got = []
    for k in range(1, n):
        ideal = k * w / n
        lo, hi = int(ideal - 0.25 * w / n), int(ideal + 0.25 * w / n)
        win = range(max(1, lo), min(w - 1, hi) + 1)
        best = max(win, key=lambda x: (share[x], -abs(x - ideal)))
        top = share[best]
        if top < GAP_MIN:
            return None
        # 똑같이 빈 줄이 여러 개 이어지면(사람 사이 벽) 그 띠의 **가운데**를 자른다
        # — 한쪽 끝을 자르면 옆 사람 팔 끝이 딸려 온다
        lo2 = hi2 = best
        while lo2 - 1 >= 1 and share[lo2 - 1] >= top - 0.01:
            lo2 -= 1
        while hi2 + 1 < w - 1 and share[hi2 + 1] >= top - 0.01:
            hi2 += 1
        got.append((lo2 + hi2) / 2 * width / w)
    edges = [0.0] + got + [float(width)]
    avg = width / n
    if any(not 0.6 * avg <= b - a <= 1.4 * avg for a, b in zip(edges, edges[1:])):
        return None
    return got


def crop(sheet, n, out_dir, stem="cast"):
    """시트를 n 칸으로 자른다. 돌려주는 것: ([(파일, (x0, x1))…], 어떻게 잘랐나)"""
    from PIL import Image     # 늦게 부른다 — 그림을 자를 때만 필요하다 (heavy_import_check)
    im = Image.open(sheet).convert("RGB")
    cuts = cuts_of(bg_share(im), n, im.width)
    how = "빈 줄을 찾아 잘랐다" if cuts else "빈 줄을 못 찾아 똑같이 나눴다"
    if not cuts:
        cuts = [k * im.width / n for k in range(1, n)]
    edges = [0] + [int(round(c)) for c in cuts] + [im.width]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    outs = []
    for i in range(n):
        p = out_dir / f"{stem}-{i + 1}.png"
        im.crop((edges[i], 0, edges[i + 1], im.height)).save(p)
        outs.append((p, (edges[i], edges[i + 1])))
    return outs, how


SHEET = "_sheet.png"          # 인물 카드 폴더 안에 둔다 — 함께 보관되어 다시 쓰인다


def make(sid, out_dir):
    """⭐ 2분 드라마 — 인물 시트 한 장을 그려 칸마다 잘라 **인물 카드**로 둔다.

    카드 이름은 조립(src/short90.py)이 찾는 이름 그대로다 (아내 → 본처.png).
    ⚠️ 시트는 **지문이 같으면 다시 안 그린다** (0원) — 인물 설계가 바뀌었을
       때만 다시 그린다. 칸 자르기는 늘 다시 한다 (0원 · 1초).
    ⚠️ 손님이 올린 얼굴(옛 방식)은 2분 드라마에서는 쓰지 않는다 — 시트 한 장에서
       나온 얼굴끼리만 서로 다르게 그려졌다는 것이 보장된다.
    """
    sys.path.insert(0, str(ROOT / "src"))
    import reuse                                             # noqa: E402
    import still as ST                                       # noqa: E402
    doc = json.loads((ROOT / "data" / "series" / f"{sid}.json")
                     .read_text(encoding="utf-8"))
    ps = order(people(doc))
    if not ps:
        raise RuntimeError(f"{sid} 에 인물 설계(characters)가 없다")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    text = prompt(ps)
    sheet = out_dir / SHEET
    sig = reuse.sig_of(text)
    ok, why = reuse.can_reuse(sheet, sig)
    print(f"■ {sid} 인물 시트 — 왼쪽부터 " + " · ".join(p["name"] for p in ps))
    if ok:
        print("   (그대로다 — 다시 안 그린다 · 0원)")
    else:
        if why:
            print(f"   ⚠️ {why} — 다시 그린다")
        try:
            ST.gen(text, sheet, ratio="16:9", size="4K", label="castsheet")
        except ST.StillError as e:
            if "HTTP 400" not in str(e):
                raise
            print(f"   4K 를 안 받아 2K 로 다시: {str(e)[:120]}")
            ST.gen(text, sheet, ratio="16:9", size="2K", label="castsheet")
        reuse.stamp(sheet, sig)
    outs, how = crop(sheet, len(ps), out_dir, stem="_cast")
    print(f"   칸 자르기 — {how}")
    for (p, box), ch in zip(outs, ps):
        name = ALIAS.get(ch["name"], ch["name"])
        dst = out_dir / f"{name}.png"
        dst.write_bytes(p.read_bytes())
        # ⚠️ 카드에는 **시트 지문 + 칸 자리**를 적는다 — 시트가 바뀌면 카드도
        #    바뀐 것이 되고, 그 카드로 그린 컷 그림도 다시 그려진다(reuse 규칙)
        reuse.stamp(dst, reuse.sig_of(sig, name, str(box)))
        print(f"   {dst.name}  ← {ch['name']} (가로 {box[0]}~{box[1]})")
    return 0


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("sid")
    ap.add_argument("--crop", help="이미 뽑은 시트를 칸으로 자르기만 한다")
    ap.add_argument("--make", metavar="카드폴더",
                    help="시트를 그려(지문이 같으면 0원) 칸마다 인물 카드로 둔다")
    a = ap.parse_args()
    if a.make:
        return make(a.sid.upper(), a.make)
    doc = json.loads((ROOT / "data" / "series" / f"{a.sid.upper()}.json")
                     .read_text(encoding="utf-8"))
    ps = order(people(doc))
    print("왼쪽부터: " + " · ".join(p["name"] for p in ps) + "\n")
    if a.crop:
        outs, how = crop(a.crop, len(ps), Path(a.crop).parent)
        print(how)
        for (p, box), ch in zip(outs, ps):
            print(f"  {p.name}  {ch['name']}  x {box[0]}~{box[1]}")
        return 0
    print(prompt(ps))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
