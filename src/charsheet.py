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

# 모든 인물에 똑같이 들어가는 것 — 이게 없어서 배경이 제멋대로 나왔다
POSE = ("standing upright, facing the camera straight on, arms relaxed at the "
        "sides, neutral calm expression, mouth closed")
FRAME = ("full body from head to feet, centered in frame, nothing cropped, "
         "vertical 9:16")
BACKDROP = ("plain flat light-grey studio backdrop, completely empty, "
            "no furniture, no props, no scenery")
LIGHT = ("soft even studio lighting from the front, no harsh shadow, "
         "no coloured light")
LOOK = ("photorealistic live-action photograph, 50mm lens, eye level, "
        "Korean TV drama realism, natural skin texture with visible pores, "
        "no beauty filter, no smoothing, no stylization")
AVOID = ("Avoid: text, letters, watermark, logo, props, furniture, background "
         "scenery, other people, hands doing anything, dramatic or coloured "
         "lighting, tilted camera, close-up crop, cartoon, illustration, "
         "3D render, painting, anime")


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
    bits = ([age.group(1)] if age else []) + [x for x in (face, hair) if x]
    if not bits:
        bits = parts[:2]
    out = ", ".join(bits)
    while len(out) > FACE_MAX and len(bits) > 1:
        bits.pop()
        out = ", ".join(bits)
    return out[:FACE_MAX].strip(" ,")


def build(ch):
    """인물 하나 → (기준 사진 프롬프트, 캐릭터 설명 한 줄)."""
    name = (ch.get("name") or "").strip()
    who, look = split_who(ch.get("flow_prompt"))
    outfit = (ch.get("outfit") or "").strip()
    face = (ch.get("face_tag") or "").strip()

    sheet = [f"Character reference photo of a {who}."]
    if look:
        sheet.append(f"APPEARANCE: {look}.")
    if outfit:
        sheet.append(f"WEARING: {outfit}.")
    sheet += [
        f"POSE: {POSE}.",
        f"FRAMING: {FRAME}.",
        f"BACKGROUND: {BACKDROP}.",
        f"LIGHT: {LIGHT}.",
        f"LOOK: {LOOK}.",
        AVOID,
    ]

    bits = [who]
    if face:
        bits.append(face)
    elif look:
        bits.append(look)
    if outfit:
        bits.append(f"always wears {outfit}")
    desc = f"{name} — " + ". ".join(x.strip(" .") for x in bits if x) + "."
    return "\n".join(sheet), desc


def fill(doc):
    """인물표에 face_tag · flow_sheet · flow_desc 를 채워 넣는다 (있으면 둔다)."""
    n = 0
    for ch in doc.get("characters") or []:
        if not (ch.get("face_tag") or "").strip():
            f = face_of(ch)
            if f:
                ch["face_tag"] = f
                n += 1
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
