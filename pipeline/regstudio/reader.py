"""Stage 5: read each triaged order; extract parties, issue, outcome, summary and references.

Everything the model returns is checked here before it is stored:
- a reference whose paragraph id is not in the order is dropped;
- a reference whose excerpt is not found in that paragraph is dropped;
- a target id that is not in the registry, the Act sections or the documents table is
  cleared and the link stored as unresolved.
"""

from __future__ import annotations

import json
import re

from . import config, db, mock, registry
from .claude_runner import ClaudeError, UsageLimitReached, ask_json
from .common import NotPrepared, fill, prepared_output, load_prompt, load_schema, norm, order_text, use_prepared

CASE_NO = re.compile(r"(?:petition|appeal|case|o\.?p\.?|i\.?a\.?)\s*no\.?\s*([\w\-/]+\s*(?:of|/)\s*\d{4})", re.I)


def _valid_targets(conn) -> dict[str, set[str]]:
    return {
        "clause": {r[0] for r in conn.execute("SELECT id FROM clauses WHERE status != 'rejected'")},
        "regulation": {r[0] for r in conn.execute("SELECT id FROM regulations WHERE status != 'rejected'")},
        "act_section": {r[0] for r in conn.execute("SELECT id FROM act_sections")},
        "document": {r[0] for r in conn.execute("SELECT id FROM documents")},
    }


def _match_document(conn, citation: str) -> str | None:
    m = CASE_NO.search(citation)
    if not m:
        return None
    key = norm(m.group(1)).replace(" ", "")
    for row in conn.execute("SELECT id, case_number FROM documents WHERE case_number IS NOT NULL"):
        if key and key in norm(row["case_number"]).replace(" ", ""):
            return row["id"]
    return None


def check_references(conn, refs: list[dict], paras: dict[str, str]) -> tuple[list[dict], list[str]]:
    targets = _valid_targets(conn)
    kept, dropped = [], []
    for r in refs:
        para = paras.get(r["pid"])
        if para is None:
            dropped.append(f"{r['citation_text']}: paragraph {r['pid']} not in order")
            continue
        if norm(r["excerpt"])[:200] not in norm(para):
            dropped.append(f"{r['citation_text']}: excerpt not found in {r['pid']}")
            continue
        tid = r.get("target_id")
        if r["target_kind"] == "document" and not tid:
            tid = _match_document(conn, r["citation_text"])
        resolved = bool(tid) and tid in targets.get(r["target_kind"], set())
        kept.append({**r, "target_id": tid if resolved else None, "resolved": int(resolved)})
    return kept, dropped


def _registry_listing(conn, commission: str) -> str:
    rows = registry.lookup_index(conn)
    scope = {commission, "cerc"} if commission != "aptel" else None
    lines = [f"{r['clause_id']} | {r['heading'] or ''}" for r in rows
             if scope is None or r["commission"] in scope]
    return "\n".join(lines) or "(registry empty for this commission)"


def run(limit: int | None = None) -> dict:
    schema = load_schema("read_output.schema.json")
    template = load_prompt("read.md")
    done = failed = dropped_total = 0
    stopped = ""
    with db.session() as conn:
        run_id = db.start_run(conn, "read")
        acts = "\n".join(f"{r['id']} | Section {r['number']}: {r['title']}"
                         for r in conn.execute("SELECT * FROM act_sections ORDER BY CAST(number AS INTEGER)"))
        docs = conn.execute(
            "SELECT * FROM documents WHERE stage = 'triaged' ORDER BY created_at"
            + (f" LIMIT {int(limit)}" if limit else "")).fetchall()
        for d in docs:
            text, paras = order_text(conn, d["id"])
            try:
                if use_prepared(f"{d['id']}.read.json"):
                    out = prepared_output(f"{d['id']}.read.json", schema)
                elif config.READER == "mock":
                    out = mock.read(paras, registry.lookup_index(conn), d["commission"])
                else:
                    prompt = fill(template, schema=json.dumps(schema),
                                  commission=config.COMMISSIONS[d["commission"]],
                                  title=d["title"] or "(none)",
                                  registry=_registry_listing(conn, d["commission"]),
                                  act_sections=acts, text=text)
                    out = ask_json(prompt, schema)
            except NotPrepared:
                continue  # left at its stage until an output is prepared
            except UsageLimitReached as e:
                stopped = f"usage limit: {e}"[:300]
                break
            except ClaudeError as e:
                db.set_stage(conn, d["id"], "error", f"read: {e}"[:500])
                failed += 1
                continue
            refs, dropped = check_references(conn, out["references"], paras)
            dropped_total += len(dropped)
            conn.execute("DELETE FROM links WHERE from_doc = ? AND added_by = 'model' AND status = 'proposed'",
                         (d["id"],))
            seen = set()
            for r in refs:
                key = (r["link_type"], r["target_id"] or r["citation_text"], r["pid"])
                if key in seen:
                    continue
                seen.add(key)
                conn.execute(
                    """INSERT INTO links(from_doc, link_type, target_kind, target_id, citation_text,
                           resolved, pid, excerpt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (d["id"], r["link_type"], r["target_kind"], r["target_id"], r["citation_text"],
                     r["resolved"], r["pid"], r["excerpt"]))
            conn.execute(
                """UPDATE orders SET parties = ?, issue = ?, outcome = ?, summary = ?, headline = ?,
                       summary_status = 'proposed' WHERE doc_id = ?""",
                (json.dumps(out["parties"]), out["issue"], out["outcome"], out["summary"],
                 (out.get("headline") or "").strip()[:120] or None, d["id"]))
            db.set_stage(conn, d["id"], "read")
            db.audit(conn, "pipeline", "read", d["id"], {"links": len(refs), "dropped": dropped})
            done += 1
            conn.commit()  # keep finished orders if a later one hits the usage limit
        db.finish_run(conn, run_id, done, failed, stopped)
    return {"read": done, "failed": failed, "references_dropped": dropped_total,
            **({"stopped": stopped} if stopped else {})}
