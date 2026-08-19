#!/usr/bin/env python3
"""⭐ 회차가 **차례대로** 가는지 본다. 0원 · 인터넷 0회.

    python3 tools/order_test.py

왜 (2026-08-16 손님: "제작할 대본/영상 회차가 갑자기 다음 회차로 넘어가는
    문제도 해결해야 해")
    실제 사고: [도입 훅만] 버튼이 잘못 새어 EP003 대본이 승인 없이 만들어졌고
    (719원), 영상 만들기와 관리자 화면까지 EP002 를 제쳐 두고 EP003 을 권했다.
    막는 자리 세 곳이 **같은 규칙**을 쓰는지 여기서 본다:
      ① 대본 만들기(script.py)  — 앞 회차가 발행 전이면 새 회차를 안 만든다
      ② 영상 만들기(produce.yml) — '자동'이면 발행 안 된 가장 이른 회차를 고른다
      ③ 관리자 큰 버튼           — 발행 안 된 가장 이른 회차를 권한다
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

FAIL = []


def bad(msg):
    FAIL.append(msg)
    print(f"   ❌ {msg}")


def ok(msg):
    print(f"   ✅ {msg}")


def main():
    from script import order_gate

    print("⭐ 회차 차례 지키기")
    with tempfile.TemporaryDirectory() as td:
        sd = Path(td)
        for e in ("EP001", "EP002", "EP003"):
            (sd / f"{e}.json").write_text("{}", encoding="utf-8")

        # ① 전부 발행됨 → 새 회차를 만들어도 된다
        eps = {e: {"stage": "published"} for e in ("EP001", "EP002", "EP003")}
        if order_gate(eps, sd) == []:
            ok("전부 발행됐으면 새 회차를 허락한다")
        else:
            bad("전부 발행됐는데도 새 회차를 막는다")

        # ② 발행 전 회차가 있으면 → 막고, 가장 이른 것부터 알려 준다
        eps["EP002"]["stage"] = "evaluated"
        eps["EP003"]["stage"] = "scripting"
        got = order_gate(eps, sd)
        if got and got[0] == "EP002":
            ok(f"발행 전 회차가 있으면 막는다 (가장 이른 것부터: {got})")
        else:
            bad(f"막지 않거나 순서가 틀렸다: {got}")

        # ③ state 에만 있고 대본 파일이 없는 유령 회차는 세지 않는다
        eps["EP009"] = {"stage": "scripting"}
        if "EP009" not in order_gate(eps, sd):
            ok("대본 파일이 없는 유령 회차는 세지 않는다")
        else:
            bad("유령 회차(대본 없음)까지 막는 데 쓴다")

    # ④ 대본 만들기 본문이 이 규칙을 실제로 쓰는가 (우회로가 생기면 잡는다)
    src = (ROOT / "src" / "script.py").read_text(encoding="utf-8")
    if "busy = order_gate(eps)" in src and "VT_NEW_EP_OK" in src:
        ok("대본 만들기가 규칙을 실제로 쓴다 (VT_NEW_EP_OK 로만 풀린다)")
    else:
        bad("대본 만들기 본문에서 차례 규칙이 빠졌다")

    # ⑤ 영상 만들기 '자동'과 관리자 큰 버튼이 같은 규칙(발행 안 된 가장 이른)인가
    prod = (ROOT / ".github" / "workflows" / "produce.yml").read_text(encoding="utf-8")
    if 'stage") != "published"' in prod and "todo[0]" in prod:
        ok("영상 만들기 '자동'도 발행 안 된 가장 이른 회차를 고른다")
    else:
        bad("영상 만들기 '자동'이 다른 규칙을 쓴다")
    adm = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
    if "localeCompare(b[0])" in adm and "noVideo" in adm:
        ok("관리자 큰 버튼도 이른 회차부터 권한다")
    else:
        bad("관리자 큰 버튼이 최신 회차부터 권한다 (내림차순 find)")

    print("─" * 52)
    if FAIL:
        print(f"❌ 회차 차례 시험: {len(FAIL)}가지 실패")
        return 1
    print("✅ 회차 차례 시험: 전부 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
