#!/usr/bin/env python3
"""모델을 부르는 **모든 자리**가 규격에 맞는지 코드를 읽어 확인한다. 비용 0원.

    python3 tools/callsite_check.py

왜 필요한가 — 2026-08-11 에 두 번 연달아 실패한 원인
    `effort`(생각 깊이) 를 여섯 자리에 넣었는데, 정작 값을 **받는 쪽**에
    그 이름을 안 만들어 줬다. 파이썬은 실행해 보기 전까지 이걸 모른다.
    그래서 GitHub 에서 첫 호출을 거는 순간에야 죽었다.

        NameError: name 'effort' is not defined

    돌려 보지 않고도 알 수 있는 실수였다. 이 검사가 그것을 한다 —
    코드를 **읽어서** 부르는 자리와 받는 자리를 맞춰 본다.
    인터넷도 열쇠도 필요 없고, 1초면 끝난다.

무엇을 보는가
    src/ 안에서 `무엇인가.json(...)` 으로 모델을 부르는 자리를 전부 찾아
      1. 넘기는 이름이 받는 쪽에 다 있는가 (오타·없는 이름)
      2. 자리 수(위치 인자)가 넘치지 않는가
      3. Claude 와 Gemini 가 **같은 이름을 받는가** (한쪽만 고치면 다른 쪽이 죽는다)
    를 확인한다.
"""

import ast
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import claude                                        # noqa: E402
import llm as llm_mod                                # noqa: E402

fails = []

# 모델을 담고 있을 법한 이름들. 이 이름 뒤에 .json( 이 오면 모델 호출로 본다.
LLM_NAMES = {"llm", "g", "alt", "grader", "writer", "client", "model", "ai"}


def sig_of(fn):
    p = inspect.signature(fn).parameters
    names = set(p) - {"self"}
    # 위치로 넘길 수 있는 최대 개수 (self 제외)
    pos = sum(1 for v in p.values()
              if v.kind in (v.POSITIONAL_ONLY, v.POSITIONAL_OR_KEYWORD)) - 1
    return names, pos


C_NAMES, C_POS = sig_of(claude.Claude.json)
G_NAMES, G_POS = sig_of(llm_mod.Gemini.json)

print("받는 쪽이 아는 이름")
print(f"  Claude : {', '.join(sorted(C_NAMES))}")
print(f"  Gemini : {', '.join(sorted(G_NAMES))}")
print()

# ── 0. 두 곳이 같은 이름을 받는가 ─────────────────────────
if C_NAMES != G_NAMES:
    only_c = sorted(C_NAMES - G_NAMES)
    only_g = sorted(G_NAMES - C_NAMES)
    fails.append(
        "Claude 와 Gemini 가 받는 이름이 다르다. "
        f"Claude 에만: {only_c or '없음'} · Gemini 에만: {only_g or '없음'}\n"
        "     → 한쪽으로 돌리면 그대로 죽는다. 두 곳을 같이 고쳐야 한다.")
else:
    print("✅ Claude 와 Gemini 가 똑같은 이름을 받는다 (어느 쪽으로 돌려도 안전)")

# ── 1. 부르는 자리를 전부 훑는다 ──────────────────────────
OK = C_NAMES & G_NAMES          # 양쪽 다 아는 이름만 안전하다
checked = 0

for path in sorted((ROOT / "src").glob("*.py")):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        fails.append(f"{path.name} 를 읽을 수 없다: {e}")
        continue

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr == "json"):
            continue
        base = f.value
        if not (isinstance(base, ast.Name) and base.id in LLM_NAMES):
            continue          # json.dumps 같은 것은 건너뛴다

        checked += 1
        where = f"{path.name}:{node.lineno}  {base.id}.json(...)"

        # 이름으로 넘긴 것
        for kw in node.keywords:
            if kw.arg is None:          # **something — 확인할 수 없다
                continue
            if kw.arg not in OK:
                if kw.arg in C_NAMES:
                    fails.append(f"{where}\n     '{kw.arg}' 는 Claude 만 안다. "
                                 "Gemini 로 돌리면 죽는다.")
                elif kw.arg in G_NAMES:
                    fails.append(f"{where}\n     '{kw.arg}' 는 Gemini 만 안다. "
                                 "Claude 로 돌리면 죽는다.")
                else:
                    fails.append(f"{where}\n     '{kw.arg}' 라는 이름을 받는 쪽이 "
                                 f"모른다. 쓸 수 있는 이름: {', '.join(sorted(OK))}")

        # 자리로 넘긴 것
        n_pos = len([a for a in node.args if not isinstance(a, ast.Starred)])
        if n_pos > min(C_POS, G_POS):
            fails.append(f"{where}\n     자리로 {n_pos}개를 넘겼는데 "
                         f"받는 쪽은 {min(C_POS, G_POS)}개까지다.")

