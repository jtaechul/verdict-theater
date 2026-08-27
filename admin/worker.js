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

// ⭐ 2026-08-22 — 이 판이 몇 번째 것인지. 배포할 때 deploy-admin.yml 이
//    깃 번호로 바꿔 넣는다.
//    왜: 운영자가 "또 뜬다" 고 하셨을 때, 그 화면이 **고치기 전 것인지 후의
//    것인지** 알 길이 없었다. 오류 글에 판 번호를 같이 찍어 두면 한눈에 안다.
const BUILD = 'dev';
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

  { file: 'series.yml', name: '2. 대본 만들기 (한 판례 → 대본)',
    desc: '판례 하나를 30초짜리 16화로 쪼갭니다. 매일 한 편씩 내고 16일이면 '
        + '8분 롱폼이 공짜로 나옵니다 (글만 쓰므로 수백 원)',
    inputs: [{ k: 'case', label: '판례 번호 (비우면 자동)', type: 'text', v: '' }] },

  { file: 'polish.yml', name: '3. 대본 다듬기',
    desc: '만든 16화를 한 번 더 읽혀 말투·앞뒤 맞음·자극성을 다듬습니다. '
        + '기계로 잡히는 것(누설·빠진 폭로·답으로 끝내기·금액 어긋남)은 이미 '
        + '0원으로 걸러지고, 여기서는 기계가 못 보는 것만 봅니다',
    inputs: [{ k: 'mode', label: '무엇을 할까요', type: 'select',
               opts: ['검토 (약 150원)', '반영 (0원)'] },
             { k: 'sid', label: '시리즈 번호', type: 'text', v: 'S001' },
             { k: 'pick', label: '고를 번호 (비우면 전부 · 예: 1,3,7)',
               type: 'text', v: '' }] },

  // ⭐⭐⭐ 2026-08-26 운영자: "실사로 가자. 시험 만들어."
  //    루미나(손으로 만들기)에서 **구글 Veo(자동)** 로 갈아탄다.
  //    맨 먼저 할 일은 **한 컷만** 만들어 한국어 입 모양을 눈으로 보는 것이다.
  { file: 'video.yml', name: '4. 영상 만들기 — 유료',
    desc: '실사 영상을 구글 Veo 로 만듭니다. ⭐ 처음이라면 "한 컷만 시험" 칸에 '
        + '1 을 넣고 눌러 보세요 — 4초짜리 한 컷만 만들어 한국어 입 모양과 '
        + '발음을 확인할 수 있고 값은 약 500원입니다. 비우면 한 화 전체를 '
        + '만들며 약 2,500원이 나갑니다',
    inputs: [{ k: 'sid', label: '시리즈 번호', type: 'text', v: 'S001' },
             { k: 'ep', label: '몇 화', type: 'text', v: '1' },
             { k: 'cut', label: '한 컷만 시험 (처음이면 1 · 비우면 전체)',
               type: 'text', v: '1' }] },

  // ⭐⭐⭐ 2026-08-27 운영자: "90초로 만들어."
  //    16화는 한 화에 사건이 하나뿐이라 "그래서 뭔데" 를 16번 기다려야 했다.
  //    한 편이면 5초 만에 32억이 나온다. 컷마다 영상을 만들면 7천 원이 넘으므로
  //    **그림 한 장 + 나레이션**으로 만든다 (손님: "비오로 하기 돈아까우니까").
  // ⚠️⚠️ 2026-08-27 — 이 단추를 실행 목록에서 **뺐다.** 손님 화면에 이것만
  //    보이고, 누르면 **올리신 인물 그림도 컷 영상도 안 쓰고** 그냥 돕니다.
  //    손님: "여기서 뭘 어떻게 넣으라는거야. 아무것도할수없잖아."
  //    → 90초 편은 아래 전용 화면(90초 한 편 ①②)에서만 시작한다.
  { file: 'short90.yml', name: '90초 한 편 만들기', desc: '', inputs: [], hidden: true },

  { file: 'stats.yml', name: '5. 성과 보기',
    desc: '올린 영상이 얼마나 보였는지 확인합니다 (0원)',
    inputs: [] },

  // ⭐ 2026-08-23 — 열쇠를 갈아끼운 뒤 **돈 쓰기 전에** 쓸 수 있는 열쇠인지 본다.
  //    계정은 유료인데 담긴 열쇠가 결제 안 붙은 것이어서 그림이 통째로 막힌 적이 있다.
  { file: 'keycheck.yml', name: '0. 열쇠 점검 (돈 쓰기 전에)',
    desc: '지금 담긴 열쇠로 그림·영상을 만들 수 있는지 확인합니다 (0원)',
    inputs: [] },

  // hidden — 실행 목록에는 안 보이고 '영상 보기' 화면의 버튼만 부른다.
  { file: 'youtube-upload.yml', name: '유튜브에 올리기', desc: '', inputs: [], hidden: true },
];

// ⭐ 재생할 수 있는 판들. 같은 영상에 소리만 다르게 얹은 것이다.
//    2026-08-23 — 소리를 누가 만들지 정하려면 **귀로 비교**해야 한다.
// ⚠️⚠️ 2026-08-27 손님: "시험1컷 영상 만들기 한거 어디서봐? 다 옛날 영상뿐인데?"
//    오늘 만든 것은 short.mp4 하나뿐인데 같은 자리에 사흘 전 ko.mp4 · veo.mp4 가
//    남아 있었고, 아래 PICK 이 **ko.mp4 를 먼저 골랐다.** 그래서 옛 영상이 떴다.
//    두 판 비교는 2026-08-23 에 '구글 소리로 확정' 하며 끝난 길이다. 지운다.
const PLAYABLE = ['short.mp4'];

const THUMB_NAME = 'thumb.jpg';           // 릴리스 자산에 들어 있는 썸네일 파일명

