"""Stage `figures`: small charts for a summary, chosen from what the document contains.

Runs for every order and draft that has a summary (and for regulations with an impact assessment).
The model picks at most three charts (bars, series, timeline) and may pick none. The rules that
make a chart acceptable are enforced here, not left to the prompt: enough items, one unit, valid
dates, and a paragraph citation that exists for every item. Like the summary, charts are proposals
and are published only with the approved summary.
"""

from __future__ import annotations

import datetime as dt
import json

from . import config, db
from .claude_runner import ClaudeError, UsageLimitReached, ask_json
from .common import NotPrepared, fill, load_prompt, load_schema, order_text, prepared_output
from .impact import PID, paragraph_ids

MIN_ITEMS = {"bars": 2, "series": 3, "timeline": 2, "flow": 2}
MAX_ITEMS = {"bars": 8, "series": 12, "timeline": 8, "flow": 7}
TABLES = {  # table -> (kind label, summary expression, extra condition)
    "orders": ("order", "o.summary", "o.summary IS NOT NULL"),
    "consultations": ("draft regulation", "o.summary", "o.summary IS NOT NULL"),
    "regulations": ("notified regulation", "NULL", "o.impact IS NOT NULL AND o.impact != 'requested'"),
}


def _date(s) -> str | None:
    try:
        return dt.date.fromisoformat(str(s)).isoformat()
    except ValueError:
        return None


def clean(out: dict, pids: set[str] | None = None) -> list[dict]:
    """Keep only charts that are sound: known type, enough cited items, usable values or dates."""
    charts = []
    for ch in (out.get("charts") or [])[:4]:
        kind = ch.get("type")
        if kind not in MIN_ITEMS:
            continue
        items = []
        for it in ch.get("items") or []:
            basis = [b for b in it.get("basis") or [] if isinstance(b, str) and PID.match(b) and (pids is None or b in pids)][:4]
            label = (it.get("label") or "").strip()[:60]
            if not label or not (basis or pids is None):
                continue
            item = {"label": label, "basis": basis}
            if kind == "flow":
                for k, n in (("detail", 160), ("otherwise", 140)):
                    if (it.get(k) or "").strip():
                        item[k] = it[k].strip()[:n]
            elif kind == "timeline":
                start, end = _date(it.get("start")), _date(it.get("end")) if it.get("end") else None
                if not start or (end and end < start):
                    continue
                item["start"] = start
                if end and end != start:
                    item["end"] = end
            else:
                v = it.get("value")
                if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
                    continue
                item["value"] = v
                if (it.get("tag") or "").strip():
                    item["tag"] = it["tag"].strip()[:28]
                if it.get("context") is True:
                    item["context"] = True
            items.append(item)
        items = items[: MAX_ITEMS[kind]]
        title = (ch.get("title") or "").strip()[:90]
        if len(items) < MIN_ITEMS[kind] or not title:
            continue
        if kind == "bars" and all(i.get("context") for i in items):
            for i in items:
                i.pop("context", None)
        chart = {"type": kind, "title": title, "items": items}
        if kind in ("bars", "series"):
            chart["unit"] = (ch.get("unit") or "").strip()[:16]
        if (ch.get("note") or "").strip():
            chart["note"] = ch["note"].strip()[:180]
        charts.append(chart)
    return charts


def _targets(conn, limit):
    rows = []
    for t, (kind, summary, cond) in TABLES.items():
        title = "o.title" if t == "regulations" else "d.title"
        rows += conn.execute(
            f"""SELECT d.id, d.commission, {title} AS title, '{kind}' AS kind, {summary} AS summary, '{t}' AS tbl
                FROM {t} o JOIN documents d ON d.id = o.doc_id WHERE o.figures IS NULL AND {cond}""").fetchall()
    return rows[: int(limit)] if limit else rows


def run(limit: int | None = None) -> dict:
    schema = load_schema("figures_output.schema.json")
    template = load_prompt("figures.md")
    done = failed = charts = 0
    stopped = ""
    with db.session() as conn:
        run_id = db.start_run(conn, "figures")
        for d in _targets(conn, limit):
            try:
                if config.READER == "file":
                    out = prepared_output(f"{d['id']}.figures.json", schema)
                elif config.READER == "mock":
                    continue
                else:
                    text, _ = order_text(conn, d["id"], budget=60_000)
                    out = ask_json(fill(template, schema=json.dumps(schema), kind=d["kind"], title=d["title"] or "(none)",
                                        commission=config.COMMISSIONS[d["commission"]], summary=d["summary"] or "(none)", text=text), schema)
            except NotPrepared:
                continue
            except UsageLimitReached as e:
                stopped = f"usage limit: {e}"[:300]
                break
            except ClaudeError as e:
                failed += 1
                db.audit(conn, "pipeline", "figures.error", d["id"], {"error": str(e)[:300]})
                continue
            result = clean(out, paragraph_ids(conn, d["id"]))
            conn.execute(f"UPDATE {d['tbl']} SET figures = ? WHERE doc_id = ?", (json.dumps(result, ensure_ascii=False), d["id"]))
            db.audit(conn, "pipeline", "figures", d["id"], {"charts": len(result), "offered": len(out.get("charts") or [])})
            done += 1
            charts += len(result)
            conn.commit()
        db.finish_run(conn, run_id, done, failed, stopped)
    return {"figures": done, "charts": charts, "failed": failed, **({"stopped": stopped} if stopped else {})}


def load(raw: str | None) -> list[dict]:
    return json.loads(raw) if raw else []
