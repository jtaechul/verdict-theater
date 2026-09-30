#!/usr/bin/env python3
"""⭐ 새 방식 시험(인물 시트 + 옴니 입모양)이 약속대로 짜여 있는가 — 값 0원 · 인터넷 0회

    python3 tools/omni_check.py

2026-09-30 — 손님이 앱(구글 플로우)에서 옴니 시험을 하다 '유명인 정책' 으로
막혀 API 로 옮겼다 (src/omni.py · src/castsheet.py · tools/omni_test.py).
돈이 나가는 길이라 여기서 못을 박는다.

  ① 값      옴니 단가가 표에 있다 — 없으면 '모르는 이름' 값($0.40)으로 네 배를 센다
  ② 프롬프트 안전 검사 낱말 · '하지 마' 꼴 · 옷 묘사가 없다 (series 의 규칙 그대로)
            그림 역할을 맨 앞에 적었다 · 대사가 한 글자도 안 바뀌었다 · 길이를 글로 적었다
  ③ 시트    여자끼리 붙지 않는다 · 여섯 명까지 · 안전 검사 낱말이 없다
  ④ 칸 자르기 흰 틈이 있으면 그 자리를, 없으면 똑같이 나눈다 (가짜 시트로 재 본다)
  ⑤ 단추    관리자 페이지가 넘기는 선택지 글자가 워크플로와 한 글자도 안 틀린다
"""
import json
import re
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

import castsheet                                             # noqa: E402
import cost                                                  # noqa: E402
import omni                                                  # noqa: E402
import omni_test                                             # noqa: E402
import series                                                # noqa: E402

bad = []


def ck(name, ok, why=""):
    print(("   ✅ " if ok else "   ❌ ") + name + (f" — {why}" if why and not ok else ""))
    if not ok:
        bad.append(name)


print("⭐ 새 방식 시험 (인물 시트 + 옴니) 점검 — 값 0원")

# ── ① 값 ────────────────────────────────────────────────
k7 = cost.video_krw(omni.MODEL, 7)
ck("옴니 단가가 표에 있다 (7초 약 1,000~1,240원)",
   7 * 0.10 * cost.USD_KRW <= k7 <= 7 * 0.12 * cost.USD_KRW,
   f"7초가 {k7:,.0f}원으로 셈된다 — cost.VIDEO_USD_SEC 에 gemini-omni 가 없는가")
ck("실제 토큰 값 셈이 공시가와 맞는다 (7초 영상 40,544토큰 ≈ $0.71)",
   abs(omni.usage_krw({"output_tokens_by_modality": [{"modality": "video",
                                                        "tokens": 40544}]})
       - 40544 * 17.5 / 1e6 * cost.USD_KRW) < 1)

# ── ② 프롬프트 (대본마다) ─────────────────────────────────
docs = []
for f in sorted((ROOT / "data" / "series").glob("S*.json")):
    if re.fullmatch(r"S\d+\.json", f.name):
        d = json.loads(f.read_text(encoding="utf-8"))
        if d.get("characters") and any(omni_test.good_cut(c) for c in d.get("cuts", [])):
            docs.append((f.stem, d))
ck("시험할 대본이 하나 이상 있다", bool(docs))
for sid, d in docs:
    c = omni_test.pick(d)
    who, text = omni_test.turns_of(c)[0]
    gap = omni_test.cast_gap(d, c)
    if gap:
        # 인물 설계가 사건과 안 맞는 대본 — 엉뚱한 사람을 사기 전에 멈춰야 한다
        was = sys.argv
        sys.argv = ["omni_test.py", sid, "--dry"]
        try:
            rc = omni_test.main()
        finally:
            sys.argv = was
        ck(f"{sid}: 인물 설계에 없는 사람({', '.join(gap)})이면 돈 쓰기 전에 멈춘다",
           rc == 2, f"끝값 {rc}")
        continue
    sec = omni_test.plan_sec(text)
    for first in (True, False):
        p = omni_test.omni_prompt(d, c, sec, first=first)
        what = f"{sid} 컷{c['n']} 옴니 ({'첫 장면+참조' if first else '참조만'})"
        hits = series.risky_words(p) + series.negative_words(p) + series.wear_bait(p)
        ck(f"{what}: 걸리는 낱말·'하지 마'·옷 묘사가 없다", not hits, str(hits))
        ck(f"{what}: 그림 역할을 맨 앞에 적었다", p.startswith("[# "))
        ck(f"{what}: 대사가 한 글자도 안 바뀌었다", f'"{text}"' in p)
        ck(f"{what}: 길이를 글로 적었다 ({sec}초)", f"exactly {sec} seconds" in p)
        ck(f"{what}: 한국어로 말하게 했다", "[LANGUAGE: KOREAN]" in p)
    ck(f"{sid}: 길이가 옴니가 받는 범위다 (4~10초)", 4 <= sec <= 10, str(sec))
    sp = omni_test.still_prompt(c)
    ck(f"{sid} 컷 그림: 시트 칸에 한 사람이 두 번 나온다고 적었다",
       omni_test.TWICE.strip() in sp)

    # ── ③ 시트 ──
    ps = castsheet.order(castsheet.people(d, first=c.get("who") or []))
    sheet = castsheet.prompt(ps)
    ck(f"{sid} 시트: 여섯 명까지 ({len(ps)}명)", 1 <= len(ps) <= castsheet.MAX_CAST)
    ck(f"{sid} 시트: 칸마다 한 사람씩 적었다",
       all(f"COLUMN {i + 1}" in sheet for i in range(len(ps))))
    ck(f"{sid} 시트: 안전 검사 낱말이 없다", not series.risky_words(sheet),
       str(series.risky_words(sheet)))
    ck(f"{sid} 시트: 말하는 사람이 시트에 있다",
       castsheet.char_of(d, who) in ps, who)

