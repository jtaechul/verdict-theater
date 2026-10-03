#!/usr/bin/env python3
"""⭐ 받아쓰기 점검 — 완성 영상의 소리를 AI 가 **한 번** 받아 적고, 대본의 숫자·이름이
   그대로 읽혔는지 본다 (한 번 약 15원 · 손으로만 · 값은 장부에)

    python3 tools/listen_check.py S94

⭐ 2026-10-02 (S94 v5) — 목소리 모델이 지시문을 소리 내어 읽거나(컷18 · 25자가 15초) 숫자를
   달리 읽으면 자막과 소리가 어긋난다. 눈으로 보는 검수(drama60 sheet)로는 못 잡는다
   → 귀로 한 번 듣는다. S94 v5 는 연도·금액·이름이 대본 그대로 들렸다 (약 15원).
   ⚠️ gemini-2.5-flash 는 약한 끝소리(…요·…라)를 자주 빼먹는다 — gemini-3.5-flash 로 듣는다.
   ⚠️ 값이 나간다 — 자체 점검(checkall)에 넣지 않는다. 숫자 비교만 열쇠 없이 시험한다.
"""
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

BASE = "https://generativelanguage.googleapis.com/v1beta"
MODEL = os.environ.get("LISTEN_MODEL", "gemini-3.5-flash")
ASK = ("이 소리는 한국어 쇼츠 영상입니다. 배경음악은 무시하고, 들리는 한국어 말을 **들리는 그대로** "
       "빠짐없이 받아 적으세요. 고치거나 다듬지 말고, 숫자는 들린 대로(예: 천구백육십구 년 → 1969년) "
       "아라비아 숫자로 적으세요. 한 문장마다 한 줄, 줄 앞에 [분:초] 를 붙이세요.")
# 숫자 + 한국어 단위 (1억 5천만 · 4천만 · 1969 · 40여) — 띄어쓰기·쉼표는 먼저 지운다
NUM = re.compile(r"\d+(?:억|천만|백만|만|천|백)?(?:\d+(?:천만|백만|만|천|백))*")


def flat(t):
    return re.sub(r"[\s,]", "", str(t or ""))


def numbers_of(text):
    """대본·받아쓰기에서 숫자 덩어리 — 한 자리 숫자(1심 · 3번)는 어디에나 맞으니 뺀다."""
    return [m for m in NUM.findall(flat(text)) if len(m) > 1]


def compare(doc, heard):
    """(숫자 놓친 것, 이름 놓친 것) — 대본 말(나레이션·대사)의 숫자·가명이 받아쓰기에 있는가."""
    said = " ".join(str(c["turns"][0][1]) for c in doc.get("cuts") or [] if c.get("turns"))
    h = flat(heard)
    nums = [x for x in dict.fromkeys(numbers_of(said)) if x not in h]
    names = [str(p.get("alias")) for p in doc.get("cast") or []
             if p.get("alias") and str(p.get("alias")) in said and flat(p.get("alias")) not in h]
    return nums, names


def listen(mp4):
    import cost                                                # noqa: E402
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise SystemExit("❌ GEMINI_API_KEY 가 없다")
    with tempfile.TemporaryDirectory() as t:
        a = Path(t) / "a.mp3"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4), "-vn", "-ac", "1",
                        "-ar", "16000", "-b:a", "48k", str(a)], check=True)
        data = base64.b64encode(a.read_bytes()).decode()
    body = {"contents": [{"parts": [{"inlineData": {"mimeType": "audio/mp3", "data": data}},
                                    {"text": ASK}]}],
            "generationConfig": {"temperature": 0.0}}
    req = urllib.request.Request(f"{BASE}/models/{MODEL}:generateContent?key={key}",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    got = json.loads(urllib.request.urlopen(req, timeout=300).read())
    text = got["candidates"][0]["content"]["parts"][0]["text"]
    u = got.get("usageMetadata") or {}
    tin = int(u.get("promptTokenCount") or 0)
    tout = int(u.get("candidatesTokenCount") or 0) + int(u.get("thoughtsTokenCount") or 0)
    won = cost.krw(MODEL, tin, tout)
    cost.record("검토", won, f"받아쓰기 점검 {Path(mp4).name} (목소리가 대본대로인지)")
    return text, won


def main():
    if len(sys.argv) < 2 or not re.fullmatch(r"[Ss]\d{1,4}", sys.argv[1]):
        print(__doc__)
        return 2
    sid = sys.argv[1].upper()
    doc = json.loads((ROOT / "data" / "series" / f"{sid}.json").read_text(encoding="utf-8"))
    mp4 = ROOT / "build" / "s90" / f"{sid}_part1.mp4"
    if not mp4.exists():
        print(f"❌ 영상이 없다: {mp4.relative_to(ROOT)} — drama60 build 를 먼저")
        return 2
    text, won = listen(mp4)
    out = mp4.with_name(mp4.stem + ".listen.txt")
    out.write_text(text + "\n", encoding="utf-8")
    print(text)
    nums, names = compare(doc, text)
    print("─" * 56)
    print(f"■ 값 약 {won:,.1f}원 (장부에 적었다) · 받아쓰기 {out.relative_to(ROOT)}")
    if nums or names:
        print(f"⚠️ 대본과 다르게 들린 것 — 숫자 {nums or '없음'} · 이름 {names or '없음'}")
        print("   그 컷을 직접 들어 본다 (받아쓰기가 틀렸을 수도 있다)")
        return 1
    print("✅ 대본의 숫자·이름이 전부 그대로 들렸다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
