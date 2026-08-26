#!/usr/bin/env python3
"""조립한 쇼츠가 **끊기지 않고 깜빡이지 않는가** (0원 · 인터넷 0회 · 20초).

왜 이 검사가 있는가 (2026-08-23 운영자 신고 두 건)
    ① "올린 영상 뒷부분이 남아있는데 잘렸어. 자막은 마지막 대사까지 나오는데
        영상 및 나레이션은 뒷부분이 남아있는 상태에서 끊겼어."
       → 원인 둘. (a) trim_dead 가 '대사 수보다 말 토막이 많다'는 이유로
         **진짜 나레이션을 잘라냈다**(Veo 가 지어낸 말을 자르려고 만든 장치인데
         루미나는 전부 진짜 대사다). (b) -shortest 가 **가장 짧은 입력**에서
         끊는데, 소리가 영상보다 긴 클립에서 소리가 날아갔다.
    ② "검은색 띠가 짧게 없어졌다 나타나기를 반복해. 깜빡거리는 느낌이야."
       → 띠를 **자막 조각 그림 안에** 그리고 있었다. 조각과 조각 사이에는
         자막 겹침을 막으려고 반 프레임 틈을 두는데, 그 순간 띠까지 사라졌다.
         옛 코드로 재현하니 정확히 1프레임에서 띠가 없어졌다.

무엇을 보나 — 진짜 ffmpeg 로 만들어 **모든 프레임을 픽셀로 잰다**
    ① 소리가 영상보다 길어도 나레이션이 안 잘린다
    ② 전 프레임에서 위·아래 검은 띠가 살아 있다 (깜빡임 0)
    ③ 자막은 여전히 조각별로 바뀐다 (늘 켜 두면 안 된다)
"""
import os
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("KEEP_AUDIO", "1")          # 루미나 길 (원본 소리 유지)
import shorts as S                                           # noqa: E402
from PIL import Image                                        # noqa: E402

fails = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + ("" if ok else f"  ({why})"))
    if not ok:
        fails.append(name)


def make(d, vsec, asec, color="white"):
    """영상 vsec 초 · 소리 asec 초짜리 가짜 클립 (루미나와 같은 496x864)."""
    p = d / f"src_{vsec}_{asec}.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", f"color=c={color}:s=496x864:d={vsec}:r=24",
         "-f", "lavfi", "-i", f"sine=frequency=300:duration={asec}",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(p)],
        check=True, capture_output=True)
    return p


TMP = pathlib.Path(tempfile.mkdtemp(prefix="compose-"))
print("=" * 62)
print("조립한 쇼츠가 끊기지 않고 깜빡이지 않는가 (값 0원)")
print("=" * 62)

print("① 소리가 영상보다 길어도 나레이션이 안 잘린다")
src = make(TMP, 4.0, 4.6)
out = S.compose(src, "후킹 문구", "첫 대사입니다. / 둘째 대사입니다.",
                TMP / "a.mp4", TMP, label="제목 · 1화")
got_a, got_v = S.audio_sec(out), S.C.probe(out)[2]
ck(f"나레이션이 끝까지 남는다 (원본 소리 4.6초 → {got_a:.2f}초)", got_a >= 4.55,
   f"{got_a:.3f}초 — 잘렸다")
ck("영상도 소리 길이만큼 이어진다 (마지막 화면을 붙잡는다)", got_v >= 4.5,
   f"{got_v:.3f}초")

print("② 영상이 소리보다 길어도 영상이 안 잘린다")
src2 = make(TMP, 5.0, 4.2)
out2 = S.compose(src2, "", "한 줄 대사.", TMP / "b.mp4", TMP)
ck(f"영상이 끝까지 남는다 (원본 5.0초 → {S.C.probe(out2)[2]:.2f}초)",
   S.C.probe(out2)[2] >= 4.95, f"{S.C.probe(out2)[2]:.3f}초")

print("③ 전 프레임에서 위 칸(후킹)이 살아 있다 (깜빡임 0)")
# ⚠️ 예전엔 자막 조각 그림 안에 틀까지 같이 그려서, 조각과 조각 사이 반 프레임
#    틈에 틀이 통째로 사라졌다. 운영자: "깜빡거리는 느낌이야."
src3 = make(TMP, 5.0, 5.0)
out3 = S.compose(src3, "후킹", "하나 둘 셋 넷. / 다섯 여섯 일곱. / 여덟 아홉 열.",
                 TMP / "c.mp4", TMP, label="제목 · 1화")
