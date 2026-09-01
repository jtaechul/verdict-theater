#!/usr/bin/env python3
"""지금부터 N시간 뒤를 유튜브가 받는 모양으로 찍어 준다.

    python3 tools/plus_hours.py 24     → 2026-09-02T05:18:00Z

⭐ 2026-09-01 — 한 사건을 세 편으로 나눠 올릴 때, 2·3편은 **예약 공개**로
   하루씩 띄운다. 손님이 사흘 동안 다시 안 들어오셔도 알아서 뜬다.

⚠️ 유튜브는 **Z 로 끝나는 UTC** 만 받는다. 우리 나라 시각으로 적으면 9시간
   어긋나 엉뚱한 때 공개된다 — 그래서 여기 한 곳에서만 만든다.
⚠️ 워크플로 안에 파이썬을 박지 않는다(YAML 이 깨진다). 파일로 둔다 —
   이 저장소에 이미 적혀 있던 교훈이다.
"""
import sys
from datetime import datetime, timedelta, timezone

MIN_MIN = 20        # 유튜브가 너무 가까운 예약을 싫어한다 — 넉넉히 띄운다


def stamp(hours, base=None):
    h = float(hours)
    t = (base or datetime.now(timezone.utc)) + timedelta(hours=h)
    least = (base or datetime.now(timezone.utc)) + timedelta(minutes=MIN_MIN)
    if t < least:
        t = least
    return t.replace(second=0, microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    if len(sys.argv) < 2:
        print("몇 시간 뒤인지 적으십시오 (예: 24)", file=sys.stderr)
        return 2
    print(stamp(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
