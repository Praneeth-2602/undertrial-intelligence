#!/usr/bin/env bash
set -euo pipefail

# Automates phase-based commits from PROJECT_PHASES.md
# Usage:
#   bash scripts/commit_phase.sh <day-number> [--dry-run] [--no-push]
#   bash scripts/commit_phase.sh --auto-daily [--dry-run] [--no-push]
# Example:
#   bash scripts/commit_phase.sh 3
#   bash scripts/commit_phase.sh 5 --dry-run
#   bash scripts/commit_phase.sh --auto-daily

usage() {
  echo "Usage:"
  echo "  bash scripts/commit_phase.sh <day-number 1-7> [--dry-run] [--no-push]"
  echo "  bash scripts/commit_phase.sh --auto-daily [--dry-run] [--no-push]"
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

DAY=""
DRY_RUN="false"
AUTO_DAILY="false"
AUTO_PUSH="true"

for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN="true"
      ;;
    --auto-daily)
      AUTO_DAILY="true"
      ;;
    --no-push)
      AUTO_PUSH="false"
      ;;
    [1-7])
      if [[ -n "$DAY" ]]; then
        echo "Error: multiple day arguments provided"
        usage
        exit 1
      fi
      DAY="$arg"
      ;;
    *)
      echo "Error: unknown argument '$arg'"
      usage
      exit 1
      ;;
  esac
done

if [[ "$AUTO_DAILY" == "true" && -n "$DAY" ]]; then
  echo "Error: provide either <day-number> or --auto-daily, not both"
  usage
  exit 1
fi

if [[ "$AUTO_DAILY" == "false" && -z "$DAY" ]]; then
  echo "Error: day must be provided when not using --auto-daily"
  usage
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Error: not inside a git repository"
  exit 1
fi

STATE_FILE=".git/commit_phase_daily_state"
TODAY="$(date +%F)"

if [[ "$AUTO_DAILY" == "true" ]]; then
  LAST_RUN_DATE=""
  LAST_RUN_DAY="0"

  if [[ -f "$STATE_FILE" ]]; then
    LAST_RUN_DATE="$(grep -E '^last_run_date=' "$STATE_FILE" | cut -d'=' -f2 || true)"
    LAST_RUN_DAY="$(grep -E '^last_run_day=' "$STATE_FILE" | cut -d'=' -f2 || true)"
    LAST_RUN_DAY="${LAST_RUN_DAY:-0}"
  fi

  if [[ "$LAST_RUN_DATE" == "$TODAY" ]]; then
    echo "Auto-daily already ran today ($TODAY). No action taken."
    exit 0
  fi

  if [[ "$LAST_RUN_DAY" =~ ^[0-9]+$ ]] && [[ "$LAST_RUN_DAY" -ge 7 ]]; then
    echo "All 7 days are already completed according to $STATE_FILE."
    exit 0
  fi

  DAY="$((LAST_RUN_DAY + 1))"
  echo "Auto-daily mode selected day $DAY"
fi

if ! [[ "$DAY" =~ ^[1-7]$ ]]; then
  echo "Error: day must be a number between 1 and 7"
  exit 1
fi

message_for_day() {
  case "$1" in
    1) echo "chore: initialize root git repo" ;;
    2) echo "feat: stabilize api contracts" ;;
    3) echo "feat: improve knowledge ingestion pipeline" ;;
    4) echo "feat: refine agent orchestration" ;;
    5) echo "feat: redesign frontend presentation" ;;
    6) echo "test: add verification for core flows" ;;
    7) echo "docs: finalize project documentation" ;;
  esac
}

paths_for_day() {
  case "$1" in
    1)
      cat <<'EOF'
.gitignore
PROJECT_PHASES.md
README.md
frontend/README.md
frontend/index.html
frontend/package.json
frontend/package-lock.json
frontend/vite.config.js
frontend/src/main.jsx
frontend/src/App.jsx
frontend/src/index.css
backend/main.py
backend/requirements.txt
EOF
      ;;
    2)
      cat <<'EOF'
