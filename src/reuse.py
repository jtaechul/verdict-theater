#!/usr/bin/env python3
"""⭐ **만들어 둔 것을 다시 쓸 때** 지켜야 할 규칙 — 한 곳에 모은다 (2026-08-27 신설).

왜 생겼나 (같은 사고가 세 번 났다)
    돈이 나가는 것(인물 카드·컷 그림·컷 영상)은 한 번 만들면 보관해 두고
    다음 실행에서 다시 쓴다. 그 판단이 여태 **"파일이 있으면 건너뛴다"** 였다.
    그러면 **무엇으로 만든 것인지**를 안 보므로, 지시문을 고쳐도 옛것이 그대로
    나온다.

      2026-08-26 손님: "그림체는 실사로 가기로 했는데 영상 끝부분에는 일부러
                        애니메이션풍으로 바꾼거야?"
      → 아니다. 화풍을 실사로 바꿨는데 본처·남편·내연녀 카드가 그림체 시절
        것으로 다시 쓰였다(딸·변호사만 새로 그려졌다). 그 카드를 참조로 컷
        그림을 그리니 실사 지시문과 그림체 그림이 섞였고, 그 사이를 이은
        영상이 앞은 실사, 뒤는 그림체가 됐다.

규칙 (예외 없다)
    다시 쓸 수 있는 것 옆에는 **무엇으로 만들었는지(지문)** 를 적어 둔다.
    지문이 같으면 그대로 쓰고(값 0원), 다르거나 없으면 다시 만든다.
    지문에는 **그것을 만들 때 쓴 것 전부**를 넣는다 — 지시문뿐 아니라
    참조로 넣은 그림 파일의 속내용까지. 재료가 바뀌면 결과도 바뀌어야 한다.

⚠️ 새로 "이미 있으면 건너뛴다" 를 쓰고 싶어지면 여기 can_reuse 를 쓴다.
   tools/pair_check.py 가 날것 건너뛰기를 찾아내 빨간불을 켠다.
"""

import hashlib
from pathlib import Path

# 이보다 작으면 만들다 만 찌꺼기로 본다 (빈 파일·오류 응답)
MIN_BYTES = 10_000


def sig_of(*parts):
    """지문 한 줄. 글자는 글자대로, 파일은 **속내용**으로 섞는다.

    파일 이름이 아니라 속내용을 넣는 것이 핵심이다 — 인물 카드는 이름이
    그대로인 채로 그림만 바뀌기 때문이다."""
    h = hashlib.sha1()
    for p in parts:
        if isinstance(p, Path):
            h.update(p.read_bytes() if p.exists() else b"<none>")
        else:
            h.update(str(p).encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:16]


def sig_file(out):
    """지문을 적어 두는 자리 (그림 옆에 같은 이름으로 둔다)."""
    return Path(out).with_suffix(".sig")


def can_reuse(out, sig):
    """그대로 다시 써도 되는가. (된다/안 된다, 왜) 를 돌려준다."""
    out = Path(out)
    if not out.exists() or out.stat().st_size <= MIN_BYTES:
        return False, ""
    f = sig_file(out)
    old = f.read_text(encoding="utf-8").strip() if f.exists() else ""
    if old == sig:
        return True, "그대로다"
    return False, "만든 재료가 바뀌었다" if old else "지문이 없다 — 옛것이다"


def by_hand(out):
    """손님이 손으로 올려 둔 것인가 (옆에 .hand 표시가 있는가).

    ⭐ 2026-08-27 — 손님이 제미나이에서 인물 그림을 직접 만들어 눈으로 고르셨다.
       시스템이 다시 그리면 **고르신 얼굴이 아닌 사람**이 나온다. 표시가 있으면
       지문을 따지지 않고 그대로 쓴다."""
    return Path(out).with_suffix(".hand").exists()


def stamp(out, sig):
    """다 만든 뒤 지문을 적어 둔다. 이걸 빼먹으면 매번 다시 만든다."""
    f = sig_file(out)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(sig, encoding="utf-8")
