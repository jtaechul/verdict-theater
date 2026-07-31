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
  { file: 'build-assets.yml', name: '0. 에셋 만들기', desc: '캐릭터·배경·소리. 한 번만',
    inputs: [{ k: 'what', label: '무엇을', type: 'select',
               opts: ['소리 (비용 0원)', '캐릭터 한 명 시험', '캐릭터 전부', '배경 전부', '빠진 것 확인만'] }] },
  { file: 'collect.yml', name: '1. 판례 수집', desc: '판례를 받아 기계 선정',
    inputs: [{ k: 'max_calls', label: '호출 수', type: 'text', def: '180' },
             { k: 'queries', label: '검색어 (비우면 전부)', type: 'text', def: '' }] },
  { file: 'script.yml', name: '2. 대본 만들기', desc: '소재 심사 + 12분 대본 + 쇼츠',
    inputs: [{ k: 'mode', label: '무엇을', type: 'select',
               opts: ['둘다', '소재 심사만', '대본 생성만', '쇼츠만 다시'] },
             { k: 'writer', label: '대본을 쓸 곳', type: 'select',
               opts: ['자동 (Claude 우선)', 'Claude', 'Gemini'] },
             { k: 'gate_limit', label: '심사 판례 수', type: 'text', def: '10' },
             { k: 'episode', label: "회차 ('쇼츠만 다시' 일 때만)", type: 'text', def: '' }] },
  { file: 'produce.yml', name: '3. 영상 만들기', desc: '렌더링 + 유튜브 비공개 업로드',
    inputs: [{ k: 'voice', label: '나레이션', type: 'select', opts: ['음성 생성', '무음으로 시험'] },
             { k: 'upload', label: '업로드', type: 'select', opts: ['롱폼만', '롱폼 + 쇼츠', '올리지 않음'] },
             { k: 'limit', label: '앞 N컷만 (0=전체)', type: 'text', def: '0' }] },
  { file: 'publish.yml', name: '4. 공개하기', desc: '검수 끝난 영상을 공개로',
    inputs: [{ k: 'episode', label: '회차', type: 'text', def: '' },
             { k: 'what', label: '무엇을', type: 'select',
               opts: ['롱폼', '쇼츠 1번 (궁금증형)', '쇼츠 2번 (분노형)', '쇼츠 3번 (사이다형)'] }] },
  { file: 'stats.yml', name: '5. 성과 보기', desc: '조회수·지속률·KPI 점검', inputs: [] },
];

