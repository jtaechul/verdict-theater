#!/usr/bin/env python3
"""⭐ 1분 전부 영상 드라마 점검 — 값 0원 · 인터넷 0회 · 열쇠 없이

    python3 tools/drama60_check.py

2026-10-02 손님: "1분이면 이미지 필요 없이 그냥 전체 다 영상으로" · "360p 9대16" ·
"1.28배" · "쉬는 공간 없이" · "카메라·구도 다채롭게" — 시험작 S94 로 처음 만들었다.

  ① 카메라 계획   이웃 컷은 렌즈·높이·움직임 둘 이상 다름 · 특별 시점 2번까지 · 뒤집히는
                  나레이션은 돌리줌 · 장소 첫 방문은 어디인지 보여 주기 · 마지막은 멀어지기
  ② 영상 지문     대사 컷은 대본 그대로 + 고정 목소리 + 또박또박 · 나레이션 컷은 입을 다문다
  ③ 360p 값       720p 의 약 3분의 1 · make() 가 화질을 그대로 보낸다
  ④ 목소리 파일   wav 안의 wav(머리말 틱 · 끝 출처 글 잡음)를 벗긴다 · 지시문 낭독을 길이로 잡는다
  ⑤ 대사 후처리   말 앞뒤만 남기고 화면·소리를 함께 1.28배 · 나레이션 컷은 멈춘 얼굴까지
  ⑥ 길이 규격     all_video 대본은 13~40컷 · 대사 4~7 · 벽은 쇼츠 한도(3분) · 말 사이 쉼은 대본이
  ⑦ 처음 보는 사람용 이름표 · 관계 한 줄 · 가명
  ⑧ 영상 창고      같은 장면은 다시 안 산다 · 액자 테두리
  ⑨ 설명 드라마(v5) 그림 컷 0원 · 이름표 「윤정숙 (딸)」 · 대목 표시 · 자막 덩어리 · 끝 멈춤
  ⑩ 기본 짜임       style="explainer" 하나로 쉼 0.5 · 이름표 · 끝 글 · 대본 검사(화면 속 사람 =
                    나레이션 · 이름 + 씨 · 헷갈리는 말 · 그림 맞물림) · 검수 시간표 · 받아쓰기 비교
                    (2026-10-02 손님: "앞으로 우리가 제작하는 영상에서도 동일한 방식으로")

⚠️ ①②⑦⑧ 은 1분 시험작(S94 v3) 그대로의 고정 대본(tools/fixtures/drama60_s94_v3.json)으로 본다.
   지금 S94 는 손님이 고르신 v5(약 2분 50초 · 그림 컷 17개)로 바뀌었다 (2026-10-02).
"""
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["VT_SID"] = "S94"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import camera60 as C                                          # noqa: E402
import drama60 as D                                           # noqa: E402
import omni                                                   # noqa: E402
import short90 as S9                                          # noqa: E402
import story90 as T                                           # noqa: E402
import talkplan                                               # noqa: E402
import tts                                                    # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


doc = json.loads((ROOT / "tools" / "fixtures" / "drama60_s94_v3.json").read_text(encoding="utf-8"))
cuts = doc["cuts"]
live = json.loads((ROOT / "data" / "series" / "S94.json").read_text(encoding="utf-8"))

print("⭐ 1분 전부 영상 드라마 점검\n")
print("① 카메라 계획")
shots = C.plan(cuts)
ck("규칙 검사가 깨끗하다", not C.check(cuts, shots), "; ".join(C.check(cuts, shots)))
ck("이웃 컷은 렌즈·높이·움직임 가운데 둘 이상 다르다",
   all(C.diff(a, b) >= C.MIN_DIFF for a, b in zip(shots, shots[1:])))
ck(f"특별한 시점은 {C.SPECIAL_MAX}번까지", sum(s["special"] for s in shots) <= C.SPECIAL_MAX)
tw = [i for i, c in enumerate(cuts) if c["narr"] and C.is_twist(c)]
ck("뒤집히는 나레이션(그런데…)은 돌리줌", tw and all(shots[i]["key"] == "n-dolly-zoom"
                                             for i in tw), str(tw))
ck("첫 컷은 어디인지 보여 주는 구도", shots[0]["kind"] == "est", shots[0]["key"])
ck("마지막 나레이션은 멀어지는 구도", shots[-1]["kind"] == "end", shots[-1]["key"])
ck("대사 컷은 크게 안 움직인다 (입이 또렷하게)",
   all(s["kind"] == "talk" and s["move"] in ("static", "push", "drift", "handheld")
       for c, s in zip(cuts, shots) if not c["narr"]))
again = C.plan(cuts)
ck("같은 대본은 늘 같은 계획 (다시 지어도 0원)", [s["key"] for s in again] == [s["key"] for s in shots])
ck("한 편에 쓰인 구도가 여덟 가지 이상이다", len({s["key"] for s in shots}) >= 8,
   str(len({s["key"] for s in shots})))

print("\n② 영상 지문")
by = D.cast_of(doc)
talk = next(c for c in cuts if not c["narr"])
narr = next(c for c in cuts if c["narr"])
sh_t = shots[cuts.index(talk)]
sh_n = shots[cuts.index(narr)]
pt = D.prompt(talk, sh_t, 4, by)
pn = D.prompt(narr, sh_n, 5, by)
ck("대사 컷 — 대본 대사를 글자 그대로 말한다", f'"{talk["turns"][0][1]}"' in pt)
sp = by[talk["turns"][0][0]]
ck("대사 컷 — 고정 목소리 줄(나이·성별·톤)이 들어간다", T.voice_line(sp) in pt)
ck("대사 컷 — 또박또박", "clearly articulated" in pt)
ck("나레이션 컷 — 아무도 말하지 않고 입을 다문다",
   "nobody speaks" in pn and "mouth stays closed" in pn)
