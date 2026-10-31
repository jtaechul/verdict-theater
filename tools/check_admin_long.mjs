// ⭐⭐⭐ 관리자 페이지 — 긴 영상 길 · 대본 보기 · 마지막 대본 결과가 **진짜로 그려지는가** (값 0원 · 인터넷 0회)
//
//   node tools/check_admin_long.mjs
//
// 왜 필요한가 (2026-10-31 손님: "노후 투자 사기로 지금 쇼츠 만들기 눌렀는데 이거 롱폼으로 제작되는
//   거 맞지? 그리고 지금 제작 대본 같은 경우에는 어디서 확인해야 돼?")
//   ① [이 사건으로 쇼츠 만들기] 는 2분 세로 쇼츠(Gemini)만 지었다 — 채널 방침은 긴 영상인데 화면에
//      긴 영상으로 가는 길이 없었다. 손님은 롱폼이 만들어지는 줄 아셨다 (S97 · 2분 한도 초과로 실패 · 558원).
//   ② 2분 드라마 · 긴 영상은 ② 칸을 통째로 숨겨서 대본이 화면 **어디에도** 없었다.
//   ③ 대본 짓기 결과는 누른 화면을 켜 둔 동안만 떴다 — 새로 고치면 실패를 알 길이 없었다.
//   화면 코드를 실제로 돌려(진짜 대본 S95 · 가짜 결과표) 셋 다 손님 눈에 보이는지 본다.

import { readFileSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';
import vm from 'vm';

const bad = [];
const ck = (name, ok, why = '') => {
  console.log((ok ? '   ✅ ' : '   ❌ ') + name + (!ok && why ? ' — ' + why : ''));
  if (!ok) bad.push(name);
};

const src = readFileSync('admin/worker.js', 'utf8');
const mod = join(tmpdir(), 'vt-worker-long-check.mjs');
writeFileSync(mod, src.replace('export default', 'const _wk =') + '\nexport { appHtml };\n');
const { appHtml } = await import('file://' + mod + '?t=' + Date.now());
const js = appHtml().match(/<script>([\s\S]*?)<\/script>/)[1];

const els = {};
const doc = {
  getElementById: (id) => els[id] || (els[id] = { innerHTML: '', style: {}, value: '' }),
  addEventListener() {}, body: {}, querySelector: () => null, querySelectorAll: () => [],
  createElement: () => ({ className: '', style: {}, appendChild() {}, classList: { add() {}, toggle() {} } }),
};
let LAST = null;
let alerted = '';
const ctx = {
  document: doc, console, navigator: {},
  localStorage: { getItem: () => null, setItem() {}, removeItem() {} },
  location: { href: '', pathname: '/', reload() {} },
  alert: (m) => { alerted = String(m); }, confirm: () => false,
  setTimeout: () => 0, clearTimeout() {}, setInterval: () => 0, clearInterval() {},
  fetch: async (u) => ({ json: async () => (String(u).includes('/api/story-last') ? { last: LAST } : {}) }),
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(js, ctx);
const fn = (name) => vm.runInContext(name, ctx);

console.log('⭐ 관리자 페이지: 긴 영상 길 · 대본 보기 · 마지막 대본 결과 (값 0원)\n');

console.log('① 사건마다 긴 영상으로 가는 길이 있는가');
vm.runInContext('WORKS = {}', ctx);
const q = fn('queueCard')([{ case_id: '149312', case_type: '노인에게 원금보장이라며 판 파생펀드',
  gate_score: 88, topic: '노후투자사기', senior: true, one_line: '한 줄' }]);
ck('사건마다 [긴 영상으로] 단추가 있다', /onclick="longAsk\(this\)">긴 영상으로</.test(q));
ck('옛 단추는 [2분 쇼츠만 (예전 방식)] 이라고 똑바로 부른다 (긴 영상으로 오해하지 않게)',
   /onclick="makeStory\(this\)">2분 쇼츠만 \(예전 방식\)</.test(q) && !q.includes('이 사건으로 쇼츠 만들기</button>'));
ck('안내에 기본 흐름(긴 영상 1편 → 미끼 쇼츠 3~5편)과 작업 칸에서 짓는다는 것이 적혀 있다',
   q.includes('긴 영상 1편') && q.includes('미끼 쇼츠 3~5편') && q.includes('작업 칸'));
fn('longAsk')({ dataset: { cid: '149312', nm: '노후 투자 사기' } });
ck('[긴 영상으로] 를 누르면 작업 칸에 보낼 말(판례 번호 · 사건 이름)을 알려 준다',
   alerted.includes('판례 149312') && alerted.includes('긴 영상으로 만들어줘')
   && alerted.includes('쇼츠 3~5편'), alerted.slice(0, 120));
const makeSrc = js.slice(js.indexOf('async function makeStory'), js.indexOf('async function makeStory') + 900);
ck('[2분 쇼츠 대본] 확인창이 긴 영상이 아니라고 먼저 알린다', makeSrc.includes('긴 영상이 아닙니다'));

console.log('\n② 2분 드라마 · 긴 영상도 대본이 보이는가');
const s95 = JSON.parse(readFileSync('data/series/S95.json', 'utf8'));
const card = fn('scriptCard')(s95);
ck('긴 영상 대본에 「대본 보기」 칸이 그려진다 (형식 · 컷 수)',
   card.includes('대본 보기') && card.includes('긴 영상 (가로 16:9)') && card.includes(s95.cuts.length + '컷'));
const first = s95.cuts.find((c) => Array.isArray(c.turns) && c.turns.length);
ck('컷마다 말이 그대로 나온다', card.includes(String(first.turns[0][1]).replace(/&/g, '&amp;').slice(0, 12)));
const tags = [...card.matchAll(/<b>컷 (\d+)<\/b> <small[^>]*>[^<]*<\/small> <span[^>]*>([^<]*)<\/span>/g)];
const tagOf = (n) => (tags.find((x) => x[1] === String(n)) || [])[2];
const talkCut = s95.cuts.find((c) => !c.narr && c.kind && c.kind !== '나레이션' && c.place !== '그림' && !c.fig);
const figCut = s95.cuts.find((c) => c.place === '그림' || c.fig);
ck('대사 · 그림 컷을 가른다', tagOf(talkCut.n) === '대사' && tagOf(figCut.n) === '그림',
   `${talkCut.n}:${tagOf(talkCut.n)} ${figCut.n}:${tagOf(figCut.n)}`);
const thin = { format: 'drama', cuts: [{ n: '1', sec: '5', turns: [['나레이션', '가']] },
                                       { n: '2', sec: '3', turns: [['은행원', '나']] }] };
const c2 = fn('scriptCard')(thin);
const t2 = [...c2.matchAll(/<b>컷 (\d+)<\/b> <small[^>]*>[^<]*<\/small> <span[^>]*>([^<]*)<\/span>/g)].map((x) => x[2]);
ck('kind · narr 칸이 없는 대본도 나레이션을 대사로 잘못 적지 않는다', t2.join(',') === '나레이션,대사', t2.join(','));
const cutsSrc = js.slice(js.indexOf('async function s90Cuts'), js.indexOf('async function s90Cuts') + 3200);
ck('2분 드라마 · 긴 영상이면 컷 칸 자리에 대본 보기를 그린다 (빈칸으로 두지 않는다)',
   cutsSrc.includes('if (isDrama()) { box.innerHTML = scriptCard(S90DOC)'));

console.log('\n③ 마지막 대본 짓기 결과가 새로 고쳐도 보이는가');
LAST = { sid: 'S97', name: '노후 투자 사기', state: '실패', krw: 558, at: new Date().toISOString(),
         why: ['1편이 약 112초다 — 110초를 넘으면 2분 벽에 걸린다'] };
await fn('storyLastShow')();
const box = doc.getElementById('w-story-last').innerHTML;
ck('실패 · 사건 · 쓴 값 · 까닭이 보인다',
   box.includes('실패') && box.includes('S97') && box.includes('558') && box.includes('112초'), box.slice(0, 160));
LAST = { ...LAST, at: new Date(Date.now() - 9 * 24 * 3600 * 1000).toISOString() };
doc.getElementById('w-story-last').innerHTML = '';
await fn('storyLastShow')();
ck('일주일 지난 결과는 안 띄운다', doc.getElementById('w-story-last').innerHTML === '');

console.log('\n' + '─'.repeat(60));
if (bad.length) {
  console.log(`❌ ${bad.length}개 걸렸습니다 — 손님이 긴 영상 길 · 대본 · 실패 까닭을 못 봅니다`);
  process.exit(1);
}
console.log('✅ 관리자 페이지: 긴 영상 길 · 대본 보기 · 마지막 대본 결과가 보인다');
