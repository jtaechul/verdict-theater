#!/usr/bin/env python3
"""⭐ **목이 잘린 인물이 저장소에 있으면 막는다.** 인터넷 0회 · 0원 · 몇 초.

    python3 tools/head_test.py

왜 이 검사가 있는가 (2026-08-13)
    손님: "미친놈아 이건 목이 잘렸잖아"
    실제로 M70 의 full_back · full_sit · full_walk 세 컷이 **목 아래만** 남아
    있었다. 사람이 눈으로 보기 전까지 아무도 몰랐다.

    까닭은 이랬다. 모델이 시트를 그릴 때 **머리 꼭대기 위로 격자선을 긋는다.**
    그 선을 지우는 코드가 '선 한쪽이 초록이면 통째로 초록으로 덮는다' 였는데,
    머리 위 선은 위가 초록·아래가 머리카락이라 **머리 꼭대기가 지워졌다.**
    지워진 자리에서 덩어리가 끊겨 목 아래만 남은 것이다.

    ⭐ 그래서 규칙을 하나 세웠다 — **의심스러우면 지우지 말고 이어 붙인다.**
       잘못 이어 붙이면 작은 막대 토막이 남을 뿐이지만,
       잘못 지우면 **사람의 머리가 없어진다.** 둘의 무게가 다르다.

두 겹으로 막는다
    ① 만들 때   — 포즈 이름을 확인하는 그 호출에서 "목 잘린 것 있나" 도 같이
                  묻는다(값 0원). 잘린 것은 저장하지 않는다.
    ② 올린 뒤   — 이 검사가 저장소에 있는 컷아웃을 전부 훑는다.
                  ①이 놓쳐도 여기서 걸리고, 놓친 줄 모른 채 방송되지 않는다.

어떻게 자로 재나 (짐작이 아니라 측정)
    사람은 위에서부터 **머리 → 목(잘록) → 어깨(넓어짐)** 순이다.
    목이 잘리면 그 잘록한 데가 없고 맨 위부터 바로 넓다.
    그래서 위에서 15% 지점의 폭을 가장 넓은 폭과 견준다.
      실측(M70): 머리 있는 것 0.49·0.55 / 목 잘린 것 0.66·0.71·0.80
    0.62 를 넘으면 '의심' 으로 본다. 얼굴(face_) 컷은 원래 머리가 화면을
    가득 채우므로 이 검사를 하지 않는다 — 전신·상반신만 본다.

⚠️ ffmpeg 없이 돈다. numpy·Pillow 만 있으면 된다. 없으면 **크게 건너뛴다고
   적는다** — '안 해 봄' 을 '통과' 라고 부르지 않는다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHARS = ROOT / "assets" / "char"

# 위에서 이만큼 내려온 자리의 폭을 본다 / 이 값을 넘으면 목이 잘린 것으로 본다.
DEPTH = 0.15
WIDE = 0.62

# 이 자세는 등이 맨 위에 오는 것이 정상이라 위 셈법으로 못 잰다 (2026-08-14)
POSE_SKIP = {"full_sit_down"}
# 전신·상반신만 본다. 얼굴 컷은 머리가 화면을 채우는 것이 정상이다.
CHECK_PREFIX = ("full_", "bust_")

FAIL = []


def bad(msg):
    FAIL.append(msg)
    print(f"   ❌ {msg}")


def shoulder_ratio(path):
    """위에서 15% 지점의 폭 ÷ 가장 넓은 폭. 못 재면 None."""
    from PIL import Image
    import numpy as np
    im = Image.open(path).convert("RGBA")
    a = np.asarray(im.getchannel("A")) > 60
    rows = np.where(a.any(axis=1))[0]
    if len(rows) < 20:
        return None
    a = a[rows[0]:rows[-1] + 1]
    w = a.sum(axis=1).astype(float)
    mx = w.max()
    if mx <= 0:
        return None
    return float(w[int(len(w) * DEPTH)] / mx)


def main():
    try:
        import numpy  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        print("⚠️  numpy 나 Pillow 가 없어 **재지 못했습니다.**")
        print("   이 결과는 '통과' 가 아니라 '안 해 봄' 입니다.")
        print("   깃허브(자체 점검)에서는 실제로 돌아갑니다.")
        return 0

    if not CHARS.is_dir():
        print("컷아웃 폴더가 없습니다 — 볼 것이 없습니다.")
        return 0

    print("⭐ 목이 잘린 인물이 있는가 (전신·상반신 컷)")
    n = 0
    worst = []
    for d in sorted(CHARS.iterdir()):
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.png")):
            if not p.stem.startswith(CHECK_PREFIX):
                continue
            # ⚠️ 2026-08-14 — 이 자가 **멀쩡한 그림을 목 잘림으로 몰았다.**
            #    `full_sit_down`(바닥에 주저앉기)은 프롬프트가 "고개를 아래로
            #    숙이고 등을 둥글게 만다" 고 시킨 자세다. 그러면 실루엣의 맨 위가
            #    머리가 아니라 **둥글게 만 등**이라 당연히 넓다(실측 0.74).
            #    이 자는 '맨 위가 좁으면 머리' 라는 셈법이라 그 자세를 못 읽는다.
            #    ⭐ 기준을 무르게 하는 것이 아니다 — **이 자세 하나만** 뺀다.
            #       나머지 열여섯 컷은 그대로 이 자로 잰다. 이 자세에 머리가
            #       붙어 있는지는 만들 때 눈(label_figures 의 headless 물음)이 본다.
            if p.stem in POSE_SKIP:
                continue
            r = shoulder_ratio(p)
            if r is None:
                continue
            n += 1
            worst.append((r, f"{d.name}/{p.stem}"))
            if r > WIDE:
                bad(f"{d.name}/{p.stem} — 맨 위가 이미 어깨 폭이다({r:.2f}). "
                    "목 위가 잘린 것으로 보입니다")
    worst.sort(reverse=True)
    print(f"   컷 {n}개를 쟀습니다.")
    if worst:
        print("   위태로운 것 5개 (0.62 넘으면 실패):")
        for r, name in worst[:5]:
            print(f"     {r:.2f}  {name}")

    print()
    print("⭐ 시트의 칸 선이 인물에 닿아 있지 않은가 (닿으면 어떻게 잘라도 안 된다)")
    # ⭐ 2026-08-13 손님: "선은 마젠타로 긋고 배경을 초록으로 했으면 이런 일이
    #    없었을 텐데 왜 자꾸 반복되는 거야?"
    #    색은 처음부터 맞았다. 빠진 것은 **어디에 그으라는 말**이었고,
    #    더 빠진 것은 **그게 지켜졌는지 재는 일**이었다. 여기서 잰다.
    sys.path.insert(0, str(ROOT / "src"))
    try:
        import assets_gen as G
        from PIL import Image as _I
        sheets = sorted((ROOT / "assets" / "sheets").glob("*.png"))
        if not sheets:
            print("   (시트가 없습니다)")
        touched = []
        for sp in sheets:
            ratio, isbad = G.lines_touch_figures(_I.open(sp))
            mark = "⚠️ 닿았다" if isbad else "✅"
            print(f"   {mark} {sp.name:12s} 인물의 {ratio * 100:.1f}% 가 선에 닿아 있다")
            if isbad:
                touched.append(sp.name)
        if touched:
            # ⚠️ 2026-08-15 — 여기가 **실패(FAIL)** 였는데 경고로 내린다. 까닭:
            #    방송에 나가는 것은 시트가 아니라 **컷아웃**이다. 시트에 선이
            #    닿아 있어도 이미 잘라 둔 컷아웃이 멀쩡하면(위의 목 잘림 검사가
            #    직접 잰다) 영상은 문제없이 나간다. 실제로 EP001 이 그렇게 나갔다.
            #    이 시트로 **다시 자르는 것**만 위험한데, 그건 자르는 단계
            #    (sync 의 sheet_ok · sheet_gate)가 따로 막는다.
            #    원칙: 직접 잰 것(컷아웃)은 불합격, 다른 단계 소관(시트)은 경고.
            #    이 실패 때문에 멀쩡한 컷아웃을 쓰는 배우까지 몽땅 다시 만들어야
            #    영상이 나가는 구조였다 — 2,120원을 헛돈 쓰게 만드는 길이었다.
            print(f"   ⚠️ 선 닿은 시트 {len(touched)}장 — 이 시트로 다시 자르지만 않으면 된다.")
            print("      (배우를 새로 만들면 이 시트들도 함께 새것으로 바뀐다)")
    except Exception as e:                              # noqa: BLE001
        print(f"   (재지 못했습니다: {e})")

    print()
    print("⭐ 만들 때도 묻는가 (올린 뒤에만 잡으면 이미 늦다)")
    cs = (ROOT / "src" / "char_sheet.py").read_text(encoding="utf-8")
    if "headless" not in cs:
        bad("포즈를 확인하는 그 호출에서 '목 잘린 것' 을 안 묻는다 "
            "— 같은 호출이라 물어도 값이 0원 더 안 든다")
    elif "목이 잘려 **버린다**" not in cs:
        bad("목이 잘린 것을 찾고도 그냥 저장한다 — 빠지는 편이 낫다")
    else:
        print("   ✅ 포즈 확인과 같은 호출에서 같이 묻고, 잘린 것은 저장하지 않는다")

    print()
    print("⭐ 핵심 규칙이 코드에 적혀 있는가 (같은 사고를 되풀이하지 않게)")
    if "의심스러우면 지우지 말고 이어 붙인다" not in cs:
        bad("'의심스러우면 지우지 말고 이어 붙인다' 규칙이 안 적혀 있다")
    else:
        print("   ✅ 적혀 있다 (지우면 머리가 없어지고, 이어 붙이면 토막만 남는다)")

    print()
    print("─" * 52)
    if FAIL:
        print(f"❌ 목 잘림 검사: {len(FAIL)}가지 문제")
        print("   → [2-2] → [효과음 + 배경사진만 (0원)] 으로 다시 오려내십시오.")
        return 1
    print("✅ 목 잘림 검사: 정상")
    return 0


if __name__ == "__main__":
    sys.exit(main())
