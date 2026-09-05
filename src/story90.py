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

# ⭐ 기본 다섯 — 얼굴 그림(assets/cards/s90)이 있어 늘 같은 얼굴로 나온다
BASE_WHO = ("아내", "남편", "내연녀", "딸", "변호사")
WHO_OK = BASE_WHO + ("나레이션",)

# ⭐⭐⭐ 2026-09-04 — S91(상간자위자료)이 여기서 걸렸다.
#    AI 가 판결을 전할 사람으로 '법원' 을 썼는데 목록에 없어 대본 전체가
#    버려졌다(2,100원). 그리고 앞으로 장남·며느리·시어머니 사건이 오면
#    같은 일이 또 난다 — 다섯으로는 상속 이야기를 못 쓴다.
#    → 사건마다 **인물을 늘릴 수 있게** 한다. 늘릴 때는 나이대·성별을 함께
#      적게 해서, 얼굴 그림이 없어도 목소리를 제대로 골라 줄 수 있게 한다.
#    ⚠️ 사람이 아닌 것(법원·재판부·판사)은 화자로 못 쓴다 — 판결은 나레이션이
#      전한다. 이건 autofix() 가 0원으로 고쳐 준다.
AGES = ("10대", "20대", "30대", "40대", "50대", "60대", "70대")
SEXES = ("남", "여")
# 사람이 아니거나, 드라마에 세우면 안 되는 화자 → 나레이션으로 돌린다
NOT_PEOPLE = ("법원", "재판부", "판사", "법관", "검사", "기자", "앵커",
              "내레이션", "내래이션", "해설", "자막", "화면")
PEOPLE_MAX = 4          # 기본 다섯 말고 더 세울 수 있는 사람 수

# 한 편 글자 수 상한. 1자당 0.248초는 실측값이다(127초 영상 ÷ 513자).
#   225자 ≈ 55.8초 — 60초까지 4초쯤 여유를 둔다. 목소리는 매번 조금씩
#   달라지므로 상한에 딱 붙여 두면 어느 날 60초를 넘는다.
PART_CHARS = 225
# ⭐⭐⭐ 2026-09-05 손님: "영상이 너무 짧은데? 두편이야? 세 편 이상 나오게
#    해야지. 너무 빠르게 본론으로 들어가 버리니까 내용이 이해가 안 돼."
#    S91 을 재 보니 그대로였다 — 2편 15컷 389자. S90(3편 24컷 607자)보다
#    **36% 얇다.** 게다가 1편이 43초로 12초를 그냥 버렸다.
#    까닭은 셋이다.
#      ① 프롬프트가 "사건이 단순하면 2편" 이라고 **쉬운 길을 열어 줬다**
#      ② 상한(225자)만 있고 **하한이 없어** 짧게 써도 아무도 안 잡았다
#      ③ "말을 짧게 자르고 끝을 흐린다" 를 AI 가 **말줄임표 남발**로 풀었다
#         (S91 에 15개 · S90 은 5개). 글자 수만 먹고 뜻이 없다.
#    → 편을 늘리면 총 분량이 늘어난다: 2편 450자 → 4편 900자. 두 배 자세해진다.
#      게다가 편 하나가 업로드 하나라 피드 진입도 늘어난다.
PART_CHARS_MIN = 185             # 46초. 이보다 짧으면 쓸 수 있는 시간을 버린 것
SEC_PER_CHAR = 0.248
PART_MIN_CUTS, PART_MAX_CUTS = 8, 11
PARTS_MIN, PARTS_MAX = 3, 5      # 2편은 안 된다 (손님 지시)
ELLIPSIS_MAX = 3                 # 편당 말줄임표 — 넘으면 분량만 먹는다

