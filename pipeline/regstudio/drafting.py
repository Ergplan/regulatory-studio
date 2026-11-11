"""Stage 6: assemble the weekly digest from orders read this week."""

from __future__ import annotations

import datetime as dt
import json

from . import config, db, mock
from .claude_runner import ClaudeError, UsageLimitReached, ask_json
from .common import fill, load_prompt, load_schema


def week_bounds(day: dt.date) -> tuple[str, dt.date, dt.date]:
    year, week, _ = day.isocalendar()
    start = day - dt.timedelta(days=day.weekday())
    return f"{year}-W{week:02d}", start, start + dt.timedelta(days=6)


def run(limit: int | None = None, day: dt.date | None = None) -> dict:
    week_id, start, end = week_bounds(day or dt.date.today())
    with db.session() as conn:
        existing = conn.execute("SELECT status FROM digests WHERE id = ?", (week_id,)).fetchone()
        if existing and existing["status"] == "approved":
            return {"digest": week_id, "note": "already approved; not redrafted"}
        rows = conn.execute(
            """SELECT d.id, d.commission, d.title, o.summary, o.significance FROM documents d
               JOIN orders o ON o.doc_id = d.id
               WHERE d.stage IN ('read', 'drafted') AND o.summary_status IN ('proposed', 'approved')
                 AND date(d.created_at) BETWEEN ? AND ?""",
            (start.isoformat(), end.isoformat())).fetchall()
        items = [dict(r) for r in rows]
        if not items:
            return {"digest": week_id, "items": 0}
        try:
            if config.READER == "mock":
                out = mock.digest(items)
            else:
                schema = load_schema("digest_output.schema.json")
                listing = "\n\n".join(
                    f"id: {i['id']}\ncommission: {i['commission'].upper()}\nsignificance: {i['significance']}\n"
                    f"title: {i['title']}\nsummary: {i['summary']}" for i in items)
                out = ask_json(fill(load_prompt("digest.md"), schema=json.dumps(schema), items=listing), schema)
        except UsageLimitReached as e:
            return {"digest": week_id, "stopped": f"usage limit: {e}"[:300]}
        except ClaudeError as e:
            return {"digest": week_id, "error": str(e)[:300]}
        ids = {i["id"] for i in items}
        order = [i for i in out["order"] if i in ids] + [i for i in ids if i not in out["order"]]
        conn.execute(
            """INSERT INTO digests(id, from_date, to_date, intro, items, status) VALUES (?, ?, ?, ?, ?, 'proposed')
               ON CONFLICT(id) DO UPDATE SET intro = excluded.intro, items = excluded.items,
                 status = 'proposed'""",
            (week_id, start.isoformat(), end.isoformat(), out["intro"], json.dumps(order)))
        for i in ids:
            db.set_stage(conn, i, "drafted")
    return {"digest": week_id, "items": len(items)}
