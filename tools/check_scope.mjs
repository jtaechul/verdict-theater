// ⭐ 워크플로를 부를 때 **그 칸에 없는 것**을 넘기지 않는가 본다.
//
// ⚠️⚠️ 2026-08-22 사고 — /api/upload-clips 에 `const cut` 을 넣으면서, 똑같은
//    문장이 /api/voice 에도 있는 줄 모르고 **두 군데를 한꺼번에** 바꿨다
//    (파이썬 replace 는 기본이 '전부 바꾸기'다).
//    /api/voice 에는 cut 이라는 것이 없으니, 버튼을 누르면 그냥 실패한다.
//    문법은 멀쩡해서 node --check 도 다른 검사도 다 통과했다 — 눈으로만 못 잡는다.
//
// 여기서는 **워크플로에 넘기는 값(inputs)** 만 좁혀서 본다. 넓게 훑으면
// 문자열 속 낱말까지 걸려 헛경보가 쏟아진다 (실제로 그랬다).
import { readFileSync } from 'node:fs';

// 파일을 인자로 받을 수 있게 해 둔다 — 그래야 **일부러 망가뜨린 판**으로
// 이 검사기가 진짜 잡는지 스스로 시험할 수 있다.
const FILE = process.argv[2]
  || new URL('../admin/worker.js', import.meta.url);
const src = readFileSync(FILE, 'utf8');
const MARK = "if (url.pathname === '";
const at = [];
for (let i = src.indexOf(MARK); i >= 0; i = src.indexOf(MARK, i + 1)) at.push(i);
const declared = (t) => {
  const out = new Set();
  for (const m of t.matchAll(/\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)/g)) out.add(m[1]);
  for (const m of t.matchAll(/\b(?:const|let|var)\s*\{([^}]*)\}\s*=/g))
    for (const w of m[1].split(',')) {
      const n = w.split(':').pop().trim();
      if (/^[A-Za-z_$][\w$]*$/.test(n)) out.add(n);
    }
  for (const m of t.matchAll(/\bfunction\s+([A-Za-z_$][\w$]*)/g)) out.add(m[1]);
  return out;
};

// ⚠️ '바깥'을 통째로 믿으면 안 된다. 이 파일에는 **브라우저에서 도는 글**도
//    통짜 문자열로 들어 있는데, 거기에도 같은 이름(cut 같은)이 있어서
//    "바깥에 있으니 괜찮다"고 넘겨 버렸다 (실제로 이 검사기가 처음엔 못 잡았다).
//    워크플로에 넘기는 값은 **언제나 그 요청에서 뽑은 것**이므로,
//    같은 칸 안에서 만든 것만 받아 준다.
const OK_ANYWHERE = new Set(['String', 'Number', 'JSON', 'Boolean', 'null',
                             'true', 'false', 'undefined']);
const bad = [];
let seen = 0;
at.forEach((p, k) => {
  const name = src.slice(p + MARK.length, src.indexOf("'", p + MARK.length));
  const body = src.slice(p, at[k + 1] ?? src.length);
  const mine = declared(body);
  for (const m of body.matchAll(/\binputs:\s*([^\n]*)/g)) {
    seen++;
    // ⚠️ `only: ''` 처럼 **이름표(key)** 는 값이 아니다. 이름표 뒤에 값이
    //    따로 있으면 그 이름표는 빼고 본다. 다만 `{ sid, ep }` 처럼 이름표와
    //    값이 같은 짧은 꼴은 값이기도 하므로 그대로 둔다.
    const expr = m[1].replace(/\b[A-Za-z_$][\w$]*\s*:/g, ' ');
    for (const t of expr.matchAll(/[A-Za-z_$][\w$]*/g)) {
      const n = t[0];
      if (mine.has(n) || OK_ANYWHERE.has(n)) continue;
      bad.push(`${name} 칸이 워크플로에 '${n}' 을(를) 넘기는데, `
             + `그건 이 칸에 없는 것입니다 (다른 칸에서 만든 것)`);
    }
  }
});

if (bad.length) {
  console.log('❌ 없는 것을 워크플로에 넘깁니다 — 버튼을 누르면 그냥 실패합니다\n');
  for (const x of bad) console.log('   · ' + x);
  process.exit(1);
}
console.log(`✅ 워크플로에 넘기는 값 ${seen}군데: 다 그 칸에 있는 것입니다`);