ck("참조 그림 표시가 화면 인물 수와 같다",
   pt.split("\n")[0].count("@Image") == len(talk["who"]))
ck("화면에 글자 금지 · 참조는 얼굴만 (첫 장면으로 안 쓴다)",
   "no subtitles" in pt and D.REF_ONLY in pt)
ck("한국어 이름이 영어 역할로 바뀌어 들어간다", "딸" not in pn.split("TIMELINE")[0][:900])

print("\n③ 360p 값")
k360, k720 = omni.est_krw(10, "360p"), omni.est_krw(10, "720p")
ck("360p 어림값은 720p 의 3분의 1 남짓", 0.30 < k360 / k720 < 0.40, f"{k360:.0f}/{k720:.0f}")
ck("720p 어림값은 예전 단가표 그대로", abs(k720 - S9.cost.video_krw(omni.MODEL, 10)) < 1)
src = (ROOT / "src" / "omni.py").read_text(encoding="utf-8")
ck("make() 가 받은 화질을 그대로 보낸다", '"resolution": res,' in src)
ck("1분 전부 영상은 360p 로 산다", D.RES == "360p")

print("\n④ 목소리 파일")
pcm = (b"\x10\x00\xf0\xff" * 2400)
inner = io.BytesIO()
with wave.open(inner, "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(24000)
    w.writeframes(pcm)
blob = inner.getvalue() + b"C2PA manifest SynthID trailer" * 20
got, r = tts.unwrap(blob, 16000)
ck("wav 통째로 와도 소리 칸만 꺼낸다 (끝 출처 글은 버린다)", got == pcm and r == 24000)
ck("날것이면 그대로 둔다", tts.unwrap(pcm, 24000) == (pcm, 24000))
got2, _ = tts.unwrap(b"RI\x00\x00" + blob, 24000)
ck("앞에 몇 바이트가 끼어 있어도 찾는다", got2 == pcm)
with tempfile.TemporaryDirectory() as t:
    f = Path(t) / "x.wav"
    with wave.open(str(f), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(blob[: len(blob) // 2 * 2])
    ck("이미 만든 파일도 벗긴다 (0원)", tts.unwrap_file(f))
    ck("두 번째는 손대지 않는다", not tts.unwrap_file(f))
line = "땅주인이 딸에게 어머니 묘를 파내라는 소장을 보냈습니다."
ck("지시문까지 읽은 길이(8.8초)를 잡는다", tts.read_aloud(b"\x00\x00" * int(24000 * 8.8), 24000, line))
ck("정상 길이(5.1초)는 그대로 둔다", not tts.read_aloud(b"\x00\x00" * int(24000 * 5.1), 24000, line))

print("\n⑤ 대사·나레이션 후처리 (실제로 돌려 본다)")
with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    raw = t / "raw.mp4"
    # 1초 조용 · 2초 말소리(톤) · 1초 조용 — 옴니 대사 컷과 같은 모양
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=gray:s=360x640:r=24:d=4", "-f", "lavfi", "-i",
                    "aevalsrc='0.4*sin(2*PI*220*t)*between(t,1,3)+0.001*sin(2*PI*50*t)'"
                    ":s=48000:d=4", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-ac", "2", str(raw)], check=True)
    out = t / "talk.mp4"
    D.post_talk(raw, out)
    want = (2.0 + D.TALK_LEAD + D.TALK_TAIL) / S9.SPEED
    ck("대사 컷은 말 앞뒤만 남기고 1.28배 (화면 길이)", abs(S9.dur_of(out) - want) < 0.25,
       f"{S9.dur_of(out):.2f} vs {want:.2f}")
    ck("소리도 같이 감긴다 (입이 안 어긋난다)", S9.has_audio(out))
    sq = t / "narr.mp4"
    D.post_narr(raw, sq, 3.2, land=True)
    ck("멈추는 구도는 나레이션 길이에 맞춰 빠르게 담는다 (멈춘 얼굴까지)",
       abs(S9.dur_of(sq) - 3.2) < 0.2, f"{S9.dur_of(sq):.2f}")
    st = t / "narr2.mp4"
    D.post_narr(raw, st, 5.0)
    ck("영상이 모자라면 화면만 느리게 늘인다 (되돌려 잇지 않는다)",
       abs(S9.dur_of(st) - 5.0) < 0.2, f"{S9.dur_of(st):.2f}")
    ck("나레이션 컷 영상에는 소리를 안 남긴다", not S9.has_audio(st))

print("\n⑥ 길이 규격 (60초 벽을 풀었다 · 2026-10-02 손님)")
ck("S94 는 전부 영상 대본이다", live.get("all_video") is True)
story = json.loads((ROOT / "data" / "series" / "S94.story.json").read_text(encoding="utf-8"))
ck("S94 대본이 규격 검사를 통과한다", not T.check(story), "; ".join(T.check(story)))
ck("S94 대본이 드라마 검사를 통과한다", not T.check_drama(story), "; ".join(T.check_drama(story)))
R = T.rules_of(story)
ck("전부 영상 규격: 13~40컷 · 쇼츠 한도(3분) 안", (R["PART_MIN_CUTS"], R["PART_MAX_CUTS"]) == (13, 40)
   and R["PART_SEC_MAX"] < 180)
gap = float(T.style_get(story, "gap", T.GAP_TIGHT))
ck("길이 잣대는 말 사이 쉼(gap)만큼 컷마다 늘어난다",
   abs(T.part_sec(story["cuts"], story) -
       (T.SEC60_PER_CHAR * sum(T.chars(c) for c in story["cuts"])
        + (T.SEC60_PER_CUT + gap - T.GAP_TIGHT) * len(story["cuts"]))) < 1e-6)
ck("2분 드라마 잣대는 그대로 (손대지 않았다)",
   T.rules_of({"format": "drama"})["PART_MAX_CUTS"] == 24
   and abs(T.part_sec(story["cuts"]) - (T.SEC_PER_CHAR * sum(T.chars(c) for c in story["cuts"])
                                         + T.SEC_PER_CUT * len(story["cuts"]))) < 1e-6)
ck("벽 — 전부 영상은 쇼츠 한도 179.5초 · 2분 드라마 2분 · 옛 여러 편 60초",
   talkplan.part_max_sec(live) == talkplan.SHORTS_MAX_SEC == 179.5
   and talkplan.part_max_sec({"format": "drama"}) == talkplan.DRAMA_MAX_SEC
   and talkplan.part_max_sec({}) == 59.5)
s9 = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
ck("말 사이 쉼은 대본이 정한다 (없으면 0.12초)",
   S9.PAD_TIGHT == 0.12 and "PAD = gap_of(doc)" in s9 and S9.gap_of({}) == 0.12
   and S9.gap_of({"gap": 0.5}) == 0.5)
ck("조립은 옴니 영상 폴더(video60)를 읽는다", "video_dir() / f\"c{n:02d}.mp4\"" in s9)

print("\n⑦ 처음 보는 사람용 (인물 이름 · 관계)")
story_cast = {p["name"]: p.get("intro") for p in story["cast"]}
ck("대본 인물마다 관계 한 줄(intro)이 살아 있다 (꼴 맞추기가 안 지운다)",
   all(story_cast.values()), str(story_cast))
it = S9.intro_of(doc)
firsts = {}
for c in cuts:
    for w in ([c["turns"][0][0]] if not c["narr"] else c["who"]):
        firsts.setdefault(w, c["n"])
ck("사람마다 **처음 나오는 컷**에 이름과 관계가 뜬다",
   all(it.get(n, ("", ""))[0] == w and it[n][1] for w, n in firsts.items()), str(it))
later = [c for c in cuts if c["narr"] and c["n"] not in firsts.values()]
ck("그 뒤 나레이션 컷에도 화면 속 사람 이름표가 뜬다 (관계는 다시 안 붙인다)",
   all(it.get(c["n"]) == (c["who"][0], "") for c in later), str(later[:1]))
with tempfile.TemporaryDirectory() as t:
    a, b = Path(t) / "a.png", Path(t) / "b.png"
    nc = next(c for c in cuts if c["narr"])
    S9.overlay(nc, a, None, now=0, mark="x")
    S9.overlay(nc, b, None, now=0, mark="x", intro=("딸", "어머니 묘를 지키는 친딸"))
    from PIL import Image, ImageChops
    box = (0, S9.NAME_Y - 20, S9.W, S9.NAME_Y + 80)
    ck("나레이션 컷에도 이름표가 실제로 그려진다",
       ImageChops.difference(Image.open(a).crop(box), Image.open(b).crop(box)).getbbox()
       is not None)
al = S9.aliases_of(doc)
ck("인물마다 가명이 있다 (이름표가 '딸 (윤정숙)' 이 된다)", len(al) == len(doc["cast"]), str(al))
with tempfile.TemporaryDirectory() as t:
    from PIL import Image, ImageChops
    a, b = Path(t) / "a.png", Path(t) / "b.png"
    tc0 = next(c for c in cuts if not c["narr"])
    S9.overlay(tc0, a, None, now=0, mark="x")
    S9.overlay(tc0, b, None, now=0, mark="x", alias=al)
    box = (0, S9.NAME_Y - 20, S9.W, S9.NAME_Y + 80)
    ck("이름표에 가명이 괄호로 실제로 그려진다",
       ImageChops.difference(Image.open(a).crop(box), Image.open(b).crop(box)).getbbox()
       is not None)
    e1, e2 = Path(t) / "e1.png", Path(t) / "e2.png"
    S9.end_card(S9.TAIL_LAST, e1)
    S9.end_card(S9.TAIL_LAST, e2, note=S9.ALIAS_NOTE)
    ck("끝 화면에 '등장인물 이름은 모두 가명입니다' 가 붙는다",
       ImageChops.difference(Image.open(e1), Image.open(e2)).getbbox() is not None)
s1 = dict(story, cast=[dict(story["cast"][0], alias="Kim")] + story["cast"][1:])
ck("가명은 한글 2~4자 — 아니면 대본 검사가 잡는다",
   any("가명" in x for x in T.check_drama(s1)))
s2 = dict(story, cast=[dict(p, alias="윤정숙") for p in story["cast"]])
ck("가명이 겹치면 대본 검사가 잡는다", any("가명이 겹친다" in x for x in T.check_drama(s2)))
bad_cast = [dict(story["cast"][0], intro="가" * 30)]
ck("관계 한 줄이 너무 길면 대본 검사가 잡는다",
   any("관계 한 줄" in x for x in T.check_drama(dict(story, cast=bad_cast + story["cast"][1:]))))

print("\n⑧ 영상 창고 (같은 장면은 다시 안 산다)")
c0 = dict(cuts[0])
ck("컷 번호·나레이션이 바뀌어도 같은 장면이면 같은 영상",
   D.vkey(c0) == D.vkey(dict(c0, n=9, turns=[["나레이션", "다른 말"]])))
tc = next(c for c in cuts if not c["narr"])
ck("대사 컷은 대사가 바뀌면 다른 영상 (입이 안 맞는다)",
   D.vkey(tc) != D.vkey(dict(tc, turns=[[tc["turns"][0][0], "다른 대사"]])))
ck("화면 묘사가 바뀌면 다른 영상", D.vkey(c0) != D.vkey(dict(c0, scene="x")))
pins = {0: shots[0], 5: shots[5]}
again2 = C.plan(cuts, pinned=pins)
ck("이미 산 영상의 구도는 계획에서 그대로 고정된다",
   again2[0]["key"] == shots[0]["key"] and again2[5]["key"] == shots[5]["key"])
ck("고정된 구도 옆도 규칙을 지킨다", not C.check(cuts, again2), "; ".join(C.check(cuts, again2)))
with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    framed, plain = t / "framed.mp4", t / "plain.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=s=288x512:r=24:d=3", "-vf",
                    "pad=360:640:36:64:color=0xA6C4BE", "-pix_fmt", "yuv420p",
                    str(framed)], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=s=360x640:r=24:d=3", "-pix_fmt", "yuv420p", str(plain)],
                   check=True)
    fb = D.frame_box(framed)
    inside = (fb is not None and fb[2] >= 33 and fb[3] >= 61
              and fb[2] + fb[0] <= 36 + 288 + 3 and fb[3] + fb[1] <= 64 + 512 + 3)
    ck("옴니의 '액자 속 그림' 테두리를 찾아 안쪽만 쓴다 (테두리는 안 남고 그림은 85% 넘게 살린다)",
       inside and fb[0] * fb[1] >= 0.85 * 288 * 512, str(fb))
    ck("테두리가 없는 영상은 손대지 않는다", D.frame_box(plain) is None)

vt = (ROOT / "tools" / "viewer_test.py").read_text(encoding="utf-8")
ck("처음 보는 시청자 시험 도구가 있다 (헷갈린 순간 · 관계 · 점수를 묻고 값을 장부에 적는다)",
   "헷갈리거나 이해가 안 된 순간" in vt and "관계" in vt and 'cost.record("검토"' in vt)

print("\n⑨ 설명 드라마 v5 (그림 컷 · 이름표 · 대목 · 자막)")
figs = [c for c in live["cuts"] if c.get("fig")]
ck("그림 컷이 있고, 그림 설계가 대본에 있다", figs and all(c["fig"]["id"] in live["figs"]
                                                       for c in figs))
rows, _bad = D.plan(live)
ck("그림 컷은 옴니를 안 산다 (값 0원)",
   all(r.get("fig") and r["krw"] == 0 for r, c in zip(rows, live["cuts"]) if c.get("fig")))
# ⚠️ 영상 창고(build/)는 이 작업 칸에만 있다 — 깃허브 자체 점검에는 없으니 그때는 건너뛴다
if (S9.video_dir() / "library.json").exists():
    ck("그림 컷 밖의 컷은 전부 창고 영상이다 (새로 사는 컷 0개)",
       all(r["lib"] for r, c in zip(rows, live["cuts"]) if not c.get("fig")),
       str([c["n"] for r, c in zip(rows, live["cuts"]) if not c.get("fig") and not r["lib"]]))
else:
    print("   ⏭  영상 창고가 없다 (깃허브) — '전부 창고 영상' 은 작업 칸에서만 본다")
lb = S9.labels_of(live)
ck("이름표는 이름이 먼저 — 「윤정숙 (딸)」 「윤기철 (배다른 남동생)」",
   lb.get("딸") == "윤정숙 (딸)" and lb.get("이복동생") == "윤기철 (배다른 남동생)", str(lb))
ck("옛 대본은 옛 이름표 그대로 (name_first 가 없으면 빈 것)", S9.labels_of(doc) == {})
ck("자막 토막 — 「윤정숙 씨」 · 「1억 5천만 원」 · 「40여 년」 이 안 갈린다",
   all(" 씨" not in x[:2] and not x.startswith("씨") for x in
       S9.chunks_of("서류상으로는 윤정숙 씨의 친동생이 된 셈입니다."))
   and any("1억 5천만 원" in x for x in S9.chunks_of("모두 1억 5천만 원을 보냈습니다."))
   and any("40여 년" in x for x in S9.chunks_of("사연은 40여 년 전으로 거슬러 올라갑니다.")))
with tempfile.TemporaryDirectory() as t:
    from PIL import Image, ImageChops
    t = Path(t)
    cc = next(c for c in live["cuts"] if c.get("chapter") and not c.get("fig"))
    a, b = t / "a.png", t / "b.png"
    S9.overlay(dict(cc, chapter=""), a, None, now=0, mark="x")
    S9.overlay(cc, b, None, now=0, mark="x")
    top = (0, S9.CHAP_Y - 40, S9.W, S9.CHAP_Y + 40)
    ck("화면 위 대목 표시가 실제로 그려진다",
       ImageChops.difference(Image.open(a).crop(top), Image.open(b).crop(top)).getbbox())
    fc = figs[0]
    S9.overlay(fc, a, None, now=0, mark="x")
    S9.overlay(dict(fc, chapter="재판"), b, None, now=0, mark="x")
    ck("그림 컷에는 대목 표시를 안 얹는다 (그림에 제목이 있다)",
       not ImageChops.difference(Image.open(a).crop(top), Image.open(b).crop(top)).getbbox())
    tc5 = next(c for c in live["cuts"] if not c["narr"])
    S9.overlay(tc5, a, None, now=0, mark="x", labels=lb, intro=(tc5["turns"][0][0], "산을 새로 산 사람"))
    S9.overlay(tc5, b, None, now=0, mark="x", labels=lb)
    up = (0, S9.NAME_Y - 90, S9.W, S9.NAME_Y - 10)
    ck("처음 나오는 사람의 관계 한 줄은 이름 **위**에 (긴 이름표 옆에 자리가 없다)",
       ImageChops.difference(Image.open(a).crop(up), Image.open(b).crop(up)).getbbox())
    import diagram60 as G
    ck("그림 설계 일곱 가지가 다 있다",
       set(G.FIGS) >= {"card", "family", "timeline", "issue", "money", "paper", "verdict"})
    sh, adds = G.schedule(live, figs[1], 6.0)
    ck("그림 요소는 신호 낱말을 말할 때 나타난다 (빈 신호는 첫머리에 차례로)",
       adds and all(0 <= tt <= 6.0 for _, tt in adds))
    later_f = next(c for c in figs[2:] if c["fig"]["id"] == figs[1]["fig"]["id"])
    sh2, _ = G.schedule(live, later_f, 6.0)
    ck("같은 그림의 뒤 컷은 앞 컷 요소를 처음부터 보인다 (그림이 이어진다)", len(sh2) >= len(adds))
    mp = t / "fig.mp4"
    G.render(live, figs[1], 0.5, mp, frames=8)
    ck("그림 컷이 실제로 영상이 된다 (1080×1920 · 소리 없음)",
       mp.exists() and S9.dur_of(mp) > 0.2 and not S9.has_audio(mp))
    raw = t / "raw.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=s=360x640:r=24:d=2", "-pix_fmt", "yuv420p", str(raw)], check=True)
    hold = t / "hold.mp4"
    D.post_narr(raw, hold, 4.5, stretch=D.STRETCH_REUSE)
    ck("창고 영상이 나레이션보다 짧으면 1.6배까지 늘이고 나머지는 끝 장면에서 멈춘다",
       abs(S9.dur_of(hold) - 4.5) < 0.25, f"{S9.dur_of(hold):.2f}")
