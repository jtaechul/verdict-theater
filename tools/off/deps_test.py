#!/usr/bin/env python3
"""버튼이 부르는 코드가 **쓰는 꾸러미를 워크플로가 진짜 깔아 주는지** 잰다. 값 0원.

    python3 tools/deps_test.py

왜 이 검사가 있는가 (2026-08-14)
    시범 1장 만들기를 눌렀는데 그림은 멀쩡히 다 그려졌고(265원 나갔고),
    바로 그 뒤 검사기가 이렇게 넘어졌다:

        ModuleNotFoundError: No module named 'numpy'

    까닭은 단순하다. `build-assets.yml` 의 '도구 준비' 가 `Pillow` 만 깔았는데,
    새로 만든 `src/sheet_gate.py` 와 `src/char_sheet.py` 는 `numpy` 로 픽셀을 센다.
    **돈은 이미 나간 뒤에 넘어졌다** — 가장 나쁜 자리에서 터진 셈이다.

    이건 '조심하자' 로 막을 수 없다. 코드에 import 한 줄을 더할 때마다
    사람이 워크플로 여덟 개를 뒤져 pip 줄을 고칠 리가 없기 때문이다.
    (CLAUDE.md 핵심 규칙: *규칙만 적고 재지 않으면 같은 일이 되풀이된다.*)

어떻게 재는가 (사람 눈이 아니라 코드가 읽는다)
    ① 워크플로 파일마다, 일(job)마다 — `python3 어떤파일.py` 를 전부 찾는다
    ② 그 파일이 `import` 하는 것을 읽고, 우리 저장소 안의 파일이면 **따라 들어간다**
       (assets_gen → char_sheet → numpy 처럼 두세 다리 건너간 것도 잡는다)
    ③ 파이썬에 원래 들어 있는 것(sys, json …)과, `try: import …` 로 감싸
       없어도 되게 만든 것은 뺀다
    ④ 남은 것이 그 일의 `pip install` 줄에 다 적혀 있는지 본다

    빠진 게 있으면 **어느 워크플로의 어느 일에 무엇을 더해야 하는지**까지 찍는다.
"""

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"

# import 이름 → pip 로 까는 이름 (다른 것들만 적는다)
PIP_NAME = {
    "PIL": "Pillow",
    "yaml": "PyYAML",
    "cv2": "opencv-python",
    "bs4": "beautifulsoup4",
}

# 파이썬에 원래 들어 있는 것
STDLIB = set(getattr(sys, "stdlib_module_names", ()))

ok = True
_cache = {}


def bad(m):
    global ok
    print("❌ " + m)
    ok = False


# ── 파일 하나가 무엇을 쓰는지 읽는다 ────────────────────────
class Scan(ast.NodeVisitor):
    """`import` 를 모으되, 세 갈래로 나눈다.

        hard — 파일 첫머리에 있다. 없으면 **부르는 즉시** 죽는다.
        lazy — 함수 안에 있다. 그 갈래로 들어갈 때만 죽는다(더 고약하다 —
               한참 돌다가, 돈이 나간 뒤에 죽을 수 있다. 265원이 딱 그랬다).
        soft — `try:` 로 감쌌다. 없어도 되게 만들어 둔 것이니 안 센다.
    """

    def __init__(self):
        self.hard = set()
        self.lazy = set()
        self.soft = set()
        self._in_try = 0
        self._in_def = 0

    def _add(self, name):
        top = name.split(".")[0]
        if self._in_try:
            self.soft.add(top)
        elif self._in_def:
            self.lazy.add(top)
        else:
            self.hard.add(top)

    def visit_FunctionDef(self, node):
        self._in_def += 1
        self.generic_visit(node)
        self._in_def -= 1

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Import(self, node):
        for a in node.names:
            self._add(a.name)

    def visit_ImportFrom(self, node):
        if node.level == 0 and node.module:
            self._add(node.module)

    def visit_Try(self, node):
        # 잡아채는 것이 ImportError(또는 통째로 Exception/맨 except)면
        # 그 안의 import 는 '없어도 되는 것' 이다.
        forgiving = False
        for h in node.handlers:
            if h.type is None:
                forgiving = True
            else:
                names = []
                t = h.type
                for n in (t.elts if isinstance(t, ast.Tuple) else [t]):
                    if isinstance(n, ast.Name):
                        names.append(n.id)
                if {"ImportError", "ModuleNotFoundError", "Exception",
                    "BaseException"} & set(names):
                    forgiving = True
        if forgiving:
            self._in_try += 1
            for st in node.body:
                self.visit(st)
            self._in_try -= 1
        else:
            for st in node.body:
                self.visit(st)
        for st in node.handlers + node.orelse + node.finalbody:
            self.visit(st)


def local_file(name):
    """우리 저장소 안의 파일인가. 맞으면 그 경로를 준다."""
    for d in ("src", "tools"):
        p = ROOT / d / f"{name}.py"
        if p.exists():
            return p
    return None


