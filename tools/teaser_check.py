#!/usr/bin/env python3
"""⭐ 미끼 쇼츠(tools/teaser.py) 자체 점검 — 0원 · 열쇠 없이 · 인터넷 0회

    python3 tools/teaser_check.py

보는 것 (2026-10-06 S96 1편을 만들며 실제로 걸렸던 것들)
    ① 대본 검사 — 퀴즈 · "정답은 본편 몇 분 몇 초" 금지 · 대사는 본편 대사와 한 글자도 같게 ·
       나레이션을 입이 움직이는 대사 영상 위에 안 얹는다 · 첫 컷 도장 · 마지막 컷 끊기
    ② 자막 — 금색 말은 한 토막 안에(「12년 / 묵은 편지」 금지) · 금색은 그 말이 든 낱말만
    ③ 대사 소리 — 약한 끝소리(「…어요」)까지 넣는다 (speech_span 문턱은 「요」를 버렸다)
    ④ 말소리 크기 — **감은 뒤에** 재서 맞춘다 (홑소리→두소리 −3dB 로 나레이션이 5dB 작았다)
    ⑤ 박자표 — 첫 화면은 0.0초부터 · 말은 LEAD 초 · 끊은 뒤 까만 화면 → 끝 화면
    ⑥ 지켜 주는 것 — 다음 사건 번호가 미끼 쇼츠 번호를 건너뛴다 · short90/build_short90 이 미끼 쇼츠를 안 만진다
    ⑦ 지금 있는 미끼 쇼츠 대본(data/series/*.json format=teaser)이 대본 검사를 지난다
"""
import array
import copy
import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
os.environ.setdefault("VT_SID", "S96")

import teaser as T                                             # noqa: E402

FAIL = []


def ck(label, cond, extra=""):
    print(("   ✅ " if cond else "   ❌ ") + label + (f"  ({extra})" if extra else ""))
    if not cond:
        FAIL.append(label)


def tone(path, parts):
    """[(초, dB)] 차례로 이어 붙인 사인파 소리 (dB 가 None 이면 무음)."""
    hz = 16000
    a = array.array("h")
    for sec, db in parts:
        amp = 0 if db is None else 32767 * 10 ** (db / 20) * math.sqrt(2)
        for i in range(int(sec * hz)):
            a.append(int(amp * math.sin(2 * math.pi * 220 * i / hz)))
    raw = Path(path).with_suffix(".raw")
    raw.write_bytes(a.tobytes())
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "s16le", "-ar", str(hz), "-ac", "1",
                    "-i", str(raw), str(path)], check=True)
    raw.unlink()
    return Path(path)


def fake_doc():
    """본편(S95) 없이도 도는 작은 대본 둘 — 본편 대본은 임시 자리에 둔다."""
    src = {"sid": "S8001", "cuts": [
        {"n": 1, "kind": "나레이션", "narr": True, "turns": [["나레이션", "본편 나레이션"]]},
        {"n": 2, "kind": "아들", "turns": [["아들", "10년이 지났습니다. 너무 늦으셨어요."]]},
        {"n": 3, "kind": "나레이션", "narr": True, "turns": [["나레이션", "끝 나레이션"]]},
        {"n": 4, "kind": "나레이션", "fig": "chart", "narr": True, "turns": [["나레이션", "그림"]]}]}
    doc = {"sid": "S8002", "format": "teaser", "source": "S8001", "parts": [
        {"no": 1, "cuts": [1, 3], "stamp": ["아버지가", "돌아가시면 내 것"], "head": ["한 줄"],
         "end": ["이 이야기의 끝은", "본편에서"], "end_note": "화면 아래 영상 링크를 눌러 보세요"}],
        "cuts": [
            {"n": 1, "turns": [["나레이션", "살아 계신 아버지 땅 등기부에."]], "clip": 1, "stamp": True},
            {"n": 2, "turns": [["아들", "10년이 지났습니다. 너무 늦으셨어요."]], "clip": 2, "talk": True,
             "tag": "아들"},
            {"n": 3, "turns": [["나레이션", "판결 날, 그 편지가…"]], "clip": 3, "cliff": True}]}
    for c in doc["cuts"]:
        c["text"] = c["turns"][0][1]
    return src, doc


