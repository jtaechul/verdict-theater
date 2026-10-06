#!/usr/bin/env python3
"""⭐ 설명 드라마 대본 손질 — 작업 칸에서 **직접 지은** 대본을 제작 쪽이 아는 꼴로 맞추고 검사한다 (0원)

    python3 tools/explainer_story.py pick           다음에 지을 판례 (대기열 · 갈래 섞기 · 아직 안 쓴 것)
    python3 tools/explainer_story.py sid 190939     그 판례의 사건 번호 (이미 지은 게 있으면 그 번호)
    python3 tools/explainer_story.py shape S95      꼴 맞추기 + 대본 검사 → data/series/S95.story.json

⭐⭐⭐ 2026-10-02 손님: "제미나이 시키지 말고 네가 직접 만들고 네가 직접 검수해" ·
   "앞으로 우리가 제작하는 영상에서도 동일한 방식으로 제작이 될수 있게끔".
   설명 드라마 대본은 AI 대본 짓기(story90 main · 워크플로)를 거치지 않고 작업 칸에서 짓는다.
   그때 손으로 하던 일(컷 번호 · 길이 어림 · parts/people · 목소리 꼴)을 여기 한 곳에 둔다.
   짓는 법·본보기: .claude/skills/verdict-explainer/SKILL.md · 쇼츠 data/series/S94.story.json · 긴 영상 S95.story.json

shape 가 하는 일 (여러 번 돌려도 같다)
    · style="explainer" · all_video=true · format="drama" 를 박는다
    · 컷 번호를 1부터 다시 매기고, 컷마다 길이 어림(sec)을 적는다
    · 맨 위 yt_title · card 를 한 편짜리 parts 로 옮긴다 (story90.shape_drama)
    · 인물 목소리를 나이·성별·원어민·톤 꼴로 맞추고(fix_voices) people 을 만든다
    · 대본 검사(story90.check — 설명 드라마 규칙 · 그림 맞물림)를 돌려 걸린 곳을 보인다
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import story90 as ST                                          # noqa: E402

SERIES = ROOT / "data" / "series"


def shape(doc):
    """작업 칸에서 지은 대본 → 제작 쪽 꼴 (0원 · 같은 것을 다시 넣어도 같다)."""
    doc = dict(doc)
    doc["all_video"] = True
    doc["style"] = ST.EXPLAINER
    cuts = []
    for i, c in enumerate(doc.get("cuts") or [], 1):
        c = dict(c)
        c["n"] = i
        c.setdefault("scene", "")
        c.setdefault("who", [])
        c.setdefault("say", [doc.get("narr") or ""])
        # ⭐ 컷 길이 어림은 그 대본의 말 빠르기로 (긴 영상 1.15배 · 쇼츠 1.28배)
        c["sec"] = round(ST.char_sec(ST.speed_of(doc)) * ST.chars(c) + 0.6, 1)
        cuts.append(c)
    doc["cuts"] = cuts
    return ST.shape_drama(doc)


def main():
    if sys.argv[1:2] == ["pick"]:
        # 대기열에서 다음 판례 — 게이트 통과 · 아직 안 쓴 것 · 갈래 섞기(바로 앞과 다른 갈래 · 상속 30%)
        row = ST.pick_case()
        print(f"■ 판례 {row['case_id']} · {row.get('topic', '')}/{row.get('case_type', '')} · "
              f"{row.get('법원명', '')} {row.get('선고일자', '')}")
        print(f"   {row.get('one_line', '')}")
        print(f"   판결문: data/cases/{row['case_id']}.json · 사건 번호: "
              f"{ST.sid_for(row['case_id']) or ST.next_sid()}")
        return 0
    if len(sys.argv) < 3 or sys.argv[1] not in ("sid", "shape"):
        print(__doc__)
        return 2
    if sys.argv[1] == "sid":
        print(ST.sid_for(sys.argv[2]) or ST.next_sid())      # 처음 짓는 판례면 다음 번호
        return 0
    sid = sys.argv[2].upper()
    f = SERIES / f"{sid}.story.json"
    if not f.exists():
        print(f"❌ {f.relative_to(ROOT)} 이 없다 — 대본을 먼저 짓는다 (본보기 S94.story.json)")
        return 2
    doc = shape(json.loads(f.read_text(encoding="utf-8")))
    f.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = ST.check(doc)
    secs = ST.part_sec(doc["cuts"], doc)
    talk = sum(1 for c in doc["cuts"] if c["turns"][0][0] != "나레이션")
    figs = sum(1 for c in doc["cuts"] if c.get("fig"))
    print(f"■ {sid} — {len(doc['cuts'])}컷 (대사 {talk} · 그림 {figs}) · 잣대 약 {secs:.0f}초 "
          f"→ {f.relative_to(ROOT)}")
    if bad:
        print(f"❌ 대본 검사 {len(bad)}군데 — 고치고 다시 shape")
        for b in bad:
            print(f"   · {b}")
        return 1
    print("✅ 대본 검사 통과 — 손님께 대본부터 보이고(0원), 좋다고 하시면 "
          f"python3 tools/build_short90.py {sid} → drama60 {sid} check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
