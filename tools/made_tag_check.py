#!/usr/bin/env python3
"""만든 영상이 **관리자 페이지 목록에 실제로 뜨는가** (값 0원 · 인터넷 0회)

    python3 tools/made_tag_check.py

⚠️⚠️ 2026-08-31 — 이 검사가 없어서 손님이 만든 영상을 못 보셨다.
   90초 편 만들기는 성공했는데 화면에 아무것도 안 떴다. 까닭은
   **워크플로가 붙이는 이름과 화면이 찾는 이름이 달랐기** 때문이다.

     워크플로  release_file.py put short90-S90 short.mp4
     화면      /^short-(S\\d{3})-ep(\\d{2})…$/   ← 90초 편은 안 걸린다

   양쪽 다 멀쩡해 보이는데 가운데가 끊긴 고장이라 눈으로는 안 보인다.
   그래서 **워크플로가 붙이는 이름을 뽑아, 화면 규칙에 넣어 본다.**
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BAD = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + ("" if ok else f"  ({why})"))
    if not ok:
        BAD.append(name)


def js_re(src):
    """자바스크립트 정규식 글자를 파이썬 것으로 바꾼다."""
    return re.compile(src.replace("\\/", "/").replace("(?:", "(?:"))


def main():
    print("⭐ 만든 영상이 목록에 뜨는가 (값 0원)\n")
    w = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")

    # 화면(/api/shorts)이 tag_name 에 대 보는 규칙을 전부 뽑는다
    body = w[w.index("'/api/shorts'"):]
    body = body[:body.index("return Response.json({ items })")]
    rules = [js_re(x) for x in re.findall(r"match\(/(.+?)/\)", body)]
    ck("화면이 쓰는 이름 규칙을 찾았다", bool(rules), "규칙이 바뀌었다 — 검사를 고쳐라")
    if not rules:
        return 1
    print(f"      규칙 {len(rules)}개: " + " · ".join(r.pattern for r in rules))

    # 워크플로가 붙이는 이름을 뽑는다 (완성 영상만 — short.mp4 를 올리는 것)
    print("\n■ 워크플로가 붙이는 이름")
    tags = []
    for y in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for tag in re.findall(r"release_file\.py put (\S+) short\.mp4", y.read_text(encoding="utf-8")):
            tags.append((y.name, tag))
    ck("완성 영상을 올리는 워크플로가 있다", bool(tags), "put … short.mp4 를 못 찾았다")

    # 이름에 든 셸 변수를 **실제로 들어갈 값**으로 바꿔 본다.
    #   ⚠️ 못 맞히는 변수는 실패로 치지 않는다 — 애먼 빨간불은 검사를 못 믿게 만든다.
    KNOWN = {"SID": "S001", "EP": "01", "SUF": "", "CUT": "", "N": "1"}
    for yml, tag in tags:
        text = (ROOT / ".github" / "workflows" / yml).read_text(encoding="utf-8")
        var = dict(KNOWN)
        for k, v in re.findall(r'^\s*([A-Z_]+)="?([^"\n]*)"?\s*$', text, re.M):
            var.setdefault(k, v)
        sample = tag.strip('"')
        for _ in range(3):                      # 변수 안에 변수가 또 있다
            sample = re.sub(r"\$\{\{[^}]*\}\}", "S001", sample)
            sample = re.sub(r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?",
                            lambda m: var.get(m.group(1), m.group(0)), sample)
        if "$" in sample:
            print(f"   ⏭  {yml}: `{tag}` — 이름을 못 맞혀 건너뛴다 (→ {sample})")
            continue
        hit = any(r.match(sample) for r in rules)
        ck(f"{yml}: `{tag}` 를 화면이 찾아 준다", hit, f"→ {sample} 이 어느 규칙에도 안 걸린다")

    print("\n" + "─" * 60)
    if BAD:
        print("❌ 걸린 것:")
        for b in BAD:
            print("     " + b)
        return 1
    print("✅ 만든 영상 목록 점검: 전부 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
