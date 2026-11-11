"""Stage 1: register new files from the inbox, deduplicated by content hash.

The inbox is read-only to the pipeline: files stay where the download script put them;
a copy named by hash goes to data/store/files.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema

from . import config, db


@dataclass
class IntakeResult:
    added: list[str] = field(default_factory=list)
    duplicates: int = 0
    rejected: list[tuple[str, str]] = field(default_factory=list)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _schema() -> dict:
    return json.loads((config.SCHEMAS / "inbox_metadata.schema.json").read_text())


def run(limit: int | None = None) -> IntakeResult:
    config.ensure_dirs()
    result = IntakeResult()
    schema = _schema()
    validator = jsonschema.validators.validator_for(schema)(schema)
    pdfs = sorted(config.INBOX.glob("*/*/*.pdf"))
    with db.session() as conn:
        run_id = db.start_run(conn, "intake")
        for pdf in pdfs:
            if limit is not None and len(result.added) >= limit:
                break
            rel = str(pdf.relative_to(config.INBOX))
            meta_path = pdf.with_suffix(".json")
            if not meta_path.exists():
                result.rejected.append((rel, "no metadata file beside the PDF"))
                continue
            try:
                meta = json.loads(meta_path.read_text())
            except json.JSONDecodeError as e:
                result.rejected.append((rel, f"metadata is not valid JSON: {e}"))
                continue
            errors = sorted(validator.iter_errors(meta), key=lambda e: e.path)
            if errors:
                result.rejected.append((rel, "; ".join(e.message for e in errors[:3])))
                continue
            actual = sha256_file(pdf)
            if actual != meta["sha256"]:
                result.rejected.append((rel, "sha256 in metadata does not match the file"))
                continue
            if pdf.parent.parent.name != meta["commission"]:
                result.rejected.append((rel, "folder commission differs from metadata commission"))
                continue
            if conn.execute("SELECT 1 FROM documents WHERE id = ?", (actual,)).fetchone():
                result.duplicates += 1
                continue
            dest = config.FILES / f"{actual}.pdf"
            if not dest.exists():
                shutil.copyfile(pdf, dest)
            conn.execute(
                """INSERT INTO documents(id, commission, doc_type, source_url, downloaded_at,
                       title, doc_date, case_number, file_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (actual, meta["commission"], meta["doc_type"], meta["source_url"], meta["downloaded_at"],
                 meta.get("title"), meta.get("doc_date"), meta.get("case_number"),
                 str(dest.relative_to(config.STORE))),
            )
            db.audit(conn, "pipeline", "intake", actual, {"inbox_path": rel})
            result.added.append(actual)
        db.finish_run(conn, run_id, len(result.added), len(result.rejected),
                      f"duplicates={result.duplicates}")
    return result
