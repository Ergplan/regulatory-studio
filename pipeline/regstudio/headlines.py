"""Stage `headlines`: a plain-English headline for summaries read before headlines existed.

New summaries get their headline from the read stage. This fills the gap for older ones, from the summary
alone, so it adds no facts. Like the summary it is a proposal the reviewer edits on the review screen.
"""

from __future__ import annotations

import json

from . import config, db
from .claude_runner import ClaudeError, UsageLimitReached, ask_json
from .common import NotPrepared, fill, prepared_output, use_prepared

SCHEMA = {"type": "object", "required": ["headline"], "additionalProperties": False,
          "properties": {"headline": {"type": "string", "minLength": 8, "maxLength": 120}}}
PROMPT = """Write a headline for this summary of an Indian electricity regulatory order, for a business reader:
what the order decides, in at most 15 words. Use only facts in the summary. No quotation marks.
Example: "Rajasthan pays up to Rs 9.99/kWh for peak power from the only bidder".

Return only JSON matching this schema: {schema}

Commission: {commission}
Summary: {summary}"""


def run(limit: int | None = None) -> dict:
    done = failed = 0
    stopped = ""
    with db.session() as conn:
        rows = conn.execute(
            """SELECT d.id, d.commission, o.summary FROM orders o JOIN documents d ON d.id = o.doc_id
               WHERE o.summary IS NOT NULL AND o.headline IS NULL AND o.summary_status IN ('proposed', 'approved')""").fetchall()
        for d in rows[: int(limit)] if limit else rows:
            name = f"{d['id']}.headline.json"
            try:
                if use_prepared(name):
                    out = prepared_output(name, SCHEMA)
                elif config.READER == "mock":
                    continue
                else:
                    out = ask_json(fill(PROMPT, schema=json.dumps(SCHEMA), commission=config.COMMISSIONS[d["commission"]],
                                        summary=d["summary"]), SCHEMA)
            except NotPrepared:
                continue
            except UsageLimitReached as e:
                stopped = f"usage limit: {e}"[:300]
                break
            except ClaudeError as e:
                failed += 1
                db.audit(conn, "pipeline", "headline.error", d["id"], {"error": str(e)[:300]})
                continue
            conn.execute("UPDATE orders SET headline = ? WHERE doc_id = ?", (out["headline"].strip()[:120], d["id"]))
            done += 1
    return {"headlines": done, "failed": failed, **({"stopped": stopped} if stopped else {})}