# ⚠️ 설명 드라마는 end_note 를 안 적어도 기본 글('실제 판결을 재구성…')이 따라온다 — style 도 뺀다
s3 = {k: v for k, v in story.items() if k not in ("end_note", "style")}
ck("끝 화면 글(end_note)에 '실제' 가 없으면 마지막 컷 규칙이 다시 잡는다",
   any("마지막 컷" in x for x in T.check_drama(s3)))
ck("우리말 나레이션 — 마디 문장 · 인용 · 「한옥자 씨도」 는 주어 검사에 안 걸린다",
   not T.needs_subject("경기도 용인의 한 야산.") and not T.needs_subject("한옥자 씨도 그렇게 증언했습니다.")
   and not T.needs_subject("'한옥자, 윤기철 모자와 법적으로 다투지 않는다.'")
   and T.needs_subject("법원을 끝까지 믿었습니다."))

print("\n⑩ 설명 드라마 = 기본 짜임 (손님: \"앞으로 우리가 제작하는 영상에서도 동일한 방식으로\")")
import copy                                                   # noqa: E402
import diagram60 as G                                         # noqa: E402
import listen_check as L                                      # noqa: E402
ck("본보기 S94 대본이 설명 드라마다 (style=explainer)", T.is_explainer(story) and T.is_explainer(live))
ex = {"format": "drama", "all_video": True, "style": "explainer",
      "cast": [{"name": "딸", "alias": "윤정숙", "tag": "딸"}]}
