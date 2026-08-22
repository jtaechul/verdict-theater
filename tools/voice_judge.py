#!/usr/bin/env python3
"""⭐ 목소리 26개를 **재서 점수 매기고** 가장 한국사람 같은 것을 고른다.

    python3 tools/voice_judge.py --dir build/pick --out state/voice_rank.json

왜 (2026-08-22)
    운영자: "그냥 니가 알아서 기준과 알고리즘을 만들어서 잘 골라봐."
    나는 귀가 없다. 그래서 **들어서** 고를 수 없다. 대신 **잴 수 있는 것**으로
    고른다. 무엇을 재는지, 왜 그것이 '한국사람 같음'과 이어지는지 아래에 적는다.

기준 네 가지 (100점)
    ① 받아쓰기 정확도 (40점)
       그 소리를 다시 글로 받아쓰게 해서 원래 대사와 얼마나 같은가.
       발음이 뭉개지거나 억양이 엉뚱하면 받아쓰기가 틀린다. **가장 속이기
       어려운 잣대**라 제일 무겁게 둔다.
    ② 원어민 같은가 (30점)
       소리를 알아듣는 모델에게 **목소리 이름을 감추고** 물어본다.
       "한국 사람이 말하는 것 같은가, 외국인이 한국어를 하는 것 같은가."
       사람 판단에 가장 가깝지만 어디까지나 의견이라 ①보다 가볍게 둔다.
    ③ 말 빠르기 (15점)
       한국 드라마 대사는 초당 6~7.5음절쯤이다. 너무 느리면 또박또박 읽는
       외국인처럼, 너무 빠르면 씹어삼킨 것처럼 들린다.
    ④ 억양이 살아 있나 (15점)
       목소리 높낮이가 얼마나 움직이는가(반음 단위). 밋밋하면 기계처럼,
       지나치면 과장된 더빙처럼 들린다. 가운데를 좋게 본다.

⚠️ ②는 모델의 의견이다. ①③④는 실제로 잰 값이다. 그래서 점수를 매길 때
   잰 값 쪽(①③④=70점)이 의견(②=30점)보다 무겁다.
"""
import argparse
import base64
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import tts as T                                              # noqa: E402

API = ("https://generativelanguage.googleapis.com/v1beta/models/"
       "{m}:generateContent?key={k}")
JUDGE_MODELS = ["gemini-2.5-flash", "gemini-3-flash-preview", "gemini-2.0-flash"]
GOOD_SPS = (6.0, 7.5)          # 한국 드라마 대사의 자연스러운 초당 음절
GOOD_ST = (2.0, 5.0)           # 억양 폭(반음). 밋밋도 과장도 아닌 구간


# ── 재기 ────────────────────────────────────────────────
def to_wav(src, out, hz=16000):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src),
                    "-ac", "1", "-ar", str(hz), str(out)], check=True)
    return out


def frames(path):
    """(초당 표본수, [값…]) — -1~1 로 맞춘 홑소리."""
    with wave.open(str(path), "rb") as w:
        hz, n = w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    out = []
    for i in range(0, len(raw) - 1, 2):
        v = int.from_bytes(raw[i:i + 2], "little", signed=True)
        out.append(v / 32768.0)
    return hz, out


