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
DIA_MAX = 24
SUB_MAX = 30           # 자막은 대사를 담아야 하므로 대사보다 짧으면 안 된다

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


AVOID_FIX = ("Avoid: on-screen text, signage, documents with visible writing, "
             "screens, extra people in focus.")


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


def soft(doc):
    """버릴 것까진 아니지만 사람이 한 번 봐야 할 곳."""
    out = []
    for e in doc.get("episodes") or []:
        for c in e.get("cuts") or []:
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

            # 한국어 대사 길이 (6초에 18자 넘게는 안 들어간다)
            for line in p.split("\n"):
                if line.startswith("DIALOGUE:"):
                    for say in re.findall(r'"([^"]*)"', line):
                        if len(say) > DIA_MAX:
                            bad.append(f"{tag}: 대사가 {len(say)}자다 "
                                       f"({DIA_MAX}자 이내) — {say}")
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
    doc = llm.json(body, tier="pro", max_output_tokens=32768, temperature=0.85,
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
    state[sid] = {"case_id": row["case_id"], "title": doc.get("title", ""),
                  "episodes": EPISODES, "made": 0, "writer": who}
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n✅ {sid}.json 저장 — 매일 한 화씩 30초 영상을 만들면 된다")
    for w in soft(doc):
        print(f"  ⚠️ 손볼 곳 — {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
