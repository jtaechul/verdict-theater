#!/usr/bin/env python3
"""⭐ **썸네일이 진짜로 만들어지고 진짜로 올라가는가.** 값 0원.

    python3 tools/thumb_check.py

⭐⭐⭐ 2026-09-07 손님: "섬네일을 내가 지정한 걸로 똑바로 지금 올렸으면 이런 일
   없잖아. 맨날 올릴 때 섬네일이 이상한 대로 지정되어 있으니까."

   맞는 말씀이었다. 90초 쇼츠를 올리는 길에는 **썸네일이 한 군데도 없었다** —
   만들지도 않았고(src/short90.py), 올리지도 않았다(upload.py cmd_series).
   그래서 유튜브가 영상 한가운데 아무 장면이나 골라 썼다.
   16화 쪽(cmd_public)에는 set_thumbnail 이 있었는데 90초 쪽만 빠져 있었다.

여기서 보는 것
   ① 만들 때 썸네일이 나오는가 (진짜 영상에서 뽑아 본다)
   ② 보관함에 넣고, 치울 때 안 지우는가
   ③ 올릴 때 꺼내 와서 **두 길 다** 넘기는가 (세 편·한 편)
   ④ 올린 뒤 실제로 set_thumbnail 을 부르는가 (세 길 다)
"""
import io
import re
import subprocess
import sys
import tempfile
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def code_of(text):
    """주석과 따옴표 안 설명글을 걷어내고 **진짜 코드만** 남긴다.

    ⚠️ 설명글에 적힌 낱말을 읽고 통과시키는 사고가 이 저장소에서 이미
       났다(2026-09-06 ledger_check). 자리는 그대로 두고 빈칸으로 지운다."""
    lines = text.splitlines(keepends=True)
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except Exception:                                        # noqa: BLE001
        return re.sub(r"#.*", "", text)
    for tok in toks:
        if tok.type not in (tokenize.COMMENT, tokenize.STRING):
            continue
        (r1, c1), (r2, c2) = tok.start, tok.end
        for r in range(r1, r2 + 1):
            ln = lines[r - 1]
            a = c1 if r == r1 else 0
            b = c2 if r == r2 else len(ln)
            lines[r - 1] = ln[:a] + " " * (b - a) + ln[b:]
    return "".join(lines)


def fn_of(code, name):
    """그 함수 몸통만 잘라 낸다 (다른 함수의 코드를 보고 통과하면 안 된다)."""
    m = re.search(rf"\ndef {name}\(([\s\S]*?)(?=\ndef |\Z)", code)
    return m.group(0) if m else ""


def main():
    print("⭐ 썸네일이 만들어지고 올라가는가 (값 0원)\n")

    print("① 만들 때 썸네일이 나오는가")
    sh = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
    shc = code_of(sh)
    ck("썸네일 자리를 정해 둔다 (part_thumb)", "def part_thumb(" in shc)
    ck("영상에서 한 장면을 뽑는다 (make_thumb)", "def make_thumb(" in shc)
    ck("편을 조립할 때 실제로 부른다",
       "make_thumb(" in fn_of(shc, "build_part"),
       "함수만 있고 아무도 안 부르면 파일이 안 생긴다")

    # ⚠️ 붙박이 영상으로 **진짜 뽑아 본다** — 코드만 보면 '되겠지' 로 끝난다
    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode == 0:
        sys.path.insert(0, str(ROOT / "src"))
        import short90 as S9                                 # noqa: E402
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            mp4 = d / "t.mp4"
            subprocess.run(
                ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                 "-i", "testsrc=size=1080x1920:rate=30:duration=3",
                 "-pix_fmt", "yuv420p", str(mp4)], check=True)
            out = S9.make_thumb(mp4, d / "t.jpg")
            ck("진짜 영상에서 JPEG 이 나온다", out.exists() and out.stat().st_size > 0)
            ck(f"유튜브 상한 2MB 밑이다 ({out.stat().st_size / 1000:.0f}KB)",
               out.exists() and out.stat().st_size <= S9.THUMB_MAX_BYTES)
            ck("세로(9:16) 그대로 뽑힌다", b"\xff\xd8" == out.read_bytes()[:2],
               "JPEG 이 아니다")
    else:
        print("   (ffmpeg 이 없어 실제 뽑기는 건너뛴다)")

    print("\n② 보관함에 넣고, 치울 때 안 지우는가")
    mk = (ROOT / ".github" / "workflows" / "short90.yml").read_text(encoding="utf-8")
    ck("보관함에 썸네일을 넣는다", 'put "short90-$S" \\\n              "part$K.jpg"' in mk
       or re.search(r'put "short90-\$S"[\s\\]*"part\$K\.jpg"', mk) is not None)
    prune = re.search(r"prune[\s\S]{0,600}?\|\| true", mk)
    ck("치울 때 썸네일을 남긴다 (prune 목록에 있다)",
       prune and "part1.jpg" in prune.group(0) and "part3.jpg" in prune.group(0),
       "prune 은 '남길 것만 두고 다 지운다' — 목록에 없으면 매번 지워진다")

    print("\n③ 올릴 때 꺼내 와서 두 길 다 넘기는가")
    up = (ROOT / ".github" / "workflows" / "short90-upload.yml").read_text(encoding="utf-8")
    ck("보관함에서 썸네일을 꺼낸다", 'part$K.jpg' in up)
    n = len(re.findall(r"--thumb ", up))
    ck(f"세 편 길·한 편 길 둘 다 넘긴다 (지금 {n}자리)", n >= 2,
       "한 자리만 있으면 다른 길로 올릴 때 또 빠진다")
    ck("글만 고칠 때도 썸네일을 갈아 끼운다", "--thumb-dir" in up)

    print("\n④ 올린 뒤 실제로 set_thumbnail 을 부르는가")
    ul = code_of((ROOT / "src" / "upload.py").read_text(encoding="utf-8"))
    for f in ("cmd_series", "cmd_fixmeta"):
        ck(f"{f} 가 set_thumbnail 을 부른다", "set_thumbnail(" in fn_of(ul, f),
           "썸네일 파일만 만들고 안 올리면 아무 일도 안 난다")
    ck("썸네일이 실패해도 영상은 살린다 (try/except)",
       re.search(r"try:[\s\S]{0,200}set_thumbnail\(", fn_of(ul, "cmd_series")),
       "썸네일 하나 때문에 이미 올라간 영상이 실패로 뜨면 안 된다")

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 썸네일: {len(bad)}군데 — 유튜브가 아무 장면이나 고른다")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 썸네일: 만들고 · 보관하고 · 꺼내서 · 진짜로 올린다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
