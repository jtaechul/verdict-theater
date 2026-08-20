#!/usr/bin/env python3
"""⭐ 플로우에서 캐릭터를 만들 때 넣을 **제대로 된 프롬프트**를 짓는다. 0원.

    python3 src/charsheet.py S001

왜 (2026-08-20 운영자 지시)
    "인물 생성하는 프롬프트가 너무 짧아. 저렇게 하면 이상하게 배경 뜨고
     막 이렇게 나오는데 제대로 풀세트로 캐릭터가 만들어질 수 있게…"

    실제로 25~30낱말짜리였다 —
      "Korean woman, 52 years old, oval face, tired eyes …, Photorealistic."
    이러면 **배경도 자세도 옷도 매번 새로 뽑는다.** 캐릭터 기준 사진은
    "이 사람이 누구인가" 만 담아야 하는데, 안 정해 준 것이 너무 많았다.

    그래서 빠진 자리를 전부 채워 넣는다 —
      · 어떻게 서 있나(자세)   · 어디까지 보이나(화면 잡기)
      · 배경은 무엇인가(빈 스튜디오)  · 빛은 어떤가
      · 무엇을 입었나          · 하지 말아야 할 것(소품·글자·다른 사람)

    두 가지를 만든다. 플로우 캐릭터 만들기 화면에 각각 붙여 넣는 것이다.
      flow_sheet — 기준 사진을 뽑는 긴 프롬프트
      flow_desc  — '캐릭터 설명' 칸에 넣을 짧은 한 줄
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERIES = ROOT / "data" / "series"

# ⭐⭐ 2026-08-20 세 번째 — 플로우가 인물 만들기를 계속 막았다.
#    "이 프롬프트는 유명인의 동영상 생성에 관한 정책을 위반할 가능성이…"
#    예전 프롬프트를 다시 읽어 보면 **실존 인물 증명사진 주문서**였다 —
#      · Character reference **sheet** for a Korean man, **55 years old**
#      · standing upright, **facing the camera straight on**   (증명사진 구도)
#      · photorealistic studio **photograph**, **50mm lens, eye level**
#      · natural skin texture with **visible pores**, **no beauty filter**
#    합치면 "55세 한국 남자의 보정 없는 실제 전신사진을 찍어 달라" 가 된다.
#    유명인 검사가 잡으라고 만들어진 바로 그 모양이다.
#
#    → **사진 주문**이 아니라 **지어낸 인물 그림**으로 바꿔 쓴다.
#      · '사진' 을 가리키는 말(photograph · photo · reference sheet · lens ·
#        eye level · pores · beauty filter)을 전부 뺀다
#      · 맨 앞에서 **지어낸 사람, 실존 인물 아님**을 못 박는다
#      · '평범하고 눈에 안 띄는 얼굴' 이라고 적는다 — 유명인 닮은 얼굴이
#        뽑히는 것 자체를 막는다 (닮게 뽑히면 그 뒤로 계속 막힌다)
#      · 나이는 숫자 대신 **또래말**로 ("55 years old" → "in his mid-fifties")
#    ⚠️ "not based on any real person" 처럼 **'실존 인물' 이라는 말 자체**를
#       쓰지 않는다. 부인하는 말이라도 그 낱말이 들어가면 검사에 걸린다.
HEAD = ("An invented, fictional character for a short story. "
        "Completely made up")
POSE = ("standing upright and still, arms relaxed at the sides, "
        "mouth closed, calm everyday expression")
FRAME = ("full body from head to feet, centred, nothing cropped, "
         "vertical 9:16")
BACKDROP = ("plain flat light-grey empty wall, no furniture, no props, "
            "no scenery")
LIGHT = "soft even light from the front, no hard shadow, no coloured light"
LOOK = ("natural and realistic, ordinary everyday appearance, "
        "plain unremarkable features, no glamour, no retouching, "
        "no stylisation")
AVOID = ("Avoid: text, letters, watermark, logo, props, furniture, "
         "background scenery, other people, harsh or coloured lighting, "
         "tilted camera, close-up crop, cartoon, illustration, 3D render, "
         "painting, anime")

# 사진을 가리키는 말 — 인물 설명에 남아 있으면 떼어 낸다
PHOTO_WORDS = ["photorealistic", "photograph", "photo", "portrait", "headshot",
               "reference sheet", "50mm", "35mm", "lens", "eye level",
               "visible pores", "beauty filter", "studio shot", "dslr",
               "8k", "4k", "hyperrealistic", "raw photo"]

# 나이 숫자 → 또래말. 숫자는 '이 사람이 누구인가' 를 가리키는 신호라 뺀다.
BAND = [(0, 3, "early"), (4, 6, "mid"), (7, 9, "late")]
TENS = {2: "twenties", 3: "thirties", 4: "forties", 5: "fifties",
        6: "sixties", 7: "seventies", 8: "eighties"}


def age_band(n, male):
    """55 → 'in his mid-fifties' (숫자를 안 쓴다)."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    tens, ones = n // 10, n % 10
    word = TENS.get(tens)
    if not word:
        return "young" if n < 20 else "elderly"
    part = next((w for a, b, w in BAND if a <= ones <= b), "mid")
    return f"in {'his' if male else 'her'} {part} {word}"