backend/main.py
EOF
      ;;
    3)
      cat <<'EOF'
backend/rag/
backend/seed_knowledge_base.py
backend/utils/prompt_loader.py
backend/utils/llm_config.py
EOF
      ;;
    4)
      cat <<'EOF'
backend/agents/
prompts/
EOF
      ;;
    5)
      cat <<'EOF'
frontend/src/components/
frontend/src/pages/
frontend/src/lib/
frontend/src/App.jsx
frontend/src/index.css
EOF
      ;;
    6)
      cat <<'EOF'
backend/tests/
backend/utils/
backend/requirements.txt
EOF
      ;;
    7)
      cat <<'EOF'
README.md
RAG_COMPLETENESS_REPORT.md
PROJECT_PHASES.md
EOF
      ;;
  esac
}

COMMIT_MESSAGE="$(message_for_day "$DAY")"

echo "Day $DAY"
echo "Commit message: $COMMIT_MESSAGE"
echo ""
echo "Candidate paths:"
paths_for_day "$DAY"
echo ""

# Build an array of existing paths only to avoid failing on missing files.
mapfile -t CANDIDATE_PATHS < <(paths_for_day "$DAY")
EXISTING_PATHS=()
for p in "${CANDIDATE_PATHS[@]}"; do
  [[ -z "$p" ]] && continue
  if [[ -e "$p" ]]; then
    EXISTING_PATHS+=("$p")
  fi
done

if [[ ${#EXISTING_PATHS[@]} -eq 0 ]]; then
  echo "No matching files found for day $DAY in current workspace state."
  exit 0
fi

if [[ "$DRY_RUN" == "true" ]]; then
  echo "Dry run enabled: no files staged or committed."
  echo "Files that would be staged:"
  printf '  %s\n' "${EXISTING_PATHS[@]}"
  if [[ "$AUTO_PUSH" == "true" ]]; then
    echo "Push flow: stash remaining local changes -> push -> stash pop"
  else
    echo "Push flow disabled via --no-push"
  fi
  exit 0
fi

git add -- "${EXISTING_PATHS[@]}" ':(exclude)**/__pycache__/**' ':(exclude)**/*.pyc'

if git diff --cached --quiet; then
  echo "Nothing new staged for day $DAY."
  exit 0
fi

git commit -m "$COMMIT_MESSAGE"
echo "Committed day $DAY with message: $COMMIT_MESSAGE"

if [[ "$AUTO_PUSH" == "true" ]]; then
  CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
  STASHED="false"
  STASH_MSG="auto-stash-before-push-day-${DAY}-$(date +%Y%m%d-%H%M%S)"

  if [[ -n "$(git status --porcelain)" ]]; then
    git stash push -u -m "$STASH_MSG" >/dev/null
    STASHED="true"
    echo "Stashed remaining local changes before push."
  fi

  PUSH_STATUS=0
  if ! git push origin "$CURRENT_BRANCH"; then
    PUSH_STATUS=$?
  fi

  if [[ "$STASHED" == "true" ]]; then
    if ! git stash pop; then
      echo "Push result: $PUSH_STATUS"
      echo "Warning: stash pop had conflicts. Resolve conflicts manually."
      exit 1
    fi
    echo "Restored local changes after push."
  fi

  if [[ "$PUSH_STATUS" -ne 0 ]]; then
    echo "Push failed. Commit is local; your working changes are restored."
    exit "$PUSH_STATUS"
  fi

  echo "Pushed day $DAY commit to origin/$CURRENT_BRANCH"
else
  echo "Push skipped (--no-push)."
fi

if [[ "$AUTO_DAILY" == "true" ]]; then
  {
    echo "last_run_date=$TODAY"
    echo "last_run_day=$DAY"
  } > "$STATE_FILE"
  echo "Updated auto-daily state in $STATE_FILE"
fi
