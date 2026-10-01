#!/usr/bin/env python3
"""⭐ **2분 드라마 카메라** 가 약속대로인가 — 값 0원 · 인터넷 0회

    python3 tools/camera_check.py

2026-10-01 손님 승인 (반려동물 식당 쇼츠 · 해양생물 쇼츠에서 배운 것 다섯):
  ① 나레이션 컷에도 등장인물 **얼굴** (손님: "나레이션컷에서도 등장인물 얼굴
     나오는거로 반영해") — 옛 여러 편은 그대로 (나레이션 = 장소)
  ② 구도 계획 — 크기·방향 꼬리표 · 이웃 컷은 **둘 다** 다르게 · 특수 구도 4번까지
  ③ 그림이 나온 뒤 이웃 컷끼리 견주어 닮은 컷만 한 번 다시 (한 편 2장까지)
  ④ 그림 먼저 확인 → 고칠 컷만 다시 → 그다음 영상 (그림만 만드는 실행은 영상을 안 산다)
  ⑤ 카메라 — 옴니는 초 단위 카메라 시간표 · 그림은 부드럽게 출발·멈춤 + 이름이
     들리는 순간 얼굴로 · 증거를 말하는 순간 그 물건 확대 화면

진짜 대본 꼴(tools/fixtures/drama_story.json)을 진짜 코드에 흘려 본다. 그림
만들기(still.gen)만 가짜로 바꾼다 — 돈이 나가는 자리이기 때문이다.
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
# ⚠️ 시험은 진짜 상태 파일을 건드리지 않는다 (CLAUDE.md · VT_SHORTS_STATE)
WORK = ROOT / "build" / "_camera_check"
shutil.rmtree(WORK, ignore_errors=True)
WORK.mkdir(parents=True, exist_ok=True)
os.environ["VT_SHORTS_STATE"] = str(WORK / "shorts.json")

from PIL import Image, ImageDraw                             # noqa: E402

import lookalike                                             # noqa: E402
import series                                                # noqa: E402
import story90 as S                                          # noqa: E402

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


print("⭐ 2분 드라마 카메라 점검 — 값 0원\n")

# ── ① 나레이션 컷에도 등장인물 얼굴 ──────────────────────────────
print("① 나레이션 컷에도 등장인물 얼굴")
good = story()
ck("좋은 대본은 그대로 통과한다", not S.check(good, new=True), str(S.check(good)[:2]))
narr = {"n": 1, "who": ["아내"], "turns": [["나레이션", "가"]], "scene": "x"}
talk = {"n": 2, "who": ["아내"], "turns": [["아내", "가"]], "scene": "x"}
ck("2분 드라마 나레이션 컷은 얼굴을 그린다 (still_who)",
   S.still_who(narr, True) == ["아내"] and S.still_who(talk, True) == ["아내"])
ck("옛 여러 편 나레이션 컷은 그대로 장소다 (still_who)", S.still_who(narr, False) == [])

d = story()
for c in d["cuts"]:
    if S.is_narr_cut(c):
        c["who"] = []
        c["scene"] = "an empty kitchen table under a dim lamp"
ck("나레이션 컷이 빈 방이면 규격 검사가 잡는다",
   any("나레이션 컷 화면에 등장인물이 없다" in b for b in S.check(d, new=True)))
log = S.autofix(d)
miss = [c["n"] for c in d["cuts"] if S.is_narr_cut(c) and not c.get("who")]
ck("autofix 가 0원으로 그 순간의 인물을 세운다", not miss and log, str(miss))
c1 = d["cuts"][0]
ck("나레이션이 부른 이름을 먼저 세운다 (컷1 '아내는 은행에서…')", c1["who"] == ["아내"],
   str(c1["who"]))
ck("화면 묘사에 그 이름을 적어 그림 모델이 누구를 그릴지 안다",
   all(any(w in c["scene"] for w in c["who"]) for c in d["cuts"] if S.is_narr_cut(c)))
ck("세운 사람은 전부 등장인물(cast) 안이다 (등장인물 외 사람 금지)",
   all(set(c["who"]) <= {p["name"] for p in d["cast"]} for c in d["cuts"]))
ck("한 화면에 둘까지", all(len(c["who"]) <= S.DRAMA_NARR_WHO_MAX
                          for c in d["cuts"] if S.is_narr_cut(c)))
ck("손본 대본은 규격을 통과한다", not S.check(d, new=True), str(S.check(d)[:2]))
old = json.loads((ROOT / "data" / "series" / "S93.story.json").read_text(encoding="utf-8"))
o2 = json.loads(json.dumps(old))
S.autofix(o2)
ck("옛 여러 편(S93)은 autofix 가 나레이션에 사람을 안 세운다",
   [c.get("who") for c in o2["cuts"]] == [c.get("who") for c in old["cuts"]])

# ── 대본 짓기 (build_short90) ─────────────────────────────────
import build_short90 as B                                    # noqa: E402


def build(st):
    tmp = Path(tempfile.mkdtemp(prefix="b_", dir=WORK))
    sp, op, mp = tmp / "S999.story.json", tmp / "S999.json", tmp / "S999.meta.json"
    sp.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    was = B.paths
    B.paths = lambda sid: (sp, op, mp)
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            B.main(["S999"])
    finally:
        B.paths = was
        B.SHEET_REFS = False
    return json.loads(op.read_text(encoding="utf-8"))


doc = build(good)
cuts = doc["cuts"]
nar = [c for c in cuts if c["narr"]]
ck("나레이션 그림 지문에 인물이 선다 (PEOPLE · 입은 다문다)",
   nar and all("PEOPLE:" in c["still"] and "Mouths closed" in c["still"] for c in nar))
ck("나레이션 그림 지문이 '빈 장소' 판이 아니다",
   not [c["n"] for c in nar if "The place itself is the subject" in c["still"]])
ck("얼굴이 또렷한 구도만 — 뒷모습·실루엣·작게 담기 없음",
   not [c["n"] for c in cuts if re.search(r"from behind|silhouette|small against|"
                                          r"leaves the person small|face not visible",
                                          c["still"], re.I)])
ck("그림 지문의 인물 이름이 PEOPLE 줄과 같다 (아내 → WIFE)",
   all("SHOT: 아내" not in c["still"] for c in cuts))
oldstill = B.still_prompt({"n": 5, "who": ["아내"], "turns": [["나레이션", "시험"]],
                           "scene": "a thick folder is placed on a large wooden desk"})
ck("옛 형식 나레이션 그림은 그대로 장소 판이다",
   "The place itself is the subject" in oldstill and "PEOPLE:" not in oldstill)

# ── ② 구도 계획 ──────────────────────────────────────────────
print("\n② 구도 계획 — 크기·방향 · 이웃 컷은 둘 다 다르게 · 특수 구도 4번까지")
shots = [c.get("shot") for c in cuts]
ck("컷마다 구도 계획이 붙는다", all(shots), str([c["n"] for c in cuts if not c.get("shot")]))
pairs = list(zip(shots, shots[1:]))
both = [(i + 2) for i, (a, b) in enumerate(pairs)
        if a["size"] == b["size"] or a["dir"] == b["dir"]]
ck("이웃한 두 컷은 크기와 방향이 **둘 다** 다르다", not both, f"컷 {both}")
ck("이웃한 두 컷은 움직임도 다르다",
   not [(i + 2) for i, (a, b) in enumerate(pairs) if a["move"] == b["move"]])
plan = B.plan_shots(good["cuts"], {cuts[-2]["n"]})
spec = sum(1 for p in plan if p and p["special"])
ck(f"특수 구도(유리·문틀)는 {B.SPECIAL_MAX}번까지 ({spec}번)", spec <= B.SPECIAL_MAX)
plan3 = B.plan_shots([dict(c, n=i) for i, c in enumerate(good["cuts"] * 3, 1)])
ck("컷이 많아도 특수 구도는 한도 안 (60컷 시험)",
   sum(1 for p in plan3 if p and p["special"]) <= B.SPECIAL_MAX)
ck("같은 대본은 늘 같은 구도다 (다시 지어도 0원)",
   [c.get("shot") for c in build(story())["cuts"]] == shots)
clim = [c for c in cuts if (c.get("shot") or {}).get("key") == "climax"]
ck("결정적 순간(마지막 대사)은 얼굴 클로즈업 · 카메라를 멈춘다",
   len(clim) == 1 and clim[0]["shot"]["move"] == "hold"
   and clim[0]["n"] == max(c["n"] for c in cuts if not c["narr"]))
ck("판결 나레이션 전에는 앵글을 뒤집지 않는다 (2분 드라마는 한 편)",
   B.drama_flip_from(good["cuts"]) > 1)
talks = [c for c in cuts if not c["narr"]]
TABLE = {s_["key"]: s_ for s_ in (B.FACE_SHOTS + B.TWO_SHOTS + B.OTS_SHOTS
                                  + [B.CLIMAX_SHOT])}
twin, dup = [], []
for c in talks:
    head = TABLE[c["shot"]["key"]]["text"].split("{")[0][:24]
    if head not in c["still"] or head not in c["omni"]:
        twin.append(c["n"])
    sl = [x for x in c["omni"].splitlines() if x.startswith("SHOT:")][0]
    if "already under way" in sl:
        dup.append(c["n"])
ck("그림과 옴니 영상이 같은 구도 계획을 읽는다 (잣대 한 벌)", not twin, str(twin))
ck("옴니 SHOT 줄에는 움직임을 안 겹쳐 적는다 (시간표가 맡는다)", not dup, str(dup))

# ── ⑤-1 옴니 카메라 시간표 ────────────────────────────────────
print("\n⑤-1 옴니 대사 컷 — 초 단위 카메라 시간표")
rows_ok, neg = [], []
for c in talks:
    tl = c["omni"].split("TIMELINE:")[1].split("DIALOGUE:")[0]
    rows = [r for r in tl.splitlines() if r.strip().startswith("[")]
    if not rows or not all("Camera:" in r for r in rows):
        rows_ok.append(c["n"])
    h = series.negative_words(c["omni"]) + series.risky_words(c["omni"])
    if h:
        neg.append((c["n"], h))
ck("시간표 구간마다 카메라가 적힌다", not rows_ok, str(rows_ok))
ck("카메라 지시에 '하지 마'·걸리는 낱말이 없다", not neg, str(neg[:2]))
ck("끝 구간에서 카메라가 멈춰 선다 (컷 끝에서 흐트러지지 않게)",
   all(re.search(r"(settles to a stop|locked off until the end)",
                 c["omni"].split("TIMELINE:")[1].split("DIALOGUE:")[0].strip().splitlines()[-1])
       for c in talks))
ck("결정적 순간은 시간표 내내 카메라가 멈춰 있다",
   all("locked off" in r for r in
       clim[0]["omni"].split("TIMELINE:")[1].split("DIALOGUE:")[0].strip().splitlines()))

# ── ⑤-2 그림 컷 카메라 (켄번즈) ───────────────────────────────
print("\n⑤-2 그림 컷 — 부드럽게 출발·멈춤 · 이름이 들리는 순간 얼굴로")
import short90 as S9                                         # noqa: E402

c1 = next(c for c in cuts if c["n"] == 1)
sec = 7.0
p = S9.drama_path(c1, sec)
want = S9.key_time(c1, sec, ["아내"])
ck("이름이 들리는 순간 다가가기 시작한다",
   want is not None and abs(p["t1"] - max(0.3, want - S9.NAME_EARLY)) < 1e-6,
   f"{p['t1']} vs {want}")
zs = [S9.path_at(p["z"], p["t1"], p["t2"], k / S9.FPS) for k in range(int(sec * S9.FPS) + 1)]
ys = [S9.path_at(p["y"], p["t1"], p["t2"], k / S9.FPS) for k in range(int(sec * S9.FPS) + 1)]
step = max(abs(a - b) for a, b in zip(zs, zs[1:]))
ck(f"한 프레임 줌 변화가 {S9.STEP_MAX} 이하 (계단식 줌 금지 · 최대 {step:.4f})",
   step <= S9.STEP_MAX)
ck("줌이 흐려지지 않는 범위 안 (1.0~1.30)", 1.0 <= min(zs) and max(zs) <= 1.30)
ck("세로 자리가 화면 안 (0~1)", 0.0 <= min(ys) and max(ys) <= 1.0)
ck("천천히 출발한다 (첫 프레임 변화가 아주 작다)", abs(zs[1] - zs[0]) < 1e-3)
ck("천천히 멈춘다 (얼굴에 닿고 나면 거의 안 움직인다)", abs(zs[-1] - zs[-2]) < 1e-4)
c3 = next(c for c in cuts if c["n"] == 11)          # 이름 없는 나레이션도 부드럽게
q = S9.drama_path(dict(c3, turns=[["나레이션", "끝까지 한 발도 물러서지 않았습니다."]]), 6.0)
zq = [S9.path_at(q["z"], q["t1"], q["t2"], k / S9.FPS) for k in range(181)]
ck("이름이 없으면 부드럽게 한 번 움직인다 (처음·끝이 느리다)",
   abs(zq[1] - zq[0]) < 1e-3 and abs(zq[-1] - zq[-2]) < 1e-3 and zq[0] != zq[-1])
old_c = {"n": 3, "who": [], "turns": [["나레이션", "가"]]}
ck("옛 형식 컷은 옛 켄번즈 그대로 (shot 이 없으면 옛 길)",
   "zoompan=z='" in S9.still_bg(old_c, Path("x.png"), 5.0)[1]
   and "pow(" not in S9.still_bg(old_c, Path("x.png"), 5.0)[1])

# ── ⑤-3 증거 확대 화면 ───────────────────────────────────────
print("\n⑤-3 증거 확대 화면")
ins_cuts = [c for c in cuts if c.get("insert")]
ck("대본의 증거 확대가 짓기로 넘어온다 (그림 지문까지)",
   len(ins_cuts) == 2 and all(c["insert"].get("still") for c in ins_cuts))
PERSON = re.compile(r"\b(person|people|man|woman|men|women|face|faces|hand|hands|"
                    r"wife|husband|lawyer|skin)\b", re.I)
ck("확대 그림 지문에 사람 낱말이 없다 (낯선 사람이 안 들어온다)",
   not [c["n"] for c in ins_cuts if PERSON.search(c["insert"]["still"])])
ck("확대 그림 지문에 글자 금지 줄이 있다", all(B.NO_TEXT in c["insert"]["still"]
                                         for c in ins_cuts))
dp = doc["talk"]["drama"]
ck("그림값에 확대 그림이 들어간다", dp.get("inserts") == 2 and dp["still_krw"] >= 0)
bad_ins = story()
cc = [c for c in bad_ins["cuts"] if S.is_narr_cut(c)]
cc[0]["insert"] = {"word": "없는낱말", "thing": "a folded document"}
cc[1]["insert"] = {"word": cc[1]["turns"][0][1][:2], "thing": "the wife holding a phone"}
cc[2]["insert"] = {"word": cc[2]["turns"][0][1][:2], "thing": "녹음기"}
fx = S.fix_inserts(bad_ins)
left = [c["n"] for c in bad_ins["cuts"] if c.get("insert")]
ck("틀린 확대 표시는 0원으로 뺀다 (없는 낱말 · 사람 · 한글)",
   cc[0]["n"] not in left and cc[1]["n"] not in left and cc[2]["n"] not in left, str(fx))
ck("한 편에 둘까지만 남긴다", len(left) <= S.DRAMA_INSERT_MAX)
c5 = next(c for c in cuts if c.get("insert"))
sp_ = S9.insert_span(c5, 7.0)
kt = S9.key_time(c5, 7.0, [c5["insert"]["word"]])
ck("그 낱말이 들리는 순간 확대 화면으로 넘어간다", sp_ and abs(sp_[0] - max(0.2, kt - 0.05)) < 1e-6,
   f"{sp_} vs {kt}")
ck("끝에 얼굴이 조금만 남으면 확대 화면으로 맺는다 (깜빡 돌아오지 않는다)",
   all((b == s) or (s - b >= 0.6) for s in (3.0, 4.0, 5.0, 7.0, 9.0)
       for a, b in [S9.insert_span(c5, s) or (0, s)]))

# 진짜로 한 컷 만들어 본다 (ffmpeg · 그림은 가짜)
tmp = Path(tempfile.mkdtemp(prefix="r_", dir=WORK))
im = Image.new("RGB", (900, 1600), (40, 50, 60))
ImageDraw.Draw(im).ellipse((300, 400, 600, 760), fill=(200, 160, 140))
im.save(tmp / f"c{c5['n']:02d}.png")
im2 = Image.new("RGB", (900, 1600), (90, 70, 40))
ImageDraw.Draw(im2).rectangle((200, 600, 700, 1000), fill=(230, 230, 220))
im2.save(tmp / f"i{c5['n']:02d}.png")
Image.new("RGBA", (S9.W, S9.H), (0, 0, 0, 0)).save(tmp / "blank.png")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                "sine=frequency=220:duration=5", "-ar", "24000", "-ac", "1",
                str(tmp / "v.wav")], check=True)
sec5, _ = S9.cut_sec(c5, tmp / "v.wav", None)
try:
    S9.cut_video(c5, tmp / f"c{c5['n']:02d}.png", tmp / "v.wav", None,
                 [(tmp / "blank.png", 0.0, sec5)], tmp / "out.mp4")
    made = (tmp / "out.mp4").exists() and abs(S9.dur_of(tmp / "out.mp4") - sec5) < 0.15
except Exception as e:                                       # noqa: BLE001
    made, sec5 = False, str(e)[:120]
ck("확대 화면이 든 컷이 실제로 만들어진다 (길이 그대로)", made, str(sec5))
if made:
    a, b = S9.insert_span(c5, sec5)
    fr = []
    for t in (max(0.05, a - 0.4), (a + b) / 2):
        f = tmp / f"f{t:.2f}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i",
                        str(tmp / "out.mp4"), "-frames:v", "1", str(f)], check=True)
        fr.append(Image.open(f).convert("RGB").resize((9, 16)).getpixel((4, 2)))
    ck("확대 화면 동안에는 그 물건 그림이 보인다 (배경 색이 바뀐다)",
       abs(fr[0][0] - fr[1][0]) + abs(fr[0][2] - fr[1][2]) > 40, str(fr))

# ── ③ 이웃 컷 닮음 → 한 번 다시 ───────────────────────────────
print("\n③ 이웃 컷이 같은 구도로 보이면 그 컷만 한 번 다시")
a_ = tmp / "a.png"
b_ = tmp / "b.png"
im.save(a_)
im3 = Image.new("RGB", (900, 1600), (40, 50, 60))
ImageDraw.Draw(im3).ellipse((40, 1200, 160, 1400), fill=(200, 160, 140))
im3.save(b_)
ck("같은 그림은 닮음이 잣대 이상", (lookalike.likeness(a_, a_) or 0) >= lookalike.SAME)
ck("짜임이 다른 그림은 잣대 아래", (lookalike.likeness(a_, b_) or 1) < lookalike.SAME)

# ── ④ 그림 먼저 · 고칠 컷만 다시 (stills 를 가짜 그림으로 돌린다) ──
print("\n④ 그림 먼저 확인 → 고칠 컷만 다시 → 그다음 영상")
import still as ST                                           # noqa: E402

calls = []


def fake_gen(prompt, out, refs=(), ratio="16:9", size=None, seed=None, label=""):
    n = Path(out).stem
    calls.append({"out": Path(out).name, "refs": [Path(r).name for r in refs],
                  "seed": seed, "prompt": prompt})
    # ⚠️ 잡티를 깐다 — 너무 단순한 그림은 10KB 가 안 돼 '깨진 그림' 으로 보고
    #    다시 그린다 (reuse.MIN_BYTES). 잡티는 닮음 잣대(흐린 36×64)에는 안 잡힌다.
    x = Image.blend(Image.new("RGB", (450, 800), (30, 40, 50)),
                    Image.effect_noise((450, 800), 40).convert("RGB"), 0.25)
    dr = ImageDraw.Draw(x)
    # 컷2·컷3 은 일부러 같은 짜임으로 — 닮음 다시 그리기가 잡아야 한다.
    # 나머지는 홀수 왼쪽 위 · 짝수 오른쪽 아래로 번갈아 — 이웃끼리 안 닮는다.
    k = int(n[1:]) if n[1:].isdigit() else 0
    if "previous shot" in prompt:
        dr.rectangle((20, 600, 140, 780), fill=(220, 200, 180))
    elif k in (2, 3):
        dr.ellipse((150, 200, 300, 380), fill=(200, 160, 140))
    elif k % 2:
        dr.rectangle((10, 10, 210, 280), fill=(180 + k, 120, 100))
    else:
        dr.rectangle((240, 520, 440, 790), fill=(120, 180, 100 + k))
    x.save(out)
    return 0


out0 = S9.OUT
saved = ST.gen
tmp4 = Path(tempfile.mkdtemp(prefix="s_", dir=WORK))
try:
    S9.OUT = tmp4
    ST.gen = fake_gen
    (tmp4 / "cards").mkdir(parents=True)
    for p_ in doc["cast"]:
        nm = S9.ST_NAME.get(p_["name"], p_["name"])
        Image.new("RGB", (64, 64), (100, 100, 100)).save(tmp4 / "cards" / f"{nm}.png")
    with contextlib.redirect_stdout(io.StringIO()):
        S9.stills(doc)
    first = list(calls)
    narr_refs = [x for x in first if x["out"] in
                 {f"c{c['n']:02d}.png" for c in nar}]
    ck("나레이션 그림에 등장인물 얼굴 참조를 붙인다",
       narr_refs and all(x["refs"] for x in narr_refs))
    ck("증거 확대 그림을 그린다 (얼굴 참조 없이)",
       sorted(x["out"] for x in first if x["out"].startswith("i"))
       == sorted(f"i{c['n']:02d}.png" for c in ins_cuts)
       and all(not x["refs"] for x in first if x["out"].startswith("i")))
    re_ = [x for x in first if "previous shot" in x["prompt"]]
    ck("닮은 이웃 컷(2·3)에서 뒤 컷만 다시 그린다 (앞 컷을 참조로)",
       len(re_) == 1 and re_[0]["out"] == "c03.png" and re_[0]["refs"][-1] == "c02.png",
       str([x["out"] for x in re_]))
    log_ = json.loads((tmp4 / "stills" / S9.ALIKE_LOG).read_text(encoding="utf-8"))
    ck("다시 그린 기록을 그림 보관함에 남긴다", "c03" in log_)
    n0 = len(calls)
    with contextlib.redirect_stdout(io.StringIO()):
        S9.stills(doc)
    ck("다시 누르면 한 장도 안 그린다 (0원 · 닮음 다시 그리기도 한 번뿐)",
       len(calls) == n0, str([x["out"] for x in calls[n0:]]))
    os.environ["VT_REDO_STILLS"] = "4,9"
    n1 = len(calls)
    with contextlib.redirect_stdout(io.StringIO()):
        S9.stills(doc)
    again = calls[n1:]
    os.environ.pop("VT_REDO_STILLS", None)
    ck("고르신 컷(4·9)만 다시 그린다",
       sorted(x["out"] for x in again) == ["c04.png", "c09.png"],
       str([x["out"] for x in again]))
    ck("다시 그릴 때는 새 씨앗이다 (같은 그림이 또 나오지 않게)",
       all(x["seed"] != y["seed"] for x in again for y in first if x["out"] == y["out"]))
    rt = json.loads((tmp4 / "stills" / S9.RETAKE_LOG).read_text(encoding="utf-8"))
    ck("몇 번째로 다시 그렸는지 남긴다", rt.get("4") == 1 and rt.get("9") == 1, str(rt))
    import stills_view                                       # noqa: E402
    real = stills_view.ROOT
    try:
        (tmp4 / "data" / "series").mkdir(parents=True)
        (tmp4 / "data" / "series" / "S999.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        stills_view.ROOT = tmp4
        files = stills_view.make("S999", tmp4 / "stills", tmp4 / "view")
    finally:
        stills_view.ROOT = real
    view = json.loads((tmp4 / "view" / "view.json").read_text(encoding="utf-8"))
    ck("그림 미리보기 — 컷마다 줄인 그림 · 확대 그림 · view.json",
       len([f for f in files if f.startswith("v-c")]) == len(cuts)
       and len([f for f in files if f.startswith("v-i")]) == len(ins_cuts)
       and "view.json" in files)
    ck("미리보기에 다시 그린 횟수·닮음이 적힌다",
       any(r.get("retake") for r in view["cuts"]) and any("like_prev" in r for r in view["cuts"]))
    ck("미리보기 그림이 폰에 가볍다 (폭 540)",
       Image.open(tmp4 / "view" / "v-c01.jpg").size[0] == stills_view.WIDTH)
finally:
    S9.OUT = out0
    ST.gen = saved

# 워크플로 — 그림만 만드는 실행은 영상을 안 산다
raw = (ROOT / ".github" / "workflows" / "short90.yml").read_text(encoding="utf-8")
wf = yaml.safe_load(raw)
on = wf.get("on") if isinstance(wf.get("on"), dict) else wf.get(True)
steps = {s_.get("name", ""): s_ for s_ in wf["jobs"]["short90"]["steps"]}
talk_run = next(v["run"] for k, v in steps.items() if k.startswith("2-3)"))
ck("그림만 만드는 실행(step=stills)은 옴니 영상을 안 산다",
   '[ "$STEP" = "all" ]' in talk_run)
ck("그림만 만드는 실행은 조립·올리기를 안 한다",
   steps["4) 한 편으로 조립"].get("if") == "env.STEP != 'stills'"
   and next(v for k, v in steps.items() if k.startswith("릴리스에 올리기")).get("if")
   == "env.STEP != 'stills'")
ck("다시 그릴 컷을 받는다 (redo → VT_REDO_STILLS)",
   "redo" in on["workflow_dispatch"]["inputs"]
   and "VT_REDO_STILLS" in str(steps["2) 컷 그림 (세로 9:16 · 장수는 대본이 정한다)"].get("env")))
ck("2분 드라마는 그림 미리보기를 올린다",
   any("stills_view.py" in str(v.get("run")) for v in steps.values()))
js = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
ck("관리자 페이지가 미리보기를 읽는다 (/api/stills-view)",
   "url.pathname === '/api/stills-view'" in js and "stillsview-${sid}" in js)
ck("관리자 페이지가 step·redo 를 워크플로로 넘긴다",
   "body.step === 'stills'" in js and "redo: redo" in js)

shutil.rmtree(WORK, ignore_errors=True)
print("─" * 56)
if bad:
    print(f"❌ {len(bad)}개 걸렸습니다 — 고치고 다시")
    sys.exit(1)
print("✅ 2분 드라마 카메라: 나레이션 얼굴 · 구도 계획 · 닮음 다시 · 그림 먼저 · 카메라 무빙 · 증거 확대")
