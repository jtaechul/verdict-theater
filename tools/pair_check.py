#!/usr/bin/env python3
"""**짝이 있는 것을 한쪽만 고치지 않았는가** — 짝 검사 (0원 · 인터넷 0회 · 1초)

    python3 tools/pair_check.py              실제 저장소를 검사한다
    python3 tools/pair_check.py --selftest   검사기가 진짜 잡는지 스스로 시험

⭐⭐⭐ 왜 이 검사가 생겼나 (2026-08-26 손님)
    "이런 코드 실수는 왜 자꾸 범하는거야?"

    추측하지 않고 세어 보니 **실수의 대부분이 한 모양**이었다 —
    **정하는 곳과 쓰는 곳이 둘인데 한쪽만 고친다.**

      · 목록에 단추를 적음        ↔ 화면에 그리는 코드에 안 넣음  → 단추가 안 보임
      · 칸 기본값을 v: 로 적음     ↔ 코드는 def 를 읽음            → 칸이 늘 비어 있음
      · 화풍을 실사로 바꿈         ↔ '하지 마라' 목록을 안 뒤집음   → 그림체가 섞임 (2번)
      · 도구가 소리 지시를 고쳐 씀  ↔ 검사기는 그 문장을 모름        → 규격 밖인데 초록불
      · 입 모양은 '말한 사람' 기준  ↔ 샷 크기는 '화면에 선 사람' 기준 → 샷이 어긋남

    지금까지는 **사고가 난 뒤에** 검사를 하나씩 붙여 왔다. 그러면 같은 사고는
    안 나지만 **새 사고는 못 막는다.** 짝을 한곳에 적어 두고 매번 본다.

무엇을 보나
    ① **화풍** — 컷 화풍 · 인물 화풍 · '하지 마라' 목록이 같은 편인가
    ② **고정 문구** — 대본 만드는 도구가 고정 줄을 **글자로 베껴** 쓰지 않는가
       (베끼면 규격 파일만 고쳤을 때 검사기가 모르는 문장이 나간다)
    ③ **인물** — 인물 목록 · 목소리표 · 등장 차례 · 화면 이름표가 다 맞는가
    ④ **무시된 설정** — 이야기 파일에 적어 둔 것이 실제로 읽히는가
       (적어만 두고 아무도 안 읽으면 조용히 없는 셈이 된다)

⚠️ 새 짝이 생기면 **여기에 적는다.** 사고가 난 뒤에 붙이지 말고, 짝을 만들 때 적는다.
"""
import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import charsheet as CS                                       # noqa: E402
import series as S                                           # noqa: E402
import shorts as SH                                          # noqa: E402

STORY = ROOT / "data" / "series" / "S001_story.py"
REWRITE = ROOT / "tools" / "rewrite_story.py"

# ① 화풍을 가리키는 말 (어느 편인지 알아보는 용도)
REAL_WORDS = ("photoreal", "natural skin", "photographic")
DRAWN_WORDS = ("illustration", "hand-drawn", "cel shading", "linework")
# ⚠️ 2026-08-26 — 처음엔 "반대편을 막아야 한다" 를 **양쪽 똑같이** 봤다가
#    옛 상태(그림체)에서 헛경보가 났다. 코드가 실제로 막는 방식이 편마다 다르다 —
#      실사  : charsheet.AVOID 에 cartoon·anime·illustration·drawing 을 적는다
#      그림체: charsheet.PHOTO_WORDS 로 사진 부르는 말을 **떼어 낸다**
#    검사는 코드가 하는 대로 봐야 한다.
DRAWN_BAN = ("cartoon", "anime", "illustration", "drawing")
REAL_BAN = ("photorealistic", "photograph", "photo")

# ② 규격 파일이 고정으로 정한 줄들. 도구가 이걸 **글자로 베껴 쓰면 안 된다**
FIXED_KEYS = ("AUDIO:", "STYLE:", "KEEP:", "COLOR:", "CONTINUITY:", "FRAMING:")


