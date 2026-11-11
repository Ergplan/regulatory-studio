"""Amendments: propose clause-level changes, and apply them once a reviewer approves.

Stage `amend` reads each amendment document and proposes, for the principal regulation it
amends, which clauses are substituted, inserted or omitted and from when. Nothing touches the
registry until a reviewer applies a change in the review screen. Applying keeps the old wording
in clause_versions, so a clause page can show what applied when an older order was passed.
"""

from __future__ import annotations

import datetime as dt
import json
import re

from . import config, db, registry
from .claude_runner import ClaudeError, UsageLimitReached, ask_json
from .common import NotPrepared, fill, load_prompt, load_schema, norm, order_text, prepared_output


class ApplyError(ValueError):
    pass


# --- mock reader: common Indian amendment phrasings ------------------------------------------
SUBST = re.compile(r"regulation\s+(\d{1,3}[A-Z]?(?:\(\d{1,2}[a-z]?\))?)(?:(?!regulation)[^.]){0,120}?shall be substituted", re.I)
OMIT = re.compile(r"(?:sub-)?regulation\s+(\d{1,3}[A-Z]?(?:\(\d{1,2}[a-z]?\))?)[^.]{0,80}?shall be omitted", re.I)
INSERT = re.compile(r"after\s+(?:sub-)?regulation\s+(\d{1,3}[A-Z]?(?:\(\d{1,2}[a-z]?\))?)[^.]{0,80}?shall be inserted", re.I)
QUOTED = re.compile(r"[“\"](.+?)[”\"]", re.S)


def _mock(paras: dict[str, str]) -> dict:
    changes, items = [], list(paras.items())
    for i, (pid, text) in enumerate(items):
        nxt = items[i + 1][1] if i + 1 < len(items) else ""
        quoted = QUOTED.search(text + " " + nxt)
        new_text = quoted.group(1).strip() if quoted else nxt.strip()
        for rx, action in ((SUBST, "substitute"), (OMIT, "omit"), (INSERT, "insert")):
            for m in rx.finditer(text):
                number = m.group(1)
                if action == "insert":  # after 8(3) -> new 8(4); reviewer checks the number
                    sub = re.match(r"(\d+[A-Z]?)\((\d+)\)", number)
                    number = f"{sub.group(1)}({int(sub.group(2)) + 1})" if sub else str(int(re.match(r"\d+", number).group()) + 1)
                changes.append({"clause_number": number, "action": action,
                                "new_text": None if action == "omit" else new_text,
                                "pid": pid, "excerpt": text[:280]})
    return {"regulation_id": None, "effective_date": None, "changes": changes}


