#!/usr/bin/env python3
"""멈춘 대본을 **이어서** 마저 만드는 길이 실제로 도는지 본다. 비용 0원.

    python3 tools/script_resume_test.py

왜 이 검사가 있는가 (2026-08-10)
    대본 만들기가 3단계에서 멈춰 컷 120개를 날렸다. 파일을 남기게 고쳤지만,
    남겨봐야 **이어서 쓸 방법이 없으면** 처음부터 다시 만드는 수밖에 없다.
    그러면 가장 비싸고 오래 걸리는 1·2단계(설계 + 막별 컷)를 또 돈 내고 돈다.

    이 검사는 그 길을 지킨다.
      1. 멈춘 대본(초벌)이 있는 상태를 만들고
      2. --resume 으로 실행했을 때
      3. 1·2단계를 **부르지 않고** 끝까지 가는지 본다
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import script                                     # noqa: E402


class FakeLLM:
    def pick(self, tier="pro"):
        return f"가짜-{tier}"

    def spent_krw(self):
        return 0.0

    def report(self):
        return "모델 호출 0회 (검사용 가짜)"


CALLED = []


def main():
    tmp = Path(tempfile.mkdtemp(prefix="resume-"))
    scripts = tmp / "scripts"
    scripts.mkdir()
    doc = json.loads((ROOT / "data" / "scripts" / "SAMPLE_234921.json")
                     .read_text(encoding="utf-8"))

    # 멈춘 대본이 남아 있는 상태를 만든다
    (scripts / "EP007.draft.json").write_text(
        json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    orig = {k: getattr(script, k) for k in
            ("SCRIPTS", "EPISODES", "QUEUE", "CASES", "writer", "prompts",
             "gen_design", "gen_act", "machine_fix", "evaluate", "make_shorts")}
    script.SCRIPTS = scripts
    script.EPISODES = tmp / "episodes.json"
    script.QUEUE = tmp / "queue.json"
    script.CASES = tmp / "cases"
    script.CASES.mkdir()
    script.EPISODES.write_text(json.dumps(
        {"EP007": {"case_id": "234921", "stage": "scripting", "case_type": "유류분"}},
        ensure_ascii=False), encoding="utf-8")
    script.QUEUE.write_text("[]", encoding="utf-8")

    script.writer = lambda **k: (FakeLLM(), "가짜")
    script.prompts = type("P", (), {"load": staticmethod(lambda n: "x"),
                                    "fill": staticmethod(lambda b, **k: b)})()
    # 1·2단계는 **불리면 안 된다.** 불리면 표시를 남긴다.
    script.gen_design = lambda *a, **k: CALLED.append("설계") or {}
    script.gen_act = lambda *a, **k: CALLED.append("막생성") or []
    # 뒷단계는 그냥 통과시킨다 (모델을 안 부른다)
    script.machine_fix = lambda llm, d, rounds=2: (d, type("R", (), {
        "oks": [], "warns": [], "errors": []})())
    script.evaluate = lambda llm, d: {"total": 90, "verdict": "통과",
                                      "scores": {}, "blocking": [], "one_line": "검사용"}
    script.make_shorts = lambda llm, d: {"shorts": [{"no": 1, "kind": "궁금증형",
                                                     "est_sec": 40.0}]}

    argv = sys.argv
    sys.argv = ["script.py", "--resume", "EP007"]
    try:
        rc = script.main()
    finally:
        sys.argv = argv
        for k, v in orig.items():
            setattr(script, k, v)

    ok = True
    print()
    print("─" * 56)
    if CALLED:
        print(f"❌ 이어서 만든다면서 비싼 단계를 또 불렀다: {', '.join(set(CALLED))}")
        ok = False
    else:
        print("✅ 1·2단계(설계·막별 컷)를 부르지 않았다 — 값이 안 나간다")

    made = scripts / "EP007.json"
    cuts = 0
    if made.exists():
        cuts = json.loads(made.read_text(encoding="utf-8")).get("meta", {}).get("cut_count", 0)
    if cuts:
        print(f"✅ 끝까지 가서 EP007.json 을 냈다 (컷 {cuts}개 그대로)")
    else:
        print("❌ 완성본이 안 나왔다"); ok = False

    if rc == 0:
        print("✅ 정상으로 끝났다")
    else:
        print(f"❌ 끝값 {rc} — 이어서 만들기가 실패했다"); ok = False

    shutil.rmtree(tmp, ignore_errors=True)
    print("─" * 56)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
