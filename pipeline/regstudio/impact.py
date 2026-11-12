"""Stage `impact`: an evidence-based market impact assessment for chosen orders, drafts and regulations.

Opt-in: only documents a reviewer requested (impact = 'requested', set on the review screen or with
`regstudio run impact --doc <id>`) are assessed. There are no scores. Each key point, procurement item
and stakeholder comment cites paragraph ids from the document's extracted text; anything whose
citations are not in the text is dropped (CLAUDE.md rule 2). Like the summary, the result is a
proposal: the reviewer edits or clears it, and it is published only with the approved summary or
regulation.
"""

from __future__ import annotations

import json
import re

from . import config, db
from .claude_runner import ClaudeError, UsageLimitReached, ask_json
from .common import NotPrepared, fill, load_prompt, load_schema, order_text, prepared_output

GROUPS = {
    "discoms": "Discoms", "ci_consumers": "C&I and open access consumers", "captive": "Captive users",
    "re_developers": "RE developers", "storage": "Storage (BESS, pumped hydro)",
    "conventional": "Thermal and hydro generators", "transmission": "Transmission and system operators",
    "traders": "Traders and exchanges",
}
EFFECTS = ("opportunity", "cost", "mixed")
REQUESTED = "requested"
PID = re.compile(r"^p\d+\.\d+$")

# (table, key column, kind label, summary expression)
TABLES = {
    "orders": ("doc_id", "order", "o.summary"),
    "consultations": ("doc_id", "draft regulation", "o.summary"),
    "regulations": ("doc_id", "notified regulation", "NULL"),
}


def table_for(conn, doc_id: str) -> str | None:
    for t in TABLES:
        if conn.execute(f"SELECT 1 FROM {t} WHERE doc_id = ?", (doc_id,)).fetchone():
            return t
    return None


def request(conn, prefixes: list[str]) -> list[str]:
    """Queue documents (by id prefix) for assessment. Returns the full ids queued."""
    queued = []
    for p in prefixes:
        for t in TABLES:
            for r in conn.execute(f"SELECT doc_id FROM {t} WHERE doc_id LIKE ?", (p + "%",)).fetchall():
                conn.execute(f"UPDATE {t} SET impact = ? WHERE doc_id = ?", (REQUESTED, r[0]))
                queued.append(r[0])
    conn.commit()
    return queued


def _targets(conn, limit):
    rows = []
    for t, (key, kind, summary) in TABLES.items():
        title = "o.title" if t == "regulations" else "d.title"
        rows += conn.execute(
            f"""SELECT d.id, d.commission, {title} AS title, '{kind}' AS kind, {summary} AS summary, '{t}' AS tbl
                FROM {t} o JOIN documents d ON d.id = o.{key} WHERE o.impact = ?""", (REQUESTED,)).fetchall()
    if config.READER == "file":  # a prepared file counts as a request
        for t, (key, kind, summary) in TABLES.items():
            title = "o.title" if t == "regulations" else "d.title"
            for r in conn.execute(f"""SELECT d.id, d.commission, {title} AS title, '{kind}' AS kind, {summary} AS summary,
                                      '{t}' AS tbl FROM {t} o JOIN documents d ON d.id = o.{key} WHERE o.impact IS NULL""").fetchall():
                if (config.READER_OUTPUTS / f"{r['id']}.impact.json").exists():
                    rows.append(r)
    return rows[: int(limit)] if limit else rows


def _basis(b, pids: set[str] | None) -> list[str]:
    out = [p for p in (b or []) if isinstance(p, str) and PID.match(p)]
    return [p for p in out if pids is None or p in pids][:4]


def clean(out: dict, pids: set[str] | None = None) -> dict:
    """Fixed group order, known values only, and every statement backed by a paragraph that exists."""
    def points(items, n):
        res = []
        for it in items or []:
            if isinstance(it, str):  # hand-typed line without citation
                it = {"text": it, "basis": []}
            text, basis = (it.get("text") or "").strip()[:280], _basis(it.get("basis"), pids)
            if text and (basis or pids is None):
                res.append({"text": text, "basis": basis})
        return res[:n]

    cells = {}
    for g in GROUPS:
        c = (out.get("stakeholders") or {}).get(g)
        if not c:
            continue
        comment, basis = (c.get("comment") or "").strip()[:360], _basis(c.get("basis"), pids)
        if comment and c.get("effect") in EFFECTS and (basis or pids is None):
            cells[g] = {"effect": c["effect"], "comment": comment, "basis": basis}
    return {"market_note": (out.get("market_note") or "").strip()[:500],
            "key_points": points(out.get("key_points"), 5), "procurement": points(out.get("procurement"), 6),
            "stakeholders": cells,
            "open_questions": [q.strip()[:240] for q in out.get("open_questions") or [] if q and q.strip()][:3]}


def paragraph_ids(conn, doc_id: str) -> set[str]:
    return {r[0] for r in conn.execute("SELECT pid FROM paragraphs WHERE doc_id = ?", (doc_id,))}


def _mock() -> dict:
    return {"market_note": "", "key_points": [], "procurement": [], "stakeholders": {}, "open_questions": []}


def run(limit: int | None = None, docs: list[str] | None = None) -> dict:
    schema = load_schema("impact_output.schema.json")
    template = load_prompt("impact.md")
    done = failed = dropped = 0
    stopped = ""
    with db.session() as conn:
        if docs:
            request(conn, docs)
        run_id = db.start_run(conn, "impact")
        for d in _targets(conn, limit):
            try:
                if config.READER == "file":
                    out = prepared_output(f"{d['id']}.impact.json", schema)
                elif config.READER == "mock":
                    out = _mock()
                else:
                    text, _ = order_text(conn, d["id"], budget=60_000)
                    out = ask_json(fill(template, schema=json.dumps(schema), kind=d["kind"], title=d["title"] or "(none)",
                                        commission=config.COMMISSIONS[d["commission"]],
                                        summary=d["summary"] or "(none; a notified regulation)", text=text), schema)
            except NotPrepared:
                continue
            except UsageLimitReached as e:
                stopped = f"usage limit: {e}"[:300]
                break
            except ClaudeError as e:
                failed += 1
                db.audit(conn, "pipeline", "impact.error", d["id"], {"error": str(e)[:300]})
                continue
            result = clean(out, paragraph_ids(conn, d["id"]))
            n_in = len(out.get("key_points", [])) + len(out.get("procurement", [])) + len(out.get("stakeholders", {}))
            n_out = len(result["key_points"]) + len(result["procurement"]) + len(result["stakeholders"])
            dropped += n_in - n_out
            conn.execute(f"UPDATE {d['tbl']} SET impact = ? WHERE doc_id = ?", (json.dumps(result, ensure_ascii=False), d["id"]))
            db.audit(conn, "pipeline", "impact", d["id"], {"dropped_uncited": n_in - n_out})
            done += 1
            conn.commit()
        db.finish_run(conn, run_id, done, failed, stopped)
    return {"impact": done, "failed": failed, "dropped_uncited": dropped, **({"stopped": stopped} if stopped else {})}


def load(raw: str | None) -> dict | None:
    """Stored impact as a dict, or None when absent or only requested."""
    if not raw or raw == REQUESTED:
        return None
    return json.loads(raw)
