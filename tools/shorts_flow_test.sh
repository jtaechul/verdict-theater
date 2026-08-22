#!/usr/bin/env bash
# 쇼츠 워크플로의 **실행 칸(셸)** 이 갈림길을 제대로 타는가.
#
# 왜 이 검사가 있는가 (2026-08-22)
#   컷을 안 골랐는데 CUT=0 이 넘어와 "한 컷만 시험" 길로 빠졌고,
#   `❌ 1화에 0컷이 없다` 로 죽었다. 5컷을 다 올려도 완성본이 한 번도
#   안 나온 까닭이다. 그런데 그 갈림길은 **워크플로 안 셸**에 있어서,
#   파이썬·자바스크립트 검사로는 아무것도 못 잡는다.
#   → 워크플로에서 그 글을 **그대로 뽑아** 여기서 진짜로 돌린다.
#     (가짜로 베껴 적으면 워크플로가 바뀔 때 검사만 남고 뜻은 사라진다)
#
#   쓰기: bash tools/shorts_flow_test.sh     인터넷 0회 · 0원 · 몇 초
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
bad=0
ck() { if [ "$2" = 1 ]; then echo "   ✅ $1"; else echo "   ❌ $1${3:+  ($3)}"; bad=1; fi; }

# 워크플로에서 실행 칸을 이름으로 뽑아 온다
# ⚠️ 검사기가 **진짜로 잡는지** 스스로 시험할 수 있어야 한다.
#    (잡지도 못하면서 초록불만 켜는 검사가 제일 위험하다)
#    WF 로 일부러 망가뜨린 판을 넣어 돌려 볼 수 있게 해 둔다.
WF="${WF:-.github/workflows/shorts.yml}"
step() {                       # step <칸이름> [워크플로파일] [잡이름]
  WF="${2:-$WF}" JOB="${3:-shorts}" python3 - "$1" <<'PYX'
import os, sys, yaml
w = yaml.safe_load(open(os.environ["WF"], encoding="utf-8"))
for st in w["jobs"][os.environ["JOB"]]["steps"]:
    if str(st.get("name", "")).startswith(sys.argv[1]):
        # ⚠️ ${{ inputs.x }} 는 깃허브가 채우는 자리다. 셸에서 돌리려면
        #    시험용 변수로 바꿔 넣는다 (그 자리가 있다는 것도 같이 확인된다).
        run = st["run"]
        for k in ("privacy", "mode"):
            run = run.replace("${{ inputs." + k + " }}", "$TEST_" + k.upper())
        sys.stdout.write(run); break
else:
    sys.stderr.write("그런 칸이 없다: " + sys.argv[1] + "\n"); sys.exit(1)
PYX
}

# 가짜 도구들 — 진짜로 받거나 만들지 않고 **무엇을 시켰는지만** 적어 둔다
mkshims() {
  mkdir -p "$WORK/bin"
  cat > "$WORK/bin/curl" <<'EOF'
#!/usr/bin/env bash
args="$*"; echo "curl $args" >> "$LOG"
out=""; prev=""
for a in "$@"; do [ "$prev" = "-o" ] && out="$a"; prev="$a"; done
[ -n "$out" ] && cp "$ZIPSRC" "$out"
exit 0
EOF
  cat > "$WORK/bin/python3" <<'EOF'
#!/usr/bin/env bash
case "${1:-}" in
  src/shorts.py)
    echo "shorts.py $*" >> "$LOG"
    mkdir -p build/shorts
    # 한 컷 시험이면 그 이름으로, 아니면 완성본 이름으로 내놓는다
    if printf '%s\n' "$@" | grep -q -- '--demo'; then
      c=""; prev=""
      for a in "$@"; do [ "$prev" = "--cut" ] && c="$a"; prev="$a"; done
      : > "build/shorts/S001_ep01_cut${c}_short.mp4"
    else
      : > "build/shorts/S001_ep01_short.mp4"
    fi ;;
  tools/release_file.py)
    echo "release_file $*" >> "$LOG"
    # ⚠️ 영상(short.mp4)은 받아지고 **글(meta.json)만** 없는 판을 만든다.
    #    통째로 실패시키면 영상 받기에서 먼저 죽어 정작 볼 갈림길에 못 간다.
    if [ "${2:-}" = "get" ] && [ "${4:-}" = "meta.json" ] \
       && [ -n "${RELGET_FAIL:-}" ]; then exit 1; fi
    if [ "${2:-}" = "get" ]; then : > "${5:-/dev/null}"; fi ;;
  src/upload.py)   echo "upload.py $*" >> "$LOG" ;;
  src/ytmeta.py)   echo "ytmeta.py $*" >> "$LOG"; mkdir -p build; : > build/meta.json ;;
  *) exec /usr/bin/python3 "$@" ;;
