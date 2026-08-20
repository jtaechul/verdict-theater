#!/usr/bin/env python3
"""⭐ 실패했을 때 '받아 둔 것을 저장하는' 단계가 진짜 저장하는지 본다. 0원.

    python3 tools/save_step_test.py

왜 (2026-08-20)
    돈을 주고 받은 대본이 **두 번 사라졌다.** 두 번째 원인은 저장 단계의
    이 한 줄이었다:

        git add data/series state/series.json

    `git add` 는 경로 하나가 없으면 **나머지까지 통째로 안 올린다.**
    state/series.json 은 '통과했을 때만' 생기는 파일이라, 반려된 바로 그
    순간에는 언제나 없다. 그래서 살려 두려던 파일이 매번 같이 사라졌다.
    워크플로 로그에는 아무 말도 안 남는다(`2>/dev/null || true`).

    말로 고쳤다고 하지 말고, **없는 파일을 섞어 놓고 실제로 돌려서** 살아남는지
    본다.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAIL = []


def ck(label, cond, extra=""):
    print(("   ✅ " if cond else "   ❌ ") + label + (f"  ({extra})" if extra else ""))
    if not cond:
        FAIL.append(label)


def sh(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)


def staged_after(add_lines):
    """반려된 상황(= state/series.json 이 없는 상황)을 그대로 만들어 돌려 본다."""
    with tempfile.TemporaryDirectory() as d:
        sh("git init -q && git config user.email a@b && git config user.name a", d)
        (Path(d) / "data" / "series").mkdir(parents=True)
        (Path(d) / "data" / "series" / "S001.broken.json").write_text("{}")
        # state/series.json 은 일부러 만들지 않는다 — 반려 때는 없는 파일이다
        sh(add_lines, d)
        out = sh("git diff --cached --name-only", d).stdout
        return [l for l in out.splitlines() if l.strip()]


print("⭐ 실패한 대본 살리기 단계 시험\n")

print("① 옛 방식(경로를 한 줄에 몰아서)은 정말 아무것도 못 살렸는가")
old = staged_after("git add data/series state/series.json 2>/dev/null || true")
ck("옛 방식은 받아 둔 대본을 잃는다 (이게 실제로 난 사고다)", old == [], f"올라간 것 {old}")

print("\n② 지금 워크플로에 적힌 그대로 돌리면 살아남는가")
yml = (ROOT / ".github" / "workflows" / "series.yml").read_text(encoding="utf-8")
adds = re.findall(r"^\s*(git add .*)$", yml, re.M)
ck("워크플로에 git add 줄이 있다", bool(adds), f"{len(adds)}줄")
now = staged_after(" ; ".join(a.strip() for a in adds))
ck("반려된 대본이 실제로 올라간다", "data/series/S001.broken.json" in now, f"올라간 것 {now}")

print("\n③ 저장 단계가 실패해도 반드시 돌게 돼 있는가")
save = yml.split("저장소에 올리기")[-1] if "저장소에 올리기" in yml else ""
ck("저장 단계에 `if: always()` 가 붙어 있다", "if: always()" in save)

print("\n" + "─" * 52)
print(f"❌ 살리기 단계: {len(FAIL)}가지 실패" if FAIL else "✅ 살리기 단계: 전부 통과")
sys.exit(1 if FAIL else 0)
