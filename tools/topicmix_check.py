#!/usr/bin/env python3
"""⭐ **소재가 한쪽으로 쏠리지 않는가** — 값 0원 · 인터넷 0회

    python3 tools/topicmix_check.py

2026-10-01 손님: "판례를 좀 다양한 걸 수집하면 안 되냐? 너무 유류분이냐 상속하고
이거에만 매몰되어 있는 것 같은데 … 니치는 50대부터 70대, 80대 어르신들인 거는 유지하고."
그때 대기열 165건 = 상속 99 · 재산 61 · 불륜 5, 만든 네 사건 가운데 셋이 상속.

  ① 모으기   어르신 갈래 다섯(노후사기·효도계약·치매·땅·선산·요양)이 있고, 갈래마다
             확인 낱말이 있다 · '전부' 는 대기열에 적은 갈래부터 돌아가며 훑는다 ·
             어르신 갈래는 사람 이야기 아닌 사건명(임금·보험금…)을 본문 받기 전에 뺀다
  ② 심사     어르신(50~80대) 기준 · 주인공 나이(senior) 칸 · 새 갈래 사건 유형
  ③ 고르기   바로 앞 편과 같은 갈래는 뒤로 · 상속 30% 넘김은 뒤로 · 어르신 먼저 —
             자동 고르기(story90)와 관리자 화면(worker.js)이 **같은 차례**를 낸다
  ④ 단추     관리자 페이지 · 워크플로 선택지에 새 갈래가 있다
  ⑤ 심사 차례 '전부' 로 심사하면 쓸 만한 것이 적은 갈래부터 돌아가며 매긴다
             (기계 점수 순이면 상속이 늘 먼저 걸린다)
  ⑥ 어르신 다섯 새 갈래 다섯을 한 번 눌러 고르게 모으고 고르게 심사한다
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import collect as C                                          # noqa: E402
import topicmix as TM                                        # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


print("⭐ 소재 갈래 섞기 점검 — 값 0원\n")

# ── ① 모으기 ────────────────────────────────────────────────
print("① 모으기 — 어르신 갈래 · 돌아가며 · 잡음 빼기")
NEW = ("노후사기", "효도계약", "치매", "땅·선산", "요양")
ck("어르신 갈래 다섯이 있다", all(t in C.QUERY_GROUPS and C.QUERY_GROUPS[t] for t in NEW))
ck("갈래마다 '진짜 그 사건인지' 확인 낱말이 있다",
   all(C.TOPIC_WORDS.get(t) for t in NEW))
ck("검색어가 갈래끼리 겹치지 않는다 (겹치면 갈래가 엉뚱하게 붙는다)",
   len(C.QUERIES) == len(set(C.QUERIES)))
ck("옛 갈래 검색어는 그대로다 (쌓인 대기열의 갈래가 안 바뀐다)",
   C.QUERY_GROUPS["상속"][0] == "유류분" and "상간" in C.QUERY_GROUPS["불륜"])
queue = [{"topic": "상속"}] * 99 + [{"topic": "재산"}] * 61 + [{"topic": "불륜"}] * 5
order = C.rotate(C.QUERIES, queue)
first = [C.TOPIC_OF[q] for q in order[:len(C.QUERY_GROUPS)]]
ck("'전부' 는 갈래마다 하나씩 번갈아 훑는다 (앞자리에 갈래가 하나씩)",
   len(set(first)) == len(C.QUERY_GROUPS), str(first))
ck("대기열에 많이 쌓인 갈래(상속·재산)는 뒤로 간다",
   first.index("상속") > first.index("노후사기") and first.index("재산") > first.index("치매"))
ck("검색어를 하나도 안 빠뜨린다", sorted(order) == sorted(C.QUERIES))
ck("어르신 갈래는 사람 이야기 아닌 사건명을 뺀다 (임금·보험금…)",
   C.noise_name("임금등", "노후사기") == "임금" and C.noise_name("보험금", "치매") == "보험금"
   and C.noise_name("주위토지통행권확인", "땅·선산") == "")
ck("옛 갈래에는 이 거르기를 안 건다 (지금까지 걸러 온 그대로)",
   C.noise_name("임금등", "상속") == "")
src = (ROOT / "src" / "collect.py").read_text(encoding="utf-8")
ck("사건명 거르기를 **본문 받기 전에** 건다 (호출·심사값을 아낀다)",
   src.index("noise_name(r.get(\"사건명\"") < src.index("case = api.fetch(cid)"))

# ── ② 심사 ─────────────────────────────────────────────────
print("\n② 심사 — 어르신 기준 · 주인공 나이")
gp = (ROOT / "prompts" / "drama_gate.md").read_text(encoding="utf-8")
body = gp.split("<!-- PROMPT:BEGIN -->")[1]
ck("심사 기준이 50~80대 어르신이다", "50~80대" in body)
ck("주인공 나이(senior) 칸을 낸다", '"senior": true' in body and "`senior`" in body)
ck("새 갈래 사건 유형이 목록에 있다",
   all(w in body for w in ("노후투자사기", "효도계약", "치매재산", "주위토지통행",
                            "분묘기지권", "종중재산", "요양원사고")))
ck("어르신을 노린 배신도 배신으로 본다", "어르신을 노린 배신도 배신이다" in body)
gs = (ROOT / "src" / "gate.py").read_text(encoding="utf-8")
ck("심사 결과의 senior 를 대기열에 적는다", '"senior": bool(res.get("senior"))' in gs)

# ── ③ 고르기 ───────────────────────────────────────────────
print("\n③ 고르기 — 같은 갈래 연속 금지 · 상속 30% · 어르신 먼저")
ready = [
    {"case_id": "1", "topic": "상속", "gate_score": 92, "senior": True},
    {"case_id": "2", "topic": "땅·선산", "gate_score": 70, "senior": True},
    {"case_id": "3", "topic": "노후사기", "gate_score": 81, "senior": False},
    {"case_id": "4", "topic": "노후사기", "gate_score": 78, "senior": True},
    {"case_id": "5", "topic": "치매", "gate_score": 65, "senior": True},
    {"case_id": "6", "topic": "상속", "gate_score": 88, "senior": False},
]
made_q = [{"case_id": "a", "topic": "상속"}, {"case_id": "b", "topic": "불륜"},
          {"case_id": "c", "topic": "상속"}, {"case_id": "d", "topic": "노후사기"}]
works = {"S93": {"case_id": "d"}, "S90": {"case_id": "a"}, "S91": {"case_id": "b"},
         "S92": {"case_id": "c"}}
recent = TM.recent_topics(works, made_q + ready)
ck("만든 차례를 사건 번호로 읽는다 (S90 → S93)",
   recent == ["상속", "불륜", "상속", "노후사기"], str(recent))
py = [c["case_id"] for c in TM.order(ready, recent)]
ck("바로 앞 편(노후사기)과 같은 갈래는 뒤로 간다",
   py.index("4") > py.index("2") and py.index("3") > py.index("5"), str(py))
ck("상속은 최근 30%를 넘기면 뒤로 간다 (점수가 92점이어도)",
   py.index("1") > py.index("5"), str(py))
ck("어르신 이야기를 먼저 고른다", py[0] == "2", str(py))
ck("미룰 뿐 지우지 않는다 (고를 것이 그것뿐이면 그것)",
   sorted(py) == sorted(c["case_id"] for c in ready)
   and TM.order([ready[0]], recent)[0]["case_id"] == "1")
ck("만든 것이 없으면 점수·어르신 차례 그대로",
   [c["case_id"] for c in TM.order(ready, [])][0] == "1")
s90 = (ROOT / "src" / "story90.py").read_text(encoding="utf-8")
ck("자동 고르기(story90.pick_case)가 이 규칙을 쓴다",
   "topicmix.order(ready, topicmix.recent_topics(works, q))[0]" in s90)

# 관리자 화면(worker.js)의 같은 규칙이 같은 차례를 내는가 — 진짜 화면 글을 돌려 본다
#   만든 것 넷 · 하나도 없음 · 상속 아닌 한 편 · 상속 하나 낀 두 편 — 네 경우 모두 같아야 한다
SCENES = [works, {}, {"S91": {"case_id": "b"}},
          {"S90": {"case_id": "a"}, "S91": {"case_id": "b"}}]
js_src = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
with tempfile.TemporaryDirectory() as td:
    mod = Path(td) / "wk.mjs"
    mod.write_text(js_src.replace("export default", "const _wk =")
                   + "\nexport { appHtml };\n", encoding="utf-8")
    run = Path(td) / "run.mjs"
    run.write_text(
        "const { appHtml } = await import('file://" + str(mod) + "');\n"
        "const js = appHtml().match(/<script>([\\s\\S]*?)<\\/script>/)[1];\n"
        "globalThis.document = { getElementById: () => ({ innerHTML: '', style: {} }),\n"
        "  querySelectorAll: () => [], addEventListener: () => {},\n"
        "  createElement: () => ({ style: {} }), body: { appendChild() {} } };\n"
        "globalThis.window = { isSecureContext: true };\n"
        "globalThis.fetch = async () => ({ status: 200, json: async () => ({}) });\n"
        "const F = new Function('R', js + '; return { o: mixOrder(R.ready, mixRecent(R.works, R.q)).map(c => c.case_id), r: mixRecent(R.works, R.q) };');\n"
        "const out = " + json.dumps([{"ready": ready, "works": w, "q": made_q + ready}
                                     for w in SCENES], ensure_ascii=False) + ".map(F);\n"
        "console.log(JSON.stringify(out));\nprocess.exit(0);\n", encoding="utf-8")
    p = subprocess.run(["node", str(run)], capture_output=True, text=True, timeout=120)
try:
    js = json.loads(p.stdout.strip().splitlines()[-1])
except Exception:                                            # noqa: BLE001
    js = []
want = []
for w in SCENES:
    r = TM.recent_topics(w, made_q + ready)
    want.append({"o": [c["case_id"] for c in TM.order(ready, r)], "r": r})
ck("관리자 화면도 똑같은 차례를 낸다 (worker.js mixOrder = topicmix.order)",
   js == want, f"{js} · {want} · {p.stderr[-200:]}")
ck("관리자 화면이 맨 위에 [추천] 을 단다", "' <span class=\"pill ok\">추천</span>'" in js_src)

# ── ④ 단추 ─────────────────────────────────────────────────
print("\n④ 단추 — 새 갈래를 고를 수 있다")
wf = yaml.safe_load((ROOT / ".github" / "workflows" / "collect.yml").read_text(encoding="utf-8"))
on = wf.get("on") if isinstance(wf.get("on"), dict) else wf.get(True)
opts = on["workflow_dispatch"]["inputs"]["topic"]["options"]
ck("모으기 워크플로에서 새 갈래를 고를 수 있다", all(t in opts for t in NEW), str(opts))
ck("갈래 선택지가 모으기 사전과 같다 (없는 갈래를 고르면 아무것도 안 모인다)",
   set(opts) - {"전부"} == set(C.QUERY_GROUPS) | set(TM.TOPIC_SETS),
   str(set(opts) ^ (set(C.QUERY_GROUPS) | set(TM.TOPIC_SETS) | {"전부"})))

# ── ⑤ 심사 차례 ───────────────────────────────────────────
print("\n⑤ 심사 차례 — '전부' 는 쓸 만한 것이 적은 갈래부터 돌아가며")
jq = ([{"case_id": f"i{i}", "topic": "상속", "machine_score": 90} for i in range(10)]
      + [{"case_id": f"r{i}", "topic": "상속", "gate_score": 80, "gate_pass": True}
         for i in range(6)]
      + [{"case_id": f"n{i}", "topic": "노후사기", "machine_score": 50} for i in range(6)]
      + [{"case_id": f"d{i}", "topic": "치매", "machine_score": 40} for i in range(3)]
      + [{"case_id": f"p{i}", "topic": "재산", "machine_score": 60 - i} for i in range(4)])
six = [c["topic"] for c in TM.judge_order(jq, set(), 6)]
ck("기계 점수가 높아도 넉넉한 갈래(상속 6건 대기)는 뒤로 간다",
   "상속" not in six, str(six))
ck("모자란 갈래끼리는 한 건씩 돌아가며 매긴다",
   six == ["재산", "노후사기", "치매"] * 2, str(six))
twenty = [c["topic"] for c in TM.judge_order(jq, set(), 20)]
ck("다른 갈래를 다 매긴 뒤에는 넉넉한 갈래도 매긴다 (미룰 뿐 안 버린다)",
   twenty.count("상속") == 7 and twenty[-7:] == ["상속"] * 7, str(twenty))
gone = {f"r{i}" for i in range(6)}
ck("이미 만든 것은 '쌓인 것' 으로 안 센다 (다 만들었으면 상속도 모자란 갈래)",
   "상속" in [c["topic"] for c in TM.judge_order(jq, gone, 4)])
ck("이미 매긴 것은 다시 안 매긴다",
   all(c.get("gate_score") is None for c in TM.judge_order(jq, set(), 99)))
gs = (ROOT / "src" / "gate.py").read_text(encoding="utf-8")
ck("심사(gate.py)가 '전부' 일 때 이 차례를 쓴다 (갈래를 고르면 그 갈래 점수 순)",
   "todo = topicmix.judge_order(queue, used, args.limit, load_rejected())" in gs
   and gs.index("elif want:")
   < gs.index("todo = topicmix.judge_order(queue, used, args.limit, load_rejected())"))
# 10-01 밤 사고: 쓸 만한 것 0건인 '재산' 이 맨 앞에 와 25건을 다 가져갔다 — 전부 탈락
dq = ([{"case_id": f"p{i}", "topic": "재산", "machine_score": 70} for i in range(30)]
      + [{"case_id": f"s{i}", "topic": "상속", "machine_score": 60} for i in range(30)]
      + [{"case_id": f"r{i}", "topic": "상속", "gate_score": 80, "gate_pass": True}
         for i in range(6)]
      + [{"case_id": f"n{i}", "topic": "치매", "machine_score": 40} for i in range(3)])
dead = [{"case_id": f"x{i}", "topic": "재산", "gate_score": 10, "gate_pass": False}
        for i in range(25)]
pick = [c["topic"] for c in TM.judge_order(dq, set(), 10, dead)]
ck("매겨 봤더니 거의 안 나오는 갈래(재산 25건 중 0건)는 맨 뒤 — 넉넉한 상속보다도 뒤",
   pick[:3] == ["치매"] * 3 and "재산" not in pick, str(pick))
ck("탈락 기록이 대기열에서 치워져(rejected.json) 있어도 센다",
   "재산" not in [c["topic"] for c in TM.judge_order(dq, set(), 10, dead)]
   and "재산" in [c["topic"] for c in TM.judge_order(dq, set(), 10, [])][:3])
ck("다른 것을 다 매긴 뒤에는 그 갈래도 매긴다 (미룰 뿐 안 버린다)",
   [c["topic"] for c in TM.judge_order(dq, set(), 99, dead)][-30:] == ["재산"] * 30)
few = [{"case_id": f"y{i}", "topic": "재산", "gate_score": 10, "gate_pass": False}
       for i in range(TM.BARREN_MIN - 1)]
ck(f"매겨 본 것이 {TM.BARREN_MIN}건 미만이면 아직 판단하지 않는다",
   "재산" in [c["topic"] for c in TM.judge_order(dq, set(), 10, few)][:3])
gq = json.loads((ROOT / "state" / "queue.json").read_text(encoding="utf-8"))
rj = json.loads((ROOT / "state" / "rejected.json").read_text(encoding="utf-8"))
# 진짜 대기열 — 재산이 지금도 '거의 안 나오는 갈래' 일 때만 본다 (재산 낱말을 고쳐 통과가
#   늘면 이 줄은 저절로 빠진다 · 그때는 재산을 다시 앞에 두는 것이 맞다)
allj = [c for c in gq + rj if c.get("topic") == "재산" and c.get("gate_score") is not None]
if len(allj) >= TM.BARREN_MIN and sum(1 for c in allj if c.get("gate_pass")) / len(allj) \
        < TM.BARREN_RATE:
    real25 = [c.get("topic") for c in TM.judge_order(gq, set(), 25, rj)]
    ck("지금 진짜 대기열로 '전부' 25건을 매기면 재산 탈락 더미를 안 고른다",
       "재산" not in real25 or set(real25) == {"재산"}, str(real25))

# ── ⑥ 어르신 다섯 ─────────────────────────────────────────
print("\n⑥ '어르신 다섯' — 새 갈래 다섯을 한 번에 (아이폰에서 한 번 누르기)")
ck("'어르신 다섯' 은 새 갈래 다섯이다", set(TM.members("어르신 다섯")) == set(NEW),
   str(TM.members("어르신 다섯")))
ck("갈래 하나를 고르면 그 하나 · 비우면 없음",
   TM.members("치매") == ("치매",) and TM.members("") == ())
ck("묶음 이름이 갈래 이름과 겹치지 않는다", not set(TM.TOPIC_SETS) & set(C.QUERY_GROUPS))
ck("모으기 잡음 거르기가 같은 다섯을 본다", set(C.SENIOR_TOPICS) == set(NEW))
mix = C.interleave([("고수익", {"판례일련번호": "a1"}), ("원금보장", {"판례일련번호": "a2"}),
                    ("투자사기", {"판례일련번호": "a3"}), ("치매", {"판례일련번호": "b1"}),
                    ("요양원", {"판례일련번호": "c1"}), ("치매", {"판례일련번호": "b2"})],
                   ["노후사기", "치매", "요양"])
ck("본문 받을 차례도 갈래를 돌아가며 (좁은 낱말 갈래 하나가 예산을 다 먹지 않게)",
   [r["판례일련번호"] for _, r in mix] == ["a1", "b1", "c1", "a2", "b2", "a3"],
   str([r["판례일련번호"] for _, r in mix]))
cs = (ROOT / "src" / "collect.py").read_text(encoding="utf-8")
ck("여러 갈래를 한 번에 모을 때만 돌아가며 받는다 (갈래 하나·직접 낱말은 그대로)",
   "if len(spread) > 1 and not custom:" in cs)
ck("심사도 '어르신 다섯' 이면 그 다섯만 돌아가며 매긴다",
   "topicmix.TOPIC_SETS[want]" in gs and gs.index("want in topicmix.TOPIC_SETS")
   < gs.index("elif want:"))
gq = [{"case_id": f"s{i}", "topic": "상속", "machine_score": 99} for i in range(5)] \
    + [{"case_id": f"n{i}", "topic": t, "machine_score": 50}
       for i, t in enumerate(["노후사기", "치매", "요양", "땅·선산", "효도계약"] * 2)]
grp = set(TM.TOPIC_SETS["어르신 다섯"])
picked = TM.judge_order([c for c in gq if c["topic"] in grp], set(), 5)
ck("'어르신 다섯' 심사 5건이면 갈래마다 한 건씩 (상속은 안 낀다)",
   sorted(c["topic"] for c in picked) == sorted(NEW), str([c["topic"] for c in picked]))

print("─" * 56)
if bad:
    print(f"❌ {len(bad)}개 걸렸습니다 — 고치고 다시")
    sys.exit(1)
print("✅ 소재 섞기: 어르신 갈래 · 돌아가며 모으기 · 잡음 빼기 · 심사 · 고르기 · 단추 · 심사 차례 · 어르신 다섯")
