---
description: Snapshot of current purple-team state — container, bridges, services, scripts, recent commits, task backlog. Use at session start to orient quickly.
---

Run these in parallel:

```bash
cd /workspaces/gentoo

# Container + bridge state
./.claude/hooks/session-start-status.sh

# Script inventory (no backups)
echo "── scripts ──"
ls root.x86_64/scripts/*.sh 2>/dev/null | grep -v '\.bak\.' | xargs -I{} basename {}

# Regression test status
echo
echo "── regression suite ──"
ls root.x86_64/scripts/purple-regression*.sh 2>/dev/null | xargs -I{} basename {}

# NLSpec layer
echo
echo "── nlspec ──"
ls nlspec/*.md 2>/dev/null | xargs -I{} basename {}

# Factory runs
echo
echo "── factory runs ──"
ls .octo/factory/ 2>/dev/null | tail -5 || echo "  none yet"

# Recent commits
echo
echo "── recent commits ──"
git log --oneline -8

# Open PRs
echo
echo "── open PRs ──"
gh pr list --state open 2>/dev/null | head -10 || echo "  (gh not available or auth issue)"

# Task backlog
echo
echo "── tasks ──"
cat /workspaces/gentoo/.taskmaster/tasks/tasks.json 2>/dev/null \
  | python3 -c "
import sys, json
tasks = json.load(sys.stdin).get('tasks', [])
pending = [t for t in tasks if t.get('status') in ('pending','in-progress')]
for t in pending:
    print(f'  [{t[\"status\"]}] #{t[\"id\"]} [{t.get(\"priority\",\"?\")}] {t[\"title\"]}')
" 2>/dev/null || echo "  (no tasks file)"
```

Then summarize state in one paragraph: container up/down, bridge health, service count, which tasks are in-flight, and whether factory has a pending run.