print(f"✅ 모델 부르는 자리 {checked}곳을 훑었다")

# ── 2. 안쪽에서 서로 부르는 자리도 본다 (json → _call) ────
inner, inner_pos = sig_of(claude.Claude._call)
src = (ROOT / "src" / "claude.py").read_text(encoding="utf-8")
tree = ast.parse(src)
found_inner = 0
for node in ast.walk(tree):
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_call"):
        found_inner += 1
        n_pos = len([a for a in node.args if not isinstance(a, ast.Starred)])
        if n_pos > inner_pos:
            fails.append(
                f"claude.py:{node.lineno}  _call 에 자리로 {n_pos}개를 넘겼는데 "
                f"받는 쪽은 {inner_pos}개까지다.\n"
                "     ← 2026-08-11 에 실행을 두 번 죽인 바로 그 자리다.")
        for kw in node.keywords:
            if kw.arg and kw.arg not in inner:
                fails.append(f"claude.py:{node.lineno}  _call 이 '{kw.arg}' 를 모른다.")
print(f"✅ 안쪽 _call 부르는 자리 {found_inner}곳을 훑었다")

# ── 3. _call 안에서 쓰는 이름이 실제로 있는가 ─────────────
#     `if effort:` 처럼 **받지도 않은 이름을 쓰는** 것을 잡는다. 이것이 진짜 원인이었다.
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name in ("_call", "json", "_warmup"):
        have = {a.arg for a in node.args.args} | {a.arg for a in node.args.kwonlyargs}
        assigned = {t.id for n2 in ast.walk(node)
                    for t in ([n2.targets[0]] if isinstance(n2, ast.Assign)
                              and isinstance(n2.targets[0], ast.Name) else [])}
        assigned |= {n2.target.id for n2 in ast.walk(node)
                     if isinstance(n2, (ast.For, ast.AugAssign))
                     and isinstance(getattr(n2, "target", None), ast.Name)}
        assigned |= {n2.name for n2 in ast.walk(node)
                     if isinstance(n2, ast.ExceptHandler) and n2.name}
        assigned |= {a.asname or a.name.split(".")[0] for n2 in ast.walk(node)
                     if isinstance(n2, (ast.Import, ast.ImportFrom)) for a in n2.names}
        assigned |= {c.id for n2 in ast.walk(node)
                     if isinstance(n2, ast.comprehension)
                     for c in ([n2.target] if isinstance(n2.target, ast.Name) else [])}
        # 이 함수 안에서 '읽기만' 하는 이름
        for n2 in ast.walk(node):
            if isinstance(n2, ast.Name) and isinstance(n2.ctx, ast.Load):
                nm = n2.id
                if nm in have or nm in assigned:
                    continue
                if nm in dir(claude) or nm in dir(__builtins__) or nm in globals():
                    continue
                if nm.isupper() or nm.startswith("_"):
                    continue          # 파일 맨 위의 상수·도우미
                fails.append(
                    f"claude.py:{n2.lineno}  {node.name}() 안에서 '{nm}' 을 쓰는데 "
                    "받지도, 만들지도 않았다.\n"
                    "     ← 실행하는 순간 NameError 로 죽는다.")

print()
if fails:
    print(f"❌ {len(fails)}곳이 어긋난다:")
    for f in fails:
        print(f"   - {f}")
    sys.exit(1)
print("✅ 모델을 부르는 모든 자리가 규격에 맞는다. (돈 0원)")