ck("style 하나로 쉼 0.5초 · 이름표 「윤정숙 (딸)」 · 끝 화면 글이 따라온다",
   S9.gap_of(ex) == 0.5 and S9.labels_of(ex) == {"딸": "윤정숙 (딸)"}
   and "실제" in T.style_get(ex, "end_note") and "가명" in T.style_get(ex, "end_note"))
ck("대본이 따로 적은 값이 이긴다 (gap 0.3 · name_first false)",
   S9.gap_of(dict(ex, gap=0.3)) == 0.3 and S9.labels_of(dict(ex, name_first=False)) == {})
ck("style 이 없는 옛 대본은 그대로 (쉼 0.12 · 옛 이름표)",
   S9.gap_of({"format": "drama", "all_video": True}) == 0.12 and S9.labels_of(doc) == {}
   and T.style_get({}, "gap", 0.12) == 0.12)
ck("길이 잣대도 style 의 쉼(0.5초)으로 잰다",
   abs(T.part_sec(story["cuts"], {"all_video": True, "style": "explainer"})
       - T.part_sec(story["cuts"], {"all_video": True, "gap": 0.5})) < 1e-9)
b94 = (ROOT / "tools" / "build_short90.py").read_text(encoding="utf-8")
ck("제작본(build_short90)이 style 을 옮겨 적는다", 'for k in ("style", ' in b94)


