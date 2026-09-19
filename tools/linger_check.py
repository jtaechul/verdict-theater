#!/usr/bin/env python3
"""⭐ 그림 한 장이 **오래 머물지 않는가**. 값 0원 (인터넷 0회).

    python3 tools/linger_check.py

⭐⭐⭐ 2026-09-19 손님 선택 "C": "정지 그림은 오래 둘수록 들킨다.
   나레이션 컷을 3~4초로 끊고 컷 수를 늘린다."

   ⚠️ 원하신 **결과**는 "화면이 3~4초마다 바뀐다" 다. 컷을 늘리는 길은
      그림 값이 더 나가고(컷 하나 = 그림 한 장 = 132원), 편 컷 수 못
      (8~11컷)과 편 길이 못(46~55초)이 **서로 싸우게 된다** —
      한 컷을 4.5초로 막으면 8컷 편은 최대 36초라 46초 하한을 어떤 대본으로도
      못 넘긴다. 이 저장소가 두 번 당한 덫이다(검사가 버그를 지키게 된다).
   → **같은 그림을 다르게 잘라** 한 번 더 보여 주는 길로 갔다. 0원이고,
     편 길이가 그대로라 60초 벽을 안 건드리고, 이미 만든 S93 에도 먹는다.

여기서 지키는 것
   ① 한 프레이밍이 LINGER_MAX 를 넘게 안 머문다
   ② 너무 잘게 쪼개지 않는다 (2초짜리는 바뀐 게 아니라 깜빡인 것이다)
   ③ **컷 길이가 안 늘어난다** — 60초 벽을 안 건드린다
   ④ 이어지는 프레이밍은 크기가 확 다르다 (비슷하면 튄 것처럼 보인다)
   ⑤ 줌이 흐려지지 않는 범위(1.0~1.30) 안이다
   ⑥ 대사 컷은 옆으로 안 훑는다 (얼굴이 잘린다)
   ⑦ 이웃한 컷이 같은 조합을 되풀이하지 않는다
   ⑧ **진짜로 화면이 바뀐다** — 실제로 만들어 재 본다
   ⑨ 영상 컷에는 안 건다 (이미 움직인다)
   ⑩ 값이 0원이다 — 그림을 새로 안 만든다
"""
import json
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


def narr(n, sec_chars):
    return {"n": n, "who": [], "scene": "an empty hallway",
            "turns": [["나레이션", "가" * sec_chars]]}


def talk(n, sec_chars):
    return {"n": n, "who": ["아내"], "scene": "아내 in a hallway",
            "turns": [["아내", "가" * sec_chars]]}


def grid_png(d):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (S9.W, S9.H), (28, 28, 36))
    dr = ImageDraw.Draw(im)
    for i in range(0, S9.W, 40):
        dr.line([(i, 0), (i, S9.H)], fill=(200, 170, 90), width=3)
    for j in range(0, S9.H, 40):
        dr.line([(0, j), (S9.W, j)], fill=(90, 160, 200), width=3)
    p = Path(d) / "grid.png"
    im.save(p)
    return p


def render(c, png, sec, out):
    src, vf, nbg = S9.still_bg(c, png, sec)
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", *src,
                        "-filter_complex", vf.rstrip(";").replace("[bg]", "[v]"),
                        "-map", "[v]", "-t", f"{sec:.3f}", "-r", str(S9.FPS),
                        "-c:v", "libx264", "-preset", "ultrafast",
                        "-pix_fmt", "yuv420p", str(out)],
                       capture_output=True, text=True)
    return r, nbg


