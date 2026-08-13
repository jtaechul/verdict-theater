#!/usr/bin/env python3
"""배경 사진을 **Pixabay 와 Pexels 두 곳에서** 받아 온다.

    python3 src/bg_fetch.py              없는 것만 받는다
    python3 src/bg_fetch.py --force      전부 다시 받는다
    python3 src/bg_fetch.py --only home_living_day
    python3 src/bg_fetch.py --dry        받지 않고 후보만 본다
    python3 src/bg_fetch.py --source pixabay      한 곳만 쓰고 싶을 때

    열쇠는 둘 다 넣어도 되고 하나만 넣어도 된다.
      PIXABAY_API_KEY  … Pixabay 사진 검색
      PEXELS_API_KEY   … Pexels 사진 검색
    **하나가 없거나 막혀도 다른 쪽으로 계속 간다.** 둘 다 없을 때만 멈춘다.

왜 만들었나
    배경 18종을 사람이 하나씩 만들어 올리는 일이 너무 번거롭다.
    두 곳 다 상업적 사용이 자유롭고(출처 표기도 의무가 아니다) 사진 품질이 고르다.
    검색 → 고르기 → 잘라 맞추기 → 흐리게 하기까지 전부 여기서 한다.

⚠️ 왜 Pixabay 가 빠져 있었나 (2026-08-12 에 바로잡음)
    손님 지적: "왜 자꾸 픽사베이 API 썼다가 픽셀스 썼다가 왔다 갔다 하냐."
    기록을 뒤져 보니 **손님 말이 맞고, 제 설명이 부실했다.** 사실은 이렇다.

      · Pixabay 는 원래 **효과음(소리)** 받는 데 썼다 (tools/get_sfx.py).
      · 2026-08-09 에 손님 열쇠로 실측한 결과가 남아 있다:
            사진 검색 (공식 주소)   → 정상
            영상 검색 (공식 주소)   → 정상
            소리 검색 (/api/audio/) → 403 (막힘)
        즉 **열쇠는 멀쩡했고 '소리' 만 막혔다.** 소리 주소는 Pixabay 웹사이트
        내부용이라 일반 열쇠에 권한을 안 준다.
      · 그래서 **소리만** Freesound 로 옮겼는데, 그때 "Pixabay 는 안 된다" 는
        인상만 남고 **사진은 멀쩡하다는 사실이 같이 묻혔다.**
      · 배경(사진)은 그와 별개로 처음부터 Pexels 로 만들었다 (2026-08-10).

    정리하면 Pixabay 사진 API 는 한 번도 막힌 적이 없다. 안 쓴 것이 손해였다.
    이제 두 곳에서 같이 찾는다. 후보가 두 배가 되니 '사람 없는 사진' 을 고를
    확률도 올라간다. 둘 다 공짜라 몇 장을 받든 값은 0원이다.

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
PEXELS_API = "https://api.pexels.com/v1/search"
PIXABAY_API = "https://pixabay.com/api/"
SOURCES = ("pixabay", "pexels")     # 찾는 순서 (둘 다 훑는다)
TEST_QUERY = "empty office interior"    # --probe 로 두드려 볼 때 쓰는 말

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

    # ⚠️ 2026-08-12 — 아래 12종은 **검색어가 아예 없었다.** 그래서 [배경 받아오기]
    #    를 눌러도 이 자리들은 영원히 안 채워졌고, 영상에서는 회색으로 나가거나
    #    AI 로 그려서 **값이 나갔다.** (필요 30종 중 18종만 표에 있었다)
    #    어차피 흐려서 깔리므로 나라보다 빛과 결이 중요하다 — 위와 같은 기준.
    "medical_room_shared": ["hospital ward beds row", "hospital room multiple beds",
                            "clinic ward interior beds"],
    "medical_nursing_hall": ["nursing home corridor handrail", "care home hallway interior",
                             "hospital corridor handrail wall"],
    "medical_waiting": ["hospital waiting area chairs", "clinic waiting room seats",
                        "waiting room empty chairs interior"],
    "home_bedroom": ["bedroom bed window daylight", "simple bedroom interior bed",
                     "small bedroom interior quiet"],
    "office_community": ["public office counter interior", "government office desks interior",
                         "administrative office counter"],
    # ⚠️ 2026-08-13 — 이 하나만 계속 실패했다. 제미나이가 후보를 전부 물리쳤다:
    #    "All candidates contain people or readable text."
    #    당연하다 — '시장 골목' 으로 찾으면 장 보는 사람이 안 찍힌 사진이 거의 없다.
    #    그래서 **문 열기 전·닫은 뒤의 빈 시장**을 먼저 찾는다. 사람이 없는 시각의
    #    시장은 골목·차양·좌판이 그대로 보여서 배경으로는 오히려 더 낫다.
    #    (원래 검색어는 뒤에 남겨 둔다 — 앞의 것으로 못 찾으면 그때 쓴다)
    "daily_market": ["empty market stalls early morning", "closed market shutters alley",
                     "covered market arcade empty", "market stall crates produce",
                     "traditional market alley stalls", "street market narrow alley",
                     "market street awnings stalls"],
    # 반찬가게에 딱 맞는 사진은 없다 — '반찬통이 늘어선 진열대' 로 노린다
    "daily_sidedish": ["deli counter food containers", "food stall display containers",
                       "market food shop display"],
    "daily_park": ["park bench trees empty", "empty park bench path",
                   "park path benches quiet"],
    # 납골당도 흔치 않다 — '벽면 가득한 추모 명패' 가 핵심 인상이다
    "etc_columbarium": ["memorial wall niches", "cemetery memorial wall plaques",
                        "stone memorial wall rows"],
    "etc_country_yard": ["rural farmhouse yard", "old country house courtyard",
                         "village house yard"],
    "etc_busstop": ["bus stop shelter street", "empty bus stop bench",
                    "roadside bus stop"],
    "etc_alley_night": ["narrow alley night lights", "dark alley street night",
                        "night alley wet street"],
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
    "medical_room_shared": "a hospital ward with several beds in a row",
    "medical_nursing_hall": "a nursing-home or hospital corridor with a handrail on the wall",
    "medical_waiting": "a hospital or clinic waiting area with rows of empty chairs",
    "home_bedroom": "an ordinary bedroom with a bed, quiet daylight",
    "office_community": "a public administrative office with a service counter and desks",
    "daily_market": "a narrow traditional market alley lined with stalls and awnings",
    "daily_sidedish": "a shop counter with rows of food containers on display, like a deli",
    "daily_park": "an empty park bench on a path among trees",
    "etc_columbarium": "a wall of memorial niches or plaques, solemn and orderly",
    "etc_country_yard": "the dirt yard of an old rural farmhouse",
    "etc_busstop": "a roadside bus stop shelter with an empty bench",
    "etc_alley_night": "a narrow alley at night lit by scattered lights",
}

# ⚠️ Pexels 는 `Python-urllib/3.x` 라는 기본 이름표를 보면 403 으로 막는다.
#    (실측: 같은 주소를 이름표만 바꿔 부르면 200 이 온다.) 평범한 브라우저 이름표를 단다.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8"))


# ── 두 곳에서 똑같은 모양으로 받아 온다 ──────────────────────
# 뒤쪽(사람 거르기·점수·제미나이 심사·내려받기)은 어디서 왔는지 몰라도 되게
# **한 가지 모양**으로 맞춰 둔다. 새 사진 창고를 붙일 때도 여기만 늘리면 된다.
#   key    : "pixabay:12345"  — 같은 사진을 두 배경에 쓰지 않으려는 표식
#   alt    : 설명글 (사람 낱말 거르기에 쓴다)
#   thumb  : 제미나이에게 보여줄 작은 그림 주소
#   full   : 실제로 내려받을 큰 그림 주소

def search_pexels(q, key):
    url = (f"{PEXELS_API}?query={urllib.parse.quote(q)}"
           f"&per_page=40&orientation=landscape&size=large")
    out = []
    for p in get(url, {"Authorization": key}).get("photos", []):
        src = p.get("src") or {}
        full = src.get("original") or src.get("large2x") or src.get("large")
        thumb = src.get("medium") or src.get("small") or full
        if not full:
            continue
        out.append({"key": f"pexels:{p['id']}", "provider": "pexels", "id": p["id"],
                    "alt": p.get("alt", ""), "width": p.get("width", 0),
                    "height": p.get("height", 0), "thumb": thumb, "full": full,
                    "page": p.get("url", ""), "author": p.get("photographer", "")})
    return out


def search_pixabay(q, key):
    # ⚠️ Pexels 와 달리 열쇠를 주소에 붙인다(헤더가 아니다). 그래서 열쇠 값이
    #    로그에 찍히지 않도록 실패해도 주소를 그대로 출력하지 않는다.
    url = (f"{PIXABAY_API}?key={urllib.parse.quote(key)}&q={urllib.parse.quote(q)}"
           f"&image_type=photo&orientation=horizontal&per_page=40&safesearch=true")
    out = []
    for p in get(url).get("hits", []):
        full = p.get("fullHDURL") or p.get("largeImageURL") or p.get("webformatURL")
        if not full:
            continue
        out.append({"key": f"pixabay:{p['id']}", "provider": "pixabay", "id": p["id"],
                    # tags 는 "office, desk, work" 같은 쉼표 글이다 — alt 와 같게 쓴다
                    "alt": p.get("tags", ""), "width": p.get("imageWidth", 0),
                    "height": p.get("imageHeight", 0),
                    "thumb": p.get("webformatURL") or p.get("previewURL") or full,
                    "full": full, "page": p.get("pageURL", ""),
                    "author": p.get("user", "")})
    return out


FINDERS = {"pexels": search_pexels, "pixabay": search_pixabay}
KEY_ENV = {"pexels": "PEXELS_API_KEY", "pixabay": "PIXABAY_API_KEY"}


def live_sources(want=SOURCES):
    """열쇠가 있는 창고만 골라 [(이름, 열쇠), …] 로 돌려준다."""
    return [(s, os.environ.get(KEY_ENV[s], "").strip())
            for s in want if os.environ.get(KEY_ENV[s], "").strip()]


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
BATCH = GRID[0] * GRID[1]   # 한 번에 보여 주는 후보 수
ROUNDS = 3                  # 다 물리면 몇 판까지 다시 보여 줄지 (12 x 3 = 36장)


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
            req = urllib.request.Request(p["thumb"], headers={"User-Agent": UA})
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


def pick(code, sources, used, gkey="", dry=False):
    """이 배경에 쓸 사진 하나를 고른다. → (사진 정보, 쓴 검색어) 또는 (None, None)

    검색어 목록을 위에서부터 훑되 **창고마다 다 물어본다.** 설명글로 1차로 거른 뒤
    제미나이가 그림을 직접 보고 고른다. 제미나이 키가 없으면 1차 결과만 쓴다.

    ⭐ 한 창고가 막혀도(403·정지·열쇠 만료) 그 창고만 건너뛰고 계속 간다.
       두 곳이 다 조용할 때만 빈손으로 돌아간다."""
    pool, qs = [], []
    seen = set()
    dead = set()
    for q in QUERIES[code]:
        for name, key in sources:
            if name in dead:
                continue
            try:
                found = FINDERS[name](q, key)
            except Exception as e:
                # 열쇠가 막힌 창고를 검색어마다 다시 두드리지 않는다(느려지기만 한다)
                print(f"    {name} 검색 실패({q}): {e} — 이 창고는 건너뛴다")
                dead.add(name)
                continue
            for p in found:
                if p["key"] in used or p["key"] in seen:
                    continue
                if has_people(p["alt"]):
                    continue
                seen.add(p["key"])
                pool.append(p)
                qs.append(q)
        # ⚠️ 2026-08-13 — 여기가 12장만 모으고 멈췄다. 그런데 제미나이는 그 12장을
        #    **한 번에 보고 전부 물리칠 수 있다**("사람이나 글자가 들어 있다").
        #    그러면 뒤쪽 검색어는 써 보지도 못하고 그 배경은 실패로 끝났다.
        #    실제로 daily_market 하나가 그렇게 계속 실패했다.
        #    이제 세 판 분량(36장)까지 모아 두고, 아래에서 12장씩 나눠 물어본다.
        if len(pool) >= BATCH * ROUNDS:
            break

    if dry:
        by = {}
        for p in pool:
            by[p["provider"]] = by.get(p["provider"], 0) + 1
        print(f"    후보 {len(pool)}장"
              + (f" ({', '.join(f'{k} {v}' for k, v in sorted(by.items()))})" if by else ""))
        return None, None
    if not pool:
        return None, None

    order = sorted(range(len(pool)), key=lambda i: score(pool[i]), reverse=True)
    pool = [pool[i] for i in order]
    qs = [qs[i] for i in order]
    if gkey:
        # 12장씩 나눠 물어본다. 한 판이 통째로 물러나도 다음 판이 남아 있다.
        for start in range(0, len(pool), BATCH):
            batch = pool[start:start + BATCH]
            if not batch:
                break
            try:
                got = judge(code, batch, gkey)
            except Exception as e:
                print(f"    제미나이 심사 실패({e}) — 설명글 기준으로만 고른다")
                return pool[0], qs[0]
            if got:
                return got, qs[[p["key"] for p in pool].index(got["key"])]
            if start + BATCH < len(pool):
                print(f"    {len(batch)}장 다 물렀다 — 다음 {min(BATCH, len(pool) - start - BATCH)}장으로 다시 본다")
        return None, None
    return pool[0], qs[0]


def fetch(photo, path):
    """내려받아 16:9 로 잘라 맞추고 가볍게 흐리게 해서 저장한다."""
    req = urllib.request.Request(photo["full"], headers={"User-Agent": UA})
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
    ap.add_argument("--source", default=",".join(SOURCES),
                    help="쓸 사진 창고 (pixabay,pexels). 기본은 둘 다.")
    ap.add_argument("--probe", action="store_true",
                    help="창고가 열리는지만 한 번씩 두드려 본다 (안 받는다 · 0원)")
    args = ap.parse_args()
    global VARIANT
    VARIANT = max(1, args.variant)

    want = [s.strip().lower() for s in args.source.split(",") if s.strip()]
    bad = [s for s in want if s not in FINDERS]
    if bad:
        print(f"모르는 사진 창고: {', '.join(bad)}", file=sys.stderr)
        return 2
    sources = live_sources(want)
    if not sources:
        # 둘 다 없을 때만 멈춘다. 하나만 있으면 그것으로 간다.
        print("사진 창고 열쇠가 하나도 없다. "
              f"{' 또는 '.join(KEY_ENV[s] for s in want)} 중 하나는 있어야 한다.",
              file=sys.stderr)
        return 2
    print(f"  사진 창고: {', '.join(n for n, _ in sources)}"
          + ("" if len(sources) == len(want)
             else f"  (열쇠 없어 뺌: {', '.join(s for s in want if s not in dict(sources))})"))

    if args.probe:
        # 열쇠가 진짜로 열리는지 한 번씩만 두드려 본다. 내려받지 않으니 0원이고
        # 몇 초면 끝난다. (2026-08-12: Pixabay 열쇠가 사진에도 되는지 확인용)
        alive = 0
        for name, key in sources:
            try:
                n = len(FINDERS[name](TEST_QUERY, key))
                print(f"  {name}: 열린다 — '{TEST_QUERY}' 로 {n}장 찾음")
                alive += 1
            except Exception as e:
                # 열쇠 값이 주소에 들어가는 창고가 있으므로 예외 글에서 지운다
                print(f"  {name}: 막혔다 — {str(e).replace(key, '***')}")
        print(f"\n열린 창고 {alive}곳 / 열쇠 있는 곳 {len(sources)}곳")
        return 0 if alive else 1

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
    # 이미 다른 배경이 쓴 사진은 다시 안 쓴다. 예전 기록에는 'pexels_id' 만
    # 적혀 있으므로 그것도 읽어서 "pexels:12345" 모양으로 맞춰 준다.
    used = set()
    for v in credits.values():
        if not isinstance(v, dict):
            continue
        if v.get("key"):
            used.add(v["key"])
        elif v.get("pexels_id") is not None:
            used.add(f"pexels:{v['pexels_id']}")

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
        photo, q = pick(code, sources, used, gkey=gkey, dry=args.dry)
        if args.dry:
            continue
        if not photo:
            print("    사람 없는 사진을 못 찾았다"); fail.append(code); continue
        try:
            sw, sh = fetch(photo, path)
        except Exception as e:
            print(f"    내려받기 실패: {e}"); fail.append(code); continue
        used.add(photo["key"])
        credits[code] = {"key": photo["key"], "provider": photo["provider"],
                         "photo_id": photo["id"], "url": photo.get("page", ""),
                         "photographer": photo.get("author", ""),
                         "alt": photo.get("alt", ""), "query": q,
                         "source": f"{sw}x{sh}"}
        print(f"    {photo['provider']} · {sw}x{sh} · "
              f"{photo.get('author','')} · \"{q}\"")
        got += 1

    if not args.dry:
        credits_path.write_text(json.dumps(credits, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")
    print(f"\n{got}장 받음 · {skip}장 건너뜀(이미 있음) · 실패 {len(fail)}"
          + (f" → {', '.join(fail)}" if fail else ""))
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
