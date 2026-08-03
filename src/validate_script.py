#!/usr/bin/env python3
"""대본 JSON 검증기 — script_gen.md 의 규칙을 기계가 검사한다.

사용법
    python3 src/validate_script.py data/scripts/EP001.json

왜 필요한가
    대본은 사람이 손보지 않고 곧바로 렌더링에 들어간다.
    에셋 코드가 하나만 틀려도 12분 렌더링이 통째로 실패하고, GitHub Actions 시간이 날아간다.
    눈으로 보는 검수는 반드시 놓친다. 기계가 막아야 한다.

    script.yml 은 대본을 저장하기 **전에** 이 검사를 돌리고,
    ERROR 가 하나라도 있으면 저장하지 않고 재생성한다.

종료 코드
    0  ERROR 없음 (WARN 은 있을 수 있음)
    1  ERROR 있음 → 저장 금지
    2  파일을 못 읽거나 JSON 형식이 깨짐
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import money                                                # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# 막 이름 → (시작초, 끝초). prompts/script_gen.md v2.0 의 시간 예산과 같아야 한다.
#
# ⚠️ v2.0 에서 크게 바뀌었다. 법정(4막)이 150초, 5막 법령 설명이 20초여서
#    판결·금액이 전체의 20%를 넘게 차지했다. 이 채널은 법정물이 아니라 가족 드라마다.
#    4막 150→55초, 5막 50→31초로 줄이고 그 114초를 1~3막(사람 이야기)으로 옮겼다.
ACT_WINDOW = {
    "hook": (0, 22),
    "act1": (22, 240),
    "act2": (240, 446),
    "act3": (446, 634),
    "act4": (634, 689),
    "act5": (689, 720),
}

MAX_CUT_SEC = 7.0
MAX_TEXT_LEN = 45
CUT_MIN, CUT_MAX = 100, 115
RUNTIME, RUNTIME_TOL = 720, 10
ACT_TOL = 5
SHORT_MIN, SHORT_MAX = 35.0, 50.0

# 판결·금액이 차지해도 되는 최대 비율. 이야기의 90%는 사람 사이의 일이어야 한다.
LEGAL_MAX_RATIO = 0.10
MAX_AMOUNT_GFX = 1          # 금액 카드는 4막 판결 낭독 한 컷에만


class Report:
    def __init__(self):
        self.errors = []
        self.warns = []
        self.oks = []

    def error(self, where, msg):
        self.errors.append((where, msg))

    def warn(self, where, msg):
        self.warns.append((where, msg))

    def ok(self, msg):
        self.oks.append(msg)

    def dump(self):
        for m in self.oks:
            print(f"  OK    {m}")
        for w, m in self.warns:
            print(f"  WARN  [{w}] {m}")
        for w, m in self.errors:
            print(f"  ERROR [{w}] {m}")
        print()
        print(f"  통과 {len(self.oks)} · 경고 {len(self.warns)} · 오류 {len(self.errors)}")
        return 1 if self.errors else 0


def load_manifest():
    with open(ROOT / "assets" / "manifest.json", encoding="utf-8") as f:
        return json.load(f)


def all_cuts(doc):
    for act in doc.get("acts", []):
        for cut in act.get("cuts", []):
            yield act, cut


def check_structure(doc, r):
    for key in ("meta", "anonymization", "law", "characters", "acts", "shorts", "youtube"):
        if key not in doc:
            r.error("구조", f"최상위 항목 '{key}' 가 없다")
    ids = [a.get("id") for a in doc.get("acts", [])]
    if ids != list(ACT_WINDOW):
        r.error("구조", f"막 구성이 다르다: {ids} (기대: {list(ACT_WINDOW)})")
    else:
        r.ok("5단 구조 6개 막이 순서대로 있다")


def check_assets(doc, mf, r):
    bg = set(mf["bg"]["codes"])
    pose = set(mf["char"]["poses"])
    code = set(mf["char"]["codes"])
    bgm = set(mf["bgm"]["codes"])
    amb = set(mf["amb"]["codes"])
    sfx = set(mf["sfx"]["codes"])
    spk = set(mf["speakers"])
    gfx = set(mf["gfx"])

    bad = 0
    for act, cut in all_cuts(doc):
        cid = cut.get("id", "?")
        if cut.get("bg") not in bg:
            r.error(cid, f"모르는 배경 코드: {cut.get('bg')}"); bad += 1
        if cut.get("speaker") not in spk:
            r.error(cid, f"모르는 목소리 코드: {cut.get('speaker')}"); bad += 1
        if not cut.get("amb"):
            r.error(cid, "amb 가 비어 있다 — 무음 구간이 생긴다"); bad += 1
        elif cut["amb"] not in amb:
            r.error(cid, f"모르는 앰비언스 코드: {cut['amb']}"); bad += 1
        if cut.get("sfx") is not None and cut["sfx"] not in sfx:
            r.error(cid, f"모르는 효과음 코드: {cut['sfx']}"); bad += 1
        g = cut.get("gfx")
        if g is not None and g.get("type") not in gfx:
            r.error(cid, f"모르는 그래픽 종류: {g.get('type')}"); bad += 1
        chars = cut.get("chars") or []
        if len(chars) > 2:
            r.error(cid, f"한 컷에 인물 {len(chars)}명 — 최대 2명"); bad += 1
        for c in chars:
            if c.get("code") not in code:
                r.error(cid, f"모르는 인물 코드: {c.get('code')}"); bad += 1
            if c.get("pose") not in pose:
                r.error(cid, f"모르는 포즈: {c.get('pose')}"); bad += 1
    for act in doc.get("acts", []):
        if act.get("bgm") not in bgm:
            r.error(act.get("id", "?"), f"모르는 음악 코드: {act.get('bgm')}")
            bad += 1
    if bad == 0:
        r.ok("모든 에셋 코드가 manifest.json 목록 안에 있다")


def check_speaker(doc, r):
    """**말하는 사람과 화면에 있는 사람이 맞는지** 본다.

    왜 필요한가
        · 대사인데 화면에 그 인물이 없으면 목소리만 허공에서 들린다.
          실측: 쇼츠 6컷이 `chars: []` 인 채로 장남·어머니 목소리가 나왔다.
        · 서로 다른 인물에게 같은 코드를 주면 화면에 **같은 얼굴**로 나온다.
          실제로 아버지와 차남이 같은 얼굴로 나왔다."""
    bad = 0
    name2code = {}
    for ch in (doc.get("characters") or []):
        nm = str(ch.get("nametag") or ch.get("name") or "").split("·")[0].strip()
        if nm:
            name2code[nm] = ch.get("code")
    for act, cut in all_cuts(doc):
        cid = cut.get("id", "?")
        sp = cut.get("speaker") or "narrator"
        text = (cut.get("text") or "").strip()
        # 본편은 chars(복수), 쇼츠는 char(단수)를 쓴다. 둘 다 읽는다 —
        # 한쪽만 보다가 멀쩡한 쇼츠 6컷을 '화면이 비었다' 고 잘못 잡은 적이 있다.
        one = cut.get("char")
        on = [c.get("code") for c in (cut.get("chars") or [])]
        if isinstance(one, dict) and one.get("code"):
            on.append(one["code"])

        if text and sp != "narrator":
            want = sp[2:] if sp.startswith("v_") else sp
            if not on:
                r.error(cid, f"{sp} 가 말하는데 화면에 아무도 없다 — 목소리만 뜬다")
                bad += 1
            elif want not in on:
                r.error(cid, f"{sp} 가 말하는데 화면에는 {on} 뿐이다")
                bad += 1

        # 이름표에 적힌 사람이 **화면에 실제로 있는지** 본다.
        # ⚠️ chars[0] 이 그 사람일 거라고 짐작하면 안 된다. 두 명이 선 컷에서
        #    순서가 반대면 멀쩡한 대본을 오류로 잡는다(실제로 그랬다).
        #    배역 명단(characters)에서 이름 → 코드를 정확히 찾는다.
        g = cut.get("gfx") or {}
        if g.get("type") == "nametag":
            who = str(g.get("text", "")).split("·")[0].strip()
            code = name2code.get(who)
            if who and code is None:
                r.error(cid, f"이름표 '{who}' 가 배역 명단에 없다")
                bad += 1
            elif code and code not in on:
                r.error(cid, f"이름표는 '{who}'({code}) 인데 화면에는 {on} 뿐이다")
                bad += 1
    if bad == 0:
        r.ok("말하는 사람과 화면 인물이 모두 맞는다")


# 대사가 여러 명을 가리키는 말. 그만큼 사람이 실제로 있어야 한다.
PLURAL_WORDS = {
    "동생들": ("차남", "삼남", "사남", "장녀", "차녀", "막내"),
    "형들": ("장남", "차남"),
    "아들들": ("장남", "차남", "삼남", "사남"),
    "딸들": ("장녀", "차녀", "삼녀"),
    "자녀들": ("장남", "차남", "삼남", "장녀", "차녀"),
    "형제들": ("장남", "차남", "삼남", "사남"),
}


def check_plural(doc, r):
    """**여러 명을 가리키는 대사인데 사람이 그만큼 없는지** 본다.

    실제로 있었던 일
        판례 원문은 '상속인은 배우자, 장남(피고), 차남, 삼남' 인데 대본 배역에는
        삼남이 빠져 있었다. 대사는 '어머니와 동생들의 몫' 이라고 정확히 말하는데
        명단과 가족관계도에는 동생이 한 명뿐이라 앞뒤가 맞지 않았다.
        사람 눈으로만 찾을 수 있는 종류라 기계가 잡아야 한다.

    ⚠️ 상속인 수는 **금액과 직결된다.** 법정상속분은 배우자 1.5 : 자녀 1 : 1 : 1 로
       나누므로, 동생 수를 줄이면 판결 금액이 통째로 틀려진다.
       그래서 '대사를 단수로 고치는' 해법은 쓰면 안 된다 — 사람을 채워야 한다."""
    roles = set()
    for n in (doc.get("anonymization", {}) or {}).get("names", []) or []:
        if n.get("role"):
            roles.add(str(n["role"]).strip())
    for ch in (doc.get("characters") or []):
        if ch.get("role"):
            roles.add(str(ch["role"]).strip())
    for _, cut in all_cuts(doc):
        g = cut.get("gfx") or {}
        if g.get("type") == "family":
            for nd in (g.get("nodes") or []):
                if nd.get("rel"):
                    roles.add(str(nd["rel"]).strip())

    bad = 0
    for _, cut in all_cuts(doc):
        text = cut.get("text") or ""
        for word, want in PLURAL_WORDS.items():
            if word in text:
                have = sum(1 for w in want if w in roles)
                if have < 2:
                    r.error(cut.get("id", "?"),
                            f"'{word}' 라고 말하는데 해당하는 사람이 {have}명뿐이다 "
                            f"— 배역·가족관계도에 채우거나 대사를 고쳐야 한다")
                    bad += 1
    if bad == 0:
        r.ok("여러 명을 가리키는 대사에 사람이 모두 있다")


# 대사에 나오면 안 되는 것들 — 이번 회차 검수에서 실제로 걸린 것만 넣는다.
#   ① 배역에 없는 사람 (조카·사위·며느리…) 이 불쑥 나오면 시청자가 멈칫한다
#   ② 어머니가 자기 아들을 '동생' 이라 부르는 식의 **시점 어긋난 호칭**
GHOST_PEOPLE = ("조카", "사위", "며느리", "손자", "손녀", "이모", "삼촌",
                "고모", "매형", "처남", "올케", "형수", "제수")
# 부모가 **자기를 형제 자리에 놓고** 말하는 경우만 잡는다.
# ⚠️ '너희 형은 바쁘잖니' 는 어머니가 차남에게 하는 **자연스러운** 말이다.
#    처음에 '형은' 을 통째로 막았더니 멀쩡한 대사가 걸렸다 — 규칙을 좁혔다.
#    진짜 문제는 '나랑 동생들을 상대로' 처럼 자기와 동생을 한 묶음으로 놓는 것이다.
WRONG_CALL = {
    "어머니": (r"(나|저)(랑|와|하고)\s*동생", r"우리\s*동생"),
    "아버지": (r"(나|저)(랑|와|하고)\s*동생", r"우리\s*동생"),
}


def check_dialogue(doc, r):
    """대사를 사람이 읽듯 훑는다 — 없는 사람, 어긋난 호칭, 같은 말 반복.

    실제로 이번 회차에서 걸린 것들
      · '조카가 보낸 문자' — 조카는 배역에 없다. 누구인지 알 수 없다
      · 어머니가 '나랑 동생들을 상대로' — '동생' 은 형제 기준 호칭이다
      · 어머니와 차남이 **바로 이웃한 컷에서** 똑같이 '소송을 걸었다고?' 로 놀란다"""
    code2role = {c.get("code"): c.get("role", "") for c in (doc.get("characters") or [])}
    bad = 0
    prev = None
    for _, cut in all_cuts(doc):
        cid = cut.get("id", "?")
        text = (cut.get("text") or "").strip()
        sp = cut.get("speaker") or "narrator"
        if not text:
            prev = None
            continue
        for w in GHOST_PEOPLE:
            if w in text:
                r.error(cid, f"배역에 없는 사람 '{w}' 이 대사에 나온다 — "
                             "배역에 넣거나 대사를 고쳐야 한다")
                bad += 1
        role = code2role.get(sp[2:] if sp.startswith("v_") else sp, "")
        for pat in WRONG_CALL.get(role, ()):
            if re.search(pat, text):
                r.error(cid, f"{role} 가 자기를 형제 자리에 놓고 말한다 — "
                             "'동생' 은 형제 기준 호칭이다: 「" + text[:30] + "」")
                bad += 1
        # 이웃한 두 대사가 거의 같은 말인가 (핵심 낱말 겹침으로 본다)
        if prev and sp != "narrator" and prev[1] != "narrator":
            a = set(re.findall(r"[가-힣]{2,}", prev[2]))
            b = set(re.findall(r"[가-힣]{2,}", text))
            if a and b and len(a & b) / min(len(a), len(b)) >= 0.6:
                r.warn(cid, f"바로 앞({prev[0]}) 대사와 겹친다 — 같은 말을 두 번 한다")
        prev = (cid, sp, text)
    if bad == 0:
        r.ok("대사에 없는 사람·어긋난 호칭이 없다")


def check_timing(doc, r):
    cuts = list(all_cuts(doc))
    n = len(cuts)
    if not (CUT_MIN <= n <= CUT_MAX):
        r.error("분량", f"총 컷 수 {n}개 — {CUT_MIN}~{CUT_MAX} 범위를 벗어남")
    else:
        r.ok(f"총 컷 수 {n}개 ({CUT_MIN}~{CUT_MAX})")

    declared = doc.get("meta", {}).get("cut_count")
    if declared != n:
        r.error("분량", f"meta.cut_count({declared}) 가 실제 컷 수({n})와 다르다")

    over = [c["id"] for _, c in cuts if float(c.get("sec", 0)) > MAX_CUT_SEC]
    if over:
        r.error("분량", f"7.0초를 넘는 컷: {', '.join(over)}")
    else:
        r.ok(f"모든 컷이 {MAX_CUT_SEC}초 이하")

    total = 0.0
    for act in doc.get("acts", []):
        aid = act.get("id")
        s = sum(float(c.get("sec", 0)) for c in act.get("cuts", []))
        total += s
        if aid in ACT_WINDOW:
            lo, hi = ACT_WINDOW[aid]
            want = hi - lo
            if abs(s - want) > ACT_TOL:
                r.error("분량", f"{aid}: 컷 합 {s:.1f}초 — 목표 {want}초 (허용 ±{ACT_TOL})")
            else:
                r.ok(f"{aid}: {s:.1f}초 / 목표 {want}초")
    if abs(total - RUNTIME) > RUNTIME_TOL:
        r.error("분량", f"전체 {total:.1f}초 — 목표 {RUNTIME}초 (허용 ±{RUNTIME_TOL})")
    else:
        r.ok(f"전체 길이 {total:.1f}초 / 목표 {RUNTIME}초")


def check_text(doc, r):
    long_cuts = []
    for _, cut in all_cuts(doc):
        t = cut.get("text", "") or ""
        if len(t) > MAX_TEXT_LEN:
            long_cuts.append(f"{cut.get('id')}({len(t)}자)")
    if long_cuts:
        r.error("자막", f"{MAX_TEXT_LEN}자를 넘는 컷: {', '.join(long_cuts)}")
    else:
        r.ok(f"모든 대사·나레이션이 {MAX_TEXT_LEN}자 이내")


def check_hook(doc, r):
    hook = next((a for a in doc.get("acts", []) if a.get("id") == "hook"), None)
    if not hook or not hook.get("cuts"):
        r.error("3초 관문", "도입 훅이 없다")
        return
    first = hook["cuts"][0]
    if float(first.get("sec", 99)) > 3.0:
        r.error("3초 관문", f"첫 컷이 {first.get('sec')}초 — 3.0초 이내여야 한다")
    else:
        r.ok(f"첫 컷 {first.get('sec')}초 (3초 관문)")
    if first.get("speaker") == "narrator":
        r.warn("3초 관문", "첫 컷이 나레이션이다. 인물 대사로 시작하는 쪽이 강하다")
    # 배경 설명형 도입 탐지
    for cut in hook["cuts"]:
        t = cut.get("text", "")
        if re.search(r"\d+세(입니다|였습니다)|이야기입니다|소송입니다", t):
            r.error("3초 관문", f"{cut['id']}: 인물 소개·설명형 도입으로 보인다 — \"{t}\"")


def _is_money_cut(cut):
    """이 컷이 '돈 이야기' 인가."""
    return bool(money.mentions(cut.get("text") or "")) or \
        (cut.get("gfx") or {}).get("type") == "amount"


def check_legal_ratio(doc, r):
    """⭐ 판결·금액이 전체의 10%를 넘지 않는가.

    이 채널은 법정물이 아니라 가족 드라마다. 시청자는 판결이 궁금해서 보는 게 아니라
    저 집 사람들이 왜 저렇게 됐는지가 궁금해서 본다. 판결은 마침표일 뿐 본문이 아니다.

    예전 대본(v1.0)은 4막 법정 150초 + 5막 법령 설명 20초에 금액 문장이 곳곳에 흩어져
    판결·금액이 20%를 넘었다. 화면이 계속 돈 이야기로 보였다."""
    total = sum(float(c.get("sec", 0)) for _a, c in all_cuts(doc))
    budget = total * LEGAL_MAX_RATIO

    legal_sec, act4_sec, money_out = 0.0, 0.0, []
    for act, cut in all_cuts(doc):
        sec = float(cut.get("sec", 0))
        in_act4 = act.get("id") == "act4"
        if in_act4:
            act4_sec += sec
        if in_act4 or _is_money_cut(cut):
            legal_sec += sec
        if _is_money_cut(cut) and not in_act4:
            money_out.append(cut.get("id"))

    pct = 100 * legal_sec / max(1.0, total)
    if legal_sec > budget:
        r.error("판결·금액 비중",
                f"{legal_sec:.0f}초 ({pct:.1f}%) — 상한 {budget:.0f}초({LEGAL_MAX_RATIO:.0%}) 초과. "
                f"4막 {act4_sec:.0f}초 + 4막 밖 금액 컷 {len(money_out)}개"
                + (f" ({', '.join(money_out[:6])})" if money_out else ""))
    else:
        r.ok(f"판결·금액 {legal_sec:.0f}초 ({pct:.1f}%) — 상한 {budget:.0f}초 이내")

    # 금액 카드는 판결 낭독 한 컷에만. 여러 번 뜨면 화면이 계속 돈 이야기가 된다.
    amt = [c.get("id") for _a, c in all_cuts(doc)
           if (c.get("gfx") or {}).get("type") == "amount"]
    if len(amt) > MAX_AMOUNT_GFX:
        r.error("판결·금액 비중",
                f"금액 그래픽이 {len(amt)}개 ({', '.join(amt)}) — {MAX_AMOUNT_GFX}개까지")
    else:
        r.ok(f"금액 그래픽 {len(amt)}개 ({MAX_AMOUNT_GFX}개 이하)")


def check_stakes(doc, r):
    """도입과 1막에서는 금액을 말하지 않는다.

    걸린 것의 무게는 숫자가 아니라 **물건과 관계**로 전한다.
    "12억 400만 원" 이 아니라 "세 아들이 다 자란 그 집" 이다.
    시작부터 액수가 나오면 이야기가 돈 문제가 되고, 시청자는 남의 재산 구경이 된다."""
    early = []
    for act, cut in all_cuts(doc):
        if act.get("id") not in ("hook", "act1"):
            continue
        if _is_money_cut(cut):
            early.append(f"{cut.get('id')}({act.get('id')})")
    if early:
        r.error("30초 관문",
                f"도입·1막에 금액이 나온다: {', '.join(early[:6])} — "
                f"걸린 것은 물건과 관계로 말한다 ('그 집', '아버지 논')")
    else:
        r.ok("도입·1막에 금액 없음 (걸린 것을 관계로 전달)")


def check_flashback(doc, r):
    """회상이 시작되는 첫 컷마다 '언제인지'가 붙어 있는가.

    색만 세피아로 바뀌면 어르신 시청자는 '화면이 이상해졌다' 로 본다.
    EP001 실측: 회상을 8번 드나드는데 시점 표기가 하나도 없었다."""
    cuts = [c for _a, c in all_cuts(doc)]
    starts, missing, stray = 0, [], []
    prev = False
    for c in cuts:
        fb = bool(c.get("flashback"))
        lab = (c.get("flashback_label") or "").strip()
        if fb and not prev:
            starts += 1
            if not lab:
                missing.append(c.get("id"))
        elif lab:
            stray.append(c.get("id"))
        prev = fb
    if not starts:
        r.ok("회상 구간이 없다")
        return
    if missing:
        r.error("회상", f"회상 시작 컷에 시점 표기(flashback_label)가 없다: "
                        f"{', '.join(missing[:6])}")
    else:
        r.ok(f"회상 {starts}구간 모두 시점 표기 있음")
    if stray:
        r.warn("회상", f"회상 시작이 아닌데 시점 표기가 있다: {', '.join(stray[:6])}")


# 그래픽이 글자를 잘라 버리는 한계. graphics.py 의 [:N] 과 반드시 같아야 한다.
GFX_LIMIT = {
    ("timeline", "label"): 16,
    ("timeline", "when"): 14,
    ("family", "name"): 8,
    ("family", "rel"): 12,
}


def check_gfx_text(doc, r):
    """⭐ 그래픽 안의 글자가 잘리지 않는가.

    연표·관계도는 글자가 길면 **말없이 잘라서** 그린다. 잘렸다는 표시도 없다.
    실제로 연표에 '아버지가 장남에게 9억 8,000만 원'(21자)을 넣었더니
    화면에는 '아버지가 장남에게 9억 8,0' 까지만 나왔다 — 금액이 반토막 났다.
    렌더링은 성공하므로 영상을 끝까지 봐야만 발견된다. 여기서 미리 막는다."""
    bad = []
    for _a, cut in all_cuts(doc):
        g = cut.get("gfx") or {}
        kind = g.get("type")
        rows = g.get("items") if kind == "timeline" else \
            g.get("nodes") if kind == "family" else None
        for row in (rows or []):
            for field, cap in ((k[1], v) for k, v in GFX_LIMIT.items() if k[0] == kind):
                t = str(row.get(field, ""))
                if len(t) > cap:
                    bad.append(f"{cut.get('id')} {kind}.{field} {len(t)}자(한도 {cap}) '{t}'")
    if bad:
        r.error("그래픽 글자", "화면에서 잘린다: " + " / ".join(bad[:4]))
    else:
        r.ok("연표·관계도 글자가 잘리지 않는다")


def check_tags(doc, r):
    """대본이 스스로 표시해 둔 컷들. 없으면 쇼츠와 검수가 짐작에 의존하게 된다."""
    found = {}
    for _act, cut in all_cuts(doc):
        t = cut.get("tag")
        if t:
            found.setdefault(t, []).append(cut.get("id"))
    if "anger_line" not in found:
        r.error("표시", "3막의 뻔뻔한 대사에 tag:anger_line 이 없다 — 쇼츠 2번이 이 컷을 찾지 못한다")
    elif len(found["anger_line"]) > 1:
        r.error("표시", f"anger_line 이 {len(found['anger_line'])}개다. 정확히 1개여야 한다")
    for t, why in (("twist", "2막 반전"), ("verdict", "4막 판결"), ("question", "5막 질문")):
        if t not in found:
            r.warn("표시", f"{why} 컷에 tag:{t} 가 없다")
    if "anger_line" in found and len(found["anger_line"]) == 1:
        r.ok(f"핵심 컷 표시 {len(found)}종 ({', '.join(sorted(found))})")


def check_blackout(doc, r):
    bad = []
    for act in doc.get("acts", []):
        cuts = act.get("cuts", [])
        for i, c in enumerate(cuts):
            last = (i == len(cuts) - 1)
            if bool(c.get("blackout")) != last:
                bad.append(f"{c.get('id')}({'막 끝인데 false' if last else '막 중간인데 true'})")
    if bad:
        r.error("막 전환", f"blackout 이 잘못됨: {', '.join(bad)}")
    else:
        r.ok("막 전환 검은 화면이 각 막 마지막 컷에만 있다")


def check_nametags(doc, r):
    """인물이 처음 나오는 컷에 네임태그가 있어야 한다.
    고정 배우 7명을 회차마다 다른 역으로 쓰므로, 없으면 누가 누군지 알 수 없다."""
    seen = set()
    missing = []
    for _, cut in all_cuts(doc):
        g = cut.get("gfx") or {}
        has_tag = g.get("type") == "nametag"
        for c in cut.get("chars") or []:
            code = c.get("code")
            if code not in seen:
                seen.add(code)
                if not has_tag:
                    missing.append(f"{cut.get('id')}({code})")
    if missing:
        r.error("네임태그", f"첫 등장인데 네임태그가 없다: {', '.join(missing)}")
    else:
        r.ok(f"등장인물 {len(seen)}명 모두 첫 등장에 네임태그가 있다")


def check_anonymization(doc, r):
    blob = "\n".join((c.get("text") or "") for _, c in all_cuts(doc))
    blob += "\n" + (doc.get("youtube", {}).get("description_body") or "")
    blob += "\n" + (doc.get("law", {}).get("explain_5act") or "")

    years = re.findall(r"(?<!\d)(19|20)\d{2}\s*년", blob)
    if years:
        r.error("익명화", f"절대 연도가 있다 ({len(years)}곳) — 상대 표기여야 한다")
    else:
        r.ok("절대 연도 없음 (전부 상대 표기)")

    nums = re.findall(r"\d{4}\s*(?:가합|가단|나|다|두|누|구합|고합)\s*\d+", blob)
    if nums:
        r.error("익명화", f"사건번호로 보이는 표기가 있다: {nums[:3]}")
    else:
        r.ok("사건번호 표기 없음")

    courts = re.findall(r"[가-힣]{2,}(?:지방법원|고등법원|가정법원)|대법원", blob)
    if courts:
        r.error("익명화", f"특정 법원명이 있다: {sorted(set(courts))[:3]} — '법원'으로만 쓴다")
    else:
        r.ok("특정 법원명 없음")

    judge = re.findall(r"재판장\s*[가-힣]{2,4}(?:\s*판사)?(?=[\s.,]|$)", blob)
    judge = [j for j in judge if not re.search(r"재판장(은|이|을|의|께서|도|만|에게)", j)]
    if judge:
        r.error("익명화", f"재판장에 이름이 붙어 있을 수 있다: {judge[:3]}")
    else:
        r.ok("판사 실명 없음")

    scale = doc.get("anonymization", {}).get("amount_scale")
    if scale is None:
        r.error("익명화", "amount_scale 이 없다")
    elif 0.7 < float(scale) < 1.3:
        r.error("익명화", f"amount_scale {scale} — 30% 이상 변형해야 한다 (0.7 이하 또는 1.3 이상)")
    else:
        r.ok(f"금액 변형 배율 {scale} (30% 이상)")

    # 금액이 대본 안에서 일관된가
    declared = {a["value"] for a in doc.get("anonymization", {}).get("amounts_used", [])}
    found = set(re.findall(r"\d+억(?:\s*[\d,]+만)?\s*원|[\d,]+만\s*원", blob))
    stray = {f for f in found if f not in declared}
    if stray:
        r.warn("익명화", f"amounts_used 에 없는 금액 표기: {sorted(stray)}")
    else:
        r.ok(f"본문 금액이 amounts_used({len(declared)}종)와 일치")

    # 금액이 백만원 단위인가 — 끝자리가 자잘하면 귀로 들어오지 않는다.
    # 100만원 미만은 자르면 0원이 되므로 애초에 대상이 아니다.
    rough = money.untidy(blob)
    if rough:
        seen = sorted(set(rough))
        r.error("금액", f"백만원 단위가 아닌 금액 {len(seen)}종: {seen[:5]}"
                        f"{' …' if len(seen) > 5 else ''}")
    else:
        r.ok("금액이 모두 백만원 단위")


# ── 실제 지명 차단 ────────────────────────────────────────
#
# ⭐ 지역은 **가상의 시·도로 통째로 바꾼다.** 실제 지명은 한 번도 나오면 안 된다.
#    예전 규칙은 '광역 단위까지 변경' 이라고만 적혀 있어, 진짜 도(道)를 그대로 두고
#    시·군만 지우는 것으로 읽혔다. 그러면 '경남 어느 상가' 처럼 범위가 좁혀져
#    당사자를 아는 사람은 알아본다. 명예훼손의 유일한 방어선이 익명화인데 구멍이 생긴다.
#
# ⚠️ 이름만 대조하면 오검출이 쏟아진다. 실제로 겹치는 말들이 있다.
#      상주(喪主) — 장례 이야기에 반드시 나온다      장수(長壽) · 예산(豫算)
#      부여하다 · 무안하다 · 영광스럽다 · 화성(火星) · 동해(東海)
#    그래서 **두 갈래로 나눈다.**
#      1군: 그 자체로 지명인 광역 이름 → 단독으로 나와도 막는다
#      2군: 다른 뜻이 있을 수 있는 시·군 이름 → **뒤에 시/군/읍/면/구가 붙을 때만** 막는다
SIDO_HARD = [
    "서울", "부산", "대구", "인천", "대전", "울산", "세종",
    "경기도", "강원도", "충청", "전라", "경상", "제주도",
    "충북", "충남", "전북", "전남", "경북", "경남",
]
SIGUN = [
    # 경기
    "수원", "성남", "의정부", "안양", "부천", "광명", "평택", "동두천", "안산", "고양",
    "과천", "구리", "남양주", "오산", "시흥", "군포", "의왕", "하남", "용인", "파주",
    "이천", "안성", "김포", "화성", "광주", "양주", "포천", "여주", "가평", "양평", "연천",
    # 강원
    "춘천", "원주", "강릉", "동해", "태백", "속초", "삼척", "홍천", "횡성", "영월",
    "평창", "정선", "철원", "화천", "양구", "인제", "고성", "양양",
    # 충청
    "청주", "충주", "제천", "보은", "옥천", "영동", "증평", "진천", "괴산", "음성", "단양",
    "천안", "공주", "보령", "아산", "서산", "논산", "계룡", "당진", "금산", "부여",
    "서천", "청양", "홍성", "예산", "태안",
    # 전라
    "전주", "군산", "익산", "정읍", "남원", "김제", "완주", "진안", "무주", "장수",
    "임실", "순창", "고창", "부안",
    "목포", "여수", "순천", "나주", "광양", "담양", "곡성", "구례", "고흥", "보성",
    "화순", "장흥", "강진", "해남", "영암", "무안", "함평", "영광", "장성", "완도",
    "진도", "신안",
    # 경상
    "포항", "경주", "김천", "안동", "구미", "영주", "영천", "상주", "문경", "경산",
    "군위", "의성", "청송", "영양", "영덕", "청도", "고령", "성주", "칠곡", "예천",
    "봉화", "울진", "울릉",
    "창원", "진주", "통영", "사천", "김해", "밀양", "거제", "양산", "의령", "함안",
    "창녕", "남해", "하동", "산청", "함양", "거창", "합천",
    # 제주·기타
    "제주", "서귀포", "강화", "옹진",
]
_RE_SIDO = re.compile("|".join(map(re.escape, SIDO_HARD)))
_RE_SIGUN = re.compile(r"(" + "|".join(map(re.escape, SIGUN)) + r")\s*(특별시|광역시|시|군|읍|면|구)(?![가-힣])")


def check_region(doc, r):
    """⭐ 실제 지명이 화면에 나오지 않는가.

    지역은 가상의 시·도로 통째로 바꾼다. '광역 단위까지만 지운다' 로는 부족하다.
    상속·불륜 사건은 당사자가 살아 있고, 아는 사람이 보면 알아본다.
    익명화가 명예훼손(형법 제307조)의 유일한 방어선이다."""
    parts = [_screen_text(doc)]
    y = doc.get("youtube", {})
    parts += [str(y.get("description_body") or ""), str(y.get("pinned_comment") or "")]
    parts += [str(t) for t in (y.get("tags") or [])]
    parts.append(str(doc.get("meta", {}).get("logline") or ""))
    parts += [str(t) for t in (doc.get("meta", {}).get("title_candidates") or [])]
    blob = "\n".join(parts)

    hits = sorted(set(_RE_SIDO.findall(blob))) + \
        sorted({"".join(m) for m in _RE_SIGUN.findall(blob)})
    if hits:
        r.error("익명화", f"실제 지명이 있다: {hits[:6]} — 가상의 시·도로 바꿔야 한다")
    else:
        r.ok("실제 지명 없음 (가상 지역)")


def _screen_text(doc):
    """화면에 실제로 글자로 뜨는 것만 모은다.

    자막(text)과 그래픽(gfx) 안의 글자다. 유튜브 설명글이나 5막 법령 해설 원문은
    화면에 안 뜨므로 넣지 않는다 — 여기 들어가면 '설명글에만 있는 금액'이
    화면에 나온 것처럼 잘못 통과한다."""
    def walk(v, out):
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, dict):
            for k, x in v.items():
                if k != "type":                  # 'amount' 같은 종류 이름은 글자가 아니다
                    walk(x, out)
        elif isinstance(v, list):
            for x in v:
                walk(x, out)

    out = []
    for _a, cut in all_cuts(doc):
        out.append(cut.get("text") or "")
        walk(cut.get("gfx"), out)
    for s in doc.get("shorts", []):
        for cut in s.get("cuts", []):
            out.append(cut.get("text") or "")
            walk(cut.get("gfx"), out)
    return "\n".join(out)


def check_amount_onscreen(doc, r):
    """⭐ 선언한 금액이 화면에 한 번이라도 나오는가.

    EP001 에서 실제로 있었던 일이다. 장남이 미리 받아간 9억 8,000만 원은
    이 사건에서 장남이 진 **이유** 그 자체인데, 자막에도 그래픽에도 한 번도 안 떴다.
    제목과 썸네일은 '9억'을 내걸었는데 영상은 그 숫자를 끝내 보여주지 않았다.
    시청자는 왜 졌는지 모른 채 12분을 본 셈이다.

    amounts_used 에 적어 놓고 화면에 안 쓸 거면 애초에 적지 말아야 한다."""
    declared = doc.get("anonymization", {}).get("amounts_used", [])
    if not declared:
        return

    screen = _screen_text(doc)
    missing = [a for a in declared if (a.get("value") or "") not in screen]
    if missing:
        r.error("금액", "amounts_used 에 있는데 화면에 한 번도 안 나오는 금액: "
                + ", ".join(f"{a.get('value')}({a.get('label')})" for a in missing)
                + " — 자막이나 그래픽에 넣어야 시청자가 이해한다")
    else:
        r.ok(f"선언한 금액 {len(declared)}종 모두 화면에 나온다")


ical = {"십": 10, "이십": 20, "삼십": 30, "사십": 40, "오십": 50,
        "육십": 60, "칠십": 70, "팔십": 80, "구십": 90}


def _years(text):
    """글에서 '○○년' 의 햇수를 뽑는다. '50년' 과 '오십 년' 을 모두 읽는다.
    없으면 None. 여러 개면 첫 번째."""
    t = text or ""
    m = re.search(r"(\d{1,3})\s*년", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(구십|팔십|칠십|육십|오십|사십|삼십|이십|십)\s*년", t)
    return ical[m.group(1)] if m else None


PARENT_ROLES = ("어머니", "아버지", "모친", "부친")
CHILD_ROLES = ("장남", "차남", "삼남", "장녀", "차녀", "삼녀", "아들", "딸")
MIN_BIRTH_AGE = 18          # 부모가 자식을 낳을 수 있는 최소 나이


def check_ages(doc, r):
    """⭐ 나이와 세월이 서로 맞는가.

    EP001 에 실제로 있던 일이다. 어머니 68세 · 장남 50세 인데
    나레이션은 '정임 씨는 40년을 남편과 함께했습니다' 라고 했다.
    셈해 보면 어머니가 18세에 장남을 낳았고, 그 장남은 **결혼보다 10년 먼저**
    태어난 것이 된다. 상속 이야기는 시청자가 가족 관계를 직접 따라 그리며 보기 때문에
    이런 어긋남이 바로 눈에 걸린다.

    두 가지를 본다.
      1) 부모 나이 - 자식 나이 ≥ 18
      2) '○○년을 함께' 같은 결혼 세월 ≥ 맏이 나이"""
    chars = doc.get("characters", [])
    def ages(roles):
        return [(c.get("name"), c.get("role"), c.get("age")) for c in chars
                if c.get("role") in roles and isinstance(c.get("age"), int)]

    parents, kids = ages(PARENT_ROLES), ages(CHILD_ROLES)
    bad = []
    for pn, pr, pa in parents:
        for kn, kr, ka in kids:
            if pa - ka < MIN_BIRTH_AGE:
                bad.append(f"{pr} {pn}({pa}세) → {kr} {kn}({ka}세) = {pa - ka}세에 출산")
    if bad:
        r.error("나이", f"부모가 {MIN_BIRTH_AGE}세 전에 낳은 셈이 된다: " + " / ".join(bad[:4]))
    elif parents and kids:
        r.ok(f"부모·자식 나이 차 {MIN_BIRTH_AGE}세 이상 ({len(parents)}×{len(kids)}쌍)")

    # 결혼 세월 ≥ 맏이 나이. 아니면 맏이가 결혼보다 먼저 태어난 것이 된다.
    eldest = max((a for _n, _r, a in kids), default=None)
    if eldest is None:
        return
    blob = "\n".join((c.get("text") or "") for _a, c in all_cuts(doc))
    spans = [(m.group(0), int(m.group(1))) for m in
             re.finditer(r"(\d{1,2})\s*년(?:을|간|\s*동안|\s*가까이)?\s*"
                         r"(?=[^\n]{0,12}?(남편|아내|부부|함께|같이|살))", blob)]
    short = [(t, y) for t, y in spans if y < eldest]
    if short:
        r.error("나이", "결혼 세월이 맏이 나이보다 짧다 — 맏이가 결혼 전에 태어난 셈: "
                + ", ".join(f"'{t.strip()}'({y}년) < 맏이 {eldest}세" for t, y in short[:3]))
    elif spans:
        r.ok(f"결혼 세월 {spans[0][1]}년 ≥ 맏이 {eldest}세")

    # 같은 컷 안에서 회상 시점 자막과 자막 속 햇수가 어긋나지 않는가.
    # A1-01 이 실제로 그랬다 — 화면 위에는 '사십 년 전', 자막에는 '50년을 함께'.
    # 두 글자가 같은 화면에 동시에 떠 있어서 곧바로 눈에 걸린다.
    clash = []
    for _a, cut in all_cuts(doc):
        lab_y = _years(cut.get("flashback_label") or "")
        txt_y = _years(cut.get("text") or "")
        if lab_y and txt_y and lab_y != txt_y:
            clash.append(f"{cut.get('id')} 시점 '{cut['flashback_label']}'({lab_y}년)"
                         f" ↔ 자막 {txt_y}년")
    if clash:
        r.error("나이", "한 컷 안에서 햇수가 서로 다르다: " + " / ".join(clash[:3]))
    else:
        r.ok("회상 시점 자막과 자막 속 햇수가 어긋나지 않는다")


# 형사 사건에서만 쓰는 말. 민사 사건 대본에 나오면 틀린 말이다.
# 낱말 → 대신 써야 할 말
CRIMINAL_WORDS = {
    "고소": "소송",       # 고소는 '죄를 지었으니 처벌해 달라' 는 형사 신고다
    "고발": "소송",
    "피고소": "피고",
    "기소": "제소",
    "무죄": "청구 기각",
    "유죄": "청구 인용",
    "형량": "판결",
    "징역": "—",
    "벌금": "—",
}
# 민사 사건 종류. 이 말이 case_type 에 들어 있으면 형사 낱말을 쓰면 안 된다.
#
# ⚠️ 소재를 넓힐 때(v2: 불륜·혼외자·제사) **여기를 같이 늘려야 한다.**
#    이 목록에 없는 case_type 은 '형사 사건인가 보다' 하고 검사를 통째로 건너뛴다.
#    즉 빠뜨리면 오류를 잡는 게 아니라 **검사 자체가 조용히 꺼진다** — 가장 위험한 실패다.
#    실제로 v2 에서 상간자위자료·가액지급·제사주재자를 새로 허용하면서 이 구멍이 생겼다.
CIVIL_HINTS = ("상속", "유류분", "이혼", "재산분할", "손해배상", "부당이득",
               "대여금", "임대차", "명도", "청구", "확인", "등기",
               # v2 로 넓힌 소재
               "위자료", "상간", "가액", "제사", "분묘", "유골", "봉안",
               "보증", "구상", "명의", "사해행위", "증여", "유언", "사실혼")


def check_criminal_words(doc, r):
    """⭐ 민사 사건인데 형사 낱말을 쓰지 않았는가.

    실제로 EP001(상속회복청구 — 민사)에서 '어머니는 고소를 당했습니다',
    '나랑 너희를 상대로 고소를 했다는 거니?' 라고 나갔다.
    고소는 '죄를 지었으니 처벌해 달라' 고 경찰·검찰에 내는 **형사** 신고다.
    상속 다툼은 형사가 아니다. 게다가 같은 대본 바로 앞 컷은 '소송을 걸었다'
    라고 제대로 쓰고 있어서, 한 사건을 두 가지 말로 부르고 있었다.

    이 채널은 진짜 판결을 다룬다. 법을 아는 시청자가 가장 먼저 잡아내는 대목이다."""
    case = str(doc.get("meta", {}).get("case_type") or "")
    if not any(h in case for h in CIVIL_HINTS):
        return                                   # 형사 사건이면 검사하지 않는다

    hits = []
    for _a, cut in all_cuts(doc):
        t = cut.get("text") or ""
        for w, alt in CRIMINAL_WORDS.items():
            if w in t:
                hits.append(f"{cut.get('id')} '{w}'"
                            + (f" → '{alt}'" if alt != "—" else " (민사에 없는 말)"))
    if hits:
        r.error("법률 용어",
                f"민사 사건({case})인데 형사 낱말을 썼다: " + " / ".join(hits[:5])
                + (f" 외 {len(hits) - 5}건" if len(hits) > 5 else ""))
    else:
        r.ok(f"민사 사건({case})에 형사 낱말 없음")


def check_law(doc, r):
    law = doc.get("law", {})
    refs = law.get("refs_from_case", [])
    src = law.get("refs_source")
    if src not in ("참조조문", "본문추출", "없음"):
        r.error("법조문", f"law.refs_source 값이 이상하다: {src}")
    else:
        r.ok(f"법조문 출처 경로: {src}")

    blob = "\n".join((c.get("text") or "") for _, c in all_cuts(doc))
    blob += "\n" + (law.get("explain_5act") or "")
    cited = set(re.findall(r"민법 제\d+조(?:의\d+)?(?: 제\d+항)?", blob))
    unknown = {c for c in cited if not any(c in ref or ref in c for ref in refs)}
    if unknown:
        r.error("법조문", f"refs_from_case 에 없는 조문을 인용했다: {sorted(unknown)}")
    else:
        r.ok(f"인용 조문 {len(cited)}종 모두 허용 목록 안")

    advice = re.findall(r"이기[십실]|승소|받으실 수 있|하시면 됩니다|소송하세요", blob)
    if advice:
        r.error("변호사법", f"법률 자문으로 읽힐 표현: {sorted(set(advice))}")
    else:
        r.ok("법률 자문성 표현 없음")


def check_shorts(doc, r):
    shorts = doc.get("shorts", [])
    if len(shorts) != 3:
        r.error("쇼츠", f"{len(shorts)}편 — 정확히 3편이어야 한다")
        return
    ids = {c.get("id") for _, c in all_cuts(doc)}
    by_sec = {c.get("id"): float(c.get("sec", 0)) for _, c in all_cuts(doc)}
    kinds = [s.get("kind") for s in shorts]
    if len(set(kinds)) != 3:
        r.error("쇼츠", f"3편의 성격이 겹친다: {kinds}")
    else:
        r.ok(f"쇼츠 3편 성격 분리: {' / '.join(kinds)}")
    for s in shorts:
        no = s.get("no")
        miss = [c for c in s.get("cut_ids", []) if c not in ids]
        if miss:
            r.error(f"쇼츠{no}", f"존재하지 않는 컷을 가리킨다: {miss}")
        # ⚠️ 쇼츠 형식이 두 가지다.
        #    옛 형식 — 본편 컷을 가리키기만 한다(cut_ids)
        #    지금 형식 — **쇼츠 전용 컷**을 자기가 들고 있다(cuts). 대사를 짧게 다시 쓰므로
        #               본편 컷 길이로 재면 안 된다. 실제로 그래서 합이 0 으로 나와
        #               멀쩡한 쇼츠 3편이 매번 경고로 찍혔다.
        own = s.get("cuts") or []
        if own:
            body = sum(float(c.get("sec", 0)) for c in own) - 6.0
        else:
            body = sum(by_sec.get(c, 0) for c in s.get("cut_ids", []))
        est = float(s.get("est_sec", 0))
        if not (SHORT_MIN <= est <= SHORT_MAX):
            r.error(f"쇼츠{no}", f"est_sec {est}초 — {SHORT_MIN}~{SHORT_MAX}초여야 한다")
        # 본문 합 + 도입/마무리 약 6초
        if abs((body + 6.0) - est) > 4.0:
            r.warn(f"쇼츠{no}", f"est_sec {est} 와 컷 합({body:.1f}+6.0) 이 어긋난다")
        if not s.get("intro_line") or not s.get("outro_line"):
            r.error(f"쇼츠{no}", "전용 도입·마무리 문장이 있어야 한다")
    if not any(e[0].startswith("쇼츠") for e in r.errors):
        r.ok("쇼츠 3편 구간·길이·도입/마무리 정상")


def check_youtube(doc, r):
    y = doc.get("youtube", {})
    ch = y.get("chapters", [])
    if not ch or ch[0].get("sec") != 0:
        r.error("유튜브", "챕터 첫 항목은 반드시 0초여야 한다")
    elif len(ch) < 5:
        r.warn("유튜브", f"챕터가 {len(ch)}개 — 막마다 하나씩 6개를 권장")
    else:
        r.ok(f"챕터 {len(ch)}개, 0초에서 시작")
    if not y.get("pinned_comment"):
        r.error("유튜브", "고정 댓글 문구가 없다")
    body = y.get("description_body", "")
    if re.search(r"법률 상담|픽션|AI", body):
        r.warn("유튜브", "설명란에 고지문을 직접 넣지 않는다 — 시스템이 붙인다")
    titles = doc.get("meta", {}).get("title_candidates", [])
    if len(titles) != 3:
        r.error("유튜브", f"제목 후보가 {len(titles)}개 — 3개여야 한다")
    else:
        long_t = [t for t in titles if len(t) > 30]
        if long_t:
            r.warn("유튜브", f"30자를 넘는 제목 후보 {len(long_t)}개")
        else:
            r.ok("제목 후보 3개, 모두 30자 이내")


def validate_doc(doc, mf=None, with_shorts=True):
    """대본 dict 를 검사해 Report 를 돌려준다. 다른 코드(script.py)가 불러 쓴다.

    with_shorts=False 는 **쇼츠를 만들기 전** 단계에서 쓴다.
    쇼츠는 대본이 완성된 뒤 5단계에서 만들어진다. 그 전에 "쇼츠 0편" 이라고
    오류를 내면, 그 단계에서는 절대 고칠 수 없는 오류를 고치라고 6만 토큰짜리
    재작성을 매번 시키게 된다 — 실제로 그 호출에서 연결이 끊겨 죽었다."""
    mf = mf or load_manifest()
    r = Report()
    check_structure(doc, r)
    check_assets(doc, mf, r)
    check_speaker(doc, r)
    check_plural(doc, r)
    check_dialogue(doc, r)
    check_timing(doc, r)
    check_text(doc, r)
    check_hook(doc, r)
    check_legal_ratio(doc, r)
    check_stakes(doc, r)
    check_flashback(doc, r)
    check_tags(doc, r)
    check_gfx_text(doc, r)
    check_blackout(doc, r)
    check_nametags(doc, r)
    check_anonymization(doc, r)
    check_amount_onscreen(doc, r)
    check_region(doc, r)
    check_criminal_words(doc, r)
    check_ages(doc, r)
    check_law(doc, r)
    if with_shorts:
        check_shorts(doc, r)
    check_youtube(doc, r)
    return r


def errors_as_text(r, limit=12):
    """검증 오류를 모델에게 돌려줄 문장으로 만든다."""
    if not r.errors:
        return ""
    lines = [f"- [{w}] {m}" for w, m in r.errors[:limit]]
    if len(r.errors) > limit:
        lines.append(f"- (그 외 {len(r.errors) - limit}건)")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("사용법: python3 src/validate_script.py <대본.json>")
        return 2
    path = Path(sys.argv[1])
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except FileNotFoundError:
        print(f"파일이 없다: {path}")
        return 2
    except json.JSONDecodeError as e:
        print(f"JSON 형식이 깨졌다: {e}")
        return 2

    print(f"검사 대상: {path}")
    print(f"사건: {doc.get('meta', {}).get('case_id')} · {doc.get('meta', {}).get('case_type')}")
    print()
    return validate_doc(doc).dump()


if __name__ == "__main__":
    sys.exit(main())