def cut_of(d, n):
    return next(c for c in d["cuts"] if c["n"] == n)


def hit(d, needle):
    return any(needle in b for b in T.check(d))


s = copy.deepcopy(story)
cut_of(s, 18)["turns"] = [["나레이션", "다시 2011년. 산 주인이라도 남의 묘를 마음대로 파낼 수는 없습니다."]]
ck("⭐ 화면 속 사람 = 나레이션 — 옛 컷18(땅주인 얼굴 위 법 원칙)을 잡는다 (손님 1분 36초)",
   hit(s, "얼굴이 나오는데"))
ck("지금 컷18 「오병철 씨는 왜 소송까지 냈을까요?」 는 통과한다", not hit(story, "얼굴이 나오는데"))
s = copy.deepcopy(story)
cut_of(s, 2)["turns"] = [["나레이션", "그런데 2011년, 땅주인이 어머니 묘를 파내 달라며 윤정숙을 상대로 소송을 겁니다."]]
ck("나레이션은 이름 + 씨 — 「윤정숙을」 을 잡는다 (따옴표 속 인용은 그대로 둔다)",
   hit(s, "씨 없이") and not T.bare_names("'한옥자, 윤기철 모자와 법적으로 다투지 않는다.'",
                                         ["한옥자", "윤기철"]))
