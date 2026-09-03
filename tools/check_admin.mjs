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

// ⚠️⚠️ 2026-08-27 — 화면을 '지금 절차만' 으로 줄이면서(SIMPLE=true) 16화 쪽
//    카드가 안 그려지자, 그 카드 속 버튼을 보던 검사들이 통째로 헛돌았다.
//    감춘 것도 **여전히 성해야** 한다(되돌릴 때 깨져 있으면 안 된다).
//    → 검사는 SIMPLE 을 꺼서 **모든 카드를 그려** 본다. 화면에 실제로 무엇이
//      보이는지는 아래 'SIMPLE 검사' 가 따로 본다.
const CLIENT = readFileSync(js, 'utf8');
let api;
try {
  api = new Function(CLIENT.replace('const SIMPLE = true;', 'const SIMPLE = false;')
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

// ⭐⭐⭐ 2026-08-27 손님(스크린샷): "여기서 뭘 어떻게 넣으라는거야. 아무것도할수없잖아."
//   손이 필요한 칸(파일을 고르는 칸)이 **접힌 채로** 나왔다. 제목 한 줄만 보이고
//   안이 안 보이니 아무것도 못 하신다. 접기 목록(FOLD_OPEN)에 없으면 접힌다.
//   → 파일 고르는 칸이 있는 카드는 **처음부터 펴져 있어야** 한다.
// ⭐⭐⭐ 2026-09-03 손님: "막 쓸데없이 프롬프트나 이런 것 너무 많이 들어가 있어.
//   감추기를 하거나 하게 해야 될 거 같고. 불필요한 것들."
//   두 말이 부딪히는 것 같지만 아니다. 손님이 못 견디는 것은 **꼭 해야 하는 일이
//   숨어 있는 것**이지, 안 해도 되는 일이 접혀 있는 것이 아니다. 그래서 규칙을
//   하나로 합친다 —
//     · 안 해도 되는 칸이면 → 제목에 '안 하셔도 됩니다' 라고 **적어 두고** 접는다
//     · 그 말이 없으면 → 꼭 해야 하는 칸이니 처음부터 펴져 있어야 한다
//   즉 접으려면 화면에 "안 하셔도 된다"고 말해야 한다. 말없이 감추는 것은 막는다.
{
  const open = (src.match(/const FOLD_OPEN = \[([^\]]*)\]/) || [, ''])[1];
  const opens = [...open.matchAll(/'([^']+)'/g)].map((m) => m[1]);
  // ⚠️ 칸 제목에 data-t="..." 가 붙기도 한다(접기 열쇠를 못 박으려고).
  //    <h2> 만 찾으면 그런 칸을 통째로 못 보고 지나쳐 검사가 헛돈다.
  const RE = /<div class="card">\s*'?\s*\+?\s*'?<h2([^>]*)>/g;
  const at = [];
  for (let m; (m = RE.exec(src)); ) at.push([m.index, m[1], m.index + m[0].length]);
  const bad = [];
  at.forEach((t, k) => {
    const [p, attr, end] = t;
    const body = src.slice(p, at[k + 1] ? at[k + 1][0] : src.length);
    if (!/type="file"/.test(body)) return;
    const dt = (attr.match(/data-t="([^"]*)"/) || [, ''])[1];
    const title = (dt || (src.slice(end).match(/^([^'<]+)/) || [, ''])[1]).trim();
    if (opens.some((x) => title.indexOf(x) === 0)) return;   // 펴져 있다 — 됐다
    const hEnd = body.indexOf('</h2>');
    const head = hEnd < 0 ? '' : body.slice(0, hEnd);
    if (/안 하셔도 됩니다/.test(head)) return;                // 접어도 된다고 적었다
    bad.push(title || '(이름 없음)');
  });
  if (bad.length) {
    console.error('❌ 파일을 고르는 칸인데 말없이 접혀 있다: ' + bad.join(' · '));
    console.error('   제목 한 줄만 보여 손님이 아무것도 못 합니다.');
    console.error('   꼭 해야 하는 칸이면 FOLD_OPEN 에 넣어 펴 두고,');
    console.error('   안 하셔도 되는 칸이면 제목에 "안 하셔도 됩니다" 라고 적으십시오.');
    process.exit(1);
  }
  console.log('✅ 파일 고르는 칸: 꼭 할 것은 펴져 있고, 접힌 것은 안 해도 된다고 적혀 있다');
}


// ⭐⭐⭐ 2026-08-27 손님: "쓸데 없는 기능들 다 지워. 우리가 지금 절차에서 정한 거
//   외에는 일단 다 감춰놓거나 삭제하고 돈 세는 부분 없는지도 지금 체크해."
//   화면에 **실제로 보이는 단추**가 지금 절차뿐인지 본다.
{
  const list = src.match(/const WORKFLOWS = \[[\s\S]*?\n\];/)[0];
  const shown = list.split(/\{\s*file:/).slice(1)
    .filter((x) => !/hidden:\s*true/.test(x))
    .map((x) => x.match(/^\s*'([^']+)'/)[1]);
  // 지금 절차에서 보여도 되는 단추
  //   voice-route.yml — 2026-08-31 손님: "지금 어느 창구인지 확인해서
  //   알려줘." 목소리를 하루 몇 번까지 만들어 주는지 보는 단추다.
  //   1원 미만이고, 돈 쓰기 전에 이걸 봐야 한 편이 중간에 망가지지 않는다.
  //
  //   ⭐⭐⭐ collect.yml — 2026-09-02 손님: "지금 사건이 다 유류분이나 상속
  //   이런 거밖에 없어. 내가 분명히 불륜이나 이런 것들도 수집하라고 했잖아."
  //   맞다. 그리고 그 원인이 **바로 이 검사**였다. 2026-08-27 에 "지금 절차
  //   밖" 이라며 모으기 단추를 감췄고, 이 검사가 그것을 못으로 박아 두었다.
  //   그런데 화면은 손님의 **유일한 조작 수단**이다 — 감추는 순간 새 소재를
  //   모을 길이 사라지고, 대기열은 옛날에 모은 상속만 남는다.
  //   "쓸데없는 것을 감춘다" 는 규칙이 **일을 못 하게 만드는 데까지** 갔다.
  //   → 절차에 꼭 필요한 단추는 보여야 한다. 값이 드는 단추는 화면에
  //     값을 적어 두고(desc), 누르기 전에 얼마인지 보이게 하는 것으로 막는다.
  const OK = ['keycheck.yml', 'voice-route.yml', 'collect.yml'];
  const extra = shown.filter((f) => !OK.includes(f));
  // ⭐ 값이 드는 단추는 **화면에 얼마인지 적혀 있어야** 한다.
  //    감추는 대신 이것으로 막는다 — 손님은 누르기 전에 값을 보신다.
  const PAID = ['collect.yml'];
  const noPrice = PAID.filter((f) => {
    const blk = list.split(/\{\s*file:/).slice(1)
      .find((x) => (x.match(/^\s*'([^']+)'/) || [])[1] === f) || '';
    return !/원/.test(blk);
  });
  if (noPrice.length) {
    console.error('❌ 값이 드는 단추인데 화면에 값이 안 적혀 있다: '
                  + noPrice.join(', '));
    console.error('   desc 에 "약 ○○원" 을 적으십시오 — 누르기 전에 보이게');
    bad = 1;
  } else {
    console.log('✅ 값이 드는 단추는 화면에 값이 적혀 있다');
  }
  if (extra.length) {
    console.error('❌ 지금 절차 밖인데 화면에 보이는 단추: ' + extra.join(', '));
    console.error('   눌리면 돈이 나갈 수 있습니다 — hidden: true 를 붙이십시오');
    process.exit(1);
  }
  if (!/const SIMPLE = true;/.test(src)) {
    console.error('❌ SIMPLE 이 켜져 있지 않다 — 16화 화면이 다시 다 나옵니다');
    process.exit(1);
  }
  console.log('✅ 화면에 보이는 단추는 지금 절차뿐이다 (열쇠 점검 + 90초 한 편)');
}

// ⭐⭐⭐ 2026-08-31 — **한 칸 안에서 같은 id 를 두 번 쓰면 안 된다.**
//   90초 편 유튜브 칸을 만들면서 16화 칸과 같은 id(ytmsg)를 썼다가 알아챘다.
//   한 화면에 같은 id 가 둘이면 getElementById 는 **앞의 것만** 집는다 —
//   알림이 엉뚱한 칸에 뜨고, 값을 읽으면 남의 칸 값을 읽는다.
//
//   ⚠️ 다만 **저장소 전체에서 유일할 필요는 없다.** 화면은 한 번에 하나만
//      그려지므로(innerHTML 로 통째로 갈아 끼운다) 다른 화면끼리는 안 겹친다.
//      전체를 유일하게 하라고 하면 ytbox·pl 같은 멀쩡한 것까지 빨간불이 나고,
//      애먼 빨간불은 검사를 못 믿게 만든다.
//      → **한 함수 안**에서 같은 id 를 두 번 그리는 것만 잡는다. 그건 무조건
//        고장이다.
{
  const bad = [];
  // 함수 하나하나를 잘라서 그 안만 본다
  // ⚠️ src(바깥 파일)를 보면 안 된다 — 브라우저 코드가 통째로 들어 있는
  //    appHtml() 하나로 잡혀 화면이 다른 것끼리도 겹쳤다고 나온다.
  //    **브라우저 코드(CLIENT)** 를 함수별로 잘라서 본다.
  for (const m of CLIENT.matchAll(/\n(?:async )?function (\w+)\s*\([^)]*\)\s*\{/g)) {
    const name = m[1];
    let depth = 0, j = m.index + m[0].length - 1, end = j;
    for (; j < CLIENT.length; j += 1) {
      if (CLIENT[j] === '{') depth += 1;
      else if (CLIENT[j] === '}') { depth -= 1; if (depth === 0) { end = j; break; } }
    }
    const body = CLIENT.slice(m.index, end);
    const seen = {};
    for (const g of body.matchAll(/id="([A-Za-z][\w-]*)"/g)) {
      const id = g[1];
      if (/-$/.test(id)) continue;      // 만들 때 번호가 붙는 것(s90f-'+who)
      seen[id] = (seen[id] || 0) + 1;
    }
    for (const [id, n] of Object.entries(seen))
      if (n > 1) bad.push(`${name}() 안에서 ${id} 를 ${n}번`);
  }
  if (bad.length) {
    console.error('❌ 한 칸 안에서 같은 id 를 여러 번 씁니다:');
    for (const b of bad) console.error('   ' + b);
    console.error('   getElementById 가 앞의 것만 집습니다 — 이름을 나누십시오');
    process.exit(1);
  }
  console.log('✅ 한 칸 안에서 같은 id 를 두 번 쓰지 않는다');
}

// ⭐⭐⭐ 2026-09-03 손님: "막 쓸데없이 프롬프트나 이런 것 너무 많이 들어가 있어."
//   컷마다 프롬프트를 통째로 적은 상자(textarea)가 스무 개 깔려 있었다. 화면에
//   3만 자다. 상자를 없애고 [프롬프트 복사] 단추만 남겼는데, 그러면 복사할 글을
//   **화면이 아니라 대본에서** 꺼내야 한다. 이 세 가지가 같이 지켜져야 한다 —
//     ① 프롬프트 상자를 다시 깔지 않는다
//     ② 복사 단추는 남아 있다 (없애면 손님이 프롬프트를 못 가져가신다)
//     ③ 복사할 글을 대본(S90DOC)에서 꺼낸다 (화면에서 꺼내면 상자가 없어 빈손이다)
{
  const bad = [];
  if (/id="s90p-/.test(src))
    bad.push('컷 프롬프트 상자(s90p-)가 화면에 다시 깔려 있다');
  if (!/id="s90cp-/.test(src) || !/프롬프트 복사/.test(src))
    bad.push('[프롬프트 복사] 단추가 사라졌다');
  const cp = (src.match(/function copyCut\([\s\S]*?\n}/) || [''])[0];
  if (!/function cutPrompt/.test(src) || !/cutPrompt\(/.test(cp))
    bad.push('복사할 글을 대본에서 안 꺼낸다 (cutPrompt)');
  if (/getElementById\('s90p-/.test(cp))
    bad.push('복사할 글을 아직 화면 상자에서 꺼낸다 — 상자가 없으니 빈손이 된다');
  if (bad.length) {
    console.error('❌ 컷 프롬프트: ' + bad.join(' · '));
    process.exit(1);
  }
  console.log('✅ 컷 프롬프트: 상자는 없고 단추만 있다 (복사할 글은 대본에서 꺼낸다)');
}

// ⭐ 접기는 #app 바로 아래 칸에만 걸린다. ② 컷별 영상 칸은 #s90cuts 봉지 안에
//   있어서, 그 봉지를 안 보면 아무리 FOLD_OPEN 에서 빼도 영영 안 접힌다.
//   게다가 그 칸은 화면을 그린 **뒤에** 새로 그려지므로 그때 다시 걸어야 한다.
{
  const bad = [];
  const fy = (src.match(/function foldify\(\)[\s\S]*?\n}/) || [''])[0];
  if (!/#s90cuts > \.card/.test(fy))
    bad.push('접기가 #s90cuts 안을 안 본다 — ② 칸이 영영 안 접힌다');
  const sc = (src.match(/async function s90Cuts\(\)[\s\S]*?\n}/) || [''])[0];
  if (!/box\.innerHTML = h;[\s\S]*foldify\(\)/.test(sc))
    bad.push('컷 목록을 새로 그린 뒤 접기를 다시 안 건다');
  if (bad.length) {
    console.error('❌ 접기: ' + bad.join(' · '));
    process.exit(1);
  }
  console.log('✅ 접기가 컷 칸에도 걸린다 (다시 그려도 접힌 채로 남는다)');
}
