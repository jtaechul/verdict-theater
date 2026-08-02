#!/usr/bin/env python3
"""배경 사진을 Pexels 에서 받아 온다.

    PEXELS_API_KEY=... python3 src/bg_fetch.py              없는 것만 받는다
    PEXELS_API_KEY=... python3 src/bg_fetch.py --force      전부 다시 받는다
    PEXELS_API_KEY=... python3 src/bg_fetch.py --only home_living_day
    PEXELS_API_KEY=... python3 src/bg_fetch.py --dry        받지 않고 후보만 본다

왜 만들었나
    배경 18종을 사람이 하나씩 만들어 올리는 일이 너무 번거롭다.
    Pexels 는 상업적 사용이 자유롭고(출처 표기도 의무가 아니다) 사진 품질이 고르다.
    검색 → 고르기 → 잘라 맞추기 → 흐리게 하기까지 전부 여기서 한다.

어떻게 고르나
    ① 배경 코드마다 검색어를 여러 개 준비해 두고 위에서부터 찾는다
    ② **사람이 찍힌 사진을 걸러낸다** — 설명글(alt)에 사람을 가리키는 말이 있으면 버린다.
       인물은 컷아웃으로 따로 얹으므로 배경에 사람이 있으면 두 겹이 겹친다
    ③ 남은 것 중 가로가 넓고 해상도가 큰 것을 고른다
    ④ 이미 다른 배경이 쓴 사진은 건너뛴다 (같은 그림이 두 장소로 나오면 들킨다)

왜 미리 흐리게 하나
    렌더링할 때 어차피 흐려지지만(prepare_bg, 반경 14), 저장소에 들어가는 원본에도
    가벼운 흐림(반경 5)을 미리 넣는다. **스톡 사진에 우연히 찍힌 사람 얼굴이
    또렷한 채로 저장소에 남지 않게** 하기 위해서다. 두 번 흐려도 최종 결과는
    반경 15 정도라 지금과 거의 같다(흐림은 제곱해서 더해진다).
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "bg"
W, H = 1920, 1080
PREBLUR = 5.0
API = "https://api.pexels.com/v1/search"

# 사람이 찍힌 사진을 걸러내는 낱말. 설명글에 하나라도 있으면 버린다.
PEOPLE = (
    "man", "woman", "person", "people", "boy", "girl", "child", "children",
    "lady", "guy", "male", "female", "human", "portrait", "couple", "family",
    "crowd", "worker", "student", "customer", "hand", "hands", "face", "someone",
    "sitting", "standing", "walking", "holding", "wearing", "posing", "smiling",
)

# 배경 코드마다 검색어를 위에서부터 시도한다.
# 한국식 공간을 그대로 찾기는 어려우므로 **분위기와 구조가 맞는 것**을 노린다.
# 어차피 흐려서 깔리므로 나라보다 빛과 결이 중요하다.
QUERIES = {
    "home_living_day": ["empty living room sofa daylight", "living room interior window light",
                        "simple living room couch"],
    "home_living_night": ["dark living room lamp night", "dim living room evening",
                          "living room night interior"],
    "home_kitchen": ["small kitchen interior old", "vintage kitchen counter",
                     "simple kitchen window"],
    "home_closet": ["old wooden wardrobe bedroom", "vintage closet clothes",
                    "bedroom wardrobe interior"],
    "home_entrance": ["apartment entryway door", "hallway front door interior",
                      "entrance corridor door"],
    "court_hall": ["empty marble corridor building", "long hallway government building",
                   "institutional corridor windows"],
    "court_room": ["empty courtroom", "courtroom interior", "council chamber wooden"],
    "court_exterior": ["courthouse building exterior columns", "government building facade stairs",
                       "classical civic building"],
    "office_lawyer": ["law office desk books", "wooden desk library office",
                      "office bookshelf legal"],
    "office_registry": ["government office counter", "public office desk interior",
                        "administrative office counter"],
    "office_bank": ["bank counter interior", "bank branch office", "teller counter"],
    "funeral_hall": ["dim empty corridor carpet", "quiet hotel hallway dark",
                     "dim corridor doors"],
    "funeral_reception": ["empty dining hall tables", "banquet hall empty",
                          "traditional room low tables"],
    "funeral_parking": ["night parking lot wet asphalt", "empty parking lot night lights",
                        "parking lot rain night"],
    "funeral_altar": ["white chrysanthemum flowers", "white flowers memorial arrangement",
                      "white lily funeral flowers"],
    "medical_room_single": ["empty hospital room bed", "hospital ward interior",
                            "clinic room bed window"],
    "daily_cafe": ["empty cafe table window", "coffee shop interior empty",
                   "cafe interior morning light"],
    "daily_restaurant": ["empty restaurant table interior", "small diner interior",
                         "simple restaurant table"],
}


# ⚠️ Pexels 는 `Python-urllib/3.x` 라는 기본 이름표를 보면 403 으로 막는다.
#    (실측: 같은 주소를 이름표만 바꿔 부르면 200 이 온다.) 평범한 브라우저 이름표를 단다.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def get(url, key):
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


def has_people(alt):
    words = set("".join(c if c.isalnum() else " " for c in (alt or "").lower()).split())
    return bool(words & set(PEOPLE))


def score(p):
    """클수록 좋다. 해상도가 크고 가로로 넓은 것을 고른다."""
    w, h = p.get("width", 0), p.get("height", 0)
    if not w or not h:
        return 0
    ratio = w / h
    fit = 1.0 - min(1.0, abs(ratio - 16 / 9) / 1.2)     # 16:9 에 가까울수록 좋다
    return (min(w, 6000) / 6000) * 0.4 + fit * 0.6


def pick(code, key, used, dry=False):
    """이 배경에 쓸 사진 하나를 고른다. → (사진 정보, 쓴 검색어) 또는 (None, None)"""
    for q in QUERIES[code]:
        url = (f"{API}?query={urllib.parse.quote(q)}"
               f"&per_page=40&orientation=landscape&size=large")
        try:
            data = get(url, key)
        except Exception as e:
            print(f"    검색 실패({q}): {e}")
            continue
        cands = []
        for p in data.get("photos", []):
            if p["id"] in used:
                continue
            if has_people(p.get("alt", "")):
                continue
            cands.append(p)
        if dry:
            print(f"    [{q}] 후보 {len(cands)}장 / 전체 {len(data.get('photos', []))}장")
        if cands:
            cands.sort(key=score, reverse=True)
            return cands[0], q
    return None, None


def fetch(photo, path):
    """내려받아 16:9 로 잘라 맞추고 가볍게 흐리게 해서 저장한다."""
    src = photo["src"].get("original") or photo["src"]["large2x"]
    req = urllib.request.Request(src, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(raw)
    img = Image.open(tmp).convert("RGB")
    sw, sh = img.size
    s = max(W / sw, H / sh)
    img = img.resize((round(sw * s), round(sh * s)), Image.LANCZOS)
    left, top = (img.width - W) // 2, (img.height - H) // 2
    img = img.crop((left, top, left + W, top + H))
    img = img.filter(ImageFilter.GaussianBlur(PREBLUR))
    img.save(path, quality=90, subsampling=0)
    tmp.unlink(missing_ok=True)
    return sw, sh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="이미 있는 것도 다시 받는다")
    ap.add_argument("--only", default="", help="이 배경만 (쉼표로 여러 개)")
    ap.add_argument("--dry", action="store_true", help="받지 않고 후보 수만 본다")
    args = ap.parse_args()

    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        print("PEXELS_API_KEY 가 없다.", file=sys.stderr)
        return 2

    codes = [c.strip() for c in args.only.split(",") if c.strip()] or list(QUERIES)
    OUT.mkdir(parents=True, exist_ok=True)
    credits_path = OUT / "credits.json"
    credits = {}
    if credits_path.exists():
        try:
            credits = json.loads(credits_path.read_text(encoding="utf-8"))
        except Exception:
            credits = {}
    used = {v["pexels_id"] for v in credits.values() if isinstance(v, dict)}

    got, skip, fail = 0, 0, []
    for code in codes:
        if code not in QUERIES:
            print(f"  {code}: 검색어가 정의돼 있지 않다"); fail.append(code); continue
        path = OUT / f"{code}.jpg"
        if path.exists() and not args.force:
            skip += 1
            continue
        print(f"  {code}")
        photo, q = pick(code, key, used, dry=args.dry)
        if args.dry:
            continue
        if not photo:
            print("    사람 없는 사진을 못 찾았다"); fail.append(code); continue
        try:
            sw, sh = fetch(photo, path)
        except Exception as e:
            print(f"    내려받기 실패: {e}"); fail.append(code); continue
        used.add(photo["id"])
        credits[code] = {"pexels_id": photo["id"], "url": photo.get("url", ""),
                         "photographer": photo.get("photographer", ""),
                         "alt": photo.get("alt", ""), "query": q,
                         "source": f"{sw}x{sh}"}
        print(f"    {sw}x{sh} · {photo.get('photographer','')} · \"{q}\"")
        got += 1

    if not args.dry:
        credits_path.write_text(json.dumps(credits, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
    print(f"\n{got}장 받음 · {skip}장 건너뜀(이미 있음) · 실패 {len(fail)}"
          + (f" → {', '.join(fail)}" if fail else ""))
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