# 실사인데 AVOID 가 이걸 담고 있으면 바라는 것을 스스로 막는 것이다
REAL_MARKS_IN_AVOID = ("photoreal", "photorealistic", "natural skin")


def style_of(text):
    """이 글이 실사 편인가 그림 편인가."""
    low = (text or "").lower()
    real = sum(1 for w in REAL_WORDS if w in low)
    drawn = sum(1 for w in DRAWN_WORDS if w in low)
    if real and not drawn:
        return "실사"
    if drawn and not real:
        return "그림체"
    return "섞임" if (real and drawn) else "모름"


def load_story():
    spec = importlib.util.spec_from_file_location("story", STORY)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def check_style(bad):
    """① 컷 화풍 · 인물 화풍 · '하지 마라' 목록이 같은 편인가."""
    cut, char = style_of(S.STYLE_FIX), style_of(CS.LOOK)
    if cut != char:
        bad.append(f"화풍이 갈렸다 — 컷은 '{cut}' 인데 인물 그림은 '{char}' 다. "
                   f"둘이 다르면 컷과 인물이 따로 놀아 얼굴이 안 잡힌다 "
                   f"(series.STYLE_FIX ↔ charsheet.LOOK)")
        return
    if cut == "섞임" or cut == "모름":
        bad.append(f"컷 화풍이 '{cut}' 이다 — 실사인지 그림체인지 한쪽으로 적는다")
        return
    low = CS.AVOID.lower()
    if cut == "실사":
        # 실사일 때는 AVOID 가 그림체를 막아야 한다
        if not any(w in low for w in DRAWN_BAN):
            bad.append("화풍은 '실사' 인데 '하지 마라' 목록이 그림체를 안 막는다 — "
                       f"{', '.join(DRAWN_BAN)} 중 하나는 있어야 그림이 안 섞인다 "
                       "(charsheet.AVOID)")
        # 그러면서 실사를 막고 있으면 제 발등을 찍는 것이다
        hit = [w for w in REAL_MARKS_IN_AVOID if w in low]
        if hit:
            bad.append(f"화풍은 '실사' 인데 '하지 마라' 목록이 그걸 막고 있다 — "
                       f"{', '.join(hit)} (바라는 것을 스스로 막는 꼴이다)")
    else:
        # 그림체일 때 사진을 막는 장치는 AVOID 가 아니라 PHOTO_WORDS 다
        photo = [w.lower() for w in CS.PHOTO_WORDS]
        if not any(w in photo for w in REAL_BAN):
            bad.append("화풍은 '그림체' 인데 사진 부르는 말을 떼어 내지 않는다 — "
                       f"{', '.join(REAL_BAN)} 중 하나는 있어야 한다 "
                       "(charsheet.PHOTO_WORDS)")
        hit = [w for w in DRAWN_BAN if w in low]
        if hit:
            bad.append(f"화풍은 '그림체' 인데 '하지 마라' 목록이 그걸 막고 있다 — "
                       f"{', '.join(hit)} (바라는 것을 스스로 막는 꼴이다)")


def check_fixed(bad, src=None):
    """② 대본 만드는 도구가 고정 줄을 글자로 베껴 쓰지 않는가."""
    src = REWRITE.read_text(encoding="utf-8") if src is None else src
    body = "\n".join(l for l in src.split("\n") if not l.lstrip().startswith("#"))
    for key in FIXED_KEYS:
        for m in re.finditer(rf'"{re.escape(key)}[^"]{{6,}}"', body):
            bad.append(f"대본 만드는 도구가 '{key}' 줄을 글자로 적어 두었다 — "
                       f"{m.group(0)[:52]}… "
                       f"규격 파일(series.py)의 상수를 쓴다. 글자로 베끼면 "
                       f"한쪽만 고쳤을 때 검사기가 모르는 문장이 나간다")