def needs(path, seen=None):
    """이 파일(과 이 파일이 부르는 우리 파일들)이 있어야 하는 바깥 꾸러미.

    돌려주는 것은 `{꾸러미: '첫머리' 또는 '갈래'}` 다.
    우리 파일을 따라 들어갈 때, 그 부름이 함수 안이었으면 **그 아래는 전부
    '갈래'** 로 내려간다 (부르지 않으면 안 읽히므로)."""
    path = Path(path)
    key = str(path)
    if key in _cache:
        return dict(_cache[key])
    seen = seen or set()
    if key in seen or not path.exists():
        return {}
    seen = seen | {key}

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as e:
        bad(f"{path.relative_to(ROOT)} 를 읽을 수 없다: {e}")
        return {}

    s = Scan()
    s.visit(tree)

    out = {}

    def put(pkg, level):
        # '첫머리' 가 '갈래' 보다 세다 — 한 번이라도 첫머리면 첫머리다.
        if out.get(pkg) != "첫머리":
            out[pkg] = level

    for level, names in (("첫머리", s.hard), ("갈래", s.lazy)):
        for name in names:
            sub = local_file(name)
            if sub is not None:                   # 우리 파일 → 따라 들어간다
                for pkg, lv in needs(sub, seen).items():
                    put(pkg, "첫머리" if (level == "첫머리" and lv == "첫머리")
                        else "갈래")
            elif name not in STDLIB:
                put(PIP_NAME.get(name, name), level)
    _cache[key] = dict(out)
    return dict(out)


# ── 워크플로에서 '무엇을 깔고 무엇을 부르는지' 뽑는다 ──────────
def run_blocks(job):
    """일(job) 안의 모든 `run:` 글월을 한 줄로 잇는다."""
    out = []
    for st in job.get("steps") or []:
        if isinstance(st, dict) and isinstance(st.get("run"), str):
            out.append(st["run"])
    return "\n".join(out)


PIP_RE = re.compile(r"pip\s+install\s+([^\n|&;]*)")
PY_RE = re.compile(r"python3?\s+((?:src|tools)/[A-Za-z0-9_./-]+\.py)")


def installed(text):
    got = set()
    for m in PIP_RE.finditer(text):
        for w in m.group(1).split():
            if w.startswith("-"):                 # --quiet, -r 같은 것
                continue
            got.add(re.split(r"[=<>!\[]", w)[0])
    return got


def main():
    import yaml

    files = sorted(WF.glob("*.yml")) + sorted(WF.glob("*.yaml"))
    if not files:
        bad("워크플로 파일을 못 찾았다")
        return 1

    print(f"워크플로 {len(files)}개를 본다 — 부르는 파일이 쓰는 꾸러미가 다 깔리는가")
    print("-" * 62)

    total = 0
    for f in files:
        try:
            doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception as e:                    # noqa: BLE001
            bad(f"{f.name} 를 읽을 수 없다: {e}")
            continue

        for jname, job in (doc.get("jobs") or {}).items():
            if not isinstance(job, dict):
                continue
            text = run_blocks(job)
            scripts = sorted({m.group(1) for m in PY_RE.finditer(text)})
            if not scripts:
                continue
            have = installed(text)
            want = {}
            for s in scripts:
                for pkg, lv in needs(ROOT / s).items():
                    if want.get(pkg) != "첫머리":
                        want[pkg] = lv

            # 이름이 대소문자만 다른 경우까지 같게 본다 (pillow vs Pillow)
            have_l = {h.lower() for h in have}
            missing = sorted(w for w in want if w.lower() not in have_l)
            total += 1
            if missing:
                bad(f"{f.name} · {jname}: {', '.join(missing)} 를 안 깐다")
                for w in missing:
                    who = [s for s in scripts if w in needs(ROOT / s)]
                    when = ("부르는 즉시 넘어진다" if want[w] == "첫머리"
                            else "그 갈래로 들어가면 그때 넘어진다 — 돈이 나간 뒤일 수 있다")
                    print(f"     └ {w} 는 {', '.join(who[:3])} 가 쓴다 ({when})")
                print(f"     → '도구 준비' 의 pip install 줄에 "
                      f"{' '.join(missing)} 를 더하십시오.")
            else:
                print(f"✅ {f.name} · {jname}: "
                      f"{', '.join(sorted(want)) or '(바깥 꾸러미 없음)'} — 다 깐다")

    if total == 0:
        bad("파이썬을 부르는 일(job)을 하나도 못 찾았다 — 검사가 헛돌고 있다")

    # ── 이 검사가 스스로 눈이 멀지 않았는지 본다 ──────────────
    # (없는 꾸러미를 일부러 넣어 보고, 못 잡으면 검사기가 고장 난 것이다)
    print()
    probe = needs(ROOT / "src" / "sheet_gate.py")
    if probe.get("numpy") != "갈래":
        bad(f"sheet_gate.py 의 numpy 는 함수 안에 있는데 '{probe.get('numpy')}' 로 읽는다")
    if "numpy" not in probe:
        bad("sheet_gate.py 가 numpy 를 쓰는데 검사가 그걸 못 읽는다 — 검사기 고장")
    else:
        print("✅ 검사기 자체 확인: sheet_gate.py → numpy 를 제대로 읽는다")

    soft = Scan()
    soft.visit(ast.parse((ROOT / "tools" / "sfx_quality.py").read_text("utf-8")))
    if "numpy" not in soft.soft:
        bad("sfx_quality.py 의 numpy 는 없어도 되는 것인데 '꼭 필요' 로 읽는다")
    else:
        print("✅ 검사기 자체 확인: try 로 감싼 것은 '없어도 되는 것' 으로 센다")

    print()
    print("─" * 62)
    print("✅ 꾸러미: 워크플로와 코드가 맞는다" if ok else "❌ 꾸러미: 안 깔리는 것이 있다")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
