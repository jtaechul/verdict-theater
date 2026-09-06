#!/usr/bin/env python3
"""⭐ **다음 공개 시각**을 유튜브가 받는 모양으로 찍어 준다. 값 0원.

    python3 tools/next_slot.py 0     → 2026-09-07T23:00:00Z  (한국 09-07 08:00)
    python3 tools/next_slot.py 1     → 그다음 날 아침 8시
    python3 tools/next_slot.py 2     → 그다음 날 아침 8시

⭐⭐⭐ 2026-09-06 손님: **"한꺼번에 올리니까 1편은 매번 조회수가 0이잖아."**

   실제 숫자를 뽑아 보니 원인은 "한꺼번에" 가 아니라 **1편만 예약 없이 즉시
   공개**되던 것이었다. 워크플로에 이렇게 박혀 있었다 —

       if [ "$I" -eq 0 ]; then AT=""; else AT="--publish-at …"; fi

   그래서 1편은 업로드가 끝나는 그 순간 공개된다. 유튜브가 아직 고화질 변환을
   끝내지 못한 때다. 이때 공개되면 초기 노출 구간에서 저화질로 서빙되고
   쇼츠 피드 진입이 나빠진다.

   ■ 실측 (판결극장 쇼츠 10건 · 2026-09-06)
       즉시 공개 2건 —   349회 ·     0회
       예약 공개 8건 — 1,212회 ~ 2,946회
     같은 사건 같은 화질인데 1편(349)과 2편(2,946)이 **8배** 차이였다.

   ■ 공개 시각도 갈린다 (같은 실측)
       아침 8시 언저리 4건 평균 1,849회
       오후 1시      3건 평균 1,269회
       저녁 7시 반    1건        349회

   → **모든 편을 예약 공개로, 아침 8시(한국)에** 하루씩 띄운다.

⚠️ 유튜브는 **Z 로 끝나는 UTC** 만 받는다. 한국 시각으로 적으면 9시간
   어긋나 엉뚱한 때 공개된다 — 그래서 여기 한 곳에서만 만든다.
⚠️ 너무 가까운 예약은 안 잡는다. 변환이 안 끝난 채 공개되면 애초에 고치려던
   그 고장이 그대로 난다 (LEAD_H).
"""
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
HOUR_KST = 8          # 한국 시각 아침 8시 — 실측으로 가장 좋았다
LEAD_H = 4            # 적어도 이만큼은 뒤여야 한다 (변환이 끝날 시간)


def slot(n, base=None):
    """n 번째 편의 공개 시각 (0부터). 돌려주는 것은 UTC 글자."""
    now = base or datetime.now(timezone.utc)
    k = now.astimezone(KST)
    # 오늘 아침 8시 (한국)
    t = k.replace(hour=HOUR_KST, minute=0, second=0, microsecond=0)
    # 변환이 끝날 시간을 못 벌면 다음 날로 민다
    while t < k + timedelta(hours=LEAD_H):
        t += timedelta(days=1)
    t += timedelta(days=int(n))
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    n = sys.argv[1] if len(sys.argv) > 1 else "0"
    try:
        n = int(float(n))
    except ValueError:
        print("몇 번째 편인지 적으십시오 (0부터)", file=sys.stderr)
        return 2
    print(slot(n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
