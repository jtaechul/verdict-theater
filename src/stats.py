#!/usr/bin/env python3
"""성과 수집 + 판단 기준(KPI) 점검 + 게이트 기준 보정 근거.

    python3 src/stats.py

왜 필요한가 (지침서 10번)
    **이 사업의 최대 실패 원인은 3개월 내 포기다.**
    수익은 3개월 동안 0원이다. 그래서 수익이 아니라 선행지표로 판단한다.

    4주차   노출 클릭률(CTR)      3% 이상
    8주차   평균 시청 지속률      30% 이상  ← 핵심 분기점
    8주차   구독 전환             편당 1명 이상
    12주차  조회수 상위 1편       3,000회 이상
    16주차  수익화 요건 진입 여부

    8주차 시청 지속률이 20% 미만이면 대본 구조를 재검토한다.
    지표가 미달이어도 **대본 프롬프트를 고치는 것이 우선**이다.
    소재나 채널을 바꾸는 건 마지막 수단이다.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from upload import access_token, api  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
EPISODES = ROOT / "state" / "episodes.json"
STATS = ROOT / "state" / "stats.json"
REJECTED = ROOT / "state" / "rejected.json"
QUEUE = ROOT / "state" / "queue.json"

ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"

KPI = [
    (4, "노출 클릭률(CTR)", "ctr", 3.0, "%"),
    (8, "평균 시청 지속률", "retention", 30.0, "%"),
    (8, "편당 구독 전환", "subs_per_video", 1.0, "명"),
    (12, "최고 조회수", "top_views", 3000, "회"),
]


def _load(p, d):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else d


def _save(p, o):
    p.write_text(json.dumps(o, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def video_stats(token, ids):
    """조회수·좋아요·댓글 수. Data API 로 받는다."""
    out = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        res = api("GET", "videos", token,
                  params={"part": "statistics,snippet", "id": ",".join(chunk)})
        for it in res.get("items", []):
            s = it.get("statistics", {})
            out[it["id"]] = {
                "title": it["snippet"]["title"],
                "published_at": it["snippet"]["publishedAt"][:10],
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
                "comments": int(s.get("commentCount", 0)),
            }
    return out


def analytics(token, start, end):
    """시청 지속률·CTR·구독 전환. **별도 권한이 필요하다.**

    STARTGUIDE 3-2 는 `youtube` 권한만 받게 되어 있어서, 여기가 막힐 수 있다.
    막히면 무엇을 어떻게 고쳐야 하는지 알려주고 넘어간다."""
    params = {
        "ids": "channel==MINE",
        "startDate": start, "endDate": end,
        "metrics": ("views,estimatedMinutesWatched,averageViewDuration,"
                    "averageViewPercentage,subscribersGained"),
        "dimensions": "day",
    }
    url = f"{ANALYTICS}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        if e.code in (401, 403):
            print("  ⚠️ 시청 지속률·CTR 은 받지 못했다. 권한이 부족하다.")
            print("     developers.google.com/oauthplayground 에서 갱신 토큰을 다시 받을 때")
            print("     https://www.googleapis.com/auth/yt-analytics.readonly 를 함께 선택하고")
            print("     새 YOUTUBE_REFRESH_TOKEN 으로 교체하면 이 수치가 채워진다.")
        else:
            print(f"  분석 조회 실패 (HTTP {e.code}): {body}")
        return None


def gate_calibration():
    """개선 3회 후에도 미달한 건들을 모아 게이트 기준 보정 근거를 만든다.

    '어떤 소재가 대본으로 안 풀리는가'가 쌓이면 게이트에서 미리 거를 수 있다.
    루프가 상위 단계로 되돌아가는 지점이다."""
    rec = _load(REJECTED, [])
    if not rec:
        return []
    by_type, by_item = {}, {}
    for r in rec:
        by_type.setdefault(r.get("case_type", "미상"), []).append(r)
        for it in r.get("weak_items", []):
            by_item[it] = by_item.get(it, 0) + 1
    lines = [f"개선 실패 누적 {len(rec)}건"]
    for t, rows in sorted(by_type.items(), key=lambda x: -len(x[1])):
        avg_gate = sum(x.get("gate_score") or 0 for x in rows) / len(rows)
        avg_scr = sum(x.get("script_score") or 0 for x in rows) / len(rows)
        lines.append(f"  {t:10s} {len(rows)}건 · 게이트 평균 {avg_gate:.0f}점 "
                     f"→ 대본 평균 {avg_scr:.0f}점")
        if len(rows) >= 3 and avg_gate >= 70:
            lines.append(f"    ⚠️ 게이트를 높게 받고도 대본이 안 나온다. "
                         f"'{t}' 유형은 게이트 기준을 손볼 근거가 된다")
    if by_item:
        worst = sorted(by_item.items(), key=lambda x: -x[1])[:3]
        lines.append("  자주 미달하는 항목: " +
                     ", ".join(f"{k}({v}회)" for k, v in worst))
        lines.append("    → 그 항목을 script_gen.md 에서 더 강하게 지시해야 한다")
    return lines


def main():
    eps = _load(EPISODES, {})
    published = {k: v for k, v in eps.items() if v.get("stage") == "published"}
    if not published:
        print("공개된 회차가 없다. 성과를 볼 것이 없다.")
        print("\n" + "\n".join(gate_calibration() or ["개선 실패 기록도 없다."]))
        return 0

    try:
        token = access_token()
    except RuntimeError as e:
        print(f"❌ {e}")
        return 2

    ids, owner = [], {}
    for ep, v in published.items():
        for vid in [v.get("longform_id")] + (v.get("shorts") or []):
            if vid:
                ids.append(vid)
                owner[vid] = ep
    vs = video_stats(token, ids)

    first = min((v.get("published_at", "") for v in published.values() if v.get("published_at")),
                default=date.today().isoformat())
    weeks = max(1, (date.today() - datetime.strptime(first, "%Y-%m-%d").date()).days // 7)

    print(f"공개 회차 {len(published)}편 · 영상 {len(vs)}개 · 발행 {weeks}주차")
    print()
    print(f"{'회차':7s} {'조회':>7s} {'좋아요':>6s} {'댓글':>5s}  제목")
    print("-" * 74)
    total_views = 0
    for vid, s in sorted(vs.items(), key=lambda x: -x[1]["views"]):
        total_views += s["views"]
        print(f"{owner.get(vid, ''):7s} {s['views']:7,d} {s['likes']:6,d} "
              f"{s['comments']:5,d}  {s['title'][:34]}")

    ana = analytics(token, first, date.today().isoformat())
    metrics = {"top_views": max((s["views"] for s in vs.values()), default=0)}
    if ana and ana.get("rows"):
        cols = [h["name"] for h in ana["columnHeaders"]]
        rows = ana["rows"]
        idx = {c: i for i, c in enumerate(cols)}
        views = sum(r[idx["views"]] for r in rows)
        subs = sum(r[idx["subscribersGained"]] for r in rows)
        pct = [r[idx["averageViewPercentage"]] for r in rows if r[idx["views"]]]
        metrics["retention"] = sum(pct) / len(pct) if pct else 0
        metrics["subs_per_video"] = subs / max(1, len(published))
        metrics["views_total"] = views

    print()
    print("판단 기준 (지침서 10번)")
    print(f"{'시점':6s} {'지표':18s} {'기준':>8s} {'현재':>9s}  판정")
    print("-" * 62)
    for wk, name, key, target, unit in KPI:
        cur = metrics.get(key)
        if cur is None:
            mark, shown = "측정 불가", "-"
        else:
            shown = f"{cur:,.1f}{unit}" if isinstance(cur, float) else f"{cur:,}{unit}"
            if weeks < wk:
                mark = f"{wk}주차에 판정"
            else:
                mark = "충족" if cur >= target else "미달"
        tgt = f"{target:,.0f}{unit}"
        print(f"{wk:>3d}주  {name:18s} {tgt:>8s} {shown:>9s}  {mark}")

    ret = metrics.get("retention")
    if weeks >= 8 and ret is not None:
        print()
        if ret < 20:
            print("⚠️ 8주차 시청 지속률 20% 미만. **대본 구조를 재검토해야 한다.**")
            print("   소재나 채널을 바꾸기 전에 script_gen.md 부터 고친다.")
        elif ret < 30:
            print("△ 기준 미달이지만 붕괴는 아니다. 3초 관문과 중반 유지를 손본다.")
        else:
            print("○ 핵심 분기점 통과. 지금 방향을 유지한다.")

    cal = gate_calibration()
    if cal:
        print()
        print("게이트 보정 근거")
        print("\n".join(cal))

    snap = _load(STATS, [])
    snap.append({"date": date.today().isoformat(), "weeks": weeks,
                 "videos": len(vs), "total_views": total_views, "metrics": metrics})
    _save(STATS, snap)
    print(f"\n기록 저장: state/stats.json ({len(snap)}회차분)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
