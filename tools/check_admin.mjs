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
  // 접기 기능(foldify)이 쓰는 자리. 여기서는 빈 목록이라 아무것도 안 접지만,
  // **부르다가 죽는지**는 이 한 줄로 잡힌다. 접히는 동작 자체는
  // tools/check_fold.mjs 가 진짜 같은 화면을 만들어 따로 검사한다.
  querySelectorAll: () => [],
  createElement: () => ({ className: '', style: {}, appendChild() {},
                          classList: { add() {}, toggle() {} } }),
};
globalThis.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };
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
      gate_pass: true, one_line: '형이 다 가져갔다', topic: '상속' },
    { case_id: '77437', case_type: '유언무효', gate_score: 40, gate_pass: false,
      topic: '상속' },
    { case_id: '184051', case_type: '상속재산회복', machine_score: 70, topic: '상속' },
    // 갈래가 둘 이상이어야 고르는 단추가 그려진다 (2026-08-10 갈래별 보기)
    { case_id: '239083', 사건명: '손해배상(기)', machine_score: 90, topic: '불륜' },
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
  // 지난 수집 결과 카드도 그려 본다 (2026-08-10: 결과를 채팅이 아니라 화면에서 본다)
  collect: {
    at: new Date().toISOString(), searched: 2, found: 152, passed: 19,
    new: 2, queue: 112, calls: 7, limit: 200,
    queries: [{ q: '불륜', total: 134, kept: 16 }, { q: "상간'자", total: 18, kept: 3 }],
    dropped: [{ why: '민사 아님(형사)', n: 47 }],
    top: [{ id: '239083', score: 90, name: '소유권말소등기', court: '서울고등법원', q: '상간자' }],
  },
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
// 2026-08-18 대개편 — 목소리·오디션 카드는 관리자 페이지에서 뺐다.
//   소리를 이제 구글(옴니 플래시)이 영상과 함께 만들기 때문이다.
//   그래서 그 두 버튼을 요구하던 검사도 함께 걷어낸다.
if (!painted.includes('saveThumb(')) {
  console.error('❌ 썸네일 카드가 검사에 안 들어왔다 — 그 안의 버튼을 검사하지 못했다');
  console.error('   (2026-08-09 손님이 갇힌 [썸네일 다운받기] 가 바로 그 버튼이다)');
  process.exit(1);
}
// '아직 안 살펴봄' 판례에 **무슨 사건인지 보는 버튼**이 붙어 있는지 본다.
// (2026-08-09 손님: "아직 안 살펴봄으로 구분된 판례는 요약본을 볼 수가 없잖아")
// FAKE_STATE 의 184051 이 바로 그런 건이다 — one_line 이 없는 판례.
if (!painted.includes('showCase(')) {
  console.error('❌ 아직 안 살펴본 판례에 [무슨 사건인지 보기] 버튼이 없다');
  console.error('   요약을 볼 방법이 다시 사라졌다는 뜻이다');
  process.exit(1);
}
// 수집 결과가 **화면에** 나오는지 본다.
// (2026-08-10 손님: "내가 여기 채팅창 들어와서 봐야겠냐?")
if (!painted.includes('지난 수집 결과')) {
  console.error('❌ 지난 수집 결과 카드가 화면에 없다');
  console.error('   수집 결과를 관리자 페이지에서 볼 방법이 사라졌다는 뜻이다');
  process.exit(1);
}
if (!painted.includes('낱말별로 몇 건 걸렸나')) {
  console.error('❌ 수집 결과에 낱말별 내역이 없다 — 왜 0건인지 알 수가 없다');
  process.exit(1);
}
// 대기열을 **갈래로 골라 보는 단추**가 있는지 본다.
// (2026-08-10 손님: "소재 대기열에는 내가 원하지 않는 것만 띄워놓고… 더 볼 수 있게 해줘")
if (!painted.includes('pickTopic(')) {
  console.error('❌ 대기열에 갈래(상속·불륜…)를 고르는 단추가 없다');
  console.error('   원하는 갈래만 골라 볼 방법이 사라졌다는 뜻이다');
  process.exit(1);
}
// **다음에 할 일** 카드가 맨 위에 있는지 본다.
// (2026-08-10 손님: "나한테 깃허브 가서 뭘 하라고 시키지마. 귀찮고 어려워")
// 이 카드가 없으면 손님이 다시 '실행' 칸에서 네 가지를 골라야 한다.
if (!painted.includes('다음에 할 일')) {
  console.error('❌ 맨 위 [다음에 할 일] 카드가 없다');
  console.error('   한 번만 눌러 다음 단계로 가는 방법이 사라졌다는 뜻이다');
  process.exit(1);
}
if (!painted.includes('goNext(')) {
  console.error('❌ [다음에 할 일] 카드에 누를 버튼이 없다');
  process.exit(1);
}
// 그 버튼이 판례 번호를 **직접 넣지 않는지** 본다. 손으로 넣으면 소재
// 살펴보기를 건너뛴다 — 가사사건으로 Opus 를 19분 헛돌린 원인이 그것이다.
{
  const blk = (src.match(/const NEXT_RUN[\s\S]*?\n};/) || [''])[0];
  if (/\bcase:\s*'[^']/.test(blk)) {
    console.error('❌ [다음에 할 일] 버튼이 판례 번호를 직접 넣고 있다');
    console.error('   비워 둬야 통과한 소재 중 가장 좋은 것을 알아서 고른다');
    process.exit(1);
  }
}
// 화면을 통째로 옮기는 링크가 다시 생기지 않았는지 본다 (아이폰이 갇히는 원인)
if (/<a[^>]+download=[^>]+href="\/api\/thumb/.test(painted)) {
  console.error('❌ 썸네일을 링크로 내려받고 있다 — 아이폰에서 저장 화면에 갇힌다');
  console.error('   화면을 옮기지 말고 saveThumb() 처럼 그림만 받아야 한다');
  process.exit(1);
}

