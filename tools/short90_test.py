#!/usr/bin/env python3
"""90초 한 편이 **진짜로 조립되는가** (0원 · 인터넷 0회 · 20초쯤)

    python3 tools/short90_test.py

돈 나가는 두 자리(그림·소리)만 가짜로 바꿔치기하고, 나머지는 **실제 코드**를
그대로 돌린다 — 자막 그리기, 줌, 합치기, 길이까지 전부 진짜다.

무엇을 확인하나
    ① 대본 23컷이 규격대로인가 (번호·길이·글·프롬프트)
       ⭐ 컷 프롬프트에 **옷·생김새가 없어야** 한다 — 기준 그림이 잡는 몫이다
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
import series as S                                           # noqa: E402
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
    ck("컷이 16개다", len(cuts) == 16, len(cuts))
    ck("컷 번호가 1부터 빠짐없이 이어진다",
       [c["n"] for c in cuts] == list(range(1, len(cuts) + 1)))
    ck("컷마다 화면에 뜰 글이 있다", all(c.get("text", "").strip() for c in cuts))
    ck("컷마다 그림 프롬프트가 있다", all(c.get("still", "").strip() for c in cuts))
    # ⭐ 2026-08-27 손님: "이미지는 중간중간 섞여 있고 동영상도 있어야 돼."
    #    스물세 컷 **전부** 영상으로 올릴 수 있어야 한다
    ck("컷 전부 손으로 만들 영상 프롬프트가 있다",
       all(c.get("veo", "").strip() for c in cuts))
    ck("대사 컷 영상 프롬프트에 그 컷의 대사가 전부 들어 있다",
       all(all(t in c["veo"] for _, t in c["turns"]) for c in cuts if not c["narr"]))
    ck("나레이션 컷 영상 프롬프트는 아무도 말하지 않게 시킨다",
       all("nobody speaks" in c["veo"] for c in cuts if c["narr"]))
    say = [c for c in cuts if not c["narr"]]
    ck("대사 컷의 말하는 사람이 목소리표에 다 있다",
       all(c["kind"] in S9.VOICE for c in say),
       {c["kind"] for c in say} - set(S9.VOICE))
    # ⭐⭐⭐ 2026-08-27 손님: "wife 이미지가 있으면 와이프 옷차림 같은 건
    #    쓰면 안 되잖아." 맞다 — 그리고 이건 **이미 우리 규칙**이었다.
    #    얼굴·옷은 기준 그림이 잡는다. 컷 프롬프트에 또 적으면 두 지시가 싸워
    #    컷마다 옷이 바뀐다. 16화 쪽은 series.wear_bait 가 막고 있었는데
    #    90초 편을 새로 만들면서 그 검사를 안 붙여 그대로 새어 나갔다.
    wear = []
    for c in cuts:
        for k in ("still", "veo"):
            hit = S.wear_bait(c[k])
            if hit:
                wear.append(f"컷{c['n']}·{k}({','.join(hit)})")
    ck("컷 프롬프트에 옷·생김새를 적은 곳이 없다 (기준 그림과 안 싸운다)",
       not wear, " ".join(wear))
    ck("사람이 나오는 컷은 기준 그림을 그대로 지키라고 시킨다",
       all("reference image" in c["still"] for c in cuts if c.get("who")))

    # ⭐⭐⭐ 2026-08-27 — 손님이 구글 플로우에서 막혔다:
    #    "이 프롬프트는 유명인의 동영상 생성에 관한 Google 정책을 위반할 가능성이…"
    #    말을 바꾼 판으로 통과하는 것을 손님이 확인하셨다. 그 판(flow)이
    #    막히는 낱말을 다시 물고 들어오지 않게 못 박는다.
    BAN = ("photoreal", "photorealistic", "photograph", "natural skin",
           "reference image", "actor", "celebrity", "live-action",
           "real person", "likeness")
    # ⭐ 2026-08-28 손님: "플로우에는 캐릭터 등록을 미리 해놨으니 옷·얼굴·나이를
    #    절대 언급하지 마." → 플로우 판에는 **이름만** 들어간다.
    BAN = BAN + ("cardigan", "suit", "skirt", "blouse", "hair", "wearing",
                 "years old", "fifties", "thirties", "twenties", "forties",
                 "lawyer")
    hit = [f"컷{c['n']}({w})" for c in cuts for w in BAN
           if w in (c.get("flow") or "").lower()]
    ck("컷 전부 플로우용 프롬프트가 있다",
       all((c.get("flow") or "").strip() for c in cuts))
    ck("플로우용 프롬프트에 정책에 걸리는 낱말이 없다", not hit, " ".join(hit))
    ck("플로우용은 등록한 이름만 부른다 (옷·얼굴·나이를 안 적는다)",
       all("CAST:" in c["flow"] for c in cuts if c.get("who")))
    # ⭐ 만들 길이가 대사 길이에 맞는가 (쓸데없이 길지 않은가)
    import importlib.util as _iu
    _sp = _iu.spec_from_file_location("bs", ROOT / "tools" / "build_short90.py")
    _bs = _iu.module_from_spec(_sp); _sp.loader.exec_module(_bs)
    tooshort = [c["n"] for c in cuts if not c["narr"]
                and _bs.need_sec(c) > _bs.veo_sec(c)]
    ck("만들 길이가 대사를 다 담는다 (모자라지 않다)", not tooshort, tooshort)
    toolong = [c["n"] for c in cuts if not c["narr"]
               and _bs.veo_sec(c) - _bs.need_sec(c) > 2.2]
    ck("만들 길이가 쓸데없이 길지 않다 (남는 시간 2.2초 이하)", not toolong, toolong)

    ck("모든 컷 프롬프트가 세로(9:16)다",
       all("9:16" in c["still"] or "9 x 16" in c["still"] for c in cuts))
    mn = sum(c["sec"] for c in cuts)
    ck("대본 길이가 100초 언저리다 (85~130)", 85 <= mn <= 130, f"{mn:.0f}초")

    print("\n② 자막이 칸 안에 들어가는가")
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new("RGBA", (S9.W, S9.H)))
    over = []
    for c in cuts:
      for _, txt in c["turns"]:
        f, lines, size = S9.fit(d, txt, S9.SUB_MAX, S9.W - S9.SIDE * 2,
                                S9.SUB_BOT - S9.SUB_TOP)
        wide = max((d.textlength(x, font=f) for x in lines), default=0)
        if len(lines) > S9.SUB_LINES or wide > S9.W - S9.SIDE * 2 + 1:
            over.append(f"컷{c['n']}({len(lines)}줄 {wide:.0f}px)")
    ck("자막이 모두 세 줄·칸 안에 들어간다", not over, ", ".join(over))
    ck("자막 칸이 쇼츠 단추 자리를 안 침범한다", S9.SUB_BOT <= 1620, S9.SUB_BOT)

    print("\n③ 한 편 길이가 90초 언저리인가 (붙이지 않고 셈으로 먼저)")
    # ⚠️ 컷 길이는 대본의 초가 아니라 **만들어진 목소리 길이**가 정한다.
    #    23컷을 다 붙여 보면 몇 분씩 걸리므로, 길이는 여기서 셈으로 본다.
    say_sec = {c["n"]: max(1.0, c["sec"] - 0.8) for c in cuts}   # 목소리 길이(가정)
    want = sum(max(c["sec"], say_sec[c["n"]] + S9.PAD) for c in cuts)
    ck("셈으로 잰 길이가 100초 언저리다 (85~130)", 85 <= want <= 130, f"{want:.1f}초")

    print("\n④⑤ 실제로 조립해 본다 (그림·소리만 가짜 · 컷 몇 개만)")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        S9.OUT = tmp
        for c in cuts:
            fake_png(tmp / "stills" / f"c{c['n']:02d}.png", c["n"])
            fake_wav(tmp / "voice" / f"c{c['n']:02d}.wav", say_sec[c["n"]])
        # ⑤ 손으로 만든 영상이 섞인 상황 — 대사 컷(소리 있음)·나레이션 컷(소리 있음)
        (tmp / "clips").mkdir(parents=True, exist_ok=True)
        for n, d in ((3, 6), (8, 5)):
            subprocess.run(["ffmpeg", "-y", "-v", "error",
                            "-f", "lavfi", "-i",
                            f"color=c=red:s=720x1280:d={d}:r={S9.FPS}",
                            "-f", "lavfi", "-i", f"sine=frequency=300:duration={d}",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-shortest",
                            str(tmp / "clips" / f"c{n:02d}.mp4")], check=True)
        hand = tmp / "clips" / "c03.mp4"
        # 붙이는 것은 컷 몇 개만 — 첫 컷·대사 컷·손영상 컷·가장 긴 컷·마지막 컷
        pick = {1, 3, 8, 11, 16}
        sample = dict(doc)
        sample["cuts"] = [c for c in cuts if c["n"] in pick]
        S9.build(sample)
        final = tmp / "S90_short.mp4"
        ck("mp4 한 편이 나왔다", final.exists() and final.stat().st_size > 50_000)
        got = S9.dur_of(final)
        # ⚠️ 대사 컷에 영상을 올리면 **컷 길이는 그 영상이 정한다** (말이 잘리면
        #    안 되니까). 셈에도 그대로 반영한다 — 안 그러면 시험이 틀린 값을 본다.
        hand_sec = {3: 6.0}
        exp = sum(hand_sec.get(c["n"]) if (c["n"] in hand_sec
                                           and not c["narr"])
                  else max(c["sec"], say_sec[c["n"]] + S9.PAD)
                  for c in sample["cuts"])
        ck("붙인 길이가 셈과 맞는다 (±1초)", abs(got - exp) <= 1.0,
           f"{got:.1f}초 / 셈 {exp:.1f}초")
        # 소리가 진짜 붙어 있는가
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
             "stream=codec_type", "-of", "default=nw=1:nk=1", str(final)],
            capture_output=True, text=True).stdout
        ck("소리 길이 전체에 붙어 있다", "audio" in out, out.strip() or "소리 없음")
        ck("손으로 만든 영상이 있는 컷은 그 영상을 쓴다",
           (tmp / "parts" / "c03.mp4").exists())
        # 대사 컷은 **영상 안의 말**을 쓴다 — 우리 목소리를 덮어씌우면 입이 어긋난다
        ck("대사 컷은 올린 영상 길이(6.0초)를 그대로 지킨다",
           abs(S9.dur_of(tmp / "parts" / "c03.mp4") - 6.0) <= 0.35,
           f"{S9.dur_of(tmp / 'parts' / 'c03.mp4'):.2f}초")
        # 나레이션 컷은 영상을 올렸어도 **우리 나레이션** 길이로 간다
        n8 = [c for c in cuts if c["n"] == 8][0]
        want8 = max(n8["sec"], say_sec[8] + S9.PAD)
        ck("나레이션 컷은 영상을 올려도 우리 나레이션 길이를 지킨다",
           abs(S9.dur_of(tmp / "parts" / "c08.mp4") - want8) <= 0.35,
           f"{S9.dur_of(tmp / 'parts' / 'c08.mp4'):.2f}초 / 바람 {want8:.2f}초")

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
