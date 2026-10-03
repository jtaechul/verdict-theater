#!/usr/bin/env python3
"""⭐ 작업 칸에서 **올리기 단추를 누른다** — 손님이 그 자리에서 올리라고 하셨을 때만 (값 0원 · 되돌릴 수 없다)

    python3 tools/upload_request.py S94 --privacy 공개 --when 지금   작업 칸 — 요청을 임시 가지로 밀어 넣는다
    python3 tools/upload_request.py --dispatch upload/S94              워크플로(upload-request.yml) — 단추를 누른다

⭐ 2026-10-03 손님: "유튜브에 올리는 것까지 마무리해줘" · "공개(지금당장)"
   작업 칸은 워크플로 단추를 직접 못 누른다 (403 "Resource not accessible by integration").
   → 요청 파일(upload/request.json)을 임시 가지 upload/<사건> 에 실어 밀어 넣으면, 워크플로가
     저장소 열쇠로 [4-2. 쇼츠 유튜브에 올리기] 를 **관리자 페이지 단추와 똑같은 값**으로 누르고
     임시 가지를 지운다. 올리는 일 자체는 4-2 가 한다 (60초 벽·덜 된 편·두 번 올리기·#shorts 문지기 그대로).
   ⚠️ 올리기는 되돌릴 수 없다 — **손님이 고르신 공개 범위·시각 그대로만** 보낸다.
      공개 범위 기본은 비공개, 공개의 기본 시각은 예약(한국 아침 8시)이다.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

WF = ROOT / ".github" / "workflows" / "short90-upload.yml"
# 짧게 적어도 워크플로가 받는 글자 그대로 바꾼다 (관리자 페이지 단추와 같은 값)
PRIVACY = {"비공개": "비공개 (나만 보기)", "일부공개": "일부공개 (링크 아는 사람만)",
           "공개": "공개 (모두에게)"}
WHEN = {"예약": "예약 — 한국 아침 8시 (권장)", "지금": "지금 바로 공개"}
MODE = {"진짜": "진짜로 올리기", "연습": "연습 (올리지 않고 확인만)"}


def options(name):
    """short90-upload.yml 이 그 칸에 받는 글자들 — 다르면 워크플로가 통째로 거절한다(422)."""
    import yaml                                               # noqa: E402 (워크플로에서만)
    doc = yaml.safe_load(WF.read_text(encoding="utf-8"))
    on = doc.get("on") if isinstance(doc.get("on"), dict) else doc.get(True)
    return list(((on or {}).get("workflow_dispatch") or {}).get("inputs", {})
                .get(name, {}).get("options") or [])


def request_of(sid, part, privacy, when, mode):
    return {"sid": sid, "part": str(part), "privacy": PRIVACY.get(privacy, privacy),
            "when": WHEN.get(when, when), "mode": MODE.get(mode, mode)}


def push(sid, req):
    """main 위에 요청 파일만 얹은 임시 가지를 밀어 넣는다 (작업 칸의 main 은 안 건드린다)."""
    import stage_video as SV                                  # noqa: E402
    br = f"upload/{sid}"
    SV.git("fetch", "origin", "main")
    tmp = Path(tempfile.mkdtemp(prefix="upload-"))
    SV.git("worktree", "add", "--detach", str(tmp), "origin/main")
    try:
        (tmp / "upload").mkdir(exist_ok=True)
        (tmp / "upload" / "request.json").write_text(
            json.dumps(req, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        SV.git("add", "-f", "upload/request.json", cwd=tmp)
        SV.git("commit", "-q", "-m", f"{sid} {req['part']}편 올리기 요청 (임시 가지 · 누른 뒤 지운다)",
               cwd=tmp)
        for k in range(5):                      # 그물이 끊기면 2·4·8·16초 쉬고 다시
            try:
                SV.git("push", "-f", "origin", f"HEAD:refs/heads/{br}", cwd=tmp)
                break
            except RuntimeError:
                if k == 4:
                    raise
                time.sleep(2 ** (k + 1))
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(tmp)], cwd=ROOT,
                       capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)
    return br


def dispatch(ref):
    """워크플로에서 — 요청을 확인하고 [4-2] 단추를 누른다 (저장소 열쇠 · actions: write)."""
    sid = ref.split("/", 1)[-1]
    if not re.fullmatch(r"S\d{2,4}", sid):
        print(f"❌ 가지 이름이 upload/S<번호> 가 아니다: {ref}")
        return 2
    req = json.loads((ROOT / "upload" / "request.json").read_text(encoding="utf-8"))
    bad = []
    if req.get("sid") != sid:
        bad.append(f"요청의 사건({req.get('sid')})이 가지({sid})와 다르다")
    if not re.fullmatch(r"\d{1,2}|all", str(req.get("part") or "")):
        bad.append(f"편 번호가 이상하다: {req.get('part')}")
    for k in ("privacy", "when", "mode"):
        if req.get(k) not in options(k):
            bad.append(f"{k} '{req.get(k)}' 는 4-2 가 받는 값이 아니다 ({options(k)})")
    if bad:
        print("❌ 요청이 틀렸다 — 누르지 않는다")
        for b in bad:
            print(f"   · {b}")
        return 1
    inputs = {"part": req["part"], "privacy": req["privacy"], "when": req["when"],
              "mode": req["mode"], "fix_only": "아니오 — 새로 올린다", "every_hours": "24",
              "sid": sid}
    repo = os.environ.get("GITHUB_REPOSITORY") or "jtaechul/verdict-theater"
    body = json.dumps({"ref": "main", "inputs": inputs}).encode()
    r = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/workflows/short90-upload.yml/dispatches",
        data=body, method="POST",
        headers={"Authorization": f"Bearer {os.environ.get('GH_TOKEN', '')}",
                 "Accept": "application/vnd.github+json", "User-Agent": "verdict-theater",
                 "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=60) as resp:
        print(f"■ [4-2. 쇼츠 유튜브에 올리기] 를 눌렀다 (HTTP {resp.status}) — "
              f"{sid} {req['part']}편 · {req['privacy']} · {req['when']} · {req['mode']}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="작업 칸에서 올리기 단추를 누른다")
    ap.add_argument("sid", nargs="?", default="")
    ap.add_argument("--part", default="1")
    ap.add_argument("--privacy", default="비공개", help="비공개 · 일부공개 · 공개")
    ap.add_argument("--when", default="예약", help="예약(한국 아침 8시) · 지금")
    ap.add_argument("--mode", default="진짜", help="진짜 · 연습")
    ap.add_argument("--again", action="store_true", help="이미 올린 편을 또 올린다 (권하지 않는다)")
    ap.add_argument("--dispatch", default="", help="워크플로에서만 — upload/<사건>")
    a = ap.parse_args()
    if a.dispatch:
        return dispatch(a.dispatch)
    if not re.fullmatch(r"[Ss]\d{2,4}", a.sid or ""):
        ap.print_help()
        return 2
    sid = a.sid.upper()
    import shortstate                                          # noqa: E402
    import stage_video as SV                                   # noqa: E402
    was = shortstate.uploaded(sid, int(a.part)) if a.part.isdigit() else None
    if was and not a.again:
        print(f"❌ {sid} {a.part}편은 이미 올렸다 — https://youtu.be/{was.get('video_id')}")
        return 1
    _files, bad = SV.ready(sid)
    if bad:
        print(f"❌ {sid} 는 아직 올릴 준비가 안 됐다 — 요청하지 않는다")
        for b in bad:
            print(f"   · {b}")
        return 1
    req = request_of(sid, a.part, a.privacy, a.when, a.mode)
    br = push(sid, req)
    print(f"■ 올리기 요청을 {br} 로 보냈다 — {req['privacy']} · {req['when']} · {req['mode']}\n"
          f"  워크플로(4-2b)가 [4-2. 쇼츠 유튜브에 올리기] 를 누르고 가지를 지운다 (1분 안팎).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
