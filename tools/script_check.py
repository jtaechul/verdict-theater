#!/usr/bin/env python3
"""저장된 대본 파일이 규격에 맞는가 — **손님이 실제로 복사해 가는 그 글**을 본다.

    python3 tools/script_check.py              data/series/S*.json 을 전부 본다
    python3 tools/script_check.py --selftest   검사기가 진짜 잡는지 스스로 시험

⭐⭐⭐ 왜 이 검사가 생겼나 (2026-08-25)
    자체 점검이 스물 몇 가지를 돌리는데, 그중 **저장된 대본 파일(S001.json)을
    규격 검사에 넣는 것이 하나도 없었다.** 규격 검사는 '새로 만들 때' 만 돌았다.
    그래서 이런 일이 생겼다 —
      · 대본 만드는 도구가 AUDIO 줄을 제 나름대로 고쳐 썼다
      · 규격 검사기는 그 문장을 모르니 "AUDIO 줄이 없다" 로 걸렸을 것이다
      · 그런데 아무도 저장된 파일을 검사하지 않아서 **깃허브는 초록불**이었다
      · 손님은 그 컷을 그대로 복사해 루미나에 넣을 뻔했다
    관리자 페이지는 이 파일을 저장소에서 그대로 읽어 보여 준다. 즉 이 파일이
    곧 손님이 쓰는 물건이다. **물건 자체를 검사한다.**
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import series as S                                           # noqa: E402


def split(res):
    """check() 가 (버릴 것, 알릴 것) 을 주든 목록 하나를 주든 똑같이 받는다."""
    if isinstance(res, tuple):
        return list(res[0]), list(res[1]) if len(res) > 1 else []
    return list(res or []), []


def selftest():
    """⚠️ 잡지도 못하면서 초록불만 켜는 검사가 제일 위험하다."""
    p = ROOT / "data" / "series" / "S001.json"
    doc = json.loads(p.read_text(encoding="utf-8"))
    bad, _ = split(S.check(doc))
    assert not bad, f"멀쩡한 대본을 걸었다: {bad[:3]}"

    # AUDIO 줄을 일부러 망가뜨리면 잡아야 한다 (이번에 실제로 난 고장)
    broke = json.loads(json.dumps(doc))
    c = broke["episodes"][0]["cuts"][0]
    c["prompt"] = "\n".join(
        ("AUDIO: 아무 말이나" if l.startswith("AUDIO:") else l)
        for l in c["prompt"].split("\n"))
    bad, _ = split(S.check(broke))
    assert any("AUDIO" in b for b in bad), "망가진 AUDIO 줄을 못 잡는다"

    # KEEP 줄을 지우면 잡아야 한다
    broke = json.loads(json.dumps(doc))
    c = broke["episodes"][0]["cuts"][0]
    c["prompt"] = c["prompt"].rsplit("\n", 1)[0]
    bad, _ = split(S.check(broke))
    assert bad, "KEEP 줄이 사라진 것을 못 잡는다"
    print("   ✅ 자기시험: 망가진 AUDIO 줄 · 사라진 KEEP 줄을 잡는다")


def main():
    print("⭐ 저장된 대본 규격 검사 (값 0원)\n")
    if "--selftest" in sys.argv:
        selftest()
        return 0
    selftest()
    fails = 0
    for p in sorted((ROOT / "data" / "series").glob("S*.json")):
        doc = json.loads(p.read_text(encoding="utf-8"))
        # ⚠️ 2026-08-27 — 90초 한 편(S90.json)은 **16화 규격이 아니다.** 컷을
        #    화로 묶지 않고 23컷이 한 줄로 이어진다. 16화 자를 들이대면
        #    "화 수가 0개다" 로 걸린다. 90초 편은 tools/short90_test.py 가 본다.
        if not (doc.get("episodes") or []):
            n = len(doc.get("cuts") or [])
            print(f"\n{p.stem} — 90초 한 편 {n}컷 "
                  f"(16화 규격이 아니라 여기서는 안 본다 — short90_test 가 본다)")
            continue
        bad, soft = split(S.check(doc))
        eps = doc.get("episodes") or []
        cuts = sum(len(e.get("cuts") or []) for e in eps)
        print(f"\n{p.stem} — {len(eps)}화 {cuts}컷 · "
              f"등장인물 {len(doc.get('characters') or [])}명")
        if bad:
            fails += len(bad)
            for b in bad:
                print("   ❌ " + b)
        else:
            print("   ✅ 컷 프롬프트가 전부 규격대로다 "
                  "(머리말·11줄·AUDIO·색·이어짐·KEEP)")
            print("   ✅ 옷·생김새를 적은 곳이 없다 (루미나 기준 사진과 안 싸운다)")
            print("   ✅ 루미나 안전 검사에 걸릴 낱말이 없다")
        for b in soft:
            print("   ·  " + b)
    print("\n" + "─" * 60)
    if fails:
        print(f"❌ 저장된 대본: {fails}군데 규격 밖 — 고치고 다시")
        return 1
    print("✅ 저장된 대본: 전부 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
