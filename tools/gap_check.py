#!/usr/bin/env python3
"""⭐ **덜 된 편이 다 된 척하지 못하게** 막는다. 값 0원.

    python3 tools/gap_check.py

2026-09-14 손님(화면 캡처): **"이 부분은 영상이 아니라 이미지로 만들어져
있어. 다른 구간도 문제가 있을 테니 확인해서 조치해. 다시는 이런 일들이
발생하지 않게 코드 수정해."**

■ 무슨 일이 났나
  대사 영상을 만들라고 눌렀는데 한 달 한도에 걸려 여덟 컷을 못 샀다.
  그 컷들은 **조용히 그림으로 떨어졌고**, 조립은 "■ 다 됐다" 를 찍고
  0(성공)을 돌려줬다. 워크플로는 초록불. 손님은 다 된 줄 알고 보시다가
  슬라이드쇼를 만났다 — 3편은 대사 네 컷이 **전부** 그림이었다.

■ 이 고장의 모양 — "모자란 것"이 "된 것"으로 둔갑한다
  값이 모자라 멈추는 것 자체는 고장이 아니다. 고장은 **그 사실이 어디에도
  남지 않은 것**이다. 그래서 세 자리에 못을 박는다 —
      ① 조립이 덜 됐으면 **실패로 끝낸다** (만든 것은 그대로 둔다)
      ② 상태 파일에 **어느 컷이 비었는지 적는다** (talk_gaps)
      ③ 올리기가 **막는다** — 올리기는 되돌릴 수 없는 자리다

⚠️ '전부 그림' 으로 고르고 누른 것은 고장이 아니라 **고른 것**이다.
   그때는 막지 않는다. 이 구분을 못 하면 검사가 멀쩡한 일을 막는다.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

import short90 as S                                          # noqa: E402
import shortstate                                            # noqa: E402

bad = []


def ck(name, ok):
    print(("  ✅ " if ok else "  ❌ ") + name)
    if not ok:
        bad.append(name)


def a_still(p):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (360, 640), (30, 38, 58))
    ImageDraw.Draw(im).ellipse((100, 160, 260, 380), fill=(205, 175, 155))
    im.save(p)


def a_clip(p, png, sec):
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(png),
                    "-f", "lavfi", "-i", f"anoisesrc=d={sec}:c=pink:a=0.02",
                    "-t", str(sec), "-r", "24", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "2",
                    str(p)], check=True, capture_output=True)


def a_doc():
    def cut(n, who, txt):
        return {"n": n, "sec": 4.0,
                "who": [] if who == "나레이션" else [who],
                "turns": [[who, txt]], "say": ["조용하고 단단하게"],
                "scene": "a room", "kind": who[:4]}
    cuts = [cut(1, "나레이션", "그날 십삼억이 입금됐습니다."),
            cut(2, "아버지", "그 큰돈을 네가 왜 다 빼간 것이냐."),
            cut(3, "나레이션", "아들은 답하지 않았습니다."),
            cut(4, "장남", "아버지가 저보고 관리하라고 주신 겁니다.")]
    return {"sid": "TEST", "title": "시험",
            "people": {"아버지": {"age": "70대", "sex": "남"},
                       "장남": {"age": "50대", "sex": "남"}},
            "parts": [{"no": 1, "cuts": [1, 4], "title": "ㄱ", "card": ["ㄱ", "ㄴ"]}],
            "cuts": cuts}


def main():
    d = Path(tempfile.mkdtemp())
    doc = a_doc()

    print("■ ① 덜 된 것을 **덜 됐다고 셀 수 있는가** (talk_gaps)")
    real_out, real_tv = S.OUT, S.TALK_VIDEO
    try:
        S.OUT = d                       # 영상도 그림도 하나도 없는 자리
        S.TALK_VIDEO = True
        got = S.talk_gaps(doc)
        ck("영상이 하나도 없으면 빈 컷이 잡힌다", bool(got))
        narr = {c["n"] for c in doc["cuts"] if S.is_narr(c)}
        ck("나레이션 컷은 빈 컷에 넣지 않는다 (그건 원래 그림이다)",
           not (set(got) & narr))
        # ⚠️ 계획을 다시 부르는 것으로 재면 아무것도 안 재는 것이다.
        #    **파일을 실제로 놓아 보고** 답이 따라 바뀌는지 본다.
        n = got[0]
        st = d / "stills"
        st.mkdir(parents=True, exist_ok=True)
        a_still(st / f"c{n:02d}.png")
        td = S.talk_dir()
        td.mkdir(parents=True, exist_ok=True)
        clip = td / f"c{n:02d}.mp4"
        by = {c["n"]: c for c in doc["cuts"]}
        import talkplan as TP
        sec = TP.talk_sec(S.turns_of(by[n])[0][1])
        a_clip(clip, st / f"c{n:02d}.png", sec)
        S.reuse.stamp(clip, S.talk_sig(by[n], sec, st / f"c{n:02d}.png"))
        ck(f"그 컷 영상을 제자리에 놓으면 빈 컷에서 빠진다 (컷{n})",
           n not in S.talk_gaps(doc))
        clip.unlink()
        ck("영상을 도로 치우면 다시 빈 컷이 된다", n in S.talk_gaps(doc))
        S.TALK_VIDEO = False
        ck("'전부 그림' 으로 고른 것은 고장이 아니다 (빈손을 돌려준다)",
           S.talk_gaps(doc) == [])
    finally:
        S.OUT, S.TALK_VIDEO = real_out, real_tv

    print("\n■ ② 조립이 **다 안 됐으면 다 됐다고 하지 않는가**")
    fn = (ROOT / "src" / "short90.py").read_text("utf-8")
    body = fn.split("\ndef build(")[1].split("\ndef ")[0]
    ck("조립 끝에서 빈 컷을 센다", "talk_gaps(doc)" in body)
    tail = body.split("talk_gaps(doc)")[1]
    ck("빈 컷이 있으면 **성공으로 끝내지 않는다**",
       "return 1" in tail.split("return 0")[0])
    ck("'다 됐다' 는 빈 컷을 센 **뒤에** 찍는다",
       "다 됐다" in tail)
    ck("만든 것을 버리지 않는다고 알려 준다", "그대로 보관" in tail)

    print("\n■ ③ 상태 파일에 **어느 컷이 비었는지** 적는가")
    import os
    real = shortstate.FILE
    sp = d / "shorts.json"
    os.environ["VT_SHORTS_STATE"] = str(sp)
    shortstate.FILE = sp
    assert shortstate.FILE != real, "시험이 진짜 상태 파일을 건드릴 뻔했다"
    try:
        shortstate.mark_made("TEST", 1, 44.0, [15, 16])
        row = json.loads(sp.read_text("utf-8")) if sp.exists() else {}
    finally:
        shortstate.FILE = real
    got = (((row.get("TEST") or {}).get("parts") or {}).get("1") or {})
    ck("빈 컷 번호가 상태 파일에 남는다", got.get("talk_gaps") == [15, 16])
    ck("조립이 그것을 넘겨 준다 (mark_made 에 gaps)",
       "mark_made(doc.get(\"sid\") or \"S90\", part[\"no\"], got, gaps)" in fn)

    print("\n■ ④ **올리기가 막는가** (되돌릴 수 없는 자리다)")
    up = (ROOT / "src" / "upload.py").read_text("utf-8")
    ck("올리기가 빈 컷을 본다", 'get("talk_gaps")' in up)
    ck("빈 컷이 있으면 올리지 않는다 (return 2)",
       "return 2" in up.split('get("talk_gaps")')[1].split("was = shortstate")[0])
    ck("60초 벽과 **같은 자리**에서 막는다 (올리기 직전)",
       up.index('get("talk_gaps")') > up.index("MAX_SHORT_SEC")
       and up.index('get("talk_gaps")') < up.index("was = shortstate.uploaded"))
    ck("그래도 올릴 길은 남겨 둔다 (--gap-ok)", "--gap-ok" in up)

    print("\n■ ⑤ 화면에도 **덜 됐다고 뜨는가**")
    #    화면에 안 뜨면 손님은 "만들어짐 44초" 만 보고 다 된 줄 아신다.
    w = (ROOT / "admin" / "worker.js").read_text("utf-8")
    ck("화면이 빈 컷을 본다", "p.talk_gaps" in w)
    ck("상태 줄에 '덜 됨' 이 붙는다", "' · 덜 됨'" in w)
    ck("어느 컷이 비었는지 번호로 알려 준다",
       "아직 덜 됐습니다" in w and "gaps.map" in w)

    shutil.rmtree(d, ignore_errors=True)
    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 덜 된 편 막기: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 덜 된 편 막기: 덜 됐으면 실패로 끝나고 · 적히고 · 못 올라간다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
