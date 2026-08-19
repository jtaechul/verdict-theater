#!/usr/bin/env python3
"""⭐ **검사에 걸린 시트만** 골라낸다 — 다시 만들 것과 값을 미리 보여 준다. 0원.

    python3 tools/broken_sheets.py            사람이 읽는 표
    python3 tools/broken_sheets.py --list     기계가 읽는 목록 (CODE KIND 한 줄씩)

왜 (2026-08-16)
    옛 격자 시트의 얼굴 컷 18장(정수리 잘림)이 방송에 나갔다. 고치려면 그
    배우들의 얼굴 시트만 다시 만들면 되는데, 예전에는 'F70·M50B' 처럼 배우
    이름을 박은 일회용 단추를 만들었다가 지뢰가 됐다(수리가 끝난 뒤에 누르면
    멀쩡한 배우를 또 산다). 이제 **이름을 박지 않는다** — 목 잘림 검사와 같은
    자로 컷을 재서, 걸린 컷이 나온 시트만 그때그때 골라낸다.
    걸린 것이 없으면 빈 목록이다 — 눌러도 돈이 안 나간다.

시트와 컷의 관계 (두 시트 체계)
    CODE.png      = 얼굴 6 + 상반신 6  → face_*, bust_* 컷
    CODE_full.png = 전신 5자세          → full_* 컷
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

SHEET_KRW = 265          # 시트 한 장 값 (4K · pro 모델 실측)


def broken():
    """{(배우, 시트종류)} — 검사에 걸린 컷이 나온 시트들. 잣대는 head_test 그대로."""
    from head_test import load_mask, top_flat, big_blobs, TOP_FLAT, FACE_FLAT, POSE_SKIP
    out = set()
    chars = ROOT / "assets" / "char"
    if not chars.is_dir():
        return out
    for d in sorted(chars.iterdir()):
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.png")):
            mask = load_mask(p)
            kind = "full" if p.stem.startswith("full_") else "face"
            hit = False
            blobs = big_blobs(mask)
            if blobs is not None and blobs > 1:
                hit = True
            elif p.stem.startswith("face_"):
                r = top_flat(mask)
                hit = r is not None and r >= FACE_FLAT
            elif p.stem.startswith(("full_", "bust_")) and p.stem not in POSE_SKIP:
                r = top_flat(mask)
                hit = r is not None and r >= TOP_FLAT
            if hit:
                out.add((d.name, kind))
    return out


def main():
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        print("⚠️ numpy/Pillow 가 없어 재지 못했습니다 — 빈 목록을 내지 않고 멈춥니다.",
              file=sys.stderr)
        return 2                      # '못 쟀음' 을 '고칠 것 없음' 으로 속이지 않는다

    got = sorted(broken())
    if "--list" in sys.argv:
        for code, kind in got:
            print(code, kind)
        return 0
    if not got:
        print("✅ 검사에 걸린 시트가 없습니다 — 다시 만들 것이 없습니다 (0원).")
        return 0
    print(f"검사에 걸린 시트 {len(got)}장 — 다시 만들면 약 {len(got) * SHEET_KRW:,}원")
    for code, kind in got:
        print(f"  {code} · {'얼굴+상반신' if kind == 'face' else '전신'} 시트")
    return 0


if __name__ == "__main__":
    sys.exit(main())
