#!/usr/bin/env python3
"""prompts/*.md 에서 실제로 모델에게 보낼 본문만 잘라낸다.

각 프롬프트 파일은 이렇게 생겼다.

    ## 이 파일 사용법 (운영자용 메모 — 모델에게 보내지 않는다)
    ...
    <!-- PROMPT:BEGIN -->
    ...실제 본문...
    <!-- PROMPT:END -->

바깥쪽은 사람이 읽는 메모다. 사이만 잘라서 보낸다.
마커가 정확히 한 쌍이 아니면 즉시 오류를 낸다 — 엉뚱한 텍스트를 모델에 보내는 것보다
멈추는 편이 낫다.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "prompts"

BEGIN = "<!-- PROMPT:BEGIN -->"
END = "<!-- PROMPT:END -->"


class PromptError(RuntimeError):
    pass


def load(name):
    """prompts/{name}.md 의 본문을 돌려준다."""
    path = PROMPTS / f"{name}.md"
    if not path.exists():
        raise PromptError(f"프롬프트 파일이 없다: {path}")
    text = path.read_text(encoding="utf-8")

    nb, ne = text.count(BEGIN), text.count(END)
    if nb != 1 or ne != 1:
        raise PromptError(
            f"{path.name}: 잘라내기 표시가 {nb}쌍/{ne}쌍이다. 정확히 한 쌍이어야 한다."
        )
    body = text.split(BEGIN, 1)[1].split(END, 1)[0].strip()
    if len(body) < 500:
        raise PromptError(f"{path.name}: 본문이 {len(body)}자뿐이다. 잘못 잘렸을 수 있다.")
    return body


def fill(body, **values):
    """{{KEY}} 자리에 값을 끼워 넣는다. 남은 자리가 있으면 오류."""
    for k, v in values.items():
        body = body.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{([A-Z_]+)\}\}", body)
    if left:
        raise PromptError(f"채우지 못한 자리가 남았다: {sorted(set(left))}")
    return body


def build(name, **values):
    return fill(load(name), **values)


if __name__ == "__main__":
    for n in ["drama_gate", "script_gen", "script_eval", "shorts_gen", "script_revise"]:
        try:
            b = load(n)
            slots = sorted(set(re.findall(r"\{\{([A-Z_]+)\}\}", b)))
            print(f"{n:15s} {len(b):6,}자  채울 자리: {slots or '없음'}")
        except PromptError as e:
            print(f"{n:15s} ❌ {e}")
