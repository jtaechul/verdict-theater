#!/usr/bin/env python3
"""저장소에 넣어 둔 **인물 그림**을 카드 자리에 놓는다.

    python3 tools/repo_cards.py build/s90/cards

왜 (2026-08-30 손님: "무조건 등장인물은 첨부 등장인물 이미지를 참고하도록 해")
    손님이 다섯 사람을 직접 골라 보내 주셨다. 그 얼굴이 **매번** 쓰여야 한다.
    관리자 페이지에서 올리는 길(tools/fetch_cards.py)만 있으면, 손님이 누를
    때마다 다섯 장을 다시 올려야 하고 한 번 빠뜨리면 시스템이 제 나름대로
    다시 그려 **다른 얼굴**이 나온다. 그래서 그림을 저장소에 넣어 두고
    실행할 때마다 여기서 꺼내 쓴다 — 손님은 아무것도 안 하셔도 된다.

    ⚠️ 옆에 `.hand` 표시를 남긴다. 그게 있으면 src/still.py 가 그 사람을
       **안 다시 그린다** (카드값 661원이 안 나간다).

    ⚠️ 파일 이름은 영문이다(지침). 여기서 한글 카드 이름으로 옮겨 놓는다.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets" / "cards" / "s90"
MIN_BYTES = 10_000

# 영문 파일 이름 → 카드 이름 (src/short90.py 가 찾는 이름)
NAME = {"wife": "본처", "husband": "남편", "mistress": "내연녀",
        "daughter": "딸", "attorney": "변호사"}


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "build/s90/cards")
    out.mkdir(parents=True, exist_ok=True)
    missing = []
    n = 0
    for en, ko in NAME.items():
        src = SRC / f"{en}.png"
        if not src.exists() or src.stat().st_size < MIN_BYTES:
            missing.append(en)
            continue
        dst = out / f"{ko}.png"
        shutil.copyfile(src, dst)
        dst.with_suffix(".hand").write_text("repo", encoding="utf-8")
        sig = dst.with_suffix(".sig")           # 옛 지문은 헷갈리므로 치운다
        if sig.exists():
            sig.unlink()
        n += 1
        print(f"  ✅ {ko} ← assets/cards/s90/{en}.png "
              f"({dst.stat().st_size / 1e6:.2f}MB)")
    if missing:
        print(f"❌ 저장소에 없는 인물 그림: {', '.join(missing)}")
        return 1
    print(f"\n■ 저장소에 넣어 둔 인물 그림 {n}장을 씁니다 (0원)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