s = copy.deepcopy(story)
cut_of(s, 10)["turns"] = [["나레이션", "이듬해 그녀의 어머니가 세상을 떠났고, 아버지는 산에 아내를 묻었습니다."]]
ck("번역 투 대명사(그녀 · 그는)를 잡는다 — '그 사람이' · '그래서' 는 괜찮다",
   hit(s, "대명사") and not T.PRONOUN.search("오병철 씨는 그 사람이 윤정숙 씨가 아니라며, 그래서 그날")
   and T.PRONOUN.search("그는 끝까지 버텼습니다"))
amb = [("둘째, 윤정숙 씨가 1억 5천만 원을 받고 묘를 판 것이라는 겁니다.", "묘를 판"),
       ("아버지가 떠난 날부터 한옥자 씨가 윤정숙 씨에게 1억 5천을 보냈습니다.", "매일"),
       ("2001년, 윤기철 씨는 판결로 한옥자 씨를 친엄마로 만들었습니다.", "친엄마")]
got = []
for line, needle in amb:
    s = copy.deepcopy(story)
    cut_of(s, 22)["turns"] = [["나레이션", line]]
    got.append(hit(s, needle))
ck("손님이 실제로 헷갈린 말(묘를 판 · 그날부터 보냈다 · 친엄마로)을 잡는다", all(got), str(got))
s = copy.deepcopy(story)
cut_of(s, 12).pop("chapter")
ck("영상 컷에 대목 표시(chapter)가 없으면 잡는다", hit(s, "대목 표시"))
s = copy.deepcopy(story)
cut_of(s, 29)["fig"] = {"id": "paper", "add": [["result", ""]]}
ck("관계도 · 쟁점 · 판결 그림 가운데 하나라도 없으면 잡는다", hit(s, "판결 정리"))
s = copy.deepcopy(story)
s["cast"][0] = {k: v for k, v in s["cast"][0].items() if k != "intro"}
ck("인물마다 가명 · 이름표 관계 · 관계 한 줄이 있어야 한다", hit(s, "intro"))
ck("설명 드라마 규칙은 style 이 없는 대본에는 안 건다",
   not [b for b in T.check(dict(story, style="")) if "얼굴이 나오는데" in b or "대목" in b])
ck("그림 설계와 그림 컷이 맞물린다 (S94)", not G.validate(story), "; ".join(G.validate(story)))
s = copy.deepcopy(story)
cut_of(s, 19)["fig"]["add"][2] = ["rule", "묘를 지킬 권리가"]
cut_of(s, 20)["fig"]["add"].append(["rules", ""])
cut_of(s, 21)["fig"]["id"] = "familly"
s["figs"]["issue"]["cands"][0]["who"] = "아들"
v = G.validate(s)
ck("그림 검사 — 신호 낱말 · 없는 요소 · 없는 그림 · 인물표에 없는 얼굴을 잡는다",
   all(any(x in b for b in v) for x in ("신호 낱말", "요소가 없다", "figs 에 없다", "인물표(cast)에 없다")),
   "; ".join(v))
empty = [k for k, f in G.ICONS.items()
         if not (lambda im: (f(im, 540, 960), im)[1])(G.canvas()).getbbox()]
ck("작은 그림 일곱 가지가 실제로 그려진다 (묘·제사상·돈·집·서류·저울·반지)",
   len(G.ICONS) == 7 and not empty, str(empty))
rel = {"type": "relations", "nodes": [{"id": "a", "who": "딸", "at": [300, 600]},
                                      {"id": "b", "ghost": True, "name": "어머니", "at": [780, 600]}],
       "edges": [{"id": "e", "a": "a", "b": "b"}]}
names = lambda sp: [e.name for e in G.fig_relations(story, sp)]       # noqa: E731
ck("선 뜻풀이는 서류상 선이 있을 때만 저절로 (true · false · 직접 적기도 된다)",
   "legend" not in names(rel)
   and "legend" in names(dict(rel, edges=[dict(rel["edges"][0], style="paper")]))
   and "legend" not in names(dict(rel, legend=False, edges=[dict(rel["edges"][0], style="paper")]))
   and "legend" in names(dict(rel, legend=[["solid", "혼인"]])))
