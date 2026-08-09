#!/usr/bin/env python3
"""오디션 파일에서 **어느 목소리가 몇 초에 나오는지** 찾아낸다. 값 0원.

    python3 tools/audition_index.py build/audition/voices_all.mp3 \\
        --order build/audition/audition_order.txt --out build/audition/audition_index.json

왜 (2026-08-09 손님: "삼십 개 들어보기 해서 실제로 만들기까지 했는데
                     이걸 확인할 방법이 없잖아.")
    30개를 한 파일에 이어 붙여 놓기만 하고 **어느 소리가 누구인지 알 방법을 안 줬다.**
    2분 30초를 들어도 지금 나오는 것이 Achird 인지 Fenrir 인지 알 수가 없다.
    들려주기만 하고 고를 수는 없게 만든 셈이다 — 만들다 만 것이다.

어떻게 (제미나이를 부르지 않는다 · 이미 만든 파일을 재기만 한다)
    이어 붙일 때 목소리 사이에 **0.6초 무음**을 넣었다. 그 무음을 찾으면
    각 목소리가 몇 초에 시작하는지 알 수 있다. 그것을 목록과 짝지어 적어 둔다.
    관리자 페이지는 이 목록을 보고 '이름을 누르면 그 자리로 넘어가게' 해 준다.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# ⚠️ 2026-08-09 실측 — 처음에는 -45dB·0.35초로 잡았더니 **84군데**가 나왔다(30개여야 한다).
#    말 중간의 쉼(쉼표·문장 끝)까지 무음으로 센 것이다.
#    목소리 사이에 넣은 것은 **완전한 디지털 무음 0.6초**이고, 말 중간의 쉼은
#    방 소리가 조금이라도 남아 있다. 그래서 기준을 더 엄하게 잡는다.
#    그래도 개수가 안 맞으면 **가장 긴 것 N-1개만** 고른다 — 넣은 무음이
#    말 중간 쉼보다 길다는 것은 확실하므로, 짐작이 아니라 순서로 고르는 것이다.
GAP_MIN = 0.45          # 넣은 것은 0.6초. 말 중간 쉼은 이보다 짧다
SILENCE_DB = -55        # 넣은 것은 완전한 무음이다


def dur(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def gaps(path):
    """무음 구간 [(시작, 끝)] 을 찾는다."""
    r = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path),
         "-af", f"silencedetect=noise={SILENCE_DB}dB:d={GAP_MIN}", "-f", "null", "-"],
        capture_output=True, text=True)
    log = r.stderr or ""
    starts = [float(m) for m in re.findall(r"silence_start:\s*([0-9.]+)", log)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([0-9.]+)", log)]
    out = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        if e is not None and e > s:
            out.append((s, e))
    return out


def read_order(path):
    """'1. Achird  118Hz' 꼴을 읽는다."""
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*(\d+)\.\s*(\S+)\s+([0-9.]+)Hz", line)
        if m:
            rows.append({"n": int(m.group(1)), "name": m.group(2),
                         "hz": float(m.group(3))})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--order", required=True)
    ap.add_argument("--out", default="build/audition/audition_index.json")
    a = ap.parse_args()

    total = dur(a.audio)
    order = read_order(a.order)
    if not order:
        print(f"오류: 목록을 못 읽었습니다 — {a.order}", file=sys.stderr)
        return 1

    g = gaps(a.audio)
    want = len(order) - 1                       # 목소리 30개 → 사이는 29군데
    print(f"파일 {total:.1f}초 · 무음 {len(g)}군데 찾음 (필요한 것 {want}군데)")

    if len(g) > want:
        # ⭐ **가장 긴 것부터 필요한 만큼만 고른다.**
        #    넣은 무음(0.6초)이 말 중간 쉼보다 길다는 것은 확실하다.
        #    실측: 처음에는 84군데가 잡혔다 — 말 중간 쉼까지 센 것이다.
        g = sorted(sorted(g, key=lambda x: x[1] - x[0], reverse=True)[:want])
        print(f"  → 긴 것부터 {want}군데만 골랐습니다")

    starts = [0.0] + [e for _s, e in g]         # 목소리 시작 = 0초 + 무음이 끝나는 자리
    if len(starts) != len(order):
        # 그래도 안 맞으면 **짐작해서 맞추지 않는다.** 틀린 자리를 알려 주면
        # 손님이 엉뚱한 목소리를 고르게 된다 — 없느니만 못하다.
        print(f"⚠️ 도막 {len(starts)}개 · 목록 {len(order)}개 — 자리를 적지 않고 이름만 적습니다.",
              file=sys.stderr)
        starts = []
    else:
        # 마지막 확인: 도막 하나하나가 말 한 줄만 한 길이인가 (너무 짧으면 잘못 잡은 것)
        segs = [(starts[i + 1] if i + 1 < len(starts) else total) - s
                for i, s in enumerate(starts)]
        if min(segs) < 1.0:
            print(f"⚠️ 너무 짧은 도막이 있습니다({min(segs):.1f}초) — 자리를 적지 않습니다.",
                  file=sys.stderr)
            starts = []
        else:
            print(f"  도막 {len(segs)}개 · 가장 짧은 것 {min(segs):.1f}초"
                  f" · 가장 긴 것 {max(segs):.1f}초")

    items = []
    for i, row in enumerate(order):
        it = dict(row)
        if starts:
            it["start"] = round(starts[i], 2)
            nxt = starts[i + 1] if i + 1 < len(starts) else total
            it["dur"] = round(max(0.0, nxt - starts[i]), 2)
        items.append(it)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"total": round(total, 2), "items": items},
                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"적었습니다: {out}")
    for it in items[:6]:
        t = f"{int(it['start']) // 60}:{int(it['start']) % 60:02d}" if "start" in it else "-"
        print(f"  {t:>5s}  {it['name']:15s} {it['hz']:.0f}Hz")
    if len(items) > 6:
        print(f"  … 모두 {len(items)}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
