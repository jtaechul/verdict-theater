#!/usr/bin/env python3
"""⭐ 제미나이 옴니 플래시로 영상 한 토막을 만든다 (2026-09-30 신설).

    python3 src/omni.py 7        값 0원 — 7초 한 토막이 얼마인지만 보여 준다

왜 새로 만들었나
    2026-09-30 손님: "영상을 플로우가 아닌 옴니 플래쉬로 자동화 하고 싶어."
      결정적 컷(10개 안팎)만 입모양+대사 영상으로, 나머지는 인물 그림+카메라 무빙.
    같은 날 손님이 앱(구글 플로우)에서 직접 해 보셨다 — 인물 시트는 잘 나왔는데
    영상은 "유명인의 동영상 생성에 관한 Google 정책" 으로 막혔다. 앱은 사람
    그림을 첨부하면 막는다 (CLAUDE.md '프롬프트가 두 판이다' · 2026-08-27 과
    같은 벽). 그래서 **API 로** 돈다.

부르는 법 — 해양생물 쪽(Product 저장소 short-movie-generator/v2/tools/
run_request.py 의 gen_omni)에서 실제로 사 본 규격을 그대로 옮겼다.
거기서 4·5·6·7·8초를 받았고, 한 번에 25~35초 걸렸다.
    POST {BASE}/interactions
      model · input(그림들 + 글) · response_format(video · 720p · 9:16)
      · generation_config.video_config.task (image_to_video / reference_to_video)
    진행 중이면 GET {BASE}/interactions/{id} 로 10초마다 본다.
    ⚠️ 길이를 넣는 칸이 없다 — **글로** 정한다 ("exactly 7 seconds").

값 — ai.google.dev/gemini-api/docs/pricing (2026-09-30 직접 읽고 적었다)
    출력 영상 100만 토큰당 $17.50 · 720p 1초 = 5,792 토큰 → 1초 약 $0.10
    입력(글·그림·영상·소리) 100만 토큰당 $1.50 · 출력 글(생각 포함) $9.00
    → 부르기 **전에** 초당 $0.105 로 어림해 한도를 보고 장부에 적는다
      (cost.VIDEO_USD_SEC). 다 만든 뒤 구글이 알려 준 실제 토큰 값이
      더 크면 모자란 만큼 한 줄 더 적는다 — 장부는 모자라게 적지 않는다.

⚠️ 구글 문서(ai.google.dev/gemini-api/docs/omni, 2026-09-30)에 적힌 것
    · "소리 참조를 올리는 것은 지원하지 않는다" — 우리 성우 목소리를 넣어
      입을 맞추게 할 수 없다. 대사는 옴니가 직접 말한다.
    · "영어만 완전 지원, 다른 언어는 평가하지 않았다" — 한국어는 **시험으로** 본다.
    · "알아볼 수 있는 사람이 든 그림은 올릴 수 없다" — 우리 인물은 지어낸 사람이다.
    · 그림 역할은 프롬프트 맨 앞에 적는다:
        [# Sources <FIRST_FRAME>@Image1] [# References <IMAGE_REF_0>@Image2]
"""

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cost                                                  # noqa: E402

BASE = "https://generativelanguage.googleapis.com/v1beta"
MODEL = os.environ.get("OMNI_MODEL", "gemini-omni-1.1-flash")
# 값이 720p 기준으로 매겨진다 (1초 5,792토큰). 화질을 올리면 값이 달라진다.
RESOLUTION = os.environ.get("OMNI_RESOLUTION", "720p").strip() or "720p"
# ⭐⭐⭐ 2026-10-02 손님: "360p로 … 9대16 비율로 만들어. 처음부터." (1분 전부 영상)
#    1초에 나오는 영상 토큰 — 720p 는 구글 공시(5,792), 나머지는 같은 표의 공개 실측
#    (360p 1,931 · 1080p 8,688 · 4K 17,376 — 2026-10-02 검색). 화질값은 이 비율로만 센다.
#    다 만든 뒤 구글이 알려 준 **실제 토큰 값**이 더 크면 모자란 만큼 한 줄 더 적는다(아래).
VIDEO_TOKENS_SEC = {"360p": 1931, "720p": 5792, "1080p": 8688, "4k": 17376}
# 한 번 실행에서 옴니를 몇 번까지 부르나 — 실패가 겹쳐도 조용히 여러 번 사지 않게
CALL_CAP = int(os.environ.get("OMNI_CALL_CAP", "2"))
POLL_SEC, POLL_WAIT = 10, 900          # 10초마다 · 최대 15분

# 100만 토큰당 달러 (위 머리말의 공시가)
USD_IN, USD_OUT_TEXT, USD_OUT_VIDEO = 1.50, 9.00, 17.50

# 안전 검사에 걸렸을 때 구글이 쓰는 말들 (대소문자 안 가림)
FILTER_WORDS = ("safety", "blocked", "policy", "prohibited", "recognizable",
                "celebrity", "filtered", "responsible ai", "not supported for")


