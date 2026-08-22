// 큰 파일 임시 보관함(KV)이 제대로 넣고 제대로 꺼내는가.
//
// 왜 이 검사가 있는가 (2026-08-22)
//   관리자 페이지의 깃허브 열쇠는 읽기 전용이라, 브라우저에서 올린 압축파일을
//   깃허브에 얹지 못했다(403). 그래서 파일을 클라우드플레어 보관함에 두고
//   워크플로가 받아 가게 바꿨다. 그 길이 **한 바이트도 안 틀리고** 오가는지
//   여기서 인터넷 없이 확인한다. 틀리면 영상이 깨진 채로 만들어진다.
//
//   쓰기: node tools/blob_test.mjs      인터넷 0회 · 0원 · 몇 초

import { writeFileSync, readFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

const src = readFileSync('admin/worker.js', 'utf8');
const mod = join(tmpdir(), 'vt-blob-test.mjs');
writeFileSync(mod,
  src.replace('export default', 'const _wk =')
  + '\nexport { _wk, bin, blobPutStream, blobPutText, blobText, blobUrl,'
  + ' KV_CHUNK, KV_MAX, sign };\n');
const W = await import('file://' + mod + '?t=' + Date.now());

let bad = 0;
const ok = (cond, what) => {
  if (cond) console.log('   ✅ ' + what);
  else { console.log('   ❌ ' + what); bad = 1; }
};

// ── 가짜 보관함 (진짜 KV 와 같은 모양으로만 굴린다) ──────────────
function fakeKV() {
  const m = new Map();
  return {
    _m: m,
    async put(k, v, opt) {
      if (typeof v === 'string') m.set(k, { s: v, opt });
      else {
        const b = v instanceof ArrayBuffer ? new Uint8Array(v) : new Uint8Array(v.buffer || v);
        if (b.length > 25 * 1024 * 1024) throw new Error('KV 한 값 상한(25MB)을 넘었다');
        m.set(k, { b: b.slice(), opt });
      }
    },
    async get(k, type) {
      const e = m.get(k);
      if (!e) return null;
      if (type === 'arrayBuffer')
        return e.b ? e.b.buffer.slice(e.b.byteOffset, e.b.byteOffset + e.b.length)
                   : new TextEncoder().encode(e.s).buffer;
      return e.s !== undefined ? e.s : new TextDecoder().decode(e.b);
    },
  };
}

// 20MB 짜리 시험용 파일 — 8MB 로 잘리므로 조각이 3개 나와야 한다
const N = 20 * 1024 * 1024;
const src20 = new Uint8Array(N);
for (let i = 0; i < N; i++) src20[i] = (i * 7 + (i >> 11)) & 0xff;

// 진짜처럼 **잘게 나뉘어** 흘러 들어오게 만든다 (브라우저 업로드가 그렇다)
function streamOf(bytes, piece) {
  let off = 0;
  return new ReadableStream({
    pull(c) {
      if (off >= bytes.length) { c.close(); return; }
      const end = Math.min(off + piece, bytes.length);
      c.enqueue(bytes.subarray(off, end));
      off = end;
    },
  });
}

console.log('⭐ 큰 파일 보관함: 넣은 그대로 꺼내지는가');

// ① 넣기 — 조각 수와 크기
const env = { BLOB: fakeKV(), ADMIN_PASSWORD: 'pw', SESSION_SECRET: 'sss' };
const total = await W.blobPutStream(env, streamOf(src20, 300 * 1024), 'clips/t-1', 60);
ok(total === N, `크기가 그대로다 (${total} 바이트)`);
const head = JSON.parse(await env.BLOB.get('clips/t-1'));
ok(head.parts === 3, `8MB 씩 조각냈다 (조각 ${head.parts}개)`);
ok(head.size === N, '머리글에 적힌 크기도 같다');

// ② 꺼내기 — **워커의 진짜 문(/api/blob)** 을 그대로 두드린다
const res = await W._wk.fetch(
  new Request('https://admin.example.workers.dev/api/blob?key=clips/t-1',
              { headers: { 'x-vt-pass': 'pw' } }), env);
ok(res.status === 200, '비밀번호를 대면 내려준다');
const back = new Uint8Array(await res.arrayBuffer());
ok(back.length === N, `내려받은 크기가 같다 (${back.length})`);
let same = back.length === N;
for (let i = 0; same && i < N; i++) if (back[i] !== src20[i]) same = false;
ok(same, '한 바이트도 안 틀린다');

// ③ 아무나 못 가져간다
const no = await W._wk.fetch(
  new Request('https://admin.example.workers.dev/api/blob?key=clips/t-1'), env);
ok(no.status === 401, '비밀번호 없이는 못 가져간다');
const wrong = await W._wk.fetch(
  new Request('https://admin.example.workers.dev/api/blob?key=clips/t-1',
              { headers: { 'x-vt-pass': 'nope' } }), env);
ok(wrong.status === 401, '틀린 비밀번호로도 못 가져간다');

// ④ 이상한 열쇠는 막는다 (남의 자리를 넘겨다보지 못하게)
for (const k of ['../secret', 'clips/../x', 'a/b/c', '', 'CLIPS/x']) {
  const r = await W._wk.fetch(
    new Request('https://admin.example.workers.dev/api/blob?key=' + encodeURIComponent(k),
                { headers: { 'x-vt-pass': 'pw' } }), env);
  if (r.status !== 400) { console.log(`   ❌ 이상한 열쇠를 받아 줬다: ${k} → ${r.status}`); bad = 1; }
}
ok(true, '이상한 열쇠는 다 막는다');

// ⑤ 없는 것은 404 (하루 지나 지워졌을 때)
const gone = await W._wk.fetch(
  new Request('https://admin.example.workers.dev/api/blob?key=clips/nope',
              { headers: { 'x-vt-pass': 'pw' } }), env);
ok(gone.status === 404, '없는 것은 없다고 말한다');

// ⑥ 짧은 글(한글 포함)도 그대로 오간다
const meta = JSON.stringify({ title: '판결극장 1화 — 「재판장」이 말했다', tags: ['판결'] });
await W.blobPutText(env, 'meta/short-S001-ep01', meta, 0);
ok(await W.blobText(env, 'meta/short-S001-ep01') === meta, '한글이 든 글도 그대로다');
ok(await W.blobText(env, 'meta/없는것') === null, '없는 글은 null 이다');

// ⑦ 보관함이 안 붙은 배포에서도 죽지 않는다 (옛 길로 가야 한다)
ok(W.bin({}) === null, '보관함이 없으면 없다고 말한다');
ok(await W.blobText({}, 'meta/x') === null, '보관함이 없어도 터지지 않는다');

// ⑧ 워크플로에 넘길 주소가 제 모양인가
const u = W.blobUrl(new Request('https://admin.example.workers.dev/api/upload-clips?ep=1'),
                    'clips/t-1');
ok(u === 'https://admin.example.workers.dev/api/blob?key=clips%2Ft-1',
   '주소가 제 모양이다 (' + u + ')');
ok(/^https:\/\/[^/]+\.workers\.dev\//.test(u),
   '워크플로가 받아 주는 주소다 (workers.dev 만 받는다)');

// ⑨ 너무 큰 것은 받다가 끊는다 (메모리를 지킨다)
try {
  const big = new Uint8Array(1024 * 1024);
  let sent = 0;
  const s = new ReadableStream({
    pull(c) { if (sent > W.KV_MAX + 2 * 1024 * 1024) { c.close(); return; }
              sent += big.length; c.enqueue(big); },
  });
  await W.blobPutStream({ BLOB: fakeKV() }, s, 'clips/big', 60);
  console.log('   ❌ 90MB 를 넘겼는데 그냥 받았다'); bad = 1;
} catch (e) {
  ok(String(e.message).includes('TOO_BIG'), '90MB 를 넘으면 받다가 끊는다');
}

// ⑩ ⭐ 가장 중요한 것 — [영상 올리기] 를 눌렀을 때 실제로 무슨 일이 벌어지는가.
//    깃허브에 파일을 얹으려 들면 안 되고(403 의 원인), 보관함에 두고
//    쇼츠 만들기를 **부르기만** 해야 한다. 깃허브 쪽은 가짜로 받아 적는다.
console.log('⭐ [영상 올리기] 를 누르면 깃허브에 쓰지 않고 보관함에 둔다');
const called = [];
const realFetch = globalThis.fetch;
globalThis.fetch = async (u, init) => {
  const s0 = String(u && u.url ? u.url : u);
  if (s0.includes('github.com')) {
    called.push({ url: s0, body: init && init.body ? JSON.parse(init.body) : null });
    return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
  }
  return realFetch(u, init);
};

const env2 = { BLOB: fakeKV(), ADMIN_PASSWORD: 'pw', SESSION_SECRET: 'sss', GH_TOKEN: 'x' };
const val = '1700000000000';
const cookie = 'vt=' + encodeURIComponent(val + '.' + await W.sign(env2, val));
const zip = new Uint8Array(3 * 1024 * 1024).fill(7);
const up = await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/upload-clips?sid=S001&ep=1',
  { method: 'POST', body: streamOf(zip, 256 * 1024), duplex: 'half',
    headers: { Cookie: cookie, 'Content-Length': String(zip.length) } }), env2);
