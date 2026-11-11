"""Legal review screen. Runs on the Mac mini at http://127.0.0.1:8765.

Only this app moves anything from 'proposed' to 'approved', and it records who did it.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import config, db

app = FastAPI(title="Regulatory Studio review")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals.update(COMMISSIONS=config.COMMISSIONS, LINK_TYPES=config.LINK_TYPES,
                             TOPICS=config.TOPICS)


def reviewer(request: Request) -> str | None:
    return request.cookies.get("reviewer")


def need_reviewer(request: Request) -> str:
    name = reviewer(request)
    if not name:
        raise HTTPException(status_code=403, detail="Set your name on the queue page first.")
    return name


def back(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


@app.get("/", response_class=HTMLResponse)
def queue(request: Request):
    with db.session() as conn:
        orders = conn.execute(
            """SELECT d.id, d.commission, d.title, d.case_number, d.doc_date, d.ocr, d.language,
                      o.significance, o.summary_status,
                      (SELECT count(*) FROM links l WHERE l.from_doc = d.id AND l.status = 'proposed') AS open_links
               FROM documents d JOIN orders o ON o.doc_id = d.id
               WHERE o.summary_status IN ('proposed', 'approved') AND d.stage IN ('read', 'drafted')
               ORDER BY o.summary_status = 'approved', o.significance DESC, d.doc_date DESC""").fetchall()
        regs = conn.execute(
            """SELECT r.id, r.title, r.commission,
                      sum(c.status = 'proposed') AS open_clauses, count(c.id) AS clauses
               FROM regulations r LEFT JOIN clauses c ON c.regulation_id = r.id
               GROUP BY r.id HAVING open_clauses > 0 OR r.status = 'proposed'
               ORDER BY r.commission, r.id""").fetchall()
        digests = conn.execute("SELECT id, status, from_date, to_date FROM digests ORDER BY id DESC LIMIT 6").fetchall()
        listed = conn.execute("SELECT count(*) FROM documents WHERE stage = 'listed'").fetchone()[0]
        errors = conn.execute("SELECT id, commission, title, error FROM documents WHERE stage = 'error'").fetchall()
    return templates.TemplateResponse(request, "queue.html", {
        "reviewer": reviewer(request), "orders": orders, "regs": regs, "digests": digests,
        "listed": listed, "errors": errors})


@app.post("/whoami")
def set_reviewer(name: str = Form(...)):
    resp = back("/")
    resp.set_cookie("reviewer", name.strip()[:80], max_age=60 * 60 * 24 * 180, samesite="lax")
    return resp


@app.get("/file/{doc_id}")
def pdf(doc_id: str):
    with db.session() as conn:
        row = conn.execute("SELECT file_path FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(404)
    return FileResponse(config.STORE / row["file_path"], media_type="application/pdf")


@app.get("/order/{doc_id}", response_class=HTMLResponse)
def order(request: Request, doc_id: str):
    with db.session() as conn:
        d = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        o = conn.execute("SELECT * FROM orders WHERE doc_id = ?", (doc_id,)).fetchone()
        if not d or not o:
            raise HTTPException(404)
        links = conn.execute("SELECT * FROM links WHERE from_doc = ? ORDER BY pid, id", (doc_id,)).fetchall()
        paras = {r["pid"]: {"text": r["text"], "page": r["page"]} for r in conn.execute(
            "SELECT pid, text, page FROM paragraphs WHERE doc_id = ?", (doc_id,))}
        targets = [dict(r) for r in conn.execute(
            """SELECT c.id, 'clause' AS kind, c.number || ' ' || coalesce(c.heading, '') AS label
               FROM clauses c WHERE c.status != 'rejected'
               UNION ALL SELECT id, 'act_section', 'Electricity Act s.' || number || ' ' || title FROM act_sections
               UNION ALL SELECT id, 'regulation', title FROM regulations WHERE status != 'rejected'
               UNION ALL SELECT id, 'document', coalesce(case_number, title, id) FROM documents
                 WHERE doc_type IN ('order', 'judgment') AND id != ?""", (doc_id,))]
    return templates.TemplateResponse(request, "order.html", {
        "reviewer": reviewer(request), "d": d, "o": o, "links": links, "paras": paras,
        "parties": json.loads(o["parties"] or "[]"), "topics": json.loads(o["topics"] or "[]"),
        "targets": targets})


@app.post("/order/{doc_id}/summary")
def save_summary(request: Request, doc_id: str, action: str = Form(...), summary: str = Form(""),
                 issue: str = Form(""), outcome: str = Form(""), topics: list[str] = Form([])):
    name = need_reviewer(request)
    topics = [t for t in topics if t in config.TOPICS]
    with db.session() as conn:
        prev = conn.execute("SELECT summary_status FROM orders WHERE doc_id = ?", (doc_id,)).fetchone()
        if not prev:
            raise HTTPException(404)
        if action == "approve":
            if not summary.strip():
                raise HTTPException(400, "Summary is empty.")
            conn.execute(
                """UPDATE orders SET summary = ?, issue = ?, outcome = ?, topics = ?, summary_status = 'approved',
                       reviewer = ?, approved_at = datetime('now'),
                       revised_at = CASE WHEN ? = 'approved' THEN datetime('now') ELSE revised_at END
                   WHERE doc_id = ?""",
                (summary.strip(), issue.strip(), outcome.strip(), json.dumps(topics), name,
                 prev["summary_status"], doc_id))
        elif action == "save":
            conn.execute("UPDATE orders SET summary = ?, issue = ?, outcome = ?, topics = ? WHERE doc_id = ?",
                         (summary.strip(), issue.strip(), outcome.strip(), json.dumps(topics), doc_id))
        elif action == "reject":
            conn.execute("UPDATE orders SET summary_status = 'rejected', reviewer = ? WHERE doc_id = ?",
                         (name, doc_id))
            db.set_stage(conn, doc_id, "listed")
        db.audit(conn, name, f"summary.{action}", doc_id)
    return back(f"/order/{doc_id}" if action != "reject" else "/")


@app.post("/link/{link_id}")
def decide_link(request: Request, link_id: int, action: str = Form(...), link_type: str = Form(None),
                target: str = Form("")):
    name = need_reviewer(request)
    with db.session() as conn:
        link = conn.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
        if not link:
            raise HTTPException(404)
        if action == "approve":
            kind, tid = _parse_target(conn, target) if target else (link["target_kind"], link["target_id"])
            if not tid:
                raise HTTPException(400, "Pick the provision this citation refers to before approving.")
            lt = link_type if link_type in config.LINK_TYPES else link["link_type"]
            conn.execute(
                """UPDATE links SET status = 'approved', link_type = ?, target_kind = ?, target_id = ?, resolved = 1,
                       reviewer = ?, approved_at = datetime('now') WHERE id = ?""",
                (lt, kind, tid, name, link_id))
        elif action == "reject":
            conn.execute("UPDATE links SET status = 'rejected', reviewer = ? WHERE id = ?", (name, link_id))
        elif action == "reopen":
            conn.execute("UPDATE links SET status = 'proposed', reviewer = NULL, approved_at = NULL WHERE id = ?",
                         (link_id,))
        db.audit(conn, name, f"link.{action}", str(link_id), {"target": target or link["target_id"]})
    return back(f"/order/{link['from_doc']}#link-{link_id}")


def _parse_target(conn, value: str) -> tuple[str, str]:
    kind, _, tid = value.partition("::")
    table = {"clause": "clauses", "act_section": "act_sections", "regulation": "regulations",
             "document": "documents"}.get(kind)
    if not table or not conn.execute(f"SELECT 1 FROM {table} WHERE id = ?", (tid,)).fetchone():
        raise HTTPException(400, f"Unknown target {value!r}")
    return kind, tid


@app.post("/order/{doc_id}/link")
def add_link(request: Request, doc_id: str, link_type: str = Form(...), target: str = Form(...),
             citation_text: str = Form(...), pid: str = Form(...), excerpt: str = Form(...)):
    name = need_reviewer(request)
    if link_type not in config.LINK_TYPES:
        raise HTTPException(400, "Unknown link type")
    with db.session() as conn:
        if not conn.execute("SELECT 1 FROM paragraphs WHERE doc_id = ? AND pid = ?", (doc_id, pid)).fetchone():
            raise HTTPException(400, f"Paragraph {pid} is not in this order.")
        kind, tid = _parse_target(conn, target)
        lid = conn.execute(
            """INSERT INTO links(from_doc, link_type, target_kind, target_id, citation_text, resolved, pid,
                   excerpt, added_by, status, reviewer, approved_at)
               VALUES (?, ?, ?, ?, ?, 1, ?, ?, 'reviewer', 'approved', ?, datetime('now'))""",
            (doc_id, link_type, kind, tid, citation_text.strip(), pid, excerpt.strip(), name)).lastrowid
        db.audit(conn, name, "link.add", str(lid))
    return back(f"/order/{doc_id}#link-{lid}")


@app.get("/regulation/{reg_id:path}", response_class=HTMLResponse)
def regulation(request: Request, reg_id: str):
    with db.session() as conn:
        r = conn.execute("SELECT * FROM regulations WHERE id = ?", (reg_id,)).fetchone()
        if not r:
            raise HTTPException(404)
        clauses = conn.execute(
            "SELECT * FROM clauses WHERE regulation_id = ? ORDER BY CAST(number AS INTEGER), number",
            (reg_id,)).fetchall()
        regs = conn.execute("SELECT id, title FROM regulations WHERE id != ? ORDER BY id", (reg_id,)).fetchall()
    return templates.TemplateResponse(request, "regulation.html", {
        "reviewer": reviewer(request), "r": r, "clauses": clauses, "regs": regs})


@app.post("/regulation/{reg_id:path}/meta")
def save_regulation(request: Request, reg_id: str, title: str = Form(...), short_title: str = Form(""),
                    notified_date: str = Form(""), action: str = Form("save")):
    name = need_reviewer(request)
    with db.session() as conn:
        conn.execute("UPDATE regulations SET title = ?, short_title = ?, notified_date = ? WHERE id = ?",
                     (title.strip(), short_title.strip() or None, notified_date or None, reg_id))
        if action == "approve":
            conn.execute("UPDATE regulations SET status = 'approved', reviewer = ?, approved_at = datetime('now') "
                         "WHERE id = ?", (name, reg_id))
            conn.execute("UPDATE clauses SET status = 'approved', reviewer = ?, approved_at = datetime('now') "
                         "WHERE regulation_id = ? AND status = 'proposed'", (name, reg_id))
        db.audit(conn, name, f"regulation.{action}", reg_id)
    return back(f"/regulation/{reg_id}")


@app.post("/clause/{clause_id:path}")
def save_clause(request: Request, clause_id: str, action: str = Form(...), heading: str = Form(""),
                text: str = Form(""), in_force_from: str = Form(""), in_force_to: str = Form("")):
    name = need_reviewer(request)
    with db.session() as conn:
        c = conn.execute("SELECT regulation_id FROM clauses WHERE id = ?", (clause_id,)).fetchone()
        if not c:
            raise HTTPException(404)
        status = {"approve": "approved", "reject": "rejected"}.get(action)
        conn.execute(
            """UPDATE clauses SET heading = ?, text = ?, in_force_from = ?, in_force_to = ?,
                   status = coalesce(?, status), reviewer = CASE WHEN ? IS NULL THEN reviewer ELSE ? END,
                   approved_at = CASE WHEN ? = 'approved' THEN datetime('now') ELSE approved_at END
               WHERE id = ?""",
            (heading.strip() or None, text.strip(), in_force_from or None, in_force_to or None,
             status, status, name, status, clause_id))
        db.audit(conn, name, f"clause.{action}", clause_id)
    return back(f"/regulation/{c['regulation_id']}#c-{clause_id}")


@app.get("/digest/{week}", response_class=HTMLResponse)
def digest(request: Request, week: str):
    with db.session() as conn:
        dg = conn.execute("SELECT * FROM digests WHERE id = ?", (week,)).fetchone()
        if not dg:
            raise HTTPException(404)
        ids = json.loads(dg["items"] or "[]")
        items = []
        for i in ids:
            row = conn.execute(
                """SELECT d.id, d.commission, d.title, o.summary, o.summary_status FROM documents d
                   JOIN orders o ON o.doc_id = d.id WHERE d.id = ?""", (i,)).fetchone()
            if row:
                items.append(row)
    return templates.TemplateResponse(request, "digest.html", {"reviewer": reviewer(request), "dg": dg,
                                                              "items": items})


@app.post("/digest/{week}")
def save_digest(request: Request, week: str, intro: str = Form(...), action: str = Form("save")):
    name = need_reviewer(request)
    with db.session() as conn:
        conn.execute("UPDATE digests SET intro = ? WHERE id = ?", (intro.strip(), week))
        if action == "approve":
            conn.execute("UPDATE digests SET status = 'approved', reviewer = ?, approved_at = datetime('now') "
                         "WHERE id = ?", (name, week))
        db.audit(conn, name, f"digest.{action}", week)
    return back(f"/digest/{week}")
