#!/usr/bin/env python3
"""보관함에 **진짜로 들어갔는지** 눈으로 안 믿고 확인한다 (값 0원).

    python3 tools/release_verify.py short90-S90 part1.mp4 part2.mp4 part3.mp4

⭐⭐⭐ 2026-09-02 손님: "영상 재생은 안 되는데 확인해봐."
   세 편을 다 만들었는데 보관함에는 마지막 한 편만 남아 있었다. 올리는 줄이
   **바로 다음 줄에서 앞 편을 지우고** 있었기 때문이다(prune 을 편마다 돌렸다).
   그런데 워크플로는 초록불이었다 — 올리는 것도 지우는 것도 각각은 성공했으니까.

   **올렸다는 것과 남아 있다는 것은 다르다.** 여기서 마지막에 한 번 더 물어
   본다. 없으면 워크플로를 빨간불로 만든다 — 화면이 "만들어짐" 이라고 적어
   놓고 실제로는 재생이 안 되는 일이 다시는 없게.
"""
import json
import os
import sys
import urllib.request

API = "https://api.github.com"


def repo():
    return f"{API}/repos/{os.environ.get('GITHUB_REPOSITORY', '')}"


def call(url):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {os.environ.get('GH_TOKEN', '')}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "verdict-theater",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main():
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    tag, want = sys.argv[1], sys.argv[2:]
    try:
        rel = call(f"{repo()}/releases/tags/{tag}")
    except Exception as e:                                   # noqa: BLE001
        print(f"❌ 보관함 {tag} 를 못 열었습니다: {str(e)[:120]}")
        return 1
    have = {a["name"]: a.get("size", 0) for a in rel.get("assets", [])}
    bad = []
    for n in want:
        sz = have.get(n)
        if sz is None:
            bad.append(f"{n} 없음")
        elif sz < 100_000:
            bad.append(f"{n} 너무 작음 ({sz:,} 바이트)")
        else:
            print(f"   ✅ {n} ({sz / 1e6:.1f}MB)")
    if bad:
        print(f"\n❌ 보관함 {tag} 에 빠진 것이 있습니다 — " + " · ".join(bad))
        print("   올리기는 됐는데 남아 있지 않다면, 뒤에서 지우는 줄을 보십시오"
              " (release_file.py prune).")
        print(f"   지금 들어 있는 것: {', '.join(sorted(have)) or '(없음)'}")
        return 1
    print(f"\n■ 보관함 {tag} — 편 {len(want)}개 모두 들어 있습니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
