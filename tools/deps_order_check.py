#!/usr/bin/env python3
"""자체 점검이 **읽는 준비물을 실제로 깔아 두는가**, 그리고 쓰기 전에 까는가.

    python3 tools/deps_order_check.py             인터넷 0회 · 0원 · 1초
    python3 tools/deps_order_check.py --selftest  검사기가 진짜 잡는지 스스로 시험

왜 이 검사가 있는가 — 같은 사고를 **두 번** 냈다
    2026-08-22 ①  PyYAML 을 맨 아래 칸에서 깔았는데 중간 검사가 그걸 읽어서 죽었다.
    2026-08-22 ②  새 검사를 131번째 줄에 넣었는데 그것이 읽는 pillow 를
                  135번째 줄에서 깔고 있었다.
    두 번 다 **내 컴퓨터에는 이미 깔려 있어** 로컬에서는 "전부 통과" 로 보였고,
    깃허브에서만 빨간불이 났다. 눈으로는 절대 안 보인다.

무엇을 보나
    ① 준비물은 맨 앞 '준비물' 칸 **한 곳에서만** 깐다 (아래에 흩어 두지 않는다)
    ② 자체 점검이 돌리는 검사들이 읽는 바깥 꾸러미가 그 목록에 다 있는가
       (검사가 읽는 src/*.py 가 읽는 것까지 따라 들어간다)
"""

import ast
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows" / "selfcheck.yml"

# 꾸러미 이름과 읽는 이름이 다른 것들
ALIAS = {"PIL": "pillow", "yaml": "pyyaml", "cv2": "opencv-python"}
# 우리 것 (깔 필요 없다)
OURS = {p.stem for p in (ROOT / "src").glob("*.py")} | \
       {p.stem for p in (ROOT / "tools").glob("*.py")}


def third_party(path, seen=None):
    """이 파일이 읽는 **바깥 꾸러미** 이름들 (우리 것은 따라 들어간다)."""
    seen = seen if seen is not None else set()
    path = pathlib.Path(path)
    if not path.exists() or path in seen:
        return set()
    seen.add(path)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    out, ours = set(), set()
    # ⚠️ **맨 바깥(모듈 수준)에서 읽는 것만** 본다.
    #    함수 안에서 읽는 것(지연 로딩)은 그 함수를 안 부르면 없어도 된다.
    #    실제로 numpy 가 그렇다 — 이 컴퓨터에도 없는데 검사가 다 통과한다.
    #    그것까지 걸면 헛경보가 쏟아져 검사를 아무도 안 믿게 된다.
    for node in tree.body:
        names = []
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module.split(".")[0]]
        elif isinstance(node, ast.Try):        # try: import X  (있으면 쓰고 없으면 만다)
            continue
        for n in names:
            if n in sys.stdlib_module_names:
                continue
            if n in OURS:
                ours.add(n)
            else:
                out.add(n)
    for n in ours:                      # 우리 것이 읽는 것까지 따라 들어간다
        for d in ("src", "tools"):
            out |= third_party(ROOT / d / f"{n}.py", seen)
    return out


