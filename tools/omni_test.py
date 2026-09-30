#!/usr/bin/env python3
"""⭐ **새 방식 시험 — 인물 시트 한 장 + 옴니 입모양 한 컷** (약 1,500원)

    python3 tools/omni_test.py S93             알아서 고른 결정적 컷 하나
    python3 tools/omni_test.py S93 --cut 8     컷을 골라서
    python3 tools/omni_test.py S93 --dry       값 0원 — 무엇을 살지와 프롬프트만
    python3 tools/omni_test.py S93 --fresh     인물 시트부터 새로 (지난 시트를 안 쓴다)

⭐⭐⭐ 2026-09-30 손님이 정한 새 방식의 **0번 관문**이다.
    ① 등장인물(6명 이내)을 **한 장에** 그린다 → 칸마다 잘라 인물 참조로 쓴다
    ② 결정적 컷만 옴니 플래시로 입모양+대사 영상, 나머지는 그림+카메라 무빙
    한 편 전부(결정적 컷 10개 안팎 · 만 원 넘게)를 사기 전에 **한 컷만** 사서
    눈과 귀로 본다.

    같은 날 손님이 앱(구글 플로우)에서 직접 해 보셨다 — 시트는 잘 나왔는데
    영상은 "유명인의 동영상 생성에 관한 Google 정책" 으로 막혔다. 앱은 사람
    그림을 첨부하면 막는다. 그래서 이 시험은 **API 로** 돈다 (src/omni.py).

순서 (다시 누르면 지난 시트를 꺼내 써서 그만큼 0원)
    1. 인물 시트 한 장 (4K · 약 265원)          src/castsheet.py
    2. 칸 자르기 (0원)                           빈 세로줄을 찾아서, 못 찾으면 똑같이
    3. 그 컷 그림 (2K · 약 132원)                말하는 사람의 칸을 참조로
    4. 옴니 영상 (7초 안팎 · 약 1,000원)         3을 첫 장면, 2를 인물 참조로
       안전 검사에 걸리면 한 번만 '참조만' 으로 다시 해 본다 (첫 장면 없이)

보실 것 네 가지
    ① 다섯 얼굴이 확실히 다른가 (특히 내연녀와 딸)
    ② 한국어 발음이 알아들을 만한가
    ③ 입 모양이 말과 맞는가
    ④ 얼굴이 시트 속 그 사람과 같은가 · 화면에 글자가 박히지 않았는가

⚠️ 값이 나간다. 그래서 **단추로만 돈다** (.github/workflows/omni-test.yml).
"""
import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import castsheet                                             # noqa: E402
import cost                                                  # noqa: E402
import omni                                                  # noqa: E402
import still                                                 # noqa: E402

OUT = ROOT / "build" / "omni_test"
PER_SEC = 4.6            # 한국어 1초에 약 4.6자 (vprompt.seconds_for 와 같은 잣대)
LEAD, PAUSE, TAIL = 0.6, 0.5, 0.7
SEC_MIN, SEC_MAX = 4, 10  # 옴니는 길이를 글로 받는다 (해양생물 쪽 실측 4~8초)
# 안전 검사가 자주 막는 낱말 — 시험용으로는 이런 대사를 안 고른다 (talk_test 와 같다)
HOT = ("관계", "잤", "몸", "성관계", "강간", "죽", "때렸")
# '하나의 사람 · 두 모습' — 시트 칸에는 한 사람이 가까이·전신 두 번 나온다
TWICE = (" The reference picture shows each person twice — a close view and a "
         "full-length view — and each is one single person.")


def turns_of(c):
    if c.get("turns"):
        return [(w, t) for w, t in c["turns"]]
    return [(c.get("kind") or "나레이션", c.get("text") or "")]


def is_narr(c):
    return all(w == "나레이션" for w, _ in turns_of(c))


