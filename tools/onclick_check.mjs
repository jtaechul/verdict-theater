// 단추가 부르는 함수가 **실제로 있는가**.
//
// 왜 이 검사가 있는가 (2026-08-23)
//   운영자: "우리 한국어 목소리, 구글이 만든 소리 둘다 클릭안되서
//            한가지 동영상이 나오는데 이게 어떤 영상인지 몰라."
//   단추는 멀쩡히 그려지는데 pickAudio() 함수가 통째로 사라져 있었다.
//   눌러도 아무 일이 안 일어난다. **화면만 봐서는 절대 안 보이는 고장**이라
//   기계가 매번 대조한다.
//
//   쓰기: node tools/onclick_check.mjs      인터넷 0회 · 0원 · 1초

import { readFileSync, writeFileSync } from 'fs';
import { tmpdir } from 'os';
import { join } from 'path';

const src = readFileSync('admin/worker.js', 'utf8');
const mod = join(tmpdir(), 'vt-onclick.mjs');
writeFileSync(mod, src.replace('export default', 'const _wk =') + '\nexport { appHtml };\n');
const { appHtml } = await import('file://' + mod + '?t=' + Date.now());
const js = appHtml().match(/<script>([\s\S]*?)<\/script>/)[1];

// 화면 쪽에 정의된 이름들
const defined = new Set();
for (const m of js.matchAll(/\bfunction\s+([A-Za-z_$][\w$]*)\s*\(/g)) defined.add(m[1]);
for (const m of js.matchAll(/\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\()/g))
  defined.add(m[1]);

// 단추가 부르는 이름들 — 소스의 onclick 문자열에서 뽑는다
const called = new Map();
for (const m of src.matchAll(/onclick="([A-Za-z_$][\w$]*)\(/g)) called.set(m[1], 'onclick');
for (const m of src.matchAll(/mini\([^,]+,\s*'([A-Za-z_$][\w$]*)\(/g)) called.set(m[1], 'mini()');
for (const m of src.matchAll(/\bmini\(\s*'[^']*',\s*'([A-Za-z_$][\w$]*)\(/g)) called.set(m[1], 'mini()');

const OK = new Set(['alert', 'confirm', 'open', 'history']);
const missing = [...called].filter(([n]) => !defined.has(n) && !OK.has(n));

console.log('='.repeat(58));
console.log('단추가 부르는 함수가 실제로 있는가 (값 0원)');
console.log('='.repeat(58));
console.log(`  단추가 부르는 이름 ${called.size}개 · 화면에 정의된 이름 ${defined.size}개`);
if (missing.length) {
  for (const [n, where] of missing) {
    console.log(`   ❌ ${n}()  — ${where} 가 부르는데 정의가 없다. 눌러도 아무 일이 안 난다`);
  }
  console.log('-'.repeat(58));
  console.log(`❌ ${missing.length}개가 먹통이다`);
  process.exit(1);
}
console.log('-'.repeat(58));
console.log('✅ 단추가 부르는 함수가 전부 있다.');
