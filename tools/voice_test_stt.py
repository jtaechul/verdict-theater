#!/usr/bin/env python3
"""받아쓰기 대조(stt_verify)를 시험한다. 제미나이는 안 부른다(전사·합성 모두 가짜).

2026-08-08 손님 지시: "대본에서 나레이션 누락되는 거 없도록."
길이 짐작 검사(50~200% 띠, 이웃 짝)는 두 번 뚫렸다(A1-19, A1-18).
받아쓰기 대조는 소리를 글로 받아 적어 **내용으로** 대조하므로 이 유형을 뿌리에서 잡는다.

시험 목록
    1. 다 맞으면 → 통과, 아무것도 안 만든다 (0원)
    2. 한 컷의 꼬리가 빠졌으면 → 그 통만 새로 만들어 다시 맞춘다
    3. 전사 자체가 안 되면 → 막지 않고 알리기만 한다 (장애로 발이 묶이면 안 된다)
    4. 다시 만들어도 안 맞으면 → 렌더링 전에 멈춘다 (사람이 들어봐야 한다)
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
SYNTH = []


def check(label, cond, extra=""):
    print(f"  {'OK  ' if cond else 'FAIL'} {label} {extra}")
    if not cond:
        fails.append(label)


CUTS = [{"id": f"D{i}", "speaker": "narrator",
         "text": f"나레이션 {i}번 문장입니다 그날의 기록이 이렇게 이어집니다"}
        for i in range(1, 13)]
A, B = [c["id"] for c in CUTS[:6]], [c["id"] for c in CUTS[6:]]
TEXT = {c["id"]: c["text"] for c in CUTS}


def fake_group(key, model, lines, speaker, out_mp3, rotate=False):
    """가짜 제미나이 — 줄 사이 1초 쉼을 지키는 소리를 만든다."""
    SYNTH.append(len(lines))
    ins, chain, k = [], [], 0
    for i, (_cid, t) in enumerate(lines):
        if i:
            ins += ["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono:d=1.0"]
            chain.append(f"[{k}:a]")
            k += 1
        ins += ["-f", "lavfi", "-i",
                f"sine=frequency=95:duration={max(1.0, len(t) / 6.0):.2f}"
                ":sample_rate=24000"]
        chain.append(f"[{k}:a]")
        k += 1
    subprocess.run(["ffmpeg", "-v", "error", "-y"] + ins +
                   ["-filter_complex", "".join(chain) + f"concat=n={k}:v=0:a=1[a]",
                    "-map", "[a]", "-b:a", "160k", str(out_mp3)], check=True)
    return out_mp3


class FakePool:
    models = ["m"]

    def wait_for(self, m):
        return m

    def penalize(self, m, s):
        pass


def build(vdir):
    """컷 파일 + 이름표를 깐다 (통 A·B 각 6컷)."""
    shutil.rmtree(vdir, ignore_errors=True)
    vdir.mkdir(parents=True)
    for cid in A + B:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                        "-i", "sine=frequency=95:duration=3:sample_rate=24000",
                        "-b:a", "160k", str(vdir / f"{cid}.mp3")], check=True)
    gmap = {c: "takeA" for c in A}
    gmap.update({c: "takeB" for c in B})
    return gmap


T = Path(tempfile.mkdtemp(prefix="vt-stt-"))
V = T / "voice"
PIN = {"narrator": "m"}
tts.synth_group = fake_group
tts.make_one = lambda *a, **k: (RuntimeError("낱개 호출 금지"), None)

print("=" * 72)
print("  시험 1 — 다 맞으면 통과하고 아무것도 안 만든다 (0원)")
print("=" * 72)
gmap = build(V)
SYNTH.clear()
tts.transcribe_pieces = lambda key, files: [TEXT[f.stem] for f in files]
ok = tts.stt_verify(FakePool(), "k", CUTS, V, PIN, {}, gmap)
check("통과한다", ok is True)
check("아무것도 새로 안 만든다", not SYNTH, f"호출 {len(SYNTH)}번")

print("\n" + "=" * 72)
print("  시험 2 — 꼬리 빠진 컷(D2)이 있으면 그 통만 새로 만들어 맞춘다")
print("=" * 72)
gmap = build(V)
SYNTH.clear()
STATE = {"broken": True}


def stt_broken_d2(key, files):
    out = []
    for f in files:
        t = TEXT[f.stem]
        # 수선 전에는 D2 의 뒷문장이 소리에 없다 (A1-18 사고 재현)
        out.append(t[:8] if STATE["broken"] and f.stem == "D2" else t)
    return out


def synth_and_heal(key, model, lines, speaker, out_mp3, rotate=False):
    STATE["broken"] = False            # 새로 읽히면 온전한 소리가 나온다
    return fake_group(key, model, lines, speaker, out_mp3, rotate)


tts.transcribe_pieces = stt_broken_d2
tts.synth_group = synth_and_heal
book2 = {}
ok = tts.stt_verify(FakePool(), "k", CUTS, V, PIN, book2, gmap)
check("수선 후 통과한다", ok is True)
check("통 하나만 새로 만들었다", len(SYNTH) == 1, f"호출 {len(SYNTH)}번")
check("B통(멀쩡한 쪽)은 안 건드렸다", all(gmap[c] == "takeB" for c in B))
check("A통 이름표가 새 통으로 바뀌었다", all(gmap[c] != "takeA" for c in A))
check("조리법이 적혔다", all(c in book2 for c in A), f"{len(book2)}개")

print("\n" + "=" * 72)
print("  시험 3 — 전사가 안 되면 막지 않고 알리기만 한다")
print("=" * 72)
gmap = build(V)
SYNTH.clear()
tts.synth_group = fake_group
tts.transcribe_pieces = lambda key, files: None
ok = tts.stt_verify(FakePool(), "k", CUTS, V, PIN, {}, gmap)
check("막지 않는다", ok is True)
check("아무것도 새로 안 만든다", not SYNTH, f"호출 {len(SYNTH)}번")

print("\n" + "=" * 72)
print("  시험 4 — 통을 다시 만들어도 안 맞으면 **그 컷만 혼자** 만들고 계속 간다")
print("=" * 72)
# 손님 요구(2026-08-08): "영상 제작 누르면 또 실패하는 거 아니야? 그런 일 없게 해."
# 받아쓰기가 안 맞는다고 영상을 통째로 못 만들면 그것도 실패다.
# 한 줄만 혼자 읽히면 **자를 일이 없어** 문장이 잘릴 수 없다 — 그 길로 빠져나간다.
gmap = build(V)
SYNTH.clear()
ALONE = []
tts.transcribe_pieces = \
    lambda key, files: [TEXT[f.stem][:8] if f.stem == "D2" else TEXT[f.stem]
                        for f in files]


def fake_one(pool, key, text, speaker, out_mp3, tries=2, pinned=None):
    ALONE.append(out_mp3.stem)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=95:duration=3:sample_rate=24000",
                    "-b:a", "160k", str(out_mp3)], check=True)
    return None, "m"


tts.make_one = fake_one
book4 = {}
ok = tts.stt_verify(FakePool(), "k", CUTS, V, PIN, book4, gmap)
check("영상은 계속 만든다 (멈추지 않는다)", ok is True)
check("문제 컷만 혼자 다시 만들었다", ALONE == ["D2"], f"{ALONE}")
check("혼자 만든 컷의 조리법이 적혔다", book4.get("D2", "").endswith("|s1"),
      book4.get("D2", "(없음)"))
check("통 수선은 한 번만 시도했다", len(SYNTH) == 1, f"호출 {len(SYNTH)}번")

print("\n" + "=" * 72)
print("  시험 5 — 소리를 아예 못 만들면 그때는 멈춘다 (무음이 나가면 안 된다)")
print("=" * 72)
gmap = build(V)
SYNTH.clear()
tts.make_one = lambda *a, **k: (RuntimeError("한도 초과"), None)


def synth_hole(key, model, lines, speaker, out_mp3, rotate=False):
    SYNTH.append(len(lines))
    raise tts.LLMError("한도 초과")     # 통도 못 만들고 낱개도 못 만드는 상황


tts.synth_group = synth_hole
tts.transcribe_pieces = \
    lambda key, files: [TEXT[f.stem][:8] if f.stem == "D2" else TEXT[f.stem]
                        for f in files]
ok = tts.stt_verify(FakePool(), "k", CUTS, V, PIN, {}, gmap)
check("멈춘다(False)", ok is False)
gone = [c for c in A if not (V / f"{c}.mp3").exists()]
check("소리가 비어 있는 컷이 실제로 생겼다", bool(gone), f"{len(gone)}컷")

print("\n" + "=" * 72)
print("  시험 6 — 받아쓰기 모델을 **이름으로 짐작하지 않고 목록에서 고른다**")
print("=" * 72)
# 2026-08-08 실제 실행: 'gemini-2.5-flash' 로 못 박아 뒀는데 그 이름이 안 통해
# 115컷 전부 '확인 못 했다' 로 지나갔다. 지켜준다던 장치가 조용히 놀고 있었다.
import types  # noqa: E402
FAKE_LIST = {"models": [
    {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.1-flash", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.1-flash-lite", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/gemini-3.1-flash-tts-preview", "supportedGenerationMethods": ["generateContent"]},
    {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
]}


class _Resp:
    def read(self): return json.dumps(FAKE_LIST).encode()
    def __enter__(self): return self
    def __exit__(self, *a): return False


tts.urllib.request.urlopen = lambda *a, **k: _Resp()
got = tts.stt_models("k")
check("소리를 못 내는 도구(임베딩)는 뺀다", "text-embedding-004" not in got)
check("음성 합성 전용(tts)도 뺀다", not any("tts" in g for g in got), f"{got}")
check("싼 flash 를 먼저 고른다", "flash" in got[0], f"1순위 {got[0]}")
check("lite 는 뒤로 미룬다", not got[0].endswith("lite"), f"{got}")

print("\n" + "=" * 72)
print("  모두 통과" if not fails else f"  실패 {len(fails)}건: {fails}")
print("=" * 72)
sys.exit(1 if fails else 0)