const upj = await up.json();
ok(up.status === 200 && upj.ok, '올리기가 성공한다');
ok(upj.via === 'blob', '깃허브가 아니라 보관함으로 갔다 (via=' + upj.via + ')');
ok(!called.some((c) => c.url.includes('uploads.github.com')),
   '깃허브에 파일을 얹으려 들지 않는다 (403 이 날 자리가 없다)');
const disp = called.find((c) => c.url.includes('/dispatches'));
ok(!!disp && disp.url.includes('shorts.yml'), '쇼츠 만들기를 부른다');
ok(!!disp && /^https:\/\/[^/]+\.workers\.dev\/api\/blob\?key=/.test(disp.body.inputs.blob),
   '받아 갈 주소를 같이 넘긴다');
// 넘긴 주소로 진짜 받아지는가 (워크플로가 할 일을 그대로 해 본다)
const gotUrl = new URL(disp.body.inputs.blob);
const back2 = await W._wk.fetch(
  new Request(disp.body.inputs.blob, { headers: { 'x-vt-pass': 'pw' } }), env2);
ok(back2.status === 200 && (await back2.arrayBuffer()).byteLength === zip.length,
   '워크플로가 그 주소에서 압축파일을 그대로 받는다');
ok(gotUrl.pathname === '/api/blob', '주소가 보관함 문을 가리킨다');

