#!/usr/bin/env python3
"""⭐ 회차 하나의 컷 영상을 Veo 로 만든다 (2026-08-23 신설).

    python3 src/veo.py S001 1 --out build/in
    python3 src/veo.py S001 1 --out build/in --cut 1     한 컷만 시험

왜 새로 만들었나
    여태 컷 영상은 **구글 플로우에서 손으로** 만들어 압축파일로 올리셨다.
    손이 많이 가고, 회차마다 인물·옷·배경이 어긋났다. 대본(data/series/*.json)에
    컷마다 Veo 프롬프트가 이미 적혀 있으므로, 그것을 그대로 API 로 보낸다.

나오는 파일 이름
    c001.mp4 · c002.mp4 …  ← shorts.py 의 pick_clips() 가 이 번호로 짝짓는다.
    이름에 컷 번호가 박혀 있으면 순서가 어긋날 수 없다 (플로우 파일명 사고 방지).

돈
    Veo 는 **초당** 값이 매겨진다. 6초 x 5컷 = 30초 = 약 2,650원 (veo 3.1 lite).
    한 컷 만들기 전에 매번 한 달 한도와 한 번 실행 한도를 본다. 넘으면 그 자리에서
    멈추고, **이미 만든 컷은 그대로 남긴다** (다시 누르면 없는 것만 채운다).
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cost                                                  # noqa: E402
import reuse                                                 # noqa: E402
import vprompt                                               # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://generativelanguage.googleapis.com/v1beta"
MODEL = os.environ.get("VEO_MODEL", "veo-3.1-lite-generate-preview")

# 한 번 실행에서 Veo 를 몇 번까지 부를 수 있는가. 상한이 없으면 실패가 겹칠 때
# 조용히 수십 번을 부른다 — 한 번에 500원짜리라 그러면 큰돈이 된다.
CALL_CAP = int(os.environ.get("VEO_CALL_CAP", "8"))
# 실측: 720p·1080p 둘 다 받는다. 최종 화면 가로가 1080px 이므로
# 1080p 로 받아 잘라야 선이 흐려지지 않는다.
RESOLUTION = os.environ.get("VEO_RESOLUTION", "1080p")
# ⚠️⚠️ 2026-09-05 실측 — **1080p 는 4초를 안 받는다.**
#      HTTP 400: "1080p is not supported for a duration of 4 seconds."
#      편 첫 장면(4초)이 이것으로 세 개 다 실패했다(값은 0원 — 거절당했다).
#      길이에 맞는 화질로 저절로 내린다. 720p 로 받아 1080 으로 조금 늘리면
#      살짝 덜 선명하지만, 4초만 나오고 곧 그림으로 넘어가 티가 적다.
#      8초로 올리면 선명하지만 값이 두 배이고 스와이프 판정 구간 밖이다.
RES_MIN_SEC_1080 = 6             # 이보다 짧으면 1080p 를 못 쓴다


def res_for(sec):
    """그 길이에 쓸 수 있는 화질. 짧으면 720p 로 내린다."""
    if RESOLUTION == "1080p" and float(sec) < RES_MIN_SEC_1080:
        return "720p"
    return RESOLUTION
POLL_SEC, POLL_MAX = 10, 60           # 10초마다 · 최대 10분

_calls = {"n": 0}


class VeoError(RuntimeError):
    pass


def _key():
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if not k:
        raise VeoError("GEMINI_API_KEY 가 없다. Secrets 에 등록하라.")
    return k


def _post(path, body):
    req = urllib.request.Request(
        f"{BASE}/{path}", data=json.dumps(body).encode(),
        headers={"x-goog-api-key": _key(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        msg = raw[:300]
        try:
            msg = json.loads(raw)["error"]["message"][:300]
        except Exception:                                    # noqa: BLE001
            pass
        if e.code == 429:
            raise VeoError(
                "구글이 영상 만들기를 안 받아 줍니다 (한도).\n"
                "  관리자 페이지 [0. 제미나이 열쇠 점검] 을 눌러 결제가 붙었는지 보십시오.\n"
                f"  구글이 한 말: {msg}") from None
        raise VeoError(f"영상 만들기 실패 (HTTP {e.code}): {msg}") from None


def _get(path):
    req = urllib.request.Request(f"{BASE}/{path}",
                                 headers={"x-goog-api-key": _key()})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def _find_uri(obj):
    """응답 생김새가 판마다 다르다. 어디에 있든 영상 주소를 찾아낸다."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("uri", "videoUri", "url") and isinstance(v, str) and v.startswith("http"):
                return v
            got = _find_uri(v)
            if got:
                return got
    elif isinstance(obj, list):
        for v in obj:
            got = _find_uri(v)
            if got:
                return got
    return None


