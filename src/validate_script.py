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
    check_timing(doc, r)
    check_text(doc, r)
    check_hook(doc, r)
    check_legal_ratio(doc, r)
    check_stakes(doc, r)
    check_flashback(doc, r)
    check_tags(doc, r)
    check_blackout(doc, r)
    check_nametags(doc, r)
    check_anonymization(doc, r)
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
