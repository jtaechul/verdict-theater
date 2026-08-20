#!/usr/bin/env python3
"""⭐ 시리즈 화면이 진짜 대본으로 제대로 그려지는지 본다. 0원 · 인터넷 0회.

    python3 tools/series_screen_test.py

왜 (2026-08-20)
    손님: "관리자페이지에서 못봐??" — 대본을 만들어 놓고 화면에 안 띄워서
    GitHub 링크를 드렸다. 손님은 GitHub 에 안 들어간다.

    화면을 붙였다고 말만 하면 안 된다. **실제 대본(data/series/*.json)을
    넣고 브라우저 코드를 그대로 돌려서** 인물 프롬프트·컷 프롬프트·복사
    버튼이 정말 나오는지 확인한다. 특히 클립 프롬프트 6줄이 한 글자도
    안 깨지고 나와야 한다 — 그걸 그대로 구글 플로우에 붙여 넣기 때문이다.
"""
import json
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


docs = sorted((ROOT / "data" / "series").glob("S*.json"))
docs = [d for d in docs if not d.name.endswith(".broken.json")]
if not docs:
    print("⚠️ 만들어 둔 시리즈 대본이 없어 건너뛴다 (0원)")
    sys.exit(0)
doc = json.loads(docs[0].read_text(encoding="utf-8"))
sid = docs[0].stem

print(f"⭐ 시리즈 화면 시험 — {sid} 「{doc.get('title','')}」\n")

# 브라우저에 실제로 나갈 코드를 뽑아, 가짜 화면에 붙여 한 번 그려 본다
runner = r"""
import { readFileSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
const src = readFileSync('admin/worker.js', 'utf8');
const mod = join(tmpdir(), 'vt-series-screen.mjs');
writeFileSync(mod, src.replace('export default', 'const _wk =') + '\nexport { appHtml };\n');
const { appHtml } = await import('file://' + mod);
const js = appHtml().match(/<script>([\s\S]*?)<\/script>/)[1];

const boxes = {};
globalThis.document = {
  getElementById: (id) => boxes[id] || (boxes[id] = { innerHTML: '', style: {}, textContent: '' }),
  querySelectorAll: () => [],
  addEventListener: () => {},
  createElement: () => ({ style: {}, appendChild(){}, select(){} }),
  body: { appendChild(){}, removeChild(){} },
  execCommand: () => true,
};
globalThis.window = { isSecureContext: true };
globalThis.location = { href: '' };
globalThis.fetch = async () => ({ status: 200, json: async () => ({}) });
globalThis.scrollTo = () => {};
// navigator 는 노드에 이미 있어 덮어쓸 수 없다 — 복사는 화면 시험 대상이 아니다

const doc = JSON.parse(readFileSync(process.argv[2], 'utf8'));

// ⚠️ 2026-08-20 — 복사 단추를 눌러 플로우에 붙였더니 URL 인코딩된 글자가
//    붙었다("%20%22%EB%8D%94..."). 그래서 **실제로 복사되는 문자열을 붙잡아**
//    원본과 한 글자도 다르지 않은지 본다. 화면이 그려지는 것만 봐서는 모른다.
const clip = { last: null };

// 화면 코드 전체를 들여와 시리즈 그리기만 직접 부른다
const run = new Function('DOC', 'SIDIN', 'CLIP', js + `
  S = { series: { [SIDIN]: { title: DOC.title, episodes: 16, made: 0 } } };
  SDOC = DOC; SDOC._sid = SIDIN; SID = SIDIN; SEP = 1;
  const out = { card: seriesCard(), ep1: '' };
  seriesRender();
  out.ep1 = document.getElementById('app').innerHTML;
  // 실제로 복사되는 글자를 붙잡는다
  out.copied = {};
  Object.keys(COPY).forEach(k => { out.copied[k] = COPY[k]; });
  SEP = 16; seriesRender();
  out.ep16 = document.getElementById('app').innerHTML;
  return out;
`);
console.log(JSON.stringify(run(doc, process.argv[3], clip)));
"""
with tempfile.TemporaryDirectory() as d:
    r = Path(d) / "run.mjs"
    r.write_text(runner)
    p = subprocess.run(["node", str(r), str(docs[0]), sid],
                       cwd=ROOT, capture_output=True, text=True)
