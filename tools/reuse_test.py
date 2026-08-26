#!/usr/bin/env python3
"""**만들어 둔 것을 다시 쓰는 규칙**이 진짜로 도는지 (0원 · 인터넷 0회 · 1초)

    python3 tools/reuse_test.py

⚠️⚠️ 왜 이 시험이 생겼나 (2026-08-26 손님)
    "그림체는 실사로 가기로 했는데 영상 끝부분에는 일부러 애니메이션풍으로
     바꾼거야?"

    아니다. 화풍을 실사로 바꿨는데 **본처·남편·내연녀 카드가 그림체 시절
    것으로 다시 쓰였다**(그날 새로 그려진 것은 딸·변호사뿐이었다 — 장부에
    그렇게 찍혀 있다). 그 그림체 카드를 참조로 컷 그림을 그리니 실사 지시문과
    그림체 그림이 섞였고, 그 둘 사이를 이은 영상이 앞뒤로 화풍이 갈렸다.

    짝 검사(pair_check)는 **코드 생김새**를 본다. 이 시험은 **실제로 돌려서**
    본다 — 그림을 만드는 자리를 가짜로 바꿔치기해 돈 한 푼 안 쓰고,
    재료가 바뀌었을 때 정말 다시 만드는지 센다.

무엇을 확인하나
    ① 아무것도 안 바뀌면 다시 안 만든다 (돈이 안 나간다)
    ② 인물 설명이 바뀌면 **카드**를 다시 만든다
    ③ 카드 그림이 바뀌면 그 카드로 그린 **컷 그림**도 다시 그린다  ← 이번 사고
    ④ 컷 그림이 바뀌면 그 그림으로 만든 **컷 영상**도 다시 만든다
"""
import hashlib
import json
import pathlib
import shutil
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import still as ST                                           # noqa: E402
import veo as VEO                                            # noqa: E402

BIG = b"x" * 40_000        # '만들다 만 찌꺼기' 로 안 보일 만큼 큰 가짜 파일


def fake_still(made):
    def gen(prompt, out, refs=(), ratio="16:9", size=None, seed=None, label=""):
        out.parent.mkdir(parents=True, exist_ok=True)
        # 지시문·참조가 바뀌면 그림도 달라진다 — 실제와 같게 만든다.
        # ⚠️ 참조 그림은 **속내용 전체**를 섞어야 한다. 처음에 앞 80바이트만
        #    썼더니 가짜 그림들의 앞부분이 다 같아서, 카드가 바뀌어도 컷 그림이
        #    안 바뀌는 시늉이 됐다 (시험이 스스로를 속인 셈이다).
        mix = [hashlib.sha1(pathlib.Path(r).read_bytes()).hexdigest() for r in refs]
        out.write_bytes(BIG + str((prompt, mix)).encode())
        made.append(out.name)
        return 0.0
    return gen


def fake_clip(made):
    def make_clip(prompt, sec, out, ratio="16:9", seed=None, start=None, end=None):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(BIG)
        made.append(out.name)
        return 0.0
    return make_clip


def run(tmp, doc_path, sid="S001", no=1):
    """카드 → 컷 그림 → 컷 영상을 한 바퀴 돌리고, 새로 만든 것 이름을 돌려준다."""
    made = []
    ST.gen, VEO.make_clip = fake_still(made), fake_clip(made)
    ST.ROOT = VEO.ROOT = doc_path
    ST.cards(sid, tmp / "cards")
    ST.scenes(sid, no, tmp / "cards", tmp / "stills", only_cut=1)
    VEO.episode(sid, no, tmp / "cuts", only_cut=1, stills=tmp / "stills")
    return made


def main():
    print("⭐ 다시 쓰기 시험 — 재료가 바뀌면 정말 다시 만드는가 (값 0원)\n")
    src = json.loads((ROOT / "data" / "series" / "S001.json").read_text(encoding="utf-8"))
    src["episodes"] = [e for e in src["episodes"] if int(e["no"]) == 1]
    src["episodes"][0]["cuts"] = src["episodes"][0]["cuts"][:1]

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        home = tmp / "repo"
        (home / "data" / "series").mkdir(parents=True)

        def put(d):
            (home / "data" / "series" / "S001.json").write_text(
                json.dumps(d, ensure_ascii=False), encoding="utf-8")

        put(src)
        first = run(tmp, home)
        assert first, "첫 바퀴에 아무것도 안 만들었다"
        print(f"   첫 바퀴: {len(first)}개 만들었다 — {', '.join(first)}")

        # ① 아무것도 안 바뀌면 다시 안 만든다
        again = run(tmp, home)
        assert not again, f"안 바뀌었는데 또 만들었다 (돈이 샌다): {again}"
        print("   ✅ 아무것도 안 바뀌면 다시 안 만든다 — 값 0원")

        # ②③④ 인물 설명 한 줄을 바꾸면 카드 → 컷 그림 → 컷 영상까지 번져야 한다
        d2 = json.loads(json.dumps(src))
        who = d2["characters"][0]["name"]
        d2["characters"][0]["flow_sheet"] = \
            (d2["characters"][0].get("flow_sheet") or "") + " Now photoreal."
        put(d2)
        after = run(tmp, home)
        assert f"{who}.png" in after, f"인물 설명을 바꿨는데 카드를 안 다시 만든다: {after}"
        assert any(x.startswith("c001") and x.endswith(".png") for x in after), \
            f"카드가 바뀌었는데 컷 그림을 그대로 쓴다 — 이번 사고다: {after}"
        assert "c001.mp4" in after, f"컷 그림이 바뀌었는데 옛 영상을 그대로 쓴다: {after}"
        print(f"   ✅ 인물 한 줄을 고치니 {len(after)}개가 다시 만들어졌다 — "
              f"{', '.join(after)}")
        print("      (카드 → 컷 그림 → 컷 영상까지 번진다)")

        # 다시 한 바퀴 — 이제 또 잠잠해야 한다
        assert not run(tmp, home), "다시 만든 뒤에도 계속 만든다"
        print("   ✅ 다시 만든 뒤에는 또 잠잠하다")

    print("\n" + "─" * 60)
    print("✅ 다시 쓰기 시험: 전부 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
