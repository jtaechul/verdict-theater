#!/usr/bin/env python3
"""⭐ 목소리 26개를 **재서 점수 매기고** 가장 한국사람 같은 것을 고른다.

    python3 tools/voice_judge.py --dir build/pick --out state/voice_rank.json

왜 (2026-08-22)
    운영자: "그냥 니가 알아서 기준과 알고리즘을 만들어서 잘 골라봐."
    나는 귀가 없다. 그래서 **들어서** 고를 수 없다. 대신 **잴 수 있는 것**으로
    고른다. 무엇을 재는지, 왜 그것이 '한국사람 같음'과 이어지는지 아래에 적는다.

⚠️⚠️ 1차는 **실패했다.** 세 군데가 한꺼번에 망가졌다 (2026-08-22).
    ① 받아쓰기 40점 → **26개 전부 만점.** 목소리가 다 알아들을 만해서
       변별력이 0이었다. 40점이 통째로 죽었다.
    ② 원어민 30점 → **26개 전부 10/10.** 절대 점수를 물으면 모델이 다 좋다고
       한다. 30점도 죽었다.
    ③ 빠르기 15점 → 앞뒤 **무음을 안 잘라서** 실제의 절반으로 쟀다
       (2.4~4.0음절/초로 나왔는데 좋은 구간을 6.0~7.5로 잡아 뒀다).
       26개 전부 구간 밖 → 사실상 전원 0점.
    → 남은 것은 억양 15점뿐. **그 하나로 순위가 정해졌고**, 1등이 하필
      운영자가 이미 "외국인 같다"고 물린 Fenrir 였다.

고친 기준 (100점)
    ⓪ 관문 — 받아쓰기
       점수로 주지 않는다. 알아들을 수 없으면(글자 15% 넘게 틀리면) **탈락**.
       다 알아들을 만하면 이 잣대는 할 일이 없다. 점수가 아니라 문지기다.
    ① 눈 가리고 줄 세우기 (60점)
       "몇 점이냐" 고 물으면 다 10점이라 한다. 그러니 **줄을 세우게** 한다.
       "한국에서 나고 자란 사람 말처럼 들리는 순서대로 나열하라."
       ⚠️ **들려주는 차례를 섞어 세 번** 물어 평균 낸다. 한 번만 물으면
          앞에 놓인 것이 유리해지는 자리 편향이 그대로 남는다.
       ⚠️ 세 번의 답이 서로 얼마나 맞는지도 잰다. 서로 딴소리를 하면
          **모델이 구별을 못 하는 것**이므로, 그 사실을 그대로 적는다.
    ② 말 빠르기 (20점) — **앞뒤 무음을 잘라 내고** 잰다
    ③ 억양이 살아 있나 (20점) — 높낮이 폭. 밋밋도 과장도 아닌 가운데
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
GOOD_SPS = (5.5, 7.5)          # 무음을 뺀 **실제 말하는** 속도 기준
CER_GATE = 0.35                # 혼자만 이만큼 틀리면 알아들을 수 없다 → 탈락
CER_OVER = 0.25                # 남들보다 이만큼 더 틀리면 탈락 (상대 비교)
ROUNDS = 3                     # 차례를 섞어 몇 번 줄 세우게 할까
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


def speech_sec(path):
    """**실제로 말한** 시간(초). 앞뒤 무음은 뺀다.

    ⚠️ 2026-08-22 — 이걸 안 해서 1차가 망했다. 소리 파일 길이로 재면
       앞뒤 무음까지 들어가 말 빠르기가 **절반으로** 나온다.
    """
    hz, x = frames(path)
    win = max(1, hz // 100)                   # 10ms
    lv = []
    for s0 in range(0, len(x) - win, win):
        seg = x[s0:s0 + win]
        lv.append(sum(v * v for v in seg) / win)
    if not lv:
        return 0.0
    top = max(lv)
    gate = max(top * 0.02, 1e-6)              # 가장 큰 곳의 2% 넘으면 말한 것
    on = [i for i, v in enumerate(lv) if v > gate]
    if len(on) < 2:
        return len(x) / hz
    return (on[-1] - on[0] + 1) * win / hz


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
# ⚠️⚠️ 2026-08-22 — 3차가 여기서 망했다. "JSON 하나로만: {"order":[…]}" 라고
#    글로 부탁했더니 모델이 **제 마음대로 다른 모양**으로 답했다
#    (직접 걸어 보니 {"answer": 2} 를 돌려줬다). 내 코드는 order 를 못 찾고
#    빈손으로 물러섰고, 그러면 '들려준 차례 그대로' 가 답이 된다.
#    차례를 섞어 세 번 물었으니 세 답이 서로 뒤집힌 꼴이 되어
#    일치도가 0.00 으로 찍혔다 — 모델이 못 고른 게 아니라 **내가 못 받은 것**이다.
#    → 부탁하지 말고 **모양을 못 박는다** (responseSchema).
ORDER_SCHEMA = {"type": "OBJECT",
                "properties": {"order": {"type": "ARRAY",
                                         "items": {"type": "INTEGER"}}},
                "required": ["order"]}
HEARD_SCHEMA = {"type": "OBJECT",
                "properties": {"rows": {"type": "ARRAY", "items": {
                    "type": "OBJECT",
                    "properties": {"i": {"type": "INTEGER"},
                                   "heard": {"type": "STRING"}},
                    "required": ["i", "heard"]}}},
                "required": ["rows"]}


def ask(parts, tries=4, schema=None):
    k = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not k:
        raise RuntimeError("GEMINI_API_KEY 가 없다")
    cfg = {"temperature": 0.0, "responseMimeType": "application/json"}
    if schema:
        cfg["responseSchema"] = schema
    body = {"contents": [{"parts": parts}], "generationConfig": cfg}
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


def hear(items, text):
    """받아쓰기만 받는다 (관문용). {번호: 들린 글}"""
    parts = [{"text":
              "다음은 같은 한국어 대사를 서로 다른 목소리로 읽은 소리다.\n"
              "각 소리를 **들리는 대로** 한국어로 받아써라. "
              "원래 대사를 짐작해서 베끼지 말고, 귀에 들린 그대로 적어라.\n"
              'JSON 하나로만: {"rows":[{"i":1,"heard":"…"}, …]}'}]
    for i, it in enumerate(items, 1):
        parts.append({"text": f"[{i}번]"})
        parts.append({"inline_data": {
            "mime_type": "audio/mpeg",
            "data": base64.b64encode(Path(it["path"]).read_bytes()).decode()}})
    got = ask(parts, schema=HEARD_SCHEMA)
    out = {}
    for r in got.get("rows") or []:
        try:
            out[int(r["i"])] = str(r.get("heard") or "")
        except Exception:                                    # noqa: BLE001
            pass
    return out


def rank_once(items, order, text):
    """한 번 줄 세우게 한다. 돌려주는 것: [원래자리…] 좋은 것부터.

    ⚠️ **목소리 이름을 감춘다.** 이름을 보여 주면 이름값으로 판단할 수 있다.
    ⚠️ 들려주는 차례(order)를 바깥에서 섞어 넣는다 — 앞에 놓인 것이
       유리해지는 자리 편향을 없애려면 섞은 채로 여러 번 물어야 한다.
    """
    n = len(order)
    parts = [{"text":
              f"다음 {n}개는 **같은 한국어 대사**를 서로 다른 목소리로 읽은 "
              f"것이다. 대사는 \"{text}\" 이다.\n"
              "한국에서 나고 자란 사람이 실제로 말하는 것처럼 들리는 "
              "**순서대로** 번호를 나열하라. 가장 한국사람 같은 것이 맨 앞.\n"
              "보는 곳: 발음, 억양의 오르내림, 말끝 처리, 리듬. "
              "목소리가 좋고 나쁨이 아니라 **한국어 원어민 같은지**만 본다.\n"
              f"{n}개를 하나도 빠뜨리지 말고, 같은 자리에 둘을 놓지 마라.\n"
              'JSON 하나로만: {"order":[3,7,1,…]}'}]
    for pos, k in enumerate(order, 1):
        parts.append({"text": f"[{pos}번]"})
        parts.append({"inline_data": {
            "mime_type": "audio/mpeg",
            "data": base64.b64encode(
                Path(items[k]["path"]).read_bytes()).decode()}})
    got = ask(parts, schema=ORDER_SCHEMA)
    raw = list(got.get("order") or [])
    if not raw:
        raise RuntimeError("줄 세운 답을 못 받았다 (order 가 비어 있다)")
    seen, out = set(), []
    for v in got.get("order") or []:
        try:
            pos = int(v)
        except Exception:                                    # noqa: BLE001
            continue
        if 1 <= pos <= n and pos not in seen:
            seen.add(pos)
            out.append(order[pos - 1])       # 들려준 자리 → 원래 자리
    miss = [k for k in order if k not in out]
    if miss:
        print(f"    ⚠️ {len(miss)}개를 빠뜨렸다 — 뒤에 붙인다")
        out += miss
    # ⚠️ 들려준 차례를 그대로 돌려주면 **고른 것이 아니다.** 그냥 받아 적은 것이다.
    if out == list(order):
        raise RuntimeError("들려준 차례를 그대로 돌려줬다 — 고른 것이 아니다")
    return out


def agree(a, b):
    """두 줄 세우기가 얼마나 맞는가 (1=똑같다, 0=완전 거꾸로).

    ⚠️ 이걸 재는 까닭: 섞어서 여러 번 물었는데 답이 서로 딴소리면
       **모델이 구별을 못 하는 것**이다. 그러면 순위는 그냥 잡음이다.
       그 사실을 감추지 않고 그대로 적어야 한다.
    """
    n = len(a)
    if n < 2:
        return 1.0
    pa = {v: i for i, v in enumerate(a)}
    pb = {v: i for i, v in enumerate(b)}
    ok = bad = 0
    for i in range(n):
        for j in range(i + 1, n):
            x, y = a[i], a[j]
            if y not in pb or x not in pb:
                continue
            (ok := ok + 1) if pb[x] < pb[y] else (bad := bad + 1)
    tot = ok + bad
    return (ok / tot) if tot else 1.0


def rank_many(items, text, rounds=ROUNDS):
    """차례를 섞어 여러 번 줄 세우고 평균 자리를 낸다.

    돌려주는 것: ({원래자리: 평균 등수}, 서로 얼마나 맞았나)
    """
    n = len(items)
    runs, why = [], []
    for t in range(rounds):
        # ⚠️ Math.random 같은 것을 안 쓴다 — 몇 번째냐에 따라 정해진 만큼
        #    돌려서 섞는다. 그래야 다시 돌려도 같은 결과가 나온다.
        shift = (t * max(1, n // rounds)) % max(1, n)
        order = list(range(shift, n)) + list(range(shift))
        if t % 2:
            order = order[::-1]
        try:
            r = rank_once(items, order, text)
            runs.append(r)
            why.append({"round": t + 1, "ok": True,
                        "order": [items[k]["voice"] for k in r]})
            print(f"    · {t + 1}번째 끝 — 앞자리: "
                  + ", ".join(items[k]["voice"] for k in r[:4]))
        except Exception as e:                               # noqa: BLE001
            why.append({"round": t + 1, "ok": False, "why": str(e)[:200]})
            print(f"    ⚠️ {t + 1}번째 실패 — {str(e)[:120]}")
    if not runs:
        # ⚠️ 한 번도 못 받았으면 **줄 세우기는 없는 것**이다. 0점을 주면
        #    "가장 나쁘다" 는 뜻이 되어 거짓말이 된다 → 없다고 알린다.
        return {}, None, why
    pos = {k: [] for k in range(n)}
    for r in runs:
        for i, k in enumerate(r):
            pos[k].append(i)
    mean = {k: (sum(v) / len(v) if v else n - 1) for k, v in pos.items()}
    ag = []
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            ag.append(agree(runs[i], runs[j]))
    return mean, (sum(ag) / len(ag) if ag else None), why


def main():
    try:
        return _run()
    except Exception as e:                                   # noqa: BLE001
        # ⚠️ 판정이 죽어도 **무슨 일이 있었는지는 남긴다.** 실행 화면의 긴 글은
        #    뒤쪽만 잘려 보여서, 죽은 까닭을 못 읽은 적이 여러 번이다.
        import traceback
        print("\n❌ 판정이 죽었다:\n" + traceback.format_exc()[-1500:])
        return 1


def _run():
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

    DEBUG = {}
    print(f"⭐ 목소리 {len(rows)}개를 재고 줄 세운다\n")
    print("① 잴 수 있는 것부터 (말한 시간·빠르기·억양)")
    tmp = d / "_wav"
    tmp.mkdir(exist_ok=True)
    for r in rows:
        try:
            w8 = to_wav(r["path"], tmp / (r["voice"] + "_8k.wav"), 8000)
            r["sec"] = T.dur_of(r["path"])
            r["talk"] = speech_sec(w8)          # ⚠️ 무음 뺀 **실제** 말한 시간
            r["sps"] = len(re.findall(r"[가-힣]", r["text"])) / max(0.01, r["talk"])
            r["st"] = f0_spread(w8)
        except Exception as e:                               # noqa: BLE001
            print(f"   ⚠️ {r['voice']} 못 쟀다 — {e}")
            r["sec"] = r["talk"] = r["sps"] = 0.0
            r["st"] = None
        print(f"   {r['sex']} {r['voice']:14s} 파일 {r['sec']:.2f}초 · "
              f"말 {r['talk']:.2f}초 · {r['sps']:.1f}음절/초 · 억양 "
              + (f"{r['st']:.1f}반음" if r["st"] is not None else "못 쟀다"))

    print("\n② 관문 — 알아들을 수 있는가 (받아쓰기)")
    for sex, text in (("여", T.AUD_F), ("남", T.AUD_M)):
        part = [r for r in rows if r["sex"] == sex]
        if not part:
            continue
        try:
            got = hear(part, text)
        except Exception as e:                               # noqa: BLE001
            print(f"   ⚠️ {sex}자 쪽을 못 물어봤다 — {e}")
            got = {}
        for i, r in enumerate(part, 1):
            h = got.get(i, "")
            r["heard"] = h
            r["cer"] = cer(r["text"], h) if h else None
        # ⚠️⚠️ 2026-08-22 — 처음엔 "0.15 넘으면 탈락" 이라고 절대값으로 잘랐다.
        #    그랬더니 **남자 13개가 전부 똑같이 0.222 로 탈락**했다.
        #    "못 살아" 를 "못 사라" 로 들은 것인데, 아홉 글자짜리 대사에서
        #    두 글자면 22%다. 모두가 똑같이 틀렸다면 그건 **목소리 탓이 아니라
        #    대사 탓**이다. 그런데도 전원 탈락시켜 남자 쪽 줄 세우기를 통째로
        #    건너뛰었다.
        #    → 남들과 견줘서 **혼자 유난히** 못 알아들을 때만 떨어뜨린다.
        _c = sorted(x["cer"] for x in part if x.get("cer") is not None)
        mid = _c[len(_c) // 2] if _c else 0.0
        for r in part:
            v = r.get("cer")
            r["pass"] = (v is None) or (v <= max(CER_GATE, mid + CER_OVER))
            if not r["pass"]:
                print(f"   ❌ {sex} {r['voice']:14s} 탈락 — 「{r['heard'][:18]}」 "
                      f"({v:.2f} 틀림 · 다들 {mid:.2f})")
        print(f"   (다들 {mid:.2f} 쯤 틀린다 — 여기서 "
              f"{max(CER_GATE, mid + CER_OVER):.2f} 넘게 틀려야 탈락)")
    _bad = [r for r in rows if not r.get("pass", True)]
    print(f"   {len(rows) - len(_bad)}개 통과 · {len(_bad)}개 탈락"
          + ("  (다 알아들을 만하면 이 관문은 할 일이 없다)" if not _bad else ""))

    print("\n③ 눈 가리고 줄 세우기 (차례를 섞어 세 번)")
    for sex, text in (("여", T.AUD_F), ("남", T.AUD_M)):
        part = [r for r in rows if r["sex"] == sex and r.get("pass", True)]
        if not part:
            continue
        print(f"   {sex}자 {len(part)}개")
        mean, ag, why = rank_many(part, text)
        DEBUG[sex] = why
        for k, r in enumerate(part):
            if mean:
                r["rank"] = mean.get(k, len(part) - 1)
                r["rank_n"] = len(part)
        for r in [x for x in rows if x["sex"] == sex]:
            r["agree"] = (round(ag, 3) if ag is not None else None)
        if ag is None:
            print("   → ❌ **한 번도 못 받았다.** 줄 세우기는 없는 셈 친다")
        else:
            print(f"   → 세 번의 답이 서로 맞는 정도: {ag:.2f}"
                  + ("  ✅ 구별하고 있다" if ag >= 0.7 else
                     ("  ⚠️ 애매하다 — 반쯤은 잡음이다" if ag >= 0.6 else
                      "  ❌ **거의 잡음이다.** 이 줄 세우기는 못 믿는다")))

    # ⚠️ 줄 세우기를 못 받았으면 그 60점은 **아무한테도 주지 않는다.**
    #    누구는 0점 누구는 60점처럼 갈리면 잡음이 순위가 된다.
    _no_rank = all(r.get("rank") is None for r in rows)
    if _no_rank:
        print("\n④ 점수 — ⚠️ 줄 세우기를 못 받아 **빠르기·억양만으로** 매긴다."
              "\n   이 순위는 '한국사람 같은가' 를 못 본 것이다. 믿지 마라.")
    print("\n④ 점수 (줄 세우기 60 · 빠르기 20 · 억양 20)")
    for r in rows:
        if not r.get("pass", True):
            r["score"], r["parts"] = 0.0, {"줄세우기": 0.0, "빠르기": 0.0,
                                           "억양": 0.0, "관문": "탈락"}
            continue
        n = max(2, r.get("rank_n", 2))
        s1 = (0.0 if r.get("rank") is None
              else 60 * (1.0 - r["rank"] / (n - 1)))
        s2 = 20 * band(r.get("sps"), *GOOD_SPS, wide=2.5)
        s3 = 20 * band(r.get("st"), *GOOD_ST, wide=3.0)
        r["score"] = round(s1 + s2 + s3, 1)
        r["parts"] = {"줄세우기": round(s1, 1), "빠르기": round(s2, 1),
                      "억양": round(s3, 1), "관문": "통과"}

    rows.sort(key=lambda r: -r["score"])
    print(f"\n{'':3s}{'목소리':14s}{'점수':>6s}  {'줄세우기':>8s}{'빠르기':>7s}"
          f"{'억양':>6s}   {'음절/초':>7s}{'반음':>6s}")
    for i, r in enumerate(rows, 1):
        p = r["parts"]
        st = f"{r['st']:.1f}" if r.get("st") is not None else "-"
        print(f"{i:2d} {r['sex']} {r['voice']:12s}{r['score']:6.1f}  "
              f"{p['줄세우기']:8.1f}{p['빠르기']:7.1f}{p['억양']:6.1f}   "
              f"{r.get('sps', 0):7.1f}{st:>6s}")

    best = {}
    for sex, key in (("여", "f"), ("남", "m")):
        got = [r for r in rows if r["sex"] == sex and r.get("pass", True)]
        if got:
            best[key] = got[0]["voice"]
            _ag = got[0].get("agree")
            print(f"\n🏆 {sex}자 → **{got[0]['voice']}** ({got[0]['score']}점, "
                  + (f"줄 세우기 일치도 {_ag:.2f})" if _ag is not None
                     else "줄 세우기는 못 받았다 — 빠르기·억양만으로 고른 것)"))
    # ⚠️ 무슨 일이 있었는지 **결과 파일에 같이 적는다.** 실행 화면의 긴 글은
    #    뒤쪽만 잘려 보여서, 정작 왜 실패했는지를 못 읽은 적이 여러 번이다.
    for f, data in ((a.out, {"rows": rows, "best": best, "debug": DEBUG,
                             "trust": all(
                                 (r.get("agree") or 0) >= 0.7 for r in rows)}),
                    (a.pick, best)):
        q = Path(f)
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
    print(f"\n✅ {a.out} · {a.pick} 에 적었다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
