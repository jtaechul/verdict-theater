#!/usr/bin/env python3
"""관리자 페이지의 선택지가 워크플로의 선택지와 **한 글자도 안 틀리는지** 본다.

    python3 tools/admin_choice_check.py     인터넷 0회 · 0원 · 1초

왜 이 검사가 있는가 (2026-08-12)
    관리자 페이지 [그림·소리 만들기] 안에 '배경 전부' 라는 선택지가 있었는데,
    워크플로에 있는 이름은 '배경 전부 (AI 로 그림 · 값 나감)' 였다.
    깃허브는 고르는 칸(choice)의 값이 **목록에 있는 것과 정확히 같아야** 받아준다.
    그래서 손님이 그 버튼을 눌러도 깃허브가 거절했다 — 화면에는 그냥 실패로 보인다.

    이런 어긋남은 눈으로는 절대 못 잡는다(글자가 길고 괄호까지 붙는다).
    여기서 기계가 맞춰 본다. 어긋나면 올리는 순간 빨간 X 가 뜬다.
"""

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
JS = ROOT / "admin" / "worker.js"
WF = ROOT / ".github" / "workflows"

src = JS.read_text(encoding="utf-8")

# 관리자 페이지에서 { file: 'xxx.yml' … } 덩어리마다 고르는 칸을 뽑는다.
# 덩어리는 다음 `{ file:` 이 나오기 전까지다.
starts = [(m.start(), m.group(1)) for m in re.finditer(r"\{\s*file:\s*'([^']+\.yml)'", src)]
bad = 0
seen = 0

for i, (pos, wfname) in enumerate(starts):
    end = starts[i + 1][0] if i + 1 < len(starts) else len(src)
    block = src[pos:end]

    path = WF / wfname
    if not path.exists():
        print(f"❌ {wfname}: 관리자 페이지가 가리키는 워크플로 파일이 없다")
        bad += 1
        continue

    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # PyYAML 은 'on:' 을 True 로 읽는다 (YAML 1.1 에서 on = 참). 둘 다 본다.
    on = doc.get("on") if isinstance(doc.get("on"), dict) else doc.get(True)
    wfin = ((on or {}).get("workflow_dispatch") or {}).get("inputs") or {}

    # 관리자 쪽: k: '…' 다음에 오는 opts: [ … ] 를 그 칸의 선택지로 본다
    for m in re.finditer(r"k:\s*'([^']+)'", block):
        key = m.group(1)
        rest = block[m.end():]
        nxt = re.search(r"k:\s*'", rest)
        scope = rest[:nxt.start()] if nxt else rest
        om = re.search(r"opts:\s*\[", scope)
        if not om:
            continue                       # 고르는 칸이 아니다 (글자 입력 칸)
        depth, j = 1, om.end()
        while j < len(scope) and depth:
            depth += (scope[j] == "[") - (scope[j] == "]")
            j += 1
        chosen = re.findall(r"v:\s*'((?:[^'\\]|\\.)*)'", scope[om.end():j])
        chosen = [c.replace("\\'", "'") for c in chosen]
        if not chosen:
            continue

        spec = wfin.get(key)
        if spec is None:
            print(f"❌ {wfname} · '{key}': 워크플로에 그런 칸이 없다")
            bad += 1
            continue
        allowed = [str(o) for o in (spec.get("options") or [])]
        if not allowed:
            # 워크플로가 **글자 입력 칸**이면 아무 값이나 받는다. 관리자 페이지가
            # 그 위에 목록을 씌워 손님이 오타를 못 내게 한 것뿐이라 문제가 아니다.
            print(f"·  {wfname} · '{key}': 워크플로는 글자 입력 칸 — 무엇을 보내도 받는다")
            continue

        seen += 1
        miss = [c for c in chosen if c not in allowed]
        if miss:
            bad += 1
            print(f"❌ {wfname} · '{key}': 워크플로에 없는 선택지 — 눌러도 거절당한다")
            for c in miss:
                near = [a for a in allowed if a.startswith(c[:6])]
                print(f"     관리자: {c!r}")
                for a in near or allowed:
                    print(f"     워크플로: {a!r}")
        else:
            print(f"✅ {wfname} · '{key}' 선택지 {len(chosen)}개 전부 일치")

print()
if bad:
    print(f"❌ 관리자 선택지: {bad}군데 어긋남 — 그 버튼은 눌러도 실패한다")
else:
    print(f"✅ 관리자 선택지: {seen}개 칸 전부 워크플로와 일치")
sys.exit(1 if bad else 0)
