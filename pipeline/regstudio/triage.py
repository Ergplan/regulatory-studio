"""Stage 4: decide which orders deserve a summary."""

from __future__ import annotations

import json

from . import config, db, mock
from .claude_runner import ClaudeError, UsageLimitReached, ask_json
from .common import NotPrepared, fill, prepared_output, load_prompt, load_schema, order_text


def run(limit: int | None = None) -> dict:
    schema = load_schema("triage_output.schema.json")
    template = load_prompt("triage.md")
    summarise = listed = failed = 0
    stopped = ""
    with db.session() as conn:
        run_id = db.start_run(conn, "triage")
        docs = conn.execute(
            "SELECT * FROM documents WHERE stage = 'extracted' AND doc_type IN ('order', 'judgment') "
            "ORDER BY created_at" + (f" LIMIT {int(limit)}" if limit else "")).fetchall()
        for d in docs:
            text, _ = order_text(conn, d["id"], budget=40_000)  # triage needs the gist, not everything
            try:
                if config.READER == "file":
                    out = prepared_output(f"{d['id']}.triage.json", schema)
                elif config.READER == "mock":
                    out = mock.triage(text)
                else:
                    prompt = fill(template, topics=", ".join(config.TOPICS), schema=json.dumps(schema),
                                  commission=config.COMMISSIONS[d["commission"]],
                                  title=d["title"] or "(none)", text=text)
                    out = ask_json(prompt, schema)
            except NotPrepared:
                continue  # left at its stage until an output is prepared
            except UsageLimitReached as e:
                stopped = f"usage limit: {e}"[:300]
                break
            except ClaudeError as e:
                db.set_stage(conn, d["id"], "error", f"triage: {e}"[:500])
                failed += 1
                continue
            topics = [t for t in out["topics"] if t in config.TOPICS]
            conn.execute(
                """INSERT INTO orders(doc_id, topics, significance, triage_reason) VALUES (?, ?, ?, ?)
                   ON CONFLICT(doc_id) DO UPDATE SET topics = excluded.topics,
                     significance = excluded.significance, triage_reason = excluded.triage_reason""",
                (d["id"], json.dumps(topics), out["significance"], out["reason"]))
            keep = out["in_scope"] and out["significance"] >= config.SIGNIFICANCE_THRESHOLD
            db.set_stage(conn, d["id"], "triaged" if keep else "listed")
            summarise += keep
            listed += not keep
        db.finish_run(conn, run_id, summarise + listed, failed, stopped)
        conn.commit()
    return {"to_summarise": summarise, "listed_only": listed, "failed": failed,
            **({"stopped": stopped} if stopped else {})}
