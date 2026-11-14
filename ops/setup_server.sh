#!/bin/bash
# One run sets the Mac mini up as the Regulatory Studio server. In the Mac's Terminal:
#   cd ~/Downloads/regulatory-studio && git stash -u && git pull && ops/setup_server.sh
# It asks three things as it goes: the review address, the two Cloudflare Access values, and the reviewers.
# Safe to run again: finished steps are skipped. Nothing is published as reviewed by this script.
set -eu
cd "$(dirname "$0")/.."
REPO="$(pwd)"
say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
stop() { printf '\nSTOPPED: %s\n' "$*"; exit 1; }

say "1/7  Python packages"
[ -d .venv ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -e "pipeline[access]" || stop "pip could not install the packages. Check the internet connection and run this again."
regstudio status >/dev/null 2>&1 || true   # applies database changes

say "2/7  GitHub: can this Mac push?"
if GIT_TERMINAL_PROMPT=0 git push --dry-run origin HEAD:refs/heads/_regstudio_push_test >/dev/null 2>&1; then
  echo "     yes"
else
  stop "this Mac cannot push to GitHub. Run:  gh auth login   (choose GitHub.com, HTTPS, sign in with the browser), then run this script again."
fi
[ -n "$(git config user.name || true)" ] && [ -n "$(git config user.email || true)" ] || stop "git has no name or email. Run:  git config --global user.name \"Your Name\"  and  git config --global user.email you@firm  (the GitHub account Vercel accepts)."

say "3/7  Cloudflare tunnel and Access"
HOST="$(sed -n 's/^ *- hostname: *//p' "$HOME/.cloudflared/regstudio.yml" 2>/dev/null | head -1)"
if [ -n "$HOST" ] && grep -Eq '^REGSTUDIO_ACCESS_AUD=.+' ops/studio.env 2>/dev/null; then
  echo "     already set up for $HOST"
else
  [ -n "$HOST" ] || read -r -p "     Address for the review screen (for example review.yourdomain.com): " HOST
  ops/cloudflare_setup.sh "$HOST"
fi

say "4/7  Reviewers"
if [ -f data/store/reviewers.json ]; then echo "     already registered:"; python3 -c 'import json; [print("      ", n, "<" + r.get("email", "password only") + ">") for n, r in json.load(open("data/store/reviewers.json")).items()]'; fi
echo "     Add each reviewer with the same email as in the Cloudflare Access policy. Press Return on an empty name to finish."
while true; do
  read -r -p "     Full name: " RNAME; [ -n "$RNAME" ] || break
  read -r -p "     Email: " REMAIL
  regstudio add-reviewer "$RNAME" --email "$REMAIL" || echo "     not added; try again"
done
[ -f data/store/reviewers.json ] || stop "no reviewers registered. Run this again and add at least one."

say "5/7  Load the prepared analysis and refresh the preview site"
REGSTUDIO_READER=file regstudio run impact check figures comments || echo "     (some prepared files were not loaded; see the lines above)"
regstudio deploy --only preview || echo "     (the preview site was not pushed; see the message above)"

say "6/7  Start the four background jobs"
ops/install_mac.sh

say "7/7  Check"
sleep 6
CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 http://127.0.0.1:8765/login || true)"
[ "$CODE" = "200" ] && echo "     review screen is running on this Mac" || echo "     PROBLEM: review screen did not answer (code $CODE). See data/store/logs/review.err"
sleep 6
OUT="$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' --max-time 20 "https://$HOST/" || true)"
case "$OUT" in
  302*cloudflareaccess.com*) echo "     https://$HOST asks for a Cloudflare sign-in: correct";;
  *) echo "     CHECK: https://$HOST answered '$OUT'. Expected a redirect to the Cloudflare sign-in. A new address can take a few minutes; if it stays like this, check the Access application covers $HOST.";;
esac

cat <<TXT

Done. Open https://$HOST from a phone on mobile data and sign in with a reviewer's email.
Two settings to make by hand on this Mac (System Settings):
  - Energy: "Prevent automatic sleeping when the display is off" and "Start up automatically after a power failure"
  - Users & Groups: automatic login for this user
The first scan runs on the next Tuesday or Friday at 06:00. To scan now: ops/scan.sh
TXT