def scan(steps, resolve=True):
    """어긋난 곳들을 돌려준다."""
    bad = []
    prep_i, installed = None, set()
    for i, st in enumerate(steps):
        name = str(st.get("name") or "")
        run = str(st.get("run") or "")
        installs = re.findall(r"pip\s+install[^\n]*", run)
        if name.strip() == "준비물":          # 정확히 이 이름인 칸만
            prep_i = i
            if not installs:
                bad.append("'준비물' 칸에 pip install 이 없습니다")
            for one in installs:
                for w in one.split():
                    if w in ("pip", "install", "--quiet", "-q", "python3", "-m"):
                        continue
                    installed.add(w.lower())
            continue
        for one in installs:
            bad.append(f"{i + 1}번째 칸 '{name}' 에서 준비물을 깝니다 → {one.strip()}")

    if prep_i is None:
        bad.append("'준비물' 칸이 없습니다")
        return bad

    first_tool = next((i for i, st in enumerate(steps)
                       if re.search(r"^\s*(python3|node|bash)\s+tools/",
                                    str(st.get("run") or ""), re.M)), None)
    if first_tool is not None and prep_i > first_tool:
        bad.append(f"'준비물' 칸({prep_i + 1})이 첫 검사({first_tool + 1})보다 뒤에 있습니다")

    if not resolve:
        return bad

    # ② 돌리는 검사들이 읽는 바깥 꾸러미가 다 깔려 있는가
    need = {}
    for st in steps:
        for line in str(st.get("run") or "").splitlines():
            m = re.match(r"^\s*python3\s+(tools/[\w.]+\.py)", line)
            if not m:
                continue
            for pkg in third_party(ROOT / m.group(1)):
                need.setdefault(ALIAS.get(pkg, pkg).lower(), set()).add(m.group(1))
    for pkg, who in sorted(need.items()):
        if pkg not in installed:
            bad.append(f"'{pkg}' 를 안 깔았는데 {', '.join(sorted(who))} 가 읽습니다")
    return bad


def selftest():
    """⚠️ 잡지도 못하면서 초록불만 켜는 검사가 제일 위험하다."""
    ok_steps = [{"name": "준비물", "run": "python3 -m pip install --quiet PyYAML pillow"},
                {"name": "검사", "run": "python3 tools/x.py"}]
    assert not scan(ok_steps, resolve=False), "멀쩡한 것을 걸었다"
    late = [{"name": "준비물", "run": "python3 -m pip install --quiet PyYAML"},
            {"name": "검사", "run": "python3 -m pip install --quiet pillow\npython3 tools/x.py"}]
    got = scan(late, resolve=False)
    assert any("준비물을 깝니다" in b for b in got), "아래에서 까는 것을 못 잡는다"
    after = [{"name": "검사", "run": "python3 tools/x.py"},
             {"name": "준비물", "run": "python3 -m pip install --quiet PyYAML"}]
    got = scan(after, resolve=False)
    assert any("보다 뒤에 있습니다" in b for b in got), "순서가 뒤바뀐 것을 못 잡는다"
    # ⭐ 가장 중요한 것 — **아예 안 깐 것**을 잡는가.
    #    2026-08-22 에 이것 때문에 깃허브가 빨갛게 됐다:
    #    clip_order_test 가 shorts.py 를 읽고, shorts.py 가 PIL 을 읽는데
    #    준비물에 pillow 가 없었다.
    miss = [{"name": "준비물", "run": "python3 -m pip install --quiet PyYAML"},
            {"name": "검사", "run": "python3 tools/clip_order_test.py"}]
    got = scan(miss)
    assert any("pillow" in b for b in got), f"안 깐 꾸러미를 못 잡는다: {got}"
    full = [{"name": "준비물", "run": "python3 -m pip install --quiet PyYAML pillow"},
            {"name": "검사", "run": "python3 tools/clip_order_test.py"}]
    assert not scan(full), f"멀쩡한 것을 걸었다: {scan(full)}"
    print("   ✅ 자기시험: 늦게 까는 것 · 순서 뒤바뀜 · **안 깐 꾸러미** 다 잡는다")


print("⭐ 준비물을 다 깔았는가 · 쓰는 것보다 먼저 까는가")
selftest()
doc = yaml.safe_load(WF.read_text(encoding="utf-8"))
bad = scan(doc["jobs"]["check"]["steps"])
if bad:
    for b in bad:
        print(f"   ❌ {b}")
    print("────────────────────────────────────────────────────")
    print("❌ 준비물은 맨 앞 '준비물' 칸 한 곳에서만 까십시오")
    print("   (내 컴퓨터에는 깔려 있어 로컬에서는 안 드러납니다)")
    sys.exit(1)
print("   ✅ 준비물은 맨 앞 한 곳에서만 깐다")
print("   ✅ 검사들이 읽는 바깥 꾸러미가 다 깔려 있다")
print("────────────────────────────────────────────────────")
print("✅ 준비물: 성하다")
