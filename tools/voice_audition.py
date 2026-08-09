#!/usr/bin/env python3
"""**목소리 30개를 한 번에 들어보고, 높이를 재서 표로 만든다.**

    python3 tools/voice_audition.py                  # 전부
    python3 tools/voice_audition.py --only Orus,Umbriel
    python3 tools/voice_audition.py --dry            # 값 안 쓰고 계획만 보기

왜 (2026-08-09 손님: "나중에도 이러면 어떡해.
                     목소리를 바꾸고 싶은 사람이 있으면 어떻게 해야 되는지도 제안해 줘.")
    같은 실수를 세 번 했다 — Puck(들뜬), Algenib(쉰 목소리), Gacrux(186Hz 여자 음역).
    셋 다 **내가 구글이 붙인 설명만 보고 골랐기 때문**이다. 소리를 들어보지도,
    높이를 재보지도 않았다. 손님은 영상을 다 만든 뒤에야 귀로 아셨다.

    이제 **한 번에 다 들어보고 다 재 둔다.**
      ① 같은 대사를 목소리마다 한 번씩 읽힌다
      ② 높이(Hz)를 재서 data/voices.json 에 적는다 → 배역-목소리 검사가 이 표를 쓴다
      ③ 이름을 말해 주는 안내와 함께 한 파일로 이어 붙인다 → 관리자 페이지에서 재생

값
    목소리 하나에 짧은 대사 한 줄(4초 안팎). 30개면 약 2분치 = **약 250원, 한 번만.**
    그 뒤로는 누구 목소리를 바꾸든 이 파일을 다시 들으면 되므로 **0원**이다.
    ⚠️ 모델을 바꾸면 높이가 통째로 달라진다(실측: 같은 이름이 86Hz ↔ 186Hz).
       그때는 한 번 더 돌려야 한다.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

VOICES_JSON = ROOT / "data" / "voices.json"

# 들어볼 대사 — **장남 대사로 고정한다.**
#   배역에 맞는지 판단하려면 실제 대본에 나오는 말투로 들어야 한다.
#   짧아야 값이 안 든다(4초 안팎).
LINE = "어머니, 제가 받을 몫이 비잖아요. 법대로 하시죠."

# 연기 지시 — 목소리 자체를 비교해야 하므로 **모두에게 같은 지시**를 준다.
STYLE = "쉰 살 남자가 가족에게 말한다. 배우가 연기하듯 자연스럽게 말한다."

# Gemini TTS 가 주는 목소리 이름 30종.
#   ⚠️ 구글이 붙인 설명은 참고만 한다 — 'Mature(원숙한)' Gacrux 가 186Hz 였다.
#      **믿을 것은 여기서 직접 잰 값과 손님 귀뿐이다.**
ALL_VOICES = [
    "Achernar", "Achird", "Algenib", "Algieba", "Alnilam", "Aoede", "Autonoe",
    "Callirrhoe", "Charon", "Despina", "Enceladus", "Erinome", "Fenrir", "Gacrux",
    "Iapetus", "Kore", "Laomedeia", "Leda", "Orus", "Puck", "Pulcherrima",
    "Rasalgethi", "Sadachbia", "Sadaltager", "Schedar", "Sulafat", "Umbriel",
    "Vindemiatrix", "Zephyr", "Zubenelgenubi",
]

GAP = 0.6


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


def measure_hz(path):
    """목소리의 기본 높이(Hz). tts.py 가 쓰는 것과 같은 자를 쓴다."""
    try:
        from tts import measure_f0
        return measure_f0(path)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build/audition")
    ap.add_argument("--only", default="", help="이 목소리들만 (쉼표로 구분)")
    ap.add_argument("--line", default=LINE)
    ap.add_argument("--dry", action="store_true", help="값 안 쓰고 계획만 본다")
    a = ap.parse_args()

    names = [x.strip() for x in a.only.split(",") if x.strip()] or ALL_VOICES
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    sec = len(a.line) * 0.18                       # 한 글자 0.18초 어림
    print(f"목소리 {len(names)}개 · 대사 '{a.line}' ({len(a.line)}자 · 약 {sec:.0f}초)")
    print(f"어림값: 약 {len(names) * sec:.0f}초치 = 약 {len(names) * sec / 60 * 111:.0f}원")
    if a.dry:
        print("(--dry 라서 여기까지만 합니다. 값이 들지 않았습니다.)")
        return 0

    import tts

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        print("오류: GEMINI_API_KEY 가 없습니다.", file=sys.stderr)
        return 2
    model = os.environ.get("VT_AUDITION_MODEL", tts.CHAR_MODEL_ORDER[0])
    print(f"모델: {model}\n")

    # ⭐ **영상에 쓰는 것과 똑같은 길로 만든다.**
    #    따로 만든 길로 들려드리면 "여기서 들은 소리" 와 "영상에 나올 소리" 가
    #    달라진다. 그래서 임시 배역(_audition)을 하나 만들어 목소리만 갈아 끼운다.
    tts.VOICE_STYLE["_audition"] = (STYLE, 1.12)
    tts.BODY["_audition"] = tts.BODY.get("v_M50A", "")

    got, failed = {}, []
    for i, v in enumerate(names, 1):
        p = out / f"{i:02d}_{v}.mp3"
        try:
            if not p.exists():
                tts.VOICE_NAME["_audition"] = v
                tts.synth_one(key, model, a.line, "_audition", p)
            hz = measure_hz(p)
            got[v] = {"hz": round(hz, 1) if hz else None, "file": p.name}
            print(f"  {i:2d}/{len(names)}  {v:15s} {hz:6.1f}Hz" if hz
                  else f"  {i:2d}/{len(names)}  {v:15s}  (높이를 못 쟀습니다)")
        except Exception as e:
            failed.append(f"{v}: {type(e).__name__}")
            print(f"  {i:2d}/{len(names)}  {v:15s}  실패 — {type(e).__name__}")

    if not got:
        print("하나도 못 만들었습니다.", file=sys.stderr)
        return 1

    # ── 표를 적는다 (배역-목소리 검사가 이것을 읽는다) ──
    old = {}
    if VOICES_JSON.exists():
        try:
            old = json.loads(VOICES_JSON.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    voices = dict(old.get("voices") or {})
    for v, row in got.items():
        if row["hz"]:
            keep = voices.get(v, {})
            voices[v] = {"hz": row["hz"], "note": keep.get("note", "")}
    old.update({"model": model, "measured": "audition", "voices": voices})
    VOICES_JSON.write_text(json.dumps(old, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(f"\n높이표를 적었습니다: {VOICES_JSON} ({len(voices)}개)")

    # ── 낮은 것부터 늘어놓아 보여 준다 (배역 고르기 쉽게) ──
    rows = sorted(((r["hz"], v) for v, r in got.items() if r["hz"]))
    print("\n낮은 목소리부터")
    for hz, v in rows:
        band = "남자" if hz < 155 else ("애매" if hz < 165 else "여자")
        print(f"  {hz:6.1f}Hz  {band}  {v}")

    # ── 한 파일로 이어 붙인다 (관리자 페이지에서 재생) ──
    work = out / "_w"
    work.mkdir(exist_ok=True)
    sil = work / "gap.mp3"
    run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "anullsrc=r=44100:cl=stereo", "-t", str(GAP), "-b:a", "160k", str(sil)])
    parts = []
    for hz, v in rows:                     # 낮은 것부터 = 남자 → 여자 순서
        parts += [out / got[v]["file"], sil]
    if parts:
        parts.pop()
        lst = work / "list.txt"
        lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
        dst = out / "audition_all.mp3"
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", str(lst), "-c:a", "libmp3lame", "-b:a", "192k", str(dst)])
        print(f"\n들어보기: {dst} (낮은 목소리부터 이어 붙였습니다)")
        (out / "audition_order.txt").write_text(
            "\n".join(f"{i:2d}. {v}  {hz:.0f}Hz" for i, (hz, v) in enumerate(rows, 1)),
            encoding="utf-8")

    if failed:
        print(f"\n못 만든 것 {len(failed)}개: {', '.join(failed[:6])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
