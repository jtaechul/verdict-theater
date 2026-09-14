#!/usr/bin/env python3
"""⭐ **자막이 깜빡이지 않는지** 본다. 값 0원 (진짜로 한 컷 만들어서 잰다).

    python3 tools/flicker_check.py

2026-09-14 손님: **"마지막 4편을 보면 자막이 나타났다 사라지면서 계속
검은색으로 깜빡거리는 현상이 발생하거든. 앞으로는 이런 문제점 없도록
코드 수정해."**

■ 까닭 — `between(t, a, b)` 는 **양쪽 끝을 다 넣는다**
  자막은 낱말마다 한 장씩 깔리고, 앞 장의 끝(b)과 뒷 장의 시작(a)이
  **같은 값**이다. 그래서 딱 그 한 프레임에서 두 장이 겹쳐 깔린다.
  자막 판(어두운 그늘)이 두 겹이 되니 그 프레임만 확 어두워진다 —
  낱말이 바뀔 때마다 한 번씩, 그래서 "계속 깜빡" 인다.
  실측(S92 4편 완성본): 프레임 1292·1322·1370·1412 에서
  자막칸 밝기 65.5 → **41.5** → 65.5 (딱 한 프레임씩)

■ 왜 못 잡았나 — **한 프레임은 눈으로만 보인다**
  화면·소리·길이·자막 글자 다 멀쩡하다. 파형에도 안 나온다.
  1/30초짜리라 캡처 한 장으로도 안 잡힌다. 그래서 이 검사는
  **프레임을 한 장씩 재서** 한 프레임만 튀는 자리를 찾는다.

■ 고침 — `gte(t,a) * lt(t,b)` (끝은 빼는 반열린 구간)
  그러면 어느 순간에도 자막 장은 정확히 하나만 깔린다.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw                             # noqa: E402

import short90 as S                                          # noqa: E402

bad = []


def ck(name, ok):
    print(("  ✅ " if ok else "  ❌ ") + name)
    if not ok:
        bad.append(name)


def a_still(p):
    """⚠️ 바탕을 **밝게** 만든다. 어두운 바탕이면 자막 판(그늘)이 두 겹이
       돼도 밝기 차이가 작아 시험이 고장을 못 잡는다 (처음에 그랬다)."""
    im = Image.new("RGB", (S.W, S.H), (232, 228, 220))
    d = ImageDraw.Draw(im)
    for y in range(0, S.H, 90):
        d.rectangle((0, y, S.W, y + 45), fill=(250, 248, 244))
    im.save(p)


def a_voice(p, sec):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"sine=f=220:d={sec}", "-ac", "1", str(p)],
                   check=True, capture_output=True)


def blinks(mp4):
    """자막칸이 **한 프레임만** 튀는 자리들."""
    out = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(mp4),
         "-vf", "crop=%d:330:0:%d,signalstats,"
                "metadata=print:key=lavfi.signalstats.YAVG:file=-"
                % (S.W, S.SUB_TOP - 10),
         "-f", "null", "-"], capture_output=True, text=True).stdout
    vals, t = [], None
    for line in out.splitlines():
        m = re.match(r"frame:(\d+)\s+pts:\d+\s+pts_time:([0-9.]+)", line)
        if m:
            t = (int(m.group(1)), float(m.group(2)))
        m2 = re.search(r"YAVG=([0-9.]+)", line)
        if m2 and t:
            vals.append((t[0], t[1], float(m2.group(1))))
            t = None
    out = []
    for i in range(1, len(vals) - 1):
        a, b, c = vals[i - 1][2], vals[i][2], vals[i + 1][2]
        # 앞뒤는 비슷한데 **가운데 한 장만** 확 다르다 = 깜빡임
        if abs(b - a) > 8 and abs(b - c) > 8 and abs(c - a) < 6:
            out.append((vals[i][0], round(vals[i][1], 2), round(a, 1), round(b, 1)))
    return out, len(vals)


def one_cut(d, mod=None):
    """자막 장을 **프레임 시각에 딱 맞춰** 깔아 한 컷 만든다.

    ⚠️⚠️ 여기가 이 시험의 핵심이다. 두 장이 겹치는 것은 자막 장의 경계가
       **프레임 시각과 정확히 같을 때만** 일어난다(between 은 양끝을 다
       넣으므로, 그 순간의 프레임이 두 장을 다 받는다). 경계가 프레임 사이에
       떨어지면 아무 일도 안 생긴다.
       → 처음에 아무 경계나 썼다가 **고장난 판에서도 깜빡임이 0** 으로 나와
         시험이 거짓말을 했다. 경계를 1/FPS 의 배수로 딱 맞춘다.
    """
    m = mod or S
    cut = {"n": 38, "sec": 6.0, "who": [],
           "turns": [["나레이션", "결국 장남은 동생들에게 돈을 토해냈습니다."]],
           "say": ["담담하고 또렷하게"], "scene": "an empty hall", "kind": "나레이션"}
    still = d / "s.png"
    a_still(still)
    voice = d / "v.wav"
    sec = 5.0
    a_voice(voice, sec)
    # 자막 장 다섯을 1초씩 — 경계가 30·60·90·120 프레임에 딱 떨어진다
    ovs = []
    for k in range(5):
        png = d / f"ov{k}.png"
        m.overlay(cut, png, cut["turns"][0], now=k)
        ovs.append((png, float(k), float(k + 1)))
    out = d / "c.mp4"
    m.cut_video(cut, still, voice, None, ovs, out)
    return out, len(ovs)


def main():
    d = Path(tempfile.mkdtemp())

    print("■ ① 자막 장이 **겹치지 않게** 깔리는가 (짜임)")
    fn = (ROOT / "src" / "short90.py").read_text("utf-8")
    body = fn.split("def cut_video(")[1].split("\ndef ")[0]
    ck("끝을 뺀 반열린 구간을 쓴다 (gte · lt)",
       "gte(t," in body and "lt(t," in body)
    # ⚠️ 내 주석에도 'between(t,' 이라는 낱말이 있다. 낱말이 아니라
    #    **실제로 쓰는 자리**(enable= 뒤)를 본다.
    ck("양끝을 다 넣는 between 을 안 쓴다",
       "enable='between(t," not in body)

    print("\n■ ② 진짜로 한 컷 만들어서 **프레임을 한 장씩 재 본다**")
    mp4, n_ov = one_cut(d)
    got, frames = blinks(mp4)
    print(f"     자막 장 {n_ov}개 · 프레임 {frames}개를 쟀다")
    ck("한 프레임만 튀는 자리가 하나도 없다", not got)
    for f, t, a, b in got[:6]:
        print(f"       프레임{f} {t}초  {a} → {b}")

    print("\n■ ③ 이 시험이 **진짜 깜빡임을 잡을 수 있는가**")
    #    ⚠️ 못 잡는 시험은 초록불만 켜 준다. 일부러 되돌려 만들어 본다.
    src = (ROOT / "src" / "short90.py").read_text("utf-8")
    hurt = src.replace("f\":enable='gte(t,{a:.3f})*lt(t,{b:.3f})'{nxt};\")",
                       "f\":enable='between(t,{a:.3f},{b:.3f})'{nxt};\")", 1)
    ck("일부러 되돌릴 자리를 찾았다", hurt != src)
    # ⚠️ 흉내 판은 **src/ 옆에** 두어야 글꼴·자원 경로가 맞는다
    hp = ROOT / "src" / "_flicker_hurt.py"
    hp.write_text(hurt, encoding="utf-8")
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("s90hurt", hp)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["s90hurt"] = mod
        spec.loader.exec_module(mod)
        hd = d / "hurt"
        hd.mkdir()
        out2, _ = one_cut(hd, mod)
        got2, _ = blinks(out2)
    finally:
        hp.unlink(missing_ok=True)
    ck(f"양끝을 다 넣게 되돌리면 **깜빡임이 잡힌다** ({len(got2)}군데)", bool(got2))
    for f, t, a, b in got2[:4]:
        print(f"       프레임{f} {t}초  {a} → {b}")

    shutil.rmtree(d, ignore_errors=True)
    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 자막 깜빡임: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 자막 깜빡임: 어느 순간에도 자막 장은 하나만 깔린다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