fr = TMP / "fr"; fr.mkdir(exist_ok=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out3),
                "-vf", "fps=24", str(fr / "f%04d.png")], check=True,
               capture_output=True)
files = sorted(fr.glob("*.png"))
gone_hook, subs = [], set()
for p in files:
    im = Image.open(p).convert("L")
    hk = im.crop((0, S.HOOK_TOP, S.W, S.HOOK_BOT))
    sb = im.crop((0, S.SUB_TOP, S.W, S.SUB_BOT))
    if sum(hk.histogram()[150:]) < 3000:
        gone_hook.append(p.name)
    subs.add(sum(sb.histogram()[150:]) // 400)          # 자막 모양이 바뀌는지
ck(f"후킹이 {len(files)}프레임 내내 살아 있다", not gone_hook,
   f"{len(gone_hook)}프레임에서 사라짐 {gone_hook[:4]}")
ck("자막은 그대로 조각마다 바뀐다 (후킹과 달리 늘 켜 두면 안 된다)",
   len(subs) >= 3, f"모양이 {len(subs)}가지뿐")

print("④ 끝 안내 — 위 칸에서 마지막 컷 내내 (영상은 하나도 안 가린다)")
import json                                                  # noqa: E402
DOC = json.loads((ROOT / "data" / "series" / "S001.json").read_text(encoding="utf-8"))
big, small = S.end_card(DOC, 1)
ck("다음 화 **제목**을 보여 준다 (그냥 '다음 화에 계속' 보다 세다)",
   big != "다음 화에 계속" and len(big) > 6, big)
ck("구독 안내는 한 줄만 (화면을 둘로 나누지 않는다)", "구독" in small, small)
lbig, lsmall = S.end_card(DOC, len(DOC["episodes"]))
ck("마지막 화는 완결 안내로 바뀐다", "완" in lbig, lbig)

src4 = make(TMP, 5.0, 5.0, color="0x3a4050")
plain = S.compose(src4, "후킹 문구", "마지막 대사.", TMP / "d.mp4", TMP)
withend = S.compose(src4, "후킹 문구", "마지막 대사.", TMP / "e.mp4", TMP,
                    end=(big, small))
ck("끝 안내를 넣어도 길이가 안 늘어난다 (쇼츠 시청률 보호)",
   abs(S.C.probe(withend)[2] - S.C.probe(plain)[2]) < 0.05,
   f"{S.C.probe(plain)[2]:.2f} → {S.C.probe(withend)[2]:.2f}초")


def ink(mp4, t, box):
    q = TMP / f"p{t}_{box[1]}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(mp4),
                    "-frames:v", "1", str(q)], check=True, capture_output=True)
    return sum(Image.open(q).convert("L").crop(box).histogram()[150:])


TOPBOX = (0, S.HOOK_TOP, S.W, S.HOOK_BOT)
VIDBOX = (0, S.VID_TOP + 10, S.W, S.VID_TOP + S.VID_H - 10)
ck("끝 안내가 **처음부터** 위 칸에 떠 있다 (2.6초가 아니라 컷 내내)",
   ink(withend, 0.6, TOPBOX) > 3000 and ink(withend, 4.4, TOPBOX) > 3000,
   f"0.6초 {ink(withend, 0.6, TOPBOX)} · 4.4초 {ink(withend, 4.4, TOPBOX)}")
ck("끝 안내가 영상 자리를 하나도 안 가린다", ink(withend, 4.4, VIDBOX) < 500,
   f"{ink(withend, 4.4, VIDBOX)}픽셀 — 얼굴을 덮고 있다")
ck("끝 안내가 있으면 그 자리에 후킹은 안 뜬다 (둘이 안 겹친다)",
   abs(ink(withend, 2.0, TOPBOX) - ink(plain, 2.0, TOPBOX)) > 1000,
   "위 칸 그림이 후킹과 같다 — 끝 안내로 안 바뀌었다")

