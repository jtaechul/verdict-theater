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
  { file: 'build-assets.yml', name: '그림·소리 만들기 (처음 한 번)', rare: true,
    desc: '영상에 쓸 등장인물 그림, 배경 그림, 효과음을 만듭니다 (처음에 한 번만)',
    inputs: [{ k: 'what', label: '무엇을 만들까요', type: 'select',
               help: '효과음은 값이 들지 않습니다. 그림은 한 장씩 값이 듭니다.',
               opts: [{ v: '소리 (비용 0원)', t: '효과음 (0원)' },
                      { v: '캐릭터 한 명 시험', t: '등장인물 한 명만 시험 삼아' },
                      { v: '캐릭터 전부', t: '등장인물 전부' },
                      // ⚠️ 2026-08-12 — 여기가 '배경 전부' 였다. 워크플로에는 그런
                      //    이름의 선택지가 **없어서** 눌러도 깃허브가 거절했다.
                      //    (선택지 글자가 워크플로와 한 글자도 안 틀려야 한다)
                      { v: '배경 받아오기 (Pixabay + Pexels · 0원)',
                        t: '배경 사진 받아오기 (0원)' },
                      { v: '배경 창고 열쇠 확인만 (0원)',
                        t: '배경 사진 열쇠가 열리는지 확인만 (0원)' },
                      { v: '배경 전부 (AI 로 그림 · 값 나감)',
                        t: '배경을 AI 로 그리기 (값 나감)' },
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
               help: '보통은 맨 위 그대로 두십시오. 쓸 소재가 남아 있으면 심사를 건너뛰고 바로 대본을 씁니다.',
               opts: [{ v: '둘다', t: '대본 만들기 (소재 없을 때만 심사)' },
                      { v: '소재 심사만', t: '소재 고르기만 (대본은 안 씀)' },
                      { v: '대본 생성만', t: '심사는 절대 안 함 — 대본만' },
                      { v: '쇼츠만 다시', t: '쇼츠 대본만 다시 쓰기' }] },
             { k: 'writer', label: '대본을 쓸 AI', type: 'select',
               help: '그대로 두십시오. 앞의 AI가 막히면 저절로 다른 AI가 이어서 씁니다.',
               opts: [{ v: '자동 (Claude 우선)', t: '자동 (권장)' },
                      { v: 'Claude', t: 'Claude 로만' },
                      { v: 'Gemini', t: 'Gemini 로만' }] },
             { k: 'gate_limit', label: '살펴볼 기록 수', type: 'text', def: '10',
               help: '대기열 위에서부터 몇 건을 AI가 읽어보고 고를지입니다. 10이면 넉넉합니다.' },
             // ⭐ 한도를 여기서 고칠 수 있게 둔다. GitHub 설정에 들어갈 일이 없어야 한다.
             { k: 'budget', label: '한 번에 쓸 수 있는 돈 (원)', type: 'text', def: '3000',
               help: '지금 한 편에 약 2,100원 듭니다. 이 금액을 넘으면 그 자리에서 멈추고, 만들던 대본은 저장합니다. 그때는 [이어서 마저 만들기] 를 누르면 됩니다.' },
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

  // 2026-08-09 손님: "나중에도 이러면 어떡해. 목소리를 바꾸고 싶은 사람이 있으면
  //                   어떻게 해야 되는지도 방법을 같이 고민해서 제안해 줘."
  { file: 'voiceaudition.yml', name: '목소리 오디션 다시 만들기',
    desc: '목소리 30개를 같은 대사로 읽혀 한 파일로 들려드립니다. 한 번 약 280원, 그 뒤로는 0원',
    inputs: [{ k: 'dry', label: '실제로 만들까요', type: 'select',
               help: "'계획만' 을 고르면 값이 얼마나 들지만 알려드리고 끝납니다 (0원).",
               opts: [{ v: '아니오 (실제로 만듭니다)', t: '실제로 만들기 (약 280원)' },
                      { v: '예 (계획만 보기 · 0원)', t: '계획만 보기 (0원)' }] },
             { k: 'only', label: '몇 개만 들어볼까요', type: 'text', def: '',
               help: '비워 두면 30개 전부입니다. 몇 개만 다시 들으려면 이름을 쉼표로 '
                   + '적으십시오 (예: Orus,Umbriel,Iapetus).' }] },

  { file: 'sfx.yml', name: '소리·음악 받아오기', rare: true,
    desc: '효과음과 배경음악을 Freesound 에서 진짜 녹음으로 받아 넣습니다 (0원)',
    // ⚠️ v(보내는 글자)는 워크플로의 선택지와 **한 글자도 달라선 안 된다.**
    //    다르면 깃허브가 거절해서 눌러도 아무 일이 안 일어난다.
    //    (tools/admin_choice_check.py 가 올릴 때마다 맞춰 본다)
    inputs: [{ k: 'kind', label: '무엇을 받을까요', type: 'select',
               help: '배경음악은 8곡 중 빠진 것만 받아옵니다. 둘 다 0원입니다.',
               opts: [{ v: '효과음', t: '효과음' },
                      { v: '배경음악 (빠진 것만 · 0원)', t: '배경음악 — 빠진 것만 받기' },
                      { v: '배경음악 (후보만 들어보기)', t: '배경음악 — 후보만 들어보기' }] },
             { k: 'name', label: '어떤 효과음 (위에서 효과음을 골랐을 때만)', type: 'select',
               help: '고른 소리를 새로 받아 넣습니다. 지금 쓰는 것은 덮어씁니다.',
               opts: [{ v: 'clock phone heartbeat', t: '가짜 소리 3가지 한꺼번에 (권장)' },
                      { v: 'clock', t: '시계 초침' }, { v: 'phone', t: '전화벨' },
                      { v: 'heartbeat', t: '심장 뛰는 소리' },
                      { v: 'footsteps', t: '발소리' }, { v: 'door', t: '문 여닫는 소리' },
                      { v: 'gavel', t: '의사봉' }, { v: 'paper', t: '종이 넘기는 소리' },
                      { v: 'all', t: '전부 다시 받기' }] },
             { k: 'query', label: '무엇을 찾을까요 (영어)', type: 'text', def: '',
               help: '보통은 비워 두십시오 — 소리마다 알맞은 말이 이미 정해져 있습니다. '
                   + '여러 소리를 한꺼번에 받을 때는 반드시 비워 두셔야 합니다.' },
             { k: 'install', label: '바로 넣을까요', type: 'select',
               help: "'듣기만' 을 고르면 후보만 받아 두고 지금 소리는 그대로 둡니다.",
               opts: [{ v: 'best', t: '기계가 고른 1순위를 바로 넣기' },
                      { v: '', t: '듣기만 하고 안 넣기' }] }] },

  { file: 'stats.yml', name: '4. 성과 보기',
    desc: '올린 영상이 얼마나 보였는지 — 조회수, 끝까지 본 비율 등을 확인합니다 (0원)',
    inputs: [] },

  // hidden — 실행 목록에는 안 보이고 '영상 보기' 화면의 [다시 만들기] 버튼만 부른다.
  // 여기 적어 두는 이유는 /api/run 이 **이 명단에 있는 것만** 실행하기 때문이다.
  { file: 'castvoice.yml', name: '등장인물 목소리 바꾸기', desc: '', inputs: [], hidden: true },
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
    // ⚠️ **묵은 답을 쓰지 않는다.** 깃허브는 답에 '1분간 재사용해도 된다' 를 붙여 보낸다.
    //    그대로 두면 썸네일을 새로 만들고 [새로 불러오기] 를 눌러도 **옛 그림 번호**가
    //    돌아와 "안 바뀐다" 로 보인다 (2026-08-09 손님 지적).
    cf: { cacheTtl: 0, cacheEverything: false },
    headers: {
      'Cache-Control': 'no-cache',
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
/* 접었다 폈다 — 제목 줄 전체가 누르는 자리다(손가락으로 쉽게 맞도록 48px 확보) */
.card h2.ft{cursor:pointer;display:flex;align-items:center;justify-content:space-between;
gap:10px;margin:-4px 0 0;padding:10px 0;min-height:44px;user-select:none}
.card h2.ft.on{margin:-4px 0 8px}
/* 삼각형은 글꼴이 아니라 테두리로 그린다 — 기기마다 모양이 다를 일이 없다 */
.ca{width:0;height:0;flex:0 0 auto;border-left:5px solid transparent;
border-right:5px solid transparent;border-top:6px solid var(--dim);
transition:transform .15s;transform:rotate(-90deg)}
.ca.on{transform:none}
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
/* 제목 옆에 붙는 작은 버튼 (새로고침). 손가락으로 눌리게 높이는 남겨 둔다. */
button.mini{width:auto;min-height:34px;padding:7px 12px;font-size:13px;font-weight:600;
background:#262a38;color:#9599ab;border-radius:9px;margin-left:10px;vertical-align:middle}
/* 멈추기 — 실행과 확실히 달라 보여야 잘못 누르지 않는다. 폭도 좁게 둬 오조작을 막는다. */
button.stopbtn{background:#3a2730;color:#e79aa6;width:auto;flex:0 0 auto;padding:14px 18px}
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
let QTOPIC = '';     // 대기열에서 지금 고른 갈래 (''=전체)
let QMAX = 20;       // 대기열에 한 번에 보여줄 건수. [더 보기] 로 늘어난다

// 갈래를 고른다. 고를 때마다 보여줄 건수는 처음으로 되돌린다.
function pickTopic(t) { QTOPIC = (QTOPIC === t ? '' : t); QMAX = 20; home(); }
function moreQueue() { QMAX += 30; home(); }
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
  h += nextCard(eps, ready, ungated);
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

  h += collectCard();

  h += '<div class="card"><h2>소재 대기열 <small style="font-weight:400;color:#9599ab">'
     + '— 점수가 높을수록 이야기가 잘 나오는 재판 기록입니다</small></h2>';
  if (!(S.queue||[]).length) h += '<div class="empty">모아 둔 기록이 없습니다. <b>1. 재판 기록 모으기</b>를 먼저 누르십시오.</div>';

  // ⭐ 갈래로 골라 본다. (2026-08-10 손님: "소재 대기열에는 내가 원하지 않는 것만
  //    띄워놓고… 내가 더 볼 수 있게 해줘. 유류분 가지고 재미없어.")
  //    상속만 잔뜩 뜨는 것을 막고, 불륜 같은 갈래만 따로 볼 수 있게 한다.
  const all = S.queue || [];
  const cnt = {};
  all.forEach((q) => { const t = q.topic || '기타'; cnt[t] = (cnt[t] || 0) + 1; });
  const topics = Object.keys(cnt).sort((a, b) => cnt[b] - cnt[a]);
  if (topics.length > 1) {
    let tabs = '<button class="mini' + (QTOPIC ? '' : ' gold')
             + '" onclick="pickTopic(\\'\\')">전체 ' + all.length + '</button>';
    topics.forEach((t) => {
      tabs += '<button class="mini' + (QTOPIC === t ? ' gold' : '')
            + '" data-t="' + esc(t) + '" onclick="pickTopic(this.dataset.t)">'
            + esc(t) + ' ' + cnt[t] + '</button>';
    });
    h += '<div class="btns" style="margin-bottom:8px">' + tabs + '</div>';
  }
  const shown = QTOPIC ? all.filter((q) => (q.topic || '기타') === QTOPIC) : all;
  if (all.length && !shown.length) {
    h += '<div class="empty">이 갈래에는 아직 모아 둔 기록이 없습니다.</div>';
  }
  if (shown.length > QMAX) {
    h += '<div style="color:#9599ab;font-size:13px;margin-bottom:6px">'
       + shown.length + '건 가운데 점수 높은 ' + QMAX + '건을 보고 있습니다.</div>';
  }
  shown.slice(0, QMAX).forEach(q => {
    const mark = q.gate_pass ? '' : (q.gate_score == null ? ' <span class="pill">아직 안 살펴봄</span>' : ' <span class="pill">쓰지 않기로 함</span>');
    const nm = q.case_type || q['사건명'] || ('판례 ' + q.case_id);
    // 심사에서 이미 떨어진 소재(폐기)는 버튼을 안 단다. 나머지는 눌러도 안전하다 —
    // 아직 안 살펴본 소재를 누르면 script.py 가 돈 쓰기 전에 멈추고
    // "먼저 살펴보라" 고 알려준다 (2026-08-11 부터. 그 전에는 '둘다' 모드가
    // 늘 심사부터 돌아서 막혔는데, 그 심사가 이 판례를 본다는 보장이 없었다).
    // ⚠️ 소재 이름을 onclick 문자열에 직접 끼우지 않는다(따옴표가 들어 있으면
    //    페이지가 통째로 깨진다 — 8월 7일 무한로딩 사고와 같은 유형). data- 로 넘긴다.
    const canGo = q.gate_pass || q.gate_score == null;
    // ⭐ 아직 안 살펴본 것은 한 줄 요약이 없다 (3차 평가를 안 돌려서).
    //    그렇다고 무엇에 관한 사건인지 알 길이 없으면 고를 수가 없다.
    //    (2026-08-09 손님: "요약본을 볼 수 있는 방법이 없잖아. 어떻게든 조치해봐.")
    //    → 이미 받아 둔 판결문에서 법원이 쓴 요약을 꺼내 보여준다. **값 0원.**
    const look = (!q.one_line && q.case_id)
      ? '<button class="mini" data-cid="' + esc(String(q.case_id)) + '" '
        + 'onclick="showCase(this)">무슨 사건인지 보기</button> '
      : '';
    const btn = (look || (canGo && q.case_id))
      ? '<div class="btns" style="margin-top:6px">' + look
        + (canGo && q.case_id
           ? '<button class="mini" data-cid="' + esc(String(q.case_id)) + '" '
             + 'data-nm="' + esc(nm) + '" '
             + 'onclick="makeScript(this.dataset.cid, this.dataset.nm)">이 소재로 대본 만들기</button>'
           : '')
        + '</div>'
      : '';
    const tp = q.topic ? ' <span class="pill">' + esc(q.topic) + '</span>' : '';
    h += '<div class="q"><b>' + (q.gate_score ?? q.machine_score ?? '-') + '점</b>'
      + esc(nm) + tp + mark
      + '<div style="color:#9599ab;font-size:13px;margin-top:3px">' + esc(q.one_line || '') + '</div>'
      + '<div id="cs_' + esc(String(q.case_id || '')) + '"></div>'
      + btn + '</div>';
  });
  if (shown.length > QMAX) {
    h += '<div class="btns" style="margin-top:8px">'
       + '<button class="mini" onclick="moreQueue()">더 보기 (+30)</button></div>';
  }
  h += '</div>';

  // ⭐ 실행 차례대로 한 카드에 담는다 (2026-08-09 손님 두 차례 지적).
  //    ① "쓸데없는 메뉴가 많아"        → 가끔 쓰는 것은 접어 둔다
  //    ② "등장인물 목소리는 대본 아래쪽에 배치되는 게 정상이고, 감추기가 가능해야 해"
  //       → 목소리 일은 **대본을 쓴 뒤, 영상을 만들기 전**에 하는 것이 순서다.
  //         그 자리에 접힌 채로 넣는다.
  h += '<div class="card"><h2>실행 <small style="font-weight:400;color:#9599ab">'
     + '— 위에서부터 차례대로 누르시면 됩니다</small></h2>';
  h += wfList(['collect.yml', 'script.yml']);
  h += fold('목소리 고르기 (등장인물 목소리 · 오디션)', voiceBlock());
  h += wfList(['produce.yml', 'stats.yml']);
  h += fold('가끔 쓰는 것 (처음 준비 · 효과음)',
            wfList(['build-assets.yml', 'sfx.yml']));
  h += '</div>';

  if ((S.runs||[]).length) {
    // ⭐ 제목 옆 새로고침 (2026-08-12 손님 요청).
    //    data-t 로 접기 열쇠를 못 박는다 — 안 그러면 버튼 글자까지 제목으로 읽혀
    //    접었던 상태를 못 찾는다. 그리고 버튼을 눌러도 카드가 접히면 안 되므로
    //    event.stopPropagation() 으로 제목 클릭과 갈라 놓는다.
    h += '<div class="card"><h2 data-t="최근 실행">최근 실행'
       + '<button class="mini" onclick="event.stopPropagation();load()">새로고침</button>'
       + '</h2><table>';
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
  foldify();
  if (S.audition) fillAudition();
}

// 오디션 목록을 채운다 — 이름을 누르면 그 목소리 자리로 넘어간다.
// (30개를 이어 붙여 놓고 누가 누군지 안 알려 주면 고를 수가 없다)
async function fillAudition() {
  const box = document.getElementById('aulist');
  if (!box) return;
  let j = { items: [] };
  try {
    j = await (await fetch('/api/auditionindex?id=' + (S.audition.index || ''),
                           { cache: 'no-store' })).json();
  } catch (e) {}
  const items = j.items || [];
  if (!items.length) {
    box.innerHTML = '아직 목록이 없습니다. [작업] 화면의 <b>목소리 오디션</b>에서 '
      + "<b>'목록만 다시 만들기 (0원)'</b> 을 한 번 눌러 주십시오.";
    return;
  }
  const used = { Algenib: '장남', Fenrir: '차남', Algieba: '재판장',
                 Enceladus: '아버지', Sulafat: '어머니', Erinome: '며느리',
                 Vindemiatrix: '할머니', Charon: '해설' };
  let s = '<table style="width:100%">';
  items.forEach((it) => {
    const t = it.start == null ? '' : mmss(it.start);
    const band = it.hz < 155 ? '남자' : (it.hz < 165 ? '애매' : '여자');
    const mine = used[it.name] ? ' <b style="color:#e8c37a">← ' + used[it.name] + '</b>' : '';
    s += '<tr><td style="padding:5px 0">'
      + (it.start == null ? '' : '<button class="mini" data-t="' + it.start
         + '" onclick="seekAudition(this)">' + t + '</button> ')
      + '<b style="color:#e6e8f0">' + esc(it.name) + '</b>'
      + ' <small>' + Math.round(it.hz) + 'Hz · ' + band + '</small>' + mine
      + '</td></tr>';
  });
  box.innerHTML = s + '</table>';
}

// 목소리 관련을 한 묶음으로 그린다 — **대본 아래, 영상 만들기 위**에 접힌 채로 들어간다.
// (2026-08-09 손님: "등장인물 목소리는 대본 아래쪽에 배치되는 게 정상일 듯하고,
//                   감추기가 가능해야 해." — 목소리 일은 대본을 쓴 뒤에 하는 것이 순서다)
function voiceBlock() {
  let h = '';

  // ① 지금 누가 어떤 목소리를 쓰는지 + 바꾸기
  if ((S.voiceList||[]).length) {
    const ROLES = [['v_M50A','장남'],['v_M50B','차남'],['v_F50A','어머니'],
                   ['v_F50B','며느리'],['v_M70','아버지'],['v_F70','할머니'],
                   ['v_JUDGE','재판장'],['narrator','해설']];
    const now = S.cast || {};
    const hzOf = {}; S.voiceList.forEach(v => { hzOf[v.name] = v.hz; });
    h += '<div class="wf"><b>등장인물 목소리</b>'
      + '<small>지금 누가 어떤 목소리를 쓰는지 보고, 여기서 바꿉니다</small>';
    h += '<table style="width:100%;margin:8px 0 12px">';
    ROLES.forEach(([k, ko]) => {
      const v = now[k];
      const hz = v ? hzOf[v] : null;
      h += '<tr><td style="padding:4px 0;color:#e6e8f0">' + esc(ko) + '</td>'
        + '<td style="text-align:right;color:#9599ab;font-size:13px">'
        + (v ? esc(v) + (hz ? ' · ' + Math.round(hz) + 'Hz' : '')
             : '<span style="color:#6b6f80">기본값</span>') + '</td></tr>';
    });
    h += '</table>';
    h += '<label>누구를<select id="cv_who">'
      + ROLES.map(([k, ko]) => '<option value="' + k + '">' + esc(ko) + '</option>').join('')
      + '</select></label>';
    h += '<label>어떤 목소리로<select id="cv_voice">'
      + S.voiceList.map(v => {
          const band = v.hz < 155 ? '남자' : (v.hz < 165 ? '애매' : '여자');
          return '<option value="' + esc(v.name) + '">' + esc(v.name)
               + ' · ' + Math.round(v.hz) + 'Hz · ' + band + '</option>';
        }).join('') + '</select></label>';
    h += '<div style="color:#9599ab;font-size:12.5px;margin:-6px 0 10px;line-height:1.5">'
      + '아래 <b>오디션</b>에서 들어보시고 고르십시오. 남자 배역에 여자 음역을 '
      + '고르면 저장되지 않고 알려드립니다.</div>';
    h += '<button onclick="changeVoice()">이 목소리로 바꾸기</button>';
    h += '<div style="color:#9599ab;font-size:13px;margin-top:9px">'
      + '바꾸는 것만으로는 <b>값이 들지 않습니다.</b> 다음에 [영상 만들기] 를 누르실 때 '
      + '<b>그 사람 대사만</b> 새로 만들어집니다 (장남이면 60~100원).</div>';
    h += '</div>';
  }

  // ② 오디션 들어보기 (이름을 누르면 그 목소리 자리로 넘어간다)
  if (S.audition) {
    h += '<div class="wf"><b>오디션 들어보기 (30개)</b>'
      + '<small>낮은 목소리부터 이어 붙였습니다 · ' + mb(S.audition.size)
      + (S.audition.at ? ' · ' + esc(ago(S.audition.at)) + ' 만듦' : '') + '</small>'
      + '<div style="color:#9599ab;font-size:13px;margin:8px 0">'
      + '<b>이름을 누르면 그 목소리부터 들립니다.</b></div>'
      + '<audio id="auplay" controls preload="none" style="width:100%"'
      + ' src="/api/audio?id=' + S.audition.id + '"></audio>'
      + '<div id="aulist" style="margin-top:10px;color:#9599ab;font-size:13px">'
      + '목록 불러오는 중…</div></div>';
  }

  // ③ 오디션을 새로 만드는 메뉴 (값이 드는 것이라 맨 아래)
  h += wfList(['voiceaudition.yml']);
  return h;
}

// ── 지난 수집 결과 ──────────────────────────────────────
// 2026-08-10 손님: "수집 결과 보기는 관리자 페이지의 메뉴나 버튼으로 넣어야 될 거
// 아니야? 내가 여기 채팅창 들어와서 봐야겠냐?"
//  → '1. 재판 기록 모으기' 를 누른 결과를 이 화면에서 바로 읽으시게 한다.
//    깃허브 실행 기록을 찾아 들어갈 필요가 없다.
function collectCard() {
  const c = S.collect;
  if (!c) return '';
  const d = c.at ? new Date(c.at) : null;
  const p2 = (n) => String(n).padStart(2, '0');
  const when = d ? (d.getMonth() + 1) + '월 ' + d.getDate() + '일 '
                 + p2(d.getHours()) + ':' + p2(d.getMinutes()) : '';

  let h = '<div class="card"><h2>지난 수집 결과 '
        + '<small style="font-weight:400;color:#9599ab">— ' + esc(when) + '</small></h2>';

  // 맨 위에 **한 줄로 결론부터.** 0건이면 왜 0건인지도 같이 적는다.
  if (!c.new) {
    h += '<div class="empty">새로 받은 판례가 <b>0건</b>입니다.<br>'
       + (c.searched
          ? '찾을 낱말 ' + c.searched + '개로 ' + (c.found || 0) + '건을 찾았지만, '
            + '아래 <b>걸러낸 것</b>에 적힌 이유로 모두 빠졌거나 이미 갖고 있는 판례였습니다.'
          : '이번에는 새로 훑은 낱말이 없었습니다. 이미 다 훑어 본 낱말들입니다.')
       + '</div>';
  }
  h += row('새로 받은 판례', '<b>' + (c.new || 0) + '건</b>');
  h += row('찾을 낱말', (c.searched || 0) + '개');
  h += row('검색으로 걸린 것', (c.found || 0) + '건');
  h += row('1차 통과', (c.passed || 0) + '건');
  h += row('대기열 총계', (c.queue || 0) + '건');
  h += row('오늘 검색 횟수', (c.calls || 0) + ' / ' + (c.limit || 0) + '회');

  if ((c.top || []).length) {
    let t = '';
    c.top.forEach((x) => {
      t += '<div class="q"><b>' + (x.score ?? '-') + '점</b>' + esc(x.name || '')
         + '<div style="color:#9599ab;font-size:13px;margin-top:3px">'
         // '불륜로/상간자로' 처럼 조사가 틀리지 않게, 조사를 아예 안 쓴다
         + esc(x.court || '') + (x.q ? " · 찾은 낱말 '" + esc(x.q) + "'" : '') + '</div></div>';
    });
    h += fold('새로 받은 판례 보기 (' + c.top.length + '건)', t);
  }
  if ((c.queries || []).length) {
    let t = '';
    c.queries.forEach((x) => {
      t += row(esc(x.q), (x.total || 0) + '건 중 ' + (x.kept || 0) + '건 통과');
    });
    h += fold('낱말별로 몇 건 걸렸나 (' + c.queries.length + '개)', t);
  }
  if ((c.dropped || []).length) {
    let t = '<div style="color:#9599ab;font-size:13px;margin-bottom:6px">'
          + '아래는 이야기로 만들 수 없어 뺀 것입니다. 형사·행정·세금 사건이고, '
          + '가사(이혼 등)는 판결문이 공개되지 않아 못 씁니다.</div>';
    c.dropped.forEach((x) => { t += row(esc(x.why), (x.n || 0) + '건'); });
    h += fold('걸러낸 것 (' + c.dropped.length + '가지)', t);
  }
  return h + '</div>';
}

// 접었다 폈다 하는 묶음. 기본은 **접힌 채**로 둔다 (화면이 짧아야 찾기 쉽다).
function fold(title, inner) {
  return '<details style="margin-top:6px"><summary style="cursor:pointer;'
       + 'color:#9599ab;font-size:14px;padding:8px 0">' + esc(title) + '</summary>'
       + '<div style="padding-top:4px">' + inner + '</div></details>';
}

// 실행 메뉴에서 **정해진 것만 정해진 차례로** 그린다.
// ⚠️ 자리(i)는 WF 전체 기준이어야 한다 — run(i) 가 그 번호로 찾기 때문이다.
//    그래서 files 로 걸러도 i 는 WF 안에서의 번호를 그대로 쓴다.
function wfList(files) {
  let h = '';
  files.forEach((f) => {
    const i = WF.findIndex((x) => x.file === f);
    if (i < 0) return;
    const w = WF[i];
    if (w.hidden) return;                 // 버튼 전용이라 목록에 안 띄운다
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
    // ⭐ 멈추기 버튼 (2026-08-12 손님 요청). 예전에는 멈추려면 GitHub 에 들어가
    //    Cancel workflow 를 눌러야 했다 — 손님은 GitHub 에 안 들어간다.
    h += '<div style="height:12px"></div>'
       + '<div style="display:flex;gap:8px">'
       + '<button onclick="run(' + i + ')" style="flex:1">실행</button>'
       + '<button onclick="stopWf(' + i + ')" class="stopbtn">멈추기</button>'
       + '</div></div>';
  });
  return h;
}

// 배역 목소리를 바꾼다. 바꾸기만 하고 값은 들지 않는다 —
// 실제 음성은 다음 [영상 만들기] 때 그 사람 대사만 새로 만들어진다.
async function changeVoice() {
  const who = (document.getElementById('cv_who') || {}).value || '';
  const voice = (document.getElementById('cv_voice') || {}).value || '';
  if (!who || !voice) return;
  if (!confirm('목소리를 ' + voice + ' 로 바꿀까요?\\n\\n'
             + '지금은 값이 들지 않습니다.\\n'
             + '다음에 [영상 만들기] 를 누르실 때 그 사람 대사만 새로 만들어집니다.')) return;
  toast('바꾸는 중…');
  const since = Date.now();
  let j = {};
  try {
    const r = await fetch('/api/run', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file: 'castvoice.yml', inputs: { who: who, voice: voice } }) });
    j = await r.json();
  } catch (e) { j = { ok: false, error: '연결이 끊겼습니다' }; }
  if (!j.ok) { toast('실패: ' + (j.error || '알 수 없는 이유'), 8000); return; }
  watchRun('castvoice.yml', since, (r) => {
    if (r.conclusion === 'success') {
      toast('바꿨습니다. 다음 [영상 만들기] 부터 이 목소리로 만들어집니다.', 10000);
      load();
    } else if (r.conclusion === 'timeout') {
      toast('아직입니다. 잠시 뒤 새로고침해 주십시오.', 9000);
    } else {
      toast('바꾸지 못했습니다 — 배역에 안 맞는 높이일 수 있습니다. '
            + '[작업] 화면의 최근 실행에서 까닭을 보십시오.', 14000);
    }
  }, 8, 5);
}

// 아직 안 살펴본 판례가 **무슨 사건인지** 판결문에서 꺼내 보여준다. 값 0원.
// (3차 평가를 돌리기 전에는 한 줄 요약이 없다. 그래도 판결문에는 법원이 쓴
//  판시사항이나 주문이 들어 있어서, 무엇에 관한 다툼인지는 알 수 있다)
async function showCase(el) {
  const id = el.getAttribute('data-cid') || '';
  const box = document.getElementById('cs_' + id);
  if (!box) return;
  if (box.innerHTML) { box.innerHTML = ''; el.textContent = '무슨 사건인지 보기'; return; }
  box.innerHTML = '<div style="color:#9599ab;font-size:13px;margin-top:6px">읽는 중…</div>';
  let j = {};
  try { j = await (await fetch('/api/case?id=' + encodeURIComponent(id))).json(); }
  catch (e) { j = {}; }
  if (!j.found) {
    box.innerHTML = '<div style="color:#9599ab;font-size:13px;margin-top:6px">'
      + '판결문을 못 찾았습니다.</div>';
    return;
  }
  el.textContent = '접기';
  box.innerHTML = '<div style="margin-top:8px;padding:10px;border-radius:8px;'
    + 'background:#14161f;color:#c9ccd8;font-size:13px;line-height:1.65">'
    + '<div style="color:#9599ab;margin-bottom:5px">' + esc(j.kind)
    + (j.court ? ' · ' + esc(j.court) : '') + (j.at ? ' · ' + esc(j.at) : '') + '</div>'
    + esc(j.text) + '</div>';
}

function seekAudition(el) {
  const a = document.getElementById('auplay');
  if (!a) return;
  a.currentTime = parseFloat(el.getAttribute('data-t') || '0');
  a.play().catch(() => {});
}

// ── 접었다 폈다 ─────────────────────────────────────────
//
// 손님: "안 쓰는 메뉴는 감추기(축소) 기능 활성화 시켜. 스크롤하다가 손가락 뿌러지겠다"
//
// 카드마다 코드를 고치지 않는다. **다 그린 뒤에 한 번 훑어서** 제목 아래를
// 통째로 접을 수 있게 만든다. 카드를 새로 만들어도 저절로 접히게 된다.
// 접은 상태는 이 기기에 기억되므로, 한 번 접어두면 다음에 열어도 접혀 있다.
const FOLD_OPEN = ['다음에 할 일', '지금 상태', '회차'];   // 처음엔 펴 두는 것
const foldKey = (t) => 'fold:' + t.slice(0, 24);

function setFold(h, body, caret, open) {
  body.style.display = open ? '' : 'none';
  caret.classList.toggle('on', open);
  h.classList.toggle('on', open);
}

function foldify() {
  document.querySelectorAll('#app > .card').forEach(card => {
    const h = card.querySelector('h2');
    if (!h || h.dataset.ft || h.parentElement !== card) return;
    h.dataset.ft = '1';
    // 제목 안에 버튼이 있을 수 있다(새로고침). 그 글자가 제목에 섞이면
    // 접기 열쇠가 달라져 접었던 상태를 못 찾는다. data-t 가 있으면 그것을 쓴다.
    const title = (h.dataset.t || h.textContent || '').trim();

    // 제목 아래 내용을 통째로 한 봉지에 담는다
    const body = document.createElement('div');
    while (h.nextSibling) body.appendChild(h.nextSibling);
    card.appendChild(body);

    const caret = document.createElement('span');   // 삼각형 — 테두리로 그린다
    caret.className = 'ca';
    h.classList.add('ft');
    h.appendChild(caret);

    const saved = localStorage.getItem(foldKey(title));
    const open = saved === null
      ? FOLD_OPEN.some(x => title.indexOf(x) === 0)
      : saved === '1';
    setFold(h, body, caret, open);

    h.onclick = () => {
      const now = body.style.display === 'none';
      setFold(h, body, caret, now);
      try { localStorage.setItem(foldKey(title), now ? '1' : '0'); } catch (e) {}
    };
  });
}

// ── 다음에 할 일 (맨 위 · 한 번만 누르면 되는 자리) ────────
//
// 아래 '실행' 칸에는 고를 것이 네 개씩 붙어 있다. 그때마다 "무엇을 골라야 하지"
// 를 판단해야 하고, 실제로 판례 번호를 손으로 넣었다가 가사사건으로 Opus 를
// 19분 헛돌린 적이 있다(2026-08-10).
// 그래서 **지금 상태를 보고 다음에 할 일 하나만** 골라 큰 버튼으로 띄운다.
// 손님은 이 버튼만 누르면 된다. 아래 '실행' 칸은 손대고 싶을 때만 쓴다.
function nextStep(eps, ready, ungated) {
  // ⭐ '돌아가는 중' 은 **손님이 누른 작업**일 때만이다 (2026-08-12 손님 지적:
  //    "다음에 할 일에 '지금 돌아가는 중입니다' 라고 나와서 영상을 만들 수가 없잖아")
  //
  //    예전에는 안 끝난 실행이 **하나라도** 있으면 이 카드가 떴다. 그런데 거기엔
  //    [0. 자체 점검](코드 올릴 때마다 도는 0원짜리 검사)과 [6. 관리자 페이지 배포]가
  //    섞여 있다. 둘 다 손님이 하려는 일과 아무 상관이 없는데, 그것 때문에
  //    버튼이 통째로 사라져 아무것도 못 하게 됐다.
  //    → 화면에 버튼이 있는 작업(WF)만 따진다. 그 밖의 것은 무시한다.
  const mine = (S.runs || []).filter(r => !r.conclusion
                 && WF.some(w => w.name === r.name));
  if (mine.length)
    return { title: esc(mine[0].name) + ' 이(가) 돌아가는 중입니다',
             body: '끝나면 아래 <b>최근 실행</b>에 결과가 뜹니다. 그냥 두셔도 됩니다.<br>'
                 + '<span style="color:#9599ab">멈추려면 [작업] 화면에서 그 작업의 '
                 + '[멈추기] 를 누르십시오.</span>' };

  if (!(S.queue || []).length)
    return { title: '재판 기록부터 모아야 합니다',
             body: '아직 소재가 하나도 없습니다. 기록을 받아 오는 것부터 시작합니다.',
             btn: '재판 기록 모으기', act: 'goNext(\\'collect\\')' };

  // ⭐ 만들다 만 대본은 **처음부터 다시 만들지 않는다.**
  //    컷을 쓰는 1·2단계가 값의 8할이고 20분을 먹는다. 이미 있는 컷을 그대로 두고
  //    뒷단계만 마저 하면 값이 8할 줄고 5분이면 끝난다.
  //    ⚠️ stage 값으로 짐작하면 안 된다. 'scripting' 은 src/script.py 에서
  //       "대본은 다 됐는데 기계 검사 오류가 남았다" 는 뜻이지 "만들다 말았다" 가
  //       아니다. 2026-08-11 에 그걸 잘못 읽어, 99점으로 완성된 EP002 를
  //       '덜 만들어졌다' 로 띄우고 [이어서 마저 만들기] 를 권했다. 그 버튼은
  //       완성되면 지워지는 초벌 파일을 찾으므로 **반드시 실패**했고, 실패해도
  //       카드가 그대로라 또 누르게 되는 무한 반복이 됐다.
  //       그래서 워크플로가 보는 것과 **똑같은 것**을 본다 — 초벌 파일의 존재.
  const stuck = (S.drafts || [])[0];
  if (stuck)
    return { title: esc(stuck) + ' 대본이 덜 만들어졌습니다',
             body: '도중에 멈춘 대본입니다. <b>이미 써 둔 컷은 그대로 두고</b> '
                 + '남은 단계만 마저 합니다.<br>'
                 + '<span style="color:#9599ab">약 5분 · 처음부터 다시 만드는 것보다 '
                 + '값이 8할쯤 적게 듭니다.</span>',
             btn: '이어서 마저 만들기', act: 'goNext(\\'resume\\')' };

  // ⭐ 대본은 다 됐는데 영상이 아직 없는 회차가 있으면 **그것부터**다.
  //    예전에는 이 갈래가 아예 없어서, 방금 대본을 만들어 놓고도 화면이
  //    "대본을 만들 차례입니다" 라고 다음 편을 권했다. 만든 것을 두고
  //    또 만들라고 하면 값만 두 배로 나간다.
  const noVideo = eps.find(([k, v]) => v.stage !== 'published' && !(S.videos || {})[k]);
  if (noVideo) {
    const warn = (noVideo[1].validation_errors || 0);
    return { title: esc(noVideo[0]) + ' 대본이 다 됐습니다 — 영상을 만들 차례입니다',
             body: '채점 <b>' + (noVideo[1].script_score || '-') + '점</b>'
                 + (warn ? ' · 작은 경고 ' + warn + '건 (영상 만드는 데는 지장 없습니다)' : '')
                 + '<br><span style="color:#9599ab">약 40분 걸립니다. 누르고 나가셔도 됩니다.</span>',
             btn: '영상 만들기', act: 'goNext(\\'produce\\')' };
  }

  if (ready.length)
    return { title: '대본을 만들 차례입니다',
             body: '쓸 만하다고 판정된 소재가 <b>' + ready.length + '건</b> 있습니다. '
                 + '그중 가장 점수가 높은 것으로 한 편 만듭니다.<br>'
                 + '<span style="color:#9599ab">약 20분 걸립니다. 누르고 나가셔도 됩니다.</span>',
             btn: '대본 만들기', act: 'goNext(\\'script\\')' };

  if (ungated.length)
    return { title: '소재를 살펴볼 차례입니다',
             body: '아직 안 살펴본 기록이 <b>' + ungated.length + '건</b> 있습니다. '
                 + '10건을 점수 매겨 쓸 만한 것을 고릅니다.<br>'
                 + '<span style="color:#9599ab">약 4분 · 852원쯤 듭니다.</span>',
             btn: '소재 살펴보기', act: 'goNext(\\'gate\\')' };

  return { title: '재판 기록을 더 모아야 합니다',
           body: '가진 기록을 다 살펴봤는데 쓸 만한 소재가 없습니다.',
           btn: '재판 기록 모으기', act: 'goNext(\\'collect\\')' };
}

function nextCard(eps, ready, ungated) {
  const n = nextStep(eps, ready, ungated);
  let h = '<div class="card" style="border:1px solid #3c4257">'
        + '<h2 style="color:#e8b64c">다음에 할 일</h2>'
        + '<div style="font-size:17px;font-weight:700;margin:2px 0 6px">' + n.title + '</div>'
        + '<div style="color:#c8ccda;font-size:14px;line-height:1.7">' + n.body + '</div>';
  if (n.btn)
    h += '<div style="height:14px"></div>'
       + '<button style="width:100%" onclick="' + n.act + '">' + n.btn + '</button>';
  return h + '</div>';
}

// 버튼 하나가 알아서 맞는 설정으로 실행한다. 고를 것을 묻지 않는다.
// ⚠️ case(판례 번호)는 **일부러 안 보낸다.** 비워 두면 살펴보기를 통과한 소재 중
//    가장 좋은 것을 알아서 고른다. 손으로 넣으면 그 단계를 건너뛰어 위험하다.
const NEXT_RUN = {
  collect: { file: 'collect.yml', name: '재판 기록 모으기',
             inputs: { max_calls: '180', topic: '전부', queries: '', pages: '3' } },
  gate:    { file: 'script.yml', name: '소재 살펴보기',
             inputs: { mode: '소재 심사만', writer: '자동 (Claude 우선)', gate_limit: '10',
                       budget: '1000' } },
  script:  { file: 'script.yml', name: '대본 만들기',
             inputs: { mode: '둘다', writer: '자동 (Claude 우선)', gate_limit: '10',
                       budget: '3000' } },
  // 회차를 안 보낸다 — 워크플로가 만들다 만 것을 알아서 찾는다
  resume:  { file: 'script.yml', name: '이어서 마저 만들기',
             inputs: { mode: '이어서 마저 만들기', writer: '자동 (Claude 우선)',
                       budget: '3000' } },
  // 회차를 안 보낸다 — 워크플로가 대본이 있는 가장 최근 회차를 알아서 고른다
  produce: { file: 'produce.yml', name: '영상 만들기',
             inputs: { episode: '', limit: '0', voice: '음성 생성' } },
};

async function goNext(key) {
  const w = NEXT_RUN[key];
  toast(w.name + ' 시작하는 중…');
  let j = {};
  try {
    const r = await fetch('/api/run', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file: w.file, inputs: w.inputs }) });
    j = await r.json();
  } catch (e) { j = { ok: false, error: '연결이 끊겼습니다' }; }
  if (!j.ok) { toast('실패: ' + (j.error || '알 수 없는 이유'), 6000); return; }
  toast(w.name + ' 시작했습니다. 이 화면이 저절로 갱신됩니다.', 6000);
  watch();
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
  // ⚠️ 묵은 답을 쓰지 않는다 — [새로 불러오기] 인데 옛 것이 오면 뜻이 없다.
  try {
    j = await (await fetch('/api/videos?ep=' + encodeURIComponent(ep) + '&t=' + Date.now(),
                           { cache: 'no-store' })).json();
  } catch (e) {}
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
    + '올리기 전에 확인을 한 번 더 여쭙습니다.</div>'
    // 진짜로 올리지 않고 '되는지' 만 보는 길. 되돌릴 수 없는 일을 하기 전에 쓴다.
    + '<div style="height:10px"></div>'
    + '<button class="mini" onclick="doUpload(\\'' + ep + '\\',\\'' + what + '\\',1)">'
    + '먼저 연습해 보기 (올리지 않음)</button>'
    + '<div style="color:#9599ab;font-size:13px;margin-top:9px">'
    + '유튜브에 올리지 않고, <b>올리기 직전까지</b> 되는지만 확인합니다.<br>'
    + '유튜브 열쇠·영상·제목·설명이 준비됐는지 여기서 알 수 있습니다.</div>';

  h += '<div style="height:12px"></div>'
    + '<button class="ghost" onclick="remakeOne(\\'' + ep + '\\',\\'' + what + '\\')">'
    + '이 영상만 다시 만들기</button>'
    + '<div style="color:#9599ab;font-size:13px;margin-top:9px">'
    + '이것 하나만 새로 만듭니다. 나머지 영상은 그대로 둡니다.<br>'
    + '음성은 이미 만들어 둔 것을 그대로 쓰므로 <b>값이 들지 않습니다.</b></div>';
  h += '</div>';
  return h;
}

