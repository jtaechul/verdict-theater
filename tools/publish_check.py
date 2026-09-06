#!/usr/bin/env python3
"""⭐ **올릴 때 예약 공개가 제대로 걸리는가.** 값 0원 (유튜브를 안 부른다).

    python3 tools/publish_check.py

⭐⭐⭐ 2026-09-06 손님: **"한꺼번에 올리니까 1편은 매번 조회수가 0이잖아."**

   실제 숫자를 뽑아 보니 원인은 "한꺼번에" 가 아니라 **1편만 예약 없이 즉시
   공개**되던 것이었다. 워크플로에 이렇게 박혀 있었다 —

       if [ "$I" -eq 0 ]; then AT=""; else AT="--publish-at …"; fi

   1편은 업로드가 끝나는 그 순간 공개된다. 유튜브가 아직 **고화질 변환을
   못 끝낸 때**다. 그 상태로 공개되면 초기 노출에서 저화질로 서빙되고
   쇼츠 피드 진입이 나빠진다. [한 편만 올리기] 도 같은 고장이 있었다.

   ■ 실측 (판결극장 쇼츠 10건 · 2026-09-06)
       즉시 공개 2건 —   349회 ·     0회
       예약 공개 8건 — 1,212회 ~ 2,946회   (같은 사건 1편 349 vs 2편 2,946)
       아침 8시 4건 평균 1,849 · 오후 1시 3건 1,269 · 저녁 7시반 1건 349

여기서 보는 것 — **워크플로의 그 셸 글을 뽑아 진짜로 돌려 본다.**
   ① 세 편을 올릴 때 **1편에도** 예약이 걸리는가
   ② 한 편만 올릴 때도 걸리는가
   ③ 공개 시각이 **한국 아침 8시**인가 · 하루씩 띄우는가
   ④ 비공개·일부공개를 고르면 예약을 **안** 거는가 (저절로 공개되면 안 된다)
   ⑤ 변환이 끝날 시간을 벌어 두는가 (너무 가까운 예약을 안 잡는다)
"""
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import next_slot as NS                                      # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name
          + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


def run_block(privacy, part, every="24"):
    """워크플로의 올리는 칸을 **그대로 뽑아** 돌린다 (업로드는 흉내만)."""
    y = (ROOT / ".github" / "workflows" / "short90-upload.yml").read_text(
        encoding="utf-8")
    m = re.search(r"          RC=0\n[\s\S]*?\n          exit \$RC", y)
    if not m:
        return None
    blk = "\n".join(l[10:] for l in m.group(0).splitlines())
    d = Path(tempfile.mkdtemp())
    (d / "build" / "s90").mkdir(parents=True)
    for k in (1, 2, 3):
        (d / "build" / "s90" / f"part{k}.mp4").write_text("x")
    (d / "build" / "s90" / "meta.json").write_text("{}")
    (d / "tools").mkdir()
    (d / "tools" / "next_slot.py").write_bytes(
        (ROOT / "tools" / "next_slot.py").read_bytes())
    (d / "src").mkdir()
    (d / "src" / "upload.py").write_text(
        "import sys\nprint('UP ' + ' '.join(sys.argv[1:]))\n")
    sh = f'P={privacy}\nPART={part}\nDRY=""\nS=S91\nEVERY={every}\n' + blk
    r = subprocess.run(["bash", "-c", sh], cwd=d, capture_output=True, text=True)
    out = []
    for line in r.stdout.splitlines():
        if not line.startswith("UP "):
            continue
        no = (re.search(r"--part (\S+)", line) or [None, "?"])[1]
        at = re.search(r"--publish-at (\S+)", line)
        out.append((no, at.group(1) if at else None))
    return out