esac
EOF
  chmod +x "$WORK/bin/curl" "$WORK/bin/python3"
}

run_case() {                      # run_case <이름> <CUT> <BLOB>
  local name="$1" cut="$2" blob="$3"
  local d="$WORK/$name"; mkdir -p "$d"; cd "$d"
  mkdir -p build state
  export LOG="$d/log.txt"; : > "$LOG"
  export GITHUB_ENV="$d/env.txt"; : > "$GITHUB_ENV"
  export ZIPSRC="$WORK/clips.zip"
  export PATH="$WORK/bin:$PATH"
  export SID=S001 EPNO=1 CUT="$cut" BLOB="$blob" VOICE="" ADMIN_PASS=pw
  ( eval "$(cd "$ROOT" && step '올린 압축파일 받기')" ) >>"$LOG" 2>&1
  local rc1=$?
  # GITHUB_ENV 에 적힌 것을 다음 칸이 물려받는다 (깃허브가 하는 일)
  set -a; [ -s "$GITHUB_ENV" ] && . "$GITHUB_ENV"; set +a
  ( eval "$(cd "$ROOT" && step '쇼츠 만들기')" ) >>"$LOG" 2>&1
  ( eval "$(cd "$ROOT" && step '릴리스에 올리기')" ) >>"$LOG" 2>&1
  echo "$rc1" > "$d/rc1"
  cd "$ROOT"
}

# 시험용 압축파일 (영상 5개인 척)
# ⚠️ zip 명령에 기대지 않는다 — 깃허브 러너에 없으면 검사가 준비물 때문에
#    죽는다. 파이썬은 어차피 있어야 하니 파이썬으로 만든다.
WORK="$WORK" python3 - <<'PY'
import os, zipfile
w = os.environ["WORK"]
with zipfile.ZipFile(os.path.join(w, "clips.zip"), "w") as z:
    for i in range(1, 6):
        z.writestr(f"c00{i}.mp4", b"")
PY
mkshims

echo "⭐ 쇼츠 워크플로: 갈림길을 제대로 타는가"

# ① 컷을 안 고름 → 5컷 전체
run_case none "" "https://x.workers.dev/api/blob?key=clips%2Fa"
L="$WORK/none/log.txt"
grep -q -- "--clips build/in" "$L" && a=1 || a=0
ck "컷을 안 고르면 5컷 전체로 만든다" "$a" "$(grep -m1 shorts.py "$L")"
grep -q -- "--demo" "$L" && a=0 || a=1
ck "한 컷 시험 길로 새지 않는다" "$a"
grep -q "release_file .*put short-S001-ep01 " "$L" && a=1 || a=0
ck "완성본 이름으로 올린다 (short-S001-ep01)" "$a" "$(grep -m1 'release_file .*put' "$L")"

# ② ⚠️ 여기서 죽었다 — CUT=0 이 넘어와도 5컷 전체여야 한다
run_case zero "0" "https://x.workers.dev/api/blob?key=clips%2Fa"
L="$WORK/zero/log.txt"
grep -q -- "--clips build/in" "$L" && a=1 || a=0
ck "CUT=0 이 와도 5컷 전체로 만든다" "$a" "여기서 '1화에 0컷이 없다' 로 죽었다"
grep -q -- "--cut 0" "$L" && a=0 || a=1
ck "0컷을 찾으러 가지 않는다" "$a"
grep -q "release_file .*put short-S001-ep01 " "$L" && a=1 || a=0
ck "이름에 -cut0 이 안 붙는다" "$a" "$(grep -m1 'release_file .*put' "$L")"

# ③ 진짜 한 컷 시험은 그대로 돌아야 한다
run_case cut3 "3" "https://x.workers.dev/api/blob?key=clips%2Fa"
L="$WORK/cut3/log.txt"
grep -q -- "--cut 3" "$L" && a=1 || a=0
ck "3컷 시험은 3컷으로 만든다" "$a"
grep -q "release_file .*put short-S001-ep01-cut3 " "$L" && a=1 || a=0
ck "시험본은 딴 이름으로 올린다 (완성본을 안 덮는다)" "$a" "$(grep -m1 'release_file .*put' "$L")"

# ④ 주소가 오면 보관함에서 받고, 없으면 릴리스에서 받는다
grep -q "curl .*x.workers.dev" "$WORK/none/log.txt" && a=1 || a=0
ck "주소가 오면 보관함에서 받는다" "$a"
run_case norel "" ""
grep -q "release_file .*get clips-S001-ep01 " "$WORK/norel/log.txt" && a=1 || a=0
ck "주소가 없으면 릴리스에서 받는다 (예전 길도 살아 있다)" "$a" \
   "$(grep -m1 release_file "$WORK/norel/log.txt")"

