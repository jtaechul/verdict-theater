#!/usr/bin/env python3
"""wrangler 가 뱉은 보관함(KV) 목록에서 우리 것의 번호만 뽑는다.

    npx wrangler kv namespace list | python3 tools/kv_id.py

왜 따로 있는가 (2026-08-22)
    워크플로의 실행 칸 안에 파이썬을 직접 적었더니, 파이썬은 들여쓰기가
    규칙인 언어라서 YAML 의 들여쓰기와 부딪혀 파일 전체가 깨졌다.
    파일로 빼면 둘 다 편하고, 여기서 따로 시험도 할 수 있다.

    wrangler 는 앞뒤에 안내 문구를 섞어 뱉는다. 그래서 대괄호 사이만 잘라 읽는다.
"""

import json
import sys

WANT = "verdict-theater-admin-BLOB"


def pick(raw: str) -> str:
    i, j = raw.find("["), raw.rfind("]")
    if i < 0 or j <= i:
        return ""
    try:
        got = json.loads(raw[i:j + 1])
    except Exception:
        return ""
    if not isinstance(got, list):
        return ""
    for n in got:
        if isinstance(n, dict) and n.get("title") == WANT:
            return str(n.get("id") or "")
    # 이름 규칙이 바뀌었을 때를 대비한 두 번째 그물
    for n in got:
        if isinstance(n, dict) and str(n.get("title") or "").endswith("-BLOB"):
            return str(n.get("id") or "")
    return ""


if __name__ == "__main__":
    sys.stdout.write(pick(sys.stdin.read()))
