"""Stage `consult`: summarise draft regulations and consultations for the review screen.

Each draft gets a proposed summary, its main proposed changes, and its comment deadline and hearing
date. Deadlines from the commission's listing (stored at intake) win over anything read from the
text. Nothing is approved here; a reviewer approves on the review screen.
"""

from __future__ import annotations

import json
import re

from . import config, db
from .claude_runner import ClaudeError, UsageLimitReached, ask_json
from .common import NotPrepared, fill, load_prompt, load_schema, order_text, prepared_output
from .download.sites import _any_date

DEADLINE = re.compile(r"(?:on or before|last date[^.]{0,60}?|latest by|not later than|by)\s+"
                      r"(\d{1,2}(?:st|nd|rd|th)?[\s./-]+(?:\d{1,2}|[A-Za-z]{3,9})[\s.,/-]+\d{4})", re.I)
HEARING = re.compile(r"public hearing[^.]{0,80}?on\s+(\d{1,2}(?:st|nd|rd|th)?[\s./-]+(?:\d{1,2}|[A-Za-z]{3,9})"
                     r"[\s.,/-]+\d{4})", re.I)


def _kind(title: str) -> str:
    t = (title or "").lower()
    if "consultation" in t or "discussion paper" in t or "approach paper" in t:
        return "consultation_paper"
    if t.startswith("proposal") or "suo motu" in t:
        return "proposal"
    return "draft_amendment" if "amendment" in t else "draft_regulation"


def _mock(title: str, paras: dict[str, str]) -> dict:
    text = " ".join(paras.values())
    deadline = DEADLINE.search(text)
    hearing = HEARING.search(text)
    body = [p for p in paras.values() if len(p) > 80][:2]
    return {"kind": _kind(title), "summary": ("Proposal: " + " ".join(body))[:1500] if body else "Proposal.",
            "proposes": [], "comment_deadline": _any_date(deadline.group(1)) if deadline else None,
            "hearing_date": _any_date(hearing.group(1)) if hearing else None, "amends": None}


def run(limit: int | None = None) -> dict:
    schema = load_schema("consult_output.schema.json")
    template = load_prompt("consult.md")
    done = failed = 0
    stopped = ""
    with db.session() as conn:
        run_id = db.start_run(conn, "consult")
        rows = conn.execute(
            """SELECT d.*, c.comment_deadline AS listed_deadline, c.hearing_date AS listed_hearing
               FROM documents d JOIN consultations c ON c.doc_id = d.id
               WHERE d.stage = 'extracted' AND d.doc_type = 'draft' AND c.summary_status = 'none'
               ORDER BY d.created_at""" + (f" LIMIT {int(limit)}" if limit else "")).fetchall()
        for d in rows:
            text, paras = order_text(conn, d["id"], budget=60_000)
            try:
                if config.READER == "file":
                    out = prepared_output(f"{d['id']}.consult.json", schema)
                elif config.READER == "mock":
                    out = _mock(d["title"], paras)
                else:
                    out = ask_json(fill(template, schema=json.dumps(schema), title=d["title"] or "(none)",
                                        commission=config.COMMISSIONS[d["commission"]], text=text), schema)
            except NotPrepared:
                continue
            except UsageLimitReached as e:
                stopped = f"usage limit: {e}"[:300]
                break
            except ClaudeError as e:
                db.set_stage(conn, d["id"], "error", f"consult: {e}"[:500])
                failed += 1
                continue
            conn.execute(
                """UPDATE consultations SET kind = ?, summary = ?, proposes = ?, amends = ?,
                       comment_deadline = coalesce(?, ?), hearing_date = coalesce(?, ?),
                       summary_status = 'proposed' WHERE doc_id = ?""",
                (out["kind"], out["summary"], json.dumps(out["proposes"], ensure_ascii=False), out["amends"],
                 d["listed_deadline"], out["comment_deadline"], d["listed_hearing"], out["hearing_date"], d["id"]))
            db.set_stage(conn, d["id"], "read")
            db.audit(conn, "pipeline", "consult", d["id"], {"kind": out["kind"]})
            done += 1
            conn.commit()
        db.finish_run(conn, run_id, done, failed, stopped)
    return {"consultations": done, "failed": failed, **({"stopped": stopped} if stopped else {})}