// 릴리스 자산 파일명 → 사람이 읽는 이름.
// ⭐ 순서가 화면 순서다. '목소리 확인' 을 맨 앞에 둬서, 만들어져 있으면
//    '영상 보기' 를 눌렀을 때 **바로 이것이 재생**되게 한다(한 번만 누르면 되도록).
//    영상 만들기를 다시 돌리면 이 파일은 저절로 사라지고 본편이 다시 맨 앞이 된다.
const VIDEO_LABEL = {
  // ⭐ 2026-08-23 — 같은 영상에 소리만 다르게 얹은 두 판. 귀로 듣고 고르시면 된다.
  'ko.mp4': '① 우리 한국어 목소리 (또박또박)',
  'veo.mp4': '② 구글이 만든 소리 (입은 정확 · 발음은?)',
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
  // ⚠️ 후킹의 `*…*` 는 색 넣을 자리 표시다 — 유튜브 글에서는 뗀다
  const hook = ytClean(String(ep.hook || '').replace(/\*([^*]+)\*/g, '$1'))
    || ytClean(ep.title);
  const cut1 = (ep.cuts || [])[0] || {};
  const line = ytClean(String(cut1.subtitle || '').split(' / ')[0]).replace(/^"|"$/g, '');

  let title = ytClean(ep.yt_title);
  if (!title) title = hook || line || series;
  // ⭐ 몇 화인지는 우리가 붙인다 (대본에는 적지 말라고 일러 두었다)
  // ⭐⭐ 2026-08-24 — 예전엔 `(1/16)`. 처음 보는 사람에게 '16편짜리'는
  //    분량 부담으로 읽힌다(1화 이탈률 60%를 파고들다 나온 것).
  //    순서는 알려 주되 총 편수는 안 보이게 `(1화)` 로.
  if (title.indexOf('(' + no + '화') < 0 && title.indexOf('(' + no + '/') < 0)
    title = title + ' (' + no + '화)';
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

// ⭐⭐ 2026-08-22 — 영상을 폰으로 흘려보내기.
//    ⚠️ 아이폰 사파리는 영상을 받을 때 "몇 번째 바이트부터 몇 번째까지" 를
//       먼저 물어본다(Range). 그걸 무시하고 통째로 주면 **재생 자체가 안 된다.**
//       /api/video 는 이걸 제대로 하고 있었는데 /api/short(완성된 쇼츠)는
//       그냥 통째로 주고 있었다. 운영자가 만든 영상을 한 번도 못 본 까닭이다.
//       같은 코드를 두 군데가 나눠 쓰게 해서 한쪽만 낡는 일을 없앤다.
async function streamAsset(env, req, id, fname) {
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
  // 받는 파일로 내려줄 때 — 브라우저가 재생 대신 저장 창을 띄운다
  if (fname) h.set('Content-Disposition', `attachment; filename="${fname}"`);
  for (const k of ['Content-Length', 'Content-Range', 'ETag', 'Last-Modified']) {
    const v = up.headers.get(k);
    if (v) h.set(k, v);
  }
  return new Response(up.body, { status: up.status, headers: h });
}

// ⚠️⚠️⚠️ 2026-08-22 — **쇼츠 만들기가 여기서 죽고 있었다.**
//    원래 이렇게 적혀 있었다:
//        const cut = String(parseInt(url.searchParams.get('cut') || '0', 10) || 0);
//    컷을 안 고르시면 이 값은 숫자 0 이 아니라 **글자 "0"** 이 된다.
//    자바스크립트는 글자 "0" 을 '있는 것'(참)으로 친다.
//    → 컷을 안 골랐는데도 cut="0" 이 워크플로로 넘어갔고, 워크플로는 그걸 보고
//      "한 컷만 시험" 길로 빠져 `❌ 1화에 0컷이 없다` 로 죽었다.
//      5컷을 다 올려도 완성본이 **한 번도** 안 나온 까닭이 이것이다.
//    → 완성된 쇼츠를 찾는 자리(/api/short)에도 똑같이 있었다. 그래서 어쩌다
//      만들어졌더라도 화면은 'short-…-cut0' 을 찾아 "아직 없습니다" 라고 했다.
//    두 군데가 같은 함수를 쓰게 해서, 한쪽만 고쳐지는 일을 없앤다.
function cutOf(url) {
  const n = parseInt(url.searchParams.get('cut') || '', 10);
  return Number.isInteger(n) && n >= 1 && n <= 9 ? String(n) : '';
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

// ── 큰 파일 임시 보관함 (클라우드플레어 KV) ──────────────────────────
//
// ⭐⭐ 2026-08-22 — 왜 이것이 생겼나 (읽고 나서 고치십시오)
//    관리자 페이지가 쥔 깃허브 열쇠(GH_TOKEN)는 **읽기 전용**이다.
//    그래서 브라우저에서 올린 압축파일을 깃허브 릴리스에 얹으려 하면
//    깃허브가 403 으로 막는다.
//
//    ⚠️ 그런데 **예전에 되던 길은 애초에 이 길이 아니었다.**
//       영상은 깃허브 **안(Actions)에서** 만들어졌고, 올리는 것도 워크플로
//       자신의 열쇠(GITHUB_TOKEN, 쓰기 있음)가 했다. 관리자 페이지는
//       "시작해" 하고 부르기만 했다 — 그건 actions:write 만 있으면 된다.
//       내가 브라우저→깃허브 직접 올리기를 새로 넣으면서 없던 권한이
//       필요해진 것이다. 손님 설정이 잘못된 게 아니라 내 설계가 어긋났다.
//
//    되돌리는 방법: 브라우저에서 올린 파일은 깃허브가 아니라 **여기(KV)** 에
//    잠깐 두고, 워크플로에는 **주소만** 넘긴다. 워크플로가 자기 열쇠로
//    받아 가서 예전과 똑같이 만들고 예전과 똑같이 릴리스에 올린다.
//    → 손님이 깃허브에 들어가 손댈 것은 하나도 없다.
//
// 보관함은 배포할 때 자동으로 만들어져 붙는다 (deploy-admin.yml).
const KV_CHUNK = 8 * 1024 * 1024;   // 조각 하나 8MB (KV 한 값 상한 25MB 안쪽)
// 90초 편 인물 카드 이름 (그림 파일 이름과 같아야 한다 — 아내는 '본처' 다)
const S90_CARDS = ['본처', '남편', '내연녀', '딸', '변호사'];

const KV_DAY = 60 * 60 * 24;
const KV_MAX = 90 * 1024 * 1024;    // 한 번에 받는 최대 크기

// 보관함이 붙어 있나. 배포가 오래됐으면 없을 수 있어 옛 길로 되돌아간다.
function bin(env) { return env && env.BLOB ? env.BLOB : null; }

// 흘러 들어오는 것을 조각내어 넣는다.
// ⚠️ 통째로 메모리에 올리지 않는다 — 90MB 를 한 손에 들면 워커가 죽는다.
async function blobPutStream(env, body, key, ttl) {
  const kv = bin(env);
  const rd = body.getReader();
  let hold = [], held = 0, part = 0, total = 0;
  const flush = async () => {
    if (!held) return;
    const buf = await new Blob(hold).arrayBuffer();
    await kv.put(`${key}.${part}`, buf, { expirationTtl: ttl });
    part += 1; total += held; hold = []; held = 0;
  };
  for (;;) {
    const { value, done } = await rd.read();
    if (done) break;
    hold.push(value); held += value.length;
    if (total + held > KV_MAX) throw new Error('TOO_BIG');
    if (held >= KV_CHUNK) await flush();
  }
  await flush();
  await kv.put(key, JSON.stringify({ parts: part, size: total,
    type: 'application/zip' }), { expirationTtl: ttl });
  return total;
}

// 짧은 글(올릴 제목·고른 목소리 따위)은 통째로 둔다
async function blobPutText(env, key, text, ttl) {
  const kv = bin(env);
  const opt = ttl ? { expirationTtl: ttl } : {};
  await kv.put(`${key}.0`, text, opt);
  await kv.put(key, JSON.stringify({ parts: 1,
    size: new TextEncoder().encode(text).length,
    type: 'application/json' }), opt);
}

async function blobText(env, key) {
  const kv = bin(env);
  if (!kv) return null;
  if (!(await kv.get(key))) return null;
  return await kv.get(`${key}.0`);
}

// 워크플로가 받아 갈 주소. 워커는 자기 주소를 요청에서 알아낸다 —
// 그래야 손님이 주소를 어디에도 등록할 필요가 없다.
function blobUrl(req, key) {
  return `${new URL(req.url).origin}/api/blob?key=${encodeURIComponent(key)}`;
}

// ⚠️⚠️ 여기 함정이 하나 있다 (모르면 "가끔 옛것이 올라간다" 로 나타난다)
//    보관함은 **전 세계에 퍼지는 데 최대 1분**이 걸린다. 손님(한국)이 방금
//    고친 것을, 깃허브 러너(미국)가 곧바로 읽으면 **고치기 전 것**이 나올 수 있다.
//    → 늘 같은 이름을 쓰는 것(올릴 글·고른 목소리)은 부를 때마다 **새 이름으로
//      한 벌 복사해** 그 주소를 넘긴다. 새 이름은 어디에도 캐시된 적이 없으므로
//      옛것이 나올 자리가 없다.
//    (압축파일은 애초에 올릴 때마다 새 이름이라 이 문제가 없다.)
async function blobPin(env, req, key, prefix) {
  const text = await blobText(env, key);
  if (!text) return null;
  const fresh = `${prefix}/${crypto.randomUUID()}`;
  await blobPutText(env, fresh, text, KV_DAY);
  return blobUrl(req, fresh);
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
<!-- ⭐ 2026-08-22 — 지금 보고 계신 화면이 **어느 판**인지 여기에 적힌다.
     운영자가 "또 뜬다" 고 하셨을 때 고치기 전 화면인지 알 길이 없었다.
     화면을 캡처해 주시면 이 줄로 바로 알 수 있다. -->
<div style="text-align:center;color:#4a4d5c;font-size:11px;padding:14px 0 24px">판 ${BUILD}</div>
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
//    손님은 GitHub 에 안 들어간다. 클립 프롬프트는 **여기서 복사**해 루미나에
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

// ⚠️ 2026-08-20 손님: 복사해서 루미나(예전 플로우)에 붙이니 이런 것이 붙었다 —
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

// ⭐⭐ 2026-08-23 — 루미나(Lumina)용으로 다듬어 준다.
//
//    운영자: "루미나는 레퍼런스를 참조하는 기능이 있어서 캐릭터를 넣고 영상을
//            제작하면 옷 같은 것들이 그대로 제작되기 때문에, 불필요한 부분은
//            오히려 삭제하는 게 더 맞을 거 같아."
//
//    맞는 말이다. 옷을 글로 또 적으면 **참조 그림과 싸운다** — 실제로 1화에서
//    카드(카키)와 대본(와인색)이 서로 다른 옷을 말해 4컷에서 세 번째 옷이
//    나왔다. 참조가 정하는 것은 글에서 빼는 것이 맞다.
//
//    빼는 것
//      · SUBJECT 줄 **통째로** (2026-08-25 운영자 지시)
//        까닭: 운영자가 루미나에서 **main body reference** 로 등장인물
//        **전신 참조 이미지**를 넣는다. 루미나는 그 사람이 무엇을 입었는지
//        이미 안다 — 거기에 글로 옷을 또 적으면 두 지시가 싸워서 **옷이
//        계속 바뀐다.** 막으려던 바로 그것이 생긴다.
//        (대본에서도 안 만들고, 검사기가 프롬프트 어느 줄에 있어도 잡는다)
//      · STYLE / COLOR / CONTINUITY 줄 (루미나는 참조로 화풍을 잡는다)
//      · VOICE / AUDIO 줄 (원본 나레이션을 그대로 쓰므로 필요 없다)
//    남기는 것 — SHOT · ACTION · DIALOGUE · SETTING · Avoid (연출과 대사)
function luminaPrompt(t) {
  // ⚠️⚠️ 2026-08-24 — 여기서 COLOR·STYLE 을 떼어 내고 있었다.
  //    2026-08-23 에 '루미나는 레퍼런스로 화풍을 잡으니 필요 없다'고 뺐는데,
  //    레퍼런스는 **사람**을 잡지 장면의 색·화풍을 안 잡는다. 그래서
  //    회차마다 색감이 달라졌다(운영자: "1화랑 2화랑 왜 색감이 달라?").
  //    → 색과 화풍은 반드시 남긴다. 떼는 것은 소리 지시뿐.
  //    ⚠️⚠️ 2026-08-24 (두 번째) — CONTINUITY 도 떼고 있었다. 그 줄이
  //    "앞 컷과 같은 옷·같은 방·같은 자리" 를 붙잡는 줄인데, 그것을 떼니
  //    컷마다 배경과 옷이 다시 그려져 이어지는 느낌이 사라졌다.
  //    (운영자: "컷별로 연결된다는 느낌이 안 들어") → 다시 남긴다.
  // ⚠️ 2026-08-25 — SUBJECT 를 통째로 뺀다. 대본에서도 안 만들지만,
  //    예전에 만들어 둔 대본에는 아직 남아 있을 수 있어 여기서도 막는다.
  const drop = ['SUBJECT:', 'VOICE:', 'AUDIO:', 'Avoid:'];
  // ⚠️ 여기는 백틱 문자열 안이다 — 주석에도 백틱을 쓰면 문자열이 끊긴다.
  // ⚠️⚠️ 2026-08-25 — 예전 대본에는 마지막 줄이 Avoid 였다. 그 줄의
  //    "옷을 갈아입지 마라 · 얼굴을 바꾸지 마라" 를 루미나 안전 검사기가
  //    **해 달라는 말로 읽어** 영상 만들기를 거절했다 (code=23007).
  //    지금 대본은 KEEP (바라는 것만) 으로 바뀌었지만, 옛 대본을 열었을
  //    때를 대비해 붙여 넣는 글에서도 Avoid 줄은 뺀다.
  const out = [];
  let skip = false;
  String(t || '').split(String.fromCharCode(10)).forEach((l) => {
    const head = /^[A-Z][A-Z ]{2,}:/.test(l);
    if (head) skip = drop.some((k) => l.indexOf(k) === 0);
    else if (skip && l.indexOf('  ') === 0) return;   // 이어지는 들여쓴 줄
    else if (skip) skip = false;
    if (skip) return;
    out.push(l);
  });
  // ⚠️ 이 코드는 템플릿 문자열 안에 있다. 정규식에 줄바꿈 이스케이프를 쓰면
  //    바깥 템플릿이 먼저 진짜 줄바꿈으로 풀어 버려 정규식이 통째로 깨진다
  //    (페이지가 안 뜬다). 빈 줄 정리는 정규식 없이 한다.
  const NL = String.fromCharCode(10);
  const lines = out.join(NL).split(NL);
  const tidy = [];
  lines.forEach((x) => {
    if (x.trim() === '' && tidy.length && tidy[tidy.length - 1].trim() === '') return;
    tidy.push(x);
  });
  return tidy.join(NL).trim();
}

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
  const cs = document.getElementById('cutone');
  const cut = (cs && cs.value) || '';
  if (CANWRITE === false) {
    showErr('영상 보관함이 아직 없습니다',
      '위 빨간 칸의 [영상 보관함 준비하기] 를 한 번 누르시고 1~2분 뒤에 '
      + '다시 올려 주십시오. 깃허브에서 하실 것은 없습니다.');
    return;
  }
  const mb = f.size / 1048576;
  if (mb > 90) { showErr('파일이 큽니다',
    Math.round(mb) + 'MB 입니다. 90MB 까지만 올릴 수 있습니다.'); return; }
  msg.textContent = f.name + ' (' + mb.toFixed(1) + 'MB) 올리는 중… 잠시 기다리십시오.';
  try {
    const r = await fetch('/api/upload-clips?sid=' + encodeURIComponent(SID)
                          + '&ep=' + SEP + (cut ? '&cut=' + cut : ''),
                          { method: 'POST', body: f });
    const j = await r.json();
    if (!j.ok) { showErr('올리지 못했습니다', (j.error || '') + ' ' + (j.detail || '')); 
                 msg.textContent = ''; return; }
    msg.textContent = '✅ 올렸습니다. ' + (cut ? cut + '컷 시험본을' : '쇼츠를')
      + ' 만드는 중입니다 (2~4분).';
    toast(SEP + '화 영상을 올렸습니다');
    watchShort(cut);
  } catch (e) {
    showErr('올리지 못했습니다', String(e && e.message ? e.message : e));
    msg.textContent = '';
  }
}

// ⭐⭐⭐ 2026-08-27 손님: "이미지 다 만들었어. 이제 다움은?"
//    제미나이에서 손수 만드신 인물 그림 다섯 장을 여기서 올린다. 올린 얼굴로
//    23컷을 그리므로 컷마다 같은 사람이 나오고, 인물 카드값(661원)도 안 나간다.
//    ⚠️ 손님을 깃허브로 보내지 않는다 — 관리자 페이지가 유일한 조작 화면이다.
const S90WHO = [['본처', '아내'], ['남편', '남편'], ['내연녀', '내연녀'],
                ['딸', '딸'], ['변호사', '변호사']];
let S90CARDS = {};

function short90Card() {
  let h = '<div class="card"><h2>90초 한 편 ① 인물 그림 '
        + '<small style="font-weight:400;color:#9599ab">'
        + '— 제미나이에서 만드신 다섯 장</small></h2>';
  h += '<div class="uphint">한 사람씩 골라 올리십시오. <b>올린 얼굴 그대로</b> '
     + '23컷을 그립니다. 올리지 않은 사람은 시스템이 알아서 그립니다. '
     + '한 번 올리면 다음에도 그대로 쓰입니다.</div>';
  S90WHO.forEach(function (p) {
    h += '<div class="upbox" style="margin-top:10px">'
       + '<b>' + p[1] + '</b> '
       + '<span class="uphint" id="s90st-' + p[0] + '">' 
       + (S90CARDS[p[0]] ? '올렸습니다' : '') + '</span>'
       // ⚠️ 여기서 따옴표로 이름을 넘기면 안 된다 — 이 코드는 통째로 템플릿
       //    문자열 안이라 \' 가 ' 로 풀려 버려 줄이 깨진다 (한 번 깨뜨렸다).
       //    칸 이름(id)에서 이름을 꺼내 쓰면 따옴표가 아예 필요 없다.
       + '<input type="file" accept="image/*" id="s90f-' + p[0] + '" '
       + 'onchange="upCard(this.id.slice(5))">'
       + '</div>';
  });
  h += '<div class="uphint" style="margin-top:10px">다 올리셨으면 <b>아래 ②</b> 로 '
     + '내려가 컷별 영상을 올리시고, 맨 아래 [90초 한 편 만들기] 를 누르십시오.</div>';
  h += '</div>';
  return h;
}

async function upCard(who) {
  const el = document.getElementById('s90f-' + who);
  const st = document.getElementById('s90st-' + who);
  const f = el && el.files && el.files[0];
  if (!f || !st) return;
  const mb = f.size / 1048576;
  if (mb > 90) { st.textContent = '너무 큽니다 (' + Math.round(mb) + 'MB)'; return; }
  st.textContent = '올리는 중…';
  try {
    const r = await fetch('/api/upload-card?who=' + encodeURIComponent(who),
                          { method: 'POST', body: f });
    const j = await r.json();
    if (!j.ok) {
      st.textContent = '못 올렸습니다';
      showErr('인물 그림을 못 올렸습니다', (j.error || '') + ' ' + (j.detail || ''));
      return;
    }
    S90CARDS[who] = j.url;
    st.textContent = '올렸습니다 (' + mb.toFixed(1) + 'MB)';
  } catch (e) {
    st.textContent = '못 올렸습니다';
    showErr('인물 그림을 못 올렸습니다', String(e && e.message ? e.message : e));
  }
}

// ⭐⭐⭐ 2026-08-27 손님: "이미지는 중간중간 섞여 있고 동영상도 있어야 돼. 알지?"
//    맞다. 전부 그림이면 슬라이드쇼다. 컷마다 —
//      · 붙여 넣을 영상 프롬프트를 보여 주고
//      · 만든 영상을 그 자리에서 올리게 한다
//    올린 컷만 영상이 되고 나머지는 그림으로 간다.
let S90DOC = null;
let S90CLIPS = {};

async function s90Cuts() {
  const box = document.getElementById('s90cuts');
  if (!box) return;
  if (!S90DOC) {
    try { S90DOC = (await (await fetch('/api/short90')).json()).doc; }
    catch (e) { S90DOC = null; }
  }
  const cuts = (S90DOC && S90DOC.cuts) || [];
  if (!cuts.length) { box.innerHTML = ''; return; }
  const nv = Object.keys(S90CLIPS).length;
  let h = '<div class="card"><h2>90초 한 편 ② 컷별 영상 '
        + '<small style="font-weight:400;color:#9599ab">— 올린 컷만 영상, 나머지는 그림'
        + '</small></h2>';
  h += '<div class="uphint">컷마다 [프롬프트 복사] 를 눌러 제미나이에 붙여 영상을 '
     + '만드시고, 만든 mp4 를 그 컷에 올리십시오. <b>말하는 컷(사람 이름이 붙은 컷)'
     + '부터</b> 하시면 됩니다 — 그 컷은 영상 안의 목소리를 그대로 씁니다. '
     + '나레이션 컷은 올리셔도 우리 나레이션이 깔립니다.</div>';
  h += '<div class="uphint" style="margin-top:6px">지금 영상으로 갈 컷 <b>'
     + nv + '개</b> · 그림으로 갈 컷 <b>' + (cuts.length - nv) + '개</b></div>';
  cuts.forEach(function (c) {
    const on = !!S90CLIPS[c.n];
    h += '<div class="upbox" style="margin-top:10px">'
       + '<b>컷 ' + c.n + '</b> '
       + '<span style="color:' + (c.kind === '나레이션' ? '#9599ab' : '#c6a04a') + '">'
       + esc(c.kind) + '</span> '
       + '<span class="uphint" id="s90cs-' + c.n + '">'
       + (on ? '영상 올림' : '그림으로 갑니다') + '</span>'
       + '<div class="uphint" style="margin:6px 0">' + esc(c.text) + '</div>'
       + '<textarea id="s90p-' + c.n + '" rows="2" readonly '
       + 'style="width:100%;font-size:12px">' + esc(c.veo) + '</textarea>'
       + '<button onclick="copyCut(this.id.slice(6))" id="s90cp-' + c.n + '">'
       + '프롬프트 복사</button> '
       + '<input type="file" accept="video/*" id="s90v-' + c.n + '" '
       + 'onchange="upCut(this.id.slice(5))">'
       + '</div>';
  });
  h += '<button class="gold" style="margin-top:14px" onclick="makeShort90()">'
     + '90초 한 편 만들기</button>'
     + '<div class="uphint" style="margin-top:8px">올린 컷은 영상으로, 나머지는 '
     + '그림으로 이어 붙여 약 100초짜리 한 편이 나옵니다. 10~20분 걸립니다.</div>'
     + '<div id="s90msg" class="uphint"></div>';
  h += '</div>';
  box.innerHTML = h;
}

function copyCut(n) {
  const t = document.getElementById('s90p-' + n);
  const b = document.getElementById('s90cp-' + n);
  if (!t) return;
  t.removeAttribute('readonly'); t.select(); t.setSelectionRange(0, 999999);
  try { document.execCommand('copy'); } catch (e) { }
  if (navigator.clipboard) { try { navigator.clipboard.writeText(t.value); } catch (e) { } }
  t.setAttribute('readonly', 'readonly');
  if (b) { b.textContent = '복사했습니다'; setTimeout(function () {
    b.textContent = '프롬프트 복사'; }, 2000); }
}

async function upCut(n) {
  const el = document.getElementById('s90v-' + n);
  const st = document.getElementById('s90cs-' + n);
  const f = el && el.files && el.files[0];
  if (!f || !st) return;
  const mb = f.size / 1048576;
  if (mb > 90) { st.textContent = '너무 큽니다 (' + Math.round(mb) + 'MB)'; return; }
  st.textContent = '올리는 중…';
  try {
    const r = await fetch('/api/upload-cut?n=' + encodeURIComponent(n),
                          { method: 'POST', body: f });
    const j = await r.json();
    if (!j.ok) {
      st.textContent = '못 올렸습니다';
      showErr('컷 영상을 못 올렸습니다', (j.error || '') + ' ' + (j.detail || ''));
      return;
    }
    S90CLIPS[n] = j.url;
    st.textContent = '영상 올림 (' + mb.toFixed(1) + 'MB)';
  } catch (e) {
    st.textContent = '못 올렸습니다';
    showErr('컷 영상을 못 올렸습니다', String(e && e.message ? e.message : e));
  }
}

async function makeShort90() {
  const m = document.getElementById('s90msg');
  const n = Object.keys(S90CARDS).length;
  const v = Object.keys(S90CLIPS).length;
  // 영상으로 올린 컷은 그림을 안 그리므로 그만큼 값이 빠진다
  const shots = Math.max(0, 23 - v);
  const cost = shots * 133 + 100 + (5 - n) * 133;
  if (!confirm('90초 한 편을 만듭니다. 영상 ' + v + '컷 · 그림 ' + shots
               + '컷, 약 ' + cost.toLocaleString()
               + '원이 나갑니다. 계속할까요?')) return;
  if (m) m.textContent = '시작하는 중…';
  try {
    const r = await fetch('/api/make-short90',
                          { method: 'POST',
                            body: JSON.stringify({ cards: S90CARDS, clips: S90CLIPS }) });
    const j = await r.json();
    if (!j.ok) {
      showErr('시작하지 못했습니다', (j.error || '') + ' ' + (j.detail || ''));
      if (m) m.textContent = '';
      return;
    }
    if (m) m.textContent = '시작했습니다. 10~20분 걸립니다. '
                         + '(올리신 얼굴 ' + n + '명 · 영상 ' + v + '컷 · '
                         + '나머지는 시스템이 그립니다)';
    toast('90초 한 편을 만들기 시작했습니다');
  } catch (e) {
    showErr('시작하지 못했습니다', String(e && e.message ? e.message : e));
    if (m) m.textContent = '';
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
// passive=true 면 **한 번만** 보고 끝낸다 (타이머를 안 켠다).
// ⚠️ 화면을 열 때마다 30초 타이머를 켜면 안 된다 — 화면 검사기가 끝나지
//    않고 멈췄고, 실제 화면에서도 타이머가 쌓인다.
// ⭐ 2026-08-23 운영자: "제작된 동영상은 저장할 수 있도록 기능 추가해줘."
//    받기 주소(dl=1)를 새 창으로 열면 아이폰이 내려받기 창을 띄운다.
//    받은 뒤 [공유] → [비디오 저장] 을 누르면 사진첩에 들어간다.
function shortDl(cut) {
  window.open('/api/short?sid=' + SID + '&ep=' + SEP
              + (cut ? '&cut=' + cut : '') + '&play=1&dl=1', '_blank');
  toast('내려받기를 시작했습니다');
}

async function watchShort(cut, passive) {
  clearInterval(SHORTW);
  const q = cut ? '&cut=' + cut : '';
  const tick = async () => {
    let j = null;
    try { j = await (await fetch('/api/short?sid=' + SID + '&ep=' + SEP + q
                                 + '&t=' + Date.now())).json(); } catch (e) { return; }
    // ⚠️ 아직 안 됐으면 **왜 안 됐는지** 말해 준다. 예전에는 아무 말도 없이
    //    조용해서, 만들기가 실패해도 "기능이 없다" 로 보였다.
    if (!j || !j.ready) { await buildSay(); return; }
    clearInterval(SHORTW);
    const b = document.getElementById('shortbox');
    if (!b) return;
    b.innerHTML = '<div style="margin-top:12px"><b>'
      + (cut ? cut + '컷 시험본' : '완성된 쇼츠') + '</b>'
      + '<video controls playsinline style="width:100%;border-radius:12px;margin-top:8px" '
      + 'src="/api/short?sid=' + SID + '&ep=' + SEP + q + '&play=1&t=' + Date.now()
      + '"></video>'
      + '<div class="uphint">' + Math.round((j.size || 0) / 1048576 * 10) / 10
      + 'MB' + (cut ? ' · 시험본입니다. 소리를 들어 보십시오.'
                    : ' · 영상을 보신 뒤 아래에서 올리십시오.') + '</div>'
      + '<div class="btns" style="margin-top:8px">'
      + mini('영상 받기 (기기에 저장)', 'shortDl(\\'' + (cut || '') + '\\')')
      + '</div></div>';
    // ⚠️⚠️ 2026-08-23 운영자: "유튜브에 올릴 내용이 중복으로 들어가 있어."
    //    예전엔 여기서 <div id="ytbox"> 를 **하나 더** 만들었다. 화면에는
    //    이미 같은 id 의 상자가 있어서(회차 화면 아래쪽), 둘 다 채워져
    //    같은 글이 두 벌로 보였다. 상자는 회차 화면의 **하나만** 쓴다.
    toast(cut ? cut + '컷 시험본이 만들어졌습니다' : '쇼츠가 만들어졌습니다');
    if (!cut) ytLoad();
  };
  await tick();
  if (!passive) SHORTW = setInterval(tick, 30000);
}

// ⭐⭐ 2026-08-22 — 압축파일을 다 올린 **뒤에야** 403 을 보는 일이 없게,
//    화면을 열 때 토큰이 쓰기를 할 수 있는지 먼저 알아본다.
//    (실제로 "GitHub 403: Resource not accessible by personal access token"
//     을 몇십 MB 올린 뒤에 봤다)
let CANWRITE = null;


async function permCheck() {
  const b = document.getElementById('permwarn');
  if (!b) return true;
  let j = null;
  try { j = await (await fetch('/api/can-write?t=' + Date.now())).json(); }
  catch (e) { return true; }            // 못 물어봤으면 막지는 않는다
  CANWRITE = !!(j && j.ok);
  if (CANWRITE) { b.innerHTML = ''; return true; }
  // ⭐⭐ 2026-08-22 — 여기에 "깃허브 가서 토큰 권한을 바꾸십시오" 라고 적어
  //    두었다가 크게 혼났다. 운영자는 깃허브에서 아무것도 하지 않는다.
  //    이제 고칠 것은 이 화면에서 버튼 하나로 끝난다.
  b.innerHTML =
    '<div style="border:1px solid #7a3b46;background:#2a1b1f;border-radius:10px;'
    + 'padding:12px;margin-bottom:10px;color:#f0b8c0;font-size:14px">'
    + '<b>영상 보관함이 아직 준비되지 않았습니다.</b><br>'
    + '아래를 한 번 누르시면 1~2분 뒤에 영상을 올릴 수 있습니다. '
    + '한 번만 하면 됩니다.'
    + '<div class="btns" style="margin-top:10px">'
    + mini('영상 보관함 준비하기', 'setupBlob()', 'gold')
    + '</div><div id="blobmsg" class="uphint"></div></div>';
  return false;
}

async function setupBlob() {
  const m = document.getElementById('blobmsg');
  if (m) m.textContent = '준비하는 중입니다…';
  try {
    const r = await fetch('/api/setup-blob', { method: 'POST' });
    const j = await r.json();
    if (!j.ok) { showErr('준비하지 못했습니다', (j.error || '') + ' ' + (j.detail || ''));
                 if (m) m.textContent = ''; return; }
  } catch (e) {
    showErr('준비하지 못했습니다', String(e && e.message ? e.message : e));
    if (m) m.textContent = ''; return;
  }
  if (m) m.textContent = '준비 중입니다. 1~2분 뒤 이 화면을 새로고침해 주십시오.';
  toast('영상 보관함을 준비하고 있습니다');
  // 스스로 다시 확인해 준다 — 새로고침을 잊어도 알아서 사라진다
  let n = 0;
  const t = setInterval(async () => {
    n += 1;
    const ok = await permCheck();
    if (ok || n > 20) clearInterval(t);
  }, 15000);
}


// ⭐ 만들기가 어떻게 됐는지 한 줄로 알려 준다
async function buildSay() {
  const b = document.getElementById('shortbox');
  if (!b) return;
  let j = null;
  try { j = await (await fetch('/api/build-status?t=' + Date.now())).json(); }
  catch (e) { return; }
  let msg = '';
  if (!j.ever) {
    msg = '아직 한 번도 안 만들었습니다. 위에서 압축파일을 올리고 '
        + '[' + SEP + '화 올리고 쇼츠 만들기] 를 누르십시오.'
        + (j.why ? ' (' + esc(j.why) + ')' : '');
  } else if (j.status !== 'completed') {
    msg = '만드는 중입니다… (2~4분)';
  } else if (j.conclusion === 'success') {
    msg = '만들기는 끝났는데 영상이 안 보입니다. 잠시 뒤 다시 열어 보십시오.';
  } else {
    msg = '❌ 만들기가 실패했습니다 (' + esc(j.conclusion || '') + '). '
        + '압축파일에 영상이 5개 다 들어 있는지 확인하고 다시 올려 주십시오.';
  }
  b.innerHTML = '<div class="uphint" style="margin-top:10px">' + msg + '</div>';
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

  // ① 캐릭터 — 루미나에서 인물을 먼저 만들어 두면 참조로 얼굴·옷이 고정된다
  h += '<div class="card"><h2>① 먼저 루미나에서 인물을 만듭니다 '
     + '<small style="font-weight:400;color:#9599ab">— 한 번만 하면 됩니다'
     + '</small></h2>'
     + '<div class="uphint" style="margin:-4px 0 12px">루미나 [캐릭터/레퍼런스] 에서 '
     + '인물마다 두 칸을 채웁니다. 아래 ①을 설명 칸에, ②를 사진 만드는 칸에 '
     + '붙여 넣으십시오.</div>';
  (d.characters || []).forEach((c, i) => {
    // ⭐ 2026-08-20 운영자: "인물 프롬프트가 너무 짧아 배경이 이상하게 뜬다.
    //    캐릭터 설명 넣을 내용도 같이 복사할 수 있게 해 줘."
    //    루미나 레퍼런스 화면에도 얼굴칸·설명칸이 있다 —
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
  // ⭐ 컷 수는 화마다 다르다 (보통 3개, 장소가 여럿이면 4개).
  //    화면에 5개라고 박아 두면 없는 컷을 만들라고 시키는 셈이다.
  const NC = ((e.cuts || []).length) || 3;
  h += '<div class="card"><h2>③ 만든 영상 올리면 쇼츠가 됩니다 '
     + '<small style="font-weight:400;color:#9599ab">— ' + NC + '컷을 압축(zip)해서 한 번에'
     + '</small></h2>';
  h += '<div class="upbox">'
     + '<div id="permwarn"></div>'
     + '<input type="file" id="clipzip" accept=".zip,application/zip">'
     + '<div class="uphint">루미나에서 <b>16:9(가로)</b> 로 만든 ' + SEP + '화 클립 '
     + NC + '개를 압축해서 고르십시오. 좌우 끝을 잘라 4:3 으로 만든 뒤 화면 가운데에 넣고, '
     + '위 칸에 후킹 · 아래 칸에 자막을 넣습니다. 루미나 AI 표시도 이때 같이 잘려 나갑니다.</div>'
     + '<div class="uphint" style="margin-top:8px">파일 이름에 c001~c00' + NC + ' 가 있으면 '
     + '그 번호대로, 없으면 이름 순서대로 붙입니다.</div>'
     + '<div class="uphint" style="margin-top:8px">클립 <b>하나만</b> 시험해 볼 수도 '
     + '있습니다. 그 클립 하나만 압축해서 올리고, 아래에서 몇 컷인지 고르십시오. '
     + '(만드는 차례는 전체와 똑같습니다 — 루미나 나레이션을 그대로 씁니다)</div>'
     + '<select id="cutone" style="margin-top:8px">'
     + '<option value="">전체 ' + NC + '컷 (완성본)</option>'
     + Array.from({ length: NC }, (_, i) =>
         '<option value="' + (i + 1) + '">' + (i + 1) + '컷만 시험</option>').join('')
     + '</select>'
     + '<button class="gold" onclick="upClips()">' + SEP + '화 올리고 쇼츠 만들기</button>'
     + '<div id="upmsg" class="uphint"></div>'
     + '</div>';
  h += '<div id="shortbox"></div>';
  // ⭐ 영상이 아직 없어도 **올릴 글은 지금 확인·수정할 수 있다.**
  //    대본에서 만들어지는 것이라 영상과 상관이 없다.
  h += '<div id="ytbox"></div>';
  h += '</div>';

  // ④ 이 화의 컷들 (보통 3개 · 장소가 여럿이면 4개)
  h += '<div class="card"><h2>④ ' + SEP + '화 — ' + esc(e.title || '') + '</h2>';
  // ⭐⭐ 2026-08-25 — 이 화가 **언제 얘기이고 무엇이 밝혀지는지**를 맨 위에
  //    적어 둔다. 운영자가 "스토리가 이해가 안 된다" 고 한 원인 하나가
  //    이것이었다 — 8년짜리 사건인데 어느 화가 언제인지 아무 데도 없었다.
  if (e.when || e.reveal) {
    h += '<div style="background:#16181f;border-left:3px solid #6b5a24;'
       + 'border-radius:6px;padding:10px 12px;margin-bottom:10px">';
    // ⭐ 2026-08-26 — 막(1막 배신 · 2막 죽음 · 3막 법정)과 '몇 년 뒤' 를 같이
    //    보여 준다. 운영자: "각 화마다 시간적 순서가 너무 많이 바뀌고 쌩뚱맞아."
    var ACTS = { 1: '1막 배신', 2: '2막 죽음', 3: '3막 법정' };
    if (e.when) h += '<div style="color:#c8a951;font-size:13px">'
                   + (ACTS[e.act] ? ACTS[e.act] + '  ·  ' : '')
                   + esc(e.stamp || e.when)
                   + (e.mood ? ' · ' + esc(e.mood) : '')
                   + (e.irony ? ' · 아내가 없는 화 (시청자만 먼저 압니다)' : '')
                   + (e.quiet ? ' · 조용한 화 (소리 안 지릅니다)' : '')
                   + '</div>';
    if (e.reveal) h += '<div style="color:#e7e9ef;font-size:14px;margin-top:4px">'
                     + '이 화에서 밝혀지는 것 — ' + esc(e.reveal) + '</div>';
    h += '</div>';
  }
  // 2026-08-25 운영자: "씬 간 연결성과 스토리 전개가 제대로 이루어지지 않고 있어."
  //    앞 화가 남긴 것에서 이 화가 시작되고, 이 화가 남긴 것에서 다음 화가
  //    시작된다. 그 고리를 화면에 그대로 보여 준다 — 끊긴 데가 눈에 보이게.
  if (e.because || e.leaves) {
    h += '<div style="background:#14161c;border-radius:6px;padding:10px 12px;'
       + 'margin-bottom:10px;font-size:13px;line-height:1.7">';
    if (e.because) h += '<div style="color:#9599ab">여기서 시작합니다 &larr; '
                      + esc(e.because) + '</div>';
    if (e.leaves) h += '<div style="color:#c8a951">여기서 다음 화로 &rarr; '
                     + esc(e.leaves) + '</div>';
    h += '</div>';
  }
  if (e.recap) h += '<div style="color:#9599ab;font-size:14px;margin-bottom:10px">'
                  + '지난 줄거리: ' + esc(e.recap) + '</div>';
  // ⭐ 후킹은 화면 **맨 위 검은 칸**에 내내 뜨는 한 줄이다. 이걸 보고 남느냐
  //    떠나느냐가 갈리므로 영상 만들기 전에 운영자가 반드시 눈으로 본다.
  //    (2026-08-24 — 영상을 4:3 으로 줄여 가운데에 넣으므로 위아래에 빈
  //     검은 칸이 생긴다. 후킹이 거기 앉으니 얼굴을 가릴 일이 없다.)
  // ⚠️ 여기는 백틱 문자열 안이다 — 정규식 역슬래시를 두 번 써야 살아남는다.
  //    한 번만 쓰면 브라우저에서 'g is not defined' 로 죽는다.
  //    (주석에도 백틱을 쓰면 안 된다 — 문자열이 거기서 끊긴다)
  //    후킹의 별표는 색 넣을 자리 표시라 화면 목록에서는 뗀다.
  if (e.hook) h += '<div style="background:#2a2416;border:1px solid #6b5a24;'
                 + 'border-radius:8px;padding:10px 12px;margin-bottom:10px">'
                 + '<div style="color:#9599ab;font-size:12px">후킹 문구 — 화면 위 검은 칸에 <b>내내</b> 뜹니다 (얼굴을 안 가립니다) ('
                 + String(e.hook).replace(/\\*([^*]+)\\*/g, '$1').length
                 + '자)</div>'
                 + '<div style="color:#f0d68a;font-size:17px;font-weight:700">'
                 + esc(String(e.hook).replace(/\\*([^*]+)\\*/g, '$1'))
                 + '</div></div>';
  (e.cuts || []).forEach((c, i) => {
    const pid = 'p' + SEP + '_' + (i + 1);
    COPY[pid] = luminaPrompt(String(c.prompt || ''));
    // ⚠️ 대사는 이제 여러 줄이다 — DIALOGUE 줄 + 그 아래 들여쓴 대사 줄들.
    //    한 줄만 집으면 화면에 '한국어로 말하라' 는 머리말만 뜬다.
    const _pl = String(c.prompt || '').split(String.fromCharCode(10));
    const _di = _pl.findIndex(l => l.indexOf('DIALOGUE:') === 0);
    let _dj = _di + 1;
    while (_dj < _pl.length && _pl[_dj].indexOf('  ') === 0) _dj++;
    const say = _di < 0 ? ''
      : _pl.slice(_di, _dj).join(' / ').replace('DIALOGUE:', '').trim();
    h += '<div class="pbox"><div class="pname">' + c.n + '컷 · ' + esc(c.role || '')
       + ' <span style="color:#9599ab;font-weight:400">(' + sp.sec + '초)</span></div>';
    h += '<div style="color:#c8cbd6;font-size:14px;margin:6px 0">' + esc(say) + '</div>';
    if (c.subtitle) h += '<div style="color:#c6a04a;font-size:13px;margin-bottom:4px">'
                       + '대사 자막: ' + esc(c.subtitle) + '</div>';
    // 설명 자막 — 숫자·법률처럼 입으로 하면 어색한 사실을 우리가 화면에 얹는다
    if (c.caption) h += '<div style="color:#8fb0f0;font-size:13px;margin-bottom:6px">'
                      + '설명 자막: ' + esc(c.caption) + '</div>';
    h += '<div class="ptext">' + esc(c.prompt || '') + '</div>'
       + mini('이 컷 프롬프트 복사', 'copyRaw(\\'' + pid + '\\',\\'' + c.n + '컷\\')', 'gold');
    // ⭐ 2026-08-22 — 앞 컷과 **같은 장소**면 루미나의 [이 영상에서 이어서
    //    만들기](장면 연장)를 쓰는 편이 훨씬 낫다. 앞 영상의 마지막 프레임을
    //    실제로 물려받으므로 옷·배경이 튈 수가 없다.
    //    그때는 방·옷을 다시 세우면 물려받은 화면과 싸우므로, **바뀌는 것만**
    //    적은 짧은 프롬프트를 따로 준다.
    if (c.ext) {
      const eid = 'ext' + SEP + '_' + c.n;
      h += '<div class="uphint" style="margin-top:10px">앞 컷과 같은 장소입니다. '
         + '루미나에서 앞 영상의 <b>[이어서 만들기]</b> 를 누르고 '
         + '아래 것을 넣으면 옷·배경이 안 튑니다.</div>'
         + '<div class="ptext" id="' + eid + '" style="display:none">'
         + esc(c.ext) + '</div>'
         + mini('이어서 만들기용 복사', 'copyRaw(\\'' + eid + '\\',\\''
                + c.n + '컷 이어서\\')');
    }
    h += '</div>';
  });
  h += '</div>';

  h += '<div class="card"><div class="btns">'
     + (SEP > 1 ? mini('◀ ' + (SEP - 1) + '화', 'SEP=' + (SEP - 1) + ';seriesRender();scrollTo(0,0)') : '')
     + (SEP < eps.length ? mini((SEP + 1) + '화 ▶', 'SEP=' + (SEP + 1) + ';seriesRender();scrollTo(0,0)') : '')
     + '</div></div>';

  document.getElementById('app').innerHTML = h;
  // ⭐ 2026-08-22 — 화면을 그린 **뒤에** 올릴 글과 만들기 상태를 붙인다.
  //    예전에는 영상이 다 만들어진 뒤에야 붙어서, 만들기가 실패하면
  //    "제목·해시태그·업로드 기능이 아예 없다" 로 보였다.
  //    ⚠️ 그리는 중에 부르면 안 된다 — 화면 검사기가 통째로 멈췄다.
  //       그리기는 그리기만 하고, 서버에 묻는 일은 뒤로 미룬다.
  setTimeout(function () {
    try { permCheck(); } catch (e) { /* 나중에 다시 */ }
    try { ytLoad(); } catch (e) { /* 나중에 다시 */ }
    try { watchShort('', true); } catch (e) { /* 나중에 다시 */ }
  }, 0);
}

function home() {
  VIEW = 'home';
  const eps = Object.entries(S.episodes || {}).sort((a,b) => b[0].localeCompare(a[0]));
  const ready = (S.queue || []).filter(q => q.gate_pass);
  const ungated = (S.queue || []).filter(q => q.gate_score == null);

  let h = '';
  h += nextCard(eps, ready, ungated);
  h += madeCard();
  h += '<div class="card"><h2>지금 상태</h2>';
  h += row('모아 둔 재판 기록', (S.queue||[]).length + '건');
  h += row('대본 만들 수 있는 소재', ready.length + '건');
  h += row('아직 안 살펴본 기록', ungated.length + '건');
  h += row('지금까지 만든 편수', eps.length + '편');
  h += row('그림·소리 준비', (S.assets ? S.assets.have + ' / ' + S.assets.need + ' 개' : '-'));
  h += '</div>';

  h += seriesCard();

  // ⭐ 2026-08-23 운영자: "이건 지금 쓸데 없는거잖아 당장 메뉴에서 지워."
  //    [회차] 칸(EP001·EP002·EP003)을 뺐다. 12분짜리 롱폼을 만들던 옛 방식의
  //    목록이라 지금 하는 일(시리즈 S001 → 30초 쇼츠 16편)과 상관이 없다.
  //    시리즈 쪽은 바로 위 seriesCard() 에 따로 있다.

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
  // ⚠️ 2026-08-27 — script.yml(옛 12분 롱폼 길)을 뺐다. 2026-08-23 에 접은
  //    길인데 메뉴에 남아 있었고, series.yml 과 번호까지 '2.' 로 겹쳤다.
  h += wfList(['collect.yml']);
  // 2026-08-18: 목소리 고르기 제거 — 소리는 구글이 영상과 함께 만든다.
  // ⚠️ 2026-08-12 — 그림 만들기가 **접힌 칸 안에 숨어 있었다.**
  //    손님: "관리자 페이지 안에 그림 소리 만들기가 없잖아."
  //    맞는 지적이었다. '가끔 쓰는 것' 에 넣어 뒀는데, 등장인물 그림이 없으면
  //    영상이 아예 안 나오므로 **지금 이것이 가장 중요한 버튼**이다.
  //    꺼내서 영상 만들기 바로 위에 둔다 — 순서도 실제로 그 순서다.
  // ⚠️⚠️ 2026-08-26 손님: "3-2가 관리자페이지에 없잖나…"
  //    맞다. video.yml(3-2) 과 keycheck.yml(0) 은 **WORKFLOWS 에 적어만 두고
  //    여기 목록에 안 넣어서** 화면에 한 번도 안 나왔다. 정의해 둔 것과
  //    그려지는 것이 따로 놀았다. 이제 tools/check_admin.mjs 가 이걸 잡는다.
  //    ⭐ 순서: 대본 → 다듬기 → **열쇠 점검 → 영상 만들기** → 성과.
  //       돈 나가기 전에 열쇠부터 보는 것이 실제 순서다.
  h += wfList(['series.yml', 'polish.yml',
               'keycheck.yml', 'video.yml', 'stats.yml']);
  h += '</div>';

  h += short90Card();
  h += '<div id="s90cuts"><div class="card"><h2>90초 한 편 ② 컷별 영상</h2>'
     + '<div class="empty">컷 목록 불러오는 중…</div></div></div>';

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
  // ⚠️ 화면에 글자를 넣은 **뒤에** 부른다. 앞에서 부르면 담을 자리가 아직
  //    없어서(getElementById 가 null) 컷 목록이 통째로 안 그려진다.
  //    2026-08-27 손님 화면에 컷별 영상 칸이 아예 안 나왔던 까닭이다.
  s90Cuts();
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
        // ⚠️ 2026-08-26 — inp.def 만 봤는데 목록은 v: 로 적혀 있다.
        //    그래서 **정해 둔 기본값이 한 번도 안 찍혔고** 칸이 늘 비어 있었다.
        //    ⚠️ 이 줄 위아래 주석에 백틱을 쓰면 안 된다 — 여기는 템플릿
        //       문자열 안이라 문자열이 통째로 끊긴다 (세 번째 사고다)
        //    ("S001", "1" 을 손님이 매번 손으로 넣어야 했다)
        h += '<input id="i_'+i+'_'+inp.k+'" value="'
           + esc(inp.def !== undefined ? inp.def : (inp.v || '')) + '">';
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
// ⚠️ 여기 없는 카드는 **접힌 채로** 나온다 — 제목 한 줄만 보이고 안이 안 보인다.
//    2026-08-27 손님이 90초 편 칸을 열지 못해 아무것도 못 하셨다.
// ⚠️ 새 검사가 잡아 준 것 — 16화 쪽 '③ 만든 영상 올리면…' 칸도 접혀
//    있었다. 파일을 고르는 칸이 접혀 있으면 손님은 아무것도 못 한다.
const FOLD_OPEN = ['다음에 할 일', '지금 상태', '90초 한 편', '③ 만든 영상'];
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
  //    [0. 자체 점검]·[6. 배포] 같은 0원짜리 자동 실행은 여기서 무시한다.
  const mine = (S.runs || []).filter(r => !r.conclusion
                 && WF.some(w => w.name === r.name));
  if (mine.length)
    return { title: esc(mine[0].name) + ' 이(가) 돌아가는 중입니다',
             body: '끝나면 아래 <b>최근 실행</b>에 결과가 뜹니다. 그냥 두셔도 됩니다.<br>'
                 + '<span style="color:#9599ab">멈추려면 [작업] 화면에서 그 작업의 '
                 + '[멈추기] 를 누르십시오.</span>' };

  // ⭐⭐ 2026-08-23 대개편 — 이 카드가 옛 길(EP001~003 롱폼)을 가리키고 있었다.
  //    운영자: "이것도 현행화 안 돼 있잖아. 현행화 시켜"
  //    지금 길은 **시리즈**다: 시리즈 대본(16화) → 회차마다 [영상 만들기]
  //    (그림 → Veo → 쇼츠) → 확인 → 유튜브. EP 갈래는 지웠다 — 특히
  //    '영상을 만들 차례' 단추는 NEXT_RUN 에 없는 produce 를 불러 눌러도
  //    아무 일이 안 나는 죽은 단추였다.
  const ser = Object.entries(S.series || {}).sort((a, b) => a[0].localeCompare(b[0]));
  const going = ser.find(([, v]) => (v.made || 0) < (v.episodes || 16));
  if (going) {
    const sid = going[0], v = going[1];
    const ep = (v.made || 0) + 1;
    // ⭐ 2026-08-23 — 컷은 **루미나에서** 만든다. 예전엔 이 자리가 Veo 영상
    //    만들기(약 4,200원)를 한 번 누르면 바로 돈이 나가는 단추였다.
    //    루미나로 전환한 지금 그 단추는 **돈 새는 문**이라 안내로 바꿨다.
    //    (Veo 길은 실행 목록의 [3. 영상 만들기]에 예비로 남아 있다)
    return { title: '「' + esc(v.title || sid) + '」 ' + ep + '화 컷을 루미나에서 만들 차례입니다',
             body: '만든 영상 <b>' + (v.made || 0) + '/' + (v.episodes || 16) + '화</b><br>'
                 + '① 아래에서 ' + ep + '화 <b>프롬프트를 복사</b>해 루미나에 붙입니다<br>'
                 + '② 컷 3개(D001_E01_C01~C03· 장소가 여럿이면 4개)를 받아 <b>압축해 올립니다</b><br>'
                 + '<span style="color:#9599ab">조립은 0원입니다. 영상은 루미나 '
                 + '크레딧으로만 만들어집니다.</span>',
             btn: ep + '화 대본·프롬프트 열기',
             act: 'seriesView(\\'' + sid + '\\',' + ep + ')' };
  }
  if (ser.length && !going)
    return { title: '시리즈 16화가 다 만들어졌습니다',
             body: '다음 시리즈를 시작할 차례입니다. 아래에서 새 소재로 '
                 + '<b>시리즈 대본</b>을 만드십시오.',
             btn: '시리즈 대본 만들기', act: 'goNext(\\'series\\')' };

  if (ready.length)
    return { title: '시리즈 대본을 만들 차례입니다',
             body: '쓸 만하다고 판정된 소재가 <b>' + ready.length + '건</b> 있습니다. '
                 + '가장 점수가 높은 것을 30초짜리 16화로 쪼갭니다.<br>'
                 + '<span style="color:#9599ab">글만 쓰므로 수백 원 · 약 10분.</span>',
             btn: '시리즈 대본 만들기', act: 'goNext(\\'series\\')' };

  if (ungated.length)
    return { title: '소재를 살펴볼 차례입니다',
             body: '아직 안 살펴본 기록이 <b>' + ungated.length + '건</b> 있습니다. '
                 + '10건을 점수 매겨 쓸 만한 것을 고릅니다.<br>'
                 + '<span style="color:#9599ab">약 4분 · 852원쯤 듭니다.</span>',
             btn: '소재 살펴보기', act: 'goNext(\\'gate\\')' };

  if (!(S.queue || []).length)
    return { title: '재판 기록부터 모아야 합니다',
             body: '아직 소재가 하나도 없습니다. 기록을 받아 오는 것부터 시작합니다.',
             btn: '재판 기록 모으기', act: 'goNext(\\'collect\\')' };

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
  // 판례 번호를 비우면 점수가 가장 높은 것으로 자동
  series:  { file: 'series.yml', name: '시리즈 대본 만들기', inputs: {} },
  gate:    { file: 'script.yml', name: '소재 살펴보기',
             inputs: { mode: '소재 심사만', gate_limit: '10',
                       budget: '1000' } },
  script:  { file: 'script.yml', name: '대본 만들기',
             inputs: { mode: '둘다', gate_limit: '10',
                       budget: '3000' } },
  // 회차를 안 보낸다 — 워크플로가 만들다 만 것을 알아서 찾는다
  resume:  { file: 'script.yml', name: '이어서 마저 만들기',
             inputs: { mode: '이어서 마저 만들기',
                       budget: '3000' } },
  // ⚠️ 2026-08-16 — 회차 칸이 고르는 칸(choice)이 되면서 빈 값('')은
  //    깃허브가 거절한다. 목록에 있는 '자동'을 그대로 보낸다
  //    (자동 = 발행 안 된 가장 이른 회차 — 차례대로 간다).
};

// 회차 번호가 그때그때 달라 NEXT_RUN 에 못 박는다 — 따로 받는다.
// 목소리·타입캐스트 열쇠는 서버(/api/run)가 알아서 얹는다.
async function goVideo(sid, ep) {
  return runNow('영상 만들기 (' + ep + '화)', 'video.yml',
                { sid: sid, ep: String(ep) });
}

async function goNext(key) {
  const w = NEXT_RUN[key];
  return runNow(w.name, w.file, w.inputs);
}

async function runNow(name, file, inputs) {
  toast(name + ' 시작하는 중…');
  let j = {};
  try {
    const r = await fetch('/api/run', { method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file: file, inputs: inputs }) });
    j = await r.json();
  } catch (e) { j = { ok: false, error: '연결이 끊겼습니다' }; }
  if (!j.ok) {
    showErr(name + ' — 실행이 시작되지 못했습니다',
            (j.error || '알 수 없는 이유') + (j.detail ? '  [깃허브 원문] ' + j.detail : ''));
    return;
  }
  toast(name + ' 시작했습니다. 이 화면이 저절로 갱신됩니다.', 6000);
  watch();
}

const row = (k, v) => '<div class="row"><span class="k">' + k + '</span><span class="v">' + v + '</span></div>';
const mini = (t, fn, cls) => '<button class="mini ' + (cls||'') + '" onclick="' + fn + '">' + t + '</button>';
const mb = (b) => (b >= 1048576 ? Math.round(b/1048576) + 'MB' : Math.round(b/1024) + 'KB');

// ── 만든 영상 모아 보기 ─────────────────────────────────
// ⭐⭐ 2026-08-22 운영자: "만든 영상은 어디서 볼 수 있는 건데?
//    왜 볼 수 있는 메뉴가 없는데? 그것도 만들어야지"
//    그때까지는 **회차 화면 안쪽에서, 방금 만든 것 하나**만 볼 수 있었다.
//    첫 화면에서 한 번에 들어가 전부 볼 수 있게 한다.
let SHORTS = [];
let SHOWN = -1;
// ⭐ 2026-08-23 — 같은 영상에 소리만 다르게 얹은 판을 골라 듣는다.
//    운영자가 어느 소리로 갈지 **귀로 정해야** 하는데, 예전엔 목록이
//    short.mp4 하나만 집어 와서 비교 자체가 불가능했다.
let PICK = 'short.mp4';
const PICK_LABEL = {
  'ko.mp4': '① 우리 한국어 목소리',
  'veo.mp4': '② 구글이 만든 소리',
  'short.mp4': '기본',
};

function madeCard() {
  return '<div class="card"><h2>만든 영상</h2>'
    + '<div style="color:#9599ab;font-size:13px;line-height:1.7;margin-bottom:10px">'
    + '완성된 쇼츠를 여기서 바로 보실 수 있습니다.<br>'
    + '마음에 들면 그 자리에서 유튜브에 올리실 수 있습니다.</div>'
    + '<div class="btns">' + mini('만든 영상 보기', 'madeList()', 'gold') + '</div></div>';
}

function madeName(x) {
  return (x.title ? x.title + ' ' : '') + x.ep + '화'
    + (x.cut ? ' (' + x.cut + '컷 시험본)' : '');
}

async function madeList() {
  VIEW = 'made';
  document.getElementById('app').innerHTML = '<div class="empty">만든 영상 찾는 중…</div>';
  let j = {};
  try {
    j = await (await fetch('/api/shorts?t=' + Date.now(), { cache: 'no-store' })).json();
  } catch (e) { j = {}; }
  SHORTS = j.items || [];
  SHOWN = -1;
  madeDraw();
  scrollTo(0, 0);
}

function madeDraw() {
  if (VIEW !== 'made') return;
  let h = '<button class="ghost" onclick="home()">← 처음으로</button>'
        + '<div style="height:12px"></div>';
  if (!SHORTS.length) {
    h += '<div class="card"><h2>만든 영상</h2><div class="empty">'
       + '아직 만든 영상이 없습니다.<br>'
       + '<b>시리즈 대본</b>에서 회차를 열고 루미나에서 받은 '
       + '<b>클립 압축파일</b>을 올리시면 여기에 쌓입니다.</div></div>';
    document.getElementById('app').innerHTML = h;
    return;
  }
  if (SHOWN >= 0 && SHORTS[SHOWN]) {
    const v = SHORTS[SHOWN];
    // playsinline 이 없으면 아이폰이 전체화면으로 낚아채 간다.
    h += '<div class="card"><h2>' + esc(madeName(v))
      + ((v.names || []).length > 2 ? ' — ' + esc(PICK_LABEL[PICK] || PICK) : '')
      + '</h2>'
      + '<video id="pl" controls playsinline preload="metadata" '
      + 'style="width:100%;max-height:70vh;border-radius:12px;background:#000;'
      + 'display:block" src="/api/short?sid=' + encodeURIComponent(v.sid)
      + '&ep=' + v.ep + (v.cut ? '&cut=' + v.cut : '')
      + '&name=' + encodeURIComponent(PICK) + '&play=1"></video>'
      + (((v.names || []).filter(function (n) { return n !== 'short.mp4'; }).length > 1)
         ? '<div style="color:#9599ab;font-size:13px;margin:10px 0 4px">'
           + '소리가 다른 판이 있습니다. 눌러서 바꿔 들어 보십시오 (영상은 똑같습니다).'
           + '</div><div class="btns">'
           + v.names.filter(function (n) { return n !== 'short.mp4'; })
               .map(function (n) {
                 return mini(PICK_LABEL[n] || n, 'pickAudio(\\'' + n + '\\')',
                             PICK === n ? 'gold' : '');
               }).join('')
           + '</div>'
         : '')
      + '<div style="color:#9599ab;font-size:13px;margin:10px 0 4px">'
      + esc(v.sid) + ' · ' + mb(v.size) + ' · '
      + esc(String(v.at || '').slice(0, 10)) + ' 만듦</div>'
      + '<div class="btns">'
      + mini('이 회차 열기 (유튜브에 올리기)',
             'seriesView(\\'' + v.sid + '\\',' + v.ep + ')', 'gold')
      + mini('영상 받기 (기기에 저장)', 'madeDl(' + SHOWN + ')')
      + '</div></div>';
  }
  h += '<div class="card"><h2>만든 영상 ' + SHORTS.length + '개</h2>';
  SHORTS.forEach((x, k) => {
    h += '<div class="row"><span class="k">' + esc(madeName(x))
      + '<br><small style="color:#9599ab">' + mb(x.size) + ' · '
      + esc(String(x.at || '').slice(0, 10)) + '</small></span>'
      + (k === SHOWN ? '<span class="pill go">보는 중</span>'
                     : mini('재생', 'madePlay(' + k + ')', 'gold'))
      + '</div>';
  });
  h += '</div>';
  document.getElementById('app').innerHTML = h;
}

function madePlay(k) {
  SHOWN = k;
  // 소리가 다른 판이 있으면 **우리 한국어 목소리**부터 들려드린다.
  const ns = (SHORTS[k] && SHORTS[k].names) || [];
  // ⚠️ 예전엔 ko.mp4 가 있으면 그걸 먼저 골랐다(두 판 비교 시절). 그 길이
  //    끝난 뒤에도 기본값이 안 바뀌어 **옛 파일이 재생됐다.**
  PICK = 'short.mp4';
  madeDraw(); scrollTo(0, 0);
}

// ⚠️⚠️ 2026-08-23 — 이 함수가 통째로 사라져 있었다. 단추는 그려지는데 눌러도
//    아무 일이 안 일어났다("클릭도 안되고 한가지 버전밖에 선택이 안되잖아").
//    화면만 봐서는 멀쩡해 보이는 고장이라, 아래 검사기가 **단추가 부르는 함수가
//    실제로 있는지**를 매번 대조한다.
function pickAudio(n) { PICK = n; madeDraw(); scrollTo(0, 0); }

function madeDl(k) {
  const v = SHORTS[k];
  if (!v) return;
  window.open('/api/short?sid=' + encodeURIComponent(v.sid) + '&ep=' + v.ep
              + (v.cut ? '&cut=' + v.cut : '') + '&play=1&dl=1', '_blank');
  toast('내려받기를 시작했습니다');
}

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
      + '영상을 만들면 여기에 함께 생깁니다.</div>';
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
  // ⚠️ 2026-08-23 — [다시 만들기] 단추를 뺐다. 부르는 함수(remakeThumb)가
  //    2026-08-18 에 지워졌는데 단추만 남아 눌러도 아무 일이 안 났다.
  //    새 방식에서 다시 붙일 때 함수와 **같이** 붙인다.
  //    (tools/onclick_check.mjs 가 이런 먹통 단추를 이제 매번 잡는다)
  h += '<div style="color:#9599ab;font-size:13px;margin-top:9px">'
    + '새 썸네일이 안 보이면 아래 <b>새로 불러오기</b>를 눌러 확인하십시오.</div>';
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

    // ⭐ 워크플로(깃허브 안)가 보관함에서 파일을 받아 가는 문.
    //    깃허브 러너에는 브라우저 로그인 쿠키가 없다. 대신 **관리자 비밀번호**를
    //    머리글로 받는다 — 그 값은 이미 깃허브 Secrets 에 있는 것이라
    //    손님이 새로 등록할 것이 없다.
    //    열쇠(key)는 아무도 못 맞히는 무작위 글자이고, 하루가 지나면 저절로
    //    사라진다. 로그인해서 들어온 사람도 볼 수 있게 둔다(미리보기용).
    if (url.pathname === '/api/version')
      return Response.json({ build: BUILD }, { headers: { 'Cache-Control': 'no-store' } });

    if (url.pathname === '/api/blob') {
      const kv = bin(env);
      if (!kv) return new Response('보관함이 없습니다', { status: 503 });
      const key = url.searchParams.get('key') || '';
      if (!/^[a-z]+\/[A-Za-z0-9._-]+$/.test(key))
        return new Response('열쇠가 이상합니다', { status: 400 });
      const pass = req.headers.get('x-vt-pass') || '';
      const passOk = env.ADMIN_PASSWORD ? pass === env.ADMIN_PASSWORD : true;
      if (!passOk && !ok)
        return new Response('unauthorized', { status: 401 });
      const head = await kv.get(key);
      if (!head)
        return new Response('없습니다 (하루가 지나 지워졌을 수 있습니다)', { status: 404 });
      let m = null;
      try { m = JSON.parse(head); } catch (e) { m = null; }
      if (!m) return new Response('보관함이 깨졌습니다', { status: 500 });
      let i = 0;
      const rs = new ReadableStream({
        async pull(c) {
          if (i >= m.parts) { c.close(); return; }
          const b = await kv.get(`${key}.${i}`, 'arrayBuffer');
          i += 1;
          if (b) c.enqueue(new Uint8Array(b));
          else c.error(new Error('조각이 없습니다'));
        },
      });
      return new Response(rs, { headers: {
        'Content-Type': m.type || 'application/octet-stream',
        'Cache-Control': 'no-store' } });
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
        // ⭐⭐ 2026-08-22 — '만든 영상 0/16' 이 영원히 0 이었다.
        //    state/series.json 의 made 를 **아무도 올리지 않는다.**
        //    영상을 만들어도 첫 화면은 계속 0 이라 손님이 "만든 게 어디 있냐"
        //    고 하시게 된다.
        //    → 숫자를 어딘가에 적어 두고 맞추려 들지 않는다. 그러면 언젠가
        //      또 어긋난다. **실제로 만들어져 있는 것을 세어** 쓴다.
        //      (완성본만 센다 — 한 컷 시험본은 작품이 아니다)
        const madeBy = {};
        (Array.isArray(rels) ? rels : []).forEach((r) => {
          const m = /^short-(S\d{3})-ep(\d{2})$/.exec(r.tag_name || '');
          if (m && (r.assets || []).some((a) => a.name === 'short.mp4'))
            (madeBy[m[1]] = madeBy[m[1]] || new Set()).add(m[2]);
        });
        const series2 = {};
        for (const [sid, v] of Object.entries(series || {}))
          series2[sid] = { ...v, made: (madeBy[sid] || new Set()).size };
        // 대본은 없는데 영상만 있는 경우도 숨기지 않는다
        for (const sid of Object.keys(madeBy))
          if (!series2[sid]) series2[sid] = { made: madeBy[sid].size, episodes: 16 };

        return Response.json({
          episodes: episodes || {},
          queue: Array.isArray(queue) ? queue : [],
          assets,
          videos,
          series: series2,
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
        // ⚠️ 쇼츠 만들기는 [실행] 카드 목록엔 없지만 상태는 물어볼 수 있어야 한다
        //    (2026-08-24 — 목소리 둘은 메뉴와 함께 없앴다)
        const EXTRA = ['shorts.yml'];
        if (!WORKFLOWS.some((w) => w.file === file) && !EXTRA.includes(file))
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
        return streamAsset(env, req, id);
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
      //    루미나에 붙여 넣는다.
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
        // ⭐ 2026-08-22 — 클립 하나로 시험하는 길. 운영자가 컷 하나만 만들어
        //    소리까지 제대로 입혔는지 보고 싶어 한다. 이때는 **딴 이름**으로
        //    둔다 — 시험 한 번에 5컷짜리 완성본이 덮이면 안 된다.
        const cut = cutOf(url);
        const suf = cut ? `-cut${cut}` : '';
        const tag = `clips-${sid}-ep${String(ep).padStart(2, '0')}${suf}`;
        const told = +(req.headers.get('content-length') || 0);
        if (told > KV_MAX)
          return Response.json({ ok: false, error:
            '파일이 90MB 를 넘습니다. 클립을 나눠 올리거나 화질을 낮춰 주십시오.' },
            { status: 400 });

        // ⭐⭐ 새 길 (2026-08-22) — 깃허브에 직접 올리지 않는다.
        //    보관함에 두고 **주소만** 워크플로에 넘긴다. 만드는 것도 릴리스에
        //    올리는 것도 예전처럼 깃허브 안에서 워크플로가 한다.
        if (bin(env) && req.body) {
          try {
            const key = `clips/${tag}-${crypto.randomUUID()}`;
            const size = await blobPutStream(env, req.body, key, KV_DAY);
            if (!size)
              return Response.json({ ok: false, error: '파일이 비었습니다' }, { status: 400 });
            const inputs = { sid, ep, blob: blobUrl(req, key) };
            if (cut) inputs.cut = cut;
            await gh(env, `/repos/${REPO}/actions/workflows/shorts.yml/dispatches`, {
              method: 'POST', body: JSON.stringify({ ref: BRANCH, inputs }),
            });
            return Response.json({ ok: true, tag, size, via: 'blob' });
          } catch (e) {
            const m = String(e && e.message ? e.message : e);
            if (m.includes('TOO_BIG'))
              return Response.json({ ok: false, error:
                '파일이 90MB 를 넘습니다. 클립을 나눠 올리거나 화질을 낮춰 주십시오.' },
                { status: 400 });
            return Response.json({ ok: false, error: '올리지 못했습니다',
              detail: m.slice(0, 220) + ` [판 ${BUILD}]` }, { status: 502 });
          }
        }

        // ⚠️⚠️⚠️ 여기 있던 '옛 길'(브라우저 → 깃허브 릴리스 직접 올리기)을
        //    **통째로 지웠다.** 2026-08-22, 운영자가 같은 403 을 또 봤다:
        //      GitHub 403 … documentation_url: releases#create-a-release
        //    남겨 두면 언젠가 또 그리로 새어 나간다. 길이 없으면 샐 수도 없다.
        //    ⭐ 애초에 이 길은 예전에 없던 길이다 — 영상은 늘 깃허브 안에서
        //       워크플로가 만들고 워크플로가 올렸다. 내가 새로 낸 길이 사고였다.
        return Response.json({ ok: false, error: '영상 보관함이 아직 없습니다',
          detail: '[영상 보관함 준비하기] 를 한 번 누르시면 1~2분 뒤 올릴 수 있습니다. '
                + '깃허브에서 하실 것은 없습니다.',
          fix: 'setup-blob' }, { status: 503 });
      }

      // ⭐ 90초 편 대본 — 컷마다 붙여 넣을 영상 프롬프트가 들어 있다
      if (url.pathname === '/api/short90') {
        const doc = await getJson(env, 'data/series/S90.json');
        return Response.json({ doc });
      }

      // ⭐⭐⭐ 2026-08-27 손님: "이미지는 중간중간 섞여 있고 동영상도 있어야 돼."
      //    맞다. 전부 그림이면 슬라이드쇼다. 컷마다 만든 영상을 여기서 받는다.
      //    올린 컷만 영상이 되고 나머지는 그림으로 간다.
      if (url.pathname === '/api/upload-cut' && req.method === 'POST') {
        const n = parseInt(url.searchParams.get('n') || '0', 10) || 0;
        if (n < 1 || n > 99)
          return Response.json({ ok: false, error: '컷 번호가 이상합니다' },
                               { status: 400 });
        if (!bin(env) || !req.body)
          return Response.json({ ok: false, error: '보관함이 아직 없습니다',
            detail: '[영상 보관함 준비하기] 를 한 번 누르시고 1~2분 뒤에 다시 '
                  + '올려 주십시오.', fix: 'setup-blob' }, { status: 503 });
        if (+(req.headers.get('content-length') || 0) > KV_MAX)
          return Response.json({ ok: false, error: '파일이 90MB 를 넘습니다' },
                               { status: 400 });
        try {
          const key = `clips/S90-c${n}-${crypto.randomUUID()}`;
          const size = await blobPutStream(env, req.body, key, KV_DAY);
          if (!size)
            return Response.json({ ok: false, error: '파일이 비었습니다' }, { status: 400 });
          return Response.json({ ok: true, url: blobUrl(req, key), size });
        } catch (e) {
          const m = String(e && e.message ? e.message : e);
          if (m.includes('TOO_BIG'))
            return Response.json({ ok: false, error: '파일이 90MB 를 넘습니다' },
                                 { status: 400 });
          return Response.json({ ok: false, error: '올리지 못했습니다',
            detail: m.slice(0, 220) + ` [판 ${BUILD}]` }, { status: 502 });
        }
      }

      // ⭐⭐⭐ 2026-08-27 손님이 제미나이에서 인물 그림을 직접 만들어 오셨다.
      //    한 장씩 받아 보관함에 두고 **주소만** 워크플로에 넘긴다
      //    (압축파일 올리기와 같은 길 — 깃허브에 직접 올리지 않는다).
      if (url.pathname === '/api/upload-card' && req.method === 'POST') {
        const who = url.searchParams.get('who') || '';
        if (S90_CARDS.indexOf(who) < 0)
          return Response.json({ ok: false, error: '누구 그림인지 알 수 없습니다' },
                               { status: 400 });
        if (!bin(env) || !req.body)
          return Response.json({ ok: false, error: '보관함이 아직 없습니다',
            detail: '[영상 보관함 준비하기] 를 한 번 누르시고 1~2분 뒤에 다시 '
                  + '올려 주십시오.', fix: 'setup-blob' }, { status: 503 });
        if (+(req.headers.get('content-length') || 0) > KV_MAX)
          return Response.json({ ok: false, error: '파일이 90MB 를 넘습니다' },
                               { status: 400 });
        try {
          const key = `cards/S90-${who}-${crypto.randomUUID()}`;
          const size = await blobPutStream(env, req.body, key, KV_DAY);
          if (!size)
            return Response.json({ ok: false, error: '파일이 비었습니다' }, { status: 400 });
          return Response.json({ ok: true, url: blobUrl(req, key), size });
        } catch (e) {
          const m = String(e && e.message ? e.message : e);
          return Response.json({ ok: false, error: '올리지 못했습니다',
            detail: m.slice(0, 220) + ` [판 ${BUILD}]` }, { status: 502 });
        }
      }

      // 올린 얼굴로 90초 한 편을 만들라고 시킨다
      if (url.pathname === '/api/make-short90' && req.method === 'POST') {
        let body = {};
        try { body = await req.json(); } catch (e) { body = {}; }
        const cards = {};
        for (const k of S90_CARDS) {
          const v = body && body.cards ? body.cards[k] : '';
          if (typeof v === 'string' && v.startsWith('http')) cards[k] = v;
        }
        // 컷마다 올린 영상 (없으면 그 컷은 그림으로 간다)
        const clips = {};
        const sent = (body && body.clips) || {};
        for (const k of Object.keys(sent)) {
          const num = parseInt(k, 10);
          const v = sent[k];
          if (num >= 1 && num <= 99 && typeof v === 'string' && v.startsWith('http'))
            clips[String(num)] = v;
        }
        // ⚠️ 넘기는 값은 **이 칸 안에서 만든 것**만 쓴다. 글자를 바로 적으면
        //    check_scope 가 "이 칸에 없는 것" 으로 잡는다 (일부러 그렇게 좁게
        //    본다 — 다른 칸 것을 잘못 넘기던 사고가 있었다).
        const step = 'all';
        const payload = JSON.stringify(cards);
        const shots = JSON.stringify(clips);
        try {
          await gh(env, `/repos/${REPO}/actions/workflows/short90.yml/dispatches`, {
            method: 'POST', body: JSON.stringify({ ref: BRANCH,
              inputs: { step: step, cards: payload, clips: shots } }),
          });
          return Response.json({ ok: true, n: Object.keys(cards).length,
                                 clips: Object.keys(clips).length });
        } catch (e) {
          const m = String(e && e.message ? e.message : e);
          return Response.json({ ok: false, error: '시작하지 못했습니다',
            detail: m.slice(0, 220) }, { status: 502 });
        }
      }

      // ⭐⭐ 2026-08-22 운영자: "미리보기도 없고, 제목·해시태그도 없고,
      //    업로드 버튼도 없어."
      //    셋 다 만들어져 있었다. 다만 **영상이 다 된 뒤에만** 화면에 붙게
      //    되어 있어서, 만들기가 실패하면 화면이 그냥 조용했다.
      //    (실제로 shorts.yml 은 한 번도 돈 적이 없었다)
      //    → 만들기가 어떻게 됐는지 화면이 말할 수 있게 한다.
      // ⭐⭐ 2026-08-22 — 압축파일 올리기가 이렇게 실패했다:
      //    GitHub 403: "Resource not accessible by personal access token"
      //    토큰이 **Contents = Read** 로만 만들어져 있어서 릴리스를 못 만든다
      //    (배포 안내에 그렇게 적혀 있다 — 처음부터 어긋난 설계였다).
      //    ⚠️ 권한은 코드로 못 만든다. 대신 **미리 알아보고 미리 알려 준다** —
      //       몇십 MB 를 다 올린 뒤에 영어 오류를 보는 일이 없게.
      if (url.pathname === '/api/can-write') {
        // ⭐⭐ 2026-08-22 — 이제 영상은 깃허브가 아니라 보관함으로 올라간다.
        //    보관함이 붙어 있으면 깃허브 쓰기 권한은 **아예 필요 없다.**
        //    (예전에 되던 길이 원래 이랬다 — 만들고 올리는 것은 깃허브 안에서
        //     워크플로가 자기 열쇠로 한다. 관리자 페이지는 부르기만 한다.)
        if (bin(env)) return Response.json({ ok: true, via: 'blob' });
        try {
          const r = await gh(env, `/repos/${REPO}`);
          const ok = !!(r.permissions && r.permissions.push);
          return Response.json({ ok, who: r.full_name || '' });
        } catch (e) {
          return Response.json({ ok: false,
            why: String(e && e.message ? e.message : e).slice(0, 200) });
        }
      }

      // ⭐ 보관함이 아직 없을 때, 화면에서 바로 준비시킨다.
      //    손님을 깃허브로 보내지 않기 위한 문이다 (그러지 말라고 하셨다).
      //    관리자 페이지 배포를 다시 돌리면 보관함이 만들어져 붙는다.
      if (url.pathname === '/api/setup-blob' && req.method === 'POST') {
        try {
          await gh(env, `/repos/${REPO}/actions/workflows/deploy-admin.yml/dispatches`, {
            method: 'POST', body: JSON.stringify({ ref: BRANCH }),
          });
          return Response.json({ ok: true });
        } catch (e) {
          return Response.json({ ok: false, error: '준비를 시작하지 못했습니다',
            detail: String(e && e.message ? e.message : e).slice(0, 220) }, { status: 502 });
        }
      }

      if (url.pathname === '/api/build-status') {
        try {
          const r = await gh(env,
            `/repos/${REPO}/actions/workflows/shorts.yml/runs?per_page=1`);
          const run = (r.workflow_runs || [])[0];
          if (!run) return Response.json({ ever: false });
          return Response.json({ ever: true, status: run.status,
            conclusion: run.conclusion, at: run.created_at,
            url: run.html_url });
        } catch (e) {
          return Response.json({ ever: false,
            why: String(e && e.message ? e.message : e).slice(0, 200) });
        }
      }

      // 만들어진 쇼츠를 화면에서 바로 본다 (릴리스에서 그대로 흘려보낸다)
      // ⭐⭐ 2026-08-22 운영자: "만든 영상은 어디서 볼 수 있는 건데?
      //    왜 볼 수 있는 메뉴가 없는데? 그것도 만들어야지"
      //    맞다. 완성된 쇼츠를 보는 곳이 **회차 화면 안쪽에만** 있었다.
      //    그것도 방금 만든 것 하나뿐이었다. 만든 것을 모아 보는 곳을 만든다.
      if (url.pathname === '/api/shorts') {
        let rels = [];
        try { rels = await gh(env, `/repos/${REPO}/releases?per_page=100`); }
        catch (e) { rels = []; }
        const items = [];
        for (const r of rels || []) {
          const m = String(r.tag_name || '').match(/^short-(S\d{3})-ep(\d{2})(?:-cut(\d+))?$/);
          if (!m) continue;
          const a = (r.assets || []).find((x) => x.name === 'short.mp4');
          if (!a) continue;
          // ⭐ 2026-08-23 — 같은 영상에 소리만 다르게 얹은 판이 여럿 있을 수 있다.
          //    예전엔 short.mp4 하나만 집어 와서 **비교를 할 수가 없었다.**
          const names = PLAYABLE.filter((n) =>
            (r.assets || []).some((x) => x.name === n));
          items.push({ sid: m[1], ep: +m[2], cut: m[3] ? +m[3] : 0,
                       size: a.size, names,
                       at: a.updated_at || r.published_at || '' });
        }
        // 새로 만든 것이 위로
        items.sort((x, y) => String(y.at).localeCompare(String(x.at)));
        // 시리즈 제목을 붙여 준다 — 'S001 3화' 보다 '바람난 남편이…' 가 낫다
        const ser = (await getJson(env, 'state/series.json')) || {};
        for (const it of items) {
          const v = ser[it.sid];
          it.title = (v && (v.title || v.name)) || '';
        }
        return Response.json({ items });
      }

      if (url.pathname === '/api/short') {
        const sid = url.searchParams.get('sid') || '';
        const ep = String(parseInt(url.searchParams.get('ep') || '0', 10) || 0);
        if (!/^S\d{3}$/.test(sid)) return new Response('bad', { status: 400 });
        const cut = cutOf(url);
        const tag = `short-${sid}-ep${String(ep).padStart(2, '0')}`
                  + (cut ? `-cut${cut}` : '');
        let rel = null;
        try { rel = await gh(env, `/repos/${REPO}/releases/tags/${tag}`); } catch { rel = null; }
        // 아무 이름이나 받지 않는다 — 미리 정해 둔 것만.
        const want = PLAYABLE.includes(url.searchParams.get('name') || '')
          ? url.searchParams.get('name') : 'short.mp4';
        const a = (rel && (rel.assets || []).find((x) => x.name === want)) || null;
        if (!a) return Response.json({ ready: false });
        if (url.searchParams.get('play') !== '1')
          return Response.json({ ready: true, size: a.size, at: a.updated_at });
        // ⚠️ 예전엔 여기서 통째로 내려보냈다 → 아이폰이 재생을 못 했다.
        // ⭐ 2026-08-23 — dl=1 이면 재생이 아니라 **내려받기**로 준다.
        //    파일 이름은 영문으로 (한글 이름은 올리기에서 한 번 죽었다).
        const dl = url.searchParams.get('dl') === '1'
          ? `${sid}_ep${String(ep).padStart(2, '0')}${cut ? '_cut' + cut : ''}`
            + `${want === 'short.mp4' ? '' : '_' + want.replace('.mp4', '')}.mp4`
          : null;
        return streamAsset(env, req, a.id, dl);
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
        // 손님이 고쳐 둔 것이 있으면 그것을 먼저 — 보관함(새 길)을 먼저 본다
        const kept = await blobText(env, `meta/${tag}`);
        if (kept) {
          try { return Response.json({ ...JSON.parse(kept), saved: true }); }
          catch (e) { /* 깨졌으면 아래에서 다시 만든다 */ }
        }
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
        // ⭐ 2026-08-22 — 여기도 깃허브에 쓰던 자리였다(403 의 두 번째 원인).
        //    보관함에 담고, 올릴 때 워크플로가 그 주소에서 받아 가게 한다.
        if (bin(env)) {
          try {
            await blobPutText(env, `meta/${tag}`, JSON.stringify(meta, null, 1), KV_DAY * 90);
            return Response.json({ ok: true, via: 'blob' });
          } catch (e) { /* 아래 옛 길로 */ }
        }
        // ⚠️ 여기 있던 깃허브 직접 쓰기도 지웠다 (같은 403 을 낼 두 번째 자리)
        return Response.json({ ok: false, error: '영상 보관함이 아직 없습니다',
          detail: '[영상 보관함 준비하기] 를 한 번 누르시면 1~2분 뒤 저장됩니다.',
          fix: 'setup-blob' }, { status: 503 });
      }

      if (url.pathname === '/api/yt-up' && req.method === 'POST') {
        const { sid, ep, privacy, dry } = await req.json();
        if (!/^S\d{3}$/.test(sid || ''))
          return Response.json({ ok: false, error: '회차가 이상합니다' }, { status: 400 });
        const P = { public: '전체 공개', unlisted: '일부 공개 (링크 있는 사람만)',
                    private: '비공개 (나만 보기)' }[privacy || 'private'];
        const mtag = `short-${sid}-ep${String(ep).padStart(2, '0')}`;
        try {
          const inputs = { sid, ep: String(ep), privacy: P,
            mode: dry ? '연습 (올리지 않고 확인만)' : '진짜로 올리기' };
          // 화면에서 확인한 글이 보관함에 있으면 그 주소를 넘긴다 —
          // 보여드린 것과 올라가는 것이 반드시 같아야 한다.
          // (그래서 더더욱 새 이름으로 복사해 넘긴다 — 위 함정 설명 참고)
          const murl = await blobPin(env, req, `meta/${mtag}`, 'meta');
          if (murl) inputs.meta = murl;
          await gh(env, `/repos/${REPO}/actions/workflows/shorts-upload.yml/dispatches`, {
            method: 'POST', body: JSON.stringify({ ref: BRANCH, inputs }),
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
