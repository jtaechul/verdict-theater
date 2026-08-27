#!/usr/bin/env python3
"""손님이 관리자 페이지에서 올린 **컷 영상**을 받아 자리에 놓는다.

    python3 tools/fetch_clips.py '{"4":"https://…","7":"https://…"}' build/s90/clips

왜 (2026-08-27 손님: "이미지는 중간중간 섞여 있고 동영상도 있어야 돼")
    맞다. 전부 그림이면 슬라이드쇼다. 말하는 컷은 사람이 실제로 말해야 한다.
    컷 번호마다 영상을 받아 cNN.mp4 로 두면, src/short90.py 가 **그 컷만**
    영상으로 만들고 나머지는 그림으로 간다.
"""
import json
import sys
import urllib.request
from pathlib import Path

MIN_BYTES = 50_000
MAX_CUT = 99


def main():
    raw = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "build/s90/clips")
    if not raw or raw in ("{}", "null"):
        print("■ 올린 컷 영상이 없다 — 전부 그림으로 만든다")
        return 0
    try:
        got = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ 올린 영상 목록을 못 읽었다: {e}")
        return 1
    if not isinstance(got, dict):
        print("❌ 올린 영상 목록이 컷번호:주소 꼴이 아니다")
        return 1

    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for k, url in got.items():
        try:
            cut = int(str(k))
        except ValueError:
            print(f"  ⚠️ 컷 번호가 아니라 건너뛴다: {k}")
            continue
        if not 1 <= cut <= MAX_CUT:
            print(f"  ⚠️ 컷 번호가 벗어났다 — 건너뛴다: {cut}")
            continue
        if not isinstance(url, str) or not url.startswith("http"):
            print(f"  ⚠️ 컷{cut}: 주소가 이상하다 — 건너뛴다")
            continue
        dst = out / f"c{cut:02d}.mp4"
        try:
            with urllib.request.urlopen(url, timeout=300) as r, open(dst, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
        except Exception as e:                                # noqa: BLE001
            print(f"  ❌ 컷{cut}: 못 받았다 ({str(e)[:80]})")
            return 1
        if dst.stat().st_size < MIN_BYTES:
            print(f"  ❌ 컷{cut}: 받은 영상이 너무 작다 ({dst.stat().st_size} 바이트)")
            return 1
        n += 1
        print(f"  ✅ 컷{cut} ({dst.stat().st_size / 1e6:.1f}MB) — 이 컷은 영상으로 갑니다")
    print(f"\n■ 올리신 컷 영상 {n}개를 씁니다 (나머지 컷은 그림)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
