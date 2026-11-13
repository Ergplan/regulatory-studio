#!/bin/zsh
# Sets the Mac mini up as the Regulatory Studio server: four background jobs that start at login.
#   scan    Tuesday and Friday 06:00   fetch, read, check, queue for review, refresh the preview site
#   review  always                     the legal team's review screen on 127.0.0.1:8765
#   deploy  every 10 minutes           push approved items to the public site
#   tunnel  always                     Cloudflare Tunnel to the review screen
# Run from the repo: ops/install_mac.sh            (ops/install_mac.sh --remove takes them out again)
set -eu
REPO="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS="$HOME/Library/LaunchAgents"
JOBS=(scan review deploy tunnel)
unload() { launchctl bootout "gui/$(id -u)/in.joulewise.regstudio.$1" 2>/dev/null || true; }

if [ "${1:-}" = "--remove" ]; then
  for j in $JOBS; do unload $j; [ -f "$AGENTS/in.joulewise.regstudio.$j.plist" ] && mv "$AGENTS/in.joulewise.regstudio.$j.plist" "$REPO/data/store/"; done
  echo "Jobs stopped. Their files were moved to data/store/."; exit 0
fi

fail() { echo "NOT INSTALLED: $1"; exit 1; }
[ -x "$REPO/.venv/bin/regstudio" ] || fail "no .venv with regstudio. Run: python3 -m venv .venv && source .venv/bin/activate && pip install -e 'pipeline[access]'"
"$REPO/.venv/bin/python" -c "import jwt" 2>/dev/null || fail "Cloudflare Access support is missing. Run: pip install -e 'pipeline[access]'"
command -v cloudflared >/dev/null || fail "cloudflared is not installed. Run: brew install cloudflared"
[ -f "$HOME/.cloudflared/regstudio.yml" ] || fail "no ~/.cloudflared/regstudio.yml. See ops/cloudflared.example.yml"
[ -f "$REPO/ops/studio.env" ] || fail "no ops/studio.env. Copy ops/studio.env.example and fill in the two Access values"
grep -Eq '^REGSTUDIO_ACCESS_AUD=.+' "$REPO/ops/studio.env" || fail "REGSTUDIO_ACCESS_AUD is empty in ops/studio.env"
[ -f "$REPO/data/store/reviewers.json" ] || fail "no reviewers yet. Run: regstudio add-reviewer \"Name\" --email name@firm"
git -C "$REPO" ls-remote --exit-code origin main >/dev/null 2>&1 || fail "this Mac cannot reach the GitHub repository. Check: git -C $REPO fetch"
git -C "$REPO" push --dry-run origin HEAD:refs/heads/_regstudio_push_test >/dev/null 2>&1 || fail "this Mac cannot push to GitHub. Sign in once with: gh auth login"

mkdir -p "$AGENTS" "$REPO/data/store/logs"
launchctl bootout "gui/$(id -u)/in.jouleWise.regulatorystudio" 2>/dev/null || true   # the old weeknight job
for j in $JOBS; do
  unload $j
  sed "s|REPO_PATH|$REPO|g" "$REPO/ops/launchd/$j.plist" > "$AGENTS/in.joulewise.regstudio.$j.plist"
  launchctl bootstrap "gui/$(id -u)" "$AGENTS/in.joulewise.regstudio.$j.plist"
  echo "started: $j"
done
echo
echo "Done. Check: launchctl list | grep regstudio     Logs: $REPO/data/store/logs/"
echo "The jobs run while this user is logged in. Turn on automatic login and stop the Mac sleeping (see docs/MAC_MINI_SERVER.md)."