print("⑤ 후킹은 내내 떠 있고, 영상은 하나도 안 가린다 (2026-08-24)")
# 운영자: "위에 후킹문구를 계속 띄워놓은건 어때?"
#   → 띠 배치에서는 후킹이 **빈 검은 칸**에 앉는다. 가릴 얼굴이 없으니 내내 띄운다.
src5 = make(TMP, 6.0, 6.0, color="0x101015")
hooked = S.compose(src5, "이것이 후킹 문구다", "한 줄 대사.", TMP / "f.mp4", TMP,
                   label="제목 · 1화")
for _t in (0.5, 3.0, 5.5):
    ck(f"{_t}초에도 후킹이 떠 있다", ink(hooked, _t, TOPBOX) > 3000,
       f"{ink(hooked, _t, TOPBOX)}픽셀")
ck("후킹이 영상 자리를 하나도 안 가린다", ink(hooked, 3.0, VIDBOX) < 500,
   f"{ink(hooked, 3.0, VIDBOX)}픽셀 — 얼굴을 덮고 있다")
plain5 = S.compose(src5, "", "한 줄 대사.", TMP / "g.mp4", TMP, label="제목 · 1화")
ck("후킹을 안 넘기면 위 칸이 빈다", ink(plain5, 3.0, TOPBOX) < 500,
   f"{ink(plain5, 3.0, TOPBOX)}픽셀")
ck("후킹이 없어도 길이는 그대로", abs(S.C.probe(plain5)[2] - 6.0) < 0.1,
   f"{S.C.probe(plain5)[2]:.2f}초")
_ep = (ROOT / "src" / "shorts.py").read_text(encoding="utf-8")
ck("모든 컷에 후킹을 넘기도록 코드가 박혀 있다",
   "hook if (not HOOK_SEC or first_cut) else \"\"" in _ep)

print("⑥ 자막에 '누가 말하는지' 이름표가 붙는가 (2026-08-24)")
# 1화 이탈률 60%를 파고들다 찾은 것: 사람이 셋 나오는데 화자 표시가 없어
# "얘가 누구지?" 하는 순간 이야기에서 튕겨 나갔다.
# ⭐ 2026-08-24 — 이름표는 자막 **왼쪽 기둥**에 세로로 선다 (둥근 알약 폐기)
PILLBOX = (S.SIDE - 8, S.SUB_TOP - 6, S.W // 2, S.SUB_TOP + S.NAME_SIZE + 20)


def pill_colors(mp4, t):
    """그 시각 자막 **왼쪽 위**(세로 막대 + 이름 자리)에 색이 있는가."""
    q = TMP / f"n{t}_{mp4.stem}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(mp4),
                    "-frames:v", "1", str(q)], check=True, capture_output=True)
    im = Image.open(q).convert("RGB").crop(PILLBOX)
    return len([c for n, c in im.getcolors(im.size[0] * im.size[1]) if sum(c) > 200])


src6 = make(TMP, 5.0, 5.0, color="0x101015")
named = S.compose(src6, "", "당장 나가. / 그만해.", TMP / "n1.mp4", TMP,
                  whos=["Wife", "Husband"])
ck("이름표가 자막 왼쪽 위에 붙는다", pill_colors(named, 0.6) > 0,
   "아무것도 안 그려졌다")
ck("이름표가 바탕체(명조)다 — 굵은 고딕은 앱 화면처럼 보인다",
   "FONT_SERIF" in (ROOT / "src" / "shorts.py").read_text(encoding="utf-8")
   and S.FONT_SERIF.exists(), str(S.FONT_SERIF.name))
ck("색이 원색이 아니라 눌린 색이다 (유치해 보이지 않게)",
   all(max(c) - min(c) < 110 for _, c in S.WHO_KO.values()),
   str([c for _, c in S.WHO_KO.values()]))
plain6 = S.compose(src6, "", "당장 나가. / 그만해.", TMP / "n2.mp4", TMP)
ck("화자를 모르면 아무것도 안 붙인다 (틀린 이름보다 없는 편이 낫다)",
   pill_colors(plain6, 0.6) == 0, "이름표가 그려졌다")
odd = S.compose(src6, "", "당장 나가.", TMP / "n3.mp4", TMP, whos=["Nobody"])
ck("모르는 이름은 그냥 넘어간다", pill_colors(odd, 0.6) == 0, "이름표가 그려졌다")
# ⚠️ 2026-08-26 — 딸·변호사가 빠져 있었다. 이름표가 없는 사람은 자막 위에
#    **아무것도 안 그려진다** — 어르신은 "얘가 누구지" 하다가 튕겨 나간다.
_WHOS = ("Wife", "the wife", "Husband", "Other woman", "Daughter", "Lawyer")
ck("다섯 사람 이름표가 다 준비돼 있다", all(S.who_ko(k) for k in _WHOS),
   str([k for k in _WHOS if not S.who_ko(k)]))
