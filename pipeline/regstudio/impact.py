"""Stage `impact`: market impact, procurement requirements and a stakeholder heat-map row.

Runs on orders and drafts that already have a proposed summary. Like the summary, the assessment is
a proposal: the reviewer edits or clears it on the review screen, and it is published only with an
approved summary.
"""

from __future__ import annotations

import json

from . import config, db
from .claude_runner import ClaudeError, UsageLimitReached, ask_json
from .common import NotPrepared, fill, load_prompt, load_schema, order_text, prepared_output

GROUPS = {
    "discoms": "Discoms", "ci_consumers": "C&I and open access consumers", "captive": "Captive users",
    "re_developers": "RE developers", "storage": "Storage (BESS, pumped hydro)",
    "conventional": "Thermal and hydro generators", "transmission": "Transmission and system operators",
    "traders": "Traders and exchanges",
}
EFFECTS = ("opportunity", "cost", "mixed", "neutral")


def _targets(conn, limit):
    rows = conn.execute(
        """SELECT d.id, d.commission, d.title, 'order' AS kind, o.summary FROM documents d JOIN orders o ON o.doc_id = d.id
           WHERE o.summary_status = 'proposed' AND o.impact IS NULL AND o.summary IS NOT NULL
           UNION ALL
           SELECT d.id, d.commission, d.title, 'draft regulation' AS kind, c.summary FROM documents d
           JOIN consultations c ON c.doc_id = d.id
           WHERE c.summary_status = 'proposed' AND c.impact IS NULL AND c.summary IS NOT NULL""").fetchall()
    return rows[: int(limit)] if limit else rows


def _mock(summary: str) -> dict:
    return {"market_note": "", "key_points": [], "procurement": [],
            "stakeholders": {g: {"level": 0, "effect": "neutral", "why": ""} for g in GROUPS}}


def clean(out: dict) -> dict:
    """Keep only known groups, in a fixed order, with sane values."""
    cells = {}
    for g in GROUPS:
        c = (out.get("stakeholders") or {}).get(g) or {}
        level = max(0, min(3, int(c.get("level", 0) or 0)))
        effect = c.get("effect") if c.get("effect") in EFFECTS else "neutral"
        cells[g] = {"level": level, "effect": effect if level else "neutral", "why": (c.get("why") or "")[:200]}
    return {"market_note": (out.get("market_note") or "")[:400], "key_points": [p for p in out.get("key_points", []) if p][:5],
            "procurement": [p for p in out.get("procurement", []) if p][:6], "stakeholders": cells}


def run(limit: int | None = None) -> dict:
    schema = load_schema("impact_output.schema.json")
    template = load_prompt("impact.md")
    done = failed = 0
    stopped = ""
    with db.session() as conn:
        run_id = db.start_run(conn, "impact")
        for d in _targets(conn, limit):
            try:
                if config.READER == "file":
                    out = prepared_output(f"{d['id']}.impact.json", schema)
                elif config.READER == "mock":
                    out = _mock(d["summary"])
                else:
                    text, _ = order_text(conn, d["id"], budget=40_000)
                    out = ask_json(fill(template, schema=json.dumps(schema), kind=d["kind"], title=d["title"] or "(none)",
                                        commission=config.COMMISSIONS[d["commission"]], summary=d["summary"], text=text), schema)
            except NotPrepared:
                continue
            except UsageLimitReached as e:
                stopped = f"usage limit: {e}"[:300]
                break
            except ClaudeError as e:
                failed += 1
                db.audit(conn, "pipeline", "impact.error", d["id"], {"error": str(e)[:300]})
                continue
            table = "orders" if d["kind"] == "order" else "consultations"
            conn.execute(f"UPDATE {table} SET impact = ? WHERE doc_id = ?", (json.dumps(clean(out), ensure_ascii=False), d["id"]))
            db.audit(conn, "pipeline", "impact", d["id"])
            done += 1
            conn.commit()
        db.finish_run(conn, run_id, done, failed, stopped)
    return {"impact": done, "failed": failed, **({"stopped": stopped} if stopped else {})}
