#!/usr/bin/env python3
"""⭐ 캐릭터 카드와 '컷 첫 장면 스틸' 을 만든다 (2026-08-23 신설).

    python3 src/still.py cards  S001                  인물 카드 (한 시리즈에 한 번)
    python3 src/still.py scenes S001 1                1화 컷마다 첫 장면 스틸

왜 이 단계가 생겼나
    컷마다 Veo 를 따로 부르면 얼굴·옷·배경이 컷마다 달라진다. 실측해 보니
    veo-3.1-lite 는 `referenceImages` 를 **안 받고**(400), 받는 것은
    **시작 프레임 이미지 한 장**(`image`)뿐이다. 그래서 순서가 이렇게 된다.

        ① 인물 카드 한 장씩 만든다 (본처·내연녀·남편 — 시리즈당 3장)
        ② 그 카드를 **참조 이미지로 넣어** 컷마다 첫 장면 스틸을 그린다
        ③ 그 스틸을 Veo 의 시작 프레임으로 넣어 영상을 만든다

    ②에서 카드를 넣을 수 있다는 것도 값 0원으로 실측했다 — 그림 모델은
    contents.parts 안에 inlineData 로 이미지를 받는다(1장도 3장도 받는다).
    없는 필드를 보내면 400 이 나는 것까지 확인해 검증법 자체를 검증했다.

값
    카드 3장 + 컷 스틸 5장 = 8장. gemini-3.1-flash-image 2K 기준 한 장 약 130원.
    컷마다 부르기 전에 한 달 한도를 본다. 이미 있는 그림은 다시 안 만든다.
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cost                                                  # noqa: E402
import vprompt                                               # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://generativelanguage.googleapis.com/v1beta"

# 실측으로 이 열쇠에 있는 것을 확인한 모델만 적는다. imagen 계열은 이 API 에 없다.
MODEL = os.environ.get("STILL_IMAGE_MODEL", "gemini-3.1-flash-image")
SIZE = os.environ.get("STILL_IMAGE_SIZE", "2K")
CALL_CAP = int(os.environ.get("STILL_CALL_CAP", "24"))

_calls = {"n": 0}


class StillError(RuntimeError):
    pass


def _key():
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if not k:
        raise StillError("GEMINI_API_KEY 가 없다.")
    return k


def seed_of(*parts):
    """같은 것을 다시 만들면 같은 그림이 나오도록 씨앗을 고정한다.

    ⚠️ 컷마다 **다른** 씨앗이어야 한다. 같은 씨앗을 다섯 컷에 쓰면 다섯 장이
       거의 같은 그림이 된다. 대신 시리즈·인물이 같으면 늘 같은 값이 나오게
       이름에서 만들어 낸다 — 실행할 때마다 달라지면 안 된다."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:8], 16) % 2_000_000_000


