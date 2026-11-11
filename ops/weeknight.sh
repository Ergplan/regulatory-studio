#!/bin/zsh
# Weeknight pipeline run on the Mac mini. Each stage resumes from database state, so a run
# that stops on a usage limit is picked up by the next one. Logs go to data/store/logs.
set -u
cd "$(dirname "$0")/.."
source .venv/bin/activate
mkdir -p data/store/logs
LOG="data/store/logs/$(date +%Y-%m-%d).log"
{
  echo "=== $(date) ==="
  regstudio run intake extract registry amend
  regstudio run triage --limit 60
  regstudio run read --limit 15
  # Friday: assemble the week's digest for Saturday review
  [ "$(date +%u)" = "5" ] && regstudio run draft
  regstudio status
} >> "$LOG" 2>&1
