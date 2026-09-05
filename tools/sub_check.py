#!/usr/bin/env python3
"""⭐ 자막이 **말 한복판에서 안 갈리고 · 글씨 크기가 안 튀는지** 본다.
   그리고 나레이션이 **주어를 밝히는지** 본다. 값 0원 (모델을 안 부른다).

    python3 tools/sub_check.py

손님(2026-09-05)
  ① "자꾸 자막이 단어 단위로 안 끊기고 말이 중간에 끊기는 경우가 부분적으로 있고"
  ② "글씨 크기가 갑자기 작아지거나 하는 상황이 발생해. 글씨 크기 변동이 없도록
     유지해주고, 글씨가 많을 경우에는 중간에 문장을 끌어서 다음 자막으로 띄우면
     되잖아."
  ③ "나레이션에서는 말 줄이지 말고 친절하게 풀어서 설명을 해. … 불륜의 대가를
     치렀다고 쓰는 거면 그 주체가 누구인지 주어를 쓰고 서술을 해야지."

까닭 — 옛 셈은 낱말 3개·글자 9자로 못을 박아 놓고, 넘치면 **글씨를 줄였다.**
   ⓐ 자리가 남아도 3낱말에서 끊겨 「관계 / 맺는」 처럼 말이 갈렸다
   ⓑ 토막마다 줄이는 폭이 달라 한 컷 안에서 104 → 96 → 102 로 크기가 튀었다
새 셈 — 크기는 SUB_FIXED 로 **고정**하고, 그 크기로 **한 줄에 들어가는 만큼**
   담는다. 넘치는 말은 다음 자막으로 넘긴다 (손님이 시키신 그대로다).

⚠️ 이 검사는 **저장된 대본 파일을 안 읽는다.** 손님이 대본을 다시 만드시면
   글이 바뀌는데, 그때 검사가 빨개지면 안 된다 (2026-09-04 에 실제로 그랬다).
   아래 시험글은 이 파일 안에 박아 둔다.
"""
import re
import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw, ImageFont          # noqa: E402

import short90 as S9                                 # noqa: E402
import story90 as ST                                 # noqa: E402

bad = []

# ── 시험글 (손님이 짚으신 줄 + 길고 어려운 줄) ────────────────────────────
LINES = [
    "당신 차에서 관계 맺는 소리가 다 찍혔어.",
    "며칠 뒤 여자에게 삼천만 원짜리 소장이 날아갔습니다.",
    "그냥 아는 동생이 술 취해서 헛소리한 거야.",
    "아내는 남편의 차 조수석 밑에 작은 녹음기를 숨겨 두었습니다.",
    "내연녀는 결국 불륜의 대가를 치렀습니다.",
    "재판장은 두 사람이 부부 공동생활을 무너뜨렸다고 보았습니다.",
    "법원은 위자료 삼천만 원을 지급하라고 판결했습니다.",
    "남편은 그날 밤 열한 시가 넘어서야 집에 들어왔습니다.",
    "여자는 상대가 결혼한 사람인 줄 몰랐다고 주장했습니다.",
    "실제로 있었던 사건입니다.",
    "그 소리는 조수석 밑에 숨겨둔 녹음기에서 나온 것이었습니다.",
    "다만 몰래 녹음한 행위는 법 위반으로 인정되었습니다.",
    "아내가 홧김에 한 번 찾아간 것은 불법이 아니라고 보았습니다.",
    "재판부는 아내가 물려받은 재산까지 들여다보았습니다.",
    "아내가 내민 녹취록에는 두 사람의 목소리가 그대로 담겨 있었습니다.",
]


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name
          + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def ink_height(im, top, bot):
    """자막 칸에서 **흰 글자가 실제로 차지한 높이**(px). 크기가 줄면 같이 준다.

    ⚠️ 투명도로 재면 안 된다 — 자막 칸에는 **어둡게 까는 막**(scrim)이 늘
       깔려 있어 칸 전체가 '무언가 있다' 로 나온다(실측 320px 고정).
       글자는 흰색이므로 **까만 바탕에 얹어 밝기**로 잰다.
    """
    bgc = Image.new("RGB", im.size, (0, 0, 0))
    bgc.paste(im.convert("RGBA"), (0, 0), im.convert("RGBA"))
    g = bgc.convert("L").crop((0, top, S9.W, bot))
    rows = [y for y in range(g.height)
            if max(g.crop((0, y, g.width, y + 1)).getdata()) > 200]
    return (rows[-1] - rows[0] + 1) if rows else 0