def gen(prompt, out, refs=(), ratio="16:9", size=None, seed=None, label=""):
    """그림 한 장. refs 에 넣은 그림들을 **참조**로 같이 보낸다."""
    if _calls["n"] >= CALL_CAP:
        raise StillError(f"이번 실행의 그림 만들기 상한({CALL_CAP}장)에 걸렸다.")
    size = size or SIZE
    krw = cost.image_krw(MODEL, size)
    if cost.month_total() + krw > cost.MONTH_KRW:
        raise cost.MonthlyCapReached(
            f"이번 달 한도({cost.MONTH_KRW:,.0f}원)에 걸렸습니다. "
            f"지금까지 {cost.month_total():,.0f}원 썼고 이 그림이 약 {krw:,.0f}원입니다.")

    parts = []
    for r in refs:
        parts.append({"inlineData": {"mimeType": "image/png",
                                     "data": base64.b64encode(Path(r).read_bytes()).decode()}})
    parts.append({"text": prompt})
    body = {"contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"],
                                 "imageConfig": {"aspectRatio": ratio, "imageSize": size}}}
    if seed is not None:
        # 실측: seed 는 generationConfig 안이다. imageConfig 안에 넣으면 400.
        body["generationConfig"]["seed"] = int(seed)

    req = urllib.request.Request(f"{BASE}/models/{MODEL}:generateContent",
                                 data=json.dumps(body).encode(),
                                 headers={"x-goog-api-key": _key(),
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            raw = json.loads(raw)["error"]["message"]
        except Exception:                                    # noqa: BLE001
            pass
        raise StillError(f"그림 만들기 실패 (HTTP {e.code}): {raw[:250]}") from None
    _calls["n"] += 1
    cost.record("image", krw, f"{MODEL} {size} {ratio} {out.name}")

    b64 = None
    for c in data.get("candidates", []):
        for p in (c.get("content") or {}).get("parts", []):
            d = p.get("inlineData") or p.get("inline_data")
            if d and d.get("data"):
                b64 = d["data"]
    if not b64:
        # 안전필터에 걸리면 200 인데 그림이 안 온다. 왜 없는지 알려 준다.
        why = json.dumps(data, ensure_ascii=False)[:220]
        raise StillError(f"그림이 안 왔다 (안전필터일 수 있다): {why}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(b64))
    print(f"    ✅ {out.name}  ({out.stat().st_size / 1e6:.2f}MB · 약 {krw:,.0f}원)")
    return krw


def load(sid):
    return json.loads((ROOT / "data" / "series" / f"{sid}.json").read_text(encoding="utf-8"))


def card_path(out_dir, name):
    return Path(out_dir) / f"{name}.png"


def cards(sid, out_dir):
    """인물 카드. 시리즈당 한 번만 만들면 된다."""
    doc = load(sid)
    chars = doc.get("characters") or []
    print(f"■ {sid} 인물 카드 {len(chars)}장 (약 "
          f"{cost.image_krw(MODEL, SIZE) * len(chars):,.0f}원)")
    for c in chars:
        name = c.get("name", "?")
        out = card_path(out_dir, name)
        print(f"  {name}")
        if out.exists() and out.stat().st_size > 10_000:
            print(f"    (이미 있다 — 건너뛴다)")
            continue
        prompt = vprompt.still_prompt(c.get("flow_sheet") or c.get("flow_prompt") or "")
        gen(prompt, out, ratio="9:16", seed=seed_of(sid, name), label=name)
    return 0


def who_in(cut, doc):
    """이 컷에 나오는 인물들. 지시문에 영어 이름이 적혀 있다."""
    nm = doc.get("_name_map") or {}
    text = (cut.get("prompt") or "").lower()
    out = []
    for c in doc.get("characters") or []:
        ko = c.get("name", "")
        en = (nm.get(ko) or c.get("role_en") or "").lower()
        if en and en in text:
            out.append(ko)
    return out


def scenes(sid, no, cards_dir, out_dir, only_cut=None):
    doc = load(sid)
    ep = next((e for e in (doc.get("episodes") or [])
               if int(e.get("no", 0)) == int(no)), None)
    if not ep:
        raise StillError(f"{sid} 에 {no}화가 없다.")
    cuts = ep.get("cuts") or []
    if only_cut:
        cuts = [c for c in cuts if int(c.get("n", 0)) == int(only_cut)]
    out_dir = Path(out_dir)
    print(f"■ {sid} {no}화 「{ep.get('title','')}」 컷 스틸 {len(cuts) * 2}장 "
          f"(시작·끝 두 장씩 · 약 {cost.image_krw(MODEL, SIZE) * len(cuts) * 2:,.0f}원)")
    # ⭐⭐ 2026-08-23 운영자 지시 — 컷마다 **시작·끝 두 장**을 만든다.
    #    한 장(시작)만 주니 도착점이 자유라 옷이 바뀌고 사람이 사라졌다 나타났다.
    #    "이미지 여러 개를 가지고서 동영상이 연결되게끔만 했어도 이런 사단은
    #     안 났잖아." — 맞는 말이라 그대로 한다. 영상은 두 장 사이를 잇기만 한다.
    #    ⚠️ 끝 장면은 **시작 장면 그림을 참조에 같이 넣어** 만든다 — 그래야
    #       두 장의 옷·배경·자리가 같은 데서 출발한다.
    made, want = 0, 0
    for c in cuts:
        n = int(c.get("n", 0))
        names = who_in(c, doc)
        print(f"  컷{n}  나오는 사람: {', '.join(names) or '없음'}")
        refs = [p for p in (card_path(cards_dir, x) for x in names) if p.exists()]
        if names and not refs:
            print("    ⚠️ 인물 카드가 없다 — 카드부터 만들어야 얼굴이 같아진다")
        stop = False
        for when, suffix in (("start", ""), ("end", "_end")):
            want += 1
            out = out_dir / f"c{n:03d}{suffix}.png"
            if out.exists() and out.stat().st_size > 10_000:
                print(f"    (이미 있다 — 건너뛴다: {out.name})")
                made += 1
                continue
            use = list(refs)
            first = out_dir / f"c{n:03d}.png"
            if when == "end" and first.exists():
                use = [first] + use          # 시작 장면이 첫 참조 — 그대로 이어지게
            try:
                gen(vprompt.still_prompt(c.get("prompt") or "", when), out,
                    refs=use, ratio="16:9", seed=seed_of(sid, no, n, when))
                made += 1
            except (StillError, cost.MonthlyCapReached) as e:
                print(f"    ❌ {e}")
                print(f"\n  여기서 멈춘다. 만든 {made}장은 남는다 — "
                      f"다시 누르면 없는 것만 채운다.")
                stop = True
                break
        if stop:
            break
    print(f"\n■ 스틸 {made}/{want}장")
    return 0 if made == want else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["cards", "scenes"])
    ap.add_argument("sid")
    ap.add_argument("no", nargs="?", default="1")
    ap.add_argument("--cards", default="build/cards")
    ap.add_argument("--out", default="")
    ap.add_argument("--cut", default="")
    a = ap.parse_args()
    try:
        if a.what == "cards":
            return cards(a.sid, a.out or a.cards)
        return scenes(a.sid, a.no, a.cards, a.out or "build/stills", a.cut or None)
    except (StillError, cost.MonthlyCapReached) as e:
        print(f"❌ {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
