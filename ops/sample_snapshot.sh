#!/usr/bin/env bash
# Build an approved SAMPLE snapshot in a scratch folder: fixtures -> pipeline (mock reader)
# -> scripted approvals -> publish. For CI and local site development only.
set -euo pipefail
OUT="${1:?usage: ops/sample_snapshot.sh <scratch-dir>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export REGSTUDIO_INBOX="$OUT/inbox" REGSTUDIO_STORE="$OUT/store" REGSTUDIO_SNAPSHOT="$OUT/snapshot" REGSTUDIO_READER=mock
python3 "$ROOT/pipeline/tests/make_fixtures.py" "$REGSTUDIO_INBOX" >/dev/null
regstudio run intake extract registry triage read draft >/dev/null
python3 - <<'PY'
import sqlite3, os
db = sqlite3.connect(os.path.join(os.environ["REGSTUDIO_STORE"], "working.db"))
who = "CI sample reviewer"
db.execute("UPDATE regulations SET status='approved', reviewer=?, approved_at=datetime('now')", (who,))
db.execute("UPDATE clauses SET status='approved', reviewer=?, approved_at=datetime('now')", (who,))
db.execute("UPDATE links SET status='approved', reviewer=?, approved_at=datetime('now') WHERE resolved=1", (who,))
db.execute("UPDATE orders SET summary_status='approved', reviewer=?, approved_at=datetime('now') WHERE summary_status='proposed'", (who,))
db.execute("UPDATE digests SET status='approved', reviewer=?, approved_at=datetime('now')", (who,))
db.commit()
PY
regstudio publish
