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
  // ⭐ 2026-08-23 — 복사본은 루미나용으로 다듬은 글이다. 파이썬 쪽에서 다시
  //    구현하면 두 벌이 되어 어긋나므로, **화면 코드가 만든 값**을 그대로 준다.
  out.lumina = {};
  (DOC.episodes[0].cuts || []).forEach((c, i) => {
    out.lumina['p1_' + (i + 1)] = luminaPrompt(String(c.prompt || ''));
  });
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
# ⭐ 후킹은 **첫 컷 앞 3초**에 크게 뜨는 한 줄이다. 영상을 만들기 전에
#    운영자가 반드시 눈으로 봐야 한다 (2026-08-20 운영자: "자극적으로 뽑아").
#    (2026-08-24 — 예전엔 내내 켜 뒀는데 얼굴을 덮어서 3초로 줄였다)
# ⚠️ 후킹의 별표는 **색 넣을 자리 표시**라 화면에는 안 나온다 (맨글자로 견준다)
HK_LABEL = "첫 3초 후킹"
_hk = S.hook_plain(e1.get("hook"))
ck("화면 맨 위 후킹이 보인다", _hk in ep1, _hk[:30] or "(비었다)")
ck("별표는 화면에 안 나온다", "*" not in _hk and (
    "*" not in ep1.split(HK_LABEL)[1][:200] if HK_LABEL in ep1 else True))
ck("후킹이라는 이름표가 붙어 있다", HK_LABEL in ep1)

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
# ⭐ 2026-08-23 — 복사되는 글은 원본 그대로가 아니라 **루미나용으로 다듬은 것**이다
#    (옷·화풍·목소리 묘사를 뺀다 — 루미나는 참조 그림이 그것을 정한다).
#    검사의 목적은 그대로다: 글자가 **깨지지 않는가**(URL 인코딩·줄바꿈 사고).
lumina = out.get("lumina") or {}
for i, c in enumerate(e1["cuts"], 1):
    got = copied.get(f"p1_{i}")
    if got != lumina.get(f"p1_{i}"):
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
# ⚠️ 줄 수를 숫자로 못 박아 두면 시험이 매번 깨진다. **다듬은 글과 견준다.**
#    (2026-08-23 — 이제 옷·화풍·소리 줄을 빼므로 원본보다 줄이 적은 게 정상이다)
ck("줄바꿈이 진짜 줄바꿈으로 남아 있다",
   all(copied.get(f"p1_{i}", "").count("\n")
       == (lumina.get(f"p1_{i}") or "").count("\n")
       for i in range(1, len(e1["cuts"]) + 1))
   and (lumina.get("p1_1") or "").count("\n") > 3,
   f"1컷 {copied.get('p1_1','').count(chr(10)) + 1}줄")

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
ck("클립보드에 들어간 글이 화면이 만든 글과 한 글자도 다르지 않다",
   cl.get("last") == lumina.get("p1_1"),
   "다름" if cl.get("last") != lumina.get("p1_1") else "")
ck("클립보드 글에 %20 같은 인코딩이 없다",
   not re.search(r"%[0-9A-Fa-f]{2}", cl.get("last") or ""))
ck("[안 되면 여기서] 같은 우회 단추가 없다", "showCopySheet(" not in ep1)

# ⭐ 2026-08-23 운영자 지시 — 옷은 참조 그림이 정하므로 글에서 뺀다.
#    "불필요한 부분은 오히려 삭제하는 게 더 맞을 거 같아."
_dirty = [k for k, v in lumina.items()
          if "wearing" in v or "VOICE:" in v or "AUDIO:" in v]
ck("복사되는 글에 옷·목소리 묘사가 없다 (참조 그림이 정한다)",
   not _dirty, " ".join(_dirty))
# ⭐⭐ 2026-08-24 — **색과 화풍은 절대 떼면 안 된다.**
#    2026-08-23 에 '레퍼런스가 화풍을 잡는다'고 COLOR·STYLE 을 떼었더니
#    회차마다 색감이 달라졌다(운영자: "1화랑 2화랑 왜 색감이 달라?").
#    레퍼런스는 **사람**을 잡지 장면의 색을 안 잡는다. 다시 떼면 여기서 걸린다.
_nocolor = [k for k, v in lumina.items() if "COLOR:" not in v]
ck("복사되는 글에 **색 지시**가 들어 있다 (빠지면 회차마다 색이 달라진다)",
   not _nocolor, " ".join(_nocolor))
