// ⭐⭐⭐ 관리자 페이지의 **창구(API)를 하나도 빼놓지 않고 진짜로 불러 본다.**
//
// 왜 이 검사가 있는가 (2026-09-10)
//   손님이 [전체 만들기] 를 눌렀더니 화면에 이렇게 떴다:
//     ReferenceError: Cannot access 'cards' before initialization
//   /api/make-short90 안에서 `const payload = JSON.stringify(cards)` 가
//   `const cards = {}` **위**에 있었다. 자바스크립트의 const 는 선언보다
//   앞에서 쓰면 그 자리에서 죽는다. 눈으로는 안 보인다 — 두 줄이 열세 줄
//   떨어져 있었고, 그 사이에 주석이 열 줄 있었다.
//
//   더 뼈아픈 것: 바로 그 자리에 **"sid 를 선언 전에 쓸 뻔했다"** 는 경고를
//   내가 직접 적어 두었고, 검사(cast_check)도 만들어 두었다. 그런데 그 검사는
//   `const sid` 와 `castOfDoc(` 의 **순서 한 쌍**만 봤다. 규칙이 아니라 사례를
//   적어 둔 것이라, 한 칸 옆(payload↔cards)에서 똑같은 일이 나도 조용했다.
//
//   → 그래서 이 검사는 **글을 읽지 않는다. 진짜로 돌린다.**
//      창구 목록도 손으로 적지 않고 worker.js 에서 뽑는다. 창구가 늘면
//      여기도 저절로 늘어난다.
//
//   쓰기: node tools/api_run_test.mjs      인터넷 0회 · 0원 · 몇 초
import { writeFileSync, readFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

const src = readFileSync('admin/worker.js', 'utf8');
const mod = join(tmpdir(), 'vt-api-run-test.mjs');
writeFileSync(mod, src.replace('export default', 'const _wk =')
  + '\nexport { _wk, sign };\n');
const W = await import('file://' + mod + '?t=' + Date.now());

let bad = 0;
const ok = (cond, what, why = '') => {
  if (cond) console.log('   ✅ ' + what);
  else { console.log('   ❌ ' + what + (why ? ' — ' + why : '')); bad = 1; }
};

// ── 창구 목록을 **소스에서 뽑는다** (손으로 적으면 새 창구가 빠진다) ──
const ROUTES = [...new Set(
  [...src.matchAll(/url\.pathname === '(\/api\/[a-z0-9-]+)'/g)].map(m => m[1]))];

// ── 가짜 바깥세상 ──────────────────────────────────────────────
const kv = new Map();
const env = {
  ADMIN_PASSWORD: 'pw', SESSION_SECRET: 'secret', GH_TOKEN: 'ghp_fake',
  BLOB: {
    async put(k, v) { kv.set(k, v); },
    async get(k, t) {
      const v = kv.get(k);
      if (v === undefined) return null;
      return t === 'arrayBuffer' ? new ArrayBuffer(0) : v;
    },
    async list() { return { keys: [], list_complete: true }; },
    async delete(k) { kv.delete(k); },
  },
};
// 바깥으로 나가는 것은 전부 가로챈다 — 인터넷 0회.
globalThis.fetch = async (u) => new Response(
  JSON.stringify({ ok: true, workflow_runs: [], content: '', sha: 'x' }),
  { status: 200, headers: { 'Content-Type': 'application/json' } });

// 로그인 쿠키 (창구 대부분이 로그인을 본다)
const cookie = 'vt=' + encodeURIComponent('u.' + await W.sign(env, 'u'));

// ⚠️ "죽었다" 로 볼 말들. 이 말이 나오면 **손님 화면에 그대로 뜬다.**
const DEAD = /ReferenceError|is not defined|before initialization|is not a function|Cannot read propert/;

async function hit(path, method, body) {
  const init = { method, headers: { Cookie: cookie } };
  if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  try {
    const r = await W._wk.fetch(new Request('https://x' + path, init), env);
    const t = await r.text();
    // ⚠️ 로그인 화면(HTML)에는 안내용 자바스크립트가 들어 있어 그 안의 글자가
    //    "죽었다" 로 잘못 읽힌다. **답이 JSON 일 때만** 글을 본다.
    const isJson = (r.headers.get('Content-Type') || '').includes('json');
    return { threw: null, text: isJson ? t : '' };
  } catch (e) {
    return { threw: String(e && e.stack ? e.stack : e), text: '' };
  }
}

// 창구마다 그럴듯한 몸통 하나. 없으면 빈 몸통으로 부른다.
const BODY = {
  '/api/make-short90': { sid: 'S92', part: '', video_kind: 'talk',
                         cards: { 아버지: 'https://x/a.png' }, clips: {} },
  '/api/make-story': { case_id: '601919', sid: 'S93' },
  '/api/edit-line': { sid: 'S92', cut: '38', turn: '0', text: '고친 말' },
  '/api/run': { step: 'all', sid: 'S92' },
  '/api/short90': { sid: 'S92' },
  '/api/yt-up': { sid: 'S92', part: '1' },
  '/api/yt-save': { sid: 'S92', part: '1', title: '제목' },
  '/api/card': { sid: 'S92' },
};

console.log('⭐ 관리자 창구를 하나도 안 빼고 진짜로 불러 본다 '
          + `(${ROUTES.length}개 · 인터넷 0회)\n`);

for (const p of ROUTES) {
  const body = BODY[p];
  const tries = body !== undefined
    ? [['POST', body]]
    : [['GET', undefined], ['POST', {}]];
  let dead = '';
  for (const [m, b] of tries) {
    const r = await hit(p + (m === 'GET' ? '?sid=S92&part=1&id=1&no=1' : ''), m, b);
    if (r.threw && DEAD.test(r.threw)) dead = r.threw.split('\n')[0];
    else if (DEAD.test(r.text)) dead = (r.text.match(DEAD) || [''])[0]
      + ' — ' + r.text.slice(0, 120);
  }
  ok(!dead, p + ' 가 죽지 않는다', dead);
}

console.log('\n' + '─'.repeat(60));
if (bad) {
  console.log('❌ 창구 하나가 손님 화면에서 죽는다 (위 빨간 줄)');
  process.exit(1);
}
console.log(`✅ 창구 ${ROUTES.length}개 전부 끝까지 돌았다 — 선언 전 사용 없음`);
