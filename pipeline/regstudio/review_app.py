"""Legal review screen. Runs on the Mac mini at http://127.0.0.1:8765.

Only this app moves anything from 'proposed' to 'approved', and it records who did it.
With reviewers added (regstudio add-reviewer), every page needs a signed-in reviewer.
"""

from __future__ import annotations

import datetime as dt
import json
import urllib.parse
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import amend, auth, config, db, registry

app = FastAPI(title="Regulatory Studio review")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals.update(COMMISSIONS=config.COMMISSIONS, LINK_TYPES=config.LINK_TYPES,
                             TOPICS=config.TOPICS)


@app.middleware("http")
async def require_sign_in(request: Request, call_next):
    if auth.enabled() and request.url.path not in ("/login",) and not reviewer(request):
        return RedirectResponse("/login", status_code=303)
    return await call_next(request)


def reviewer(request: Request) -> str | None:
    if auth.enabled():
        return auth.read_session(request.cookies.get("rs_session"))
    return request.cookies.get("reviewer")


LOGIN_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sign in · Regulatory Studio review</title><style>body{font:15px -apple-system,sans-serif;background:#f7f8fa;display:grid;place-items:center;height:100vh;margin:0}
form{background:#fff;border:1px solid #d9dde5;border-radius:10px;padding:24px;width:320px}label{display:block;margin:10px 0 4px;color:#5b6475;font-size:13px}
input{width:100%;padding:8px;border:1px solid #d9dde5;border-radius:6px;box-sizing:border-box}button{margin-top:16px;width:100%;padding:9px;border:0;border-radius:6px;background:#1f5fbf;color:#fff}
p{color:#b3261e}</style></head><body><form method="post" action="/login"><b>Regulatory Studio review</b>{error}
<label>Name</label><input name="name" autocomplete="username" required><label>Password</label>
<input name="password" type="password" autocomplete="current-password" required><button>Sign in</button></form></body></html>"""


@app.get("/login", response_class=HTMLResponse)
def login_form():
    if not auth.enabled():
        return back("/")
    return LOGIN_PAGE.replace("{error}", "")


@app.post("/login")
def login(name: str = Form(...), password: str = Form(...)):
    if not auth.enabled():
        return back("/")
    if not auth.check_password(name, password):
        return HTMLResponse(LOGIN_PAGE.replace("{error}", "<p>Name or password not recognised.</p>"), status_code=401)
    resp = back("/")
    resp.set_cookie("rs_session", auth.make_session(name.strip()), max_age=auth.SESSION_HOURS * 3600,
                    httponly=True, samesite="strict")
    return resp


@app.get("/logout")
def logout():
    resp = back("/login")
    resp.delete_cookie("rs_session")
    return resp


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
        amendments = conn.execute(
            """SELECT d.id, d.commission, d.title, d.doc_date, count(a.id) AS open_changes
               FROM documents d JOIN amendment_changes a ON a.amendment_doc = d.id
               WHERE a.status = 'proposed' GROUP BY d.id ORDER BY d.doc_date DESC""").fetchall()
        consultations = conn.execute(
            """SELECT d.id, d.commission, d.title, c.kind, c.comment_deadline, c.hearing_date, c.summary_status
               FROM documents d JOIN consultations c ON c.doc_id = d.id
               WHERE c.summary_status IN ('proposed', 'approved')
               ORDER BY c.summary_status = 'approved', coalesce(c.comment_deadline, '9999') ASC""").fetchall()
        listed = conn.execute("SELECT count(*) FROM documents WHERE stage = 'listed'").fetchone()[0]
        errors = conn.execute("SELECT id, commission, title, error FROM documents WHERE stage = 'error'").fetchall()
    return templates.TemplateResponse(request, "queue.html", {
        "reviewer": reviewer(request), "orders": orders, "regs": regs, "digests": digests, "amendments": amendments,
        "listed": listed, "errors": errors, "sources": _download_health(),
        "consultations": consultations})


def _download_health() -> dict | None:
    """Last `regstudio download` result per commission, so the team can see a site that went quiet."""
    f = config.STORE / "download_last.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except ValueError:
        return None


@app.post("/whoami")
def set_reviewer(name: str = Form(...)):
    if auth.enabled():
        raise HTTPException(403, "Reviewers sign in with a password.")
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
        # A suggested provision for unresolved links; the reviewer still has to approve it.
        suggest = {l["id"]: registry.suggest_target(conn, l["citation_text"], d["commission"])
                   for l in links if not l["target_id"] and l["status"] == "proposed"}
    return templates.TemplateResponse(request, "order.html", {
        "reviewer": reviewer(request), "d": d, "o": o, "links": links, "paras": paras,
        "parties": json.loads(o["parties"] or "[]"), "topics": json.loads(o["topics"] or "[]"),
        "targets": targets, "suggest": suggest, **impact_context(o)})


@app.post("/order/{doc_id}/summary")
def save_summary(request: Request, doc_id: str, action: str = Form(...), summary: str = Form(""),
                 issue: str = Form(""), outcome: str = Form(""), topics: list[str] = Form([]),
                 title: str = Form("")):
    name = need_reviewer(request)
    topics = [t for t in topics if t in config.TOPICS]
    with db.session() as conn:
        prev = conn.execute("SELECT summary_status FROM orders WHERE doc_id = ?", (doc_id,)).fetchone()
        if not prev:
            raise HTTPException(404)
        if title.strip():
            conn.execute("UPDATE documents SET title = ? WHERE id = ?", (title.strip()[:200], doc_id))
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


@app.get("/amendment/{doc_id}", response_class=HTMLResponse)
def amendment(request: Request, doc_id: str):
    with db.session() as conn:
        d = conn.execute("SELECT * FROM documents WHERE id = ? AND doc_type = 'amendment'", (doc_id,)).fetchone()
        if not d:
            raise HTTPException(404)
        changes = conn.execute("SELECT * FROM amendment_changes WHERE amendment_doc = ? ORDER BY id", (doc_id,)).fetchall()
        current = {}
        for c in changes:
            if c["regulation_id"]:
                row = conn.execute("SELECT text, in_force_from FROM clauses WHERE id = ?",
                                   (f"{c['regulation_id']}/{c['clause_number']}",)).fetchone()
                current[c["id"]] = row
        regs = conn.execute("SELECT id, title FROM regulations WHERE status != 'rejected' ORDER BY id").fetchall()
        paras = {r["pid"]: {"text": r["text"], "page": r["page"]} for r in conn.execute(
            "SELECT pid, text, page FROM paragraphs WHERE doc_id = ?", (doc_id,))}
    meta = changes[0] if changes else None
    return templates.TemplateResponse(request, "amendment.html", {
        "reviewer": reviewer(request), "d": d, "changes": changes, "current": current, "regs": regs,
        "paras": paras, "reg_id": meta["regulation_id"] if meta else None,
        "effective": meta["effective_date"] if meta else d["doc_date"], "error": request.query_params.get("error")})


@app.post("/amendment/{doc_id}/meta")
def amendment_meta(request: Request, doc_id: str, regulation_id: str = Form(""), effective_date: str = Form("")):
    name = need_reviewer(request)
    with db.session() as conn:
        if regulation_id and not conn.execute("SELECT 1 FROM regulations WHERE id = ?", (regulation_id,)).fetchone():
            raise HTTPException(400, "Unknown regulation")
        conn.execute("UPDATE amendment_changes SET regulation_id = ?, effective_date = ? WHERE amendment_doc = ? AND status = 'proposed'",
                     (regulation_id or None, effective_date or None, doc_id))
        db.audit(conn, name, "amendment.meta", doc_id, {"regulation": regulation_id, "effective": effective_date})
    return back(f"/amendment/{doc_id}")


@app.post("/amendment-change/{change_id}")
def amendment_change(request: Request, change_id: int, action: str = Form(...), new_text: str = Form(None),
                     clause_number: str = Form(None)):
    name = need_reviewer(request)
    with db.session() as conn:
        ch = conn.execute("SELECT * FROM amendment_changes WHERE id = ?", (change_id,)).fetchone()
        if not ch:
            raise HTTPException(404)
        if ch["status"] == "proposed" and (new_text is not None or clause_number):
            conn.execute("UPDATE amendment_changes SET new_text = coalesce(?, new_text), clause_number = coalesce(?, clause_number) WHERE id = ?",
                         (new_text.strip() if new_text is not None else None, (clause_number or "").strip() or None, change_id))
        if action == "apply":
            try:
                amend.apply_change(conn, change_id, name)
            except amend.ApplyError as e:
                conn.commit()
                return back(f"/amendment/{ch['amendment_doc']}?error={urllib.parse.quote(str(e))}#ch-{change_id}")
        elif action == "reject":
            conn.execute("UPDATE amendment_changes SET status = 'rejected', reviewer = ? WHERE id = ?", (name, change_id))
            db.audit(conn, name, "amendment.reject", str(change_id))
    return back(f"/amendment/{ch['amendment_doc']}#ch-{change_id}")


# --- Draft regulations and consultations ---------------------------------------------------------
KINDS = {"draft_regulation": "Draft regulations", "draft_amendment": "Draft amendment",
         "consultation_paper": "Consultation paper", "proposal": "Proposal"}


@app.get("/consultation/{doc_id}", response_class=HTMLResponse)
def consultation(request: Request, doc_id: str):
    with db.session() as conn:
        d = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        c = conn.execute("SELECT * FROM consultations WHERE doc_id = ?", (doc_id,)).fetchone()
        if not d or not c:
            raise HTTPException(404)
        paras = {r["pid"]: {"text": r["text"], "page": r["page"]} for r in conn.execute(
            "SELECT pid, text, page FROM paragraphs WHERE doc_id = ? ORDER BY page, idx", (doc_id,))}
    return templates.TemplateResponse(request, "consultation.html", {
        "reviewer": reviewer(request), "d": d, "c": c, "paras": paras, "KINDS": KINDS,
        "proposes": json.loads(c["proposes"] or "[]"), "related": json.loads(c["related"] or "[]"), **impact_context(c)})


def _iso_or_none(value: str) -> str | None:
    value = value.strip()
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError:
        raise HTTPException(400, f"Dates are YYYY-MM-DD: {value!r}")


@app.post("/consultation/{doc_id}")
def save_consultation(request: Request, doc_id: str, action: str = Form(...), title: str = Form(""),
                      kind: str = Form("draft_regulation"), summary: str = Form(""), proposes: str = Form(""),
                      comment_deadline: str = Form(""), hearing_date: str = Form(""), amends: str = Form("")):
    name = need_reviewer(request)
    if kind not in KINDS:
        raise HTTPException(400, "Unknown kind.")
    lines = [l.strip(" -•\t") for l in proposes.splitlines() if l.strip(" -•\t")][:8]
    deadline, hearing = _iso_or_none(comment_deadline), _iso_or_none(hearing_date)
    with db.session() as conn:
        if not conn.execute("SELECT 1 FROM consultations WHERE doc_id = ?", (doc_id,)).fetchone():
            raise HTTPException(404)
        if title.strip():
            conn.execute("UPDATE documents SET title = ? WHERE id = ?", (title.strip()[:300], doc_id))
        fields = (kind, summary.strip(), json.dumps(lines, ensure_ascii=False), deadline, hearing,
                  amends.strip() or None)
        if action == "approve":
            if not summary.strip():
                raise HTTPException(400, "Summary is empty.")
            conn.execute("""UPDATE consultations SET kind = ?, summary = ?, proposes = ?, comment_deadline = ?,
                                hearing_date = ?, amends = ?, summary_status = 'approved', reviewer = ?,
                                approved_at = datetime('now') WHERE doc_id = ?""", (*fields, name, doc_id))
        elif action == "save":
            conn.execute("""UPDATE consultations SET kind = ?, summary = ?, proposes = ?, comment_deadline = ?,
                                hearing_date = ?, amends = ? WHERE doc_id = ?""", (*fields, doc_id))
        elif action == "reject":
            conn.execute("UPDATE consultations SET summary_status = 'rejected', reviewer = ? WHERE doc_id = ?",
                         (name, doc_id))
        elif action == "reopen":
            conn.execute("UPDATE consultations SET summary_status = 'proposed' WHERE doc_id = ?", (doc_id,))
        else:
            raise HTTPException(400, "Unknown action.")
        db.audit(conn, name, f"consultation.{action}", doc_id)
    return back(f"/consultation/{doc_id}" if action != "reject" else "/")


# --- Market impact --------------------------------------------------------------------------------
from .impact import EFFECTS as IMPACT_EFFECTS, GROUPS as IMPACT_GROUPS, clean as clean_impact  # noqa: E402


def impact_context(row) -> dict:
    raw = row["impact"] if row is not None and "impact" in row.keys() else None
    return {"impact": json.loads(raw) if raw else None, "GROUPS": IMPACT_GROUPS, "EFFECTS": IMPACT_EFFECTS}


@app.post("/impact/{doc_id}")
async def save_impact(request: Request, doc_id: str):
    name = need_reviewer(request)
    form = await request.form()
    with db.session() as conn:
        table = "orders" if conn.execute("SELECT 1 FROM orders WHERE doc_id = ?", (doc_id,)).fetchone() else "consultations"
        if not conn.execute(f"SELECT 1 FROM {table} WHERE doc_id = ?", (doc_id,)).fetchone():
            raise HTTPException(404)
        if form.get("action") == "clear":
            conn.execute(f"UPDATE {table} SET impact = NULL WHERE doc_id = ?", (doc_id,))
        else:
            lines = lambda k: [l.strip(" -•\t") for l in str(form.get(k, "")).splitlines() if l.strip(" -•\t")]
            out = {"market_note": str(form.get("market_note", "")).strip(), "key_points": lines("key_points"),
                   "procurement": lines("procurement"),
                   "stakeholders": {g: {"level": int(form.get(f"level_{g}", 0) or 0), "effect": str(form.get(f"effect_{g}", "neutral")),
                                        "why": str(form.get(f"why_{g}", "")).strip()} for g in IMPACT_GROUPS}}
            conn.execute(f"UPDATE {table} SET impact = ? WHERE doc_id = ?", (json.dumps(clean_impact(out), ensure_ascii=False), doc_id))
        db.audit(conn, name, f"impact.{form.get('action', 'save')}", doc_id)
    back_to = "/order/" if table == "orders" else "/consultation/"
    return back(f"{back_to}{doc_id}#impact")
