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


def check_file(pdf: Path, validator) -> tuple[dict | None, str | None, str | None]:
    """Validate one inbox PDF against the contract. Returns (metadata, sha256, problem)."""
    meta_path = pdf.with_suffix(".json")
    if not meta_path.exists():
        return None, None, "no metadata file beside the PDF"
    try:
        meta = json.loads(meta_path.read_text())
    except json.JSONDecodeError as e:
        return None, None, f"metadata is not valid JSON: {e}"
    errors = sorted(validator.iter_errors(meta), key=lambda e: list(e.path))
    if errors:
        return None, None, "; ".join(e.message for e in errors[:3])
    with pdf.open("rb") as f:
        if f.read(5) != b"%PDF-":
            return None, None, "file is not a PDF (check for an HTML error page saved as .pdf)"
    actual = sha256_file(pdf)
    if actual != meta["sha256"]:
        return None, None, "sha256 in metadata does not match the file"
    if pdf.parent.parent.name != meta["commission"]:
        return None, None, "folder commission differs from metadata commission"
    if not re_date(pdf.parent.name):
        return None, None, "folder name is not a date (YYYY-MM-DD)"
    return meta, actual, None


def re_date(name: str) -> bool:
    import re
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", name))


def check() -> dict:
    """Dry run for the download team: report every problem in the inbox, register nothing."""
    schema = _schema()
    validator = jsonschema.validators.validator_for(schema)(schema)
    ok, problems = 0, []
    for pdf in sorted(config.INBOX.glob("*/*/*.pdf")):
        _, _, problem = check_file(pdf, validator)
        if problem:
            problems.append({"file": str(pdf.relative_to(config.INBOX)), "problem": problem})
        else:
            ok += 1
    orphans = [str(j.relative_to(config.INBOX)) for j in sorted(config.INBOX.glob("*/*/*.json"))
               if not j.with_suffix(".pdf").exists()]
    misplaced = [str(f.relative_to(config.INBOX)) for f in sorted(config.INBOX.rglob("*"))
                 if f.is_file() and f.name != ".gitkeep" and len(f.relative_to(config.INBOX).parts) != 3]
    return {"valid": ok, "problems": problems, "metadata_without_pdf": orphans, "misplaced_files": misplaced}


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
            meta, actual, problem = check_file(pdf, validator)
            if problem:
                result.rejected.append((rel, problem))
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
            if meta["doc_type"] == "draft":
                conn.execute(
                    """INSERT OR IGNORE INTO consultations(doc_id, issued_date, comment_deadline, hearing_date, related)
                       VALUES (?, ?, ?, ?, ?)""",
                    (actual, meta.get("doc_date"), meta.get("comment_deadline"), meta.get("hearing_date"),
                     json.dumps(meta.get("related", []), ensure_ascii=False)))
            db.audit(conn, "pipeline", "intake", actual, {"inbox_path": rel})
            result.added.append(actual)
        db.finish_run(conn, run_id, len(result.added), len(result.rejected),
                      f"duplicates={result.duplicates}")
    return result