def main():
    print("⭐ 자막·나레이션 (값 0원 — 모델을 안 부른다)\n")
    lim = S9.W - S9.SIDE * 2
    f = ImageFont.truetype(str(S9.FONT_SUB), S9.SUB_FIXED)

    print("① 토막이 한 줄에 들어간다 — 그래서 글씨를 줄일 일이 없다")
    over, n = [], 0
    for t in LINES:
        for x in S9.chunks_of(t):
            n += 1
            if f.getlength(x) > lim:
                over.append(f"{int(f.getlength(x))}px 「{x}」")
    ck(f"{n}토막이 모두 {lim}px 안에 들어간다", not over, " · ".join(over[:2]))

    print("\n② 말 한복판이 안 갈린다 (손님이 짚으신 그 줄로 잰다)")
    for whole, part in (("당신 차에서 관계 맺는 소리가 다 찍혔어.", "관계 맺는"),
                        ("며칠 뒤 여자에게 삼천만 원짜리 소장이 날아갔습니다.",
                         "삼천만 원짜리"),
                        ("그냥 아는 동생이 술 취해서 헛소리한 거야.", "헛소리한 거야")):
        got = S9.chunks_of(whole)
        ck(f"「{part}」 이 안 갈린다", any(part in x for x in got), str(got))
    ck("숫자와 단위를 한 덩어리로 붙인다",
       S9.merge_units("삼천만 원짜리 소장이".split())[0] == "삼천만 원짜리")
    # ⭐ 가장 센 잣대 — **토막 끝이 '다음 말에 붙어야 하는 말' 이면 안 된다.**
    #    이것이 "말이 중간에 끊긴다" 를 코드로 옮긴 것이다.
    cut_mid = []
    for t in LINES:
        ch = S9.chunks_of(t)
        for k, x in enumerate(ch[:-1]):
            last = x.split()[-1]
            if S9.hangs(last):
                cut_mid.append(f"「{x}」 → 「{ch[k + 1]}」")
    ck("토막 끝이 다음 낱말에 붙어야 하는 말로 끝나지 않는다",
       not cut_mid, " · ".join(cut_mid[:2]))

    print("\n② -2 「는·은」 을 관형형과 조사로 가르는가")
    # ⭐⭐⭐ 2026-09-05 — 처음엔 「는」 을 무조건 붙였다. 그러면 한국어에서
    #    가장 자연스러운 끊는 자리가 통째로 막혀, 「행위는 법 / 위반으로」
    #    처럼 엉뚱한 데서 갈렸다. 대본 19종을 세어 잣대를 정했다.
    ADN = ("맺는", "아는", "없는", "좋은", "모은", "것은",          # 붙는다
           "배상하라는", "만나자는", "취급하는", "물려받은")
    JOSA = ("아내는", "행위는", "남편은", "법원은", "증거는", "재판부는",  # 끊어도 된다
            "내연녀는", "녹음은")
    miss = [w for w in ADN if not S9.hangs(w)] + [w for w in JOSA if S9.hangs(w)]
    ck(f"관형형 {len(ADN)}개는 붙이고 조사 {len(JOSA)}개는 끊는다",
       not miss, " · ".join(miss))
    got = S9.chunks_of("다만 몰래 녹음한 행위는 법 위반으로 인정되었습니다.")
    ck("「법 위반으로」 가 안 갈린다", any("법 위반으로" in x for x in got), str(got))
    ck("「녹음한 행위는」 이 안 갈린다",
       any("녹음한 행위는" in x for x in got), str(got))

    print("\n③ 한 글자도 안 잃고 안 겹친다 (넘친 말은 다음 자막으로)")
    lost = [t for t in LINES
            if "".join(S9.chunks_of(t)).replace(" ", "")
            != t.replace(" ", "")]
    ck("토막을 도로 이으면 원문 그대로다", not lost, str(lost[:1]))
    span = [t for t in LINES for x in S9.chunks_of(t)
            if len(re.findall(r"[.?!]", x[:-1])) > 0]
    ck("한 토막이 두 문장에 걸치지 않는다", not span, str(span[:1]))

    print("\n④ 글씨 크기가 안 튄다 (진짜로 그려서 픽셀로 잰다)")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "sub.png"
        hs = []
        for t in LINES:
            cut = {"n": 1, "kind": "나레이션", "text": t}
            for k in range(len(S9.chunks_of(t))):
                S9.overlay(cut, out, turn=("나레이션", t), now=k)
                hs.append(ink_height(Image.open(out), S9.SUB_TOP, S9.SUB_BOT))
        hs = [h for h in hs if h]
        ck(f"{len(hs)}토막을 그렸다", len(hs) == sum(len(S9.chunks_of(t))
                                                for t in LINES))
        ck(f"글자 높이가 토막마다 같다 ({min(hs)}~{max(hs)}px)",
           max(hs) - min(hs) <= 8,
           "크기가 튄다 — 손님이 '글씨가 갑자기 작아진다' 고 하신 그 고장")

    print("\n⑤ 크기를 못 박아 두었는가 (코드)")
    src = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
    ov = (re.search(r"def overlay\([\s\S]*?\n\ndef ", src) or [""])[0]
    ck("토막 자막은 정해진 크기로만 그린다",
       "lines, size = [text], SUB_FIXED" in ov)
    ch = (re.search(r"def chunks_of\([\s\S]*?\n\ndef ", src) or [""])[0]
    ck("낱말 수·글자 수로 못을 박지 않는다 (자리가 남으면 더 담는다)",
       "CHUNK_WORDS" not in ch and "CHUNK_CHARS" not in ch)
    ck("들어가는 만큼 재서 담는다", "getlength" in ch or "wide(" in ch)
    ck("끊는 자리를 조사·어미 뒤에서 고른다",
       "BREAK_END" in ch and "hangs(" in ch)
    hg = (re.search(r"def hangs\([\s\S]*?\n\ndef ", src) or [""])[0]
    ck("「는·은」 은 앞 음절 수로 관형형인지 가른다",
       "len(t) <= 2" in hg and "QUOTE_END" in hg)

    print("\n⑥ 나레이션이 주어를 밝히는가")
    ck("누가 그랬는지 빠지면 잡는다",
       ST.needs_subject("끝내 불륜의 대가를 치렀습니다."))
    ck("주어를 밝히면 통과한다",
       not ST.needs_subject("내연녀는 결국 불륜의 대가를 치렀습니다."))
    ck("무엇인지를 밝히는 문장은 주어가 없어도 된다",
       not ST.needs_subject("조수석 밑에 숨겨둔 녹음기에서 나온 소리였습니다.")
       and not ST.needs_subject("실제로 있었던 사건입니다."))
    ck("한 줄에 두 문장이면 문장마다 본다",
       len(ST.sentences("끝내 대가를 치렀습니다. 실제로 있었던 사건입니다.")) == 2)

    print("\n⑥ -2 대본 검사가 실제로 반려하는가 (가짜 대본으로 · 0원)")
    doc = thin()
    why = ST.check(doc, new=True)
    hit = [x for x in why if "주어가 없다" in x]
    ck("주어 없는 나레이션을 반려한다", hit,
       "'주어가 없다' 사유가 하나도 안 나왔다 — 규칙이 빠졌다")
    doc2 = thin(subj=True)
    ck("주어를 밝힌 대본은 이 사유로 안 걸린다",
       not [x for x in ST.check(doc2, new=True) if "주어가 없다" in x])
    ck("옛 대본은 이 사유로 안 걸린다 (새로 만들 때만 본다)",
       not [x for x in ST.check(doc, new=False) if "주어가 없다" in x])

    print("\n⑦ 프롬프트에도 적혀 있는가 (다음 대본부터 그렇게 나오게)")
    md = (ROOT / "prompts" / "story90_gen.md").read_text(encoding="utf-8")
    ck("좋은 예까지 적혀 있다",
       "나레이션은 주어를 밝힌다" in md
       and "내연녀는 결국 불륜의 대가를 치렀습니다" in md)
    fx = (ROOT / "prompts" / "story90_fix.md").read_text(encoding="utf-8")
    ck("고치는 프롬프트에도 적혀 있다", "주어를 밝힌다" in fx)

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 자막·나레이션: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 자막·나레이션: 말이 안 갈리고 · 크기가 안 튀고 · 주어를 밝힌다")
    return 0


