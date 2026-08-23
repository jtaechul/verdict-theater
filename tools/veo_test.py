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
import vprompt                                               # noqa: E402
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
    C1 = DOC["episodes"][0]["cuts"][0]
    WANT_SEC = vprompt.seconds_for(C1["subtitle"])
    ck("모델 이름이 주소에 들어간다", veo.MODEL in u, u)
    # ⚠️⚠️ 구글은 4·6·8 초만 받는다. 거절 문구가 "between 4 and 8" 이라
    #    7초를 보냈다가 400 을 맞고 컷이 통째로 날아갔다(2026-08-23).
    ck(f"컷 길이를 대사에 맞춰 {WANT_SEC}초로 보낸다",
       p.get("durationSeconds") == WANT_SEC, p)
    ck("구글이 받는 길이(4·6·8)만 쓴다",
       all(vprompt.seconds_for(c["subtitle"]) in vprompt.OK_SEC
           for c in DOC["episodes"][0]["cuts"]),
       [vprompt.seconds_for(c["subtitle"]) for c in DOC["episodes"][0]["cuts"]])
    ck("비율을 16:9 로 보낸다 (shorts 가 4:3 으로 자른다)", p.get("aspectRatio") == "16:9", p)
    ck("1080p 로 받는다 (최종 가로가 1080px)", p.get("resolution") == "1080p", p)
    ck('personGeneration 은 "ALLOW_ALL" (allow_adult 는 400)',
       p.get("personGeneration") == "ALLOW_ALL", p)
    ck("씨앗(seed)을 보낸다", isinstance(p.get("seed"), int), p)
    BAD = ("negativePrompt", "numberOfVideos", "referenceImages", "lastFrame")
    ck("구글이 안 받는 필드를 안 보낸다",
       not [k for k in BAD if k in p or k in b["instances"][0]], p)

    # ⭐ 여기가 이번 판의 핵심이다 — 지시문을 그대로 보내면 안 된다.
    pr = b["instances"][0]["prompt"]
    print("② 지시문을 제대로 고쳐 보내는가")
    # ⚠️⚠️ 대사는 **남아 있어야 한다.** 빼면 Veo 가 누가 언제 말하는지 몰라
    #    둘이 내내 입을 움직인다(2026-08-23 사고).
    ck("대사(DIALOGUE) 토막이 남아 있다", "DIALOGUE" in pr)
    ck("한국어 대사가 들어 있다",
       [ch for ch in pr if "\uac00" <= ch <= "\ud7a3"])
    ck("자기 차례에만 입을 움직이라고 시킨다", vprompt.LIPS_DIA in pr)
    ck("적힌 대사 말고는 말하지 말라고 시킨다 (지어낸 나레이션 방지)",
       vprompt.ONLY_LINES in pr)
    # ⭐ 2026-08-23 운영자 확정 — 소리는 구글이 만든다. VOICE·AUDIO 묘사가
    #    있어야 회차마다 목소리 결이 같아진다. 빼면 매번 다른 목소리가 나온다.
    ck("목소리(VOICE)·소리(AUDIO) 묘사가 남아 있다 (구글이 이대로 만든다)",
       "VOICE:" in pr and "AUDIO:" in pr)
    import pathlib as _pl
    _wf = (_pl.Path(__file__).resolve().parent.parent
           / ".github" / "workflows" / "video.yml").read_text(encoding="utf-8")
    ck("워크플로가 구글 소리를 그대로 둔다 (KEEP_AUDIO)", "KEEP_AUDIO: '1'" in _wf)
    ck("거친 낱말(furious·shouting)이 순화됐다",
       "furious" not in pr.lower() and "shouting" not in pr.lower())
    ck("화면 글자 막는 문구가 **맨 끝**에 있다",
       pr.rstrip().endswith(vprompt.NO_TEXT), pr[-90:])
    ck("가운데로 몰아 찍으라고 시킨다 (좌우가 잘린다)", vprompt.FRAME in pr)
    # ⚠️ 2026-08-23 — "배경은 최대한 블러" 는 파이프라인 정리 때 정해 놓고
    #    프롬프트에 안 넣어 배경이 아주 선명하게 나왔다. 다시 빠지지 않게 못박는다.
    ck("배경을 흐리게 하라고 시킨다", vprompt.BLUR in pr, pr[-400:])
    ck("머리말의 초가 실제 길이와 같다", f"{WANT_SEC}-second" in pr,
       pr.splitlines()[0][-40:])

    # 그림(시작 프레임)이 선명하면 영상도 선명해진다 — 그림 쪽에도 있어야 한다
    sp = vprompt.still_prompt(C1["prompt"])
    print("③ 시작 그림 지시문도 같은 규칙을 지키는가")
    ck("그림에도 배경을 흐리게 하라고 시킨다", vprompt.BLUR in sp)
    ck("그림에도 화면 글자 막는 문구가 맨 끝에 있다",
       sp.rstrip().endswith(vprompt.NO_TEXT), sp[-90:])
    # 그림은 한 장이라 말할 차례가 없다 — 대사는 여기선 뺀다
    ck("그림에는 한국어 대사가 안 남았다",
       not [ch for ch in sp if "\uac00" <= ch <= "\ud7a3"],
       "".join(ch for ch in sp if "\uac00" <= ch <= "\ud7a3")[:40])

