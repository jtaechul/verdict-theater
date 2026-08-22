#!/usr/bin/env python3
"""관리자 페이지가 워크플로에 넘기는 **값 이름**이 그 워크플로에 있는가 본다.

    python3 tools/dispatch_input_check.py     인터넷 0회 · 0원 · 1초

왜 이 검사가 있는가 (2026-08-22)
    깃허브는 워크플로가 받겠다고 적어 두지 않은 값을 넘기면 통째로 거절한다
    (422 Unexpected inputs provided). 화면에는 그냥 "실패" 로만 보인다.
    이번에 압축파일 주소(blob)·목소리(voice)·올릴 글(meta) 을 새로 넘기게
    되었으므로, 그 세 칸이 워크플로에 실제로 적혀 있는지 기계가 맞춰 본다.

    ⚠️ 앞선 검사(check_scope.mjs)는 "이 칸에 있는 변수인가" 만 본다.
       여기서는 "저쪽 워크플로가 받아 주는 이름인가" 를 본다 — 다른 사고다.
"""

import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
JS = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
WF = ROOT / ".github" / "workflows"

MARK = "if (url.pathname === '"


def declared(name: str):
    """워크플로가 받겠다고 적어 둔 값 이름들."""
    path = WF / name
    if not path.exists():
        return None
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # PyYAML 은 'on:' 을 True 로 읽는다 (YAML 1.1 에서 on = 참)
    on = doc.get("on") if isinstance(doc.get("on"), dict) else doc.get(True)
    return set((((on or {}).get("workflow_dispatch") or {}).get("inputs") or {}).keys())


def brace(text: str, start: int) -> str:
    """`{` 부터 짝이 맞는 `}` 까지 잘라 온다."""
    depth, i = 0, start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    return text[start:]


def keys_of(block: str):
    """`{ sid, ep, blob: … }` 에서 이름표만 뽑는다 (한 겹만)."""
    out = set()
    inner = block[1:-1] if block.startswith("{") else block
    depth, buf, parts = 0, "", []
    for ch in inner:
        if ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    parts.append(buf)
    for p in parts:
        p = p.strip()
        if not p:
            continue
        m = re.match(r"^([A-Za-z_$][\w$]*)\s*(:|$)", p)
        if m:
            out.add(m.group(1))
    return out


def scan(js, have_of):
    """관리자 페이지 글 + '그 워크플로가 받는 이름들' 을 주면 어긋난 곳을 돌려준다."""
    bad, seen = [], 0
    # 칸(핸들러) 단위로 자른다 — 넓게 훑으면 옆 칸의 글이 섞인다
    at = [m.start() for m in re.finditer(re.escape(MARK), js)]
    for k, p in enumerate(at):
        body = js[p:at[k + 1] if k + 1 < len(at) else len(js)]
        for m in re.finditer(r"actions/workflows/([A-Za-z0-9._-]+\.yml)/dispatches", body):
            wfname = m.group(1)
            have = have_of(wfname)
            if have is None:
                bad.append(f"{wfname}: 그런 워크플로 파일이 없습니다")
                continue
            sent = set()
            # ① 그 자리에 통째로 적은 꼴: inputs: { … }
            for mm in re.finditer(r"\binputs:\s*\{", body):
                sent |= keys_of(brace(body, mm.end() - 1))
            # ② 미리 만들어 둔 꼴: const inputs = { … } / inputs.blob = …
            for mm in re.finditer(r"\b(?:const|let|var)\s+inputs\s*=\s*\{", body):
                sent |= keys_of(brace(body, mm.end() - 1))
            for mm in re.finditer(r"\binputs\.([A-Za-z_$][\w$]*)\s*=", body):
                sent.add(mm.group(1))
            # `inputs: cut ? {…} : {…}` 같은 갈림길도 ① 이 양쪽을 다 잡는다
            for key in sorted(sent):
                seen += 1
                if key not in have:
                    bad.append(
                        f"{wfname} 에 '{key}' 칸이 없는데 관리자 페이지가 그걸 넘깁니다 "
                        f"(깃허브가 422 로 통째로 거절합니다). "
                        f"그 워크플로의 workflow_dispatch.inputs 에 '{key}' 를 넣으십시오"
                    )

    # ③ [실행] 카드가 쓰는 목록(WORKFLOWS)도 같은 사고를 낼 수 있다
    starts = [(m.start(), m.group(1))
              for m in re.finditer(r"\{\s*file:\s*'([^']+\.yml)'", js)]
    for i, (pos, wfname) in enumerate(starts):
        block = js[pos:starts[i + 1][0] if i + 1 < len(starts) else len(js)]
        have = have_of(wfname)
        if have is None:
            bad.append(f"{wfname}: 그런 워크플로 파일이 없습니다")
            continue
        for m in re.finditer(r"k:\s*'([^']+)'", block):
            seen += 1
            if m.group(1) not in have:
                bad.append(f"{wfname} 에 '{m.group(1)}' 칸이 없는데 화면이 그걸 넘깁니다")
    return bad, seen


def selftest():
    """⚠️ 잡지도 못하면서 초록불만 켜는 검사가 제일 위험하다. 먼저 스스로 시험한다."""
    fake = (
        "if (url.pathname === '/api/x') {\n"
        "  const inputs = { sid, ep };\n"
        "  if (cut) inputs.nosuch = cut;\n"
        "  await gh(env, `/repos/x/actions/workflows/fake.yml/dispatches`, {\n"
        "    method: 'POST', body: JSON.stringify({ ref: BRANCH, inputs }) });\n"
        "}\n"
    )
    bad, _ = scan(fake, lambda n: {"sid", "ep"})
    assert any("nosuch" in b for b in bad), "없는 칸을 못 잡는다"
    bad, _ = scan(fake, lambda n: {"sid", "ep", "nosuch"})
    assert not bad, f"멀쩡한 것을 걸었다: {bad}"
    # 그 자리에 통째로 적은 꼴도 잡는가
    fake2 = (
        "if (url.pathname === '/api/y') {\n"
        "  await gh(env, `/repos/x/actions/workflows/fake.yml/dispatches`, {\n"
        "    method: 'POST', body: JSON.stringify({ ref: BRANCH,\n"
        "      inputs: { sid, ep, blob: u } }) });\n"
        "}\n"
    )
    bad, _ = scan(fake2, lambda n: {"sid", "ep"})
    assert any("blob" in b for b in bad), "통째로 적은 꼴을 못 잡는다"
    print("✅ 자기시험: 없는 칸은 잡고 멀쩡한 것은 통과시킨다")


print("⭐ 워크플로에 넘기는 값 이름이 저쪽에 실제로 있는가")
selftest()
bad, seen = scan(JS, declared)
if bad:
    for b in bad:
        print(f"   ❌ {b}")
    print("────────────────────────────────────────────────────")
    print(f"❌ 어긋난 곳 {len(bad)}군데 — 고치고 다시")
    sys.exit(1)
print(f"✅ {seen}개 다 저쪽 워크플로에 있는 이름입니다")