vd = {"type": "verdict", "rows": [{"id": "r", "icon": "home", "claim": "집을 나눠라?",
                                   "answer": "→ 받아들였다", "mark": "o"}],
      "lose": "원고 일부 승소", "stay": {"text": "집은 절반씩"}}
o = {e.name: e for e in G.fig_verdict(story, vd)}
x = {e.name: e for e in G.fig_verdict(story, dict(vd, rows=[dict(vd["rows"][0], mark="x")]))}
from PIL import ImageChops                                    # noqa: E402
ck("판결 줄 표시는 받아들임 O · 안 받아들임 X (기본 X)",
   ImageChops.difference(o["r"].build().sprite, x["r"].build().sprite).getbbox() is not None)
rows = D.timetable(live, [2.0] * len(live["cuts"]))
ck("검수 시간표 — 손님이 짚은 시각(1:36 · 1분 36초)을 컷으로 찾는다",
   D.secs_of("1:36") == 96 and D.secs_of("1분 36초") == 96 and D.secs_of("96") == 96
   and D.cut_at(rows, 5.0)[0] == 3 and rows[-1][2] == 2.0 * len(live["cuts"]))
ck("대본 검사가 대본(.story)과 제작본(.json)이 어긋난 것을 잡는다",
   not D.stale(story, live) and D.stale(dict(story, cuts=story["cuts"][:-1]), live))
import explainer_story as E                                   # noqa: E402
sh = E.shape(json.loads(json.dumps(story)))
ck("대본 손질(explainer_story shape)은 본보기 S94 를 그대로 둔다 (여러 번 돌려도 같다)",
   sh == story and E.shape(json.loads(json.dumps(sh))) == sh)
ck("받아쓰기 비교 — 숫자 덩어리(연도 · 1억 5천만)만 보고 한 자리 숫자는 뺀다",
   L.numbers_of("1969년 · 모두 1억 5천만 원 · 1심 · 4천만 원") == ["1969", "1억5천만", "4천만"])
heard = "1969년 ... 2011년 ... 1억5천만 원 ... 윤정숙 씨"
mini = {"cuts": [{"turns": [["나레이션", "1969년 윤정숙 씨 · 2011년 · 모두 1억 5천만 원 · 2008년"]]}],
        "cast": [{"alias": "윤정숙"}, {"alias": "오병철"}]}
ck("받아쓰기 비교 — 안 들린 숫자만 집는다 (대본에 없는 이름은 안 본다)",
   L.compare(mini, heard) == (["2008"], []))

print("\n⑪ 올릴 영상 화질 — 360p / 720p 를 고른다 (손님: \"720p 또는 360p를 선택할 수 있도록\")")
ck("화질은 --res 가 이기고, 없으면 대본 res, 그것도 없으면 360p",
   D.res_of({}) == "360p" and D.res_of({"res": "720p"}) == "720p"
   and D.res_of({"res": "720p"}, "360p") == "360p" and D.RES == "360p")
try:
    D.res_of({"res": "1080p"})
    ck("고를 수 있는 화질은 360p · 720p 둘뿐이다", False)
except SystemExit:
    ck("고를 수 있는 화질은 360p · 720p 둘뿐이다", T.RES_CHOICES == ("360p", "720p"))
ck("대본 검사가 엉뚱한 화질(res)을 잡는다",
   any("화질" in b for b in T.check_drama(dict(story, res="1080p")))
   and not any("화질" in b for b in T.check_drama(dict(story, res="720p"))))
ck("제작본(build_short90)이 화질(res)을 옮겨 적는다",
   '("style", "res", "gap", "name_first", "end_note", "figs")' in b94)
with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    keep_vd = S9.video_dir
    S9.video_dir = lambda: t                                   # noqa: E731
    try:
        nc = next(c for c in live["cuts"] if not c.get("fig") and not c["narr"])
        (t / "raw").mkdir()
        (t / "raw" / "v.mp4").write_bytes(b"x")
        e360 = {"raw": "raw/v.mp4", "shot": {"key": "x"}, "sec": 6}
        D.RES = "720p"
        lo = D.stock(nc, {D.vkey(nc): e360}) is None
        hi = D.stock(nc, {D.vkey(nc): dict(e360, res="720p")}) is not None
        D.RES = "360p"
        down = D.stock(nc, {D.vkey(nc): dict(e360, res="720p")}) is not None
    finally:
        D.RES = "360p"
        S9.video_dir = keep_vd
    ck("720p 로 만들 때 360p 로 산 창고 영상은 안 쓴다 (흐린 컷이 안 섞인다) · 720p 영상은 360p 에도 쓴다",
       lo and hi and down, f"{lo} {hi} {down}")
t360, k360b = D.price(live, "360p", lib={})
t720, k720b = D.price(live, "720p", lib={})
ck("계획은 두 화질 값을 함께 센다 — 720p 는 360p 의 약 2.8배",
   t360 == t720 > 0 and 2.5 < k720b / k360b < 3.2 and D.RES == "360p", f"{k360b:.0f}/{k720b:.0f}")
old_env = os.environ.pop("VT_RUN_KRW", None)
try:
    cap_default = D.run_cap()
    os.environ["VT_RUN_KRW"] = "5000"
    cap_env = D.run_cap()
finally:
    os.environ.pop("VT_RUN_KRW", None)
    if old_env is not None:
        os.environ["VT_RUN_KRW"] = old_env
