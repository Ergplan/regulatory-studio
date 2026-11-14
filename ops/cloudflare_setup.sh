#!/bin/bash
# Connects the review screen to Cloudflare, step by step. Run it in the Mac mini's Terminal:
#   ops/cloudflare_setup.sh review.your-domain.com
# It signs in to Cloudflare in your browser (you approve it there), creates the tunnel, points the
# address at it, writes the tunnel settings, then asks for the two Access values and saves them.
# Safe to run again: it skips what is already done. It never prints or copies the tunnel's secret file.
set -eu
HOST="${1:-}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
NAME=regstudio
CF="$HOME/.cloudflared"
case "$HOST" in *.*.*) ;; *) echo "Usage: ops/cloudflare_setup.sh review.your-domain.com   (a sub-address of a domain that is on your Cloudflare account)"; exit 1;; esac

echo "1/5  cloudflared"
if ! command -v cloudflared >/dev/null; then
  command -v brew >/dev/null || { echo "Install Homebrew first (https://brew.sh), then run this again."; exit 1; }
  brew install cloudflared
fi

echo "2/5  Sign in to Cloudflare"
if [ ! -f "$CF/cert.pem" ]; then
  echo "     A browser window opens. Sign in and pick the domain that $HOST belongs to."
  cloudflared tunnel login
fi

echo "3/5  Tunnel"
tunnel_id() { cloudflared tunnel list --output json 2>/dev/null | python3 -c 'import json,sys; print(next((t["id"] for t in json.load(sys.stdin) if t["name"]=="'"$NAME"'"), ""))'; }
ID="$(tunnel_id)"
if [ -z "$ID" ]; then cloudflared tunnel create "$NAME"; ID="$(tunnel_id)"; fi
[ -n "$ID" ] || { echo "Could not create or find the tunnel. Run: cloudflared tunnel list"; exit 1; }
[ -f "$CF/$ID.json" ] || { echo "The tunnel exists but its credentials file is not on this Mac ($CF/$ID.json)."; echo "It was created on another machine. Delete it in the Cloudflare dashboard (Networks > Tunnels) and run this again."; exit 1; }
cat > "$CF/regstudio.yml" <<YML
tunnel: $ID
credentials-file: $CF/$ID.json
ingress:
  - hostname: $HOST
    service: http://127.0.0.1:8765
  - service: http_status:404
YML
echo "     settings written to $CF/regstudio.yml"

echo "4/5  Address"
cloudflared tunnel route dns "$NAME" "$HOST" || echo "     (If it says the record already exists and points at this tunnel, that is fine.)"

echo "5/5  Access: who may open the review screen"
cat <<TXT

  Do this now in the browser, at https://one.dash.cloudflare.com  (Zero Trust):
    a. Access > Applications > Add an application > Self-hosted
    b. Name: Regulatory Studio review     Domain: $HOST     Session duration: 24 hours
    c. Add a policy:  Action = Allow,  Include = Emails,  and list each reviewer's email
    d. Save. Open the application again and copy the "Application Audience (AUD) Tag"
    e. Your team name is under Settings > Custom Pages / Team domain: the part before .cloudflareaccess.com

TXT
read -r -p "  Team name (the part before .cloudflareaccess.com): " TEAM
read -r -p "  Application Audience (AUD) tag: " AUD
TEAM="${TEAM%.cloudflareaccess.com}"; TEAM="${TEAM#https://}"
[ -n "$TEAM" ] && [ ${#AUD} -ge 32 ] || { echo "Those do not look right (the AUD tag is a long string of letters and digits). Run this again when you have them."; exit 1; }
ENV="$REPO/ops/studio.env"
[ -f "$ENV" ] || cp "$REPO/ops/studio.env.example" "$ENV"
grep -v '^REGSTUDIO_ACCESS_\(TEAM\|AUD\)=' "$ENV" > "$ENV.new" || true
{ cat "$ENV.new"; echo "REGSTUDIO_ACCESS_TEAM=$TEAM"; echo "REGSTUDIO_ACCESS_AUD=$AUD"; } > "$ENV"
mv "$ENV.new" "$REPO/data/store/studio.env.previous" 2>/dev/null || true

echo
if curl -fsS --max-time 15 "https://$TEAM.cloudflareaccess.com/cdn-cgi/access/certs" >/dev/null; then echo "  Team name checked: Cloudflare answers for $TEAM."; else echo "  WARNING: Cloudflare did not answer for team '$TEAM'. Check the team name and run this again."; fi
cat <<TXT

Cloudflare is set up. Next:
  regstudio add-reviewer "Full Name" --email name@firm      (once per reviewer, same emails as in the policy)
  ops/install_mac.sh                                         (starts the review screen, tunnel, scan and publisher)
Then open https://$HOST from a phone on mobile data.
TXT
