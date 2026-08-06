#!/usr/bin/env python3
"""묶어서 읽힌 소리를 **제대로 잘라내는지** 시험한다. 제미나이는 안 부른다.

가짜 '한 통' 을 만든다: 문장마다 길이가 다르고, 사이에 쉼이 들어간다.
쉼표 자리에도 짧은 쉼을 섞어 **가짜 후보**를 일부러 만든다 — 진짜 어려운 경우다.
"""
import subprocess
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import tts  # noqa: E402

T = Path(tempfile.mkdtemp(prefix="vt-split-"))
fails = []


def check(label, cond, extra=""):
    print(f"  {'OK  ' if cond else 'FAIL'} {label} {extra}")
    if not cond:
        fails.append(label)


def tone(sec, hz=110):
    return f"sine=frequency={hz}:duration={sec:.2f}:sample_rate=24000"


def build(parts, path):
    """parts = [('말', 초) | ('쉼', 초)] 를 이어 붙여 한 통을 만든다."""
    ins, chain, k = [], [], 0
    for kind, sec in parts:
        if kind == "말":
            ins += ["-f", "lavfi", "-i", tone(sec)]
        else:
            ins += ["-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono:d={sec:.2f}"]
        chain.append(f"[{k}:a]")
        k += 1
    f = "".join(chain) + f"concat=n={k}:v=0:a=1[a]"
    subprocess.run(["ffmpeg", "-v", "error", "-y"] + ins +
                   ["-filter_complex", f, "-map", "[a]", "-b:a", "160k", str(path)],
                   check=True)


def run(name, lines, parts, expect_ok):
    T.mkdir(parents=True, exist_ok=True)
    big = T / "big.mp3"
    build(parts, big)
    for cid, _ in lines:
        (T / f"{cid}.mp3").unlink(missing_ok=True)
    made = tts.split_group(big, lines, T)
    ok = bool(made)
    check(f"{name} — {'잘라야 함' if expect_ok else '거절해야 함'}", ok == expect_ok,
          f"(결과: {'잘랐다 ' + str(len(made)) + '컷' if ok else '거절'})")
    if ok and expect_ok:
        durs = []
        for cid, txt in lines:
            p = T / f"{cid}.mp3"
            r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "format=duration", "-of", "csv=p=0", str(p)],
                               capture_output=True, text=True)
            durs.append((cid, len(txt), float(r.stdout.strip())))
        for cid, n, d in durs:
            print(f"        {cid}  {n}자  {d:.2f}초")
        return durs
    return None


print("=" * 72)
print("  시험 1 — 반듯한 경우 (문장 사이 1초씩 쉼)")
print("=" * 72)
L = [("H02", "가" * 28), ("H03", "가" * 24), ("H04", "가" * 34), ("H05", "가" * 31)]
run("반듯한 4줄", L,
    [("말", 4.0), ("쉼", 1.0), ("말", 3.4), ("쉼", 1.0), ("말", 4.8), ("쉼", 1.0), ("말", 4.4)],
    True)

print("\n" + "=" * 72)
print("  시험 2 — 어려운 경우 (쉼표 자리에도 짧은 쉼 → 가짜 후보가 섞임)")
print("=" * 72)
d = run("쉼표가 섞인 4줄", L,
        [("말", 1.6), ("쉼", 0.32), ("말", 2.4), ("쉼", 1.0),        # H02 (쉼표 1개)
         ("말", 3.4), ("쉼", 1.0),                                    # H03
         ("말", 2.2), ("쉼", 0.30), ("말", 2.6), ("쉼", 1.0),         # H04 (쉼표 1개)
         ("말", 4.4)],                                                # H05
        True)
if d:
    # 문장 경계에서 잘렸는지 — 각 도막이 '말' 부분을 온전히 담아야 한다
    want = {"H02": 4.0 + 0.32, "H03": 3.4, "H04": 4.8 + 0.30, "H05": 4.4}
    worst = max(abs(x[2] - want[x[0]] - 0.5) for x in d)   # 쉼 절반씩 붙는다
    check("문장 경계에서 잘렸다", worst < 0.6, f"가장 큰 오차 {worst:.2f}초")

print("\n" + "=" * 72)
print("  시험 3 — 쉼이 아예 없는 경우 → **거절해야 한다**")
print("=" * 72)
run("쉼 없는 4줄", L, [("말", 16.0)], False)

print("\n" + "=" * 72)
print("  시험 4 — 한 줄이 통째로 빠진 경우(모델이 안 읽음) → **거절해야 한다**")
print("=" * 72)
run("3줄만 읽힌 4줄", L,
    [("말", 4.0), ("쉼", 1.0), ("말", 3.4), ("쉼", 1.0), ("말", 4.8)], False)

print("\n" + "=" * 72)
print("  시험 5 — 도중에 잘려 끝난 경우(길이 초과) → **거절해야 한다**")
print("=" * 72)
run("중간에 끊긴 4줄", L,
    [("말", 4.0), ("쉼", 1.0), ("말", 3.4), ("쉼", 1.0), ("말", 0.5)], False)

print("\n" + "=" * 72)
print("  시험 6 — 한 줄을 **웅얼거려 거의 안 들리는** 경우 → 거절해야 한다")
print("=" * 72)
# 왜 이 시험이 있나 (2026-08-06)
#   모델이 한 줄을 아주 작게 읽으면, 무음 검출로는 안 잡히고 길이도 멀쩡하다.
#   그런데 앞뒤 빈 소리를 잘라내면 그 도막이 통째로 사라진다 →
#   **자막은 뜨는데 목소리가 안 나오는 컷**이 된다. 영상에서 가장 나쁜 사고다.
#   길이만 재면 못 잡는다 — 소리 크기까지 재야 잡힌다.
T.mkdir(parents=True, exist_ok=True)
big6 = T / "big6.mp3"
secs = [4.0, 3.4, 4.8, 4.4]
ins, chain, k = [], [], 0
for i, sec in enumerate(secs):
    if i:
        ins += ["-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono:d=1.0"]
        chain.append(f"[{k}:a]")
        k += 1
    ins += ["-f", "lavfi", "-i", tone(sec)]
    if i == 2:                                   # 세 번째 줄만 -60dB (웅얼거림)
        chain.append(f"[m{k}]")
        pre = f"[{k}:a]volume=-60dB[m{k}];"
    else:
        chain.append(f"[{k}:a]")
        pre = ""
    chain.insert(0, pre) if pre else None
    k += 1
head = "".join(x for x in chain if x.endswith(";"))
body = "".join(x for x in chain if not x.endswith(";"))
subprocess.run(["ffmpeg", "-v", "error", "-y"] + ins +
               ["-filter_complex", head + body + f"concat=n={k}:v=0:a=1[a]",
                "-map", "[a]", "-b:a", "160k", str(big6)], check=True)
for cid, _ in L:
    (T / f"{cid}.mp3").unlink(missing_ok=True)
made6 = tts.split_group(big6, L, T)
check("웅얼거린 줄이 있으면 거절한다", not made6,
      "(결과: 잘랐다 — 위험!)" if made6 else "(결과: 거절)")
left6 = [c for c, _ in L if (T / f"{c}.mp3").exists()]
check("거절할 때 반쪽 파일을 안 남긴다", not left6, f"남은 것 {left6}")

print("\n" + "=" * 72)
print("  모두 통과" if not fails else f"  실패 {len(fails)}건: {fails}")
print("=" * 72)
sys.exit(1 if fails else 0)
