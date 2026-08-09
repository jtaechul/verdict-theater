// 관리자 페이지의 **브라우저에서 도는 코드**를 검사한다.
//
// 왜 필요한가 (2026-08-07 사고)
//   worker.js 는 `node --check` 를 통과했는데 **페이지가 '불러오는 중…' 에서 멈췄다.**
//   화면에 뜨는 코드는 worker.js 안의 **템플릿 문자열 속**에 들어 있다.
//   node --check 는 바깥 파일만 본다 — 그 안쪽 문자열은 그냥 글자로 볼 뿐이다.
//   그래서 안쪽이 깨져도 배포가 초록불로 지나갔고, 손님 화면만 죽었다.
//
//   실제 원인: 템플릿 문자열은 \\ 를 \ 로, \n 을 줄바꿈으로 한 겹 풀어 준다.
//   내가 `doUpload(\'` 라고 썼더니 브라우저에는 `doUpload('` 로 가서 문자열이 끊겼다.
//   (`\\'` 라고 써야 브라우저가 `\'` 로 받는다)
//
// 이제 **화면에 실제로 나갈 코드를 뽑아 문법 검사하고 한 번 돌려 본다.**
// 배포 전에 이걸 통과해야 한다.

import { writeFileSync, readFileSync, unlinkSync } from 'fs';
import { execFileSync } from 'child_process';
import { tmpdir } from 'os';
import { join } from 'path';

const src = readFileSync('admin/worker.js', 'utf8');
const mod = join(tmpdir(), 'vt-worker-check.mjs');
writeFileSync(mod, src.replace('export default', 'const _wk =') + '\nexport { appHtml };\n');

const { appHtml } = await import('file://' + mod);
const m = appHtml().match(/<script>([\s\S]*?)<\/script>/);
if (!m) {
  console.error('❌ 화면에서 <script> 를 못 찾았다');
  process.exit(1);
}
const js = join(tmpdir(), 'vt-client-check.js');
writeFileSync(js, m[1]);

// ① 문법
try {
  execFileSync(process.execPath, ['--check', js], { stdio: 'pipe' });
} catch (e) {
  console.error('❌ 브라우저 코드에 문법 오류가 있다 — 페이지가 안 뜬다:\n');
  console.error((e.stderr || '').toString().split('\n').slice(0, 6).join('\n'));
  process.exit(1);
}

// ② 실제로 한 번 돌려 본다. 문법이 맞아도 첫 줄에서 죽으면 화면은 똑같이 멈춘다.
globalThis.document = {
  getElementById: () => ({ innerHTML: '', value: '', style: {} }),
  addEventListener: () => {}, body: {}, querySelector: () => null,
};
globalThis.window = globalThis;
globalThis.location = { href: '', pathname: '/', reload() {} };
// ⭐ 빈 값이 아니라 **진짜 같은 값**을 준다.
//    빈 목록이면 화면을 그리는 코드(회차 카드·대기열 카드·실행 카드)가 거의
//    안 돌아, 그 안의 잘못을 못 잡는다. 실제로 8월 7일 무한로딩이 그런 자리였다.
const FAKE_STATE = {
  episodes: { EP001: { stage: 'rendering', case_type: '상속', gate_score: 82,
                       script_score: 90, longform_id: 'abc123' } },
  queue: [
    { case_id: '234921', 사건명: "상속회복청구'등'의 소", machine_score: 80,
      gate_pass: true, one_line: '형이 다 가져갔다' },
    { case_id: '77437', case_type: '유언무효', gate_score: 40, gate_pass: false },
    { case_id: '184051', case_type: '상속재산회복', machine_score: 70 },
  ],
  runs: [{ name: '3. 영상 만들기', at: new Date().toISOString(), conclusion: 'success' }],
  videos: { EP001: 4 },
  // 오디션 카드도 그려 본다 (2026-08-09: 만들어 놓고 화면에 안 띄운 자리)
  audition: { id: 777, size: 3419085, index: 778, at: new Date().toISOString() },
  // 등장인물 목소리 카드도 그려 본다 (2026-08-09 추가)
  cast: { v_M50A: 'Algenib', v_M50B: 'Fenrir' },
  voiceList: [{ name: 'Achird', hz: 117.6 }, { name: 'Algenib', hz: 134.5 },
              { name: 'Sulafat', hz: 211.9 }],
  assets: { have: 30, need: 38 },
  items: [],
};
// ⚠️ 주소에 따라 다른 답을 준다. 한 가지만 돌려주면 오디션 목록이 늘 비어서,
//    그 안의 버튼(seekAudition)이 **한 번도 검사되지 않는다.**
const FAKE_AUDITION = { total: 150, items: [
  { n: 1, name: 'Achird', hz: 117.6, start: 0, dur: 5.1 },
  { n: 2, name: 'Algenib', hz: 134.5, start: 5.1, dur: 5.3 },
  { n: 3, name: 'Sulafat', hz: 211.9, start: 10.4, dur: 5.0 },
]};
globalThis.fetch = async (u) => ({
  status: 200, ok: true,
  json: async () => (String(u).includes('/api/auditionindex') ? FAKE_AUDITION : FAKE_STATE),
});
globalThis.scrollTo = () => {};
globalThis.alert = () => {};
globalThis.confirm = () => false;

