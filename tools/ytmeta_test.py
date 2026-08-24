#!/usr/bin/env python3
"""⭐ 유튜브에 올릴 제목·설명·해시태그가 제대로 만들어지는지 본다. 0원.

    python3 tools/ytmeta_test.py

왜 (2026-08-20 운영자 지시)
    "동영상 올릴 때 유튜브 쇼츠 영상, 제목이라든가 설명, 해시태그 아무것도
     안 들어가 있어. 업로드 설정도 같이 추가해 줘."

    ⚠️ 같은 계산이 **두 군데**에 있다 — 파이썬(src/ytmeta.py)과 관리자 페이지
       (admin/worker.js). 화면에서 본 것과 실제로 올라가는 것이 다르면 안 되므로
       **두 곳의 결과가 한 글자도 다르지 않은지** 여기서 맞춰 본다.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import ytmeta as Y                                          # noqa: E402

FAIL = []


def ck(label, cond, extra=""):
    print(("   ✅ " if cond else "   ❌ ") + label + (f"  ({extra})" if extra else ""))
    if not cond:
        FAIL.append(label)


DOC = {
    "series_id": "S001", "title": "바람난 남편이 빼돌린 15억", "case_type": "유류분",
    "episodes": [
        {"no": 1, "title": "집을 나가는 남편", "recap": "",
         "cuts": [{"n": 1, "subtitle": '"당신 진짜 제정신이야?" / "더는 못 살아."'}]},
        {"no": 2, "hook": "통장이 텅 비어 있었다", "title": "빈 통장",
         "recap": "집을 나간 남편",
         "cuts": [{"n": 1, "subtitle": '"돈이 하나도 없다고요?"'}]},
    ],
}

print("⭐ 유튜브에 올릴 글 시험\n")

print("① 제목")
m1 = Y.make(DOC, 1)
m2 = Y.make(DOC, 2)
ck("제목이 비지 않는다", bool(m1["title"].strip()))
ck("100자를 넘지 않는다", len(m1["title"]) <= 100, f"{len(m1['title'])}자")
ck("#shorts 가 붙는다", "#shorts" in m1["title"], m1["title"])
# ⭐ 2026-08-24 — `(1/2)` → `(1화)`. 총 편수를 감춰 분량 부담을 없앤다.
ck("몇 화인지 들어간다", "(1화)" in m1["title"])
ck("후킹이 있으면 그것을 쓴다", m2["title"].startswith("통장이 텅"), m2["title"])

print("\n② 해시태그")
ck("제목 조각이 아니라 주제어다", "바람난" not in m1["tags"] and "남편이" not in m1["tags"],
   " ".join(m1["tags"][:4]))
ck("사건 갈래에서 뽑는다", "유류분" in m1["tags"] or "상속" in m1["tags"],
   " ".join(m1["tags"]))
ck("불륜 이야기면 그 태그도", "불륜" in m1["tags"])
ck("채널 태그가 늘 붙는다", "판결극장" in m1["tags"] and "shorts" in m1["tags"])
ck("15개를 넘지 않는다", len(m1["tags"]) <= 15, f"{len(m1['tags'])}개")
ck("# 는 안 붙인 채로 담는다", all(not t.startswith("#") for t in m1["tags"]))

print("\n③ 설명")
ck("시리즈 제목과 회차가 들어간다",
   "바람난 남편이 빼돌린 15억" in m1["description"] and "1화 / 전 2화" in m1["description"])
ck("각색·익명 고지가 들어간다", "각색한 이야기" in m1["description"]
   and "바꾸었습니다" in m1["description"])
ck("해시태그가 설명 끝에 붙는다", "#판결극장" in m1["description"])
ck("2화부터 지난 이야기가 들어간다", "지난 이야기" in m2["description"])
ck("1화에는 지난 이야기가 없다", "지난 이야기" not in m1["description"])
ck("4900자를 넘지 않는다", len(m1["description"]) <= 4900)

print("\n④ 대본이 정해 준 것이 있으면 그것을 먼저 쓴다")
d = json.loads(json.dumps(DOC))
d["episodes"][0]["yt_title"] = "손님이 정한 제목"
d["episodes"][0]["yt_tags"] = ["직접", "고른", "태그"]
m = Y.make(d, 1)
ck("정해 준 제목을 쓴다", m["title"].startswith("손님이 정한 제목"), m["title"])
ck("정해 준 태그를 쓴다", m["tags"][:3] == ["직접", "고른", "태그"])

print("\n⑤ 관리자 페이지와 **한 글자도** 다르지 않은가")
runner = r"""
import { readFileSync, writeFileSync } from 'fs';
import { tmpdir } from 'os'; import { join } from 'path';
const src = readFileSync('admin/worker.js', 'utf8');
const m = join(tmpdir(), 'vt-yt.mjs');
writeFileSync(m, src.replace('export default', 'const _w =') + '\nexport { ytMeta };');
const mod = await import('file://' + m);
const doc = JSON.parse(readFileSync(process.argv[2], 'utf8'));
console.log(JSON.stringify([mod.ytMeta(doc, 1), mod.ytMeta(doc, 2)]));
"""
with tempfile.TemporaryDirectory() as d:
    d = Path(d)
    (d / "doc.json").write_text(json.dumps(DOC, ensure_ascii=False), encoding="utf-8")
    (d / "r.mjs").write_text(runner)
    r = subprocess.run(["node", str(d / "r.mjs"), str(d / "doc.json")],
                       cwd=ROOT, capture_output=True, text=True)
if r.returncode != 0:
    ck("관리자 페이지 쪽이 돌아간다", False, (r.stderr or "")[:200])
else:
    j1, j2 = json.loads(r.stdout)
    for k in ("title", "description", "tags"):
        ck(f"1화 {k} 가 같다", j1[k] == m1[k],
           f"화면:{str(j1[k])[:40]} / 파이썬:{str(m1[k])[:40]}")
        ck(f"2화 {k} 가 같다", j2[k] == m2[k])

print("\n⑥ 실제 대본으로도 나오는가")
real = ROOT / "data" / "series" / "S001.json"
if real.exists():
    rm = Y.make(json.loads(real.read_text(encoding="utf-8")), 1)
    ck("실제 대본에서 제목이 나온다", bool(rm["title"].strip()), rm["title"])
    ck("실제 대본에서 태그가 나온다", len(rm["tags"]) >= 5, " ".join(rm["tags"][:5]))
else:
    print("   (대본이 없어 건너뜀)")

print("\n" + "─" * 52)
print(f"❌ 올릴 글: {len(FAIL)}가지 실패" if FAIL else "✅ 올릴 글: 전부 통과")
sys.exit(1 if FAIL else 0)