// 작업이 끝날 때까지 지켜보다가 **결과를 화면에 알려준다.**
// ⚠️ 예전에는 시작만 시켜 놓고 "텔레그램으로 알려드립니다" 하고 끝냈다.
//    텔레그램 열쇠가 등록돼 있지 않아 아무 소식도 오지 않았고, 실제로
//    2026-08-09 13:11 의 업로드는 18초 만에 죽었는데 손님은 그 사실을 몰랐다.
async function watchRun(file, since, onDone, everySec = 10, maxMin = 30) {
  const until = Date.now() + maxMin * 60000;
  let started = false;
  const tick = async () => {
    if (Date.now() > until) { onDone({ conclusion: 'timeout' }); return; }
    let j = null;
    try { j = await (await fetch('/api/lastrun?file=' + encodeURIComponent(file))).json(); }
    catch (e) { j = null; }
    if (j && j.found && new Date(j.at).getTime() >= since - 60000) {
      started = true;
      if (j.status === 'completed') { onDone(j); return; }
    }
    setTimeout(tick, everySec * 1000);
  };
  setTimeout(tick, 6000);
}

async function doUpload(ep, what, dry) {
  const label = (VIDEO_LABEL_JS[what + '.mp4'] || what);
  if (dry) {
    if (!confirm('「' + label + '」 을(를) 올리는 데 문제가 없는지 확인만 합니다.\\n\\n'
               + '유튜브에는 **올리지 않습니다.**\\n해볼까요?')) return;
  } else if (!confirm('「' + label + '」 을(를) 유튜브에 **즉시 공개**로 올립니다.\\n\\n'
                    + '되돌리려면 유튜브 앱에서 직접 지우셔야 합니다.\\n올릴까요?')) {
    return;
  }
  toast(dry ? '확인하는 중…' : '유튜브에 올리는 중… (몇 분 걸립니다)');
  const since = Date.now();
  const inputs = { episode: ep, what: what };
  if (dry) inputs.mode = '연습 (올리지 않고 확인만)';
  let j = {};
  try {
    const r = await fetch('/api/run', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file: 'youtube-upload.yml', inputs: inputs }) });
    j = await r.json();
  } catch (e) { j = { ok: false, error: '연결이 끊겼습니다' }; }
  if (!j.ok) { toast('실패: ' + (j.error || '알 수 없는 이유'), 8000); return; }
  toast(dry ? '확인하는 중입니다. 이 화면을 켜 두시면 결과를 알려드립니다.'
            : '올리는 중입니다. 이 화면을 켜 두시면 결과를 여기에 알려드립니다.', 12000);
  watchRun('youtube-upload.yml', since, (r) => {
    if (r.conclusion === 'success') {
      toast(dry ? '이상 없습니다. 지금 누르시면 그대로 올라갑니다.'
                : '「' + label + '」 유튜브에 공개로 올라갔습니다.', 12000);
      if (!dry) load();
    } else if (r.conclusion === 'timeout') {
      toast('아직 끝나지 않았습니다. 잠시 뒤 [작업] 화면에서 확인해 주십시오.', 12000);
    } else {
      toast((dry ? '확인에서 문제가 나왔습니다 (' : '올리지 못했습니다 (')
            + (CONCL[r.conclusion] || r.conclusion || '알 수 없음')
            + '). [작업] 화면의 최근 실행에서 까닭을 볼 수 있습니다.', 15000);
    }
  });
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
    // ⚠️ 주소 뒤에 시각을 붙인다 — 안 붙이면 폰이 **전에 받아 둔 그림**을 그대로
    //    다시 보여줘서, 새로 만들어도 "안 바뀐다" 로 보인다 (2026-08-09 손님 지적).
    h += '<img src="/api/thumb?id=' + THUMB.id + '&amp;t=' + Date.now() + '" alt="썸네일" '
      + 'style="width:100%;border-radius:12px;background:#000;display:block">';
    h += '<div style="color:#9599ab;font-size:13px;margin:9px 0 0">'
      + '1280×720 · ' + mb(THUMB.size)
      + (THUMB.at ? ' · <b>' + esc(ago(THUMB.at)) + '</b> 만듦' : '')
      + ' · 유튜브에 자동으로 등록됩니다</div>';
    // ⚠️ 그냥 링크로 두면 아이폰이 **저장 화면으로 넘어가 버리고 되돌아올 수가 없다**
    //    (관리자 페이지는 한 화면짜리라 화면이 바뀌면 통째로 사라진다 — 손님이 갇히셨다).
    //    그래서 화면을 옮기지 않고, 그림만 받아서 저장한다.
    h += '<div class="btns"><button class="mini gold" '
      + 'onclick="saveThumb(\\'' + ep + '\\')">썸네일 다운받기</button></div>';
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

