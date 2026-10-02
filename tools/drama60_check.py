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
  ⑥ 1분 규격      all_video 대본은 13~18컷 · 대사 4~7 · 60초 벽 · 조립 여운 0.12초
"""
import io
import json
import os
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


doc = json.loads((ROOT / "data" / "series" / "S94.json").read_text(encoding="utf-8"))
cuts = doc["cuts"]

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

print("\n⑥ 1분 규격")
ck("S94 는 1분 전부 영상 대본이다", doc.get("all_video") is True)
story = json.loads((ROOT / "data" / "series" / "S94.story.json").read_text(encoding="utf-8"))
ck("1분 대본이 규격 검사를 통과한다", not T.check(story), "; ".join(T.check(story)))
R = T.rules_of(story)
ck("1분 규격: 13~18컷", (R["PART_MIN_CUTS"], R["PART_MAX_CUTS"]) == (13, 18))
ck("1분 길이 잣대는 1.28배 · 틈 없는 조립으로 잰다",
   abs(T.part_sec(story["cuts"], story) -
       (T.SEC60_PER_CHAR * sum(T.chars(c) for c in story["cuts"])
        + T.SEC60_PER_CUT * len(story["cuts"]))) < 1e-6)
ck("2분 드라마 잣대는 그대로 (손대지 않았다)",
   T.rules_of({"format": "drama"})["PART_MAX_CUTS"] == 24
   and abs(T.part_sec(story["cuts"]) - (T.SEC_PER_CHAR * sum(T.chars(c) for c in story["cuts"])
                                         + T.SEC_PER_CUT * len(story["cuts"]))) < 1e-6)
ck("벽은 60초", talkplan.part_max_sec(doc) == 59.5
   and talkplan.part_max_sec({"format": "drama"}) == talkplan.DRAMA_MAX_SEC)
s9 = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
ck("조립 여운은 0.12초 (쉬는 틈 없이)", S9.PAD_TIGHT == 0.12 and "PAD = PAD_TIGHT" in s9)
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

print("─" * 56)
if bad:
    print(f"❌ {len(bad)}개 걸렸습니다 — 고치고 다시")
    sys.exit(1)
print("✅ 1분 전부 영상: 카메라 · 지문 · 360p · 목소리 · 후처리 · 1분 규격")
