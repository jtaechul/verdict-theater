#!/usr/bin/env python3
"""회상 시점 자막 규칙을 검사한다. 값 0원 · 인터넷 없이 돈다.

    python3 tools/timelabel_test.py

왜 (2026-08-09 손님 지적)
    화면 위에 '아버지 생전' 이라고 떠 있는데 인물은 지금 나이 그대로였다.
    젊은 시절 그림이 없으니 시대를 못 박는 자막을 쓰면 안 된다.
    그 규칙(`src/timelabel.py`)이 앞으로도 살아 있는지 여기서 지킨다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import timelabel as TL  # noqa: E402

FAIL = []


def eq(got, want, what):
    if got != want:
        FAIL.append(f"{what}: 기대 {want!r} · 실제 {got!r}")
        print(f"  ✗ {what}: 기대 {want!r} · 실제 {got!r}")
    else:
        print(f"  ✓ {what}")


DOC = {"characters": [
    {"code": "F50A", "name": "이정임", "age": 72},
    {"code": "M50A", "name": "김성일", "age": 50},
    {"code": "M50B", "name": "김성훈", "age": 48},
]}


def cut(label, code=None, speaker="narrator"):
    c = {"flashback": True, "flashback_label": label, "speaker": speaker}
    if code:
        c["chars"] = [{"code": code, "pose": "bust_neutral"}]
    return c


print("\n[1] 시대를 못 박는 말은 막는다 (손님이 실제로 본 것들)")
for bad in ("아버지 생전", "살아생전", "오십 년 전", "사십 년 전", "십수 년 전",
            "20년 전", "몇 해 전", "어린 시절", "어릴 적", "형제가 자라던 때",
            "학창 시절", "젊었을 때", "신혼 시절", "그해 겨울", "옛날",
            "스무 살 때", "결혼 전"):
    eq(TL.is_safe(bad), False, f"'{bad}' 는 막힌다")

print("\n[2] '누구누구 시점' 은 쓸 수 있다 (손님이 괜찮다고 하신 형태)")
for good in ("이정임 씨의 기억", "김성일 씨의 기억", "김성훈 씨 시점",
             "이정임 씨의 회상", "지난 일"):
    eq(TL.is_safe(good), True, f"'{good}' 는 쓸 수 있다")

print("\n[3] 비어 있으면 문제 삼지 않는다 (다른 검사가 본다)")
eq(TL.is_safe(""), True, "빈 자막")
eq(TL.is_safe(None), True, "자막 없음")

print("\n[4] 어긋난 자막은 그 컷 인물의 기억으로 바뀐다")
eq(TL.safe_label(cut("아버지 생전", "M50A"), DOC), "김성일 씨의 기억", "A1-08 · A2-09")
eq(TL.safe_label(cut("오십 년 전", "F50A"), DOC), "이정임 씨의 기억", "A1-01")
eq(TL.safe_label(cut("형제가 자라던 때", "M50B"), DOC), "김성훈 씨의 기억", "A1-15")

print("\n[5] 멀쩡한 자막은 손대지 않는다")
eq(TL.safe_label(cut("이정임 씨의 기억", "F50A"), DOC), "이정임 씨의 기억", "그대로 둔다")
eq(TL.safe_label(cut("", "F50A"), DOC), "", "빈 것은 빈 채로")

print("\n[6] 누구인지 못 찾으면 '지난 일' 로 둔다 (틀린 말을 내보내지 않는다)")
eq(TL.safe_label(cut("아버지 생전"), DOC), "지난 일", "화면에 인물이 없을 때")
eq(TL.safe_label(cut("아버지 생전", "XXXX"), DOC), "지난 일", "명단에 없는 인물")

print("\n[7] 인물이 둘이면 말하는 사람의 기억으로 본다")
c = {"flashback": True, "flashback_label": "아버지 생전", "speaker": "v_M50B",
     "chars": [{"code": "M50A"}, {"code": "M50B"}]}
eq(TL.safe_label(c, DOC), "김성훈 씨의 기억", "말하는 사람(차남) 기준")

print("\n[8] 걸린 낱말을 정확히 짚어 준다 (고칠 사람이 알아보게)")
eq(TL.era_claim("아버지 생전"), "생전", "'생전' 을 짚는다")
eq(TL.era_claim("오십 년 전"), "오십 년 전", "햇수를 짚는다")
eq(TL.era_claim("이정임 씨의 기억"), None, "멀쩡하면 없다")

print("\n[9] 대본 검사가 이 규칙을 쓰고 있는가")
import validate_script as V  # noqa: E402
eq(hasattr(V, "TL"), True, "validate_script 가 timelabel 을 쓴다")

print("\n[10] 그리기 직전 한 번 더 거르는가 (render.fix_time_labels)")
try:
    import render as R  # noqa: E402
    eq(callable(getattr(R, "fix_time_labels", None)), True, "fix_time_labels 가 있다")
    d = {"characters": DOC["characters"],
         "acts": [{"cuts": [cut("아버지 생전", "M50A")]}]}
    R.fix_time_labels(d)
    eq(d["acts"][0]["cuts"][0]["flashback_label"], "김성일 씨의 기억", "실제로 바뀐다")
except ImportError as e:
    print(f"  (건너뜀 — {e})")

print()
if FAIL:
    print(f"❌ {len(FAIL)}가지 틀렸습니다")
    for f in FAIL:
        print("   -", f)
    sys.exit(1)
print("✅ 회상 시점 자막 규칙 모두 통과")
