#!/usr/bin/env python3
"""⭐ **장소 컷만** Pexels 무료 영상으로 채운다 (값 0원).

    python3 src/stock_video.py S93            없는 것만 받는다
    python3 src/stock_video.py S93 --dry      받지 않고 후보만 본다

⭐⭐⭐ 2026-09-17 손님: "Pexels videos 장소 컷에만 넣는 거 진행해!
   대신 우리의 색감은 입혀서 영상으로 제작하자."

왜 여기만인가
    빈 복도·창밖·법정 같은 **사람 없는 장소 컷**은 AI 로 그려 봐야 얼어붙은
    사진이고(장당 132원), Veo 로 사면 초당 118원이다. 그런데 이런 장면은
    무료 스톡에 진짜 실사 푸티지가 널려 있다 — **0원에 진짜로 움직인다.**
    ⚠️ 사람이 나오는 컷에는 **절대 안 쓴다.** 우리 등장인물 얼굴이 아니기
       때문이다 (핵심 규칙: 등장인물 외 사람은 화면에 안 나온다).

사람을 어떻게 막나 — 세 겹
    ① 검색어 자체에 'empty · no people' 을 넣는다
    ② 주소 슬러그로 거른다 — pexels 주소는
       `/video/a-man-walking-in-the-hallway-12345/` 처럼 **설명이 들어 있다.**
       거기에 사람 낱말이 있으면 버린다 (bg_fetch 의 낱말표를 그대로 쓴다)
    ③ **제미나이가 눈으로 본다** — 받은 영상에서 프레임을 뽑아 "사람이 있나"
       를 묻는다.
    ⚠️ ②만으로는 부족하다는 것을 이 저장소가 이미 배웠다. bg_fetch 주석:
       "법정 사진에 판사가, 변호사 사무실 사진에 사람이 앉아 있는 채로
        통과했다. 설명글은 사람이 붙인 것이라 사람이 찍혔어도 안 적혀 있을
        수 있다." 사진에서 겪은 일을 영상에서 되풀이하지 않는다.

우리 색감을 입힌다
    스톡 영상은 제각각이라 그대로 쓰면 AI 그림 컷과 색이 튄다 — 한 편 안에서
    섞이면 바로 들킨다. 그래서 받은 영상에 **우리 COLOR 규격**을 입힌다
    (warm neutral · 낮은 대비 · 살짝 든 블랙 · 낮은 채도).
        실측: 채도 252 → 204 · 최저 밝기 16 → 32 · 파랑 내려감

열쇠가 없으면
    조용히 아무것도 안 한다. 그 컷은 지금까지처럼 AI 그림 + 켄번즈로 간다.
    **값이 나가는 길이 아니므로 실패해도 손해가 없다.**
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

# ⭐ 두 곳에서 찾는다 — bg_fetch 가 사진에서 배운 것 그대로.
#    "후보가 두 배가 되니 '사람 없는 것' 을 고를 확률도 올라간다. 둘 다 공짜라
#     몇 개를 받든 값은 0원이다."
#    ⚠️ 하나가 없거나 막혀도 다른 쪽으로 계속 간다. 둘 다 없을 때만 안 한다.
PEXELS_API = "https://api.pexels.com/videos/search"
PIXABAY_API = "https://pixabay.com/api/videos/"
KEY_ENV = "PEXELS_API_KEY"
KEY_ENV2 = "PIXABAY_API_KEY"
W, H = 1080, 1920

# ⭐⭐⭐ 2026-09-19 — **이름표(User-Agent) 가 없어서 통째로 막히고 있었다.**
#    S93 실행 기록: pexels 검색도 403, pixabay 영상 내려받기도 403.
#    열쇠 문제로 보이지만 아니었다. 실측(같은 주소·틀린 열쇠로):
#        pexels  이름표 없음 → 403 Forbidden  ·  이름표 있음 → 401 (열쇠만 틀림)
#        pixabay 이름표 없음 → 403 Forbidden  ·  이름표 있음 → 404 (주소만 틀림)
#    즉 이름표가 없으면 **열쇠를 보여 줄 기회조차 없이** 문 앞에서 막힌다.
#    두 곳 다 방패(Cloudflare 등) 뒤에 있어 "파이썬이 왔다"(Python-urllib)
#    는 이름표를 그냥 거절한다.
#    → 바깥에 나가는 모든 요청은 **_open 하나**를 지난다. 두 벌로 두면
#      한쪽만 고쳐져 또 절반이 막힌다(이 저장소가 여러 번 당한 자리다).
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _open(url, headers=None, timeout=20, data=None):
    """바깥에 나가는 **단 하나의 문**. 늘 이름표를 붙인다."""
    h = {"User-Agent": UA}
    h.update(headers or {})
    return urllib.request.urlopen(
        urllib.request.Request(url, data=data, headers=h), timeout=timeout)

# ⭐ 우리 COLOR 규격을 ffmpeg 로 옮긴 것.
#    "warm neutral base, low overall contrast, slightly lifted blacks,
#     muted greens and cyans, natural unsaturated skin tones"
#    ⚠️ 글로 적힌 규격과 **같은 것**이어야 한다. 한쪽만 바꾸면 그림 컷과
#       스톡 컷의 색이 갈린다 — 섞이는 순간 들킨다.
GRADE = ("eq=saturation=0.72:contrast=0.93,"
         "colorbalance=rs=0.04:bs=-0.05,"
         "curves=all='0/0.045 0.5/0.5 1/0.98'")


def key():
    return os.environ.get(KEY_ENV, "").strip()


def _people_words():
    """사람 낱말표 — bg_fetch 에서 가져온다. 두 벌로 두면 한쪽만 고쳐진다."""
    try:
        import bg_fetch as BF
        return set(BF.PEOPLE_HARD) | set(BF.PEOPLE_SOFT)
    except Exception:                                        # noqa: BLE001
        # bg_fetch 를 못 부르면 **더 좁게** 막는다 (모르면 보수적으로)
        return {"man", "men", "woman", "women", "people", "person", "boy",
                "girl", "child", "kids", "family", "couple", "crowd", "he",
                "she", "portrait", "model", "worker", "student", "hand",
                "hands", "face"}


def slug_of(v):
    """pexels 주소에 들어 있는 설명 — `/video/a-man-in-a-hallway-123/`."""
    m = re.search(r"/video/([a-z0-9-]+?)-\d+/?$", str(v.get("url") or ""))
    return (m.group(1) if m else "").replace("-", " ")


def looks_human(v):
    """설명에 사람 낱말이 있는가 (첫 번째 그물).

    pexels 는 주소 슬러그가, pixabay 는 tags 가 설명이다 — 둘 다 `desc` 로
    맞춰 두고 **한 가지 잣대**로 본다.
    """
    d = v.get("desc")
    if d is None:                       # 옛 모양(원본 그대로)도 받아 준다
        d = slug_of(v)
    return bool(set(str(d).split()) & _people_words())


def _get(url, headers=None):
    with _open(url, headers) as r:
        return json.loads(r.read().decode("utf-8"))


def search_pexels(query, per=15):
    k = key()
    if not k:
        return []
    q = urllib.parse.urlencode({"query": query, "per_page": per,
                                "orientation": "portrait", "size": "medium"})
    try:
        got = _get(f"{PEXELS_API}?{q}", {"Authorization": k}).get("videos") or []
    except Exception as e:                                   # noqa: BLE001
        print(f"  ⚠️ pexels 검색을 못 했다 ({e})")
        return []
    # 주소 슬러그가 곧 설명이다 (`/video/a-man-in-a-hallway-123/`)
    return [{"desc": slug_of(v), "files": v.get("video_files") or [],
             "where": "pexels"} for v in got]


def search_pixabay(query, per=15):
    k = os.environ.get(KEY_ENV2, "").strip()
    if not k:
        return []
    q = urllib.parse.urlencode({"key": k, "q": query, "per_page": per,
                                "video_type": "film", "safesearch": "true"})
    try:
        got = _get(f"{PIXABAY_API}?{q}").get("hits") or []
    except Exception as e:                                   # noqa: BLE001
        print(f"  ⚠️ pixabay 검색을 못 했다 ({e})")
        return []
    out = []
    for h in got:
        vs = h.get("videos") or {}
        files = [{"link": f.get("url"), "width": f.get("width") or 0,
                  "height": f.get("height") or 0}
                 for f in vs.values() if f.get("url")]
        # tags 는 "office, desk, work" 같은 쉼표 글 — 설명으로 그대로 쓴다
        out.append({"desc": str(h.get("tags") or "").replace(",", " "),
                    "files": files, "where": "pixabay"})
    return out


def search(query, per=15):
    """두 창고를 합쳐서 돌려준다. 하나가 막혀도 다른 쪽으로 간다."""
    got = search_pexels(query, per) + search_pixabay(query, per)
    if not got:
        print("  ⚠️ 쓸 만한 후보가 없다 — 그림으로 갑니다")
    return got


def best_file(v):
    """세로에 가장 잘 맞는 파일 하나. 너무 작은 것은 버린다."""
    got = [f for f in (v.get("files") or v.get("video_files") or [])
           if (f.get("height") or 0) >= 1080 and f.get("link")]
    if not got:
        return None
    got.sort(key=lambda f: (f.get("height") or 0) >= (f.get("width") or 1),
             reverse=True)
    return got[0]


def grade_to(src, out, sec):
    """9:16 으로 잘라 맞추고 **우리 색감**을 입힌다. 길이도 맞춘다."""
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,"
          f"crop={W}:{H},{GRADE},fps=30")
    r = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", str(src),
         "-t", f"{max(1.0, float(sec)):.3f}", "-an", "-vf", vf,
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out)],
        capture_output=True, text=True)
    if r.returncode or not out.exists():
        print(f"  ⚠️ 색을 못 입혔다: {r.stderr[-160:]}")
        out.unlink(missing_ok=True)
        return False
    return True


def frame_of(mp4, png):
    """가운데 프레임 한 장 — 제미나이가 눈으로 볼 거리."""
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "0.5",
                    "-i", str(mp4), "-frames:v", "1", "-vf", "scale=512:-1",
                    str(png)], capture_output=True)
    return png.exists()


def has_person(png):
    """⭐ 제미나이가 **눈으로** 본다 — 사람이 있으면 True.

    ⚠️ 열쇠가 없으면 **True 를 돌려준다**(= 안 쓴다). 모를 때는 버리는 쪽이다 —
       사람이 섞여 나가는 것보다 그림으로 가는 것이 낫다.
    """
    # ⚠️ bg_fetch.judge() 를 쓰지 않는다 — 그것은 후보 12장을 격자로 만들어
    #    "이 장면에 맞는 것 하나" 를 고르는 함수다. 여기서 묻는 것은
    #    "이 한 장에 사람이 있나" 라 뜻이 다르다.
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        print("    (GEMINI_API_KEY 가 없어 눈으로 못 본다 — 이 컷은 그림으로)")
        return True
    return _ask(png)


def _ask(png):
    import base64
    model = os.environ.get("BG_JUDGE_MODEL", "gemini-3.1-flash-lite")
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key="
           f"{os.environ['GEMINI_API_KEY'].strip()}")
    body = {"contents": [{"parts": [
        {"text": "Is any person, human body part, or face visible in this "
                 "image, even small or blurred or in the background? "
                 "Answer with exactly one word: YES or NO."},
        {"inline_data": {"mime_type": "image/png",
                         "data": base64.b64encode(png.read_bytes()).decode()}},
    ]}]}
    try:
        with _open(url, {"Content-Type": "application/json"}, 30,
                   json.dumps(body).encode()) as r:
            t = json.loads(r.read().decode())
            said = (t["candidates"][0]["content"]["parts"][0]["text"]).strip()
            return not said.upper().startswith("NO")
    except Exception as e:                                   # noqa: BLE001
        print(f"    ⚠️ 눈으로 못 봤다 ({e}) — 이 컷은 그림으로")
        return True                                          # 모르면 버린다


def query_of(c):
    """그 컷 화면 묘사 → 검색어. 사람이 안 나오게 못을 박는다."""
    sc = re.sub(r"[^a-zA-Z ]", " ", str(c.get("scene") or ""))
    sc = " ".join(w for w in sc.split() if len(w) > 2)[:70]
    return f"{sc} empty no people"


def place_cuts(doc):
    """스톡을 쓸 컷 — **나레이션이고 사람이 한 명도 없는** 컷만."""
    out = []
    for c in doc.get("cuts") or []:
        narr = all(str(w) == "나레이션" for w, _ in (c.get("turns") or [[""]]))
        if narr and not (c.get("who") or []):
            out.append(c)
    return out


def fetch_one(c, out, dry=False):
    """컷 하나 — 후보를 세 겹 그물로 걸러 받아 색을 입힌다. (받았나, 까닭)"""
    q = query_of(c)
    got = search(q)
    if not got:
        return False, "후보가 없다"
    # ① 주소 설명으로 거른다 (값싼 그물 먼저)
    cand = [v for v in got if not looks_human(v)]
    dropped = len(got) - len(cand)
    if dry:
        return False, f"후보 {len(got)}개 · 설명으로 {dropped}개 버림"
    tmp = out.parent / f".{out.stem}.raw.mp4"
    png = out.parent / f".{out.stem}.png"
    for v in cand[:4]:                       # 위에서부터 네 개까지만 본다
        f = best_file(v)
        if not f:
            continue
        try:
            # ⚠️ urlretrieve 를 쓰면 안 된다 — 이름표를 붙일 자리가 없어
            #    CDN 이 403 으로 막는다(2026-09-19 에 이것으로 다 막혔다).
            with _open(f["link"], timeout=60) as r, open(tmp, "wb") as w:
                shutil.copyfileobj(r, w)
        except Exception as e:               # noqa: BLE001
            print(f"    ⚠️ 못 받았다 ({e})")
            continue
        # ② 색을 입혀 우리 규격으로 만든다
        if not grade_to(tmp, out, c.get("sec") or 5):
            continue
        # ③ 제미나이가 눈으로 본다 — 사람이 있으면 버린다
        if frame_of(out, png) and has_person(png):
            print(f"    · 사람이 보인다 — 버린다 ({v.get('desc', '')[:38]})")
            out.unlink(missing_ok=True)
            continue
        png.unlink(missing_ok=True)
        tmp.unlink(missing_ok=True)
        return True, f"{v.get('where', '')} · {v.get('desc', '')[:32]}"
    tmp.unlink(missing_ok=True)
    png.unlink(missing_ok=True)
    return False, f"쓸 만한 것이 없다 (후보 {len(got)} · 설명으로 {dropped} 버림)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sid", nargs="?", default="S90")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    sid = a.sid.upper()
    doc = json.loads((ROOT / "data" / "series" / f"{sid}.json")
                     .read_text(encoding="utf-8"))
    out_d = Path(a.out) if a.out else (ROOT / "out" / "stock")
    cuts = place_cuts(doc)
    print(f"⭐ 장소 컷 무료 실사 영상 — {sid} · {len(cuts)}컷 (값 0원)")
    if not (key() or os.environ.get(KEY_ENV2, "").strip()):
        print(f"  {KEY_ENV}/{KEY_ENV2} 가 없습니다 — 아무것도 안 합니다. "
              f"그 컷들은 지금까지처럼 그림 + 카메라 무빙으로 갑니다.")
        return 0
    made, skip = 0, 0
    for c in cuts:
        out = out_d / f"c{c['n']:02d}.mp4"
        if out.exists():
            skip += 1
            continue
        ok, why = fetch_one(c, out, a.dry)
        print(f"  컷{c['n']:>2} {'받음' if ok else '그림으로'} — {why}")
        made += 1 if ok else 0
    print(f"\n■ 받음 {made} · 그대로 씀 {skip} · "
          f"나머지는 그림으로 갑니다 (값 0원)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
