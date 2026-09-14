#!/usr/bin/env node
/* ⭐ 화면이 **편 수를 세어서 적는지** 본다. 값 0원.
 *
 *     node tools/partcount_check.js
 *
 * 2026-09-14 손님: "이거 4편인 거지? 오타가 맞지?"
 *   S92 는 4편인데 단추에는 "세 편 예약 공개로 올리기" 라고 떠 있었다.
 *   화면 아홉 군데에 **"세 편" 이 글자로 박혀** 있었다. 편 수는 대본이
 *   정하는데 화면만 셋으로 굳어 있으면, 손님은 매번 화면을 의심해야 한다.
 *   (접힘 목록 FOLD_OPEN 바로 위에는 "편 수는 사건마다 다르므로 번호를
 *    하나씩 적어 두지 않는다" 고 적혀 있었고, 바로 아랫줄에서 어겼다.)
 *
 * ⚠️ 이 검사는 **주석은 빼고 화면에 나가는 글자만** 본다. 주석에 남은
 *    '세 편' 은 지난 사고를 적어 둔 기록이라 지우면 안 된다.
 */
import { readFileSync } from 'node:fs';

const src = readFileSync(new URL('../admin/worker.js', import.meta.url), 'utf8');
const bad = [];
const ck = (name, ok) => { console.log((ok ? '  ✅ ' : '  ❌ ') + name); if (!ok) bad.push(name); };

// 주석(//…)을 걷어낸 뒤 화면 글자만 남긴다
const code = src.split('\n')
  .map((l) => l.replace(/^\s*\/\/.*$/, '').replace(/\s\/\/\s.*$/, ''))
  .join('\n');

console.log('■ ① 편 수를 글자로 박아 두지 않는다');
const stuck = ['한 편', '두 편', '세 편', '네 편', '다섯 편']
  .filter((w) => code.includes("'" + w) || code.includes(w + " 예약")
                 || code.includes(w + " 만들기") || code.includes(w + " 모두"));
ck('화면 글자에 "N 편" 이 박혀 있지 않다 (' + (stuck.join(' · ') || '없음') + ')',
   stuck.length === 0);

console.log('\n■ ② 세어서 적는 도우미가 있고, 실제로 쓰인다');
ck('partWord(n) 이 있다', /function partWord\(n\)/.test(code));
ck('workParts() 가 지금 사건의 편 수를 센다',
   /function workParts\(\)/.test(code) && /partList\(\(WORKS/.test(code));
const uses = (code.match(/partWord\(/g) || []).length;
ck('편 수를 적는 자리마다 쓴다 (' + uses + '군데)', uses >= 8);

console.log('\n■ ③ 우리말로 제대로 센다');
// worker.js 에서 함수만 떼어다 그대로 돌려 본다 (흉내 내지 않는다)
const body = code.slice(code.indexOf('function partWord(n)'));
const fn = new Function(body.slice(0, body.indexOf('\n}\n') + 3) + '\nreturn partWord;')();
const want = [[1, '한 편'], [3, '세 편'], [4, '네 편'], [5, '다섯 편'], [11, '11편'], [0, '0편']];
for (const [n, w] of want) ck(`${n} → ${w}`, fn(n) === w);

console.log('\n■ ④ 접힘 목록이 편 수가 든 제목도 알아본다');
//    제목이 "③ 네 편 만들기" 로 바뀌므로 '③ 세 편 만들기' 로 적어 두면 못 찾는다
const fold = (code.match(/const FOLD_OPEN = \[[^\]]*\]/s) || [''])[0];
//    ⚠️ '90초 한 편' 은 카드 **이름**이지 편 수가 아니다 — 헛걸리면 안 된다
ck('접힘 목록에 "N 편 만들기" 가 박혀 있지 않다',
   !/[한두세네]\s*편\s*만들기/.test(fold));
ck("'③ ' 앞부분으로 맞춘다", /'③ '/.test(fold));

console.log('\n' + '─'.repeat(60));
if (bad.length) {
  console.log(`❌ 편 수 세기: ${bad.length}군데`);
  bad.forEach((b) => console.log('     ' + b));
  process.exit(1);
}
console.log('✅ 편 수 세기: 화면이 언제나 대본을 세어서 적는다');