const STAGE_LABEL = {
  selected: '소재 선정', scripting: '대본 작성 중', evaluated: '대본 완료',
  rendering: '영상 제작 중', uploaded_private: '검수 대기', approved: '승인됨',
  published: '공개됨',
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
.ep{display:flex;justify-content:space-between;align-items:center;gap:8px;
padding:13px 0;border-bottom:1px solid var(--line)}
.ep:last-child{border-bottom:0}
.ep b{font-size:15px}.ep small{color:var(--dim);display:block;font-size:13px}
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
  const eps = Object.entries(S.episodes || {}).sort((a,b) => b[0].localeCompare(a[0]));
  const ready = (S.queue || []).filter(q => q.gate_pass);
  const ungated = (S.queue || []).filter(q => q.gate_score == null);

  let h = '';
  h += '<div class="card"><h2>지금 상태</h2>';
  h += row('소재 대기열', (S.queue||[]).length + '건');
  h += row('제작 가능 (심사 통과)', ready.length + '건');
  h += row('심사 안 한 판례', ungated.length + '건');
  h += row('만든 회차', eps.length + '편');
  h += row('에셋', (S.assets ? S.assets.have + ' / ' + S.assets.need : '-'));
  h += '</div>';

  h += '<div class="card"><h2>회차</h2>';
  if (!eps.length) h += '<div class="empty">아직 만든 회차가 없습니다.<br>아래 <b>2. 대본 만들기</b>를 눌러 시작하십시오.</div>';
  eps.forEach(([id, v]) => {
    const st = STAGE[v.stage] || v.stage || '-';
    const cls = v.stage === 'published' ? 'ok' : (v.stage === 'uploaded_private' ? 'wait' : 'go');
    h += '<div class="ep"><div><b>' + id + '</b>'
      + '<small>' + esc(v.case_type||'') + ' · 소재 ' + (v.gate_score??'-') + '점 · 대본 ' + (v.script_score??'-') + '점</small></div>'
      + '<div style="text-align:right"><span class="pill ' + cls + '">' + st + '</span><br>'
      + '<button class="ghost" style="width:auto;padding:7px 12px;min-height:0;margin-top:7px;font-size:13px" '
      + 'onclick="script(\\'' + id + '\\')">대본 읽기</button></div></div>';
  });
  h += '</div>';

  h += '<div class="card"><h2>대기열 (점수순)</h2>';
  if (!(S.queue||[]).length) h += '<div class="empty">판례가 없습니다. <b>1. 판례 수집</b>을 먼저 누르십시오.</div>';
  (S.queue||[]).slice(0, 12).forEach(q => {
    const mark = q.gate_pass ? '' : (q.gate_score == null ? ' <span class="pill">심사 전</span>' : ' <span class="pill">폐기</span>');
    h += '<div class="q"><b>' + (q.gate_score ?? q.machine_score ?? '-') + '점</b>'
      + esc(q.case_type || q['사건명'] || '') + mark
      + '<div style="color:#9599ab;font-size:13px;margin-top:3px">' + esc(q.one_line || '') + '</div></div>';
  });
  h += '</div>';

  h += '<div class="card"><h2>실행</h2>';
  WF.forEach((w, i) => {
    h += '<div class="wf"><b>' + esc(w.name) + '</b><small>' + esc(w.desc) + '</small>';
    w.inputs.forEach(inp => {
      h += '<label>' + esc(inp.label);
      if (inp.type === 'select')
        h += '<select id="i_'+i+'_'+inp.k+'">' + inp.opts.map(o => '<option>' + esc(o) + '</option>').join('') + '</select>';
      else
        h += '<input id="i_'+i+'_'+inp.k+'" value="' + esc(inp.def || '') + '">';
      h += '</label>';
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

async function run(i) {
  const w = WF[i];
  const inputs = {};
  w.inputs.forEach(inp => { inputs[inp.k] = document.getElementById('i_'+i+'_'+inp.k).value; });
  toast(w.name + ' 실행 요청 중…');
  const r = await fetch('/api/run', { method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ file: w.file, inputs }) });
  const j = await r.json();
  toast(j.ok ? (w.name + ' 시작됨. 몇 분 뒤 새로고침하십시오.') : ('실패: ' + (j.error||'')), 6000);
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
  h += row('길이', mmss(total) + ' · ' + cuts.length + '컷');
  h += row('사건 유형', esc(m.case_type||'-'));
  (a.amounts_used||[]).forEach(x => { h += row(esc(x.label), esc(x.value)); });
  h += row('인용 조문', esc(((d.law||{}).refs_from_case||[]).join(', ') || '없음'));
  h += '</div>';

  h += '<div class="card"><h2>등장인물</h2>';
  (d.characters||[]).forEach(c => {
    h += '<div class="row"><span class="k">' + esc(c.nametag||'') + '</span>'
      + '<span class="v" style="font-weight:400;color:#9599ab;font-size:13px">' + esc(c.note||'') + '</span></div>';
  });
  h += '</div>';

  h += '<div class="card"><h2>먼저 볼 세 곳</h2>';
  const first = ((d.acts||[])[0]||{}).cuts||[];
  if (first[0]) h += hi('3초 관문 · 첫 컷 ' + first[0].sec + '초',
    who(first[0].speaker) + ': 「' + esc(first[0].text) + '」');
  const ang = tag('anger_line');
  if (ang) h += hi('분노 대사 · 쇼츠 2번이 될 한 줄', who(ang.speaker) + ': 「' + esc(ang.text) + '」');
  const ver = tag('verdict');
  if (ver) h += hi('판결 · 금액이 박히는 순간', esc(ver.text));
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
      const form = await req.formData();
      if (form.get('pw') !== env.ADMIN_PASSWORD) {
        return new Response(LOGIN_HTML.replace('<form', '<div style="color:#d2564a;font-size:14px">비밀번호가 다릅니다</div><form'),
          { status: 401, headers: { 'Content-Type': 'text/html; charset=utf-8' } });
      }
      const val = String(Date.now());
      const cookie = `vt=${encodeURIComponent(val + '.' + await sign(env, val))}` +
        '; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=2592000';
      return new Response(null, { status: 302, headers: { Location: '/', 'Set-Cookie': cookie } });
    }

    if (!ok) {
      if (url.pathname.startsWith('/api/'))
        return Response.json({ error: 'unauthorized' }, { status: 401 });
      return new Response(LOGIN_HTML, { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
    }

    try {
      if (url.pathname === '/api/state') {
        const [episodes, queue, manifest, runsRes, files] = await Promise.all([
          getJson(env, 'state/episodes.json'),
          getJson(env, 'state/queue.json'),
          getJson(env, 'assets/manifest.json'),
          gh(env, `/repos/${REPO}/actions/runs?per_page=10`).catch(() => ({ workflow_runs: [] })),
          listDir(env, 'assets/bg').catch(() => []),
        ]);
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
          runs: (runsRes.workflow_runs || []).map((r) => ({
            name: r.name, conclusion: r.conclusion, status: r.status, at: r.created_at,
          })),
        });
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

      return new Response(appHtml(), { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
    } catch (e) {
      if (url.pathname.startsWith('/api/'))
        return Response.json({ ok: false, error: String(e).slice(0, 300) }, { status: 500 });
      return new Response('오류: ' + String(e).slice(0, 300), { status: 500 });
    }
  },
};