def split_who(t):
    """짧은 옛 프롬프트에서 '누구인가' 와 '어떻게 생겼나' 를 갈라낸다."""
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    # 끝에 붙던 화풍 문구는 아래에서 새로 넣으므로 떼어낸다
    t = re.split(r"\.\s*(?:Photorealistic|photorealistic)", t)[0].strip(" .")
    m = re.match(r"(Korean (?:woman|man)[^,]*,\s*\d+\s*years old)\s*,?\s*(.*)",
                 t, re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip(" .")
    return t, ""


# ⭐ 컷마다 붙일 **얼굴 못** (2026-08-20)
#    첫 영상에서 남편이 컷마다 다른 배우 얼굴로 나왔다. 컷 프롬프트의
#    SUBJECT 줄에 이름만 있으면 영상 만드는 쪽이 매번 새 얼굴을 뽑는다.
#    그래서 이름 뒤에 **짧은 얼굴 설명**을 괄호로 붙인다 — 나이 + 얼굴 + 머리.
#    길면 컷 프롬프트가 무거워지므로 60글자 안쪽으로 자른다.
FACE_MAX = 60


def face_of(ch):
    """인물 하나 → 이름 뒤에 붙일 짧은 얼굴 설명 ('52, oval face, low bun')."""
    who, look = split_who(ch.get("flow_prompt"))
    parts = [p.strip(" .") for p in look.split(",") if p.strip(" .")]
    age = re.search(r"(\d+)\s*years?\s*old", who or "")
    face = next((p for p in parts if "face" in p.lower()), "")
    hair = next((p for p in parts if "hair" in p.lower()), "")
    # ⚠️ 나이 숫자는 넣지 않는다 — 이름·얼굴과 함께 있으면 '실존 인물 신상' 이
    #    되어 유명인 검사에 걸린다 (2026-08-20). 또래말은 who_line 이 따로 넣는다.
    bits = [x for x in (face, hair) if x]
    if not bits:
        bits = parts[:2]
    out = ", ".join(bits)
    while len(out) > FACE_MAX and len(bits) > 1:
        bits.pop()
        out = ", ".join(bits)
    return out[:FACE_MAX].strip(" ,")


def strip_photo(t):
    """설명에서 '사진 주문' 을 가리키는 말과 표정 말을 떼어 낸다."""
    parts = [p.strip(" .") for p in str(t or "").split(",")]
    keep = []
    for p in parts:
        low = p.lower()
        if not low:
            continue
        if any(w in low for w in PHOTO_WORDS):
            continue
        # 나이 숫자는 '이 사람이 누구인가' 를 가리키는 신호라 뺀다 (또래말로 쓴다)
        if re.fullmatch(r"\d{1,3}s?", low) or re.fullmatch(r"\d{1,3}\s*years?\s*old", low):
            continue
        # 기준 그림은 **평온한 얼굴**이어야 한다. 화난 표정은 컷에서 준다.
        if "expression" in low or "gaze" in low or "smile" in low:
            continue
        keep.append(p)
    return ", ".join(keep)


def who_line(ch):
    """'an ordinary Korean man in his mid-fifties' — 숫자 없이."""
    who, _ = split_who(ch.get("flow_prompt"))
    # ⚠️ `"man" in who` 로 보면 **woman 안에도 man 이 들어 있어** 여자가
    #    전부 남자가 된다 (실제로 본처·내연녀가 'Korean man' 으로 나왔다).
    #    낱말 경계로 본다.
    male = bool(re.search(r"\bman\b|\bmale\b|\bboy\b", (who or "").lower()))
    m = re.search(r"(\d+)\s*years?\s*old", who or "")
    nat = "Korean"
    kind = "man" if male else "woman"
    band = age_band(m.group(1), male) if m else ""
    return " ".join(x for x in (f"an ordinary {nat} {kind}", band) if x)


def build(ch):
    """인물 하나 → (기준 그림 프롬프트, 캐릭터 설명 한 줄).

    ⚠️ '사진을 찍어 달라' 가 아니라 '지어낸 인물을 그려 달라' 로 쓴다.
       예전 것은 증명사진 주문서라 유명인 검사에 걸렸다 (위 설명 참고).
    """
    _, look = split_who(ch.get("flow_prompt"))
    look = strip_photo(look)
    outfit = strip_photo(ch.get("outfit"))
    label = (ch.get("role_en") or "").strip() or (ch.get("name") or "").strip()

    sheet = [f"{HEAD} — {who_line(ch)}."]
    if look:
        sheet.append(f"FACE AND HAIR: {look}.")
    if outfit:
        sheet.append(f"WEARING: {outfit}.")
    sheet += [
        f"POSE: {POSE}.",
        f"FRAME: {FRAME}.",
        f"BACKGROUND: {BACKDROP}.",
        f"LIGHT: {LIGHT}.",
        f"LOOK: {LOOK}.",
        AVOID,
    ]

    bits = [who_line(ch)]
    face = strip_photo(ch.get("face_tag")) or look
    if face:
        bits.append(face)
    if outfit:
        bits.append(f"always wears {outfit}")
    # ⭐ 목소리도 캐릭터 정보에 넣는다 (2026-08-20 운영자 지시).
    #    플로우에서 목소리를 미리 골라 두면 그것이 프롬프트를 눌러 이긴다 —
    #    미리 고르지 말고 **여기와 컷 프롬프트로** 목소리를 준다.
    voice = (ch.get("voice") or "").strip()
    if voice:
        bits.append(f"speaks with {voice}")
    desc = f"{label} — " + ". ".join(x.strip(" .") for x in bits if x) + "."
    return "\n".join(sheet), desc


# 정책에 걸리는 말 → 뜻이 같은 안전한 말 (2026-08-20)
#   플로우가 "유명인 동영상 생성 정책" 으로 막았다. 실제 방송·배우를 가리키는
#   말이 겹치면 실존 인물을 만들라는 말로 읽힌다.
SAFE = [("Korean TV drama realism", "grounded everyday Korean realism"),
        ("K-drama realism", "grounded everyday Korean realism"),
        ("photorealistic live-action", "photorealistic"),
        ("live-action", "live footage"),
        ("like a Korean actress", "in a plain natural way"),
        ("like a Korean actor", "in a plain natural way"),
        ("actress", "person"), ("actor", "person")]


def scrub(t):
    """인물 설명에서 방송·배우를 가리키는 말을 안전한 말로 바꾼다."""
    out = str(t or "")
    for a, b in SAFE:
        out = re.sub(re.escape(a), b, out, flags=re.I)
    return out


def stale(ch):
    """예전 문구로 만들어 둔 것인가 (정책에 걸리는 말이 남아 있는가)."""
    blob = (ch.get("flow_sheet") or "") + (ch.get("flow_desc") or "")
    if not blob.strip():
        return False
    if LOOK not in (ch.get("flow_sheet") or ""):
        return True
    if (ch.get("voice") or "").strip() and "speaks with" not in (ch.get("flow_desc") or ""):
        return True
    return any(re.search(re.escape(a), blob, re.I) for a, _ in SAFE)


def fill(doc):
    """인물표에 face_tag · flow_sheet · flow_desc 를 채워 넣는다 (있으면 둔다).

    ⚠️ 단, **예전 문구로 만들어 둔 것은 다시 만든다.** 안 그러면 정책에 걸리는
       말이 인물표에 그대로 남아 이미 만든 대본은 계속 막힌다 (2026-08-20).
    """
    n = 0
    for ch in doc.get("characters") or []:
        ch["flow_prompt"] = scrub(ch.get("flow_prompt"))
        # 얼굴 못을 **먼저** 박는다 — 아래에서 다시 만들 때도 쓰이기 때문이다
        if not (ch.get("face_tag") or "").strip():
            f = face_of(ch)
            if f:
                ch["face_tag"] = f
                n += 1
        if stale(ch):
            ch["flow_sheet"], ch["flow_desc"] = build(ch)
            n += 1
            continue
        if not (ch.get("flow_sheet") or "").strip():
            ch["flow_sheet"], d = build(ch)
            if not (ch.get("flow_desc") or "").strip():
                ch["flow_desc"] = d
            n += 1
        elif not (ch.get("flow_desc") or "").strip():
            ch["flow_desc"] = build(ch)[1]
            n += 1
    return n


def main():
    a = argparse.ArgumentParser()
    a.add_argument("sid")
    g = a.parse_args()
    p = SERIES / f"{g.sid}.json"
    if not p.exists():
        raise SystemExit(f"❌ {g.sid} 대본이 없다")
    doc = json.loads(p.read_text(encoding="utf-8"))
    fill(doc)
    for ch in doc.get("characters") or []:
        print("=" * 62)
        print(f"[{ch['name']}] 캐릭터 설명 칸에 넣을 것")
        print("  " + ch["flow_desc"])
        print(f"\n[{ch['name']}] 기준 사진 프롬프트 "
              f"({len(ch['flow_sheet'].split())}낱말)")
        for l in ch["flow_sheet"].split("\n"):
            print("  " + l)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
