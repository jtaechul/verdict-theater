#!/usr/bin/env python3
"""⭐ 시리즈 대본 — 판례 1건을 30초짜리 16화로 쪼갠다 (구글 영상 제작용).

    python3 src/series.py                 다음 소재로 시리즈 하나
    python3 src/series.py --case 230761   그 판례로
    python3 src/series.py --check S001    이미 만든 것만 다시 검사 (0원)

왜 (2026-08-18 대개편)
    영상을 구글(옴니 플래시)이 만든다. 하루 무료 크레딧 50개 = 6초 클립 5개 =
    30초. 그래서 한 회차를 12분짜리로 쓰던 옛 방식은 통째로 버리고,
    **판례 하나를 30초 × 16화**로 쪼갠다. 매일 한 편 내고, 16일이면 8분짜리
    롱폼이 공짜로 나온다(이미 만든 클립을 잇기만 하면 되므로).

지키는 것 (운영자 지시)
    ① 매 화 첫 컷은 후킹 — 설명으로 시작하는 화는 반려
    ② 영상 안에 글자가 한 자도 나오면 안 된다 — 글자가 나올 물건을 안 부른다
    ③ 자막·채널명은 우리 프로그램이 나중에 얹는다 (subtitle 칸에 따로 적는다)

값
    글만 쓴다 — 회차(16화 전부)당 수백 원. 영상값은 여기서 한 푼도 안 나간다.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import prompts                                              # noqa: E402
from claude import writer                                   # noqa: E402

SERIES_DIR = ROOT / "data" / "series"
CASES = ROOT / "data" / "cases"
QUEUE = ROOT / "state" / "queue.json"
STATE = ROOT / "state" / "series.json"

EPISODES = 16          # 16화 × 30초 = 8분 (롱폼 한 편)
CUTS = 5               # 한 화 5컷
SEC = 6                # 컷 하나 6초 (플로우 무료 하루 50크레딧 = 45크레딧)
ROLES = ["후킹", "상황", "맞섬", "뒤집기", "끊기"]

# ⚠️ 2026-08-19 첫 실행에서 20군데가 걸렸는데 **15군데가 이 한 줄** 때문이었다.
#    지난 줄거리를 18자로 정해 뒀는데, 한국어로 지난 화를 요약하기엔 너무 짧다.
#    실물로 재보지 않고 숫자를 적은 내 잘못이다(시트 검사 오판 265원과 같은 실수).
#    화면 아래 한 줄 자막으로 읽히는 길이는 30자까지가 무난하다.
RECAP_MAX = 30

# ⚠️ 2026-08-20 — 대사 18자도 recap 18자와 **똑같이 재보지 않고 적은 숫자**였다.
#    실제 드라마 한 줄을 재보니 "재판장님, 저는 그 돈을 만진 적이 없습니다." = 24자,
#    말하면 약 3.5초다. 6초 클립에 넉넉히 들어간다. 18자는 한국어 한 문장을
#    끝맺지도 못하는 길이라 억지 대사가 나온다.
# ⚠️ 2026-08-20 (두 번째) — 한 줄 24자 제한이 **한 글자 차이로** 멀쩡한 대사
#    둘을 막았다 ("악의적 증여는 시효 상관없이 다 토해내야 해." 25자 ≈ 5초).
#    총합 28자 제한이 이미 같은 일을 하고 있었다 — 혼자 말하면 28자를 다 쓰면
#    되고, 둘이 나누면 한쪽이 24자를 쓰는 순간 상대는 4자밖에 못 써서 총합에서
#    걸린다. 겹치는 제한을 하나 더 두어 돈만 날렸다. 총합 하나로 통일한다.
#    (recap 18자 · 대사 18자 · paper · phone 에 이어 **다섯 번째** 같은 실수다.
#     숫자를 정할 때는 반드시 실물을 먼저 잰다.)

# ⚠️ 2026-08-20 손님: "뭔 대사가 저렇게 짧아.. 무슨 한 컷에 대사를 한 명만 치면
#    스토리 전개가 전혀 안 되지 않아?"  — 재봤더니 둘 다 맞았다.
#      · 80컷 **전부** 말하는 사람이 1명 (주고받는 대화가 한 번도 없다)
#      · 대사 평균 13.9자 (6초에 28~33자가 들어가는데 절반도 안 썼다)
#    원인은 모델이 아니라 내 규격이었다 — 프롬프트에 '대사 한 줄', '말하는
#    사람'(단수) 이라고 못 박아 두었다.
#    한국어는 초당 약 5자. 6초 클립에서 앞뒤 숨 쉴 틈을 빼면 약 5.5초를 말하니
#    **한 컷에 28자**까지 들어간다. 두 사람이면 각 14자씩 — 실제 드라마 한
#    합이 딱 그 길이다("이 집, 이제 저희 겁니다." 14자).
# ⚠️ 2026-08-20 (세 번째) 손님: "대사가 너무 적어. 말도 어색해. 구어체가
#    아닌 것 같고 실제 같지 않아."  — 재봤더니 또 맞았다.
#      · 대사 112줄 / 80컷 = 컷당 1.4줄 (거의 한 마디씩만 하고 끝난다)
#      · 대사 20줄(18%)에 법률·서류 용어가 들어 있다
#        ("대법원 판례상 사망보험금은 내 거야." — 싸우면서 이렇게 말하는 사람은 없다)
#    까닭: 사실을 전할 통로가 대사밖에 없어서 입에 다 밀어 넣었다.
#    그래서 ① 주고받는 횟수를 늘리고 ② 사실은 '설명 자막(caption)' 이 지게 한다.
# ⚠️ 여기서 **재는 단위 자체가 틀렸다**는 것을 찾았다.
#    나는 '글자 수'로 재고 있었는데, 공백·쉼표·물음표는 **소리가 나지 않는다.**
#      "여기가 어디라고 뻔뻔하게 와?"  = 16자지만 실제 소리는 12음절
#    실제 대본 112줄을 재보니 글자 수가 소리보다 1.44배 많았다.
#    그래서 28자로 막았던 것은 실제로는 19음절 = 약 3.5초뿐 — 6초 클립이
#    늘 반쯤 비어 있었다. 손님이 "대사가 너무 적어" 라고 한 것이 이것이다.
#    이제 **음절로 센다.** 한국어 드라마 대사는 초당 5~6음절이고, 6초 중
#    5.5초를 말하니 약 30음절이 들어간다.
def syl(t):
    """실제로 소리 나는 것만 센다 — 공백·쉼표·물음표는 시간을 안 잡아먹는다."""
    return len(re.findall(r"[가-힣]", t or ""))


# ⚠️ 최소치를 12로 뒀더니 **모델이 바닥에 붙어서 썼다** — 80컷 중 30컷이
#    12~15음절(2.2~2.7초)에 몰렸고 평균이 6초의 56%에 그쳤다. 특히 혼자
#    말하는 컷이 짧았다(주고받는 컷은 이미 24~25음절을 쓰고 있었다).
#    바닥이 곧 목표가 되므로, 바닥을 20음절(3.6초 · 6초의 60%)로 올린다.
# ⚠️ 2026-08-20 (네 번째) 손님: "실제 사람은 말을 좀 더 빨리 하잖아."
#    맞다. 실제 대본에 나온 대사를 말다툼 속도로 재보니 —
#      "여기가 어디라고 와. 당장 안 나가?"   13음절 / 1.9초 = 초당 6.8
#      "매일 같이 살았으면서 그걸 모른다고?" 15음절 / 2.2초 = 초당 6.8
#      "돈 다 빼돌리고 나한테 이딴 빚만…"    18음절 / 3.0초 = 초당 6.0
#    평균 **초당 6.4음절**. 내가 잡았던 5.5는 느렸고, 그래서 상한 30음절이
#    실제로는 4.7초 — 6초 중 1.3초가 남았다. 6.4로 다시 잡는다.
SYL_PER_SEC = 6.4      # 실측 (말다툼 속도). 화면 문구도 전부 이 값을 쓴다
SPEAK_SEC = SEC - 0.4  # 6초 중 앞뒤 0.4초를 빼고 말한다

# ⭐ 숫자를 손으로 적지 않고 **위 실측값에서 계산한다.**
#    이번에만 recap 18 · 대사 18 · 28자 · 24자 · 33자 · 20음절을 눈대중으로
#    적었다가 여섯 번 고쳤다. 계산해서 나오게 하면 속도만 다시 재면 된다.
DIA_SYL_MAX = int(SPEAK_SEC * SYL_PER_SEC)      # 5.6초 × 6.4 = 35음절
# ⚠️ "바닥은 빈 컷만 막고, 길이는 목표치가 끌어올린다" 고 했는데 **틀렸다.**
#    목표를 30~34 로 적어 뒀는데 80컷 중 30음절을 넘긴 것은 **1컷뿐**이었고
#    53컷이 24~27에 몰렸다(평균 25.2). 모델에게 목표는 권고일 뿐이고 실제로
#    강제되는 것은 바닥뿐이다 — 이번에 바닥을 올릴 때마다 평균이 따라
#    올라간 것도 같은 까닭이다(12→16→20 일 때 15.5→18.4→22.1).
#    그러니 **바닥을 목표 바로 아래에 둔다.**
# ⚠️ 28 로 올렸더니 80컷 중 41컷이 걸렸다. 나눠 보니 원인이 한쪽에 있었다 —
#      혼자 말하는 컷 47개: 평균 28.7음절 (4.5초) — 이미 충분하다
#      주고받는 컷   33개: 평균 26.5음절, **전부 두 번만** 주고받는다
#    길이가 모자란 것이 아니라 **주고받는 횟수가 모자랐다.** 두 번을 세 번으로
#    (A→B→A) 늘리면 한 번에 10~12음절씩 30~35가 된다. 그건 프롬프트가 할 일이고,
#    바닥은 다시 '거의 빈 컷'만 막는 자리로 돌려놓는다(반씩 걸러 내면 돈만 나간다).
DIA_SYL_MIN = int(3.6 * SYL_PER_SEC)            # 3.6초어치 = 23음절
TALKERS_MAX = 3        # 한 컷에 말을 주고받는 횟수 ("뭐?" "들었잖아." "야!")
TALK_MIN = 2           # 한 화 5컷 중 **주고받는 컷**이 최소 몇 컷이어야 하는가
SUB_MAX = 60           # 자막은 주고받은 대사를 다 담아야 한다 (' / ' 로 나눈다)

# 프롬프트 6줄 규격 — 이 순서, 이 이름이 아니면 반려한다
LINES = ["SHOT:", "SUBJECT:", "ACTION:", "DIALOGUE:", "SETTING:", "STYLE:", "Avoid:"]
STYLE_FIX = ("STYLE: Korean TV drama realism, muted desaturated palette, soft "
             "practical lighting, 35mm lens look, shallow depth of field, "
             "natural skin texture, no stylization.")

# ⚠️ 영상에 글자가 나오는 가장 큰 원인은 '글자가 있는 물건'을 부른 것이다.
#    그런데 **두 번 연속으로 지나치게 넓은 낱말이 멀쩡한 대본을 막았다.**
#      1차 'phone'  — 전화기에는 글자가 없다. 전화 받는 장면이 모두 막혔다.
#      2차 'paper' — 종이 한 장에도 글자는 없다. 6화 1컷이 이것 하나로 반려됐다.
#    반려는 돈을 다시 쓰게 만들고, 글자가 조금 새는 것은 delogo 로 지우면 된다.
#    손해가 훨씬 큰 쪽으로 기울인다 — **그 자체가 글자인 것**만 무조건 막는다.
TEXT_HARD = ["signage", "banner", "billboard", "poster", "newspaper", "magazine",
             "headline", "subtitle", "caption", "nameplate", "plaque",
             "certificate", "whiteboard", "blackboard", "receipt", "text"]

# 글자가 나올 수도 있는 물건 — '읽는다 / 쓰여 있다' 와 같이 나올 때만 막는다.
#    봉투를 건네는 것은 되고, 봉투를 읽는 것은 안 된다.
TEXT_SOFT = ["paper", "document", "letter", "book", "screen", "monitor",
             "contract", "label", "file", "folder", "envelope", "sign"]

# 위 물건을 '글자가 보이게' 만드는 말
READING = ["read", "reads", "reading", "written", "writing", "printed", "print",
           "legible", "handwriting", "inscription", "title", "words", "letters",
           "signature"]


def word(w, s):
    return re.search(rf"\b{w}s?\b", s) is not None


def text_bait(head):
    """글자가 나올 물건을 불렀는가."""
    hit = [w for w in TEXT_HARD if word(w, head)]
    if any(word(r, head) for r in READING):
        hit += [w for w in TEXT_SOFT if word(w, head)]
    return hit


def load(p, dflt):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return dflt


def next_id(state):
    n = 1 + max((int(k[1:]) for k in state if re.fullmatch(r"S\d+", k)), default=0)
    return f"S{n:03d}"


def pick_case(queue, state):
    """아직 시리즈로 안 만든 것 중 점수가 가장 높은 판례."""
    used = {v.get("case_id") for v in state.values()}
    ready = [c for c in queue if c.get("gate_pass") and c["case_id"] not in used]
    ready.sort(key=lambda c: (c.get("gate_score") or 0, c.get("machine_score") or 0),
               reverse=True)
    return ready[0] if ready else None


def case_json(row):
    """판결문 본문 + 게이트가 찾아 둔 힌트를 프롬프트에 넣을 꼴로."""
    body = load(CASES / f"{row['case_id']}.json", {})
    keep = ["사건명", "선고일자", "사건종류명", "판시사항", "판결요지", "판례내용"]
    d = {k: body.get(k, "") for k in keep}
    if len(d["판례내용"]) > 60000:
        d["판례내용"] = d["판례내용"][:60000] + "\n\n…(이하 생략)"
    d["_한줄요약"] = row.get("one_line", "")
    d["_반전"] = row.get("twist_hint", "")
    d["_사건유형"] = row.get("case_type", "")
    return json.dumps(d, ensure_ascii=False, indent=2)


# ⚠️ 'extra people in focus' 는 **두 번째 주인공까지 막는 말**로 읽힌다.
#    주고받는 대화를 하려면 두 사람이 같이 화면에 있어야 한다. 막고 싶은 것은
#    지나가는 행인이지 상대역이 아니므로 'background extras' 로 못 박는다.
AVOID_FIX = ("Avoid: on-screen text, signage, documents with visible writing, "
             "screens, background extras in focus.")


def normalize(doc):
    """고쳐 쓸 수 있는 것은 **버리지 말고 우리가 고친다.**

    ⚠️ 2026-08-19 — STYLE 줄 한 글자가 다르다고 16화 전체를 버리고 다시 사게
       돼 있었다. 그 줄은 어차피 **모든 컷에서 똑같아야 하는 고정 문구**라
       모델에게 받을 이유가 없다. 여기서 갈아 끼운다.
       (내용에 관한 것 — 후킹·글자 나올 물건·대사 길이 — 은 고치지 않는다.
        그건 이야기를 바꾸는 일이라 사람이 판단할 몫이다.)"""
    n = 0
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
            lines = (c.get("prompt") or "").split("\n")
            out = []
            for l in lines:
                if l.startswith("STYLE:") and l != STYLE_FIX:
                    l, n = STYLE_FIX, n + 1
                elif l.startswith("Avoid:") and l != AVOID_FIX:
                    l, n = AVOID_FIX, n + 1
                out.append(l)
            # 대사 없는 컷에 DIALOGUE 줄을 통째로 빠뜨리는 일이 있다.
            # 빈 값이 'None.' 으로 정해져 있으므로 우리가 끼워 넣는다
            # (이야기를 바꾸는 게 아니라 빈칸을 채우는 것뿐이다).
            if not any(l.startswith("DIALOGUE:") for l in out):
                at = next((i for i, l in enumerate(out)
                           if l.startswith("SETTING:")), len(out))
                out.insert(at, "DIALOGUE: None.")
                n += 1
            # 아예 빠뜨린 경우에도 우리가 붙인다 — 고정 문구라 받을 이유가 없다
            if not any(l.startswith("STYLE:") for l in out):
                out.append(STYLE_FIX)
                n += 1
            # Avoid 는 **맨 끝**이어야 한다. 순서만 바뀐 것으로 16화를 다시 살 수 없다.
            out = [l for l in out if not l.startswith("Avoid:")]
            out.append(AVOID_FIX)
            c["prompt"] = "\n".join(out)
    if n:
        print(f"  (고정 문구 {n}줄을 우리가 채워 넣었다 — 이것 때문에 버리지 않는다)")
    return doc


# 사람이 입으로 하지 않는 '딱지'. 판결문·기사에나 쓰는 제3자 호칭이라
# 대사에 들어가면 즉시 어색해진다 ("내연녀 집에서 떨어져 죽었다고요?").
# ⚠️ 이것 때문에 16화를 버리지는 않는다 — 한 줄만 손보면 되는 일이다.
#    반려가 아니라 **손볼 곳**으로 알려 준다.
SPOKEN_BAN = ["내연녀", "내연남", "상간녀", "상간남", "피상속인"]

# ⭐ 2026-08-20 — 첫 실제 영상에서 **여자 손가락이 남자 옷 속으로 녹아들었다.**
#    영상 만드는 쪽이 두 사람이 닿는 자리를 아직 제대로 못 그린다.
#    닿는 동작을 안 부르면 그 오류가 아예 안 생긴다.
#    ⚠️ 반려까지 하지는 않는다 — 이야기를 바꾸는 일이라 사람이 볼 몫이고,
#       무엇보다 이런 것으로 16화를 다시 사면 안 된다. **손볼 곳**으로 알린다.
TOUCH = ["grab", "grabs", "grabbing", "grip", "grips", "holds her", "holds his",
         "takes her hand", "takes his hand", "push", "pushes", "shove", "shoves",
         "shakes her", "shakes his", "hug", "hugs", "embrace", "embraces",
         "slaps", "snatches", "clutches his", "clutches her", "pulls her",
         "pulls his", "touches", "hands over", "hands her", "hands him"]

# 서류·판결문에나 쓰는 말. 싸우는 사람 입에서 나오면 즉시 가짜가 된다.
# ⚠️ 한두 줄은 봐준다(법정 장면에서는 실제로 나온다). 대사 전체가 법률
#    설명이 되어 버리는 것을 막는 것이 목적이므로 **줄 수로** 센다.
STIFF = ["유류분", "한정승인", "상속재산", "상속액", "판례", "시효", "증여",
         "물가상승률", "반환청구", "귀책", "고유재산", "사망보험금", "악의적",
         "청구권", "소명", "입증", "채권자", "피고", "원고"]
STIFF_MAX = 5          # 이보다 많으면 대본 전체가 법률 설명이라는 뜻


def soft(doc):
    """버릴 것까진 아니지만 사람이 한 번 봐야 할 곳."""
    out = []
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
            act = next((l for l in (c.get("prompt") or "").split("\n")
                        if l.startswith("ACTION:")), "").lower()
            hit = [w for w in TOUCH if re.search(rf"\b{w}\b", act)]
            if hit:
                out.append(f"{e.get('no')}화 {c.get('n')}컷: 서로 몸이 닿는 동작 "
                           f"— {', '.join(sorted(set(hit)))} "
                           f"(손이 옷 속으로 녹아든다)")
            for l in (c.get("prompt") or "").split("\n"):
                if not l.startswith("DIALOGUE:"):
                    continue
                for say in re.findall(r'"([^"]*)"', l):
                    for w in SPOKEN_BAN:
                        if w in say:
                            out.append(f"{e.get('no')}화 {c.get('n')}컷: 대사에 "
                                       f"'{w}' — 사람은 그렇게 말하지 않는다 "
                                       f'("{say}")')
    return out


# ── 검사 ────────────────────────────────────────────────
def check(doc):
    """규격을 어긴 곳을 전부 찾아 돌려준다. 하나라도 있으면 저장하지 않는다."""
    bad = []
    stiff_lines = 0            # 법률·서류 말투가 들어간 대사 줄 수
    stiff_hits = set()
    eps = doc.get("episodes") or []
    if len(eps) != EPISODES:
        bad.append(f"화 수가 {len(eps)}개다 (있어야 할 것 {EPISODES}개)")
    if len(doc.get("characters") or []) > 3:
        bad.append("등장인물이 3명을 넘는다")
    names = [(ch.get("name") or "").strip() for ch in (doc.get("characters") or [])]

    for e in eps:
        no = e.get("no", "?")
        cuts = e.get("cuts") or []
        if len(cuts) != CUTS:
            bad.append(f"{no}화: 컷이 {len(cuts)}개다 (있어야 할 것 {CUTS}개)")
        if no != 1 and not (e.get("recap") or "").strip():
            bad.append(f"{no}화: 지난 줄거리(recap)가 비었다")
        if len(e.get("recap") or "") > RECAP_MAX:
            bad.append(f"{no}화: 지난 줄거리가 {RECAP_MAX}자를 넘는다 "
                       f"({len(e['recap'])}자)")

        talk = 0          # 이 화에서 두 사람이 주고받은 컷 수
        for c in cuts:
            n = c.get("n", "?")
            tag = f"{no}화 {n}컷"
            p = c.get("prompt") or ""

            want = ROLES[n - 1] if isinstance(n, int) and 1 <= n <= CUTS else None
            if want and c.get("role") != want:
                bad.append(f"{tag}: 역할이 '{c.get('role')}' 이다 (있어야 할 것 '{want}')")

            got = [l.split(":")[0] + ":" for l in p.split("\n") if ":" in l]
            if got[:len(LINES)] != LINES:
                bad.append(f"{tag}: 6줄 규격이 아니다 — {got[:8]}")
            if STYLE_FIX not in p:
                bad.append(f"{tag}: STYLE 줄이 고정 문구와 다르다")
            if not p.rstrip().endswith("focus."):
                bad.append(f"{tag}: Avoid 줄로 끝나지 않는다")

            # ⭐ 글자가 나올 물건을 불렀는가 (영상에 글자 금지 — 운영자 지시)
            head = p.split("STYLE:")[0].lower()
            hit = text_bait(head)
            if hit:
                bad.append(f"{tag}: 글자가 나올 물건을 불렀다 — {', '.join(hit)}")

            # 한국어 대사 — 6초에 들어가는 양 (한 줄 · 총합 · 말하는 사람 수)
            says = []
            for line in p.split("\n"):
                if line.startswith("DIALOGUE:"):
                    says += re.findall(r'"([^"]*)"', line)
            total = sum(syl(x) for x in says)
            if total > DIA_SYL_MAX:
                bad.append(f"{tag}: 대사가 다 합쳐 {total}음절이다 "
                           f"({DIA_SYL_MAX}음절 이내 — {total / SYL_PER_SEC:.1f}초라 {SEC}초에 "
                           f"안 들어간다)")
            if len(says) > TALKERS_MAX:
                bad.append(f"{tag}: 한 컷에서 {len(says)}번 말한다 "
                           f"({TALKERS_MAX}번 이내 — 6초에 그 이상은 뭉개진다)")
            if says and total < DIA_SYL_MIN:
                bad.append(f"{tag}: 대사가 다 합쳐 {total}음절뿐이다 "
                           f"({DIA_SYL_MIN}음절 이상 — {total / SYL_PER_SEC:.1f}초라 {SEC}초가 "
                           f"거의 빈다) — {' / '.join(says)}")
            stiff_hits.update(w for x in says for w in STIFF if w in x)
            stiff_lines += sum(1 for x in says if any(w in x for w in STIFF))
            if len(says) >= 2:
                talk += 1
            if len(c.get("subtitle") or "") > SUB_MAX:
                bad.append(f"{tag}: 자막이 {SUB_MAX}자를 넘는다")
            # 지시대명사 — 컷은 하나씩 따로 만들어져 모델이 못 알아듣는다.
            # ⚠️ 2026-08-20 — 이 검사가 **우리 예시 대본까지 걸러냈다.**
            #    "시동생 holds out a folder; she does not take it." 처럼 앞에 이름이
            #    있으면 모델은 알아듣는다. 정말 위험한 것은 화면에 누가 있는지
            #    적는 SUBJECT 줄에 이름 없이 'the same woman' 만 적는 경우다.
            #    그래서 SUBJECT 줄만, 그것도 이름이 하나도 없을 때만 잡는다.
            subj = next((l for l in p.split("\n") if l.startswith("SUBJECT:")), "")
            if re.search(r"\bthe same\b|\bshe\b|\bhe\b", subj.lower()) and \
                    not any(nm and nm in subj for nm in names):
                bad.append(f"{tag}: SUBJECT 에 이름 없이 지시대명사를 썼다 "
                           f"— 누가 화면에 있는지 이름으로 적는다")

        # ⭐ 한 명이 혼잣말만 5번 하면 이야기가 안 굴러간다 (2026-08-20 손님 지적).
        #    맞섬·뒤집기 같은 컷은 반드시 주고받아야 장면이 앞으로 나간다.
        if cuts and talk < TALK_MIN:
            bad.append(f"{no}화: 두 사람이 주고받는 컷이 {talk}컷뿐이다 "
                       f"({TALK_MIN}컷 이상 — 혼잣말만 이으면 이야기가 안 굴러간다)")

    # ⭐ 대사가 법률 설명을 대신 지고 있으면 말이 통째로 가짜가 된다
    #    (2026-08-20 손님: "말도 어색해. 구어체가 아닌 것 같고 실제 같지 않아.")
    #    법정 장면 한두 줄은 봐준다 — 대본 전체가 설명이 되는 것만 막는다.
    if stiff_lines > STIFF_MAX:
        bad.append(f"대사 {stiff_lines}줄이 서류·판결문 말투다 "
                   f"({STIFF_MAX}줄까지만) — {', '.join(sorted(stiff_hits))} · "
                   f"사실은 설명 자막(caption)이 지고, 입은 감정만 말한다")
    return bad


def summary(doc, sid, case_id):
    cuts = sum(len(e.get("cuts") or []) for e in doc.get("episodes") or [])
    sec = cuts * SEC
    print(f"\n{sid} · 판례 {case_id} · 「{doc.get('title', '')}」")
    print(f"  {len(doc.get('episodes') or [])}화 × {CUTS}컷 × {SEC}초 "
          f"= 컷 {cuts}개 · 총 {sec}초 ({sec / 60:.1f}분)")
    print(f"  등장인물 {len(doc.get('characters') or [])}명 · "
          f"하루 45크레딧(무료 50) · 16일이면 롱폼 한 편")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="", help="판례 번호 (비우면 자동)")
    ap.add_argument("--check", default="", help="이미 만든 시리즈만 다시 검사 (0원)")
    ap.add_argument("--writer", default="", help="claude / gemini (기본: gemini)")
    args = ap.parse_args()

    SERIES_DIR.mkdir(parents=True, exist_ok=True)
    state = load(STATE, {})

    if args.check:
        doc = load(SERIES_DIR / f"{args.check}.json", None)
        if not doc:
            print(f"❌ {args.check} 가 없다", file=sys.stderr)
            return 2
        bad = check(normalize(doc))
        summary(doc, args.check, doc.get("case_id", ""))
        for b in bad:
            print(f"  ❌ {b}")
        print("\n" + ("❌ 규격에 안 맞는 곳 %d군데" % len(bad) if bad else "✅ 규격 통과"))
        for w in soft(doc):
            print(f"  ⚠️ 손볼 곳 — {w}")
        return 1 if bad else 0

    queue = load(QUEUE, [])
    row = (next((c for c in queue if c["case_id"] == args.case), None) if args.case
           else pick_case(queue, state))
    if not row:
        print("❌ 쓸 판례가 없다. [1. 재판 기록 모으기] 를 먼저 돌려라", file=sys.stderr)
        return 2

    sid = next_id(state)
    print(f"{sid} 만드는 중 — 판례 {row['case_id']} · {row.get('case_type', '')}")
    print(f"  {row.get('one_line', '')[:70]}")

    # ⭐ 글은 제미나이가 쓴다 (2026-08-18 운영자 지시)
    llm, who = writer(max_calls=6, prefer=(args.writer or "gemini"))
    body = prompts.fill(prompts.load("series_gen"), CASE_JSON=case_json(row))
    # ⚠️ 2026-08-20 — 대사가 길어지고 caption 칸이 생기면서 16화 JSON 이
    #    32,768 토큰을 넘어 잘렸다. 16화 × 5컷 × (프롬프트 7줄 + 자막 2종)
    #    이면 5만 토큰쯤 된다. 넉넉히 잡는다 — 안 쓰면 값도 안 나간다.
    doc = llm.json(body, tier="pro", max_output_tokens=65536, temperature=0.85,
                   label="시리즈", effort="high")

    doc = normalize(doc)
    doc["case_id"] = row["case_id"]
    doc["series_id"] = sid
    doc["spec"] = {"episodes": EPISODES, "cuts": CUTS, "sec": SEC}

    bad = check(doc)
    summary(doc, sid, row["case_id"])
    if bad:
        broken = SERIES_DIR / f"{sid}.broken.json"
        broken.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n❌ 규격에 안 맞는 곳 {len(bad)}군데 — 저장하지 않았다")
        for b in bad[:15]:
            print(f"  · {b}")
        if len(bad) > 15:
            print(f"  · … 외 {len(bad) - 15}군데")
        print(f"  (받은 것은 {broken.name} 에 남겨 뒀다)")
        return 1

    (SERIES_DIR / f"{sid}.json").write_text(
        json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    # ⚠️ 2026-08-20 — 통과한 뒤에도 지난번 반려본이 그대로 남아 있어서, 내가
    #    **새 대본 대신 옛 반려본을 읽고** 결과가 안 바뀌었다고 잘못 읽었다.
    #    통과했으면 짝이 되는 반려본은 지운다(더 볼 이유가 없다).
    old = SERIES_DIR / f"{sid}.broken.json"
    if old.exists():
        old.unlink()
        print(f"  (지난 반려본 {old.name} 은 지웠다)")
    state[sid] = {"case_id": row["case_id"], "title": doc.get("title", ""),
                  "episodes": EPISODES, "made": 0, "writer": who}
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✅ {sid}.json 저장 — 매일 한 화씩 30초 영상을 만들면 된다")
    for w in soft(doc):
        print(f"  ⚠️ 손볼 곳 — {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
