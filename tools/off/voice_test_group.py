#!/usr/bin/env python3
"""묶어서 만들기 전 과정을 시험한다. 진짜 대본(EP001)을 쓰고, 제미나이만 가짜로 바꾼다.

가짜 제미나이는 진짜와 같은 성질을 흉내 낸다:
  · 글자 수에 비례한 길이로 말하고, 문장 사이에 쉰다
  · **호출마다 목소리(높이)가 조금씩 달라진다** — 이것이 진짜 문제였다
  · 길이 한도를 넘으면 도중에 끊어서 준다 (한도 시험용)
"""
import json
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import tts  # noqa: E402

T = Path(tempfile.mkdtemp(prefix="vt-grp-"))
fails = []
CALLS = []


def check(label, cond, extra=""):
    print(f"  {'OK  ' if cond else 'FAIL'} {label} {extra}")
    if not cond:
        fails.append(label)


def fake_synth(limit_sec=None, base_hz=None):
    """가짜 synth_group. 호출마다 목소리 높이를 바꿔 '다른 사람' 을 흉내 낸다."""
    def go(key, model, lines, speaker, out_mp3, rotate=False):
        CALLS.append((speaker, len(lines)))
        hz = (base_hz or 84) + (len(CALLS) * 7) % 40      # 호출마다 다른 높이
        ins, chain, k, used = [], [], 0, 0.0
        for i, (_cid, t) in enumerate(lines):
            sec = max(1.0, len(t) / 6.0)
            if limit_sec is not None and used + sec > limit_sec:
                sec = max(0.3, limit_sec - used)          # 한도에서 뚝 끊긴다
                if sec <= 0.35:
                    break
            used += sec
            if i:
                ins += ["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono:d=1.0"]
                chain.append(f"[{k}:a]")
                k += 1
                used += 1.0
            ins += ["-f", "lavfi",
                    "-i", f"sine=frequency={hz}:duration={sec:.2f}:sample_rate=24000"]
            chain.append(f"[{k}:a]")
            k += 1
            if limit_sec is not None and used >= limit_sec:
                break
        f = "".join(chain) + f"concat=n={k}:v=0:a=1[a]"
        subprocess.run(["ffmpeg", "-v", "error", "-y"] + ins +
                       ["-filter_complex", f, "-map", "[a]", "-b:a", "160k", str(out_mp3)],
                       check=True)
        return out_mp3
    return go


class FakePool:
    models = ["m"]

    def wait_for(self, m):
        return m

    def penalize(self, m, s):
        pass


doc = json.loads((Path(__file__).resolve().parent.parent
                  / "data/scripts/EP001.json").read_text(encoding="utf-8"))
cuts = [c for a in doc["acts"] for c in a["cuts"]]
speakers = sorted({c.get("speaker", "narrator") for c in cuts})
PIN = {s: "m" for s in speakers}


def fresh():
    shutil.rmtree(T, ignore_errors=True)
    T.mkdir(parents=True)
    CALLS.clear()


print("=" * 72)
print("  시험 1 — 평범한 경우: 114컷을 몇 번 불러서 만드나")
print("=" * 72)
fresh()
tts.synth_group = fake_synth()
book = {}
done = tts.make_groups(FakePool(), "k", cuts, T, PIN, book)
want = [c["id"] for c in cuts if (c.get("text") or "").strip()]
check("모든 컷이 만들어졌다", len(done) == len(want), f"{len(done)}/{len(want)}컷")
check("호출 수가 크게 줄었다", len(CALLS) <= 12, f"{len(CALLS)}번 (예전 {len(want)}번)")
check("조리법이 다 적혔다", all(c in book for c in done), f"{len(book)}개")
missing = [c for c in want if not (T / f"{c}.mp3").exists()]
check("빠진 파일이 없다", not missing, f"빠진 것 {missing[:3]}")

# ⭐ 핵심: 손님이 지적한 세 줄이 **같은 통**에서 나왔는가 = 같은 목소리인가
import importlib  # noqa: E402
hz = {c: tts.measure_f0(T / f"{c}.mp3") for c in ("H04", "H05", "A1-01")}
print(f"        H04 {hz['H04']:.0f}Hz · H05 {hz['H05']:.0f}Hz · A1-01 {hz['A1-01']:.0f}Hz")
spread = max(hz.values()) - min(hz.values())
check("H04·H05·A1-01 이 같은 목소리다", spread < 1.0, f"세 줄의 높이 차이 {spread:.1f}Hz")