_nostyle = [k for k, v in lumina.items() if "STYLE:" not in v]
ck("복사되는 글에 **화풍 지시**가 들어 있다", not _nostyle, " ".join(_nostyle))
ck("색 지시가 '회차를 넘어서' 같아야 한다고 못박는다",
   "every episode" in (lumina.get("p1_1") or ""),
   "한 화 안에서만 같으면 되는 것으로 읽힌다")
ck("연출과 대사는 그대로 남아 있다",
   all(x in (lumina.get("p1_1") or "") for x in ("SHOT:", "ACTION:", "DIALOGUE:", "SETTING:")))

c2 = out.get("clip2") or {}
ck("ClipboardItem 이 없는 기기에서는 두 번째 길로 넘어간다", c2.get("how") == "writeText",
   c2.get("how") or "안 넘어감")
ck("두 번째 길로 가도 글자는 그대로다",
   c2.get("last") == lumina.get("p1_1"))
nepn = ep1.count('class="epn')
ck("1~16화 번호판이 다 있다", nepn == len(doc["episodes"]), f"{nepn}개")

print("\n③-3 만든 영상을 올리는 칸이 있는가 (2026-08-20 운영자 지시)")
ck("클립 하나만 시험할 수 있다", 'id="cutone"' in ep1)
# ⚠️⚠️ 2026-08-22 — 압축파일을 다 올린 **뒤에** 이 오류를 봤다:
#    GitHub 403: "Resource not accessible by personal access token"
#    처음엔 "토큰 권한을 쓰기로 바꾸십시오" 라고 화면에 적었다가 크게 혼났다.
#    운영자는 깃허브에서 아무것도 하지 않는다 — 그게 이 시스템의 대전제다.
#
#    ⭐ 다시 보니 **예전에 되던 길에는 그 권한이 필요 없었다.**
#       영상은 깃허브 안(Actions)에서 만들어졌고 올리는 것도 워크플로 자신의
#       열쇠가 했다. 내가 브라우저→깃허브 직접 올리기를 새로 넣으면서 없던
#       권한이 필요해진 것이다. → 그 설계를 되돌렸다.
#       이제 파일은 클라우드플레어 보관함(KV)을 거치고, 깃허브 쓰기는 없다.
_js = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
ck("올릴 수 있는 상태인지 미리 알아본다", "permCheck" in _js and "api/can-write" in _js,
   "몇십 MB 를 다 올린 뒤 영어 오류를 보게 하면 안 된다")
ck("안내가 들어갈 자리가 있다", 'id="permwarn"' in ep1)
ck("준비가 안 됐으면 올리기를 막는다", "CANWRITE === false" in _js)
ck("올린 파일은 보관함으로 간다", "blobPutStream" in _js and "'/api/blob'" in _js,
   "깃허브에 직접 얹으면 읽기 전용 토큰에서 403 이 난다")
ck("보관함이 있으면 깃허브 쓰기를 안 묻는다", "if (bin(env)) return Response.json({ ok: true" in _js)
ck("막혔을 때 화면에서 바로 고친다", "setupBlob" in _js and "'/api/setup-blob'" in _js,
   "손님을 깃허브로 보내면 안 된다 (그러지 말라고 하셨다)")
# ⭐ 어디에도 "깃허브 가서 Contents 권한을 쓰기로 바꾸라" 는 말이 남으면 안 된다.
#    (actions 권한은 처음 한 번 만든 것이라 그대로 둔다 — 그건 이미 있다)
# ⚠️ 그물이 너무 넓으면 "actions: read+write" (그건 원래 있어야 한다) 까지
#    걸어 버린다. Contents **바로 뒤에** 쓰기가 붙은 것만 잡는다.
_NAG = re.compile(r"[Cc]ontents\s*(?:=|:|을|를)?\s*[*\[]{0,2}\s*[Rr]ead\s*(?:and|\+)\s*write")
for _f in ("admin/worker.js", ".github/workflows/deploy-admin.yml", "admin/wrangler.toml"):
    _t = (ROOT / _f).read_text(encoding="utf-8")
    ck(f"{_f}: Contents 권한을 바꾸라고 시키지 않는다", not _NAG.search(_t),
       "운영자는 깃허브에서 아무것도 하지 않는다")
