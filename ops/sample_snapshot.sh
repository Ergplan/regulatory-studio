#!/usr/bin/env bash
# Build an approved SAMPLE snapshot in a scratch folder: fixtures -> pipeline (mock reader)
# -> scripted approvals -> publish. For CI and local site development only.
set -euo pipefail
OUT="${1:?usage: ops/sample_snapshot.sh <scratch-dir>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export REGSTUDIO_INBOX="$OUT/inbox" REGSTUDIO_STORE="$OUT/store" REGSTUDIO_SNAPSHOT="$OUT/snapshot" REGSTUDIO_READER=mock
python3 "$ROOT/pipeline/tests/make_fixtures.py" "$REGSTUDIO_INBOX" >/dev/null
python3 - "$ROOT/pipeline/tests" <<'PY'
# A SAMPLE draft regulation, so the consultations pages are built and checked too.
import hashlib, json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import make_fixtures
folder = Path(os.environ["REGSTUDIO_INBOX"]) / "rerc" / "2026-11-10"
folder.mkdir(parents=True, exist_ok=True)
pdf = folder / "sample-draft.pdf"
make_fixtures.make_pdf(["SAMPLE STATE ELECTRICITY REGULATORY COMMISSION",
    "Draft Sample Green Energy Open Access (Second Amendment) Regulations, 2026",
    "The Commission proposes that banking charges fall from eight to five percent of the energy banked.",
    "Comments may be sent on or before 30.12.2099. A public hearing will be held on 05.01.2100."], pdf)
pdf.with_suffix(".json").write_text(json.dumps({"commission": "rerc", "doc_type": "draft",
    "source_url": "https://example.invalid/sample/sample-draft.pdf", "downloaded_at": "2026-11-10T09:00:00+05:30",
    "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(), "doc_date": "2026-11-10",
    "title": "Draft Sample Green Energy Open Access (Second Amendment) Regulations, 2026 (SAMPLE)"}))
PY
regstudio run intake extract registry consult triage read draft >/dev/null
python3 - <<'PY'
import sqlite3, os
db = sqlite3.connect(os.path.join(os.environ["REGSTUDIO_STORE"], "working.db"))
who = "CI sample reviewer"
db.execute("UPDATE regulations SET status='approved', reviewer=?, approved_at=datetime('now')", (who,))
db.execute("UPDATE clauses SET status='approved', reviewer=?, approved_at=datetime('now')", (who,))
db.execute("UPDATE links SET status='approved', reviewer=?, approved_at=datetime('now') WHERE resolved=1", (who,))
db.execute("UPDATE orders SET summary_status='approved', reviewer=?, approved_at=datetime('now') WHERE summary_status='proposed'", (who,))
db.execute("UPDATE digests SET status='approved', reviewer=?, approved_at=datetime('now')", (who,))
db.execute("UPDATE consultations SET summary_status='approved', reviewer=?, approved_at=datetime('now') WHERE summary_status='proposed'", (who,))
db.commit()
PY
regstudio publish