def good_cut(c):
    """시험에 좋은 컷 — 한 사람이 한 줄 말하고, 화면에도 그 사람뿐이다."""
    if is_narr(c) or len(c.get("turns") or []) != 1:
        return False
    who, text = c["turns"][0]
    return (c.get("who") or []) == [who] and not any(w in text for w in HOT)


def cast_gap(doc, c):
    """이 컷 화면에 나오는데 인물 설계(characters)에 없는 사람 — 시트에 못 그린다.
    ⚠️ 2026-09-30 — S92 는 사건 인물이 장남·차남·아버지… 인데 characters 에는
       옛 다섯(본처·남편…)이 그대로 있다. 그대로 시트를 그리면 **엉뚱한 사람들**을
       사고 만다. 돈 쓰기 전에 멈춘다."""
    return [w for w in (c.get("who") or []) if not castsheet.char_of(doc, w)]


def pick(doc, n=0):
    if n:
        return next((c for c in doc["cuts"] if c["n"] == n), None)
    try:
        import talkplan                                      # noqa: E402
        keys = [c for c in talkplan.key_cuts(doc) if good_cut(c)]
    except Exception:                                        # noqa: BLE001
        keys = []
    rest = [c for c in doc["cuts"] if good_cut(c)]
    return (keys or rest or [None])[0]


def sentences(text):
    return [s for s in re.split(r"(?<=[.?!…])\s+", str(text or "").strip()) if s]


def speak_sec(s):
    """소리 나는 글자만 센다 — 마침표·쉼표는 말하지 않는다."""
    return len(re.sub(r"[^0-9A-Za-z가-힣]", "", s)) / PER_SEC


def plan_sec(text):
    ss = sentences(text)
    need = LEAD + sum(speak_sec(s) for s in ss) + PAUSE * max(0, len(ss) - 1) + TAIL
    return int(min(SEC_MAX, max(SEC_MIN, math.ceil(need))))


def timeline(role, text, sec):
    """[0.0-0.6s] 처럼 초를 박아 적는다 — 옴니 문서가 권하는 적기다."""
    rows, t = [], LEAD
    rows.append(f"[0.0-{t:.1f}s] silent, {role} holds the moment and takes one slow breath.")
    ss = sentences(text)
    for i, s in enumerate(ss):
        e = t + speak_sec(s)
        rows.append(f"[{t:.1f}-{e:.1f}s] {role} says in Korean: \"{s}\"")
        t = e
        if i + 1 < len(ss):
            rows.append(f"[{t:.1f}-{t + PAUSE:.1f}s] one beat of silence.")
            t += PAUSE
    rows.append(f"[{t:.1f}-{sec:.1f}s] silent, lips closed, {role} holds the look "
                "until the end.")
    return rows


def line_of(prompt, head):
    return next((ln for ln in str(prompt or "").split("\n") if ln.startswith(head)), "")


def english(text, doc):
    """지문 속 한국어 이름('아내')을 영어 역할('the wife')로 바꾼다."""
    out = str(text or "")
    names = {ch.get("name") for ch in doc.get("characters") or []}
    names |= set(castsheet.ALIAS)
    for nm in sorted((n for n in names if n), key=len, reverse=True):
        ch = castsheet.char_of(doc, nm)
        if ch and nm in out:
            out = out.replace(nm, str(ch.get("role_en") or nm))
    return out


