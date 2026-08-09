#!/usr/bin/env python3
"""등장인물 목소리를 **귀로 들어볼 수 있는 mp3 한 개**로 묶는다. 값 0원.

    python3 tools/voice_sample.py data/scripts/EP001.json --voice build/voice \\
        --who v_M50A --out build/sample

왜 (2026-08-09 손님: "장남 목소리 한번 다시 들려줄래?
                     여기다가 mp3파일이나 wav 파일로 하나만 올려줘봐.")
    영상 전체를 다시 보며 장남 대사만 찾아 듣는 것은 번거롭다.
    이미 만들어 둔 음성 조각에서 그 사람 대사만 뽑아 **한 파일로 이어 붙인다.**

⭐ 제미나이를 한 번도 부르지 않는다 — 이미 만들어 둔 소리를 꺼내 붙일 뿐이다.

⭐ **실제 영상과 같은 소리로 들려준다.**
    영상은 컷마다 음량과 저음·고음 균형을 맞춘 뒤 재생한다. 그것을 빼먹고 날것을
    들려주면 영상에서 들릴 소리와 달라져, 손님이 엉뚱한 것을 듣고 판단하시게 된다
    (전에 실제로 그런 일이 있었다). 그래서 render 와 같은 보정을 걸어 붙인다.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

GAP = 0.45          # 대사 사이 쉼(초). 너무 붙으면 한 사람인지 분간이 안 된다
MAX_CUTS = 14       # 이보다 많으면 앞에서부터 이만큼만 (파일이 길어지지 않게)


def run(cmd):
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


def flat_cuts(doc):
    return [c for a in doc.get("acts", []) for c in (a.get("cuts") or [])]


def who_name(doc, speaker):
    """'v_M50A' → '김성일 · 50세 · 장남' (없으면 기호 그대로)."""
    code = speaker[2:] if speaker.startswith("v_") else speaker
    for ch in doc.get("characters", []) or []:
        if str(ch.get("code")) == code or str(ch.get("voice")) == speaker:
            return ch.get("nametag") or ch.get("name") or speaker
    return "해설" if speaker == "narrator" else speaker


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--voice", default="build/voice", help="만들어 둔 음성이 있는 곳")
    ap.add_argument("--who", default="v_M50A", help="누구 (v_M50A / narrator …). all 이면 전부")
    ap.add_argument("--out", default="build/sample")
    ap.add_argument("--max", type=int, default=MAX_CUTS)
    a = ap.parse_args()

    doc = json.loads(Path(a.script).read_text(encoding="utf-8"))
    vdir = Path(a.voice)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if not vdir.is_dir():
        print(f"만들어 둔 음성이 없습니다: {vdir}", file=sys.stderr)
        return 1

    # 실제 영상과 같은 보정을 쓰려고 render 가 재 둔 값을 불러온다.
    try:
        import render
        render.set_cast(doc)
        render.set_voice_gains(doc, str(vdir))
        tone_of = render._TONE
        gain_of = render._GAIN
    except Exception as e:                       # Pillow 가 없거나 할 때
        print(f"(영상과 같은 보정은 건너뜁니다 — {type(e).__name__})")
        tone_of, gain_of = {}, {}

    cuts = flat_cuts(doc)
    speakers = sorted({str(c.get("speaker") or "") for c in cuts if c.get("speaker")})
    want = speakers if a.who == "all" else [a.who]

    made = []
    for sp in want:
        mine = [c for c in cuts if c.get("speaker") == sp]
        have = [(c, vdir / f"{c['id']}.mp3") for c in mine]
        have = [(c, p) for c, p in have if p.exists()]
        if not have:
            print(f"{sp}: 만들어 둔 소리가 없습니다 (건너뜁니다)")
            continue
        have = have[:max(1, a.max)]

        work = out / f"_w_{sp}"
        work.mkdir(parents=True, exist_ok=True)
        sil = work / "gap.mp3"
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", "anullsrc=r=44100:cl=stereo", "-t", str(GAP),
             "-b:a", "160k", str(sil)])

        parts = []
        for c, p in have:
            cid = c["id"]
            fixed = work / f"{cid}.mp3"
            chain = ",".join(x for x in (tone_of.get(cid, ""),
                                         f"volume={gain_of.get(cid, 0.0):+.1f}dB") if x)
            try:
                run(["ffmpeg", "-v", "error", "-y", "-i", str(p),
                     "-af", chain or "anull", "-b:a", "160k", str(fixed)])
                parts.append(fixed)
            except Exception:
                parts.append(p)              # 보정 실패해도 날것이라도 들려준다
            parts.append(sil)
        parts.pop()                          # 맨 끝 쉼은 뺀다

        lst = work / "list.txt"
        lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts),
                       encoding="utf-8")
        dst = out / f"{sp}.mp3"
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", str(lst), "-c:a", "libmp3lame", "-b:a", "192k", str(dst)])

        dur = 0.0
        try:
            dur = float(subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", str(dst)],
                capture_output=True, text=True, check=True).stdout.strip())
        except Exception:
            pass
        made.append((sp, dst, len(have), dur))
        print(f"{sp} ({who_name(doc, sp)}): 대사 {len(have)}줄 · {dur:.0f}초 → {dst}")
        for c, _p in have[:4]:
            print(f"    {c['id']}  {(c.get('text') or '')[:34]}")

    if not made:
        print("만든 것이 없습니다.", file=sys.stderr)
        return 1
    print(f"\n{len(made)}개 만들었습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
