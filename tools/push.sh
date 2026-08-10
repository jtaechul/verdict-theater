#!/usr/bin/env bash
# 결과물을 저장소에 올린다. **밀어넣기가 밀려도 만든 것을 잃지 않는다.**
#
#     bash tools/push.sh "커밋 메시지" 올릴경로 [올릴경로 …]
#
# ─────────────────────────────────────────────────────────────────────
# 왜 이 파일이 따로 있는가 — 2026-08-10 EP002 실종 사고
#
# 예전에는 워크플로마다 이렇게 적혀 있었다.
#
#     git commit -m "…"
#     for i in 1 2 3 4; do
#       git push origin HEAD:main && break
#       sleep $((2**i)); git pull --rebase origin main || true
#     done
#
# 문제는 state/queue.json 처럼 **매번 통째로 다시 쓰는 파일**이다.
# 그 사이 다른 실행이 같은 파일을 올려 두면 rebase 는 거의 반드시 충돌한다.
# 충돌이 나면 rebase 가 중간에 멈춘 채로 남는데, 뒤에 붙은 `|| true` 가
# 그 실패를 조용히 삼킨다. 그 상태에서 다음 push 는 이렇게 답한다.
#
#     Everything up-to-date
#
# 우리 커밋이 가지에서 떨어져 나갔기 때문이다. 워크플로는 **성공으로 끝나고**
# 결과물은 사라진다. 실제로 Opus 로 19분에 걸쳐 만든 대본 EP002(컷 120개)가
# 이렇게 통째로 없어졌다. 로그에도 '실패'라는 말이 한 번도 안 나왔다.
#
# 그래서 여기서는 **합치려 들지 않는다.**
#   원격 최신본을 받아 그 위에 우리가 만든 파일만 그대로 얹고 다시 커밋한다.
#   충돌이라는 개념 자체가 생기지 않는다. 우리 결과물은 항상 남는다.
#   (state 파일은 원래 '마지막에 쓴 쪽이 맞다'가 옳다 — 프로그램이 매번
#    전체를 다시 계산해서 쓰기 때문이다.)
# ─────────────────────────────────────────────────────────────────────

set -u

MSG="${1:-}"
if [ -z "$MSG" ]; then
  echo "쓸 커밋 메시지가 없다. 사용법: bash tools/push.sh \"메시지\" 경로 …" >&2
  exit 2
fi
shift
if [ "$#" -eq 0 ]; then
  echo "올릴 경로가 없다." >&2
  exit 2
fi
PATHS=("$@")

git config user.name  "verdict-theater-bot"
git config user.email "actions@github.com"

# 경로를 하나씩 넣는다. 없는 경로가 하나 섞여도 나머지가 다 날아가지 않게.
# -A 라서 새로 생긴 것 · 바뀐 것 · **지워진 것**이 모두 반영된다
# (다 만든 뒤 지우는 초벌 파일 EP00N.draft.json 이 여기 해당한다).
stage() {
  for p in "${PATHS[@]}"; do
    git add -A -- "$p" 2>/dev/null || true
  done
}

stage
if git diff --cached --quiet; then
  # 담을 것이 없다. 두 가지 경우다.
  #   ① 정말 바뀐 것이 없다              → 올릴 것도 없다
  #   ② 워크플로가 이미 커밋까지 해 놨다  → 올리기만 하면 된다
  git fetch -q origin main 2>/dev/null || true
  if [ -z "$(git log --oneline origin/main..HEAD 2>/dev/null)" ]; then
    echo "바뀐 것이 없다. 올릴 것이 없다."
    exit 0
  fi
  echo "이미 커밋돼 있다. 올리기만 한다: $(git log -1 --oneline)"
else
  git commit -q -m "$MSG"
  echo "커밋함: $(git log -1 --oneline)"
fi
MINE="$(git rev-parse HEAD)"

# 이번 실행이 **지운** 파일 목록. (예: 대본을 다 만든 뒤 없애는 초벌 EP00N.draft.json)
# 다시 얹을 때 이걸 안 챙기면 지운 파일이 원격에서 되살아난다.
DELETED="$(git diff --name-only --diff-filter=D "$MINE^" "$MINE" 2>/dev/null || true)"

for i in 1 2 3 4; do
  if git push origin HEAD:main; then
    echo "저장소에 올렸다."
    exit 0
  fi

  W=$((2 ** i))
  echo "밀어넣기가 밀렸다 — 그 사이 다른 실행이 먼저 올린 것이 있다. ${W}초 뒤 다시 한다."
  sleep "$W"

  # 중간에 멈춰 있는 작업이 있으면 먼저 걷어낸다. 이게 남아 있으면
  # 다음 push 가 엉뚱한 자리를 가리켜 '올릴 것 없음'으로 끝난다.
  git rebase      --abort 2>/dev/null || true
  git merge       --abort 2>/dev/null || true
  git cherry-pick --abort 2>/dev/null || true

  if ! git fetch origin main; then
    echo "원격을 읽지 못했다. 다시 시도한다."
    continue
  fi

  # 원격 최신본으로 갈아탄 뒤, 우리가 만든 파일만 그 위에 덮어쓴다.
  # ⚠️ 폴더를 통째로 지우고 덮지 않는다. 그 사이 다른 실행이 올린 회차
  #    (예: 원격에만 있는 EP003)까지 같이 지워 버리기 때문이다.
  git reset --hard origin/main || git reset --hard FETCH_HEAD
  for p in "${PATHS[@]}"; do
    git checkout "$MINE" -- "$p" 2>/dev/null || true
  done
  # 우리가 지운 파일은 여기서도 지운다 (되살아나지 않게)
  if [ -n "$DELETED" ]; then
    while IFS= read -r f; do
      [ -n "$f" ] && rm -f -- "$f"
    done <<< "$DELETED"
  fi

  stage
  if git diff --cached --quiet; then
    echo "원격에 이미 같은 내용이 들어 있다. 더 올릴 것이 없다."
    exit 0
  fi
  git commit -q -m "$MSG"
done

echo "::warning::네 번 시도했지만 저장소에 올리지 못했다."
exit 1