def omni_prompt(doc, c, sec, first=True):
    who, text = turns_of(c)[0]
    ch = castsheet.char_of(doc, who) or {}
    role = str(ch.get("role_en") or "the speaker")
    her = "her" if castsheet.sex_age(ch)[0] == "woman" else "his"
    ref = "<IMAGE_REF_0>"
    head = (f"[# Sources <FIRST_FRAME>@Image1] [# References {ref}@Image2]" if first
            else f"[# References {ref}@Image1]")
    shot = english(c.get("scene") or "", doc).rstrip(".")
    say = "; ".join(c.get("say") or [])
    rows = [
        head,
        "A short fictional drama scene. Every character is invented for this story "
        f"and resembles nobody. Vertical 9:16, exactly {sec} seconds, one single "
        "continuous shot from the first frame to the last.",
        f"CAST: {role} {ref} is the only person in this scene and looks exactly like "
        f"{ref} the whole time. {ref} shows {role} twice — a close view and a "
        "full-length view — one single person.",
        f"SHOT: {shot}. The camera stays completely still on a tripod; only {her} "
        "face and breathing move.",
    ]
    if not first:
        # 첫 장면이 없으면 화면 잡기를 글로 정해 줘야 한다 (그 컷 그림 프롬프트의 것)
        rows.append(english(line_of(c.get("still"), "FRAMING:"), doc))
    rows += ["TIMELINE:", *timeline(role, text, sec)]
    rows += [
        f"DIALOGUE: [LANGUAGE: KOREAN] {role} speaks only these exact words, once, in "
        "natural fluent everyday Korean with standard Seoul intonation, lips moving "
        f"in sync with every syllable: \"{text}\"",
        f"VOICE: {ch.get('voice') or 'a natural Korean voice'}."
        + (f" Delivery (Korean note): {say}." if say else ""),
        f"SOUND: {role}'s voice with quiet room tone underneath, and nothing else.",
        line_of(c.get("still"), "COLOR:") or
        "COLOR: warm neutral base, low overall contrast, slightly lifted blacks, "
        "muted greens and cyans, natural unsaturated skin tones.",
        "STYLE: naturalistic cinematic drama, soft film grain, muted desaturated "
        "palette, soft practical lighting, shallow depth of field.",
        "ON SCREEN: no text, no letters, no subtitles, no captions, no watermark, "
        "no logo.",
        ("Use Image1 as the starting frame. Use Image2 as a reference for the video "
         "generation." if first else
         # ⚠️ 옴니 문서의 권장 문구("…should not be used as a literal initial
         #    frame")는 '하지 마' 꼴이라 쓰지 않는다 (series.NEGATIVE) — 바라는 것만
         "Use the given image only as a reference for how the person looks; the "
         "video opens on a fresh shot of the scene."),
    ]
    return "\n".join(r for r in rows if r)


def still_prompt(c):
    """그 컷 그림 프롬프트 그대로 + '시트 칸에는 한 사람이 두 번 나온다' 한 줄."""
    rows = []
    for ln in str(c.get("still") or "").split("\n"):
        rows.append(ln + TWICE if ln.startswith("PEOPLE:") else ln)
    return "\n".join(rows)


def is_image(p):
    """지난 시트를 다시 써도 되나 — 진짜 그림인가.
    ⚠️ 보관함에서 꺼낼 때 이름이 없으면 **하나뿐인 다른 파일**을 대신 받는
       길이 있다(tools/release_file.py get). 그림이 아니면 새로 만든다."""
    try:
        from PIL import Image                                # noqa: E402
        with Image.open(p) as im:
            im.verify()
        return True
    except Exception:                                        # noqa: BLE001
        return False


def preview(png):
    """폰에서 볼 가벼운 사본 (v-이름.jpg). 원본 PNG 는 참조로 쓰므로 그대로 둔다.
    ⚠️ 4K 시트 PNG 는 10MB 가 넘는다 — 휴대폰 데이터로 열면 한참 걸린다."""
    try:
        from PIL import Image                                # noqa: E402
        png = Path(png)
        with Image.open(png) as im:
            im = im.convert("RGB")
            im.thumbnail((1400, 5600))
            dst = png.with_name(f"v-{png.stem}.jpg")
            im.save(dst, "JPEG", quality=85)
        return dst
    except Exception:                                        # noqa: BLE001
        return None