// 한 컷만 시험할 때는 cut 도 같이 넘어가야 한다
called.length = 0;
const up2 = await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/upload-clips?sid=S001&ep=1&cut=3',
  { method: 'POST', body: streamOf(zip, 256 * 1024), duplex: 'half',
    headers: { Cookie: cookie } }), env2);
await up2.json();
const d2 = called.find((c) => c.url.includes('/dispatches'));
ok(!!d2 && d2.body.inputs.cut === '3', '한 컷 시험이면 컷 번호도 넘어간다');

// 로그인 안 한 사람은 못 올린다
const nope = await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/upload-clips?sid=S001&ep=1',
  { method: 'POST', body: 'x' }), env2);
ok(nope.status === 401, '로그인 안 하면 못 올린다');

// ⑪ 유튜브에 올릴 글 — 화면에서 고친 그대로 올라가는가.
//    여기도 깃허브에 쓰던 자리였다(403 의 두 번째 원인).
console.log('⭐ 올릴 글도 깃허브에 쓰지 않고 보관함으로 간다');
called.length = 0;
const form = { sid: 'S001', ep: 1, title: '「재판장」이 말했다', tags: ['판결', '상속'],
               description: '판결극장 1화', privacy: 'unlisted' };
const sv = await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/yt-save',
  { method: 'POST', body: JSON.stringify(form), headers: { Cookie: cookie } }), env2);
const svj = await sv.json();
ok(svj.ok && svj.via === 'blob', '올릴 글이 보관함에 담긴다');
ok(!called.some((c) => c.url.includes('uploads.github.com')),
   '올릴 글도 깃허브에 얹으려 들지 않는다');

