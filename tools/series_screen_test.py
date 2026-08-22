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
sys.path.insert(0, str(ROOT / "src"))
import series as S                                          # noqa: E402
import charsheet as CS                                      # noqa: E402

FAIL = []


def esc(t):
    """화면은 & < > \" 를 바꿔 넣는다 — 견줄 때도 같이 바꾼다."""
    return (str(t).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


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
const run = new Function('DOC', 'SIDIN', 'CLIP', 'navigator', 'Blob', 'ClipboardItemIn',
  'let ClipboardItem = ClipboardItemIn;' + js + `
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

  // ⭐ 진짜로 단추를 눌러 본다 — 클립보드에 무엇이 들어가는지 붙잡는다
  SEP = 1; seriesRender();
  copyRaw('p1_1', '1컷');
  out.clip = JSON.parse(JSON.stringify(CLIP));
  // ClipboardItem 이 없는 기기에서도 두 번째 길로 제대로 넘어가는가
  CLIP.last = null; CLIP.how = null;
  ClipboardItem = undefined;
  copyRaw('p1_1', '1컷');
  out.clip2 = JSON.parse(JSON.stringify(CLIP));
  return out;
`);

// 아이폰이 쓰는 길(write + ClipboardItem)을 흉내 낸다
class FakeBlob {
  constructor(parts, opts) { this.text = parts.join(''); this.type = (opts || {}).type || ''; }
}
class FakeItem {
  constructor(map) { this.map = map; }
}
const fakeNav = {
  clipboard: {
    write: (items) => {
      const it = items[0];
      clip.kinds = Object.keys(it.map);
      const b = it.map['text/plain'];
      clip.last = b ? b.text : null;
      clip.blobType = b ? b.type : null;
      clip.how = 'write';
      return Promise.resolve();
    },
    writeText: (t) => { clip.last = t; clip.how = 'writeText'; return Promise.resolve(); },
  },
};
console.log(JSON.stringify(run(doc, process.argv[3], clip, fakeNav, FakeBlob, FakeItem)));
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
    # 이제 화면에는 원문이 아니라 **풀세트로 늘린 것**이 뜬다
    want = (c.get("flow_sheet") or c.get("flow_prompt") or "")
    ck(f"{c['name']} 기준 사진 프롬프트가 통째로 들어 있다",
       all(esc(x) in ep1 for x in want.split("\n") if x.strip()),
       f"{len(want.split())}낱말")

print("\n③ 1화 5컷 — 이걸 그대로 플로우에 붙여 넣는다")
e1 = doc["episodes"][0]
for c in e1["cuts"]:
    # 프롬프트 6줄이 한 줄도 빠짐없이 화면에 있어야 한다
    lines = [l for l in c["prompt"].split("\n") if l.strip()]
    miss = [l[:26] for l in lines
            if l.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
               .replace('"', "&quot;") not in ep1]
    ck(f"{c['n']}컷 프롬프트 {len(lines)}줄이 전부 있다", not miss, ("빠짐: " + str(miss)) if miss else "")
# ⭐ 후킹은 30초 내내 화면 맨 위에 붙는 한 줄이다. 영상을 만들기 전에
#    운영자가 반드시 눈으로 봐야 한다 (2026-08-20 운영자: "자극적으로 뽑아").
# ⚠️ 후킹의 별표는 **색 넣을 자리 표시**라 화면에는 안 나온다 (맨글자로 견준다)
_hk = S.hook_plain(e1.get("hook"))
ck("화면 맨 위 후킹이 보인다", _hk in ep1, _hk[:30] or "(비었다)")
ck("별표는 화면에 안 나온다", "*" not in _hk and (
    "*" not in ep1.split("화면 맨 위 후킹")[1][:200] if "화면 맨 위 후킹" in ep1 else True))
ck("후킹이라는 이름표가 붙어 있다", "화면 맨 위 후킹" in ep1)

ck("컷마다 복사 버튼이 있다", ep1.count("copyRaw(") >= len(e1["cuts"]),
   f"{ep1.count('copyRaw(')}개")

print("\n③-2 실제로 복사되는 글자가 원본과 같은가 (URL 인코딩 사고 재발 방지)")
copied = out.get("copied", {})
ck("복사할 원본이 화면마다 담긴다", len(copied) >= len(e1["cuts"]), f"{len(copied)}개")

print("\n②-2 인물 프롬프트가 풀세트인가 (2026-08-20 운영자 지시)")
for i, ch in enumerate(doc.get("characters", [])):
    sheet = copied.get(f"chs{i}", "")
    ck(f"{ch['name']} 기준 사진 프롬프트가 충분히 길다", len(sheet.split()) >= 90,
       f"{len(sheet.split())}낱말")
    # ⚠️ 줄 이름을 글자로 베끼지 않는다 — 코드에서 가져온다 (FRAMING → FRAME)
    for need, why in [(CS.BACKDROP, "배경을 안 정하면 아무거나 뜬다"),
                      (CS.POSE, "자세를 안 정하면 매번 다르게 선다"),
                      (CS.FRAME, "어디까지 보일지 안 정하면 잘린다"),
                      (CS.LIGHT, "빛을 안 정하면 색이 튄다"),
                      (CS.AVOID, "소품·글자·다른 사람이 끼어든다")]:
        ck(f"{ch['name']} — {need[:22]}… ({why})", need in sheet)
    ck(f"{ch['name']} 캐릭터 설명도 따로 있다",
       bool(copied.get(f"chd{i}", "").strip())
       and copied.get(f"chd{i}") != sheet)
ck("설명 복사 단추가 있다", "설명 복사" in ep1)
ck("사진 프롬프트 복사 단추가 있다", "사진 프롬프트 복사" in ep1)
bad_enc, bad_eq = [], []
for i, c in enumerate(e1["cuts"], 1):
    got = copied.get(f"p1_{i}")
    if got != (c.get("prompt") or ""):
        bad_eq.append(f"{i}컷")
    if got and re.search(r"%[0-9A-Fa-f]{2}", got):
        bad_enc.append(f"{i}컷")
for i, ch in enumerate(doc.get("characters", [])):
    # 인물은 두 가지를 복사한다 — ① 캐릭터 설명 ② 기준 사진 프롬프트
    if copied.get(f"chd{i}") != (ch.get("flow_desc") or ch.get("flow_prompt") or ""):
        bad_eq.append(f"인물{i + 1} 설명")
    if copied.get(f"chs{i}") != (ch.get("flow_sheet") or ch.get("flow_prompt") or ""):
        bad_eq.append(f"인물{i + 1} 사진")
ck("복사되는 글자가 원본과 **한 글자도** 다르지 않다", not bad_eq, ", ".join(bad_eq))
ck("%20 같은 URL 인코딩이 섞이지 않는다", not bad_enc, ", ".join(bad_enc))
# ⚠️ 줄 수를 숫자로 못 박아 두면 줄이 하나 늘 때마다 시험이 깨진다
#    (머리말 · VOICE · AUDIO 를 붙일 때마다 실제로 깨졌다). **대본과 견준다.**
ck("줄바꿈이 진짜 줄바꿈으로 남아 있다",
   all(copied.get(f"p1_{i}", "").count("\n") == e1["cuts"][i - 1]["prompt"].count("\n")
       for i in range(1, len(e1["cuts"]) + 1)),
   f"컷마다 {e1['cuts'][0]['prompt'].count(chr(10)) + 1}줄")

# ⭐⭐ 2026-08-20 두 번째 사고 — 우리 클립보드는 멀쩡한데, **붙여 넣는 쪽**이
#    `SHOT:` 을 주소 이름(http: 같은 것)으로 읽어 글자를 통째로 %20 · %EB.. 로
#    바꿔 놓았다. 그래서 복사되는 글이 주소로 읽히는지를 직접 재 본다.
url_like = [k for k, v in copied.items() if S.looks_like_url(v)]
ck("복사되는 글이 '단어:' 로 시작하지 않는다 (주소로 읽힌다)",
   not url_like, " ".join(url_like))
ck("컷 프롬프트가 머리말로 시작한다",
   all(copied.get(f"p1_{i}", "").startswith(S.HEAD_FIX)
       for i in range(1, len(e1["cuts"]) + 1)), S.HEAD_FIX)
cl = out.get("clip") or {}
ck("단추를 누르면 클립보드에 실제로 들어간다", bool(cl.get("last")), cl.get("how") or "안 들어감")
ck("아이폰이 쓰는 길(write + ClipboardItem)로 넣는다", cl.get("how") == "write",
   cl.get("how") or "")
ck("글자 꼴을 text/plain 하나로만 못 박는다",
   cl.get("kinds") == ["text/plain"] and cl.get("blobType") == "text/plain",
   f"{cl.get('kinds')} · {cl.get('blobType')}")
ck("클립보드에 들어간 글이 원본과 한 글자도 다르지 않다",
   cl.get("last") == (e1["cuts"][0].get("prompt") or ""),
   "다름" if cl.get("last") != (e1["cuts"][0].get("prompt") or "") else "")
ck("클립보드 글에 %20 같은 인코딩이 없다",
   not re.search(r"%[0-9A-Fa-f]{2}", cl.get("last") or ""))
ck("[안 되면 여기서] 같은 우회 단추가 없다", "showCopySheet(" not in ep1)

c2 = out.get("clip2") or {}
ck("ClipboardItem 이 없는 기기에서는 두 번째 길로 넘어간다", c2.get("how") == "writeText",
   c2.get("how") or "안 넘어감")
ck("두 번째 길로 가도 글자는 그대로다",
   c2.get("last") == (e1["cuts"][0].get("prompt") or ""))
nepn = ep1.count('class="epn')
ck("1~16화 번호판이 다 있다", nepn == len(doc["episodes"]), f"{nepn}개")

print("\n③-3 만든 영상을 올리는 칸이 있는가 (2026-08-20 운영자 지시)")
# ⭐ 2026-08-21 — 목소리는 클립 5개를 다 만들기 전에 들어 봐야 한다
ck("목소리 들어보기 단추가 있다", "makeVoice()" in ep1)
ck("들을 자리가 있다", 'id="voicebox"' in ep1)
# ⚠️ 2026-08-22 — 예전에는 "값 0원" 이라고 적혀 있는지 봤다. 그런데 목소리를
#    무료 등급(하루 10번)에서 **결제 계정**으로 옮긴 뒤로 0원이 아니다.
#    화면이 거짓말을 하면 안 되므로, 값이 **얼마든 적혀 있는지**를 본다.
ck("값이 얼마인지 알려 준다", "원" in ep1 and ("1원 미만" in ep1 or "0원" in ep1),
   "누르면 돈이 나가는데 화면에 안 적혀 있으면 안 된다")
# ⭐ 2026-08-22 — 말투 결을 운영자가 귀로 고른다 (내가 혼자 골랐다가 틀렸다)
ck("말투 결을 고를 수 있다", 'id="vstyle"' in ep1)
for _s in ("drama", "fierce", "dry", "deep"):
    ck(f"결 '{_s}' 를 고를 수 있다", f'value="{_s}"' in ep1)
ck("클립 하나만 시험할 수 있다", 'id="cutone"' in ep1)

ck("압축파일 고르는 칸이 있다", 'id="clipzip"' in ep1 and 'accept=".zip' in ep1)
ck("올리기 단추가 있다", "upClips()" in ep1)
ck("완성된 쇼츠가 나올 자리가 있다", 'id="shortbox"' in ep1)
ck("고른 화 번호가 단추에 찍힌다", "1화 올리고 쇼츠 만들기" in ep1)

wk = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
ck("서버에 올리는 길이 있다", "'/api/upload-clips'" in wk)
ck("목소리 견본을 만드는 길이 있다", "'/api/voice'" in wk)
ck("목소리 워크플로를 부른다", "voice-sample.yml/dispatches" in wk)
ck("목소리를 소리 파일로 흘려보낸다", "audio/mpeg" in wk)
ck("완성본을 보는 길이 있다", "'/api/short'" in wk)
ck("압축파일을 **릴리스**에 올린다 (저장소 커밋 금지)",
   "uploads.github.com" in wk and "releases" in wk)
ck("올린 뒤 쇼츠 만들기를 자동으로 부른다", "shorts.yml/dispatches" in wk)
ck("너무 큰 파일은 막는다", "90 * 1024 * 1024" in wk)

wf = ROOT / ".github" / "workflows" / "shorts.yml"
ck("쇼츠 워크플로가 있다", wf.exists())
if wf.exists():
    y = wf.read_text(encoding="utf-8")
    ck("워크플로가 압축파일을 받아 푼다", "release_file.py get" in y and "unzip" in y)
    ck("워크플로가 결과를 릴리스에 올린다", "release_file.py put" in y)
    ck("완성 영상을 저장소에 커밋하지 않는다",
       "git commit" not in y and "push.sh" not in y)

print("\n③-4 유튜브 올리기 설정이 붙어 있는가 (2026-08-20 운영자 지시)")
wk = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
ck("올릴 글을 만들어 주는 길이 있다", "'/api/yt-meta'" in wk)
ck("고친 글을 저장하는 길이 있다", "'/api/yt-save'" in wk)
ck("올리기를 시작하는 길이 있다", "'/api/yt-up'" in wk)
ck("제목·설명·해시태그를 고칠 수 있다",
   "id=\"ytt\"" in wk and "id=\"ytd\"" in wk and "id=\"ytg\"" in wk)
ck("공개 범위를 고를 수 있다", "id=\"ytp\"" in wk and "unlisted" in wk)
ck("연습(안 올리고 확인만) 이 있다", "ytUp(true)" in wk)
ck("전체 공개는 한 번 더 묻는다", "전체 공개로 올립니다" in wk)
wf = ROOT / ".github" / "workflows" / "shorts-upload.yml"
ck("올리기 워크플로가 있다", wf.exists())
if wf.exists():
    y = wf.read_text(encoding="utf-8")
    ck("화면에서 고친 글을 먼저 쓴다", "meta.json build/meta.json" in y)
    ck("없으면 대본에서 만든다", "src/ytmeta.py" in y)
    ck("영상은 릴리스에서 꺼낸다", "release_file.py get" in y)
    ck("완성 영상을 저장소에 커밋하지 않는다", "git add build" not in y)

print("\n④ 다른 화로 넘어가도 그 화 내용이 나오는가")
e16 = doc["episodes"][15]
ck("16화 제목이 뜬다", (e16.get("title") or "") in ep16, e16.get("title", ""))
ck("16화 1컷 대사가 뜬다",
   (e16["cuts"][0].get("subtitle") or "").replace('"', "&quot;") in ep16)
# ⚠️ 예전엔 `split("\n")[1]` 로 두 번째 줄을 봤는데, 머리말이 생기면서 그 자리가
#    `SHOT:` (16화에도 똑같이 있는 줄) 로 밀렸다. 줄 이름으로 집는다.
# ⚠️ DIALOGUE 줄 **앞머리**는 모든 화가 똑같다(한국어로 말하라는 고정 문구).
#    그 화에만 있는 것은 **따옴표 안 대사**다. 그것으로 견준다.
_say1 = S.dia_says(e1["cuts"][0]["prompt"])[0]
ck("1화 내용은 더 이상 안 보인다", _say1 not in ep16, _say1[:30])

print("\n" + "─" * 52)
print(f"❌ 시리즈 화면: {len(FAIL)}가지 실패" if FAIL else "✅ 시리즈 화면: 전부 통과")
sys.exit(1 if FAIL else 0)
