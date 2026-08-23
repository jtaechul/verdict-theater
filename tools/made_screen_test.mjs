// [만든 영상] 화면이 실제로 그려지는가.
//
// 왜 이 검사가 있는가 (2026-08-22)
//   운영자: "만든 영상은 어디서 볼 수 있는 건데? 왜 볼 수 있는 메뉴가 없는데?"
//   그때까지 완성된 쇼츠는 회차 화면 안쪽에서, 그것도 방금 만든 것 하나만
//   볼 수 있었다. 첫 화면에서 들어가 전부 보는 화면을 새로 만들었으므로,
//   그 화면이 **글자 하나 안 깨지고 그려지는지** 여기서 확인한다.
//
//   쓰기: node tools/made_screen_test.mjs      인터넷 0회 · 0원 · 1초

import { readFileSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

const src = readFileSync('admin/worker.js', 'utf8');
const mod = join(tmpdir(), 'vt-made-screen.mjs');
writeFileSync(mod, src.replace('export default', 'const _wk =') + '\nexport { appHtml };\n');
const { appHtml } = await import('file://' + mod + '?t=' + Date.now());
const js = appHtml().match(/<script>([\s\S]*?)<\/script>/)[1];

const boxes = {};
globalThis.document = {
  getElementById: (id) => boxes[id] || (boxes[id] = { innerHTML: '', style: {}, textContent: '' }),
  querySelectorAll: () => [],
  addEventListener: () => {},
  createElement: () => ({ style: {}, appendChild() {}, select() {} }),
  body: { appendChild() {}, removeChild() {} },
};
globalThis.window = { isSecureContext: true };
globalThis.scrollTo = () => {};
globalThis.fetch = async () => ({ status: 200, json: async () => ({}) });

const ITEMS = [
  { sid: 'S001', ep: 1, cut: 0, size: 4200000, at: '2026-08-22T15:00:00Z',
    title: '바람난 남편이 빼돌린 15억' },
  { sid: 'S001', ep: 2, cut: 3, size: 900000, at: '2026-08-22T14:00:00Z',
    title: '바람난 남편이 빼돌린 15억' },
];

const run = new Function('ITEMS', js + `
  const out = {};
  out.card = madeCard();
  SHORTS = []; VIEW = 'made'; SHOWN = -1; madeDraw();
  out.empty = document.getElementById('app').innerHTML;
  SHORTS = ITEMS; SHOWN = -1; madeDraw();
  out.list = document.getElementById('app').innerHTML;
  madePlay(0);
  out.playing = document.getElementById('app').innerHTML;
  return out;
`);
const out = run(ITEMS);

let bad = 0;
const ck = (what, cond, why) => {
  if (cond) console.log('   ✅ ' + what);
  else { console.log('   ❌ ' + what + (why ? '  (' + why + ')' : '')); bad = 1; }
};

console.log('⭐ [만든 영상] 화면');
ck('첫 화면에 들어가는 단추가 있다',
   out.card.includes('만든 영상 보기') && out.card.includes('madeList()'));
ck('하나도 없을 때 무엇을 해야 하는지 말해 준다',
   out.empty.includes('아직 만든 영상이 없습니다') && out.empty.includes('클립 압축파일'),
   '"없습니다" 만 띄우면 손님은 다음에 뭘 할지 모른다');
ck('만든 것이 다 보인다', out.list.includes('만든 영상 2개'));
ck('번호 대신 제목으로 보여 준다', out.list.includes('바람난 남편이 빼돌린 15억 1화'));
ck('시험본은 시험본이라고 적는다', out.list.includes('3컷 시험본'));
ck('크기와 날짜가 보인다', out.list.includes('4MB') && out.list.includes('2026-08-22'));
ck('재생 단추가 있다', out.list.includes('madePlay(0)'));

ck('재생을 누르면 영상이 붙는다', out.playing.includes('<video'));
ck('아이폰이 전체화면으로 낚아채지 않는다', out.playing.includes('playsinline'),
   'playsinline 이 없으면 아이폰이 영상을 전체화면으로 가져간다');
ck('올바른 주소를 본다', out.playing.includes('/api/short?sid=S001&ep=1&play=1'));
ck('보는 중인 것은 다시 재생 단추가 안 뜬다',
   out.playing.includes('보는 중') && !out.playing.includes('madePlay(0)'));
ck('그 자리에서 유튜브로 갈 수 있다',
   out.playing.includes("seriesView('S001',1)"),
   '보고 나서 올리려면 회차 화면으로 갈 길이 있어야 한다');
ck('그 자리에서 기기에 저장할 수 있다', out.playing.includes('madeDl(0)'),
   '2026-08-23 운영자: 제작된 동영상은 저장할 수 있어야 한다');
ck('돌아가는 길이 있다', out.list.includes('home()'));

console.log('────────────────────────────────────────────────────');
console.log(bad ? '❌ 만든 영상 화면: 걸린 것이 있다' : '✅ 만든 영상 화면: 제대로 그려진다');
process.exit(bad);
