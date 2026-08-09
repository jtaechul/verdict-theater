#!/usr/bin/env python3
"""쇼츠 화면·묶음을 시험한다. 제미나이는 안 부른다(값 0원).

2026-08-08 손님 지적 두 가지를 그대로 재현해 막는다.
  ① "쇼츠 영상 위에 글씨가 겹치잖아!!!"
     위 검은 띠에 상황 한 줄(장례식날 전달된 소장)과 채널 이름(판결극장)을
     둘 다 가운데 정렬로 그려서 글자가 그대로 포개졌다.
  ② "자막하고 나레이션하고 하나도 맞지 않아 / 앞뒤 개연성이 없어"
     쇼츠 3편의 해설 20줄을 **한 통**에 몰아 만들고 20조각으로 잘랐다.
     경계 하나만 어긋나면 그 뒤가 전부 한 칸씩 밀려, 자막과 소리가 어긋난다.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import os  # noqa: E402
os.environ.setdefault("GEMINI_API_KEY", "fake-key-for-test")
import graphics as G  # noqa: E402
import render as R    # noqa: E402
import tts            # noqa: E402
from PIL import Image  # noqa: E402

fails = []


def check(label, cond, extra=""):
    print(f"  {'OK  ' if cond else 'FAIL'} {label} {extra}")
    if not cond:
        fails.append(label)


print("=" * 72)
print("  시험 1 — 쇼츠 첫 화면: 상황 한 줄과 채널 이름이 겹치지 않나")
print("=" * 72)
W, H = 1080, 1920
band, _ = R.stage_box(W, H, True)
TOP = "장례식날 전달된 소장"

blank = Image.new("RGBA", (W, H), (0, 0, 0, 0))


def ink(img):
    """**글자만**의 자리. 글자 뒤 그늘(번짐)은 빼고 잰다.

    번짐까지 재면 띠(172픽셀)를 넘는 것처럼 보이는데, 그것은 옅은 그늘이라
    화면에서 글자로 보이지 않는다. 겹쳤는지는 진한 획으로 판단해야 한다."""
    return img.getchannel("A").point(lambda v: 255 if v > 160 else 0).getbbox()


line_bbox = ink(G.draw_top_line(blank.copy(), TOP, box=(0, 0, W, band)))
logo_bbox = ink(G.draw_logo(blank.copy(), W, H, vertical=True, band=band))
print(f"        상황 한 줄 세로 {line_bbox[1]}~{line_bbox[3]} · "
      f"채널 이름 세로 {logo_bbox[1]}~{logo_bbox[3]} (띠 높이 {band})")
overlap = not (line_bbox[3] <= logo_bbox[1] or logo_bbox[3] <= line_bbox[1])
check("둘을 같이 그리면 실제로 겹친다 (이것이 손님이 본 화면)", overlap,
      "겹침 확인" if overlap else "안 겹침 — 시험이 뜻이 없다")

T = Path(tempfile.mkdtemp(prefix="vt-shorts-"))
lp_hook = R.logo_png(T, W, H, True, blank=True)
lp_rest = R.logo_png(T, W, H, True, blank=False)
hook_has_ink = Image.open(lp_hook).convert("RGBA").getbbox() is not None
rest_has_ink = Image.open(lp_rest).convert("RGBA").getbbox() is not None
check("상황 한 줄이 있는 컷에는 채널 이름을 안 그린다", not hook_has_ink)
check("나머지 컷에는 채널 이름이 그대로 나온다", rest_has_ink)
check("두 파일이 서로 다른 파일이다", Path(lp_hook) != Path(lp_rest))

# 띠 밖으로 삐져나오면 아래 그림 위에 글자가 얹힌다 — 그것도 겹침이다.
for t in (TOP, "장례식 날 배달된 소장 한 통이 남긴 것",
          "어머니가 서랍에서 꺼낸 종이 한 장"):
    bb = ink(G.draw_top_line(blank.copy(), t, box=(0, 0, W, band)))
    check(f"'{t[:12]}…' 이 띠 안에 들어간다", bb[3] <= band,
          f"글자 아래끝 {bb[3]} · 띠 {band}")

print("\n" + "=" * 72)
print("  시험 2 — 쇼츠 묶음이 **편을 넘나들지 않나** (자막↔소리 어긋남 방지)")
print("=" * 72)
sh = json.loads((ROOT / "data/scripts/EP001.shorts.json").read_text(encoding="utf-8"))
cuts = [dict(c, _grp=i) for i, s_ in enumerate(sh.get("shorts", []))
        for c in (s_.get("cuts") or [])]
cuts = [c for c in cuts if c.get("id")]
OUT = Path(tempfile.mkdtemp(prefix="vt-shorts-grp-"))
groups = tts.plan_groups(cuts, OUT)
by_id = {c["id"]: c for c in cuts}
worst = 0
for sp, lines in groups:
    grps = {by_id[cid]["_grp"] for cid, _ in lines}
    worst = max(worst, len(lines))
    name = "해설" if sp == "narrator" else sp
    print(f"        {name:8s} {len(lines):2d}줄  편 {sorted(grps)}"
          f"  {lines[0][0]} ~ {lines[-1][0]}")
    if len(grps) > 1:
        fails.append(f"{name} 묶음이 여러 편에 걸침")
check("한 통이 여러 편에 걸치지 않는다",
      all(len({by_id[cid]["_grp"] for cid, _ in lines}) == 1 for _, lines in groups))
check("한 통이 12줄을 넘지 않는다 (자를 경계가 적을수록 안전)", worst <= 12,
      f"가장 큰 통 {worst}줄 (예전에는 20줄이었다)")

print("\n" + "=" * 72)
print("  시험 3 — 이름표를 지운 컷도 **소리를 받는가** (컷이 통째로 빠지던 것)")
print("=" * 72)
# 2026-08-08 실제 사고: 이름표를 지울 때 컷이 사본으로 바뀌는데, 소리 쪽에서
# 그 사본을 못 알아봐 **컷 3개의 소리가 통째로 빠지고** 뒤가 전부 앞으로 당겨졌다.
# (쇼츠 1편 실측: 계획 35.7초 → 나온 영상 25.7초, 자막과 소리가 끝까지 어긋남)
s1 = sh["shorts"][0]
sdoc = {"acts": [{"id": "S1", "cuts": s1["cuts"], "bgm": "hook"}]}
all_cuts = [c for a in sdoc["acts"] for c in a["cuts"]]
keep = [(c, 3.0) for c in all_cuts]
keep, dropped = R.drop_repeat_nametags(keep)
check("이름표를 지운 컷이 실제로 있다 (시험이 뜻있음)", dropped > 0, f"{dropped}개")
sub = R.subdoc_for(sdoc, keep)
n = sum(len(a["cuts"]) for a in sub["acts"])
check("소리로 넘어가는 컷 수가 화면 컷 수와 같다", n == len(keep),
      f"소리 {n}컷 · 화면 {len(keep)}컷")
ids_sub = [c["id"] for a in sub["acts"] for c in a["cuts"]]
check("차례도 그대로다", ids_sub == [c["id"] for c, _ in keep])

# 예전 방식(메모리 번호로 고르기)이면 몇 개나 빠지는지 — 시험이 진짜를 잡는지 확인
kept_ids = {id(c) for c, _ in keep}
old_n = sum(1 for a in sdoc["acts"] for c in a["cuts"] if id(c) in kept_ids)
check("예전 방식이었다면 컷이 빠졌다", old_n < len(keep),
      f"예전 {old_n}컷 / 지금 {n}컷 (화면은 {len(keep)}컷)")

print("\n" + "=" * 72)
print("  시험 4 — 편을 안 나누면 예전처럼 20줄 한 통이 된다 (시험이 뜻있음을 확인)")
print("=" * 72)
plain = [{k: v for k, v in c.items() if k != "_grp"} for c in cuts]
OUT2 = Path(tempfile.mkdtemp(prefix="vt-shorts-old-"))
old_groups = tts.plan_groups(plain, OUT2)
big = max(len(l) for _, l in old_groups)
check("예전 방식이면 통 하나가 12줄을 넘는다", big > 12,
      f"가장 큰 통 {big}줄")

print("\n" + "=" * 72)
print("  시험 5 — 말 빠르기가 **합계 1.2배**를 넘지 않나 (발음 뭉개짐 방지)")
print("=" * 72)
# 2026-08-08: 목소리를 만들 때 이미 1.12배가 걸려 있는데 렌더링에서 1.2배를 또
# 얹어 합계 1.34배가 됐고, 자음이 뭉개졌다. 합계가 얼마인지 코드가 알고 있어야 한다.
check("목소리 쪽 배속과 렌더 쪽 배속을 곱하면 합계와 같다",
      abs(R.SPEECH_SPEED * R.TEMPO - R.TEMPO_TOTAL) < 0.001,
      f"{R.SPEECH_SPEED} × {R.TEMPO:.4f} = {R.SPEECH_SPEED * R.TEMPO:.3f}")
check("합계가 1.25배를 넘지 않는다 (넘으면 발음이 뭉개진다)", R.TEMPO_TOTAL <= 1.25,
      f"합계 {R.TEMPO_TOTAL}배")
_speed = {v[1] for v in tts.VOICE_STYLE.values()}
check("목소리 쪽 배속이 코드에 적힌 값과 맞다", R.SPEECH_SPEED in _speed,
      f"대본 인물들의 배속 {sorted(_speed)}")

print("\n" + "=" * 72)
print("  모두 통과" if not fails else f"  실패 {len(fails)}건: {fails}")
print("=" * 72)
sys.exit(1 if fails else 0)
