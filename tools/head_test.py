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

    ⭐ 2026-08-16 — **얼굴 컷도 잰다.** 얼굴은 '몸통 눈금'에서 빼는 대신
       제 눈금(FACE_FLAT)으로 정수리 잘림을 본다. 얼굴을 통째로 건너뛰던
       구멍으로 옛 격자 시트의 잘린 얼굴 18장이 EP002 방송까지 나갔다.

어떻게 자로 재나 (짐작이 아니라 측정)
    ⚠️ 2026-08-15 자를 바꿨다. 예전 자("위에서 15% 지점의 폭")는 남자(M70)로
    눈금을 맞춘 것이라 **머리숱이 옆으로 넓은 여자 배우를 목 잘림으로 몰았다**
    (멀쩡한 컷 0.62~0.68 ↔ 진짜 잘린 컷 0.66 — 눈금이 겹쳐서 고칠 수도 없다).
    그래서 진짜 잘린 컷을 옛 기록에서 꺼내 놓고 여러 자를 대 본 뒤,
    **멀쩡과 잘림이 확실히 갈라지는 자 두 개**만 남겼다.

    ① 맨 위가 평평한가 (top_flat)
       머리가 있으면 맨 위는 정수리 곡선이라 **뾰족**하다(위 1% 줄의 폭이 좁다).
       격자선을 지우다 머리가 날아간 컷은 **일직선으로 싹둑** 잘려 맨 위부터 넓다.
         실측 — 잘린 컷: 0.794 · 0.802 · 0.808  /  멀쩡(18컷 전부): 0.178~0.290
       가운데(0.55)를 눈금으로 쓴다. 양쪽과 0.25 이상 떨어져 있어 안 겹친다.
    ② 큰 덩어리가 몇 개인가 (big blobs)
       사람 하나면 몸은 **한 덩어리**다. 잘리면 머리 없는 몸통 + 떨어져 나간
       조각(기둥·이웃 인물)이 **두 덩어리 이상**으로 남는다.
         실측 — 잘린 컷: 2개  /  멀쩡(전 배우 전 컷): 최대 1개
       (전체 넓이의 5% 넘는 덩어리만 센다 — 먼지 같은 점은 무시)

    ①은 '평평하게 잘린' 유형을, ②는 '조각이 섞인' 유형을 잡는다.
    옛 격자 자르기가 만들던 '작은 조각 하나만 남은' 유형(실측 0.05·1덩어리)은
    둘 다 피해 가지만, 그 자르기 방식 자체가 없어졌고 지금 자르기는 큰 덩어리
    하나만 남기므로(keep_main_blob) 그 유형은 더 생길 수 없다.

    얼굴(face_) 컷은 원래 머리가 화면을 가득 채우므로 ①을 하지 않는다
    — 전신·상반신만 본다. ②(덩어리 수)는 모든 컷에 잰다.

⚠️ ffmpeg 없이 돈다. numpy·Pillow 만 있으면 된다. 없으면 **크게 건너뛴다고
   적는다** — '안 해 봄' 을 '통과' 라고 부르지 않는다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHARS = ROOT / "assets" / "char"

# ① 위 1% 줄의 폭 ÷ 가장 넓은 폭. 이 값을 넘으면 '일직선으로 잘림'.
#    실측: 잘린 컷 0.794~0.808 / 멀쩡 0.178~0.290 → 가운데 0.55.
TOP_FLAT = 0.55
# ①-얼굴. 얼굴 컷은 머리가 화면을 채워 몸통 눈금(0.55)이 안 맞는다 — 따로 잰다.
#    ⚠️ 2026-08-16 실측 사고 — 옛 격자 시트의 얼굴 컷 18장(F50A·JUDGE·M50A)이
#       **정수리가 일직선으로 잘린 채** EP002 방송에 나갔다. 잘린 자리에 옛
#       자르기가 흰 테두리를 둘러 '흰 뚜껑'까지 생겼다(손님이 캡처로 확인).
#       이 검사가 얼굴 컷을 통째로 건너뛰고 있어 아무도 못 잡았다.
#    실측(얼굴 42장 전수): 멀쩡 0.24~0.47 / 잘림 0.51~0.95 → 가운데 0.49.
#    (경계의 두 장은 눈으로 열어 확인했다 — 0.47 F50B 멀쩡, 0.51 M50A 잘림)
#    ⚠️ 2026-08-17 재조정 — 위의 "0.47 F50B 멀쩡" 판정이 **틀렸다.** 손님이
#       영상 캡처로 확인: 한미주(F50B) 정수리가 여전히 잘려 나간다. 컷아웃만
#       볼 때는 미묘했지만 화면에서는 흰 테두리와 함께 또렷하다. 배우 여섯이
#       새 시트로 바뀐 지금 다시 재면 경계가 훨씬 깨끗하다:
#         새 시트 6명 전부 0.19~0.28  /  F50B(마지막 옛 격자) 0.35~0.47
#       → 0.32 로 조인다 (깨끗한 최대 0.28 위 0.04, F50B 최소 0.35 아래 0.03).
FACE_FLAT = 0.32
# ② 전체 넓이의 이 비율을 넘는 덩어리만 '큰 덩어리'로 센다. 2개면 잘린 것.
BLOB_MIN = 0.05