def kst(z):
    return (datetime.strptime(z, "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=timezone.utc).astimezone(NS.KST))


def main():
    print("⭐ 올릴 때 예약 공개 (값 0원 — 유튜브를 안 부른다)\n")

    print("① 세 편을 올릴 때 — **1편에도** 예약이 걸리는가")
    got = run_block("public", "all")
    ck("올리는 칸을 워크플로에서 뽑아 돌렸다", got and len(got) == 3, str(got))
    if not got or len(got) != 3:
        print("❌ 더 볼 수 없다"); return 1
    ck("세 편 다 예약이 걸린다 (즉시 공개가 하나도 없다)",
       all(a for _n, a in got),
       " · ".join(f"{n}편={'예약' if a else '즉시'}" for n, a in got))
    ts = [kst(a) for _n, a in got]
    ck(f"전부 한국 아침 {NS.HOUR_KST}시다 ({' · '.join(f'{t:%m-%d %H:%M}' for t in ts)})",
       all(t.hour == NS.HOUR_KST and t.minute == 0 for t in ts))
    ck("하루씩 띄운다",
       all((ts[i + 1] - ts[i]).days == 1 for i in range(len(ts) - 1)),
       str([str(ts[i + 1] - ts[i]) for i in range(len(ts) - 1)]))

    print("\n② 한 편만 올릴 때도 걸리는가 (여기가 비어 있었다)")
    one = run_block("public", "2")
    ck("한 편만 올려도 예약이 걸린다", one and one[0][1], str(one))
    ck("그 한 편도 아침 8시다",
       one and one[0][1] and kst(one[0][1]).hour == NS.HOUR_KST)

    print("\n③ 비공개·일부공개를 고르면 예약을 안 거는가")
    for pv in ("private", "unlisted"):
        g = run_block(pv, "all")
        ck(f"{pv} — 저절로 공개되지 않는다",
           g and not any(a for _n, a in g), str(g))

    print("\n③ -2 공개 시각이 실측으로 정한 그 시각인가")
    # ⚠️⚠️ 위 ①의 "아침 8시다" 검사는 NS.HOUR_KST 를 그대로 견주고 있었다.
    #    그러면 상수를 저녁 7시로 바꿔도 **양쪽이 같이 바뀌어** 통과한다
    #    (되돌리기 시험에서 드러났다). 값을 여기 **따로 못 박는다.**
    ck("한국 아침 8시다 (실측: 08시 4건 1,849 · 13시 3건 1,269 · 19시반 1건 349)",
       NS.HOUR_KST == 8, f"지금 {NS.HOUR_KST}시로 돼 있다")

    print("\n④ 변환이 끝날 시간을 벌어 두는가")
    ck(f"적어도 {NS.LEAD_H}시간 뒤로 잡는다", NS.LEAD_H >= 3)
    for h in (0, 3, 7, 8, 23):
        base = datetime(2026, 9, 6, h, 0, tzinfo=NS.KST).astimezone(timezone.utc)
        t = kst(NS.slot(0, base))
        gap = (t - base.astimezone(NS.KST)).total_seconds() / 3600
        ck(f"한국 {h:02d}시에 눌러도 {gap:.0f}시간 뒤다 ({t:%m-%d %H시})",
           gap >= NS.LEAD_H)

    print("\n⑤ 화면이 손님께 그대로 알려 주는가")
    js = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
    ck("세 편 모두 예약 공개라고 적혀 있다", "세 편 모두 예약 공개" in js)
    # ⚠️ 화면에 적힌 시각과 코드의 시각이 갈라지면 손님이 딴 때를 기다린다
    ck(f"화면에 적힌 시각과 코드가 같다 (아침 {NS.HOUR_KST}시)",
       f"아침 {NS.HOUR_KST}시" in js)
    ck("왜 그렇게 하는지도 적혀 있다", "고화질 변환을 끝내기 전" in js)
    ck("'첫 편은 지금 올리고' 라는 옛 안내가 없다", "첫 편은 지금 올리고" not in js)

    print("\n" + "─" * 60)
    if bad:
        print(f"❌ 예약 공개: {len(bad)}군데")
        for b in bad:
            print(f"     {b}")
        return 1
    print("✅ 예약 공개: 1편도 예약이 걸리고, 한국 아침 8시에 하루씩 뜬다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