def thin(subj=False):
    """검사기를 시험할 **가짜 대본**. 저장된 대본 파일을 안 읽으려고 여기서 만든다
    (2026-09-04 에 검사를 진짜 파일에 묶어 두었다가, 손님이 대본을 다시
    만드시자 검사가 빨개졌다. 같은 실수를 안 한다)."""
    narr = ("내연녀는 결국 불륜의 대가를 치렀습니다." if subj
            else "끝내 불륜의 대가를 치렀습니다.")
    talk = "당신 차에서 관계 맺는 소리가 다 찍혔어."
    cuts, parts = [], []
    for p in range(3):
        a = p * 9 + 1
        for i in range(a, a + 9):
            who = "나레이션" if (i - a) in (0, 4, 8) else "아내"
            t = narr if who == "나레이션" else talk
            cuts.append({"n": i, "who": [] if who == "나레이션" else ["아내"],
                         "turns": [[who, t]], "say": ["담담하게"],
                         "scene": "a quiet parked car at night"})
        parts.append({"no": p + 1, "cuts": [a, a + 8]})
    return {"title": "삼천만 원 위자료, 녹음기가 잡아낸 하룻밤",
            "card": "위자료 3천만 원", "parts": parts,
            "people": {"아내": {"sex": "여", "age": "30대"}},
            "cuts": cuts}


if __name__ == "__main__":
    raise SystemExit(main())
