// ⭐⭐⭐ 관리자 페이지 「올릴 글」 칸이 편마다 끝까지 차 있는가 — **진짜로 돌려 본다** (값 0원 · 인터넷 0회)
//
//   node tools/check_admin_meta.mjs
//
// 왜 필요한가 (2026-10-09 손님: "쇼츠 3편 같은 경우에는 제목이랑 내용이랑 해시태그 같은 게
//   아무것도 안 들어가 있어서 예약 업로드가 안 돼." · "뭐 이런 어처구니 없는 실수를 하니?")
//
//   손님이 1편(10/7) · 2편(10/8)을 **한 편씩** 올리셨다. 한 편만 올릴 때 화면은 그 편 글만
//   보내고, 워커는 그것을 'meta/<사건>' 에 **통째로** 저장해 1~3편 글을 덮었다. 화면을 다시
//   열면 /api/yt90 이 그 저장된 기록을 **먼저** 줘서 3편 칸이 비었고, [올리기]가
//   「3편 제목이 비었습니다」로 막혔다. (올리기 워크플로는 저장소 글만 써서 문제가 없었다 —
//   화면과 올리기가 **서로 다른 곳**을 보고 있었던 것이 뿌리다.)
//
//   예전 검사(yt90_check)는 worker.js 에 낱말이 **있는지만** 봤다. 낱말은 다 있었다.
//   그래서 이번에는 워커를 실제로 불러, 손님이 하신 순서 그대로 돌려 본다:
//     ① 1편만 올리기 → ② 2편만 올리기 → ③ 화면 다시 열기(/api/yt90)
//     → 1·2·3편 칸이 **저장소 글 그대로** 다 차 있어야 한다.

