#!/usr/bin/env python3
"""⭐ 편 첫 장면 영상이 제대로 붙는지 본다. 값 0원 (Veo 를 안 부른다).

    python3 tools/open_check.py

손님(2026-09-04): "각 편당 첫번째 씬만 영상으로 나오고 그 다음씬부터는
이미지로 나오는거지."

편이 셋이면 **독립된 스와이프 판정이 셋**이고 그 판정은 첫 1~2초에 갈린다.
그 자리 셋에만 진짜 움직임을 넣는다. 값이 나가는 일이라 지켜야 할 것이 많다 —
켜야만 돌고 · 그림을 넣어 움직이게 하고(얼굴이 안 바뀌게) · 4초만 사고 ·
다시 누르면 0원이고 · 하나 실패해도 편 전체가 안 죽어야 한다.

⚠️ 표만 보지 않는다. **가짜 4초 영상으로 진짜 조립까지 해서** 길이·화면
   갈림·자막을 잰다 (Veo 는 안 부르므로 0원).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image                                        # noqa: E402

import cost                                                  # noqa: E402
import short90 as S                                          # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name
          + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def rules():
    src = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
    op = (re.search(r"def openers\(doc\)[\s\S]*?\n\ndef ", src) or [""])[0]

    print("① 값이 새지 않는가")
    ck("켜야만 돈다 (기본은 꺼짐)", not S.OPEN_VIDEO)
    # ⚠️ **읽는 자리**를 센다. 설명글에 이름이 나오는 것은 안 센다.
    #    두 곳에서 읽으면 한쪽만 고쳐 놓고 "껐다" 고 믿게 된다.
    ck("켜는 열쇠를 읽는 자리가 하나뿐이다 (VT_OPEN_VIDEO)",
       src.count('os.environ.get("VT_OPEN_VIDEO"') == 1)
    ck("만들기 **전에** 값을 적어 준다", "약 {krw1:,.0f}원" in op)
    ck("다시 누르면 0원이다 (지문으로 건너뛴다)",
       "reuse.can_reuse(out, sig)" in op and "reuse.stamp(out, sig)" in op)
    ck("그림이 바뀌면 다시 만든다 (지문에 그림이 들어 있다)",
       "still.read_bytes()" in op)
    ck("4초만 산다 (8초는 값만 두 배고 판정 구간 밖이다)", S.OPEN_SEC <= 4.0)
    ck(f"한 개 값이 계산된다 (약 "
       f"{cost.video_krw('veo-3.1-lite', S.OPEN_SEC):,.0f}원)",
       cost.video_krw("veo-3.1-lite", S.OPEN_SEC) > 0)

    print("\n② 화면이 망가지지 않는가")
    ck("**그림을 넣어** 움직이게 한다 (image-to-video)", "start=still" in op)
    ck("세로로 받는다 (위아래가 안 잘리게)", S.OPEN_RATIO == "9:16")
    # ⚠️⚠️ 2026-09-05 실측 — 1080p 는 4초를 안 받는다 (HTTP 400).
    #    이것 때문에 편 첫 장면 세 개가 다 실패했다. 값은 0원이었지만
    #    손님은 켰다고 믿고 계셨다. 길이에 맞는 화질을 골라야 한다.
    import veo as V                                          # noqa: E402
    ck(f"그 길이에 쓸 수 있는 화질을 고른다 "
       f"({S.OPEN_SEC:g}초 → {V.res_for(S.OPEN_SEC)})",
       V.res_for(S.OPEN_SEC) == "720p",
       "1080p 는 4초를 안 받는다 — 400 으로 통째로 실패한다")
    ck("긴 것은 여전히 선명하게 받는다 (8초 → 1080p)",
       V.res_for(8) == "1080p")
    ob = (re.search(r"def open_bg\([\s\S]*?\n\ndef ", src) or [""])[0]
    ck("되돌려 잇지 않는다 (4초에서 화면이 안 튄다)",
       "stream_loop" not in ob and "xfade" in ob)
    ck("그림으로 부드럽게 넘어간다", S.OPEN_XFADE > 0)
    ck("Veo 소리를 안 쓴다 (우리 나레이션이 깔린다)",
       "opener" not in (re.search(r"def cut_sec\([\s\S]*?\n\ndef ",
                                  src) or [""])[0])

    print("\n③-2 하나 실패해도 편 전체가 사는가")
    ck("못 만들면 그 컷은 그림으로 간다",
       "이 컷은 그림으로 갑니다" in op and "continue" in op)
    ck("실패한 찌꺼기 파일을 지운다", "out.unlink(missing_ok=True)" in op)
    bp = (re.search(r"def build_part\([\s\S]*?\n\ndef ", src) or [""])[0]
    ck("영상이 있을 때만 쓴다 (없으면 그냥 그림)", "opener.exists()" in bp)
    ck("편의 **첫 컷**만 연다", "i == 0 and opener.exists()" in bp)


def lips():
    """⭐ 2026-09-04 손님: "동영상에서 입은 안움직여도 될 것 같아."

    편 첫 컷은 나레이션 컷이라 화면에서는 아무도 말하지 않는다. 입이 움직이면
    우리 나레이션과 어긋나 곧바로 가짜처럼 보인다.
    ⚠️ 이 저장소의 오랜 규칙 — **금지형으로 적지 않는다.** 모델은 부정을
       흘려듣고 오히려 그대로 한다. 입을 다물게 하려고 적은 줄이 입을
       움직이게 만들 수 있다.
    """
    print("\n③ 첫 장면에서 입이 안 움직이는가")
    # ⚠️⚠️ 2026-09-05 — 예전에는 여기서 **저장된 S90 대본을 읽었다.** 그런데
    #    길이 검사가 "8-second 가 없다" 였고, S90 지문에는 마침 8-second 가
    #    적혀 있어 통과했다. 실제로 만든 S91 지문은 **6-second** 였고,
    #    손보는 코드도 "8-second" 만 바꾸고 있어 **한 번도 안 바뀌었다.**
    #    → 시험글을 여기서 만든다. 그리고 몇 초라고 적혀 있든 잡는다.
    c = fake_cut(6)
    t = S.open_prompt(c)
    ck("입을 다물라고 **바라는 것만**으로 적었다",
       "mouth closed" in t and "jaw relaxed" in t)
    ck("말하는 게 아니라 생각하는 얼굴이라고 적었다", "thinking rather than" in t)
    ck("움직임을 무엇으로 채울지 적었다 (숨·눈깜빡임·머리카락)",
       "calm breath" in t and "slow blink" in t)
    # 입·소리를 **금지형**으로 적은 줄이 남아 있으면 안 된다
    hot = [ln for ln in t.splitlines()
           if re.search(r"nobody|never|\bdo(es)? not\b|\bdon't\b", ln)
           or (re.search(r"\bno \w", ln) and not ln.startswith("ON SCREEN:"))]
    ck("입·소리를 금지형으로 적은 줄이 없다", not hot, " | ".join(hot)[:120])
    # ⭐ 몇 초라고 적혀 있든 **우리가 사는 길이**로 바뀌어야 한다
    got = re.findall(r"(\d+(?:\.\d+)?)-second single continuous take", t)
    ck(f"우리가 사는 길이와 프롬프트가 맞는다 ({S.OPEN_SEC:g}초)",
       got and all(float(x) == S.OPEN_SEC for x in got),
       f"지문에 {got} 초라고 적혀 있다")
    for sec in (6, 8, 5):                 # 대본이 어떤 길이로 적어 와도
        tt = S.open_prompt(fake_cut(sec))
        ck(f"{sec}초짜리로 적혀 와도 {S.OPEN_SEC:g}초로 바꾼다",
           f"{S.OPEN_SEC:g}-second single continuous take" in tt
           and f"{sec}-second single continuous take" not in tt)
    ck("첫 프레임부터 움직이라고 적는다 (앞머리가 정지 화면이 안 되게)",
       "MOTION START" in t and "very first frame" in t)
    ck("원본 대본은 안 건드린다 (손보기는 첫 장면에만)",
       "6-second" in str(c.get("veo") or ""))
    # ⚠️ 손본 글을 **실제로 쓰는지**까지 본다. 손보는 함수만 있고 안 쓰면
    #    시험은 통과하는데 진짜 영상에는 옛 글이 들어간다.
    src = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
    op = (re.search(r"def openers\(doc\)[\s\S]*?\n\ndef ", src) or [""])[0]
    ck("만들 때 그 손본 글을 쓴다", "prompt = open_prompt(c)" in op)


def fake_cut(sec):
    """시험용 컷 하나. **저장된 대본 파일을 안 읽으려고** 여기서 만든다
    (2026-09-05: S90 을 읽던 검사가 S91 의 진짜 고장을 못 잡았다)."""
    return {"n": 1, "kind": "나레이션", "who": ["아내"],
            "turns": [["나레이션", "시험"]],
            "veo": (f"Fictional scene, invented characters, photoreal grounded "
                    f"drama. {sec}-second single continuous take, vertical "
                    f"portrait format (9 x 16).\n"
                    f"SHOT: the wife sits in a dark room.\n"
                    f"ACTION: the wife sits still. Mouths stay closed the whole "
                    f"time.\n"
                    f"AUDIO: nobody speaks and nobody moves their lips at any "
                    f"point; only the quiet room tone of the location.")}


def fake_doc():
    """시험용 대본 하나 (3편 × 3컷). 저장된 대본 파일을 안 읽으려고 만든다."""
    cuts, parts = [], []
    for k in range(3):
        a = k * 3 + 1
        for n in range(a, a + 3):
            cuts.append({"n": n, "kind": "나레이션", "who": ["아내"],
                         "turns": [["나레이션", "시험 문장입니다."]],
                         "say": ["담담하게"], "sec": 5.0,
                         "scene": "the wife sits in a dark room",
                         "still": f"SHOT: still {n}", "veo": f"VEO {n}"})
        parts.append({"no": k + 1, "cuts": [a, a + 2],
                      "card": ["첫 줄", "둘째 줄"], "yt_title": "시험"})
    return {"sid": "TEST", "title": "시험 사건", "series_label": "시험 사건",
            "cuts": cuts, "parts": parts}


def wiring():
    """단추 → 워크플로 → 프로그램까지 스위치가 끊기지 않고 이어지는가."""
    js = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
    yml = (ROOT / ".github" / "workflows" / "short90.yml").read_text(encoding="utf-8")

    print("\n④ 단추에서 프로그램까지 이어지는가")
    ck("화면에 켜고 끄는 자리가 있다", 'id="w-open"' in js)
    # ⚠️ 파일 전체에서 '약 …원' 을 찾으면 다른 칸의 값 표시에 속는다.
    #    **이 칸(③ 세 편 만들기) 안에서** 찾는다.
    pc = (re.search(r"function partsCard\(w\)[\s\S]*?\n}", js) or [""])[0]
    ck("그 자리에 **값이 적혀 있다**",
       'id="w-open"' in pc and "+약 " in pc and "470" in pc)
    ck("기본은 꺼짐이다 (checked 가 없다)",
       'id="w-open" checked' not in js.replace("> ", ">"))
    mk = (re.search(r"async function workMake\([\s\S]*?\n}", js) or [""])[0]
    ck("누르기 전에 얼마인지 보여 준다", "원이 나갑니다" in mk)
    ck("끄고 누르면 0원이라고 적어 준다", "전부 그림 · 0원" in mk)
    ck("켠 값을 서버로 보낸다", "open_video:" in mk)
    ck("서버는 '예' 일 때만 켠다", "=== '예') ? '예' : '아니요'" in js)
    ck("워크플로로 넘긴다", "open_video: openv" in js)
    ck("워크플로가 그 칸을 받는다", "open_video:" in yml)
    ck("워크플로가 프로그램 스위치로 바꾼다", "VT_OPEN_VIDEO:" in yml)
    # ⚠️ 돈 뚜껑을 안 올리면 켠 날에 한도에 걸려 멈춘다. 늘 올려 두면
    #    안 켠 날에 막는 시늉만 하게 된다 — **켤 때만** 올려야 한다.
    # ⭐ 2026-09-05 — 뚜껑을 손으로 안 적고 대본에서 셈한다(plan_cost.py).
    #    그러니 "켰을 때만 영상값이 더해지는가" 를 **진짜 돌려서** 본다.
    import subprocess as _sp
    def _cap(on):
        e = dict(os.environ, VT_SID="S91", VT_OPEN_VIDEO=("1" if on else ""))
        out = _sp.run([sys.executable, str(ROOT / "tools" / "plan_cost.py"),
                       "--env"], capture_output=True, text=True, env=e).stdout
        return int([x for x in out.splitlines()
                    if x.startswith("VT_RUN_KRW=")][0].split("=")[1])
    off, on = _cap(False), _cap(True)
    ck(f"켤 때만 돈 뚜껑이 올라간다 (끔 {off:,}원 → 켬 {on:,}원)", on > off + 800)
    ck("Veo 부르는 횟수에도 뚜껑이 있다", "VEO_CALL_CAP=" in
       (ROOT / "tools" / "plan_cost.py").read_text(encoding="utf-8"))
    # ⭐⭐⭐ 2026-09-05 — **이 단계가 없어서 한 번도 안 돌았다.**
    #    src/short90.py 는 stills/voice/build 를 따로 부르는데, 첫 장면은
    #    'all' 일 때만 돌게 걸어 뒀다. 손님이 체크하고 값까지 각오하셨는데
    #    기능이 통째로 안 돈 것이다. 표만 보고 "붙였다" 고 믿으면 안 된다.
    ck("워크플로에 첫 장면 단계가 **있다**",
       "short90.py open" in yml,
       "만드는 자리가 없으면 켜도 아무 일이 안 일어난다")
    ck("그 단계가 그림 다음 · 소리 앞이다",
       yml.index("short90.py stills") < yml.index("short90.py open")
       < yml.index("short90.py voice"),
       "그림을 넣어 움직이게 하므로 그림이 먼저다")
    ck("켰을 때만 그 단계가 돈다", "env.VT_OPEN_VIDEO == '1'" in yml)
    ck("첫 장면이 실패해도 편 전체가 안 죽는다",
       "그림으로 갑니다" in yml and "exit 1" not in
       yml[yml.index("2-2) 편 첫 장면"):yml.index("3) 나레이션")])
    ck("만든 첫 장면을 사건마다 따로 보관한다", '"open-$S"' in yml)
    ck("조립 단계가 첫 장면을 받아 온다", "for T in stills voice open" in yml)


def live():
    """가짜 4초 영상으로 **진짜 조립**해 본다 (Veo 를 안 부르므로 0원)."""
    print("\n⑤ 진짜로 붙는가 (가짜 4초 영상으로 조립 · 0원)")
    doc = fake_doc()                     # ⚠️ 저장된 대본 파일에 안 기댄다
    ns = S.open_cuts(doc)
    ck(f"편마다 첫 컷 하나씩 골라진다 ({ns})",
       len(ns) == len(S.parts_of(doc)) and len(set(ns)) == len(ns))

    with tempfile.TemporaryDirectory() as td:
        T = Path(td)
        op = T / "open.mp4"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                        f"testsrc=size={S.W}x{S.H}:rate={S.FPS}:duration=4",
                        "-pix_fmt", "yuv420p", str(op)], check=True)
        still = T / "s.png"
        Image.new("RGB", (S.W, S.H), (30, 40, 60)).save(still)
        voice = T / "v.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                        "sine=frequency=200:duration=12", "-ac", "1",
                        str(voice)], check=True)
        (T / "v.len.json").write_text(json.dumps([12.0]))

        c = [x for x in doc["cuts"] if x["n"] == ns[0]][0]
        sec0, _ = S.cut_sec(c, voice, None)
        ovs = S.karaoke(c, sec0, voice, T / "ov", ns[0],
                        title={"no": 1, "label": "시험", "card": ["첫 줄", "둘째 줄"],
                               "size": 72}, mark="시험 · 1편")
        out = T / "cut.mp4"
        sec = S.cut_video(c, still, voice, None, ovs, out, opener=op)
        got = S.dur_of(out)
        ck(f"길이가 셈과 맞는다 ({sec:.1f}초 ≈ {got:.1f}초)", abs(sec - got) < 0.25)
        ck("컷이 4초보다 길다 (그림으로 이어져야 하는 상황이다)", sec > S.OPEN_SEC + 1)

        def px(t):
            f = T / f"f{t}.png"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t),
                            "-i", str(out), "-frames:v", "1", str(f)], check=True)
            return Image.open(f).convert("RGB").getpixel((S.W // 2, 300))

        a, b = px(1.0), px(min(sec - 0.4, S.OPEN_SEC + 2.0))
        ck("앞은 영상이다 (색띠가 보인다)", sum(a) > 200, str(a))
        ck("뒤는 그림이다 (남색 배경)", abs(b[0] - 30) < 25 and abs(b[2] - 60) < 25,
           str(b))
        ck("영상과 그림이 서로 다른 화면이다", a != b)
        ck("자막이 얹혀 있다 (배경을 밀어내지 않는다)", len(ovs) >= 2)


def again():
    """⑥ 안전 필터에 걸리면 **한 번만** 다시 해 보는가 (2026-09-05 손님).

    손님: "1화는 앞에 영상이 아닌 이미지야."
    까닭 — 구글 안전 필터가 1편 첫 장면을 걸렀다(raiMediaFilteredCount). 그런데
    우리가 찾던 열쇳말이 안 맞아 "까닭을 모르겠다" 로 적혔고, 다시 해 보지도
    않고 그림으로 넘어갔다.
    """
    print("\n⑥ 안전 필터에 걸렸을 때 (2026-09-05 손님: 1편이 그림으로 열렸다)")
    import veo                                             # noqa: E402
    ck("안전 필터를 따로 잡는 갈래가 있다",
       issubclass(veo.RaiFiltered, veo.VeoError))
    vs = (ROOT / "src" / "veo.py").read_text(encoding="utf-8")
    ck("구글이 쓰는 열쇳말(rai)을 대소문자 안 가리고 본다",
       'low = blob.lower()' in vs and '"rai"' in vs)
    src = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
    op = (re.search(r"def openers\(doc\)[\s\S]*?\n\ndef ", src) or [""])[0]
    ck("걸리면 씨앗을 바꿔 한 번 더 부른다",
       "except veo.RaiFiltered" in op and 'veo._seed(doc.get("sid"), n, "2")' in op)
    ck("두 번까지만 한다 (세 번째는 없다)", op.count("veo.make_clip") == 2)
    ck("그래도 안 되면 편 전체를 안 죽인다", "이 컷은 그림으로 갑니다" in op)
    ck("어느 편이 그림으로 열리는지 크게 적는다",
       "첫 장면이 그림으로 열리는 편" in op)
    pc = (ROOT / "tools" / "plan_cost.py").read_text(encoding="utf-8")
    ck("다시 해 보는 값이 뚜껑에 들어 있다", "(parts + 1)" in pc)


def cover():
    """⑦ 컷이 짧으면 **그림이 다시 안 나온다** (2026-09-05 손님).

    손님: "3화 앞에는 영상부터 나와야 하는데, 이미지 나온후 영상 나왔다가
          또 같은 이미지가 나와."
    까닭 — 컷 4.23초 · 영상 4초. 남은 0.23초에 그림이 다시 떠서, 영상이 끝나고
    사진으로 얼어붙는 것처럼 보였다.
    """
    print("\n⑦ 짧은 컷은 영상 하나로 덮는가 (진짜로 붙여서 화면 색으로 잰다)")
    with tempfile.TemporaryDirectory() as td:
        T = Path(td)
        op, still, ov = T / "o.mp4", T / "s.png", T / "ov.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                        f"color=c=red:s={S.W}x{S.H}:d=4:r={S.FPS}",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(op)],
                       check=True)
        Image.new("RGB", (S.W, S.H), (0, 0, 255)).save(still)
        Image.new("RGBA", (S.W, S.H), (0, 0, 0, 0)).save(ov)

        def build(sec):
            wav = T / f"v{int(sec * 100)}.wav"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                            "anullsrc=r=48000:cl=mono", "-t",
                            f"{sec * 1.06:.2f}", str(wav)], check=True)
            c = {"n": 1, "kind": "나레이션", "text": "시험", "scene": "x",
                 "turns": [["나레이션", "시험"]], "sec": sec}
            out = T / f"c{int(sec * 100)}.mp4"
            got = S.cut_video(c, still, wav, None, [(ov, 0.0, sec)], out,
                              opener=op)
            seq, t = [], 0.0
            while t < got - 0.05:
                f = T / "f.png"
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss",
                                f"{t:.2f}", "-i", str(out), "-frames:v", "1",
                                str(f)], check=True)
                r, _g, b = Image.open(f).convert("RGB").resize((1, 1)) \
                    .getpixel((0, 0))
                seq.append("V" if r > b + 30 else ("I" if b > r + 30 else "x"))
                t += 0.2
            return "".join(seq), got

        a, sa = build(4.23)          # 손님이 보신 그 길이 (3편 첫 컷)
        ck(f"짧은 컷({sa:.1f}초)은 처음부터 끝까지 영상이다 [{a}]",
           set(a) == {"V"}, "그림이 다시 나온다 — 손님이 짚으신 그 고장")
        b, sb = build(5.47)          # 그림으로 넘어갈 만큼 긴 컷 (2편 첫 컷)
        ck(f"긴 컷({sb:.1f}초)은 영상 → 그림으로 넘어간다 [{b}]",
           b.startswith("V") and b.endswith("I"))
        ck("긴 컷의 그림이 눈에 보일 만큼 남는다",
           b.count("I") * 0.2 >= S.OPEN_TAIL_MIN * 0.6, f"{b.count('I')}칸뿐")


def main():
    print("⭐ 편 첫 장면 영상 (값 0원 — Veo 를 안 부른다)\n")
    rules()
    lips()
    wiring()
    live()
    again()
    cover()
    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 편 첫 장면: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 편 첫 장면: 켜야만 돌고 · 그림으로 부드럽게 이어진다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
