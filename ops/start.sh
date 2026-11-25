#!/bin/zsh
# One command for the Mac mini: update, fetch, read, build this week's edition, publish, start the background jobs
# and connect to the review site.
#   ~/Downloads/regulatory-studio/ops/start.sh
# Safe to run again at any time: every step carries on from where the last run stopped.
set -u
cd "$(dirname "$0")/.."
say() { echo; echo "▶ $*"; }
# macOS does not let background jobs read Downloads, Desktop or Documents. If the project is there, move it to the
# home folder once and carry on from the new place.
case "$PWD" in
  "$HOME/Downloads/"*|"$HOME/Desktop/"*|"$HOME/Documents/"*)
    NEW="$HOME/regulatory-studio"
    if [ -e "$NEW" ]; then echo "The project is in $PWD, where background jobs cannot run, and $NEW already exists. Run: $NEW/ops/start.sh"; exit 1; fi
    say "Moving the project to $NEW (background jobs cannot run from $(basename "$(dirname "$PWD")"))"
    ops/install_mac.sh --remove >/dev/null 2>&1
    lsof -ti tcp:8765 2>/dev/null | xargs kill 2>/dev/null
    OLD="$PWD"; cd "$HOME" && mv "$OLD" "$NEW" && cd "$NEW" || { echo "Could not move the project. Nothing was changed."; exit 1; }
    rm -rf .venv                                   # it remembers the old location; it is rebuilt below
    git worktree repair data/store/deploy/* >/dev/null 2>&1
    exec ops/start.sh ;;
esac
mkdir -p data/store/logs data/store/backups
LOG="data/store/logs/start-$(date +%Y-%m-%d-%H%M).log"
PROBLEMS=()
run() { "$@" >> "$LOG" 2>&1 || PROBLEMS+=("$*"); }

say "1/7  Getting the latest version"
git pull --quiet >> "$LOG" 2>&1 || PROBLEMS+=("git pull")
[ -x .venv/bin/python ] || python3 -m venv .venv
source .venv/bin/activate
pip install --quiet -e pipeline >> "$LOG" 2>&1 || PROBLEMS+=("pip install")
[ -f ops/studio.env ] && { set -a; source ops/studio.env; set +a; }
sqlite3 data/store/working.db ".backup 'data/store/backups/working-$(date +%Y%m%d-%H%M).db'" 2>/dev/null

say "2/7  Fetching new orders from the commission websites (a few minutes)"
regstudio download --limit 80 2>>"$LOG" | tee -a "$LOG" | python3 -c '
import json, sys
t = sys.stdin.read()
for site, r in json.loads(t[t.index("{"):]).items():
    for e in r.get("errors", []): print(f"download {site}: {e[:120]}")' 2>/dev/null > "$LOG.dl"
while IFS= read -r line; do PROBLEMS+=("$line"); done < "$LOG.dl"; rm -f "$LOG.dl"

# Documents the first sort left out but which should be read after all (one id per line).
if [ -f data/reader_outputs/promote.txt ]; then
  for id in $(cat data/reader_outputs/promote.txt); do regstudio promote "$id" >> "$LOG" 2>&1; done
  mv data/reader_outputs/promote.txt "data/reader_outputs/promote-done-$(date +%Y%m%d-%H%M).txt"
fi

say "3/7  Reading and checking them (this is the long step; scanned PDFs are slow)"
for stage in intake extract registry amend consult triage read headlines check impact figures commercial revise learn; do
  echo "     $stage"
  run regstudio run $stage
done

# Orders the owner chose to show on the public site before legal review, marked "pending legal review".
if [ -f data/reader_outputs/publish_pending.txt ]; then
  WHO="$(sed -n 's/^# as: //p' data/reader_outputs/publish_pending.txt | head -1)"
  regstudio publish-pending --file data/reader_outputs/publish_pending.txt --as "${WHO:-the studio owner}" >> "$LOG" 2>&1 || PROBLEMS+=("publish-pending")
  mv data/reader_outputs/publish_pending.txt "data/reader_outputs/publish_pending-done-$(date +%Y%m%d-%H%M).txt"
fi

say "4/7  Building this week's edition"
regstudio run draft 2>>"$LOG" | tee -a "$LOG" | tail -1

say "5/7  Publishing: approved items to the public site, everything else to the preview"
run regstudio deploy

say "6/7  Starting the background jobs (scan, review screen, sync, publishing)"
if ops/install_mac.sh >> "$LOG" 2>&1; then echo "     running"; else PROBLEMS+=("background jobs: $(grep 'NOT INSTALLED' "$LOG" | tail -1)"); fi
sleep 4

say "7/7  Connecting to the review site ($(python -c 'from regstudio import config; print(config.REVIEW_SITE)'))"
regstudio sync-key > /dev/null 2>>"$LOG"
if regstudio sync >> "$LOG" 2>&1; then
  echo "     connected; the review pages are up to date"
  if [ ! -f data/store/first_admin_invited ]; then
    echo
    echo "     Set up your own sign-in (asked once). You will choose a password in the browser."
    printf "     Your full name: "; read NAME
    printf "     Your work email: "; read EMAIL
    if [ -n "$NAME" ] && [ -n "$EMAIL" ] && regstudio invite "$NAME" "$EMAIL" --team admin --open >> "$LOG" 2>&1; then
      touch data/store/first_admin_invited; echo "     Your invitation opened in the browser. Invite the others from the Admin page there."
    else PROBLEMS+=("could not create your invitation"); fi
  fi
else
  echo "     not connected yet: $(grep '^sync: ' "$LOG" | tail -1 | cut -c7-200)"
  echo "     If it is about the key: tell Claude \"the key is ready\". It is in data/store/sync_public_key.txt (a public key, safe to share)."
  PROBLEMS+=("review site: $(grep '^sync: ' "$LOG" | tail -1 | cut -c7-200)")
fi

echo
regstudio status 2>/dev/null | head -20
echo
if [ ${#PROBLEMS[@]} -eq 0 ]; then
  echo "✅ Done. Reviewers sign in at $(python -c 'from regstudio import config; print(config.REVIEW_SITE)')"
else
  echo "⚠️  Finished with ${#PROBLEMS[@]} problem(s):"
  for p in "${PROBLEMS[@]}"; do echo "   - $p"; done
  echo "   Details are in $LOG"
fi