def frames(mp4, jpg):
    """영상에서 네 장면을 뽑아 한 장으로 — 폰에서 영상을 못 틀어도 보이게."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return None
    try:
        dur = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(mp4)], capture_output=True, text=True).stdout or 0)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf",
             f"fps=4/{max(dur, 0.1):.2f},scale=270:-2,"
             "tile=4x1:margin=6:padding=6:color=white",
             "-frames:v", "1", str(jpg)], check=True)
        return round(dur, 2)
    except Exception:                                        # noqa: BLE001
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sid")
    ap.add_argument("--cut", type=int, default=0, help="컷 번호 (비우면 알아서)")
    ap.add_argument("--fresh", action="store_true", help="인물 시트부터 새로")
    ap.add_argument("--dry", action="store_true", help="값 0원 — 무엇을 살지만 본다")
    a = ap.parse_args()

    sid = a.sid.strip().upper()
    f = ROOT / "data" / "series" / f"{sid}.json"
    if not f.exists():
        print(f"❌ 대본이 없습니다: data/series/{sid}.json")
        return 2
    doc = json.loads(f.read_text(encoding="utf-8"))
    c = pick(doc, a.cut)
    if c is None or not good_cut(c):
        what = f"컷{a.cut}" if a.cut else "알맞은 컷"
        print(f"❌ {what} 으로는 시험할 수 없습니다 — 한 사람이 한 줄 말하고 화면에도 "
              f"그 사람뿐인 대사 컷이어야 합니다.\n"
              f"   고를 만한 컷: {[x['n'] for x in doc['cuts'] if good_cut(x)]}")
        return 2
    gap = cast_gap(doc, c)
    if gap:
        print(f"❌ 이 사건의 인물 설계(characters)에 {', '.join(gap)} 이(가) 없습니다.\n"
              f"   시트에 그릴 수 없어 시작하지 않습니다 (0원). 인물 설계가 있는 사건"
              f"(예: S93)으로 해 주십시오.")
        return 2
    who, text = turns_of(c)[0]
    sec = plan_sec(text)
    ps = castsheet.order(castsheet.people(doc, first=c.get("who") or []))
    if not ps:
        print("❌ 대본에 인물 설계(characters)가 없습니다")
        return 2

    out = OUT / sid
    out.mkdir(parents=True, exist_ok=True)
    sheet = out / "sheet.png"
    reuse = is_image(sheet) and not a.fresh
    tag = f"c{c['n']:02d}"
    k_sheet = 0 if reuse else cost.image_krw(still.MODEL, "4K")
    k_still = cost.image_krw(still.MODEL, "2K")
    k_omni = omni.est_krw(sec)
    sp = castsheet.prompt(ps)
    op = omni_prompt(doc, c, sec)

    print(f"■ 새 방식 시험 — {sid} 컷{c['n']} [{who}]")
    print(f"   대사   \"{text}\"")
    print(f"   인물 시트 (왼쪽부터)  {' · '.join(p['name'] for p in ps)}")
    print(f"   값 어림  시트 {'0원 (지난 것을 씀)' if reuse else f'{k_sheet:,.0f}원'}"
          f" + 컷 그림 {k_still:,.0f}원 + 옴니 {sec}초 {k_omni:,.0f}원"
          f" = 약 {k_sheet + k_still + k_omni:,.0f}원")
    print(f"   (안전 검사에 걸려 한 번 더 해 보면 +{omni.est_krw(sec):,.0f}원)")
    print(f"   이번 달 쓴 돈 {cost.month_total():,.0f}원 / 한도 {cost.MONTH_KRW:,.0f}원")
    if a.dry:
        print("\n── 인물 시트 프롬프트 ──\n" + sp)
        print("\n── 컷 그림 프롬프트 ──\n" + still_prompt(c))
        print("\n── 옴니 프롬프트 ──\n" + op)
        print("\n(연습이라 실제로는 안 삽니다 · 0원)")
        return 0

    res = {"sid": sid, "cut": c["n"], "who": who, "text": text, "sec": sec,
           "cast": [], "attempts": [], "krw": 0, "ok": False,
           "prompts": {"sheet": sp, "still": still_prompt(c), "omni": op}}
    spent0 = cost.month_total()

    def save(msg=""):
        res["krw"] = round(cost.month_total() - spent0)
        if msg:
            res["error"] = msg
        (out / "result.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    try:
        # 1. 인물 시트 — 4K 가 안 되는 모델이면 2K 로 (400 은 값이 안 나간다)
        if reuse:
            print("\n1. 인물 시트 — 지난 것을 씁니다 (0원)")
        else:
            print("\n1. 인물 시트 만드는 중…")
            try:
                still.gen(sp, sheet, ratio="16:9", size="4K", label="castsheet")
            except still.StillError as e:
                if "HTTP 400" not in str(e):
                    raise
                print(f"    4K 를 안 받아 2K 로 다시 합니다: {str(e)[:120]}")
                still.gen(sp, sheet, ratio="16:9", size="2K", label="castsheet")
        # 2. 칸 자르기
        outs, how = castsheet.crop(sheet, len(ps), out)
        print(f"2. 칸 자르기 — {how}")
        for (p, box), ch in zip(outs, ps):
            res["cast"].append({"file": p.name, "name": ch["name"],
                                "role": ch.get("role_en") or ""})
            print(f"    {p.name}  {ch['name']}  (가로 {box[0]}~{box[1]})")
        for p in [sheet] + [p for p, _ in outs]:
            preview(p)
        crop_of = {ch["name"]: p for (p, _), ch in zip(outs, ps)}
        mine = castsheet.char_of(doc, who)
        ref = crop_of.get((mine or {}).get("name"))
        if not ref:
            raise RuntimeError(f"{who} 의 칸을 못 찾았습니다")
        # 3. 그 컷 그림 (말하는 사람 칸을 참조로)
        still_png = out / f"{tag}-still.png"
        print(f"3. 컷{c['n']} 그림 만드는 중…")
        still.gen(still_prompt(c), still_png, refs=[ref], ratio="9:16", size="2K",
                  label=tag)
        preview(still_png)
        # 4. 옴니 — 그림을 첫 장면, 칸을 인물 참조로
        mp4 = out / f"{tag}-omni.mp4"
        print("4. 옴니 영상")
        try:
            got = omni.make(op, [still_png, ref], mp4, sec, task="image_to_video")
            res["attempts"].append({"task": "image_to_video", "ok": True, **got})
        except omni.OmniFiltered as e:
            res["attempts"].append({"task": "image_to_video", "ok": False,
                                    "error": str(e)[:400]})
            print(f"    ⚠️ 안전 검사에 걸렸습니다 — 첫 장면 없이 '참조만' 으로 한 번 더:"
                  f"\n    {str(e)[:200]}")
            op2 = omni_prompt(doc, c, sec, first=False)
            res["prompts"]["omni_ref_only"] = op2
            got = omni.make(op2, [ref], mp4, sec, task="reference_to_video")
            res["attempts"].append({"task": "reference_to_video", "ok": True, **got})
        dur = frames(mp4, out / f"{tag}-frames.jpg")
        res["video_sec"] = dur
        res["ok"] = True
        save()
    except (omni.OmniError, still.StillError, cost.MonthlyCapReached,
            RuntimeError) as e:
        res["attempts"].append({"ok": False, "error": str(e)[:400]})
        save(str(e)[:400])
        print(f"\n❌ 못 만들었습니다: {e}")
        print(f"   이번에 쓴 돈 약 {res['krw']:,}원")
        return 1

    print(f"\n✅ 만들었습니다 — {mp4.name} ({dur or '?'}초) · 이번에 쓴 돈 약 "
          f"{res['krw']:,}원")
    print("\n■ 보실 것 네 가지")
    print("   ① 다섯 얼굴이 확실히 다른가 (특히 내연녀와 딸)")
    print("   ② 한국어 발음이 알아들을 만한가")
    print("   ③ 입 모양이 말과 맞는가")
    print("   ④ 얼굴이 시트 속 그 사람과 같은가 · 화면에 글자가 박히지 않았는가")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