# 여자끼리 붙지 않는다 (가짜 인물 다섯)
fake = [{"name": n, "flow_prompt": f"Korean {s}, 30 years old"}
        for n, s in (("가", "woman"), ("나", "woman"), ("다", "woman"),
                     ("라", "man"), ("마", "man"))]
line = [castsheet.sex_age(p)[0] for p in castsheet.order(fake)]
ck("시트: 여자 셋·남자 둘이면 여 남 여 남 여", line == ["woman", "man"] * 2 + ["woman"],
   str(line))

# ── ④ 칸 자르기 (가짜 시트) ─────────────────────────────
try:
    from PIL import Image, ImageDraw
    W, H, N = 1600, 900, 5
    shift = [0, 18, -14, 9, 0]           # 모델이 그은 틈은 똑같은 자리가 아니다
    gaps = [int(k * W / N) + shift[k] for k in range(1, N)]
    im = Image.new("RGB", (W, H), (205, 205, 205))
    dr = ImageDraw.Draw(im)
    edges = [0] + gaps + [W]
    for a, b in zip(edges, edges[1:]):   # 칸마다 사람(어두운 덩어리) 하나 — 칸을 거의 채운다
        dr.rectangle([a + 12, 60, b - 12, H - 40], fill=(60, 50, 45))
    for g in gaps:                       # 흰 틈
        dr.rectangle([g - 3, 0, g + 3, H], fill=(252, 252, 252))
    got = castsheet.cuts_of(castsheet.bg_share(im), N, W)
    ck("칸 자르기: 흰 틈을 찾아 그 자리를 쓴다 (똑같이 나눈 자리가 아니라)",
       got is not None and all(abs(x - g) <= 4 for x, g in zip(got, gaps)),
       f"찾은 자리 {got} · 틈 {gaps}")
    solid = Image.new("RGB", (W, H), (60, 50, 45))
    ck("칸 자르기: 틈이 없으면 똑같이 나눈다 (못 찾았다고 알린다)",
       castsheet.cuts_of(castsheet.bg_share(solid), N, W) is None)
    with tempfile.TemporaryDirectory() as t:
        p = Path(t) / "sheet.png"
        im.save(p)
        outs, how = castsheet.crop(p, N, t)
        ck("칸 자르기: 사람 수만큼 파일이 나온다",
           len(outs) == N and all(o.exists() for o, _ in outs), how)
except ImportError:
    ck("칸 자르기 시험 — 그림 라이브러리(pillow)가 있어야 한다", False,
       "selfcheck.yml 에서 pillow 를 까는지 보십시오")

# ── ⑤ 단추 글자 ─────────────────────────────────────────
wf = yaml.safe_load((ROOT / ".github" / "workflows" / "omni-test.yml")
                    .read_text(encoding="utf-8"))
on = wf.get("on") if isinstance(wf.get("on"), dict) else wf.get(True)
opts = on["workflow_dispatch"]["inputs"]["mode"]["options"]
js = (ROOT / "admin" / "worker.js").read_text(encoding="utf-8")
m = re.search(r"const mode = body && body\.fresh \? '([^']+)' : '([^']+)';", js)
ck("관리자 페이지가 넘기는 선택지가 워크플로에 한 글자도 안 틀리고 있다",
   bool(m) and m.group(1) in opts and m.group(2) in opts,
   f"페이지 {m.groups() if m else '못 찾음'} · 워크플로 {opts}")
raw = (ROOT / ".github" / "workflows" / "omni-test.yml").read_text(encoding="utf-8")
ck("워크플로가 선택지 글자대로 --fresh · --dry 를 붙인다",
   all(f'"$M" = "{o}"' in raw for o in opts[1:]))

print("─" * 56)
if bad:
    print(f"❌ {len(bad)}개 걸렸습니다 — 고치고 다시")
    sys.exit(1)
print("✅ 새 방식 시험: 값 · 프롬프트 · 시트 · 칸 자르기 · 단추 모두 약속대로")
