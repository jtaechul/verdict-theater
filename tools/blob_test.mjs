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

// ⚠️⚠️ 2026-08-22 — **쇼츠 만들기가 여기서 죽었다.**
//    컷을 안 골랐는데도 cut="0" 이 넘어가, 워크플로가 "한 컷만 시험" 길로
//    빠져 `❌ 1화에 0컷이 없다` 로 끝났다. 5컷을 다 올려도 완성본이
//    한 번도 안 나온 까닭이다. 글자 "0" 은 자바스크립트에서 '참'이다.
ok(!!disp && !('cut' in disp.body.inputs),
   '컷을 안 고르면 cut 을 아예 안 넘긴다'
   + (disp && 'cut' in disp.body.inputs ? ' ← cut=' + disp.body.inputs.cut : ''));
ok(!!disp && !disp.body.inputs.blob.includes('-cut'),
   '이름에도 -cut0 이 안 붙는다');

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

// ⑩-b ⭐ 타입캐스트 열쇠 (2026-08-23 운영자: "typecast 로 바꿔볼까? API 있음")
//    열쇠는 관리자 페이지에서 넣고, 진짜인지 그 자리에서 확인하고,
//    워크플로에는 **주소만** 넘어간다 (열쇠 값이 실행 기록에 보이면 안 된다).
console.log('⭐ 타입캐스트 열쇠 — 담고, 확인하고, 값은 안 새는가');
const tcCalls = [];
globalThis.fetch = async (u, init) => {
  const s0 = String(u && u.url ? u.url : u);
  if (s0.includes('api.typecast.ai/v1/voices')) {
    tcCalls.push({ url: s0, key: init && init.headers && init.headers['X-API-KEY'] });
    const bad = tcCalls[tcCalls.length - 1].key === 'wrong';
    return new Response(bad ? '{}' : JSON.stringify({ result: [{ voice_id: 'tc_1' },
      { voice_id: 'tc_2' }] }), { status: bad ? 401 : 200,
      headers: { 'Content-Type': 'application/json' } });
  }
  if (s0.includes('github.com')) {
    called.push({ url: s0, body: init && init.body ? JSON.parse(init.body) : null });
    return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
  }
  return realFetch(u, init);
};
// 틀린 열쇠는 담기지 않는다
let tj = await (await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/tckey',
  { method: 'POST', headers: { Cookie: cookie },
    body: JSON.stringify({ key: 'wrong' }) }), env2)).json();
ok(tj.ok === false, '틀린 열쇠는 거절한다 (' + (tj.error || '') + ')');
ok(await W.blobText(env2, 'voice/tckey') === null, '틀린 열쇠는 담기지 않는다');
// 맞는 열쇠는 담기고, 목소리 수를 알려 준다
tj = await (await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/tckey',
  { method: 'POST', headers: { Cookie: cookie },
    body: JSON.stringify({ key: 'tk_good' }) }), env2)).json();
ok(tj.ok === true && tj.n === 2, '맞는 열쇠는 담고 목소리 수를 센다 (' + tj.n + '개)');
ok(await W.blobText(env2, 'voice/tckey') === 'tk_good', '보관함에 담긴다');
// 상태를 물어봐도 열쇠 값은 안 나온다
const tst = await (await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/tckey?t=1',
  { headers: { Cookie: cookie } }), env2)).json();
ok(tst.have === true && !JSON.stringify(tst).includes('tk_good'),
   '상태에 열쇠 값이 안 실린다');
// 영상 올리기가 열쇠 **주소**를 워크플로에 넘긴다 (값이 아니라)
called.length = 0;
await (await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/upload-clips?sid=S001&ep=1',
  { method: 'POST', body: streamOf(zip, 256 * 1024), duplex: 'half',
    headers: { Cookie: cookie } }), env2)).json();
const dtc = called.find((c) => c.url.includes('shorts.yml'));
ok(!!dtc && /\/api\/blob\?key=voice%2F/.test(dtc.body.inputs.tckey || ''),
   '워크플로에 열쇠 주소를 넘긴다');
ok(!!dtc && !JSON.stringify(dtc.body).includes('tk_good'),
   '열쇠 값 자체는 워크플로 입력에 안 싣는다 (실행 기록에 보이면 안 된다)');

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

