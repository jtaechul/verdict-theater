#!/usr/bin/env python3
"""⭐ 인물 배치가 EP002 의 두 사고를 되풀이하지 않는지 본다. 0원 · 인터넷 0회.

    python3 tools/place_test.py

왜 (2026-08-16 — 손님이 EP002 캡처 세 장으로 확인해 준 사고)
    ① 옛 격자 시트의 얼굴 컷 18장이 **정수리가 일직선으로 잘린 채** 방송됐다.
       잘린 자리에 흰 테두리가 둘러져 '흰 뚜껑'까지 보였다.
       → 목 잘림 검사(head_test)가 얼굴 컷을 통째로 건너뛰던 구멍. 이제 잰다.
    ② 한 컷에 상반신 컷과 얼굴 컷이 섞여 **한 사람만 절반 크기**로 보였다.
       → 렌더러가 얼굴 컷을 같은 표정의 상반신 컷으로 바꿔 틀을 통일한다.

무엇을 확인하나
    1. 정수리가 잘린 얼굴(가짜 그림)을 검사가 잡는다 / 둥근 머리는 통과한다
    2. 실제 저장소 그림으로: 얼굴+상반신이 섞인 컷이 상반신으로 통일된다
    3. 화질이 4배 다른 두 배우(옛 4K ↔ 새 1.1K)를 한 컷에 세워도
       머리 크기가 같게 풀린다 (크기 계산의 해상도 독립성)
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

FAIL = []


def bad(msg):
    FAIL.append(msg)
    print(f"   ❌ {msg}")


def ok(msg):
    print(f"   ✅ {msg}")


def fake_face(path, flat):
    """가짜 얼굴 그림 — flat=True 면 정수리를 일직선으로 자른 모양."""
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (400, 500), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if flat:
        # 잘린 머리: 위가 일직선인 네모 + 아래 턱 곡선
        d.rectangle([60, 40, 340, 420], fill=(230, 200, 180, 255))
        d.ellipse([60, 300, 340, 480], fill=(230, 200, 180, 255))
    else:
        # 둥근 머리: 타원
        d.ellipse([60, 40, 340, 480], fill=(230, 200, 180, 255))
    im.save(path)


def main():
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        print("⚠️ numpy/Pillow 가 없어 **재지 못했습니다.** '통과' 가 아니라 '안 해 봄' 입니다.")
        return 0

    from head_test import load_mask, top_flat, FACE_FLAT
    import render as R

    print("⭐ 인물 배치 — EP002 사고 재발 방지 시험")

    # ── 1. 정수리 잘림을 잡는 눈금 ─────────────────────────
    with tempfile.TemporaryDirectory() as td:
        cut_p, dome_p = Path(td) / "face_cut.png", Path(td) / "face_dome.png"
        fake_face(cut_p, flat=True)
        fake_face(dome_p, flat=False)
        tf_cut = top_flat(load_mask(cut_p))
        tf_dome = top_flat(load_mask(dome_p))
        if tf_cut is not None and tf_cut >= FACE_FLAT:
            ok(f"일직선으로 잘린 얼굴을 잡는다 (평평함 {tf_cut:.2f} ≥ {FACE_FLAT})")
        else:
            bad(f"잘린 얼굴을 못 잡는다 (평평함 {tf_cut})")
        if tf_dome is not None and tf_dome < FACE_FLAT:
            ok(f"둥근 머리는 통과한다 (평평함 {tf_dome:.2f} < {FACE_FLAT})")
        else:
            bad(f"둥근 머리를 잘림으로 몬다 (평평함 {tf_dome})")

    # head_test 가 얼굴 컷을 다시 건너뛰게 되면 여기서 잡는다 (구멍 재발 방지)
    ht = (ROOT / "tools" / "head_test.py").read_text(encoding="utf-8")
    if "FACE_FLAT" in ht and 'startswith("face_")' in ht:
        ok("목 잘림 검사가 얼굴 컷도 잰다 (건너뛰던 구멍 막음)")
    else:
        bad("목 잘림 검사가 얼굴 컷을 다시 건너뛴다")

    # ── 2. 얼굴+상반신 섞임 → 상반신으로 통일 ──────────────
    chars = [{"code": "M50B", "pose": "bust_neutral"},
             {"code": "F70", "pose": "face_sad"}]
    got = R.unify_kinds([dict(c) for c in chars], "TEST")
    poses = [c["pose"] for c in got]
    if poses == ["bust_neutral", "bust_sad"]:
        ok("섞인 컷이 상반신으로 통일된다 (face_sad → bust_sad)")
    else:
        bad(f"틀 통일이 안 된다: {poses}")
    solo = R.unify_kinds([{"code": "F70", "pose": "face_sad"}], "TEST")
    if solo[0]["pose"] == "face_sad":
        ok("혼자 선 컷의 얼굴은 그대로 둔다 (얼굴 크게 잡는 연출 유지)")
    else:
        bad("혼자 선 컷까지 바꿔 버린다")

    # ── 3. 화질 4배 차이 나는 두 배우의 머리 크기 ───────────
    #    (M50B 새 시트 1.1K ↔ F50B 옛 시트 4K — 실제 저장소 그림으로 잰다)
    cut = {"id": "TEST", "text": "시험 문장입니다.",
           "chars": [{"code": "M50B", "pose": "bust_neutral"},
                     {"code": "F50B", "pose": "bust_neutral"}]}
    W, H = 1920, 1080
    plan = [R._solve_char(c, cut, W, H, False, 0, banded=True)
            for c in cut["chars"]]
    fit = [p for p in plan if p["hw"] > 0]
    want_px = [p["target_h"] * p["hw"] for p in fit]
    cap_px = [p["cap"] * p["hw"] for p in fit]
    want = max(min(want_px), min(min(cap_px), max(want_px)))
    heads = [min(p["cap"], want / p["hw"]) * p["hw"] for p in fit]
    gap = abs(heads[0] - heads[1]) / max(heads)
    if gap <= 0.06:
        ok(f"화질이 달라도 머리 크기가 같다 (차이 {gap * 100:.1f}%)")
    else:
        bad(f"머리 크기가 벌어진다 (차이 {gap * 100:.1f}% — {[round(h) for h in heads]}px)")
    # 위 셈이 렌더러 본문과 같은 식인지 — 식이 바뀌면 이 시험도 같이 고쳐야 한다
    rsrc = (ROOT / "src" / "render.py").read_text(encoding="utf-8")
    if "want = max(min(want_px), min(min(cap_px), max(want_px)))" in rsrc:
        ok("이 시험의 셈이 렌더러 본문과 같은 식이다")
    else:
        bad("렌더러의 크기 셈이 바뀌었다 — 이 시험을 함께 고치십시오")

    print("─" * 52)
    if FAIL:
        print(f"❌ 인물 배치 시험: {len(FAIL)}가지 실패")
        return 1
    print("✅ 인물 배치 시험: 전부 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
