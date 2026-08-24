#!/usr/bin/env python3
"""플로우에서 받은 파일이 **제 컷에 붙는가**.

    python3 tools/clip_order_test.py     인터넷 0회 · 0원 · 1초

왜 이 검사가 있는가 (2026-08-22)
    플로우가 지어 주는 파일 이름은 제각각이고, 이름 순서대로 붙이면
    통째로 어긋난다. 실제로 운영자가 올린 5개는 이름 순서로는
    4·2·3·1·5 였다 — 그대로 붙였으면 자막과 장면이 전부 엇갈린
    영상이 나왔을 것이다. **그래도 영상은 멀쩡히 만들어진다.**
    오류가 안 나므로 검사가 없으면 아무도 모른다.

    ⚠️ 이 짝짓기는 낱말을 맞추는 방식이라 가장 깨지기 쉬운 부분인데,
       여태 한 번도 검사된 적이 없었다 (내 시험은 c001~c005 라는
       '정답이 이름에 박힌' 파일로만 돌렸다).
"""

import io
import json
import pathlib
import sys
import tempfile
from contextlib import redirect_stdout

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import shorts as S                                              # noqa: E402

bad = 0


def ck(what, cond, why=""):
    global bad
    if cond:
        print(f"   ✅ {what}")
    else:
        print(f"   ❌ {what}" + (f"  ({why})" if why else ""))
        bad = 1


def order(names, cuts):
    """이름들을 컷에 붙여 본다. 무엇을 말했는지도 같이 돌려준다."""
    with tempfile.TemporaryDirectory() as d:
        for nm in names:
            (pathlib.Path(d) / nm).write_bytes(b"")
        buf = io.StringIO()
        with redirect_stdout(buf):
            got = S.pick_clips(d, len(cuts), cuts)
    return {k: v.name for k, v in got.items()}, buf.getvalue()


# ⚠️⚠️ 2026-08-24 — 예전엔 여기서 **지금의 1화 대본**을 읽어 왔다. 그런데
#    1화 대사·연출을 다시 쓰자 이 검사가 통째로 깨졌다. 이 검사가 지키려는
#    것은 "2026-08-22 에 실제로 올라온 파일 이름이 제 컷에 붙는가" 이지
#    "1화 대본이 그때 그대로인가" 가 아니다. 그래서 **그때의 컷을 여기에
#    박아 둔다** — 대본을 고쳐도 이 검사는 계속 같은 것을 지킨다.
TWO = ("SHOT: Medium two-shot, static camera, both faces visible. Framed from the waist "
       "up so both faces fill much of the frame, close enough that every expression is clear.")
ONE = ("SHOT: Medium close-up, static camera, focusing on the character. Framed from the "
       "waist up so both faces fill much of the frame, close enough that every expression "
       "is clear.")
SYNC = " Both people keep their lips moving in exact sync with the Korean lines they say."
cuts = [
    {"n": 1, "prompt": TWO + "\nACTION: the wife steps in front of the husband, "
                             "blocking the way." + SYNC},
    {"n": 2, "prompt": ONE + "\nACTION: the husband pulls away sharply." + SYNC},
    {"n": 3, "prompt": TWO + "\nACTION: the other woman smirks crossing her arms." + SYNC},
    {"n": 4, "prompt": ONE + "\nACTION: the husband glares coldly at her." + SYNC},
    {"n": 5, "prompt": ONE + "\nACTION: the wife clenches her fists tightly." + SYNC},
]

print("⭐ 받은 파일이 제 컷에 붙는가")

# ① 2026-08-22 운영자가 실제로 올린 이름 그대로
REAL = [
    "Husband_glaring_coldly_at_her_202608222355.mp4",
    "Husband_pulls_away_sharply_202608222355.mp4",
    "Two_women_arguing_in_hallway_202608222355.mp4",
    "Wife_blocking_husband_arguing_202608222355.mp4",
    "Wife_clenches_fists_speaking_Korean_202608222355.mp4",
]
got, said = order(REAL, cuts)
ck("다섯 컷이 다 채워진다", len(got) == 5, str(got))
ck("1컷 = 아내가 막아서는 장면", got.get(1, "").startswith("Wife_blocking"), got.get(1, ""))
ck("2컷 = 남편이 뿌리치는 장면", got.get(2, "").startswith("Husband_pulls_away"), got.get(2, ""))
ck("4컷 = 남편이 차갑게 노려보는 장면", got.get(4, "").startswith("Husband_glaring"), got.get(4, ""))
ck("5컷 = 아내가 주먹을 쥐는 장면", got.get(5, "").startswith("Wife_clenches"), got.get(5, ""))
# ⚠️ 이름 순서대로 붙이는 것과 **달라야** 한다. 같다면 짝짓기가 죽은 것이다.
abc = {i + 1: n for i, n in enumerate(sorted(REAL))}
ck("이름 순서대로 붙이는 것과 다르다", got != abc,
   "이름 순서면 4·2·3·1·5 로 통째로 어긋난다 — 짝짓기가 죽었다는 뜻")
ck("다 맞췄으면 경고를 띄우지 않는다", "이름으로 못 맞춰" not in said, said.strip())

# ② 이름에 컷 번호가 있으면 그것이 가장 확실하다
NUM = ["c001_x.mp4", "c002_x.mp4", "c003_x.mp4", "c004_x.mp4", "c005_x.mp4"]
got, _ = order(NUM, cuts)
ck("이름에 번호가 있으면 번호대로 붙인다",
   all(got.get(k, "").startswith(f"c00{k}") for k in range(1, 6)), str(got))

# ③ 아무 낱말도 안 맞으면 **조용히 넘어가면 안 된다**
JUNK = [f"video{i}.mp4" for i in range(1, 6)]
got, said = order(JUNK, cuts)
ck("맞출 수 없어도 다섯 컷을 채우기는 한다", len(got) == 5, str(got))
ck("못 맞췄으면 크게 알린다", "이름으로 못 맞춰" in said,
   "틀려도 영상은 멀쩡히 나온다 — 조용하면 그대로 올라간다")
ck("어느 컷이 위험한지 알려 준다", said.count("컷은 이름으로 못 맞춰") == 5, said.strip())

print("────────────────────────────────────────────────────")
print("❌ 컷 붙이기: 걸린 것이 있다" if bad else "✅ 컷 붙이기: 제 컷에 제대로 붙는다")
sys.exit(bad)
