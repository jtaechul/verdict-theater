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
    ck("컷이 19개다", len(cuts) == 19, len(cuts))
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
    ck("대본 길이가 130초 언저리다 (110~150)", 110 <= mn <= 150, f"{mn:.0f}초")

    # ⭐⭐⭐ 2026-08-28 손님: "너무 그 사이사이에 나레이션을 너무 많이 날려먹었는데
    #    이러면 이해가 되는 게 맞아?" — 맞다. 겹친다고 뺐다가 **언제·어디인지
    #    알려 주는 줄**까지 뺐다. 35~43초 동안 왜 법원인지 모른 채로 있었다.
    print("\n①-2 이야기가 끊기지 않는가")
    PAD = S9.PAD
    t, marks, tl = 0.0, [], []
    for c in cuts:
        ln = (c["sec"] + PAD) if c["narr"] else c["sec"]
        tl.append((t, c))
        if c["narr"]:
            marks.append(t)
        t += ln
    gap = max((b - a) for a, b in zip(marks, marks[1:] + [t])) if marks else t
    # 30초로 잡은 까닭 — 지금 가장 긴 구간은 27초(장례식장 → 사무실 → 금액)인데
    # 장면이 이어지고 대사가 사실을 나르므로 이해가 끊기지 않는다. 그보다 길어지면
    # 관객이 "지금 언제·어디" 를 놓친다.
    ck("나레이션 없이 흐르는 구간이 30초를 안 넘는다", gap <= 30, f"{gap:.0f}초")
    hook = next((a for a, c in tl if "32억" in c["text"] or "삼십이억" in c["text"]),
                999)
    ck("32억이 20초 안에 나온다 (제목이 32억이다)", hook <= 20, f"{hook:.0f}초")
    suit = next((a for a, c in tl if "소송" in c["text"]), 999)
    ck("소송 이야기가 법정 장면보다 먼저 나온다", suit < 60, f"{suit:.0f}초")

    # ⭐⭐ 2026-08-30 손님: "무조건 등장인물은 첨부 등장인물 이미지를 참고하도록 해."
    #    다섯 얼굴이 **매번** 쓰여야 한다. 하나라도 빠지면 그 사람만 시스템이
    #    제 나름대로 그려서, 컷마다 다른 얼굴이 나온다 — 예전에 실제로 난 사고다.
    print("\n①-3 손님이 고른 다섯 얼굴이 늘 쓰이는가")
    sys.path.insert(0, str(ROOT / "tools"))
    import repo_cards as RC                                  # noqa: E402
    from PIL import Image

    for en, ko in RC.NAME.items():
        f = RC.SRC / f"{en}.png"
        big = f.exists() and f.stat().st_size > RC.MIN_BYTES
        ck(f"{ko} 그림이 저장소에 있다 (assets/cards/s90/{en}.png)", big,
           "없거나 너무 작다")
        if big:
            w, h = Image.open(f).size
            ck(f"{ko} 그림이 세로다", h > w, f"{w}x{h}")

    need = sorted({S9.ST_NAME.get(w, w) for c in cuts for w in (c.get("who") or [])})
    have = set(RC.NAME.values())
    ck("컷에 나오는 사람이 모두 카드로 있다", set(need) <= have,
       f"없는 사람: {sorted(set(need) - have)}")

    # ⭐ 그림 만들 때 그 얼굴을 **참조로 진짜 넣는지** — 이름이 한 글자만 어긋나도
    #    조용히 빠지고, 그 컷만 다른 얼굴이 나온다. 그러니 눈으로 믿지 말고
    #    실제로 한 번 돌려 본다 (그림 만드는 자리만 가짜 · 값 0원 · 인터넷 0회).
    import still as ST                                       # noqa: E402
    import tempfile                                          # noqa: E402
    import subprocess as SP                                  # noqa: E402
    tmp = pathlib.Path(tempfile.mkdtemp())
    SP.run([sys.executable, str(ROOT / "tools" / "repo_cards.py"), str(tmp / "cards")],
           check=True, capture_output=True)
    seen, real_gen, real_out = {}, ST.gen, S9.OUT

    def spy(prompt, out, refs=(), **kw):
        seen[out.name] = [pathlib.Path(r).name for r in refs]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"\x00" * 20_000)
        return 0.0

    try:
        ST.gen, S9.OUT = spy, tmp
        S9.stills(doc)
    finally:
        ST.gen, S9.OUT = real_gen, real_out

    wrong = [c["n"] for c in cuts
             if seen.get(f"c{c['n']:02d}.png", []) !=
             [S9.ST_NAME.get(w, w) + ".png" for w in (c.get("who") or [])]]
    with_ref = [c["n"] for c in cuts if c.get("who")]
    ck(f"사람이 나오는 {len(with_ref)}컷에 그 사람 얼굴이 그대로 붙는다",
       not wrong, f"어긋난 컷 {wrong}")
    ck("그림 19장을 다 만든다 (빠지는 컷이 없다)", len(seen) == len(cuts),
       f"{len(seen)}/{len(cuts)}")

    # ⭐ 워크플로는 저장소 그림을 놓은 **뒤에** still.py cards S001 을 부른다.
    #    S001 에 우리가 안 넣어 둔 사람이 하나라도 있으면, 그 사람만 시스템이
    #    새로 그려서 카드값 132원이 조용히 나간다 (게다가 다른 얼굴이 된다).
    s001 = json.loads((ROOT / "data" / "series" / "S001.json")
                      .read_text(encoding="utf-8"))
    s001_who = {c.get("name") for c in (s001.get("characters") or [])}
    ck("S001 인물이 모두 넣어 둔 그림으로 덮인다 (카드값 0원)",
       s001_who <= have, f"그림이 없어 새로 그릴 사람: {sorted(s001_who - have)}")

    wf = (ROOT / ".github" / "workflows" / "short90.yml").read_text(encoding="utf-8")
    i_repo, i_fetch = wf.find("repo_cards.py"), wf.find("fetch_cards.py")
    i_draw = wf.find("still.py cards")
    ck("워크플로가 저장소 그림을 먼저 놓는다", 0 < i_repo < i_fetch < i_draw,
       f"repo={i_repo} fetch={i_fetch} draw={i_draw}")

    print("\n①-4 한 번 눌렀을 때 나갈 돈")
    import cost                                              # noqa: E402
    one = cost.image_krw(ST.MODEL, ST.SIZE)
    krw = one * len(cuts)
    print(f"   그림 {len(cuts)}장 x {one:,.0f}원 = {krw:,.0f}원 "
          f"(+ 소리 약 100원) · 한 번 한도 {cost.RUN_KRW:,.0f}원")
    ck("한 번 실행 한도 안에 들어간다", krw + 100 <= cost.RUN_KRW,
       f"{krw + 100:,.0f}원 > {cost.RUN_KRW:,.0f}원")
    ck("카드값은 안 나간다 (손님 그림을 쓴다)", len(RC.NAME) == 5)

    print("\n①-5 그림 프롬프트에 영상 말이 안 섞였는가")
    vid = ["continuous take", "first frame", "seconds", "camera pans", "camera moves"]
    for c in cuts:
        low = c["still"].lower()
        bad = [w for w in vid if w in low]
        if bad:
            ck(f"컷{c['n']} 그림 프롬프트가 깨끗하다", False, f"영상 말: {bad}")
            break
    else:
        ck(f"{len(cuts)}컷 모두 그림 프롬프트에 영상 말이 없다", True)
    ck("그림 화풍과 영상 화풍의 꼬리가 같다",
       S.STYLE_FIX.endswith(S.STYLE_TAIL) and S.STYLE_STILL.endswith(S.STYLE_TAIL))

    # ⭐⭐ 2026-08-31 손님: "대사 목소리와 대본 자막이 시간차가 발생."
    #    자막 바뀌는 때를 글자 수로 짐작하고 있었다. 짐작이 맞는지 눈으로는
    #    못 본다 — **일부러 어긋나게** 만들어 놓고 셈이 소리를 따라가는지 본다.
    print("\n①-6 자막이 목소리를 따라가는가")
    two = next((c for c in cuts if len(c.get("turns") or []) > 1), None)
    ck("두 사람이 주고받는 컷이 있다", bool(two))
    if two:
        import tempfile as _tf
        td = pathlib.Path(_tf.mkdtemp())
        wav = td / "c.wav"
        fake_wav(wav, 7.0)
        # 첫 줄은 **짧게 말하고** 글자는 길게 — 글자 수로 짐작하면 크게 틀린다
        S9.lens_of(wav).write_text("[2.0, 5.0]", encoding="utf-8")
        sec = 8.0
        at = S9.sub_windows(two, sec, wav)
        ck("첫 줄이 목소리가 끝나는 그때 바뀐다",
           abs(at[0][1] - 2.0) < 0.01, f"{at[0][1]:.2f}초에 바뀐다 (2.00초여야 한다)")
        ck("둘째 줄이 바로 이어 받는다", abs(at[1][0] - 2.0) < 0.01, f"{at[1][0]:.2f}초")
        ck("마지막 줄은 컷 끝까지 남는다", abs(at[1][1] - sec) < 0.01, f"{at[1][1]:.2f}초")
        # 글자 수로 짐작하던 옛 셈과 **실제로 달라야** 뜻이 있다
        guess = S9.sub_windows(two, sec, None)
        ck("옛 짐작과 다르다 (고친 값이다)", abs(guess[0][1] - at[0][1]) > 0.2,
           f"짐작 {guess[0][1]:.2f}초 · 진짜 {at[0][1]:.2f}초")
        # 올린 영상의 소리를 쓰는 컷은 우리 길이를 쓰면 안 된다
        ck("올린 영상 컷은 옛 방식 그대로다",
           S9.sub_windows(two, sec, None) == guess)

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
    # ⭐⭐⭐ 2026-08-28 손님: "왜 프롬프트부터 위아래 그림에 생성이 안 되도록 해."
    #    자막 자리는 **우리가 나중에 덮는다.** 그림은 화면을 꽉 채워 받는다 —
    #    비워 두라고 시키면 화면의 20%를 버리고 그리는 셈이다.
    waste = [f"컷{c['n']}" for c in cuts
             for k in ("still", "veo", "flow")
             if "caption will sit" in (c.get(k) or "")
             or "lower fifth" in (c.get(k) or "")]
    ck("프롬프트가 화면 아래를 비우라고 시키지 않는다", not waste, " ".join(waste))
    ck("프롬프트가 화면을 꽉 채우라고 시킨다",
       all("filling the whole frame" in c["flow"] for c in cuts))

    print("\n③ 한 편 길이가 90초 언저리인가 (붙이지 않고 셈으로 먼저)")
    # ⚠️ 컷 길이는 대본의 초가 아니라 **만들어진 목소리 길이**가 정한다.
    #    23컷을 다 붙여 보면 몇 분씩 걸리므로, 길이는 여기서 셈으로 본다.
    say_sec = {c["n"]: max(1.0, c["sec"] - 0.8) for c in cuts}   # 목소리 길이(가정)
    want = sum(max(c["sec"], say_sec[c["n"]] + S9.PAD) for c in cuts)
    ck("셈으로 잰 길이가 130초 언저리다 (110~150)", 110 <= want <= 150, f"{want:.1f}초")

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
        for n, d in ((4, 6), (10, 5)):
            subprocess.run(["ffmpeg", "-y", "-v", "error",
                            "-f", "lavfi", "-i",
                            f"color=c=red:s=720x1280:d={d}:r={S9.FPS}",
                            "-f", "lavfi", "-i", f"sine=frequency=300:duration={d}",
                            "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-shortest",
                            str(tmp / "clips" / f"c{n:02d}.mp4")], check=True)
        hand = tmp / "clips" / "c04.mp4"
        # 붙이는 것은 컷 몇 개만 — 첫 컷·대사 컷·손영상 컷·가장 긴 컷·마지막 컷
        pick = {1, 4, 10, 13, 19}
        sample = dict(doc)
        sample["cuts"] = [c for c in cuts if c["n"] in pick]
        S9.build(sample)
        final = tmp / "S90_short.mp4"
        ck("mp4 한 편이 나왔다", final.exists() and final.stat().st_size > 50_000)
        got = S9.dur_of(final)
        # ⚠️ 대사 컷에 영상을 올리면 **컷 길이는 그 영상이 정한다** (말이 잘리면
        #    안 되니까). 셈에도 그대로 반영한다 — 안 그러면 시험이 틀린 값을 본다.
        hand_sec = {4: 6.0}
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
           (tmp / "parts" / "c04.mp4").exists())
        # 대사 컷은 **영상 안의 말**을 쓴다 — 우리 목소리를 덮어씌우면 입이 어긋난다
        ck("대사 컷은 올린 영상 길이(6.0초)를 그대로 지킨다",
           abs(S9.dur_of(tmp / "parts" / "c04.mp4") - 6.0) <= 0.35,
           f"{S9.dur_of(tmp / 'parts' / 'c04.mp4'):.2f}초")
        # 나레이션 컷은 영상을 올렸어도 **우리 나레이션** 길이로 간다
        n10 = [c for c in cuts if c["n"] == 10][0]
        want10 = max(n10["sec"], say_sec[10] + S9.PAD)
        ck("나레이션 컷은 영상을 올려도 우리 나레이션 길이를 지킨다",
           abs(S9.dur_of(tmp / "parts" / "c10.mp4") - want10) <= 0.35,
           f"{S9.dur_of(tmp / 'parts' / 'c10.mp4'):.2f}초 / 바람 {want10:.2f}초")

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
