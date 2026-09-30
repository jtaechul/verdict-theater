#!/usr/bin/env python3
"""⭐ **2분 드라마** 가 약속대로 짜여 있는가 — 값 0원 · 인터넷 0회

    python3 tools/drama_check.py

2026-09-30 손님 확정 — "2분 이내 쇼츠 드라마로 가자."
  · 등장인물(6명 이내)을 한 장에 그려 칸마다 잘라 참조로 쓴다
  · 대사 컷(한 사람 한 줄)은 전부 옴니 입모양 영상 · 대사 목소리는 옴니 그대로
  · 나머지 컷은 나레이션 + 그림 + 카메라 무빙 · 한 번 실행 16,000원까지

새 형식은 옛 여러 편 형식과 **같은 길**(대본 → 그림 → 영상 → 조립 → 올리기)을
나눠 쓴다. 어느 한 자리만 형식을 몰라도 엉뚱한 얼굴·엉뚱한 값·60초 벽이
튀어나온다. 그래서 자리마다 못을 박는다 — 진짜 대본 꼴(tools/fixtures/
drama_story.json)을 실제 코드에 흘려 본다.

  ① 대본   좋은 대본은 통과 · 나쁜 대본(두 줄 컷 · 없는 인물 · 긴 대사 …)은 걸린다
  ② 형식   새 사건은 2분 드라마 · 있던 사건은 그 형식 그대로
  ③ 짓기   인물은 대본이 정한 것 · 대사 컷마다 옴니 지문 · 걸리는 낱말 없음
  ④ 셈     대사 컷 전부 · 2분 벽 · 옴니 값 · 한 번 한도 16,000원 안
  ⑤ 제작   대사 컷을 옴니로 산다 (그림 = 첫 장면 · 시트 칸 = 참조) · 다시 누르면 0원
  ⑥ 올리기 2분 드라마는 2분 벽 · 옛 편은 60초 벽 그대로
  ⑦ 단추   관리자 페이지 · 워크플로 · 대본 형식이 한 글자도 안 어긋난다
"""
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
# ⚠️ 시험은 진짜 상태 파일을 건드리지 않는다 (CLAUDE.md · VT_SHORTS_STATE).
#    대본 짓기(build_short90)가 상태 파일에 사건 칸을 만들기 때문이다.
WORK = ROOT / "build" / "_drama_check"
shutil.rmtree(WORK, ignore_errors=True)
WORK.mkdir(parents=True, exist_ok=True)
os.environ["VT_SHORTS_STATE"] = str(WORK / "shorts.json")

import cost                                                  # noqa: E402
import series                                                # noqa: E402
import story90 as S                                          # noqa: E402
import talkplan                                              # noqa: E402

FIX = ROOT / "tools" / "fixtures" / "drama_story.json"
bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def story():
    d = json.loads(FIX.read_text(encoding="utf-8"))
    for c in d["cuts"]:
        c["sec"] = round(S.chars(c) / 4.6 + 1.2, 1)
    S.shape_drama(d)
    d["sid"], d["case_id"] = "S999", "000000"
    return d


print("⭐ 2분 드라마 점검 — 값 0원")

# ── ① 대본 ────────────────────────────────────────────────
good = story()
ck("좋은 대본은 통과한다", not S.check(good, new=True), str(S.check(good)[:3]))
ck("한 편짜리 parts 가 생긴다", good["parts"] == [{
    "no": 1, "cuts": [1, len(good["cuts"])], "yt_title": good["parts"][0]["yt_title"],
    "card": good["parts"][0]["card"]}] and good["parts"][0]["yt_title"])
ck("인물 → 목소리 나이대·성별 (people)",
   good["people"].get("아내") == {"age": "50대", "sex": "여"}
   and good["people"].get("변호사") == {"age": "40대", "sex": "남"})


def broken(fn, want):
    d = story()
    fn(d)
    got = S.check(d, new=True)
    return any(want in b for b in got), got


def two_turns(d):
    c = next(x for x in d["cuts"] if x["turns"][0][0] != "나레이션")
    c["turns"].append(["나레이션", "그 말에 아무도 대답하지 않았습니다."])
    c["say"].append("사건을 전하는 낮고 묵직한 목소리로")


def stranger(d):
    c = next(x for x in d["cuts"] if x["turns"][0][0] == "아내")
    c["who"] = c["who"] + ["장남"]


def long_line(d):
    c = next(x for x in d["cuts"] if x["turns"][0][0] == "변호사")
    c["turns"][0][1] = ("유언이 있어도 가족 몫은 법이 지켜 줍니다. 그걸 유류분이라고 "
                        "부르고 법원이 반드시 인정해 줍니다.")


def few_talk(d):
    for c in d["cuts"][1:-1]:
        if c["turns"][0][0] != "나레이션" and c["n"] > 7:
            c["turns"][0][0] = "나레이션"
            c["who"] = []


