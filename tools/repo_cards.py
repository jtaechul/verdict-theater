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
CARDS = ROOT / "assets" / "cards"
FALLBACK = "s90"
MIN_BYTES = 10_000

# 영문 파일 이름 → 카드 이름 (src/short90.py 가 찾는 이름)
NAME = {"wife": "본처", "husband": "남편", "mistress": "내연녀",
        "daughter": "딸", "attorney": "변호사"}


def src_dir(sid):
    """그 사건의 얼굴 폴더. 없으면 기본 다섯(s90)으로 돌아간다.

    ⭐⭐⭐ 2026-09-05 손님: "에피소드에서 등장인물들을 좀 새로 생성하고
       싶거든? 전혀 다른 얼굴이 생성되도록."
       그때까지 얼굴 폴더가 **assets/cards/s90 하나뿐**이었다. 새 사건에
       새 얼굴을 넣으면 옛 사건 얼굴까지 바뀌어, 이미 올린 편과 얼굴이
       달라진다. → 사건마다 제 폴더를 갖는다 (assets/cards/<sid>).
       폴더가 없는 사건은 지금까지처럼 s90 다섯을 쓴다.
    """
    d = CARDS / str(sid or "").strip().lower()
    if d.name and d.is_dir():
        return d, False
    return CARDS / FALLBACK, True


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "build/s90/cards")
    sid = (sys.argv[2] if len(sys.argv) > 2 else "").strip() or "s90"
    SRC, fell = src_dir(sid)
    if fell and SRC.name != str(sid).lower():
        print(f"■ {sid.upper()} 전용 얼굴 폴더가 없습니다 "
              f"— 기본 얼굴(assets/cards/{FALLBACK})을 씁니다")
    else:
        print(f"■ {sid.upper()} 전용 얼굴을 씁니다 (assets/cards/{SRC.name})")
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
        print(f"  ✅ {ko} ← assets/cards/{SRC.name}/{en}.png "
              f"({dst.stat().st_size / 1e6:.2f}MB)")
    if missing:
        print(f"❌ assets/cards/{SRC.name} 에 없는 인물 그림: "
              f"{', '.join(missing)}")
        return 1
    print(f"\n■ 저장소에 넣어 둔 인물 그림 {n}장을 씁니다 (0원)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
