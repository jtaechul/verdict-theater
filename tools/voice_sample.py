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


def build_one(doc, sp, vdir, out, cap, tone_of, gain_of, tag=""):
    """한 사람의 대사를 이어 붙여 mp3 하나로 만든다. (파일, 줄 수, 길이) 를 돌려준다.

    tag 를 주면 파일 이름 뒤에 붙는다 — 낮추기 단계를 여러 개 만들 때 쓴다
    (`v_M50A__-3반음.mp3`). 관리자 페이지가 이 이름을 사람 말로 바꿔 보여 준다."""
    cuts = flat_cuts(doc)
    mine = [c for c in cuts if c.get("speaker") == sp]
    have = [(c, vdir / f"{c['id']}.mp3") for c in mine]
    have = [(c, p) for c, p in have if p.exists()]
    if not have:
        print(f"{sp}: 만들어 둔 소리가 없습니다 (건너뜁니다)")
        return None
    have = have[:max(1, cap)]

    name = f"{sp}__{tag}" if tag else sp
    work = out / f"_w_{name}"
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
            parts.append(p)                  # 보정 실패해도 날것이라도 들려준다
        parts.append(sil)
    parts.pop()                              # 맨 끝 쉼은 뺀다

    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts), encoding="utf-8")
    dst = out / f"{name}.mp3"
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
    print(f"{name} ({who_name(doc, sp)}): 대사 {len(have)}줄 · {dur:.0f}초 → {dst}")
    for c, _p in have[:3]:
        print(f"    {c['id']}  {(c.get('text') or '')[:34]}")
    return (name, dst, len(have), dur)


def report(doc, made):
    if not made:
        print("만든 것이 없습니다.", file=sys.stderr)
        return 1
    print(f"\n{len(made)}개 만들었습니다.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--voice", default="build/voice", help="만들어 둔 음성이 있는 곳")
    ap.add_argument("--who", default="v_M50A", help="누구 (v_M50A / narrator …). all 이면 전부")
    ap.add_argument("--out", default="build/sample")
    ap.add_argument("--max", type=int, default=MAX_CUTS)
    ap.add_argument("--pitch-sweep", default="",
                    help="목소리를 얼마나 낮출지 여러 단계로 만든다 (예: '0,-2,-3,-4,-5'). "
                         "값 0원 — 이미 만들어 둔 소리를 손보는 것뿐이다")
    a = ap.parse_args()

    doc = json.loads(Path(a.script).read_text(encoding="utf-8"))
    vdir = Path(a.voice)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    if not vdir.is_dir():
        print(f"만들어 둔 음성이 없습니다: {vdir}", file=sys.stderr)
        return 1

    # 실제 영상과 같은 보정을 쓰려고 render 가 재 둔 값을 불러온다.
    # 낮추기 단계를 만들 때는 단계마다 다시 재므로, 여기서는 재지 않는다
    # (여기서 재면 기본 낮추기 값이 로그에 한 번 더 찍혀 헷갈린다).
    render = None
    try:
        import render
        render.set_cast(doc)
        if not a.pitch_sweep:
            render.set_voice_gains(doc, str(vdir))
        tone_of = render._TONE
        gain_of = render._GAIN
    except Exception as e:                       # Pillow 가 없거나 할 때
        print(f"(영상과 같은 보정은 건너뜁니다 — {type(e).__name__})")
        tone_of, gain_of = {}, {}

    cuts = flat_cuts(doc)
    speakers = sorted({str(c.get("speaker") or "") for c in cuts if c.get("speaker")})
    want = speakers if a.who == "all" else [a.who]

    # ⭐ 목소리를 얼마나 낮출지 **여러 단계로 만들어 귀로 고르시게 한다.**
    #    (2026-08-09 손님: "장남 목소리 너무 가늘고 여자 같아")
    #    이미 만들어 둔 소리를 손보는 것뿐이라 몇 단계를 만들어도 **값 0원**이다.
    sweep = []
    if a.pitch_sweep:
        if render is None:
            print("오류: 낮추기는 render 가 있어야 합니다.", file=sys.stderr)
            return 1
        for x in a.pitch_sweep.split(","):
            x = x.strip()
            if x:
                sweep.append(float(x))

    made = []
    if sweep:
        for sp in want:
            for st in sweep:
                render.VOICE_PITCH[sp] = st
                render.set_voice_gains(doc, str(vdir))   # 낮춘 뒤 크기를 다시 잰다
                # ⚠️ 파일 이름은 **영문·숫자만** 쓴다. 보관함(릴리스)에 올릴 때
                #    한글 이름은 깨질 수 있다. 화면에 뜨는 한글 이름은 관리자
                #    페이지가 이 이름을 보고 붙인다 (down3 → '3반음 낮춤').
                tag = "same" if abs(st) < 0.25 else f"down{abs(st):.0f}"
                r = build_one(doc, sp, vdir, out, a.max, render._TONE, render._GAIN,
                              tag=tag)
                if r:
                    made.append(r)
        return report(doc, made)

    for sp in want:
        r = build_one(doc, sp, vdir, out, a.max, tone_of, gain_of)
        if r:
            made.append(r)
    return report(doc, made)


if __name__ == "__main__":
    sys.exit(main())