class OmniError(RuntimeError):
    pass


class OmniFiltered(OmniError):
    """안전 검사에 걸렸다 — 고장이 아니다. 그림 역할이나 말을 바꾸면 통과할 수 있다."""


class RunCapReached(OmniError):
    """한 번 실행에 정한 값(cost.RUN_KRW)을 넘었다."""


_calls = {"n": 0}
_spent = {"krw": 0.0}


def est_krw(sec, res=None):
    """부르기 전 어림값(원). cost 의 영상 단가표(720p) 한 곳에서 나와 화질 비율만 곱한다.
    ⚠️ 입력·생각 토큰 몫(초당 약 $0.004)은 화질과 상관없으므로 그대로 둔다."""
    base = cost.video_krw(MODEL, sec)
    res = (res or RESOLUTION).lower()
    if res == "720p" or res not in VIDEO_TOKENS_SEC:
        return base
    extra = 0.004 * max(0.0, float(sec)) * cost.USD_KRW
    k = VIDEO_TOKENS_SEC[res] / VIDEO_TOKENS_SEC["720p"]
    return (base - extra) * k + extra


def usage_krw(u):
    """구글이 알려 준 실제 토큰으로 매긴 값(원). 모르면 0."""
    if not isinstance(u, dict):
        return 0.0
    tin = float(u.get("total_input_tokens") or 0)
    vid = sum(float(x.get("tokens") or 0)
              for x in (u.get("output_tokens_by_modality") or [])
              if str(x.get("modality", "")).lower() == "video")
    tout = float(u.get("total_output_tokens") or 0)
    # 생각 토큰이 출력 합계에 이미 들었는지 판마다 달라, 따로 더해 넉넉히 센다
    text = max(0.0, tout - vid) + float(u.get("total_thought_tokens") or 0)
    usd = (tin * USD_IN + vid * USD_OUT_VIDEO + text * USD_OUT_TEXT) / 1e6
    return usd * cost.USD_KRW


def _key():
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if not k:
        raise OmniError("GEMINI_API_KEY 가 없다. Secrets 에 등록하라.")
    return k


def _why(raw):
    try:
        return json.loads(raw)["error"]["message"]
    except Exception:                                        # noqa: BLE001
        return raw


def _filtered(text):
    low = str(text or "").lower()
    return any(w in low for w in FILTER_WORDS)


