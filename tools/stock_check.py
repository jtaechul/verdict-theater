#!/usr/bin/env python3
"""⭐ 장소 컷 무료 실사 영상이 **사람을 안 들이는가**. 값 0원 (인터넷 0회).

    python3 tools/stock_check.py

⭐⭐⭐ 2026-09-17 손님: "Pexels videos 장소 컷에만 넣는 거 진행해!
   대신 우리의 색감은 입혀서 영상으로 제작하자."

여기서 지키는 것 — 이 저장소가 가장 여러 번 사고 난 자리다
   ① **사람 나오는 컷에는 절대 안 쓴다** (핵심 규칙)
   ② 주소 설명에 사람 낱말이 있으면 버린다
   ③ 눈으로 못 보면(열쇠 없음) **버린다** — 모를 때는 안 쓰는 쪽
   ④ 우리 색감을 입힌다 (안 입히면 그림 컷과 색이 튄다)
   ⑤ 열쇠가 없어도 안 죽는다 — 그냥 그림으로 간다
   ⑥ 스톡이 있는 컷은 Veo 로 **또 사지 않는다** (값이 두 번 나간다)
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import stock_video as SV                                     # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name
          + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def main():
    print("⭐ 장소 컷 무료 실사 영상 (값 0원 · 인터넷 0회)\n")

    print("① 사람 나오는 컷에는 안 쓴다 (핵심 규칙)")
    doc = {"cuts": [
        {"n": 1, "who": [], "turns": [["나레이션", "빈 복도였습니다"]],
         "scene": "a long empty corridor"},
        {"n": 2, "who": ["아내"], "turns": [["나레이션", "아내가 서 있었습니다"]],
         "scene": "아내 stands in a long empty corridor"},
        {"n": 3, "who": ["딸"], "turns": [["딸", "엄마"]],
         "scene": "딸 stands in a corridor"},
    ]}
    ns = [c["n"] for c in SV.place_cuts(doc)]
    ck("사람 없는 나레이션 컷만 고른다", ns == [1], str(ns))
    ck("등장인물이 선 나레이션 컷은 안 고른다 (얼굴이 우리 사람이어야 한다)",
       2 not in ns)
    ck("대사 컷은 안 고른다", 3 not in ns)

    print("\n② 주소 설명으로 거른다")
    for url, want in (
            ("https://www.pexels.com/video/a-man-walking-in-the-hallway-1/", True),
            ("https://www.pexels.com/video/woman-sitting-by-window-2/", True),
            ("https://www.pexels.com/video/a-crowd-at-a-station-3/", True),
            ("https://www.pexels.com/video/empty-courtroom-benches-4/", False),
            ("https://www.pexels.com/video/rain-on-a-window-at-night-5/", False)):
        got = SV.looks_human({"url": url})
        ck(f"{'거른다' if want else '통과'} — {SV.slug_of({'url': url})[:34]}",
           got == want)
    # ⚠️ 낱말표를 **두 벌로 두지 않는다** — bg_fetch 것을 가져온다
    ck("사람 낱말표를 bg_fetch 에서 가져온다",
       "import bg_fetch" in (ROOT / "src" / "stock_video.py").read_text("utf-8"),
       "두 벌로 두면 한쪽만 고쳐져 규칙이 반쪽이 된다")
    ck("낱말표가 비어 있지 않다", len(SV._people_words()) >= 20,
       f"{len(SV._people_words())}개")

    print("\n③ 모를 때는 **버린다**")
    import os
    was = os.environ.pop("GEMINI_API_KEY", None)
    try:
        png = Path(tempfile.mkdtemp()) / "x.png"
        png.write_bytes(b"x")
        ck("눈으로 못 보면 안 쓴다 (사람이 섞이느니 그림으로)",
           SV.has_person(png) is True)
    finally:
        if was:
            os.environ["GEMINI_API_KEY"] = was
    src = (ROOT / "src" / "stock_video.py").read_text("utf-8")
    ck("검색어에 'no people' 을 박는다", "empty no people" in src)

    print("\n④ 우리 색감을 입히는가 (안 입히면 색이 튄다)")
    tmp = Path(tempfile.mkdtemp())
    raw, out = tmp / "raw.png", tmp / "out.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "testsrc2=s=640x360:d=1", "-frames:v", "1",
                    str(raw)], check=True)
    ck("색을 입혀 9:16 으로 만든다", SV.grade_to(raw, out, 1.0) and out.exists())
    if out.exists():
        from PIL import Image, ImageStat
        g = tmp / "g.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out),
                        "-frames:v", "1", str(g)], check=True)
        a = ImageStat.Stat(Image.open(raw).convert("HSV")).mean[1]
        b = ImageStat.Stat(Image.open(g).convert("HSV")).mean[1]
        ck(f"채도를 낮춘다 ({a:.0f} → {b:.0f})", b < a * 0.95)
        lo = min(Image.open(g).convert("L").getextrema())
        ck(f"블랙을 살짝 든다 (최저 밝기 {lo})", lo >= 20)
        w, h = Image.open(g).size
        ck(f"세로 9:16 이다 ({w}x{h})", (w, h) == (SV.W, SV.H))
    # ⚠️ 색 규격이 두 벌이 되면 안 된다 — 글로 적힌 COLOR 와 같은 결이어야 한다
    ck("낮은 채도·낮은 대비·든 블랙을 다 건드린다",
       "saturation=" in SV.GRADE and "contrast=" in SV.GRADE
       and "curves=" in SV.GRADE)

    print("\n⑤~⑥ 실패해도 안 죽는가 · 값이 두 번 안 나가는가")
    ck("열쇠가 없으면 검색을 아예 안 한다", SV.search("x") == []
       if not SV.key() else True)
    ck("열쇠가 없으면 조용히 그림으로 간다는 것을 적어 두었다",
       "그림 + 카메라 무빙으로 갑니다" in src)
    yml = (ROOT / ".github" / "workflows" / "short90.yml").read_text("utf-8")
    ck("워크플로에서 실패해도 편을 안 죽인다", "continue-on-error: true" in yml)
    ck("워크플로가 그림 **뒤에** 부른다 (그림이 밑바탕이다)",
       yml.index("2-1) 장소 컷") > yml.index("2) 컷 그림"))
    s9 = (ROOT / "src" / "short90.py").read_text("utf-8")
    ck("스톡이 있는 컷은 Veo 로 또 사지 않는다",
       "stock_dir() / f\"c{c['n']:02d}.mp4\").exists()" in s9,
       "값이 두 번 나간다")
    ck("조립이 사람 없는 나레이션 컷에만 스톡을 쓴다",
       'is_narr(c) and not (c.get("who") or [])' in s9)

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 장소 컷 실사 영상: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 장소 컷 실사 영상: 사람을 안 들이고 · 우리 색이고 · 공짜다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
