#!/usr/bin/env python3
"""⭐ 해설 통 높이 '마무리'가 검사기를 반드시 통과시키는지 재현한다. 0원.

    python3 tools/voice_settle_test.py

왜 (2026-08-15 — 영상 만들기 네 번째 실패)
    통 맞추기는 "폭 4.1반음" 이라며 끝났는데 검사기는 "5.0반음" 이라며 막았다.
    ① 맞춘 **뒤에** 소리를 또 바꾸는 단계가 있었고 ② 둘의 계산법이 달랐다.
    고친 뒤에는 [마무리(settle) → 검사기] 가 **같은 함수**로 재므로,
    마무리가 닫으면 검사기는 반드시 통과해야 한다 — 여기서 그걸 **가짜 음성**으로
    실제로 돌려 본다. 그날의 실측 높이(74·86·99Hz)를 그대로 재현한다.

무엇을 확인하나
    1. 그날과 같은 통 배치(74/86/99Hz)면 검사기가 **막는다** (재현 성공)
    2. settle_narrator 가 0원으로 닫는다 (폭 ≤ 4.5반음)
    3. 닫은 뒤 검사기가 **통과한다** (잣대가 하나라는 증명)
    4. 한 번 더 돌리면 "손댈 것 없음" (몇 번을 돌려도 안전)
    5. ±2반음으로 못 닫는 폭(10반음)은 여전히 **막고**, 두 번 불려도
       옮김 장부 덕에 **이동이 쌓이지 않는다** (±4반음 금지)
    6. 쇼츠 대본도 실제로 재진다 (예전엔 acts 칸이 없어 한 컷도 안 재고 통과)

⚠️ ffmpeg 와 numpy 가 없으면 '안 해 봄' 이라고 크게 적는다 — '통과' 라 부르지 않는다.
"""
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

FAIL = []


def bad(msg):
    FAIL.append(msg)
    print(f"   ❌ {msg}")


def tone(path, hz, sec=2.0):
    """해당 높이의 순음(사인파) mp3 — measure_f0 가 그대로 읽는다(실측 확인)."""
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"sine=frequency={hz}:duration={sec}",
         "-af", "volume=0.35", "-ar", "24000", "-b:a", "160k", str(path)],
        check=True, timeout=60)


def build(vdir, plan):
    """plan = {통이름: (높이Hz, [컷id...])} → 음성 파일 + 이름표(groups.json)."""
    vdir.mkdir(parents=True, exist_ok=True)
    gmap = {}
    for sig, (hz, cids) in plan.items():
        for cid in cids:
            tone(vdir / f"{cid}.mp3", hz)
            gmap[cid] = sig
    (vdir / "groups.json").write_text(json.dumps(gmap), encoding="utf-8")
    return gmap


def script_for(path, cids, shorts_cids=None):
    """검사기가 읽을 최소 대본(+쇼츠 대본)을 만든다."""
    doc = {"acts": [{"cuts": [
        {"id": c, "speaker": "narrator", "text": "시험 문장입니다.", "sec": 2}
        for c in cids]}]}
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    if shorts_cids is not None:
        sh = {"shorts": [{"cuts": [
            {"id": c, "speaker": "narrator", "text": "시험 문장입니다.", "sec": 2}
            for c in shorts_cids]}]}
        path.with_suffix(".shorts.json").write_text(
            json.dumps(sh, ensure_ascii=False), encoding="utf-8")


def guard(script, vdir, shorts=False):
    """진짜 voiceguard 를 그대로 돌린다. (rc, 출력)"""
    cmd = [sys.executable, str(ROOT / "src" / "voiceguard.py"), str(script),
           "--voice", str(vdir)]
    if shorts:
        cmd.append("--shorts")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return r.returncode, r.stdout + r.stderr


