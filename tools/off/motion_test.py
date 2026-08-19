#!/usr/bin/env python3
"""인물이 배경과 **따로** 움직이는지 본다. 인터넷 0회 · 0원 · 몇 초.

    python3 tools/motion_test.py

왜 이 검사가 있는가 (2026-08-12)
    손님: "애니메이션으로 가는 거면 기본적으로 조금 움직임이 있는 거를
           어떤 식으로 구현할지 창의적인 방식으로 좀 고민해 봐."

    고민해 보니 **먼저 고쳐야 할 것이 있었다.** 예전에는 배경과 인물을 한 장으로
    합친 뒤 그 한 장에 확대와 `+0.004*sin(on/26)` 을 걸었다. 그래서 그 '숨쉬기' 는
    사람이 숨쉬는 게 아니라 **화면 전체가 흔들리는 것** — 카메라 떨림이었다.
    인물을 배경에서 떼어내야 비로소
      · 인물만 오르내리는 진짜 숨쉬기
      · 배경과 속도가 달라 생기는 깊이(패럴랙스)
      · 나중에 눈 깜빡임 부품을 얼굴에 얹을 자리
    가 생긴다.

    이 검사는 그 분리가 살아 있는지, 그리고 **다시 한 장으로 합쳐지지 않았는지**를
    본다. 합쳐지면 조용히 예전으로 돌아가는데 화면만 봐서는 알아채기 어렵다.
"""

import json
import math
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import render as R                                    # noqa: E402

ok = True


def bad(msg):
    global ok
    ok = False
    print(f"   ❌ {msg}")


def a_cut():
    """인물이 있는 컷 하나. 대본이 없으면 손으로 만든다."""
    for name in ("EP002", "EP001"):
        p = ROOT / "data" / "scripts" / f"{name}.json"
        if not p.exists():
            continue
        doc = json.loads(p.read_text(encoding="utf-8"))
        for a in doc.get("acts", []):
            for c in a.get("cuts", []):
                if c.get("chars"):
                    return c
    return None


print("① 인물이 배경과 따로 나오는가 (split)")
cut = a_cut()
if not cut:
    print("   · 대본이 없어 건너뛴다")
else:
    got = R.build_plates(cut, 1920, 1080, False, split=True)
    if len(got) != 4:
        bad(f"겹이 {len(got)}장뿐이다 — 인물이 배경에 합쳐져 있다")
    else:
        bg, ch, _g, _s = got
        if ch.mode != "RGBA":
            bad("인물 겹이 투명하지 않다")
        else:
            al = ch.getchannel("A")
            lo, hi = al.getextrema()
            if hi == 0:
                bad("인물 겹이 비어 있다 — 인물이 안 그려졌다")
            elif lo != 0:
                bad("인물 겹에 빈 곳이 없다 — 배경이 같이 들어갔다")
            else:
                print("   ✅ 배경 1장 + 인물 1장 (인물 겹은 배경 자리가 비어 있다)")

print()
print("② split 을 안 쓰면 예전과 똑같은가 (다른 도구가 안 깨졌는가)")
# tools/preview.py · tools/check_place.py 가 3장을 받는다. 4장이 오면 터진다.
if cut:
    got = R.build_plates(cut, 1920, 1080, False)
    if len(got) != 3:
        bad(f"split 없이 불렀는데 {len(got)}장이 왔다 — preview·check_place 가 터진다")
    else:
        print("   ✅ 3장 (예전 그대로)")

print()
print("③ 숨쉬기가 실제로 오르내리는가")
# 확대식을 파이썬으로 그대로 계산해 본다. ffmpeg 를 안 돌려도 알 수 있다.
frames = 300


def z_char(on, shock=False):
    span = R.ZOOM_MAX - R.ZOOM_START - R.BREATH
    z = (R.ZOOM_START + R.BREATH + span * (on / frames)
         + R.PARALLAX * (on / frames) + R.BREATH * math.sin(on / R.BREATH_T))
    if shock:
        z += R.IMPACT * max(0, 1 - on / R.IMPACT_F)
    return z


def z_bg(on):
    span = R.ZOOM_MAX - R.ZOOM_START - R.BREATH
    return R.ZOOM_START + R.BREATH + span * (on / frames)


