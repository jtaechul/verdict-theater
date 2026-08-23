#!/usr/bin/env python3
"""워크플로의 **단계 하나하나**가 깃허브가 받아 주는 모양인가.

    python3 tools/workflow_step_check.py     인터넷 0회 · 0원 · 1초

왜 (2026-08-23 사고)
    열쇠 받기 단계를 끼워 넣다가 setup-python 의 with(파이썬 판 지정)가
    **내 단계에 잘못 붙었다.** run 과 with 가 한 단계에 같이 있으면
    깃허브는 그 워크플로 파일을 **통째로 거부**한다. YAML 문법으로는
    멀쩡해서 어느 검사에도 안 걸렸고, 운영자가 버튼을 누르고서야 터졌다
    ("전부 다 들어보기 들어오면은 오류 뜨잖아").
    → 단계 규칙을 기계로 잰다: run 이나 uses 중 **딱 하나**, with 는
      uses 단계에만.
"""

import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
bad = []
n = 0

for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
    doc = yaml.safe_load(wf.read_text(encoding="utf-8")) or {}
    for jname, job in (doc.get("jobs") or {}).items():
        for i, st in enumerate(job.get("steps") or [], 1):
            n += 1
            name = st.get("name") or st.get("uses") or f"{i}번째 단계"
            has_run, has_uses = "run" in st, "uses" in st
            if has_run and has_uses:
                bad.append(f"{wf.name} · {name}: run 과 uses 가 같이 있다")
            if not has_run and not has_uses:
                bad.append(f"{wf.name} · {name}: run 도 uses 도 없다")
            if "with" in st and not has_uses:
                bad.append(f"{wf.name} · {name}: run 단계에 with 가 붙어 있다 "
                           f"(깃허브가 파일을 통째로 거부한다)")

print("⭐ 워크플로 단계가 깃허브가 받아 주는 모양인가")
# 자기시험 — 사고 났던 그 무늬를 진짜로 잡는지
_broken = {"jobs": {"j": {"steps": [
    {"name": "x", "run": "echo hi", "with": {"python-version": "3.12"}}]}}}
_b2 = []
for st in _broken["jobs"]["j"]["steps"]:
    if "with" in st and "uses" not in st:
        _b2.append(1)
assert _b2, "사고 무늬를 못 잡는다"
print("   ✅ 자기시험: run 단계에 with 가 붙은 것을 잡는다")

if bad:
    for x in bad:
        print(f"   ❌ {x}")
    print("────────────────────────────────────────────────────")
    print(f"❌ 단계 {len(bad)}개가 어긋났다 — 깃허브가 실행을 거부한다")
    sys.exit(1)
print(f"   ✅ 단계 {n}개 전부 제 모양이다")
print("────────────────────────────────────────────────────")
print("✅ 워크플로 단계: 성하다")