def _call(path, body=None, timeout=120, raw=False, tries=1):
    """body 가 있으면 POST. ⚠️ 만들기(POST)는 다시 부르지 않는다 — 두 번 살 수 있다."""
    url = path if path.startswith("http") else f"{BASE}/{path}"
    data = json.dumps(body).encode() if body is not None else None
    for i in range(tries):
        req = urllib.request.Request(
            url, data=data, headers={"x-goog-api-key": _key(),
                                     "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                got = r.read()
                return got if raw else json.loads(got)
        except urllib.error.HTTPError as e:
            msg = _why(e.read().decode("utf-8", "replace"))[:400]
            if e.code in (429, 500, 503) and i + 1 < tries:
                time.sleep(8 * (i + 1))
                continue
            if e.code == 429:
                raise OmniError(
                    "구글이 영상 만들기를 안 받아 줍니다 (한도).\n"
                    "  관리자 페이지 [0. 제미나이 열쇠 점검] 을 눌러 결제가 붙었는지 "
                    f"보십시오.\n  구글이 한 말: {msg}") from None
            if _filtered(msg):
                raise OmniFiltered(f"안전 검사에 걸렸다 (HTTP {e.code}): {msg}") from None
            raise OmniError(f"옴니 부르기 실패 (HTTP {e.code}): {msg}") from None
    raise OmniError("옴니가 대답하지 않는다")


def _find_video(o):
    """응답 어디에 있든 영상(글자로 담긴 data 또는 주소 uri)을 찾는다."""
    if isinstance(o, dict):
        mt = str(o.get("mime_type") or o.get("mimeType") or "")
        if (o.get("type") == "video" or mt.startswith("video")) and \
                (o.get("data") or o.get("uri")):
            return o
        for k in ("output_video", "outputVideo"):
            if isinstance(o.get(k), dict) and (o[k].get("data") or o[k].get("uri")):
                return o[k]
        for v in o.values():
            f = _find_video(v)
            if f:
                return f
    elif isinstance(o, list):
        for v in o:
            f = _find_video(v)
            if f:
                return f
    return None


def _strip(o):
    """기록용 — 영상 글자(수 MB)는 빼고 생김새만 남긴다."""
    if isinstance(o, dict):
        return {k: (f"<{len(v)}자>" if k == "data" and isinstance(v, str) else _strip(v))
                for k, v in o.items()}
    if isinstance(o, list):
        return [_strip(v) for v in o]
    return o


def _usage(j):
    if not isinstance(j, dict):
        return None
    return j.get("usage") or j.get("usageMetadata") or j.get("usage_metadata")


def _mime(p):
    s = str(p).lower()
    return "image/png" if s.endswith(".png") else "image/jpeg"


def make(prompt, images, out, sec, task="image_to_video", ratio="9:16", res=None):
    """영상 한 토막. images 는 차례대로 프롬프트의 Image1 · Image2 … 와 맞는다.
    res 를 주면 그 화질로 (비우면 RESOLUTION).

    돌려주는 것: {"krw", "usage", "wait", "task", "file"}"""
    if _calls["n"] >= CALL_CAP:
        raise OmniError(f"이번 실행의 옴니 부르기 상한({CALL_CAP}번)에 걸렸다.")
    res = res or RESOLUTION
    krw = est_krw(sec, res)
    # 한 번 실행 한도·한 달 한도는 **값이 나가는 이 자리**에서 본다 (veo.py 와 같다)
    if _spent["krw"] + krw > cost.RUN_KRW:
        raise RunCapReached(
            f"이번 실행 한도({cost.RUN_KRW:,.0f}원)에 걸렸습니다. "
            f"여기까지 옴니에 {_spent['krw']:,.0f}원 썼고 이 토막이 약 {krw:,.0f}원입니다.")
    if cost.month_total() + krw > cost.MONTH_KRW:
        raise cost.MonthlyCapReached(
            f"이번 달 한도({cost.MONTH_KRW:,.0f}원)에 걸렸습니다. "
            f"지금까지 {cost.month_total():,.0f}원 썼고 이 토막이 약 {krw:,.0f}원입니다.")

    inputs = [{"type": "image", "mime_type": _mime(p),
               "data": base64.b64encode(Path(p).read_bytes()).decode()} for p in images]
    inputs.append({"type": "text", "text": prompt})
    body = {"model": MODEL, "input": inputs,
            "response_format": {"type": "video", "resolution": res,
                                "aspect_ratio": ratio},
            "generation_config": {"video_config": {"task": task}}}
    print(f"    옴니 부르는 중… ({task} · {sec}초 · {res} · {ratio} · "
          f"그림 {len(images)}장 · 약 {krw:,.0f}원)")
    _calls["n"] += 1
    t0 = time.time()
    j = _call("interactions", body, timeout=900)
    # ⚠️ 받아 준 순간부터 값이 나간다고 보고 **지금** 적는다. 기다리다 실패해도
    #    나간 값은 나간 것이다 (veo.py 와 같은 원칙 — 장부는 모자라게 적지 않는다).
    _spent["krw"] += krw
    cost.record("영상", krw, f"{MODEL} {res} {sec}초 {Path(out).name} (어림)")

    busy = ("in_progress", "pending", "running", "queued", "processing")
    while not _find_video(j) and j.get("id") and \
            str(j.get("status", "")).lower() in busy:
        if time.time() - t0 > POLL_WAIT:
            raise OmniError(f"{POLL_WAIT}초를 기다려도 안 끝났다.")
        time.sleep(POLL_SEC)
        j = _call(f"interactions/{j['id']}", tries=4)

    v = _find_video(j)
    if not v:
        blob = json.dumps(_strip(j), ensure_ascii=False)
        if _filtered(blob):
            raise OmniFiltered(f"안전 검사에 걸렸다 (영상을 안 돌려줬다): {blob[:400]}")
        raise OmniError(f"다 됐다는데 영상이 없다: {blob[:400]}")
    if v.get("data"):
        vid = base64.b64decode(v["data"])
    else:
        fid = str(v["uri"]).rstrip("/").split("/")[-1]
        for _ in range(90):
            st = _call(f"files/{fid}", tries=4)
            if str(st.get("state", "")).upper() == "ACTIVE":
                break
            time.sleep(5)
        vid = _call(f"files/{fid}:download?alt=media", raw=True, timeout=600, tries=4)
    if len(vid) < 10_000:
        raise OmniError(f"받은 영상이 너무 작다 ({len(vid)} 바이트)")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(vid)

    usage = _usage(j)
    real = usage_krw(usage)
    if real > krw + 1:
        cost.record("영상", real - krw, f"{MODEL} {out.name} 실제 토큰 값 차액")
        _spent["krw"] += real - krw
    wait = round(time.time() - t0, 1)
    print(f"    ✅ {out.name}  ({out.stat().st_size / 1e6:.1f}MB · {wait}초 걸림 · "
          f"약 {max(krw, real):,.0f}원)")
    return {"krw": round(max(krw, real)), "usage": usage, "wait": wait,
            "task": task, "file": out.name}


if __name__ == "__main__":
    s = float(sys.argv[1]) if len(sys.argv) > 1 else 6
    print(f"{MODEL} {s:g}초 어림값: 약 {est_krw(s):,.0f}원 "
          f"(1초 ${cost.video_krw(MODEL, 1) / cost.USD_KRW:.3f})")