# ⑤ 모르는 주소는 받지 않는다
run_case evil "" "https://evil.example.com/steal"
[ "$(cat "$WORK/evil/rc1")" != "0" ] && a=1 || a=0
ck "모르는 주소는 아예 받지 않고 멈춘다" "$a" "$(tail -2 "$WORK/evil/log.txt" | head -1)"


# ══════════════════════════════════════════════════════
# 다음에 누르는 단추 — [유튜브에 올리기]
# ⚠️ 이 워크플로의 셸도 한 번도 돌아 본 적이 없다. 쇼츠가 만들어지면
#    손님이 바로 여기를 누르신다. 여기서 또 죽으면 안 된다.
UPWF="$ROOT/.github/workflows/shorts-upload.yml"
run_up() {                     # run_up <이름> <META> <PRIVACY> <MODE>
  local name="$1"; local d="$WORK/up-$name"; mkdir -p "$d"; cd "$d"
  mkdir -p build
  export LOG="$d/log.txt"; : > "$LOG"
  export GITHUB_ENV="$d/env.txt"; : > "$GITHUB_ENV"
  export ZIPSRC="$WORK/clips.zip"
  export PATH="$WORK/bin:$PATH"
  export SID=S001 EPNO=1 META="$2" ADMIN_PASS=pw
  export TEST_PRIVACY="$3" TEST_MODE="$4"
  ( eval "$(cd "$ROOT" && step '올릴 영상과 글 받기' "$UPWF" up)" ) >>"$LOG" 2>&1
  echo "$?" > "$d/rc1"
  set -a; [ -s "$GITHUB_ENV" ] && . "$GITHUB_ENV"; set +a
  ( eval "$(cd "$ROOT" && step '유튜브에 올리기' "$UPWF" up)" ) >>"$LOG" 2>&1
  echo "$?" > "$d/rc2"
  cd "$ROOT"
}

echo ""
echo "⭐ 유튜브 올리기 워크플로: 화면에서 본 글이 그대로 올라가는가"

run_up kept "https://x.workers.dev/api/blob?key=meta%2Fabc" "비공개 (나만 보기)" "진짜로 올리기"
L="$WORK/up-kept/log.txt"
grep -q "curl .*x.workers.dev.*meta" "$L" && a=1 || a=0
ck "고쳐 둔 글을 보관함에서 받는다" "$a"
grep -q "화면에서 확인한 글을 그대로 씁니다" "$L" && a=1 || a=0
ck "그 글을 쓴다고 말한다" "$a"
grep -q "ytmeta.py" "$L" && a=0 || a=1
ck "대본에서 새로 만들지 않는다 (보여드린 것과 달라지면 안 된다)" "$a"
grep -q -- "upload.py series S001 1" "$L" && a=1 || a=0
ck "유튜브에 올린다" "$a" "$(grep -m1 upload.py "$L")"
grep -q -- "--privacy private" "$L" && a=1 || a=0
ck "비공개는 private 으로 간다" "$a" "$(grep -m1 upload.py "$L")"
grep -q -- "--dry" "$L" && a=0 || a=1
ck "진짜로 올리기면 연습이 아니다" "$a"

RELGET_FAIL=1 run_up fresh "" "전체 공개" "연습 (올리지 않고 확인만)"
L="$WORK/up-fresh/log.txt"
grep -q "ytmeta.py" "$L" && a=1 || a=0
ck "고쳐 둔 글이 없으면 대본에서 만든다" "$a"
grep -q -- "--privacy public" "$L" && a=1 || a=0
ck "전체 공개는 public 으로 간다" "$a" "$(grep -m1 upload.py "$L")"
grep -q -- "--dry" "$L" && a=1 || a=0
ck "연습이면 진짜로 안 올린다 (--dry)" "$a" "$(grep -m1 upload.py "$L")"

run_up unl "" "일부 공개 (링크 있는 사람만)" "진짜로 올리기"
grep -q -- "--privacy unlisted" "$WORK/up-unl/log.txt" && a=1 || a=0
ck "일부 공개는 unlisted 로 간다" "$a" "$(grep -m1 upload.py "$WORK/up-unl/log.txt")"

run_up evil "https://evil.example.com/steal" "비공개 (나만 보기)" "진짜로 올리기"
[ "$(cat "$WORK/up-evil/rc1")" != "0" ] && a=1 || a=0
ck "모르는 주소는 여기서도 받지 않는다" "$a"

echo "────────────────────────────────────────────────────"
if [ "$bad" = 0 ]; then echo "✅ 쇼츠 워크플로 갈림길: 전부 제대로 탄다"; else
  echo "❌ 쇼츠 워크플로 갈림길: 걸린 것이 있다"; fi
exit $bad
