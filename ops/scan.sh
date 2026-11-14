#!/bin/zsh
# The scan: runs on the Mac mini on Tuesday and Friday mornings (ops/launchd/scan.plist).
# It fetches what the commissions and APTEL have posted, has Claude read it, runs the checks,
# and leaves everything as PROPOSED in the review queue. It then refreshes the preview site.
# Nothing reaches the public site from here: that needs a reviewer's approval.
# Each stage resumes from database state, so a run cut short by a usage limit is finished by the next.
set -u
cd "$(dirname "$0")/.."
source .venv/bin/activate
[ -f ops/studio.env ] && { set -a; source ops/studio.env; set +a; }
mkdir -p data/store/logs data/store/backups
LOG="data/store/logs/scan-$(date +%Y-%m-%d).log"
STATUS=ok
step() { echo "--- $*"; "$@" || { STATUS="problems: see $LOG"; echo "FAILED: $*"; }; }
{
  echo "=== scan started $(date) ==="
  # A copy of the database before anything is changed; the last 14 are kept
  sqlite3 data/store/working.db ".backup 'data/store/backups/working-$(date +%Y%m%d-%H%M).db'" 2>/dev/null \
    && ls -t data/store/backups/working-*.db | tail -n +15 | xargs rm -f
  step regstudio download --limit 80          # last 14 days, skipping what is already fetched
  regstudio check-inbox || echo "check-inbox: problems listed above; intake skips bad files"
  step regstudio run intake extract registry amend
  step regstudio run consult --limit 20
  step regstudio run triage --limit 120
  step regstudio run read --limit 30
  step regstudio run headlines --limit 40
  step regstudio run check --limit 30         # number check and two AI reviewers, before legal review
  step regstudio run impact --limit 20
  step regstudio run figures --limit 30
  step regstudio run comments --limit 10
  [ "$(date +%u)" = "5" ] && step regstudio run draft   # Friday: assemble the week's digest
  step regstudio deploy --refresh               # preview site shows the new proposals; public site only what is approved
  regstudio status
  echo "=== scan finished $(date): $STATUS ==="
} >> "$LOG" 2>&1
printf '{"finished": "%s", "status": "%s"}\n' "$(date +%Y-%m-%dT%H:%M:%S%z)" "$STATUS" > data/store/scan_last.json
