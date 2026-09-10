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


# ⚠️⚠️⚠️ 2026-09-09 손님: "매번 이렇게 등장인물이 고정되는 게 아닌데 매번
#    똑같은 등장인물만 등록할 수 있도록 하는 오류가 발생하고 있어."
#
#    맞다. 여기가 `OK = ("본처","남편","내연녀","딸","변호사")` 로 **박혀
#    있었다.** 사건마다 나오는 사람이 다른데(시어머니·아들·형·사장…), 그
#    다섯 말고는 얼굴을 올려도 "모르는 사람" 이라며 조용히 버렸다.
#
#    → 이제 **그 사건 대본에 실제로 나오는 사람**을 받는다. 목록을 손으로
#      적지 않으므로 새 인물이 생겨도 저절로 따라간다.
#    ⚠️ 아무 이름이나 받으면 안 된다 — 파일 이름이 되므로 엉뚱한 글자가
#      들어오면 파일이 이상해진다. 대본에 있는 이름만 받는다.
ROOT = Path(__file__).resolve().parent.parent
MIN_BYTES = 10_000
# 화면 이름 ↔ 카드 파일 이름 (src/short90.ST_NAME 과 같아야 한다)
CARD_NAME = {"아내": "본처"}


FALLBACK = {"본처", "남편", "내연녀", "딸", "변호사"}


def cast_of_doc(doc):
    """이 대본에 나오는 사람들 (카드 파일 이름으로).

    ⚠️ 검사가 살아 있는 파일에 안 묶이도록 **대본을 받아서** 따진다."""
    # ⚠️⚠️ 2026-09-10 — people 을 같이 보다가 걸렸다. people 에는 **화면에
    #    안 나오고 말로만 언급되는 사람**도 들어간다(S92 의 어머니).
    #    화면·서버·여기가 같은 규칙을 써야 한다 — **컷에 서는 사람만**.
    got = set()
    for c in (doc or {}).get("cuts") or []:
        for w in c.get("who") or []:
            got.add(CARD_NAME.get(w, w))
    return got or set(FALLBACK)


def cast_of(sid):
    """그 사건 대본에 나오는 사람들.

    ⚠️ 대본을 못 읽으면 옛 다섯으로 물러선다 — 아무도 못 올리게 되면
       손님이 올린 얼굴이 통째로 사라진다."""
    f = ROOT / "data" / "series" / f"{sid}.json"
    try:
        return cast_of_doc(json.loads(f.read_text(encoding="utf-8")))
    except Exception:                                        # noqa: BLE001
        return set(FALLBACK)


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
    sid = (os.environ.get("VT_SID") or "S90").strip().upper()
    ok = cast_of(sid)
    print(f"■ {sid} 대본에 나오는 사람: {' · '.join(sorted(ok))}")
    n = 0
    warned = []
    for who, url in got.items():
        if who not in ok:
            print(f"  ⚠️ 이 사건 대본에 없는 사람이라 건너뛴다: {who}")
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
