#!/usr/bin/env python3
"""⭐ **없는 이름을 부르는 곳**이 있는가. 값 0원 · 인터넷 0회.

    python3 tools/name_check.py

⭐⭐⭐ 2026-09-10 — 왜 이 검사가 생겼나.
   `TALK_TAIL = 0.45` 한 줄이 조용히 사라졌다. 위 블록을 갈아끼우다 같이
   날아갔는데, 그 이름을 쓰는 talk_trim() 은 **영상을 실제로 살 때만** 도는
   자리다. 그래서 검사 72개가 전부 초록불이었고, 값(컷마다 706~941원)이
   나가는 순간 NameError 로 죽었을 것이다.

   파이썬은 함수 **안**의 이름을 부를 때까지 확인하지 않는다. 그래서 '한 번도
   안 돌려 본 갈래'의 오타·삭제는 검사를 다 통과한다. 여기서는 **돌리지 않고**
   각 함수가 부르는 전역 이름을 전부 꺼내 실제로 있는지만 본다.

방법
   함수마다 co_names(그 함수가 부르는 이름들)를 꺼내, 모듈 전역·빌트인·
   import 한 것 중에 있는지 본다. 없으면 그 자리는 도는 순간 죽는다.
   ⚠️ 속성 이름(a.b 의 b)도 co_names 에 섞여 들어온다 — 그래서 **점 뒤에
      오는 이름**은 소스에서 찾아 빼낸다. 안 그러면 거짓 빨간불이 쏟아진다.
"""
import ast
import builtins
import importlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

# 볼 파일들 — src/ 에서 **무겁지 않게 불러지는 것**만.
MODS = ["short90", "story90", "talkplan", "ytmeta", "reuse", "cost"]

bad = []


def known_of(src):
    """이 파일 안에서 **어딘가에 묶인** 이름 전부.

    ⚠️ co_names 에는 전역만 오는 게 아니다. 속성 이름(a.b 의 b), 키워드 인자
       이름도 섞인다. 그리고 함수 **안**에서 한 import(`import veo`)나 함수
       안에 정의한 함수(`def refs_of(c)`)도 전역 목록에는 안 뜬다 — 그러나
       도는 데는 아무 문제가 없다. 이런 것을 다 빼야 거짓 빨간불이 안 난다.
       그래도 **어디에서도 안 묶인 이름**(지워진 상수·오타)은 그대로 남는다.
    """
    got = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Attribute):
            got.add(node.attr)                       # a.b 의 b
        elif isinstance(node, ast.keyword) and node.arg:
            got.add(node.arg)                        # f(x=1) 의 x
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            got.add(node.id)                         # 어디서든 대입한 이름
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef)):
            got.add(node.name)                       # 중첩 함수 포함
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:                     # 함수 안 import 포함
                got.add((a.asname or a.name).split(".")[0])
        elif isinstance(node, ast.ExceptHandler) and node.name:
            got.add(node.name)
        elif isinstance(node, ast.arg):
            got.add(node.arg)
        elif isinstance(node, ast.Global):
            got.update(node.names)
    return got


def walk_funcs(obj, seen=None):
    """모듈 안의 함수·중첩 함수를 전부 꺼낸다."""
    import types
    seen = seen if seen is not None else set()
    out = []
    for v in vars(obj).values():
        if isinstance(v, types.FunctionType) and id(v) not in seen:
            seen.add(id(v))
            out.append(v)
            for k in v.__code__.co_consts:
                if isinstance(k, type(v.__code__)):
                    out.append((v, k))
    return out


def names_of(code):
    """이 코드 덩이와 그 안 중첩 함수가 부르는 이름 전부."""
    got = set(code.co_names)
    for k in code.co_consts:
        if hasattr(k, "co_names"):
            got |= names_of(k)
    return got


def main():
    print("⭐ 없는 이름을 부르는 곳이 있는가 (값 0원 · 안 돌려 보고 본다)\n")
    for name in MODS:
        try:
            m = importlib.import_module(name)
        except Exception as e:                               # noqa: BLE001
            print(f"   ❌ {name} 을(를) 못 불러온다 — {e}")
            bad.append(name)
            continue
        src = Path(m.__file__).read_text(encoding="utf-8")
        skip = known_of(src) | set(dir(builtins)) | set(vars(m))
        miss = {}
        import types
        for v in vars(m).values():
            if not isinstance(v, types.FunctionType):
                continue
            if getattr(v, "__module__", None) != name:
                continue                                     # import 해 온 것
            for nm in names_of(v.__code__):
                if nm in skip or nm.startswith("__"):
                    continue
                miss.setdefault(nm, []).append(v.__name__)
        if miss:
            print(f"   ❌ {name}: 없는 이름 {len(miss)}개")
            for nm, where in sorted(miss.items()):
                print(f"        · {nm}  ← {', '.join(sorted(set(where))[:3])} 에서 부른다")
            bad.append(name)
        else:
            print(f"   ✅ {name}: 부르는 이름이 전부 있다")

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 없는 이름: {len(bad)}개 파일 — 그 갈래는 도는 순간 죽는다")
        return 1
    print("✅ 없는 이름 없음 — 안 돌려 본 갈래도 이름은 다 있다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
