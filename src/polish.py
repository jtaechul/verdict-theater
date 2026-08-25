#!/usr/bin/env python3
"""대본 다듬기 — 자연스러움 · 정합성 · 자극성을 **모델에게 한 번 더 검토시킨다.**

    python3 src/polish.py review S001    검토만 한다 (약 150원)
    python3 src/polish.py apply  S001    검토에서 나온 고침안을 대본에 넣는다 (0원)

왜 이 절차가 있는가 (2026-08-25 운영자)
    "대사의 자연스러움과 전체 맥락에서의 정합성을 체크하고 자극적이도록
     다듬는 절차도 추가하자."

    기계로 잡을 수 있는 것(tools/story_check.py)은 이미 0원으로 잡는다 —
    누설·빠진 폭로·답으로 끝내기·장부 밖 금액·거꾸로 가는 때.
    그런데 **기계가 못 보는 것**이 남는다:
      · "내 앞으로" 가 맞는지 "네 앞으로" 가 맞는지 (누가 말하느냐에 달렸다)
      · 사람이 실제로 그렇게 말하는지
      · 그 대사가 손가락을 멈추게 할 만큼 센지
    이건 글을 읽어야 아는 것이라 모델을 한 번 부른다.

절차 (두 단계 — 사람이 가운데에서 본다)
    ① review  모델이 16화 전체를 한 번에 읽고 **고칠 곳과 고침안**을 낸다
    ② apply   고침안을 이야기 파일에 넣고, **기계 검사를 전부 다시 돌린다.**
              하나라도 걸리면 **통째로 되돌린다** (반쯤 고친 대본을 안 남긴다)
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import series as S                                           # noqa: E402
from claude import grader                                    # noqa: E402

OUT = ROOT / "state" / "polish.json"
KINDS = ("정합성", "자연스러움", "자극성")


def story_path(sid):
    return ROOT / "data" / "series" / f"{sid}_story.py"


def doc_path(sid):
    return ROOT / "data" / "series" / f"{sid}.json"


def script_text(doc):
    """모델에게 보여 줄 **16화 전체 대사** (한눈에 들어오게)."""
    out = []
    led = doc.get("ledger") or {}
    if led:
        out.append("[금액 장부] " + " · ".join(f"{k} {v}" for k, v in led.items()))
    for e in doc.get("episodes") or []:
        out.append(f"\n=== {e.get('no')}화 「{e.get('title')}」 "
                   f"· {e.get('when')} · 감정 {e.get('mood')} ===")
        if e.get("irony"):
            out.append("  (아내가 없는 화 — 시청자만 먼저 안다)")
        out.append(f"  이 화의 폭로: {e.get('reveal')}")
        for c in e.get("cuts") or []:
            out.append(f"  [{c.get('n')}컷]")
            for who, txt in S.dia_turns(c.get("prompt")):
                out.append(f"    {who}: {txt}")
    return "\n".join(out)


PROMPT = """너는 세로형 숏드라마(DramaBox 같은 것)의 **대본 감수자**다.
아래는 실제 판결문으로 만든 16화짜리 한국어 숏드라마 대본이다.
등장인물은 셋뿐이다 — Wife(본처) · Husband(남편) · Other woman(그 여자).

세 가지만 본다.

1. 정합성 — 앞뒤가 맞는가
   · 아직 일어나지 않은 일을 미리 말하지 않는가
   · **누가 말하느냐에 따라 달라지는 말**이 뒤집혀 있지 않은가
     (예: 남편이 "내 앞으로 된 게 없다" 라고 해야 할 자리에 "네 앞으로" 라고 썼다든가)
   · 사실·금액·날짜가 화마다 어긋나지 않는가
   · 그 화의 폭로가 정말 그 화에서 처음 나오는가

2. 자연스러움 — 실제 사람이 그렇게 말하는가
   · 서류 말투·설명체가 섞이지 않았는가 ("~에 근거하여", "~하였습니다")
   · 싸우는 사람의 말투인가 (조사 생략, 말끝 살리기, 군말)
   · 한 사람이 같은 말투만 되풀이하지 않는가

3. 자극성 — 손가락을 멈추게 하는가
   · 밋밋한 대사를 더 세게 (단, **사실을 바꾸지 않는다**)
   · 특히 각 화의 **마지막 대사**는 다음 화를 보고 싶게 만드는 질문이어야 한다

