#!/usr/bin/env python3
"""⭐ **한 컷은 한 프레이밍이다** — 같은 그림을 겹쳐 넘겨 두 번 보여 주지 않는다.
   값 0원 (인터넷 0회).

    python3 tools/linger_check.py

⭐⭐⭐ 2026-09-19 — 이 검사는 **되돌린 일을 지키는 못**이다.

   그날 낮: "정지 그림은 오래 둘수록 들킨다" 는 진단에 따라, 긴 컷을 둘로
   잘라 같은 그림을 넓게 → 바짝 두 번 보여 주게 했다(겹쳐 넘기기).
   그날 저녁 손님:
       "이렇게 줌을 두 번 하는 거는 굉장히 어색하고 **더 이미지인 걸
        부각하는 것 같다.**"
   맞는 말씀이고 까닭이 분명하다 — 같은 그림을 다시 보여 주면 **새 정보가
   0**이다. 눈은 "화면이 바뀌었다" 보다 "아까 그 사진을 또 보네" 를 먼저
   읽는다. 감추려던 것을 되레 드러냈다.

   ⚠️⚠️ **진짜 병은 따로 있었다.** 컷이 오래 머무는 것이 아니라 **36컷의
      구도가 전부 같은 것**이었다. tools/build_short90.py 의 연출(shot_of —
      와이드·인서트·로우앵글·어깨너머·락오프)은 **영상 프롬프트에만** 이어져
      있고, 그림 프롬프트는 "허리 위 미디엄" 과 "빈 방 와이드" 두 가지뿐이라
      한 프레임도 안 닿았다. 게다가 마지막 실행은 영상을 한 편도 안 샀다.
      → 증상을 건드리면 이렇게 **더 나빠진다.** 병을 고쳐야 한다.

여기서 지키는 것
   ① 한 컷 = 한 프레이밍 (같은 그림을 겹쳐 넘기지 않는다)
   ② 컷 길이가 카메라 때문에 달라지지 않는다 (60초 벽을 안 건드린다)
   ③ 카메라는 컷마다 **다르게** 움직인다 (이웃이 같으면 안 움직이는 듯 보인다)
   ④ 그림이 진짜로 움직인다 — 실제로 만들어 잰다
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import short90 as S9                                        # noqa: E402
import talkplan as TP                                       # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name
          + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def narr(n):
    return {"n": n, "who": [], "scene": "an empty hallway",
            "turns": [["나레이션", "가" * 30]]}


def talk(n):
    return {"n": n, "who": ["아내"], "scene": "아내 in a hallway",
            "turns": [["아내", "가" * 30]]}


def main():
    print("⭐ 한 컷은 한 프레이밍인가 (값 0원)\n")

    print("① 같은 그림을 겹쳐 넘겨 두 번 보여 주지 않는다")
    many = []
    for tenth in range(22, 161):                 # 2.2초 ~ 16.0초
        sec = tenth / 10.0
        for c in (narr(3), talk(4)):
            plan = S9.shot_plan(c, sec)
            if len(plan) != 1 or abs(plan[0][0] - sec) > 1e-6:
                many.append((sec, len(plan)))
    ck("아무리 긴 컷도 프레이밍은 하나다", not many, str(many[:4]))
    # ⚠️ 소스를 잘라 보면 옆 함수(open_bg — 영상→그림 넘김에 xfade 를 정당하게
    #    쓴다)까지 딸려 온다. **만들어 낸 필터 글**을 직접 본다.
    td0 = Path(tempfile.mkdtemp())
    png0 = td0 / "x.png"
    png0.write_bytes(b"x")
    long_vf = S9.still_bg(narr(5), png0, 14.0)[1]
    ck("긴 컷에도 겹쳐 넘기기(xfade)를 안 쓴다", "xfade" not in long_vf,
       "같은 그림을 두 번 보여 주게 된다")
    ck("그림 입력을 갈라 쓰지(split) 않는다", "split=" not in long_vf)
    src = (ROOT / "src" / "short90.py").read_text("utf-8")
    ck("되돌린 까닭을 적어 두었다",
       "더 이미지인 걸" in src and "새 정보가" in src,
       "왜 뺐는지 없으면 누군가 또 넣는다")

    print("\n② 컷 길이가 카메라 때문에 달라지지 않는다 (60초 벽)")
    off = [round(s / 10.0, 1) for s in range(22, 161)
           if abs(S9.shot_plan(narr(5), s / 10.0)[0][0] - s / 10.0) > 1e-6]
    ck("카메라가 컷 길이를 안 건드린다", not off, str(off[:4]))

    print("\n③ 카메라가 컷마다 다르게 움직이는가")
    ns = list(range(1, 38))
    moves = [S9.move_of(narr(n)) for n in ns]
    same = [n for n, a, b in zip(ns[1:], moves[1:], moves) if a == b]
    ck("이웃한 나레이션 컷이 같은 움직임이 아니다", not same, str(same[:5]))
    ck(f"움직임이 여러 가지다 ({len({m[6] for m in moves})}가지)",
       len({m[6] for m in moves}) >= 3)
    tm = [S9.move_of(talk(n)) for n in ns]
    # ⭐ 2026-09-20 — 대사 컷도 옆으로 움직이되, 한도는 **나레이션 표에서
    #    계산한다**(short90_dryrun.py 와 같은 잣대 — 손으로 적으면 둘이
    #    어긋난다). 그 이상이면 얼굴이 잘릴 만큼 크게 훑는 것이다.
    cap_x = max(abs(S9.MOVES[i][3] - S9.MOVES[i][2]) for i in S9.MOVES_NARR) * 0.75
    cap_y = max(abs(S9.MOVES[i][5] - S9.MOVES[i][4]) for i in S9.MOVES_NARR) * 0.75
    ck("대사 컷은 폭을 줄여서만 움직인다 (얼굴이 잘릴 만큼 크게는 안 훑는다)",
       all(abs(m[3] - m[2]) <= cap_x and abs(m[5] - m[4]) <= cap_y for m in tm))
    ck("줌이 흐려지지 않는 범위 안이다 (1.0~1.30)",
       all(1.0 < m[0] <= 1.30 and 1.0 < m[1] <= 1.30 for m in moves + tm))

    print("\n④ 그림이 진짜로 움직이는가 (실제로 만들어 잰다)")
    from PIL import Image, ImageChops, ImageDraw, ImageStat
    td = Path(tempfile.mkdtemp())
    im = Image.new("RGB", (S9.W, S9.H), (28, 28, 36))
    dr = ImageDraw.Draw(im)
    for i in range(0, S9.W, 40):
        dr.line([(i, 0), (i, S9.H)], fill=(200, 170, 90), width=3)
    for j in range(0, S9.H, 40):
        dr.line([(0, j), (S9.W, j)], fill=(90, 160, 200), width=3)
    png = td / "g.png"
    im.save(png)
    sec = 5.0
    c = narr(5)
    s2, vf, nbg = S9.still_bg(c, png, sec)
    out = td / "o.mp4"
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", *s2, "-filter_complex",
                        vf.rstrip(";").replace("[bg]", "[v]"), "-map", "[v]",
                        "-t", f"{sec:.3f}", "-r", str(S9.FPS), "-c:v", "libx264",
                        "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(out)],
                       capture_output=True, text=True)
    ck("만들어진다", r.returncode == 0, r.stderr[:160])
    ck("배경 입력은 그림 한 장뿐이다", nbg == 1)
    if out.exists():
        ck(f"길이가 그대로다 ({S9.dur_of(out):.2f}초)",
           abs(S9.dur_of(out) - sec) < 0.15)
        for lbl, t in (("a", 0.4), ("b", sec - 0.4)):
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}",
                            "-i", str(out), "-frames:v", "1",
                            str(td / f"{lbl}.png")], check=True)
        a = Image.open(td / "a.png").convert("L").resize((120, 213))
        b = Image.open(td / "b.png").convert("L").resize((120, 213))
        gap = ImageStat.Stat(ImageChops.difference(a, b)).mean[0]
        ck(f"처음과 끝이 다르다 — 카메라가 움직인다 (밝기차 {gap:.1f})", gap > 3.0,
           "정지 사진 그대로다")

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 프레이밍: {len(bad)}군데")
        for x in bad:
            print(f"     {x}")
        return 1
    print("✅ 프레이밍: 한 컷에 하나 · 길이는 그대로 · 카메라는 컷마다 다르다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
