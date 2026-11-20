#!/bin/zsh
# One command for the Mac mini: update, fetch, read, build this week's edition, publish, open the review screen.
#   ~/Downloads/regulatory-studio/ops/start.sh
# Safe to run again at any time: every step carries on from where the last run stopped.
set -u
cd "$(dirname "$0")/.."
say() { echo; echo "▶ $*"; }
mkdir -p data/store/logs data/store/backups
LOG="data/store/logs/start-$(date +%Y-%m-%d-%H%M).log"
PROBLEMS=()
run() { "$@" >> "$LOG" 2>&1 || PROBLEMS+=("$*"); }

say "1/6  Getting the latest version"
git pull --quiet >> "$LOG" 2>&1 || PROBLEMS+=("git pull")
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install --quiet -e 'pipeline[access]' >> "$LOG" 2>&1 || PROBLEMS+=("pip install")
[ -f ops/studio.env ] && { set -a; source ops/studio.env; set +a; }
sqlite3 data/store/working.db ".backup 'data/store/backups/working-$(date +%Y%m%d-%H%M).db'" 2>/dev/null

say "2/6  Fetching new orders from the commission websites (a few minutes)"
run regstudio download --limit 80

say "3/6  Reading and checking them (this is the long step; scanned PDFs are slow)"
for stage in intake extract registry amend consult triage read headlines check impact figures commercial revise learn; do
  echo "     $stage"
  run regstudio run $stage
done

say "4/6  Building this week's edition"
regstudio run draft 2>>"$LOG" | tee -a "$LOG" | tail -1

say "5/6  Publishing: approved items to the public site, everything else to the preview"
run regstudio deploy

say "6/6  Opening the review screen"
lsof -ti tcp:8765 2>/dev/null | xargs kill 2>/dev/null
sleep 1
nohup regstudio review >> data/store/logs/review.log 2>&1 &
sleep 3
open "http://127.0.0.1:8765"

echo
regstudio status 2>/dev/null | head -20
echo
if [ ${#PROBLEMS[@]} -eq 0 ]; then
  echo "✅ Done. The review screen is open in your browser: http://127.0.0.1:8765"
else
  echo "⚠️  Finished with ${#PROBLEMS[@]} problem(s):"
  for p in "${PROBLEMS[@]}"; do echo "   - $p"; done
  echo "   Details are in $LOG"
fi
