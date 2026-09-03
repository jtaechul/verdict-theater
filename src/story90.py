#!/usr/bin/env python3
"""⭐ 재판 기록 한 건 → **쇼츠 시리즈 대본** (data/series/<SID>.story.json)

    python3 src/story90.py --case 230761
    python3 src/story90.py                (대기열에서 점수가 제일 높은 것)

⭐⭐⭐ 2026-09-01 손님: "앞으로 영상을 계속 만들어나가고 계속 올려야 되는데
   이런 식으로 관리자 페이지를 구성하면 지속 가능하지 않거든."

   맞다. 그때까지 90초 대본은 **사람이 손으로 쓴 파이썬 파일**이었다.
   손님은 파이썬을 못 쓰시니, 사건 2번째를 혼자서는 시작조차 못 하셨다.
   심사를 통과한 재판 기록이 165건이나 쌓여 있는데 길이 없었던 것이다.
   → 이 파일이 그 길이다. 단추 한 번이면 대본이 나온다.

⚠️ 값이 나가는 일이다(대본 한 편 약 2,100원). 그래서 **단추로만** 돈다.

⚠️⚠️ 받은 것을 그대로 믿지 않는다. 아래 check() 가 규격을 다 본다 —
   특히 **편당 글자 수**. 210자를 넘으면 55초를 넘고, 55초를 넘으면
   유튜브 쇼츠 피드가 안 태운다(2026-09-01 에 실제로 겪었다: 60초 이하
   6편은 전부 1,200회 넘게 나왔는데 127초 한 편은 0회였다).
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import claude                                                # noqa: E402
import prompts                                               # noqa: E402
import shortstate                                            # noqa: E402

QUEUE = ROOT / "state" / "queue.json"
CASES = ROOT / "data" / "cases"
SERIES = ROOT / "data" / "series"

# 사람은 관계로만 부른다 — 인물 카드(assets/cards/s90)에 있는 다섯이 전부다
WHO_OK = ("아내", "남편", "내연녀", "딸", "변호사", "나레이션")

# 한 편 글자 수 상한. 1자당 0.248초는 실측값이다(127초 영상 ÷ 513자).
#   225자 ≈ 55.8초 — 60초까지 4초쯤 여유를 둔다. 목소리는 매번 조금씩
#   달라지므로 상한에 딱 붙여 두면 어느 날 60초를 넘는다.
PART_CHARS = 225
SEC_PER_CHAR = 0.248
PART_MIN_CUTS, PART_MAX_CUTS = 6, 10
TITLE_MIN, TITLE_MAX = 26, 48
CARD_MAX = 16
LABEL_MAX = 12

# 상표가 딸려 나오는 말 — 화면 묘사에 쓰면 실제 로고가 그려져 나온다
BRANDED = ("bank statement", "letterhead", "bank logo", "business card",
           "branded", "brand name", "receipt from", "credit card",
           "id card", "passport", "newspaper front page")


# ── ⭐⭐⭐ 2026-09-04 손님: "대사 목소리 감정이 너무 격하게 표현되지
#    않도록 코드에도 반영해줘." ────────────────────────────────────
#
#    기계 목소리는 "세게 읽어라" 하면 연기가 되는 게 아니라 **소리만 커진다.**
#    그러면 싸구려 더빙처럼 들린다. 한국 드라마의 싸움은 내지르지 않는다 —
#    낮게, 조용하게, 그래서 더 서늘하다.
#
#    막는 자리를 **두 겹**으로 둔다.
#      ① prompts/story90_gen.md 가 애초에 그렇게 쓰라고 시킨다 (예방)
#      ② 그래도 격한 말이 오면 여기서 **조용한 말로 바꿔 끼운다** (수선 · 0원)
#    ②가 있어야 하는 까닭: 대본 한 편이 약 2,100원이다. 격한 말 하나 때문에
#    통째로 물리면 손님이 단추를 또 눌러 2,100원을 더 쓰셔야 한다.
#    바꿔 끼우는 것은 0원이고, 무엇을 바꿨는지 화면에 적어 드린다.
HOT = [
    # ⚠️ 말끝은 여러 가지로 온다 — 듯 / 며 / 면서 / 고. 하나만 적으면
    #    "소리치듯" 은 잡고 "소리치며" 는 그대로 지나간다(실제로 겪었다).
    (r"목소리가\s*확?\s*올라가(?:며|고|면서|는)", "목소리를 낮게 눌러"),
    (r"목소리를\s*(?:확\s*)?높(?:여|이며|이면서|이고)", "목소리를 낮게 눌러"),
    (r"(?:분노|감정|울분|화)(?:가|이)?\s*터져\s*나오(?:듯|며|면서|고)",
     "속으로 삼키듯"),
    (r"터뜨리(?:듯|며|면서)|폭발하(?:듯|며|면서)", "속으로 삼키듯"),
    (r"(?:소리치|내지르|악을\s*쓰|울부짖|절규하|오열하)(?:듯|며|면서|고|으며|으면서)",
     "낮게 눌러 말하듯"),
    (r"비명을?\s*지르(?:듯|며|면서)", "숨을 삼키듯"),
    (r"이를\s*악물(?:고|며|면서)", "턱에 힘을 준 채"),
    (r"서슬\s*퍼렇게", "서늘하게"),
    (r"몰아붙이(?:며|면서|고)", "차분하게"),
    (r"몰아붙이듯", "차분히 짚어 가듯"),
    (r"쏘아붙이(?:듯|며|면서|고)", "짧게 끊어 말하듯"),
    (r"다그치(?:듯|며|면서|고)", "조용히 되묻듯"),
    (r"날카롭게|앙칼지게", "조용하고 단단하게"),
    (r"격앙되어|격정적으로|격하게", "담담하게"),
    (r"끝을\s*떨(?:면서|며|고)\s*힘겹게", "말끝이 조금 흔들리게"),
    (r"(?<![가-힣])세게(?![가-힣])|(?<![가-힣])강하게(?![가-힣])", "또렷하게"),
]


def soften(say):
    """연기 지시 한 줄에서 **격한 말을 조용한 말로** 바꿔 끼운다.

    바꾼 것이 있으면 (바뀐 줄, 바꾼 내역) 을 돌려준다. 0원.
    """
    out, hit = str(say or ""), []
    for pat, calm in HOT:
        m = re.search(pat, out)
        if m:
            hit.append(f"{m.group(0)} → {calm}")
            out = re.sub(pat, calm, out)
    # ⚠️ 한 줄에 격한 말이 둘이면 같은 조용한 말이 두 번 들어간다
    #    ("낮게 눌러 말하듯 낮게 눌러 말하듯"). 뒤엣것을 지운다.
    for _, calm in HOT:
        while out.count(calm) > 1:
            i = out.index(calm, out.index(calm) + len(calm))
            out = out[:i] + out[i + len(calm):]
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s*,\s*(?=,|$)", "", out).strip(" ,")
    return out, hit


def cool_all(doc):
    """대본 전체의 연기 지시를 훑어 격한 말을 눌러 준다."""
    log = []
    for c in doc.get("cuts") or []:
        says = c.get("say") or []
        for i, one in enumerate(says):
            new, hit = soften(one)
            if hit:
                says[i] = new
                log.append(f"컷{c.get('n')}: " + " · ".join(hit))
        c["say"] = says
    return log


def too_hot(say):
    """아직도 격한 말이 남아 있으면 그 말을 돌려준다 (없으면 '')."""
    for pat, _ in HOT:
        m = re.search(pat, str(say or ""))
        if m:
            return m.group(0)
    return ""


def load(p, dflt):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return dflt


def chars(c):
    """그 컷이 말하는 글자 수 (띄어쓰기·점 뺀 것). 길이를 재는 잣대다."""
    return sum(len(re.sub(r"[\s…·]", "", t)) for _, t in c["turns"])


def next_sid():
    """다음 사건 번호. 이미 있는 대본을 덮어쓰지 않는다."""
    n = 0
    for f in SERIES.glob("S*.story.json"):
        m = re.fullmatch(r"S(\d+)", f.name.split(".")[0])
        if m:
            n = max(n, int(m.group(1)))
    # ⚠️ 옛 16화 시리즈(S001…)와 번호가 겹치면 안 된다. 쇼츠는 S90 부터 센다.
    return f"S{max(n, 89) + 1}"


def pick_case(case_id=None):
    q = load(QUEUE, [])
    if case_id:
        row = next((c for c in q if str(c.get("case_id")) == str(case_id)), None)
        if not row:
            raise SystemExit(f"❌ 대기열에 그 판례가 없다: {case_id}")
        return row
    used = {v.get("case_id") for v in shortstate.load().values()}
    ready = [c for c in q if c.get("gate_pass") and c["case_id"] not in used]
    ready.sort(key=lambda c: (c.get("gate_score") or 0,
                              c.get("machine_score") or 0), reverse=True)
    if not ready:
        raise SystemExit("❌ 쓸 판례가 없다. [1. 재판 기록 모으기] 를 먼저 돌려라")
    return ready[0]


def case_json(row):
    """판결문 본문 + 심사가 찾아 둔 힌트를 프롬프트에 넣을 꼴로."""
    body = load(CASES / f"{row['case_id']}.json", {})
    keep = ["사건명", "선고일자", "사건종류명", "판시사항", "판결요지", "판례내용"]
    d = {k: body.get(k, "") for k in keep}
    if len(d.get("판례내용") or "") > 60000:
        d["판례내용"] = d["판례내용"][:60000] + "\n\n…(이하 생략)"
    d["_한줄요약"] = row.get("one_line", "")
    d["_반전"] = row.get("twist_hint", "")
    d["_사건유형"] = row.get("case_type", "")
    d["_피해자"] = row.get("victim", "")
    d["_가해자"] = row.get("villain", "")
    d["_금액"] = row.get("amount_label", "")
    return json.dumps(d, ensure_ascii=False, indent=2)


def check(doc, new=True):
    """규격 검사. `new=False` 면 **이미 만들어 둔 대본**을 보는 것이다.

    ⚠️ 연기 지시(say)가 격한지 보는 못은 `new=True` 일 때만 박는다.
       이미 만든 대본은 그 지시로 **목소리가 이미 나와 있다.** 지시를 고치면
       지문이 달라져 스무 줄을 다시 만들게 되는데, 값이 들 뿐 아니라 이미
       올라간 편과 소리가 달라진다. 손님도 "**다음번부터**" 라고 하셨다
       (2026-09-04). 그래서 옛 대본은 그대로 두고, 새로 짓는 것부터 막는다.
    """
    bad = []
    cuts = doc.get("cuts") or []
    parts = doc.get("parts") or []
    if not cuts:
        return ["컷이 하나도 없다"]
    if not (2 <= len(parts) <= 4):
        bad.append(f"편이 {len(parts)}개다 — 2~4편이어야 한다")

    ns = [c.get("n") for c in cuts]
    if ns != list(range(1, len(cuts) + 1)):
        bad.append(f"컷 번호가 1부터 이어지지 않는다: {ns[:12]}")

    for c in cuts:
        n = c.get("n")
        turns = c.get("turns") or []
        if not turns or len(turns) > 2:
            bad.append(f"컷{n}: 대사 줄이 {len(turns)}개다 (1~2개여야 한다)")
        for w, t in turns:
            if w not in WHO_OK:
                bad.append(f"컷{n}: 모르는 사람 '{w}' (쓸 수 있는 것: "
                           f"{', '.join(WHO_OK)})")
            if not str(t).strip():
                bad.append(f"컷{n}: 빈 대사")
        say = c.get("say") or []
        if len(say) != len(turns) or any(not str(x).strip() for x in say):
            bad.append(f"컷{n}: 연기 지시(say)가 대사 줄 수와 안 맞는다")
        # ⭐ 감정을 격하게 시키는 말이 남아 있으면 안 된다 (cool_all 이 눌러 준다)
        for one in (say if new else []):
            hot = too_hot(one)
            if hot:
                bad.append(f"컷{n}: 연기 지시가 너무 격하다 — '{hot}' "
                           f"(감정은 속으로 눌러 담는 말로 적는다)")
        sc = str(c.get("scene") or "")
        if not sc.strip():
            bad.append(f"컷{n}: 화면 묘사(scene)가 비었다")
        # ⚠️ 규칙은 "그 말을 절대 쓰지 마라" 가 아니다. **쓰려면 뒷감당을 해라** 다.
        #    그림을 다시 그리면 132원이 나가지만, 정해 둔 자리를 흐리게 가리면
        #    0원이다(그 컷에 scrub 을 적어 두면 된다). 둘 중 하나도 안 하고
        #    넘어가는 것만 막는다.
        if not (c.get("scrub") or {}).get("box"):
            for w in BRANDED:
                if w in sc.lower():
                    bad.append(f"컷{n}: 화면 묘사에 '{w}' — 실제 상표가 그려져 "
                               f"나온다 (말을 바꾸거나 그 컷에 scrub 을 적는다)")
        for w in c.get("who") or []:
            if w not in WHO_OK or w == "나레이션":
                bad.append(f"컷{n}: 화면에 못 넣는 사람 '{w}'")

    seen = []
    for p in parts:
        a, b = (p.get("cuts") or [0, 0])[:2]
        mine = [c for c in cuts if a <= c["n"] <= b]
        seen += [c["n"] for c in mine]
        no = p.get("no")
        if not mine:
            bad.append(f"{no}편에 컷이 없다")
            continue
        if not (PART_MIN_CUTS <= len(mine) <= PART_MAX_CUTS):
            bad.append(f"{no}편이 {len(mine)}컷이다 "
                       f"({PART_MIN_CUTS}~{PART_MAX_CUTS}컷이어야 한다)")
        ch = sum(chars(c) for c in mine)
        if ch > PART_CHARS:
            bad.append(f"{no}편이 {ch}자({ch * SEC_PER_CHAR:.0f}초)다 — "
                       f"{PART_CHARS}자를 넘으면 쇼츠 피드가 안 태운다")
        t = str(p.get("yt_title") or "")
        if not (TITLE_MIN <= len(t) <= TITLE_MAX):
            bad.append(f"{no}편 제목이 {len(t)}자다 "
                       f"({TITLE_MIN}~{TITLE_MAX}자여야 한다): {t[:30]}")
        if re.search(r"\d\s*편", t):
            bad.append(f"{no}편 제목에 편 번호가 들어 있다 — "
                       f"보는 사람이 '1편부터 봐야 하나' 하고 넘긴다")
        card = p.get("card") or []
        if len(card) != 2:
            bad.append(f"{no}편 화면 제목(card)이 {len(card)}줄이다 (2줄이어야 한다)")
        for x in card:
            if len(str(x)) > CARD_MAX:
                bad.append(f"{no}편 화면 제목이 {len(str(x))}자다 "
                           f"({CARD_MAX}자 이내여야 한다): {x}")
    if sorted(seen) != sorted(ns):
        miss = sorted(set(ns) - set(seen))
        bad.append(f"편 나누기가 컷을 놓쳤다 — 빠진 컷 {miss}")

    if len(str(doc.get("series_label") or "")) > LABEL_MAX:
        bad.append(f"series_label 이 {len(doc['series_label'])}자다 "
                   f"({LABEL_MAX}자 이내)")
    for k in ("title", "series_label", "hook"):
        if not str(doc.get(k) or "").strip():
            bad.append(f"{k} 가 비었다")
    return bad


def summary(doc):
    print(f"\n■ 「{doc['title']}」 — {doc['series_label']} · "
          f"{len(doc['cuts'])}컷 · {len(doc['parts'])}편")
    for p in doc["parts"]:
        a, b = p["cuts"]
        mine = [c for c in doc["cuts"] if a <= c["n"] <= b]
        ch = sum(chars(c) for c in mine)
        print(f"\n  ── {p['no']}편 · 컷{a}~{b} ({len(mine)}컷 · {ch}자 · "
              f"약 {ch * SEC_PER_CHAR:.0f}초)")
        print(f"     제목: {p['yt_title']} ({len(p['yt_title'])}자)")
        print(f"     화면: {p['card'][0]} / {p['card'][1]}")
        for c in mine:
            who = c["turns"][0][0]
            print(f"     {c['n']:>2} [{who:<4}] {c['turns'][0][1][:34]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="", help="판례 번호 (비우면 점수 1등)")
    ap.add_argument("--sid", default="", help="사건 번호 (비우면 다음 번호)")
    a = ap.parse_args()

    row = pick_case(a.case or None)
    sid = (a.sid or next_sid()).upper()
    print(f"■ {sid} 대본 짓는 중 — 판례 {row['case_id']} · "
          f"{row.get('case_type', '')}")
    print(f"  {row.get('one_line', '')[:70]}")

    llm, _who = claude.writer(max_calls=4, prefer="gemini")
    body = prompts.build("story90_gen", CASE_JSON=case_json(row))
    doc = llm.json(body, tier="pro", max_output_tokens=32768, temperature=0.85,
                   label="쇼츠 대본", effort="high")

    doc["sid"] = sid
    doc["case_id"] = str(row["case_id"])
    doc["narr"] = ("사건을 전하는 낮고 묵직한 목소리로, "
                   "쇼츠 속도에 맞춰 담담하고 또렷하게")
    # 최소 길이는 글자 수로 다시 잡는다 — 모델이 적어 준 값은 못 믿는다
    for c in doc.get("cuts") or []:
        c["turns"] = [list(t) for t in c["turns"]]
        c["who"] = list(c.get("who") or [])
        c["sec"] = round(chars(c) / 4.6 + 1.2, 1)

    # ⭐ 검사하기 **전에** 격한 연기 지시를 눌러 준다. 0원이고, 여기서
    #    안 눌러 주면 대본 한 편(2,100원)을 통째로 물리게 된다.
    cooled = cool_all(doc)
    if cooled:
        print(f"\n■ 연기 지시를 눌러 담았다 ({len(cooled)}줄) — 값 0원")
        for line in cooled[:8]:
            print(f"  · {line}")

    bad = check(doc)
    if bad:
        broken = SERIES / f"{sid}.broken.json"
        broken.write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                          encoding="utf-8")
        print(f"\n❌ 규격에 안 맞는 곳 {len(bad)}군데 — 저장하지 않았다")
        for b in bad[:20]:
            print(f"  · {b}")
        print(f"  (받은 것은 {broken.name} 에 남겨 뒀다)")
        return 1

    out = SERIES / f"{sid}.story.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    summary(doc)
    print(f"\n✅ {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
