#!/usr/bin/env python3
"""⭐ 처음 보는 시청자 시험 — AI 가 60대 시청자로 영상을 **한 번** 보고 답한다 (한 번에 약 10~20원)

    python3 tools/viewer_test.py build/s90/S94_part1.mp4

⭐⭐⭐ 2026-10-02 손님: "처음보는 사람이 보아도 스토리 전개를 이해하고 공감할 수 있도록 만들어야해."
   만든 사람은 이야기를 이미 알아서 무엇이 헷갈리는지 못 본다. 그래서 영상을 처음 보는
   눈으로 보게 하고 ① 이해한 줄거리 ② 인물 관계 ③ 헷갈린 순간(초) ④ 공감 ⑤ 넘기고 싶던 곳
   ⑥ 고칠 점 ⑦ 이해·공감 점수 를 받는다. S94 실측: v1 은 관계·돈의 성격·연도 순서에서
   걸렸고, 관계 자막·연도·인과 한 줄을 넣은 v2 는 네 사람 관계를 다 맞혔다.
   ⚠️ 점수는 실행마다 1~2점 흔들린다 — 점수보다 **헷갈린 순간 목록**을 본다.
   ⚠️ 값이 나간다 — 손으로만 돈다 (자체 점검에 넣지 않는다). 값은 장부에 적는다.
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import cost                                                   # noqa: E402

BASE = "https://generativelanguage.googleapis.com/v1beta"
MODEL = os.environ.get("VIEWER_MODEL", "gemini-3.5-flash")
ASK = """당신은 이 이야기를 처음 보는 60대 한국인 시청자입니다. 유튜브 쇼츠로 이 영상을 딱 한 번 봤습니다.
솔직하게 한국어로 답하세요.
1) 내가 이해한 줄거리를 3~5문장으로 (모르는 부분은 '모르겠다'고 쓰세요)
2) 등장인물마다 누구인지, 서로 어떤 관계인지 (확실하지 않으면 '헷갈림')
3) 보다가 헷갈리거나 이해가 안 된 순간을 몇 초쯤인지와 장면/대사와 함께 전부 (없으면 '없음')
4) 주인공에게 공감이 됐는지, 왜 그런지
5) 끝까지 볼 마음이 들었는지, 몇 초쯤에서 넘기고 싶었는지
6) 이해와 공감을 높이려면 무엇을 바꾸면 좋을지 구체적으로 3가지
7) 이해도 점수 0~10, 공감 점수 0~10"""


def small(mp4, out):
    """보내기 가벼운 사본 (360×640 · 초당 15장 · 홑소리) — 원본은 손대지 않는다."""
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4), "-vf", "scale=360:640",
                    "-r", "15", "-c:v", "libx264", "-crf", "32", "-preset", "veryfast",
                    "-c:a", "aac", "-b:a", "64k", "-ac", "1", str(out)], check=True)
    return out


def ask(mp4):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise SystemExit("❌ GEMINI_API_KEY 가 없다")
    with tempfile.TemporaryDirectory() as t:
        data = base64.b64encode(small(mp4, Path(t) / "v.mp4").read_bytes()).decode()
    body = {"contents": [{"parts": [{"inlineData": {"mimeType": "video/mp4", "data": data}},
                                    {"text": ASK}]}],
            "generationConfig": {"temperature": 0.4}}
    req = urllib.request.Request(f"{BASE}/models/{MODEL}:generateContent?key={key}",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    got = json.loads(urllib.request.urlopen(req, timeout=300).read())
    text = got["candidates"][0]["content"]["parts"][0]["text"]
    u = got.get("usageMetadata") or {}
    tin = int(u.get("promptTokenCount") or 0)
    tout = int(u.get("candidatesTokenCount") or 0) + int(u.get("thoughtsTokenCount") or 0)
    won = cost.krw(MODEL, tin, tout)
    cost.record("검토", won, f"처음 보는 시청자 시험 {Path(mp4).name}")
    return text, won


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    mp4 = Path(sys.argv[1])
    if not mp4.exists():
        print(f"❌ 영상이 없다: {mp4}")
        return 2
    text, won = ask(mp4)
    out = mp4.with_name(mp4.stem + ".viewer.txt")
    out.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"\n■ 값 약 {won:,.0f}원 (장부에 적었다) · {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
