// ⭐ **영상이 진짜로 재생되는 꼴로 나가는가.** 값 0원 (인터넷 0회).
//
//     node tools/play_check.mjs
//
// ⭐⭐⭐ 2026-09-20 손님: "왜 이렇게 영상이 제대로 재생이 안 되냐.
//    관리자 페이지에서 아니면 영상을 좀 저장을 할 수 있게 해 주든가."
//
//    streamAsset 에 **두 군데**가 어긋나 있었다.
//      ① Range(몇 번째 바이트부터 달라)를 **리다이렉트된 뒤에만** 넘겼다.
//         깃허브가 리다이렉트 없이 본문을 바로 주면 Range 가 안 붙어
//         통째로 200 이 나갔다.
//      ② 그래 놓고 `Accept-Ranges: bytes` 는 **늘** 붙였다. "나 건너뛰기
//         되는 영상이야" 라고 해 놓고 정작 물어보면 Content-Range 없는
//         200 을 준 것이다. 사파리·크롬은 이걸 깨진 영상으로 보고
//         **재생을 멈춘다.** 되감기도 당연히 안 된다.
//
//    ⚠️ 이런 것은 **글만 읽어서는 안 보인다.** 가짜 깃허브를 세워 놓고
//       진짜로 불러서, 나가는 머리글을 재 본다.
import fs from 'node:fs';

const SRC = fs.readFileSync(new URL('../admin/worker.js', import.meta.url), 'utf8');
let bad = 0;
const ck = (name, ok, why = '') => {
  console.log((ok ? '   ✅ ' : '   ❌ ') + name + (!ok && why ? ` — ${why}` : ''));
  if (!ok) bad++;
};

// streamAsset 만 떼어 온다 (워커 전체를 돌릴 수는 없다)
const m = SRC.match(/async function streamAsset[\s\S]*?\n}\n/);
if (!m) { console.log('❌ streamAsset 을 못 찾았다'); process.exit(1); }
const GH = 'https://api.github.com';
const REPO = 'x/y';
const streamAsset = new Function('GH', 'REPO', 'fetch',
  m[0] + '\nreturn streamAsset;')(GH, REPO, (...a) => globalThis.__fetch(...a));

// 가짜 깃허브 — 두 가지 꼴을 다 흉내 낸다
function fakeGH({ redirect, honorsRange }) {
  return async (url, init = {}) => {
    const rng = (init.headers || {})['Range'] || (init.headers || {}).Range;
    if (redirect && String(url).startsWith(GH)) {
      return new Response(null, { status: 302, headers: { Location: 'https://cdn/x.mp4' } });
    }
    if (rng && honorsRange) {
      return new Response('AB', { status: 206,
        headers: { 'Content-Range': 'bytes 0-1/999', 'Content-Length': '2' } });
    }
    return new Response('ABCDEFGHIJ', { status: 200, headers: { 'Content-Length': '10' } });
  };
}

const req = (range) => new Request('https://a/api/video?id=1',
  range ? { headers: { Range: range } } : {});

async function run(opt, range) {
  globalThis.__fetch = fakeGH(opt);
  return streamAsset({ GH_TOKEN: 't' }, req(range), '1', null);
}

console.log('⭐ 영상이 재생되는 꼴로 나가는가 (값 0원)\n');

console.log('① 건너뛰기(Range)를 물으면 **부분**으로 답한다');
for (const redirect of [true, false]) {
  const nm = redirect ? '리다이렉트로 줄 때' : '본문을 바로 줄 때';
  const r = await run({ redirect, honorsRange: true }, 'bytes=0-1');
  ck(`${nm}: 206 으로 답한다`, r.status === 206, `${r.status}`);
  ck(`${nm}: Content-Range 를 붙인다`, !!r.headers.get('Content-Range'));
  ck(`${nm}: Accept-Ranges 를 붙인다`, r.headers.get('Accept-Ranges') === 'bytes');
}

console.log('\n② 저쪽이 건너뛰기를 **못 해 줄 때는 거짓말하지 않는다**');
const r2 = await run({ redirect: false, honorsRange: false }, 'bytes=0-1');
ck('200 으로 답한다', r2.status === 200, `${r2.status}`);
ck('Accept-Ranges 를 안 붙인다 (붙이면 브라우저가 속아 재생을 멈춘다)',
   !r2.headers.get('Accept-Ranges'), r2.headers.get('Accept-Ranges') || '');

console.log('\n③ 평범한 요청(Range 없음)은 그대로 흐른다');
const r3 = await run({ redirect: true, honorsRange: true }, null);
ck('200 으로 답한다', r3.status === 200, `${r3.status}`);
ck('건너뛰기가 된다고 알려 준다', r3.headers.get('Accept-Ranges') === 'bytes');
ck('영상으로 알려 준다', r3.headers.get('Content-Type') === 'video/mp4');

console.log('\n④ 저장(내려받기) 길이 살아 있는가');
globalThis.__fetch = fakeGH({ redirect: true, honorsRange: true });
const r4 = await streamAsset({ GH_TOKEN: 't' }, req(null), '1', 'S93_part1.mp4');
ck('저장 창이 뜨게 이름을 붙인다',
   (r4.headers.get('Content-Disposition') || '').includes('S93_part1.mp4'),
   r4.headers.get('Content-Disposition') || '없음');
ck('90초 편 화면에 [영상 저장] 단추가 있다',
   SRC.includes('function workSave') && SRC.includes('영상 저장'));
ck('저장 단추가 dl=1 로 부른다', /workSave[\s\S]{0,320}dl=1/.test(SRC));
ck('편 번호를 넘긴다 (안 넘기면 늘 1편만 받힌다)',
   /function workSave\(no\)[\s\S]{0,300}part=' \+ no/.test(SRC));

console.log('\n' + '-'.repeat(56));
if (bad) { console.log(`❌ 재생: ${bad}군데`); process.exit(1); }
console.log('✅ 재생: 건너뛰기가 되고 · 거짓말을 안 하고 · 저장도 된다');