# ⑥ 장부
print("② 쓴 돈이 장부에 남는가")
rows = json.loads(cost.LEDGER.read_text(encoding="utf-8")) if cost.LEDGER.exists() else []
ck(f"장부에 {CUTS}줄이 남았다", len(rows) == CUTS, len(rows))
want = round(cost.video_krw(veo.MODEL, vprompt.seconds_for(
    DOC["episodes"][0]["cuts"][0]["subtitle"])))
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

# ⚠️ ⑤에서 장부에 한도를 넘는 가짜 줄을 넣었다. 그대로 두면 뒤 검사가 전부
#    "한도 초과"로 막힌다. 깨끗한 장부로 갈아 끼운다.
cost.LEDGER = pathlib.Path(tempfile.mkdtemp(prefix="veo-ledger2-")) / "spend.json"

print("⑥ 시작 그림이 있으면 시작 프레임으로 넣는가")
d4 = pathlib.Path(tempfile.mkdtemp(prefix="veo-start-"))
st = pathlib.Path(tempfile.mkdtemp(prefix="veo-stills-"))
(st / "c001.png").write_bytes(b"\x89PNG" + b"\0" * 20_000)
sent.clear(); veo._calls["n"] = 0
with redirect_stdout(io.StringIO()):
    veo.episode("S001", 1, d4, only_cut=1, stills=st)
b = [b for u, b in sent if ":predictLongRunning" in u][0]
img = b["instances"][0].get("image") or {}
ck("image 를 같이 보낸다", bool(img.get("bytesBase64Encoded")), list(img))
ck("mimeType 도 같이 보낸다 (하나만 보내면 400)", img.get("mimeType") == "image/png", img.get("mimeType"))

print("⑦ 안전필터에 걸린 것을 알아채는가")
def blocked(req, timeout=None):
    u = req.full_url
    if ":predictLongRunning" in u:
        return Fake(json.dumps({"name": "models/veo/operations/op9"}).encode())
    return Fake(json.dumps({"done": True, "response": {
        "raiFilteredReason": "blocked by safety"}}).encode())
urllib.request.urlopen = blocked
d5 = pathlib.Path(tempfile.mkdtemp(prefix="veo-safe-"))
veo._calls["n"] = 0
with redirect_stdout(io.StringIO()) as log:
    veo.episode("S001", 1, d5, only_cut=1)
out5 = log.getvalue()
ck("영상이 없다는 것을 알아챈다", "영상이 없다" in out5, out5[-160:])
ck("안전필터라고 알려 준다", "안전필터" in out5, out5[-160:])
urllib.request.urlopen = fake_urlopen

print("-" * 62)
if fails:
    print(f"❌ {len(fails)}가지 실패")
    sys.exit(1)
print("✅ Veo 로 컷을 만드는 길이 처음부터 끝까지 성하다. (값 0원)")
