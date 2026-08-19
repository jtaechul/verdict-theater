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
        body = scope[om.end():j]
        # ⭐ 2026-08-18 — 여기가 `{ v: '...' }` 꼴만 읽고 있었다. 그래서 글자만
        #    적은 선택지( opts: ['둘다', '소재 심사만', …] )는 **검사에서 통째로
        #    빠졌다.** 눌러도 거절당하는 그 사고를 막으려고 만든 검사인데,
        #    정작 가장 흔한 형태를 안 보고 있었던 것이다. 둘 다 읽는다.
        chosen = re.findall(r"v:\s*'((?:[^'\\]|\\.)*)'", body)
        plain = re.sub(r"\{[^{}]*\}", "", body)          # {v:…,t:…} 짝은 위에서 이미 읽었다
        chosen += re.findall(r"'((?:[^'\\]|\\.)*)'", plain)
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

# ── 꼭 보여야 하는 버튼이 접힌 칸에 묻히지 않았는가 ──────────
# ── [다음에 할 일] 큰 버튼이 보내는 값도 목록에 있는가 ──────────
# ⚠️ 2026-08-16 — 영상 만들기의 회차 칸이 고르는 칸(choice)이 되면서,
#    큰 버튼이 보내던 빈 값('')이 목록에 없어 **깃허브가 거절할 뻔했다.**
#    위 검사는 실행 카드의 선택지만 봤지, 큰 버튼(NEXT_RUN)이 보내는 값은
#    안 봤다. 같은 규칙(정확히 같아야 받는다)이므로 여기서도 맞춰 본다.
print()
print("── [다음에 할 일] 큰 버튼이 보내는 값 ──")
nm = re.search(r"const NEXT_RUN = \{(.*?)\n\};", src, re.S)
if not nm:
    bad += 1
    print("❌ NEXT_RUN 을 못 찾았다 — 큰 버튼 검사를 못 한다")
else:
    for em in re.finditer(
            r"file:\s*'([^']+\.yml)'[^{]*inputs:\s*\{([^}]*)\}", nm.group(1)):
        wfname, body = em.group(1), em.group(2)
        path = WF / wfname
        if not path.exists():
            bad += 1
            print(f"❌ 큰 버튼이 없는 워크플로를 가리킨다: {wfname}")
            continue
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        on = doc.get("on") if isinstance(doc.get("on"), dict) else doc.get(True)
        wfin = ((on or {}).get("workflow_dispatch") or {}).get("inputs") or {}
        for km in re.finditer(r"(\w+):\s*'((?:[^'\\]|\\.)*)'", body):
            key, val = km.group(1), km.group(2).replace("\\'", "'")
            spec = wfin.get(key)
            if spec is None:
                bad += 1
                print(f"❌ {wfname} · 큰 버튼이 보내는 '{key}' 칸이 워크플로에 없다")
                continue
            allowed = [str(o) for o in (spec.get("options") or [])]
            if allowed and val not in allowed:
                bad += 1
                print(f"❌ {wfname} · '{key}': 큰 버튼이 목록에 없는 값을 보낸다"
                      f" — 눌러도 거절당한다\n     보내는 값: {val!r}")
            else:
                print(f"✅ {wfname} · '{key}' = {val!r}")

# ⚠️ 2026-08-12 — 손님: "관리자 페이지 안에 그림 소리 만들기가 없잖아."
#    버튼은 **있었다.** 다만 fold('가끔 쓰는 것 …') 안에 들어 있어서
#    한 번 더 눌러야 보였다. 등장인물 그림이 없으면 영상이 아예 안 나오는데
#    그 버튼이 '가끔 쓰는 것' 에 있었던 것이다.
#    "있다" 와 "보인다" 는 다르다 — 여기서 그것을 지킨다.
# ⭐ 2026-08-18 대개편 — 영상을 구글(옴니 플래시)이 만들면서 '등장인물 그림
#    만들기'(build-assets)와 옛 '영상 만들기'(produce)가 없어졌다.
#    새 흐름의 버튼(오늘 한 편 · 완성 · 롱폼 묶기)이 붙으면 여기에 다시 넣는다.
MUST_SHOW = {
    "series.yml": "시리즈 대본 만들기",
    "script.yml": "대본 만들기",
    "collect.yml": "재판 기록 모으기",
}
print()
print("── 꼭 보여야 하는 버튼이 접혀 있지 않은가 ──")
# fold(제목, wfList([...])) 안에 든 것과, 그냥 wfList([...]) 로 놓인 것을 가른다
folded, shown = set(), set()
for m in re.finditer(r"wfList\(\[([^\]]*)\]\)", src):
    files = re.findall(r"'([^']+\.yml)'", m.group(1))
    # 이 wfList 앞 120자 안에 fold( 가 있고 닫히지 않았으면 접힌 것으로 본다
    before = src[max(0, m.start() - 160):m.start()]
    inside_fold = "fold(" in before and before.rfind("fold(") > before.rfind(");")
    (folded if inside_fold else shown).update(files)
for f, label in MUST_SHOW.items():
    if f in shown:
        print(f"✅ {label} — 바로 보인다")
    elif f in folded:
        bad += 1
        print(f"❌ {label}({f}) 가 접힌 칸 안에 있다 — 손님이 못 찾는다")
    else:
        bad += 1
        print(f"❌ {label}({f}) 가 화면에 아예 없다")

print()
if bad:
    print(f"❌ 관리자 페이지: {bad}군데 문제 — 눌러도 거절당하거나, 있어도 안 보인다")
else:
    print(f"✅ 관리자 페이지: 고르는 칸 {seen}개가 워크플로와 일치하고, "
          "꼭 필요한 버튼은 다 보인다")
sys.exit(1 if bad else 0)