def racy(d):
    d["cast"][1]["wear"] = "a sexy low-cut red dress"


def no_end(d):
    d["cuts"][-1]["turns"][0][1] = "가족은 서로의 몫을 지켜 냈습니다."


for name, fn, want in (
        ("한 컷에 두 줄 (대사+나레이션)", two_turns, "한 컷 한 줄"),
        ("화면에 인물 설계에 없는 사람", stranger, "인물(cast)에 없다"),
        ("대사가 너무 길다", long_line, "대사가"),
        ("대사 컷이 모자란다", few_talk, "대사 컷이"),
        ("인물 옷에 그림이 막히는 낱말", racy, "막히는 낱말"),
        ("마지막 컷이 사건 맺음말이 아니다", no_end, "마지막 컷"),
):
    hit, got = broken(fn, want)
    ck(f"나쁜 대본을 잡는다 — {name}", hit, str(got[:3]))

old = json.loads((ROOT / "data" / "series" / "S93.story.json").read_text(encoding="utf-8"))
ck("옛 여러 편 대본(S93)은 옛 규격 그대로 통과한다", not S.check(old, new=False),
   str(S.check(old, new=False)[:2]))
ck("옛 여러 편에는 기본 다섯이 그대로 있다", "아내" in S.people_of(old))
ck("2분 드라마에는 기본 다섯을 억지로 넣지 않는다",
   "남편" not in S.people_of(good))

# ── ② 형식 ────────────────────────────────────────────────
ck("새 사건은 2분 드라마로 짓는다", S.pick_format(None, None) == "drama")
ck("있던 옛 사건(S93)은 옛 형식 그대로 다시 짓는다", S.pick_format(None, "S93") == "parts")
ck("고른 형식이 있으면 그것이 이긴다", S.pick_format("parts", None) == "parts")
ck("고치기 프롬프트가 형식마다 따로 있다",
   (ROOT / "prompts" / "drama120_fix.md").exists()
   and "drama120_fix" in (ROOT / "src" / "story90.py").read_text(encoding="utf-8"))

# ── ③ 짓기 (build_short90) ─────────────────────────────────
import build_short90 as B                                    # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="build_", dir=WORK))
try:
    sp, op, mp = tmp / "S999.story.json", tmp / "S999.json", tmp / "S999.meta.json"
    sp.write_text(json.dumps(good, ensure_ascii=False), encoding="utf-8")
    was = B.paths
    B.paths = lambda sid: (sp, op, mp)
    try:
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            B.main(["S999"])
    finally:
        B.paths = was
        B.SHEET_REFS = False
    doc = json.loads(op.read_text(encoding="utf-8"))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

ck("대본 형식이 이어진다 (format=drama)", doc.get("format") == "drama")
ck("인물은 대본이 정한 것이다 (기본 다섯이 아니다)",
   [c["name"] for c in doc["characters"]] == [c["name"] for c in good["cast"]])
talks = [c for c in doc["cuts"] if not c["narr"]]
ck("대사 컷마다 옴니 지문이 있다 (첫 장면판 · 참조만판)",
   talks and all(c.get("omni") and c.get("omni_ref") and c.get("omni_sec") for c in talks))
hits = []
for c in talks:
    for k in ("omni", "omni_ref"):
        h = series.risky_words(c[k]) + series.negative_words(c[k]) + series.wear_bait(c[k])
        if h:
            hits.append((c["n"], k, h))
ck("옴니 지문에 걸리는 낱말·'하지 마'·옷 묘사가 없다", not hits, str(hits[:3]))
ck("옴니 지문이 그림 역할을 맨 앞에 적는다",
   all(c["omni"].startswith("[# Sources <FIRST_FRAME>@Image1] [# References <IMAGE_REF_0>@Image2")
       and c["omni_ref"].startswith("[# References <IMAGE_REF_0>@Image1") for c in talks))
ck("옴니 지문의 참조 수가 화면 인물 수와 같다",
   all(c["omni"].count("<IMAGE_REF_") >= len(c["who"]) and
       f"<IMAGE_REF_{len(c['who'])}>" not in c["omni"] for c in talks))
ck("옴니 지문이 대사를 한 글자도 안 바꾼다",
   all(f'"{c["turns"][0][1]}"' in c["omni"] for c in talks))
ck("목소리는 인물마다 한 줄로 고정된다 (같은 인물 = 같은 설명)",
   all(next(p["voice"] for p in good["cast"] if p["name"] == c["turns"][0][0]).rstrip(".")
       in c["omni"] for c in talks))
people_cuts = [c for c in doc["cuts"] if c["who"] and not c["narr"]]
ck("시트 칸을 참조로 쓰는 그림 지문에 '한 사람이 두 번' 이 적힌다",
   people_cuts and all(B.TWICE.strip() in c["still"] for c in people_cuts))