// ⑮ ⭐ 만든 영상을 **아이폰이 실제로 재생할 수 있는가.**
//    2026-08-22 운영자: "만든 영상은 어디서 볼 수 있는 건데? 메뉴가 없는데?"
//    보는 곳이 없기도 했고, 있었어도 못 봤을 것이다 — 아이폰 사파리는
//    "몇 번째 바이트부터" 를 먼저 묻는데(Range) /api/short 는 그걸 무시하고
//    통째로 내려보내고 있었다. 그러면 재생이 시작되지 않는다.
console.log('⭐ 만든 영상: 목록이 보이고, 아이폰이 재생할 수 있는가');
const ASSET = 999123;
let sawRange = null;
globalThis.fetch = async (u, init) => {
  const s0 = String(u && u.url ? u.url : u);
  const hdr = (init && init.headers) || {};
  if (s0.includes('/releases/tags/short-S001-ep01'))
    return Response.json({ id: 1, assets: [
      { name: 'short.mp4', id: ASSET, size: 4_200_000, updated_at: '2026-08-22T15:00:00Z' }] });
  if (s0.includes('/releases/assets/' + ASSET))
    return new Response(null, { status: 302,
      headers: { Location: 'https://objects.example.com/short.mp4' } });
  if (s0.startsWith('https://objects.example.com/')) {
    sawRange = hdr.Range || hdr.range || null;
    return new Response('0123456789', { status: 206, headers: {
      'Content-Range': 'bytes 0-9/4200000', 'Content-Length': '10' } });
  }
  if (s0.includes('/releases?per_page='))
    return Response.json([
      { tag_name: 'short-S001-ep01', published_at: '2026-08-22T15:00:00Z',
        assets: [{ name: 'short.mp4', id: 1, size: 4_200_000,
                   updated_at: '2026-08-22T15:00:00Z' }] },
      { tag_name: 'short-S001-ep02-cut3', published_at: '2026-08-22T14:00:00Z',
        assets: [{ name: 'short.mp4', id: 2, size: 900_000,
                   updated_at: '2026-08-22T14:00:00Z' }] },
      { tag_name: 'clips-S001-ep01', assets: [{ name: 'clips.zip', id: 3, size: 5 }] },
      { tag_name: 'short-S001-ep09', assets: [] },
    ]);
  if (s0.includes('/contents/state/series.json'))
    return Response.json({ content: Buffer.from(JSON.stringify(
      { S001: { title: '바람난 남편이 빼돌린 15억' } }), 'utf8').toString('base64') });
  if (s0.includes('github.com')) return new Response('{}', { status: 200 });
  return realFetch(u, init);
};

const vres = await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/short?sid=S001&ep=1&play=1',
  { headers: { Cookie: cookie, Range: 'bytes=0-9' } }), env2);
ok(sawRange === 'bytes=0-9', '아이폰이 물어본 구간을 그대로 넘긴다 (' + sawRange + ')');
ok(vres.status === 206, '구간만 내려준다 (206)');
ok(vres.headers.get('Accept-Ranges') === 'bytes', '구간을 받는다고 알려 준다');
ok(vres.headers.get('Content-Range') === 'bytes 0-9/4200000', '어디부터 어디까지인지 알려 준다');
ok(vres.headers.get('Content-Type') === 'video/mp4', '영상이라고 알려 준다');

// ⚠️ 완성된 쇼츠를 찾는 자리에도 같은 실수가 있었다 —
//    'short-S001-ep01-cut0' 을 찾으니 만들어져 있어도 "아직 없습니다" 였다.
let askedTag = '';
const oldFetch2 = globalThis.fetch;
globalThis.fetch = async (u, init) => {
  const s1 = String(u && u.url ? u.url : u);
  const m1 = s1.match(/\/releases\/tags\/([^?]+)/);
  if (m1) { askedTag = decodeURIComponent(m1[1]); return Response.json({ id: 1, assets: [] }); }
  return oldFetch2(u, init);
};
await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/short?sid=S001&ep=1',
  { headers: { Cookie: cookie } }), env2);
ok(askedTag === 'short-S001-ep01',
   '완성본을 찾을 때도 -cut0 을 안 붙인다 (찾은 이름: ' + askedTag + ')');
askedTag = '';
await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/short?sid=S001&ep=1&cut=3',
  { headers: { Cookie: cookie } }), env2);
ok(askedTag === 'short-S001-ep01-cut3', '진짜 시험본은 시험본 이름으로 찾는다');
globalThis.fetch = oldFetch2;

// ⭐ 2026-08-23 운영자: "제작된 동영상은 저장할 수 있도록"
//    dl=1 이면 재생이 아니라 **받는 파일**로 내려줘야 한다.
const dlr = await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/short?sid=S001&ep=1&play=1&dl=1',
  { headers: { Cookie: cookie } }), env2);
const cd = dlr.headers.get('Content-Disposition') || '';
ok(cd.startsWith('attachment'), '받는 파일로 내려준다 (' + cd + ')');
ok(cd.includes('S001_ep01.mp4'), '파일 이름이 영문이다 (한글 이름은 한 번 죽었다)');
ok(!(vres.headers.get('Content-Disposition')), '재생일 때는 받는 파일이 아니다');

// ⚠️⚠️ 2026-08-23 운영자: "유튜브에 올릴 내용이 중복으로 들어가 있어."
//    상자(id="ytbox")를 두 군데서 만들어 같은 글이 두 벌로 보였다.
//    **주석 아닌 줄**에서 상자를 만드는 곳이 딱 한 곳이어야 한다.
const makers = src.split('\n')
  .filter((l) => !l.trim().startsWith('//') && l.includes('id="ytbox"'));
ok(makers.length === 1,
   '올릴 내용 상자는 한 곳에서만 만든다 (' + makers.length + '곳)');
ok(src.includes("function shortDl") && src.includes("function madeDl"),
   '받기 단추가 두 화면(완성 카드·만든 영상)에 다 있다');

