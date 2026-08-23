#!/usr/bin/env python3
"""클로드(Anthropic) API 로 가는 길이 **정말로 다 막혔는가**.

    python3 tools/no_claude_test.py             인터넷 0회 · 0원 · 1초
    python3 tools/no_claude_test.py --selftest  검사기가 진짜 잡는지 스스로 시험

왜 이 검사가 있는가
    2026-08-23 운영자: "클로드 꺼. 모두 제미나이 API 가 저렴하니까 제미나이로 진행해."

    그전에도 같은 뜻을 말한 적이 있었는데 **지켜지지 않았다.** 8월 18일 대본 작업
    로그에 "CLAUDE_API_KEY 확인됨 — 대본은 Claude 가 쓴다 / 만드는 곳: claude" 가
    그대로 찍혀 있었다. 눈으로 훑어서는 못 잡는다. 길이 여섯 군데였고, 그중
    하나는 **제미나이가 실패하면 말없이 클로드로 넘어가는** 길이었다.

    그래서 사람 눈 대신 기계가 매번 본다.

무엇을 보나 (두 겹을 따로따로 검사한다 — 한 겹이 풀려도 잡힌다)
    ① 워크플로가 CLAUDE_API_KEY 를 러너에 넘기지 않는가   ← 바깥 자물쇠
    ② 코드가 클로드를 절대 돌려주지 않는가                ← 안쪽 자물쇠
    ③ 관리자 페이지가 클로드를 고르게 하거나 보내지 않는가
    ④ '조용히 클로드로 되돌아가는' 길이 남아 있지 않은가
"""

import os
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

KEYS = ("CLAUDE_API_KEY", "ANTHROPIC_API_KEY")
fails = []


def bad(msg):
    fails.append(msg)
    print(f"  ❌ {msg}")


def ok(msg):
    print(f"  ✅ {msg}")


def wf_texts():
    return [(w.name, w.read_text(encoding="utf-8"))
            for w in sorted((ROOT / ".github" / "workflows").glob("*.yml"))]


# ── ① 바깥 자물쇠 — 워크플로가 열쇠를 넘기지 않는다 ────────────────────
def check_workflows(items=None):
    items = items if items is not None else wf_texts()
    print("① 워크플로가 클로드 열쇠를 러너에 넘기지 않는가")
    leaks = []
    for name, text in items:
        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for k in KEYS:
                # 러너에 넘기는 모양은 'NAME: ${{ secrets.NAME }}' 이다
                if re.search(rf"\b{k}\s*:\s*\$\{{\{{", line):
                    leaks.append(f"{name}:{n}  {line.strip()}")
    if leaks:
        for l in leaks:
            bad(f"클로드 열쇠를 넘기는 줄이 남아 있다 — {l}")
    else:
        ok("어느 워크플로도 클로드 열쇠를 넘기지 않는다 (금고에 있어도 코드가 못 본다)")

    print("② 워크플로 고르는 칸에 클로드가 없는가")
    picks = []
    for name, text in items:
        for n, line in enumerate(text.splitlines(), 1):
            t = line.strip()
            if t.startswith("- ") and "claude" in t.lower():
                picks.append(f"{name}:{n}  {t}")
    if picks:
        for p in picks:
            bad(f"버튼에서 클로드를 고를 수 있다 — {p}")
    else:
        ok("어느 버튼에서도 클로드를 고를 수 없다")


