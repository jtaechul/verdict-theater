#!/usr/bin/env python3
"""사건 ↔ 편 뼈대가 성한가 (값 0원 · 인터넷 0회)

    python3 tools/parts_check.py

⭐⭐⭐ 2026-09-01 손님: "앞으로 영상을 계속 만들어나가고 계속 올려야 되는데
   이런 식으로 관리자 페이지를 구성하면 한 편 만들고 올리고 난 다음엔 다시 또
   관리자 페이지 체계를 바꿔야 될 걸로 보여져. 지속 가능하지 않거든."

   맞는 지적이었다. 그전까지 화면도 대본도 **S90 한 사건에 못이 박혀** 있었다.
   이 검사가 하는 일은 딱 하나 —
   **다시 못이 박히지 않았는지** 매번 보는 것이다.

   못이 박히는 모양은 늘 이렇다:
     · 화면이 'S90' 을 글자 그대로 적어 두고 그것만 그린다
     · 편 수를 3으로 못 박는다 (사건마다 2편일 수도 4편일 수도 있다)
     · 대본을 파이썬 파일로 되돌린다 (손님은 파이썬을 못 쓰신다)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

BAD = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + ("" if ok else f"  ({why})"))
    if not ok:
        BAD.append(name)


def main():
    print("⭐ 사건 ↔ 편 뼈대 점검 (값 0원)\n")
    series = ROOT / "data" / "series"

    print("① 대본이 **데이터 파일**인가 (기계가 지을 수 있어야 한다)")
    stories = sorted(series.glob("*.story.json"))
    ck(f"쇼츠 대본이 있다 ({len(stories)}건)", bool(stories))
    old = sorted(series.glob("S9*_story.py"))
    ck("손으로 쓴 파이썬 대본이 남아 있지 않다", not old,
       f"{[f.name for f in old]} — 손님은 파이썬을 못 쓰십니다")
    gen = ROOT / "src" / "story90.py"
    ck("대본을 짓는 프로그램이 있다 (src/story90.py)", gen.exists())
    wf = ROOT / ".github" / "workflows" / "story90.yml"
    ck("대본 짓는 단추가 있다 (story90.yml)", wf.exists())
    if wf.exists():
        t = wf.read_text(encoding="utf-8")
        ck("단추로만 돈다 (밀기만 해도 돈이 나가면 큰일이다)",
           "workflow_dispatch" in t and "\n  push:" not in t)
        import yaml
        yaml.safe_load(t)
        ck("YAML 이 성하다", True)

    print("\n② 편 나누기가 성한가")
    import story90                                            # noqa: E402
    for f in stories:
        d = json.loads(f.read_text(encoding="utf-8"))
        sid = d.get("sid") or f.name.split(".")[0]
        bad = story90.check(d)
        ck(f"{sid} 대본이 규격에 맞는다", not bad, "; ".join(bad[:3]))
        built = series / f"{sid}.json"
        ck(f"{sid} 프롬프트까지 지어져 있다", built.exists(),
           f"python3 tools/build_short90.py {sid} 를 돌리십시오")

    print("\n③ 편 수를 못 박지 않았는가")
    # 편이 셋이라고 코드에 적어 두면 2편·4편짜리 사건에서 화면이 어긋난다
    js = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
    nail = re.findall(r"parts\s*\[\s*[012]\s*\]", js)
    ck("화면이 편을 번호로 집어 쓰지 않는다", not nail, f"{nail[:3]}")
    import short90 as S9                                      # noqa: E402
    ck("편 목록을 대본에서 읽는다 (parts_of)", hasattr(S9, "parts_of"))
    ck("편마다 파일 이름을 만든다 (part_file)", hasattr(S9, "part_file"))
    # ⚠️ 조립하는 쪽이 S90 만 읽으면 두 번째 사건에서 **엉뚱한 대본**으로 만든다
    ck("조립도 사건을 골라 읽는다 (VT_SID)",
       "VT_SID" in (ROOT / "src" / "short90.py").read_text(encoding="utf-8"))
    ck("만들기 단추가 사건을 넘긴다",
       "VT_SID:" in (ROOT / ".github" / "workflows" / "short90.yml")
       .read_text(encoding="utf-8"))

    print("\n④ 화면이 한 사건에 못 박혀 있지 않은가")
    # 사건 목록을 **상태 파일 한 곳**에서 읽어 그려야 한다
    ck("사건 목록을 읽는 자리가 있다 (/api/works)", "'/api/works'" in js)
    ck("상태 파일 한 곳만 읽는다 (state/shorts.json)",
       "state/shorts.json" in js)
    ck("사건을 열어 보는 화면이 있다 (openWork)", "function openWork" in js)
    ck("사건 번호를 주소로 받는다 (sidOf)", "function sidOf" in js)
    # ⚠️ 'S90' 을 글자 그대로 적어 둔 자리가 많으면 다음 사건에서 또 못이 박힌다.
    #    기본값으로 쓰는 것 몇 개는 괜찮다 — 늘어나는 것을 막는다.
    hard = len(re.findall(r"'S90'", js))
    ck(f"화면에 S90 을 글자로 박아 둔 자리가 적다 ({hard}군데)", hard <= 8,
       f"{hard}군데 — 사건이 늘면 여기가 전부 어긋납니다")

    print("\n⑤ 편마다 따로 만들고 따로 올릴 수 있는가")
    mk = (ROOT / ".github" / "workflows" / "short90.yml").read_text(encoding="utf-8")
    ck("만들기가 편을 고를 수 있다", "--part" in mk)
    ck("만들기가 사건을 고를 수 있다", "sid:" in mk)
    up = (ROOT / ".github" / "workflows"
          / "short90-upload.yml").read_text(encoding="utf-8")
    ck("올리기가 편을 고를 수 있다", "part:" in up)
    ck("세 편을 한 번에 예약 공개할 수 있다", "every_hours" in up)
    ck("화면에 편별 만들기 단추가 있다", "function workMake" in js)
    ck("화면에 편별 올리기 단추가 있다", "function workUp" in js)
    # ⚠️⚠️ 단추가 두 번 눌려 같은 영상이 두 번 올라갈 뻔한 적이 있다
    ck("단추를 누르면 잠긴다 (두 번 눌려도 한 번만 간다)",
       "function lock" in js and "WBUSY" in js)
    upy = (ROOT / "src" / "upload.py").read_text(encoding="utf-8")
    ck("올리는 쪽에서도 두 번 올리기를 막는다", "이미 올렸다" in upy,
       "화면 잠금만 믿으면 언젠가 새어 나갑니다")

    print("\n⑥ 보관할 때 앞 편을 지우지 않는가")
    # ⚠️⚠️⚠️ 2026-09-02 — 실제로 지워 먹었다. prune 은 "남길 것만 두고
    #    나머지를 전부 지운다" 는 명령인데 그것을 **편마다** 돌렸다.
    #      part1 올림 → part1만 남김 / part2 올림 → part2만 남김(part1 사라짐)
    #    세 편을 다 만들고도 마지막 한 편만 남아, 손님 화면에서 1·2편이
    #    재생되지 않았다. 화면은 "만들어짐" 이라고 적혀 있으니 더 헷갈린다.
    mk_t = (ROOT / ".github" / "workflows" / "short90.yml").read_text(encoding="utf-8")
    lines = [l for l in mk_t.splitlines() if "release_file.py prune" in l
             and not l.lstrip().startswith("#")]
    ck(f"치우는 줄이 딱 하나다 ({len(lines)}개)", len(lines) == 1,
       f"{len(lines)}개 — 편마다 치우면 앞 편이 지워진다")
    # 반복문 **안**에서 돌면 안 된다 — 편 번호 변수가 들어 있으면 그 안이다
    ck("치우는 줄에 편 번호 변수가 없다",
       all("$K" not in l for l in lines),
       "반복문 안에서 치우고 있다 — 앞 편이 지워진다")
    # 남길 목록에 편 파일이 넉넉히 들어 있어야 한다
    keep = mk_t[mk_t.find("release_file.py prune"):][:400] if lines else ""
    import re as _re
    n_keep = len(_re.findall(r"part\d+\.mp4", keep))
    ck(f"남길 목록에 편 파일이 넉넉하다 ({n_keep}개)", n_keep >= 5,
       f"{n_keep}개 — 편이 더 늘면 그 편이 지워진다")
    ck("남길 목록에 올릴 글(meta.json)이 있다", "meta.json" in keep)
    # ⚠️ 올렸다는 것과 **남아 있다는 것**은 다르다. 위 사고 때 워크플로는
    #    초록불이었다 — 올리기도 지우기도 각각은 성공했으니까.
    ck("보관 뒤에 진짜로 들어갔는지 확인한다",
       "release_verify.py" in mk_t,
       "확인을 안 하면 초록불인데 재생이 안 되는 일이 또 생긴다")
    ck("확인하는 프로그램이 있다",
       (ROOT / "tools" / "release_verify.py").exists())

    print("\n⑦ 시험이 진짜 상태 파일을 안 건드리는가")
    # ⚠️⚠️ 2026-09-01 — 예행연습이 **가짜 소리로 잰 길이**를 진짜 상태 파일에
    #    적어, 화면에 "만들어짐 50초" 로 떠 버렸다. 손님은 화면밖에 못 보시니
    #    만들지도 않은 것을 만든 줄 아신다. 화면이 거짓말하는 것이 제일 나쁘다.
    import shortstate                                         # noqa: E402
    ck("상태 파일 자리를 바꿀 수 있다 (VT_SHORTS_STATE)",
       "VT_SHORTS_STATE" in (ROOT / "src" / "shortstate.py")
       .read_text(encoding="utf-8"))
    for f in ("short90_dryrun.py", "short90_test.py"):
        ck(f"{f} 가 딴 자리를 쓴다",
           "VT_SHORTS_STATE" in (ROOT / "tools" / f).read_text(encoding="utf-8"),
           "시험이 진짜 화면을 거짓말하게 만듭니다")

    print("\n⑧ 60초 못을 네 곳이 다 박고 있는가")
    # ⚠️⚠️ 이 채널이 실제로 겪은 일 — 60초 이하 6편은 전부 1,209~1,554회,
    #    127초 한 편은 5시간 반 동안 **조회수 0**. 쇼츠 피드가 안 태운 것이다.
    ck("조립할 때 본다 (short90.PART_MAX_SEC)",
       getattr(S9, "PART_MAX_SEC", 999) <= 60)
    ck("대본 지을 때 본다 (story90.PART_CHARS)",
       getattr(story90, "PART_CHARS", 999) <= 240)
    t1 = (ROOT / "tools" / "short90_test.py").read_text(encoding="utf-8")
    ck("규격 시험이 본다", "60초 아래" in t1)
    t2 = (ROOT / "tools" / "short90_dryrun.py").read_text(encoding="utf-8")
    ck("진짜 크기 시험이 본다", "60초를 안 넘는다" in t2)

    print("\n" + "─" * 60)
    if BAD:
        print("❌ 걸린 것:")
        for b in BAD:
            print("     " + b)
        return 1
    print("✅ 사건 ↔ 편 뼈대: 전부 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
