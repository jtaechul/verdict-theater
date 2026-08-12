#!/usr/bin/env python3
"""배경 사진을 두 창고(Pixabay·Pexels)에서 받아오는지 본다. 인터넷 0회 · 0원 · 1초.

    python3 tools/bg_source_test.py

왜 이 검사가 있는가 (2026-08-12)
    손님 지적: "왜 자꾸 픽사베이 API 썼다가 픽셀스 썼다가 왔다 갔다 하냐.
                열쇠 둘 다 넣어놨으니 앞으로 안 된다는 말 하지 마라."

    맞는 지적이었다. Pixabay 는 **소리** 만 막혀 있었는데(2026-08-09 실측 403),
    그 일로 "Pixabay 는 안 된다" 는 인상이 남아 **사진까지 안 쓰고 있었다.**
    Pixabay 사진 API 는 한 번도 막힌 적이 없다.

    이 검사가 지키는 약속은 하나다 — **한쪽이 막혀도 배경 받기는 안 멈춘다.**
    창고를 하나만 보게 되돌리거나, 한 창고의 오류가 전체를 세우면 여기서 걸린다.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import bg_fetch as bf                                 # noqa: E402

ok = True


def bad(msg):
    global ok
    ok = False
    print(f"   ❌ {msg}")


# ── 두 창고가 진짜로 주는 것과 같은 모양의 가짜 답 ──────────────
PEXELS_JSON = {"photos": [
    {"id": 111, "width": 4000, "height": 2250, "alt": "empty wooden hall",
     "url": "https://pexels.com/p/111", "photographer": "Kim",
     "src": {"original": "https://px/111-orig.jpg", "large2x": "https://px/111-2x.jpg",
             "medium": "https://px/111-med.jpg"}},
    {"id": 222, "width": 3000, "height": 2000, "alt": "a man sitting at a desk",
     "url": "https://pexels.com/p/222", "photographer": "Lee",
     "src": {"original": "https://px/222-orig.jpg", "medium": "https://px/222-med.jpg"}},
]}
PIXABAY_JSON = {"hits": [
    {"id": 333, "imageWidth": 5000, "imageHeight": 2812, "tags": "corridor, door, quiet",
     "pageURL": "https://pixabay.com/p/333", "user": "Park",
     "fullHDURL": "https://pb/333-hd.jpg", "largeImageURL": "https://pb/333-lg.jpg",
     "webformatURL": "https://pb/333-web.jpg", "previewURL": "https://pb/333-pre.jpg"},
    {"id": 444, "imageWidth": 2000, "imageHeight": 1333, "tags": "woman, portrait, smile",
     "pageURL": "https://pixabay.com/p/444", "user": "Choi",
     "largeImageURL": "https://pb/444-lg.jpg", "webformatURL": "https://pb/444-web.jpg"},
]}

CALLS = []
DEAD = set()


def fake_get(url, headers=None):
    """인터넷 대신. 어느 창고를 부르는지 주소로 가린다."""
    who = "pixabay" if "pixabay.com" in url else "pexels"
    CALLS.append(who)
    if who in DEAD:
        raise RuntimeError("HTTP Error 403: Forbidden")
    return PIXABAY_JSON if who == "pixabay" else PEXELS_JSON


bf.get = fake_get
BOTH = [("pixabay", "K1"), ("pexels", "K2")]

print("① 두 창고가 똑같은 모양으로 돌아오는가")
a = bf.search_pexels("court", "K")[0]
b = bf.search_pixabay("court", "K")[0]
need = {"key", "provider", "id", "alt", "width", "height", "thumb", "full", "page", "author"}
for name, rec in (("pexels", a), ("pixabay", b)):
    miss = need - set(rec)
    if miss:
        bad(f"{name} 에 빠진 칸: {sorted(miss)}")
if a["key"] != "pexels:111" or b["key"] != "pixabay:333":
    bad(f"표식이 이상하다: {a['key']} / {b['key']}")
elif not ok:
    pass
else:
    print(f"   ✅ {a['key']} / {b['key']} — 뒤쪽 코드는 어디서 왔는지 몰라도 된다")

print()
print("② 사람이 찍힌 사진은 두 창고 다 걸러진다")
# Pexels 는 alt("a man sitting"), Pixabay 는 tags("woman, portrait") 로 들어온다
CALLS.clear()
got, _ = bf.pick("court_hall", BOTH, set(), gkey="", dry=False)
picked = {p["key"] for p in bf.search_pexels("q", "K") + bf.search_pixabay("q", "K")
          if not bf.has_people(p["alt"])}
if picked != {"pexels:111", "pixabay:333"}:
    bad(f"사람 거르기가 두 창고에 똑같이 안 먹는다: {picked}")
else:
    print("   ✅ 222(man)·444(woman) 는 빠지고 111·333 만 남는다")

print()
print("③ 두 창고를 다 물어본다 (한 곳만 보고 끝내지 않는다)")
if {"pixabay", "pexels"} - set(CALLS):
    bad(f"한 곳만 불렀다: {sorted(set(CALLS))}")
else:
    print(f"   ✅ {' + '.join(sorted(set(CALLS)))}")

print()
print("④ ⭐ 한 창고가 막혀도 배경 받기는 안 멈춘다 (이 검사의 핵심)")
DEAD.add("pixabay")
CALLS.clear()
got, q = bf.pick("court_hall", BOTH, set(), gkey="", dry=False)
if not got:
    bad("Pixabay 가 403 이라고 배경을 통째로 못 받았다 — 손님이 금지한 바로 그 상황")
elif got["provider"] != "pexels":
    bad(f"막힌 창고에서 골랐다: {got}")
else:
    print(f"   ✅ Pixabay 403 → Pexels 로 계속 간다 ({got['key']})")

print()
print("⑤ 막힌 창고를 검색어마다 다시 두드리지 않는다 (헛되이 느려진다)")
n = CALLS.count("pixabay")
if n > 1:
    bad(f"막힌 창고를 {n}번 불렀다 — 한 번 실패하면 그 판에서는 빼야 한다")
else:
    print("   ✅ 한 번 실패하면 그 배경을 찾는 동안은 안 부른다")

print()
print("⑥ 반대쪽이 막혀도 마찬가지다")
DEAD.clear(); DEAD.add("pexels")
got, _ = bf.pick("court_hall", BOTH, set(), gkey="", dry=False)
if not got or got["provider"] != "pixabay":
    bad(f"Pexels 가 막히니 못 받는다: {got}")
else:
    print(f"   ✅ Pexels 403 → Pixabay 로 계속 간다 ({got['key']})")
DEAD.clear()

print()
print("⑦ 열쇠가 하나만 있어도 돌아간다 / 둘 다 없을 때만 멈춘다")
import os                                             # noqa: E402
saved = {k: os.environ.get(k) for k in ("PIXABAY_API_KEY", "PEXELS_API_KEY")}
try:
    os.environ.pop("PIXABAY_API_KEY", None)
    os.environ["PEXELS_API_KEY"] = "K2"
    if [n for n, _ in bf.live_sources()] != ["pexels"]:
        bad("Pexels 열쇠만 있는데 그것을 못 쓴다")
    os.environ.pop("PEXELS_API_KEY", None)
    os.environ["PIXABAY_API_KEY"] = "K1"
    if [n for n, _ in bf.live_sources()] != ["pixabay"]:
        bad("Pixabay 열쇠만 있는데 그것을 못 쓴다")
    os.environ.pop("PIXABAY_API_KEY", None)
    if bf.live_sources():
        bad("열쇠가 없는데 있다고 한다")
    if ok:
        print("   ✅ 하나만 있으면 그것으로, 둘 다 없을 때만 멈춘다")
finally:
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

print()
print("⑧ 예전 기록(pexels_id 만 적힌 것)도 '이미 쓴 사진' 으로 읽는가")
# credits.json 을 예전 모양으로 흉내 낸다 — 못 읽으면 같은 사진이 두 배경에 들어간다
old = {"court_room": {"pexels_id": 111, "photographer": "Kim"},
       "daily_cafe": {"key": "pixabay:333", "provider": "pixabay", "photo_id": 333}}
used = set()
for v in old.values():
    if v.get("key"):
        used.add(v["key"])
    elif v.get("pexels_id") is not None:
        used.add(f"pexels:{v['pexels_id']}")
if used != {"pexels:111", "pixabay:333"}:
    bad(f"예전 기록을 못 읽는다: {used}")
else:
    got, _ = bf.pick("court_hall", BOTH, used, gkey="", dry=False)
    if got is not None:
        bad(f"이미 쓴 사진을 또 골랐다: {got['key']}")
    else:
        print("   ✅ 예전 기록도 읽어서 같은 사진을 두 번 안 쓴다")

print()
print("⑨ 소스에 옛 모양(p['src']['medium'])이 남아 있지 않은가")
# 한 군데만 안 고치면 실제로 부를 때 KeyError 로 죽는다 — 미리 본다
src = (ROOT / "src" / "bg_fetch.py").read_text(encoding="utf-8")
for stale in ('["src"]["medium"]', '["src"].get("original")', 'photo["src"]',
              'data.get("photos", [])'):
    if stale in src:
        bad(f"옛 모양이 남아 있다: {stale}")
else:
    if ok:
        print("   ✅ 전부 새 모양(thumb·full·key)을 쓴다")

print()
print("⑩ 열쇠 값이 화면에 찍히지 않는가 (Pixabay 는 열쇠를 주소에 붙인다)")
DEAD.add("pixabay")
import io                                             # noqa: E402
import contextlib                                     # noqa: E402
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    bf.pick("court_hall", [("pixabay", "SUPERSECRET123")], set(), gkey="", dry=False)
DEAD.clear()
if "SUPERSECRET123" in buf.getvalue():
    bad("실패 메시지에 열쇠가 그대로 찍힌다 — 로그에 남으면 안 된다")
else:
    print("   ✅ 실패해도 열쇠는 안 찍힌다")

print()
print("⑪ ⭐ 필요한 배경을 **전부** 공짜로 받아올 수 있는가")
# ⚠️ 2026-08-12 — 영상이 요구하는 배경은 30종인데 검색어 표에는 18종뿐이었다.
#    나머지 12종은 [배경 받아오기] 를 눌러도 영원히 안 채워졌고, 영상에서는
#    회색으로 나가거나 AI 로 그려서 **값이 나갔다.** 표에 없으면 공짜 길이 없다.
sys.path.insert(0, str(ROOT / "src"))
import assets_gen as G                                # noqa: E402
need = list(G.BG_PLACE)
noq = [c for c in need if c not in bf.QUERIES]
now = [c for c in need if c not in bf.WANT]
if noq:
    bad(f"검색어가 없어 공짜로 못 받는 배경 {len(noq)}개: {', '.join(noq)}")
elif now:
    bad(f"제미나이가 볼 기준(WANT)이 없는 배경 {len(now)}개: {', '.join(now)}")
else:
    print(f"   ✅ 필요한 {len(need)}종 전부 검색어와 판단 기준이 있다 (전부 0원으로 받을 수 있다)")

print()
print("─" * 52)
print("✅ 배경 두 창고: 정상" if ok else "❌ 배경 두 창고: 문제 있음")
sys.exit(0 if ok else 1)
