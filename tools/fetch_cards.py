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
import os
import urllib.request
from pathlib import Path

# ⚠️⚠️ 2026-08-30 — **여기서 암호를 안 보내고 있었다.**
#    보관함(/api/blob)은 x-vt-pass 로 암호를 받는다. shorts.yml 은 보내는데
#    여기만 안 보내서, 손님이 올리신 그림을 받아 갈 때 통째로 튕겼다
#    (그 한 줄 때문에 90초 편 만들기가 실패했다).
def _open(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "verdict-theater",
        "x-vt-pass": os.environ.get("ADMIN_PASS", ""),
    })
    return urllib.request.urlopen(req, timeout=300)


OK = ("본처", "남편", "내연녀", "딸", "변호사")
MIN_BYTES = 10_000


def main():
    raw = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "build/s90/cards")
    if not raw or raw in ("{}", "null"):
        # ⭐ 2026-08-30 — 이제 다섯 얼굴은 저장소에 들어 있다(tools/repo_cards.py).
        #    여기서 "시스템이 그린다" 고 적으면 로그가 거짓말이 된다.
        print("■ 새로 올리신 인물 그림이 없다 — 넣어 둔 다섯 얼굴을 그대로 씁니다")
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
    warned = []
    for who, url in got.items():
        if who not in OK:
            print(f"  ⚠️ 모르는 사람이라 건너뛴다: {who}")
            continue
        if not isinstance(url, str) or not url.startswith("http"):
            print(f"  ⚠️ {who}: 주소가 이상하다 — 건너뛴다")
            continue
        dst = out / f"{who}.png"
        # ⭐⭐ 2026-08-30 — **못 받았다고 다 죽이면 안 된다.**
        #    저장소에 넣어 둔 다섯 얼굴이 이미 제자리에 놓여 있는데(repo_cards),
        #    올리신 그림 한 장을 못 받았다고 여기서 죽어서 90초 편 만들기가
        #    통째로 실패했다. 이미 얼굴이 있으면 그것으로 이어서 만든다.
        #    ⚠️ 다만 **크게 알린다** — 새로 올리신 얼굴이 안 쓰인 것이니까.
        have = dst.exists() and dst.stat().st_size >= MIN_BYTES
        tmp = dst.with_suffix(".new")
        try:
            with _open(url) as r, open(tmp, "wb") as f:
                f.write(r.read())
            if tmp.stat().st_size < MIN_BYTES:
                raise ValueError(f"받은 그림이 너무 작다 ({tmp.stat().st_size} 바이트)")
            tmp.replace(dst)
        except Exception as e:                                # noqa: BLE001
            if tmp.exists():
                tmp.unlink()
            why = str(e)[:80]
            if have:
                print(f"  ⚠️ {who}: 올리신 그림을 못 받았다 ({why}) — "
                      f"넣어 둔 얼굴로 이어서 만듭니다")
                warned.append(who)
                continue
            print(f"  ❌ {who}: 못 받았고 쓸 얼굴도 없다 ({why})")
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
    if warned:
        print(f"⚠️ 못 받아서 넣어 둔 얼굴을 쓴 사람: {', '.join(warned)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