ck("옛 형식 그림 지문에는 그 줄이 안 붙는다",
   B.TWICE.strip() not in B.people_of(["아내"], still=True))

# ── ④ 셈 ────────────────────────────────────────────────
tp = doc["talk"]
ck("대사 컷 전부를 산다", tp["n"] == len(talks), f"{tp['n']} vs {len(talks)}")
ck("벽은 2분이다", tp.get("max_sec") == talkplan.DRAMA_MAX_SEC and not tp["over"],
   str(tp.get("parts")))
ck("옴니 길이는 4~10초", all(4 <= c["omni_sec"] <= 10 for c in talks))


def speech_end(p):
    ends = [float(m.group(1)) for m in
            re.finditer(r"\[\d+\.\d-(\d+\.\d)s\] [^\n]*says in Korean", p)]
    return max(ends) if ends else 99.0


ck("초 표의 말이 산 길이 안에서 끝난다 (문장 사이 숨까지 · 말이 안 잘린다)",
   all(speech_end(c["omni"]) <= c["omni_sec"] - talkplan.OMNI_TAIL + 0.05
       for c in talks),
   str([(c["n"], speech_end(c["omni"]), c["omni_sec"]) for c in talks][:4]))
dp = tp.get("drama") or {}
want = round(sum(cost.video_krw("gemini-omni-1.1-flash", c["omni_sec"]) for c in talks))
ck("대사 영상값은 옴니 단가로 센다", abs(dp.get("talk_krw", 0) - want) <= len(talks),
   f"{dp.get('talk_krw')} vs {want}")
ck("화면에 적을 합계(대사+그림+시트)가 있다",
   dp.get("krw") == round(dp["talk_krw"] + dp["still_krw"] + dp["sheet_krw"]) or
   abs(dp.get("krw", 0) - (dp["talk_krw"] + dp["still_krw"] + dp["sheet_krw"])) <= 1)
ck("한 편이 한 번 한도(16,000원) 안에 든다", dp.get("krw", 99999) <= cost.DRAMA_RUN_KRW)
old93 = json.loads((ROOT / "data" / "series" / "S93.json").read_text(encoding="utf-8"))
ck("옛 사건(S93)의 벽은 60초 그대로", talkplan.part_max_sec(old93) == 59.5)
ck("옛 사건(S93)의 대사 영상 길이는 Veo 규격 그대로",
   all(talkplan.talk_sec_of(old93, t) in (4, 6, 8) for t in ("짧다.", "조금 더 긴 대사입니다.")))

# plan_cost — 워크플로 뚜껑
import plan_cost                                             # noqa: E402
real = plan_cost.ROOT
tmp2 = Path(tempfile.mkdtemp(prefix="plan_", dir=WORK))
try:
    (tmp2 / "data" / "series").mkdir(parents=True)
    (tmp2 / "data" / "series" / "S999.json").write_text(json.dumps(doc, ensure_ascii=False),
                                                     encoding="utf-8")
    plan_cost.ROOT = tmp2
    pc = plan_cost.plan("S999", False, True, False)
finally:
    plan_cost.ROOT = real
    shutil.rmtree(tmp2, ignore_errors=True)
ck("워크플로 뚜껑이 16,000원을 넘지 않는다", pc["run_krw"] <= cost.DRAMA_RUN_KRW,
   str(pc["run_krw"]))
ck("워크플로 뚜껑이 대사 영상값 이상이다 (반쪽에서 안 멈춘다)",
   pc["run_krw"] >= dp["talk_krw"] + dp["still_krw"])
ck("옴니 부르기 상한을 대본에서 센다", pc.get("omni_cap", 0) >= len(talks))

# ── ⑤ 제작 (short90.talkers 의 옴니 길) ─────────────────────
import short90                                               # noqa: E402
import still as ST                                           # noqa: E402
import omni                                                  # noqa: E402

out0 = short90.OUT
tmp3 = Path(tempfile.mkdtemp(prefix="make_", dir=WORK))
calls = []
saved = (omni.make, short90.has_audio, short90.has_speech, short90.talk_trim)
try:
    short90.OUT = tmp3
    (tmp3 / "stills").mkdir(parents=True)
    (tmp3 / "cards").mkdir(parents=True)
    for c in doc["cuts"]:
        (tmp3 / "stills" / f"c{c['n']:02d}.png").write_bytes(b"P" * 60000 + bytes([c["n"]]))
    for p in doc["cast"]:
        nm = short90.ST_NAME.get(p["name"], p["name"])
        (tmp3 / "cards" / f"{nm}.png").write_bytes(b"C" * 60000)

    def fake_make(prompt, images, out, sec, task="image_to_video", ratio="9:16"):
        calls.append({"prompt": prompt, "images": [Path(i).name for i in images],
                      "sec": sec, "task": task})
        Path(out).write_bytes(b"V" * 80000)
        return {"krw": 0}

    omni.make = fake_make
    short90.has_audio = lambda p: True
    short90.has_speech = lambda p: True
    short90.talk_trim = lambda p, s: None
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        short90.talkers(doc)
    first = list(calls)
    with contextlib.redirect_stdout(io.StringIO()):
        short90.talkers(doc)                      # 다시 누름 — 0원이어야 한다
    again = calls[len(first):]
    ok_ok = all(short90.talk_ok(c, tmp3 / "talk" / f"c{c['n']:02d}.mp4",
                                tmp3 / "stills" / f"c{c['n']:02d}.png")[0] for c in talks)
