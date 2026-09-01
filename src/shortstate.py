#!/usr/bin/env python3
"""사건 하나 ↔ 편 여럿 — **상태를 적어 두는 곳 한 군데**.

    state/shorts.json

⭐⭐⭐ 2026-09-01 손님: "앞으로 영상을 계속 만들어나가고 계속 올려야 되는데
   이런 식으로 관리자 페이지를 구성하면 그 한 편을 제작하고 올리고 난 다음엔
   다시 또 관리자 페이지 체계를 바꿔야 될 걸로 보여져. 지속 가능하지 않거든."

   맞다. 그전까지는 화면도 상태도 **S90 한 사건에 못이 박혀** 있었다
   (state/series.json 의 "S90" → "uploaded" → "0" 한 칸).
   사건이 둘이 되는 순간 화면과 코드를 또 뜯어야 했다.

   → 여기 한 파일에 **사건 목록**과 **편 목록**을 담는다. 사건이 백 개가 돼도
     화면은 이 파일만 읽고 그린다. 편 수도 고정하지 않는다(2편이든 4편이든).

모양

    { "S90": {
        "sid": "S90", "title": "…", "label": "32억 상속 사건",
        "case_id": "230761", "cuts": 24,
        "parts": {
          "1": { "no": 1, "title": "…", "card": ["…","…"],
                 "sec": 44.2, "made_at": "2026-09-01T12:00:00Z",
                 "uploaded": { "video_id": "…", "privacy": "public",
                               "at": "…", "publish_at": null } },
          "2": { … } } } }

⚠️ 두 곳에서 따로 적지 않는다. 만들 때(src/short90.py)도 올릴 때(src/upload.py)도
   여기를 거쳐 적는다. 두 곳에서 각자 적으면 언젠가 갈라지고, 갈라지면 화면이
   거짓말을 한다 — 손님은 화면밖에 못 보신다.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ⚠️⚠️ 2026-09-01 — 예행연습(short90_dryrun)이 **진짜 상태 파일에 값을 적었다.**
#    가짜 소리로 만든 길이가 화면에 "만들어짐 50초" 로 떠 버린다 — 손님은
#    화면밖에 못 보시니 만들지도 않은 것을 만든 줄 아신다.
#    → 시험은 VT_SHORTS_STATE 로 딴 자리를 가리킨다.
FILE = Path(os.environ.get("VT_SHORTS_STATE")
            or (ROOT / "state" / "shorts.json"))


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load():
    if not FILE.exists():
        return {}
    try:
        d = json.loads(FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except json.JSONDecodeError:
        # ⚠️ 여기서 죽으면 화면이 통째로 안 뜬다. 깨진 파일은 없는 셈 친다.
        return {}


def save(d):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n",
                    encoding="utf-8")
    return FILE


def row(d, sid):
    return d.setdefault(sid, {"sid": sid, "parts": {}})


def from_doc(doc):
    """대본(<SID>.json)에 맞춰 사건·편 칸을 만들어 둔다. 이미 있는 값은 안 지운다.

    ⚠️ 올린 기록(uploaded)은 **절대 건드리지 않는다.** 대본을 다시 지었다고
       올린 사실이 사라지면, 화면이 '안 올림' 으로 보여 같은 영상을 두 번 올린다.
    """
    d = load()
    sid = doc.get("sid") or "S90"
    r = row(d, sid)
    r["title"] = doc.get("title") or sid
    r["label"] = doc.get("series_label") or r["title"]
    r["case_id"] = doc.get("case_id") or r.get("case_id", "")
    r["cuts"] = len(doc.get("cuts") or [])
    r["scripted_at"] = r.get("scripted_at") or now()
    keep = r.get("parts") or {}
    parts = {}
    for p in doc.get("parts") or []:
        k = str(p["no"])
        was = keep.get(k) or {}
        parts[k] = {**was, "no": int(p["no"]),
                    "title": p.get("yt_title") or "",
                    "card": list(p.get("card") or []),
                    "cuts": list(p.get("cuts") or [])}
    r["parts"] = parts
    save(d)
    return r


def mark_made(sid, no, sec):
    d = load()
    p = row(d, sid).setdefault("parts", {}).setdefault(str(no), {"no": int(no)})
    p["sec"] = round(float(sec), 1)
    p["made_at"] = now()
    save(d)
    return p


def mark_uploaded(sid, no, video_id, privacy, publish_at=None):
    d = load()
    p = row(d, sid).setdefault("parts", {}).setdefault(str(no), {"no": int(no)})
    p["uploaded"] = {"video_id": video_id, "privacy": privacy,
                     "at": now(), "publish_at": publish_at or None}
    save(d)
    return p


def uploaded(sid, no):
    """이미 올렸으면 그 기록. 안 올렸으면 None. (두 번 올리는 것을 막는 데 쓴다)"""
    p = (load().get(sid) or {}).get("parts", {}).get(str(no)) or {}
    return p.get("uploaded")


def main():
    d = load()
    if not d:
        print("아직 만든 사건이 없습니다.")
        return 0
    for sid, r in sorted(d.items()):
        ps = r.get("parts") or {}
        up = sum(1 for p in ps.values() if p.get("uploaded"))
        print(f"■ {sid} {r.get('label') or r.get('title','')} — "
              f"{len(ps)}편 · 올림 {up}편")
        for k in sorted(ps, key=lambda x: int(x)):
            p = ps[k]
            u = p.get("uploaded") or {}
            state = (f"올림 ({u.get('privacy')})" if u else
                     ("만들어짐" if p.get("sec") else "아직"))
            sec = f"{p['sec']:.0f}초" if p.get("sec") else "—"
            print(f"   {k}편 {sec:>6} · {state:<14} {p.get('title','')[:40]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
