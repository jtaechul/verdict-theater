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
VARIANT = 1
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
    "home_living_day": ["living room sofa coffee table", "living room interior daylight sofa",
                        "apartment living room furniture"],
    "home_living_night": ["dark living room lamp night", "living room evening warm lamp",
                          "dim interior night sofa"],
    "home_kitchen": ["kitchen sink window interior", "small kitchen counter wooden",
                     "home kitchen interior"],
    "home_closet": ["wooden wardrobe clothes hanging", "closet clothes rail bedroom",
                    "old wardrobe interior"],
    "home_entrance": ["front door hallway interior", "apartment corridor door interior",
                      "entrance hall door"],
    "court_hall": ["office building corridor daylight", "long hallway windows interior",
                   "institutional hallway daylight"],
    "court_room": ["courtroom benches empty", "council chamber wooden seats",
                   "assembly hall wooden desks"],
    "court_exterior": ["courthouse building exterior columns", "city hall building exterior",
                       "government building facade street", "old civic building entrance steps"],
    "office_lawyer": ["office desk bookshelf documents", "wooden desk law books",
                      "study room desk books"],
    "office_registry": ["office counter documents desk", "reception counter office interior",
                        "public service counter"],
    # ⚠️ "bank interior counter" 로 찾으면 어두운 나무 대청이 잔뜩 나온다(교회처럼 보인다).
    #    창구의 핵심은 '카운터와 대기 의자' 이므로 그쪽으로 찾는다.
    "office_bank": ["office reception desk lobby", "service counter desk interior",
                    "reception desk waiting area", "bank interior counter"],
    "funeral_hall": ["dim corridor carpet doors", "quiet hallway warm light",
                     "hotel corridor dim"],
    "funeral_reception": ["banquet hall empty tables", "dining hall long tables",
                          "event hall tables chairs"],
    "funeral_parking": ["empty parking lot night", "parking garage interior cars",
                        "night street wet asphalt lights", "underground parking lot"],
    "funeral_altar": ["white chrysanthemum flowers", "white flowers arrangement dark",
                      "white lily bouquet"],
    "medical_room_single": ["hospital room bed empty", "hospital ward bed window",
                            "clinic patient room"],
    "daily_cafe": ["cafe interior table chairs", "coffee shop table window",
                   "cafe empty seats interior"],
    "daily_restaurant": ["restaurant table chairs interior", "diner interior table",
                         "dining table restaurant empty"],
}


# 제미나이가 후보를 볼 때 "이 장면이 맞나" 를 재는 기준.
# 배경 코드가 무엇을 뜻하는지 사람 말로 적어 둔다.
WANT = {
    "home_living_day": "the living room of an ordinary apartment in daytime, sofa and low table visible",
    "home_living_night": "a living room at night, lit only by a lamp, dark and quiet",
    "home_kitchen": "a small ordinary home kitchen with a counter and sink",
    "home_closet": "a wardrobe or closet with clothes, inside a bedroom",
    "home_entrance": "the small entryway or front door area of a home",
    "court_hall": "a long institutional corridor with daylight, like a courthouse or government building",
    "court_room": "a courtroom or formal chamber with wooden benches and desks",
    "court_exterior": "the exterior of a civic or courthouse building with columns or steps",
    "office_lawyer": "a lawyer's office: a wooden desk with documents and shelves of books",
    "office_registry": "a public service counter in a government office",
    "office_bank": "the interior of a bank branch with a teller counter",
    "funeral_hall": "a dim quiet corridor with closed doors, solemn atmosphere",
    "funeral_reception": "a large hall with rows of empty tables, like a banquet or reception room",
    "funeral_parking": "an outdoor parking lot at night",
    "funeral_altar": "white chrysanthemum or lily flowers, funeral flower arrangement",
    "medical_room_single": "a hospital room with a bed",
    "daily_cafe": "a cafe interior with a table by a window",
    "daily_restaurant": "a small restaurant or diner interior with a table",
}

# ⚠️ Pexels 는 `Python-urllib/3.x` 라는 기본 이름표를 보면 403 으로 막는다.
#    (실측: 같은 주소를 이름표만 바꿔 부르면 200 이 온다.) 평범한 브라우저 이름표를 단다.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def get(url, key):
    req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


# ── 제미나이가 후보를 눈으로 보고 고른다 ──────────────────────
# ⚠️ 처음에는 설명글(alt)에 사람 낱말이 있는지만 봤다. **그것으로는 부족했다** —
#    법정 사진에 판사가, 변호사 사무실 사진에 사람이 앉아 있는 채로 통과했다.
#    설명글은 사람이 붙인 것이라 사람이 찍혔어도 안 적혀 있을 수 있다.
#    이제 후보 12장을 번호 붙인 한 장의 판으로 만들어 제미나이에게 보여주고
#    "사람이 없고 이 장면에 맞는 것" 을 고르게 한다. 판이 한 장이라 호출도 한 번이다.
JUDGE_MODEL = os.environ.get("BG_JUDGE_MODEL", "gemini-3.1-flash-lite")
GEMINI = "https://generativelanguage.googleapis.com/v1beta"
GRID = (4, 3)               # 가로 4 × 세로 3 = 12장
TILE = 320


