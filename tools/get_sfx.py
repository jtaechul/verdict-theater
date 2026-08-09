#!/usr/bin/env python3
"""효과음을 **Pixabay 에서 받아 온다.** (값 0원 · 마음대로 써도 되는 소리만)

    python3 tools/get_sfx.py footsteps --query "footsteps hall"
    python3 tools/get_sfx.py footsteps --query "footsteps hall" --install best

왜 (2026-08-08 손님 지적: "법정에서 걸음소리 좆같아")
    지금 발소리는 **분당 131걸음** — 법정이 아니라 뛰다시피 하는 속도다.
    ⚠️ 나는 "Pixabay API 에는 소리가 없다" 고 단정했는데 **틀렸다.**
       문서 페이지에는 사진·영상만 적혀 있지만, 실제로 `/api/audio/` 가 살아 있다
       (없는 주소는 404 인데 이 주소는 '키가 없다'(400) 고 답한다 — 실측).
       문서에 없다고 없는 것이 아니다. 두드려 보고 판단할 것.

무엇을 하나
    1. Pixabay 에서 소리를 검색한다 (열쇠: PIXABAY_API_KEY)
    2. 후보마다 **걸음 속도(분당)·묵직함·길이**를 기계가 재서 점수를 매긴다
    3. 후보를 이어 붙인 '들어보기' 파일을 만든다 (사람이 귀로 고르라고)
    4. --install best|번호 를 주면 assets/sfx/{이름}.mp3 로 넣는다
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sfx_quality import BEEP_TONALITY, tone_ratio       # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SFX = ROOT / "assets" / "sfx"
PIXABAY = "https://pixabay.com/api/audio/"
FREESOUND = "https://freesound.org/apiv2/search/text/"

# 법정 걸음. 사람이 천천히 걸으면 분당 60~80걸음이다(지금 것은 131 — 그래서 싸구려다).
WANT_BPM = (55, 85)

# ── 소리마다 '무엇이 맞는 소리인가' 기준 ────────────────────────────
#    2026-08-09: 여기 있던 clock·phone·heartbeat·monitor 는 **소리가 아니라
#    기계가 만든 삑** 이었다(1400·1000·52·880Hz 순수음). 손님이 6분30초에서
#    "삑 삑" 을 듣고 빼 달라고 하셨다. 그래서 진짜 녹음으로 받아 온다.
#      bpm        — 규칙적으로 울리는 소리의 분당 횟수(없으면 안 본다)
#      beats_min  — 최소 몇 번은 울려야 그 소리로 들린다
#      bright     — 이보다 높으면 얇고 쨍한 소리라 감점
PROFILES = {
    "footsteps": {"query": "footsteps hall walking", "bpm": (55, 85),
                  "beats_min": 3, "bright": 1200, "trim": 6.0,
                  "what": "법정 복도 걸음"},
    "clock":     {"query": "wall clock ticking", "bpm": (50, 130),
                  "beats_min": 3, "bright": 3000, "trim": 5.0,
                  "what": "벽시계 초침 (똑딱)"},
    # ⚠️ 2026-08-09: 처음 받아 온 것은 1.8초에 여섯 번 울리는 **쨍한 전자음**이었다
    #    (4kHz 위에 힘의 42%). 삑 소리는 아니지만 손님이 싫어하신 그 성질이다.
    #    그래서 '쇠종이 울리는 옛 전화' 쪽으로 찾고, 얇고 쨍하면 크게 깎는다(bright 낮춤).
    #    ⚠️ 'rotary telephone bell ringing analog' 로 찾았더니 **한 건도 안 나왔다**
    #       (마음대로 쓸 수 있는 소리 + 길이 조건까지 걸리면 너무 좁다).
    #       찾는 말은 넓게 두고, 고르는 자(bright)를 조여서 따뜻한 쪽을 뽑는다.
    "phone":     {"query": "telephone bell ring", "bpm": None,
                  "beats_min": 0, "bright": 1200, "trim": 4.0,
                  "what": "전화벨 (쇠종이 울리는 쪽으로)"},
    "heartbeat": {"query": "human heartbeat chest", "bpm": (45, 100),
                  "beats_min": 2, "bright": 800, "trim": 4.0,
                  "what": "심장 뛰는 소리"},
    "door":      {"query": "wooden door open close", "bpm": None,
                  "beats_min": 0, "bright": 2500, "trim": 3.0,
                  "what": "문 여닫는 소리"},
    "paper":     {"query": "paper document handling", "bpm": None,
                  "beats_min": 0, "bright": 6000, "trim": 3.0,
                  "what": "서류 넘기는 소리"},
    "stamp":     {"query": "rubber stamp on paper", "bpm": None,
                  "beats_min": 0, "bright": 3000, "trim": 2.0,
                  "what": "도장 찍는 소리"},
    "gavel":     {"query": "judge gavel wood", "bpm": None,
                  "beats_min": 0, "bright": 2000, "trim": 2.0,
                  "what": "의사봉 소리"},
}


def profile(name):
    return PROFILES.get(name, PROFILES["footsteps"])

# ⚠️ 2026-08-09 실측 — **Pixabay 소리 API 는 일반 열쇠로 안 열린다.**
#    같은 열쇠로 사진 검색·영상 검색은 정상(3건)인데 /api/audio/ 만 403 이다
#    (브라우저처럼 위장해도 같다). 주소는 살아 있지만 웹사이트 내부용이다.
#    그래서 소리는 **Freesound** 에서 받는다 — 여기는 공식 API 로 소리를 준다.
#    Pixabay 길은 남겨 둔다(나중에 열릴 수도 있고, 사진·영상에는 쓸 수 있다).
KEY_NAMES = {
    "freesound": ("FREESOUND_TOKEN", "FREESOUND_API_KEY", "FREESOUND_KEY", "FREESOUND"),
    "pixabay": ("PIXABAY_API_KEY", "PIXABAY_KEY", "PIXABAY_TOKEN", "PIXABAY"),
}


def api_key(source):
    for n in KEY_NAMES[source]:
        v = os.environ.get(n, "").strip()
        if v:
            return n, v
    return None, ""


# Pixabay 는 낯선 프로그램 이름을 막는 일이 있다(403). 브라우저처럼 보이게 한다.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def get(url, timeout=60, ua=UA):
    req = urllib.request.Request(url, headers={
        "User-Agent": ua,
        "Accept": "application/json, audio/mpeg, */*",
        "Accept-Language": "ko,en;q=0.8",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def diagnose(key):
    """403 이 났을 때 **열쇠 탓인지 주소 탓인지** 가린다.

    사진 검색(/api/)은 문서에 있는 공식 주소다. 그것이 되면 열쇠는 멀쩡한 것이고,
    소리(/api/audio/)만 막힌 것이다 — 그러면 다른 길을 찾아야 한다.
    이 진단이 없으면 "열쇠가 틀렸나?" 를 계속 되묻게 된다."""
    print("\n  ── 무엇이 막혔는지 확인 ──")
    tests = [
        ("사진 검색 (공식 주소)", f"https://pixabay.com/api/?key={key}&q=court&per_page=3"),
        ("영상 검색 (공식 주소)", f"https://pixabay.com/api/videos/?key={key}&q=court&per_page=3"),
        ("소리 검색 (문서에 없는 주소)", f"{PIXABAY}?key={key}&q=footsteps&per_page=3"),
    ]
    for label, url in tests:
        for ua_name, ua in (("브라우저처럼", UA), ("프로그램 이름", "verdict-theater/1.0")):
            try:
                raw = get(url, timeout=30, ua=ua)
                n = len(json.loads(raw.decode("utf-8")).get("hits") or [])
                print(f"    {label:24s} [{ua_name}] 정상 — {n}건")
                break
            except urllib.error.HTTPError as e:
                print(f"    {label:24s} [{ua_name}] HTTP {e.code}")
            except Exception as e:
                print(f"    {label:24s} [{ua_name}] {type(e).__name__}")
    print("    → 사진·영상은 되는데 소리만 막히면, 소리 API 는 이 열쇠로 못 씁니다.")


def _audio_url(hit):
    """응답에서 소리 파일 주소를 찾는다.

    Pixabay 오디오 API 는 문서가 없어 필드 이름을 확신할 수 없다.
    그래서 **소리처럼 보이는 주소를 전부 뒤져** 첫 번째를 쓴다.
    (나중에 이름이 바뀌어도 이 함수가 견딘다)"""
    for k in ("audio", "audio_url", "previewURL", "preview", "url", "download"):
        v = hit.get(k)
        if isinstance(v, str) and v.startswith("http"):
            return v
    for v in hit.values():                      # 한 겹 더 들어가 본다
        if isinstance(v, dict):
            for vv in v.values():
                if isinstance(vv, str) and vv.startswith("http") and \
                        any(vv.lower().split("?")[0].endswith(e)
                            for e in (".mp3", ".ogg", ".m4a", ".wav")):
                    return vv
        if isinstance(v, str) and v.startswith("http") and \
                any(v.lower().split("?")[0].endswith(e)
                    for e in (".mp3", ".ogg", ".m4a", ".wav")):
            return v
    return None


def search_freesound(key, query, n=10, dur=(1.0, 10.0)):
    """Freesound 에서 **마음대로 써도 되는(CC0)** 소리만 검색한다.

    CC0 만 쓰는 이유: 유튜브에 올릴 것이라 출처 표기 의무가 없어야 뒤탈이 없다.
    받는 것은 미리듣기 mp3(128kbps) 다 — 원본은 로그인 절차가 필요한데,
    효과음 한두 개에 그 절차를 넣을 이유가 없다. 우리 영상 소리는 어차피
    192kbps 로 다시 인코딩된다."""
    q = urllib.parse.urlencode({
        "query": query,
        "filter": f'license:"Creative Commons 0" duration:[{dur[0]} TO {dur[1]}]',
        "fields": "id,name,duration,license,previews,username,url",
        "page_size": max(3, n),
        "token": key,
    })
    data = json.loads(get(f"{FREESOUND}?{q}").decode("utf-8"))
    out = []
    for r in data.get("results", []):
        url = (r.get("previews") or {}).get("preview-hq-mp3")
        if url:
            out.append({"id": r.get("id"), "tags": r.get("name"),
                        "pageURL": r.get("url"), "audio": url,
                        "license": r.get("license"), "user": r.get("username")})
    return out


def search(key, query, n=10):
    q = urllib.parse.urlencode({"key": key, "q": query,
                                "per_page": max(3, n), "safesearch": "true"})
    raw = get(f"{PIXABAY}?{q}")
    data = json.loads(raw.decode("utf-8"))
    hits = data.get("hits") or data.get("results") or []
    if hits and not _audio_url(hits[0]):
        # 어떤 이름으로 오는지 로그에 남긴다 — 다음에 고칠 때 짐작하지 않으려고
        print(f"    (응답 필드: {sorted(hits[0].keys())})")
    return hits


def measure(path):
    """걸음 속도(분당)·묵직함(무게중심 Hz). numpy 가 없으면 못 잰다."""
    try:
        import numpy as np
    except ImportError:
        return None
    w = tempfile.mktemp(suffix=".wav")
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path),
                        "-ac", "1", "-ar", "16000", w], check=True)
        with wave.open(w) as f:
            x = np.frombuffer(f.readframes(f.getnframes()), "<i2").astype(float)
    except Exception:
        return None
    finally:
        Path(w).unlink(missing_ok=True)
    if len(x) < 1600:
        return None
    sr = 16000
    sm = np.convolve(np.abs(x), np.ones(sr // 50) / (sr // 50), "same")
    thr = sm.max() * 0.35
    hits = np.where((sm[1:] > thr) & (sm[:-1] <= thr))[0] / sr
    sp = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    fr = np.fft.rfftfreq(len(x), 1 / sr)
    cen = float((sp * fr).sum() / max(1e-9, sp.sum()))
    bpm = 0.0
    if len(hits) > 1:
        gap = float(np.diff(hits).mean())
        bpm = 60.0 / gap if gap > 0 else 0.0
    return {"sec": len(x) / sr, "steps": len(hits), "bpm": bpm, "center": cen}


def score(m, prof=None):
    """그 자리에 얼마나 맞는 소리인가. 클수록 좋다. (prof 는 PROFILES 의 한 줄)"""
    prof = prof or PROFILES["footsteps"]
    if not m:
        return 0.0
    s = 100.0
    lo, hi = prof.get("bpm") or (0, 0)
    if lo or hi:
        if m["bpm"]:
            if m["bpm"] < lo:
                s -= (lo - m["bpm"]) * 1.2
            elif m["bpm"] > hi:
                s -= (m["bpm"] - hi) * 1.2      # 빠를수록 크게 깎는다
        else:
            s -= 25
    if m["steps"] < prof.get("beats_min", 3):
        s -= 20                                  # 두어 발로는 걸어오는 느낌이 안 난다
    if m["sec"] > 12:
        s -= (m["sec"] - 12) * 2                 # 너무 길면 컷에 안 맞는다
    s -= max(0.0, m["center"] - prof.get("bright", 1200)) / 40.0   # 얇고 쨍하면 감점
    return round(s, 1)


def one(name, query, install, out_dir, trim, source, key):
    """소리 하나를 받아 고르고(원하면) 설치한다. 0=성공, 1=실패."""
    prof = profile(name)
    query = query or prof["query"]
    trim = trim if trim is not None else prof.get("trim", 6.0)

    print(f"\n{'=' * 72}")
    print(f"■ {name}  ({prof.get('what', '')})   찾는 말: '{query}'")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    try:
        found = (search_freesound(key, query) if source == "freesound"
                 else search(key, query))
    except Exception as e:
        print(f"  오류: 검색 실패 — {type(e).__name__}: {e}", file=sys.stderr)
        try:
            diagnose(key)
        except Exception:
            pass
        return 1
    if not found:
        print(f"  '{query}' 로 나온 소리가 없습니다. 찾는 말을 바꿔 보십시오.")
        return 1

    print(f"  찾은 소리 {len(found)}개")
    print(f"  {'번호':4s}{'점수':>6s}{'분당':>7s}{'길이':>8s}{'묵직함':>9s}"
          f"{'몰린정도':>9s}  이름")
    print("  " + "-" * 78)
    rows = []
    for i, h in enumerate(found, 1):
        url = _audio_url(h)
        if not url:
            continue
        p = out / f"{name}_{i:02d}.mp3"
        try:
            p.write_bytes(get(url, timeout=120))
        except Exception as e:
            print(f"  {i:<4d} (내려받기 실패 {type(e).__name__})")
            continue
        m = measure(p)
        sc = score(m, prof)
        # ⭐ 기계가 만든 '삑' 은 아무리 점수가 높아도 안 쓴다.
        #    바로 이것 때문에 손님이 6분30초에서 "삑 삑" 을 들으셨다.
        tone = tone_ratio(p)
        beep = tone is not None and tone >= BEEP_TONALITY
        if beep:
            sc = -999.0
        rows.append((sc, i, p, h, m, tone))
        nm = str(h.get("tags") or h.get("name") or h.get("title") or "")[:28]
        tstr = f"{tone * 100:8.0f}%" if tone is not None else f"{'-':>9s}"
        if m:
            print(f"  {i:<4d}{sc:6.1f}{m['bpm']:7.0f}{m['sec']:7.1f}초"
                  f"{m['center']:8.0f}Hz{tstr}  {nm}"
                  + ("   ⚠ 삑 소리 — 안 씁니다" if beep else ""))
        else:
            print(f"  {i:<4d}{sc:6.1f}{'-':>7s}{'-':>8s}{'-':>9s}{tstr}  {nm}"
                  + ("   ⚠ 삑 소리 — 안 씁니다" if beep else ""))

    usable = [r for r in rows if r[0] > -900]
    if not usable:
        print("  쓸 수 있는 후보가 없습니다"
              + (" (전부 삑 소리였습니다)." if rows else "."))
        return 1
    usable.sort(reverse=True, key=lambda x: x[0])
    best = usable[0]
    print(f"\n  기계가 고른 1순위: {best[1]}번 (점수 {best[0]})")

    listen = out / f"{name}_listen.mp3"
    ins, chain, k = [], [], 0
    for _sc, _i, p, _h, _m, _t in sorted(rows, key=lambda x: x[1]):
        ins += ["-i", str(p)]
        chain.append(f"[{k}:a]")
        k += 1
        ins += ["-f", "lavfi", "-t", "0.8", "-i", "anullsrc=r=44100:cl=stereo"]
        chain.append(f"[{k}:a]")
        k += 1
    try:
        subprocess.run(["ffmpeg", "-v", "error", "-y"] + ins +
                       ["-filter_complex",
                        "".join(chain) + f"concat=n={k}:v=0:a=1[a]",
                        "-map", "[a]", "-b:a", "192k", str(listen)], check=True)
        print(f"  들어보기: {listen} (번호 순서로 이어 붙였습니다)")
    except Exception:
        pass

    if not install:
        return 0

    pick = best if install == "best" else \
        next((r for r in usable if str(r[1]) == str(install)), None)
    if not pick:
        print(f"  오류: {install} 번은 쓸 수 없는 후보입니다.", file=sys.stderr)
        return 1
    SFX.mkdir(parents=True, exist_ok=True)
    dst = SFX / f"{name}.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(pick[2]),
                    "-t", f"{trim}", "-ac", "2",
                    "-af", "loudnorm=I=-20:TP=-2", "-b:a", "192k", str(dst)],
                   check=True)
    # ⭐ 넣은 뒤 **다시 잰다.** 자르고 소리크기를 맞추는 사이에 성질이 바뀔 수 있다.
    t2 = tone_ratio(dst)
    if t2 is not None and t2 >= BEEP_TONALITY:
        dst.unlink(missing_ok=True)
        print(f"  ⚠ 넣고 보니 삑 소리였습니다(몰린정도 {t2 * 100:.0f}%). 넣지 않았습니다.")
        return 1

    h = pick[3]
    note = SFX / "SOURCES.md"
    line = (f"- `{name}.mp3` — {source} #{h.get('id')} "
            f"{str(h.get('tags') or '')[:50]}"
            + (f" by {h.get('user')}" if h.get('user') else "")
            + (f" ({h.get('license')})" if h.get('license') else "")
            + f" {h.get('pageURL') or ''}\n")
    old = note.read_text(encoding="utf-8") if note.exists() else \
        ("# 효과음 출처\n\n마음대로 써도 되는 소리만 씁니다"
         " (Freesound CC0 · Pixabay 콘텐츠 라이선스).\n\n")
    old = "".join(x for x in old.splitlines(keepends=True)
                  if not x.startswith(f"- `{name}.mp3`"))
    note.write_text(old + line, encoding="utf-8")
    m2 = measure(dst)
    print(f"  설치: {dst}"
          + (f"  → 분당 {m2['bpm']:.0f}번 · {m2['sec']:.1f}초" if m2 else "")
          + (f" · 몰린정도 {t2 * 100:.0f}%" if t2 is not None else ""))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="+",
                    help="효과음 이름 (여러 개 가능 · assets/sfx/{이름}.mp3)")
    ap.add_argument("--query", default="",
                    help="찾는 말. 안 주면 소리마다 정해진 말을 쓴다")
    ap.add_argument("--install", default="", help="best 또는 후보 번호")
    ap.add_argument("--out", default="build/sfx")
    ap.add_argument("--trim", type=float, default=None,
                    help="설치할 때 최대 길이(초). 안 주면 소리마다 정해진 값")
    a = ap.parse_args()

    names = a.name
    if len(names) == 1 and names[0] == "all":
        names = list(PROFILES)
    if len(names) > 1 and a.query:
        print("오류: 소리를 여러 개 받을 때는 --query 를 줄 수 없습니다"
              " (소리마다 찾는 말이 다릅니다).", file=sys.stderr)
        return 2

    # Freesound 를 먼저 본다 (소리를 공식으로 주는 곳). 없으면 Pixabay.
    source, which, key = None, None, ""
    for src in ("freesound", "pixabay"):
        which, key = api_key(src)
        if key:
            source = src
            break
    if not key:
        print("오류: 소리를 받아올 열쇠가 없습니다.", file=sys.stderr)
        print(f"      Freesound: {', '.join(KEY_NAMES['freesound'])}", file=sys.stderr)
        print(f"      Pixabay:   {', '.join(KEY_NAMES['pixabay'])}", file=sys.stderr)
        return 2
    print(f"소리 받아올 곳: {source} (열쇠 {which} 등록돼 있습니다)")

    bad = []
    for nm in names:
        try:
            if one(nm, a.query, a.install, a.out, a.trim, source, key):
                bad.append(nm)
        except Exception as e:
            print(f"  오류: {nm} — {type(e).__name__}: {e}", file=sys.stderr)
            bad.append(nm)

    print(f"\n{'=' * 72}")
    ok = [n for n in names if n not in bad]
    if ok:
        print(f"된 것 {len(ok)}개: {' · '.join(ok)}")
    if bad:
        print(f"안 된 것 {len(bad)}개: {' · '.join(bad)}")
    return 1 if len(bad) == len(names) else 0


if __name__ == "__main__":
    sys.exit(main())
