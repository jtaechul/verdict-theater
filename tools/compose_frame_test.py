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

print("③ 전 프레임에서 검은 띠가 살아 있다 (깜빡임 0)")
src3 = make(TMP, 5.0, 5.0)
out3 = S.compose(src3, "후킹", "하나 둘 셋 넷. / 다섯 여섯 일곱. / 여덟 아홉 열.",
                 TMP / "c.mp4", TMP, label="제목 · 1화")
fr = TMP / "fr"; fr.mkdir(exist_ok=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out3),
                "-vf", "fps=24", str(fr / "f%04d.png")], check=True,
               capture_output=True)
files = sorted(fr.glob("*.png"))
gone_top, gone_bot, subs = [], [], set()
for p in files:
    im = Image.open(p).convert("L")
    top = im.crop((0, 0, S.W, S.BAR_TOP - 10))
    bot = im.crop((0, S.H - S.BAR_BOT + 10, S.W, S.H))
    if sum(top.histogram()[60:]) > top.size[0] * top.size[1] * 0.25:
        gone_top.append(p.name)
    if sum(bot.histogram()[60:]) > bot.size[0] * bot.size[1] * 0.35:
        gone_bot.append(p.name)
    subs.add(sum(bot.histogram()[60:]) // 400)          # 자막 모양이 바뀌는지
ck(f"위 띠가 {len(files)}프레임 내내 살아 있다", not gone_top,
   f"{len(gone_top)}프레임에서 사라짐 {gone_top[:4]}")
ck("아래 띠도 내내 살아 있다", not gone_bot,
   f"{len(gone_bot)}프레임에서 사라짐 {gone_bot[:4]}")
ck("자막은 그대로 조각마다 바뀐다 (띠와 달리 늘 켜 두면 안 된다)",
   len(subs) >= 3, f"모양이 {len(subs)}가지뿐")

print("④ 끝 안내 — 길이를 안 늘리고 마지막에만 겹친다")
import json                                                  # noqa: E402
DOC = json.loads((ROOT / "data" / "series" / "S001.json").read_text(encoding="utf-8"))
big, small = S.end_card(DOC, 1)
ck("다음 화 **제목**을 보여 준다 (그냥 '다음 화에 계속' 보다 세다)",
   big != "다음 화에 계속" and len(big) > 6, big)
ck("구독 안내는 한 줄만 (화면을 둘로 나누지 않는다)", "구독" in small, small)
lbig, lsmall = S.end_card(DOC, len(DOC["episodes"]))
ck("마지막 화는 완결 안내로 바뀐다", "완" in lbig, lbig)

src4 = make(TMP, 5.0, 5.0, color="0x3a4050")
plain = S.compose(src4, "", "마지막 대사.", TMP / "d.mp4", TMP)
withend = S.compose(src4, "", "마지막 대사.", TMP / "e.mp4", TMP,
                    end=(big, small))
ck("끝 안내를 넣어도 길이가 안 늘어난다 (쇼츠 시청률 보호)",
   abs(S.C.probe(withend)[2] - S.C.probe(plain)[2]) < 0.05,
   f"{S.C.probe(plain)[2]:.2f} → {S.C.probe(withend)[2]:.2f}초")


def ink_mid(mp4, t):
    """그 시각 화면의 **가운데 아래**(끝 안내 자리)에 글자가 있는가."""
    q = TMP / f"p{t}.png"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", str(mp4),
                    "-frames:v", "1", str(q)], check=True, capture_output=True)
    im = Image.open(q).convert("L").crop(
        (0, S.END_TOP, S.W, S.H - S.BAR_BOT))
    return sum(im.histogram()[150:])


ck("앞부분에는 끝 안내가 안 뜬다", ink_mid(withend, 1.0) < 2000,
   f"{ink_mid(withend, 1.0)}픽셀")
ck("마지막 2.6초에만 뜬다", ink_mid(withend, 4.4) > 8000,
   f"{ink_mid(withend, 4.4)}픽셀")

print("⑤ 원본 소리를 쓸 때는 클립을 자르지 않는다")
_src = (ROOT / "src" / "shorts.py").read_text(encoding="utf-8")
ck("keep_audio 면 trim_dead 를 건너뛴다", "if not keep_audio():" in _src)
ck("-shortest 로 끊지 않는다 (길이를 우리가 정한다)",
   '"-shortest"' not in _src and '"-t", f"{sec:.3f}"' in _src)

print("-" * 62)
if fails:
    print(f"❌ {len(fails)}가지 실패")
    sys.exit(1)
print("✅ 끊김 없고 깜빡임 없다.")