def with_source(src, fn):
    """본편 대본을 잠깐 data/series 에 두고 fn() — 끝나면 지운다."""
    f = T.doc_path(src["sid"])
    f.write_text(json.dumps(src, ensure_ascii=False), encoding="utf-8")
    try:
        return fn()
    finally:
        f.unlink(missing_ok=True)


def main():
    print("⭐ 미끼 쇼츠 점검 (0원)\n")
    src, doc = fake_doc()

    print("■ ① 대본 검사")
    ck("바른 대본은 지난다", with_source(src, lambda: T.check(doc)) == [],
       with_source(src, lambda: T.check(doc)))

    def bad_of(mut):
        d = copy.deepcopy(doc)
        mut(d)
        return " / ".join(with_source(src, lambda: T.check(d)))

    def quiz(d):
        d["cuts"][2]["turns"][0][1] = d["cuts"][2]["text"] = "정답은 본편 4분 12초에"
    ck("퀴즈 · '정답은 본편 몇 분 몇 초' 를 막는다", "퀴즈" in bad_of(quiz))

    def end_time(d):
        d["parts"][0]["end_note"] = "본편 5:38 에서"
    ck("끝 화면 글의 시각 안내(5:38)도 막는다", "시각 안내" in bad_of(end_time))

    def talk_diff(d):
        d["cuts"][1]["turns"][0][1] = d["cuts"][1]["text"] = "10년이 지났어요."
    ck("대사가 본편 대사와 한 글자라도 다르면 막는다 (소리는 본편 그대로다)",
       "본편 컷2 과 다르다" in bad_of(talk_diff))

    def narr_on_talk(d):
        d["cuts"][0]["clip"] = 2
    ck("나레이션을 입이 움직이는 대사 영상 위에 얹으면 막는다", "대사 영상이다" in bad_of(narr_on_talk))

    def fig(d):
        d["cuts"][0]["clip"] = 4
    ck("본편 그림 컷은 안 쓴다 (얼굴 영상만)", "그림 컷" in bad_of(fig))

    def no_cliff(d):
        d["cuts"][2].pop("cliff")
    ck("마지막 컷이 말 한복판에서 안 끊기면 막는다", "cliff" in bad_of(no_cliff))

    def no_stamp(d):
        d["cuts"][0].pop("stamp")
    ck("첫 컷에 도장이 없으면 막는다 (첫 3초)", "도장" in bad_of(no_stamp))

    def no_tag(d):
        d["cuts"][1].pop("tag")
    ck("대사에 이름표가 없으면 막는다", "이름표" in bad_of(no_tag))

    print("\n■ ② 자막 — 금색 말")
    t = "그런데 새엄마가 아들에게 보낸, 12년 묵은 편지 한 통이 있었습니다."
    ch = T.chunks(t, ["12년 묵은 편지"])
    ck("금색 말은 한 토막 안에 둔다 (「12년 / 묵은 편지」 로 안 갈린다)",
       any("12년 묵은 편지" in x for x in ch), ch)
    ck("토막을 이으면 줄과 같다 (글자가 안 샌다)", " ".join(ch) == t)
    ws = "살아 계신 아버지 땅 등기부에, 아들이 올려 둔 말입니다.".split()
    hot = T.hot_words(" ".join(ws), ["등기부"])
    ck("금색은 그 말이 든 낱말만 (앞 낱말까지 번지지 않는다)", [ws[i] for i in sorted(hot)] == ["등기부에,"],
       [ws[i] for i in sorted(hot)])
    ws2 = "그 사이 아들은 그 땅으로 큰 빚까지 졌습니다.".split()
    hot2 = T.hot_words(" ".join(ws2), ["큰 빚"])
    ck("띄어 쓴 금색 말은 걸친 낱말 모두", [ws2[i] for i in sorted(hot2)] == ["큰", "빚까지"],
       [ws2[i] for i in sorted(hot2)])
    wins = T.sub_windows({"c": {"turns": [["나레이션", t]], "gold": ["12년 묵은 편지"]},
                          "at": 1.0, "a": 4.0, "t1": 5.5})
    ck("자막 토막이 말 시작에 뜨고 컷 끝까지 이어진다",
       abs(wins[0][2] - 1.0) < 1e-6 and abs(wins[-1][3] - 5.5) < 1e-6
       and all(abs(wins[i][3] - wins[i + 1][2]) < 1e-6 for i in range(len(wins) - 1)))

    with tempfile.TemporaryDirectory() as td:
        print("\n■ ③ 대사 소리 — 약한 끝소리")
        f = tone(Path(td) / "talk.wav", [(0.10, None), (1.0, -18), (0.30, -34), (0.6, None)])
        beg, fin = T.talk_span(f)
        ck("약한 끝소리(-34dB)까지 넣는다 — 1.40초 뒤에서 끊는다", fin >= 1.40, f"{beg:.2f}~{fin:.2f}초")
        ck("말 앞 숨도 조금 남긴다", beg <= 0.10, f"{beg:.2f}초")

        print("\n■ ④ 말소리 크기 — 감은 뒤에 잰다")
        mono = tone(Path(td) / "narr.wav", [(1.5, -24)])
        st = Path(td) / "st.wav"
        T.run(["ffmpeg", "-y", "-v", "error", "-i", str(mono), "-af",
               f"aresample=48000,aformat=channel_layouts=stereo,{T.S9.tempo_filter(1.28)}", str(st)])
        out = Path(td) / "lv.wav"
        T.level(st, out)
        got = T.mean_db(out)
        ck(f"마지막 모양(두소리 · 1.28배)에서 {T.VOICE_DB:.0f}dB 로 맞는다", abs(got - T.VOICE_DB) < 1.0,
           f"{got:.1f}dB")

    print("\n■ ⑤ 박자표")
    pieces = {1: ("a1.wav", 3.0, 0.0), 2: ("a2.wav", 2.0, 0.1), 3: ("a3.wav", 1.5, 3.0)}
    d2 = copy.deepcopy(doc)
    segs, cliff, end0, total = T.timeline(d2, d2["parts"][0], pieces)
    ck("첫 화면은 0.0초부터 · 첫 말은 LEAD 초", segs[0]["t0"] == 0.0 and abs(segs[0]["at"] - T.LEAD) < 1e-9)
    ck("컷과 컷 사이에 빈 화면이 없다", all(abs(segs[i]["t1"] - segs[i + 1]["t0"]) < 1e-9
                                          for i in range(len(segs) - 1)))
    ck("끊는 컷은 말이 끝나는 순간 끊는다 (뒤 쉼 없음)", abs(cliff - (segs[-1]["at"] + 1.5)) < 1e-9)
    ck("끊은 뒤 까만 화면 → 끝 화면", abs(end0 - cliff - T.CLIFF_BLACK) < 1e-9
       and abs(total - end0 - T.END_SEC) < 1e-9)
    ck("첫 컷 영상은 말보다 LEAD 만큼 먼저 시작한다", abs(segs[0]["src_at"] - (0.0 - T.LEAD)) < 1e-9)
    fx = [n for n, _ in T.fx_list(segs, cliff)]
    ck("도장 '쾅' 과 끊는 순간 판사봉이 있다", "stamp" in fx and "gavel" in fx)
    # 대사로 여는 편(2·3편) — 0.0초부터 그 영상 소리 그대로 (LEAD 를 두면 입이 0.1초 어긋난다)
    d3 = copy.deepcopy(doc)
    d3["cuts"][0].update({"talk": True, "tag": "아들"})
    pieces3 = {1: ("a1.wav", 2.5, 0.0), 2: ("a2.wav", 2.0, 0.1), 3: ("a3.wav", 1.5, 3.0)}
    segs3, _, _, _ = T.timeline(d3, d3["parts"][0], pieces3)
    ck("대사로 여는 편은 첫 말이 0.0초 · 화면도 그 자리 (입이 맞는다)",
       segs3[0]["at"] == 0.0 and segs3[0]["src_at"] == 0.0)
    fx2 = T.fx_list(segs3, 6.0, 1.45)
    ck("첫 도장 효과음이 편마다 정한 때(stamp_at)에 난다", any(n == "stamp" and abs(t - 1.42) < 1e-6 for n, t in fx2))
    d4 = copy.deepcopy(doc)
    d4["cuts"][1]["slam"] = {"lines": ["돌아온 것", "0원"], "at": 0.5}
    segs4, cl4, _, _ = T.timeline(d4, d4["parts"][0], pieces)
    fx4 = [(n, round(t, 2)) for n, t in T.fx_list(segs4, cl4)]
    ck("편 가운데 도장에도 '쾅' 이 난다", ("stamp", round(segs4[1]["at"] + 0.5 - 0.03, 2)) in fx4, fx4)
    ck("가운데 도장 꼴이 틀리면 막는다", bad_of(lambda d: d["cuts"][1].update({"slam": "0원"})) != "")

    print("\n■ ⑤-2 자막 — 문장마다 소리 쉼에 맞춘다")
    seg5 = {"c": {"turns": [["아들", "10년이 지났습니다. 너무 늦으셨어요."]], "gold": []},
            "at": 5.0, "a": 2.6, "t1": 7.8, "voiced": [(0.05, 0.95), (1.55, 2.35)]}
    w5 = T.sub_windows(seg5)
    ck("둘째 문장 자막은 둘째 말 덩어리가 시작할 때 뜬다", abs(w5[1][2] - 6.55) < 1e-6, [(x[2], x[3]) for x in w5])
    ck("마지막 토막은 컷 끝까지", abs(w5[-1][3] - 7.8) < 1e-6)
    seg6 = dict(seg5, voiced=[])
    ck("소리 덩어리를 못 재면 글자 수로 나눈다 (맛보기)", len(T.sub_windows(seg6)) == 2)

    print("\n■ ⑥ 지켜 주는 것")
    import story90 as ST
    probe = T.doc_path("S9989")
    probe.write_text(json.dumps({"sid": "S9989", "format": "teaser"}), encoding="utf-8")
    try:
        ck("다음 사건 번호가 대본(.story) 없는 미끼 쇼츠 번호를 건너뛴다", ST.next_sid() == "S9990",
           ST.next_sid())
    finally:
        probe.unlink(missing_ok=True)
    s9 = (ROOT / "src" / "short90.py").read_text(encoding="utf-8")
    ck("short90 은 미끼 쇼츠를 안 만든다 (관리자 단추로 눌려도 멈춘다)",
       'if str(doc.get("format") or "") == "teaser":' in s9)
    b9 = (ROOT / "tools" / "build_short90.py").read_text(encoding="utf-8")
    ck("build_short90 은 미끼 쇼츠 대본·올릴 글을 안 덮는다", '.get("format") == "teaser"' in b9)
    ck("나레이션은 본편과 같은 성우", T.NARR_VOICE == T.S9.VOICE["나레이션"])

    print("\n■ ⑦ 지금 있는 미끼 쇼츠 대본")
    seen = 0
    for f in sorted((ROOT / "data" / "series").glob("S*.json")):
        if f.name.count(".") > 1:
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("format") != "teaser":
            continue
        seen += 1
        bad = T.check(d)
        ck(f"{f.stem}: 대본 검사를 지난다 (본편 {d.get('source')})", not bad, " / ".join(bad[:3]))
        meta = f.with_name(f"{f.stem}.meta.json")
        if meta.exists():
            import fetch_meta90
            why = fetch_meta90.blocked(json.loads(meta.read_text(encoding="utf-8")))
            ck(f"{f.stem}: 올릴 글이 마지막 문지기를 지난다", not why, " / ".join(why[:2]))
        # ⭐ 2026-10-06 손님 "자막 아래로" — 도장 상자는 자막 아래 · 앱이 덮는 자리(UI_TOP) 위 · 단추 줄을 비킨다
        for p in d.get("parts") or []:
            pics = [("첫 도장", T.stamp_img(p["stamp"]))]
            pics += [(f"컷{c['n']} 가운데 도장", T.stamp_img(c["slam"]["lines"]))
                     for c in T.part_cuts(d, p) if c.get("slam")]
            for what, pic in pics:
                bottom = T.BOX_TOP + pic.height - 18          # 그림자 18px 은 빼고 종이 아랫변
                ck(f"{f.stem} {p['no']}편 {what}: 자막 아래 · 앱이 덮는 자리 위 · 단추 줄 비킴",
                   bottom <= T.UI_TOP and pic.width <= T.BOX_W and T.BOX_TOP > T.SUB_Y,
                   f"아랫변 {bottom} · 너비 {pic.width}")
    print(f"   (미끼 쇼츠 대본 {seen}개)")

    print("\n" + "─" * 56)
    if FAIL:
        print(f"❌ 미끼 쇼츠 점검: {len(FAIL)}개 실패")
        for x in FAIL:
            print(f"   · {x}")
        return 1
    print("✅ 미끼 쇼츠 점검: 전부 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
