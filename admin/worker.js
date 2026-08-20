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
  // ⭐ 2026-08-18 대개편 — 영상은 구글(옴니 플래시)이 만든다.
  //    그림·소리·목소리를 우리가 만들던 카드들(에셋 만들기·효과음·목소리 오디션·
  //    목소리 바꾸기·썸네일·옛 영상 만들기)을 통째로 뺐다.
  //    남는 것은 지금도 도는 것뿐이다 — 소재 모으기 · 대본 · 성과 · 유튜브.
  { file: 'collect.yml', name: '1. 재판 기록 모으기',
    desc: '판례를 모아 대기열에 쌓습니다 (0원)',
    inputs: [{ k: 'max_calls', label: '최대 요청 수', type: 'text', v: '180' },
             { k: 'topic', label: '갈래', type: 'select',
               opts: ['전부', '불륜', '상속', '재산', '부양', '노년',
                      '가업', '혼외자', '제사', '빚'] },
             { k: 'queries', label: '직접 검색어 (비우면 자동)', type: 'text', v: '' },
             { k: 'pages', label: '페이지 수', type: 'text', v: '3' }] },

  { file: 'series.yml', name: '2. 시리즈 대본 만들기',
    desc: '판례 하나를 30초짜리 16화로 쪼갭니다. 매일 한 편씩 내고 16일이면 '
        + '8분 롱폼이 공짜로 나옵니다 (글만 쓰므로 수백 원)',
    inputs: [{ k: 'case', label: '판례 번호 (비우면 자동)', type: 'text', v: '' },
             { k: 'writer', label: '누가 쓸까요', type: 'select',
               opts: ['Gemini', 'Claude'] }] },

  { file: 'script.yml', name: '2. 대본 만들기',
    desc: '소재를 골라 대본을 씁니다 (회차당 수백 원)',
    inputs: [{ k: 'mode', label: '무엇을 할까요', type: 'select',
               opts: ['둘다', '소재 심사만', '대본 생성만', '이어서 마저 만들기',
                      '쇼츠만 다시',
                      { v: '도입 훅만 다시 쓰기 (앞 22초 · 약 150원)',
                        t: '도입 훅만 다시 쓰기 (약 150원)' }] },
             { k: 'episode', label: "회차 ('쇼츠만 다시' 일 때 · 예: EP002)", type: 'text', v: '' },
             { k: 'writer', label: '누가 쓸까요', type: 'select',
               opts: ['자동 (Claude 우선)', 'Claude', 'Gemini'] },
             { k: 'gate_limit', label: '살펴볼 소재 수', type: 'text', v: '10' },
             { k: 'budget', label: '값 상한(원)', type: 'text', v: '3000' }] },

  { file: 'stats.yml', name: '4. 성과 보기',
    desc: '올린 영상이 얼마나 보였는지 확인합니다 (0원)',
    inputs: [] },

  // hidden — 실행 목록에는 안 보이고 '영상 보기' 화면의 버튼만 부른다.
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
// ⭐ 올릴 제목·설명·해시태그를 대본에서 만든다 (2026-08-20).
//    ⚠️ src/ytmeta.py 와 **같은 결과**가 나와야 한다. 화면에서 본 것과
//       실제로 올라가는 것이 다르면 안 되기 때문이다.
//       (워크플로는 손님이 고친 meta.json 이 있으면 그것을 먼저 쓴다)
const YT_BASE_TAGS = ['판결극장', '실화사연', '사연', '법률사연', '쇼츠드라마', 'shorts'];
const YT_TOPIC = [
  [['유류분', '상속', '상속재산', '한정승인'], ['유류분', '상속', '상속분쟁']],
  [['내연', '불륜', '바람', '상간', '동거녀'], ['불륜', '외도', '상간소송']],
  [['이혼', '위자료', '재산분할'], ['이혼', '위자료', '재산분할']],
  [['보험금', '사망보험'], ['보험금분쟁']],
  [['사기', '횡령', '빼돌', '가로챈'], ['재산다툼']],
  [['층간', '이웃'], ['이웃분쟁']],
  [['임대', '전세', '보증금'], ['부동산분쟁']],
  [['폭행', '상해'], ['형사사건']],
];

function ytClean(t) { return String(t == null ? '' : t).replace(/\s+/g, ' ').trim(); }

