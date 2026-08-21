#!/usr/bin/env python3
"""⭐ 지금 **어느 길로** 목소리를 부르는지 한 줄로 알려 준다. (값 1원 미만)

    python3 tools/voice_route.py

왜 (2026-08-21)
    같은 제미나이 목소리를 두 길로 부를 수 있는데, 소리는 같아도
    **한도가 하늘과 땅 차이**다 —
      AI 스튜디오 길   무료 등급 하루 10번 (한 화도 못 만든다)
      구글 클라우드 길  하루 횟수 제한 없음
    어느 쪽으로 가고 있는지 모르면 왜 갑자기 안 되는지 알 수가 없다.

⚠️ 이 글을 워크플로 안에 heredoc(<<PY … PY)으로 적었다가 **아무것도 안 찍히고
   조용히 넘어갔다.** YAML 안에서는 끝나는 표시(PY)도 들여쓰기가 되는데,
   heredoc 의 끝 표시는 맨 왼쪽 칸에 있어야 하기 때문이다.
   → 워크플로 안에 파이썬을 박지 말고 **파일로 둔다.**
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import tts as T                                             # noqa: E402


def note(line):
    f = os.environ.get("GITHUB_STEP_SUMMARY")
    if f:
        with open(f, "a", encoding="utf-8") as h:
            h.write(line + "\n")


route = T.route_note()
cloud = T.cloud_gem_ready()

print("⭐ 지금 목소리를 부르는 길\n")
print(f"   길      : {route}")
print(f"   말투 결 : {T.style_of()['name']}")
print(f"   목소리  : 여자 {T.best_voices('FEMALE')[0]} · "
      f"남자 {T.best_voices('MALE')[0]}")
print()
if cloud:
    print("   ✅ 하루 횟수 제한이 없는 길이다 — 16화를 통째로 만들 수 있다")
else:
    print("   ⚠️ 무료 등급 길이라 **하루 10번**뿐이다 — 한 화도 못 만든다")
    print("      구글 클라우드 콘솔에서 Vertex AI API"
          "(aiplatform.googleapis.com) 를 [사용] 하면 풀린다")

# ⚠️ --strict 를 주면 **무제한 길이 아닐 때 1 을 돌려준다.**
#    까닭: 실행 화면의 긴 글은 뒤쪽만 잘려 보일 때가 있어, 정작 이 한 줄을
#    못 읽는 일이 있었다. 단계의 성공/실패 자체를 신호로 쓰면 언제나 읽힌다.
#    (워크플로에서는 continue-on-error 로 달아 두므로 점검을 막지는 않는다)
if "--strict" in sys.argv and not cloud:
    note("- ⚠️ 아직 하루 10번짜리 길입니다 (Vertex AI API 를 켜면 풀립니다)")
    sys.exit(1)

note(f"- 목소리 길: {route}")
note(f"- 말투 결: {T.style_of()['name']} "
     f"(여자 {T.best_voices('FEMALE')[0]} · 남자 {T.best_voices('MALE')[0]})")
