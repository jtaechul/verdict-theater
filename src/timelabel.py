"""회상 시점 자막(`flashback_label`)이 **그림과 어긋나지 않게** 막는다. 값 0원.

왜 (2026-08-09 손님 지적 · 화면 사진과 함께)
    "아버지 생전 문구가 나오는데 실제 이야기는 생전이 아닌 경우가 많아.
     생전이라고 할 거면 그 나이대에 맞춰서 캐릭터들도 젊은 캐릭터로 바뀌고
     나이도 바뀌어야 될 거 같아. 만약 그렇지 않은 상황이라면 생전이라는 문구
     표현은 들어가면 안돼. (다만 누구누구 시점. 경우에는 거는 활용해도 괜찮아.)"

무엇이 문제였나 (EP001 실측 — 네 자리 전부 어긋나 있었다)
    A1-01  '오십 년 전'      ↔ 화면에는 72세 이정임 (오십 년 전이면 22세)
    A1-08  '아버지 생전'     ↔ 화면에는 50세 김성일 (지금 모습 그대로)
    A1-15  '형제가 자라던 때' ↔ 화면에는 48세 김성훈 (다 큰 어른)
    A2-09  '아버지 생전'     ↔ 화면에는 50세 김성일 (지금 모습 그대로)
    인물 그림은 **한 나이만** 있다(젊은 시절 그림이 없다). 그런데 자막만
    "그때" 라고 못 박으니, 보는 사람 눈에는 글자와 그림이 따로 논다.

어떻게 고치나
    시점 자막이 **시대를 못 박지 않게** 한다. 대신 손님이 괜찮다고 하신
    '누구누구 시점' 꼴로 쓴다 — "김성일 씨의 기억".
    이러면 과거라는 것은 그대로 전해지면서(세피아 화면 + '기억'),
    몇 살 때인지는 주장하지 않으므로 그림과 어긋날 일이 없다.

    ⚠️ 대본을 쓰는 인공지능에게 "그렇게 써라" 라고 이르는 것만으로는 부족하다
       (말을 안 들으면 그대로 화면에 나간다). 그래서 **그리기 직전에 한 번 더**
       이 규칙으로 바꿔 준다(render.py). 대본 검사(validate_script.py)도 같은
       규칙을 쓴다 — 두 곳이 같은 자를 쓰도록 여기 한곳에 모아 둔다.

젊은 인물 그림이 생기면?
    그때는 이 파일의 `ART_HAS_YOUNG` 을 True 로 바꾸면 시대를 못 박는 자막이
    다시 허용된다. 지금은 젊은 그림이 없으므로 False 다.
"""
import re

# 인물의 '젊은 시절' 그림이 있는가. 없으면 시대를 못 박는 자막을 쓸 수 없다.
ART_HAS_YOUNG = False

# ── 시대를 못 박는 말 ────────────────────────────────────────────
#    이런 말이 들어가면 "화면 속 인물은 그 나이" 라는 뜻이 된다.
BANNED_WORDS = (
    "생전", "살아생전", "돌아가시기 전", "떠나기 전",
    "어린 시절", "어릴 적", "어릴 때", "어렸을 때", "자라던", "자랄 때",
    "학창", "학생 때", "젊은 시절", "젊었을 때", "청춘", "처녀 시절", "총각 시절",
    "신혼", "결혼 전", "결혼하던", "태어나기", "갓난",
    "그해", "그 시절", "그때 그", "옛날",
)

# '스무 해 전' · '40년 전' · '십수 년 전' 처럼 **햇수로 못 박는** 꼴
BANNED_PATTERNS = (
    re.compile(r"[0-9]+\s*년\s*전"),
    re.compile(r"(한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|스무|서른|마흔|쉰|예순|"
               r"일|이|삼|사|오|육|칠|팔|구|십|이십|삼십|사십|오십|육십|칠십|팔십|구십|백|"
               r"몇|십수|수)\s*(십)?\s*(년|해)\s*(전|쯤 전|가까이 전)"),
    # '스무 살 때' 처럼 나이로 못 박는 꼴 (숫자든 한글이든)
    re.compile(r"([0-9]+|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|스무|스물|서른|마흔|"
               r"쉰|예순|일흔|여든|아흔)\s*(살|세)\s*(때|무렵|적)"),
)

# 써도 되는 꼴 — '누구누구 시점' (손님이 괜찮다고 하신 형태)
SAFE_TAILS = ("의 기억", "씨의 기억", "시점", "의 회상", "이 겪은 일", "가 겪은 일")


def era_claim(label):
    """시대를 못 박는 말이 들어 있으면 **그 말**을 돌려준다. 없으면 None."""
    s = (label or "").strip()
    if not s:
        return None
    for w in BANNED_WORDS:
        if w in s:
            return w
    for pat in BANNED_PATTERNS:
        m = pat.search(s)
        if m:
            return m.group(0).strip()
    return None


def is_safe(label):
    """지금 그림으로 써도 되는 시점 자막인가."""
    s = (label or "").strip()
    if not s:
        return True                      # 없는 것은 문제 삼지 않는다(다른 검사가 본다)
    if ART_HAS_YOUNG:
        return True                      # 젊은 그림이 생기면 무엇이든 쓸 수 있다
    return era_claim(s) is None


def _speaker_code(cut):
    """말하는 사람의 인물 기호. 'v_M50A' → 'M50A'. 나레이션이면 None."""
    sp = str(cut.get("speaker") or "")
    if not sp or sp == "narrator":
        return None
    return sp[2:] if sp.startswith("v_") else sp


def whose(cut, doc=None):
    """이 컷은 **누구의 기억**인가. 인물 이름을 돌려준다(못 찾으면 None).

    ① 화면에 나온 인물이 한 사람이면 그 사람
    ② 아니면 말하는 사람
    ③ 그래도 없으면 화면에 나온 첫 인물"""
    chars = [c for c in (cut.get("chars") or []) if isinstance(c, dict)]
    codes = [str(c.get("code")) for c in chars if c.get("code")]
    code = None
    if len(codes) == 1:
        code = codes[0]
    if code is None:
        code = _speaker_code(cut)
    if code is None and codes:
        code = codes[0]
    if not code:
        return None
    for ch in (doc or {}).get("characters", []) or []:
        if str(ch.get("code")) == code:
            return (ch.get("name") or "").strip() or None
    return None


def safe_label(cut, doc=None):
    """화면에 실제로 띄울 시점 자막. 어긋나는 말은 '누구누구 시점' 으로 바꾼다.

    바꿀 이름조차 못 찾으면 '지난 일' 로 둔다 — 과거라는 것만 전하고
    언제인지는 주장하지 않는 가장 안전한 말이다."""
    lab = (cut.get("flashback_label") or "").strip()
    if not lab or is_safe(lab):
        return lab
    name = whose(cut, doc)
    return f"{name} 씨의 기억" if name else "지난 일"


def suggest(cut, doc=None):
    """대본을 고칠 사람에게 보여 줄 '이렇게 쓰십시오' 문구."""
    name = whose(cut, doc)
    return f"{name} 씨의 기억" if name else "지난 일"
