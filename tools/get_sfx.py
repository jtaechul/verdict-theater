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
import urllib.parse
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SFX = ROOT / "assets" / "sfx"
PIXABAY = "https://pixabay.com/api/audio/"

# 법정 걸음. 사람이 천천히 걸으면 분당 60~80걸음이다(지금 것은 131 — 그래서 싸구려다).
WANT_BPM = (55, 85)

# 열쇠 이름은 저장소마다 다를 수 있다. 있는 것을 찾아 쓴다.
KEY_NAMES = ("PIXABAY_API_KEY", "PIXABAY_KEY", "PIXABAY_TOKEN", "PIXABAY")


def api_key():
    for n in KEY_NAMES:
        v = os.environ.get(n, "").strip()
        if v:
            return n, v
    return None, ""


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "verdict-theater/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


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


def score(m):
    """법정 발소리로 얼마나 맞나. 클수록 좋다."""
    if not m:
        return 0.0
    s = 100.0
    lo, hi = WANT_BPM
    if m["bpm"]:
        if m["bpm"] < lo:
            s -= (lo - m["bpm"]) * 1.2
        elif m["bpm"] > hi:
            s -= (m["bpm"] - hi) * 1.2          # 빠를수록 크게 깎는다
    else:
        s -= 25
    if m["steps"] < 3:
        s -= 20                                  # 두어 발로는 걸어오는 느낌이 안 난다
    if m["sec"] > 12:
        s -= (m["sec"] - 12) * 2                 # 너무 길면 컷에 안 맞는다
    s -= max(0.0, m["center"] - 1200) / 40.0     # 얇고 쨍한 소리는 감점
    return round(s, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", help="효과음 이름 (assets/sfx/{이름}.mp3)")
    ap.add_argument("--query", default="footsteps hall")
    ap.add_argument("--install", default="", help="best 또는 후보 번호")
    ap.add_argument("--out", default="build/sfx")
    ap.add_argument("--trim", type=float, default=6.0, help="설치할 때 최대 길이(초)")
    a = ap.parse_args()

    which, key = api_key()
    if not key:
        print(f"오류: Pixabay 열쇠가 없습니다. 찾아본 이름: {', '.join(KEY_NAMES)}",
              file=sys.stderr)
        return 2
    print(f"Pixabay 열쇠: {which} (등록돼 있습니다)")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        found = search(key, a.query)
    except Exception as e:
        print(f"오류: 검색 실패 — {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    if not found:
        print(f"'{a.query}' 로 나온 소리가 없습니다. --query 를 바꿔 보십시오.")
        return 1

    print(f"\n'{a.query}' 로 찾은 소리 {len(found)}개")
    print(f"  {'번호':4s}{'점수':>6s}{'분당걸음':>9s}{'길이':>8s}{'묵직함':>9s}  이름")
    print("  " + "-" * 70)
    rows = []
    for i, h in enumerate(found, 1):
        url = _audio_url(h)
        if not url:
            continue
        p = out / f"{a.name}_{i:02d}.mp3"
        try:
            p.write_bytes(get(url, timeout=120))
        except Exception as e:
            print(f"  {i:<4d} (내려받기 실패 {type(e).__name__})")
            continue
        m = measure(p)
        sc = score(m)
        rows.append((sc, i, p, h, m))
        nm = str(h.get("tags") or h.get("name") or h.get("title") or "")[:32]
        if m:
            print(f"  {i:<4d}{sc:6.1f}{m['bpm']:9.0f}{m['sec']:7.1f}초"
                  f"{m['center']:8.0f}Hz  {nm}")
        else:
            print(f"  {i:<4d}{sc:6.1f}{'-':>9s}{'-':>8s}{'-':>9s}  {nm}")

    if not rows:
        print("쓸 수 있는 후보가 없습니다.")
        return 1
    rows.sort(reverse=True, key=lambda x: x[0])
    best = rows[0]
    print(f"\n  기계가 고른 1순위: {best[1]}번 (점수 {best[0]})")
    print(f"  기준: 법정 걸음 분당 {WANT_BPM[0]}~{WANT_BPM[1]}"
          f" · 지금 쓰는 것은 분당 131(너무 빠름)")

    listen = out / f"{a.name}_listen.mp3"
    ins, chain, k = [], [], 0
    for _sc, _i, p, _h, _m in sorted(rows, key=lambda x: x[1]):
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

    if a.install:
        pick = best if a.install == "best" else \
            next((r for r in rows if str(r[1]) == str(a.install)), None)
        if not pick:
            print(f"오류: {a.install} 번 후보가 없습니다.", file=sys.stderr)
            return 1
        SFX.mkdir(parents=True, exist_ok=True)
        dst = SFX / f"{a.name}.mp3"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(pick[2]),
                        "-t", f"{a.trim}", "-ac", "2",
                        "-af", "loudnorm=I=-20:TP=-2", "-b:a", "192k", str(dst)],
                       check=True)
        h = pick[3]
        note = SFX / "SOURCES.md"
        line = (f"- `{a.name}.mp3` — Pixabay #{h.get('id')} "
                f"{str(h.get('tags') or '')[:60]} "
                f"{h.get('pageURL') or ''}\n")
        old = note.read_text(encoding="utf-8") if note.exists() else \
            "# 효과음 출처\n\nPixabay 콘텐츠 라이선스(출처 표기 없이 상업적 사용 가능).\n\n"
        old = "".join(x for x in old.splitlines(keepends=True)
                      if not x.startswith(f"- `{a.name}.mp3`"))
        note.write_text(old + line, encoding="utf-8")
        m2 = measure(dst)
        print(f"\n  설치: {dst}"
              + (f"  → 분당 {m2['bpm']:.0f}걸음 · {m2['sec']:.1f}초" if m2 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
