#!/usr/bin/env python3
"""배경음악을 **Freesound 에서 공짜로** 받아 온다. 값 0원.

    python3 tools/get_bgm.py                 빠진 것만 받는다
    python3 tools/get_bgm.py care verdict    이것만 받는다
    python3 tools/get_bgm.py --all --force   전부 다시 받는다
    python3 tools/get_bgm.py --listen        받지 않고 후보만 본다

    필요한 열쇠: FREESOUND_TOKEN (저장소 Secrets)

왜 만들었나 (2026-08-12)
    배경음악 8곡 중 `care`(보살핌)·`verdict`(선고) 두 곡이 비어 있었다.
    그 두 장면은 음악 없이 방 소리만 깔린다. 손님 선택: "무료 음악 받아오기를 만들기".

왜 Freesound 인가
    효과음을 이미 여기서 받고 있고(tools/get_sfx.py), 같은 열쇠를 쓴다.
    **CC0(마음대로 써도 되는 것)만** 고른다 — 유튜브에 올릴 것이라 출처 표기
    의무가 있으면 뒤탈이 난다.
    ⚠️ Pixabay 소리 API 는 일반 열쇠로 안 열린다(2026-08-09 실측 403). 사진은 되지만
       소리는 안 된다. 그래서 소리·음악은 Freesound 다.

효과음 받기와 무엇이 다른가
    ① **길이** — 효과음은 1~10초, 음악은 60초 이상이라야 장면에 깔린다.
       짧은 것을 받으면 한 장면 안에서 여러 번 되풀이돼 티가 난다.
    ② **고르는 기준** — 효과음은 '삑'(기계음)을 걸러내지만, 음악은 반대로
       악기 소리가 이어져야 한다. 그래서 여기서는 다른 자로 잰다(check 참고).
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from get_sfx import api_key, get, search_freesound     # noqa: E402

ROOT = HERE.parent
OUT = ROOT / "assets" / "bgm"

# 장면마다 어떤 음악이어야 하는지. 위에서부터 찾다가 쓸 만한 것이 나오면 멈춘다.
# ⚠️ 우리 영상은 **말이 주인공**이다. 음악은 말 밑에 -36dB 로 깔린다(render.TARGET_DB).
#    그래서 선율이 뚜렷하거나 박자가 센 곡은 안 된다 — 말을 갉아먹는다.
#    "느리고, 악기가 적고, 계속 이어지는" 것을 노린다.
QUERIES = {
    "hook":     ["dark ambient tension drone", "suspense atmosphere loop"],
    "past":     ["nostalgic soft piano slow", "warm memory ambient piano"],
    # 보살핌 — 병상·간병·가족이 곁을 지키는 장면
    "care":     ["gentle warm piano calm slow", "tender emotional piano soft",
                 "soft ambient piano warm loop"],
    "reveal":   ["revealing ambient swell", "discovery atmosphere strings"],
    "conflict": ["tense strings low pulse", "conflict dramatic tension"],
    "court":    ["solemn ambient serious", "formal tension low strings"],
    # 선고 — 판결이 내려지는 순간. 무겁고 정적이어야 한다
    "verdict":  ["solemn low strings slow", "serious orchestral somber",
                 "heavy dramatic drone low"],
    "outro":    ["calm closing piano gentle", "peaceful ending ambient"],
}

MIN_SEC = 45.0        # 이보다 짧으면 장면에서 여러 번 되풀이돼 티가 난다
MAX_SEC = 300.0


def duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def mean_db(path):
    """평균 음량. 거의 무음이면 음악이 아니다."""
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path),
                        "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "mean_volume:" in line:
            try:
                return float(line.split("mean_volume:")[1].split("dB")[0])
            except ValueError:
                pass
    return -99.0


def usable(path):
    """음악으로 쓸 만한가 — 길고, 소리가 있어야 한다.

    ⚠️ 효과음 쪽의 '삑 검사'(sfx_quality.is_beep)를 쓰면 안 된다. 그것은
       '한 음만 길게 나는 것' 을 가짜로 본다. 그런데 잔잔한 배경음악은
       실제로 한 음이 길게 깔리는 경우가 많아 **멀쩡한 음악이 걸린다.**"""
    d = duration(path)
    if d < MIN_SEC:
        return False, f"너무 짧다({d:.0f}초, {MIN_SEC:.0f}초 이상 필요)"
    db = mean_db(path)
    if db < -45:
        return False, f"거의 무음이다({db:.0f}dB)"
    return True, f"{d:.0f}초 · {db:.0f}dB"


def fetch(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(get(url, timeout=180))
    # ⚠️ 192kbps 로 맞춘다. 128k 로 적어 뒀었는데 **실측해 보니 기존 6곡은
    #    192kbps** 였다(ffprobe). 새로 받은 곡만 낮은 규격이면 장면이 바뀔 때
    #    소리 결이 달라진다.
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp),
                        "-b:a", "192k", "-ar", "44100", "-ac", "2", str(path)],
                       capture_output=True, text=True)
    tmp.unlink(missing_ok=True)
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("codes", nargs="*", help="받을 음악 이름. 비우면 빠진 것만")
    ap.add_argument("--all", action="store_true", help="8곡 전부 대상")
    ap.add_argument("--force", action="store_true", help="이미 있어도 다시 받는다")
    ap.add_argument("--listen", action="store_true", help="받지 않고 후보만 본다")
    a = ap.parse_args()

    name, key = api_key("freesound")
    if not key:
        print("FREESOUND_TOKEN 이 없다. 저장소 Secrets 에 넣어야 한다.", file=sys.stderr)
        return 2
    print(f"열쇠: {name}")

    if a.codes:
        codes = [c for c in a.codes if c in QUERIES]
        unknown = [c for c in a.codes if c not in QUERIES]
        if unknown:
            print(f"모르는 이름: {', '.join(unknown)}", file=sys.stderr)
            print(f"쓸 수 있는 이름: {' '.join(QUERIES)}", file=sys.stderr)
            return 2
    elif a.all:
        codes = list(QUERIES)
    else:
        codes = [c for c in QUERIES if not (OUT / f"{c}.mp3").exists()]
        if not codes:
            print("빠진 음악이 없다. 8곡 다 있다.")
            return 0

    print(f"받을 것: {', '.join(codes)}\n")
    got, fail = [], []
    for code in codes:
        path = OUT / f"{code}.mp3"
        if path.exists() and not a.force and not a.listen:
            print(f"{code}: 이미 있다 (다시 받으려면 --force)")
            continue
        print(f"{code}")
        done = False
        for q in QUERIES[code]:
            try:
                hits = search_freesound(key, q, n=8, dur=(MIN_SEC, MAX_SEC))
            except Exception as e:
                print(f"   검색 실패({q}): {e}")
                continue
            if not hits:
                print(f"   '{q}' — 후보 없음")
                continue
            if a.listen:
                for h in hits[:4]:
                    print(f"   · {h['tags'][:44]}  {h['pageURL']}")
                done = True
                break
            for h in hits:
                if not fetch(h["audio"], path):
                    continue
                ok_, why = usable(path)
                if ok_:
                    print(f"   ✅ {why} — {h['tags'][:40]} (CC0 · {h['user']})")
                    got.append(code)
                    done = True
                    break
                print(f"   · 버림: {why}")
                path.unlink(missing_ok=True)
            if done:
                break
        if not done and not a.listen:
            print("   ❌ 쓸 만한 것을 못 찾았다")
            fail.append(code)

    if not a.listen:
        print(f"\n받음 {len(got)}곡" + (f" · 실패 {', '.join(fail)}" if fail else ""))
        if got:
            cr = OUT / "SOURCES.md"
            old = cr.read_text(encoding="utf-8") if cr.exists() else \
                "# 배경음악 출처\n\n전부 Freesound 의 CC0 — 마음대로 써도 되고 출처 표기 의무가 없다.\n"
            cr.write_text(old + f"\n- 2026-08-12 받음: {', '.join(got)}\n", encoding="utf-8")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
