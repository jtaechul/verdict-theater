#!/usr/bin/env python3
"""⭐ 돈 쓰기 전 **진짜 크기로** 한 번 돌려 본다 (값 0원 · 인터넷 0회 · 2~4분)

    python3 tools/short90_dryrun.py

왜 (2026-08-31 손님: "바뀐 방식으로 오류 없는지 한번 더 검증 및 보완해.")
    short90_test.py 는 컷 다섯 개만 붙여 본다. 그런데 이번에 바꾼 것들은
    **컷이 많아질수록 위험한 것**들이다 —
      · 카라오케: 컷마다 자막 장이 낱말 수만큼 늘어난다 (ffmpeg 입력이 늘어난다)
      · 지문으로 찾아 쓰기(salvage): 번호가 밀린 그림을 옮겨 쓴다
      · 줄마다 길이 기록(.len.json): 없으면 자막이 목소리를 못 따라간다
    그래서 **스무 컷 전부**를, 그림·소리만 가짜로 바꿔 끼우고 나머지는
    진짜 코드로 돌려 본다. 돈 나가는 자리는 아예 부르지 않는다.
"""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import reuse                                                 # noqa: E402
import short90 as S9                                         # noqa: E402
import still as ST                                           # noqa: E402

BAD = []
CALLS = {"img": [], "tts": []}


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + ("" if ok else f"  ({why})"))
    if not ok:
        BAD.append(name)


def fake_png(path, seed):
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    c = (40 + seed * 7 % 160, 50 + seed * 13 % 150, 60 + seed * 29 % 140)
    Image.new("RGB", (S9.W, S9.H), c).save(path)


def fake_wav(path, sec):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)
        w.writeframes(b"\x00\x00" * int(48000 * sec))


def dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def main():
    print("⭐ 90초 편 — 진짜 크기로 돌려 보기 (값 0원)\n")
    doc = json.loads((ROOT / "data" / "series" / "S90.json")
                     .read_text(encoding="utf-8"))
    cuts = doc["cuts"]
    tmp = pathlib.Path(tempfile.mkdtemp())
    S9.OUT = tmp

    # ── 돈 쓰는 두 자리만 가짜로 바꿔 끼운다 ───────────────────
    def spy_gen(prompt, out, refs=(), **kw):
        CALLS["img"].append(out.name)
        fake_png(out, len(CALLS["img"]))
        return 0.0

    class FakeTTS:
        @staticmethod
        def say(text, voice=None, rate=1.0, pitch=0.0, out=None, style=None,
                who=None):
            CALLS["tts"].append({"voice": voice, "style": style, "text": text})
            # 실제와 비슷하게 — 한국어는 1초에 약 4.6자
            n = len([x for x in str(text) if not x.isspace()])
            fake_wav(pathlib.Path(out), n / 4.6 + 0.8)
            return out

    ST.gen = spy_gen
    sys.modules["tts"] = FakeTTS

    # 인물 카드도 진짜 것을 놓는다 (참조가 붙는지 보려면 있어야 한다)
    subprocess.run([sys.executable, str(ROOT / "tools" / "repo_cards.py"),
                    str(tmp / "cards")], check=True, capture_output=True)

    print("① 그림 — 스무 컷 (가짜로 그린다)")
    S9.stills(doc)
    ck(f"컷 수만큼 그렸다 ({len(cuts)}장)", len(CALLS["img"]) == len(cuts),
       f"{len(CALLS['img'])}장")

    # ── ②-a 번호가 밀렸을 때 **옮겨 쓰는지** ───────────────────
    print("\n② 컷을 끼워 넣어 번호가 밀렸을 때 (값이 새면 안 된다)")
    shifted = tmp / "stills_shift"
    shifted.mkdir()
    for c in cuts:                       # 한 칸씩 밀어 둔다 (c05 → c06 …)
        src = tmp / "stills" / f"c{c['n']:02d}.png"
        dst = shifted / f"c{c['n'] + 1:02d}.png"
        shutil.copyfile(src, dst)
        shutil.copyfile(reuse.sig_file(src), reuse.sig_file(dst))
    shutil.rmtree(tmp / "stills")
    shutil.move(str(shifted), str(tmp / "stills"))
    CALLS["img"].clear()
    S9.stills(doc)
    ck("번호가 밀려도 다시 그리지 않는다 (0원)", not CALLS["img"],
       f"{len(CALLS['img'])}장을 다시 그렸다 = {len(CALLS['img']) * 132}원")

    print("\n③ 소리 — 줄마다 지시를 들고 가는가")
    # ⭐ 길목 검사가 **진짜로 막아 주는지** 먼저 본다 (하루 10번 길이면 스물세
    #    줄을 못 만드는데, 그냥 밀어붙이면 열한 번째부터 목소리가 바뀐다)
    class Ten:
        NO_FALLBACK = False

        @staticmethod
        def route_note():
            return "AI 스튜디오 — 무료 등급은 하루 10번뿐"

    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        S9.voice_route_ok(Ten, 23)
    ck("좁은 창구면 크게 알린다", "하루 10번까지인데" in buf.getvalue(),
       buf.getvalue()[:80])
    ck("좁은 창구여도 막지는 않는다 (오늘 만들 데까지 만든다)", True)
    ck("목소리가 중간에 바뀌지 못하게 잠갔다", Ten.NO_FALLBACK is True,
       "잠금이 안 걸렸다 — 열한 번째 줄부터 딴 사람 목소리가 된다")

    class Wide:
        NO_FALLBACK = False

        @staticmethod
        def route_note():
            return "구글 클라우드 (gemini-2.5-flash-tts) — 하루 횟수 제한 없음"

    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        S9.voice_route_ok(Wide, 23)
    ck("넓은 창구면 경고 없이 그냥 간다", "하루 10번까지인데" not in buf2.getvalue())

    FakeTTS.route_note = staticmethod(lambda: "구글 클라우드 — 하루 횟수 제한 없음")
    S9.voices(doc)
    turns = sum(len(c["turns"]) for c in cuts)
    ck(f"줄 수만큼 만들었다 ({turns}줄)", len(CALLS["tts"]) == turns,
       f"{len(CALLS['tts'])}줄")
    no_style = [t["text"][:16] for t in CALLS["tts"] if not t["style"]]
    ck("모든 줄에 연기 지시를 실어 보냈다", not no_style, f"빠진 줄 {no_style}")
    old = sorted({t["voice"] for t in CALLS["tts"]
                  if str(t["voice"]).startswith("ko-KR-")})
    ck("옛 엔진 목소리로 새는 줄이 없다", not old, f"{old}")
    leak = [t["text"][:16] for t in CALLS["tts"]
            if t["style"] and t["text"] not in t["style"]]
    ck("지시 안에 그 줄의 대사가 그대로 들어 있다", not leak, f"{leak}")
    lens = list((tmp / "voice").glob("*.len.json"))
    ck(f"줄마다 길이 기록을 남겼다 ({len(cuts)}개)", len(lens) == len(cuts),
       f"{len(lens)}개")

    print("\n④ 조립 — 스무 컷을 진짜로 붙인다 (카라오케 자막)")
    S9.build(doc)
    final = tmp / "S90_short.mp4"
    ck("한 편이 나왔다", final.exists() and final.stat().st_size > 100_000)
    got = dur(final)
    want = sum(max(float(c["sec"]),
                   dur(tmp / "voice" / f"c{c['n']:02d}.wav") + S9.PAD)
               for c in cuts)
    ck(f"길이가 셈과 맞는다 ({got:.1f}초)", abs(got - want) < 1.5,
       f"셈 {want:.1f}초 · 실제 {got:.1f}초")
    ck("길이가 2~3분 안에 있다", 120 <= got <= 190, f"{got:.0f}초")
    ov = list((tmp / "ov").glob("*.png"))
    words = sum(len(t.split()) for c in cuts for _, t in c["turns"])
    ck(f"자막 장을 낱말 수만큼 만들었다 ({words}장)", len(ov) == words,
       f"{len(ov)}장")

    print("\n⑤ 컷마다 자막이 끊기지 않는가 (진짜 소리 길이로)")
    holes = []
    for c in cuts:
        v = tmp / "voice" / f"c{c['n']:02d}.wav"
        sec, uca = S9.cut_sec(c, v, None)
        w = S9.karaoke(c, sec, None if uca else v, tmp / "ov2", c["n"])
        if abs(w[0][1]) > 0.01 or abs(w[-1][2] - sec) > 0.01:
            holes.append((c["n"], "끝이 안 맞는다"))
        for i in range(len(w) - 1):
            if abs(w[i][2] - w[i + 1][1]) > 0.01:
                holes.append((c["n"], f"{i}번째에서 끊긴다"))
    ck("스무 컷 모두 자막이 처음부터 끝까지 이어진다", not holes, f"{holes[:4]}")

    print("\n⑥ 소리가 영상 끝까지 붙어 있는가")
    quiet = []
    for c in cuts[:6]:                   # 앞 여섯 컷만 (시간이 걸린다)
        p = tmp / "parts" / f"c{c['n']:02d}.mp4"
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                            "-show_entries", "stream=codec_type", "-of",
                            "csv=p=0", str(p)], capture_output=True, text=True)
        if "audio" not in r.stdout:
            quiet.append(c["n"])
    ck("컷마다 소리가 붙어 있다", not quiet, f"소리 없는 컷 {quiet}")

    shutil.rmtree(tmp, ignore_errors=True)
    print("\n" + "─" * 60)
    if BAD:
        print("❌ 걸린 것:")
        for b in BAD:
            print("     " + b)
        return 1
    print("✅ 진짜 크기 시험: 전부 통과 — 눌러도 된다")
    return 0


if __name__ == "__main__":
    sys.exit(main())