ck("사람마다 색이 다르다",
   len({S.who_ko(k)[1] for k in
        ("Wife", "Husband", "Other woman", "Daughter", "Lawyer")}) == 5)
_src3 = (ROOT / "src" / "shorts.py").read_text(encoding="utf-8")
ck("대본에서 화자를 뽑아 넘긴다",
   "whos=[w for w, _ in dia_turns(c.get(\"prompt\"))]" in _src3)

print("⑧ 때(시점) 도장 — 첫 컷 내내, 자막·영상은 하나도 안 뺏는다 (2026-08-26)")
# 운영자: "씬 앞뒤로 개연성이 없다." 8년짜리 사건인데 화면에 때가 한 번도
#   안 나왔다. 이름표 오른쪽 빈 자리에 앉힌다.
# ⚠️ 2026-08-26 — 처음엔 앞 3초만 띄웠다. 앞머리 1.2초가 무음이라 실제로
#    읽을 시간은 1.8초뿐이었고, 운영자가 다시 "시간이 쌩뚱맞다" 고 했다.
#    **첫 컷 내내** 띄우도록 바꿨다 (빈자리라 아무것도 안 가린다).
src8 = make(TMP, 8.0, 8.0, color="0x101015")
stamped = S.compose(src8, "후킹 문구다", "당장 나가.", TMP / "st.mp4", TMP,
                    whos=["Wife"], stamp="2013년 8월")
plain8 = S.compose(src8, "후킹 문구다", "당장 나가.", TMP / "st0.mp4", TMP,
                   whos=["Wife"])
