#!/usr/bin/env python3
"""**전체 흐름을 끝까지 돌려 본다.** 제미나이만 가짜로 바꾸고 나머지는 진짜 코드다.

왜 이 시험이 필요한가 (2026-08-06 · 손님: "돈 낭비 안 하게 다시 검증해")
    지금까지 시험은 함수 하나씩만 따로 불러 봤다. 그런데 실제 사고는 늘
    **함수와 함수가 이어지는 자리**에서 났다 —
      · 만드는 방식을 바꿨는데 조리법이 그대로라 옛 음성이 재사용됨
      · 열쇠 확인용 한 컷만 혼자 만들어져 첫 대사가 튐
      · 다시 읽히는 몫을 앞 인물이 다 써서 정작 심한 컷에 못 닿음
    셋 다 함수 하나만 보면 멀쩡하다. 그래서 **main() 을 통째로** 돌려 본다.

가짜 제미나이가 흉내 내는 것
    · 글자 수에 비례한 길이로 말하고 문장 사이에 쉰다
    · **호출마다 목소리 높이가 달라진다** (이것이 진짜 문제다)
    · 부른 횟수를 세어 둔다 → 값이 얼마나 나갈지 그대로 보인다
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
CALLS = {"one": [], "group": []}


def check(label, cond, extra=""):
    print(f"  {'OK  ' if cond else 'FAIL'} {label} {extra}")
    if not cond:
        fails.append(label)


def _wav(path, hz, sec):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                    "-i", f"sine=frequency={hz:.1f}:duration={sec:.2f}:sample_rate=24000",
                    "-af", "tremolo=f=5:d=0.7", "-b:a", "160k", str(path)], check=True)


def install_fakes(drift=True):
    """진짜 통신 함수만 갈아 끼운다. 나머지 로직은 그대로 돈다."""
    CALLS["one"].clear()
    CALLS["group"].clear()

    def fake_models(key):
        return ["gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts",
                "gemini-2.5-pro-preview-tts"]

    def fake_one(key, model, text, speaker, out_mp3, rotate=False):
        CALLS["one"].append((speaker, out_mp3.stem))
        base = {"narrator": 84, "v_F50A": 175, "v_M50A": 120,
                "v_M50B": 147, "v_JUDGE": 120}.get(speaker, 110)
        # 컷마다 따로 부르면 매번 딴 사람 — 이것이 실제로 일어난 일이다
        hz = base * (2 ** (((len(CALLS["one"]) * 37) % 17 - 8) / 12.0)) if drift else base
        _wav(out_mp3, hz, max(1.2, len(text) / 6.0))
        return out_mp3

    def fake_group(key, model, lines, speaker, out_mp3, rotate=False):
        CALLS["group"].append((speaker, len(lines)))
        base = {"narrator": 84, "v_F50A": 175, "v_M50A": 120,
                "v_M50B": 147, "v_JUDGE": 120}.get(speaker, 110)
        # ⭐ 한 통 안에서는 **끝까지 같은 목소리** — 이것이 새 방식의 핵심이다
        hz = base * (2 ** (((len(CALLS["group"]) * 5) % 7 - 3) / 12.0)) if drift else base
        ins, chain, k = [], [], 0
        for i, (_cid, t) in enumerate(lines):
            if i:
                ins += ["-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono:d=1.0"]
                chain.append(f"[{k}:a]")
                k += 1
            ins += ["-f", "lavfi",
                    "-i", f"sine=frequency={hz:.1f}:duration={max(1.2, len(t) / 6.0):.2f}"
                          ":sample_rate=24000"]
            chain.append(f"[{k}:a]")
            k += 1
        f = "".join(chain) + f"concat=n={k}:v=0:a=1[a]"
        subprocess.run(["ffmpeg", "-v", "error", "-y"] + ins +
                       ["-filter_complex", f, "-map", "[a]", "-b:a", "160k", str(out_mp3)],
                       check=True)
        return out_mp3

    tts.tts_models = fake_models
    tts.synth_one = fake_one
    tts.synth_group = fake_group


def run_main(out, extra=()):
    argv = sys.argv
    sys.argv = ["tts.py", str(ROOT / "data/scripts/EP001.json"), "--out", str(out), *extra]
    try:
        return tts.main()
    finally:
        sys.argv = argv


# ⭐ 어느 코드를 시험했는지 반드시 찍는다.
#    작업 공간이 옛 커밋으로 되돌아간 채 시험이 돌아 "통과" 가 나온 적이 있다.
#    그 통과는 아무 뜻이 없다 — 무엇을 시험했는지 모르는 결과이기 때문이다.
_head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                       capture_output=True, text=True).stdout.strip()
print(f"시험 대상 코드: {_head}"
      f" · 묶어읽기={'있음' if hasattr(tts, 'make_groups') else '없음'}"
      f" · 인물못박기={'있음' if hasattr(tts, 'persona') else '없음'}"
      f" · 최대이동={tts._pitch_max():.1f}반음\n")
assert hasattr(tts, "make_groups") and hasattr(tts, "persona"), \
    "고친 코드가 아니다 — git reset --hard origin/main 후 다시 돌려라"

SCRIPT = json.loads((ROOT / "data/scripts/EP001.json").read_text(encoding="utf-8"))
WANT = [c["id"] for a in SCRIPT["acts"] for c in a["cuts"] if (c.get("text") or "").strip()]

print("=" * 74)
print("  시험 1 — 아무것도 없는 상태에서 한 편을 통째로 만든다")
print("=" * 74)
OUT = Path(tempfile.mkdtemp(prefix="vt-e2e-"))
install_fakes()
rc = run_main(OUT)
check("정상 종료", rc in (0, None), f"종료코드={rc}")
missing = [c for c in WANT if not (OUT / f"{c}.mp3").exists()]
check("모든 컷이 만들어졌다", not missing, f"빠진 것 {len(missing)}개 {missing[:3]}")
n_call = len(CALLS["one"]) + len(CALLS["group"])
print(f"        호출: 묶음 {len(CALLS['group'])}번 + 낱개 {len(CALLS['one'])}번 = {n_call}번")
check("호출이 크게 줄었다 (값 절약)", n_call <= 20, f"{n_call}번 (예전 방식 {len(WANT)}번)")
leftover = list(OUT.glob("_group*"))
check("찌꺼기 파일이 안 남았다", not leftover, f"{[p.name for p in leftover][:3]}")

print("\n" + "=" * 74)
print("  시험 2 — 인물마다 한 목소리인가 (검사기로 실제 판정)")
print("=" * 74)
r = subprocess.run([sys.executable, str(ROOT / "src/voiceguard.py"),
                    str(ROOT / "data/scripts/EP001.json"), "--voice", str(OUT)],
                   capture_output=True, text=True)
print("\n".join("        " + x for x in r.stdout.strip().splitlines()))
check("목소리 검사 통과", r.returncode == 0, f"종료코드={r.returncode}")

print("\n" + "=" * 74)
print("  시험 3 — 다시 눌렀을 때 **값이 또 나가지 않나** (재사용)")
print("=" * 74)
install_fakes()
rc = run_main(OUT)
again = len(CALLS["one"]) + len(CALLS["group"])
check("두 번째 실행은 공짜다", again == 0, f"호출 {again}번")

print("\n" + "=" * 74)
print("  시험 4 — 묶어 읽기가 통째로 고장 나도 영상은 나오나 (되돌아가기)")
print("=" * 74)
OUT2 = Path(tempfile.mkdtemp(prefix="vt-e2e2-"))
install_fakes()


def broken_group(*a, **k):
    CALLS["group"].append(("broken", 0))
    raise tts.LLMError("일부러 고장")


tts.synth_group = broken_group
rc = run_main(OUT2)
missing2 = [c for c in WANT if not (OUT2 / f"{c}.mp3").exists()]
check("그래도 모든 컷이 만들어졌다", not missing2, f"빠진 것 {len(missing2)}개")
check("낱개로 되돌아갔다", len(CALLS["one"]) >= len(WANT) * 0.9,
      f"낱개 {len(CALLS['one'])}번")

print("\n" + "=" * 74)
print("  시험 5 — 대본을 고치면 그 컷만 새로 만드나 (돈 낭비 방지)")
print("=" * 74)
tmp_script = Path(tempfile.mkdtemp(prefix="vt-e2e3-")) / "EP001.json"
doc = json.loads(json.dumps(SCRIPT))
doc["acts"][0]["cuts"][1]["text"] = "고친 대사입니다. 이 컷만 새로 만들어져야 합니다."
tmp_script.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
shutil.copy(ROOT / "data/scripts/EP001.shorts.json",
            tmp_script.with_suffix(".shorts.json")) if (
    ROOT / "data/scripts/EP001.shorts.json").exists() else None
install_fakes()
argv = sys.argv
sys.argv = ["tts.py", str(tmp_script), "--out", str(OUT)]
try:
    tts.main()
finally:
    sys.argv = argv
changed = len(CALLS["one"]) + len(CALLS["group"])
check("고친 컷만 다시 만든다", 1 <= changed <= 3, f"호출 {changed}번")

print("\n" + "=" * 74)
print("  모두 통과" if not fails else f"  실패 {len(fails)}건: {fails}")
print("=" * 74)
sys.exit(1 if fails else 0)