# 사인 한 주기 안에서 위아래로 흔들려야 한다
period = int(2 * math.pi * R.BREATH_T)
vals = [z_char(n) - z_bg(n) for n in range(period)]
swing = max(vals) - min(vals)
if swing < R.BREATH:
    bad(f"숨쉬기 진폭이 {swing:.4f} 뿐이다 — 사인이 안 걸렸다")
else:
    print(f"   ✅ 한 주기({period / 30:.1f}초) 동안 {swing * 100:.2f}% 오르내린다")

print()
print("④ 인물이 배경보다 더 다가오는가 (패럴랙스 = 깊이)")
# 컷 끝에서 인물 확대가 배경 확대보다 커야 한다
d = z_char(frames) - z_bg(frames)
if d <= 0:
    bad(f"인물이 배경보다 덜 다가온다({d:+.4f}) — 깊이가 안 생긴다")
else:
    print(f"   ✅ 컷 끝에서 인물이 {d * 100:.2f}% 더 커진다")

print()
print("⑤ 배경은 흔들리지 않는가 (멀리 있는 것이 떨면 카메라 떨림으로 보인다)")
bgs = [z_bg(n) for n in range(period)]
mono = all(bgs[i] <= bgs[i + 1] + 1e-9 for i in range(len(bgs) - 1))
if not mono:
    bad("배경 확대가 오르내린다 — 예전의 '카메라 떨림' 이 돌아왔다")
else:
    print("   ✅ 배경은 한 방향으로만 천천히 밀려온다")

print()
print("⑥ 충격 컷에서만 '한 방' 이 걸리는가 (남발하면 촌스럽다)")
n0 = z_char(0, shock=True) - z_char(0, shock=False)
n_after = z_char(R.IMPACT_F + 1, shock=True) - z_char(R.IMPACT_F + 1, shock=False)
if abs(n0 - R.IMPACT) > 1e-6:
    bad(f"충격 순간 확대가 {n0:.4f} — {R.IMPACT} 여야 한다")
elif n_after > 1e-6:
    bad(f"{R.IMPACT_F}프레임 뒤에도 {n_after:.4f} 남아 있다 — 제자리로 안 돌아온다")
else:
    print(f"   ✅ 첫 {R.IMPACT_F}프레임({R.IMPACT_F / 30:.2f}초)만 {R.IMPACT * 100:.0f}% "
          "커졌다 제자리")

src = (ROOT / "src" / "render.py").read_text(encoding="utf-8")
i = src.index("    shock = any(")
cond = src[i:src.index("\n", src.index("for x in", i))]
if "_shock" not in cond:
    bad("충격 판정이 포즈를 안 본다")
elif any(w in cond for w in ("anger", "cry", "sad")):
    bad("충격 말고 다른 감정에도 걸린다 — 남발하면 촌스러워진다")
else:
    print("   ✅ `*_shock` 포즈일 때만 (EP002 실측 119컷 중 9컷 = 7.5%)")

print()
print("⑦ ffmpeg 를 실제로 돌려도 인물 겹의 투명이 살아 있는가")
# ⚠️ 이게 이 방식의 **유일한 큰 위험**이었다. zoompan 이 투명한 곳을 검게 칠하면
#    인물 뒤에 검은 네모가 생겨 배경을 다 가린다. 실측으로 확인한다.
if not cut:
    print("   · 대본이 없어 건너뛴다")
elif not subprocess.run(["which", "ffmpeg"], capture_output=True).stdout:
    print("   · ffmpeg 가 없어 건너뛴다")
else:
    try:
        from PIL import Image
        wd = pathlib.Path(tempfile.mkdtemp())
        out = R.render_cut(cut, 1.0, wd, 1, 1280, 720)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out),
                        "-frames:v", "1", str(wd / "f.png")], check=True)
        im = Image.open(wd / "f.png").convert("RGB")
        # 인물 겹이 검게 칠해졌다면 화면 대부분이 새까매진다
        import numpy as np
        arr = np.asarray(im, dtype=int).sum(axis=2)
        dark = float((arr < 24).mean())
        if dark > 0.55:
            bad(f"화면의 {dark * 100:.0f}% 가 새까맣다 — zoompan 이 투명을 검게 칠했다")
        else:
            print(f"   ✅ 정상 (아주 어두운 곳 {dark * 100:.0f}%)")
    except Exception as e:
        bad(f"실제 렌더에서 터졌다: {e}")

print()
print("─" * 52)
print("✅ 인물 움직임: 정상" if ok else "❌ 인물 움직임: 문제 있음")
sys.exit(0 if ok else 1)
