// 카드 접기가 **진짜로 접히는지** 본다. 비용 0원.
//
//     node tools/check_fold.mjs
//
// 손님: "안 쓰는 메뉴는 감추기(축소) 기능 활성화 시켜. 스크롤하다가 손가락 뿌러지겠다"
//
// check_admin.mjs 의 가짜 화면은 카드가 없어서(querySelectorAll → 빈 목록)
// "부르다 죽는가" 만 잡는다. 여기서는 카드 세 장짜리 **작은 진짜 화면**을 만들어
//   1. 처음에 무엇이 펴져 있고 무엇이 접혀 있는지
//   2. 제목을 누르면 접히고 다시 눌러 펴지는지
//   3. 접은 상태를 기억해 다음에도 접혀 있는지
// 를 실제로 눌러 보며 확인한다.

import { readFileSync } from 'fs';

// ── 아주 작은 가짜 브라우저 (foldify 가 쓰는 것만) ─────────
class El {
  constructor(tag) {
    this.tag = tag; this.children = []; this.parentElement = null;
    this.dataset = {}; this.style = {}; this._text = ''; this.onclick = null;
    this._cls = new Set();
    this.classList = {
      add: (c) => this._cls.add(c),
      toggle: (c, on) => { on ? this._cls.add(c) : this._cls.delete(c); },
      has: (c) => this._cls.has(c),
    };
  }
  get className() { return [...this._cls].join(' '); }
  set className(v) { this._cls = new Set(String(v).split(/\s+/).filter(Boolean)); }
  appendChild(c) {
    if (c.parentElement) c.parentElement.children = c.parentElement.children.filter(x => x !== c);
    c.parentElement = this; this.children.push(c); return c;
  }
  get nextSibling() {
    const s = this.parentElement && this.parentElement.children;
    if (!s) return null;
    return s[s.indexOf(this) + 1] || null;
  }
  get textContent() {
    return this._text + this.children.map(c => c.textContent).join('');
  }
  set textContent(v) { this._text = v; this.children = []; }
  querySelector(sel) {
    for (const c of this.children) {
      if (c.tag === sel) return c;
      const d = c.querySelector(sel);
      if (d) return d;
    }
    return null;
  }
}

function makeCard(title, bodyBits) {
  const card = new El('div');
  card.className = 'card';
  const h = new El('h2');
  h.textContent = title;
  card.appendChild(h);
  bodyBits.forEach(b => { const d = new El('div'); d.textContent = b; card.appendChild(d); });
  return card;
}

const app = new El('div');
const CARDS = [
  ['다음에 할 일', ['대본을 만들 차례입니다']],
  ['대기열 (점수순)', ['판례1', '판례2', '판례3']],
  ['최근 실행', ['실행1', '실행2']],
];
CARDS.forEach(([t, b]) => app.appendChild(makeCard(t, b)));

// ⭐⭐⭐ 2026-09-03 — ② 컷별 영상 칸은 #app 바로 아래가 아니라 **#s90cuts 봉지
//   안**에 들어 있다. 그래서 접기가 여태 안 걸렸다(제목을 눌러도 안 접혔다).
//   foldify 가 이제 두 자리를 다 본다 — 가짜 화면도 두 자리를 다 갖춰야
//   진짜와 같은 것을 시험하는 셈이 된다.
const cuts = new El('div');
cuts.appendChild(makeCard('② 컷별 영상 — 안 하셔도 됩니다', ['컷1', '컷2']));

