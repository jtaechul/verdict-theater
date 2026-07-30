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

ROOT = Path(__file__).resolve().parent.parent

# 막 이름 → (시작초, 끝초). CLAUDE.md "7. 대본 구조"
ACT_WINDOW = {
    "hook": (0, 22),
    "act1": (22, 200),
    "act2": (200, 370),
    "act3": (370, 520),
    "act4": (520, 670),
    "act5": (670, 720),
}

MAX_CUT_SEC = 7.0
MAX_TEXT_LEN = 45
CUT_MIN, CUT_MAX = 100, 115
RUNTIME, RUNTIME_TOL = 720, 10
ACT_TOL = 5
SHORT_MIN, SHORT_MAX = 35.0, 50.0


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


def check_stakes(doc, r):
    """30초 관문 — 22~50초 안에 '무엇이 걸려 있는지'가 나와야 한다.

    도입 훅(0~22초)에는 금액을 밝히면 안 되고, 1막 첫머리에는 반드시 밝혀야 한다.
    이 둘을 혼동해 금액을 4막까지 미루면 시청자가 30초에서 이탈한다."""
    t = 0.0
    hook_amount = None
    stakes_at = None
    for act, cut in all_cuts(doc):
        has_amount = ("억" in (cut.get("text") or "")) or \
                     ((cut.get("gfx") or {}).get("type") == "amount")
        if has_amount:
            if t < 22 and hook_amount is None:
                hook_amount = (t, cut.get("id"))
            elif t >= 22 and stakes_at is None:
                stakes_at = (t, cut.get("id"))
        t += float(cut.get("sec", 0))

    if hook_amount:
        r.error("3초 관문", f"도입 22초 안에 금액이 나온다 ({hook_amount[1]}) — 볼 이유가 사라진다")
    if stakes_at is None:
        r.error("30초 관문", "걸린 것(재산의 크기)이 대본 어디에도 없다")
    elif stakes_at[0] > 50:
        r.error("30초 관문", f"걸린 것이 {stakes_at[0]:.1f}초에야 나온다 ({stakes_at[1]}) — 50초 이내여야 한다")
    else:
        r.ok(f"걸린 것이 {stakes_at[0]:.1f}초에 제시됨 ({stakes_at[1]})")


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

    mf = load_manifest()
    r = Report()

    print(f"검사 대상: {path}")
    print(f"사건: {doc.get('meta', {}).get('case_id')} · {doc.get('meta', {}).get('case_type')}")
    print()

    check_structure(doc, r)
    check_assets(doc, mf, r)
    check_timing(doc, r)
    check_text(doc, r)
    check_hook(doc, r)
    check_stakes(doc, r)
    check_blackout(doc, r)
    check_nametags(doc, r)
    check_anonymization(doc, r)
    check_law(doc, r)
    check_shorts(doc, r)
    check_youtube(doc, r)

    return r.dump()


if __name__ == "__main__":
    sys.exit(main())
