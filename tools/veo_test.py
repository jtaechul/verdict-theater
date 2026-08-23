#!/usr/bin/env python3
"""Veo 로 컷 영상을 만드는 길이 성한가 (인터넷 0회 · 값 0원 · 2초).

    python3 tools/veo_test.py

왜 필요한가
    영상 한 컷이 약 530원이다. 잘못 만들어 놓고 깃허브에서 처음 돌리면
    **틀린 채로 다섯 번 나간다**(2,650원). 인터넷을 가짜로 막아 놓고
    전 구간을 먼저 걸어 본다.

무엇을 보나
    ① 구글에 보내는 몸통이 규격대로인가 (모델·초·비율)
    ② 파일 이름이 c001…c005 인가 (shorts.py 가 컷 번호로 짝짓는다)
    ③ 이미 있는 컷은 다시 안 만드는가 (다시 눌러도 돈이 두 번 안 나간다)
    ④ 부르는 횟수 상한이 진짜로 막는가
    ⑤ 한 달 한도를 **부르기 전에** 보는가 (값 0원으로 멈춰야 한다)
    ⑥ 쓴 돈이 장부에 남는가
"""

import io
import json
import os
import pathlib
import sys
import tempfile
import urllib.request
from contextlib import redirect_stdout

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

os.environ["GEMINI_API_KEY"] = "가짜-열쇠-검사용"
import cost                                                  # noqa: E402
import veo                                                   # noqa: E402

# 진짜 장부는 절대 안 건드린다
cost.LEDGER = pathlib.Path(tempfile.mkdtemp(prefix="veo-ledger-")) / "spend.json"
veo.POLL_SEC = 0                                             # 기다리지 않는다

fails = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + ("" if ok else f"  ({why})"))
    if not ok:
        fails.append(name)


# ── 가짜 구글 ────────────────────────────────────────────────
sent = []


