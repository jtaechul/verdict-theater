#!/usr/bin/env python3
"""⭐ **워크플로 안의 셸 명령을 버튼 누르기 전에 bash 로 미리 읽어 본다.** 0원.

    python3 tools/bash_check.py

왜 이 검사가 있는가 (2026-08-15)
    [3. 영상 만들기]의 안내문 한 줄 끝에 따옴표가 **하나 더** 붙어 있었다.
        echo "... 3,180원).""
    따옴표는 둘씩 짝을 이뤄야 하는데 홀수가 되니 bash 가 '문장이 안 끝났다'
    (unexpected EOF) 며 그 단계 전체를 죽였다. 검사가 걸렸을 때 보여 줄
    안내문이 죽은 것이라, 손님은 **실패 이유조차 못 본 채** 빨간 X 만 봤다.

    YAML 문법 검사는 이미 있었지만 YAML 은 통과였다 — 문제는 YAML 안에 든
    **bash 글**이었고, 그걸 읽어 보는 눈이 없었다. 이제 여기서 읽는다.

어떻게 보나
    워크플로마다 모든 단계의 실행 칸(run:)을 꺼내 `bash -n`(실행하지 않고
    문법만 읽기)에 넣는다. 따옴표 홀수·괄호 안 닫힘·if 짝 안 맞음이 걸린다.
    `${{ ... }}` 는 깃허브가 실행 전에 값으로 바꿔 끼우는 자리라
    bash 가 모른다 — 자리만 지키는 글자로 바꾼 뒤 읽는다.

⚠️ 검사기 자신도 먼저 시험한다 — 일부러 망가뜨린 글을 못 잡으면
   이 검사 전체를 믿을 수 없으므로 그 자리에서 실패한다.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"

# 깃허브가 값을 끼우는 자리. bash 에게는 뜻 없는 글자로 바꿔 보인다.
EXPR = re.compile(r"\$\{\{.*?\}\}")


def bash_reads(text):
    """bash -n 으로 읽어 본다. 문제 없으면 None, 있으면 오류 글."""
    filled = EXPR.sub("GITHUB_VALUE", text)
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
        f.write(filled)
        path = f.name
    try:
        r = subprocess.run(["bash", "-n", path],
                           capture_output=True, text=True, timeout=20)
        if r.returncode != 0:
            return (r.stderr or r.stdout).strip()
        return None
    finally:
        Path(path).unlink(missing_ok=True)


def selftest():
    """일부러 망가뜨린 글을 잡는지 본다 — 못 잡으면 검사기가 고장난 것."""
    broken = 'echo "한 번 돌리면 풀립니다 (6명 전부는 3,180원).""\n'
    if bash_reads(broken) is None:
        print("❌ 자기시험 실패: 따옴표가 홀수인 글을 못 잡는다")
        return False
    fine = 'if [ "${{ job.status }}" = "success" ]; then\n  echo "통과"\nfi\n'
    err = bash_reads(fine)
    if err is not None:
        print(f"❌ 자기시험 실패: 멀쩡한 글을 문제 삼는다 — {err}")
        return False
    heredoc = "python3 - <<'PY'\nprint('한글')\nPY\n"
    if bash_reads(heredoc) is not None:
        print("❌ 자기시험 실패: 파이썬 끼워 넣기(heredoc)를 문제 삼는다")
        return False
    print("✅ 자기시험: 망가진 글은 잡고 멀쩡한 글은 통과시킨다")
    return True


def main():
    try:
        import yaml
    except ImportError:
        print("⚠️ PyYAML 이 없어 **읽지 못했습니다.** '통과' 가 아니라 '안 해 봄' 입니다.")
        return 0

    print("⭐ 워크플로 속 셸 명령을 bash 가 읽을 수 있는가")
    if not selftest():
        return 1

    bad = 0
    total = 0
    for p in sorted(WF.glob("*.yml")):
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        for jname, job in (doc.get("jobs") or {}).items():
            for i, step in enumerate(job.get("steps") or [], 1):
                run = step.get("run")
                if not run:
                    continue
                shell = step.get("shell", "bash")
                if "bash" not in str(shell):
                    continue
                total += 1
                err = bash_reads(run)
                if err:
                    bad += 1
                    name = step.get("name", f"{i}번째 단계")
                    first = err.splitlines()[0] if err else ""
                    print(f"   ❌ {p.name} · {jname} · 「{name}」")
                    print(f"      {first}")
    print(f"   실행 칸 {total}개를 읽었습니다.")
    print("─" * 52)
    if bad:
        print(f"❌ bash 가 못 읽는 실행 칸 {bad}개 — 버튼을 누르면 그 단계에서 죽습니다")
        return 1
    print("✅ 셸 명령 검사: 전부 읽힌다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
