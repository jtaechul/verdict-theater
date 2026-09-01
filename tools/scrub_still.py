#!/usr/bin/env python3
"""컷 그림에서 **가리기로 정한 자리**를 흐리게 만든다 (값 0원).

    python3 tools/scrub_still.py build/s90/stills

무엇을 왜
    그림 모델이 실제로 있는 상표를 그려 넣을 때가 있다. 2026-08-31 에
    컷13 서류에 **하나은행 로고와 이름**이 그대로 나왔다. 실제 은행이므로
    내보내면 안 된다.

⚠️ 왜 영상이 아니라 **그림**에 거는가
    컷13은 카메라가 다가가는 컷이라 로고가 화면에서 커지고 옮겨진다.
    영상에 고정 사각형(ffmpeg delogo)을 걸면 못 따라가서, 처음엔 맞아도
    끝에 가면 엉뚱한 데를 문지른다. 그림에 걸면 자국이 그림에 붙어 **함께
    움직인다** — 따라갈 필요가 아예 없다.

⚠️ 왜 까맣게 덮지 않고 흐리게 하는가
    문서 클로즈업이다. 검은 네모는 "가렸다" 가 눈에 보이지만, 흐림은
    **초점이 안 맞은 것**처럼 보여 화면이 안 깨진다.

⚠️ 엉뚱한 자리를 문지르지 않게
    가릴 자리에 **글자다운 무늬가 실제로 있는지** 먼저 본다. 밋밋하면
    "그림이 바뀐 것 같다" 고 크게 알린다 — 그림을 다시 그리면 로고 자리가
    달라지는데, 옛 자리를 그대로 문지르면 상표는 그대로 남기 때문이다.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
SERIES = ROOT / "data" / "series"
BLUR = 26                 # 흐림 세기 (글자가 완전히 풀릴 만큼)
FEATHER = 18              # 가장자리를 부드럽게 (네모 자국이 안 보이게)


def busy(im, box):
    """이 자리에 글자다운 무늬가 있는가 — 밝기 차이로 본다."""
    g = im.crop(box).convert("L")
    px = list(g.getdata())
    if not px:
        return 0.0
    m = sum(px) / len(px)
    return (sum((p - m) ** 2 for p in px) / len(px)) ** 0.5


def scrub(out, doc=None, sid="S90"):
    """정해 둔 자리를 흐리게 만든다. short90.stills() 가 부른다.

    ⚠️⚠️ 2026-09-01 — 가릴 자리를 **대본의 그 컷 안**에서 읽는다.
       예전에는 따로 둔 파일(S90.scrub.json)에 컷 번호로 적어 두었는데,
       편을 나누며 앞머리 나레이션이 끼어들어 번호가 하나씩 밀렸다.
       13번은 조문 장면이 되었고, 그대로 두었으면 **엉뚱한 컷을 문지르고
       은행 로고는 그대로 나갈** 뻔했다. 컷에 붙여 두면 컷이 어디로 밀려도
       자리가 함께 따라간다.
    """
    out = Path(out)
    if doc is None:
        f = SERIES / f"{sid}.json"
        if not f.exists():
            print("■ 가릴 자리가 정해진 것이 없다")
            return 0
        doc = json.loads(f.read_text(encoding="utf-8"))
    todo = [{"n": c["n"], **c["scrub"]}
            for c in (doc.get("cuts") or []) if c.get("scrub")]
    if not todo:
        print("■ 가릴 자리가 정해진 것이 없다")
        return 0
    print(f"■ 상표 가리기 {len(todo)}자리")
    for c in todo:
        n = int(c["n"])
        f = out / f"c{n:02d}.png"
        if not f.exists():
            print(f"  ⚠️ 컷{n} 그림이 없다 — 건너뛴다")
            continue
        mark = f.with_suffix(".scrubbed")
        if mark.exists() and mark.read_text(encoding="utf-8").strip() == str(c["box"]):
            print(f"  컷{n} (이미 가렸다 — 그대로 둔다)")
            continue
        # ⚠️ 그림이 아닌 파일(받다 만 것·시험용 가짜)을 만나도 **죽지 않는다.**
        #    여기서 죽으면 그림값을 다 치르고도 영상을 못 만든다.
        try:
            im = Image.open(f).convert("RGB")
        except Exception as e:                               # noqa: BLE001
            print(f"  ⚠️ 컷{n} 그림을 못 읽었다 ({str(e)[:60]}) — 건너뛴다")
            continue
        W, H = im.size
        x1, y1, x2, y2 = c["box"]
        box = (int(x1 * W), int(y1 * H), int(x2 * W), int(y2 * H))
        rough = busy(im, box)
        # 흐리게 만든 판을 만들고, 그 자리만 부드러운 가장자리로 얹는다
        blur = im.filter(ImageFilter.GaussianBlur(BLUR))
        m = Image.new("L", (W, H), 0)
        m.paste(255, box)
        m = m.filter(ImageFilter.GaussianBlur(FEATHER))
        im = Image.composite(blur, im, m)
        im.save(f)
        mark.write_text(str(c["box"]), encoding="utf-8")
        print(f"  컷{n} 가렸다 — {c.get('why', '')}  (자리 {box})")
        if rough < 12:
            print(f"     ⚠️⚠️ 그 자리가 밋밋했다(무늬 {rough:.0f}). 그림이 바뀌어"
                  f" 상표가 **다른 자리**로 갔을 수 있다 — 눈으로 확인하십시오")
    return 0


def main():
    return scrub(sys.argv[1] if len(sys.argv) > 1 else "build/s90/stills")


if __name__ == "__main__":
    raise SystemExit(main())
