#!/usr/bin/env bash
# ⭐ 자체 점검이 **실제로 돌리는 것 전부**를 그대로 돌린다.
#
# ⚠️ 2026-08-22 — 눈으로 골라 몇 개만 돌리고 "다 통과" 라고 밀어 넣었다가
#    깃허브에서 빨간불이 났다. 안 돌린 검사(series_screen_test)가 걸린 것이다.
#    → 목록을 손으로 적지 않는다. **워크플로에서 뽑아** 그대로 돌린다.
#       워크플로에 검사가 늘면 여기도 저절로 늘어난다.
#
#   쓰기: bash tools/checkall.sh
set -uo pipefail
cd "$(dirname "$0")/.."
LIST=$(python3 - <<'PY'
import re, yaml
w = yaml.safe_load(open(".github/workflows/selfcheck.yml", encoding="utf-8"))
for st in w["jobs"]["check"]["steps"]:
    for line in str(st.get("run", "")).splitlines():
        line = line.strip()
        # ⚠️ bash 로 도는 검사(워크플로 셸 갈림길)도 여기서 같이 돌려야 한다.
        #    빠뜨리면 "다 통과" 라고 밀어 넣고 깃허브에서 빨간불이 난다.
        if re.match(r"^(python3 tools/|node tools/|bash tools/)", line):
            print(line)
PY
)
bad=0
FAILED=""
while IFS= read -r c <&3; do
  [ -z "$c" ] && continue
  case "$c" in
    *tts_live_check*|*voice_route*)
      echo "⏭  $c  (열쇠가 있어야 한다 — 깃허브에서 돈다)"; continue;;
  esac
  if timeout 500 $c >/tmp/_chk.txt 2>&1 </dev/null; then
    echo "✅ $c"
  else
    bad=1; FAILED="$FAILED $c"; echo "❌ $c"
    tail -6 /tmp/_chk.txt | sed 's/^/      /'
  fi
done 3<<< "$LIST"
echo "────────────────────────────────────────────────────"
if [ "$bad" = 0 ]; then
  echo "✅ 전부 통과 — 밀어 넣어도 된다"
else
  # ⚠️ 맨 끝에 다시 적는다. `checkall.sh | tail` 로 볼 때 놓치지 않게.
  #    (실제로 파이프가 실패 신호를 삼켜 그대로 밀어 넣은 적이 있다)
  echo "❌ 걸린 것:"
  for f in $FAILED; do echo "     $f"; done
  echo "❌ 고치고 다시 — 밀어 넣지 마십시오"
fi
exit $bad