// 썸네일을 **화면을 옮기지 않고** 받는다.
// ⚠️ 예전에는 그냥 링크(<a download href=...>)였다. 아이폰 사파리는 그 주소로
//    **화면을 통째로 옮겨** 저장 화면을 띄우는데, 관리자 페이지는 한 화면짜리라
//    그 순간 사라지고 되돌아올 길이 없다 — 손님이 그 화면에 갇히셨다(2026-08-09).
//    이제 그림만 몰래 받아서(blob) 저장하므로 화면은 그대로 남는다.
async function saveThumb(ep) {
  if (!THUMB) return;
  toast('썸네일 받는 중…');
  try {
    const r = await fetch('/api/thumb?id=' + THUMB.id + '&t=' + Date.now(),
                          { cache: 'no-store' });
    if (!r.ok) throw new Error('' + r.status);
    const url = URL.createObjectURL(await r.blob());
    const a = document.createElement('a');
    a.href = url; a.download = ep + '_thumb.jpg';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 20000);
    toast('받았습니다. 파일 앱이나 사진첩에서 확인하십시오.', 7000);
  } catch (e) {
    // 폰이 이 방법을 막으면, 새 창으로 연다 — 그래도 이 화면은 남는다.
    toast('새 창에서 엽니다. 다 보시면 그 창만 닫으십시오.', 7000);
    window.open('/api/thumb?id=' + THUMB.id + '&dl=' + encodeURIComponent(ep), '_blank');
  }
}