finally:
    short90.OUT = out0
    omni.make, short90.has_audio, short90.has_speech, short90.talk_trim = saved
    shutil.rmtree(tmp3, ignore_errors=True)

ck("대사 컷마다 옴니를 한 번씩 부른다", len(first) == len(talks), f"{len(first)}")
ck("첫 그림이 그 컷 그림 · 나머지가 화면 인물의 시트 칸 (who 차례)",
   all(x["images"][0] == f"c{c['n']:02d}.png" and
       x["images"][1:] == [short90.ST_NAME.get(w, w) + ".png" for w in c["who"]]
       for x, c in zip(first, talks)))
ck("대본의 옴니 지문과 길이 그대로 산다",
   all(x["prompt"] == c["omni"] and x["sec"] == c["omni_sec"] and
       x["task"] == "image_to_video" for x, c in zip(first, talks)))
ck("다시 누르면 이미 산 것은 다시 안 산다 (0원)", not again, f"{len(again)}번 더 불렀다")
ck("조립이 산 영상을 알아본다 (talk_ok)", ok_ok)

# ── ⑥ 올리기 ─────────────────────────────────────────────
up = (ROOT / "src" / "upload.py").read_text(encoding="utf-8")
ck("올리기 벽이 대본 형식을 본다", "talkplan.part_max_sec(_doc)" in up)
ck("2분 드라마의 벽은 2분 안 (쇼츠)", talkplan.DRAMA_MAX_SEC < 120)

# ── ⑦ 단추 (관리자 페이지 · 워크플로 · 대본) ──────────────────
wf = yaml.safe_load((ROOT / ".github" / "workflows" / "short90.yml").read_text(encoding="utf-8"))
on = wf.get("on") if isinstance(wf.get("on"), dict) else wf.get(True)
opts = on["workflow_dispatch"]["inputs"]["video_kind"]["options"]
js = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
m = re.search(r"vk === 'drama' \? '([^']+)'", js)
ck("관리자 페이지의 2분 드라마 글자가 워크플로 선택지에 그대로 있다",
   bool(m) and m.group(1) in opts, f"{m.group(1) if m else '못 찾음'} · {opts}")
raw = (ROOT / ".github" / "workflows" / "short90.yml").read_text(encoding="utf-8")
env = wf["jobs"]["short90"]["env"]
ck("2분 드라마 단추가 VT_DRAMA 와 대사 영상을 켠다",
   "2분 드라마" in str(env.get("VT_DRAMA")) and "2분 드라마" in str(env.get("VT_TALK_VIDEO")))
ck("대본 형식과 단추가 어긋나면 돈 쓰기 전에 멈춘다",
   "형식 보기" in raw and raw.index("형식 보기") < raw.index("1) 인물 카드"))
ck("2분 드라마의 인물 카드는 인물 시트에서 나온다",
   'src/castsheet.py "$S" --make build/s90/cards' in raw)
sw = yaml.safe_load((ROOT / ".github" / "workflows" / "story90.yml").read_text(encoding="utf-8"))
son = sw.get("on") if isinstance(sw.get("on"), dict) else sw.get(True)
fo = son["workflow_dispatch"]["inputs"]["format"]
sraw = (ROOT / ".github" / "workflows" / "story90.yml").read_text(encoding="utf-8")
ck("대본 짓기 단추의 기본은 '알아서' (새 사건 2분 · 있던 사건 그대로)",
   fo["default"].startswith("알아서") and "60초*) ARGS=\"$ARGS --format parts\"" in sraw
   and "2분*) ARGS=\"$ARGS --format drama\"" in sraw)
ck("2분 드라마 한 번 한도는 손님이 승인한 16,000원", cost.DRAMA_RUN_KRW == 16000)

shutil.rmtree(WORK, ignore_errors=True)
print("─" * 56)
if bad:
    print(f"❌ {len(bad)}개 걸렸습니다 — 고치고 다시")
    sys.exit(1)
print("✅ 2분 드라마: 대본 · 형식 · 짓기 · 셈 · 제작 · 올리기 · 단추 모두 약속대로")
