#!/usr/bin/env python3
"""목소리 검사기(voiceguard)와 해설 통 맞추기(align_narrator)를 시험한다. 값 0원.

2026-08-08 실전 실패를 그대로 재현해 막는다:
    해설 통 하나가 다른 통보다 높았고, 검사기는 컷 단위로만 재서
    같은 통 안의 억양(H02 +4.6반음)까지 묶어 '흩어졌다'며 실행을 막았다.
    이미 만든 음성(약 709원어치)이 있는데도 영상이 안 나왔다.

시험 목록
    1. 같은 통 안의 억양 튐   → 통과해야 한다 (예전 코드는 여기서 막았다)
    2. 통끼리 진짜 벌어짐      → 막아야 한다
    3. 통 맞추기: 벌어진 통만 다시 읽혀 맞춘다 (호출 수 제한)
    4. 통 맞추기: 새로 읽힌 것이 더 나쁘면 예전 통을 되살린다 (돈만 쓰고 끝나지 않는다)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.environ.setdefault("GEMINI_API_KEY", "fake-key-for-test")
import tts  # noqa: E402

fails = []
CALLS = []


def check(label, cond, extra=""):
    print(f"  {'OK  ' if cond else 'FAIL'} {label} {extra}")
    if not cond:
        fails.append(label)


def sine(path, hz, sec=3.0):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"sine=frequency={hz:.1f}:duration={sec:.2f}:sample_rate=24000",
                    "-b:a", "160k", str(path)], check=True)


def st(n):
    """n 반음 위의 배율."""
    return 2 ** (n / 12.0)


# 해설 12컷 = 통 A(앞 6컷) + 통 B(뒤 6컷)
CUTS = [{"id": f"N{i:02d}", "speaker": "narrator",
         "text": "가나다라마바사아자차카타파하 그날의 이야기가 이어집니다."}
        for i in range(1, 13)]
A, B = [c["id"] for c in CUTS[:6]], [c["id"] for c in CUTS[6:]]
BASE = 90.0


def build(vdir, b_offset, a_outlier=None):
    """통 A는 90Hz, 통 B는 b_offset 반음 위로. a_outlier 컷만 따로 더 올린다."""
    shutil.rmtree(vdir, ignore_errors=True)
    vdir.mkdir(parents=True)
    for cid in A:
        sine(vdir / f"{cid}.mp3",
             BASE * st(a_outlier[1]) if a_outlier and cid == a_outlier[0] else BASE)
    for cid in B:
        sine(vdir / f"{cid}.mp3", BASE * st(b_offset))
    gmap = {c: "takeA" for c in A}
    gmap.update({c: "takeB" for c in B})
    (vdir / "groups.json").write_text(json.dumps(gmap), encoding="utf-8")
    return gmap


T = Path(tempfile.mkdtemp(prefix="vt-guard-"))
SCRIPT = T / "EP.json"
SCRIPT.write_text(json.dumps({"acts": [{"cuts": CUTS}]}, ensure_ascii=False),
                  encoding="utf-8")
V = T / "voice"


def guard():
    r = subprocess.run([sys.executable, str(ROOT / "src/voiceguard.py"),
                        str(SCRIPT), "--voice", str(V)],
                       capture_output=True, text=True)
    return r.returncode, r.stdout


print("=" * 72)
print("  시험 1 — 같은 통 안의 억양 튐(+6반음 한 컷)은 막지 않는다")
print("=" * 72)
build(V, b_offset=2.0, a_outlier=("N03", 6.0))    # 통끼리는 2반음(정상 범위)
rc, out1 = guard()
check("통과한다 (예전 코드는 여기서 막았다)", rc == 0, f"종료코드={rc}")
check("억양이라고 알려준다", "억양" in out1)

print("\n" + "=" * 72)
print("  시험 2 — 통끼리 6.5반음 벌어지면 막는다")
print("=" * 72)
build(V, b_offset=6.5)
rc, out2 = guard()
check("막는다", rc == 1, f"종료코드={rc}")
check("통끼리 벌어졌다고 말한다", "통끼리" in out2)
check("보관함을 지우라는 옛 조언이 없다", "보관함을 지우고" not in out2)


class FakePool:
    models = ["m"]

    def wait_for(self, m):
        return m

    def penalize(self, m, s):
        pass


def fake_group(hz):
    """다시 읽히면 hz 로 나오는 가짜 제미나이 (줄 사이 1초 쉼 포함)."""
    def go(key, model, lines, speaker, out_mp3, rotate=False):
        CALLS.append(len(lines))
        ins, chain, k = [], [], 0
        for i, (_cid, t) in enumerate(lines):
            if i:
                ins += ["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono:d=1.0"]
                chain.append(f"[{k}:a]")
                k += 1
            sec = max(1.0, len(t) / 6.0)
            ins += ["-f", "lavfi",
                    "-i", f"sine=frequency={hz:.1f}:duration={sec:.2f}:sample_rate=24000"]
            chain.append(f"[{k}:a]")
            k += 1
        f = "".join(chain) + f"concat=n={k}:v=0:a=1[a]"
        subprocess.run(["ffmpeg", "-v", "error", "-y"] + ins +
                       ["-filter_complex", f, "-map", "[a]", "-b:a", "160k",
                        str(out_mp3)], check=True)
        return out_mp3
    return go


PIN = {"narrator": "m"}

print("\n" + "=" * 72)
print("  시험 3 — 벌어진 통(B)만 다시 읽혀 맞춘다")
print("=" * 72)
gmap = build(V, b_offset=6.5)
CALLS.clear()
tts.synth_group = fake_group(BASE)          # 다시 읽히면 A와 같은 높이로 나온다
book = {}
tts.align_narrator(FakePool(), "k", CUTS, V, PIN, book, gmap)
rc, out3 = guard()
check("맞춘 뒤에는 검사를 통과한다", rc == 0, f"종료코드={rc}")
check("호출을 아꼈다 (통 하나 = 1번)", 1 <= len(CALLS) <= 2, f"{len(CALLS)}번")
check("A통(멀쩡한 쪽)은 안 건드렸다", all(gmap[c] == "takeA" for c in A))
check("B통 이름표가 새 통으로 바뀌었다", all(gmap[c] != "takeB" for c in B))
check("조리법도 적혔다", all(c in book for c in B), f"{len(book)}개")

print("\n" + "=" * 72)
print("  시험 4 — 다시 읽힌 것이 더 나쁘면 예전 통을 되살린다")
print("=" * 72)
gmap = build(V, b_offset=6.5)
before = {c: (V / f"{c}.mp3").read_bytes() for c in B}
CALLS.clear()
tts.synth_group = fake_group(BASE * st(13.0))   # 다시 읽히면 더 심하게 벗어난다
tts.align_narrator(FakePool(), "k", CUTS, V, PIN, {}, gmap)
same = all((V / f"{c}.mp3").read_bytes() == before[c] for c in B)
check("예전 통이 그대로 남아 있다", same)
check("이름표도 예전 그대로다", all(gmap[c] == "takeB" for c in B))
check("시도 횟수가 제한된다", len(CALLS) <= tts.ALIGN_TRIES, f"{len(CALLS)}번")
leftover = list(V.glob("_align_bak/*")) + list(V.glob("_group*"))
check("찌꺼기 파일이 없다", not leftover, f"{[p.name for p in leftover][:3]}")

print("\n" + "=" * 72)
print("  모두 통과" if not fails else f"  실패 {len(fails)}건: {fails}")
print("=" * 72)
sys.exit(1 if fails else 0)