def contact_sheet(images):
    """후보 그림들을 번호 붙인 한 장으로 붙인다."""
    from PIL import ImageDraw
    cols, rows = GRID
    th = round(TILE * 9 / 16)
    sheet = Image.new("RGB", (cols * TILE, rows * (th + 26)), (20, 20, 24))
    d = ImageDraw.Draw(sheet)
    for i, im in enumerate(images[:cols * rows]):
        x, y = (i % cols) * TILE, (i // cols) * (th + 26)
        sheet.paste(im.resize((TILE, th), Image.LANCZOS), (x, y))
        d.rectangle([x, y + th, x + TILE, y + th + 26], fill=(20, 20, 24))
        d.text((x + 6, y + th + 5), f"#{i + 1}", fill=(255, 255, 255))
    return sheet


def judge(code, photos, key):
    """후보 중 몇 번이 좋은지 제미나이에게 묻는다. → 뽑힌 사진 또는 None."""
    import base64
    import io
    thumbs = []
    keep = []
    for p in photos[:GRID[0] * GRID[1]]:
        try:
            req = urllib.request.Request(p["src"]["medium"], headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                thumbs.append(Image.open(io.BytesIO(r.read())).convert("RGB"))
            keep.append(p)
        except Exception:
            continue
    if not thumbs:
        return None
    buf = io.BytesIO()
    contact_sheet(thumbs).save(buf, format="JPEG", quality=82)

    want = WANT.get(code, code.replace("_", " "))
    prompt = (
        f"This contact sheet has {len(thumbs)} numbered candidate photos.\n"
        f"Pick the ONE best photo to use as a blurred background plate for a drama scene:\n"
        f"  {want}\n\n"
        "HARD REQUIREMENTS — reject a photo if any is true:\n"
        "  - any person, face, body, or human silhouette is visible, even small or in the distance\n"
        "  - it is obviously a different kind of place than described\n"
        "  - it is dominated by large readable text or a logo\n"
        "Prefer: calm, muted colour, ordinary and lived-in, clear sense of the place,\n"
        "a composition that still reads when the centre third is cropped for a vertical video.\n\n"
        'Answer with JSON only: {"best": <number, or -1 if every candidate fails>, '
        '"why": "<8 words max>"}'
    )
    body = {"contents": [{"role": "user", "parts": [
        {"text": prompt},
        {"inlineData": {"mimeType": "image/jpeg",
                        "data": base64.b64encode(buf.getvalue()).decode()}}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    req = urllib.request.Request(f"{GEMINI}/models/{JUDGE_MODEL}:generateContent?key={key}",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        res = json.loads(r.read().decode())
    txt = "".join(pt.get("text", "") for pt
                  in res["candidates"][0]["content"]["parts"])
    ans = json.loads(txt)
    n = int(ans.get("best", -1))
    if n < 1 or n > len(keep):
        print(f"    제미나이: 쓸 만한 것이 없다 ({ans.get('why','')})")
        return None
    print(f"    제미나이 선택 #{n} — {ans.get('why','')}")
    return keep[n - 1]


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


def pick(code, key, used, gkey="", dry=False):
    """이 배경에 쓸 사진 하나를 고른다. → (사진 정보, 쓴 검색어) 또는 (None, None)

    검색어 목록을 위에서부터 훑으며 후보를 모으고, 설명글로 1차로 거른 뒤
    제미나이가 그림을 직접 보고 고른다. 제미나이 키가 없으면 1차 결과만 쓴다."""
    pool, qs = [], []
    for q in QUERIES[code]:
        url = (f"{API}?query={urllib.parse.quote(q)}"
               f"&per_page=40&orientation=landscape&size=large")
        try:
            data = get(url, key)
        except Exception as e:
            print(f"    검색 실패({q}): {e}")
            continue
        for p in data.get("photos", []):
            if p["id"] in used or any(x["id"] == p["id"] for x in pool):
                continue
            if has_people(p.get("alt", "")):
                continue
            pool.append(p)
            qs.append(q)
        if len(pool) >= GRID[0] * GRID[1]:
            break

    if dry:
        print(f"    후보 {len(pool)}장")
        return None, None
    if not pool:
        return None, None

    order = sorted(range(len(pool)), key=lambda i: score(pool[i]), reverse=True)
    pool = [pool[i] for i in order]
    qs = [qs[i] for i in order]
    if gkey:
        try:
            got = judge(code, pool, gkey)
        except Exception as e:
            print(f"    제미나이 심사 실패({e}) — 설명글 기준으로만 고른다")
            got = None
        if got:
            return got, qs[[p["id"] for p in pool].index(got["id"])]
        return None, None
    return pool[0], qs[0]


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
    ap.add_argument("--variant", type=int, default=1,
                    help="몇 번째 벌로 저장할지. 2 면 funeral_hall-2.jpg "
                         "(회차마다 다른 배경을 쓰려고 여러 벌을 받아 둔다. 값 0원)")
    args = ap.parse_args()
    global VARIANT
    VARIANT = max(1, args.variant)

    key = os.environ.get("PEXELS_API_KEY", "").strip()
    if not key:
        print("PEXELS_API_KEY 가 없다.", file=sys.stderr)
        return 2

    gkey = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gkey:
        print("  (GEMINI_API_KEY 가 없어 그림을 눈으로 확인하지 않는다 — 사람이 섞일 수 있다)")
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
        # ⭐ 회차마다 배경을 바꾸려면 같은 자리의 사진이 여러 장 있어야 한다.
        #    --variant 2 로 받으면 funeral_hall-2.jpg 로 저장되고,
        #    render.py 가 회차 번호로 돌려 쓴다. Pexels 라 몇 장을 받든 0원이다.
        path = OUT / (f"{code}.jpg" if VARIANT <= 1 else f"{code}-{VARIANT}.jpg")
        if path.exists() and not args.force:
            skip += 1
            continue
        print(f"  {code}")
        photo, q = pick(code, key, used, gkey=gkey, dry=args.dry)
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
