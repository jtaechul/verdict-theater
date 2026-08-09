#!/usr/bin/env python3
"""컷에 **효과음을 자동으로 깔아 준다.** 값 0원.

    python3 tools/add_sfx.py data/scripts/EP001.json
    python3 tools/add_sfx.py data/scripts/EP001.json --check   # 몇 개 붙는지만 보기

왜 (2026-08-09 손님: "효과음을 좀 다채롭게 놔봐. 너무 지금 효과음이 없어.")
    실측: EP001 본편 115컷 중 효과음이 있는 컷은 **18컷(15%)** 뿐이었다.
    나머지 97컷은 방 소리(앰비언스)만 깔려 소리가 밋밋했다.
    대본을 다시 쓰면 값이 드니, **이미 쓴 대본에 코드가 깔아 준다.**

어떻게 고르나 (짐작이 아니라 규칙)
    1. 대사에 든 낱말이 첫째다 — "전화" 가 나오면 전화벨, "도장" 이면 도장 소리.
       말과 소리가 어긋나면 안 하느니만 못하다.
    2. 낱말이 없으면 배경으로 고른다 — 법원 복도면 발소리, 사무실이면 서류.
    3. **너무 자주 깔지 않는다.** 컷마다 소리가 나면 시끄럽고 싸구려가 된다.
       기본은 세 컷에 하나꼴(MIN_GAP), 목표 35~45%.
    4. 같은 소리를 연달아 쓰지 않는다(REPEAT_GAP).
    5. 대본이 이미 정해 둔 효과음은 **건드리지 않는다.**
    6. 판결 장면의 의사봉처럼 '그 자리에만 어울리는' 소리는 낱말로만 깔린다.

몇 번을 돌려도 결과가 같다(같은 대본이면 같은 배치).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SFX_DIR = ROOT / "assets" / "sfx"

# ── 낱말 → 효과음 (첫째 규칙) ──────────────────────────────
#    말과 소리가 맞아떨어질 때만 쓴다.
BY_WORD = [
    (("전화", "통화", "휴대폰", "연락이 왔"), "phone"),
    (("도장", "인감", "날인", "찍었"), "stamp"),
    (("의사봉", "선고", "주문", "판결한다", "판결합니다"), "gavel"),
    (("서류", "각서", "소장", "등기", "계약서", "봉투", "종이", "서명"), "paper"),
    (("문을", "문이", "현관", "들어섰", "나갔", "나섰"), "door"),
    (("눈물", "울었", "울음", "흐느", "젖은"), "tear"),
    (("심장", "가슴이 쿵", "숨이 막", "떨렸"), "heartbeat"),
    (("병원", "중환자", "산소", "링거", "심전도"), "monitor"),
    (("시계", "새벽", "몇 시간", "기다렸", "밤새"), "clock"),
    (("걸어", "복도", "발걸음", "들어왔", "다가"), "footsteps"),
]

# ── 배경 → 효과음 (둘째 규칙) ──────────────────────────────
#    그 자리에 있으면 자연스러운 소리만. 억지로 넣지 않는다.
BY_BG = {
    "court_hall": ["footsteps", "door"],
    "court_exterior": ["footsteps"],
    "court_room": ["paper", "footsteps"],
    "office_lawyer": ["paper", "stamp"],
    "office_registry": ["stamp", "paper"],
    "office_bank": ["stamp", "paper"],
    "home_living": ["clock"],
    "home_kitchen": ["clock"],
    "home_closet": ["paper"],
    "daily_cafe": ["clock"],
    "medical": ["monitor"],
    "funeral": ["clock"],
}

MIN_GAP = 3        # 효과음 사이에 최소 이만큼 컷을 띄운다 (시끄러워지지 않게)
REPEAT_GAP = 6     # 같은 소리를 다시 쓰려면 이만큼 떨어져야 한다
TARGET = 0.45      # 이 비율을 넘지 않는다 (컷의 45%)


def have(name):
    return (SFX_DIR / f"{name}.mp3").exists()


def pick_by_word(text):
    for words, name in BY_WORD:
        if any(w in text for w in words) and have(name):
            return name
    return None


def pick_by_bg(bg, used_recent):
    fam = (bg or "").rsplit("_", 1)[0] if "_" in (bg or "") else (bg or "")
    for key in (bg, fam):
        for name in BY_BG.get(key or "", []):
            if have(name) and name not in used_recent:
                return name
    return None


def add_sfx(doc, check=False):
    cuts = [c for a in doc.get("acts", []) for c in a.get("cuts", [])]
    n = len(cuts)
    if not n:
        return 0, 0
    before = sum(1 for c in cuts if c.get("sfx"))
    limit = int(n * TARGET)

    last_at = -99          # 마지막으로 효과음을 깐 컷 번호
    last_name = {}         # 소리별 마지막 자리
    added = 0
    for i, c in enumerate(cuts):
        if c.get("sfx"):                       # 대본이 정한 것은 그대로 둔다
            last_at = i
            last_name[str(c["sfx"]).replace("sfx_", "")] = i
            continue
        if before + added >= limit:
            break
        if i - last_at < MIN_GAP:
            continue
        text = (c.get("text") or "")
        recent = {k for k, at in last_name.items() if i - at < REPEAT_GAP}
        name = pick_by_word(text)
        if name and name in recent:
            name = None
        if not name:
            name = pick_by_bg(c.get("bg"), recent)
        if not name:
            continue
        if not check:
            c["sfx"] = f"sfx_{name}"
        last_at = i
        last_name[name] = i
        added += 1
    return before, added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--check", action="store_true", help="붙이지 않고 개수만 본다")
    a = ap.parse_args()

    p = Path(a.script)
    doc = json.loads(p.read_text(encoding="utf-8"))
    cuts = sum(len(x.get("cuts") or []) for x in doc.get("acts", []))
    before, added = add_sfx(doc, check=a.check)
    now = before + added
    print(f"효과음: {before}컷 → {now}컷 / 전체 {cuts}컷"
          f" ({now * 100 // max(1, cuts)}%)  · 새로 깔린 것 {added}컷")
    if added and not a.check:
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  {p.name} 에 적었습니다.")
    elif not added:
        print("  더 깔 자리가 없습니다 (이미 넉넉하거나 어울리는 소리가 없음).")

    # 어떤 소리가 몇 번 쓰였는지 — 한 가지만 반복되고 있지 않은지 눈으로 본다
    import collections
    got = collections.Counter(
        str(c.get("sfx") or "").replace("sfx_", "")
        for x in doc.get("acts", []) for c in (x.get("cuts") or []) if c.get("sfx"))
    if got:
        print("  쓰인 소리: " + " · ".join(f"{k} {v}번" for k, v in got.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
