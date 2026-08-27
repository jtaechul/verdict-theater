#!/usr/bin/env python3
"""손님이 관리자 페이지에서 올린 **인물 그림**을 받아 카드 자리에 놓는다.

    python3 tools/fetch_cards.py '{"본처":"https://…","남편":"https://…"}' build/s90/cards

왜 (2026-08-27 손님: "이미지 다 만들었어. 이제 다음은?")
    손님이 제미나이에서 다섯 사람을 직접 만들어 눈으로 고르셨다. 시스템이
    제 나름대로 다시 그리면 **손님이 고른 얼굴이 아닌 사람**이 나온다.
    올린 그림을 그대로 인물 카드로 쓴다 (카드값 661원도 안 나간다).

    ⚠️ 옆에 `.hand` 표시를 남긴다. 그게 있으면 src/still.py 가 그 사람을
       **안 다시 그린다.** 표시가 없으면 지문이 안 맞아 매번 다시 그린다.
"""
import json
import sys
import urllib.request
from pathlib import Path

OK = ("본처", "남편", "내연녀", "딸", "변호사")
MIN_BYTES = 10_000


def main():
    raw = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "build/s90/cards")
    if not raw or raw in ("{}", "null"):
        print("■ 올린 인물 그림이 없다 — 시스템이 그린다")
        return 0
    try:
        got = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ 올린 그림 목록을 못 읽었다: {e}")
        return 1
    if not isinstance(got, dict):
        print("❌ 올린 그림 목록이 이름:주소 꼴이 아니다")
        return 1

    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for who, url in got.items():
        if who not in OK:
            print(f"  ⚠️ 모르는 사람이라 건너뛴다: {who}")
            continue
        if not isinstance(url, str) or not url.startswith("http"):
            print(f"  ⚠️ {who}: 주소가 이상하다 — 건너뛴다")
            continue
        dst = out / f"{who}.png"
        try:
            with urllib.request.urlopen(url, timeout=120) as r, open(dst, "wb") as f:
                f.write(r.read())
        except Exception as e:                                # noqa: BLE001
            print(f"  ❌ {who}: 못 받았다 ({str(e)[:80]})")
            return 1
        if dst.stat().st_size < MIN_BYTES:
            print(f"  ❌ {who}: 받은 그림이 너무 작다 ({dst.stat().st_size} 바이트)")
            return 1
        # 손으로 올린 것이라는 표시 — 이게 있으면 시스템이 다시 안 그린다
        dst.with_suffix(".hand").write_text("hand", encoding="utf-8")
        # 옛 지문이 남아 있으면 헷갈리므로 치운다
        sig = dst.with_suffix(".sig")
        if sig.exists():
            sig.unlink()
        n += 1
        print(f"  ✅ {who} ({dst.stat().st_size / 1e6:.2f}MB) — 올리신 그림을 씁니다")
    print(f"\n■ 올리신 인물 그림 {n}장을 카드로 씁니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
