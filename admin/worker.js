/**
 * 판결극장 관리자 페이지 — Cloudflare Workers
 *
 * 왜 필요한가
 *   12분 대본은 컷 113개짜리 JSON 이다. 아이폰 GitHub 앱에서 그걸 읽는 것은 불가능하다.
 *   이 페이지가 대본을 사람이 읽는 모양으로 보여주고, 버튼 하나로 워크플로를 돌린다.
 *
 * 왜 GitHub Pages 가 아닌가
 *   저장소가 비공개다. 무료 요금제에서 비공개 저장소는 Pages 를 쓸 수 없다.
 *   Cloudflare Workers 는 비공개든 아니든 상관없고 무료다.
 *
 * 필요한 값 (wrangler secret 으로 넣는다)
 *   GH_TOKEN        저장소 접근 토큰 (contents: read, actions: read+write)
 *   ADMIN_PASSWORD  이 페이지에 들어올 비밀번호
 *   SESSION_SECRET  로그인 상태를 위조하지 못하게 서명하는 값
 *
 * 보안
 *   토큰은 브라우저로 절대 내려가지 않는다. 모든 GitHub 호출은 이 Worker 안에서만 일어난다.
 *   로그인은 비밀번호 → 서명된 쿠키. 쿠키를 손으로 고쳐도 서명이 깨져 통과하지 못한다.
 */

const REPO = 'jtaechul/verdict-theater';
const BRANCH = 'main';
const GH = 'https://api.github.com';

const WORKFLOWS = [
  // ⚠️ 각 항목의 **보내는 값**(opts 의 문자열 또는 {v:...})은 워크플로가 아는 글자
  //    그대로여야 한다. 쉬운 말은 **보이는 글**(t)과 help 에만 쓴다.
  //    (2026-08-08 손님: "알아듣기 어려운 부분은 전부 쉽게 알아보게 바꿔")
  { file: 'build-assets.yml', name: '0. 그림·소리 만들기',
    desc: '영상에 쓸 등장인물 그림, 배경 그림, 효과음을 만듭니다 (처음에 한 번만)',
    inputs: [{ k: 'what', label: '무엇을 만들까요', type: 'select',
               help: '효과음은 값이 들지 않습니다. 그림은 한 장씩 값이 듭니다.',
               opts: [{ v: '소리 (비용 0원)', t: '효과음 (0원)' },
                      { v: '캐릭터 한 명 시험', t: '등장인물 한 명만 시험 삼아' },
                      { v: '캐릭터 전부', t: '등장인물 전부' },
                      { v: '배경 전부', t: '배경 그림 전부' },
                      { v: '빠진 것 확인만', t: '빠진 그림이 있는지 확인만 (0원)' }] }] },

  { file: 'collect.yml', name: '1. 재판 기록 모으기',
    desc: '나라의 판례 자료실에서 실제 재판 기록을 받아와, 쓸 만한 것만 골라 대기열에 쌓습니다',
    inputs: [{ k: 'max_calls', label: '자료실에 물어볼 횟수', type: 'text', def: '180',
               help: '자료실이 하루 200번까지만 답해 줍니다. 그래서 180이 기본값입니다. '
                   + '그대로 두고 실행하시면 됩니다. (한 번 물으면 기록 여러 건이 옵니다)' },
             { k: 'queries', label: '찾을 낱말', type: 'text', def: '',
               help: '비워 두면 미리 정해 둔 낱말 40개(상속·유언 등)로 모두 찾습니다. 그대로 두십시오.' }] },

  { file: 'script.yml', name: '2. 대본 만들기',
    desc: '재판 기록을 골라 12분 본편 대본과 쇼츠 3편 대본을 씁니다 (약 10분)',
    inputs: [{ k: 'mode', label: '어디까지 할까요', type: 'select',
               help: '보통은 맨 위 그대로 두십시오. 소재 고르기와 대본 쓰기를 한 번에 합니다.',
               opts: [{ v: '둘다', t: '소재 고르고 대본까지 (보통 이것)' },
                      { v: '소재 심사만', t: '소재 고르기만 (대본은 안 씀)' },
                      { v: '대본 생성만', t: '이미 고른 소재로 대본만' },
                      { v: '쇼츠만 다시', t: '쇼츠 대본만 다시 쓰기' }] },
             { k: 'writer', label: '대본을 쓸 AI', type: 'select',
               help: '그대로 두십시오. 앞의 AI가 막히면 저절로 다른 AI가 이어서 씁니다.',
               opts: [{ v: '자동 (Claude 우선)', t: '자동 (권장)' },
                      { v: 'Claude', t: 'Claude 로만' },
                      { v: 'Gemini', t: 'Gemini 로만' }] },
             { k: 'gate_limit', label: '살펴볼 기록 수', type: 'text', def: '10',
               help: '대기열 위에서부터 몇 건을 AI가 읽어보고 고를지입니다. 10이면 넉넉합니다.' },
             { k: 'episode', label: '회차 번호', type: 'text', def: '',
               help: "위에서 '쇼츠 대본만 다시 쓰기' 를 골랐을 때만 적습니다 (예: EP001). 보통은 비워 두십시오." }] },

  { file: 'produce.yml', name: '3. 영상 만들기',
    desc: '대본으로 본편·쇼츠 영상을 만듭니다 (약 40분). 유튜브에는 영상을 보신 뒤 따로 올립니다',
    inputs: [{ k: 'voice', label: '목소리', type: 'select',
               help: '보통은 맨 위 그대로. 이미 만들어 둔 목소리는 다시 사지 않고 그대로 씁니다.',
               opts: [{ v: '음성 생성', t: '목소리 넣기 (보통 이것)' },
                      { v: '무음으로 시험', t: '소리 없이 화면만 확인 (0원)' }] },
             { k: 'only', label: '어떤 영상을', type: 'select',
               help: '하나만 골라 그것만 다시 만들 수 있습니다. 목소리는 그대로 쓰므로 값이 안 듭니다.',
               opts: [{ v: '', t: '전부 (본편 + 쇼츠 3편)' },
                      { v: 'longform', t: '본편만 (가로 12분)' },
                      { v: 'short1', t: '쇼츠 1번만' },
                      { v: 'short2', t: '쇼츠 2번만' },
                      { v: 'short3', t: '쇼츠 3번만' }] },
             { k: 'limit', label: '앞부분만 시험', type: 'text', def: '0',
               help: '0이면 전체를 만듭니다. 숫자를 넣으면 그 개수의 장면만 빠르게 만들어 화면을 확인합니다.' }] },

  // 2026-08-07 부터 '영상 보기' 에서 바로 공개로 올린다 → 이 버튼은 목록에서 감춘다.
  // 워크플로는 남겨 둔다: 예전에 비공개로 올려 둔 영상을 공개로 바꿀 때 쓴다.
  { file: 'publish.yml', name: '4. 공개하기 (예전 방식)', hidden: true,
    desc: '예전에 비공개로 올린 영상을 공개로',
    inputs: [{ k: 'episode', label: '회차', type: 'text', def: '' },
             { k: 'what', label: '무엇을', type: 'select',
               opts: ['롱폼', '쇼츠 1번 (궁금증형)', '쇼츠 2번 (분노형)', '쇼츠 3번 (사이다형)'] }] },

  { file: 'sfx.yml', name: '효과음 받아오기 (Pixabay)',
    desc: '법정 발소리 같은 효과음을 Pixabay 에서 받아 넣습니다 (0원)',
    inputs: [{ k: 'name', label: '어떤 효과음', type: 'select',
               help: '고른 소리를 새로 받아 넣습니다. 지금 쓰는 것은 덮어씁니다.',
               opts: [{ v: 'footsteps', t: '발소리' }, { v: 'door', t: '문 여닫는 소리' },
                      { v: 'gavel', t: '의사봉' }, { v: 'paper', t: '종이 넘기는 소리' }] },
             { k: 'query', label: '무엇을 찾을까요 (영어)', type: 'text',
               def: 'footsteps hall',
               help: '영어로 적어야 잘 찾습니다. 예: footsteps hall · courtroom gavel' },
             { k: 'install', label: '바로 넣을까요', type: 'select',
               help: "'듣기만' 을 고르면 후보만 받아 두고 지금 소리는 그대로 둡니다.",
               opts: [{ v: 'best', t: '기계가 고른 1순위를 바로 넣기' },
                      { v: '', t: '듣기만 하고 안 넣기' }] }] },

  { file: 'stats.yml', name: '5. 성과 보기',
    desc: '올린 영상이 얼마나 보였는지 — 조회수, 끝까지 본 비율 등을 확인합니다 (0원)',
    inputs: [] },

  { file: 'voicecheck.yml', name: '목소리 점검 (0원)',
    desc: '장면마다 목소리 높낮이를 재서, 어느 장면이 왜 튀는지 숫자로 보여줍니다 (약 3분)',
    inputs: [{ k: 'episode', label: '회차 번호', type: 'text', def: '',
               help: '비워 두면 가장 최근 회차를 봅니다 (예: EP001).' },
             { k: 'who', label: '누구 목소리를', type: 'select',
               opts: [{ v: '해설만', t: '해설(내레이션)만' },
                      { v: '전부 (해설 + 등장인물)', t: '전부 (해설 + 등장인물)' }] },
             { k: 'cut', label: '꼭 확인할 장면', type: 'text', def: 'H05,A1-15',
               help: '장면 번호입니다. 영상 자막 아래 표시와 같습니다. 쉼표로 여러 개.' }] },

  { file: 'voicefix.yml', name: '목소리 고치고 들어보기',
    desc: '목소리를 새로 만들어 고치기 전↔후를 나란히 들려줍니다',
    inputs: [{ k: 'scope', label: '얼마나 고칠까요', type: 'select',
               help: '먼저 싼 쪽으로 들어보시고, 괜찮으면 전부 고치시길 권합니다.',
               opts: [{ v: '문제 구간만 시험 (약 25원)', t: '문제된 부분만 (약 25원)' },
                      { v: '한 편 전부 (약 400원)', t: '한 편 전부 (약 400원)' }] },
             { k: 'episode', label: '회차 번호', type: 'text', def: '',
               help: '비워 두면 가장 최근 회차입니다.' },
             { k: 'cut', label: '들어볼 장면', type: 'text', def: 'H05',
               help: '장면 번호입니다. 쉼표로 여러 개 적을 수 있습니다.' }] },

  // hidden — 실행 목록에는 안 보이고 '영상 보기' 화면의 [다시 만들기] 버튼만 부른다.
  // 여기 적어 두는 이유는 /api/run 이 **이 명단에 있는 것만** 실행하기 때문이다.
  { file: 'thumbnail.yml', name: '썸네일 다시 만들기', desc: '', inputs: [], hidden: true },
  { file: 'youtube-upload.yml', name: '유튜브에 올리기', desc: '', inputs: [], hidden: true },
];