# 브라우저에 뜨는 글에 토큰 설정 링크가 있으면 안 된다
ck("화면이 토큰 설정 페이지로 보내지 않는다", "personal-access-tokens" not in _js,
   "관리자 페이지가 유일한 조작 화면이다")

ck("압축파일 고르는 칸이 있다", 'id="clipzip"' in ep1 and 'accept=".zip' in ep1)
ck("올리기 단추가 있다", "upClips()" in ep1)
ck("완성된 쇼츠가 나올 자리가 있다", 'id="shortbox"' in ep1)
ck("고른 화 번호가 단추에 찍힌다", "1화 올리고 쇼츠 만들기" in ep1)

# ⭐⭐ 2026-08-24 운영자: "이 부분은 이제 불필요한 메뉴이니 삭제해."
#    루미나가 나레이션까지 만들어 주므로 목소리 만들기는 통째로 없앴다.
#    지운 것이 슬그머니 되살아나지 않는지 여기서 지킨다 — 되살아나면
#    쓰지도 않을 유료 열쇠가 다시 돌아다니게 된다.
print("\n③-4 없앤 목소리 메뉴가 되살아나지 않았는가 (2026-08-24)")
for _dead in ("makeVoice()", "pickVoice()", "pickShow()", "tcSave()",
              "id=\"vstyle\"", "id=\"voicebox\"", "id=\"tcform\"",
              "id=\"engbadge\"", "id=\"audbtn\""):
    ck(f"화면에 {_dead} 가 없다", _dead not in ep1, "지운 메뉴가 되살아났다")
_wk3 = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
for _dead in ("/api/voice", "/api/voicepick", "/api/tckey",
              "voice-sample.yml", "voice-pick.yml", "typecast.ai"):
    ck(f"서버에 {_dead} 길이 없다", _dead not in _wk3, "지운 길이 되살아났다")

wk = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
ck("서버에 올리는 길이 있다", "'/api/upload-clips'" in wk)
ck("완성본을 보는 길이 있다", "'/api/short'" in wk)
# ⭐ 2026-08-22 — 압축파일을 깃허브에 직접 올리던 길은 **지웠다.**
#    읽기 전용 열쇠로는 403 이 나고, 운영자는 깃허브에서 아무것도 하지 않는다.
#    이제 보관함에 두고 주소만 넘기면 워크플로가 자기 열쇠로 받아 간다.
ck("압축파일을 보관함에 둔다", "blobPutStream" in wk and "'/api/blob'" in wk)
ck("깃허브에 쓰는 길이 하나도 없다",
   "uploads.github.com" not in wk and "/releases`, {" not in wk,
   "길이 남아 있으면 언젠가 또 그리로 새어 403 이 난다")
ck("올린 뒤 쇼츠 만들기를 자동으로 부른다", "shorts.yml/dispatches" in wk)
ck("너무 큰 파일은 막는다", "90 * 1024 * 1024" in wk)

wf = ROOT / ".github" / "workflows" / "shorts.yml"
ck("쇼츠 워크플로가 있다", wf.exists())
if wf.exists():
    y = wf.read_text(encoding="utf-8")
    ck("워크플로가 압축파일을 받아 푼다", "release_file.py get" in y and "unzip" in y)
    ck("워크플로가 결과를 릴리스에 올린다", "release_file.py put" in y)
    # ⚠️ 2026-08-22 — 예전에는 "git commit 이라는 글자가 아예 없어야 한다" 로
    #    봤다. 그런데 **쓴 돈 장부(state/spend.json)** 는 커밋해서 남겨야 한다
    #    (안 남기면 깃허브 컨테이너와 함께 버려진다 — 실제로 그랬다).
    #    지켜야 할 규칙은 "커밋 금지" 가 아니라 **"영상 커밋 금지"** 다.
    _adds = [ln.strip() for ln in y.splitlines() if "git add" in ln]
    ck("완성 영상을 저장소에 커밋하지 않는다",
       all(("build" not in a) and (".mp4" not in a) for a in _adds),
       str(_adds))
    ck("장부처럼 작은 글 파일만 커밋한다",
       all(("state/" in a) or ("|| true" in a) for a in _adds) if _adds else True,
       str(_adds))

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