let api;
try {
  api = new Function(readFileSync(js, 'utf8')
                   + '\n;return {home, thumbCard, fillAudition, setS: (v) => { S = v; },'
                   + ' setTHUMB: (v) => { THUMB = v; }};')();
} catch (e) {
  console.error(`❌ 브라우저 코드가 첫 실행에서 죽는다 — 페이지가 '불러오는 중…' 에서 멈춘다`);
  console.error(`   ${e.constructor.name}: ${e.message}`);
  process.exit(1);
}

// ③ 첫 화면을 **실제 값으로 한 번 그려 본다.** 그리다 죽으면 화면이 멈춘다.
let painted = '';
globalThis.document.getElementById = () => ({
  set innerHTML(v) { painted += v; }, get innerHTML() { return painted; },
  value: '', style: {},
});
try {
  api.setS(FAKE_STATE);
  api.home();
} catch (e) {
  console.error('❌ 첫 화면을 그리다 죽는다 — 페이지가 빈 채로 멈춘다');
  console.error(`   ${e.constructor.name}: ${e.message}`);
  process.exit(1);
}

// ③-1 **오디션 목록이 채워지기를 기다린다.**
//     ⚠️ 여기서 fillAudition() 을 직접 부르면 안 된다. 그러면 '함수는 멀쩡한데
//        home() 이 부르지 않는' 상태를 못 잡는다 — 실제로 그 구멍을 확인했다.
//        home() 이 스스로 불러 채우기를 기다려야 진짜 화면과 같아진다.
for (let i = 0; i < 20; i++) await new Promise((r) => setTimeout(r, 0));

// ③-2 **썸네일 카드도 그려 본다.** 여기 버튼(다운받기·다시 만들기)이
//     2026-08-09 에 손님을 저장 화면에 가둔 자리다 — 첫 화면에는 안 나오므로
//     따로 그려 주지 않으면 아래 버튼 검사를 통째로 건너뛴다.
try {
  if (typeof api.setTHUMB === 'function')
    api.setTHUMB({ id: 999, size: 172031, at: new Date().toISOString() });
  if (typeof api.thumbCard === 'function') painted += api.thumbCard('EP001');
} catch (e) {
  console.error('❌ 썸네일 카드를 그리다 죽는다');
  console.error(`   ${e.constructor.name}: ${e.message}`);
  process.exit(1);
}

// ④ 그려진 화면의 **버튼 속 코드**를 하나씩 문법 검사한다.
//    2026-08-07 무한로딩이 바로 이 자리였다: 소재 이름에 따옴표가 들어가면
//    onclick 안의 코드가 깨지는데, 바깥 파일은 멀쩡해 보여 검사를 통과했다.
//    (FAKE_STATE 의 사건명에 일부러 작은따옴표를 넣어 뒀다)
const unesc = (s) => s.replace(/&amp;/g, '&').replace(/&lt;/g, '<')
                      .replace(/&gt;/g, '>').replace(/&quot;/g, '"');
let nHandler = 0;
for (const m of painted.matchAll(/onclick="([^"]*)"/g)) {
  const code = unesc(m[1]);
  nHandler++;
  try {
    new Function('event', code);
  } catch (e) {
    console.error('❌ 버튼 속 코드가 깨졌다 — 누르면 아무 일도 안 일어나거나 화면이 멈춘다');
    console.error(`   버튼 코드: ${code.slice(0, 90)}`);
    console.error(`   ${e.constructor.name}: ${e.message}`);
    process.exit(1);
  }
}
if (!nHandler) {
  console.error('❌ 화면에 버튼이 하나도 안 그려졌다 — 화면 그리기가 도중에 멈춘 것이다');
  process.exit(1);
}

// ⑤ 썸네일 버튼이 **실제로 검사에 들어왔는지** 확인한다.
//    thumbCard 를 못 그리면 위 검사가 조용히 건너뛰어, 손님을 가둔 그 버튼이
//    다시 깨져도 초록불이 뜬다. 검사를 안 한 것을 통과로 보면 안 된다.
if (!painted.includes('changeVoice(')) {
  console.error('❌ 등장인물 목소리 카드가 검사에 안 들어왔다 — 바꾸는 버튼을 못 봤다');
  process.exit(1);
}
if (!painted.includes('seekAudition(')) {
  console.error('❌ 오디션 목록이 검사에 안 들어왔다 — 이름을 눌러 넘어가는 버튼을 못 봤다');
  console.error('   (2026-08-09 손님이 "확인할 방법이 없잖아" 라고 한 그 화면이다)');
  process.exit(1);
}
if (!painted.includes('saveThumb(')) {
  console.error('❌ 썸네일 카드가 검사에 안 들어왔다 — 그 안의 버튼을 검사하지 못했다');
  console.error('   (2026-08-09 손님이 갇힌 [썸네일 다운받기] 가 바로 그 버튼이다)');
  process.exit(1);
}
// 화면을 통째로 옮기는 링크가 다시 생기지 않았는지 본다 (아이폰이 갇히는 원인)
if (/<a[^>]+download=[^>]+href="\/api\/thumb/.test(painted)) {
  console.error('❌ 썸네일을 링크로 내려받고 있다 — 아이폰에서 저장 화면에 갇힌다');
  console.error('   화면을 옮기지 말고 saveThumb() 처럼 그림만 받아야 한다');
  process.exit(1);
}

for (const f of [mod, js]) { try { unlinkSync(f); } catch {} }
console.log('✅ 관리자 페이지: 바깥 코드 + 브라우저 코드 둘 다 정상');
