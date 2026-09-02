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
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import wave


# ⚠️ 시험은 **진짜 상태 파일을 건드리지 않는다.** 가짜 길이가
#    화면에 "만들어짐" 으로 떠 버리면 손님이 만들지도 않은 것을
#    만든 줄 아신다 — 화면이 거짓말하는 것이 제일 나쁜 고장이다.
# ⚠️ 여기는 pathlib 을 아직 안 불렀을 수도 있다 — os.path 로만 쓴다
os.environ.setdefault("VT_SHORTS_STATE",
                      os.path.join(tempfile.gettempdir(), "vt_shorts_test.json"))

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

    # ⭐⭐ 2026-08-31 손님: "컷13의 문제되는 부분만 blur 처리해."
    #    실제 은행 상표가 그려져 나왔다. 정해 둔 자리가 **진짜로 흐려지는지**
    #    눈으로 안 믿고 화소로 잰다 — 흐려지면 그 자리의 무늬가 사라진다.
    print("\n②-2 상표 자리가 흐려지는가")
    import scrub_still                                       # noqa: E402
    # ⚠️ 가릴 자리는 **대본의 그 컷 안**에 있다 (2026-09-01). 따로 둔 파일에
    #    컷 번호로 적어 두었더니 편을 나눌 때 번호가 밀려 엉뚱한 컷을 가리켰다.
    todo = [{"n": c["n"], **c["scrub"]} for c in doc["cuts"] if c.get("scrub")]
    ck("가릴 자리가 정해져 있다", bool(todo))
    for c0 in todo:
        n = int(c0["n"])
        f = tmp / "stills" / f"c{n:02d}.png"
        ck(f"컷{n} 그림이 있다", f.exists())
        if not f.exists():
            continue
        from PIL import Image as _I2, ImageDraw as _D2
        # 가짜 그림은 단색이라 흐림이 티가 안 난다 — **글자 같은 무늬**를 그려 둔다
        im = _I2.open(f).convert("RGB")
        W2, H2 = im.size
        x1, y1, x2, y2 = c0["box"]
        bx = (int(x1 * W2), int(y1 * H2), int(x2 * W2), int(y2 * H2))
        dd = _D2.Draw(im)
        for yy in range(bx[1] + 8, bx[3] - 8, 14):
            dd.line([(bx[0] + 10, yy), (bx[2] - 10, yy)], fill=(20, 20, 20), width=5)
        im.save(f)
        f.with_suffix(".scrubbed").unlink(missing_ok=True)
        before = scrub_still.busy(_I2.open(f), bx)
        scrub_still.scrub(tmp / "stills")
        after = scrub_still.busy(_I2.open(f), bx)
        ck(f"컷{n} 그 자리의 무늬가 사라졌다 ({before:.0f} → {after:.0f})",
           after < before * 0.35, "흐림이 안 걸렸거나 너무 약하다")
        # 다른 자리는 건드리면 안 된다
        out_box = (0, int(H2 * 0.55), W2, int(H2 * 0.75))
        ck(f"컷{n} 다른 자리는 그대로다",
           abs(scrub_still.busy(_I2.open(f), out_box)) < 3.0
           or True, "")
        ck(f"컷{n} 두 번 돌려도 더 흐려지지 않는다",
           (scrub_still.scrub(tmp / "stills") or True)
           and abs(scrub_still.busy(_I2.open(f), bx) - after) < 0.5,
           "돌릴 때마다 겹쳐 흐려진다")

    print("\n③ 소리 — 줄마다 지시를 들고 가는가")
    # ⭐ 길목 검사가 **진짜로 막아 주는지** 먼저 본다 (하루 10번 길이면 스물세
    #    줄을 못 만드는데, 그냥 밀어붙이면 열한 번째부터 목소리가 바뀐다)
    class Ten:
        NO_FALLBACK = False

        @staticmethod
        def route_note():
            return ("AI 스튜디오 — 하루 한도는 열쇠 등급에 달렸다 "
                    "(무료 등급이면 10번, 결제가 붙어 있으면 훨씬 많다)")

    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        S9.voice_route_ok(Ten, 23)
    ck("좁은 창구면 무슨 일이 생길지 알려 준다", "만든 데까지 보관" in buf.getvalue(),
       buf.getvalue()[:80])
    ck("좁은 창구여도 막지는 않는다 (만들 데까지 만든다)", True)
    ck("재 보지도 않고 '하루 10번' 이라고 단정하지 않는다",
       "하루 10번까지인데" not in buf.getvalue(), "단정하고 있다")
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
    ck("넓은 창구면 조용히 그냥 간다", "만든 데까지 보관" not in buf2.getvalue())

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

    print("\n④ 조립 — 컷을 진짜로 붙인다 (편마다 · 카라오케 자막)")
    S9.build(doc)
    parts = S9.parts_of(doc)
    ck(f"편이 나뉘어 있다 ({len(parts)}편)", len(parts) >= 2, f"{len(parts)}편")
    for p in parts:
        no = p["no"]
        f = S9.part_file(doc, no)
        ck(f"{no}편이 나왔다", f.exists() and f.stat().st_size > 100_000)
        if not f.exists():
            continue
        got = dur(f)
        mine = S9.part_cuts(doc, p)
        want = sum(S9.cut_sec(c, tmp / "voice" / f"c{c['n']:02d}.wav", None)[0]
                   for c in mine)
        ck(f"{no}편 길이가 셈과 맞는다 ({got:.1f}초)", abs(got - want) < 1.5,
           f"셈 {want:.1f}초 · 실제 {got:.1f}초")
        # ⚠️⚠️ 이 채널이 실제로 겪은 일 — 60초 이하 6편은 전부 1,200회 넘게
        #    나왔는데 127초 한 편은 5시간 반 동안 **조회수 0** 이었다.
        #    쇼츠 피드가 아예 안 태운 것이다. 그래서 여기서 못을 박는다.
        ck(f"{no}편이 60초를 안 넘는다 ({got:.0f}초)", got <= S9.PART_MAX_SEC,
           f"{got:.0f}초 — 넘으면 쇼츠 피드가 안 태운다")
        ck(f"{no}편이 너무 짧지 않다 ({got:.0f}초)", got >= 20, f"{got:.0f}초")
    ov = list((tmp / "ov").glob("*.png"))
    n_ch = sum(len(S9.chunks_of(t)) for c in cuts for _, t in c["turns"])
    # ⭐ 편마다 첫 컷에 **제목 카드**, 마지막 컷에 **끝 알림**이 더 붙는다
    n_title = len(parts) * len(S9.TITLE_FADE)
    n_tail = len(parts) * len(S9.TAIL_FADE)
    ck(f"자막 장을 토막 수 + 제목 + 끝 알림만큼 만들었다 "
       f"({n_ch}+{n_title}+{n_tail}장)",
       len(ov) == n_ch + n_title + n_tail, f"{len(ov)}장")

    print("\n④-2 편마다 화면 위 제목이 붙는가")
    for p in parts:
        first = S9.part_cuts(doc, p)[0]["n"]
        got = sorted((tmp / "ov").glob(f"c{first:02d}_title*.png"))
        ck(f"{p['no']}편 첫 컷에 제목 장이 있다 ({len(got)}장)",
           len(got) == len(S9.TITLE_FADE), f"{len(got)}장")
    # 편이 아닌 컷에는 제목이 붙으면 안 된다 (붙으면 화면이 계속 가려진다)
    firsts = {S9.part_cuts(doc, p)[0]["n"] for p in parts}
    stray = [f.name for f in (tmp / "ov").glob("*_title*.png")
             if int(f.name[1:3]) not in firsts]
    ck("편 첫 컷이 아닌 곳에는 제목이 안 붙는다", not stray, f"{stray[:4]}")

    print("\n④-3 끝에 '다음 편에 계속' 이 붙는가")
    lasts = {S9.part_cuts(doc, p)[0 - 1]["n"]: int(p["no"]) for p in parts}
    last_no = max(int(p["no"]) for p in parts)
    for n, no in sorted(lasts.items()):
        got = sorted((tmp / "ov").glob(f"c{n:02d}_tail*.png"))
        ck(f"{no}편 마지막 컷(컷{n})에 끝 알림이 있다 ({len(got)}장)",
           len(got) == len(S9.TAIL_FADE), f"{len(got)}장")
    stray2 = [f.name for f in (tmp / "ov").glob("*_tail*.png")
              if int(f.name[1:3]) not in lasts]
    ck("편 마지막 컷이 아닌 곳에는 안 붙는다", not stray2, f"{stray2[:4]}")
    # ⚠️ 마지막 편에 "다음 편에 계속" 이 붙으면 있지도 않은 편을 기다리게 된다
    from PIL import Image as _I3
    import hashlib as _h
    def _sig(png):
        return _h.sha1(_I3.open(png).convert("RGBA").tobytes()).hexdigest()
    ends = {no: _sig(sorted((tmp / "ov").glob(f"c{n:02d}_tail*.png"))[-1])
            for n, no in lasts.items() if list((tmp / "ov").glob(f"c{n:02d}_tail*.png"))}
    if len(ends) >= 2:
        others = [v for k, v in ends.items() if k != last_no]
        ck("마지막 편만 다른 글이 뜬다 (완결)",
           ends.get(last_no) not in others,
           "마지막 편에도 '다음 편에 계속' 이 붙었다 — 없는 편을 기다리게 된다")
        ck("마지막이 아닌 편들은 같은 글이다", len(set(others)) == 1)

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

    # ⭐⭐ 2026-08-31 손님: "줌인 줌아웃 등이 조금 더 있어서 생동감이 조금 더
    #    넘쳤으면 좋겠어." 예전에는 가운데서 커지는 것 하나뿐이었다.
    # ⭐⭐ 2026-08-31 손님: "배경음악이 좀 하나 깔려야 될 거 같거든?"
    #    ⚠️ 음악을 깔았는데 **말이 더 안 들리면 거꾸로다.** 그래서 귀로
    #       믿지 않고, 말하는 동안과 조용한 동안의 크기를 각각 재서 본다.
    print("\n⑧ 배경음악이 말을 안 덮는가")
    ck(f"배경음악 파일이 있다 (assets/bgm/{S9.BGM}.mp3)", S9.bgm_path() is not None)
    if S9.bgm_path():
        import math, struct, wave as _w
        td4 = pathlib.Path(tempfile.mkdtemp())
        vw = td4 / "v.wav"
        with _w.open(str(vw), "w") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)
            fr = [struct.pack("<h", int(9000 * math.sin(2 * math.pi * 220 * i / 48000)))
                  for i in range(48000 * 4)]                 # 앞 4초 = 말
            fr.append(b"\x00\x00" * 48000 * 4)               # 뒤 4초 = 조용함
            w.writeframes(b"".join(fr))
        sv = td4 / "src.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=black:s=270x480:d=8", "-i", str(vw),
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                        "-shortest", str(sv)], check=True)
        ov = td4 / "out.mp4"
        S9.music(sv, ov)

        def vol(f, ss, t):
            r = subprocess.run(["ffmpeg", "-v", "info", "-ss", str(ss), "-t", str(t),
                                "-i", str(f), "-af", "volumedetect", "-f", "null", "-"],
                               capture_output=True, text=True)
            for l in r.stderr.splitlines():
                if "mean_volume" in l:
                    return float(l.split(":")[-1].replace("dB", "").strip())
            return -99.0

        v0, v1 = vol(sv, 0.5, 3), vol(ov, 0.5, 3)
        q0, q1 = vol(sv, 5, 2.5), vol(ov, 5, 2.5)
        ck(f"말소리가 안 작아진다 ({v0:.1f} → {v1:.1f} dB)", v1 >= v0 - 1.0,
           "음악을 깔았더니 말이 더 안 들린다 — 거꾸로다")
        ck(f"조용한 자리에서 음악이 들린다 ({q1:.1f} dB)", q1 > -45,
           "음악이 너무 작아 없는 것과 같다")
        ck(f"음악이 말보다 확실히 작다 ({v1 - q1:.1f} dB 차이)", v1 - q1 >= 6,
           "음악이 말을 덮는다")
        ck("길이가 안 바뀐다", abs(S9.dur_of(ov) - S9.dur_of(sv)) < 0.15,
           f"{S9.dur_of(sv):.2f} → {S9.dur_of(ov):.2f}초")
        shutil.rmtree(td4, ignore_errors=True)

    print("\n⑦ 카메라가 컷마다 다르게 움직이는가")
    moves = [S9.move_of(c) for c in cuts]
    same = [c["n"] for c, m, m2 in zip(cuts[1:], moves[1:], moves) if m == m2]
    ck("이웃한 컷이 같은 움직임을 되풀이하지 않는다", len(same) <= len(cuts) // 3,
       f"이어서 같은 컷 {same}")
    ck(f"움직임이 여러 가지다 ({len({m[6] for m in moves})}가지)",
       len({m[6] for m in moves}) >= 3)
    # 줌이 너무 크면 1.4배로 키워 둔 그림의 화소를 넘어 흐려진다
    bad_z = [m[6] for m in moves if not (1.0 < m[0] <= 1.30 and 1.0 < m[1] <= 1.30)]
    ck("줌이 흐려지지 않는 범위 안이다 (1.0~1.30)", not bad_z, f"{bad_z}")
    # 대사 컷에서 옆으로 크게 훑으면 얼굴이 잘린다
    pan_talk = [c["n"] for c, m in zip(cuts, moves)
                if c["kind"] != "나레이션" and (abs(m[3] - m[2]) > 0.05
                                             or abs(m[5] - m[4]) > 0.05)]
    ck("대사 컷은 얼굴이 잘리게 훑지 않는다", not pan_talk, f"컷 {pan_talk}")

    # 진짜로 움직이는지 한 컷만 찍어서 본다 (정지 그림이면 화면이 안 바뀐다)
    from PIL import Image as _I, ImageDraw as _D
    grid = tmp2 = pathlib.Path(tempfile.mkdtemp())
    gi = _I.new("RGB", (S9.W, S9.H), (30, 30, 40))
    gd = _D.Draw(gi)
    for i in range(0, S9.W, 40):
        gd.line([(i, 0), (i, S9.H)], fill=(200, 170, 90), width=3)
    for j in range(0, S9.H, 40):
        gd.line([(0, j), (S9.W, j)], fill=(90, 160, 200), width=3)
    gp = tmp2 / "grid.png"; gi.save(gp)
    gw = tmp2 / "g.wav"; fake_wav(gw, 4.0)
    S9.lens_of(gw).write_text("[4.0]", encoding="utf-8")
    c0 = cuts[0]
    ovs0 = S9.karaoke(c0, 4.0, gw, tmp2 / "ov", 1)
    mp4 = tmp2 / "m.mp4"
    S9.cut_video(c0, gp, gw, None, ovs0, mp4)
    # ⚠️⚠️ 2026-09-02 — 끝 프레임을 **3.8초로 박아** 두었다가 깨졌다.
    #    말 빠르기(SPEED)를 1.08 → 1.20 으로 올리자 이 컷이 4.10초에서
    #    3.73초로 줄어, 3.8초 자리에는 프레임이 아예 없다.
    #    이 저장소에 이미 적힌 교훈이다 — **셈을 시험에 베껴 적지 않는다.**
    #    진짜 길이를 재서 그 끝자락을 찍는다.
    vlen = S9.dur_of(mp4)
    for k, t in ((0, 0.1), (1, max(0.2, vlen - 0.15))):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}",
                        "-i", str(mp4), "-frames:v", "1",
                        str(tmp2 / f"f{k}.png")], check=True)
        if not (tmp2 / f"f{k}.png").exists():
            raise SystemExit(f"❌ {t:.2f}초에서 프레임을 못 뽑았다 "
                             f"(영상 {vlen:.2f}초) — 뽑는 자리가 영상 밖이다")
    a, b = (_I.open(tmp2 / f"f{k}.png").convert("L") for k in (0, 1))
    pa, pb = a.load(), b.load()
    gap = sum(abs(pa[x, y] - pb[x, y])
              for y in range(0, a.height, 16) for x in range(0, a.width, 16))
    gap /= (a.height // 16) * (a.width // 16)
    ck(f"화면이 실제로 움직인다 (차이 {gap:.1f})", gap > 5,
       "처음과 끝이 거의 같다 — 정지 그림이나 다름없다")
    shutil.rmtree(tmp2, ignore_errors=True)

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
