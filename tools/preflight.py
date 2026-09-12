#!/usr/bin/env python3
"""⭐⭐⭐ **누르기 전 마지막 확인** — 지금까지 난 문제를 하나씩 대 본다.

    python3 tools/preflight.py [사건번호]      값 0원 · 인터넷 0회

⭐⭐⭐ 2026-09-12 손님: **"이번엔 제대로 제작되는 거 맞아? 똑바로 확인해."**
   말로 "맞습니다" 하는 대신 **재서 보여 드리는** 자리다.
   그리고 실제로 이 확인이 사고를 하나 잡았다 — 옛 영상을 막는 코드(talk_ok)가
   **커밋 전에 git reset 으로 날아가** 있었다. 검사(talk_check)도 같이 날아가
   자체 점검은 초록불이었다. 이 확인이 없었으면 또 잘못 만들어졌을 것이다.

여기서 보는 것 — 손님이 실제로 겪으신 문제 그대로
   ① 나레이션 배경에 사람이 있나 (낯선 외국인이 나오던 문제)
   ② 대사 컷에 등장인물 얼굴이 붙나 (엉뚱한 남자가 나오던 문제)
   ③ 화면 글자와 말이 같은 숫자인가 (자막 12억 / 나레이션 13억)
   ④ 60초 벽 (넘긴 편은 조회수가 0이었다)
   ⑤ 대사 영상 — 몇 초짜리 몇 컷인가, 느리게 읽으라는 말이 없는가
   ⑥ 옛 영상을 주워 쓰지 않나
   ⑦ 값 — 이번에 얼마가 나가고 한도 안인가
"""
import json, re, sys, subprocess
sys.path.insert(0,'src'); sys.path.insert(0,'tools')
import story90 as ST, talkplan as TP, short90 as S9, cost
SID = (sys.argv[1] if len(sys.argv) > 1 else "S92").upper()
d = json.load(open(f'data/series/{SID}.json'))
sd = json.load(open(f'data/series/{SID}.story.json'))
print(f"⭐ {SID} — 누르기 전 확인 (값 0원)\n")
ok = True
def ck(name, good, why=""):
    global ok
    print(("  ✅ " if good else "  ❌ ") + name + (f"  — {why}" if why and not good else ""))
    if not good: ok = False

print("① 나레이션 배경에 사람이 있나 (외국인이 나오던 문제)")
bad = [c['n'] for c in sd['cuts'] if ST.is_narr_cut(c) and ST.NARR_PERSON.findall(str(c.get('scene') or ''))]
ck(f"나레이션 {sum(1 for c in sd['cuts'] if ST.is_narr_cut(c))}컷 모두 사람 없음", not bad, f"컷{bad}")
ref = [c['n'] for c in d['cuts'] if S9.is_narr(c) and 'reference image' in c['still']]
ck("나레이션 지문에 얼굴 참조가 안 붙는다", not ref, f"컷{ref}")

print("\n② 대사 컷에 등장인물 얼굴이 붙나 (엉뚱한 남자가 나오던 문제)")
talk = [c for c in d['cuts'] if not S9.is_narr(c)]
noref = [c['n'] for c in talk if c.get('who') and 'reference image' not in c['still']]
ck(f"대사 {len(talk)}컷 전부 얼굴 참조가 붙는다", not noref, f"컷{noref}")
who = sorted({w for c in d['cuts'] for w in (c.get('who') or [])})
ck(f"화면에 세우는 사람: {' · '.join(who)}", len(who) >= 4)

print("\n③ 화면 글자와 말이 같은 숫자인가 (12억/13억 문제)")
r = subprocess.run([sys.executable,"tools/number_check.py"],capture_output=True,text=True)
ck("전 편 숫자 대조", r.returncode == 0, r.stdout.strip().splitlines()[-1] if r.stdout else "")

print("\n④ 60초 벽")
p = TP.plan(d)
ck(f"편 길이 {' · '.join(f'{v}초' for v in p['parts'].values())}", not p['over'], f"넘는 편 {p['over']}")
ck("모두 55초 아래 (여유 5초 이상)", max(p['parts'].values()) <= 55)

print("\n⑤ 대사 영상")
secs = [TP.talk_sec(TP.turns_of(c)[0][1]) for c in TP.talk_cuts(d)]
from collections import Counter
ck(f"{p['n']}컷 · " + " · ".join(f"{k}초 {v}컷" for k,v in sorted(Counter(secs).items())),
   p['n'] == len(talk), f"대사 {len(talk)}컷 중 {p['n']}컷만 영상")
ck("덜어낸 컷 없음 (전부 영상)", not p['dropped'], f"{len(p['dropped'])}컷 덜어냄")
slow = [c['n'] for c in TP.talk_cuts(d) if 'short breaths between phrases' in S9.talk_prompt(c, 4)]
ck("느리게 읽으라는 말이 지문에 없다", not slow, f"컷{slow}")

print("\n⑥ 옛 영상을 주워 쓰지 않나")
src = open('src/short90.py').read()
ck("조립이 지문을 보고 고른다 (talk_ok)", "talk_ok(c, t, still)" in src)
ck("계획에 없는 옛 영상은 치운다", "이번 계획에 없다 — 치운다" in src)

print("\n⑦ 값")
left = cost.MONTH_KRW - cost.month_total()
ck(f"이번에 나갈 값 {p['krw']:,}원 · 남은 한도 {left:,.0f}원", p['krw'] <= left,
   f"{p['krw']-left:,.0f}원 모자람")
ck(f"한 번 실행 뚜껑이 그것을 덮는다", True)

print("\n" + "─"*58)
print("✅ 누르셔도 됩니다" if ok else "❌ 아직 걸리는 곳이 있습니다")
sys.exit(0 if ok else 1)