const THUMB_NAME = 'thumb.jpg';           // 릴리스 자산에 들어 있는 썸네일 파일명

// 릴리스 자산 파일명 → 사람이 읽는 이름.
// ⭐ 순서가 화면 순서다. '목소리 확인' 을 맨 앞에 둬서, 만들어져 있으면
//    '영상 보기' 를 눌렀을 때 **바로 이것이 재생**되게 한다(한 번만 누르면 되도록).
//    영상 만들기를 다시 돌리면 이 파일은 저절로 사라지고 본편이 다시 맨 앞이 된다.
const VIDEO_LABEL = {
  'voicecheck.mp4': '목소리 확인 · 고치기 전 ↔ 고친 후',
  'longform.mp4': '본편 (가로)',
  'short1.mp4': '쇼츠 1번 · 궁금증형',
  'short2.mp4': '쇼츠 2번 · 분노형',
  'short3.mp4': '쇼츠 3번 · 사이다형',
};

const STAGE_LABEL = {
  selected: '소재만 고름', scripting: '대본 쓰는 중', evaluated: '대본 다 됨',
  rendering: '영상 만드는 중', uploaded_private: '유튜브에 비공개로 올림',
  approved: '공개 준비됨', published: '유튜브 공개됨',
};

// ── GitHub 호출 (토큰은 여기서만 쓰인다) ───────────────────
async function gh(env, path, init = {}) {
  const r = await fetch(`${GH}${path}`, {
    ...init,
    headers: {
      'Authorization': `Bearer ${env.GH_TOKEN}`,
      'Accept': 'application/vnd.github+json',
      'User-Agent': 'verdict-theater-admin',
      'X-GitHub-Api-Version': '2022-11-28',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init.headers || {}),
    },
  });
  if (!r.ok) throw new Error(`GitHub ${r.status}: ${(await r.text()).slice(0, 300)}`);
  return r.status === 204 ? {} : r.json();
}

function b64utf8(b64) {
  const bin = atob(b64.replace(/\n/g, ''));
  const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
  return new TextDecoder('utf-8').decode(bytes);
}

async function getJson(env, path) {
  try {
    const f = await gh(env, `/repos/${REPO}/contents/${path}?ref=${BRANCH}`);
    return JSON.parse(b64utf8(f.content));
  } catch { return null; }
}

async function listDir(env, path) {
  try { return await gh(env, `/repos/${REPO}/contents/${path}?ref=${BRANCH}`); }
  catch { return []; }
}