def f0_spread(path):
    """목소리 높낮이가 얼마나 움직이는가(반음). 못 재면 None.

    ⚠️ numpy 가 없으므로 손으로 센다. 소리를 8kHz 로 줄이고, 50ms 씩 끊어
       **자기 자신과 겹쳐 보아**(자기상관) 가장 잘 겹치는 간격을 찾는다.
       그 간격이 곧 목소리의 높이다. 사람 목소리 범위(70~400Hz)만 본다.
    """
    hz, x = frames(path)
    if hz != 8000:
        return None
    lo, hi = hz // 400, hz // 70          # 20 ~ 114 표본
    win, hop = 400, 200                   # 50ms 씩, 25ms 걸음
    got = []
    for s in range(0, max(0, len(x) - win), hop):
        seg = x[s:s + win]
        e = sum(v * v for v in seg)
        if e < 0.02:                      # 조용한 곳은 건너뛴다
            continue
        best, bl = 0.0, 0
        for lag in range(lo, hi):
            c = 0.0
            for i in range(win - lag):
                c += seg[i] * seg[i + lag]
            c /= (win - lag)
            if c > best:
                best, bl = c, lag
        if bl and best > 0.3 * (e / win):
            got.append(hz / bl)
    if len(got) < 5:
        return None
    got.sort()
    got = got[len(got) // 10: len(got) - len(got) // 10] or got   # 양끝 잘라내기
    m = sum(got) / len(got)
    sd = math.sqrt(sum((v - m) ** 2 for v in got) / len(got))
    return 12 * math.log2((m + sd) / max(1e-6, m - sd)) / 2 if m > sd else 0.0


# ── 받아쓰기·의견 물어보기 ──────────────────────────────
def ask(parts, tries=4):
    k = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not k:
        raise RuntimeError("GEMINI_API_KEY 가 없다")
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.0,
                                 "responseMimeType": "application/json"}}
    last = ""
    for m in JUDGE_MODELS:
        for t in range(tries):
            req = urllib.request.Request(
                API.format(m=m, k=k), data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    d = json.loads(r.read().decode("utf-8"))
                return json.loads(
                    d["candidates"][0]["content"]["parts"][0]["text"])
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", "replace")
                last = f"{m} HTTP {e.code} {raw[:150]}"
                if e.code == 429:
                    w = re.search(r"retry in ([\d.]+)", raw)
                    s = min(50.0, float(w.group(1)) + 1) if w else 20.0
                    print(f"    ⏳ 한도 — {s:.0f}초 쉰다")
                    time.sleep(s)
                    continue
                break                     # 이 모델은 안 된다 → 다음 모델
            except Exception as e:        # noqa: BLE001
                last = f"{m} {e}"
                time.sleep(5)
    raise RuntimeError(f"물어보지 못했다: {last}")


def cer(want, got):
    """글자가 얼마나 틀렸는가 (0=똑같다, 1=전부 다르다)."""
    a = re.sub(r"[^가-힣]", "", str(want or ""))
    b = re.sub(r"[^가-힣]", "", str(got or ""))
    if not a:
        return 1.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return min(1.0, prev[-1] / len(a))


def band(v, lo, hi, wide):
    """lo~hi 안이면 1점, 벗어난 만큼 깎는다 (wide 만큼 벗어나면 0점)."""
    if v is None:
        return 0.5                        # 못 쟀으면 가운데로 둔다
    if lo <= v <= hi:
        return 1.0
    off = (lo - v) if v < lo else (v - hi)
    return max(0.0, 1.0 - off / float(wide))


def judge(items, text):
    """한쪽 성별을 통째로 들려주고 받아쓰기와 의견을 받는다.

    ⚠️ **목소리 이름을 감춘다.** 이름을 보여 주면 모델이 이름값으로 판단할 수
       있다. 번호만 준다.
    """
    parts = [{"text":
              "다음은 같은 한국어 대사를 서로 다른 목소리로 읽은 소리다. "
              f"원래 대사는 \"{text}\" 이다.\n"
              "각 소리마다 두 가지를 답하라.\n"
              "  heard  : 실제로 들리는 대로 받아쓴 한국어 (원래 대사를 "
              "베끼지 말고 **들리는 대로**)\n"
              "  native : 한국에서 나고 자란 사람의 말처럼 들리면 10, "
              "외국인이 한국어를 하는 것처럼 들리면 0. 0~10 사이 정수.\n"
              "           발음·억양·말끝 처리를 본다. 목소리가 좋은지 나쁜지가 "
              "아니라 **한국어 원어민 같은지**만 본다.\n"
              "JSON 하나로만 답하라: "
              '{"rows":[{"i":1,"heard":"…","native":7}, …]}'}]
    for i, it in enumerate(items, 1):
        parts.append({"text": f"[{i}번]"})
        parts.append({"inline_data": {
            "mime_type": "audio/mpeg",
            "data": base64.b64encode(Path(it["path"]).read_bytes()).decode()}})
    got = ask(parts)
    out = {}
    for r in got.get("rows") or []:
        try:
            out[int(r["i"])] = (str(r.get("heard") or ""),
                                max(0, min(10, int(r.get("native", 0)))))
        except Exception:                                    # noqa: BLE001
            pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="build/pick")
    ap.add_argument("--out", default="state/voice_rank.json")
    ap.add_argument("--pick", default="state/voice.json")
    a = ap.parse_args()
    d = Path(a.dir)
    rows = json.loads((d / "list.json").read_text(encoding="utf-8"))
    for r in rows:
        r["path"] = str(d / r["file"])
        r["text"] = T.AUD_F if r["sex"] == "여" else T.AUD_M

    print(f"⭐ 목소리 {len(rows)}개를 재고 점수를 매긴다\n")
    print("① 잴 수 있는 것부터 (빠르기·억양)")
    tmp = d / "_wav"
    tmp.mkdir(exist_ok=True)
    for r in rows:
        try:
            w8 = to_wav(r["path"], tmp / (r["voice"] + "_8k.wav"), 8000)
            r["sec"] = T.dur_of(r["path"])
            r["sps"] = len(re.findall(r"[가-힣]", r["text"])) / max(0.01, r["sec"])
            r["st"] = f0_spread(w8)
        except Exception as e:                               # noqa: BLE001
            print(f"   ⚠️ {r['voice']} 못 쟀다 — {e}")
            r["sec"], r["sps"], r["st"] = 0.0, 0.0, None
        print(f"   {r['sex']} {r['voice']:14s} {r['sec']:.2f}초 · "
              f"{r['sps']:.1f}음절/초 · 억양 "
              + (f"{r['st']:.1f}반음" if r["st"] is not None else "못 쟀다"))

    print("\n② 받아쓰기와 의견 (목소리 이름은 감추고 물어본다)")
    for sex, text in (("여", T.AUD_F), ("남", T.AUD_M)):
        part = [r for r in rows if r["sex"] == sex]
        if not part:
            continue
        try:
            got = judge(part, text)
        except Exception as e:                               # noqa: BLE001
            print(f"   ⚠️ {sex}자 쪽을 못 물어봤다 — {e}")
            got = {}
        for i, r in enumerate(part, 1):
            heard, nat = got.get(i, ("", None))
            r["heard"], r["native"] = heard, nat
            r["cer"] = cer(r["text"], heard) if heard else None
            print(f"   {sex} {r['voice']:14s} 원어민 "
                  + (f"{nat:2d}/10" if nat is not None else " ?/10")
                  + " · 받아쓰기 「" + (heard or "못 받음")[:16] + "」"
                  + (f" (틀린 정도 {r['cer']:.2f})" if r["cer"] is not None else ""))

    print("\n③ 점수 (받아쓰기 40 · 원어민 30 · 빠르기 15 · 억양 15)")
    for r in rows:
        s1 = 40 * (1.0 - r["cer"]) if r.get("cer") is not None else 20.0
        s2 = 30 * (r["native"] / 10.0) if r.get("native") is not None else 15.0
        s3 = 15 * band(r.get("sps"), *GOOD_SPS, wide=2.5)
        s4 = 15 * band(r.get("st"), *GOOD_ST, wide=3.0)
        r["score"] = round(s1 + s2 + s3 + s4, 1)
        r["parts"] = {"받아쓰기": round(s1, 1), "원어민": round(s2, 1),
                      "빠르기": round(s3, 1), "억양": round(s4, 1)}

    rows.sort(key=lambda r: -r["score"])
    print(f"\n{'':2s} {'목소리':16s} {'점수':>5s}  받아쓰기 원어민 빠르기 억양")
    for i, r in enumerate(rows, 1):
        p = r["parts"]
        print(f"{i:2d} {r['sex']} {r['voice']:14s} {r['score']:5.1f}  "
              f"{p['받아쓰기']:7.1f} {p['원어민']:6.1f} {p['빠르기']:6.1f} "
              f"{p['억양']:5.1f}")

    best = {}
    for sex, key in (("여", "f"), ("남", "m")):
        got = [r for r in rows if r["sex"] == sex]
        if got:
            best[key] = got[0]["voice"]
            print(f"\n🏆 {sex}자 → **{got[0]['voice']}** ({got[0]['score']}점)")
    for f, data in ((a.out, {"rows": rows, "best": best}), (a.pick, best)):
        p = Path(f)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
    print(f"\n✅ {a.out} · {a.pick} 에 적었다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