// 쉼표로 이어 붙인 고르개('#app > .card, #s90cuts > .card')를 알아듣는다.
const BOX = { '#app': app, '#s90cuts': cuts };
const pick = (sel) => {
  const out = [];
  for (const one of String(sel).split(',')) {
    const m = one.trim().match(/^(#[\w-]+) > \.card$/);
    if (!m) continue;
    const box = BOX[m[1]];
    if (box) for (const c of box.children) if (out.indexOf(c) < 0) out.push(c);
  }
  return out;
};

const store = {};
globalThis.localStorage = {
  getItem: (k) => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
};
globalThis.document = {
  querySelectorAll: pick,
  createElement: (t) => new El(t),
};

// ── worker.js 안의 브라우저 코드에서 접기 부분만 꺼내 돌린다 ──
const src = readFileSync('admin/worker.js', 'utf8');
const grab = (re, what) => {
  const m = src.match(re);
  if (!m) { console.error(`❌ ${what} 를 worker.js 에서 못 찾았다 — 접기 기능이 사라졌다`); process.exit(1); }
  return m[0];
};
const code = [
  grab(/const FOLD_OPEN = \[[^\]]*\];/, 'FOLD_OPEN'),
  grab(/const foldKey = [^\n]+/, 'foldKey'),
  grab(/function setFold\([\s\S]*?\n}/, 'setFold'),
  grab(/function foldify\(\)[\s\S]*?\n}\n/, 'foldify'),
].join('\n').replace(/\\\\'/g, "\\'");
const foldify = new Function(code + '\nreturn foldify;')();

let ok = true;
const fail = (m) => { console.error('❌ ' + m); ok = false; };
const shown = (card) => {
  const body = card.children[card.children.length - 1];
  return body.style.display !== 'none';
};
const head = (card) => card.children[0];

// ── 1) 처음 상태 ──
foldify();
if (!shown(app.children[0])) fail('[다음에 할 일] 이 처음부터 접혀 있다 — 이건 늘 보여야 한다');
if (shown(app.children[1])) fail('[대기열] 이 처음부터 펴져 있다 — 길어서 접혀 있어야 한다');
if (shown(app.children[2])) fail('[최근 실행] 이 처음부터 펴져 있다 — 접혀 있어야 한다');
if (ok) console.log('✅ 처음 상태: 중요한 것만 펴져 있고 긴 것은 접혀 있다');

// ── 2) 눌러서 접었다 폈다 ──
head(app.children[0]).onclick();
if (shown(app.children[0])) fail('제목을 눌렀는데 안 접힌다');
head(app.children[0]).onclick();
if (!shown(app.children[0])) fail('다시 눌렀는데 안 펴진다');
if (ok) console.log('✅ 제목을 누르면 접히고, 다시 누르면 펴진다');

// ── 3) 접은 것을 기억하는가 ──
head(app.children[0]).onclick();          // 접어 둔다
const app2 = new El('div');
CARDS.forEach(([t, b]) => app2.appendChild(makeCard(t, b)));
BOX['#app'] = app2;
foldify();                                 // 화면을 다시 그린 셈
if (shown(app2.children[0])) fail('접어 뒀는데 다시 그리니 또 펴져 있다 — 기억을 못 한다');
else console.log('✅ 접어 둔 것은 다음에 열어도 접혀 있다');

// ── 4) 두 번 훑어도 망가지지 않는가 ──
const before = app2.children[1].children.length;
foldify();
if (app2.children[1].children.length !== before)
  fail('두 번 훑으면 카드 속이 겹쳐 쌓인다');
else console.log('✅ 여러 번 훑어도 화면이 겹치지 않는다');

// ── 5) 봉지(#s90cuts) 안에 있는 칸도 접히는가 ──
//   손님: "그 안에 들어가 보면은 막 쓸데없이 프롬프트나 이런 것 너무 많이
//   들어가 있어. 감추기를 하거나 하게 해야 될 거 같고."
//   ② 컷별 영상 칸은 '안 하셔도 됩니다' 라고 적어 두고 접어 둔다. 그런데 이
//   칸은 #app 바로 아래가 아니라 봉지 안에 있어서, 봉지를 안 보면 접기가
//   아예 안 걸린다 — 눌러도 안 접히고 처음부터 펴진 채로 남는다.
const cut = cuts.children[0];
if (shown(cut)) fail('[② 컷별 영상] 이 처음부터 펴져 있다 — 안 해도 되는 칸이다');
else if (!head(cut).onclick) fail('[② 컷별 영상] 제목을 눌러도 아무 일이 없다');
else {
  head(cut).onclick();
  if (!shown(cut)) fail('[② 컷별 영상] 제목을 눌렀는데 안 펴진다');
  else console.log('✅ 봉지 안에 있는 칸도 접히고, 눌러서 펼 수 있다');
}

console.log(ok ? '\n✅ 카드 접기: 정상' : '\n❌ 카드 접기: 문제 있음');
process.exit(ok ? 0 : 1);