def check_people(bad, doc, order=None, voices=None):
    """③ 인물 목록 · 목소리표 · 등장 차례 · 화면 이름표가 다 맞는가."""
    st = load_story()
    order = list(st.ORDER if order is None else order)
    voices = set(st.VOICES if voices is None else voices)
    if set(order) != voices:
        bad.append(f"등장 차례와 목소리표가 다르다 — "
                   f"차례에만 {sorted(set(order) - voices)}, "
                   f"목소리표에만 {sorted(voices - set(order))} "
                   f"(S001_story.ORDER ↔ VOICES)")
    says = {w for e in doc.get("episodes") or [] for c in e.get("cuts") or []
            for w, _ in S.dia_turns(c.get("prompt"))}
    miss = sorted(says - set(order))
    if miss:
        bad.append(f"대본에서 말하는데 등장 차례에 없는 사람 — {miss}")
    for w in sorted(says):
        if not SH.who_ko(w):
            bad.append(f"'{w}' 의 화면 이름표가 없다 — 자막 위에 아무것도 "
                       f"안 그려진다 (shorts.WHO_KO)")
    n_char = len(doc.get("characters") or [])
    if n_char != len(order):
        bad.append(f"대본의 등장인물이 {n_char}명인데 등장 차례는 "
                   f"{len(order)}명이다")


def check_used(bad, keys=None, src=None):
    """④ 이야기 파일에 적어 둔 것이 실제로 읽히는가."""
    src = REWRITE.read_text(encoding="utf-8") if src is None else src
    if keys is None:
        keys = {k for e in load_story().EPS for k in e}
    for k in sorted(keys):
        if k == "cuts":
            continue
        if not re.search(rf'''\.get\(["']{k}["']|\[["']{k}["']\]''', src):
            bad.append(f"이야기 파일에 '{k}' 를 적어 두었는데 대본 만드는 도구가 "
                       f"한 번도 안 읽는다 — 적어만 두고 조용히 무시된다")


def scan(doc):
    bad = []
    check_style(bad)
    check_fixed(bad)
    check_people(bad, doc)
    check_used(bad)
    return bad


