#!/bin/bash
# afk-ralph.sh — Autonomous Ralph loop: runs N iterations, stops on completion.
# Usage: ./afk-ralph.sh <iterations>
#   e.g. ./afk-ralph.sh 15
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

if [ -z "${1:-}" ]; then
  echo "Usage: $0 <iterations>"
  echo "  e.g. $0 15"
  exit 1
fi

MAX_ITERATIONS="$1"
LOGDIR="$REPO_ROOT/ralph-logs"
mkdir -p "$LOGDIR"

# Ensure progress file exists
touch progress.txt

echo "=== AFK Ralph: starting $MAX_ITERATIONS iterations ==="
echo "    Logs: $LOGDIR/"
echo ""

for ((i=1; i<=MAX_ITERATIONS; i++)); do
  TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
  LOGFILE="$LOGDIR/ralph-${TIMESTAMP}-iter${i}.log"

  echo "--- Iteration $i/$MAX_ITERATIONS ($(date)) ---"

  result=$(claude \
    --dangerously-skip-permissions \
    --model claude-sonnet-4-6 \
    --effort high \
    -p \
    "$(cat <<'PROMPT'
You are an autonomous coding agent implementing the WASZP GP Scorer project.

## Context

- The PRD is GitHub issue #1. Read it with: gh issue view 1
- Sub-issues #2–#15 are vertical slices. List them with: gh issue list
- Each sub-issue has a "Blocked by" section — respect the dependency order.
- progress.txt in the repo root tracks completed work.
- Read CLAUDE.md or .claude/settings.json for project conventions if they exist.

## Your task

1. Read progress.txt to understand what has been done so far.
2. Run: gh issue list --json number,title,state --limit 20
   Find the next AFK issue that is (a) not yet closed, (b) not blocked by an open issue, and (c) not marked done in progress.txt.
   If ALL non-HITL issues are closed or done, output exactly: <promise>COMPLETE</promise> and stop.
3. Read the full issue body: gh issue view <number>
4. Implement the issue. Follow the acceptance criteria exactly.
5. Run tests (pytest) and type checks (mypy) if applicable. Fix any failures before committing.
6. Run black and flake8 if configured. Fix any violations.
7. Stage your changes (specific files, not git add -A) and commit with a descriptive message referencing the issue:
     Implement <short description> (#<number>)

     Co-Authored-By: Claude <noreply@anthropic.com>
8. Update progress.txt: append a line with the date, issue number, and summary.
9. Comment on the GitHub issue with a summary of what was implemented and any decisions made:
     gh issue comment <number> --body "<summary>"
10. If all acceptance criteria are met, close the issue:
     gh issue close <number>

## Rules
- ONLY WORK ON A SINGLE ISSUE per invocation.
- Do NOT work on HITL issues (#9, #15). Skip them and pick the next AFK issue.
- Do NOT push to the remote — only commit locally.
- Prefer editing existing files over creating new ones.
- All code must have type hints and docstrings per PRD conventions.
- Never commit real user data or .env files.
- Use src/ layout per PRD: src/waszp_gp_scorer/
- If ALL non-HITL issues are done, output exactly: <promise>COMPLETE</promise>
PROMPT
)" 2>&1 | tee "$LOGFILE")

  echo ""

  # Check for completion sigil
  if [[ "$result" == *"<promise>COMPLETE</promise>"* ]]; then
    echo "=== PRD complete after $i iterations! ==="
    echo "$(date): All AFK issues complete after $i iterations" >> progress.txt
    exit 0
  fi

  # Brief pause between iterations to avoid hammering the API
  if [ "$i" -lt "$MAX_ITERATIONS" ]; then
    sleep 5
  fi
done

echo "=== AFK Ralph: completed $MAX_ITERATIONS iterations (PRD may not be fully done) ==="
