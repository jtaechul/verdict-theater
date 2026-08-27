#!/usr/bin/env python3
"""**단추를 안 눌러도 저절로 돈이 나가는 길이 있는가** (0원 · 인터넷 0회 · 1초)

    python3 tools/auto_spend_check.py

⭐⭐⭐ 2026-08-27 손님: "우리가 안 쓰는 기능인데 돈이 세면 안 되잖아. 그렇지?"
    맞다. 그때까지 이랬다 —
      · video.yml (Veo 영상) 이 `.trigger/video` **파일 하나만 바뀌어도** 돌았다.
        그 파일은 저장소 안에 있어서, 딴 일로 커밋에 딸려 들어가기만 해도
        수천 원이 나갈 수 있었다.
      · series.yml (Claude 대본) · short90.yml (그림·소리) 도 같았다.
      · collect.yml · stats.yml 은 **매주 저절로** 돌았다 (값은 0원).

    → 돈이 나가는 워크플로는 **단추(workflow_dispatch)로만** 돌아야 한다.
      여기서 매번 확인한다. 새 워크플로가 이 규칙을 어기면 빨간불.

무엇을 돈 쓰는 것으로 보나
    유료 열쇠를 env 에 넣은 워크플로 — GEMINI_API_KEY(그림·영상) ·
    ANTHROPIC_API_KEY(글) · GOOGLE_TTS_KEY(소리) · TYPECAST_API_KEY(목소리)
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"

PAID = ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_TTS_KEY", "TYPECAST_API_KEY")
# 값이 0원인 것이 확실해 자동으로 돌아도 되는 것 (이유를 반드시 적는다)
FREE_OK = {
    "keycheck.yml": "열쇠가 살아 있는지만 본다 — 글자 몇 자(0.01원 미만)",
}


def on_block(text):
    """`on:` 부터 다음 최상위 칸까지 (여기에 자동 실행이 적힌다)."""
    m = re.search(r"^on:\n((?:[ \t].*\n|\n)*)", text, re.M)
    return m.group(1) if m else ""


def look(path):
    t = path.read_text(encoding="utf-8")
    paid = [k for k in PAID if re.search(r"^\s*[A-Z_]+:\s*\$\{\{\s*secrets\." + k,
                                         t, re.M)]
    on = on_block(t)
    auto = []
    if re.search(r"^  schedule:", on, re.M):
        auto.append("매주/매일 저절로 (schedule)")
    if re.search(r"^  push:", on, re.M):
        auto.append("커밋만 해도 (push)")
    if re.search(r"^  workflow_run:", on, re.M):
        auto.append("다른 워크플로가 끝나면 (workflow_run)")
    return paid, auto


def main():
    print("⭐ 저절로 돈이 나가는 길이 있는가 (값 0원)\n")
    bad, seen = [], 0
    for p in sorted(WF.glob("*.yml")):
        paid, auto = look(p)
        if not paid:
            continue
        seen += 1
        mark = "돈" if p.name not in FREE_OK else "0원"
        why = FREE_OK.get(p.name, "")
        if auto and p.name not in FREE_OK:
            bad.append(f"{p.name} — {', '.join(auto)} 로 저절로 돕니다 "
                       f"(유료 열쇠: {', '.join(paid)})")
            print(f"   ❌ {p.name:<18} {', '.join(auto)}")
        else:
            print(f"   ✅ {p.name:<18} 단추로만 돈다  [{mark}]"
                  + (f" — {why}" if why else ""))
    print()
    if bad:
        for b in bad:
            print("   ❌ " + b)
        print("\n" + "─" * 60)
        print("❌ 단추를 안 눌러도 돈이 나갈 수 있습니다 — 자동 실행을 빼십시오")
        return 1
    print("─" * 60)
    print(f"✅ 돈 쓰는 워크플로 {seen}개 — 전부 단추를 눌러야만 돕니다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