# ⭐⭐⭐ 2026-09-05 손님: "단순히 짧아서 길게 늘리는 게 아니라, 이 이야기를
#    충분히 이해할 수 있게끔 나레이션이라던가 대사들로 조금 더 풍부하게.
#    극적으로 몰입을 할 수 있게 하는 게 목적이야."
#
#    맞는 지적이고, 내가 만든 것을 그 잣대로 보니 **거꾸로 되어 있었다.**
#    내가 넣은 못은 대부분 '분량 하한'(185자·3편·8컷)인데, 그것은 AI 에게
#    **"채워라"** 라고 시키는 것이다. 채우라고 하면 같은 말을 늘여 쓰거나
#    빈 대사("이거... 진짜야...?")를 더 넣는다 — 손님이 하지 말라신 바로 그것.
#
#    → 짧은 것은 **증상**이고 병은 **걸음이 빠진 것**이다. 그래서 아래 셋을
#      더 본다. 셋 다 '길이'가 아니라 '따라갈 수 있는가'를 재는 것이다.
#        ① 새 인물이 **말하기 전에 화면에 먼저** 나오는가
#           (S91 은 남편·내연녀가 얼굴 없이 목소리부터 나왔다)
#        ② 편마다 **맥락을 나르는 나레이션**이 있는가 (반응만으로는 못 따라간다)
#        ③ 같은 말을 **되풀이해 분량만 채우지** 않았는가
NARR_MIN_PER_PART = 3            # 편마다 맥락을 나르는 나레이션 최소 줄 수
# ⭐ 2026-09-04 — 아래 선이 26자였다. 그런데 S91 이 **25자** 하나로 통째로
#    버려졌고(2,100원), 더 나쁜 것은 이 채널에서 **가장 잘된 제목 셋이
#    22~24자**였다는 점이다. 검사가 검증된 길이를 막고 있었던 셈이다.
#    → 22자부터 통과. 프롬프트는 30~45자를 겨냥하라고 시키되(잘리는 자리를
#      고려한 값), 짧게 잘 뽑힌 것을 버리지는 않는다.
TITLE_MIN, TITLE_MAX = 22, 48
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


# ── ⭐⭐⭐ 자동 손보기 (0원) ──────────────────────────────────
#    2026-09-04 — S91 이 세 군데로 반려되며 2,100원이 통째로 날아갔다.
#    그중 둘은 **기계가 확실히 아는 잘못**이었다(사람 아닌 화자, 겹쳐 센 것).
#    이런 것까지 사람에게 물리면 손님이 단추를 또 눌러 2,100원을 더 쓰신다.
#    → 확실한 것만 여기서 조용히 고치고, 무엇을 고쳤는지 화면에 적어 드린다.
#    ⚠️ **애매한 것은 안 고친다.** 제목을 기계가 늘리면 밋밋해진다 —
#       그런 것은 되받아 고치기(repair)로 AI 에게 다시 시킨다.
# 화면 묘사(영어)에 이 말이 나오면 그 사람이 화면에 있다는 뜻이다.
# ⚠️ tools/build_short90.py 의 EN 과 짝이다 — 한쪽만 고치면 안 된다
#    (tools/pair_check.py 가 본다).
SCENE_EN = {"아내": "the wife", "남편": "the husband",
            "내연녀": "the mistress", "딸": "the daughter",
            "변호사": "the lawyer"}


