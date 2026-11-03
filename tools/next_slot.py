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

⭐⭐⭐ 2026-11-03 손님: "업로드 시간은 정각으로 하니까 다른 것들하고 너무 중복이 많이 돼서 8시 7분, 4분 이런 식으로
   정각, 5분이나 10분 정각이 되지 않도록 세팅하자. 내가 아니면 시간 분을 선택할 수 있게 해줘, 날짜랑."
   → 기본 예약은 **아침 8시 X분** — 분은 0 · 5 · 10 처럼 5로 나눠떨어지지 않는 1~19분 가운데 하나
     (그날 · 그 편마다 달라진다 · 같은 날 같은 분이 겹치지 않는다).
   → `--at "2026-11-05 08:07"` (한국 시각) 을 주면 그 날짜·시각에 (편이 여럿이면 하루씩 뒤 같은 시각).
"""
import re
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
HOUR_KST = 8          # 한국 시각 아침 8시 — 실측으로 가장 좋았다
LEAD_H = 4            # 적어도 이만큼은 뒤여야 한다 (변환이 끝날 시간)
PICK_LEAD_H = 1       # 손님이 직접 고른 시각은 적어도 1시간 뒤 (변환이 끝날 시간 · 4시간 권장)
# 정각 · 5분 단위를 피한 분 — 다른 채널 예약이 몰리는 자리를 비켜 간다
ODD_MINUTES = [m for m in range(1, 20) if m % 5]


def odd_minute(day, n=0):
    """그날(day · date) n 번째 편의 분 — 날마다 · 편마다 다르게, 5로 나눠떨어지지 않게."""
    return ODD_MINUTES[(day.toordinal() * 7 + int(n) * 5) % len(ODD_MINUTES)]


def picked(at, n=0, now=None):
    """손님이 고른 한국 시각("YYYY-MM-DD HH:MM") → n 번째 편 UTC 글자. 틀리면 ValueError."""
    m = re.fullmatch(r"\s*(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})\s*", str(at or ""))
    if not m:
        raise ValueError(f"날짜·시각 꼴이 틀렸다: {at!r} (예: 2026-11-05 08:07)")
    y, mo, d, h, mi = (int(x) for x in m.groups())
    t = datetime(y, mo, d, h, mi, tzinfo=KST) + timedelta(days=int(n))
    now = now or datetime.now(timezone.utc)
    if t < now.astimezone(KST) + timedelta(hours=PICK_LEAD_H):
        raise ValueError(f"고른 시각 {t:%Y-%m-%d %H:%M}(한국)이 너무 가깝거나 지났다 — 적어도 {PICK_LEAD_H}시간 뒤로")
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slot(n, base=None):
    """n 번째 편의 공개 시각 (0부터). 돌려주는 것은 UTC 글자."""
    now = base or datetime.now(timezone.utc)
    k = now.astimezone(KST)
    # 오늘 아침 8시 (한국)
    t = k.replace(hour=HOUR_KST, minute=0, second=0, microsecond=0)
    # 변환이 끝날 시간을 못 벌면 다음 날로 민다 (분은 아래에서 더한다 — 19분 안이라 하루가 바뀌지 않는다)
    while t < k + timedelta(hours=LEAD_H):
        t += timedelta(days=1)
    t += timedelta(days=int(n))
    t = t.replace(minute=odd_minute(t.date(), n))
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    args = sys.argv[1:]
    at = ""
    if "--at" in args:
        i = args.index("--at")
        at = args[i + 1] if i + 1 < len(args) else ""
        args = args[:i] + args[i + 2:]
    n = args[0] if args else "0"
    try:
        n = int(float(n))
    except ValueError:
        print("몇 번째 편인지 적으십시오 (0부터)", file=sys.stderr)
        return 2
    if at.strip():
        try:
            print(picked(at, n))
        except ValueError as e:
            print(f"❌ {e}", file=sys.stderr)
            return 2
        return 0
    print(slot(n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