# --- stage ------------------------------------------------------------------------------------
def run(limit: int | None = None) -> dict:
    schema = load_schema("amend_output.schema.json")
    template = load_prompt("amend.md")
    done = failed = dropped = 0
    stopped = ""
    with db.session() as conn:
        run_id = db.start_run(conn, "amend")
        reg_ids = {r[0] for r in conn.execute("SELECT id FROM regulations WHERE status != 'rejected'")}
        listing = "\n".join(f"{r['id']} | {r['title']}" for r in conn.execute(
            "SELECT id, title FROM regulations WHERE status != 'rejected' ORDER BY id")) or "(none yet)"
        docs = conn.execute(
            "SELECT * FROM documents WHERE stage = 'extracted' AND doc_type = 'amendment' ORDER BY created_at"
            + (f" LIMIT {int(limit)}" if limit else "")).fetchall()
        for d in docs:
            text, paras = order_text(conn, d["id"])
            try:
                if config.READER == "file":
                    out = prepared_output(f"{d['id']}.amend.json", schema)
                elif config.READER == "mock":
                    out = _mock(paras)
                else:
                    out = ask_json(fill(template, schema=json.dumps(schema), commission=config.COMMISSIONS[d["commission"]],
                                        title=d["title"] or "(none)", regulations=listing, text=text), schema)
            except NotPrepared:
                continue
            except UsageLimitReached as e:
                stopped = f"usage limit: {e}"[:300]
                break
            except ClaudeError as e:
                db.set_stage(conn, d["id"], "error", f"amend: {e}"[:500])
                failed += 1
                continue
            reg = out["regulation_id"] if out["regulation_id"] in reg_ids else None
            eff = out["effective_date"] or d["doc_date"]
            conn.execute("DELETE FROM amendment_changes WHERE amendment_doc = ? AND status = 'proposed'", (d["id"],))
            for c in out["changes"]:
                para = paras.get(c["pid"])
                if para is None or norm(c["excerpt"])[:200] not in norm(para):
                    dropped += 1
                    continue
                conn.execute(
                    """INSERT INTO amendment_changes(amendment_doc, regulation_id, clause_number, action, new_text,
                           effective_date, pid, excerpt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (d["id"], reg, c["clause_number"], c["action"], c["new_text"], eff, c["pid"], c["excerpt"]))
            db.set_stage(conn, d["id"], "registered")
            db.audit(conn, "pipeline", "amend", d["id"], {"changes": len(out["changes"]), "regulation": reg})
            done += 1
            conn.commit()
        db.finish_run(conn, run_id, done, failed, stopped)
    return {"amendments": done, "failed": failed, "changes_dropped": dropped, **({"stopped": stopped} if stopped else {})}


# --- applying a reviewed change ---------------------------------------------------------------
def _day_before(iso: str | None) -> str | None:
    return (dt.date.fromisoformat(iso) - dt.timedelta(days=1)).isoformat() if iso else None


def apply_change(conn, change_id: int, reviewer: str) -> str:
    ch = conn.execute("SELECT * FROM amendment_changes WHERE id = ?", (change_id,)).fetchone()
    if not ch or ch["status"] != "proposed":
        raise ApplyError("change not found or already decided")
    if not ch["regulation_id"]:
        raise ApplyError("set the principal regulation for this amendment first")
    if not ch["effective_date"]:
        raise ApplyError("set the amendment's effective date first")
    clause_id = f"{ch['regulation_id']}/{ch['clause_number']}"
    current = conn.execute("SELECT * FROM clauses WHERE id = ?", (clause_id,)).fetchone()
    eff = ch["effective_date"]
    if ch["action"] == "insert":
        if current:
            raise ApplyError(f"clause {ch['clause_number']} already exists; use substitute instead")
        top = ch["clause_number"].split("(")[0]
        parent = conn.execute("SELECT heading FROM clauses WHERE id = ?", (f"{ch['regulation_id']}/{top}",)).fetchone()
        conn.execute(
            """INSERT INTO clauses(id, regulation_id, number, heading, text, in_force_from, amended_by, source_pid,
                   status, reviewer, approved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'approved', ?, datetime('now'))""",
            (clause_id, ch["regulation_id"], ch["clause_number"], parent["heading"] if parent else None,
             ch["new_text"] or "", eff, ch["amendment_doc"], ch["pid"], reviewer))
    else:
        if not current:
            raise ApplyError(f"clause {ch['clause_number']} is not in the registry")
        conn.execute(
            "INSERT INTO clause_versions(clause_id, text, in_force_from, in_force_to, replaced_by) VALUES (?, ?, ?, ?, ?)",
            (clause_id, current["text"], current["in_force_from"], _day_before(eff), change_id))
        if ch["action"] == "substitute":
            conn.execute(
                """UPDATE clauses SET text = ?, in_force_from = ?, in_force_to = NULL, amended_by = ?,
                       status = 'approved', reviewer = ?, approved_at = datetime('now') WHERE id = ?""",
                (ch["new_text"] or "", eff, ch["amendment_doc"], reviewer, clause_id))
        else:  # omit
            conn.execute("UPDATE clauses SET in_force_to = ?, amended_by = ? WHERE id = ?",
                         (_day_before(eff), ch["amendment_doc"], clause_id))
    conn.execute("UPDATE amendment_changes SET status = 'applied', reviewer = ?, applied_at = datetime('now') WHERE id = ?",
                 (reviewer, change_id))
    db.audit(conn, reviewer, f"amendment.{ch['action']}", clause_id, {"change": change_id})
    return clause_id


_ = registry  # registry ids are what regulation_id refers to