ck("옴니 한 번 한도는 드라마 한 편 한도(16,000원) — 720p 한 편도 한 번에 끝난다 (VT_RUN_KRW 를 주면 그 값)",
   cap_default == S9.cost.DRAMA_RUN_KRW == 16000 and cap_env == S9.cost.RUN_KRW
   and k720b < cap_default, f"{cap_default} {cap_env} {k720b:.0f}")
with tempfile.TemporaryDirectory() as t:
    t = Path(t)
    framed = t / "framed720.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc2=s=576x1024:r=24:d=3", "-vf",
                    "pad=720:1280:72:128:color=0xA6C4BE", "-pix_fmt", "yuv420p",
                    str(framed)], check=True)
    cr = D.crop_of(framed)
    m = re.match(r"crop=(\d+):(\d+):(\d+):(\d+),scale=720:1280,", cr)
    inside = bool(m) and int(m.group(3)) >= 66 and int(m.group(4)) >= 122 \
        and int(m.group(1)) + int(m.group(3)) <= 72 + 576 + 6 \
        and int(m.group(2)) + int(m.group(4)) <= 128 + 1024 + 6
    ck("720p 영상의 액자 테두리도 제자리를 잘라 720×1280 으로 둔다 (360 기준 자리 × 2)",
       inside and D.size_of(framed) == (720, 1280), cr)

print("\n⑫ 올릴 준비 (손님: \"유튜브에 올릴 수 있게 준비까지 마무리해줘\")")
import ytmeta as Y                                            # noqa: E402
import stage_video as SV                                      # noqa: E402
sh2 = T.shape_drama({"cuts": [], "yt_tags": ["#상속분쟁", "상속"], "yt_title": "제목", "card": ["가", "나"]})
ck("대본의 yt_tags 가 편 해시태그로 들어간다 (꼴 맞추기가 안 지운다)",
   sh2["parts"][0].get("tags") == ["상속분쟁", "상속"]
   and T.shape_drama(json.loads(json.dumps(sh2)))["parts"][0].get("tags") == ["상속분쟁", "상속"])
m94 = json.loads((ROOT / "data" / "series" / "S94.meta.json").read_text(encoding="utf-8"))["parts"][0]
ck("S94 올릴 글 — 묘 사건에 #불륜 · #이혼사연 이 안 붙고 #상속분쟁 이 붙는다",
   "#상속분쟁" in m94["title"] and "불륜" not in m94["tags"] and "이혼사연" not in m94["tags"]
   and m94["tags"][:3] == ["사연", "상속분쟁", "상속"], m94["title"])
ck("설명 드라마 설명의 맺음말 = 끝 화면 글 (판결문 지명을 쓰므로 '지명은 바꾸었고' 를 안 쓴다)",
   "등장인물 이름은 모두 가명입니다." in m94["description"]
   and "지명은 바꾸었고" not in m94["description"])
old_meta = Y.part_meta(doc, doc["parts"][0], last=True)
ck("옛 대본(설명 드라마 아님)의 맺음말은 그대로", "지명은 바꾸었고" in old_meta["description"])
_f, _b = SV.ready("S999")
ck("보관함에 넣기 전에 막힐 것을 먼저 본다 (없는 사건은 밀어 넣지 않는다)", not _f and _b)
wf = (ROOT / ".github" / "workflows" / "stage-video.yml").read_text(encoding="utf-8")
ck("임시 가지는 보관함에 옮긴 뒤 지운다 (영상이 main 에 안 남는다)",
   "stage/S*" in wf and "--delete" in wf and "stage_video.py --release" in wf
   and "GEMINI_API_KEY" not in wf)
import upload_request as UR                                   # noqa: E402
rq = UR.request_of("S94", 1, "공개", "지금", "진짜")
ck("작업 칸의 올리기 요청은 4-2 가 받는 값 그대로다 (다르면 422 로 통째로 거절)",
   rq["privacy"] in UR.options("privacy") and rq["when"] in UR.options("when")
   and rq["mode"] in UR.options("mode") and rq["when"] == "지금 바로 공개"
   and UR.request_of("S94", 1, "비공개", "예약", "연습")["when"] in UR.options("when"), str(rq))
uw = (ROOT / ".github" / "workflows" / "upload-request.yml").read_text(encoding="utf-8")
ck("올리기 요청은 임시 가지로만 · 4-2 를 누르고 가지를 지운다 (올리는 일은 4-2 가 한다)",
   "upload/S*" in uw and "actions: write" in uw and "--delete" in uw
   and "upload_request.py --dispatch" in uw and "YOUTUBE_" not in uw)
if (S9.OUT / "S94_part1.mp4").exists():
    _f94, _b94 = SV.ready("S94")
    ck("S94 는 올릴 준비가 됐다 (영상 · 썸네일 · 길이 · 만든 기록 · 올릴 글)",
       not _b94 and set(_f94) == {"part1.mp4", "part1.jpg", "meta.json"}, "; ".join(_b94))
else:
    print("   ⏭  완성 영상이 없다 (깃허브) — 'S94 올릴 준비' 는 작업 칸에서만 본다")

print("─" * 56)
if bad:
    print(f"❌ {len(bad)}개 걸렸습니다 — 고치고 다시")
    sys.exit(1)
print("✅ 전부 영상 드라마: 카메라 · 지문 · 화질(360p·720p) · 목소리 · 후처리 · 길이 · 이름표 · 그림 컷 · 기본 짜임")