class Fake(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen(req, timeout=None):
    url = req.full_url
    body = json.loads(req.data.decode()) if getattr(req, "data", None) else None
    sent.append((url, body))
    if ":predictLongRunning" in url:
        return Fake(json.dumps({"name": "models/veo/operations/op1"}).encode())
    if url.endswith("/videos/x.mp4") or "storage" in url:
        return Fake(b"\0" * 200_000)                         # 가짜 영상 알맹이
    if "operations/op1" in url:
        return Fake(json.dumps({
            "done": True,
            "response": {"generateVideoResponse": {"generatedSamples": [
                {"video": {"uri": "https://storage.example/videos/x.mp4"}}]}},
        }).encode())
    raise AssertionError(f"모르는 주소: {url}")


urllib.request.urlopen = fake_urlopen

DOC = json.loads((ROOT / "data" / "series" / "S001.json").read_text(encoding="utf-8"))
CUTS = len(DOC["episodes"][0]["cuts"])
SEC = int((DOC.get("spec") or {}).get("sec") or 6)

print("=" * 62)
print("Veo 컷 만들기 (값 0원 · 인터넷 0회)")
print("=" * 62)

# ① + ② 전 구간
print("① 구글에 보내는 몸통 · 파일 이름")
d = pathlib.Path(tempfile.mkdtemp(prefix="veo-out-"))
sent.clear(); veo._calls["n"] = 0
with redirect_stdout(io.StringIO()) as log:
    rc = veo.episode("S001", 1, d)
out = log.getvalue()
ck("5컷을 다 만들고 정상으로 끝난다", rc == 0, f"rc={rc}\n{out[-400:]}")
names = sorted(p.name for p in d.glob("*.mp4"))
ck("이름이 c001…c005 이다", names == [f"c{i:03d}.mp4" for i in range(1, CUTS + 1)], names)
posts = [(u, b) for u, b in sent if ":predictLongRunning" in u]
ck(f"영상 만들기를 {CUTS}번 부른다", len(posts) == CUTS, len(posts))
if posts:
    u, b = posts[0]
    p = b.get("parameters", {})
    ck("모델 이름이 주소에 들어간다", veo.MODEL in u, u)
    ck(f"길이를 {SEC}초로 보낸다", p.get("durationSeconds") == SEC, p)
    ck("비율을 16:9 로 보낸다 (shorts 가 4:3 으로 자른다)", p.get("aspectRatio") == "16:9", p)
    ck("대본의 지시문을 그대로 보낸다",
       b["instances"][0]["prompt"] == DOC["episodes"][0]["cuts"][0]["prompt"].strip())
    # ⭐ 2026-08-23 실측 — 구글이 안 받는 필드를 보내면 400 이 나고 그 컷이 통째로
    #    날아간다. 실측으로 확인한 것만 보내는지 매번 대조한다.
    ck("1080p 로 받는다 (최종 가로가 1080px)", p.get("resolution") == "1080p", p)
    ck('personGeneration 은 "ALLOW_ALL" (allow_adult 는 400)',
       p.get("personGeneration") == "ALLOW_ALL", p)
    BAD = ("negativePrompt", "numberOfVideos", "referenceImages", "lastFrame")
    ck("구글이 안 받는 필드를 안 보낸다", not [k for k in BAD if k in p or k in b["instances"][0]],
       [k for k in BAD if k in p or k in b["instances"][0]])

# ⑥ 장부
print("② 쓴 돈이 장부에 남는가")
rows = json.loads(cost.LEDGER.read_text(encoding="utf-8")) if cost.LEDGER.exists() else []
ck(f"장부에 {CUTS}줄이 남았다", len(rows) == CUTS, len(rows))
want = round(cost.video_krw(veo.MODEL, SEC))
ck(f"한 컷 값이 {want:,}원으로 적힌다", rows and rows[0]["krw"] == want, rows[:1])

# ③ 이어 만들기
print("③ 이미 있는 컷은 다시 안 만드는가")
sent.clear(); veo._calls["n"] = 0
with redirect_stdout(io.StringIO()):
    veo.episode("S001", 1, d)
ck("한 번도 안 부른다 (돈이 두 번 안 나간다)",
   not [u for u, _ in sent if ":predictLongRunning" in u], sent)

(d / "c003.mp4").unlink()
sent.clear(); veo._calls["n"] = 0
with redirect_stdout(io.StringIO()):
    veo.episode("S001", 1, d)
ck("지운 한 컷만 다시 만든다",
   len([u for u, _ in sent if ":predictLongRunning" in u]) == 1, sent)

# ④ 상한
print("④ 부르는 횟수 상한이 진짜로 막는가")
d2 = pathlib.Path(tempfile.mkdtemp(prefix="veo-cap-"))
keep = veo.CALL_CAP
veo.CALL_CAP = 2
sent.clear(); veo._calls["n"] = 0
with redirect_stdout(io.StringIO()) as log:
    veo.episode("S001", 1, d2)
n = len([u for u, _ in sent if ":predictLongRunning" in u])
ck("상한 2에서 멈춘다", n == 2, f"{n}번 불렀다")
ck("만든 것은 남는다", len(list(d2.glob('*.mp4'))) == 2, sorted(p.name for p in d2.glob('*.mp4')))
veo.CALL_CAP = keep

# ⑤ 한 달 한도 — 부르기 전에 막아야 한다
print("⑤ 한 달 한도를 부르기 전에 보는가")
d3 = pathlib.Path(tempfile.mkdtemp(prefix="veo-cap2-"))
cost.record("영상", cost.MONTH_KRW + 1, "검사용 가짜")
sent.clear(); veo._calls["n"] = 0
with redirect_stdout(io.StringIO()) as log:
    veo.episode("S001", 1, d3)
ck("한 번도 안 부르고 멈춘다 (값 0원)",
   not [u for u, _ in sent if ":predictLongRunning" in u], sent)
ck("왜 멈췄는지 알려준다", "이번 달 한도" in log.getvalue(), log.getvalue()[-200:])

print("-" * 62)
if fails:
    print(f"❌ {len(fails)}가지 실패")
    sys.exit(1)
print("✅ Veo 로 컷을 만드는 길이 처음부터 끝까지 성하다. (값 0원)")
