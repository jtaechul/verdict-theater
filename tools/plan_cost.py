#!/usr/bin/env python3
"""⭐ 이번에 만들면 **얼마나 · 몇 번** 부르는지 대본에서 셈한다. 값 0원.

    python3 tools/plan_cost.py          → 사람이 읽을 표
    python3 tools/plan_cost.py --env    → 워크플로가 쓸 값 (GITHUB_ENV 꼴)

⚠️⚠️ 2026-09-05 — 이것이 없어서 손님이 [전체 만들기] 를 눌렀는데 아무것도
   안 나왔다. 상한이 **손으로 적은 숫자**였기 때문이다 —
     STILL_CALL_CAP: '24'   # 컷 19 + 재시도 여유
   그런데 대본 규격을 3~5편 · 편당 8~11컷으로 넓히면서(손님 지시) 컷이
   27장이 됐고, 24장을 그린 뒤 상한에 걸려 통째로 멈췄다.
   → **손으로 적은 숫자는 언젠가 반드시 어긋난다.** 대본을 보고 셈한다.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import cost                                                  # noqa: E402
import still as ST                                           # noqa: E402

SPARE_CALLS = 6          # 안전필터 등으로 몇 번 다시 부를 여유
SPARE_KRW = 1.15         # 값은 15% 여유 (모델이 값을 조금씩 다르게 매긴다)


def plan(sid, open_video):
    doc = json.loads((ROOT / "data" / "series" / f"{sid}.json")
                     .read_text(encoding="utf-8"))
    cuts = doc.get("cuts") or []
    # 지문이 같은 컷은 옮겨 쓴다(0원) — 그림은 **서로 다른 지시문 수**만큼 든다
    uniq = len({c.get("still") for c in cuts})
    lines = sum(max(1, len(c.get("turns") or [1])) for c in cuts)
    parts = len(doc.get("parts") or [])

    one_img = cost.image_krw(ST.MODEL, ST.SIZE)
    img_krw = one_img * uniq
    vid_krw = 0.0
    if open_video:
        import short90 as S9                                 # noqa: E402
        vid_krw = cost.video_krw("veo-3.1-lite", S9.OPEN_SEC) * parts

    return {
        "sid": sid, "cuts": len(cuts), "uniq": uniq, "lines": lines,
        "parts": parts,
        "still_cap": uniq + SPARE_CALLS,
        "tts_cap": lines + SPARE_CALLS,
        "veo_cap": parts + 2,
        "img_krw": img_krw, "vid_krw": vid_krw,
        "run_krw": round((img_krw + vid_krw) * SPARE_KRW + 200),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", default=os.environ.get("VT_SID") or "S90")
    ap.add_argument("--open", dest="open_video", default="",
                    help="편 첫 장면 영상을 켰는가 (1/예)")
    ap.add_argument("--env", action="store_true", help="GITHUB_ENV 꼴로 낸다")
    a = ap.parse_args()
    ov = str(a.open_video or os.environ.get("VT_OPEN_VIDEO") or "").strip()
    p = plan((a.sid or "S90").upper(), ov in ("1", "예", "on"))

    if a.env:
        print(f"STILL_CALL_CAP={p['still_cap']}")
        print(f"TTS_CALL_CAP={p['tts_cap']}")
        print(f"VEO_CALL_CAP={p['veo_cap']}")
        print(f"VT_RUN_KRW={p['run_krw']}")
        return 0

    print(f"■ {p['sid']} — {p['parts']}편 · {p['cuts']}컷 "
          f"(서로 다른 그림 {p['uniq']}장 · 말 {p['lines']}줄)")
    print(f"   그림        약 {p['img_krw']:,.0f}원")
    if p["vid_krw"]:
        print(f"   편 첫 장면  약 {p['vid_krw']:,.0f}원")
    print(f"   ─────────────────────────────")
    print(f"   이번 실행 뚜껑 {p['run_krw']:,}원 "
          f"(그림 {p['still_cap']}번 · 소리 {p['tts_cap']}번 · "
          f"영상 {p['veo_cap']}번까지)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