def autofix(doc):
    log = []

    # ① 사람이 아닌 화자(법원·판사·해설…) → 나레이션으로 돌린다
    #    판결은 원래 나레이션이 전해야 한다. 드라마에 법원을 세우지 않는다.
    for c in doc.get("cuts") or []:
        turns = c.get("turns") or []
        for i, t in enumerate(turns):
            w = str((t or ["", ""])[0]).strip()
            if w in NOT_PEOPLE:
                turns[i] = ["나레이션", t[1]]
                log.append(f"컷{c.get('n')}: 화자 '{w}' → 나레이션")
        c["turns"] = turns
        # 화면에 세울 사람 목록에서도 뺀다 (나레이션은 화면에 안 세운다)
        who = [w for w in (c.get("who") or [])
               if w not in NOT_PEOPLE and w != "나레이션"]
        if who != (c.get("who") or []):
            c["who"] = who

    # ② 대본이 더 세운 사람 중 사람이 아닌 것은 목록에서 뺀다
    ppl = doc.get("people") or {}
    for nm in [k for k in ppl if str(k).strip() in NOT_PEOPLE]:
        ppl.pop(nm, None)
        log.append(f"사람 목록에서 '{nm}' 을(를) 뺐다")
    if ppl or "people" in doc:
        doc["people"] = ppl

    # ③ 화면에 세운 사람이 그 사건 사람 목록에 없으면 뺀다
    #    (그림에 못 넣을 뿐, 대사는 ①에서 이미 정리됐다)
    OK = set(who_ok(doc))
    for c in doc.get("cuts") or []:
        who = [w for w in (c.get("who") or []) if w in OK and w != "나레이션"]
        if who != (c.get("who") or []):
            gone = [w for w in (c.get("who") or []) if w not in who]
            if gone:
                log.append(f"컷{c.get('n')}: 화면에서 {', '.join(gone)} 을(를) 뺐다")
            c["who"] = who

    # ④ 화면 묘사에 사람이 있는데 who 가 비었으면 **그 사람을 세운다**
    #    ⭐⭐⭐ 2026-09-05 손님: "관련 없는 등장인물이 나오는 문제가 발생해."
    #    who 가 비면 얼굴 기준 그림을 안 붙인다 → 그림 모델이 **아무 얼굴이나**
    #    지어낸다. 그런데 화면 묘사가 "the wife hides a device" 처럼 사람을
    #    부르고 있으면, 낯선 사람이 그려지는 것이 당연하다.
    #    (실제로 S91 의 옛 대본 컷1 이 그랬다)
    for c in doc.get("cuts") or []:
        sc = str(c.get("scene") or "").lower()
        add = [k for k, en in SCENE_EN.items()
               if en in sc and k in who_ok(doc) and k not in (c.get("who") or [])]
        if add:
            c["who"] = (c.get("who") or []) + add
            log.append(f"컷{c.get('n')}: 화면 묘사에 나오는 "
                       f"{', '.join(add)} 을(를) 화면에 세웠다 "
                       f"(안 세우면 낯선 얼굴이 그려진다)")

    # ⑤ 격한 연기 지시를 눌러 담는다 (2026-09-04 에 넣은 것)
    log += cool_all(doc)
    return log


# ── ⭐⭐⭐ 나레이션은 **주어를 밝힌다** (2026-09-05 손님 지시) ──────
#    손님: "나레이션에서는 말 줄이지 말고 친절하게 풀어서 설명을 해.
#           불륜의 대가를 치렀다고 쓰는 거면 그 주체를 누가 치렀는지를
#           주어를 쓰고 그다음에 서술을 해야지.
#           '내연녀는 결국 불륜의 대가를 치렀습니다.' 가 맞잖아."
#    맞다. 주어를 빼면 **누구 이야기인지 모른 채** 결말만 듣게 된다.
#
#    ⚠️ 다만 **모든 문장에 주어를 요구하면 안 된다.** 「…소리였습니다」 처럼
#       무엇인지를 밝히는 문장(이다/였다)은 주어 없이도 자연스럽다.
#       → **동작·결과를 서술하는 문장**에만 주어를 요구한다.
SUBJ = re.compile(r"[가-힣]+(?:은|는|이|가)(?=\s|,|$)")
# 무엇인지를 밝히는 맺음 — 주어가 없어도 된다
COPULA = ("입니다", "였습니다", "이었습니다", "이다", "였다", "이었다",
          "겁니다", "것입니다", "뿐입니다")


def sentences(t):
    """한 줄을 문장으로 쪼갠다 (한 줄에 두 문장이 들어 있을 수 있다)."""
    return [x.strip() for x in re.split(r"(?<=[.?!])\s+", str(t or "")) if x.strip()]


def needs_subject(one):
    """이 문장이 **주어를 밝혀야 하는데 안 밝혔는가**."""
    t = one.strip()
    if len(re.sub(r"[^가-힣]", "", t)) < 6:      # 아주 짧은 말은 안 본다
        return False
    if t.rstrip(".!?").endswith(COPULA):         # 무엇인지를 밝히는 문장
        return False
    return not SUBJ.search(t + " ")


def people_of(doc):
    """그 사건에 나오는 사람들 — {이름: {age, sex}}. 기본 다섯도 넣어 준다."""
    out = {"아내": {"age": "50대", "sex": "여"},
           "남편": {"age": "50대", "sex": "남"},
           "내연녀": {"age": "30대", "sex": "여"},
           "딸": {"age": "20대", "sex": "여"},
           "변호사": {"age": "40대", "sex": "남"}}
    for name, v in (doc.get("people") or {}).items():
        nm = str(name).strip()
        if not nm or nm in out:
            continue
        out[nm] = {"age": str((v or {}).get("age") or "40대"),
                   "sex": str((v or {}).get("sex") or "여")}
    return out