async function remakeThumb(ep) {
  const v = (document.getElementById('tv') || {}).value || '문구 1';
  toast('썸네일 다시 만드는 중… (' + v + ')');
  const since = Date.now();
  let j = {};
  try {
    const r = await fetch('/api/run', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file: 'thumbnail.yml', inputs: { episode: ep, variant: v } }) });
    j = await r.json();
  } catch (e) { j = { ok: false, error: '연결이 끊겼습니다' }; }
  if (!j.ok) { toast('실패: ' + (j.error || '알 수 없는 이유'), 6000); return; }
  // ⭐ 다 되면 **저절로 새로 불러온다.** 예전에는 "1분쯤 뒤에 눌러 보십시오" 라고만
  //    했는데, 너무 일찍 누르면 옛 그림이 나와 "안 바뀐다" 로 보였다 (손님 지적).
  toast('만드는 중입니다. 다 되면 저절로 새 그림이 뜹니다.', 12000);
  watchRun('thumbnail.yml', since, (r) => {
    if (r.conclusion === 'success') {
      toast('새 썸네일이 나왔습니다 (' + v + ').', 8000);
      videos(ep);
    } else if (r.conclusion === 'timeout') {
      toast('아직입니다. 잠시 뒤 [새로 불러오기]를 눌러 주십시오.', 9000);
    } else {
      toast('만들지 못했습니다 (' + (CONCL[r.conclusion] || r.conclusion || '알 수 없음')
            + '). [작업] 화면에서 까닭을 볼 수 있습니다.', 12000);
    }
  }, 8, 6);
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
  foldify();
  scrollTo(0, 0);
}

