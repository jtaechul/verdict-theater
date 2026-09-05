#!/usr/bin/env python3
"""작품 화면이 **사건마다 따로** 도는가 (값 0원 · 인터넷 0회)

    python3 tools/percase_check.py

⭐⭐⭐ 2026-09-02 손님: "지금 만들고 있는 영상을 들어가는 것도 지금 만들고
   있는 것만 볼 수 있게끔 되어 있어서 문제가 좀 있고."

   맞았다. 겉은 사건별로 나눠 놓고 **속은 아직 S90 에 묶여 있었다** —
     · 인물 그림 보관 자리가 'cards/S90-…' 로 박혀 있었다
     · 컷 영상 보관 자리가 'clips/S90-…' 로 박혀 있었다
     · 인물 이름 다섯(본처·남편·내연녀·딸·변호사)이 코드에 박혀 있었다
   그래서 새 사건을 열어 얼굴을 올려도 **S90 자리에 덮어쓰였고**, 사건마다
   다른 인물은 칸이 아예 안 떴다.

   이 검사가 하는 일은 하나다 — **다시 한 사건에 묶이지 않았는지** 보는 것.

⚠️ 주석에 적힌 것은 안 센다. 예전에 blob_auth_check 에서 "설명만 남고 코드가
   빠진" 꼴을 놓친 적이 있다 — 그때 배운 것을 여기도 쓴다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BAD = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + ("" if ok else f"  ({why})"))
    if not ok:
        BAD.append(name)


def code_only(js):
    """주석(//)을 걷어낸 코드만. 문자열 안의 // 는 여기서는 문제되지 않는다."""
    out = []
    for line in js.splitlines():
        t = line.lstrip()
        if t.startswith("//"):
            continue
        out.append(line)
    return "\n".join(out)


def main():
    print("⭐ 작품 화면이 사건마다 따로 도는가 (값 0원)\n")
    js = code_only((ROOT / "admin" / "worker.js").read_text(encoding="utf-8"))

    print("① 보관 자리에 사건 번호가 들어가는가")
    ck("인물 그림 자리가 사건별이다", "cards/${sid}-" in js,
       "cards/S90- 처럼 박아 두면 새 사건이 S90 자리를 덮어씁니다")
    ck("컷 영상 자리가 사건별이다", "clips/${sid}-" in js,
       "clips/S90- 처럼 박아 두면 새 사건이 S90 자리를 덮어씁니다")
    ck("인물 그림 자리에 S90 을 박아 두지 않았다", "cards/S90-" not in js)
    ck("컷 영상 자리에 S90 을 박아 두지 않았다", "clips/S90-" not in js)

    print("\n② 올릴 때 어느 사건인지 넘기는가")
    ck("인물 그림을 올릴 때 사건을 넘긴다", "upload-card?sid=" in js)
    ck("컷 영상을 올릴 때 사건을 넘긴다", "upload-cut?sid=" in js)
    ck("받는 쪽이 사건 번호를 읽는다 (인물)",
       re.search(r"upload-card'[\s\S]{0,200}?sidOf\(url\)", js) is not None)
    ck("받는 쪽이 사건 번호를 읽는다 (컷)",
       re.search(r"upload-cut'[\s\S]{0,200}?sidOf\(url\)", js) is not None)

    print("\n③ 인물 이름을 코드에 박아 두지 않았는가")
    # 사건마다 나오는 사람이 다르다. 대본에서 읽어야 한다.
    ck("화면이 인물을 대본에서 읽는다 (castOf)", "function castOf" in js,
       "다섯 이름을 박아 두면 다른 사건에서 엉뚱한 칸이 뜹니다")
    ck("화면이 그 목록을 실제로 쓴다", re.search(r"const cast = castOf\(\)", js)
       is not None)
    ck("받는 쪽도 대본에 나오는 사람인지로 본다",
       "S90_CARDS.indexOf(who) < 0" not in js,
       "이름을 목록으로 막으면 다른 사건 인물이 전부 튕깁니다")
    ck("모르는 이름도 자리 이름을 만들 수 있다 (whoKey)", "function whoKey" in js,
       "한글 이름은 보관함이 안 받습니다 — 영문 딱지가 필요합니다")

    print("\n④ 대본·영상·상태도 사건별인가")
    ck("대본을 사건 번호로 읽는다", "'data/series/' + sid + '.json'" in js)
    py = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
    ck("조립도 사건을 골라 읽는다 (VT_SID)", "VT_SID" in py)

    print("\n⑤ 얼굴이 사건 사이로 새지 않는가")
    # ⭐⭐⭐ 2026-09-05 손님: "에피소드에서 등장인물들을 좀 새로 생성하고
    #    싶거든? 전혀 다른 얼굴이 생성되도록."
    #    그때까지 얼굴 폴더도 보관 이름도 **S90 하나로 고정**이었다. 새 사건에
    #    새 얼굴을 넣으면 이미 올린 편의 얼굴까지 바뀐다.
    yml0 = (ROOT / ".github" / "workflows" / "short90.yml").read_text(encoding="utf-8")
    # ⚠️ 설명글(#)에 적힌 옛 이름에 속지 않는다 — **도는 줄**만 본다.
    #    (한 번 속았다: "cards90-S90 으로 고정이었다" 는 설명을 고장으로 셌다)
    yml = "\n".join(ln for ln in yml0.splitlines()
                    if not ln.lstrip().startswith("#"))
    rc = (ROOT / "tools" / "repo_cards.py").read_text(encoding="utf-8")
    ck("얼굴 보관 이름이 사건마다 다르다",
       "cards90-S90" not in yml and 'cards90-$S' in yml,
       "cards90-S90 으로 고정이면 앞 사건 얼굴을 받아 와 섞입니다")
    ck("얼굴 폴더를 사건 번호로 고른다", "def src_dir(sid)" in rc,
       "assets/cards/s90 하나만 보면 새 사건이 옛 얼굴을 씁니다")
    ck("전용 폴더가 없으면 기본 다섯으로 돌아간다", 'FALLBACK = "s90"' in rc)
    ck("워크플로가 사건 번호를 넘겨 준다",
       'repo_cards.py build/s90/cards "$S"' in yml)
    # 진짜로 갈리는지 돌려 본다 (0원)
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "repo_cards.py"),
                            td, "S91"], capture_output=True, text=True)
        ck("없는 사건은 기본 얼굴로 돌아간다고 말해 준다",
           "기본 얼굴" in r.stdout, r.stdout.strip()[:80])

    print("\n⑥ 만들어 둔 것도 사건마다 따로인가")
    # ⭐⭐⭐ 2026-09-05 — 얼굴만 사건별로 고치고 **그림·목소리·컷 영상은
    #    stills-S90 처럼 고정**으로 남겨 뒀다. 그래서 S91 을 만들 때 S90 의
    #    그림 60MB 를 받아 왔고(전부 다시 그렸다), 끝나고 S91 그림을
    #    stills-S90 에 덮어써 **S90 의 그림을 날렸다.**
    for t in ("stills", "voice", "clips90", "open"):
        ck(f"{t} 을 사건마다 따로 보관한다",
           f'"{t}-$S"' in yml and f"{t}-S90 " not in yml,
           f"{t}-S90 로 고정이면 앞 사건 것을 받아 오고 덮어쓴다")
    ck("보관 이름에 쓸 사건 번호를 job 에서 한 번만 정한다",
       re.search(r"^      S: \$\{\{ inputs\.sid", yml, re.M) is not None,
       "단계마다 셸이 달라 한 단계에서 S= 로 정해도 다음 단계는 모른다")

    print("\n⑦ 상한을 손으로 적어 두지 않았는가")
    # ⭐⭐⭐ 2026-09-05 손님: "야 전체 만들기 눌렀는데 왜 아무것도 안 나와."
    #    STILL_CALL_CAP 이 '24' 로 **손으로 적혀** 있었다. 대본 규격을 넓혀
    #    컷이 27장이 되자 24장을 그린 뒤 상한에 걸려 통째로 멈췄다.
    for k in ("STILL_CALL_CAP", "TTS_CALL_CAP", "VEO_CALL_CAP", "VT_RUN_KRW"):
        ck(f"{k} 를 손으로 안 적는다",
           not re.search(rf"^      {k}: ", yml, re.M),
           "손으로 적은 숫자는 대본이 커지면 반드시 어긋난다")
    ck("대본을 보고 셈해서 넣는다",
       "tools/plan_cost.py --env" in yml and '>> "$GITHUB_ENV"' in yml)
    ck("셈하는 단계가 돈 쓰는 단계보다 앞이다",
       yml.index("plan_cost.py --env") < yml.index("short90.py stills"))

    print("\n⑧ 올린 얼굴이 새로고침에도 남는가")
    # ⭐⭐⭐ 2026-09-05 손님: "새로고침 할 때마다 아예 없어져버려. 그래서
    #    반영되고 있는지 안 되고 있는지 난 알 수가 없으니까."
    #    올린 기록이 화면 메모리에만 있었고, 열쇠에 임의 번호가 붙어 되찾을
    #    길도 없었고, 보관함은 하루짜리였다. 그 상태로 [전체 만들기] 를
    #    누르면 **옛 얼굴로 조용히** 그려졌다.
    ck("보관함에 물어보는 창구가 있다", "'/api/cards'" in js)
    ck("누구 얼굴인지 적어 두고 올린다", "who: who, at: Date.now()" in js)
    ck("목록이 그 쪽지를 읽는다", "k.metadata" in js and "m.who" in js)
    ck("조각(.0 .1)을 얼굴로 세지 않는다", "\\.\\d+$/.test(k.name)" in js)
    ck("사람별로 **가장 최근** 것을 고른다", "at > best[who].at" in js)
    ck("얼굴은 하루가 아니라 오래 둔다 (KV_MONTH)",
       "KV_MONTH" in js and "blobPutStream(env, req.body, key, KV_MONTH" in js)
    ck("작품 화면을 열 때 되찾아 온다", "await loadCards(WORK)" in js)
    sc = (re.search(r"function short90Card\(\)[\s\S]*?\n}", js) or [""])[0]
    ck("올리신 얼굴을 화면에 띄운다", "s90im-" in sc and "S90CARDS[p[0]]" in sc)
    ck("무엇을 쓰는지 글로도 적는다",
       "올리신 얼굴을 씁니다" in sc and "기본 얼굴을 씁니다" in sc)
    ck("언제 올렸는지 적는다", "function whenTxt" in js and "S90CARDW" in sc)
    mk = (re.search(r"async function workMake\([\s\S]*?if \(!confirm", js)
          or [""])[0]
    ck("만들기 확인 창에도 이번에 쓸 얼굴을 적는다",
       "이번에 쓸 얼굴" in mk and "기본 얼굴" in mk,
       "값이 나가기 직전 마지막 문이다")

    print("\n" + "─" * 60)
    if BAD:
        print("❌ 걸린 것:")
        for b in BAD:
            print("     " + b)
        return 1
    print("✅ 작품 화면: 사건마다 따로 돈다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