if p.returncode != 0:
    print("   ❌ 화면 코드가 돌다가 죽었다:\n" + (p.stderr or "")[:900])
    sys.exit(1)
out = json.loads(p.stdout)
card, ep1, ep16 = out["card"], out["ep1"], out["ep16"]

print("① 첫 화면 카드")
ck("시리즈 제목이 뜬다", doc.get("title", "") in card, doc.get("title", "")[:24])
ck("[대본 보기] 버튼이 있다", "seriesView(" in card)

print("\n② 인물 — 플로우에서 얼굴을 먼저 만들 때 쓴다")
for c in doc.get("characters", []):
    ck(f"{c['name']} 이름이 뜬다", c["name"] in ep1)
    ck(f"{c['name']} 프롬프트가 통째로 들어 있다",
       c["flow_prompt"][:60] in ep1, c["flow_prompt"][:38] + "…")

print("\n③ 1화 5컷 — 이걸 그대로 플로우에 붙여 넣는다")
e1 = doc["episodes"][0]
for c in e1["cuts"]:
    # 프롬프트 6줄이 한 줄도 빠짐없이 화면에 있어야 한다
    lines = [l for l in c["prompt"].split("\n") if l.strip()]
    miss = [l[:26] for l in lines
            if l.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
               .replace('"', "&quot;") not in ep1]
    ck(f"{c['n']}컷 프롬프트 {len(lines)}줄이 전부 있다", not miss, ("빠짐: " + str(miss)) if miss else "")
ck("컷마다 복사 버튼이 있다", ep1.count("copyRaw(") >= len(e1["cuts"]),
   f"{ep1.count('copyRaw(')}개")

print("\n③-2 실제로 복사되는 글자가 원본과 같은가 (URL 인코딩 사고 재발 방지)")
copied = out.get("copied", {})
ck("복사할 원본이 화면마다 담긴다", len(copied) >= len(e1["cuts"]), f"{len(copied)}개")
bad_enc, bad_eq = [], []
for i, c in enumerate(e1["cuts"], 1):
    got = copied.get(f"p1_{i}")
    if got != (c.get("prompt") or ""):
        bad_eq.append(f"{i}컷")
    if got and re.search(r"%[0-9A-Fa-f]{2}", got):
        bad_enc.append(f"{i}컷")
for i, ch in enumerate(doc.get("characters", [])):
    got = copied.get(f"ch{i}")
    if got != (ch.get("flow_prompt") or ""):
        bad_eq.append(f"인물{i + 1}")
ck("복사되는 글자가 원본과 **한 글자도** 다르지 않다", not bad_eq, ", ".join(bad_eq))
ck("%20 같은 URL 인코딩이 섞이지 않는다", not bad_enc, ", ".join(bad_enc))
ck("줄바꿈이 진짜 줄바꿈으로 남아 있다",
   all(copied.get(f"p1_{i}", "").count("\n") == 6 for i in range(1, len(e1["cuts"]) + 1)),
   "각 프롬프트 7줄")
ck("버튼으로 안 될 때 직접 복사할 길이 있다", "showCopySheet(" in ep1)
nepn = ep1.count('class="epn')
ck("1~16화 번호판이 다 있다", nepn == len(doc["episodes"]), f"{nepn}개")

print("\n④ 다른 화로 넘어가도 그 화 내용이 나오는가")
e16 = doc["episodes"][15]
ck("16화 제목이 뜬다", (e16.get("title") or "") in ep16, e16.get("title", ""))
ck("16화 1컷 대사가 뜬다",
   (e16["cuts"][0].get("subtitle") or "").replace('"', "&quot;") in ep16)
ck("1화 내용은 더 이상 안 보인다",
   (e1["cuts"][0]["prompt"].split("\n")[1][:40]) not in ep16)

print("\n" + "─" * 52)
print(f"❌ 시리즈 화면: {len(FAIL)}가지 실패" if FAIL else "✅ 시리즈 화면: 전부 통과")
sys.exit(1 if FAIL else 0)