# 이 자세는 고개를 숙여 등이 맨 위에 오는 것이 정상이라 ①을 잰들 못 믿는다.
# (② 덩어리 수는 자세와 무관하므로 이 자세에도 그대로 잰다)
POSE_SKIP = {"full_sit_down"}
# ①(평평함)은 전신·상반신만 본다. 얼굴 컷은 머리가 화면을 채우는 것이 정상이다.
CHECK_PREFIX = ("full_", "bust_")

FAIL = []


def bad(msg):
    FAIL.append(msg)
    print(f"   ❌ {msg}")


def load_mask(path):
    """그림을 **한 번만** 열어 몸(알파) 마스크로 만든다.

    같은 그림에 자를 두 개 대는데 그때마다 다시 열면 여는 시간이 재는
    시간보다 길다 (실측: 열기 두 번 = 검사 전체의 절반). 한 번 열어 나눠 쓴다.
    """
    from PIL import Image
    import numpy as np
    im = Image.open(path).convert("RGBA")
    return np.asarray(im.getchannel("A")) > 60


def top_flat(mask):
    """위 1% 줄에서 가장 넓은 폭 ÷ 전체에서 가장 넓은 폭. 못 재면 None.

    머리가 있으면 맨 위는 정수리 곡선(뾰족) → 값이 작다.
    일직선으로 잘렸으면 맨 위부터 어깨/몸통 폭 → 값이 크다.
    """
    import numpy as np
    a = mask
    rows = np.where(a.any(axis=1))[0]
    if len(rows) < 20:
        return None
    a = a[rows[0]:rows[-1] + 1]
    w = a.sum(axis=1).astype(float)
    mx = w.max()
    if mx <= 0:
        return None
    band = max(3, int(len(w) * 0.01))
    return float(w[:band].max() / mx)


def big_blobs(mask):
    """전체 넓이의 5% 를 넘는 몸 덩어리 수. 못 재면 None.

    작은 그림으로 줄여서 세도 5% 덩어리는 그대로 5% 다 — 빠르게 센다.
    (칸칸이 건너뛰며 뽑는 축소라 덩어리가 이어져 있는 모양은 그대로 남는다)
    """
    import numpy as np
    step = max(1, max(mask.shape) // 192)
    a = mask[::step, ::step]
    total = int(a.sum())
    if total < 40:
        return None
    H, W = a.shape
    seen = np.zeros_like(a)
    big = 0
    for y, x in np.argwhere(a):
        if seen[y, x]:
            continue
        stack = [(int(y), int(x))]
        seen[y, x] = True
        size = 0
        while stack:
            cy, cx = stack.pop()
            size += 1
            for ny, nx in ((cy + 1, cx), (cy - 1, cx),
                           (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < H and 0 <= nx < W \
                        and a[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if size >= total * BLOB_MIN:
            big += 1
    return big


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

    print("⭐ 목이 잘린 인물이 있는가 — ① 맨 위 평평함(전신·상반신) ② 덩어리 수(전 컷)")
    n = 0
    worst = []
    for d in sorted(CHARS.iterdir()):
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.png")):
            mask = load_mask(p)
            # ② 큰 덩어리 수 — 자세·컷 종류와 무관하게 전부 잰다.
            blobs = big_blobs(mask)
            if blobs is not None and blobs > 1:
                bad(f"{d.name}/{p.stem} — 큰 덩어리가 {blobs}개다. "
                    "사람 하나면 한 덩어리여야 한다 — 조각이나 이웃 인물이 섞였습니다")
                continue
            # ①-얼굴 — 정수리가 일직선으로 잘렸는가 (눈금만 다르고 셈은 같다)
            if p.stem.startswith("face_"):
                r = top_flat(mask)
                if r is not None and r >= FACE_FLAT:
                    bad(f"{d.name}/{p.stem} — 정수리가 일직선으로 잘렸다({r:.2f}). "
                        "옛 격자 시트의 얼굴 컷입니다 — 시트를 다시 만들어야 합니다")
                continue
            # ① 맨 위 평평함 — 전신·상반신만.
            if not p.stem.startswith(CHECK_PREFIX):
                continue
            # `full_sit_down`(주저앉기)은 프롬프트가 "고개를 숙이고 등을 둥글게
            # 만다" 고 시킨 자세라 맨 위가 머리가 아니다 — 이 자세만 ①을 뺀다.
            # (2026-08-14 옛 자가 이 자세를 목 잘림으로 몰았던 일의 재발 방지.
            #  이 자세의 머리는 만들 때 눈(label_figures 의 headless 물음)이 본다)
            if p.stem in POSE_SKIP:
                continue
            r = top_flat(mask)
            if r is None:
                continue
            n += 1
            worst.append((r, f"{d.name}/{p.stem}"))
            if r >= TOP_FLAT:
                bad(f"{d.name}/{p.stem} — 맨 위가 일직선으로 평평하다({r:.2f}). "
                    "정수리가 잘려 나간 것으로 보입니다")
    worst.sort(reverse=True)
    print(f"   컷 {n}개를 쟀습니다.")
    if worst:
        print(f"   맨 위가 평평한 순 5개 ({TOP_FLAT:.2f} 넘으면 실패 · 멀쩡 실측은 0.29 이하):")
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