def _download(uri, out):
    sep = "&" if "?" in uri else "?"
    req = urllib.request.Request(uri if "key=" in uri else f"{uri}{sep}key={_key()}",
                                 headers={"x-goog-api-key": _key()})
    with urllib.request.urlopen(req, timeout=600) as r, open(out, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    if out.stat().st_size < 10_000:
        raise VeoError(f"받은 영상이 너무 작다 ({out.stat().st_size} 바이트)")


def make_clip(prompt, sec, out, ratio="16:9", seed=None, start=None, end=None):
    """컷 하나를 만든다. 돈을 쓰기 **전에** 한도를 본다."""
    if _calls["n"] >= CALL_CAP:
        raise VeoError(f"이번 실행의 영상 만들기 상한({CALL_CAP}번)에 걸렸다.")

    krw = cost.video_krw(MODEL, sec)
    if cost.month_total() + krw > cost.MONTH_KRW:
        raise cost.MonthlyCapReached(
            f"이번 달 한도({cost.MONTH_KRW:,.0f}원)에 걸렸습니다. "
            f"지금까지 {cost.month_total():,.0f}원 썼고 이 컷이 약 {krw:,.0f}원입니다.")

    print(f"    영상 만드는 중… ({sec}초 · {res_for(sec)} · 약 {krw:,.0f}원)")
    inst = {"prompt": prompt}
    if start:
        # ⚠️ 실측: image 에는 bytesBase64Encoded 와 mimeType 이 **둘 다** 있어야
        #    한다 (하나만 넣으면 400). gcsUri 는 이 모델이 안 받는다.
        inst["image"] = {"bytesBase64Encoded": base64.b64encode(
            Path(start).read_bytes()).decode(), "mimeType": "image/png"}
        if end:
            # 2026-08-23 운영자 지시 — 끝 그림까지 못박아 영상은 두 장
            # 사이를 **잇기만** 하게 한다. (lastFrame 은 image 와 같이 줄
            # 때만 받는다 — 단독이면 400, 둘이면 통과. 0원 실측)
            inst["lastFrame"] = {"bytesBase64Encoded": base64.b64encode(
                Path(end).read_bytes()).decode(), "mimeType": "image/png"}
    op = _post(f"models/{MODEL}:predictLongRunning", {
        "instances": [inst],
        # ⭐ 2026-08-23 — 값 0원으로 실측한 규격만 보낸다 (틀린 필드는 400).
        #    실측: durationSeconds 는 숫자 4~8 / aspectRatio 는 16:9·9:16만
        #    (4:3 은 400) / resolution 720p·1080p / seed·sampleCount O
        #    / negativePrompt·numberOfVideos 는 **미지원** / personGeneration 은
        #    "ALLOW_ALL" 만 (allow_adult 는 400).
        #    ⚠️ 16:9 로 받는다. 우리 화면의 영상 자리가 4:3(1080x810)이라
        #       16:9 는 좌우만 12.5%씩 잘리지만, 9:16 은 위아래를 58% 잘라야 해
        #       머리·턱이 날아간다.
        "parameters": {"aspectRatio": ratio, "durationSeconds": int(sec),
                       "resolution": res_for(sec), "personGeneration": "ALLOW_ALL",
                       **({"seed": int(seed)} if seed is not None else {})},
    })
    _calls["n"] += 1
    name = op.get("name")
    if not name:
        raise VeoError(f"작업 번호를 못 받았다: {json.dumps(op, ensure_ascii=False)[:200]}")

    # ⚠️ 돈은 **부른 순간** 나간다. 기다리다 실패해도 값은 나갔으므로 여기서 적는다.
    cost.record("영상", krw, f"{MODEL} {sec}초 {out.name}")

    for i in range(POLL_MAX):
        time.sleep(POLL_SEC)
        st = _get(name)
        if st.get("error"):
            raise VeoError(f"만들다 실패: {json.dumps(st['error'], ensure_ascii=False)[:250]}")
        if st.get("done"):
            uri = _find_uri(st)
            if not uri:
                # ⚠️ 안전필터에 걸리면 **오류가 아니라 성공**으로 온다 — done 은
                #    true 인데 영상이 없다. 왜 없는지 알려 줘야 고칠 수 있다.
                blob = json.dumps(st, ensure_ascii=False)
                why = "안전필터에 걸린 듯하다" if any(
                    k in blob for k in ("SAFETY", "raiFilteredReason", "blocked",
                                        "filtered")) else "까닭을 모르겠다"
                raise VeoError(f"다 됐다는데 영상이 없다 ({why}): {blob[:250]}")
            _download(uri, out)
            print(f"    ✅ {out.name}  ({out.stat().st_size / 1e6:.1f}MB)")
            return krw
        if i and i % 6 == 0:
            print(f"    …{(i + 1) * POLL_SEC}초 기다리는 중")
    raise VeoError(f"{POLL_MAX * POLL_SEC}초를 기다려도 안 끝났다.")


def _seed(*parts):
    """같은 컷을 다시 만들면 같은 구도가 나오게 씨앗을 고정한다.

    실측: seed 는 요청이 받아들여진다. 컷마다 **다른** 값이어야 하고, 실행할
    때마다 달라지면 안 되므로 이름에서 만들어 낸다."""
    h = hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()
    return int(h[:8], 16) % 2_000_000_000


def episode(sid, no, out_dir, only_cut=None, stills=None, auto_sec=True):
    doc = json.loads((ROOT / "data" / "series" / f"{sid}.json").read_text(encoding="utf-8"))
    eps = doc.get("episodes") or []
    ep = next((e for e in eps if int(e.get("no", 0)) == int(no)), None)
    if not ep:
        raise VeoError(f"{sid} 에 {no}화가 없다.")
    sec = int((doc.get("spec") or {}).get("sec") or 6)
    cuts = ep.get("cuts") or []
    if only_cut:
        cuts = [c for c in cuts if int(c.get("n", 0)) == int(only_cut)]
        if not cuts:
            raise VeoError(f"{no}화에 {only_cut}컷이 없다.")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"■ {sid} {no}화 「{ep.get('title', '')}」 — 컷 {len(cuts)}개 x {sec}초")
    print(f"  모델 {MODEL} · 예상 약 {cost.video_krw(MODEL, sec) * len(cuts):,.0f}원")
    print(f"  이번 달 이미 쓴 돈 {cost.month_total():,.0f}원 / 한도 {cost.MONTH_KRW:,.0f}원")
    print()

    spent, made = 0.0, 0
    for c in cuts:
        n = int(c.get("n", 0))
        out = out_dir / f"c{n:03d}.mp4"
        print(f"  컷{n} [{c.get('role', '')}] {c.get('subtitle', '')[:40]}")
        raw = (c.get("prompt") or "").strip()
        if not raw:
            print("    ⚠️ 이 컷에 영상 지시문이 없다 — 건너뛴다")
            continue
        # ⭐ 컷 길이는 **대사 길이에 맞춘다** (2026-08-23). 6초 컷에 9초짜리
        #    대사를 얹으면 남는 3초 동안 마지막 장면이 얼어붙어 사고처럼 보인다.
        csec = vprompt.seconds_for(c.get("subtitle") or "") if auto_sec else sec
        prompt = vprompt.video_prompt(raw, csec)
        start = end = None
        if stills:
            cand = Path(stills) / f"c{n:03d}.png"
            if cand.exists() and cand.stat().st_size > reuse.MIN_BYTES:
                start = cand
            cand2 = Path(stills) / f"c{n:03d}_end.png"
            if start and cand2.exists() and cand2.stat().st_size > reuse.MIN_BYTES:
                end = cand2
            if end:
                print("    시작·끝 그림 두 장으로 못박는다 — 영상은 사이를 잇기만 한다")
            elif start:
                print(f"    시작 그림만 쓴다: {cand.name} (끝 그림이 없어 도착점이 자유다)")
        # ⚠️ 보관해 둔 컷을 다시 쓸지는 **무엇으로 만든 것인가**로 판단한다.
        #    "파일이 있으면 건너뛴다" 로 두면 지시문·그림을 고쳐도 옛 영상이
        #    그대로 나온다 (2026-08-26 화풍 사고와 같은 모양). 규칙: src/reuse.py
        sig = reuse.sig_of(prompt, csec, *(p for p in (start, end) if p))
        ok, why = reuse.can_reuse(out, sig)
        if ok:
            print(f"    (그대로다 — 건너뛴다: {out.name})")
            made += 1
            continue
        if why:
            print(f"    ⚠️ {why} — 다시 만든다: {out.name}")
        try:
            spent += make_clip(prompt, csec, out, seed=_seed(sid, no, n),
                               start=start, end=end)
            reuse.stamp(out, sig)
            made += 1
        except (cost.MonthlyCapReached, VeoError) as e:
            print(f"    ❌ {e}")
            print(f"\n  여기서 멈춘다. 만든 컷 {made}개는 그대로 남는다 — "
                  f"다시 누르면 없는 것만 채운다.")
            break
        if spent > cost.RUN_KRW:
            print(f"\n  한 번 실행 한도({cost.RUN_KRW:,.0f}원)를 넘었다 — 여기서 멈춘다. "
                  f"만든 컷 {made}개는 남는다.")
            break

    print(f"\n■ 컷 {made}/{len(cuts)}개 · 이번에 쓴 돈 약 {spent:,.0f}원")
    return 0 if made == len(cuts) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sid")
    ap.add_argument("no")
    ap.add_argument("--out", default="build/in")
    ap.add_argument("--cut", default="", help="한 컷만 만들어 본다")
    ap.add_argument("--stills", default="",
                    help="컷 첫 장면 그림 폴더 (있으면 시작 프레임으로 넣는다)")
    ap.add_argument("--fixed-sec", action="store_true",
                    help="대사 길이에 맞추지 않고 대본의 초를 그대로 쓴다")
    a = ap.parse_args()
    try:
        return episode(a.sid, a.no, a.out, a.cut or None,
                       stills=a.stills or None, auto_sec=not a.fixed_sec)
    except (VeoError, cost.MonthlyCapReached) as e:
        print(f"❌ {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
