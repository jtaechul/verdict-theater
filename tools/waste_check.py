#!/usr/bin/env python3
"""⭐⭐⭐ **이미 만든 것을 다시 만들지 않는가** (값이 새는 자리). 0원 · 인터넷 0회.

    python3 tools/waste_check.py

⭐⭐⭐ 2026-09-10 손님: **"이미 제작된 영상이나 이미지 중에 제대로 제작된
   부분들은 다시 제작되지 않도록 하여 토큰이나 비용이 낭비되지 않도록."**

재활용(src/reuse.py)은 2026-08-27 부터 돌고 있었다. 그런데 감사해 보니
**값이 새는 자리가 셋** 있었다 —

  ① 보관(릴리스)이 **조용히** 실패했다.
     워크플로가 `put ... || true` 로 감싸고 있어, 못 올려도 초록불이었다.
     보관이 한 번 실패하면 다음 실행에서 그림 38장(약 5,000원)과 대사 영상
     (컷마다 706~941원)을 **처음부터 전부** 다시 만든다. 그런데 화면에는
     아무 차이가 없어 몇 번이고 되풀이될 수 있었다.
  ② **한 번 실행 한도가 대사 영상에만 없었다.**
     still.py 에도 veo.py 에도 있는 한도(3,000원)가, 가장 비싼 자리인
     short90.talkers 에만 없었다. 대사 컷 14개면 12,900원이 한 번에 나간다.
  ③ **얼마를 아꼈는지 아무도 안 적었다.**
     그래서 ①이 일어나도 눈으로 알 길이 없었다.

여기서 보는 것 — 위 셋이 다시 뚫리지 않는가.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import reuse                                                 # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def main():
    print("⭐ 이미 만든 것을 다시 만들지 않는가 (값 0원)\n")
    s9 = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
    rf = (ROOT / "tools" / "release_file.py").read_text(encoding="utf-8")
    yml = (ROOT / ".github" / "workflows" / "short90.yml").read_text(encoding="utf-8")

    print("① 보관이 진짜 됐는지 확인하는가")
    ck("올린 뒤 되읽어 크기를 견준다",
       re.search(r'back = release\(tag\)[\s\S]{0,300}int\(got\.get\("size"\)', rf)
       is not None, "확인 안 하면 조용히 날아가고 다음에 값을 또 쓴다")
    ck("보관 실패는 0이 아닌 값으로 알린다",
       re.search(r"보관 실패[\s\S]{0,400}return 3", rf) is not None)
    ck("실패했을 때 **무엇이 다시 나가는지** 값으로 적어 준다",
       "132원" in rf and "941원" in rf)
    silent = [ln.strip() for ln in yml.splitlines()
              if "release_file.py put" in ln and "|| true" in ln]
    ck("워크플로가 보관 실패를 `|| true` 로 삼키지 않는다",
       not silent, f"{len(silent)}군데가 조용히 넘어간다")
    warn = [ln for ln in yml.splitlines()
            if "release_file.py put" in ln and "::warning::" in ln]
    ck(f"보관하는 자리마다 경고가 붙어 있다 ({len(warn)}군데)", len(warn) >= 5)

    print("\n② 한 번 실행 한도가 **값이 나가는 자리 전부**에 걸려 있는가")
    # ⚠️ 자리 목록을 손으로 적지 않는다 — 소스에서 **돈 쓰는 함수**를 찾는다.
    #    새로 값 나가는 갈래가 생기면 한도를 달기 전까지 여기서 걸린다.
    paid = []
    for m in re.finditer(r"\ndef (\w+)\(doc\):", s9):
        nxt = s9.find("\ndef ", m.end())
        body = s9[m.start():nxt if nxt > 0 else len(s9)]
        if "veo.make_clip(" in body:          # **영상**을 사는 갈래만 본다
            paid.append((m.group(1), body))
    ck(f"영상을 사는 갈래를 찾았다 ({', '.join(n for n, _ in paid)})", len(paid) >= 2,
       "못 찾으면 이 시험은 아무것도 안 잰다")
    # ⚠️ 한도는 **부르는 쪽**이 아니라 값이 나가는 자리(still.gen · veo.make_clip)
    #    에 박혀 있어야 한다. 부르는 쪽마다 달면 새 갈래가 생길 때 잊는다
    #    (실제로 openers·talkers 두 갈래가 모두 뚫려 있었다).
    st = (ROOT / "src" / "still.py").read_text(encoding="utf-8")
    ve = (ROOT / "src" / "veo.py").read_text(encoding="utf-8")
    ck("그림 만드는 자리(still.gen)에 한도가 박혀 있다",
       re.search(r"_spent\[.krw.\] \+ krw > cost\.RUN_KRW", st) is not None)
    ck("영상 만드는 자리(veo.make_clip)에 한도가 박혀 있다",
       re.search(r"def make_clip[\s\S]{0,1200}?_spent\[.krw.\] \+ krw > cost\.RUN_KRW",
                 ve) is not None,
       "부르는 쪽에만 달면 새 갈래가 생길 때 잊는다")
    ck("영상값을 진짜로 쌓는다 (안 쌓으면 한도가 안 걸린다)",
       re.search(r'_spent\["krw"\] \+= krw', ve) is not None)
    for name, body in paid:
        ck(f"{name}() 이 한도에 닿으면 **그림으로 안 떨어뜨리고** 멈춘다",
           "RunCapReached" in body,
           "값이 모자라 멈춘 것을 고장으로 보면 그 컷이 조용히 그림이 된다")
    ck("한도에 닿으면 만든 것은 남기고 멈춘다",
       "만든" in s9 and "그대로 남는다" in s9)

    print("\n③ 아낀 값을 눈에 보이게 적는가")
    ck("장부가 있다 (reuse.note · reuse.book_flush)",
       hasattr(reuse, "note") and hasattr(reuse, "book_flush"))
    ck("컷 그림이 장부에 적는다", 'reuse.note("컷 그림"' in s9)
    ck("대사 영상이 장부에 적는다", 'reuse.note("대사 영상"' in s9)
    ck("실행 끝에 장부를 찍는다", "reuse.book_flush(SID)" in s9)
    # 아낀 값이 0이면 보관이 죽었다는 뜻 — 그것을 말로 알려야 한다
    src = (ROOT / "src" / "reuse.py").read_text(encoding="utf-8")
    ck("하나도 못 쓰면 '보관이 안 되고 있다' 고 알려 준다",
       "하나도 못 쓰고 전부 새로" in src,
       "값이 새는 것을 눈으로 알 길이 있어야 한다")

    print("\n③ -2 장부가 진짜로 셈하는가 (글이 아니라 돌려 본다)")
    reuse._BOOK.clear()
    reuse.note("컷 그림", 37, 1, 132)
    saved = reuse.book_flush("시험")
    ck(f"아낀 값을 맞게 센다 (37장 x 132원 = {37 * 132:,}원)",
       abs(saved - 37 * 132) < 1, f"{saved}")
    ck("찍고 나면 장부를 비운다", not reuse._BOOK)

    print("\n④ 다시 쓸 판단이 **지문**으로 이루어지는가 (파일 있으면 건너뛰기 금지)")
    for kind, pat in (("컷 그림", r'sig = reuse\.sig_of\(c\["still"\], \*refs\)'),
                      ("대사 영상", r"sig = reuse\.sig_of\(prompt, str\(sec\)"),
                      ("목소리", r"sig = reuse\.sig_of\(\*\[f\"\{w\}\|")):
        ck(f"{kind}: 만든 재료로 지문을 만든다",
           re.search(pat, s9) is not None)
    ck("대사 영상 지문에 **그 컷 그림**이 들어간다 (image-to-video 라서)",
       re.search(r"sig = reuse\.sig_of\(prompt, str\(sec\)[\s\S]{0,200}still\.read_bytes",
                 s9) is not None,
       "그림이 바뀌면 영상도 바뀌어야 한다")
    ck("이름이 밀려도 다시 안 만든다 (salvage)",
       s9.count("salvage(") >= 3)

    print("\n⑤ 앞 단계를 건너뛴 실행에서도 만들어 둔 것을 받아 오는가")
    for t in ("stills", "voice", "open", "talk"):
        ck(f"조립 단계가 {t} 를 받아 온다",
           re.search(rf"for T in [^\n]*{t}", yml) is not None
           or re.search(rf'get "{t}-\$S"', yml) is not None)

    print("\n⑥ 한 번에 다 안 될 때 **몇 번 눌러야 하는지** 미리 알리는가")
    # ⚠️ 한도(3,000원) 때문에 대사 영상은 한 번에 다 안 만들어질 수 있다.
    #    그것을 안 알리면 손님은 "왜 몇 개만 됐지" 하고 다시 누르는데,
    #    다시 누르는 것이 **정답**이라는 것을 알아야 한다(만든 것은 0원).
    import talkplan as TP                                    # noqa: E402
    doc = {"parts": [{"no": 1, "cuts": [1, 9], "card": ["가", "나"],
                      "yt_title": "제" * 30}],
           "cuts": [{"n": i + 1, "who": [] if i in (0, 8) else ["아내"],
                     "turns": [["나레이션" if i in (0, 8) else "아내", "가" * 26]],
                     "say": ["담담하게"], "scene": "a lamp lights an empty chair"}
                    for i in range(9)]}
    pl = TP.plan(doc)
    ck("셈에 '몇 번 눌러야 하는지'가 들어 있다",
       "presses" in pl and "cap" in pl, str(sorted(pl)))
    ck("한 번에 안 되면 2번 이상이라고 센다",
       pl["krw"] <= pl["cap"] or pl["presses"] >= 2,
       f"{pl['krw']:,}원인데 {pl['presses']}번이라고 한다")
    js = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
    ck("화면이 그것을 말로 적어 준다", "번 눌러야 다 만들어집니다" in js)
    ck("두 번째부터는 값이 더 안 든다고 알려 준다",
       "값이 더 안 나갑니다" in js)

    print("\n⑦ 실행 뚜껑 셈이 **값 나가는 갈래를 전부** 아는가")
    # ⭐⭐⭐ 2026-09-10 — plan_cost 가 **대사 영상을 몰랐다.**
    #    켜 두고 실행해도 그림값만 잡아서
    #        VEO_CALL_CAP = 6   (대사 컷은 8개인데)
    #        VT_RUN_KRW  = 5,982원  (대사 영상만 6,118원인데)
    #    이 되어, 달 한도를 올려도 **여섯 컷째에서 잘린다.**
    #    손님은 "왜 몇 개만 됐지" 만 보게 된다.
    import importlib                                         # noqa: E402
    pc = importlib.import_module("plan_cost")
    sid = "S92"
    if not (ROOT / "data" / "series" / f"{sid}.json").exists():
        sid = "S90"
    off = pc.plan(sid, False, False)
    on = pc.plan(sid, False, True)
    import talkplan as TP2                                   # noqa: E402
    import json as _json                                     # noqa: E402
    doc = _json.loads((ROOT / "data" / "series" / f"{sid}.json")
                      .read_text(encoding="utf-8"))
    tp = TP2.plan(doc)
    ck("대사 영상을 켜면 뚜껑이 그만큼 커진다",
       on["run_krw"] > off["run_krw"] + tp["krw"] * 0.8,
       f"끔 {off['run_krw']:,} → 켬 {on['run_krw']:,} (대사값 {tp['krw']:,})")
    ck(f"영상 부르는 횟수 뚜껑이 대사 컷 수({tp['n']}개)를 덮는다",
       on["veo_cap"] >= tp["n"], f"뚜껑 {on['veo_cap']}번")
    ck("무슨 영상값인지 이름을 붙여 준다 (대사 장면 / 편 첫 장면)",
       on.get("vid_label") == "대사 장면", str(on.get("vid_label")))
    yml2 = (ROOT / ".github" / "workflows" / "short90.yml").read_text(encoding="utf-8")
    ck("워크플로가 그 스위치를 셈보다 **먼저** 정해 준다",
       yml2.find("VT_TALK_VIDEO") < yml2.find("plan_cost.py"),
       "뒤에 정하면 셈이 꺼진 줄 알고 뚜껑을 낮게 잡는다")

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 값이 새는 자리: {len(bad)}군데")
        for x in bad:
            print(f"     {x}")
        return 1
    print("✅ 값 낭비 막기: 보관을 확인하고 · 한도가 걸리고 · 아낀 값을 적는다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
