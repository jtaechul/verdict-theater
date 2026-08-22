#!/usr/bin/env python3
"""wrangler 가 뱉은 글에서 보관함(KV) 번호만 뽑는다.

    npx wrangler kv namespace list   | python3 tools/kv_id.py
    npx wrangler kv namespace create BLOB | python3 tools/kv_id.py

왜 따로 있는가 (2026-08-22)
    ① 워크플로의 실행 칸 안에 파이썬을 직접 적었더니, 파이썬은 들여쓰기가
       규칙인 언어라서 YAML 의 들여쓰기와 부딪혀 파일 전체가 깨졌다.
    ② 파일로 빼면 여기서 **진짜 출력으로 시험**할 수 있다. 실제로 필요했다 —
       처음에 나는 wrangler 가 이름을 "verdict-theater-admin-BLOB" 으로
       지을 줄 알았는데, 4.86 은 그냥 **"BLOB"** 으로 짓는다.
       그래서 만들어 놓고도 못 찾아, 보관함 없이 배포가 지나갔다.

두 가지 글을 다 읽는다
    · list   → JSON 배열 (앞뒤에 안내 문구가 섞여 있어 대괄호 사이만 읽는다)
    · create → 사람이 읽는 글. 그 안에 id = "…" 가 있다.
"""

import json
import re
import sys

# 이름은 wrangler 판마다 다르게 지어진다. 셋 다 받아 준다.
WANT = ("BLOB", "verdict-theater-admin-BLOB")


def pick(raw: str) -> str:
    # ① list 가 준 JSON 배열
    i, j = raw.find("["), raw.rfind("]")
    if i >= 0 and j > i:
        try:
            got = json.loads(raw[i:j + 1])
        except Exception:
            got = None
        if isinstance(got, list):
            for n in got:
                if isinstance(n, dict) and n.get("title") in WANT:
                    return str(n.get("id") or "")
            for n in got:                       # 이름 규칙이 또 바뀌었을 때
                if isinstance(n, dict) and str(n.get("title") or "").endswith("BLOB"):
                    return str(n.get("id") or "")
            return ""
    # ② create 가 준 사람 글: id = "…"
    m = re.search(r'\bid\s*=\s*"([0-9a-fA-F]{32})"', raw)
    return m.group(1) if m else ""


def selftest() -> None:
    """⚠️ 진짜 출력으로 시험한다. 짐작으로 만들었다가 한 번 헛돌았다."""
    # 실제로 wrangler 4.86 이 뱉은 글 (2026-08-22 배포 기록에서 그대로)
    made = (
        ' ⛅️ wrangler 4.86.0\n───────────────────\nResource location: remote \n\n'
        '🌀 Creating namespace with title "BLOB"\n✨ Success!\n'
        'To access your new KV Namespace in your Worker, add the following '
        'snippet to your configuration file:\n'
        '[[kv_namespaces]]\nbinding = "BLOB"\nid = "fd8c9bc19e4d4a3d944e705c013fe05b"\n'
    )
    assert pick(made) == "fd8c9bc19e4d4a3d944e705c013fe05b", "만든 직후 글을 못 읽는다"
    listed = (
        ' ⛅️ wrangler 4.86.0\n[\n'
        ' {"id":"aaaa","title":"something-else"},\n'
        ' {"id":"fd8c9bc19e4d4a3d944e705c013fe05b","title":"BLOB"}\n]\n'
    )
    assert pick(listed) == "fd8c9bc19e4d4a3d944e705c013fe05b", "목록에서 'BLOB' 을 못 찾는다"
    old = '[{"id":"bbbb","title":"verdict-theater-admin-BLOB"}]'
    assert pick(old) == "bbbb", "옛 이름 규칙을 못 읽는다"
    assert pick("아무것도 없음") == "", "없는데 있다고 한다"
    assert pick('[{"id":"cccc","title":"other"}]') == "", "남의 보관함을 우리 것이라 한다"
    print("✅ 자기시험: 만든 직후 글도, 목록도, 옛 이름도 다 읽는다", file=sys.stderr)


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        sys.stdout.write(pick(sys.stdin.read()))
