#!/usr/bin/env python3
"""영상 맨 끝에 **구독 유도 한 컷**을 붙인다. 몇 번 돌려도 결과가 같다.

    python3 tools/add_outro.py data/scripts/EP001.json

왜 맨 끝인가 (손님 선택 2026-08-07)
    대본의 마지막 줄이 이미 질문으로 끝난다 —
      "욕심 때문에 가족이라는 이름마저 버린 사람, 당신의 주변에도 있습니까?"
    그 질문 바로 뒤에 붙이면 흐름이 끊기지 않는다. 그리고 12분을 끝까지 본 사람은
    구독할 마음이 가장 큰 사람이다.
    맨 앞(0~30초)에는 넣지 않는다 — 아직 채널을 모르는데 부탁부터 하면 이탈한다.
    이 채널은 훅이 23초뿐이라 특히 그렇다.

왜 대본에 직접 넣는가
    렌더링에서만 붙이면 **소리가 없다.** 대본에 컷으로 들어가야 음성도 만들어지고,
    대본 검사·자막·길이 계산이 전부 자동으로 따라온다. 특별 취급이 필요 없다.
"""

import json
import sys
from pathlib import Path

# 정중한 존댓말 (손님 선택). 채널 시청자가 50~60대라 '구독 좋아요 알림설정' 식은 안 쓴다.
SUB_LINE = "다음 이야기도 놓치지 않으시려면, 구독 버튼을 눌러 두십시오."
SUB_SEC = 5.0
MARK = "-sub"


def add(doc):
    """붙였으면 True. 이미 있으면 False(아무것도 안 한다)."""
    acts = doc.get("acts") or []
    if not acts or not acts[-1].get("cuts"):
        return False
    last_act = acts[-1]
    cuts = last_act["cuts"]
    if any(str(c.get("id", "")).endswith(MARK) for a in acts for c in a.get("cuts", [])):
        return False

    base = cuts[-1]
    # ⚠️ blackout(막 끝 암전)은 **막의 마지막 컷에만** 있어야 한다(대본 검사 규칙).
    #    새 컷을 뒤에 붙이면 예전 마지막 컷은 더 이상 마지막이 아니다 — 꺼 준다.
    base["blackout"] = False
    c = json.loads(json.dumps(base))       # 배경·분위기를 그대로 이어받는다
    c["id"] = base["id"] + MARK
    c["sec"] = SUB_SEC
    c["text"] = SUB_LINE
    c["speaker"] = "narrator"
    c["chars"] = []                        # 글자만 남긴다. 인물이 있으면 시선이 흩어진다
    c["gfx"] = None
    c["sfx"] = None
    c["blackout"] = True
    c["tag"] = "cta"
    cuts.append(c)

    # 막의 끝 시각과 컷 수도 같이 맞춘다. 안 맞추면 대본 검사에서 걸린다.
    if isinstance(last_act.get("end_sec"), (int, float)):
        last_act["end_sec"] = round(last_act["end_sec"] + SUB_SEC, 1)
    meta = doc.get("meta") or {}
    if isinstance(meta.get("cut_count"), int):
        meta["cut_count"] = sum(len(a.get("cuts", [])) for a in acts)
    for k in ("duration_sec", "total_sec", "runtime_sec"):
        if isinstance(meta.get(k), (int, float)):
            meta[k] = round(meta[k] + SUB_SEC, 1)
    return True


def main():
    if len(sys.argv) < 2:
        print("쓰는 법: python3 tools/add_outro.py data/scripts/EP001.json")
        return 2
    p = Path(sys.argv[1])
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not add(doc):
        print("구독 유도 컷이 이미 있다 — 그대로 둔다")
        return 0
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    last = doc["acts"][-1]["cuts"][-1]
    print(f"구독 유도 컷을 붙였다: {last['id']} ({SUB_SEC:.0f}초)")
    print(f"  \"{SUB_LINE}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