STAMPBOX = (S.W // 2, S.SUB_TOP, S.W, S.SUB_TOP + 60)
ck("앞머리에 때가 떠 있다",
   ink(stamped, 1.0, STAMPBOX) - ink(plain8, 1.0, STAMPBOX) > 300,
   f"{ink(stamped, 1.0, STAMPBOX)} vs {ink(plain8, 1.0, STAMPBOX)}")
ck("컷이 끝날 때까지 안 사라진다",
   ink(stamped, 6.0, STAMPBOX) - ink(plain8, 6.0, STAMPBOX) > 300,
   f"{ink(stamped, 6.0, STAMPBOX)} vs {ink(plain8, 6.0, STAMPBOX)}")
ck("영상 자리를 하나도 안 가린다", ink(stamped, 1.0, VIDBOX) < 500,
   f"{ink(stamped, 1.0, VIDBOX)}픽셀")
ck("길이가 안 늘어난다",
   abs(S.C.probe(stamped)[2] - S.C.probe(plain8)[2]) < 0.05,
   f"{S.C.probe(plain8)[2]:.2f} → {S.C.probe(stamped)[2]:.2f}초")
_src8 = (ROOT / "src" / "shorts.py").read_text(encoding="utf-8")
ck("첫 컷에만 넘긴다 (대본의 stamp — '3년 뒤 · 2017년 1월')",
   'ep.get("stamp") or ep.get("when")' in _src8 and "first_cut" in _src8)

# ⭐⭐ 2026-08-26 — 지난 줄거리를 화면에 띄운다.
#    화마다 한 줄씩 적어 두고도 **그리는 코드가 아예 없었다.** 쇼츠는 앞 화를
#    안 보고 들어오는 사람이 대부분인데 맥락이 0이었다.
print("⑧-2 지난 줄거리 — 앞머리에만, 길이는 그대로 (2026-08-26)")
recapped = S.compose(src8, "후킹 문구다", "당장 나가.", TMP / "rc.mp4", TMP,
                     whos=["Wife"], recap="모르는 번호가 남편 서류를 물었다")
RECAPBOX = (0, S.VID_TOP, S.W, S.VID_TOP + S.RECAP_H)
ck("앞머리에는 지난 줄거리 한 줄이 뜬다",
   ink(recapped, 1.0, RECAPBOX) - ink(plain8, 1.0, RECAPBOX) > 500,
   f"{ink(recapped, 1.0, RECAPBOX)} vs {ink(plain8, 1.0, RECAPBOX)}")
ck("대사가 시작될 즈음엔 사라진다",
   abs(ink(recapped, 5.0, RECAPBOX) - ink(plain8, 5.0, RECAPBOX)) < 300,
   f"{ink(recapped, 5.0, RECAPBOX)} vs {ink(plain8, 5.0, RECAPBOX)}")
ck("길이가 안 늘어난다",
   abs(S.C.probe(recapped)[2] - S.C.probe(plain8)[2]) < 0.05,
   f"{S.C.probe(plain8)[2]:.2f} → {S.C.probe(recapped)[2]:.2f}초")
_src9 = (ROOT / "src" / "shorts.py").read_text(encoding="utf-8")
ck("첫 컷에만 넘긴다 (대본의 recap)",
   'recap=(ep.get("recap") or "") if first_cut else ""' in _src9)

print("⑨ 다음 화 예고 — 영상 칸만 어두워지고, 후킹은 위에서 그대로 (2026-08-25)")
# 운영자: "만든 영상이 끝나면 다음화 예고 문구를 화면 중간에 띄워주고, 그 화면이
#   반투명 검정색으로 바뀌고… 드라마 보면 다음 화 안내하잖아."
#   ⚠️ 화면 **전체**를 덮으면 위 칸 후킹까지 어두워진다 (운영자는 후킹을 끝까지
#      유지하라고도 하셨다). 위아래 띠는 원래 검은색이니 **영상 칸만** 덮는다.
src9 = make(TMP, 8.0, 5.5, color="0x6a5f52")
PREV = ("다음 화 예고", "바람피운 놈이 걸었다가 기각당했다", "구독하고 내일 이어 보기")
prev = S.compose(src9, "후킹 문구다", "그럼 애들은 어떻게 되는 건데?",
                 TMP / "pv.mp4", TMP, whos=["Wife"], preview=PREV)
noprev = S.compose(src9, "후킹 문구다", "그럼 애들은 어떻게 되는 건데?",
                   TMP / "pv0.mp4", TMP, whos=["Wife"])
ck("길이가 1초도 안 늘어난다 (쇼츠 평균 시청률 보호)",
   abs(S.C.probe(prev)[2] - S.C.probe(noprev)[2]) < 0.05,
   f"{S.C.probe(noprev)[2]:.2f} → {S.C.probe(prev)[2]:.2f}초")
ck("영상 중간에는 예고가 안 뜬다 (대사를 안 가린다)",
   abs(ink(prev, 2.0, VIDBOX) - ink(noprev, 2.0, VIDBOX)) < 200,
   f"{ink(prev, 2.0, VIDBOX)} vs {ink(noprev, 2.0, VIDBOX)}")
ck("마지막에는 화면 가운데에 예고가 뜬다",
   ink(prev, 7.6, VIDBOX) - ink(noprev, 7.6, VIDBOX) > 2000,
   f"{ink(prev, 7.6, VIDBOX)} vs {ink(noprev, 7.6, VIDBOX)}")
ck("후킹은 예고가 떠도 위에서 그대로 밝다 (어두워지지 않는다)",
   abs(ink(prev, 7.6, TOPBOX) - ink(noprev, 7.6, TOPBOX)) < 200,
   f"{ink(prev, 7.6, TOPBOX)} vs {ink(noprev, 7.6, TOPBOX)}")
_src9 = (ROOT / "src" / "shorts.py").read_text(encoding="utf-8")
ck("마지막 컷에만 넘긴다", "preview=preview_card(doc, no) if last_cut else None" in _src9)
ck("예고 큰 줄이 **다음 화 후킹**이다 (제목은 목차처럼 밋밋하다)",
   "hook_plain(nxt.get(\"hook\"))" in _src9)

print("⑦ 원본 소리를 쓸 때는 클립을 자르지 않는다")
_src = (ROOT / "src" / "shorts.py").read_text(encoding="utf-8")
ck("keep_audio 면 trim_dead 를 건너뛴다", "if not keep_audio():" in _src)
ck("-shortest 로 끊지 않는다 (길이를 우리가 정한다)",
   '"-shortest"' not in _src and '"-t", f"{sec:.3f}"' in _src)

print("-" * 62)
if fails:
    print(f"❌ {len(fails)}가지 실패")
    sys.exit(1)
print("✅ 끊김 없고 깜빡임 없다.")