function ytMeta(doc, no) {
  const eps = doc.episodes || [];
  const ep = eps.find((e) => +e.no === +no) || {};
  const total = eps.length;
  const series = ytClean(doc.title);
  const hook = ytClean(ep.hook) || ytClean(ep.title);
  const cut1 = (ep.cuts || [])[0] || {};
  const line = ytClean(String(cut1.subtitle || '').split(' / ')[0]).replace(/^"|"$/g, '');

  let title = ytClean(ep.yt_title);
  if (!title) title = hook || line || series;
  // ⭐ 몇 화인지는 우리가 붙인다 (대본에는 적지 말라고 일러 두었다)
  if (title.indexOf('(' + no + '/') < 0) title = title + ' (' + no + '/' + total + ')';
  if (title.toLowerCase().indexOf('#shorts') < 0 && title.length + 8 <= 100)
    title += ' #shorts';
  title = title.slice(0, 100);

  let tags = (ep.yt_tags || []).map((x) => ytClean(x).replace(/^#/, '')).filter(Boolean);
  if (!tags.length) {
    const blob = [doc.case_type, series, hook, ep.recap].map(ytClean).join(' ');
    tags = [];
    YT_TOPIC.forEach(([keys, out]) => {
      if (keys.some((k) => blob.indexOf(k) >= 0))
        out.forEach((t) => { if (tags.indexOf(t) < 0) tags.push(t); });
    });
    tags = tags.slice(0, 5);
  }
  YT_BASE_TAGS.forEach((b) => { if (tags.indexOf(b) < 0) tags.push(b); });
  tags = tags.slice(0, 15);

  let desc = ytClean(ep.yt_desc);
  if (!desc) {
    const recap = ytClean(ep.recap);
    const body = ['[' + series + '] ' + no + '화 / 전 ' + total + '화'];
    if (hook) { body.push(''); body.push(hook); }
    if (recap && +no > 1) body.push('(지난 이야기: ' + recap + ')');
    body.push('', '실제 판결문을 바탕으로 각색한 이야기입니다.',
              '등장인물의 이름·지명·금액은 모두 바꾸었습니다.', '',
              '매일 한 편씩 올라갑니다. 다음 화도 놓치지 마세요.', '',
              tags.map((t) => '#' + t).join(' '));
    desc = body.join('\n');
  }
  return { sid: doc.series_id || '', ep: +no, title,
           description: desc.slice(0, 4900), tags, privacy: 'private' };
}

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
/* 유튜브에 올릴 글 */
.ytbox{border:1px solid var(--line);border-radius:12px;padding:14px;margin-top:12px;
background:#161822}
.ytbox label{display:block;margin:12px 0 0;font-size:13px;color:var(--dim)}
.ytbox label small{color:#6d7182}
.ytd{width:100%;min-height:150px;margin-top:6px;padding:11px;border-radius:10px;
border:1px solid var(--line);background:#101219;color:var(--ink);
font:14px/1.55 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif;
resize:vertical}
/* 만든 영상 올리는 칸 */
.upbox{border:1px dashed #3a4055;border-radius:12px;padding:14px;background:#161822}
.upbox input[type=file]{width:100%;margin:0 0 10px;padding:10px;border-radius:9px;
border:1px solid var(--line);background:#101219;color:var(--ink);font-size:15px}
.uphint{color:var(--dim);font-size:13px;line-height:1.5;margin-top:8px}
/* 시리즈 — 클립 프롬프트를 눌러서 복사하는 상자 (2026-08-20) */
.pbox{border:1px solid var(--line);border-radius:12px;padding:12px;margin-bottom:10px;
background:#161822}
.pname{font-weight:700;font-size:15px;margin-bottom:4px}
.plabel{color:var(--dim);font-size:13px;margin:10px 0 5px;font-weight:600}
.plabel small{font-weight:400;color:#6d7182}
.ptext.short{max-height:none}
/* 프롬프트 본문. 길어도 화면을 밀지 않게 가로는 접고 세로로만 늘린다. */
.ptext{font:12px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace;color:#aeb3c4;
background:#101219;border:1px solid var(--line);border-radius:9px;padding:10px;
white-space:pre-wrap;word-break:break-word;max-height:190px;overflow-y:auto;margin-bottom:9px}
/* 1~16화 고르는 번호판. 손가락으로 눌리게 44px 이상. */
.epgrid{display:grid;grid-template-columns:repeat(8,1fr);gap:7px}
.epn{width:100%;min-height:44px;padding:0;font-size:15px;font-weight:700;
background:#262a38;color:var(--dim);border-radius:10px}
.epn.on{background:var(--gold);color:#1a1608}
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
.errbox{position:fixed;left:14px;right:14px;bottom:20px;background:#2b1d20;
border:1px solid #7a3a44;border-radius:12px;padding:14px;z-index:60;display:none;
word-break:break-all;font-size:13px;line-height:1.5}
.errbox b{color:#ff8896;display:block;margin-right:44px}
.errbox .ebody{margin-top:8px;color:#c8cbd6}
.errbox .eclose{position:absolute;top:10px;right:12px;background:none;border:1px solid #7a3a44;
border-radius:8px;color:#ff8896;font-size:13px;padding:4px 10px}
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
<div class="errbox" id="errbox"></div>
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
// ⭐ 2026-08-17: 버튼이 거부당한 **이유**가 6초짜리 알림으로만 떴다 사라져서,
//    손님도 개발자도 원인을 못 읽었다 ("또 실패"만 남음). 실패는 닫기 전까지
//    화면에 남는 상자로 보여준다. 내용은 textContent 로만 넣는다(주입 방지).
function showErr(title, detail) {
  const b = document.getElementById('errbox');
  b.textContent = '';
  b.style.position = 'fixed';
  const x = document.createElement('button');
  x.className = 'eclose'; x.textContent = '닫기';
  x.onclick = () => { b.style.display = 'none'; };
  const t = document.createElement('b');
  t.textContent = title;
  const d = document.createElement('div');
  d.className = 'ebody'; d.textContent = detail || '';
  b.appendChild(x); b.appendChild(t); b.appendChild(d);
  b.style.display = 'block';
  document.getElementById('toast').style.display = 'none';
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

// ⭐ 2026-08-20 손님: "관리자페이지에서 못봐??"
//    시리즈 대본(16화 × 5컷)을 만들어 놓고 화면에 안 띄워서 GitHub 링크를 드렸다.
//    손님은 GitHub 에 안 들어간다. 클립 프롬프트는 **여기서 복사**해 구글 플로우에
//    붙여 넣는 것이 실제 작업 순서이므로, 복사 버튼까지 여기 있어야 한다.
function seriesCard() {
  const list = Object.entries(S.series || {}).sort((a, b) => b[0].localeCompare(a[0]));
  let h = '<div class="card"><h2>시리즈 대본 <small style="font-weight:400;color:#9599ab">'
        + '— 하루 한 화(30초)씩 · 16화 모이면 8분 롱폼</small></h2>';
  if (!list.length) {
    h += '<div class="empty">아직 만든 시리즈가 없습니다.<br>'
       + '아래 <b>2. 시리즈 대본 만들기</b>를 눌러 시작하십시오.</div></div>';
    return h;
  }
  list.forEach(([sid, v]) => {
    const made = v.made || 0, tot = v.episodes || 16;
    h += '<div class="ep"><div class="ep-top"><div><b>' + esc(v.title || sid) + '</b>'
       + '<small>' + sid + ' · ' + tot + '화 · 만든 영상 ' + made + '/' + tot + '화</small></div>'
       + '<span class="pill ' + (made >= tot ? 'ok' : 'go') + '">'
       + (made >= tot ? '롱폼 가능' : (made + 1) + '화 차례') + '</span></div>'
       + '<div class="btns">' + mini('대본 보기', 'seriesView(\\'' + sid + '\\')', 'gold') + '</div></div>';
  });
  return h + '</div>';
}

// ⚠️ 2026-08-20 손님: 복사해서 플로우에 붙이니 이런 것이 붙었다 —
//      "...%20%22%EB%8D%94%EB%8A%94%20%EC%88%A8%20..."
//    공백이 %20, 줄바꿈이 %0A, 한글이 %EB.. 로 바뀐 **URL 인코딩**이다.
//    (빗금은 그대로인 것으로 보아 encodeURI 규칙)
//    우리 코드에는 그런 호출이 없다. 그래서 원인을 더 캐는 대신 **그런 일이
//    끼어들 자리 자체를 없앤다** — 화면에 그린 글자를 다시 읽어오지 않고
//    (HTML 을 거치면 실체 문자·엔티티·브라우저 처리가 낄 틈이 생긴다)
//    받아 둔 원본 문자열(SDOC)에서 곧바로 복사한다.
//
//    그리고 **복사한 것을 되읽어 확인한다.** 예전에는 실패해도 "복사했습니다"
//    라고 띄웠다 — 손님은 엉뚱한 것이 붙어도 알 길이 없었다.

// 지금 화면에서 복사할 수 있는 원본들. 화면을 그릴 때 여기에 담는다.
let COPY = {};

function copyRaw(key, label) {
  const t = COPY[key];
  if (typeof t !== 'string' || !t) { copyFailed(label, '복사할 글이 없습니다'); return; }
  const done = () => toast((label || '프롬프트') + ' 복사했습니다');

  // ⭐ 아이폰 사파리·크롬(둘 다 WebKit)에서 가장 확실한 길:
  //    **text/plain 이라고 못 박은 덩어리**를 클립보드에 넣는다.
  //    writeText 만 쓰면 브라우저가 알아서 다른 꼴(HTML·URL)을 같이 얹는 일이
  //    있고, 받는 쪽이 그 꼴을 집으면 %20 · %EB 같은 글자가 끼어든다.
  //    write([ClipboardItem]) 은 우리가 넣은 꼴 하나만 들어간다.
  //    ⚠️ 반드시 손가락이 누른 그 순간(onclick) 안에서 불러야 한다.
  //       기다렸다 부르면 아이폰이 '사용자가 시킨 일' 로 안 보고 막는다.
  try {
    // ⚠️ window.ClipboardItem 으로 보면 안 된다 — window 가 없는 자리도 있고,
    //    시험에서도 이 길을 못 타고 옛 길로 새는 것을 잡았다. 이름 그대로 본다.
    if (navigator.clipboard && navigator.clipboard.write
        && typeof ClipboardItem !== 'undefined') {
      const item = new ClipboardItem({
        'text/plain': new Blob([t], { type: 'text/plain' }),
      });
      navigator.clipboard.write([item]).then(done, () => plainCopy(t, label, done));
      return;
    }
  } catch (e) { /* 이 기기에 ClipboardItem 이 없다 — 아래로 */ }
  plainCopy(t, label, done);
}

// 두 번째 길 — 글자만 넣기
function plainCopy(t, label, done) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(t).then(done, () => legacyCopy(t, label, done));
  } else legacyCopy(t, label, done);
}

// 세 번째 길 — 옛 방식. 아이폰은 글상자가 **보이는 상태**여야 잡힌다.
//   화면 밖(top:-9999px)이나 opacity:0 으로 두면 iOS 가 선택을 지워 버려
//   execCommand 가 조용히 실패한다. 그래서 화면 안에 두되 1px 로 만든다.
function legacyCopy(t, label, done) {
  const a = document.createElement('textarea');
  a.value = t;
  a.contentEditable = 'true';
  a.readOnly = false;
  a.style.position = 'fixed';
  a.style.left = '0'; a.style.top = '50%';
  a.style.width = '1px'; a.style.height = '1px';
  a.style.padding = '0'; a.style.border = '0';
  a.style.fontSize = '16px';          // 16px 미만이면 아이폰이 화면을 확대해 버린다
  document.body.appendChild(a);

  const r = document.createRange();
  r.selectNodeContents(a);
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(r);
  a.setSelectionRange(0, t.length);   // 아이폰은 이것까지 있어야 확실히 잡힌다

  let ok = false;
  try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
  sel.removeAllRanges();
  document.body.removeChild(a);
  if (ok) done();
  else copyFailed(label, '이 브라우저가 복사를 막았습니다. 주소가 https 인지 확인해 주십시오.');
}

//  운영자가 그런 우회로 말고 복사가 그냥 되게 하라고 했다 — 2026-08-20)
function copyFailed(label, why) {
  showErr((label || '프롬프트') + ' 복사 실패', why);
}

let SDOC = null, SID = '', SEP = 1;

// ⭐ 압축파일을 그대로 서버로 보낸다. 서버가 깃허브 릴리스에 올리고
//    [3. 올린 영상으로 쇼츠 만들기] 를 부른다.
async function upClips() {
  const el = document.getElementById('clipzip');
  const msg = document.getElementById('upmsg');
  const f = el && el.files && el.files[0];
  if (!f) { msg.textContent = '먼저 압축파일을 고르십시오.'; return; }
  const mb = f.size / 1048576;
  if (mb > 90) { showErr('파일이 큽니다',
    Math.round(mb) + 'MB 입니다. 90MB 까지만 올릴 수 있습니다.'); return; }
  msg.textContent = f.name + ' (' + mb.toFixed(1) + 'MB) 올리는 중… 잠시 기다리십시오.';
  try {
    const r = await fetch('/api/upload-clips?sid=' + encodeURIComponent(SID)
                          + '&ep=' + SEP, { method: 'POST', body: f });
    const j = await r.json();
    if (!j.ok) { showErr('올리지 못했습니다', (j.error || '') + ' ' + (j.detail || '')); 
                 msg.textContent = ''; return; }
    msg.textContent = '✅ 올렸습니다. 쇼츠를 만드는 중입니다 (2~4분).';
    toast(SEP + '화 영상을 올렸습니다');
    watchShort();
  } catch (e) {
    showErr('올리지 못했습니다', String(e && e.message ? e.message : e));
    msg.textContent = '';
  }
}

// 다 만들어졌는지 30초마다 들여다본다
// ⭐ 유튜브에 올릴 글 (2026-08-20 운영자: "제목·설명·해시태그 아무것도 안 들어가
//    있어. 업로드 설정도 같이 추가해 줘.")
//    대본에서 만들어 보여 주고, **고친 그대로** 올린다.
async function ytLoad() {
  const b = document.getElementById('ytbox');
  if (!b) return;
  b.innerHTML = '<div class="uphint">올릴 글 준비 중…</div>';
  let m = null;
  try {
    m = await (await fetch('/api/yt-meta?sid=' + SID + '&ep=' + SEP
                           + '&t=' + Date.now())).json();
  } catch (e) { b.innerHTML = '<div class="uphint">올릴 글을 못 불러왔습니다.</div>'; return; }
  if (m.error) { b.innerHTML = '<div class="uphint">' + esc(m.error) + '</div>'; return; }
  YT = m;
  b.innerHTML =
    '<div class="ytbox"><b>유튜브에 올릴 내용</b>'
    + (m.saved ? '<div class="uphint">(전에 고쳐 두신 것입니다)</div>' : '')
    + '<label>제목 <small>100자까지</small></label>'
    + '<input id="ytt" maxlength="100" value="' + esc(m.title) + '">'
    + '<label>해시태그 <small>쉼표로 나눕니다</small></label>'
    + '<input id="ytg" value="' + esc((m.tags || []).join(', ')) + '">'
    + '<label>설명</label>'
    + '<textarea id="ytd" class="ytd">' + esc(m.description) + '</textarea>'
    + '<label>공개 범위</label>'
    + '<select id="ytp">'
    + '<option value="private">비공개 (나만 보기) — 먼저 확인하실 때</option>'
    + '<option value="unlisted">일부 공개 (링크 있는 사람만)</option>'
    + '<option value="public">전체 공개</option>'
    + '</select>'
    + '<div class="btns" style="margin-top:12px">'
    + mini('글 저장', 'ytSave()')
    + mini('연습 (안 올리고 확인만)', 'ytUp(true)')
    + mini('유튜브에 올리기', 'ytUp(false)', 'gold')
    + '</div><div id="ytmsg" class="uphint"></div></div>';
}

let YT = null;

function ytForm() {
  const t = (document.getElementById('ytt') || {}).value || '';
  const g = ((document.getElementById('ytg') || {}).value || '')
    .split(',').map((x) => x.trim().replace(/^#/, '')).filter(Boolean);
  const d = (document.getElementById('ytd') || {}).value || '';
  const p = (document.getElementById('ytp') || {}).value || 'private';
  return { sid: SID, ep: SEP, title: t, description: d, tags: g, privacy: p };
}

async function ytSave() {
  const msg = document.getElementById('ytmsg');
  const f = ytForm();
  if (!f.title.trim()) { showErr('제목이 비었습니다', '제목을 적어 주십시오.'); return; }
  msg.textContent = '저장하는 중…';
  const r = await fetch('/api/yt-save', { method: 'POST', body: JSON.stringify(f) });
  const j = await r.json();
  if (!j.ok) { showErr('저장하지 못했습니다', (j.error || '') + ' ' + (j.detail || ''));
               msg.textContent = ''; return; }
  msg.textContent = '✅ 저장했습니다. 이대로 올라갑니다.';
  toast('올릴 글을 저장했습니다');
}

async function ytUp(dry) {
  const msg = document.getElementById('ytmsg');
  const f = ytForm();
  if (!f.title.trim()) { showErr('제목이 비었습니다', '제목을 적어 주십시오.'); return; }
  if (!dry && f.privacy === 'public'
      && !confirm('전체 공개로 올립니다. 되돌리려면 유튜브 앱에서 직접 바꿔야 합니다. 올릴까요?'))
    return;
  msg.textContent = '올릴 글을 저장하는 중…';
  let r = await fetch('/api/yt-save', { method: 'POST', body: JSON.stringify(f) });
  let j = await r.json();
  if (!j.ok) { showErr('저장하지 못했습니다', (j.error || '') + ' ' + (j.detail || ''));
               msg.textContent = ''; return; }
  msg.textContent = dry ? '연습으로 확인하는 중…' : '유튜브에 올리는 중…';
  r = await fetch('/api/yt-up', { method: 'POST',
    body: JSON.stringify({ sid: SID, ep: SEP, privacy: f.privacy, dry: !!dry }) });
  j = await r.json();
  if (!j.ok) { showErr('올리지 못했습니다', (j.error || '') + ' ' + (j.detail || ''));
               msg.textContent = ''; return; }
  msg.textContent = dry
    ? '연습을 시작했습니다. 2~3분 뒤 [지금 상태] 에서 결과를 보십시오.'
    : '올리기를 시작했습니다. 2~5분 걸립니다.';
  toast(dry ? '연습으로 확인합니다' : '유튜브에 올리는 중입니다');
}

let SHORTW = null;
async function watchShort() {
  clearInterval(SHORTW);
  const tick = async () => {
    let j = null;
    try { j = await (await fetch('/api/short?sid=' + SID + '&ep=' + SEP
                                 + '&t=' + Date.now())).json(); } catch (e) { return; }
    if (!j || !j.ready) return;
    clearInterval(SHORTW);
    const b = document.getElementById('shortbox');
    if (!b) return;
    b.innerHTML = '<div style="margin-top:12px"><b>완성된 쇼츠</b>'
      + '<video controls playsinline style="width:100%;border-radius:12px;margin-top:8px" '
      + 'src="/api/short?sid=' + SID + '&ep=' + SEP + '&play=1&t=' + Date.now() + '"></video>'
      + '<div class="uphint">' + Math.round((j.size || 0) / 1048576 * 10) / 10
      + 'MB · 영상을 보신 뒤 아래에서 올리십시오.</div>'
      + '<div id="ytbox"></div></div>';
    toast('쇼츠가 만들어졌습니다');
    ytLoad();
  };
  await tick();
  SHORTW = setInterval(tick, 30000);
}

async function seriesView(sid, ep) {
  SID = sid; SEP = ep || 1;
  if (!SDOC || SDOC._sid !== sid) {
    document.getElementById('app').innerHTML = '<div class="empty">대본 불러오는 중…</div>';
    const r = await fetch('/api/series?sid=' + encodeURIComponent(sid));
    const j = await r.json();
    if (!j.doc) { document.getElementById('app').innerHTML =
      '<div class="card"><div class="empty">대본을 찾을 수 없습니다.</div>'
      + '<button class="ghost" onclick="home()">돌아가기</button></div>'; return; }
    SDOC = j.doc; SDOC._sid = sid;
  }
  seriesRender();
}

function seriesRender() {
  VIEW = 'series';
  const d = SDOC, eps = d.episodes || [], e = eps[SEP - 1] || {};
  const sp = d.spec || { sec: 6, cuts: 5 };

  let h = '<button class="ghost" onclick="SDOC=null;home()">← 목록</button>'
        + '<div style="height:12px"></div>';

  h += '<div class="card"><h2>' + SID + '</h2>'
     + '<div style="font-size:18px;font-weight:700;margin-bottom:10px">'
     + esc(d.title || '') + '</div>';
  h += row('전체', eps.length + '화 × ' + sp.cuts + '컷 × ' + sp.sec + '초');
  h += row('한 화 길이', (sp.cuts * sp.sec) + '초');
  h += row('다 모으면', Math.round(eps.length * sp.cuts * sp.sec / 60 * 10) / 10 + '분 롱폼');
  h += row('하루 크레딧', (sp.cuts * sp.sec * 1.5) + ' / 무료 50');
  h += '</div>';

  // 복사할 원본은 **화면에 그린 글자를 다시 읽지 않고** 여기 담아 둔다
  COPY = {};

  // ① 캐릭터 — 플로우에서 얼굴을 먼저 만들어 두어야 화마다 같은 사람이 나온다
  h += '<div class="card"><h2>① 먼저 구글 플로우에서 인물을 만듭니다 '
     + '<small style="font-weight:400;color:#9599ab">— 한 번만 하면 됩니다'
     + '</small></h2>'
     + '<div class="uphint" style="margin:-4px 0 12px">플로우 [캐릭터 만들기] 에서 '
     + '인물마다 두 칸을 채웁니다. 아래 ①을 설명 칸에, ②를 사진 만드는 칸에 '
     + '붙여 넣으십시오.</div>';
  (d.characters || []).forEach((c, i) => {
    // ⭐ 2026-08-20 운영자: "인물 프롬프트가 너무 짧아 배경이 이상하게 뜬다.
    //    캐릭터 설명 넣을 내용도 같이 복사할 수 있게 해 줘."
    //    플로우 캐릭터 만들기 화면에는 **두 칸**이 있다 —
    //      ① 캐릭터 설명   ② 기준 사진을 뽑는 프롬프트
    //    각각 따로 복사할 수 있어야 한다.
    const csid = 'chs' + i, cdid = 'chd' + i;
    const sheet = String(c.flow_sheet || c.flow_prompt || '');
    const desc = String(c.flow_desc || c.flow_prompt || '');
    COPY[csid] = sheet;
    COPY[cdid] = desc;
    h += '<div class="pbox"><div class="pname">' + esc(c.name) + '</div>'
       + '<div class="plabel">① 캐릭터 설명 칸에 넣을 것</div>'
       + '<div class="ptext short">' + esc(desc) + '</div>'
       + mini('설명 복사', 'copyRaw(\\'' + cdid + '\\',\\'' + esc(c.name) + ' 설명\\')')
       + '<div class="plabel">② 기준 사진 만들 때 넣을 것 <small>'
       + sheet.split(/\s+/).length + '낱말</small></div>'
       + '<div class="ptext">' + esc(sheet) + '</div>'
       + mini('사진 프롬프트 복사', 'copyRaw(\\'' + csid + '\\',\\'' + esc(c.name) + ' 사진\\')', 'gold')
       + '</div>';
  });
  h += '</div>';

  // ② 화 고르기
  h += '<div class="card"><h2>② 만들 화를 고릅니다</h2><div class="epgrid">';
  eps.forEach((x, i) => {
    h += '<button class="epn' + (i + 1 === SEP ? ' on' : '') + '" onclick="SEP=' + (i + 1)
       + ';seriesRender();scrollTo(0,0)">' + (i + 1) + '</button>';
  });
  h += '</div></div>';

  // ③ 만든 영상 올리기 — 여기서 쇼츠가 나온다
  h += '<div class="card"><h2>③ 만든 영상 올리면 쇼츠가 됩니다 '
     + '<small style="font-weight:400;color:#9599ab">— 5컷을 압축(zip)해서 한 번에'
     + '</small></h2>';
  h += '<div class="upbox">'
     + '<input type="file" id="clipzip" accept=".zip,application/zip">'
     + '<div class="uphint">플로우에서 받은 ' + SEP + '화 클립 5개를 압축해서 고르십시오. '
     + '파일 이름에 c001~c005 가 있으면 그 번호대로, 없으면 이름 순서대로 붙입니다.</div>'
     + '<button class="gold" onclick="upClips()">' + SEP + '화 올리고 쇼츠 만들기</button>'
     + '<div id="upmsg" class="uphint"></div>'
     + '</div>';
  h += '<div id="shortbox"></div>';
  h += '</div>';

  // ④ 이 화의 5컷
  h += '<div class="card"><h2>④ ' + SEP + '화 — ' + esc(e.title || '') + '</h2>';
  if (e.recap) h += '<div style="color:#9599ab;font-size:14px;margin-bottom:10px">'
                  + '지난 줄거리: ' + esc(e.recap) + '</div>';
  // ⭐ 후킹은 30초 내내 화면 맨 위에 붙는 한 줄이다. 이걸 보고 남느냐 떠나느냐가
  //    갈리므로 영상 만들기 전에 운영자가 반드시 눈으로 본다 (2026-08-20).
  if (e.hook) h += '<div style="background:#2a2416;border:1px solid #6b5a24;'
                 + 'border-radius:8px;padding:10px 12px;margin-bottom:10px">'
                 + '<div style="color:#9599ab;font-size:12px">화면 맨 위 후킹 ('
                 + String(e.hook).length + '자)</div>'
                 + '<div style="color:#f0d68a;font-size:17px;font-weight:700">'
                 + esc(e.hook) + '</div></div>';
  (e.cuts || []).forEach((c, i) => {
    const pid = 'p' + SEP + '_' + (i + 1);
    COPY[pid] = String(c.prompt || '');
    const say = (String(c.prompt || '').split(String.fromCharCode(10))
      .find(l => l.indexOf('DIALOGUE:') === 0) || '').replace('DIALOGUE:', '').trim();
    h += '<div class="pbox"><div class="pname">' + c.n + '컷 · ' + esc(c.role || '')
       + ' <span style="color:#9599ab;font-weight:400">(' + sp.sec + '초)</span></div>';
    h += '<div style="color:#c8cbd6;font-size:14px;margin:6px 0">' + esc(say) + '</div>';
    if (c.subtitle) h += '<div style="color:#c6a04a;font-size:13px;margin-bottom:4px">'
                       + '대사 자막: ' + esc(c.subtitle) + '</div>';
    // 설명 자막 — 숫자·법률처럼 입으로 하면 어색한 사실을 우리가 화면에 얹는다
    if (c.caption) h += '<div style="color:#8fb0f0;font-size:13px;margin-bottom:6px">'
                      + '설명 자막: ' + esc(c.caption) + '</div>';
    h += '<div class="ptext">' + esc(c.prompt || '') + '</div>'
       + mini('이 컷 프롬프트 복사', 'copyRaw(\\'' + pid + '\\',\\'' + c.n + '컷\\')', 'gold')
       + '</div>';
  });
  h += '</div>';

  h += '<div class="card"><div class="btns">'
     + (SEP > 1 ? mini('◀ ' + (SEP - 1) + '화', 'SEP=' + (SEP - 1) + ';seriesRender();scrollTo(0,0)') : '')
     + (SEP < eps.length ? mini((SEP + 1) + '화 ▶', 'SEP=' + (SEP + 1) + ';seriesRender();scrollTo(0,0)') : '')
     + '</div></div>';

  document.getElementById('app').innerHTML = h;
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

  h += seriesCard();

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

  // ⭐ 2026-08-16 손님: "관리자 페이지가 너무 복잡해. 메뉴 구조조정이 필요해."
  //    화면 차례를 일하는 차례로 맞췄다 — [다음에 할 일] → [지금 상태] →
  //    [회차] → [실행(1→4)] 까지가 본 줄기고, 소재 대기열과 지난 수집
  //    결과는 참고 자료라 그 아래로 내렸다(접힌 채로 시작한다).
  // ⭐ 실행 차례대로 한 카드에 담는다 (2026-08-09 손님 두 차례 지적).
  //    ① "쓸데없는 메뉴가 많아"        → 가끔 쓰는 것은 접어 둔다
  //    ② "등장인물 목소리는 대본 아래쪽에 배치되는 게 정상이고, 감추기가 가능해야 해"
  //       → 목소리 일은 **대본을 쓴 뒤, 영상을 만들기 전**에 하는 것이 순서다.
  //         그 자리에 접힌 채로 넣는다.
  h += '<div class="card"><h2>실행 <small style="font-weight:400;color:#9599ab">'
     + '— 위에서부터 차례대로 누르시면 됩니다</small></h2>';
  h += wfList(['collect.yml', 'script.yml']);
  // 2026-08-18: 목소리 고르기 제거 — 소리는 구글이 영상과 함께 만든다.
  // ⚠️ 2026-08-12 — 그림 만들기가 **접힌 칸 안에 숨어 있었다.**
  //    손님: "관리자 페이지 안에 그림 소리 만들기가 없잖아."
  //    맞는 지적이었다. '가끔 쓰는 것' 에 넣어 뒀는데, 등장인물 그림이 없으면
  //    영상이 아예 안 나오므로 **지금 이것이 가장 중요한 버튼**이다.
  //    꺼내서 영상 만들기 바로 위에 둔다 — 순서도 실제로 그 순서다.
  h += wfList(['series.yml', 'stats.yml']);
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

// 2026-08-18: 목소리 오디션 카드 제거 — 소리는 구글이 영상과 함께 만든다.

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

// 2026-08-18: 목소리 바꾸기 제거 — 배역별 목소리를 우리가 고르지 않는다.

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
  // ⚠️ 2026-08-16 — eps 는 최신이 앞이라(내림차순) 그냥 find 하면 EP003 이
  //    EP002 를 제치고 뽑혔다. 손님: "회차가 갑자기 다음 회차로 넘어가는 문제."
  //    회차는 **차례대로** 간다 — 발행 안 된 것 중 가장 이른 회차부터
  //    (영상 만들기의 '자동'과 같은 규칙이라, 권하는 회차와 만드는 회차가 늘 같다).
  const noVideo = [...eps].sort((a, b) => a[0].localeCompare(b[0]))
    .find(([k, v]) => v.stage !== 'published' && !(S.videos || {})[k]);
  if (noVideo) {
    const err = (noVideo[1].validation_errors || 0);
    // 검사 오류가 남은 대본은 영상 만들기가 어차피 막는다 — 헛걸음 시키지 않는다.
    if (noVideo[1].stage !== 'evaluated' && err)
      return { title: esc(noVideo[0]) + ' 대본에 검사 오류가 ' + err + '건 남았습니다',
               body: '이대로 영상을 만들면 대본 검사에서 멈춥니다. 도입부 문제면 '
                   + '[대본 만들기]의 <b>도입 훅만 다시 쓰기</b>(약 150원)로 고쳐집니다.<br>'
                   + '<span style="color:#9599ab">고친 뒤에 이 자리가 [영상 만들기]로 바뀝니다.</span>' };
    return { title: esc(noVideo[0]) + ' 대본이 다 됐습니다 — 영상을 만들 차례입니다',
             body: '채점 <b>' + (noVideo[1].script_score || '-') + '점</b>'
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
  // ⚠️ 2026-08-16 — 회차 칸이 고르는 칸(choice)이 되면서 빈 값('')은
  //    깃허브가 거절한다. 목록에 있는 '자동'을 그대로 보낸다
  //    (자동 = 발행 안 된 가장 이른 회차 — 차례대로 간다).
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
  if (!j.ok) {
    showErr(w.name + ' — 실행이 시작되지 못했습니다',
            (j.error || '알 수 없는 이유') + (j.detail ? '  [깃허브 원문] ' + j.detail : ''));
    return;
  }
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

  // 2026-08-18: [이 영상만 다시 만들기] 제거 — 새 방식(구글 영상)에서 다시 붙인다.
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
  toast('시작했습니다 (10분 안팎). 완성 알림이 오면 대본을 읽어보시고, 괜찮으면 다음 단계로 넘어가시면 됩니다.', 9000);
}

// 2026-08-18: 한 편만 다시 만들기 제거 — 새 방식(구글 영상)에서 다시 붙인다.

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

// 2026-08-18: 썸네일 다시 만들기 제거 — 새 방식에서 다시 붙인다.

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
  // 2026-08-17: 통신이 끊기면 여기서 그대로 멈춰 "요청 중…"만 영원히 떠 있었다.
  let j = {};
  try {
    const r = await fetch('/api/run', { method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ file: w.file, inputs }) });
    if (r.status === 401) { location.href = '/'; return; }
    j = await r.json();
  } catch (e) { j = { ok: false, error: '연결이 끊겼습니다 — 인터넷을 확인하고 다시 눌러 주십시오' }; }
  if (!j.ok) {
    showErr(w.name + ' — 실행이 시작되지 못했습니다',
            (j.error || '알 수 없는 이유') + (j.detail ? '  [깃허브 원문] ' + j.detail : ''));
    return;
  }
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
        const [episodes, queue, series, manifest, runsRes, files, rels, scriptFiles] = await Promise.all([
          getJson(env, 'state/episodes.json'),
          getJson(env, 'state/queue.json'),
          // ⭐ 2026-08-20 손님: "관리자페이지에서 못봐??"
          //    시리즈 대본을 만들어 놓고 화면에 안 띄워, GitHub 링크를 드렸다.
          //    손님은 GitHub 에 안 들어간다 — 여기서 다 보여야 한다.
          getJson(env, 'state/series.json'),
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
          series: series || {},
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

      // ⭐ 시리즈 대본 한 편 (16화 × 5컷). 클립 프롬프트를 여기서 복사해
      //    구글 플로우에 붙여 넣는다.
      if (url.pathname === '/api/series') {
        const sid = url.searchParams.get('sid') || '';
        if (!/^S\d{3}$/.test(sid)) return Response.json({ error: 'bad sid' }, { status: 400 });
        const doc = await getJson(env, `data/series/${sid}.json`);
        return Response.json({ doc });
      }

      // ⭐ 2026-08-20 운영자: "압축파일로 올릴 거니까 영상 올리면 쇼츠로 만들 수
      //    있게 메뉴 만들어."
      //    받은 압축파일을 **릴리스 자산**으로 올린다. 저장소에 커밋하면 안 된다
      //    (MP4 는 지워도 깃 이력에 영구히 남아 저장소가 되돌릴 수 없이 커진다).
      //    올린 뒤 곧바로 [3. 올린 영상으로 쇼츠 만들기] 를 부른다.
      if (url.pathname === '/api/upload-clips' && req.method === 'POST') {
        const sid = url.searchParams.get('sid') || '';
        const ep = String(parseInt(url.searchParams.get('ep') || '0', 10) || 0);
        if (!/^S\d{3}$/.test(sid) || +ep < 1 || +ep > 99)
          return Response.json({ ok: false, error: '회차를 고르십시오' }, { status: 400 });
        const body = await req.arrayBuffer();
        if (!body.byteLength)
          return Response.json({ ok: false, error: '파일이 비었습니다' }, { status: 400 });
        if (body.byteLength > 90 * 1024 * 1024)
          return Response.json({ ok: false, error:
            '파일이 90MB 를 넘습니다. 클립을 나눠 올리거나 화질을 낮춰 주십시오.' },
            { status: 400 });

        const tag = `clips-${sid}-ep${String(ep).padStart(2, '0')}`;
        try {
          let rel;
          try {
            rel = await gh(env, `/repos/${REPO}/releases/tags/${tag}`);
          } catch (e) {
            rel = await gh(env, `/repos/${REPO}/releases`, {
              method: 'POST',
              body: JSON.stringify({ tag_name: tag, name: tag, body: '올린 클립' }),
            });
          }
          // 다시 올릴 수 있어야 하므로 같은 이름은 지우고 새로 올린다
          for (const a of rel.assets || []) {
            if (a.name === 'clips.zip')
              await gh(env, `/repos/${REPO}/releases/assets/${a.id}`, { method: 'DELETE' });
          }
          const up = await fetch(
            `https://uploads.github.com/repos/${REPO}/releases/${rel.id}/assets?name=clips.zip`,
            { method: 'POST', body,
              headers: {
                'Authorization': `Bearer ${env.GH_TOKEN}`,
                'Content-Type': 'application/zip',
                'User-Agent': 'verdict-theater-admin',
                'X-GitHub-Api-Version': '2022-11-28',
              } });
          if (!up.ok)
            throw new Error(`올리기 실패 ${up.status}: ${(await up.text()).slice(0, 200)}`);

          await gh(env, `/repos/${REPO}/actions/workflows/shorts.yml/dispatches`, {
            method: 'POST',
            body: JSON.stringify({ ref: BRANCH, inputs: { sid, ep } }),
          });
          return Response.json({ ok: true, tag, size: body.byteLength });
        } catch (e) {
          return Response.json({ ok: false, error: '올리지 못했습니다',
            detail: String(e && e.message ? e.message : e).slice(0, 220) }, { status: 502 });
        }
      }

      // 만들어진 쇼츠를 화면에서 바로 본다 (릴리스에서 그대로 흘려보낸다)
      if (url.pathname === '/api/short') {
        const sid = url.searchParams.get('sid') || '';
        const ep = String(parseInt(url.searchParams.get('ep') || '0', 10) || 0);
        if (!/^S\d{3}$/.test(sid)) return new Response('bad', { status: 400 });
        const tag = `short-${sid}-ep${String(ep).padStart(2, '0')}`;
        let rel = null;
        try { rel = await gh(env, `/repos/${REPO}/releases/tags/${tag}`); } catch { rel = null; }
        const a = (rel && (rel.assets || []).find((x) => x.name === 'short.mp4')) || null;
        if (!a) return Response.json({ ready: false });
        if (url.searchParams.get('play') !== '1')
          return Response.json({ ready: true, size: a.size, at: a.updated_at });
        const r0 = await fetch(`${GH}/repos/${REPO}/releases/assets/${a.id}`, {
          headers: {
            'Authorization': `Bearer ${env.GH_TOKEN}`,
            'Accept': 'application/octet-stream',
            'User-Agent': 'verdict-theater-admin',
          } });
        return new Response(r0.body, { headers: {
          'Content-Type': 'video/mp4', 'Cache-Control': 'no-store' } });
      }

      // ⭐ 2026-08-20 운영자: "동영상 올릴 때 제목·설명·해시태그 아무것도 안 들어가
      //    있어. 업로드 설정도 같이 추가해 줘."
      //    올릴 글을 만들어 주고(대본에서 · 0원), 손님이 고친 것을 릴리스에 담아 둔다.
      //    올릴 때 그 글을 그대로 쓴다 — 화면에서 본 것과 올라가는 것이 같아야 한다.
      if (url.pathname === '/api/yt-meta') {
        const sid = url.searchParams.get('sid') || '';
        const ep = String(parseInt(url.searchParams.get('ep') || '0', 10) || 0);
        if (!/^S\d{3}$/.test(sid)) return Response.json({ error: 'bad sid' }, { status: 400 });
        const tag = `short-${sid}-ep${String(ep).padStart(2, '0')}`;
        // 손님이 고쳐 둔 것이 있으면 그것을 먼저
        try {
          const rel = await gh(env, `/repos/${REPO}/releases/tags/${tag}`);
          const a = (rel.assets || []).find((x) => x.name === 'meta.json');
          if (a) {
            const r0 = await fetch(`${GH}/repos/${REPO}/releases/assets/${a.id}`, {
              headers: { 'Authorization': `Bearer ${env.GH_TOKEN}`,
                         'Accept': 'application/octet-stream',
                         'User-Agent': 'verdict-theater-admin' } });
            const saved = await r0.json();
            return Response.json({ ...saved, saved: true });
          }
        } catch (e) { /* 아직 없다 — 아래에서 만든다 */ }
        const doc = await getJson(env, `data/series/${sid}.json`);
        if (!doc) return Response.json({ error: '대본이 없습니다' }, { status: 404 });
        return Response.json({ ...ytMeta(doc, +ep), saved: false });
      }

      if (url.pathname === '/api/yt-save' && req.method === 'POST') {
        const { sid, ep, title, description, tags, privacy } = await req.json();
        if (!/^S\d{3}$/.test(sid || ''))
          return Response.json({ ok: false, error: '회차가 이상합니다' }, { status: 400 });
        if (!String(title || '').trim())
          return Response.json({ ok: false, error: '제목을 적어 주십시오' }, { status: 400 });
        const tag = `short-${sid}-ep${String(ep).padStart(2, '0')}`;
        const meta = { sid, ep: +ep, title: String(title).slice(0, 100),
                       description: String(description || '').slice(0, 4900),
                       tags: (tags || []).slice(0, 15), privacy: privacy || 'private' };
        try {
          const rel = await gh(env, `/repos/${REPO}/releases/tags/${tag}`);
          for (const a of rel.assets || []) {
            if (a.name === 'meta.json')
              await gh(env, `/repos/${REPO}/releases/assets/${a.id}`, { method: 'DELETE' });
          }
          const up = await fetch(
            `https://uploads.github.com/repos/${REPO}/releases/${rel.id}/assets?name=meta.json`,
            { method: 'POST', body: JSON.stringify(meta, null, 1),
              headers: { 'Authorization': `Bearer ${env.GH_TOKEN}`,
                         'Content-Type': 'application/json',
                         'User-Agent': 'verdict-theater-admin' } });
          if (!up.ok) throw new Error(`${up.status}: ${(await up.text()).slice(0, 160)}`);
          return Response.json({ ok: true });
        } catch (e) {
          return Response.json({ ok: false, error: '저장하지 못했습니다',
            detail: String(e && e.message ? e.message : e).slice(0, 200) }, { status: 502 });
        }
      }

      if (url.pathname === '/api/yt-up' && req.method === 'POST') {
        const { sid, ep, privacy, dry } = await req.json();
        if (!/^S\d{3}$/.test(sid || ''))
          return Response.json({ ok: false, error: '회차가 이상합니다' }, { status: 400 });
        const P = { public: '전체 공개', unlisted: '일부 공개 (링크 있는 사람만)',
                    private: '비공개 (나만 보기)' }[privacy || 'private'];
        try {
          await gh(env, `/repos/${REPO}/actions/workflows/shorts-upload.yml/dispatches`, {
            method: 'POST',
            body: JSON.stringify({ ref: BRANCH, inputs: {
              sid, ep: String(ep), privacy: P,
              mode: dry ? '연습 (올리지 않고 확인만)' : '진짜로 올리기' } }),
          });
          return Response.json({ ok: true });
        } catch (e) {
          return Response.json({ ok: false, error: '올리기를 시작하지 못했습니다',
            detail: String(e && e.message ? e.message : e).slice(0, 200) }, { status: 502 });
        }
      }

      if (url.pathname === '/api/run' && req.method === 'POST') {
        const { file, inputs } = await req.json();
        if (!WORKFLOWS.some((w) => w.file === file))
          return Response.json({ ok: false, error: '알 수 없는 워크플로' }, { status: 400 });
        const clean = {};
        for (const [k, v] of Object.entries(inputs || {})) if (v !== '') clean[k] = String(v);
        // ⭐ 2026-08-17: 깃허브가 실행 요청을 거절해도 이유가 화면에 안 남아
        //    "또 실패"만 반복됐다. 흔한 거절 코드는 쉬운 말로 풀고 원문도 붙인다.
        try {
          await gh(env, `/repos/${REPO}/actions/workflows/${file}/dispatches`, {
            method: 'POST', body: JSON.stringify({ ref: BRANCH, inputs: clean }),
          });
        } catch (e) {
          const s = String(e && e.message ? e.message : e);
          const m = s.match(/GitHub (\d{3})/);
          const code = m ? m[1] : '';
          const why =
            code === '401' ? '깃허브 열쇠(GH_TOKEN)가 만료되었거나 취소되었습니다. 열쇠를 새로 만들어 관리자 페이지에 다시 넣어야 합니다.'
            : code === '403' ? '깃허브 열쇠(GH_TOKEN)에 실행 권한(actions: write)이 없거나, 깃허브가 요청을 거부했습니다.'
            : code === '404' ? '깃허브가 저장소나 워크플로 파일을 찾지 못했습니다. 열쇠에 이 저장소 접근 권한이 빠졌을 때도 이렇게 나옵니다.'
            : code === '422' ? '버튼이 보낸 선택지 값이 워크플로의 목록과 다릅니다.'
            : '깃허브가 실행 요청을 받지 않았습니다.';
          return Response.json({ ok: false, error: why, detail: s.slice(0, 220) }, { status: 502 });
        }
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
