#!/usr/bin/env python3
"""⭐ **깔지도 않은 라이브러리를 부르는 프로그램이 없는가.** 값 0원.

    python3 tools/heavy_import_check.py

⚠️⚠️⚠️ 2026-09-09 — **같은 사고를 두 번 냈다.**

   2026-08-31: tools/fetch_meta90.py 가 글 한 장 만들자고 src/short90.py 를
     불렀다가 죽었다. short90 은 맨 윗줄에서 `from PIL import ...` 를 한다.
     그 교훈을 fetch_meta90.py 머리말에 적어 두었다.
   2026-09-09: 새로 만든 tools/talk_test.py 가 **똑같이** short90 을 불러
     또 죽었다. 대사 컷 하나 사려고 그림 라이브러리를 끌어온 것이다.

   왜 또 났나 — 교훈을 **주석으로만** 남겼고, 검사는 그 파일 하나에만
   걸어 두었다. 새 파일에는 아무 그물도 없었다.

   → 규칙을 파일 이름이 아니라 **짜임**으로 적는다:
       "pillow 를 깔지 않는 워크플로에서 도는 프로그램은,
        PIL 이 필요한 모듈을 (건너 건너라도) 부르면 안 된다."
     워크플로와 import 를 실제로 읽어 스스로 따진다 — 손으로 적은 예외
     목록이 없으므로 새 파일이 생겨도 저절로 걸린다.
"""
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"
# 이 이름들이 없으면 그 자리에서 죽는다 (pip 로 깔아야 하는 것들)
NEED_PIP = {"PIL": "pillow", "yaml": "pyyaml"}

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def code_of(text):
    """주석·설명글을 뺀 진짜 코드만 (설명글에 적힌 import 를 세면 안 된다)."""
    out = "\n".join(re.sub(r"#.*", "", ln) for ln in text.splitlines())
    return re.sub(r'"""[\s\S]*?"""', "", out)


def our_imports(path):
    """이 파일이 부르는 **우리 모듈** 이름들.

    ⚠️ **맨 왼쪽에 붙은 것만** 센다. 함수 안으로 들여쓴 import 는 그 함수를
       부를 때만 불려 오므로 안전하다 — 이 저장소가 일부러 쓰는 방식이다
       (src/upload.py:42 "render.py 는 그림을 그리는 모듈이라 늦게 부른다").
       들여쓴 것까지 세면 멀쩡한 짜임을 빨간불 낸다."""
    code = code_of(Path(path).read_text(encoding="utf-8"))
    names = set(re.findall(r"^import (\w+)", code, re.M))
    names |= set(re.findall(r"^from (\w+) import", code, re.M))
    return {n for n in names
            if (ROOT / "src" / f"{n}.py").exists()
            or (ROOT / "tools" / f"{n}.py").exists()}


def needs(path):
    """이 파일이 직접 요구하는 pip 라이브러리들."""
    code = code_of(Path(path).read_text(encoding="utf-8"))
    got = set()
    for mod, pkg in NEED_PIP.items():
        if re.search(rf"^(import {mod}\b|from {mod}[. ])", code, re.M):
            got.add(pkg)
    return got


def find(name):
    for d in ("src", "tools"):
        f = ROOT / d / f"{name}.py"
        if f.exists():
            return f
    return None


def closure_needs(path, seen=None):
    """건너 건너 부르는 것까지 다 따라가며 필요한 라이브러리를 모은다."""
    seen = seen if seen is not None else set()
    path = Path(path)
    if path in seen:
        return set(), []
    seen.add(path)
    got, why = needs(path), []
    if got:
        why.append(f"{path.name} 가 {'·'.join(sorted(got))} 를 부른다")
    for n in our_imports(path):
        f = find(n)
        if f:
            g2, w2 = closure_needs(f, seen)
            got |= g2
            why += [f"{path.name} → {x}" for x in w2]
    return got, why


def main():
    print("⭐ 깔지도 않은 라이브러리를 부르지 않는가 (값 0원)\n")
    files = sorted(WF.glob("*.yml"))
    ck(f"워크플로를 찾았다 ({len(files)}개)", files)

    checked = 0
    for f in files:
        text = f.read_text(encoding="utf-8")
        try:
            yaml.safe_load(text)
        except Exception:                                    # noqa: BLE001
            continue
        # 이 워크플로가 깔아 두는 것
        # ⚠️⚠️ **진짜 설치 줄만 본다.** 처음에 파일 전체에서 낱말을 찾았더니
        #    selfcheck.yml 52번째 줄 **주석**에 적힌 "pillow" 를 읽고 통과시켰다
        #    (설치를 빼도 초록불이었다). 검사가 코드가 아니라 글을 읽은 것이다 —
        #    이 저장소에서 세 번째 같은 함정이다.
        # ⚠️ 이름은 대소문자를 안 가린다 — PyYAML / pyyaml 로 제각각 적혀 있다.
        blob = "\n".join(re.findall(r"pip install[^\n]*", text))
        for m in re.findall(r"-r\s+([\w./-]*requirements[\w.-]*\.txt)", text):
            f2 = ROOT / m
            if f2.exists():
                blob += "\n" + f2.read_text(encoding="utf-8")
        low = blob.lower()
        has = {pkg for pkg in NEED_PIP.values() if pkg.lower() in low}
        # 이 워크플로가 돌리는 우리 프로그램
        progs = sorted(set(re.findall(r"python3 ((?:src|tools)/[\w.]+\.py)", text)))
        for p in progs:
            pf = ROOT / p
            if not pf.exists():
                continue
            want, why = closure_needs(pf)
            miss = want - has
            checked += 1
            if miss:
                ck(f"{f.name} — {p}", False,
                   f"{'·'.join(sorted(miss))} 를 안 깔았는데 부른다 "
                   f"({' / '.join(why[:2])})")
    ck(f"돌리는 프로그램을 전부 따라가 봤다 ({checked}개)", checked > 0)

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 라이브러리: {len(bad)}군데 — 그 자리에서 죽는다")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 라이브러리: 부르는 것은 전부 깔려 있다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
