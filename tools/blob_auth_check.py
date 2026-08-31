#!/usr/bin/env python3
"""보관함에서 **받아 가는 길**이 실제로 열려 있는가 (값 0원 · 인터넷 0회)

    python3 tools/blob_auth_check.py

⚠️⚠️ 2026-08-30 — 이 검사가 없어서 90초 편 첫 실행이 통째로 실패했다.
   손님이 관리자 페이지에서 인물 그림 다섯 장을 올리셨는데, 워크플로가 그것을
   받아 가는 순간 튕겼다. 원인이 **둘**이었다.

     ① tools/fetch_cards.py 가 암호(x-vt-pass)를 안 보냈고,
        워크플로도 ADMIN_PASS 를 안 넘기고 있었다.
     ② 보관함 열쇠에 한글이 들어 있었다('cards/S90-본처-…').
        /api/blob 은 열쇠를 [A-Za-z0-9._-] 로만 받는다 → 한글은 400.

   둘 다 **눈으로는 안 보이는 어긋남**이다. 그래서 글자로 맞춰 본다.
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


def main():
    print("⭐ 보관함에서 받아 가는 길 점검 (값 0원)\n")
    w = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")

    # ⚠️⚠️ 2026-08-31 — 이 목록을 **손으로 적어 두었더니** 새로 만든
    #    tools/fetch_meta90.py 가 빠졌고, 유튜브 올리기가 401 로 죽었다.
    #    똑같은 실수를 이틀 만에 두 번 했다. → 이제 **찾아서** 본다.
    #    보관함 주소를 받아 가는 파일이 새로 생기면 저절로 검사에 들어온다.
    print("① 받아 갈 때 암호를 보내는가")
    grab = sorted(str(f.relative_to(ROOT)) for f in (ROOT / "tools").glob("fetch_*.py"))
    print(f"      보관함에서 받아 가는 파일 {len(grab)}개: {', '.join(grab)}")
    for f in grab:
        t = (ROOT / f).read_text(encoding="utf-8")
        # ⚠️ 주석에 적힌 것은 안 센다. "설명만 남고 코드가 빠진" 꼴을 잡아야 한다
        code = "\n".join(l for l in t.splitlines() if not l.lstrip().startswith("#"))
        ck(f"{f} 가 x-vt-pass 를 보낸다", "x-vt-pass" in code, "암호 없이 부르면 튕긴다")
        ck(f"{f} 에 맨몸 urlopen(url 이 남아 있지 않다",
           not re.search(r"urlopen\(\s*url\b", t), "그 줄은 암호를 안 보낸다")

    print("\n② 돈 쓰는 워크플로가 그 암호를 넘기는가")
    for y in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        t = y.read_text(encoding="utf-8")
        # 위에서 찾은 파일 중 **하나라도** 부르는 워크플로면 암호가 있어야 한다
        if not any(Path(g).name in t for g in grab):
            continue
        ck(f"{y.name} 가 ADMIN_PASS 를 넘긴다",
           "ADMIN_PASS" in t, "받아 가는 단계가 암호 없이 돈다")

    print("\n③ 올릴 때 만든 열쇠를 받을 때 받아 주는가")
    m = re.search(r"if \(!/(.+)/\.test\(key\)\)", w)
    ck("/api/blob 의 열쇠 규칙을 찾았다", bool(m), "규칙이 바뀌었다 — 검사를 고쳐라")
    if not m:
        return 1
    rule = re.compile(m.group(1).replace("\\/", "/"))   # 자바스크립트 꼴 → 파이썬 꼴
    # 워커가 만드는 보관함 열쇠 꼴을 그대로 뽑아 맞춰 본다
    keys = re.findall(r"`((?:cards|clips|meta|zip)/[^`]*)`", w)
    ck("만드는 열쇠가 하나라도 있다", bool(keys), "열쇠 만드는 자리를 못 찾았다")
    uid = "0123abcd-4567-89ef-0123-456789abcdef"
    for k in sorted(set(keys)):
        # ${...} 자리를 실제로 들어갈 값으로 바꿔 본다
        sample = k
        sample = re.sub(r"\$\{crypto\.randomUUID\(\)\}", uid, sample)
        sample = re.sub(r"\$\{S90_KEY\[[^\]]+\]\}", "wife", sample)
        sample = re.sub(r"\$\{who\}", "본처", sample)          # 한글이 들어가던 자리
        sample = re.sub(r"\$\{[^}]*\}", "x1", sample)
        ck(f"열쇠 `{k}` 를 받아 준다", bool(rule.match(sample)), f"→ {sample}")

    print("\n" + "─" * 60)
    if BAD:
        print("❌ 걸린 것:")
        for b in BAD:
            print("     " + b)
        return 1
    print("✅ 보관함 길 점검: 전부 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
