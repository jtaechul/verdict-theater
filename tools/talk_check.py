#!/usr/bin/env python3
"""대사가 **사람 말처럼 들리는가** — 말투 검사 (0원 · 인터넷 0회 · 1초)

    python3 tools/talk_check.py              실제 대본을 검사한다
    python3 tools/talk_check.py --selftest   검사기가 진짜 잡는지 스스로 시험

⭐⭐⭐ 왜 이 검사가 생겼나 (2026-08-26 운영자)
    "대사도 더럽게 재미없어요. 말 뚝뚝 끊어먹고 어색하고 컴퓨터처럼 얘기하지 마.
     사람이 얘기하는 것처럼 해야지."

    내가 90초 대본을 쓰면서 두 가지를 저질렀다.

    ① **문장을 토막 냈다.** 참고 영상의 자막이 한 줄 4~9글자로 보이길래
       문장 자체를 그렇게 잘랐다. 그래서 이런 게 나왔다 —
         "그리고 판결 난 그날" / "2013년 8월 9일" / "재산을 넘겼습니다"
       **누가 누구에게 넘겼는지가 통째로 사라졌다.** 4~9글자는 화면에 나눠
       띄우는 방식일 뿐이고(shorts.py 의 sub_chunks 가 알아서 한다),
       대본에는 **온전한 문장**을 쓴다.

    ② **대사에 정보를 실었다.** 이런 것을 대사라고 썼다 —
         "우리 애는 등록금도 못 내는데, 그 사람은 매달 2천만 원씩 보험료를
          부었더군요."
       이건 싸우는 사람 입이 아니라 **보고서 낭독**이다. 금액·날짜·법률
       용어는 **해설이 진다.** 대사는 그래야 사람 말이 된다.

무엇을 보나 (버리는 것)
    ① **토막** — 대사가 조사나 접속어로 끝나면 문장이 잘린 것이다
    ② **정보 낭독** — 한 대사에 숫자(금액·날짜)가 둘 이상
    ③ **연설** — 한 대사가 세 문장을 넘음
    ④ **문어체** — 판결문 말투. 변호사·재판장만 봐준다
    ⑤ **군말** — 한 화에 되묻기·군말이 하나도 없으면 컴퓨터가 말하는 것이다

무엇을 알리기만 하나
    · **말버릇** — 사람마다 말끝이 달라야 한다. 겹치면 알려 준다
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import series as S                                           # noqa: E402

# ① 토막 — 이런 것으로 끝나면 문장이 잘린 것이다
CHOP_JOSA = ("을", "를", "이", "가", "은", "는", "의", "에", "에서", "으로",
             "로", "와", "과", "도", "만", "부터", "까지", "한테", "에게")
CHOP_HEAD = ("그리고", "그런데", "근데", "그래서", "하지만", "그러나", "또한")

# ② 정보 낭독 — 숫자·금액·날짜
# ⚠️ 2026-08-26 — 처음 만든 검사가 **셋 중 둘을 잘못 잡았다.**
#      "이십 년이야. 이십 년을 같이 살았어."  ← 같은 말 되풀이는 사람의 강조다
#      "이천십삼년 팔월 구일이야."            ← 날짜 하나지 숫자 셋이 아니다
#    그래서 ① 날짜는 통째로 하나로 세고 ② 같은 숫자는 한 번만 센다.
DATE = re.compile(r"(?:[0-9]+|[일이삼사오육칠팔구십백천만]+)\s*년"
                  r"\s*(?:[0-9]+|[일이삼사오육칠팔구십]+)\s*월"
                  r"(?:\s*(?:[0-9]+|[일이삼사오육칠팔구십]+)\s*일)?")
NUM = re.compile(r"[0-9]+|[일이삼사오육칠팔구십백천만억]{2,}")


def facts(t):
    """그 대사가 나르는 **사실 덩어리** 수 (날짜는 하나, 되풀이는 한 번)."""
    n_date = len(DATE.findall(t))
    rest = DATE.sub(" ", t)
    return n_date + len(set(NUM.findall(rest)))

# ④ 판결문 말투. 사람 입에서 나오면 즉시 가짜가 된다
BOOKISH = ["더군요", "더군", "하였", "인 것이", "라 하겠", "되었습니다",
           "이었습니다", "하고자", "에 대하여", "에 관하여", "바랍니다",
           "드립니다", "하는 바", "임을", "하였음"]
BOOK_OK = ("lawyer", "judge")      # 이 사람들은 원래 그렇게 말한다

# ⑤ 군말·되묻기 — 하나도 없으면 사람이 아니다
FILLER = ["야", "어", "아니", "근데", "그래서", "됐", "뭐", "글쎄", "참",
          "저기", "아유", "어휴", "그럼", "좀", "진짜", "왜", "무슨", "…"]

# ⑥ 글로 쓰는 말 vs 입으로 하는 말 (2026-08-26 운영자)
#    "사람이 말할 때는 '니가' 하지, '네가' 라고 하지 않아. 그건 구어체가
#     아니고 문어체야. 구어체로 똑바로 적어."
#    ⚠️ 대답하는 '네' 는 건드리면 안 된다 ("네, 제가 아내인데요").
#       `네가` · `네 + 이름씨` · `너의` 만 본다 — '네,' 는 뒤가 쉼표라 안 걸린다.
WRITTEN = [(r"네가", "니가"), (r"네\s+[가-힣]", "니 ~"), (r"너의", "니"),
           (r"무엇을", "뭘"), (r"무엇이", "뭐가"), (r"하지 아니", "안 하")]

# ⚠️ 감탄사·부름말은 **문장이 아니다.** 세면 멀쩡한 대사가 걸린다 —
#      "어, 손님 오셨어? …여보. 이 사람 누구냐고."   ← 실은 두 문장이다
#      "야. 이겼다고 좋아하지 마. 나 아직 안 끝났으니까."  ← 실은 두 문장이다
#    (2026-08-26, 이 검사가 사람 말을 잡은 두 번째 사고다.
#     **검사가 사람 말을 잡으면 대사가 아니라 검사가 틀린 것이다.**)
INTERJ = {"야", "어", "아", "응", "네", "예", "아니", "여보", "엄마", "아빠",
          "저기", "참", "아유", "어휴", "자", "그럼", "뭐", "글쎄", "허"}


def sentences(t):
    """실질 문장만 센다 — 감탄사·부름말 토막은 빼고."""
    out = []
    for x in re.split(r"[.!?…]+", t):
        x = x.strip().strip("…,\"' ")
        if not x:
            continue
        if x in INTERJ or x.rstrip(",") in INTERJ:
            continue
        out.append(x)
    return out


# ⑦ 높임말 일관성 (2026-08-26 운영자)
#    "왜 자꾸 아내는 내연녀한테 존댓말 했다가 반말 했다가 일관성이 없어.
#     특별히 바뀌어야 될 상황이 아니잖아."
#    맞다. 세어 보니 세 쌍이 섞여 있었다 —
#      아내 → 내연녀 : 16줄 중 15줄 반말, **한 줄만 존댓말**
#      내연녀 → 아내 : 14줄 중 12줄 존댓말, **두 줄이 한 대사 안에서 반말**
#      아내 → 딸     : 창구 직원에게 한 말이 '딸에게' 로 잘못 묶였다(aside 로 뺀다)
#    사람 사이의 높임말은 **관계가 정하는 것**이라 장면마다 바뀌지 않는다.
POLITE_END = ("요", "니다", "습니까", "세요", "십시오", "죠", "까요", "데요",
              "군요", "는데요", "거든요", "잖아요")

SENT_MAX = 2        # 한 대사는 두 문장까지
NUM_MAX = 1         # 한 대사에 숫자는 하나까지


def turns_of(cut):
    """(말한 사람, 대사) — 옛 꼴 대본도 빠뜨리지 않는다."""
    t = S.dia_turns(cut.get("prompt"))
    return t or [("", x) for x in S.dia_says(cut.get("prompt"))]


def chopped(t):
    """문장이 잘렸는가 — 조사나 접속어로 끝난다.

    ⚠️ 말끝을 **일부러 흐리는 것**(…)은 사람이 실제로 그렇게 말한다.
       "그이가 왜 당신 집에서…" 는 멀쩡한 대사다. 말줄임표가 있으면 봐준다.
    """
    if t.strip().rstrip("\"'").endswith("…"):
        return ""
    body = t.strip().rstrip(".!?…\"'")
    if not body:
        return ""
    last = body.split()[-1] if body.split() else ""
    for j in sorted(CHOP_JOSA, key=len, reverse=True):
        if last.endswith(j) and len(last) > len(j):
            return last
    if body.split() and body.split()[0] in CHOP_HEAD and len(body.split()) < 4:
        return body.split()[0]
    return ""


def politeness(t):
    """이 대사가 존댓말인가 반말인가 — 마지막 실질 문장의 말끝으로 본다."""
    ss = sentences(t)
    if not ss:
        return ""
    b = re.sub(r"[.!?…\"'\s,]", "", ss[-1])
    return "존댓말" if b.endswith(POLITE_END) else "반말"


def ender(t):
    """말끝 두 글자 — 사람마다 달라야 한다."""
    body = re.sub(r"[.!?…\"']", "", t.strip())
    return body[-2:] if len(body) >= 2 else body


def scan(doc, soft=None):
    bad = []
    soft = soft if soft is not None else []
    enders = {}
    pair = {}          # (말한 사람 → 듣는 사람): {높임말: [어디]}
    for e in doc.get("episodes") or []:
        no = e.get("no")
        has_filler = False
        for c in e.get("cuts") or []:
            for who, t in turns_of(c):
                tag = f"{no}화 {c.get('n')}컷 {who}"
                if any(f in t for f in FILLER):
                    has_filler = True
                enders.setdefault(who, []).append(ender(t))

                # ① 토막
                cut_at = chopped(t)
                if cut_at:
                    bad.append(f"{tag}: 문장이 잘렸다 — '{cut_at}' 로 끝난다 "
                               f'("{t}") 화면에 나눠 띄우는 건 시스템이 한다. '
                               f"대본에는 온전한 문장을 쓴다")

                # ② 정보 낭독
                n_fact = facts(t)
                if n_fact > NUM_MAX:
                    bad.append(f"{tag}: 한 대사가 사실을 {n_fact}개 나른다 — "
                               f"금액·날짜는 해설이 진다. 대사가 보고서가 "
                               f'된다 ("{t}")')

                # ③ 연설
                n_sent = len(sentences(t))
                if n_sent > SENT_MAX:
                    bad.append(f"{tag}: 한 대사가 {n_sent}문장이다 "
                               f'({SENT_MAX}문장까지 — 넘으면 연설이다) ("{t}")')

                # ⑥ 글말투 대명사 — 입으로는 그렇게 말하지 않는다
                for pat, better in WRITTEN:
                    if re.search(pat, t):
                        bad.append(f"{tag}: 글로 쓰는 말이다 — "
                                   f"'{re.search(pat, t).group(0)}' 는 "
                                   f"'{better}' 라고 말한다 (\"{t}\")")
                        break

                # ④ 문어체
                if not any(k in (who or "").lower() for k in BOOK_OK):
                    hit = [w for w in BOOKISH if w in t]
                    if hit:
                        bad.append(f"{tag}: 판결문 말투 — {', '.join(hit)} "
                                   f'("{t}")')

        # ⑦ 높임말 — 한 쌍은 처음부터 끝까지 같아야 한다
        for c in e.get("cuts") or []:
            turns = turns_of(c)
            speakers = sorted({w for w, _ in turns if w})
            if len(speakers) != 2:
                continue                     # 혼잣말·전화는 상대를 알 수 없다
            aside = set(c.get("aside") or [])
            for w, t in turns:
                if not w or w in aside:      # 화면 밖 상대에게 한 말은 뺀다
                    continue
                other = [x for x in speakers if x != w][0]
                lv = politeness(t)
                if lv:
                    pair.setdefault((w, other), {}).setdefault(lv, []).append(
                        f"{no}화 {c.get('n')}컷")

        # ⑤ 군말
        if (e.get("cuts") or []) and not has_filler:
            bad.append(f"{no}화: 되묻기도 군말도 하나도 없다 — "
                       f"사람은 말할 때 '야' '아니' '근데' '왜' 를 쓴다")

    # ⑦ 섞인 쌍은 버린다
    for (a, b), lv in sorted(pair.items()):
        if len(lv) > 1:
            bit = " / ".join(f"{k} {len(v)}줄({v[0]}…)" for k, v in lv.items())
            few = min(lv, key=lambda k: len(lv[k]))
            bad.append(f"{a} 가 {b} 에게 존댓말과 반말을 섞는다 — {bit}. "
                       f"적은 쪽({few} {len(lv[few])}줄: "
                       f"{', '.join(lv[few])})을 맞춘다. "
                       f"높임말은 관계가 정하는 것이라 장면마다 안 바뀐다")

    # 말버릇 겹침 (알리기만)
    who_list = [w for w in enders if w]
    for i, a in enumerate(who_list):
        for b in who_list[i + 1:]:
            sa, sb = set(enders[a]), set(enders[b])
            if sa and sb and len(sa & sb) / min(len(sa), len(sb)) > 0.5:
                soft.append(f"{a} 와 {b} 의 말끝이 절반 넘게 같다 "
                            f"({', '.join(sorted(sa & sb))}) — 사람마다 "
                            f"말버릇이 달라야 구별된다")
    return bad


def selftest():
    """⚠️ 잡지도 못하면서 초록불만 켜는 검사가 제일 위험하다."""
    def doc(*lines, who="Wife"):
        return {"episodes": [{"no": 1, "cuts": [{"n": 1, "prompt":
                "DIALOGUE: x\n" + "\n".join(
                    f'  {who} (numb, in Korean): "{t}"' for t in lines)}]}]}

    ok = doc("야, 이 사람 누구야.", "아니 진짜 왜 이래.")
    assert not scan(ok), f"멀쩡한 것을 걸었다: {scan(ok)}"

    d = doc("그리고 판결이 난 그날 남편은 재산을", "아니 왜 그래.")
    assert any("문장이 잘렸다" in b for b in scan(d)), f"토막을 못 잡는다: {scan(d)}"

    d = doc("야, 이천십삼년 팔월 구일에 이천만 원을 냈어.")
    assert any("사실을" in b for b in scan(d)), f"정보 낭독을 못 잡는다: {scan(d)}"
    # 되풀이·날짜는 잡으면 안 된다 (처음 만든 검사가 여기서 틀렸다)
    d = doc("야, 이십 년이야. 이십 년을 같이 살았어.")
    assert not any("사실을" in b for b in scan(d)), f"되풀이를 잡으면 안 된다: {scan(d)}"
    d = doc("야, 네가 서명한 날짜 이천십삼년 팔월 구일이야.")
    assert not any("사실을" in b for b in scan(d)), f"날짜 하나를 잡으면 안 된다: {scan(d)}"
    d = doc("아니, 그이가 왜 당신 집에서…")
    assert not any("잘렸다" in b for b in scan(d)), f"흐린 말끝을 잡으면 안 된다: {scan(d)}"

    d = doc("야. 이거 봐. 저거 봐. 그거 봐.")
    assert any("문장이다" in b for b in scan(d)), "연설을 못 잡는다"
    # 감탄사·부름말은 문장이 아니다 — 이걸 세면 멀쩡한 대사가 걸린다
    d = doc("어, 손님 오셨어? …여보. 이 사람 누구냐고.")
    assert not any("문장이다" in b for b in scan(d)), \
        f"감탄사를 문장으로 세면 안 된다: {scan(d)}"
    d = doc("야. 이겼다고 좋아하지 마. 나 아직 안 끝났으니까.")
    assert not any("문장이다" in b for b in scan(d)), \
        f"부름말을 문장으로 세면 안 된다: {scan(d)}"

    d = doc("야, 매달 이천만 원씩 부었더군요.")
    assert any("판결문 말투" in b for b in scan(d)), "문어체를 못 잡는다"
    d = doc("매달 이천만 원씩 부었더군요.", who="Lawyer")
    assert not any("판결문 말투" in b for b in scan(d)), "변호사까지 잡으면 안 된다"

    d = doc("야, 네가 그랬잖아.")
    assert any("글로 쓰는 말" in b for b in scan(d)), f"'네가' 를 못 잡는다: {scan(d)}"
    d = doc("야, 니가 그랬잖아.")
    assert not any("글로 쓰는 말" in b for b in scan(d)), "'니가' 를 잡으면 안 된다"
    d = doc("네, 제가 그 사람 아내인데요.", "아니 왜요.")
    assert not any("글로 쓰는 말" in b for b in scan(d)), \
        f"대답하는 '네' 를 잡으면 안 된다: {scan(d)}"

    # ⑦ 높임말이 섞이면 잡는다 (두 사람이 말하는 컷에서만 본다)
    mix = {"episodes": [{"no": 1, "cuts": [{"n": 1, "prompt":
           "DIALOGUE: x\n"
           '  Wife (numb, in Korean): "야, 니가 왜 여기 있어."\n'
           '  Other woman (numb, in Korean): "왜요, 오면 안 돼요?"'},
           {"n": 2, "prompt":
           "DIALOGUE: x\n"
           '  Wife (numb, in Korean): "아니 왜 여기 계세요?"\n'
           '  Other woman (numb, in Korean): "그냥 왔어요."'}]}]}
    assert any("존댓말과 반말을 섞는다" in b for b in scan(mix)), \
        f"섞인 높임말을 못 잡는다: {scan(mix)}"
    mix["episodes"][0]["cuts"][1]["aside"] = ["Wife"]
    assert not any("존댓말과 반말을 섞는다" in b for b in scan(mix)), \
        "화면 밖 상대에게 한 말까지 잡으면 안 된다"

    d = doc("이혼하자.", "서류는 보낼게.")
    assert any("군말도 하나도 없다" in b for b in scan(d)), \
        f"군말 없는 화를 못 잡는다: {scan(d)}"
    print("   ✅ 자기시험: 토막 · 정보 낭독 · 연설 · 문어체 · 군말 없음 다 잡고,\n"
          "      글말투('네가') 도 잡고,\n"
          "      되풀이 강조 · 날짜 하나 · 흐린 말끝 · 대답하는 '네' ·\n"
          "      감탄사('야' '어' '여보') 와 화면 밖 상대(창구·전화) 는 잡지 않는다")


def main():
    print("⭐ 대사 말투 검사 (값 0원)\n")
    selftest()
    fails = 0
    for p in sorted((ROOT / "data" / "series").glob("S*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        soft = []
        bad = scan(doc, soft)
        print(f"\n{p.stem}")
        if bad:
            fails += len(bad)
            for b in bad:
                print("   ❌ " + b)
        else:
            print("   ✅ 잘린 문장이 없다 (온전한 문장으로 쓴다)")
            print("   ✅ 대사가 금액·날짜를 나르지 않는다 (그건 해설 몫)")
            print("   ✅ 연설하는 대사가 없다 · 판결문 말투가 없다")
            print("   ✅ 화마다 되묻기·군말이 있다")
            print("   ✅ 글말투가 없다 ('네가' 가 아니라 '니가')")
            print("   ✅ 높임말이 사람 쌍마다 처음부터 끝까지 같다")
        for b in soft:
            print("   ·  " + b)
    print("\n" + "─" * 60)
    if fails:
        print(f"❌ 말투: {fails}곳 — 고치고 다시")
        return 1
    print("✅ 말투: 전부 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
