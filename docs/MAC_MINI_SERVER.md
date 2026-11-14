# Setting up the Mac mini as the server

**Short way:** one line in the Mac's Terminal does everything below and asks for what it needs as it goes:

```bash
cd ~/Downloads/regulatory-studio && git stash -u && git pull && ops/setup_server.sh
```

The rest of this page is the same thing step by step.

Do these once, in the Mac's own Terminal. Steps marked **you** need your accounts; nobody else
should do them for you.

## 1. Code and Python

```bash
cd ~/Downloads/regulatory-studio
git stash -u && git pull          # -u also sets aside the older untracked copies of files that are now in git
source .venv/bin/activate
pip install -e "pipeline[access]"
```

## 2. GitHub push (**you**)

The publisher pushes to GitHub as this Mac's user.

```bash
gh auth login                     # once
git push --dry-run origin HEAD:refs/heads/_test   # must not ask for a password
git config user.name; git config user.email      # must be set; use the GitHub account that Vercel accepts
```

Vercel may refuse to build commits from an author it does not know. Use the same GitHub account that
owns the Vercel project.

## 3 and 4. Cloudflare (**you**)

Needs a domain whose DNS is managed by your Cloudflare account. One script does the tunnel and asks for the
two Access values:

```bash
ops/cloudflare_setup.sh review.YOUR-DOMAIN
```

It opens the browser for you to sign in, creates the tunnel, points `review.YOUR-DOMAIN` at it, writes
`~/.cloudflared/regstudio.yml`, then prints the five clicks for the Access application and saves the team name
and AUD tag into `ops/studio.env`. The tunnel's credentials file in `~/.cloudflared/` is a secret; it stays on
the Mac and is never committed. `ops/cloudflared.example.yml` shows what the script writes.

## 5. Reviewers

One line per reviewer, with the same email as in the Access policy:

```bash
regstudio add-reviewer "Full Name" --email name@firm
```

The name is what appears against every approval. To remove someone, take their email out of the
Access policy and delete their entry from `data/store/reviewers.json`.

## 6. Load the prepared analysis into this Mac's database

From now on both sites show what is in **this Mac's database**. Load the analysis files already placed in
`data/reader_outputs/` first, or the preview site will lose the impact notes, charts and checks it shows today:

```bash
REGSTUDIO_READER=file regstudio run impact check figures comments
regstudio deploy --only preview        # look at the preview site before going further
```

## 7. Start everything

```bash
ops/install_mac.sh
launchctl list | grep regstudio          # four lines: scan, review, deploy, tunnel
```

The installer refuses to start if any step above is missing and says which one.

## 8. Keep the Mac awake and logged in

The jobs run while this user is logged in.

- System Settings > Energy: turn on "Prevent automatic sleeping when the display is off" and
  "Start up automatically after a power failure".
- System Settings > Users & Groups: automatic login for this user. (Not available with FileVault on;
  then log in by hand after a restart.)

## 9. Check it works

1. From a phone on mobile data, open `https://review.YOUR-DOMAIN`. Cloudflare asks for an email and code,
   then the queue opens showing "Reviewing as <name>".
2. From an email that is not on the list: Cloudflare refuses.
3. Approve one item. Within 10 minutes the queue's "Public site" box shows a new push, and the site updates
   a few minutes later.
4. `ops/scan.sh` runs a scan now, without waiting for Tuesday or Friday.

## Day to day

| What | Where |
|---|---|
| Scan log | `data/store/logs/scan-YYYY-MM-DD.log` |
| Job output | `data/store/logs/{scan,review,deploy,tunnel}.{out,err}` |
| Last push | "Public site" box on the queue page, or `data/store/deploy_last.json` |
| Push now | button on the queue page, or `regstudio deploy` |
| Database backups | `data/store/backups/` (taken before each scan, 14 kept) |
| Stop everything | `ops/install_mac.sh --remove` |
| After `git pull` | `ops/install_mac.sh` again, to restart the review screen on the new code |

Do not commit `data/snapshot` by hand any more: the publisher owns it on both branches. The `preview`
branch is rebuilt and replaced on every push, so do not work on it directly.
