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


# ⭐⭐⭐ 2026-09-19 — **"없으면 죽는 줄".** S93 이 세 번 연속 실패한 까닭.
#    `ls build/s90/talk/*.mp4 2>/dev/null | wc -l | xargs …`
#    맞는 파일이 하나도 없으면 ls 는 **2번**으로 끝난다. `2>/dev/null` 은
#    글만 숨길 뿐 끝값은 그대로고, 깃허브가 켜 두는 `set -e` 와 줄 맨 앞의
#    `set -o pipefail` 이 그 2번을 받아 **단계 전체를 죽인다.**
#    더 나쁜 것은, 세 자리 모두 바로 아래·다음 줄에서 "없으면 괜찮다" 를
#    다루고 있었다는 점이다 — 그 줄까지 가지도 못했다.
#
#    ⚠️ 글자만 봐서는 못 잡는다(어떤 ls 는 멀쩡하다). **빈 폴더에서 진짜로
#       돌려 본다** — 없을 때 죽는지가 곧 답이다.
#    ⚠️ 워크플로 줄을 아무거나 돌리면 위험하다. 그래서 **파일을 세거나 고르는
#       뻔한 명령만** 들어 있는 줄로 한정한다(아래 ONLY).
#    같은 덫이 `grep` 에도 있다 — 걸러 낸 것이 하나도 없으면 1번으로 끝난다.
#    (script.yml 세 자리가 그랬다. 셋 다 바로 아래에서 "없으면 괜찮다" 를
#     다루는데 거기까지 못 갔다 — 2026-08-11 에 손님이 같은 버튼을 되풀이해
#     누르시게 만든 그 빨간 X 다.)
#
#    ⚠️ 재는 자리를 **"폴더는 있고 파일만 없다"** 로 맞춘다. 그 줄까지 왔다는
#       것은 앞 단계가 폴더를 만들어 뒀다는 뜻이다. 폴더까지 없는 것으로 재면
#       멀쩡한 find 를 잡는다(실제로 shorts.yml·video.yml 넷을 잘못 잡았다) —
#       헛막는 검사는 멀쩡한 일을 막는다.
LISTY = re.compile(r"\b(?:ls|find)\b[^|;&]*[*?]")
# 그 줄이 뒤지는 폴더 — 재기 전에 **빈 채로 만들어 둔다**
FINDDIR = re.compile(r"\bfind\s+([\w./-]+)")
ONLY = {"ls", "find", "wc", "xargs", "echo", "sort", "tail", "head", "grep",
        "sed", "basename", "cut", "tr", "awk", "true", "cat", "printf"}
WORD = re.compile(r"[A-Za-z_][\w.-]*")


def listy_lines(run):
    """그 실행 칸에서 **파일을 찾아 세는 줄**만 골라 온다 (줄 이음 합침)."""
    txt = EXPR.sub("GITHUB_VALUE", run).replace("\\\n", " ")
    out = []
    for line in txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or not LISTY.search(line):
            continue
        # ⚠️ `EP=$(ls … | …)` 처럼 **값에 담는 꼴**이 더 흔하다. 담는 것도
        #    끝값이 그대로 넘어가 set -e 에 걸린다 — 껍데기를 벗기고 본다.
        m = re.match(r"^\w+=\$\((.*)\)\s*$", line)
        if m:
            line = m.group(1)
        # 첫 낱말들(명령 자리)이 전부 뻔한 것인지 본다
        cmds = [WORD.match(x.strip().lstrip("$({ ")).group(0)
                for x in re.split(r"[|;]|&&|\|\|", line)
                if WORD.match(x.strip().lstrip("$({ "))]
        if cmds and all(c in ONLY for c in cmds):
            out.append(line)
    return out


def dies_when_empty(line, mkdirs=()):
    """빈 폴더에서 돌려 본다 — 죽으면 그 줄이 단계를 죽인다.

    ⚠️ 같은 실행 칸 위쪽의 `mkdir -p` 는 **먼저 그대로 해 준다.** 안 그러면
       폴더가 아예 없는 것을 "파일이 없다" 로 착각해 멀쩡한 줄을 잡는다
       (실제로 shorts.yml 의 find 를 잘못 잡았다 — 검사가 헛막으면
       멀쩡한 일을 막는다).
    """
    d = tempfile.mkdtemp()
    dirs = list(mkdirs) + FINDDIR.findall(line)
    pre = "".join(f"mkdir -p {x}\n" for x in dirs)
    r = subprocess.run(["bash", "-c", f"set -e -o pipefail\n{pre}{line}"],
                       capture_output=True, text=True, timeout=20, cwd=d)
    return r.returncode != 0


MKDIR = re.compile(r"^mkdir\s+-p\s+(.+)$")


def mkdirs_of(run):
    """그 실행 칸이 미리 만드는 폴더들 (그대로 해 주고 나서 재야 한다)."""
    out = []
    for line in EXPR.sub("GITHUB_VALUE", run).splitlines():
        m = MKDIR.match(line.strip())
        if m and "$" not in m.group(1):
            out += m.group(1).split()
    return out


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
    # ⭐ "없으면 죽는 줄" 을 잡는지도 자기시험한다
    if not dies_when_empty("ls nope/*.mp4 2>/dev/null | wc -l"):
        print("❌ 자기시험 실패: 없을 때 죽는 줄을 못 잡는다")
        return False
    if dies_when_empty("echo \"$(find . -name '*.mp4' 2>/dev/null | wc -l)개\""):
        print("❌ 자기시험 실패: 멀쩡한 줄을 죽는다고 한다")
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
    looked = [0]
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
                name = step.get("name", f"{i}번째 단계")
                err = bash_reads(run)
                if err:
                    bad += 1
                    first = err.splitlines()[0] if err else ""
                    print(f"   ❌ {p.name} · {jname} · 「{name}」")
                    print(f"      {first}")
                # ② 파일이 하나도 없을 때 그 줄이 단계를 죽이지 않는가
                pre = mkdirs_of(run)
                for line in listy_lines(run):
                    looked[0] += 1
                    if dies_when_empty(line, pre):
                        bad += 1
                        print(f"   ❌ {p.name} · {jname} · 「{name}」")
                        print(f"      파일이 하나도 없으면 이 줄이 단계를 죽인다:")
                        print(f"      {line[:96]}")
    print(f"   실행 칸 {total}개를 읽었습니다 "
          f"(그중 파일을 찾아 세는 줄 {looked[0]}개는 빈 폴더에서 돌려 봤습니다).")
    print("─" * 52)
    if bad:
        print(f"❌ 버튼을 누르면 죽을 자리 {bad}군데")
        return 1
    print("✅ 셸 명령 검사: 전부 읽히고 · 파일이 없어도 안 죽는다")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# 2026-08-17: 저장소 공개 전환 뒤 자동 실행이 살아 있는지 확인한 탐침 커밋 (동작 변화 없음)
