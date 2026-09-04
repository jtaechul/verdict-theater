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
    doc = json.loads((ROOT / "data" / "series" / "S90.json")
                     .read_text(encoding="utf-8"))
    n = S.open_cuts(doc)[0]
    c = [x for x in doc["cuts"] if x["n"] == n][0]
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
    ck(f"우리가 사는 길이와 프롬프트가 맞는다 ({S.OPEN_SEC:g}초)",
       f"{S.OPEN_SEC:g}-second" in t and "8-second" not in t)
    ck("원본 대본은 안 건드린다 (손보기는 첫 장면에만)",
       "8-second" in str(c.get("veo") or ""))
    # ⚠️ 손본 글을 **실제로 쓰는지**까지 본다. 손보는 함수만 있고 안 쓰면
    #    시험은 통과하는데 진짜 영상에는 옛 글이 들어간다.
    src = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
    op = (re.search(r"def openers\(doc\)[\s\S]*?\n\ndef ", src) or [""])[0]
    ck("만들 때 그 손본 글을 쓴다", "prompt = open_prompt(c)" in op)


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
    ck("켤 때만 돈 뚜껑을 올린다",
       "inputs.open_video == '예' && '4300' || '2800'" in yml)
    ck("Veo 부르는 횟수에도 뚜껑이 있다", "VEO_CALL_CAP:" in yml)


def live():
    """가짜 4초 영상으로 **진짜 조립**해 본다 (Veo 를 안 부르므로 0원)."""
    print("\n⑤ 진짜로 붙는가 (가짜 4초 영상으로 조립 · 0원)")
    doc = json.loads((ROOT / "data" / "series" / "S90.json")
                     .read_text(encoding="utf-8"))
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


def main():
    print("⭐ 편 첫 장면 영상 (값 0원 — Veo 를 안 부른다)\n")
    rules()
    lips()
    wiring()
    live()
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