def who_ok(doc):
    """그 대본에서 화자로 쓸 수 있는 이름들."""
    return tuple(people_of(doc)) + ("나레이션",)


def load(p, dflt):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:                                        # noqa: BLE001
        return dflt


def chars(c):
    """그 컷이 말하는 글자 수 (띄어쓰기·점 뺀 것). 길이를 재는 잣대다."""
    return sum(len(re.sub(r"[\s…·]", "", t)) for _, t in c["turns"])


def sid_for(case_id):
    """그 판례로 이미 지은 대본이 있으면 **그 번호를 다시 쓴다.**

    ⚠️⚠️ 2026-09-05 — 없으면 같은 사건으로 다시 지을 때마다 번호가 늘어난다.
       손님이 "대본이 얇다, 다시 지어" 하고 단추를 또 누르시면 S91 은 그대로
       남고 S92 가 새로 생겨, 한 사건이 목록에 둘로 뜬다.
    """
    for f in SERIES.glob("S*.story.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:                                    # noqa: BLE001
            continue
        if str(d.get("case_id") or "") == str(case_id):
            return f.name.split(".")[0].upper()
    return ""


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
    OK = who_ok(doc)                      # 기본 다섯 + 이 사건이 더 세운 사람
    extra = [w for w in people_of(doc) if w not in BASE_WHO]
    if len(extra) > PEOPLE_MAX:
        bad.append(f"사람을 {len(extra)}명 더 세웠다 — {PEOPLE_MAX}명까지다 "
                   f"({', '.join(extra)})")
    for nm in extra:
        v = people_of(doc)[nm]
        if v["age"] not in AGES or v["sex"] not in SEXES:
            bad.append(f"'{nm}' 의 나이대·성별이 이상하다 "
                       f"({v['age']}·{v['sex']}) — 나이대는 {AGES[0]}~{AGES[-1]}, "
                       f"성별은 남/여")
        if nm in NOT_PEOPLE:
            bad.append(f"'{nm}' 은(는) 화면에 세울 사람이 아니다 — "
                       f"판결·해설은 나레이션이 전한다")
    if not cuts:
        return ["컷이 하나도 없다"]
    # ⚠️ 편 수·글자 하한·말줄임표는 **새로 짓는 것**에만 건다. 이미 만들어 둔
    #    대본을 뒤늦게 규격 위반으로 만들면, 손대지도 않은 사건이 빨간불이 난다.
    if new and not (PARTS_MIN <= len(parts) <= PARTS_MAX):
        bad.append(f"편이 {len(parts)}개다 — {PARTS_MIN}~{PARTS_MAX}편이어야 한다 "
                   f"(편을 늘리면 그만큼 자세히 쓸 수 있다)")

    ns = [c.get("n") for c in cuts]
    if ns != list(range(1, len(cuts) + 1)):
        bad.append(f"컷 번호가 1부터 이어지지 않는다: {ns[:12]}")

    for c in cuts:
        n = c.get("n")
        turns = c.get("turns") or []
        if not turns or len(turns) > 2:
            bad.append(f"컷{n}: 대사 줄이 {len(turns)}개다 (1~2개여야 한다)")
        for w, t in turns:
            if w not in OK:
                bad.append(f"컷{n}: 모르는 사람 '{w}' (쓸 수 있는 것: "
                           f"{', '.join(OK)})")
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
        # ⚠️ 2026-09-04 — 예전에는 여기서 '모르는 사람' 을 **또** 셌다.
        #    한 잘못이 두 줄로 나와 "3군데" 처럼 보였다(실제로는 2군데).
        #    여기서는 **아는 사람인데 화면엔 못 세우는 경우**만 본다.
        for w in c.get("who") or []:
            if w == "나레이션":
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
        if new and not (PART_MIN_CUTS <= len(mine) <= PART_MAX_CUTS):
            bad.append(f"{no}편이 {len(mine)}컷이다 "
                       f"({PART_MIN_CUTS}~{PART_MAX_CUTS}컷이어야 한다 — "
                       f"컷이 적으면 이야기가 껑충 뛴다)")
        ch = sum(chars(c) for c in mine)
        if ch > PART_CHARS:
            bad.append(f"{no}편이 {ch}자({ch * SEC_PER_CHAR:.0f}초)다 — "
                       f"{PART_CHARS}자를 넘으면 쇼츠 피드가 안 태운다")
        # ⭐ 하한 — 짧게 써도 아무도 안 잡아서 1편이 43초로 나왔다(12초를 버렸다)
        if new and ch < PART_CHARS_MIN:
            # ⚠️ 이 말을 "글자를 채워라" 로 읽으면 안 된다. 짧은 것은 증상이고
            #    병은 **걸음이 빠진 것**이다. 늘릴 자리에는 빠진 걸음을 넣는다.
            bad.append(f"{no}편이 {ch}자({ch * SEC_PER_CHAR:.0f}초)뿐이다 — "
                       f"이야기가 껑충 뛰고 있다는 뜻이다. 같은 말을 늘여 쓰지 "
                       f"말고, 빠진 걸음(왜 그랬는지 · 그래서 어떻게 됐는지)을 "
                       f"컷으로 넣어 {PART_CHARS_MIN}자 이상으로 만들어라")
        # ⭐ 말줄임표는 분량만 먹고 뜻이 없다 ("이거... 진짜야...?")
        ell = sum(str(t).count("...") + str(t).count("…")
                  for c in mine for _, t in c["turns"])
        if new and ell > ELLIPSIS_MAX:
            bad.append(f"{no}편에 말줄임표가 {ell}개다 — {ELLIPSIS_MAX}개까지다. "
                       f"자리만 먹고 뜻은 안 나른다")
        # ⭐ 나레이션은 주어를 밝힌다 — 누구 이야기인지 모른 채 결말만
        #    듣게 되면 안 된다 (손님: "주어를 쓰고 그다음에 서술을 해야지")
        if new:
            for c in mine:
                for w, t in c["turns"]:
                    if w != "나레이션":
                        continue
                    for one in sentences(t):
                        if needs_subject(one):
                            bad.append(f"컷{c['n']} 나레이션에 주어가 없다 — "
                                       f"누가 그랬는지 밝혀라: 「{one[:26]}」")
        # ② 편마다 맥락을 나르는 나레이션이 있어야 한다. 반응(대사)만
        #    이어지면 보는 사람은 무슨 일이 왜 벌어졌는지 못 따라간다.
        nn = sum(1 for c in mine for w, _ in c["turns"] if w == "나레이션")
        if new and nn < NARR_MIN_PER_PART:
            bad.append(f"{no}편에 나레이션이 {nn}줄뿐이다 — {NARR_MIN_PER_PART}줄 "
                       f"이상 두어라. 무슨 일이 왜 벌어졌는지는 나레이션이 나른다")
        # ③ 편은 상황을 세우고 시작한다 (첫 컷이 반응이면 맥락 없이 튄다)
        if new and mine[0]["turns"][0][0] != "나레이션":
            bad.append(f"{no}편이 대사로 시작한다 — 첫 컷은 나레이션으로 "
                       f"'지금 어떤 상황인지'를 세워라")
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
    # ── ⭐ 새 인물은 **말하기 전에 화면에 먼저** 나와야 한다 ──────────
    #    S91 은 남편이 컷4, 내연녀가 컷7 에서 얼굴 한 번 없이 목소리부터
    #    나왔다. 보는 사람은 누가 말하는지 모른 채 대사를 듣는다.
    if new:
        met = set()
        # ⚠️ 그 사건 사람 목록에 아예 없는 이름은 위에서 이미 잡았다.
        #    여기서 또 세면 한 잘못이 두 줄로 나온다 (2026-09-04 에 같은
        #    실수를 한 번 고쳤다 — 되풀이하지 않는다).
        for c in cuts:
            for w, _ in (c.get("turns") or []):
                if w != "나레이션" and w in OK and w not in met:
                    bad.append(f"컷{c.get('n')}: '{w}' 가 화면에 한 번도 안 "
                               f"나온 채 말을 한다 — 말하기 전에 그 사람이 "
                               f"나오는 컷을 먼저 두어라")
                    met.add(w)                    # 한 번만 알린다
            for w in (c.get("who") or []):
                met.add(w)
            for w, _ in (c.get("turns") or []):
                met.add(w)

    # ── ⭐ 같은 말을 되풀이해 분량만 채우지 않았는가 ─────────────────
    #    ⚠️ 분량 하한(PART_CHARS_MIN)을 두면 AI 가 채우려 든다. 채우는 가장
    #       쉬운 길이 **같은 말 다시 쓰기**다. 그 길을 막아 둔다.
    if new:
        norm = {}
        for c in cuts:
            for _, t in (c.get("turns") or []):
                k = re.sub(r"[\s…·.,!?\"'\u2018\u2019\u201c\u201d]", "", str(t))
                if len(k) < 8:
                    continue
                if k in norm:
                    bad.append(f"컷{c.get('n')}: 컷{norm[k]} 과 같은 말을 다시 "
                               f"한다 — 분량은 빠진 걸음으로 채운다: {str(t)[:24]}")
                else:
                    norm[k] = c.get("n")

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


# ── ⭐⭐⭐ 되받아 고치기 ────────────────────────────────────────
#    2026-09-04 — 규격에 걸리면 대본을 통째로 버리고 있었다. S91 은 세 군데가
#    걸렸는데 그중 하나는 **제목이 25자, 통과선이 26자** — 딱 한 글자였다.
#    잘 쓴 대본을 한 글자 때문에 버리고 손님이 2,100원을 또 쓰시게 했다.
#    → 틀린 곳만 AI 에게 돌려주고 **그 자리만** 고쳐 받는다. 판결문을 다시
#      안 보내므로 한 번에 약 100~300원이다.
FIX_ROUNDS = 2          # 두 번까지만. 그래도 안 되면 사람이 봐야 할 일이다


def apply_fix(doc, fix):
    """AI 가 돌려준 '고친 자리' 를 대본에 끼워 넣는다. 무엇이 바뀌었는지 적어 준다."""
    log = []
    if not isinstance(fix, dict):
        return ["고친 것을 못 알아봤다 (JSON 이 아니다)"]

    for k in ("title", "series_label", "hook"):
        v = fix.get(k)
        if isinstance(v, str) and v.strip() and v.strip() != doc.get(k):
            doc[k] = v.strip()
            log.append(f"{k} → {v.strip()[:30]}")

    ppl = fix.get("people")
    if isinstance(ppl, dict):
        doc["people"] = {**(doc.get("people") or {}), **ppl}
        log.append("사람 목록을 고쳤다")

    by_no = {p.get("no"): p for p in (doc.get("parts") or [])}
    for one in (fix.get("parts") or []):
        tgt = by_no.get(one.get("no"))
        if not tgt:
            continue
        for k, v in one.items():
            if k == "no" or v in (None, "", []):
                continue
            tgt[k] = v
            log.append(f"{one['no']}편 {k} → {str(v)[:34]}")

    by_n = {c.get("n"): c for c in (doc.get("cuts") or [])}
    for one in (fix.get("cuts") or []):
        tgt = by_n.get(one.get("n"))
        if not tgt:
            continue
        for k, v in one.items():
            if k == "n" or v is None:
                continue
            if k == "turns":
                v = [list(t) for t in v]
            tgt[k] = v
            log.append(f"컷{one['n']} {k} 고침")
        tgt["sec"] = round(chars(tgt) / 4.6 + 1.2, 1)
    return log


# ── ⭐⭐⭐ 판결문 대조 (사실 검사) — 2026-09-05 손님 지시 ──────────
#    손님: "상간녀가 위자료를 더 높여 불렀다. 이거는 반대가 되는 거 아니야?
#           이런 부분들은 왜 사전에 그 검증을 못하는 거지?"
#
#    그때까지 대본 검사는 **규격만** 봤다 — 편 수·글자 수·컷 수·화자·주어.
#    "이 말이 판결문과 맞는가" 를 보는 검사는 한 개도 없었다. 판결문은 저장돼
#    있는데 대본을 지은 뒤 아무도 다시 안 봤다. 그래서 S91 컷18 이
#    「여자는 사생활 침해라며 위자료를 더 올려 불렀습니다」 로 나갔다.
#    (실제는 상간녀가 **반소로 3,000만 원을 청구**했고 50만 원만 인정됐다)
#
# ⚠️ 각색을 트집 잡으면 안 된다. 지어낸 대사·장면은 이 채널의 본업이다.
#    잡는 것은 **사실이 뒤집힌 것**뿐이다 (프롬프트에 그렇게 적어 두었다).
def factcheck(llm, doc, row):
    """대본이 판결문과 어긋나는지 본다. 규격이 아니라 **사실**을 본다.

    돌려주는 것: (반려 사유 목록, AI 가 제안한 고칠 말 {컷번호: 새 줄})
    ⚠️ 이 검사가 죽어도 대본 짓기 전체를 죽이면 안 된다 — 그때는 빈 손으로
       돌아와 규격 검사만 하고 넘어간다 (값 2,100원을 날리지 않는다).
    """
    body = prompts.build("story90_fact",
                         CASE_JSON=case_json(row),
                         SCRIPT=json.dumps(doc, ensure_ascii=False, indent=1))
    out = llm.json(body, tier="pro", max_output_tokens=4096, temperature=0.2,
                   label="판결문 대조", effort="low")
    why, tip = [], {}
    for one in (out or {}).get("wrong") or []:
        try:
            n = int(one.get("n"))
        except Exception:                                    # noqa: BLE001
            continue
        what = str(one.get("무엇이틀렸나") or "").strip()
        real = str(one.get("판결문은") or "").strip()
        if not what:
            continue
        why.append(f"컷{n} 판결문과 다르다 — {what} (판결문: {real})")
        fix = str(one.get("이렇게") or "").strip()
        if fix:
            tip[n] = fix
    return why, tip


def repair(llm, doc, bad, row=None):
    """틀린 곳만 AI 에게 돌려주고 고쳐 받는다. (고친 내역, 남은 잘못)

    ⚠️ 2026-09-05 — 판결문과 어긋난 곳을 고치려면 **판결문을 같이 줘야** 한다.
       규격만 고칠 때는 안 줬는데(값을 아끼려고), 사실을 고치는 데는 필요하다.
    """
    body = prompts.build(
        "story90_fix",
        CASE=(case_json(row) if row else "(판결문 없음 — 규격만 고치는 중이다)"),
        BAD="\n".join("· " + b for b in bad[:20]),
        DOC=json.dumps(doc, ensure_ascii=False, indent=1))
    fix = llm.json(body, tier="pro", max_output_tokens=8192, temperature=0.6,
                   label="대본 고치기", effort="low")
    log = apply_fix(doc, fix)
    log += autofix(doc)                      # 고친 자리도 다시 손본다 (0원)
    return log, check(doc)


def apply_tip(doc, tip):
    """판결문 대조가 알려 준 **그 자리에 넣을 한 줄**을 0원으로 끼워 넣는다.

    ⚠️ 나레이션 줄만 바꾼다. 두 사람이 주고받는 대사 컷은 어느 줄인지가
       애매해서 AI 에게 되묻는 쪽이 안전하다.
    ⚠️ 넣은 뒤 규격을 다시 본다 — 길어져서 편이 60초를 넘으면 안 된다.
    """
    log = []
    by_n = {c.get("n"): c for c in (doc.get("cuts") or [])}
    for n, line in (tip or {}).items():
        c = by_n.get(n)
        if not c or len(c.get("turns") or []) != 1:
            continue
        was = c["turns"][0][1]
        c["turns"][0][1] = line
        c["sec"] = round(chars(c) / 4.6 + 1.2, 1)
        log.append(f"컷{n}: 「{was[:22]}」 → 「{line[:22]}」")
    return log


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


# ⭐ 화면이 결과를 읽을 자리. 워크플로가 **실패해도** 이 파일을 저장소에
#    올린다 — 관리자 페이지는 이것만 읽으면 무엇이 어떻게 됐는지 안다.
#    (2026-09-04 손님: "왜 아무것도 안떠?" — 실패를 알릴 길이 아예 없었다)
REPORT = ROOT / "state" / "story_last.json"


def report(**kw):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    kw.setdefault("at", __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    REPORT.write_text(json.dumps(kw, ensure_ascii=False, indent=1) + "\n",
                      encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="", help="판례 번호 (비우면 점수 1등)")
    ap.add_argument("--sid", default="", help="사건 번호 (비우면 다음 번호)")
    a = ap.parse_args()

    row = pick_case(a.case or None)
    # ⭐ 같은 판례로 다시 지으면 **그 번호를 다시 쓴다** (목록에 둘로 안 뜨게)
    again = sid_for(row["case_id"])
    sid = (a.sid or again or next_sid()).upper()
    if again and not a.sid:
        print(f"■ 이 판례로 지은 대본({again})이 이미 있습니다 — 다시 짓습니다")
    name = str(row.get("one_line") or "")[:70]
    print(f"■ {sid} 대본 짓는 중 — 판례 {row['case_id']} · "
          f"{row.get('case_type', '')}")
    print(f"  {name}")
    report(sid=sid, case_id=str(row["case_id"]), name=name,
           state="짓는 중", why=[], krw=0)

    # ⚠️ 부를 수 있는 횟수 — 짓기 1 + 판결문 대조 1 + 되받아 고치기 2 + 여유 2
    llm, _who = claude.writer(max_calls=6, prefer="gemini")

    def spent():
        try:
            return round(float(llm.spent_krw() or 0))
        except Exception:                                    # noqa: BLE001
            return 0

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

    # ── ① 자동 손보기 (0원) ────────────────────────────────────
    fixed = autofix(doc)
    if fixed:
        print(f"\n■ 기계가 손봤다 ({len(fixed)}군데) — 값 0원")
        for line in fixed[:10]:
            print(f"  · {line}")

    # ── ①-2 판결문과 대조한다 (사실 검사 · 약 30~80원) ─────────
    #    ⭐⭐⭐ 2026-09-05 손님: "이런 부분들은 왜 사전에 그 검증을 못하는 거지?"
    #    규격만 보던 검사에 **사실**을 보는 눈을 붙인다.
    tip = {}
    try:
        why, tip = factcheck(llm, doc, row)
        if why:
            print(f"\n■ 판결문과 어긋난 곳 {len(why)}군데 (약 30~80원)")
            for w in why[:10]:
                print(f"  · {w}")
            moved = apply_tip(doc, tip)      # 알려 준 줄은 0원으로 넣는다
            for m in moved:
                print(f"    → {m}")
        else:
            print("\n■ 판결문과 어긋난 곳 없음 (약 30~80원)")
    except Exception as e:                                   # noqa: BLE001
        # ⚠️ 이 검사가 죽어도 2,100원짜리 대본을 날리면 안 된다
        print(f"\n⚠️ 판결문 대조를 못 했다: {e} — 규격 검사만 하고 갑니다")

    # ── ② 검사 → ③ 걸리면 되받아 고치기 (최대 두 번) ───────────
    bad = check(doc)
    for r in range(1, FIX_ROUNDS + 1):
        if not bad:
            break
        print(f"\n■ 규격에 안 맞는 곳 {len(bad)}군데 — AI 에게 그 자리만 "
              f"고쳐 달라고 한다 ({r}/{FIX_ROUNDS}번째 · 약 100~300원)")
        for b in bad[:10]:
            print(f"  · {b}")
        try:
            log, bad = repair(llm, doc, bad, row)
        except Exception as e:                               # noqa: BLE001
            print(f"  ⚠️ 고치기를 못 했다: {e}")
            break
        for line in log[:10]:
            print(f"    → {line}")

    # ── ④ 그래도 안 되면: 받은 것을 남기고 까닭을 적는다 ────────
    if bad:
        broken = SERIES / f"{sid}.broken.json"
        broken.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")
        print(f"\n❌ 아직 {len(bad)}군데가 안 맞는다 — 저장하지 않았다 "
              f"(값 약 {spent():,}원)")
        for b in bad[:20]:
            print(f"  · {b}")
        print(f"  (받은 대본은 {broken.name} 에 남겨 뒀습니다 — 버리지 않았습니다)")
        report(sid=sid, case_id=str(row["case_id"]), name=name,
               state="실패", why=bad[:20], krw=spent(),
               broken=f"data/series/{broken.name}")
        return 1

    out = SERIES / f"{sid}.story.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8")
    summary(doc)
    print(f"\n✅ {out.relative_to(ROOT)} (값 약 {spent():,}원)")
    report(sid=sid, case_id=str(row["case_id"]), name=name,
           state="됨", why=[], krw=spent(),
           title=doc.get("title"), parts=len(doc.get("parts") or []),
           cuts=len(doc.get("cuts") or []))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