# ── ③ 안쪽 자물쇠 — 코드가 클로드를 안 돌려준다 ────────────────────────
def check_code():
    print("③ 열쇠를 일부러 꽂아 놓아도 코드가 클로드를 안 고르는가")
    import claude

    if claude.CLAUDE_OFF is not True:
        bad("src/claude.py 의 CLAUDE_OFF 가 True 가 아니다")
        return

    # 있지도 않은 가짜 열쇠를 **양쪽 다** 꽂아 둔다. 예전 코드라면 여기서
    # 곧장 클로드로 갔다. 인터넷은 한 번도 안 탄다 (객체만 만들고 끝).
    saved = {k: os.environ.get(k) for k in KEYS + ("GEMINI_API_KEY",)}
    try:
        for k in KEYS:
            os.environ[k] = "sk-ant-가짜-열쇠-검사용"
        os.environ["GEMINI_API_KEY"] = "가짜-제미나이-열쇠-검사용"

        for name in ("writer", "grader"):
            fn = getattr(claude, name)
            for prefer in (None, "", "gemini"):
                _, who = fn(max_calls=1, prefer=prefer)
                if who != "gemini":
                    bad(f"{name}(prefer={prefer!r}) 가 {who} 를 골랐다")
                    return
            ok(f"{name}() 는 클로드 열쇠가 있어도 언제나 제미나이를 고른다")

            # 대놓고 claude 라고 하면 **조용히 넘어가지 않고 멈춰야** 한다
            try:
                fn(max_calls=1, prefer="claude")
            except claude.ClaudeError:
                ok(f"{name}(prefer='claude') 는 조용히 넘어가지 않고 멈춘다")
            else:
                bad(f"{name}(prefer='claude') 가 그대로 통과했다")

        # 제미나이 열쇠가 없으면 클로드로 새지 않고 그냥 멈춰야 한다
        del os.environ["GEMINI_API_KEY"]
        try:
            claude.grader(max_calls=1)
        except Exception as e:
            if "claude" in type(e).__name__.lower() and "GEMINI" not in str(e):
                bad(f"제미나이 열쇠가 없을 때 클로드 쪽으로 샜다: {e}")
            else:
                ok("제미나이 열쇠가 없으면 클로드로 새지 않고 그 자리에서 멈춘다")
        else:
            bad("제미나이 열쇠가 없는데도 무언가를 돌려줬다")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    print("④ '조용히 클로드로 되돌아가는' 길이 남아 있지 않은가")
    src = (ROOT / "src" / "claude.py").read_text(encoding="utf-8")
    body = src[src.index("def writer("):]
    if re.search(r"return\s+Claude\(", body):
        bad("writer/grader 안에 아직 Claude 를 돌려주는 줄이 있다")
    else:
        ok("writer/grader 어디에도 클로드를 돌려주는 줄이 없다")

    others = []
    for py in sorted((ROOT / "src").glob("*.py")):
        if py.name == "claude.py":
            continue
        for n, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if re.search(r"\bClaude\s*\(", line) or '"claude"' in line or "'claude'" in line:
                others.append(f"{py.name}:{n}  {line.strip()}")
    if others:
        for o in others:
            bad(f"클로드를 직접 부르거나 지정하는 줄이 남아 있다 — {o}")
    else:
        ok("src/ 의 다른 파일은 클로드를 부르지도, 지정하지도 않는다")


# ── ⑤ 관리자 페이지 ────────────────────────────────────────────────
def check_admin(js=None):
    print("⑤ 관리자 페이지가 클로드를 보내거나 고르게 하지 않는가")
    js = js if js is not None else (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
    hits = [f"{n}: {l.strip()}"
            for n, l in enumerate(js.splitlines(), 1)
            if "claude" in l.lower() and not l.lstrip().startswith("//")]
    if hits:
        for h in hits:
            bad(f"관리자 페이지에 클로드가 남아 있다 — {h}")
    else:
        ok("관리자 페이지 어디에도 클로드가 없다 (보내지도, 고르게 하지도 않는다)")


def selftest():
    """검사기가 진짜로 잡는지, 가짜 나쁜 자료를 먹여 확인한다 (진짜 파일은 안 건드린다)."""
    print("=" * 62)
    print("스스로 시험 — 일부러 망가뜨려 놓고 잡히는지 본다")
    print("=" * 62)
    import claude

    cases = []

    # ① 워크플로가 클로드 열쇠를 다시 넘기게 만든 경우
    cases.append(("워크플로가 열쇠를 넘기는 경우", lambda: check_workflows(
        [("가짜.yml", "    env:\n      CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}\n")])))

    # ② 버튼에서 다시 클로드를 고를 수 있게 된 경우
    cases.append(("버튼에 클로드가 되살아난 경우", lambda: check_workflows(
        [("가짜.yml", "        options:\n          - 'Gemini'\n          - 'Claude'\n")])))

    # ③ 코드가 다시 클로드를 돌려주는 경우
    def broken_code():
        saved = claude.writer
        claude.writer = lambda max_calls=24, prefer=None: (object(), "claude")
        try:
            check_code()
        finally:
            claude.writer = saved
    cases.append(("코드가 클로드를 돌려주는 경우", broken_code))

    # ④ 관리자 페이지에 클로드가 되살아난 경우
    cases.append(("관리자 페이지에 클로드가 되살아난 경우", lambda: check_admin(
        "inputs: { mode: '둘다', writer: '자동 (Claude 우선)' }")))

    missed = 0
    for label, run in cases:
        before = len(fails)
        run()
        if len(fails) > before:
            print(f"  ✅ 잡아냈다 — {label}")
            del fails[before:]
        else:
            print(f"  ❌ 못 잡았다 — {label}")
            missed += 1
        print()
    if missed:
        print(f"❌ 검사기가 {missed}가지를 못 잡는다. 검사기부터 고쳐야 한다.")
        return 1
    print("✅ 네 가지 되살아남을 전부 잡아낸다.")
    return 0


def main():
    if "--selftest" in sys.argv:
        return selftest()
    print("=" * 62)
    print("클로드로 가는 길이 다 막혔는가 (값 0원 · 인터넷 0회)")
    print("=" * 62)
    check_workflows()
    check_code()
    check_admin()
    print("-" * 62)
    if fails:
        print(f"❌ {len(fails)}가지가 걸렸다 — 클로드로 샐 수 있다")
        return 1
    print("✅ 클로드로 가는 길이 전부 막혀 있다. 글·심사·채점 모두 제미나이로만 간다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