const lst = await (await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/shorts', { headers: { Cookie: cookie } }),
  env2)).json();
ok(lst.items.length === 2, '만든 영상만 골라 낸다 (압축파일·빈 것 제외) — ' + lst.items.length + '개');
ok(lst.items[0].ep === 1 && lst.items[0].cut === 0, '새로 만든 것이 위에 온다');
ok(lst.items[1].ep === 2 && lst.items[1].cut === 3, '컷 시험본도 시험본이라고 알려 준다');
ok(lst.items[0].title === '바람난 남편이 빼돌린 15억', 'S001 대신 제목으로 보여 준다');

// 화면 쪽 — 첫 화면에서 들어가는 문이 있고, 그리는 함수가 다 있는가
for (const need of ['function madeCard', 'function madeList', 'function madeDraw',
                    'function madePlay', 'h += madeCard();', "'/api/shorts?t='"]) {
  if (!src.includes(need)) { console.log(`   ❌ 화면에 '${need}' 가 없다`); bad = 1; }
}
ok(true, '첫 화면에 [만든 영상 보기] 가 있고 그리는 코드가 다 있다');

globalThis.fetch = realFetch;

// ⑯ 첫 화면의 '만든 영상 n/16' 이 **진짜 만들어진 것**을 세는가.
//    2026-08-22 — state/series.json 의 made 를 아무도 올리지 않아서
//    영원히 0 이었다. 영상을 만들어도 첫 화면은 계속 0 이라
//    "만든 게 어디 있냐" 가 된다. 이제 릴리스를 직접 센다.
console.log('⭐ 첫 화면이 만든 편수를 제대로 세는가');
const b64 = (o) => Buffer.from(JSON.stringify(o), 'utf8').toString('base64');
globalThis.fetch = async (u, init) => {
  const s0 = String(u && u.url ? u.url : u);
  if (s0.includes('/contents/state/series.json'))
    return Response.json({ content: b64({ S001: { title: '바람난 남편이 빼돌린 15억',
                                                  episodes: 16, made: 0 } }) });
  if (s0.includes('/releases?per_page='))
    return Response.json([
      { tag_name: 'short-S001-ep01', assets: [{ name: 'short.mp4', id: 1, size: 9 }] },
      { tag_name: 'short-S001-ep02', assets: [{ name: 'short.mp4', id: 2, size: 9 }] },
      { tag_name: 'short-S001-ep03-cut2', assets: [{ name: 'short.mp4', id: 3, size: 9 }] },
      { tag_name: 'short-S001-ep09', assets: [] },
      { tag_name: 'clips-S001-ep01', assets: [{ name: 'clips.zip', id: 4, size: 9 }] },
    ]);
  if (s0.includes('/actions/runs')) return Response.json({ workflow_runs: [] });
  if (s0.includes('github.com')) return new Response('nope', { status: 404 });
  return realFetch(u, init);
};
const st = await (await W._wk.fetch(new Request(
  'https://admin.example.workers.dev/api/state', { headers: { Cookie: cookie } }),
  env2)).json();
ok(st.series && st.series.S001, '시리즈가 화면에 온다');
ok(st.series.S001.made === 2,
   '완성본 2편을 셌다 (적어 둔 0 이 아니라) — 센 값: ' + st.series.S001.made);
ok(st.series.S001.title === '바람난 남편이 빼돌린 15억', '제목은 그대로 온다');
ok(st.series.S001.episodes === 16, '전체 화수도 그대로 온다');
globalThis.fetch = realFetch;

// ⑭ ⭐⭐ 가장 중요한 못 — 관리자 페이지는 깃허브에 **아무것도 쓰지 않는다.**
//    2026-08-22, 운영자가 같은 403 을 두 번 봤다:
//      GitHub 403 … documentation_url: releases#create-a-release
//    한 군데만 고치고 다른 데 남겨 두면 언젠가 또 그리로 샌다.
//    길이 없으면 샐 수도 없다. 여기서 길이 다시 생기는 것을 막는다.
const WRITES = [
  ['uploads.github.com', '릴리스에 파일 얹기'],
  ['/releases`, {', '릴리스 만들기 (create-a-release)'],
  ["method: 'PUT'", '저장소 파일 쓰기'],
];
for (const [needle, what] of WRITES) {
  const has = src.includes(needle);
  if (has) { console.log(`   ❌ 깃허브에 쓰는 길이 남아 있다 — ${what} (${needle})`); bad = 1; }
}
ok(true, '관리자 페이지에 깃허브로 쓰는 길이 하나도 없다');
// 지우는 것을 깜빡했는지 자기시험 — 일부러 넣은 판은 걸려야 한다
{
  const broken = src + "\nfetch('https://uploads.github.com/x');\n";
  const caught = WRITES.some(([n]) => broken.includes(n));
  ok(caught, '자기시험: 길이 다시 생기면 잡는다');
}

console.log('────────────────────────────────────────────────────');
console.log(bad ? '❌ 보관함 검사: 걸린 것이 있다' : '✅ 보관함 검사: 넣은 그대로 꺼내진다');
process.exit(bad);