for (const f of [mod, js]) { try { unlinkSync(f); } catch {} }
console.log('✅ 관리자 페이지: 바깥 코드 + 브라우저 코드 둘 다 정상');

// ⭐⭐⭐ 2026-08-26 손님: "3-2가 관리자페이지에 없잖나…"
//   맞았다. WORKFLOWS 에 **적어만 두고** wfList 목록에 안 넣어서 video.yml(3-2)
//   과 keycheck.yml 이 화면에 한 번도 안 나왔다. 정의해 둔 것과 그려지는 것이
//   따로 놀았는데 아무 검사도 그걸 안 봤다. 이제 여기서 본다.
{
  const list = src.match(/const WORKFLOWS = \[[\s\S]*?\n\];/);
  if (!list) { console.error('❌ WORKFLOWS 목록을 못 찾았다'); process.exit(1); }
  // ⚠️ 첫 시도는 file:…hidden:true 를 한 번에 훑어 **맨 앞 이름**을 숨김으로
  //    잡았다(youtube-upload 대신 collect 가 걸렸다). 항목 단위로 쪼개서 본다.
  const items = list[0].split(/\{\s*file:/).slice(1);
  const defined = [];
  const hidden = [];
  for (const it of items) {
    const m = it.match(/^\s*'([^']+)'/);
    if (!m) continue;
    defined.push(m[1]);
    if (/hidden:\s*true/.test(it)) hidden.push(m[1]);
  }
  const drawn = new Set(
    [...src.matchAll(/wfList\(\[([^\]]*)\]\)/g)]
      .flatMap((m) => [...m[1].matchAll(/'([^']+)'/g)].map((x) => x[1])));
  const missing = defined.filter((f) => !hidden.includes(f) && !drawn.has(f));
  if (missing.length) {
    console.error('❌ 목록에 적어만 두고 화면에 안 그리는 단추: ' + missing.join(', '));
    console.error('   wfList([...]) 에 넣어야 손님이 누를 수 있다');
    process.exit(1);
  }
  console.log(`✅ 적어 둔 단추 ${defined.length}개가 전부 화면에 그려진다 `
            + `(숨김 ${hidden.length}개 제외)`);
}

// ⚠️ 2026-08-26 — 칸의 기본값(v:)이 화면에 안 찍히고 있었다. 손님이 S001·1 을
//   매번 손으로 넣어야 했다. inp.def 만 보고 inp.v 를 안 봤기 때문이다.
{
  if (!/inp\.def !== undefined \? inp\.def : \(inp\.v/.test(src)) {
    console.error('❌ 칸 기본값을 inp.v 에서 안 읽는다 — 칸이 늘 비어 보인다');
    process.exit(1);
  }
  console.log('✅ 칸에 정해 둔 기본값이 찍힌다 (S001 · 1 을 손으로 안 넣어도 된다)');
}
