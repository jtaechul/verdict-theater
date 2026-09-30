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
  talk: { n: 2, krw: 1700, drama: { talk_n: 2, talk_krw: 1700, stills: 4, still_krw: 529,
                                    sheet_krw: 265, krw: 2494 } },
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
  await workMake(0);
  out.asked = asked;
  out.sent = sent;
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
ck('③ 칸이 2분 드라마 만들기 하나다 (고를 칸 없음)',
   out.head.includes('2분 드라마 만들기') && !out.head.includes('id="w-open"'));
ck('값은 대본이 찍어 둔 것을 그대로 적는다 (2,494원)', out.head.includes('2,494원'));
ck('값의 속을 적는다 (대사 영상 · 그림 · 인물 시트)',
   out.head.includes('1,700') && out.head.includes('529') && out.head.includes('265'));
ck('① 칸은 인물 시트(자동) — 얼굴 올리기 칸이 없다',
   out.cast.includes('인물 시트') && !out.cast.includes('type="file"'));
ck('인물 이름을 적는다', out.cast.includes('아내') && out.cast.includes('변호사'));
ck('누르기 전에 2분 드라마 값을 보여 드린다',
   out.asked.includes('2분 드라마') && out.asked.includes('2,494'));
ck('누르면 워크플로에 2분 드라마로 간다 (video_kind=drama)',
   out.sent && out.sent.video_kind === 'drama', JSON.stringify(out.sent));
ck('옛 여러 편은 옛 화면 그대로 (고르는 칸이 있다)',
   out.oldHead.includes('id="w-open"') && !out.oldHead.includes('2분 드라마 만들기'));

console.log('--------------------------------------------------------');
if (bad) { console.log('❌ 2분 드라마 화면이 잘못 그려진다'); process.exit(1); }
console.log('✅ 2분 드라마 화면: 값 · 인물 시트 · 단추 · 옛 화면 모두 약속대로');
// ⚠️ 페이지 글이 걸어 둔 타이머가 남아 있어도 여기서 끝낸다 (검사가 멈춰 서면 안 된다)
process.exit(0);
