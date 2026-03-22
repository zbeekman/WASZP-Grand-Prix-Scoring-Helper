#!/bin/bash
# ralph-once.sh — Human-in-the-loop Ralph: run once, watch, verify, repeat.
# Usage: ./ralph-once.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

# Ensure progress file exists
touch progress.txt

claude \
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
2. Run: gh issue list --json number,title,state,body --limit 20
   Find the next AFK issue that is (a) not yet closed, (b) not blocked by an open issue, and (c) not marked done in progress.txt.
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
PROMPT
)"