def main():
    if not shutil.which("ffmpeg"):
        print("⚠️ ffmpeg 가 없어 **재지 못했습니다.** '통과' 가 아니라 '안 해 봄' 입니다.")
        return 0
    try:
        import numpy  # noqa: F401
    except ImportError:
        print("⚠️ numpy 가 없어 **재지 못했습니다.** '통과' 가 아니라 '안 해 봄' 입니다.")
        return 0

    from tts import settle_narrator

    print("⭐ 해설 통 높이 마무리 ↔ 검사기 — 한 잣대 재현 시험")
    tmp = Path(tempfile.mkdtemp(prefix="settle_test_"))
    try:
        # ── 1~4. 그날의 실측(74/86/99Hz) 재현 ─────────────────────
        vdir = tmp / "voice"
        plan = {"gA": (74, [f"A{i:02d}" for i in range(1, 6)]),
                "gB": (86, [f"B{i:02d}" for i in range(1, 6)]),
                "gC": (99, [f"C{i:02d}" for i in range(1, 6)])}
        gmap = build(vdir, plan)
        cids = [c for _, (___, cs) in sorted(plan.items()) for c in cs]
        cuts = [{"id": c, "speaker": "narrator", "text": "시험 문장입니다.", "sec": 2}
                for c in cids]
        sp = tmp / "EPTEST.json"
        script_for(sp, cids)

        rc, _out = guard(sp, vdir)
        want = 12.0 * math.log2(99 / 74)
        if rc == 1:
            print(f"   ✅ 재현: 통 74/86/99Hz(폭 {want:.1f}반음)를 검사기가 막는다")
        else:
            bad(f"재현 실패: 그날의 배치를 검사기가 안 막는다 (rc={rc})")

        left = settle_narrator(vdir, cuts, gmap)
        if left is not None and left <= 4.5:
            print(f"   ✅ 마무리가 0원으로 닫았다 (폭 {left:.1f}반음 ≤ 4.5)")
        else:
            bad(f"마무리가 못 닫았다 (폭 {left})")

        rc, out = guard(sp, vdir)
        if rc == 0:
            print("   ✅ 닫은 뒤 검사기 통과 — 잣대가 하나다")
        else:
            bad(f"닫았는데 검사기가 또 막는다 (rc={rc}) — 잣대가 갈라졌다\n{out[-400:]}")

        left2 = settle_narrator(vdir, cuts, gmap)
        if left2 is not None and abs(left2 - left) < 0.6:
            print(f"   ✅ 한 번 더 돌려도 안전 (폭 {left2:.1f}반음)")
        else:
            bad(f"두 번째 마무리에서 폭이 변한다 ({left:.1f} → {left2})")

        # ── 5. 못 닫는 폭(10반음)은 정직하게 막고, 이동이 쌓이지 않는가 ──
        vdir2 = tmp / "voice2"
        hi = round(74 * 2 ** (10 / 12.0))          # 74Hz 에서 10반음 위
        plan2 = {"gA": (74, [f"D{i:02d}" for i in range(1, 6)]),
                 "gB": (hi, [f"E{i:02d}" for i in range(1, 6)])}
        gmap2 = build(vdir2, plan2)
        cids2 = [f"D{i:02d}" for i in range(1, 6)] + [f"E{i:02d}" for i in range(1, 6)]
        cuts2 = [{"id": c, "speaker": "narrator", "text": "시험 문장입니다.", "sec": 2}
                 for c in cids2]
        sp2 = tmp / "EPWIDE.json"
        script_for(sp2, cids2)
        led = {}
        s1 = settle_narrator(vdir2, cuts2, gmap2, ledger=led)  # ±2씩 옮겨도 못 닫는다
        rc, _out = guard(sp2, vdir2)
        if rc == 1:
            print("   ✅ 10반음짜리는 마무리 뒤에도 막는다 (억지로 옮겨 망치지 않는다)")
        else:
            bad(f"10반음짜리가 통과했다 (rc={rc}) — 망가진 소리가 방송으로 간다")
        # 같은 실행에서 마무리가 또 불려도(다시 읽기 실패 뒤) **이동이 쌓이면 안 된다.**
        # 장부 없이는 ±2 + ±2 = ±4반음이 되어 '기괴한 소리'(2026-08-06)가 재발한다.
        s2 = settle_narrator(vdir2, cuts2, gmap2, ledger=led)
        if s2 is not None and s2 > 5.0:
            print(f"   ✅ 두 번 불려도 누적 한도가 지켜진다 (폭 {s1:.1f} → {s2:.1f}반음, 더 안 옮김)")
        else:
            bad(f"두 번째 마무리가 한도를 넘겨 또 옮겼다 (폭 {s1} → {s2}) — ±4반음 위험")

        # ── 6. 쇼츠 대본을 실제로 재는가 ─────────────────────────
        vdir3 = tmp / "voice3"
        plan3 = {"gA": (74, [f"S1-{i:02d}" for i in range(1, 6)]),
                 "gB": (99, [f"S2-{i:02d}" for i in range(1, 6)])}
        build(vdir3, plan3)
        cids_m = [f"M{i:02d}" for i in range(1, 6)]
        for c in cids_m:
            tone(vdir3 / f"{c}.mp3", 86)           # 본편은 멀쩡
        gm = json.loads((vdir3 / "groups.json").read_text(encoding="utf-8"))
        gm.update({c: "gM" for c in cids_m})
        (vdir3 / "groups.json").write_text(json.dumps(gm), encoding="utf-8")
        sp3 = tmp / "EPSHORT.json"
        script_for(sp3, cids_m,
                   shorts_cids=[c for _, (___, cs) in sorted(plan3.items()) for c in cs])
        rc, out = guard(sp3, vdir3, shorts=True)
        if rc == 1 and "[쇼츠]" in out:
            print("   ✅ 쇼츠 대본을 실제로 재고, 흩어졌으면 막는다"
                  " (예전엔 한 컷도 안 재고 통과)")
        else:
            bad(f"쇼츠 검사가 여전히 비어 있다 (rc={rc}, '[쇼츠]' 표시 {'있음' if '[쇼츠]' in out else '없음'})")

        # 잣대 함수가 한 곳(tts)에만 있는지 — 검사기가 제 계산을 몰래 들고 있으면 안 된다
        vg = (ROOT / "src" / "voiceguard.py").read_text(encoding="utf-8")
        if "narrator_take_stats" in vg and "from tts import" in vg.replace("\n", " "):
            print("   ✅ 검사기가 tts 의 잣대 함수를 가져다 쓴다 (계산법 한 곳)")
        else:
            bad("검사기가 잣대를 따로 들고 있다 — 또 갈라진다")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("─" * 52)
    if FAIL:
        print(f"❌ 통 높이 마무리 시험: {len(FAIL)}가지 실패")
        return 1
    print("✅ 통 높이 마무리 시험: 전부 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
