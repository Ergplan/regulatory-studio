"""Stage `draft`: assemble the weekly digest edition.

An edition goes out on a Friday. It carries the orders and drafts read since the last approved edition
(and no older than six weeks), with a lead, key points, numbers to know, up to three charts that compare
documents, and dates to watch. Every key point, number, chart item and dated note must cite a paragraph of
a document in the edition; anything uncited is dropped. The edition is a proposal until a reviewer approves it.
"""

from __future__ import annotations

import datetime as dt
import json
import re

from . import config, db, mock
from .checks import numbers_check
from .claude_runner import ClaudeError, UsageLimitReached, ask_json
from .common import NotPrepared, fill, load_prompt, load_schema, prepared_output, use_prepared

LOOKBACK_DAYS = 42
PID = re.compile(r"^p\d+\.\d+$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def week_bounds(day: dt.date) -> tuple[str, dt.date, dt.date]:
    year, week, _ = day.isocalendar()
    start = day - dt.timedelta(days=day.weekday())
    return f"{year}-W{week:02d}", start, start + dt.timedelta(days=6)


def edition_day(day: dt.date) -> dt.date:
    """The Friday of the week the digest is drafted in."""
    return day - dt.timedelta(days=day.weekday()) + dt.timedelta(days=4)


def candidates(conn, start: dt.date) -> list[dict]:
    """Read orders and drafts not yet in an approved edition, issued (or fetched) within the look-back window."""
    published: set[str] = set()
    for (items,) in conn.execute("SELECT items FROM digests WHERE status = 'approved'"):
        published.update(json.loads(items or "[]"))
    since = (start - dt.timedelta(days=LOOKBACK_DAYS)).isoformat()
    rows = conn.execute(
        """SELECT d.id, d.commission, d.title, d.doc_date, 'order' AS kind, o.summary, o.issue, o.outcome,
                  o.significance, o.impact, o.figures
           FROM documents d JOIN orders o ON o.doc_id = d.id
           WHERE d.stage IN ('read', 'drafted') AND o.summary_status IN ('proposed', 'approved')
             AND coalesce(d.doc_date, date(d.created_at)) >= ?
           UNION ALL
           SELECT d.id, d.commission, d.title, coalesce(c.issued_date, d.doc_date), 'draft' AS kind, c.summary, '' AS issue,
                  c.proposes AS outcome, NULL AS significance, c.impact, c.figures
           FROM documents d JOIN consultations c ON c.doc_id = d.id
           WHERE c.summary_status IN ('proposed', 'approved')
             AND (coalesce(c.comment_deadline, c.hearing_date, '') >= ? OR coalesce(c.issued_date, d.doc_date, date(d.created_at)) >= ?)""",
        (since, start.isoformat(), since)).fetchall()
    return [dict(r) for r in rows if r["id"] not in published]


def _facts(item: dict) -> str:
    """Cited statements already in the item's analysis, which the digest may reuse with their paragraph ids."""
    out = []
    for src in ("impact", "figures"):
        raw = item.get(src)
        if not raw:
            continue
        data = json.loads(raw)
        if src == "impact":
            for k in ("key_points", "procurement"):
                out += [f"[{', '.join(p['basis'])}] {p['text']}" for p in data.get(k) or []]
        else:
            for ch in data:
                for i in ch.get("items", []):
                    val = i.get("value", i.get("start", ""))
                    out.append(f"[{', '.join(i['basis'])}] {ch['title']}: {i['label']} = {val}{(' ' + ch['unit']) if ch.get('unit') else ''}")
    return "\n".join(out[:24])


def _resolve(ref: str, ids: list[str]) -> str | None:
    hits = [i for i in ids if ref and i.startswith(ref)]
    return hits[0] if len(hits) == 1 else None


def clean(out: dict, pids: dict[str, set[str]], texts: dict[str, str]) -> dict:
    """Keep only what is cited to a paragraph of a document in the edition. Numbers must also appear in that document."""
    ids = list(pids)
    order = []
    for r in out.get("order") or []:
        d = _resolve(r, ids)
        if d and d not in order:
            order.append(d)

    def cite(doc, pid):
        d = _resolve(doc or "", ids)
        return d if d and isinstance(pid, str) and PID.match(pid) and pid in pids[d] else None

    points = []
    for p in out.get("key_points") or []:
        basis = [{"doc": d, "pid": b["pid"]} for b in p.get("basis") or [] if (d := cite(b.get("doc"), b.get("pid")))]
        if (p.get("text") or "").strip() and basis:
            points.append({"text": p["text"].strip()[:320], "basis": basis[:4]})
    numbers = []
    for n in out.get("numbers") or []:
        d = cite(n.get("doc"), n.get("pid"))
        value = (n.get("value") or "").strip()[:24]
        if d and value and (n.get("label") or "").strip() and not numbers_check(value, texts[d])["missing"]:
            numbers.append({"value": value, "label": n["label"].strip()[:140], "doc": d, "pid": n["pid"]})
    charts = []
    for ch in (out.get("charts") or [])[:3]:
        kind = ch.get("type")
        items = []
        for i in ch.get("items") or []:
            d = _resolve(i.get("doc") or "", ids)
            basis = [b for b in i.get("basis") or [] if d and isinstance(b, str) and PID.match(b) and b in pids[d]][:3]
            label = (i.get("label") or "").strip()[:60]
            if not (d and basis and label):
                continue
            item = {"label": label, "doc": d, "basis": basis}
            if kind == "timeline":
                if not DATE.match(i.get("start") or ""):
                    continue
                item["start"] = i["start"]
                if DATE.match(i.get("end") or ""):
                    item["end"] = i["end"]
            elif isinstance(i.get("value"), (int, float)):
                item["value"] = i["value"]
            else:
                continue
            for k, n in (("tag", 40),):
                if (i.get(k) or "").strip():
                    item[k] = i[k].strip()[:n]
            if i.get("context"):
                item["context"] = True
            items.append(item)
        if kind in ("bars", "series", "timeline") and len(items) >= 2 and (ch.get("title") or "").strip():
            c = {"type": kind, "title": ch["title"].strip()[:90], "items": items[:10]}
            for k, n in (("unit", 16), ("note", 240)):
                if (ch.get(k) or "").strip():
                    c[k] = ch[k].strip()[:n]
            charts.append(c)
    watch = []
    for w in out.get("watch") or []:
        if not (DATE.match(w.get("date") or "") and (w.get("text") or "").strip()):
            continue
        item = {"date": w["date"], "text": w["text"].strip()[:200]}
        if w.get("doc"):
            d = cite(w.get("doc"), w.get("pid"))
            if not d:
                continue
            item.update(doc=d, pid=w["pid"])
        watch.append(item)
    watch.sort(key=lambda w: w["date"])
    return {"intro": (out.get("intro") or "").strip()[:1200], "order": order, "key_points": points[:6],
            "numbers": numbers[:8], "charts": charts, "watch": watch[:8]}


def run(limit: int | None = None, day: dt.date | None = None) -> dict:
    today = day or dt.date.today()
    week_id, start, end = week_bounds(today)
    friday = edition_day(today)
    with db.session() as conn:
        existing = conn.execute("SELECT status FROM digests WHERE id = ?", (week_id,)).fetchone()
        if existing and existing["status"] == "approved":
            return {"digest": week_id, "note": "already approved; not redrafted"}
        items = candidates(conn, start)
        if not items:
            return {"digest": week_id, "items": 0}
        try:
            if use_prepared(f"{week_id}.digest.json"):
                out = prepared_output(f"{week_id}.digest.json", load_schema("digest_output.schema.json"))
            elif config.READER == "mock":
                out = mock.digest(items)
            else:
                schema = load_schema("digest_output.schema.json")
                listing = "\n\n".join(
                    f"id: {i['id']}\nkind: {i['kind']}\ncommission: {i['commission'].upper()}\ndate: {i['doc_date']}\n"
                    f"title: {i['title']}\nsummary: {i['summary']}\nfacts with their paragraph ids:\n{_facts(i) or '(none)'}"
                    for i in items)
                out = ask_json(fill(load_prompt("digest.md"), schema=json.dumps(schema), items=listing,
                                    edition=friday.isoformat()), schema)
        except NotPrepared:
            return {"digest": week_id, "items": len(items), "note": "digest not prepared yet"}
        except UsageLimitReached as e:
            return {"digest": week_id, "stopped": f"usage limit: {e}"[:300]}
        except ClaudeError as e:
            return {"digest": week_id, "error": str(e)[:300]}
        ids = [i["id"] for i in items]
        pids = {i: {r[0] for r in conn.execute("SELECT pid FROM paragraphs WHERE doc_id = ?", (i,))} for i in ids}
        texts = {i: " ".join(r[0] for r in conn.execute("SELECT text FROM paragraphs WHERE doc_id = ?", (i,))) for i in ids}
        c = clean(out, pids, texts)
        order = c["order"] or ids
        conn.execute(
            """INSERT INTO digests(id, from_date, to_date, edition_date, intro, items, key_points, numbers, charts, watch, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed')
               ON CONFLICT(id) DO UPDATE SET intro = excluded.intro, items = excluded.items, edition_date = excluded.edition_date,
                 key_points = excluded.key_points, numbers = excluded.numbers, charts = excluded.charts, watch = excluded.watch,
                 status = 'proposed'""",
            (week_id, start.isoformat(), end.isoformat(), friday.isoformat(), c["intro"], json.dumps(order),
             json.dumps(c["key_points"]), json.dumps(c["numbers"]), json.dumps(c["charts"]), json.dumps(c["watch"])))
        # an earlier edition that was never approved is replaced by this one
        conn.execute("UPDATE digests SET status = 'superseded' WHERE status = 'proposed' AND id < ?", (week_id,))
        for i in order:
            db.set_stage(conn, i, "drafted")
        dropped = {k: len(out.get(k) or []) - len(c[k]) for k in ("key_points", "numbers", "charts", "watch")}
    return {"digest": week_id, "edition": friday.isoformat(), "items": len(order), "candidates": len(ids),
            **{k: len(c[k]) for k in ("key_points", "numbers", "charts", "watch")},
            **({"dropped_uncited": {k: v for k, v in dropped.items() if v}} if any(dropped.values()) else {})}
