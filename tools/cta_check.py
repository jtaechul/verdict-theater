#!/usr/bin/env python3
"""⭐ **구독·좋아요·알림 유도**가 화면과 설명에 다 들어가는가. 값 0원.

    python3 tools/cta_check.py

⭐⭐⭐ 2026-09-06 손님: **"이제 앞으로 올릴 때는 다음화가 궁금하다면은 구독과
   좋아요, 알림을 좀 설정하도록 유도하는 건 어떨까."**

   자리는 둘이다 —
     ① 영상 **끝 화면** (1.7초) — 끝까지 본 사람에게만 보인다. 가장 좋은 자리다.
     ② 유튜브 **설명** — 나중에 다시 보는 사람이 본다.
   ⚠️ 둘이 따로 놀면 안 된다. 한쪽만 고쳐 놓고 고쳤다고 믿게 된다 —
      이 저장소가 여러 번 겪은 사고다. 여기서 **같은 말인지**까지 본다.

⚠️ 마지막 편에는 "다음 편" 이라고 하지 않는다 — 없는 편을 기다리게 된다.
⚠️ OS 이모지는 안 쓴다 (0-2 규칙 — 기기마다 모양이 달라 싸구려처럼 보인다).
"""
import json
import re
import sys
import tempfile
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image                                       # noqa: E402

import short90 as S9                                        # noqa: E402
import ytmeta as YM                                         # noqa: E402

bad = []
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name
          + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def fake_doc(parts=3):
    """시험용 대본. 저장된 대본 파일에 안 기댄다."""
    cuts, ps = [], []
    for k in range(parts):
        a = k * 9 + 1
        for n in range(a, a + 9):
            who = "나레이션" if (n - a) in (0, 4, 8) else "아내"
            cuts.append({"n": n, "kind": who, "who": [], "sec": 5.0,
                         "turns": [[who, "아내는 남편의 차에서 소리를 들었습니다."]],
                         "say": ["담담하게"], "scene": "a parked car at night"})
        ps.append({"no": k + 1, "cuts": [a, a + 8],
                   "card": ["남편 차에서 들린 목소리", "숨겨둔 녹음기"],
                   "yt_title": "남편 차에 녹음기를 숨긴 아내가 들은 것은"})
    return {"sid": "S99", "title": "시험 사건", "series_label": "시험 사건",
            "hook": "남편 차에 녹음기를 숨겼다", "cuts": cuts, "parts": ps}


def main():
    print("⭐ 구독·좋아요·알림 유도 (값 0원)\n")

    print("① 영상 끝 화면에 유도 한 줄이 있는가")
    ck("이어지는 편에 붙는 말이 있다",
       "구독" in S9.TAIL_SUB_NEXT and "알림" in S9.TAIL_SUB_NEXT,
       S9.TAIL_SUB_NEXT)
    ck("마지막 편에 붙는 말이 따로 있다",
       "구독" in S9.TAIL_SUB_LAST and S9.TAIL_SUB_LAST != S9.TAIL_SUB_NEXT)
    ck("마지막 편에는 '다음 편' 이라고 안 한다 (없는 편을 기다리게 된다)",
       "다음 편" not in S9.TAIL_SUB_LAST, S9.TAIL_SUB_LAST)
    ck("어느 쪽을 쓸지 가려 준다",
       S9.tail_sub(S9.TAIL_LAST) == S9.TAIL_SUB_LAST
       and S9.tail_sub(S9.TAIL_NEXT) == S9.TAIL_SUB_NEXT)
    for t in (S9.TAIL_SUB_NEXT, S9.TAIL_SUB_LAST, YM.CTA_NEXT, YM.CTA_LAST):
        ck(f"이모지를 안 쓴다 — 「{t[:16]}…」", not EMOJI.search(t))

    print("\n② 진짜로 그려지는가 (그림을 만들어 픽셀로 잰다)")
    # ⚠️⚠️ 처음에는 **투명도(alpha)** 로 쟀다. 그런데 글자 뒤에 까는 어두운 판이
    #    두 줄에 맞춰 커져 있어, 유도 줄을 통째로 지워도 판 때문에 통과했다
    #    (되돌리기 시험에서 드러났다). → **글자만** 재야 한다. 글자는 밝고
    #    판은 어두우므로, 까만 바탕에 얹어 **밝은 화소**만 센다.
    with tempfile.TemporaryDirectory() as td:
        T = Path(td)
        for tag in (S9.TAIL_NEXT, S9.TAIL_LAST):
            f = T / f"{tag}.png"
            S9.end_card(tag, f)
            im = Image.open(f).convert("RGBA")
            bg = Image.new("RGB", im.size, (0, 0, 0))
            bg.paste(im, (0, 0), im)
            g = bg.convert("L")
            rows = [y for y in range(S9.H)
                    if max(g.crop((0, y, S9.W, y + 1)).getdata()) > 150]
            ck(f"「{tag}」 글자가 그려진다", rows)
            big = S9.TAIL_Y + S9.TAIL_SIZE          # 큰 글이 끝나는 언저리
            low = [y for y in rows if y > big + 10]
            ck(f"「{tag}」 큰 글 **아래에** 유도 줄이 따로 있다",
               len(low) >= S9.TAIL_SUB_SIZE // 2,
               f"큰 글 아래 밝은 줄이 {len(low)}줄뿐이다 (유도 줄이 없다)")
            ck(f"「{tag}」 자막 자리(1300~)를 안 건드린다",
               rows and rows[-1] < S9.SUB_TOP, f"맨 아래 {rows[-1] if rows else 0}")

    print("\n③ 유튜브 설명에도 들어가는가")
    m = YM.meta90(fake_doc(3))
    got = [[l for l in p["description"].splitlines() if "구독" in l]
           for p in m["parts"]]
    ck("편마다 유도 한 줄이 있다", all(g for g in got),
       str([bool(g) for g in got]))
    ck("마지막 편만 다른 말이다",
       got[0][0] == got[1][0] != got[2][0] if all(got) else False)
    ck("마지막 편 설명에 '다음 편' 이 없다",
       all("다음 편" not in l for l in (got[2] if got[2] else [""])))
    ck("해시태그보다 위에 있다 (맨 끝에 묻히지 않게)",
       all(p["description"].index("구독")
           < p["description"].rindex("#") for p in m["parts"]))
    ck("한 편짜리 사건도 마지막 편으로 본다",
       "다음 편" not in " ".join(
           l for l in YM.meta90(fake_doc(1))["parts"][0]["description"].splitlines()
           if "구독" in l))

    print("\n④ 화면과 설명이 같은 말을 하는가 (한쪽만 고치는 사고 방지)")
    # ⚠️ 글자까지 똑같을 필요는 없다(길이가 다르다). **셋 다 들어 있는지**를 본다.
    for nm, t in (("화면(이어지는 편)", S9.TAIL_SUB_NEXT),
                  ("설명(이어지는 편)", YM.CTA_NEXT)):
        ck(f"{nm}: 구독·좋아요·알림 셋을 다 말한다",
           all(w in t for w in ("구독", "좋아요", "알림")), t)
    for nm, t in (("화면(마지막 편)", S9.TAIL_SUB_LAST),
                  ("설명(마지막 편)", YM.CTA_LAST)):
        ck(f"{nm}: 구독을 말한다", "구독" in t, t)

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 유도 문구: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 유도 문구: 화면 끝과 설명에 다 들어가고, 마지막 편은 말이 다르다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