// 돌고 있는 것을 멈춘다. 만들던 대본은 초벌로 남으므로 [이어서 마저 만들기] 로 이을 수 있다.
async function stopWf(i) {
  const w = WF[i];
  // 브라우저 쪽 코드는 템플릿 문자열 안에 들어 있다. 줄바꿈 이스케이프나
  // 역따옴표를 여기 쓰면 바깥 템플릿이 먼저 먹어 안쪽 문자열이 깨진다(SyntaxError).
  // 여러 줄이 필요하면 문자열을 따로 잇는다.
  if (!confirm(w.name + ' 을(를) 지금 멈출까요? '
             + '만들던 대본은 저장됩니다 — 나중에 [이어서 마저 만들기] 로 이을 수 있습니다.')) return;
  toast(w.name + ' 멈추는 중…');
  let j;
  try {
    const r = await fetch('/api/stop', { method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ file: w.file }) });
    j = await r.json();
  } catch (e) { j = { ok: false, error: '연결이 끊겼습니다' }; }
  if (!j.ok) { toast(j.error || '멈추지 못했습니다', 7000); return; }
  toast('멈췄습니다. 만들던 것은 저장됐습니다 — [이어서 마저 만들기] 로 이을 수 있습니다.', 9000);
  watch();
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
  foldify();
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
        const [episodes, queue, manifest, runsRes, files, rels, scriptFiles] = await Promise.all([
          getJson(env, 'state/episodes.json'),
          getJson(env, 'state/queue.json'),
          getJson(env, 'assets/manifest.json'),
          gh(env, `/repos/${REPO}/actions/runs?per_page=10`).catch(() => ({ workflow_runs: [] })),
          listDir(env, 'assets/bg').catch(() => []),
          // 영상은 릴리스 자산으로 보관한다 (저장소 커밋이 아니다). 어느 회차에
          // 영상이 있는지 여기서 알아야 목록에 '영상 보기' 버튼을 띄울 수 있다.
          gh(env, `/repos/${REPO}/releases?per_page=30`).catch(() => []),
          // ⭐ 만들다 만 대본의 **유일한 증거**는 초벌 파일이 실제로 있는가다.
          //    stage 값으로 짐작하면 안 된다 — 2026-08-11 에 그것 때문에
          //    다 만들어진 EP002 를 '덜 만들어졌다' 로 읽고 [이어서 마저 만들기] 를
          //    띄웠고, 그 버튼은 지워진 초벌을 찾다가 반드시 실패했다(무한 반복).
          //    워크플로가 보는 것과 똑같은 것을 화면도 봐야 어긋나지 않는다.
          listDir(env, 'data/scripts').catch(() => []),
        ]);
        const drafts = (Array.isArray(scriptFiles) ? scriptFiles : [])
          .map((f) => /^(EP\d+)\.draft\.json$/.exec(f.name || ''))
          .filter(Boolean).map((m) => m[1]);
        const videos = {};
        let audition = null;
        (Array.isArray(rels) ? rels : []).forEach((r) => {
          const m = /^video-(.+)$/.exec(r.tag_name || '');
          // 썸네일만 있고 영상은 아직 없는 회차도 '영상 보기'로 들어갈 수 있어야 한다
          // (썸네일을 먼저 만들어 보는 경우). 그래서 그림도 함께 센다.
          if (m) videos[m[1]] = (r.assets || [])
            .filter((a) => a.name.endsWith('.mp4') || a.name === THUMB_NAME).length;
          // ⚠️ 목소리 오디션(30개)은 보관함 이름이 달라 위 규칙에 안 걸렸다.
          //    그래서 **만들어 놓고도 화면에 안 떴다** (2026-08-09 손님 지적).
          if ((r.tag_name || '') === 'voice-audition') {
            const mp3 = (r.assets || []).find((a) => a.name === 'voices_all.mp3');
            const idx = (r.assets || []).find((a) => a.name === 'audition_index.json');
            if (mp3) audition = { id: mp3.id, size: mp3.size,
                                  index: idx ? idx.id : null,
                                  at: mp3.updated_at || mp3.created_at };
          }
        });
        // ⭐ 지금 누가 어떤 목소리를 쓰는지 + 쓸 수 있는 목소리(높이 포함).
        //    (2026-08-09 손님: "목소리별 등장인물 이걸 바꿀 수가 없잖아")
        //    화면에서 바로 고르시게 하려면 이 둘이 필요하다.
        // ⭐ 지난 수집 결과. 깃허브 실행 기록을 뒤지지 않고 여기서 바로 보시게 한다.
        //    (2026-08-10 손님: "수집 결과 보기를 관리자 페이지 버튼으로 넣어야 할 거 아니야")
        const [castJson, voiceJson, collectJson] = await Promise.all([
          getJson(env, 'data/cast_voices.json'), getJson(env, 'data/voices.json'),
          getJson(env, 'state/collect_last.json'),
        ]);
        const cast = (castJson && castJson.cast) || {};
        const voiceList = Object.entries((voiceJson && voiceJson.voices) || {})
          .filter(([, v]) => v && v.hz)
          .map(([name, v]) => ({ name, hz: v.hz }))
          .sort((a, b) => a.hz - b.hz);

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
          drafts,          // 만들다 만 대본의 회차들 (초벌 파일이 실제로 있는 것만)
          audition,
          cast,
          voiceList,
          collect: collectJson || null,
          runs: (runsRes.workflow_runs || []).map((r) => ({
            name: r.name, conclusion: r.conclusion, status: r.status, at: r.created_at,
          })),
        });
      }

      // 작업 하나가 지금 어떻게 되었는지 (버튼이 결과를 화면에 보여주려고 쓴다)
      // ⚠️ 예전에는 "다 되면 텔레그램으로 알려드립니다" 하고 끝냈다. 그런데 텔레그램
      //    열쇠가 등록돼 있지 않아 **아무 소식도 오지 않았다** — 2026-08-09 13:11 의
      //    업로드 실패를 손님이 알 길이 없었다. 이제 화면이 직접 결과를 보여준다.
      if (url.pathname === '/api/lastrun') {
        const file = url.searchParams.get('file') || '';
        if (!WORKFLOWS.some((w) => w.file === file))
          return Response.json({ error: '알 수 없는 작업' }, { status: 400 });
        const r = await gh(env,
          `/repos/${REPO}/actions/workflows/${file}/runs?per_page=1`).catch(() => null);
        const run = r && (r.workflow_runs || [])[0];
        if (!run) return Response.json({ found: false });
        return Response.json({
          found: true, id: run.id, status: run.status,
          conclusion: run.conclusion, at: run.created_at, url: run.html_url,
        });
      }

      // 오디션에서 **누가 몇 초에 나오는지** 목록.
      // 이게 없으면 30개를 이어 붙인 파일을 들어도 지금 나오는 소리가 누구인지
      // 알 수가 없다 — 들려주기만 하고 고를 수는 없다 (2026-08-09 손님 지적).
      // 아직 안 살펴본 판례의 **요약**. 값 0원 — 이미 받아 둔 판결문에서 뽑는다.
      // (2026-08-09 손님: "아직 안 살펴봄으로 구분된 판례는 요약본을 볼 수 있는
      //                   방법이 없잖아. 어떻게든 조치해봐.")
      // 3차 평가(LLM)를 돌리기 전에는 한 줄 요약이 없다. 그런데 판결문 자체에
      // 법원이 쓴 **판시사항**(대법원) 또는 **주문**(하급심)이 들어 있다.
      // 실측: 112건 전부에서 뽑혔다 (판시사항 66건 · 주문 46건).
      if (url.pathname === '/api/case') {
        const id = url.searchParams.get('id') || '';
        if (!/^[0-9]+$/.test(id)) return Response.json({ error: 'bad id' }, { status: 400 });
        const d = await getJson(env, 'data/cases/' + id + '.json');
        if (!d) return Response.json({ found: false });
        const flat = (t) => String(t || '').replace(/\s+/g, ' ').trim();
        let kind = '', text = '';
        for (const k of ['판시사항', '판결요지']) {
          if (flat(d[k])) { kind = k; text = flat(d[k]); break; }
        }
        if (!text) {
          // 하급심은 위 두 칸이 비어 있다 — 판결문 본문에서 '주문' 을 뽑는다
          const m = /\u3010\s*주\s*문\s*\u3011([\s\S]*?)(?=\u3010|$)/.exec(d['판례내용'] || '');
          if (m) { kind = '주문(판결 결과)'; text = flat(m[1]); }
          else { kind = '앞부분'; text = flat(d['판례내용']).slice(0, 400); }
        }
        return Response.json({
          found: true, kind, text: text.slice(0, 700),
          court: flat(d['법원명']), at: flat(d['선고일자']),
        });
      }

      if (url.pathname === '/api/auditionindex') {
        const id = url.searchParams.get('id') || '';
        if (!/^\d+$/.test(id)) return Response.json({ items: [] });
        try {
          const r0 = await fetch(`${GH}/repos/${REPO}/releases/assets/${id}`, {
            headers: { 'Authorization': `Bearer ${env.GH_TOKEN}`,
                       'Accept': 'application/octet-stream',
                       'User-Agent': 'verdict-theater-admin' } });
          if (!r0.ok) return Response.json({ items: [] });
          return Response.json(await r0.json());
        } catch { return Response.json({ items: [] }); }
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
        // ⭐ **만든 시각(at)도 함께 준다.** 이게 없으면 [다시 만들기] 를 눌러도
        //    바뀐 건지 아닌지 알 수가 없다 — 문구만 바뀌면 그림이 비슷해서
        //    '안 바뀐다' 로 보인다 (2026-08-09 손님 지적).
        const t = assets.find((a) => a.name === THUMB_NAME);
        const thumb = t ? { id: t.id, size: t.size,
                            at: t.updated_at || t.created_at } : null;
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

      // 목소리 들어보기 파일 재생 / 내려받기 (보관함의 mp3 를 그대로 흘려보낸다).
      //   손님은 아이폰만 쓰시므로, 화면에서 재생 버튼만 누르면 되어야 한다.
      if (url.pathname === '/api/audio') {
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
        if (!up.ok)
          return new Response('소리를 가져오지 못했습니다 (' + up.status + ')', { status: 502 });
        const h = new Headers();
        h.set('Content-Type', 'audio/mpeg');
        h.set('Cache-Control', 'private, no-store');
        if (dl) {
          const safe = String(dl).replace(/[^A-Za-z0-9_-]/g, '') || 'voice';
          h.set('Content-Disposition', `attachment; filename="${safe}.mp3"`);
        }
        const len = up.headers.get('Content-Length');
        if (len) h.set('Content-Length', len);
        return new Response(up.body, { status: 200, headers: h });
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

      // ⭐ 돌고 있는 것을 멈춘다 (2026-08-12 손님 요청)
      //    "대본 만들기 버튼 옆에 중단하기 버튼도 만들어줘"
      //    예전에는 멈추려면 GitHub 에 들어가 Cancel workflow 를 눌러야 했다.
      //    손님은 GitHub 에 안 들어간다("귀찮고 어려워") — 여기서 끝나야 한다.
      if (url.pathname === '/api/stop' && req.method === 'POST') {
        const { file } = await req.json();
        if (!WORKFLOWS.some((w) => w.file === file))
          return Response.json({ ok: false, error: '알 수 없는 워크플로' }, { status: 400 });
        // 그 워크플로에서 아직 안 끝난 실행을 찾는다 (대기 중인 것도 포함).
        let runs = [];
        for (const st of ['in_progress', 'queued', 'waiting', 'requested', 'pending']) {
          const r = await gh(env,
            `/repos/${REPO}/actions/workflows/${file}/runs?status=${st}&per_page=10`)
            .catch(() => ({ workflow_runs: [] }));
          runs = runs.concat(r.workflow_runs || []);
        }
        if (!runs.length)
          return Response.json({ ok: false, error: '지금 돌고 있는 것이 없습니다' });
        let done = 0;
        for (const r of runs) {
          try {
            await gh(env, `/repos/${REPO}/actions/runs/${r.id}/cancel`, { method: 'POST' });
            done += 1;
          } catch (e) { /* 이미 끝났을 수 있다 — 나머지를 계속 멈춘다 */ }
        }
        if (!done)
          return Response.json({ ok: false, error: '멈추지 못했습니다 (권한 확인 필요)' });
        return Response.json({ ok: true, n: done });
      }

      return new Response(appHtml(), { headers: HTML });
    } catch (e) {
      if (url.pathname.startsWith('/api/'))
        return Response.json({ ok: false, error: String(e).slice(0, 300) }, { status: 500 });
      return new Response('오류: ' + String(e).slice(0, 300), { status: 500 });
    }
  },
};
