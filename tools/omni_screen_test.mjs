// ⭐ [⑤ 새 방식 시험] 칸이 제대로 그려지는가 — 값 0원 · 인터넷 0회
//
//    node tools/omni_screen_test.mjs
//
// 2026-09-30 — 손님이 앱(플로우)에서 막힌 옴니 시험을 API 로 옮기면서
// 관리자 페이지에 [시험 만들기] · [결과 보기] 를 달았다. 손님은 깃허브에
// 안 들어가신다 — 결과는 **여기서 다 보여야** 한다.
//   · 폰에서는 가벼운 사본(v-이름.jpg)을 먼저 쓴다 (4K 시트 PNG 는 10MB 가 넘는다)
//   · 영상은 건너뛰기 되는 길(/api/video)로 틀고, 저장 단추가 있다
//   · 못 만들었으면 **왜 못 만들었는지** 글로 적는다 (조용한 빈 칸 금지)
//   · 아직 한 번도 안 했으면 그렇다고 적는다
import { readFileSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

const src = readFileSync('admin/worker.js', 'utf8');
const mod = join(tmpdir(), 'vt-omni-screen.mjs');
writeFileSync(mod, src.replace('export default', 'const _wk =') + '\nexport { appHtml };\n');
const { appHtml } = await import('file://' + mod + '?t=' + Date.now());
const js = appHtml().match(/<script>([\s\S]*?)<\/script>/)[1];

const boxes = {};
globalThis.document = {
  getElementById: (id) => boxes[id] || (boxes[id] = { innerHTML: '', style: {}, textContent: '', value: '' }),
  querySelectorAll: () => [],
  addEventListener: () => {},
  createElement: () => ({ style: {}, appendChild() {}, select() {} }),
  body: { appendChild() {}, removeChild() {} },
};
globalThis.window = { isSecureContext: true };
globalThis.scrollTo = () => {};
// 페이지 글은 읽히자마자 load() 로 /api/state 를 부른다 — 인터넷에 나가지 않게 막아 둔다
globalThis.fetch = async () => ({ status: 200, json: async () => ({}) });

const FULL = {
  ok: true,
  assets: [
    { name: 'sheet.png', id: 11 }, { name: 'v-sheet.jpg', id: 12 },
    { name: 'cast-1.png', id: 21 }, { name: 'v-cast-1.jpg', id: 22 },
    { name: 'cast-2.png', id: 23 },
    { name: 'c08-still.png', id: 31 }, { name: 'v-c08-still.jpg', id: 32 },
    { name: 'c08-omni.mp4', id: 41 }, { name: 'c08-frames.jpg', id: 51 },
    { name: 'result.json', id: 61 },
  ],
  result: { ok: true, cut: 8, text: '이대로는 절대 못 넘어갑니다.', sec: 7, video_sec: 7.0,
            krw: 1477,
            cast: [{ file: 'cast-1.png', name: '본처' }, { file: 'cast-2.png', name: '남편' }],
            attempts: [{ task: 'image_to_video', ok: true }] },
};
const FAIL = {
  ok: true,
  assets: [{ name: 'result.json', id: 61 }],
  result: { ok: false, cut: 8, text: '이대로는', sec: 7, krw: 397,
            error: '안전 검사에 걸렸다 (HTTP 400): blocked', cast: [], attempts: [] },
};
const NONE = { ok: true, none: true };

const AsyncFn = Object.getPrototypeOf(async function () {}).constructor;
const run = new AsyncFn('R', js + `
  const out = {};
  WORK = 'S93';
  out.card = omniCard();
  const show = async (body) => {
    globalThis.fetch = async () => ({ status: 200, json: async () => body });
    await omniShow();
    return document.getElementById('omni-box').innerHTML;
  };
  out.full = await show(R.FULL);
  out.fail = await show(R.FAIL);
  out.none = await show(R.NONE);
  return out;
`);
const out = await run({ FULL, FAIL, NONE });

let bad = 0;
const ck = (what, cond, why) => {
  if (cond) console.log('   ✅ ' + what);
  else { console.log('   ❌ ' + what + (why ? '  (' + why + ')' : '')); bad = 1; }
};

console.log('⭐ [⑤ 새 방식 시험] 칸');
ck('시험 만들기 · 시트부터 새로 · 결과 보기 단추가 있다',
   out.card.includes('omniGo(0)') && out.card.includes('omniGo(1)')
   && out.card.includes('omniShow()'));
ck('누르기 전에 값을 적어 둔다', /약 1,500원/.test(out.card));
ck('시트는 가벼운 사본(v-sheet.jpg)으로 보여 준다',
   out.full.includes('/api/thumb?id=12') && !out.full.includes('/api/thumb?id=11'));
ck('사본이 없는 칸은 원본으로라도 보여 준다 (cast-2.png)',
   out.full.includes('/api/thumb?id=23'));
ck('인물 이름을 칸 밑에 적는다', out.full.includes('본처') && out.full.includes('남편'));
ck('영상은 건너뛰기 되는 길로 튼다 (아이폰은 playsinline 이 있어야 한다)',
   out.full.includes('/api/video?id=41') && out.full.includes('playsinline'));
ck('영상 저장 단추가 있다', out.full.includes('omniSave(41,8)'));
ck('네 장면 그림이 있다 (영상이 안 틀어질 때)', out.full.includes('/api/thumb?id=51'));
ck('쓴 돈을 적는다', out.full.includes('1,477원'));
ck('못 만들었으면 왜인지 적는다',
   out.fail.includes('못 만들었습니다') && out.fail.includes('안전 검사'));
ck('아직 안 했으면 그렇다고 적는다', out.none.includes('아직 시험 결과가 없습니다'));

console.log('--------------------------------------------------------');
if (bad) { console.log('❌ 새 방식 시험 칸이 잘못 그려진다'); process.exit(1); }
console.log('✅ 새 방식 시험 칸: 단추 · 그림 · 영상 · 저장 · 실패 안내 모두 그려진다');