규칙
   · 고침안은 **원문과 같은 길이 안팎**으로 (음절 수가 크게 늘면 영상에 안 들어간다)
   · 금액은 위 장부에 있는 값만 쓴다
   · 등장인물을 늘리지 않는다
   · 고칠 곳이 없으면 issues 를 빈 배열로 둔다
   · **원문(before)은 대본에 있는 그대로** 한 글자도 다르지 않게 적는다

아래 모양의 JSON 하나만 낸다.

{{
  "issues": [
    {{"ep": 3, "cut": 1, "kind": "정합성",
      "before": "대본에 있는 그대로의 대사",
      "after":  "고친 대사",
      "why":    "왜 고쳐야 하는지 한 줄"}}
  ],
  "verdict": "전체 소감 두세 줄"
}}

--- 대본 ---
{SCRIPT}
"""


def review(sid):
    doc = json.loads(doc_path(sid).read_text(encoding="utf-8"))
    llm, who = grader(max_calls=3, prefer="gemini")
    body = PROMPT.replace("{SCRIPT}", script_text(doc))
    got = llm.json(body, tier="pro", max_output_tokens=16384, temperature=0.5,
                   label="대본 다듬기")
    issues = [i for i in (got.get("issues") or []) if i.get("before") and i.get("after")]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"sid": sid, "by": who,
                               "verdict": got.get("verdict", ""),
                               "issues": issues}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"\n⭐ 대본 다듬기 검토 — {sid} · 지적 {len(issues)}가지\n")
    print((got.get("verdict") or "").strip() + "\n")
    for i in issues:
        print(f"  [{i.get('kind', '?')}] {i.get('ep')}화 {i.get('cut')}컷")
        print(f"     지금 : {i.get('before')}")
        print(f"     고침 : {i.get('after')}")
        print(f"     까닭 : {i.get('why', '')}\n")
    if issues:
        print("→ 넣으려면 [대본 다듬기 반영] 을 누르십시오 (0원).")
    return 0


def checks_pass():
    """기계 검사 세 가지를 전부 돌린다 (0원)."""
    for cmd in (["python3", "tools/story_check.py"],
                ["python3", "tools/subtitle_audit.py"],
                ["python3", "tools/series_test.py"]):
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        if r.returncode != 0:
            print(f"❌ {' '.join(cmd)} 에서 걸렸다")
            print("\n".join((r.stdout + r.stderr).splitlines()[-12:]))
            return False
    return True


def apply(sid):
    if not OUT.exists():
        print("검토 결과가 없다 — 먼저 [대본 다듬기 검토] 를 돌리십시오.")
        return 1
    got = json.loads(OUT.read_text(encoding="utf-8"))
    issues = got.get("issues") or []
    if not issues:
        print("고칠 곳이 없다.")
        return 0

    sp = story_path(sid)
    backup = sp.with_suffix(".py.bak")
    shutil.copy2(sp, backup)
    text = sp.read_text(encoding="utf-8")
    done, miss = 0, []
    for i in issues:
        a, b = i["before"].strip(), i["after"].strip()
        # ⚠️ 대사는 큰따옴표 안에 있다. **정확히 한 군데**일 때만 바꾼다 —
        #    여러 군데면 엉뚱한 화를 고칠 수 있다.
        if text.count(f'"{a}"') == 1:
            text = text.replace(f'"{a}"', f'"{b}"')
            done += 1
        else:
            miss.append(f"{i.get('ep')}화 {i.get('cut')}컷: '{a[:24]}…'")
    sp.write_text(text, encoding="utf-8")

    r = subprocess.run(["python3", "tools/rewrite_story.py"], cwd=str(ROOT),
                       capture_output=True, text=True)
    ok = r.returncode == 0 and checks_pass()
    if not ok:
        shutil.copy2(backup, sp)
        subprocess.run(["python3", "tools/rewrite_story.py"], cwd=str(ROOT),
                       capture_output=True, text=True)
        backup.unlink(missing_ok=True)
        print("\n❌ 넣어 보니 검사에 걸렸다 — **통째로 되돌렸다.**")
        print("   (반쯤 고친 대본을 남기지 않는다)")
        return 1
    backup.unlink(missing_ok=True)
    print(f"\n✅ {done}군데 고쳐 넣었다. 기계 검사 전부 통과.")
    for m in miss:
        print(f"   ⚠️ 원문을 못 찾아 건너뛴 곳 — {m}")
    return 0


def main(argv):
    what = (argv[1] if len(argv) > 1 else "review").strip()
    sid = (argv[2] if len(argv) > 2 else "S001").strip().upper()
    if what == "apply":
        return apply(sid)
    return review(sid)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
