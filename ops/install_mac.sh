#!/bin/zsh
# Sets the Mac mini up as the Regulatory Studio server: four background jobs that start at login.
#   scan    Tuesday and Friday 06:00   fetch, read, check, queue for review, refresh the preview site
#   review  always                     the review screen, on this Mac only (127.0.0.1:8765)
#   sync    always                     link to the review site on Vercel: applies reviewers' decisions, pushes pages
#   deploy  every 10 minutes           push approved items to the public site
# Nothing connects into this Mac. Run from the repo: ops/install_mac.sh     (--remove takes the jobs out again)
set -eu
REPO="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
JOBS=(scan review sync deploy)
unload() { launchctl bootout "gui/$(id -u)/in.joulewise.regstudio.$1" 2>/dev/null || true; }

if [ "${1:-}" = "--remove" ]; then
  for j in $JOBS; do unload $j; [ -f "$AGENTS/in.joulewise.regstudio.$j.plist" ] && mv "$AGENTS/in.joulewise.regstudio.$j.plist" "$REPO/data/store/"; done
  echo "Jobs stopped. Their files were moved to data/store/."; exit 0
fi

fail() { echo "NOT INSTALLED: $1"; exit 1; }
[ -x "$REPO/.venv/bin/regstudio" ] || fail "no .venv with regstudio. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -e 'pipeline[access]'"
"$REPO/.venv/bin/python" -c "import cryptography" 2>/dev/null || fail "a package is missing. Run: pip install -e pipeline"
git -C "$REPO" ls-remote --exit-code origin main >/dev/null 2>&1 || fail "this Mac cannot reach the GitHub repository. Check: git -C $REPO fetch"
git -C "$REPO" push --dry-run origin HEAD:refs/heads/_regstudio_push_test >/dev/null 2>&1 || fail "this Mac cannot push to GitHub. Sign in once with: gh auth login"

mkdir -p "$AGENTS" "$REPO/data/store/logs"
launchctl bootout "gui/$(id -u)/in.jouleWise.regulatorystudio" 2>/dev/null || true   # the old weeknight job
unload tunnel                                                                          # the earlier Cloudflare route
for j in $JOBS; do
  unload $j
  sed "s|REPO_PATH|$REPO|g" "$REPO/ops/launchd/$j.plist" > "$AGENTS/in.joulewise.regstudio.$j.plist"
  launchctl bootstrap "gui/$(id -u)" "$AGENTS/in.joulewise.regstudio.$j.plist"
  echo "started: $j"
done
echo
echo "Done. Check: launchctl list | grep regstudio     Logs: $REPO/data/store/logs/"
echo "The jobs run while this user is logged in. Turn on automatic login and stop the Mac sleeping (see docs/MAC_MINI_SERVER.md)."
