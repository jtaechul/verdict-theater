#!/usr/bin/env python3
"""유튜브 올리기 마지막 칸이 성한가 — 진짜로 올리지 않고 확인만 한다.

    python3 tools/upload_dry_test.py     인터넷 0회 · 0원 · 1초

왜 이 검사가 있는가 (2026-08-22)
    `shorts-upload.yml` 은 **한 번도 돈 적이 없다** (실행 기록 0건).
    쇼츠가 만들어지면 손님이 바로 그 단추를 누르신다. 거기서 또 죽으면
    "만들었는데 못 올린다" 가 된다.
    그래서 그 워크플로가 실제로 부르는 명령을 여기서 그대로 불러 본다.

    ⚠️ 올리지는 않는다(--dry). 유튜브 열쇠도 필요 없다. 값 0원.
"""

import json
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
bad = 0


def ck(what, cond, why=""):
    global bad
    if cond:
        print(f"   ✅ {what}")
    else:
        print(f"   ❌ {what}" + (f"  ({why})" if why else ""))
        bad = 1


def run(*args):
    r = subprocess.run([sys.executable, "src/upload.py", *args],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)


print("⭐ 유튜브 올리기 마지막 칸 (진짜로 올리지는 않는다)")

with tempfile.TemporaryDirectory() as d:
    tmp = pathlib.Path(d)
    vid = tmp / "short.mp4"
    vid.write_bytes(b"\x00" * 4096)          # 있기만 하면 된다 (연습이라 안 읽는다)
    meta = tmp / "meta.json"

    # ① 관리자 페이지에서 확인·수정한 글이 **그대로** 쓰이는가
    want = {"sid": "S001", "ep": 1,
            "title": "불륜녀를 집에 데려온 남편이 이혼하자고 했습니다 (1/16) #shorts",
            "description": "[바람난 남편이 빼돌린 15억] 1화 / 전 16화",
            "tags": ["불륜", "외도", "판결극장"], "privacy": "private"}
    meta.write_text(json.dumps(want, ensure_ascii=False), encoding="utf-8")

    rc, out = run("series", "S001", "1", "--video", str(vid),
                  "--meta", str(meta), "--privacy", "unlisted", "--dry")
    ck("연습이 통과한다", rc == 0, out.strip().splitlines()[-1] if out.strip() else "")
    ck("화면에서 본 제목이 그대로 간다", want["title"] in out)
    ck("해시태그가 그대로 간다", "#불륜" in out and "#판결극장" in out)
    ck("화면에서 고른 공개 범위가 이긴다 (글에 적힌 것보다)",
       "공개 범위: unlisted" in out,
       "화면에서 '일부 공개' 를 골랐는데 글의 private 이 이기면 안 된다")
    ck("연습이면 진짜로 안 올린다", "실제로는 올리지 않았다" in out)

    # ② 이상한 것은 올리기 전에 막는가
    rc, out = run("series", "S001", "1", "--video", str(vid),
                  "--meta", str(meta), "--privacy", "전체공개", "--dry")
    ck("모르는 공개 범위는 막는다", rc != 0 and "공개 범위가 이상하다" in out)

    rc, out = run("series", "S001", "1", "--video", str(tmp / "없다.mp4"),
                  "--meta", str(meta), "--dry")
    ck("영상이 없으면 막는다", rc != 0 and "영상이 없다" in out)

    meta.write_text(json.dumps({**want, "title": "  "}, ensure_ascii=False),
                    encoding="utf-8")
    rc, out = run("series", "S001", "1", "--video", str(vid),
                  "--meta", str(meta), "--dry")
    ck("제목이 비었으면 막는다", rc != 0 and "제목이 비었다" in out,
       "제목 없이 올라가면 유튜브에서 손으로 고쳐야 한다")

    # ③ 화면에서 아무것도 안 고르면 글에 적힌 공개 범위를 쓴다
    meta.write_text(json.dumps(want, ensure_ascii=False), encoding="utf-8")
    rc, out = run("series", "S001", "1", "--video", str(vid),
                  "--meta", str(meta), "--dry")
    ck("안 고르면 글에 적힌 것으로 간다 (기본은 비공개)",
       rc == 0 and "공개 범위: private" in out,
       "기본이 전체 공개면 사고가 난다")

print("────────────────────────────────────────────────────")
print("❌ 올리기 칸: 걸린 것이 있다" if bad else "✅ 올리기 칸: 성하다")
sys.exit(bad)
