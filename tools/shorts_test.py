#!/usr/bin/env python3
"""⭐ 쇼츠 배치(위 후킹 · 가운데 영상 · 아래 자막)가 맞게 그려지는지 본다. 0원.

    python3 tools/shorts_test.py

왜 (2026-08-20 운영자 지시)
    "상단 검은 빈 프레임에는 후킹 문구가 들어가고, 아래쪽 검은 빈 프레임에는
     자막이 들어가도록 하자."

    글자가 **정해진 칸 안에** 들어갔는지, 영상 자리를 침범하지 않는지,
    유튜브 단추가 덮는 아래쪽을 비워 뒀는지를 그림의 픽셀로 직접 확인한다.
    (자리를 눈대중으로 적었다가 여러 번 고친 적이 있다 — 그림을 재서 본다)
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import shorts as S                                          # noqa: E402
from PIL import Image                                       # noqa: E402

FAIL = []


def ck(label, cond, extra=""):
    print(("   ✅ " if cond else "   ❌ ") + label + (f"  ({extra})" if extra else ""))
    if not cond:
        FAIL.append(label)


def rows_with_ink(img, y0, y1):
    """그 구간에서 글자가 실제로 그려진 줄 번호들."""
    a = img.crop((0, y0, S.W, y1)).split()[-1]        # 투명도 칸
    out = []
    for y in range(y1 - y0):
        line = a.crop((0, y, S.W, y + 1)).tobytes()
        if max(line) > 40:
            out.append(y0 + y)
    return out


print("⭐ 쇼츠 배치 시험\n")

print("① 칸이 서로 겹치지 않는가")
ck("위 검은 칸 → 영상 → 아래 검은 칸 순서다",
   S.HOOK_BOT <= S.VIDEO_Y < S.VIDEO_Y + S.VIDEO_H <= S.SUB_TOP,
   f"후킹끝 {S.HOOK_BOT} · 영상 {S.VIDEO_Y}~{S.VIDEO_Y + S.VIDEO_H} · 자막 {S.SUB_TOP}")
ck("영상이 정확히 4:3", S.W * 3 == S.VIDEO_H * 4, f"{S.W}×{S.VIDEO_H}")
ck("전체가 쇼츠 규격(9:16)", S.W * 16 == S.H * 9, f"{S.W}×{S.H}")
ck("유튜브 단추 자리(아래 300px 이상)를 비워 뒀다", S.H - S.SUB_BOT >= 300,
   f"{S.H - S.SUB_BOT}px 비움")

print("\n② 글자가 제자리에만 그려지는가 (그림을 픽셀로 잰다)")
with tempfile.TemporaryDirectory() as d:
    png = S.overlay_png("바람난 남편이 빼돌린 15억",
                        "당신 진짜 제정신이야? / 더는 숨 막혀서 못 살아. / "
                        "누구 맘대로 집을 나가!", Path(d) / "t.png")
    img = Image.open(png).convert("RGBA")
    ck("그림 크기가 화면과 같다", img.size == (S.W, S.H), f"{img.size}")

    hook_ink = rows_with_ink(img, S.HOOK_TOP, S.HOOK_BOT)
    sub_ink = rows_with_ink(img, S.SUB_TOP, S.SUB_BOT)
    video_ink = rows_with_ink(img, S.VIDEO_Y, S.VIDEO_Y + S.VIDEO_H)
    below_ink = rows_with_ink(img, S.SUB_BOT, S.H)

    ck("후킹 문구가 위 칸에 그려졌다", len(hook_ink) > 20, f"{len(hook_ink)}줄")
    ck("자막이 아래 칸에 그려졌다", len(sub_ink) > 20, f"{len(sub_ink)}줄")
    ck("영상 자리에는 글자가 없다", not video_ink, f"{len(video_ink)}줄 침범")
    ck("유튜브 단추 자리에도 글자가 없다", not below_ink, f"{len(below_ink)}줄 침범")

    mark_ink = rows_with_ink(img, 0, S.VIDEO_Y and S.HOOK_TOP)
    ck("우측 상단에 채널 이름이 있다", len(mark_ink) > 5, f"{len(mark_ink)}줄")

print("\n③ 자막을 말한 사람마다 줄을 나누는가")
from PIL import ImageDraw                                   # noqa: E402
d0 = ImageDraw.Draw(Image.new("RGBA", (S.W, S.H)))
f, ls = S.fit(d0, "가나다라마. / 바사아자차. / 카타파하.", S.FONT_M,
              S.SUB_SIZE, S.W - S.SIDE * 2, 4, split_slash=True)
ck("빗금마다 줄이 바뀐다", len(ls) == 3, f"{ls}")
f, ls = S.fit(d0, "한 사람만 말하는 컷입니다.", S.FONT_M,
              S.SUB_SIZE, S.W - S.SIDE * 2, 4, split_slash=True)
ck("한 사람만 말하면 한 줄", len(ls) == 1, f"{ls}")

print("\n④ 긴 글도 칸을 안 넘는가 (글자를 줄여서라도 넣는다)")
long_hook = "이십 년을 함께 산 아내에게 남긴 것은 빚 칠억과 이혼 서류 한 장뿐이었다"
BOXH = S.HOOK_BOT - S.HOOK_TOP
f, ls = S.fit_box(d0, long_hook, S.FONT_H, S.W - S.SIDE * 2, BOXH,
                  S.HOOK_MAX, S.HOOK_MIN, S.HOOK_GAP, 3)
ck("긴 후킹 문구도 3줄 안에 들어간다", len(ls) <= 3, f"{len(ls)}줄 · {f.size}px")
ck("긴 것도 상자 높이를 안 넘는다",
   len(ls) * int(f.size * S.HOOK_GAP) <= BOXH,
   f"{len(ls) * int(f.size * S.HOOK_GAP)}px ≤ {BOXH}px")
ck("그래도 너무 작아지지는 않는다", f.size >= 40, f"{f.size}px")

# ⭐ 2026-08-21 운영자: "후킹 글꼴도 바뀌어야 하고 크기도 더 커져야 한다"
short_hook = "그 여자를 데려와 이혼을 요구했다"
f2, ls2 = S.fit_box(d0, short_hook, S.FONT_H, S.W - S.SIDE * 2, BOXH,
                    S.HOOK_MAX, S.HOOK_MIN, S.HOOK_GAP, 3)
ck("짧은 후킹은 **상자에 꽉 차게** 커진다", f2.size >= 110,
   f"{f2.size}px · {len(ls2)}줄")
ck("짧은 것도 상자 높이를 안 넘는다",
   len(ls2) * int(f2.size * S.HOOK_GAP) <= BOXH)
ck("긴 후킹은 알아서 작아진다", f2.size > f.size, f"{f2.size}px vs {f.size}px")
ck("후킹이 자막보다 확실히 크다", f2.size >= S.SUB_SIZE * 1.5,
   f"후킹 {f2.size}px · 자막 {S.SUB_SIZE}px")
ck("후킹 글꼴이 저장소에 들어 있다 (깃허브엔 한글 글꼴이 없다)",
   S.FONT_H.exists(), str(S.FONT_H.name))
ck("후킹 글꼴이 자막 글꼴보다 굵다", S.FONT_H != S.FONT_M)

# ⭐ 2026-08-21 운영자: "포인트 줄 있는 부분에는 색을 좀 넣어 보자"
print("\n④-2 후킹에서 별표로 감싼 토막만 색이 들어가는가")
MK = "보험금 *15억*도 그 여자 앞으로였다"
ck("토막을 강조/보통으로 가른다",
   S.runs_of(MK) == [("보험금 ", False), ("15억", True), ("도 그 여자 앞으로였다", False)],
   str(S.runs_of(MK)))
ck("별표가 없으면 통째로 보통", S.runs_of("그냥 한 줄") == [("그냥 한 줄", False)])
f3, ls3 = S.fit_box_runs(d0, MK, S.FONT_H, S.W - S.SIDE * 2, BOXH,
                         S.HOOK_MAX, S.HOOK_MIN, S.HOOK_GAP, 3)
# ⚠️ 줄이 바뀌는 자리의 띄어쓰기는 줄바꿈이 대신한다 — 이어 붙일 때 넣어 준다
flat = " ".join("".join(x for x, _ in l) for l in ls3)
ck("줄바꿈해도 글자가 안 사라진다",
   flat.replace(" ", "") == MK.replace("*", "").replace(" ", ""), flat)
ck("띄어쓰기가 살아 있다", flat == MK.replace("*", ""), flat)
ck("강조 토막이 그대로 남는다", "15억" in [x for l in ls3 for x, e in l if e],
   str([x for l in ls3 for x, e in l if e]))
ck("강조는 한 군데만", len([x for l in ls3 for x, e in l if e]) == 1)
# 낱말 한가운데가 갈리는 경우 (`*15억*도`) 도 견디는가
ck("조사가 붙어도 안 깨진다", "도 그 여자 앞으로였다" in flat, flat)

# 실제로 색이 다르게 칠해지는가 — 그림을 그려서 화소를 센다
from PIL import Image as _I, ImageDraw as _D
_img = _I.new("RGB", (S.W, S.H), (0, 0, 0))
_d = _D.Draw(_img)
S.block_runs(_d, ls3, f3, S.HOOK_TOP, S.HOOK_BOT, (255, 255, 255), S.HOOK_HI[:3],
             S.HOOK_GAP)
_raw = _img.crop((0, S.HOOK_TOP, S.W, S.HOOK_BOT)).tobytes()
_px = [(_raw[i], _raw[i + 1], _raw[i + 2]) for i in range(0, len(_raw), 3)]
_gold = sum(1 for r, g, b in _px if r > 200 and 150 < g < 235 and b < 140)
_white = sum(1 for r, g, b in _px if r > 230 and g > 230 and b > 230)
ck("금색 글자가 실제로 그려진다", _gold > 500, f"{_gold}화소")
ck("흰 글자가 더 많다 (한 토막만 칠했다)", _white > _gold, f"흰 {_white} · 금 {_gold}")

print("\n⑤ 진짜 영상으로 한 번 만들어 본다")
if not shutil.which("ffmpeg"):
    print("   ⚠️ ffmpeg 가 없어 건너뛴다")
else:
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        fake = d / "cut.mp4"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y",
             "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=24:d=2",
             "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(fake)],
            check=True, capture_output=True)
        out = S.compose(fake, "후킹 문구", "자막 한 줄", d / "o.mp4", d / "tmp")
        import clip as C
        w, h, sec = C.probe(out)
        ck("쇼츠 크기(1080×1920)로 나온다", (w, h) == (S.W, S.H), f"{w}×{h}")
        ck("길이가 원본과 같다", abs(sec - 2.0) < 0.3, f"{sec:.1f}초")
        a = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0",
                            "-show_entries", "stream=codec_name", "-of", "csv=p=0",
                            str(out)], capture_output=True, text=True).stdout.strip()
        ck("소리가 붙어 있다", a != "", a or "없음")

print("\n⑥ 자막이 사람마다 가라오케로 켜지는가 (2026-08-20 운영자 지시)")
SUB3 = "당신 진짜 제정신이야? / 더는 숨 막혀서 못 살아. / 누구 맘대로 집을 나가!"

# 한 사람 대사가 두 줄로 접혀도 그 두 줄은 **같이** 켜져야 한다
f, ls, owner = S.fit_owned(d0, ["짧은 말.", "아주 길어서 한 줄에 안 들어가는 대사가 여기 있고 이것은 접힌다."],
                           S.FONT_M, S.SUB_SIZE, 420, 6)
ck("접힌 줄도 같은 사람 것으로 묶인다", len(set(owner)) == 2 and owner.count(1) >= 2,
   f"임자 {owner}")

# 소리를 못 읽으면 음절 수에 비례해 나눈다 (똑같이 나누는 것보다 가깝다)
sp = S.by_syllable(3, 6.0, ["짧아.", "이건 조금 더 긴 대사입니다.", "중간."])
ck("음절 수 비례로 나눈다 (긴 대사가 긴 시간)",
   (sp[1][1] - sp[1][0]) > (sp[0][1] - sp[0][0]),
   " ".join(f"{b - a:.1f}초" for a, b in sp))
ck("나눈 시간이 빈틈없이 이어진다",
   abs(sp[0][1] - sp[1][0]) < 1e-6 and abs(sp[-1][1] - 6.0) < 1e-6)
ck("한 사람만 말하면 통째로 한 구간", S.speech_spans("없는파일.mp4", 1, 6.0) == [(0.0, 6.0)])

if shutil.which("ffmpeg"):
    with tempfile.TemporaryDirectory() as dd:
        dd = Path(dd)
        # 말 1.5 / 쉼 0.5 / 말 1.8 / 쉼 0.4 / 말 1.8 = 세 사람이 번갈아 말하는 6초
        a = ("sine=f=300:d=6,volume='if(between(t,0,1.5)+between(t,2.0,3.8)"
             "+between(t,4.2,6.0),1,0)':eval=frame")
        src = dd / "cut.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y",
                        "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=24:d=6",
                        "-f", "lavfi", "-i", a, "-t", "6",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", str(src)], check=True, capture_output=True)

        sp = S.speech_spans(src, 3, 6.0)
        ck("소리에서 사람 수만큼 토막을 찾는다", len(sp) == 3,
           " ".join(f"{x:.1f}~{y:.1f}" for x, y in sp))
        ck("찾은 자리가 실제 말한 자리와 맞는다",
           abs(sp[1][0] - 2.0) < 0.3 and abs(sp[2][0] - 4.2) < 0.3,
           f"두 번째 {sp[1][0]:.2f}초 · 세 번째 {sp[2][0]:.2f}초")

        out = S.compose(src, "후킹 문구", SUB3, dd / "o.mp4", dd / "tmp")

        def ink_at(t):
            """그 시각 자막 칸에 글자가 얼마나 있는가 (몇 줄에 걸쳐 있는가)."""
            raw = subprocess.run(
                ["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(out),
                 "-frames:v", "1", "-vf",
                 f"crop={S.W}:{S.SUB_BOT - S.SUB_TOP}:0:{S.SUB_TOP},format=gray",
                 "-f", "rawvideo", "-"], capture_output=True).stdout
            band = S.SUB_BOT - S.SUB_TOP
            rows = [max(raw[y * S.W:(y + 1) * S.W]) > 60 for y in range(band)]
            return sum(rows), rows

        # ⭐ 운영자: "모든 대사가 한 번에 다 뜨지 않아" → 한 번에 **한 토막만**
        heights = []
        for t in (1.0, 3.0, 5.0):
            n, rows = ink_at(t)
            heights.append(n)
            ck(f"{t}초에 글자가 떠 있다", n > 10, f"{n}줄")
        one_line = int(S.SUB_SIZE * 1.5)
        ck("한 번에 한 토막만 뜬다 (세 줄이 한꺼번에 뜨지 않는다)",
           all(h <= one_line for h in heights), f"{heights} · 한 줄 ≈ {one_line}줄")

        # 시각마다 **다른 글자**가 떠야 한다 (같은 그림이 계속 있으면 안 바뀐 것)
        def frame_bytes(t):
            return subprocess.run(
                ["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(out),
                 "-frames:v", "1", "-vf",
                 f"crop={S.W}:{S.SUB_BOT - S.SUB_TOP}:0:{S.SUB_TOP},format=gray",
                 "-f", "rawvideo", "-"], capture_output=True).stdout
        a, b, c = frame_bytes(1.0), frame_bytes(3.0), frame_bytes(5.0)
        ck("시각마다 자막이 바뀐다", a != b and b != c and a != c)

        # 한 사람이 길게 말하는 컷은 반 문장씩
        ck("긴 혼잣말은 문장 단위로 끊는다",
           len(S.sub_chunks("내 인생 찾겠다는 거야. 당신도 이제 당신 인생 살아. "
                            "난 더 이상 안 돌아와.")[0]) == 3)
        ck("주고받는 컷은 사람마다 한 토막",
           S.sub_chunks("가나다라마 바사. / 아자차카타 파하. / 가나다라마 바사.")[0]
           == ["가나다라마 바사.", "아자차카타 파하.", "가나다라마 바사."])
        ck("짧은 한마디는 안 쪼갠다", len(S.sub_chunks("뭐라고?")[0]) == 1)
        ch = S.sub_chunks("조만간 서류 보낼 테니까 도장이나 찍어. 쓸데없이 고집 피우지 말고.")[0]
        ck("끊긴 토막이 고르게 나뉜다",
           abs(S.syl(ch[0]) - S.syl(ch[1])) <= 8,
           " + ".join(str(S.syl(x)) for x in ch) + "음절")

# ⑦ 클립 하나로 시험할 때도 **소리를 갈아 끼우는가**
#
# ⚠️⚠️ 2026-08-21 사고 — 미리보기(--demo)가 compose() 만 불렀다. 소리를 안
#    갈아 끼우는데 화면은 멀쩡히 나오니 다 된 줄 알고 운영자에게 보냈고,
#    운영자는 한동안 플로우가 만든 외국인 같은 소리를 듣고 있었다.
#    **미리보기가 진짜와 다른 길로 가면, 미리보기는 거짓말이 된다.**
print("\n⑦ 클립 하나로 시험할 때도 소리를 갈아 끼우는가")
_src = (ROOT / "src" / "shorts.py").read_text(encoding="utf-8")
_one = _src[_src.index("def one("):_src.index("def main(")]
# ⚠️ 설명글(docstring)에도 compose() 같은 말이 나온다. 자리를 재기 전에
#    설명글을 걷어 낸다 — 안 그러면 설명글을 실제 부름으로 잘못 센다.
_one = _one[_one.index('"""', _one.index('"""') + 3) + 3:]
ck("미리보기에도 소리 갈아 끼우기가 들어 있다", "dub(" in _one,
      "이게 빠지면 원본(외국인 같은) 소리가 완성본이라고 나간다")
_i_trim, _i_dub, _i_comp = (_one.find("trim_dead("), _one.find("dub("),
                            _one.find("compose("))
ck("차례가 ① 잘라내기 ② 소리 ③ 자막·크롭 순이다",
      -1 < _i_trim < _i_dub < _i_comp,
      f"자리 {_i_trim}/{_i_dub}/{_i_comp} — 자막은 **소리에서** 말한 자리를 찾으므로 "
      "소리를 먼저 갈아 끼워야 한다")
ck("못 갈아 끼웠으면 크게 알린다", "원래 소리를 그대로 쓴다" in _one)

# 관리자 페이지 ↔ 워크플로가 '몇 컷 시험' 을 같은 말로 주고받는가
_wf = (ROOT / ".github" / "workflows" / "shorts.yml").read_text(encoding="utf-8")
_ad = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
ck("워크플로가 'cut' 을 받는다", "\n      cut:" in _wf)
ck("관리자 페이지가 'cut' 을 보낸다", "{ sid, ep, cut }" in _ad)
ck("시험본이 완성본을 덮어쓰지 않는다 (딴 이름을 쓴다)",
      "-cut${cut}" in _ad and "-cut${CUT}" in _wf,
      "같은 이름이면 시험 한 번에 5컷짜리 완성본이 날아간다")
ck("고르는 칸이 화면에 있다", "cutone" in _ad)

print("\n" + "─" * 52)
print(f"❌ 쇼츠 배치: {len(FAIL)}가지 실패" if FAIL else "✅ 쇼츠 배치: 전부 통과")
sys.exit(1 if FAIL else 0)