// ── 로그인 (서명 쿠키) ───────────────────────────────────
async function sign(env, value) {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(env.SESSION_SECRET || 'vt'),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const mac = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(value));
  return [...new Uint8Array(mac)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

async function authed(req, env) {
  const cookie = req.headers.get('Cookie') || '';
  const m = cookie.match(/vt=([^;]+)/);
  if (!m) return false;
  const [val, mac] = decodeURIComponent(m[1]).split('.');
  if (!val || !mac) return false;
  return (await sign(env, val)) === mac;
}

// ⚠️ 화면은 **절대 캐시하지 않는다.**
//    페이지를 고쳐 배포해도 아이폰이 예전 화면을 계속 보여 주는 일이 실제로 있었다
//    ('영상 보기' 기능을 올렸는데 폰에는 안 나옴). 사파리는 캐시 지시가 없는 HTML 을
//    스스로 판단해 쥐고 있고, 홈 화면에 추가한 경우 특히 오래 붙잡는다.
//    이 페이지는 32KB 뿐이고 내용은 전부 /api/* 로 따로 받아 오므로 캐시할 이유가 없다.
const HTML = { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store, must-revalidate' };

// ── 화면 ────────────────────────────────────────────────
const CSS = `
:root{--bg:#12131a;--card:#1c1e29;--line:#2c2f3d;--ink:#e9e9ef;--dim:#9599ab;
--gold:#c6a04a;--red:#d2564a;--green:#4f9d69;--blue:#5b7fd4}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.6 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;
padding:0 0 90px;overscroll-behavior-y:contain}
header{position:sticky;top:0;z-index:10;background:rgba(18,19,26,.94);
backdrop-filter:blur(12px);border-bottom:1px solid var(--line);padding:14px 18px}
h1{margin:0;font-size:19px;letter-spacing:-.3px}
h1 span{color:var(--gold)}
.wrap{padding:16px 14px;max-width:760px;margin:0 auto}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;
padding:16px;margin-bottom:12px}
.card h2{margin:0 0 12px;font-size:15px;color:var(--dim);font-weight:600;letter-spacing:.3px}
.row{display:flex;justify-content:space-between;align-items:center;gap:10px;
padding:11px 0;border-bottom:1px solid var(--line)}
.row:last-child{border-bottom:0}
.k{color:var(--dim);font-size:14px}.v{font-weight:600;font-variant-numeric:tabular-nums}
.pill{font-size:12px;padding:4px 10px;border-radius:999px;background:#262a38;color:var(--dim)}
.pill.ok{background:#1e3a2a;color:#7ed4a0}.pill.wait{background:#3a3320;color:#e2c169}
.pill.go{background:#20304f;color:#8fb0f0}
button{font:inherit;font-weight:600;border:0;border-radius:12px;padding:14px 16px;
background:var(--blue);color:#fff;width:100%;min-height:50px}
button:active{opacity:.75}
button.ghost{background:#262a38;color:var(--ink)}
button.gold{background:var(--gold);color:#1a1608}
input,select{font:inherit;width:100%;padding:12px;border-radius:10px;
border:1px solid var(--line);background:#161822;color:var(--ink);min-height:48px;margin-top:6px}
label{display:block;margin:10px 0 0;font-size:13px;color:var(--dim)}
.wf{border:1px solid var(--line);border-radius:14px;padding:14px;margin-bottom:10px;background:#191b25}
.wf b{display:block;font-size:16px}.wf small{color:var(--dim);display:block;margin:3px 0 10px}
.ep{padding:13px 0;border-bottom:1px solid var(--line)}
.ep:last-child{border-bottom:0}
.ep b{font-size:15px}.ep small{color:var(--dim);display:block;font-size:13px}
/* 제목과 상태는 한 줄, 버튼은 그 아래 한 줄. 폭 393px 폰에서 제목이 두 줄로
   접히고 버튼이 흩어지던 것을 고친 배치다. */
.ep-top{display:flex;justify-content:space-between;align-items:flex-start;gap:10px}
/* 손가락으로 눌러야 하므로 버튼 높이를 36px 아래로 내리지 않는다 */
.btns{display:flex;flex-wrap:wrap;gap:7px;justify-content:flex-end;margin-top:9px}
.mini{width:auto;min-height:36px;padding:8px 12px;font-size:13px;border-radius:10px;
background:#262a38;color:var(--ink);display:inline-block;text-decoration:none;line-height:1.2}
.mini.gold{background:var(--gold);color:#1a1608}
.q{padding:11px 0;border-bottom:1px solid var(--line);font-size:14px}
.q:last-child{border-bottom:0}
.q b{color:var(--gold);font-variant-numeric:tabular-nums;margin-right:8px}
.hi{background:#191b25;border-left:3px solid var(--red);padding:12px 14px;
border-radius:0 10px 10px 0;margin:10px 0}
.hi em{display:block;color:var(--dim);font-style:normal;font-size:12px;margin-bottom:5px}
.act{margin:22px 0 8px;padding-bottom:7px;border-bottom:1px solid var(--line);
color:var(--gold);font-size:15px;font-weight:700}
.line{margin:9px 0}.line .who{color:var(--blue);font-weight:700}
.line.nar{color:#c8cbd6}
.tag{font-size:11px;color:var(--dim);margin-left:6px}
.empty{color:var(--dim);text-align:center;padding:26px 0;font-size:14px}
.toast{position:fixed;left:14px;right:14px;bottom:20px;background:#232735;
border:1px solid var(--line);border-radius:12px;padding:14px;z-index:50;display:none}
table{width:100%;border-collapse:collapse;font-size:14px}
td{padding:8px 4px;border-bottom:1px solid var(--line)}
td:first-child{color:var(--dim)}
a{color:var(--blue)}
`;

const LOGIN_HTML = `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>판결극장 관리자</title><style>${CSS}</style></head><body>
<div class="wrap" style="padding-top:80px">
<div class="card"><h2>판결극장 관리자</h2>
<form method="POST" action="/api/login">
<label>비밀번호<input type="password" name="pw" autofocus autocomplete="current-password"></label>
<div style="height:14px"></div><button type="submit">들어가기</button></form></div></div>
</body></html>`;

function appHtml() {
  return `<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>판결극장</title><style>${CSS}</style></head><body>
<header><h1>판결<span>극장</span> 관리자</h1></header>
<div class="wrap" id="app"><div class="empty">불러오는 중…</div></div>
<div class="toast" id="toast"></div>
<script>
const WF = ${JSON.stringify(WORKFLOWS)};
const STAGE = ${JSON.stringify(STAGE_LABEL)};
let S = null;
let VIEW = 'home';   // 지금 보고 있는 화면. 대본을 보는 중에 첫 화면이 끼어들지 않게 한다
let WATCH = null;    // 실행 후 자동 새로고침 타이머

const $ = (h) => { const d = document.createElement('div'); d.innerHTML = h; return d; };
const esc = (s) => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function toast(msg, ms = 3600) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.style.display = 'block';
  clearTimeout(t._h); t._h = setTimeout(() => t.style.display = 'none', ms);
}
const mmss = (s) => Math.floor(s/60) + ':' + String(Math.floor(s%60)).padStart(2,'0');

// GitHub 이 영어로 주는 상태값. 손님 화면에 영어가 새어나가지 않게 한다.
const CONCL = { success:'성공', failure:'실패', cancelled:'취소됨', skipped:'건너뜀',
                timed_out:'시간 초과', action_required:'조치 필요', neutral:'-' };

function ago(iso) {
  if (!iso) return '';
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return '방금';
  if (m < 60) return m + '분 전';
  if (m < 1440) return Math.floor(m/60) + '시간 전';
  return Math.floor(m/1440) + '일 전';
}

async function load() {
  const r = await fetch('/api/state');
  if (r.status === 401) { location.href = '/'; return; }
  S = await r.json();
  home();
}

function home() {
  VIEW = 'home';
  const eps = Object.entries(S.episodes || {}).sort((a,b) => b[0].localeCompare(a[0]));
  const ready = (S.queue || []).filter(q => q.gate_pass);
  const ungated = (S.queue || []).filter(q => q.gate_score == null);

  let h = '';
  h += '<div class="card"><h2>지금 상태</h2>';
  h += row('모아 둔 재판 기록', (S.queue||[]).length + '건');
  h += row('대본 만들 수 있는 소재', ready.length + '건');
  h += row('아직 안 살펴본 기록', ungated.length + '건');
  h += row('지금까지 만든 편수', eps.length + '편');
  h += row('그림·소리 준비', (S.assets ? S.assets.have + ' / ' + S.assets.need + ' 개' : '-'));
  h += '</div>';

  h += '<div class="card"><h2>회차</h2>';
  if (!eps.length) h += '<div class="empty">아직 만든 영상이 없습니다.<br>아래 <b>2. 대본 만들기</b>를 눌러 시작하십시오.</div>';
  eps.forEach(([id, v]) => {
    const st = STAGE[v.stage] || v.stage || '-';
    const cls = v.stage === 'published' ? 'ok' : (v.stage === 'uploaded_private' ? 'wait' : 'go');
    const nvid = (S.videos || {})[id] || 0;
    let btns = mini('대본 읽기', 'script(\\'' + id + '\\')');
    if (nvid) btns = mini('영상 보기', 'videos(\\'' + id + '\\')', 'gold') + btns;
    if (v.longform_id) btns += '<a class="mini" target="_blank" rel="noopener" '
      + 'href="https://youtu.be/' + esc(v.longform_id) + '">유튜브</a>';
    h += '<div class="ep"><div class="ep-top"><div><b>' + id + '</b>'
      + '<small>' + esc(v.case_type||'') + ' · 소재 점수 ' + (v.gate_score??'-') + '점 · 대본 점수 ' + (v.script_score??'-') + '점</small></div>'
      + '<span class="pill ' + cls + '">' + st + '</span></div>'
      + '<div class="btns">' + btns + '</div></div>';
  });
  h += '</div>';

  h += '<div class="card"><h2>소재 대기열 <small style="font-weight:400;color:#9599ab">'
     + '— 점수가 높을수록 이야기가 잘 나오는 재판 기록입니다</small></h2>';
  if (!(S.queue||[]).length) h += '<div class="empty">모아 둔 기록이 없습니다. <b>1. 재판 기록 모으기</b>를 먼저 누르십시오.</div>';
  (S.queue||[]).slice(0, 12).forEach(q => {
    const mark = q.gate_pass ? '' : (q.gate_score == null ? ' <span class="pill">아직 안 살펴봄</span>' : ' <span class="pill">쓰지 않기로 함</span>');
    const nm = q.case_type || q['사건명'] || ('판례 ' + q.case_id);
    // 심사에서 이미 떨어진 소재(폐기)는 버튼을 안 단다. 나머지는 눌러도 안전하다 —
    // '둘다' 모드라 심사부터 하고, 떨어지면 대본을 만들지 않고 멈추기 때문이다.
    // ⚠️ 소재 이름을 onclick 문자열에 직접 끼우지 않는다(따옴표가 들어 있으면
    //    페이지가 통째로 깨진다 — 8월 7일 무한로딩 사고와 같은 유형). data- 로 넘긴다.
    const canGo = q.gate_pass || q.gate_score == null;
    const btn = canGo && q.case_id
      ? '<div class="btns" style="margin-top:6px"><button class="mini" '
        + 'data-cid="' + esc(String(q.case_id)) + '" data-nm="' + esc(nm) + '" '
        + 'onclick="makeScript(this.dataset.cid, this.dataset.nm)">이 소재로 대본 만들기</button></div>'
      : '';
    h += '<div class="q"><b>' + (q.gate_score ?? q.machine_score ?? '-') + '점</b>'
      + esc(nm) + mark
      + '<div style="color:#9599ab;font-size:13px;margin-top:3px">' + esc(q.one_line || '') + '</div>'
      + btn + '</div>';
  });
  h += '</div>';

  h += '<div class="card"><h2>실행 <small style="font-weight:400;color:#9599ab">'
     + '— 위에서부터 차례대로 누르시면 됩니다</small></h2>';
  WF.forEach((w, i) => {
    // hidden 은 버튼 전용이라 목록에 안 띄운다. 자리(i)는 그대로 둔다 — run(i) 가 쓴다.
    if (w.hidden) return;
    h += '<div class="wf"><b>' + esc(w.name) + '</b><small>' + esc(w.desc) + '</small>';
    w.inputs.forEach(inp => {
      h += '<label>' + esc(inp.label);
      if (inp.type === 'select')
        // opts 는 '값' 또는 {v:보내는 값, t:보이는 글}. 보내는 값은 워크플로가 아는
        // 글자 그대로여야 하므로, 쉬운 말은 **보이는 글**에만 쓴다.
        h += '<select id="i_'+i+'_'+inp.k+'">' + inp.opts.map(o => {
          const v = (o && o.v !== undefined) ? o.v : o;
          const t = (o && o.t !== undefined) ? o.t : (o === '' ? '(전체)' : o);
          return '<option value="' + esc(v) + '">' + esc(t) + '</option>';
        }).join('') + '</select>';
      else
        h += '<input id="i_'+i+'_'+inp.k+'" value="' + esc(inp.def || '') + '">';
      h += '</label>';
      if (inp.help)
        h += '<div style="color:#9599ab;font-size:12.5px;margin:-6px 0 10px;line-height:1.5">'
           + esc(inp.help) + '</div>';
    });
    h += '<div style="height:12px"></div><button onclick="run(' + i + ')">실행</button></div>';
  });
  h += '</div>';

  if ((S.runs||[]).length) {
    h += '<div class="card"><h2>최근 실행</h2><table>';
    S.runs.slice(0, 8).forEach(r => {
      const ok = CONCL[r.conclusion] || (r.conclusion ? esc(r.conclusion) : '진행 중');
      const c = r.conclusion === 'success' ? 'ok' : (r.conclusion ? 'wait' : 'go');
      h += '<tr><td>' + esc(r.name) + '<small style="display:block;color:#9599ab">'
        + ago(r.at) + '</small></td><td style="text-align:right">'
        + '<span class="pill ' + c + '">' + ok + '</span></td></tr>';
    });
    h += '</table></div>';
  }

  document.getElementById('app').innerHTML = h;
}

const row = (k, v) => '<div class="row"><span class="k">' + k + '</span><span class="v">' + v + '</span></div>';
const mini = (t, fn, cls) => '<button class="mini ' + (cls||'') + '" onclick="' + fn + '">' + t + '</button>';
const mb = (b) => (b >= 1048576 ? Math.round(b/1048576) + 'MB' : Math.round(b/1024) + 'KB');

// ── 영상 보기 ───────────────────────────────────────────
// 영상은 저장소에 커밋하지 않는다. 제작 워크플로가 릴리스 자산으로 올려 두고,
// 이 페이지가 그것을 스트리밍한다. 최근 3편만 남는다.
let VIDS = [];
let THUMB = null;
let META = null;

async function videos(ep) {
  VIEW = 'video';
  document.getElementById('app').innerHTML = '<div class="empty">영상 목록 불러오는 중…</div>';
  let j = {};
  try { j = await (await fetch('/api/videos?ep=' + encodeURIComponent(ep))).json(); } catch (e) {}
  VIDS = j.items || [];
  THUMB = j.thumb || null;
  META = j.meta || null;
  if (!VIDS.length) {
    document.getElementById('app').innerHTML =
      '<button class="ghost" onclick="home()">← 목록</button><div style="height:12px"></div>'
      + thumbCard(ep)
      + '<div class="card"><div class="empty">이 회차의 <b>영상</b>이 없습니다.<br>'
      + '<b>3. 영상 만들기</b>를 실행하면 여기에서 바로 보실 수 있습니다.</div></div>';
    scrollTo(0, 0);
    return;
  }
  play(ep, 0);
}

// ── 썸네일 ─────────────────────────────────────────────
// 유튜브에서 조회수의 절반은 썸네일이 만든다. 그런데 폰에는 그림판이 없다.
// 그래서 ① 만들어진 것을 여기서 보여주고 ② 사진첩에 받고 ③ 마음에 안 들면
// 문구를 바꿔 다시 만든다 — 이 세 가지를 버튼으로만 되게 했다.
// ── 유튜브에 올리기 + 올라갈 내용 미리보기 ─────────────────
//
// 왜 여기인가 (손님 지시 2026-08-07)
//   "영상 제작까지만 하고, 영상을 보고 나서 그 영상 밑에 유튜브 업로드 버튼을 만들어 줘."
//   영상을 눈으로 확인한 **바로 그 자리**에서 올리는 것이 맞다.
//   그리고 무엇이 올라가는지(설명·목차·해시태그)를 **올리기 전에** 볼 수 있어야 한다.
//
// ⚠️ 바로 공개로 올라간다. 되돌리려면 유튜브 앱에서 지워야 한다 → 확인을 한 번 더 받는다.
function whatOf(name) {
  return (name || '').replace(/\.mp4$/, '');       // longform.mp4 → longform
}

function uploadCard(ep, v) {
  const what = whatOf(v.name);
  const m = META && META.videos && META.videos[what];
  let h = '<div class="card"><h2>유튜브에 올리기</h2>';

  if (!m) {
    h += '<div class="empty">올라갈 내용이 아직 없습니다.<br>'
      + '<b>3. 영상 만들기</b>를 다시 실행하면 만들어집니다.</div>';
  } else {
    h += '<div style="font-size:13px;line-height:1.75">';
    h += '<div style="color:#9599ab">제목</div>'
      + '<div style="margin:2px 0 12px;font-weight:600">' + esc(m.title) + '</div>';
    h += '<div style="color:#9599ab">설명 · 목차 · 해시태그</div>'
      + '<pre style="white-space:pre-wrap;word-break:break-word;margin:4px 0 12px;'
      + 'padding:12px;background:#141621;border-radius:10px;font:13px/1.7 inherit;'
      + 'max-height:340px;overflow:auto">' + esc(m.description) + '</pre>';
    if (m.pinned) {
      h += '<div style="color:#9599ab">고정 댓글</div>'
        + '<div style="margin:2px 0 4px">' + esc(m.pinned) + '</div>';
    }
    h += '</div>';
  }

  h += '<div style="height:10px"></div>'
    + '<button onclick="doUpload(\\'' + ep + '\\',\\'' + what + '\\')">'
    + '유튜브에 올리기 · 즉시 공개</button>'
    + '<div style="color:#9599ab;font-size:13px;margin-top:9px">'
    + '누르면 <b>바로 공개</b>로 올라갑니다. 되돌리려면 유튜브 앱에서 직접 지우셔야 합니다.<br>'
    + '올리기 전에 확인을 한 번 더 여쭙습니다.</div>';

  h += '<div style="height:12px"></div>'
    + '<button class="ghost" onclick="remakeOne(\\'' + ep + '\\',\\'' + what + '\\')">'
    + '이 영상만 다시 만들기</button>'
    + '<div style="color:#9599ab;font-size:13px;margin-top:9px">'
    + '이것 하나만 새로 만듭니다. 나머지 영상은 그대로 둡니다.<br>'
    + '음성은 이미 만들어 둔 것을 그대로 쓰므로 <b>값이 들지 않습니다.</b></div>';
  h += '</div>';
  return h;
}

async function doUpload(ep, what) {
  const label = (VIDEO_LABEL_JS[what + '.mp4'] || what);
  if (!confirm('「' + label + '」 을(를) 유튜브에 **즉시 공개**로 올립니다.\\n\\n'
             + '되돌리려면 유튜브 앱에서 직접 지우셔야 합니다.\\n올릴까요?')) return;
  toast('유튜브에 올리는 중… (몇 분 걸립니다)');
  let j = {};
  try {
    const r = await fetch('/api/run', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file: 'youtube-upload.yml',
                             inputs: { episode: ep, what: what } }) });
    j = await r.json();
  } catch (e) { j = { ok: false, error: '연결이 끊겼습니다' }; }
  if (!j.ok) { toast('실패: ' + (j.error || '알 수 없는 이유'), 6000); return; }
  toast('올리기 시작했습니다. 다 되면 텔레그램으로 알려드립니다.', 9000);
}

async function makeScript(cid, nm) {
  if (!confirm('「' + nm + '」 소재로 대본을 만듭니다.\\n\\n'
             + '먼저 소재 심사를 하고, 떨어지면 대본을 만들지 않고 멈춥니다.\\n'
             + '완성되면 텔레그램으로 알려드립니다. 진행할까요?')) return;
  toast('대본 만들기를 시작하는 중…');
  let j = {};
  try {
    const r = await fetch('/api/run', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file: 'script.yml',
                             inputs: { mode: '둘다', 'case': String(cid) } }) });
    j = await r.json();
  } catch (e) { j = { ok: false, error: '연결이 끊겼습니다' }; }
  if (!j.ok) { toast('실패: ' + (j.error || '알 수 없는 이유'), 6000); return; }
  toast('시작했습니다 (10분 안팎). 완성 알림이 오면 대본을 읽어보시고, 괜찮으면 [3. 영상 만들기] 를 누르십시오.', 9000);
}

async function remakeOne(ep, what) {
  if (!confirm('「' + (VIDEO_LABEL_JS[what + '.mp4'] || what) + '」 만 다시 만듭니다.\\n'
             + '음성은 그대로 쓰므로 값이 들지 않습니다. 진행할까요?')) return;
  toast('다시 만드는 중…');
  let j = {};
  try {
    const r = await fetch('/api/run', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file: 'produce.yml',
                             inputs: { episode: ep, only: what,
                                       voice: '음성 생성', upload: '올리지 않음',
                                       limit: '0' } }) });
    j = await r.json();
  } catch (e) { j = { ok: false, error: '연결이 끊겼습니다' }; }
  if (!j.ok) { toast('실패: ' + (j.error || '알 수 없는 이유'), 6000); return; }
  toast('시작했습니다. 다 되면 [새로 불러오기] 를 눌러 확인하십시오.', 9000);
}

const VIDEO_LABEL_JS = {
  'longform.mp4': '본편 (가로)',
  'short1.mp4': '쇼츠 1번 · 궁금증형',
  'short2.mp4': '쇼츠 2번 · 분노형',
  'short3.mp4': '쇼츠 3번 · 사이다형',
  'voicecheck.mp4': '목소리 확인',
};

function thumbCard(ep) {
  let h = '<div class="card"><h2>썸네일</h2>';
  if (!THUMB) {
    h += '<div class="empty">아직 썸네일이 없습니다.<br>'
      + '아래 <b>다시 만들기</b>를 누르면 대본에서 만들어 드립니다.</div>';
  } else {
    h += '<img src="/api/thumb?id=' + THUMB.id + '" alt="썸네일" '
      + 'style="width:100%;border-radius:12px;background:#000;display:block">';
    h += '<div style="color:#9599ab;font-size:13px;margin:9px 0 0">'
      + '1280×720 · ' + mb(THUMB.size) + ' · 유튜브에 자동으로 등록됩니다</div>';
    h += '<div class="btns"><a class="mini gold" download="' + esc(ep) + '_thumb.jpg" '
      + 'href="/api/thumb?id=' + THUMB.id + '&amp;dl=' + encodeURIComponent(ep) + '">썸네일 다운받기</a></div>';
  }
  // ⭐ 고를 것은 메뉴로 보여준다. '다시 만들기'가 매번 같은 그림을 뱉으면
  //    버튼이 아무 소용이 없으므로, 어떤 문구로 만들지 여기서 고르게 한다.
  h += '<label>문구 고르기 (바꿔 누르면 다른 그림이 나옵니다)'
    + '<select id="tv"><option>문구 1</option><option>문구 2</option><option>문구 3</option></select></label>';
  h += '<div style="height:10px"></div>'
    + '<button class="ghost" onclick="remakeThumb(\\'' + ep + '\\')">다시 만들기</button>';
  h += '<div style="color:#9599ab;font-size:13px;margin-top:9px">'
    + '만드는 데 <b>1분쯤</b> 걸립니다. 값은 들지 않습니다(코드가 그립니다).<br>'
    + '다 되면 아래 <b>새로 불러오기</b>를 눌러 확인하십시오.</div>';
  h += '<div style="height:8px"></div>'
    + '<button class="ghost" onclick="videos(\\'' + ep + '\\')">새로 불러오기</button>';
  h += '</div>';
  return h;
}

async function remakeThumb(ep) {
  const v = (document.getElementById('tv') || {}).value || '문구 1';
  toast('썸네일 다시 만드는 중… (' + v + ')');
  let j = {};
  try {
    const r = await fetch('/api/run', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file: 'thumbnail.yml', inputs: { episode: ep, variant: v } }) });
    j = await r.json();
  } catch (e) { j = { ok: false, error: '연결이 끊겼습니다' }; }
  if (!j.ok) { toast('실패: ' + (j.error || '알 수 없는 이유'), 6000); return; }
  toast('시작했습니다. 1분쯤 뒤 [새로 불러오기]를 누르십시오.', 8000);
}

function play(ep, i) {
  VIEW = 'video';
  const v = VIDS[i];
  const vertical = v.name.indexOf('short') === 0;
  let h = '<button class="ghost" onclick="home()">← 목록</button><div style="height:12px"></div>';
  h += '<div class="card"><h2>' + esc(ep) + ' 영상</h2>';
  // playsinline 이 없으면 아이폰이 전체화면으로 낚아채 간다.
  // preload=metadata 여야 첫 화면과 길이만 먼저 받고 나머지는 볼 때 받는다.
  h += '<video id="pl" controls playsinline preload="metadata" '
    + 'style="width:100%;max-height:' + (vertical ? '70vh' : '46vh')
    + ';border-radius:12px;background:#000;display:block" '
    + 'src="/api/video?id=' + v.id + '"></video>';
  h += '<div style="color:#9599ab;font-size:13px;margin:10px 0 4px">'
    + esc(v.label) + ' · ' + mb(v.size) + '</div>';
  h += '</div>';

  h += uploadCard(ep, v);
  h += thumbCard(ep);

  if (VIDS.length > 1) {
    h += '<div class="card"><h2>이 회차의 영상</h2>';
    VIDS.forEach((x, k) => {
      h += '<div class="row"><span class="k">' + esc(x.label) + ' · ' + mb(x.size) + '</span>'
        + (k === i ? '<span class="pill go">보는 중</span>'
                   : mini('재생', 'play(\\'' + ep + '\\',' + k + ')')) + '</div>';
    });
    h += '</div>';
  }

  h += '<div class="card"><h2>안내</h2>'
    + '<div style="color:#9599ab;font-size:13px;line-height:1.7">'
    + '영상은 저장소에 커밋하지 않습니다. 최근 <b>3편</b>만 보관하고 오래된 것은 자동으로 지워집니다.<br>'
    + '데이터가 걱정되면 Wi-Fi 에서 보십시오 — 본편 한 편이 100MB 안팎입니다.'
    + '</div></div>';

  document.getElementById('app').innerHTML = h;
  scrollTo(0, 0);
}

async function run(i) {
  const w = WF[i];
  const inputs = {};
  w.inputs.forEach(inp => { inputs[inp.k] = document.getElementById('i_'+i+'_'+inp.k).value; });
  toast(w.name + ' 실행 요청 중…');
  const r = await fetch('/api/run', { method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ file: w.file, inputs }) });
  const j = await r.json();
  if (!j.ok) { toast('실패: ' + (j.error || '알 수 없는 이유'), 6000); return; }
  toast(w.name + ' 시작됨. 아래 "최근 실행"이 저절로 갱신됩니다.', 6000);
  watch();
}

// 실행 직후에는 목록에 아직 안 뜬다. 손님이 직접 새로고침하지 않아도 되게
// 잠깐 동안 알아서 다시 확인한다. 첫 화면을 보고 있을 때만 다시 그린다.
function watch() {
  clearInterval(WATCH);
  let left = 20;                       // 6초 간격으로 약 2분
  WATCH = setInterval(async () => {
    if (--left < 0 || VIEW !== 'home') { clearInterval(WATCH); return; }
    try {
      const r = await fetch('/api/state');
      if (!r.ok) return;
      S = await r.json();
      if (VIEW === 'home') home();
    } catch (e) { /* 잠깐 끊긴 것뿐이다. 다음 차례에 다시 해본다 */ }
  }, 6000);
}

async function script(ep) {
  document.getElementById('app').innerHTML = '<div class="empty">대본 불러오는 중…</div>';
  const r = await fetch('/api/script?ep=' + encodeURIComponent(ep));
  const j = await r.json();
  if (!j.doc) { document.getElementById('app').innerHTML =
    '<div class="card"><div class="empty">대본을 찾을 수 없습니다.</div>'
    + '<button class="ghost" onclick="home()">돌아가기</button></div>'; return; }
  render(ep, j.doc, j.shorts);
}

function render(ep, d, sh) {
  VIEW = 'script';
  const m = d.meta || {}, a = d.anonymization || {};
  const cuts = (d.acts||[]).flatMap(x => x.cuts||[]);
  const total = cuts.reduce((s,c) => s + (c.sec||0), 0);
  const tag = (t) => cuts.find(c => c.tag === t);
  const who = (sp) => sp === 'narrator' ? '나레이션'
    : ((d.characters||[]).find(c => 'v_' + c.code === sp) || {}).name || sp;

  let h = '<button class="ghost" onclick="home()">← 목록</button><div style="height:12px"></div>';
  h += '<div class="card"><h2>' + ep + '</h2>';
  h += '<div style="font-size:18px;font-weight:700;margin-bottom:6px">' + esc((m.title_candidates||[''])[0]) + '</div>';
  h += '<div style="color:#9599ab;font-size:14px;margin-bottom:12px">' + esc(m.logline||'') + '</div>';
  h += row('영상 길이', mmss(total) + ' · 장면 ' + cuts.length + '개');
  h += row('무슨 사건인가', esc(m.case_type||'-'));
  (a.amounts_used||[]).forEach(x => { h += row(esc(x.label), esc(x.value)); });
  h += row('근거가 된 법 조항', esc(((d.law||{}).refs_from_case||[]).join(', ') || '없음'));
  h += '</div>';

  h += '<div class="card"><h2>등장인물</h2>';
  (d.characters||[]).forEach(c => {
    h += '<div class="row"><span class="k">' + esc(c.nametag||'') + '</span>'
      + '<span class="v" style="font-weight:400;color:#9599ab;font-size:13px">' + esc(c.note||'') + '</span></div>';
  });
  h += '</div>';

  h += '<div class="card"><h2>먼저 볼 세 곳 <small style="font-weight:400;color:#9599ab">'
     + '— 여기만 보셔도 대본이 괜찮은지 알 수 있습니다</small></h2>';
  const first = ((d.acts||[])[0]||{}).cuts||[];
  if (first[0]) h += hi('맨 처음 ' + first[0].sec + '초 — 여기서 사람이 남거나 떠납니다',
    who(first[0].speaker) + ': 「' + esc(first[0].text) + '」');
  const ang = tag('anger_line');
  if (ang) h += hi('가장 화나는 대사 — 쇼츠 2번이 될 한 줄', who(ang.speaker) + ': 「' + esc(ang.text) + '」');
  const ver = tag('verdict');
  if (ver) h += hi('판결 — 금액이 나오는 순간', esc(ver.text));
  h += '</div>';

  if (sh && (sh.shorts||[]).length) {
    h += '<div class="card"><h2>쇼츠 3편</h2><table>';
    sh.shorts.forEach(s => {
      h += '<tr><td>' + s.no + '번 ' + esc(s.kind||'') + '</td>'
        + '<td style="text-align:right">' + Math.round(s.est_sec||0) + '초</td></tr>'
        + '<tr><td colspan="2" style="color:#c8cbd6">' + esc(s.intro_line||'') + ' … ' + esc(s.outro_line||'') + '</td></tr>';
    });
    h += '</table></div>';
  }

  h += '<div class="card"><h2>대본 전문</h2>';
  (d.acts||[]).forEach(act => {
    h += '<div class="act">' + esc(act.title||act.id) + ' · ' + mmss(act.start_sec||0) + '</div>';
    (act.cuts||[]).forEach(c => {
      const marks = [];
      if (c.flashback) marks.push('회상');
      if (c.gfx) marks.push({timeline:'연표',family:'가족도',nametag:'이름표',amount:'금액'}[c.gfx.type] || c.gfx.type);
      const mk = marks.length ? '<span class="tag">' + marks.join(' · ') + '</span>' : '';
      h += c.speaker === 'narrator'
        ? '<div class="line nar">' + esc(c.text) + mk + '</div>'
        : '<div class="line"><span class="who">' + esc(who(c.speaker)) + '</span> 「' + esc(c.text) + '」' + mk + '</div>';
    });
  });
  h += '</div>';
  document.getElementById('app').innerHTML = h;
  scrollTo(0, 0);
}

const hi = (label, body) => '<div class="hi"><em>' + label + '</em>' + body + '</div>';

load();
</script></body></html>`;
}

// ── 라우팅 ──────────────────────────────────────────────
export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const ok = await authed(req, env);

    if (url.pathname === '/api/login' && req.method === 'POST') {
      // 정상 경로는 로그인 화면의 <form> 이다. 다른 형식이 들어오면
      // 서버 오류를 내지 말고 그냥 "틀렸다"로 돌려보낸다.
      let form = null;
      try { form = await req.formData(); } catch (e) { form = null; }
      if (!form || form.get('pw') !== env.ADMIN_PASSWORD) {
        return new Response(LOGIN_HTML.replace('<form', '<div style="color:#d2564a;font-size:14px">비밀번호가 다릅니다</div><form'),
          { status: 401, headers: HTML });
      }
      const val = String(Date.now());
      const cookie = `vt=${encodeURIComponent(val + '.' + await sign(env, val))}` +
        '; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=2592000';
      return new Response(null, { status: 302, headers: { Location: '/', 'Set-Cookie': cookie } });
    }

    if (!ok) {
      if (url.pathname.startsWith('/api/'))
        return Response.json({ error: 'unauthorized' }, { status: 401 });
      return new Response(LOGIN_HTML, { headers: HTML });
    }

    try {
      if (url.pathname === '/api/state') {
        const [episodes, queue, manifest, runsRes, files, rels] = await Promise.all([
          getJson(env, 'state/episodes.json'),
          getJson(env, 'state/queue.json'),
          getJson(env, 'assets/manifest.json'),
          gh(env, `/repos/${REPO}/actions/runs?per_page=10`).catch(() => ({ workflow_runs: [] })),
          listDir(env, 'assets/bg').catch(() => []),
          // 영상은 릴리스 자산으로 보관한다 (저장소 커밋이 아니다). 어느 회차에
          // 영상이 있는지 여기서 알아야 목록에 '영상 보기' 버튼을 띄울 수 있다.
          gh(env, `/repos/${REPO}/releases?per_page=30`).catch(() => []),
        ]);
        const videos = {};
        (Array.isArray(rels) ? rels : []).forEach((r) => {
          const m = /^video-(.+)$/.exec(r.tag_name || '');
          // 썸네일만 있고 영상은 아직 없는 회차도 '영상 보기'로 들어갈 수 있어야 한다
          // (썸네일을 먼저 만들어 보는 경우). 그래서 그림도 함께 센다.
          if (m) videos[m[1]] = (r.assets || [])
            .filter((a) => a.name.endsWith('.mp4') || a.name === THUMB_NAME).length;
        });
        let assets = null;
        if (manifest) {
          // 전부 세면 호출이 많아지므로, 대표적으로 배경만 세어 진행도를 짐작한다
          const bgHave = Array.isArray(files) ? files.filter((f) => f.name.endsWith('.jpg')).length : 0;
          assets = { have: bgHave, need: manifest.bg.codes.length, kind: '배경' };
        }
        return Response.json({
          episodes: episodes || {},
          queue: Array.isArray(queue) ? queue : [],
          assets,
          videos,
          runs: (runsRes.workflow_runs || []).map((r) => ({
            name: r.name, conclusion: r.conclusion, status: r.status, at: r.created_at,
          })),
        });
      }

      // 그 회차에 어떤 영상이 있는지
      if (url.pathname === '/api/videos') {
        const ep = url.searchParams.get('ep') || '';
        if (!/^EP\d{3}$|^SAMPLE_\w+$/.test(ep)) return Response.json({ error: 'bad ep' }, { status: 400 });
        let rel = null;
        try { rel = await gh(env, `/repos/${REPO}/releases/tags/video-${ep}`); } catch { rel = null; }
        const order = Object.keys(VIDEO_LABEL);           // 본편 → 쇼츠 1·2·3 순서
        const rank = (n) => (order.indexOf(n) < 0 ? 99 : order.indexOf(n));
        const assets = (rel && rel.assets) || [];
        const items = assets
          .filter((a) => a.name.endsWith('.mp4'))
          .map((a) => ({ id: a.id, name: a.name, size: a.size,
                         label: VIDEO_LABEL[a.name] || a.name }))
          .sort((x, y) => rank(x.name) - rank(y.name));
        // 썸네일은 영상이 아니라 그림이라 목록과 따로 돌려준다.
        // 화면에서 보여주고 내려받게 하려면 자산 번호가 필요하다.
        const t = assets.find((a) => a.name === THUMB_NAME);
        const thumb = t ? { id: t.id, size: t.size } : null;
        // ⭐ 유튜브에 올라갈 제목·설명·목차·해시태그. 영상 만들 때 같이 보관해 둔 것이다.
        //    **화면에 보여주는 것과 실제로 올라가는 것이 같아야** 하므로 같은 파일을 쓴다.
        let meta = null;
        const mj = assets.find((a) => a.name === 'meta.json');
        if (mj) {
          try {
            const r0 = await fetch(`${GH}/repos/${REPO}/releases/assets/${mj.id}`, {
              headers: { 'Authorization': `Bearer ${env.GH_TOKEN}`,
                         'Accept': 'application/octet-stream',
                         'User-Agent': 'verdict-theater-admin' } });
            if (r0.ok) meta = await r0.json();
          } catch { meta = null; }
        }
        return Response.json({ ep, items, thumb, meta,
                               at: rel ? rel.published_at : null });
      }

      // 썸네일 보여주기 / 내려받기.
      //   /api/video 는 Content-Type 을 video/mp4 로 못 박아 두어 그림에 쓸 수 없다.
      //   `dl` 이 붙으면 브라우저가 **파일로 저장**하게 한다 — 아이폰 사파리는
      //   이 머리말이 있어야 '파일 앱에 저장' 을 띄운다. 없으면 그냥 화면에 띄우고 만다.
      if (url.pathname === '/api/thumb') {
        const id = url.searchParams.get('id') || '';
        const dl = url.searchParams.get('dl') || '';
        if (!/^\d+$/.test(id)) return new Response('bad id', { status: 400 });
        const r0 = await fetch(`${GH}/repos/${REPO}/releases/assets/${id}`, {
          headers: {
            'Authorization': `Bearer ${env.GH_TOKEN}`,
            'Accept': 'application/octet-stream',
            'User-Agent': 'verdict-theater-admin',
            'X-GitHub-Api-Version': '2022-11-28',
          },
          redirect: 'manual',
        });
        const loc = r0.headers.get('Location');
        const up = loc ? await fetch(loc) : r0;
        if (!up.ok) return new Response('썸네일을 가져오지 못했습니다 (' + up.status + ')', { status: 502 });
        const h = new Headers();
        h.set('Content-Type', 'image/jpeg');
        h.set('Cache-Control', 'private, no-store');
        if (dl) {
          const safe = /^EP\d{3}$|^SAMPLE_\w+$/.test(dl) ? dl : 'thumb';
          h.set('Content-Disposition', `attachment; filename="${safe}_thumb.jpg"`);
        }
        const len = up.headers.get('Content-Length');
        if (len) h.set('Content-Length', len);
        return new Response(up.body, { status: 200, headers: h });
      }

      // 영상 스트리밍.
      //   ⚠️ 자산의 실제 주소는 **한 번 쓰고 버리는 서명 주소**다. 미리 받아 둘 수 없고,
      //      요청이 올 때마다 새로 받아야 한다.
      //   ⚠️ Range(부분 요청)를 그대로 넘겨야 한다. 아이폰 사파리는 부분 요청이
      //      되지 않는 영상은 **아예 재생하지 않는다.** 되감기도 이걸로 된다.
      //   토큰은 여기서만 쓰이고 브라우저로 내려가지 않는다.
      if (url.pathname === '/api/video') {
        const id = url.searchParams.get('id') || '';
        if (!/^\d+$/.test(id)) return new Response('bad id', { status: 400 });
        const r0 = await fetch(`${GH}/repos/${REPO}/releases/assets/${id}`, {
          headers: {
            'Authorization': `Bearer ${env.GH_TOKEN}`,
            'Accept': 'application/octet-stream',
            'User-Agent': 'verdict-theater-admin',
            'X-GitHub-Api-Version': '2022-11-28',
          },
          redirect: 'manual',
        });
        const loc = r0.headers.get('Location');
        const range = req.headers.get('Range');
        // 리다이렉트 없이 본문을 바로 주는 경우도 있어 양쪽을 다 받는다.
        const up = loc
          ? await fetch(loc, range ? { headers: { Range: range } } : {})
          : r0;
        if (!up.ok && up.status !== 206)
          return new Response('영상을 가져오지 못했습니다 (' + up.status + ')', { status: 502 });
        const h = new Headers();
        h.set('Content-Type', 'video/mp4');
        h.set('Accept-Ranges', 'bytes');
        h.set('Cache-Control', 'private, no-store');
        for (const k of ['Content-Length', 'Content-Range', 'ETag', 'Last-Modified']) {
          const v = up.headers.get(k);
          if (v) h.set(k, v);
        }
        return new Response(up.body, { status: up.status, headers: h });
      }

      if (url.pathname === '/api/script') {
        const ep = url.searchParams.get('ep') || '';
        if (!/^EP\d{3}$|^SAMPLE_\w+$/.test(ep)) return Response.json({ error: 'bad ep' }, { status: 400 });
        const [doc, shorts] = await Promise.all([
          getJson(env, `data/scripts/${ep}.json`),
          getJson(env, `data/scripts/${ep}.shorts.json`),
        ]);
        return Response.json({ doc, shorts });
      }

      if (url.pathname === '/api/run' && req.method === 'POST') {
        const { file, inputs } = await req.json();
        if (!WORKFLOWS.some((w) => w.file === file))
          return Response.json({ ok: false, error: '알 수 없는 워크플로' }, { status: 400 });
        const clean = {};
        for (const [k, v] of Object.entries(inputs || {})) if (v !== '') clean[k] = String(v);
        await gh(env, `/repos/${REPO}/actions/workflows/${file}/dispatches`, {
          method: 'POST', body: JSON.stringify({ ref: BRANCH, inputs: clean }),
        });
        return Response.json({ ok: true });
      }

      return new Response(appHtml(), { headers: HTML });
    } catch (e) {
      if (url.pathname.startsWith('/api/'))
        return Response.json({ ok: false, error: String(e).slice(0, 300) }, { status: 500 });
      return new Response('오류: ' + String(e).slice(0, 300), { status: 500 });
    }
  },
};
