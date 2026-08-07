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
globalThis.fetch = async () => ({
  status: 200, ok: true,
  json: async () => ({ episodes: {}, queue: [], runs: [], videos: {}, items: [] }),
});
globalThis.scrollTo = () => {};
globalThis.alert = () => {};
globalThis.confirm = () => false;

try {
  new Function(readFileSync(js, 'utf8'))();
} catch (e) {
  console.error(`❌ 브라우저 코드가 첫 실행에서 죽는다 — 페이지가 '불러오는 중…' 에서 멈춘다`);
  console.error(`   ${e.constructor.name}: ${e.message}`);
  process.exit(1);
}

for (const f of [mod, js]) { try { unlinkSync(f); } catch {} }
console.log('✅ 관리자 페이지: 바깥 코드 + 브라우저 코드 둘 다 정상');
