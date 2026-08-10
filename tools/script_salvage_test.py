#!/usr/bin/env python3
"""대본이 도중에 멈춰도 **만든 것은 반드시 남는가**를 확인한다. 비용 0원.

    python3 tools/script_salvage_test.py

왜 이 검사가 있는가 (2026-08-10 EP002 실종)
    컷 120개를 19분에 걸쳐 다 만들어 놓고, 3단계에서 예상 못 한 오류
    (그림 라이브러리 없음)가 튀어나왔다. 그때의 그물은 '돈 초과·모델 오류'
    네 가지만 받게 돼 있어서, 그 오류는 그물을 그냥 통과해 프로그램을 죽였다.
    Opus 값과 19분이 통째로 사라졌다.

    이 검사는 그 상황을 그대로 흉내 낸다.
      1. 설계·막별 생성까지는 정상으로 끝나게 하고
      2. 3단계에서 **전혀 다른 종류의 오류**를 일부러 터뜨린 뒤
      3. EP 파일이 남았는가 / 실패로 보고하는가 를 본다
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
    """모델을 부르지 않는 가짜. 돈이 들지 않는다."""

    def pick(self, tier="pro"):
        return f"가짜-{tier}"

    def report(self):
        return "모델 호출 0회 (검사용 가짜)"


def main():
    tmp = Path(tempfile.mkdtemp(prefix="salvage-"))
    scripts = tmp / "scripts"
    scripts.mkdir()

    sample = ROOT / "data" / "scripts" / "SAMPLE_234921.json"
    doc = json.loads(sample.read_text(encoding="utf-8"))

    # 진짜 파일을 건드리지 않도록 저장 위치와 무거운 단계를 갈아 끼운다
    orig = {
        "SCRIPTS": script.SCRIPTS, "EPISODES": script.EPISODES,
        "QUEUE": script.QUEUE, "CASES": script.CASES,
        "writer": script.writer, "gen_design": script.gen_design,
        "gen_act": script.gen_act, "assemble": script.assemble,
        "machine_fix": script.machine_fix, "prompts": script.prompts,
    }
    script.SCRIPTS = scripts
    script.EPISODES = tmp / "episodes.json"
    script.QUEUE = tmp / "queue.json"
    script.CASES = tmp / "cases"
    script.CASES.mkdir()
    (script.CASES / "999.json").write_text(
        json.dumps({"사건명": "손해배상(기)", "판례내용": "본문"}, ensure_ascii=False),
        encoding="utf-8")
    script.QUEUE.write_text(json.dumps([{
        "case_id": "999", "gate_pass": True, "gate_score": 80, "case_type": "유류분",
    }], ensure_ascii=False), encoding="utf-8")
    script.EPISODES.write_text("{}", encoding="utf-8")

    script.writer = lambda **k: (FakeLLM(), "가짜")
    script.prompts = type("P", (), {"load": staticmethod(lambda n: "x"),
                                    "fill": staticmethod(lambda b, **k: b)})()
    script.gen_design = lambda *a, **k: {"meta": {"title_candidates": ["검사용"]},
                                         "characters": [], "anonymization": {}}
    script.gen_act = lambda *a, **k: [{"sec": 1}]
    script.assemble = lambda *a, **k: doc

    def boom(*a, **k):
        # ⭐ 예전 그물이 못 받던 종류를 그대로 재현한다
        raise ModuleNotFoundError("No module named 'PIL'")
    script.machine_fix = boom

    argv = sys.argv
    sys.argv = ["script.py", "--case", "999"]
    try:
        rc = script.main()
    finally:
        sys.argv = argv
        for k, v in orig.items():
            setattr(script, k, v)

    ok = True
    made = scripts / "EP001.json"
    print()
    print("─" * 56)
    cuts = 0
    if made.exists():
        cuts = json.loads(made.read_text(encoding="utf-8")).get("meta", {}).get("cut_count", 0)
    if cuts:
        print(f"✅ 멈췄어도 대본 파일이 남았다 (EP001.json · 컷 {cuts}개)")
    else:
        print("❌ 대본이 사라졌다 — 예전 사고가 그대로 재현된다"); ok = False

    if rc != 0:
        print(f"✅ 실패로 보고한다 (끝값 {rc}) — 초록 체크로 속이지 않는다")
    else:
        print("❌ 성공으로 끝났다 — 운영자가 멈춘 줄 모른다"); ok = False

    shutil.rmtree(tmp, ignore_errors=True)
    print("─" * 56)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
