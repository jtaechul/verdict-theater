#!/usr/bin/env python3
"""대본 JSON 을 사람이 읽는 모양으로 바꾼다.

    python3 src/preview.py data/scripts/EP001.json           전체
    python3 src/preview.py data/scripts/EP001.json --short    요약만

왜 필요한가
    대본은 컷 113개짜리 JSON 이다. 아이폰 GitHub 앱에서 이런 걸 읽는다.

        { "id": "A3-05", "sec": 6.0, "bg": "home_living_day",
          "chars": [{"code":"M50A","pose":"bust_cold", ...

    사람이 읽을 수 있는 물건이 아니다. 검수를 하려면 대사와 흐름이 보여야 한다.
    Actions 요약 화면에 이 출력을 그대로 넣어 아이폰에서 바로 읽게 한다.
"""

import argparse
import json
import sys
from pathlib import Path

SPEAKER_LABEL = {"narrator": "나레이션"}


def mmss(sec):
    return f"{int(sec) // 60}:{int(sec) % 60:02d}"


def name_of(doc, speaker):
    if speaker in SPEAKER_LABEL:
        return SPEAKER_LABEL[speaker]
    code = speaker.replace("v_", "")
    for c in doc.get("characters", []):
        if c.get("code") == code:
            return c.get("name", code)
    return code


def summary(doc):
    m = doc.get("meta", {})
    a = doc.get("anonymization", {})
    out = []
    out.append(f"# {m.get('episode', '')} {m.get('title_candidates', [''])[0]}")
    out.append("")
    out.append(f"> {m.get('logline', '')}")
    out.append("")
    out.append("| 항목 | 값 |")
    out.append("|---|---|")
    out.append(f"| 사건 유형 | {m.get('case_type', '')} |")
    out.append(f"| 컷 수 | {m.get('cut_count', 0)}개 |")
    total = sum(c.get("sec", 0) for act in doc.get("acts", []) for c in act.get("cuts", []))
    out.append(f"| 길이 | {mmss(total)} ({total:.1f}초) |")
    for x in a.get("amounts_used", []):
        out.append(f"| {x.get('label', '금액')} | {x.get('value', '')} |")
    laws = doc.get("law", {}).get("refs_from_case", [])
    out.append(f"| 인용 조문 | {', '.join(laws) if laws else '없음'} |")
    out.append("")
    out.append("**등장인물**")
    out.append("")
    for c in doc.get("characters", []):
        out.append(f"- {c.get('nametag', '')} — {c.get('note', '')}")
    return out


def highlights(doc):
    """검수할 때 가장 먼저 봐야 하는 세 곳."""
    out = ["", "## 먼저 볼 세 곳", ""]
    acts = {a["id"]: a for a in doc.get("acts", [])}

    hook = acts.get("hook", {}).get("cuts", [])
    if hook:
        c = hook[0]
        out.append(f"**3초 관문** — 첫 컷 {c.get('sec')}초")
        out.append("")
        out.append(f"> {name_of(doc, c.get('speaker', ''))}: 「{c.get('text', '')}」")
        out.append("")

    # 대본이 직접 표시해 둔 컷을 읽는다. 짐작하면 틀린다.
    c = tagged(doc, "anger_line") or shortest_line(acts.get("act3", {}))
    if c:
        out.append("**분노 대사** — 쇼츠 2번이 될 한 줄")
        out.append("")
        out.append(f"> {name_of(doc, c.get('speaker', ''))}: 「{c.get('text', '')}」")
        out.append("")

    c = tagged(doc, "verdict") or last_amount(acts.get("act4", {}))
    if c:
        out.append("**판결** — 금액이 박히는 순간")
        out.append("")
        out.append(f"> {c.get('text', '')}")
        out.append("")
    return out


def tagged(doc, tag):
    for act in doc.get("acts", []):
        for c in act.get("cuts", []):
            if c.get("tag") == tag:
                return c
    return None


def shortest_line(act):
    lines = [c for c in act.get("cuts", [])
             if c.get("speaker", "").startswith("v_") and c.get("text")]
    return min(lines, key=lambda x: len(x["text"])) if lines else None


def last_amount(act):
    hits = [c for c in act.get("cuts", []) if (c.get("gfx") or {}).get("type") == "amount"]
    return hits[-1] if hits else None


def shorts_block(sh):
    if not sh:
        return []
    out = ["", "## 쇼츠 3편", "", "| 번호 | 성격 | 길이 | 첫 자막 | 마무리 |", "|---|---|---|---|---|"]
    for s in sh.get("shorts", []):
        out.append(f"| {s.get('no')} | {s.get('kind', '')} | {s.get('est_sec', 0):.0f}초 | "
                   f"{s.get('intro_line', '')} | {s.get('outro_line', '')} |")
    return out


def full(doc):
    out = []
    for act in doc.get("acts", []):
        out.append("")
        out.append(f"## {act.get('title', act['id'])}  "
                   f"({mmss(act.get('start_sec', 0))}~{mmss(act.get('end_sec', 0))}, "
                   f"음악 {act.get('bgm', '')})")
        out.append("")
        for c in act.get("cuts", []):
            who = name_of(doc, c.get("speaker", ""))
            mark = []
            if c.get("flashback"):
                mark.append("회상")
            g = c.get("gfx") or {}
            if g:
                mark.append({"timeline": "연표", "family": "가족도",
                             "nametag": "이름표", "amount": "금액"}.get(g.get("type"), g.get("type")))
            tail = f"  _{' · '.join(mark)}_" if mark else ""
            if c.get("speaker") == "narrator":
                out.append(f"{c.get('text', '')}{tail}")
            else:
                out.append(f"**{who}** 「{c.get('text', '')}」{tail}")
            out.append("")
    return out


def render(doc, sh=None, short=False):
    lines = summary(doc) + highlights(doc) + shorts_block(sh)
    if not short:
        lines += ["", "---", ""] + full(doc)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--short", action="store_true", help="요약만 (Actions 화면용)")
    args = ap.parse_args()

    p = Path(args.path)
    doc = json.loads(p.read_text(encoding="utf-8"))
    shp = p.with_suffix("").with_suffix(".shorts.json")
    if not shp.exists():
        shp = p.parent / (p.stem + ".shorts.json")
    sh = json.loads(shp.read_text(encoding="utf-8")) if shp.exists() else None
    print(render(doc, sh, args.short))
    return 0


if __name__ == "__main__":
    sys.exit(main())
