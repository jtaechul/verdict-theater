#!/usr/bin/env python3
"""구글이 지어낸 말(대본에 없는 나레이션)을 잘라 내는가 (0원 · 5초).

왜 이 검사가 있는가 (2026-08-23)
    운영자: "'어디 한번 끝까지 가보자고' 다음에 나레이션이 하나 더 있는데
             이건 자막은 안 떠."
    대사(5.5초)보다 컷(8초)이 길면 구글이 남는 시간을 지어낸 말로 채운다.
    지어낸 말은 대본에 없으니 자막이 없다. trim_dead(turns=K) 가 대본의
    대사 수 K 를 넘는 말을 잘라 내는지, 가짜 소리로 실제로 재본다.

    ① 대사 1마디 + 지어낸 말 1마디  → 지어낸 말이 잘려야 한다
    ② 한 마디가 짧은 숨으로 두 토막  → 잘리면 안 된다 (진짜 대사다)
    ③ 대사 수와 소리가 같다          → 뒤 무음만 잘려야 한다
"""
import pathlib, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import shorts as S                                           # noqa: E402

TMP = pathlib.Path(tempfile.mkdtemp(prefix="extra-"))
fails = []

def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + ("" if ok else f"  ({why})"))
    if not ok:
        fails.append(name)

def synth(out, dur, spans):
    """spans 자리에만 말소리(사인파)가 나는 가짜 영상을 만든다."""
    vol = "+".join(f"between(t,{a},{b})" for a, b in spans)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", f"color=c=black:s=320x240:d={dur}",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}",
         "-af", f"volume='({vol})':eval=frame",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
         "-shortest", str(out)], check=True, capture_output=True)
    return out

def dur_of(p):
    return S.C.probe(p)[2]

print("=" * 60)
print("지어낸 말 잘라 내기 (값 0원)")
print("=" * 60)

print("① 대사 1마디 뒤에 지어낸 말이 있으면 잘라 낸다")
a = synth(TMP / "a.mp4", 8.0, [(0.5, 3.0), (4.5, 7.5)])
out = S.trim_dead(a, TMP / "a_t.mp4", turns=1)
d = dur_of(out)
ck("지어낸 말이 잘렸다 (8.0초 → 3.5초쯤)", 2.5 < d < 4.3, f"{d:.2f}초")

print("② 한 마디가 짧은 숨(0.3초)으로 두 토막이면 안 자른다")
b = synth(TMP / "b.mp4", 8.0, [(0.5, 3.0), (3.3, 6.0)])
out = S.trim_dead(b, TMP / "b_t.mp4", turns=1)
d = dur_of(out)
ck("진짜 대사는 남았다 (끝 6.0초까지)", d > 5.5, f"{d:.2f}초")

print("③ 대사 수와 소리가 같으면 뒤 무음만 자른다")
c = synth(TMP / "c.mp4", 8.0, [(0.5, 3.0), (4.0, 6.0)])
out = S.trim_dead(c, TMP / "c_t.mp4", turns=2)
d = dur_of(out)
ck("둘 다 남고 뒤 무음만 잘렸다", 5.5 < d < 7.0, f"{d:.2f}초")

print("-" * 60)
if fails:
    print(f"❌ {len(fails)}가지 실패")
    sys.exit(1)
print("✅ 지어낸 말은 잘리고, 진짜 대사는 남는다.")
