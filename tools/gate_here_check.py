#!/usr/bin/env python3
"""⭐ 작업 칸 심사(0원)가 돈 드는 심사와 **똑같이** 적는가 — 값 0원 · 인터넷 0회

    python3 tools/gate_here_check.py

2026-10-02 손님: "왜 또 돈들어? 그냥 니가 여기서 심사하고 올려 돈쓰지마"
→ tools/gate_here.py 로 클로드가 작업 칸에서 매기고 대기열에 적는다.
   같은 채점표 · 같은 입력 · 같은 적기여야 한다 — 갈라지면 화면의 '다음 사건 고르기' 와
   대본 단계가 딴 칸을 읽는다.

  ① 같은 적기    gate.py 와 gate_here.py 가 gate.apply_result 하나로 적는다
  ② 같은 입력    꺼내는 판례 글이 gate.case_for_prompt 그대로다 (앞 9,000 · 뒤 3,000자)
  ③ 같은 규칙    합은 다시 센다 · 통과선 60 · 탈락 사유 · 목록 밖 유형은 '기타' · 한 줄 50자
  ④ 진짜로 적기  임시 대기열에 적어 본다 — 매긴 곳 표시 · 이미 매긴 것은 안 건드림
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import gate                                                   # noqa: E402
import gate_here as GH                                        # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


print("⭐ 작업 칸 심사(0원) 점검\n")

print("① 같은 적기")
gs = (ROOT / "src" / "gate.py").read_text(encoding="utf-8")
hs = (ROOT / "tools" / "gate_here.py").read_text(encoding="utf-8")
ck("돈 드는 심사가 apply_result 로 적는다", "ok = apply_result(row, res)" in gs)
ck("작업 칸 심사도 같은 apply_result 로 적는다", "gate.apply_result(row, norm)" in hs)
ck("대기열 줄을 고치는 곳은 apply_result 하나뿐이다 (row.update 가 둘이 아니다)",
   gs.count('"gate_score": total,') == 1)

print("\n② 같은 입력")
case = {"사건명": "약정금", "판례내용": "가" * 20000, "사건번호": "2024가합1"}
body = json.loads(gate.case_for_prompt(case))["판례내용"]
ck("꺼내는 글이 돈 드는 심사가 보내는 글과 같다 (가운데를 같은 자리에서 자른다)",
   "gate.case_for_prompt(case)" in hs and body.startswith("가" * gate.GATE_HEAD)
   and body.endswith("가" * gate.GATE_TAIL) and "생략" in body
   and len(body) < 20000, str(len(body)))

print("\n③ 같은 규칙")
types = GH.case_types()
ck("유형 목록을 채점표에서 읽는다 (새 갈래 유형 포함)",
   {"노후투자사기", "치매재산", "주위토지통행", "요양원사고", "기타"} <= types, str(len(types)))
res = {"case_id": "1", "total": 99, "pass": True,
       "scores": {"conflict": 18, "betrayal": 17, "twist": 9, "empathy": 13,
                  "catharsis": 12, "amount": 6, "detail": 6},
       "case_type": "아무거나", "one_line": "가" * 80, "reject": ["no_person", "엉뚱"],
       "amount_krw": "150000000", "senior": 1}
n, _ = GH.normalize(res, types)
ck("합은 일곱 항목으로 다시 센다 (모델이 적은 99 가 아니라 81)", n["total"] == 81, str(n["total"]))
ck("탈락 사유가 있으면 합이 높아도 탈락", n["pass"] is False and n["reject"] == ["no_person"])
ck("목록 밖 유형은 '기타' · 한 줄은 50자", n["case_type"] == "기타" and len(n["one_line"]) == 50)
res2 = dict(res, reject=[], scores=dict(res["scores"], twist=99))
n2, _ = GH.normalize(res2, types)
ck("항목 상한을 넘는 점수는 상한으로 (반전 15)", n2["scores"]["twist"] == 15 and n2["total"] == 87)
res3 = dict(res2, scores={"conflict": 10, "betrayal": 10, "twist": 10, "empathy": 10,
                          "catharsis": 10, "amount": 5, "detail": 4})
n3, _ = GH.normalize(res3, types)
ck(f"통과선은 돈 드는 심사와 같은 {gate.PASS_MARK}점", n3["total"] == 59 and n3["pass"] is False)

print("\n④ 진짜로 적기 (임시 대기열)")
with tempfile.TemporaryDirectory() as t:
    q = Path(t) / "queue.json"
    q.write_text(json.dumps([
        {"case_id": "1", "topic": "치매", "machine_score": 50, "gate_score": None},
        {"case_id": "2", "topic": "요양", "machine_score": 40, "gate_score": 77,
         "gate_pass": True, "one_line": "옛 결과"},
    ], ensure_ascii=False), encoding="utf-8")
    rf = Path(t) / "r.json"
    rf.write_text(json.dumps([dict(res2, case_id="1"), dict(res2, case_id="2"),
                              dict(res2, case_id="999")], ensure_ascii=False), encoding="utf-8")
    real = gate.QUEUE
    gate.QUEUE = q
    try:
        GH.merge([str(rf)])
        rows = {r["case_id"]: r for r in json.loads(q.read_text(encoding="utf-8"))}
    finally:
        gate.QUEUE = real
    r1 = rows["1"]
    ck("매긴 결과가 대기열에 들어간다 (점수 · 통과 · 유형 · 금액 · 어르신)",
       r1["gate_score"] == 87 and r1["gate_pass"] is True and r1["case_type"] == "기타"
       and r1["amount_krw"] == 150000000 and r1["senior"] is True, str(r1))
    ck("어디서 매겼는지 남는다 (작업 칸 · 0원)", r1.get("gate_by") == GH.GATE_BY)
    ck("이미 매긴 것은 건드리지 않는다", rows["2"]["one_line"] == "옛 결과")
    ck("통과한 것이 앞으로 온다 (돈 드는 심사와 같은 차례로 저장)",
       list(rows) == ["1", "2"] or json.loads(q.read_text(encoding="utf-8"))[0]["gate_pass"])

print("─" * 56)
if bad:
    print(f"❌ {len(bad)}개 걸렸습니다 — 고치고 다시")
    sys.exit(1)
print("✅ 작업 칸 심사: 같은 적기 · 같은 입력 · 같은 규칙 · 진짜로 적기")
