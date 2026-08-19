#!/usr/bin/env python3
"""회차마다 얼굴·배경이 바뀌는지 본다. 인터넷 0회 · 0원 · 1초.

    python3 tools/variant_test.py

왜 이 검사가 있는가 (2026-08-12)
    손님 지적: "왜 캐릭터 등장인물 새로 생성 안 해? 왜 저기에 그냥 모형이 들어가 있어?"

    맞는 지적이었다. 인물 코드는 사람이 아니라 '50대 여자 A' 같은 **칸**이고,
    그림은 2026-08-04 에 한 번 만들어 둔 뒤 `if not p.exists()` 라 다시 만들지
    않았다. 그래서 EP001 의 이정임(72세 어머니)과 EP002 의 윤선희(58세 아내)가
    **똑같은 얼굴**로 나왔다.

    이제 칸마다 '벌' 을 여러 개 두고 회차 번호로 돌려 쓴다.
    이 검사는 그 돌리기가 실제로 도는지, 그리고 **판사는 안 도는지**를 본다.
    (손님 지시: 판사는 고정 — 같은 법정, 같은 재판장이 채널의 얼굴이다)
"""

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import render                                        # noqa: E402

ok = True
MADE = []


def bad(msg):
    global ok
    ok = False
    print(f"   ❌ {msg}")


def face(ep, code):
    render.set_variant(ep)
    return render._char_dir(code).name


def bg(ep, code):
    render.set_variant(ep)
    p = render.bg_path(code)
    return p.name if p else None


CH = ROOT / "assets" / "char"
BG = ROOT / "assets" / "bg"

try:
    print("① 아직 한 벌뿐일 때 — 지금과 똑같이 돌아야 한다")
    names = {face(f"EP00{i}", "F50A") for i in (1, 2, 3)}
    if names != {"F50A"}:
        bad(f"한 벌뿐인데 다른 곳을 본다: {names}")
    else:
        print("   ✅ 그대로 1벌을 쓴다 (덧붙이기 전에는 아무것도 안 바뀐다)")

    # ── 두 번째 벌을 흉내 내어 넣는다 (시험이 끝나면 지운다) ──
    src = CH / "F50A"
    if not src.is_dir():
        print("   · assets/char/F50A 가 없어 나머지 시험을 건너뛴다")
        raise SystemExit(0)
    pose = next((f.name for f in src.glob("*.png")), None)
    for code in ("F50A", "JUDGE"):
        d = CH / f"{code}-2"
        if d.exists():
            continue
        d.mkdir(parents=True)
        MADE.append(d)
        s = CH / code / pose
        if s.exists():
            shutil.copy(s, d / pose)
    for n in (2, 3):
        f = BG / f"funeral_hall-{n}.jpg"
        if not f.exists() and (BG / "funeral_hall.jpg").exists():
            shutil.copy(BG / "funeral_hall.jpg", f)
            MADE.append(f)

    print()
    print("② 두 벌이 있으면 회차마다 번갈아 쓴다")
    got = [face(f"EP00{i}", "F50A") for i in (1, 2, 3, 4)]
    if got != ["F50A", "F50A-2", "F50A", "F50A-2"]:
        bad(f"번갈아 쓰지 않는다: {got}")
    else:
        print(f"   ✅ {' → '.join(got)}")

    print()
    print("③ 판사는 벌이 있어도 **절대** 안 바뀐다 (손님 지시)")
    got = [face(f"EP00{i}", "JUDGE") for i in (1, 2, 3, 4)]
    if set(got) != {"JUDGE"}:
        bad(f"판사가 바뀐다: {got} — 같은 법정, 같은 재판장이어야 한다")
    else:
        print("   ✅ 늘 JUDGE (JUDGE-2 가 있어도 안 쓴다)")

    print()
    print("④ 배경은 있는 벌 수만큼 돌아간다")
    got = [bg(f"EP00{i}", "funeral_hall") for i in (1, 2, 3, 4)]
    want = ["funeral_hall.jpg", "funeral_hall-2.jpg",
            "funeral_hall-3.jpg", "funeral_hall.jpg"]
    if got != want:
        bad(f"배경이 안 돈다: {got}")
    else:
        print(f"   ✅ {' → '.join(x.replace('funeral_hall', '') or '1' for x in got)}")

    print()
    print("⑤ 그 회차 벌이 없으면 1벌로 돌아간다 (덧붙이다 만 상태에서도 안 깨진다)")
    # F50B 는 2벌을 안 만들었다 — EP002 라도 1벌이 나와야 한다
    if (CH / "F50B").is_dir():
        if face("EP002", "F50B") != "F50B":
            bad("2벌이 없는 칸인데 없는 곳을 본다")
        else:
            print("   ✅ 2벌이 없는 칸은 조용히 1벌을 쓴다")
    if bg("EP002", "court_room") != "court_room.jpg":
        bad("2벌이 없는 배경인데 없는 파일을 본다")
    else:
        print("   ✅ 2벌이 없는 배경도 조용히 1벌을 쓴다")
    print()
    print("⑥ '판사 고정' 이 두 곳에 똑같이 적혀 있는가")
    # 한 곳만 고치면 조용히 망가진다 — 그리는 쪽은 만들고, 쓰는 쪽은 안 쓰거나 그 반대.
    import assets_gen                                # noqa: E402
    if render.FIXED_CODES != assets_gen.FIXED_FACE:
        bad(f"어긋난다 — render {render.FIXED_CODES} / assets_gen {assets_gen.FIXED_FACE}")
    else:
        print(f"   ✅ 두 곳 다 {sorted(render.FIXED_CODES)}")
finally:
    for m in MADE:
        if m.is_dir():
            shutil.rmtree(m, ignore_errors=True)
        else:
            m.unlink(missing_ok=True)

print()
print("─" * 52)
print("✅ 회차마다 얼굴·배경 바꾸기: 정상" if ok else "❌ 회차마다 얼굴·배경 바꾸기: 문제 있음")
sys.exit(0 if ok else 1)
