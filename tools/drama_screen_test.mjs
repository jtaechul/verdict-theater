// ⭐ [2분 드라마] 화면이 제대로 그려지고, 단추가 **2분 드라마로** 누르는가
//    — 값 0원 · 인터넷 0회
//
//    node tools/drama_screen_test.mjs
//
// 2026-09-30 손님 확정 — "2분 이내 쇼츠 드라마로 가자."
//   · ③ 칸은 고를 것이 없다 — [2분 드라마 만들기 (약 X원)] 하나. 값은 대본이
//     찍어 둔 것(talk.drama)을 그대로 읽는다 (화면이 스스로 세면 거짓 값이 된다)
//   · ① 칸은 얼굴 올리기가 아니다 — 인물 시트(자동). 올린 얼굴은 안 쓴다
//   · 누르면 워크플로에 '2분 드라마' 로 간다. 옛 칸(전부 그림)으로 가면
//     워크플로가 형식이 어긋났다며 멈춘다 — 손님은 이유 모를 빨간불을 본다
//   · 옛 여러 편 대본은 옛 화면 그대로다
//
// ⭐⭐⭐ 2026-10-01 손님 승인 — **그림 먼저 확인 → 그다음 영상** (해양생물 쇼츠)
//   · ③ 칸이 둘로 나뉜다: [① 그림 먼저 만들기 (그림값)] · [② 영상 만들기 (영상값)]
//   · ① 은 워크플로에 step=stills 로 간다 — 옴니 영상을 **안 산다**
//   · 그림 보기 — 컷마다 줄인 그림 · 앞 컷과 닮음 경고 · [다시 그리기] 고르기
//   · 고른 컷만 다시 그리기 — redo="3,7" 로 간다
//   · 그림을 안 보고 ② 를 누르면 한 번 더 여쭌다
import { readFileSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

const src = readFileSync('admin/worker.js', 'utf8');
const mod = join(tmpdir(), 'vt-drama-screen.mjs');
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
// 페이지 글은 읽히자마자 load() 로 /api/state 를 부른다 — 밖으로 안 나가게
globalThis.fetch = async () => ({ status: 200, json: async () => ({}) });

const DRAMA = {
  format: 'drama', sid: 'S999',
  cast: [{ name: '아내', sex: '여', age: 52 }, { name: '내연녀', sex: '여', age: 38 },
         { name: '변호사', sex: '남', age: 45 }],
  cuts: [{ n: 1, who: [], turns: [['나레이션', '가']] },
         { n: 2, who: ['아내'], turns: [['아내', '나']] },
         { n: 3, who: ['내연녀', '아내'], turns: [['내연녀', '다']] },
         { n: 4, who: [], turns: [['나레이션', '라']] }],
  talk: { n: 2, krw: 1700, drama: { talk_n: 2, talk_krw: 1700, stills: 4, inserts: 1,
                                    still_krw: 529, sheet_krw: 265, redraw_krw: 265,
                                    pic_krw: 1059, krw: 2494 } },
};
const OLD = { cuts: [{ n: 1, who: ['아내'], turns: [['아내', '가']] }],
              talk: { n: 1, krw: 706, parts: { 1: 50 } } };

const AsyncFn = Object.getPrototypeOf(async function () {}).constructor;
const run = new AsyncFn('R', js + `
  const out = {};
  WORK = 'S999';
  WORKS = { S999: { label: '33억 유류분 사건', parts: [{ no: 1 }] } };
  S90DOC = R.DRAMA;
  out.drama = isDrama();
  out.head = partsCard(WORKS.S999);
  out.cast = short90Card();
  // 단추를 누르면 무엇이 워크플로로 가는가
  let asked = '';
  globalThis.confirm = (t) => { asked = t; return true; };
  let sent = null;
  globalThis.fetch = async (u, o) => {
    if (u === '/api/make-short90') sent = JSON.parse(o.body);
    return { status: 200, json: async () => ({ ok: true }) };
  };
  // ⚠️ 페이지 안의 watchRun 은 30분 동안 10초마다 묻는다 — 시험에서는 끈다
  watchRun = function () {};
  // ② 를 그림도 안 보고 누르면
  await workMake(0);
  out.asked = asked;
  out.sent = sent;
  // ① 그림 먼저
  sent = null; asked = '';
  await dramaPics();
  out.picAsked = asked;
  out.picSent = sent;
  // 그림 보기 — 가짜 미리보기
  globalThis.fetch = async (u, o) => {
    if (String(u).startsWith('/api/stills-view')) return { status: 200, json: async () => ({
      ok: true, assets: [{ name: 'v-c01.jpg', id: 11 }, { name: 'v-c02.jpg', id: 12 },
                         { name: 'v-i01.jpg', id: 13 }, { name: 'view.json', id: 14 }],
      view: { at: '2026-10-01T00:00:00Z', same: 0.55, one_krw: 132, cuts: [
        { n: 1, kind: '나레이션', who: ['아내'], text: '가', file: 'v-c01.jpg',
          insert: 'v-i01.jpg', insert_word: '녹음기' },
        { n: 2, kind: '아내', who: ['아내'], text: '나', file: 'v-c02.jpg', like_prev: 0.61,
          redrawn: { before: 0.66, after: 0.61 } }] } }) };
    if (u === '/api/make-short90') sent = JSON.parse(o.body);
    return { status: 200, json: async () => ({ ok: true }) };
  };
  await stillsShow();
  out.pics = document.getElementById('w-pics').innerHTML;
  sent = null; asked = '';
  // ⚠️ 진짜로는 앞 실행이 끝나야(watchRun) 다시 누를 수 있다 — 시험에서는 풀어 준다
  WBUSY['w-make-pic'] = 0;
  await dramaPics('3,7');
  out.redoAsked = asked;
  out.redoSent = sent;
  // 그림을 본 뒤 ② — 더 여쭙지 않는다
  sent = null; asked = '';
  await workMake(0);
  out.asked2 = asked;
  // 옛 여러 편은 옛 화면 그대로
  S90DOC = R.OLD;
  out.oldDrama = isDrama();
  out.oldHead = partsCard(WORKS.S999);
  return out;
`);
const out = await run({ DRAMA, OLD });

let bad = 0;
const ck = (what, cond, why) => {
  if (cond) console.log('   ✅ ' + what);
  else { console.log('   ❌ ' + what + (why ? '  (' + why + ')' : '')); bad = 1; }
};

console.log('⭐ [2분 드라마] 화면');
ck('대본 형식을 알아본다', out.drama === true && out.oldDrama === false);
ck('③ 칸이 ① 그림 먼저 · ② 영상 둘이다 (고를 칸 없음)',
   out.head.includes('① 그림 먼저 만들기') && out.head.includes('② 영상 만들기')
   && !out.head.includes('id="w-open"'));
ck('① 그림값은 대본이 찍어 둔 것 그대로 (1,059원 · 다시 그리기 몫 265원 포함)',
   out.head.includes('1,059원') && out.head.includes('265'));
ck('② 영상값은 대사 영상값 그대로 (1,700원)', out.head.includes('1,700원'));
ck('나레이션 컷에도 등장인물 얼굴이라고 적는다', out.head.includes('등장인물 얼굴'));
ck('① 칸은 인물 시트(자동) — 얼굴 올리기 칸이 없다',
   out.cast.includes('인물 시트') && !out.cast.includes('type="file"'));
ck('인물 이름을 적는다', out.cast.includes('아내') && out.cast.includes('변호사'));
ck('② 누르기 전에 영상값을 보여 드린다',
   out.asked.includes('② 영상 만들기') && out.asked.includes('1,700'));
ck('그림을 안 보고 ② 를 누르면 한 번 더 여쭌다', out.asked.includes('그림을 안 보셨습니다'));
ck('② 는 워크플로에 2분 드라마 · 전부(step=all) 로 간다',
   out.sent && out.sent.video_kind === 'drama' && (out.sent.step || 'all') === 'all',
   JSON.stringify(out.sent));
ck('① 은 그림만 — step=stills 로 간다 (옴니 영상을 안 산다)',
   out.picSent && out.picSent.step === 'stills' && out.picSent.video_kind === 'drama'
   && !out.picSent.redo, JSON.stringify(out.picSent));
ck('① 누르기 전에 그림값과 "영상은 아직 안 산다" 를 보여 드린다',
   out.picAsked.includes('1,059') && out.picAsked.includes('안 삽니다'));
ck('그림 보기 — 컷 그림·확대 그림을 보관함에서 띄운다',
   out.pics.includes('/api/thumb?id=11') && out.pics.includes('/api/thumb?id=13')
   && out.pics.includes('녹음기'));
ck('그림 보기 — 앞 컷과 닮은 컷을 짚는다', out.pics.includes('앞 컷과 닮음 0.61'));
ck('그림 보기 — 컷마다 [다시 그리기] 를 고를 수 있다',
   (out.pics.match(/class="w-redo"/g) || []).length === 2);
ck('고른 컷만 다시 그리기 — redo="3,7" · 값은 장수 × 한 장 값',
   out.redoSent && out.redoSent.redo === '3,7' && out.redoSent.step === 'stills'
   && out.redoAsked.includes('264원'), JSON.stringify(out.redoSent));
ck('그림을 본 뒤 ② 는 더 여쭙지 않는다', !out.asked2.includes('그림을 안 보셨습니다'));
ck('옛 여러 편은 옛 화면 그대로 (고르는 칸이 있다)',
   out.oldHead.includes('id="w-open"') && !out.oldHead.includes('2분 드라마 만들기'));

console.log('--------------------------------------------------------');
if (bad) { console.log('❌ 2분 드라마 화면이 잘못 그려진다'); process.exit(1); }
console.log('✅ 2분 드라마 화면: 그림 먼저 · 다시 그리기 · 영상 · 인물 시트 · 옛 화면 모두 약속대로');
// ⚠️ 페이지 글이 걸어 둔 타이머가 남아 있어도 여기서 끝낸다 (검사가 멈춰 서면 안 된다)
process.exit(0);
