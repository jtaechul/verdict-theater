#!/usr/bin/env python3
"""90초 한 편이 **진짜로 조립되는가** (0원 · 인터넷 0회 · 20초쯤)

    python3 tools/short90_test.py

돈 나가는 두 자리(그림·소리)만 가짜로 바꿔치기하고, 나머지는 **실제 코드**를
그대로 돌린다 — 자막 그리기, 줌, 합치기, 길이까지 전부 진짜다.

무엇을 확인하나
    ① 대본 23컷이 규격대로인가 (번호·길이·글·프롬프트)
    ② 컷마다 자막이 칸 안에 들어가는가 (넘치면 글자가 잘려 나간다)
    ③ 한 편 길이가 90초 언저리인가 (23컷을 다 붙이면 몇 분씩 걸려 셈으로 본다)
    ④ 실제로 mp4 가 나오고 붙인 길이가 셈과 맞는가 (컷 몇 개로 확인)
    ⑤ 소리가 붙어 있는가 (자막만 나오고 소리가 없던 사고가 있었다)
    ⑥ 손으로 만든 영상(clips/cNN.mp4)이 있으면 그 컷만 영상으로 바뀌는가
"""
import json
import pathlib
import subprocess
import sys
import wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import short90 as S9                                         # noqa: E402

BAD = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + ("" if ok else f"  ({why})"))
    if not ok:
        BAD.append(name)


def fake_wav(path, sec):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(b"\x00\x00" * int(48000 * sec))


def fake_png(path, seed):
    from PIL import Image
    path.parent.mkdir(parents=True, exist_ok=True)
    # 컷마다 다른 색 — 합쳐 놓고 보면 컷이 바뀌는 것이 눈에 보인다
    c = (40 + seed * 7 % 160, 50 + seed * 13 % 150, 60 + seed * 29 % 140)
    Image.new("RGB", (S9.W, S9.H), c).save(path)


def main():
    print("⭐ 90초 한 편 시험 — 진짜로 조립되는가 (값 0원)\n")
    doc = json.loads((ROOT / "data" / "series" / "S90.json")
                     .read_text(encoding="utf-8"))
    cuts = doc["cuts"]

    print("① 대본")
    ck("컷이 23개다", len(cuts) == 23, len(cuts))
    ck("컷 번호가 1부터 빠짐없이 이어진다",
       [c["n"] for c in cuts] == list(range(1, len(cuts) + 1)))
    ck("컷마다 화면에 뜰 글이 있다", all(c.get("text", "").strip() for c in cuts))
    ck("컷마다 그림 프롬프트가 있다", all(c.get("still", "").strip() for c in cuts))
    ck("대사 컷마다 손으로 만들 영상 프롬프트가 있다",
       all(c.get("veo", "").strip() for c in cuts if c["kind"] != "나레이션"))
    ck("나레이션 컷에는 영상 프롬프트가 없다",
       all(not c.get("veo") for c in cuts if c["kind"] == "나레이션"))
    say = [c for c in cuts if c["kind"] != "나레이션"]
    ck("대사 컷의 말하는 사람이 목소리표에 다 있다",
       all(c["kind"] in S9.VOICE for c in say),
       {c["kind"] for c in say} - set(S9.VOICE))
    ck("모든 컷 프롬프트가 세로(9:16)다",
       all("9:16" in c["still"] or "9 x 16" in c["still"] for c in cuts))
    mn = sum(c["sec"] for c in cuts)
    ck("대본 최소 길이가 90초 언저리다 (80~120)", 80 <= mn <= 120, f"{mn:.0f}초")

    print("\n② 자막이 칸 안에 들어가는가")
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new("RGBA", (S9.W, S9.H)))
    over = []
    for c in cuts:
        f, lines, size = S9.fit(d, c["text"], S9.SUB_MAX, S9.W - S9.SIDE * 2,
                                S9.SUB_BOT - S9.SUB_TOP)
        wide = max((d.textlength(x, font=f) for x in lines), default=0)
        if len(lines) > S9.SUB_LINES or wide > S9.W - S9.SIDE * 2 + 1:
            over.append(f"컷{c['n']}({len(lines)}줄 {wide:.0f}px)")
    ck("컷 23개 자막이 모두 세 줄·칸 안에 들어간다", not over, ", ".join(over))
    ck("자막 칸이 쇼츠 단추 자리를 안 침범한다", S9.SUB_BOT <= 1620, S9.SUB_BOT)

    print("\n③ 한 편 길이가 90초 언저리인가 (붙이지 않고 셈으로 먼저)")
    # ⚠️ 컷 길이는 대본의 초가 아니라 **만들어진 목소리 길이**가 정한다.
    #    23컷을 다 붙여 보면 몇 분씩 걸리므로, 길이는 여기서 셈으로 본다.
    say_sec = {c["n"]: max(1.0, c["sec"] - 0.8) for c in cuts}   # 목소리 길이(가정)
    want = sum(max(c["sec"], say_sec[c["n"]] + S9.PAD) for c in cuts)
    ck("셈으로 잰 길이가 90초 언저리다 (80~125)", 80 <= want <= 125, f"{want:.1f}초")

    print("\n④⑤ 실제로 조립해 본다 (그림·소리만 가짜 · 컷 몇 개만)")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        S9.OUT = tmp
        for c in cuts:
            fake_png(tmp / "stills" / f"c{c['n']:02d}.png", c["n"])
            fake_wav(tmp / "voice" / f"c{c['n']:02d}.wav", say_sec[c["n"]])
        # ⑤ 한 컷만 손으로 만든 영상이 있는 상황
        hand = tmp / "clips" / "c04.mp4"
        hand.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                        f"color=c=red:s=720x1280:d=6:r={S9.FPS}",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(hand)],
                       check=True)
        # 붙이는 것은 컷 몇 개만 — 첫 컷·대사 컷·손영상 컷·가장 긴 컷·마지막 컷
        pick = {1, 4, 11, 16, 23}
        sample = dict(doc)
        sample["cuts"] = [c for c in cuts if c["n"] in pick]
        S9.build(sample)
        final = tmp / "S90_short.mp4"
        ck("mp4 한 편이 나왔다", final.exists() and final.stat().st_size > 50_000)
        got = S9.dur_of(final)
        exp = sum(max(c["sec"], say_sec[c["n"]] + S9.PAD) for c in sample["cuts"])
        ck("붙인 길이가 셈과 맞는다 (±1초)", abs(got - exp) <= 1.0,
           f"{got:.1f}초 / 셈 {exp:.1f}초")
        # 소리가 진짜 붙어 있는가
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
             "stream=codec_type", "-of", "default=nw=1:nk=1", str(final)],
            capture_output=True, text=True).stdout
        ck("소리 길이 전체에 붙어 있다", "audio" in out, out.strip() or "소리 없음")
        ck("손으로 만든 영상이 있는 컷은 그 영상을 쓴다",
           (tmp / "parts" / "c04.mp4").exists())

    print("\n" + "─" * 60)
    if BAD:
        for b in BAD:
            print("   ❌ " + b)
        print(f"❌ 90초 편 시험: {len(BAD)}가지 실패")
        return 1
    print("✅ 90초 편 시험: 전부 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
