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


def check(doc):
    """규격에 맞는지 다 본다. 한 군데라도 어긋나면 저장하지 않는다."""
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