def swing(mp4):
    """화면이 **한 자리에서 확 바뀌는가** — (가장 큰 변화 / 보통 변화).

    ⚠️ 프레임 바로 옆끼리 재면 안 된다. 겹쳐 넘기기(0.4초)는 변화를 네 장에
       나눠 담으므로 옆끼리 보면 묻힌다. 또 알갱이(LIVE)와 줌 때문에 옆끼리는
       늘 조금씩 다르다. → **0.5초 떨어진 두 장**을 견주고, 그 값이 평소보다
       몇 배나 튀는지로 본다. 그림 내용과 상관없이 같은 잣대가 된다.
    """
    from PIL import Image, ImageChops, ImageStat
    d = Path(tempfile.mkdtemp())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4),
                    "-vf", "fps=10,scale=120:-1", str(d / "f%04d.png")],
                   check=True)
    fs = [Image.open(x).convert("L") for x in sorted(d.glob("f*.png"))]
    gap = 5                                      # 0.5초
    vs = [ImageStat.Stat(ImageChops.difference(fs[i], fs[i + gap])).mean[0]
          for i in range(len(fs) - gap)]
    if not vs:
        return 0.0
    mid = sorted(vs)[len(vs) // 2]
    return max(vs) / max(0.01, mid)


def main():
    print("⭐ 그림 한 장이 오래 머물지 않는가 (값 0원)\n")

    print("① 한 프레이밍이 오래 안 머문다 · ② 너무 잘게 안 쪼갠다 · "
          "③ 길이가 안 늘어난다")
    over, tiny, wrong = [], [], []
    for tenth in range(22, 131):                 # 2.2초 ~ 13.0초
        sec = tenth / 10.0
        for c in (narr(3, 10), talk(4, 10)):
            plan = S9.shot_plan(c, sec)
            n = len(plan)
            span = plan[0][0]
            if n < S9.SHOT_MAX and span > S9.LINGER_MAX + 0.01:
                over.append((sec, round(span, 2)))
            if n > 1 and span < S9.SHOT_MIN - 0.01:
                tiny.append((sec, round(span, 2)))
            # 이어 붙인 총 길이 = 토막합 - 겹침 = 컷 길이
            got = sum(d for d, _ in plan) - (n - 1) * S9.REFRAME_XFADE
            if abs(got - sec) > 0.01:
                wrong.append((sec, round(got, 2)))
    ck(f"한 프레이밍이 {S9.LINGER_MAX}초를 넘게 안 머문다", not over, str(over[:4]))
    ck(f"{S9.SHOT_MIN}초보다 잘게 안 쪼갠다", not tiny, str(tiny[:4]))
    ck("컷 길이가 그대로다 (60초 벽을 안 건드린다)", not wrong, str(wrong[:4]))
    ck(f"짧은 컷은 그냥 둔다 (한 프레이밍)",
       len(S9.shot_plan(narr(3, 10), S9.LINGER_MAX - 0.2)) == 1)
    ck("긴 컷은 쪼갠다", len(S9.shot_plan(narr(3, 10), S9.LINGER_MAX + 1.0)) >= 2)

    print("\n④ 이어지는 프레이밍은 크기가 확 다르다 · ⑤ 줌이 흐려지지 않는다")
    flat, blur, pan = [], [], []
    for n in range(1, 41):
      for sec in (6.0, 9.5):                     # 둘로 쪼갤 때 · 셋으로 쪼갤 때
        for c in (narr(n, 10), talk(n, 10)):
            plan = S9.shot_plan(c, sec)
            for (_d, m) in plan:
                if not (1.0 <= m[0] <= 1.30 and 1.0 <= m[1] <= 1.30):
                    blur.append((n, m[6]))
                if not TP.is_narr(c) and (abs(m[3] - m[2]) > 0.05
                                          or abs(m[5] - m[4]) > 0.05):
                    pan.append((n, m[6]))
            for i in range(1, len(plan)):
                # 앞 프레이밍이 **끝난 크기** 와 뒤가 **시작하는 크기**
                if abs(plan[i][1][0] - plan[i - 1][1][1]) < 0.15:
                    flat.append((n, plan[i - 1][1][6], plan[i][1][6]))
    ck("이어지는 두 프레이밍의 크기 차이가 확실하다 (0.15 이상)",
       not flat, str(flat[:3]))
    ck("줌이 1.0~1.30 안이다 (그 위는 흐려진다)", not blur, str(blur[:3]))
    ck("대사 컷은 옆으로 안 훑는다 (얼굴이 잘린다)", not pan, str(pan[:3]))

    print("\n⑦ 이웃한 컷이 같은 조합을 되풀이하지 않는다 (S93 실측)")
    f = ROOT / "data" / "series" / "S93.json"
    if f.exists():
        doc = json.loads(f.read_text("utf-8"))
        keys, secs = [], []
        for c in doc.get("cuts") or []:
            sec = TP.cut_base(c)
            secs.append(sec)
            keys.append(tuple(m[6] for _, m in S9.shot_plan(c, sec)))
        same = [i + 2 for i in range(len(keys) - 1) if keys[i] == keys[i + 1]]
        ck("이웃한 컷이 같은 조합이 아니다", not same, f"컷 {same}")
        shots = sum(len(k) for k in keys)
        was = sum(secs) / max(1, len(secs))
        now = sum(secs) / max(1, shots)
        ck(f"화면이 {was:.1f}초마다 → {now:.1f}초마다 바뀐다", now <= 3.6,
           "3~4초로 끊어 달라신 몫")
        ck(f"고른 조합이 여러 가지다 ({len(set(keys))}가지)", len(set(keys)) >= 6)
    else:
        ck("S93 대본이 있다", False, "data/series/S93.json 이 없다")

    print("\n⑧ 진짜로 화면이 바뀌는가 (실제로 만들어 잰다)")
    td = Path(tempfile.mkdtemp())
    png = grid_png(td)
    c = narr(5, 10)
    sec = 6.0
    one, two = td / "one.mp4", td / "two.mp4"
    was_l = S9.LINGER_MAX
    try:
        S9.LINGER_MAX = 999.0                    # 안 쪼갠 것
        r1, _ = render(c, png, sec, one)
    finally:
        S9.LINGER_MAX = was_l
    r2, nbg = render(c, png, sec, two)
    ck("안 쪼갠 것이 만들어진다", r1.returncode == 0, r1.stderr[:160])
    ck("쪼갠 것이 만들어진다", r2.returncode == 0, r2.stderr[:160])
    if one.exists() and two.exists():
        ck(f"길이가 그대로다 ({S9.dur_of(two):.2f}초)",
           abs(S9.dur_of(two) - sec) < 0.15, f"{S9.dur_of(two):.2f} != {sec}")
        j1, j2 = swing(one), swing(two)
        ck(f"화면이 한 자리에서 확 바뀐다 "
           f"(안 쪼갠 것 {j1:.2f}배 → 쪼갠 것 {j2:.2f}배)",
           j2 > max(1.6, j1 * 1.4), "바뀌는 자리가 안 보인다")
        # 첫 장과 끝 장이 **다른 크기**로 잡혀 있어야 한다 (넓게 → 바짝)
        from PIL import Image, ImageChops, ImageStat
        fd = Path(tempfile.mkdtemp())
        for lbl, t in (("a", 0.6), ("b", sec - 0.6)):
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}",
                            "-i", str(two), "-frames:v", "1",
                            str(fd / f"{lbl}.png")], check=True)
        a = Image.open(fd / "a.png").convert("L").resize((120, 213))
        b = Image.open(fd / "b.png").convert("L").resize((120, 213))
        gap = ImageStat.Stat(ImageChops.difference(a, b)).mean[0]
        ck(f"앞과 뒤가 다르게 잘려 있다 (밝기차 {gap:.1f})", gap > 3.0,
           "같은 자리를 그대로 보고 있다")

    print("\n⑨ 영상 컷에는 안 건다 · ⑩ 값이 0원이다")
    src = (ROOT / "src" / "short90.py").read_text("utf-8")
    call = "src, vf, nbg = still_bg(c, still, sec)"
    ck("그림일 때만 부른다 (clip·opener 가 있으면 안 부른다)",
       call in src and src.index("elif clip:") < src.index(call)
       and src.index("if opener:") < src.index(call))
    ck("그림을 새로 안 만든다 — 입력이 그림 한 장뿐이다",
       nbg == 1 and render(narr(5, 10), png, 9.0, td / "z.mp4")[1] == 1)
    ck("쪼개도 파일을 더 안 읽는다 (split 으로 갈라 쓴다)",
       S9.still_bg(narr(5, 10), png, 9.0)[0].count("-i") == 1)

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 머무는 시간: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 머무는 시간: 3초쯤마다 화면이 바뀌고 · 길이는 그대로고 · 공짜다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