def selftest():
    """⚠️ 잡지도 못하면서 초록불만 켜는 검사가 제일 위험하다."""
    assert style_of("photoreal look with natural skin texture") == "실사"
    assert style_of("hand-drawn illustration with soft cel shading") == "그림체"
    assert style_of("photoreal hand-drawn illustration") == "섞임"

    keep = (S.STYLE_FIX, CS.LOOK, CS.AVOID, CS.PHOTO_WORDS)
    try:
        # 컷은 실사인데 인물 그림은 그림체 — 얼굴이 안 잡히는 그 사고다
        b = []
        S.STYLE_FIX = "STYLE: photoreal look with natural skin texture"
        CS.LOOK = "hand-drawn illustration with soft cel shading"
        check_style(b)
        assert any("화풍이 갈렸다" in x for x in b), f"갈린 화풍을 못 잡는다: {b}"

        # 실사인데 그림체를 안 막는다 — 실제로 두 번 난 사고다
        b = []
        CS.LOOK = "photoreal look with natural skin texture"
        CS.AVOID = "Avoid: text, letters, watermark"
        check_style(b)
        assert any("그림체를 안 막는다" in x for x in b), f"안 막는 목록을 못 잡는다: {b}"

        # 실사인데 실사를 막는다 — 바라는 것을 스스로 막는 꼴
        b = []
        CS.AVOID = "Avoid: photoreal, natural skin, cartoon"
        check_style(b)
        assert any("그걸 막고 있다" in x for x in b), f"제 발등 찍는 목록을 못 잡는다: {b}"

        # 그림체일 때는 PHOTO_WORDS 로 본다 (AVOID 가 아니다)
        b = []
        S.STYLE_FIX = CS.LOOK = "hand-drawn illustration with soft cel shading"
        CS.AVOID = "Avoid: text, letters, watermark"
        CS.PHOTO_WORDS = ["photorealistic", "photograph"]
        check_style(b)
        assert not b, f"그림체 멀쩡한 상태를 걸었다: {b}"
        b = []
        CS.PHOTO_WORDS = ["8k"]
        check_style(b)
        assert any("사진 부르는 말을 떼어 내지 않는다" in x for x in b), \
            f"그림체 쪽 구멍을 못 잡는다: {b}"
    finally:
        S.STYLE_FIX, CS.LOOK, CS.AVOID, CS.PHOTO_WORDS = keep

    # ② 고정 줄을 글자로 베낀 것 — 실제로 AUDIO 줄에서 났던 사고다
    b = []
    check_fixed(b, 'x = "AUDIO: the two people in the shot say the lines"')
    assert any("글자로 적어 두었다" in x for x in b), f"베낀 고정 줄을 못 잡는다: {b}"
    b = []
    check_fixed(b, "x = S.AUDIO_ONE   # AUDIO: 는 주석이라 안 걸린다")
    assert not b, f"멀쩡한 것을 걸었다: {b}"

    # ③ 인물 — 목소리표에만 있고 등장 차례에 없는 사람
    b = []
    check_people(b, {"episodes": [], "characters": []},
                 order=["Wife"], voices={"Wife", "Ghost"})
    assert any("등장 차례와 목소리표가 다르다" in x for x in b), \
        f"어긋난 인물표를 못 잡는다: {b}"
    # 화면 이름표가 없는 사람 (자막 위에 아무것도 안 그려진다)
    b = []
    doc1 = {"episodes": [{"no": 1, "cuts": [{"n": 1, "prompt":
            "DIALOGUE: x\n  Ghost (numb, in Korean): \"야.\""}]}],
            "characters": [{"name": "유령"}]}
    check_people(b, doc1, order=["Ghost"], voices={"Ghost"})
    assert any("화면 이름표가 없다" in x for x in b), f"빠진 이름표를 못 잡는다: {b}"

    # ④ 적어만 두고 아무도 안 읽는 설정 — aside 를 넣을 때 실제로 날 뻔했다
    b = []
    check_used(b, keys={"no", "aside"}, src='x = e.get("no")')
    assert any("한 번도 안 읽는다" in x for x in b), f"무시된 설정을 못 잡는다: {b}"
    b = []
    check_used(b, keys={"no"}, src='x = e.get("no")')
    assert not b, f"멀쩡한 것을 걸었다: {b}"

    print("   ✅ 자기시험: 갈린 화풍 · 반대편을 안 막는 목록 · 바라는 것을 막는\n"
          "      목록 · 베낀 고정 줄 · 어긋난 인물표 · 빠진 이름표 ·\n"
          "      무시된 설정 — 실제로 났던 사고를 재현해 다 잡는다")


def main():
    print("⭐ 짝 검사 — 한쪽만 고치지 않았는가 (값 0원)\n")
    selftest()
    doc = json.loads((ROOT / "data" / "series" / "S001.json")
                     .read_text(encoding="utf-8"))
    bad = scan(doc)
    print()
    if bad:
        for b in bad:
            print("   ❌ " + b)
        print("\n" + "─" * 60)
        print(f"❌ 짝이 어긋난 곳 {len(bad)}군데 — 한쪽만 고쳤다")
        return 1
    print(f"   ✅ 화풍이 한 편이다 — 컷 · 인물 그림 · 하지 마라 목록 "
          f"({style_of(S.STYLE_FIX)})")
    print("   ✅ 대본 만드는 도구가 고정 줄을 글자로 베끼지 않는다")
    print("   ✅ 인물 목록 · 목소리표 · 등장 차례 · 화면 이름표가 다 맞는다")
    print("   ✅ 이야기 파일에 적어 둔 설정이 전부 읽힌다")
    print("\n" + "─" * 60)
    print("✅ 짝 검사: 전부 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