print("\n" + "=" * 72)
print("  시험 2 — 길이 한도에 걸리는 경우: 쪼개서 살려내나")
print("=" * 72)
fresh()
tts.synth_group = fake_synth(limit_sec=60)      # 60초에서 뚝 끊는 모델
book = {}
done = tts.make_groups(FakePool(), "k", cuts, T, PIN, book)
check("그래도 대부분 살려냈다", len(done) >= len(want) * 0.7,
      f"{len(done)}/{len(want)}컷 ({len(done) * 100 // len(want)}%)")
bad = [c for c in done if not (T / f"{c}.mp3").exists()]
check("만들었다고 한 것은 진짜 있다", not bad, f"거짓 {bad[:3]}")

print("\n" + "=" * 72)
print("  시험 3 — 이미 있는 컷은 건드리지 않나 (돈 두 번 안 쓰나)")
print("=" * 72)
CALLS.clear()
done2 = tts.make_groups(FakePool(), "k", cuts, T, PIN, {})
check("이미 만든 컷은 다시 안 부른다", len(CALLS) <= 4,
      f"{len(CALLS)}번 (남아 있던 {len(want) - len(done)}컷 몫)")

print("\n" + "=" * 72)
print("  시험 4 — 묶기를 끄면 예전 방식 그대로인가")
print("=" * 72)
fresh()
tts.GROUP_ON = False
done3 = tts.make_groups(FakePool(), "k", cuts, T, PIN, {})
check("아무것도 안 만든다(예전 방식이 맡는다)", not done3 and not CALLS,
      f"{len(done3)}컷 · 호출 {len(CALLS)}번")
tts.GROUP_ON = True

print("\n" + "=" * 72)
print("  시험 5 — 묶어 읽기가 안 통하는 모델이면 **두 번 만에 그만두나** (값 아끼기)")
print("=" * 72)
fresh()


def never_pauses(key, model, lines, speaker, out_mp3, rotate=False):
    """쉬지 않고 붙여 읽는 모델 — 자를 수가 없다. 실제로 있을 수 있는 경우다."""
    CALLS.append((speaker, len(lines)))
    sec = sum(max(1.0, len(t) / 6.0) for _, t in lines)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"sine=frequency=110:duration={sec:.2f}:sample_rate=24000",
                    "-b:a", "160k", str(out_mp3)], check=True)
    return out_mp3


tts.synth_group = never_pauses
done5 = tts.make_groups(FakePool(), "k", cuts, T, PIN, {})
check("아무 컷도 안 만들었다(예전 방식이 맡는다)", not done5, f"{len(done5)}컷")
# 묶음 2개 × (본판 1 + 반쪽 2) = 최대 6번. 8묶음을 다 시도하면 18번이 넘는다.
check("두 묶음까지만 시도하고 멈췄다", len(CALLS) <= 6,
      f"호출 {len(CALLS)}번 (안 막으면 18번 넘게 나간다)")
# 검사에 떨어진 통은 보관하면 안 된다 — 다음 실행마다 그 통으로 또 떨어진다
check("떨어진 통은 보관하지 않았다", not list(T.glob("_master_*.mp3")),
      f"{len(list(T.glob('_master_*.mp3')))}통")

print("\n" + "=" * 72)
print("  시험 6 — 자르기만 또 고쳐도 보관된 원본으로 다시 자르나 (0원)")
print("=" * 72)
fresh()
tts.synth_group = fake_synth()
done6 = tts.make_groups(FakePool(), "k", cuts, T, PIN, {})
masters = sorted(T.glob("_master_*.mp3"))
check("잘 잘린 통의 원본이 보관됐다", len(masters) >= 5, f"{len(masters)}통")
# 자르기 방식이 바뀌면 컷은 전부 지워진다(조리법 표시가 달라서) — 그 상황을 흉내 낸다
for c in want:
    (T / f"{c}.mp3").unlink(missing_ok=True)
n_before = len(CALLS)
done6b = tts.make_groups(FakePool(), "k", cuts, T, PIN, {})
check("모든 컷이 다시 만들어졌다", len(done6b) == len(want),
      f"{len(done6b)}/{len(want)}컷")
check("한 번도 새로 부르지 않았다 — 0원", len(CALLS) == n_before,
      f"새 호출 {len(CALLS) - n_before}번")

print("\n" + "=" * 72)
print("  모두 통과" if not fails else f"  실패 {len(fails)}건: {fails}")
print("=" * 72)
sys.exit(1 if fails else 0)