import { writeFileSync, readFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import { webcrypto } from 'crypto';

const subtle = (globalThis.crypto || webcrypto).subtle;
const bad = [];
const ck = (name, ok, why = '') => {
  console.log((ok ? '   ✅ ' : '   ❌ ') + name + (!ok && why ? ' — ' + why : ''));
  if (!ok) bad.push(name);
};

// 워커를 모듈로 불러온다 (check_admin.mjs 와 같은 방법)
const src = readFileSync('admin/worker.js', 'utf8');
const mod = join(tmpdir(), 'vt-worker-meta-check.mjs');
writeFileSync(mod, src.replace('export default', 'const _wk =') + '\nexport { _wk };\n');
const { _wk } = await import('file://' + mod + '?t=' + Date.now());

// ── 가짜 보관함(KV) · 가짜 깃허브 ────────────────────────────────
const store = new Map();
const KV = {
  async get(k) { return store.has(k) ? store.get(k) : null; },
  async put(k, v) { store.set(k, typeof v === 'string' ? v : String(v)); },
  async delete(k) { store.delete(k); },
  async list() { return { keys: [...store.keys()].map((name) => ({ name })) }; },
};
const SID = 'S777';
const REPO_META = {
  sid: SID,
  parts: [1, 2, 3].map((n) => ({
    part: n, title: `저장소 제목 ${n}편 #유류분`, description: `저장소 설명 ${n}편`,
    tags: ['사연', '유류분'], privacy: 'private', card: ['위', '아래'],
  })),
};
let repoHasMeta = true;
let dispatched = 0;
const realFetch = globalThis.fetch;
globalThis.fetch = async (url, init = {}) => {
  const u = String(url);
  if (u.includes(`/contents/data/series/${SID}.meta.json`)) {
    if (!repoHasMeta) return new Response('{"message":"Not Found"}', { status: 404 });
    const content = Buffer.from(JSON.stringify(REPO_META), 'utf8').toString('base64');
    return new Response(JSON.stringify({ content }), { status: 200 });
  }
  if (u.includes('/actions/workflows/short90-upload.yml/dispatches')) {
    dispatched += 1;
    return new Response(null, { status: 204 });
  }
  return new Response('{"message":"Not Found"}', { status: 404 });
};

const env = { ADMIN_PASSWORD: 'pw', SESSION_SECRET: 'secret', GH_TOKEN: 't', BLOB: KV };
// 로그인 쿠키 (워커의 sign() 과 같은 셈)
const key = await subtle.importKey('raw', new TextEncoder().encode(env.SESSION_SECRET),
  { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
const val = 'ok';
const mac = [...new Uint8Array(await subtle.sign('HMAC', key, new TextEncoder().encode(val)))]
  .map((b) => b.toString(16).padStart(2, '0')).join('');
const COOKIE = 'vt=' + encodeURIComponent(val + '.' + mac);
const BASE = 'https://admin.example';

async function call(path, body) {
  const init = { method: body ? 'POST' : 'GET', headers: { Cookie: COOKIE } };
  if (body) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }
  const r = await _wk.fetch(new Request(BASE + path, init), env);
  let j = null;
  try { j = await r.json(); } catch (e) { j = null; }
  return { status: r.status, j };
}

// 화면이 한 편만 올릴 때 보내는 꼴 그대로 (doUpload → parts: [body])
const one = (n) => ({ sid: SID, part: String(n), privacy: '공개 (모두에게)',
  when: '예약 — 한국 아침 8시 (권장)', dry: false,
  parts: [{ part: n, title: `화면 제목 ${n}편`, description: `화면 설명 ${n}편`, tags: ['사연'] }] });

console.log('⭐ 관리자 페이지 올릴 글 칸 — 한 편씩 올린 뒤에도 편마다 차 있는가 (값 0원)\n');

console.log('① 손님이 하신 순서 그대로: 1편만 올리기 → 2편만 올리기 → 화면 다시 열기');
const u1 = await call('/api/upload-short90', one(1));
const u2 = await call('/api/upload-short90', one(2));
ck('1편 · 2편 따로 올리기가 받아들여진다', u1.j && u1.j.ok && u2.j && u2.j.ok && dispatched === 2,
   JSON.stringify([u1, u2]).slice(0, 200));
const v = await call(`/api/yt90?sid=${SID}`);
const parts = (v.j && v.j.meta && v.j.meta.parts) || [];
for (const n of [1, 2, 3]) {
  const p = parts.find((x) => parseInt(x.part, 10) === n) || {};
  ck(`${n}편 칸이 차 있다 (제목 · 설명 · 해시태그)`,
     !!(p.title && p.description && (p.tags || []).length), JSON.stringify(p).slice(0, 160));
  ck(`${n}편 칸은 저장소 글 그대로다 (올리기 워크플로가 쓰는 글과 같다)`,
     p.title === `저장소 제목 ${n}편 #유류분`, String(p.title));
}

console.log('\n② 저장된 기록이 남은 편 글을 지우지 않는가');
let kept = null;
try { kept = JSON.parse(store.get(`meta/${SID}.0`) || 'null'); } catch (e) { kept = null; }
const keptNos = ((kept && kept.parts) || []).map((x) => parseInt(x.part, 10)).sort();
ck('2편만 올린 뒤에도 기록에 1편 · 2편이 둘 다 남는다', JSON.stringify(keptNos) === '[1,2]',
   JSON.stringify(keptNos));

console.log('\n③ 저장소 글이 없을 때만 저장된 기록을 보여 준다');
repoHasMeta = false;
const w = await call(`/api/yt90?sid=${SID}`);
const wp = ((w.j && w.j.meta && w.j.meta.parts) || []).map((x) => parseInt(x.part, 10)).sort();
ck('저장소 글이 없으면 저장된 기록(1·2편)을 보여 준다', w.j && w.j.saved === true
   && JSON.stringify(wp) === '[1,2]', JSON.stringify(w.j).slice(0, 160));

globalThis.fetch = realFetch;
console.log('\n' + '─'.repeat(60));
if (bad.length) {
  console.log(`❌ ${bad.length}개 걸렸습니다 — 손님 화면의 올릴 글 칸이 빈다`);
  process.exit(1);
}
console.log('✅ 관리자 올릴 글 칸: 한 편씩 올려도 편마다 저장소 글 그대로 차 있다');
