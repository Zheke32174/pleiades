#!/usr/bin/env bash
# SessionEnd hook — brief summary of what changed this session.
set -uo pipefail

cd /workspaces/gentoo 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

echo
echo "── session summary ──"

COMMITS=$(git log --since="1 day ago" --oneline 2>/dev/null | wc -l)
if [ "$COMMITS" -gt 0 ]; then
  echo "  commits in last 24h: $COMMITS"
  git log --since="1 day ago" --oneline 2>/dev/null | head -8 | sed 's/^/    /'
fi

BRANCH=$(git branch --show-current 2>/dev/null)
echo "  current branch: ${BRANCH:-(detached)}"

DIRTY=$(git status --porcelain 2>/dev/null | wc -l)
if [ "$DIRTY" -gt 0 ]; then
  echo "  uncommitted: $DIRTY files"
fi

if command -v gh >/dev/null 2>&1; then
  PR_COUNT=$(gh pr list --state open --limit 100 --json number 2>/dev/null \
    | python3 -c "import sys,json;print(len(json.load(sys.stdin)))" 2>/dev/null)
  if [ -n "$PR_COUNT" ] && [ "$PR_COUNT" -gt 0 ]; then
    echo "  open PRs: $PR_COUNT"
    gh pr list --state open --limit 5 2>/dev/null | head -5 | sed 's/^/    /'
  fi
fi

echo