// 다시 열어 보면 고친 그대로 나온다
const rd = await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/yt-meta?sid=S001&ep=1',
  { headers: { Cookie: cookie } }), env2);
const rdj = await rd.json();
ok(rdj.saved === true && rdj.title === form.title && rdj.privacy === 'unlisted',
   '다시 열면 고친 그대로 보인다');

// 올릴 때 그 글의 주소가 워크플로로 넘어간다 (보여드린 것 = 올라가는 것)
called.length = 0;
const uj = await (await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/yt-up',
  { method: 'POST', headers: { Cookie: cookie },
    body: JSON.stringify({ sid: 'S001', ep: 1, privacy: 'unlisted', dry: true }) }),
  env2)).json();
ok(uj.ok, '유튜브 올리기가 시작된다');
const d3 = called.find((c) => c.url.includes('/dispatches'));
ok(!!d3 && d3.url.includes('shorts-upload.yml'), '쇼츠 올리기 워크플로를 부른다');
ok(!!d3 && /\/api\/blob\?key=meta%2F/.test(d3.body.inputs.meta || ''),
   '화면에서 확인한 글의 주소를 같이 넘긴다');
// ⚠️ 늘 같은 이름을 넘기면 러너가 **고치기 전 것**을 받을 수 있다 (보관함은
//    전 세계에 퍼지는 데 최대 1분). 부를 때마다 새 이름이어야 한다.
ok(!!d3 && !d3.body.inputs.meta.includes('short-S001-ep01'),
   '늘 같은 이름이 아니라 새 이름으로 넘긴다 (옛것이 올라갈 자리가 없다)');
const pinned = decodeURIComponent(new URL(d3.body.inputs.meta).searchParams.get('key'));
const pinRes = await W._wk.fetch(
  new Request(d3.body.inputs.meta, { headers: { 'x-vt-pass': 'pw' } }), env2);
ok(pinRes.status === 200 && JSON.parse(await pinRes.text()).title === form.title,
   '새 이름으로도 방금 고친 그 글이 나온다 (' + pinned + ')');
// 두 번 부르면 이름이 달라야 한다
called.length = 0;
await (await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/yt-up',
  { method: 'POST', headers: { Cookie: cookie },
    body: JSON.stringify({ sid: 'S001', ep: 1, privacy: 'unlisted', dry: true }) }),
  env2)).json();
const d4 = called.find((c) => c.url.includes('/dispatches'));
ok(!!d4 && d4.body.inputs.meta !== d3.body.inputs.meta, '부를 때마다 새 이름이다');
ok(!!d3 && d3.body.inputs.mode === '연습 (올리지 않고 확인만)', '연습이면 연습으로 넘어간다');

// ⑫ 보관함이 붙어 있으면 "깃허브 쓰기 권한" 을 더 묻지 않는다
const cw = await (await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/can-write', { headers: { Cookie: cookie } }),
  env2)).json();
ok(cw.ok === true, '보관함이 있으면 올릴 수 있다고 말한다 (깃허브로 안 보낸다)');

globalThis.fetch = realFetch;

// ⑬ 화면 어디에도 "깃허브 가서 고치라" 는 말이 남아 있으면 안 된다 (운영자 지시)
//    ⚠️ 그물을 넓게 치면 'actions: read+write'(원래 있어야 한다)까지 걸린다.
//       Contents 바로 뒤에 쓰기가 붙은 것과, 토큰 설정 링크만 잡는다.
const nag = src.match(
  /[^\n]*(personal-access-tokens|[Cc]ontents\s*(?:=|:|을|를)?\s*[*[]{0,2}\s*[Rr]ead\s*(?:and|\+)\s*write)[^\n]*/g) || [];
ok(nag.length === 0, '깃허브에 가서 고치라는 안내가 화면에 없다'
   + (nag.length ? ' ← ' + nag[0].trim().slice(0, 80) : ''));

console.log('────────────────────────────────────────────────────');
console.log(bad ? '❌ 보관함 검사: 걸린 것이 있다' : '✅ 보관함 검사: 넣은 그대로 꺼내진다');
process.exit(bad);
