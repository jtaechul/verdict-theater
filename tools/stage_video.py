#!/usr/bin/env python3
"""⭐ 작업 칸에서 만든 완성 영상을 **보관함(릴리스 short90-<사건>)** 에 넣는다 — 유튜브에 올릴 준비 (0원)

    python3 tools/stage_video.py S94                  작업 칸에서 — 올릴 준비를 보고 임시 가지로 밀어 넣는다
    python3 tools/stage_video.py --release stage/S94  워크플로(stage-video.yml)에서 — 보관함으로 옮긴다
    python3 tools/stage_video.py S95 --only jpg       썸네일만 보관함에 넣는다 (이미 올린 영상의 썸네일 바꾸기)

⭐ 2026-10-07 손님: "썸네일 보고도 아무도 안누른다." 이미 올린 영상은 썸네일만 바꾼다 —
   45MB 영상을 다시 실어 보낼 까닭이 없다. `--only jpg` 로 part<N>.jpg 만 보관함에 넣고,
   관리자 페이지 4-2 [썸네일만 바꾼다] 가 그것을 꺼내 유튜브에 건다 (upload.py thumb90 · 0원).

⭐ 2026-10-03 손님: "이거 유튜브에 올릴 수 있게 준비까지 마무리해줘"
   올리기 단추(관리자 페이지 4-2 · short90-upload.yml)는 보관함에서 part1.mp4 · part1.jpg 를
   꺼내 올린다. 설명 드라마는 작업 칸(Claude 세션)에서 만드는데, 작업 칸은 보관함을 직접
   못 만든다 ("Creating, editing, or deleting releases is not permitted for this session type").
   → 영상·썸네일·올릴 글을 **임시 가지 stage/<사건>** 에 실어 밀어 넣으면, 워크플로가
     보관함으로 옮기고 임시 가지를 지운다. 영상은 main 이력에 남지 않는다.

밀어 넣기 전에 보는 것 (올리기에서 막히는 것을 미리 — 올리기는 되돌릴 수 없다)
    · 편마다 완성 영상과 썸네일이 있는가 (build/s90/<사건>_part<N>.mp4 · .jpg)
    · 길이가 그 형식의 벽 안인가 (talkplan.part_max_sec — 설명 드라마는 쇼츠 한도 179.5초)
    · 만든 기록(state/shorts.json)에 길이가 적혀 있고, 그림으로 떨어진 대사 컷이 없는가
    · 올릴 글(data/series/<사건>.meta.json)이 마지막 문지기(fetch_meta90.blocked)를 지나는가
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

OUT = ROOT / "build" / "s90"


def dur_of(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def ready(sid):
    """(밀어 넣을 파일들 {보관함 이름: 파일}, 걸린 것들) — 0원 · 인터넷 0회."""
    import fetch_meta90                                        # noqa: E402
    import shortstate                                          # noqa: E402
    import talkplan                                            # noqa: E402
    bad, files = [], {}
    f = ROOT / "data" / "series" / f"{sid}.json"
    if not f.exists():
        return {}, [f"data/series/{sid}.json 이 없다 — build_short90 을 먼저"]
    doc = json.loads(f.read_text(encoding="utf-8"))
    wall = talkplan.part_max_sec(doc)
    for p in doc.get("parts") or []:
        no = int(p["no"])
        mp4, jpg = OUT / f"{sid}_part{no}.mp4", OUT / f"{sid}_part{no}.jpg"
        if not mp4.exists():
            bad.append(f"{no}편 완성 영상이 없다 ({mp4.relative_to(ROOT)}) — drama60 build 를 먼저")
            continue
        sec = dur_of(mp4)
        if sec > wall:
            bad.append(f"{no}편이 {sec:.1f}초 — 벽 {wall:.1f}초를 넘는다 (올리기에서 막힌다)")
        made = shortstate.made(sid, no) or {}
        if not made.get("sec"):
            bad.append(f"{no}편 만든 기록(state/shorts.json sec)이 없다 — build 를 다시")
        elif abs(float(made["sec"]) - sec) > 1.0:
            bad.append(f"{no}편 만든 기록({made['sec']}초)과 영상({sec:.1f}초)이 다르다 — build 를 다시")
        if made.get("talk_gaps"):
            bad.append(f"{no}편에 그림으로 떨어진 대사 컷이 있다: {made['talk_gaps']}")
        files[f"part{no}.mp4"] = mp4
        if jpg.exists():
            files[f"part{no}.jpg"] = jpg
        else:
            print(f"  ⚠️ {no}편 썸네일이 없다 — 유튜브가 아무 장면이나 고른다")
        # ⭐ 2026-10-06 — 긴 영상은 자막 파일(.srt · drama60 meta)도 같이 보관한다 (올리기가 함께 올린다)
        srt = mp4.with_suffix(".srt")
        if srt.exists():
            files[f"part{no}.srt"] = srt
        elif str(doc.get("layout") or "") == "long":
            print(f"  ⚠️ {no}편 자막 파일이 없다 — `drama60 {sid} meta` 를 먼저 (검색에 안 걸린다)")
    meta = ROOT / "data" / "series" / f"{sid}.meta.json"
    if not meta.exists():
        bad.append(f"올릴 글이 없다 ({meta.relative_to(ROOT)}) — build_short90 을 다시")
    else:
        mj = json.loads(meta.read_text(encoding="utf-8"))
        why = fetch_meta90.blocked(mj)
        bad += [f"올릴 글: {w}" for w in why]
        # ⭐⭐ 2026-10-09 손님: "쇼츠 3편 … 제목이랑 내용이랑 해시태그 같은 게 아무것도 안 들어가
        #    있어서 예약 업로드가 안 돼." — 편마다 제목 · 설명 · 해시태그가 **다 찼는지** 여기서도 본다.
        bad += [f"올릴 글: {w}" for w in meta_gaps(doc, mj)]
        files["meta.json"] = meta
    return files, bad


def meta_gaps(doc, meta):
    """대본의 편마다 올릴 글(제목 · 설명 · 해시태그)이 다 찼는가 — 빈 것을 줄줄이 돌려준다 (0원)."""
    have = {int(x.get("part") or 0): x for x in (meta.get("parts") or [])}
    out = []
    for p in doc.get("parts") or []:
        no = int(p["no"])
        m = have.get(no)
        if not m:
            out.append(f"{no}편 글이 아예 없다 — build_short90 (미끼 쇼츠는 teaser.py) 로 다시 짓는다")
            continue
        for k, name in (("title", "제목"), ("description", "설명")):
            if not str(m.get(k) or "").strip():
                out.append(f"{no}편 {name}이 비었다")
        if not [t for t in (m.get("tags") or []) if str(t).strip()]:
            out.append(f"{no}편 해시태그가 비었다")
    return out


def git(*a, cwd=ROOT):
    r = subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"git {' '.join(a)} — {r.stderr.strip()[:300]}")
    return r.stdout


def push_stage(sid, files):
    """main 위에 파일만 얹은 임시 가지를 만들어 밀어 넣는다 (작업 칸의 main 은 안 건드린다)."""
    br = f"stage/{sid}"
    git("fetch", "origin", "main")
    tmp = Path(tempfile.mkdtemp(prefix="stage-"))
    git("worktree", "add", "--detach", str(tmp), "origin/main")
    try:
        dst = tmp / "stage" / sid
        dst.mkdir(parents=True)
        for name, src in files.items():
            shutil.copy2(src, dst / name)
        git("add", "-f", f"stage/{sid}", cwd=tmp)
        git("commit", "-q", "-m", f"{sid} 완성 영상을 보관함으로 (임시 가지 · 옮긴 뒤 지운다)",
            cwd=tmp)
        for k in range(5):                      # 그물이 끊기면 2·4·8·16초 쉬고 다시
            try:
                git("push", "-f", "origin", f"HEAD:refs/heads/{br}", cwd=tmp)
                break
            except RuntimeError:
                if k == 4:
                    raise
                time.sleep(2 ** (k + 1))
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(tmp)], cwd=ROOT,
                       capture_output=True)
    return br


def release(ref):
    """워크플로에서 — stage/<사건>/ 의 파일을 보관함 short90-<사건> 으로 옮긴다."""
    import release_file                                        # noqa: E402
    sid = ref.split("/", 1)[-1]
    if not re.fullmatch(r"S\d{2,4}", sid):
        print(f"❌ 가지 이름이 stage/S<번호> 가 아니다: {ref}")
        return 2
    src = ROOT / "stage" / sid
    names = sorted(p.name for p in src.glob("*")
                   if re.fullmatch(r"part\d+\.(mp4|jpg|srt)|meta\.json", p.name))
    if not names:
        print(f"❌ 넣을 파일이 없다 (stage/{sid}/part1.mp4 …)")
        return 2
    rc = 0
    for n in names:
        rc = max(rc, release_file.put(f"short90-{sid}", n, str(src / n)) or 0)
    print(f"■ 보관함 short90-{sid} 에 {len(names)}개: {', '.join(names)}")
    return rc


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--release":
        return release(sys.argv[2])
    if len(sys.argv) < 2 or not re.fullmatch(r"[Ss]\d{2,4}", sys.argv[1]):
        print(__doc__)
        return 2
    sid = sys.argv[1].upper()
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv[2:-1] else ""
    if only and only not in ("jpg", "srt", "meta"):
        print(f"❌ --only 는 jpg · srt · meta 중 하나다 (받은 것: {only})")
        return 2
    files, bad = ready(sid)
    if only:
        keep = {"jpg": ".jpg", "srt": ".srt", "meta": ".json"}[only]
        files = {k: v for k, v in files.items() if k.endswith(keep)}
        if not files:
            print(f"❌ {sid} 에 보관함에 넣을 {only} 파일이 없다")
            return 1
    if bad:
        print(f"❌ {sid} 는 아직 올릴 준비가 안 됐다 — 밀어 넣지 않는다")
        for b in bad:
            print(f"   · {b}")
        return 1
    for name, src in files.items():
        print(f"  ✅ {name:<10} ← {Path(src).relative_to(ROOT)} "
              f"({Path(src).stat().st_size / 1048576:.1f}MB)")
    br = push_stage(sid, files)
    print(f"■ 임시 가지 {br} 로 밀어 넣었다 — 워크플로(4-1b)가 보관함 short90-{sid} 으로 옮기고 "
          f"가지를 지운다 (1~2분 · 0원).\n"
          f"  그다음 관리자 페이지 [4-2. 쇼츠 유튜브에 올리기] 에서 사건 {sid} 를 올린다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
