// ⭐⭐⭐ 관리자 [유튜브에 올리기] 단추가 **실제로 올리기를 보내는가** (값 0원 · 인터넷 0회)
//
//   node tools/check_admin_upload.mjs
//
// 왜 필요한가 (2026-11-03 손님: "유튜브 올리기 버튼이 안 먹는데?")
//   날짜·시각 칸을 더하면서 WHEN_PICK · AT_RE 를 일꾼(서버) 쪽에만 두고 페이지에 안 실었다.
//   → 날짜를 고르고 누르면 페이지가 "AT_RE is not defined" 로 멈추고 아무 일도 안 일어났다.
//   화면 코드를 실제로 돌려 (날짜 없이 · 날짜 고름 · 지난 날짜) 셋 다 본다.
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
const mod = join(tmpdir(), 'vt-worker-upload-check.mjs');
writeFileSync(mod, src.replace('export default', 'const _wk =') + '\nexport { appHtml };\n');
const { appHtml } = await import('file://' + mod + '?t=' + Date.now());
const js = appHtml().match(/<script>([\s\S]*?)<\/script>/)[1];

async function press(day, hm) {
  const vals = { 'w-priv-3': '공개 (모두에게)', 'w-day-3': day, 'w-at-3': hm };
  const els = {};
  const doc = {
    getElementById: (id) => els[id] || (els[id] = { innerHTML: '', style: {}, value: vals[id] || '', textContent: '' }),
    addEventListener() {}, body: {}, querySelector: () => null, querySelectorAll: () => [],
    createElement: () => ({ style: {}, appendChild() {}, classList: { add() {} } }),
  };
  let sent = null;
  const ctx = {
    document: doc, console, navigator: {}, localStorage: { getItem: () => null, setItem() {} }, location: { href: '' },
    alert() {}, confirm: () => true, setTimeout: () => 0, clearTimeout() {}, setInterval: () => 0, clearInterval() {}, scrollTo() {},
    fetch: async (u, o) => { if (String(u).includes('upload-short90')) sent = JSON.parse(o.body); return { json: async () => ({ ok: true }) }; },
  };
  ctx.window = ctx;
  vm.createContext(ctx);
  vm.runInContext(js, ctx);
  vm.runInContext("WORK='S99'; WORKS={S99:{parts:{'3':{no:3}}}}; ERRS=[]; showErr=function(a){ERRS.push(a)};"
    + " partBody=function(){return {part:3,title:'t',description:'d',tags:[]}}; lock=function(){}; watchRun=function(){}", ctx);
  let crash = '';
  try { await vm.runInContext('workUp(3, 0)', ctx); } catch (e) { crash = e.message; }
  return { sent, crash, errs: vm.runInContext('ERRS', ctx) };
}

console.log('⭐ 관리자 [유튜브에 올리기] 단추 (값 0원)\n');
const a = await press('', '');
ck('날짜를 비우고 누르면 올리기를 보낸다 (아침 8시 X분 예약)', a.sent && a.sent.at === '' && !a.crash, a.crash);
const fut = new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10);
const b = await press(fut, '08:07');
ck('날짜·시각을 고르고 누르면 그 시각을 실어 보낸다 (멈추지 않는다)',
   b.sent && b.sent.at === fut + ' 08:07' && b.sent.when === '예약 — 날짜·시각 직접 고름' && !b.crash, b.crash || JSON.stringify(b.sent));
const c = await press('2020-01-01', '08:07');
ck('지난 시각이면 보내지 않고 까닭을 알려 준다', !c.sent && !c.crash && c.errs.length === 1, c.crash);
console.log('\n' + '─'.repeat(56));
if (bad.length) { console.log(`❌ ${bad.length}개 걸렸습니다 — [유튜브에 올리기] 가 안 먹습니다`); process.exit(1); }
console.log('✅ 관리자 [유튜브에 올리기] 단추가 올리기를 보낸다');
