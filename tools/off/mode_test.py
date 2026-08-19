#!/usr/bin/env python3
"""버튼의 모드마다 **돈 쓰는 단계가 딱 맞는 것만 도는지** 잰다. 인터넷 0회 · 0원.

    python3 tools/mode_test.py

왜 이 검사가 있는가 (2026-08-14)
    '도입 훅만 다시 쓰기' 버튼을 눌렀는데, 훅을 고친 **뒤에 본편 생성까지
    이어서 돌았다.** 아무도 시키지 않은 EP003 을 만들다 돈 한도에 걸려
    빨간 X — 719원이 그냥 나갔다.

    까닭: 돈 쓰는 단계의 조건이 "이 모드만 빼고 다"(빼기 목록)였는데,
    새 모드를 만들면서 빼기 목록에 안 넣었다. 빼기 목록은 **새 모드가 생길
    때마다 같은 사고가 난다** — CLAUDE.md 핵심규칙의 '길을 하나씩 막았다'
    바로 그 꼴이다. 그래서 허용 목록("이 모드일 때만")으로 바꿨고,
    이 검사가 그 꼴이 유지되는지 + 모드마다 도는 단계가 맞는지 잰다.

어떻게 재나
    ① 돈 쓰는 단계(VT_RUN_KRW 를 받는 단계)의 if 조건에 `mode !=` 가 없어야 한다.
       빼기 목록이 되살아나면 여기서 바로 걸린다.
    ② 조건에서 `mode == '…'` 로 적힌 허용 모드를 뽑아, 버튼의 모든 모드마다
       "이 모드를 고르면 어느 돈 단계가 도는가" 표를 만들어 기대와 대조한다.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows" / "script.yml"

# 모드 → 돌아야 하는 돈 단계 (이름의 앞부분으로 맞춘다)
# ⚠️ 새 모드를 만들면 **여기와 워크플로 둘 다** 적어야 한다. 하나만 적으면
#    이 검사가 빨간불을 내서, 옛날처럼 조용히 새는 일이 없다.
EXPECT = {
    "둘다": {"소재 심사", "대본 생성"},
    "소재 심사만": {"소재 심사"},
    "대본 생성만": {"대본 생성"},
    "이어서 마저 만들기": {"이어서 마저 만들기"},
    "쇼츠만 다시": {"쇼츠만 다시"},
    "도입 훅만 다시 쓰기": {"도입 훅만 다시 쓰기"},
}

ok = True


def bad(m):
    global ok
    ok = False
    print(f"   ❌ {m}")


def main():
    import yaml
    doc = yaml.safe_load(WF.read_text(encoding="utf-8"))
    job = doc["jobs"]["script"]
    # ⚠️ 처음엔 원문 정규식으로 뽑았다가 **writer 칸의 선택지까지 딸려 와서**
    #    '자동 (Claude 우선)' 같은 것을 모드로 오해했다. 구조로 읽는다.
    #    (yaml 은 'on' 을 True 로 읽으므로 키를 이름으로 찾지 않고 값을 뒤진다)
    trig = next(v for k, v in doc.items() if k in ("on", True))
    modes = trig["workflow_dispatch"]["inputs"]["mode"]["options"]
    if not modes:
        bad("워크플로에서 모드 목록을 못 읽었다")
        return 1

    money_steps = []
    for st in job["steps"]:
        env = st.get("env") or {}
        if "VT_RUN_KRW" in env:
            money_steps.append((st.get("name", "?"), str(st.get("if", ""))))

    print(f"⭐ 버튼 모드 {len(modes)}개 × 돈 쓰는 단계 {len(money_steps)}개 — 배선이 맞는가")
    print()

    print("① 돈 쓰는 단계의 조건이 **허용 목록**인가 (빼기 목록은 새 모드마다 샌다)")
    for name, cond in money_steps:
        if "mode !=" in cond:
            bad(f"'{name}' 조건에 'mode !=' 가 있다 — 빼기 목록이다. "
                "새 모드가 생기면 또 샌다. 'mode ==' 허용 목록으로 바꿔라")
        elif "inputs.mode" not in cond and "startsWith(inputs.mode" not in cond:
            bad(f"'{name}' 에 모드 조건이 아예 없다 — 모든 모드에서 돈이 나간다")
        else:
            print(f"   ✅ {name}: 허용 목록")

    print()
    print("② 모드마다 도는 돈 단계가 기대와 같은가")

    def runs(cond, mode):
        """이 모드를 고르면 이 단계가 도는가 — 조건에서 == 허용 모드만 뽑아 본다."""
        eqs = re.findall(r"inputs\.mode\s*==\s*'([^']+)'", cond)
        starts = re.findall(r"startsWith\(inputs\.mode,\s*'([^']+)'\)", cond)
        return mode in eqs or any(mode.startswith(p) for p in starts)

    for mode in modes:
        got = {name for name, cond in money_steps if runs(cond, mode)}
        want_key = next((k for k in EXPECT if mode.startswith(k)), None)
        if want_key is None:
            bad(f"모드 '{mode}' 의 기대표가 없다 — 이 검사(EXPECT)에 추가하라")
            continue
        want = EXPECT[want_key]
        got_short = {next((w for w in EXPECT_ALL if n.startswith(w)), n) for n in got}
        if got_short != want:
            bad(f"'{mode}' → 도는 단계 {sorted(got_short) or '없음'} · "
                f"기대 {sorted(want)}")
        else:
            print(f"   ✅ {mode[:24]:24s} → {' + '.join(sorted(want))}")

    print()
    print("─" * 56)
    print("✅ 버튼 배선: 정상" if ok else "❌ 버튼 배선: 돈이 샐 길이 있다")
    return 0 if ok else 1


EXPECT_ALL = sorted({w for v in EXPECT.values() for w in v},
                    key=len, reverse=True)

if __name__ == "__main__":
    sys.exit(main())
