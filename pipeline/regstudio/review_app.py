"""Legal review screen. Runs on the Mac mini at http://127.0.0.1:8765.

Only this app moves anything from 'proposed' to 'approved', and it records who did it.
With reviewers added (regstudio add-reviewer), every page needs a signed-in reviewer.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import urllib.parse
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from . import access, amend, auth, commercial, config, db, deploy, learning, priority, registry

app = FastAPI(title="Regulatory Studio review")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals.update(COMMISSIONS=config.COMMISSIONS, LINK_TYPES=config.LINK_TYPES,
                             TOPICS=config.TOPICS)
templates.env.filters["inr"] = lambda v: commercial.fmt(float(v), 0 if float(v) == int(float(v)) else 2)


@app.middleware("http")
async def require_sign_in(request: Request, call_next):
    # A request that came through the Cloudflare Tunnel must carry a valid Access token for a registered
    # reviewer. Nothing arriving from the internet is ever let in on a typed name or a missing check.
    if access.through_cloudflare(request.headers):
        try:
            email = access.verify(request.headers.get(access.HEADER))
        except access.AccessError as e:
            return HTMLResponse(REFUSED.format(why=f"Cloudflare Access check failed: {e}."), status_code=403)
        name = auth.by_email(email)
        if not name:
            return HTMLResponse(REFUSED.format(why=f"{email} is signed in but is not registered as a reviewer. "
                                                  "Ask the administrator to run: regstudio add-reviewer \"Your Name\" --email " + email), status_code=403)
        request.state.reviewer = name
        return await call_next(request)
    if auth.enabled() and request.url.path not in ("/login",) and not reviewer(request):
        return RedirectResponse("/login", status_code=303)
    return await call_next(request)


REFUSED = """<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Not allowed · Regulatory Studio review</title>
<style>body{{font:15px -apple-system,sans-serif;background:#f7f8fa;display:grid;place-items:center;height:100vh;margin:0}}
div{{background:#fff;border:1px solid #d9dde5;border-radius:10px;padding:24px;max-width:460px}}</style></head>
<body><div><b>Regulatory Studio review</b><p>{why}</p></div></body></html>"""


def reviewer(request: Request) -> str | None:
    if getattr(request.state, "reviewer", None):
        return request.state.reviewer
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
def login(request: Request, name: str = Form(...), password: str = Form(...)):
    if not auth.enabled():
        return back("/")
    if not auth.allow_attempt(name):
        return HTMLResponse(LOGIN_PAGE.replace("{error}", "<p>Too many attempts. Try again in 15 minutes.</p>"), status_code=429)
    if not auth.check_password(name, password):
        return HTMLResponse(LOGIN_PAGE.replace("{error}", "<p>Name or password not recognised.</p>"), status_code=401)
    resp = back("/")
    resp.set_cookie("rs_session", auth.make_session(name.strip()), max_age=auth.SESSION_HOURS * 3600,
                    httponly=True, samesite="strict", secure=request.url.scheme == "https")
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
                      o.significance, o.summary_status, o.summary, o.issue, o.outcome, o.headline, o.topics, o.impact, o.parties,
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
            """SELECT d.id, d.commission, d.title, c.kind, c.comment_deadline, c.hearing_date, c.summary_status,
                      c.summary, c.proposes, c.amends, c.impact
               FROM documents d JOIN consultations c ON c.doc_id = d.id
               WHERE c.summary_status IN ('proposed', 'approved')
               ORDER BY c.summary_status = 'approved', coalesce(c.comment_deadline, '9999') ASC""").fetchall()
        listed = conn.execute("SELECT count(*) FROM documents WHERE stage = 'listed'").fetchone()[0]
        errors = conn.execute("SELECT id, commission, title, error FROM documents WHERE stage = 'error'").fetchall()
    orders = sorted((dict(o) | {"priority": priority.for_order(o)} for o in orders),
                    key=lambda o: (o["summary_status"] == "approved", -o["priority"]["score"]))
    consultations = sorted((dict(c) | {"priority": priority.for_consultation(c)} for c in consultations),
                           key=lambda c: (c["summary_status"] == "approved", -c["priority"]["score"]))
    first = sorted([o | {"href": f"/order/{o['id']}", "what": "Order"} for o in orders if o["summary_status"] == "proposed"]
                   + [c | {"href": f"/consultation/{c['id']}", "what": "Draft"} for c in consultations if c["summary_status"] == "proposed"],
                   key=lambda i: -i["priority"]["score"])[:8]
    return templates.TemplateResponse(request, "queue.html", {
        "reviewer": reviewer(request), "orders": orders, "first": first, "regs": regs, "digests": digests, "amendments": amendments,
        "listed": listed, "errors": errors, "sources": _download_health(), "deploy": deploy.last(), "scan": _last_scan(),
        "consultations": consultations})


def _last_scan() -> dict | None:
    f = config.STORE / "scan_last.json"
    try:
        return json.loads(f.read_text()) if f.exists() else None
    except ValueError:
        return None


@app.post("/deploy")
def deploy_now(request: Request, background: BackgroundTasks):
    """Push approved items to the public site now, instead of waiting for the next automatic push."""
    name = need_reviewer(request)
    with db.session() as conn:
        db.audit(conn, name, "deploy.request", "production")
    background.add_task(deploy.run)
    return back("/#site")


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
        "targets": targets, "suggest": suggest, **impact_context(o), **notes_context(doc_id, o, True)})


@app.post("/order/{doc_id}/summary")
def save_summary(request: Request, doc_id: str, action: str = Form(...), summary: str = Form(""),
                 issue: str = Form(""), outcome: str = Form(""), topics: list[str] = Form([]),
                 title: str = Form(""), headline: str = Form("")):
    name = need_reviewer(request)
    topics = [t for t in topics if t in config.TOPICS]
    with db.session() as conn:
        prev = conn.execute("SELECT summary_status FROM orders WHERE doc_id = ?", (doc_id,)).fetchone()
        if not prev:
            raise HTTPException(404)
        if title.strip():
            conn.execute("UPDATE documents SET title = ? WHERE id = ?", (title.strip()[:200], doc_id))
        conn.execute("UPDATE orders SET headline = ? WHERE doc_id = ?", (headline.strip()[:120] or None, doc_id))
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
        "reviewer": reviewer(request), "r": r, "clauses": clauses, "regs": regs, **impact_context(r)})


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
                """SELECT d.id, d.commission, d.title, d.doc_date, 'order' AS kind, o.summary, o.summary_status FROM documents d
                   JOIN orders o ON o.doc_id = d.id WHERE d.id = ?
                   UNION ALL
                   SELECT d.id, d.commission, d.title, d.doc_date, 'draft' AS kind, c.summary, c.summary_status FROM documents d
                   JOIN consultations c ON c.doc_id = d.id WHERE d.id = ?""", (i, i)).fetchone()
            if row:
                items.append(dict(row))
        names = {i["id"]: f"{i['commission'].upper()} · {(i['title'] or i['id'][:10])[:70]}" for i in items}
        edition = {k: json.loads(dg[k] or "[]") if k in dg.keys() else [] for k in ("key_points", "numbers", "charts", "watch")}
        texts = {}
        for ref in [b for p in edition["key_points"] for b in p["basis"]] + edition["numbers"] + [w for w in edition["watch"] if w.get("doc")]:
            r = conn.execute("SELECT text FROM paragraphs WHERE doc_id = ? AND pid = ?", (ref["doc"], ref["pid"])).fetchone()
            texts[(ref["doc"], ref["pid"])] = r[0] if r else "(paragraph not found)"
    with db.session() as conn:
        dnotes = learning.comments_for(conn, digest_id=week)
    return templates.TemplateResponse(request, "digest.html", {"reviewer": reviewer(request), "dg": dg, "items": items, "dnotes": dnotes,
                                                              "names": names, "texts": texts, **edition})


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
        "proposes": json.loads(c["proposes"] or "[]"), "related": json.loads(c["related"] or "[]"), **impact_context(c),
        "comment_drafts": comment_context(doc_id), **notes_context(doc_id, c, False)})


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
from .impact import EFFECTS as IMPACT_EFFECTS, GROUPS as IMPACT_GROUPS, REQUESTED as IMPACT_REQUESTED  # noqa: E402
from .impact import clean as clean_impact, load as load_impact, paragraph_ids, table_for  # noqa: E402

CITED = re.compile(r"^(.*?)\s*\[([p0-9.,\s]+)\]\s*$")


def _cited_lines(raw: str) -> list[dict]:
    """'Text [p2.1, p3.4]' per line -> {text, basis}."""
    out = []
    for line in str(raw or "").splitlines():
        line = line.strip(" -•\t")
        if not line:
            continue
        m = CITED.match(line)
        text, basis = (m.group(1), [b.strip() for b in m.group(2).split(",") if b.strip()]) if m else (line, [])
        out.append({"text": text, "basis": basis})
    return out


RATINGS = ("high", "medium", "low")


@app.post("/rating/{doc_id}")
def save_rating(request: Request, doc_id: str, rating: str = Form("")):
    """The team's overall impact rating. Only a named reviewer sets it; the model never does."""
    name = need_reviewer(request)
    if rating and rating not in RATINGS:
        raise HTTPException(400, "rating must be high, medium, low or empty")
    with db.session() as conn:
        table = table_for(conn, doc_id)
        if not table:
            raise HTTPException(404)
        conn.execute(f"UPDATE {table} SET rating = ? WHERE doc_id = ?", (rating or None, doc_id))
        db.audit(conn, name, "rating.set", doc_id, {"rating": rating or None})
        reg = conn.execute("SELECT id FROM regulations WHERE doc_id = ?", (doc_id,)).fetchone() if table == "regulations" else None
    back_to = {"orders": f"/order/{doc_id}", "consultations": f"/consultation/{doc_id}"}.get(table) or f"/regulation/{reg['id']}"
    return back(f"{back_to}#impact")


def impact_context(row, doc_id: str | None = None) -> dict:
    raw = row["impact"] if row is not None and "impact" in row.keys() else None
    return {"impact": load_impact(raw), "impact_requested": raw == IMPACT_REQUESTED,
            "rating": row["rating"] if row is not None and "rating" in row.keys() else None, "RATINGS": RATINGS,
            "figures": json.loads(row["figures"]) if row is not None and "figures" in row.keys() and row["figures"] else [],
            "figures_json": json.dumps(json.loads(row["figures"]), indent=1, ensure_ascii=False) if row is not None and "figures" in row.keys() and row["figures"] else "[]",
            "checks": json.loads(row["checks"]) if row is not None and "checks" in row.keys() and row["checks"] else None,
            "impact_doc": doc_id or (row["doc_id"] if row is not None and "doc_id" in row.keys() else None),
            "GROUPS": IMPACT_GROUPS, "EFFECTS": IMPACT_EFFECTS}


@app.post("/impact/{doc_id}")
async def save_impact(request: Request, doc_id: str):
    name = need_reviewer(request)
    form = await request.form()
    action = str(form.get("action", "save"))
    with db.session() as conn:
        table = table_for(conn, doc_id)
        if not table:
            raise HTTPException(404)
        if action == "clear":
            conn.execute(f"UPDATE {table} SET impact = NULL WHERE doc_id = ?", (doc_id,))
        elif action == "request":
            conn.execute(f"UPDATE {table} SET impact = ? WHERE doc_id = ?", (IMPACT_REQUESTED, doc_id))
        else:
            cells = {}
            for g in IMPACT_GROUPS:
                comment = str(form.get(f"comment_{g}", "")).strip()
                if comment and form.get(f"effect_{g}") in IMPACT_EFFECTS:
                    cells[g] = {"effect": str(form.get(f"effect_{g}")), "comment": comment,
                                "basis": [b.strip() for b in str(form.get(f"basis_{g}", "")).replace(";", ",").split(",") if b.strip()]}
            out = {"headline": str(form.get("headline", "")), "checks": str(form.get("checks", "")).splitlines(),
                   "market_note": str(form.get("market_note", "")).strip(), "key_points": _cited_lines(form.get("key_points")),
                   "procurement": _cited_lines(form.get("procurement")), "stakeholders": cells,
                   "open_questions": [q.strip(" -•\t") for q in str(form.get("open_questions", "")).splitlines() if q.strip(" -•\t")]}
            conn.execute(f"UPDATE {table} SET impact = ? WHERE doc_id = ?",
                         (json.dumps(clean_impact(out, paragraph_ids(conn, doc_id)), ensure_ascii=False), doc_id))
        db.audit(conn, name, f"impact.{action}", doc_id)
        reg = conn.execute("SELECT id FROM regulations WHERE doc_id = ?", (doc_id,)).fetchone() if table == "regulations" else None
    back_to = {"orders": f"/order/{doc_id}", "consultations": f"/consultation/{doc_id}"}.get(table) or f"/regulation/{reg['id']}"
    return back(f"{back_to}#impact")


# --- Studio: draft comments ------------------------------------------------------------------------
from . import comments as comment_stage  # noqa: E402


def comment_context(doc_id: str) -> list[dict]:
    with db.session() as conn:
        rows = conn.execute("SELECT * FROM comment_drafts WHERE doc_id = ? ORDER BY persona", (doc_id,)).fetchall()
    return [{"persona": r["persona"], "label": IMPACT_GROUPS[r["persona"]], "status": r["status"], "reviewer": r["reviewer"],
             "body": json.loads(r["body"]) if r["body"] else None} for r in rows if r["persona"] in IMPACT_GROUPS]


@app.post("/comments/{doc_id}")
async def save_comment(request: Request, doc_id: str):
    name = need_reviewer(request)
    form = await request.form()
    action, persona = str(form.get("action", "save")), str(form.get("persona", ""))
    if persona not in IMPACT_GROUPS:
        raise HTTPException(400, "unknown stakeholder group")
    with db.session() as conn:
        if not conn.execute("SELECT 1 FROM consultations WHERE doc_id = ?", (doc_id,)).fetchone():
            raise HTTPException(404)
        if action == "request":
            comment_stage.request(conn, [doc_id], [persona])
        elif action == "remove":
            conn.execute("DELETE FROM comment_drafts WHERE doc_id = ? AND persona = ?", (doc_id, persona))
        else:
            points = [{"clause": str(form.get(f"clause_{i}", "")), "comment": str(form.get(f"comment_{i}", "")),
                       "suggestion": str(form.get(f"suggestion_{i}", "")),
                       "basis": [b.strip() for b in str(form.get(f"basis_{i}", "")).replace(";", ",").split(",") if b.strip()]} for i in range(6)]
            body = comment_stage.clean({"position": str(form.get("position", "")), "points": points, "closing": str(form.get("closing", ""))},
                                       paragraph_ids(conn, doc_id))
            status = {"approve": "approved", "reject": "rejected"}.get(action, "proposed")
            if status == "approved" and not body["points"]:
                raise HTTPException(400, "a comment draft needs at least one point with a valid paragraph citation")
            conn.execute("""UPDATE comment_drafts SET body = ?, status = ?, reviewer = ?, approved_at = CASE WHEN ? = 'approved' THEN datetime('now') END
                            WHERE doc_id = ? AND persona = ?""",
                         (json.dumps(body, ensure_ascii=False), status, name if status != "proposed" else None, status, doc_id, persona))
            comment_stage.write_file(conn, doc_id, persona, body, f"reviewed by {name}" if status == "approved" else "draft, not reviewed")
        db.audit(conn, name, f"comments.{action}", f"{doc_id}:{persona}")
    return back(f"/consultation/{doc_id}#comments-{persona}")


# --- Charts for a summary --------------------------------------------------------------------------
from . import figures as figures_stage  # noqa: E402


@app.post("/checks/{doc_id}")
async def redo_checks(request: Request, doc_id: str):
    """Clear the pre-review checks so the next `regstudio run check` tests the edited summary."""
    name = need_reviewer(request)
    with db.session() as conn:
        table = table_for(conn, doc_id)
        if table not in ("orders", "consultations"):
            raise HTTPException(404)
        conn.execute(f"UPDATE {table} SET checks = NULL WHERE doc_id = ?", (doc_id,))
        db.audit(conn, name, "check.redo", doc_id)
    return back(f"/{'order' if table == 'orders' else 'consultation'}/{doc_id}#checks")


@app.post("/figures/{doc_id}")
async def save_figures(request: Request, doc_id: str):
    """Reviewer edits the chart list as JSON, or removes charts. The same soundness rules apply as for the model."""
    name = need_reviewer(request)
    form = await request.form()
    with db.session() as conn:
        table = table_for(conn, doc_id)
        if not table:
            raise HTTPException(404)
        if form.get("action") == "redo":
            conn.execute(f"UPDATE {table} SET figures = NULL WHERE doc_id = ?", (doc_id,))
        else:
            try:
                charts = json.loads(str(form.get("figures_json", "[]")) or "[]")
            except json.JSONDecodeError as e:
                raise HTTPException(400, f"the chart list is not valid JSON: {e}")
            drop = {int(k[5:]) for k in form.keys() if k.startswith("drop_")}
            charts = [c for i, c in enumerate(charts if isinstance(charts, list) else []) if i not in drop]
            conn.execute(f"UPDATE {table} SET figures = ? WHERE doc_id = ?",
                         (json.dumps(figures_stage.clean({"charts": charts}, paragraph_ids(conn, doc_id)), ensure_ascii=False), doc_id))
        db.audit(conn, name, f"figures.{form.get('action', 'save')}", doc_id)
        reg = conn.execute("SELECT id FROM regulations WHERE doc_id = ?", (doc_id,)).fetchone() if table == "regulations" else None
    back_to = {"orders": f"/order/{doc_id}", "consultations": f"/consultation/{doc_id}"}.get(table) or f"/regulation/{reg['id']}"
    return back(f"{back_to}#figures")


# ---------- comments for Claude, revisions, memory, commercial illustrations ----------

def notes_context(doc_id: str, row, can_revise: bool) -> dict:
    with db.session() as conn:
        notes = learning.comments_for(conn, doc_id=doc_id)
        revs = [dict(r) | {"fields": json.loads(r["fields"]), "comment_ids": json.loads(r["comment_ids"])}
                for r in conn.execute("SELECT * FROM revisions WHERE doc_id = ? AND status = 'proposed' ORDER BY id", (doc_id,))]
        ids = [n["id"] for n in notes] or [-1]
        lessons = [dict(r) for r in conn.execute(
            f"""SELECT * FROM lessons WHERE status = 'proposed'
                AND (doc_id = ? OR comment_id IN ({",".join("?" * len(ids))})) ORDER BY id""", (doc_id, *ids))]
    keys = row.keys()
    current = {f: row[f] for f in ("headline", "issue", "outcome", "summary") if f in keys}
    raw = row["commercial"] if "commercial" in keys else None
    doc = None
    with db.session() as conn:
        doc = conn.execute("SELECT commission, title, doc_date FROM documents WHERE id = ?", (doc_id,)).fetchone()
    full = dict(row) | (dict(doc) if doc else {})
    return {"priority": priority.for_order(full) if can_revise else priority.for_consultation(full),
            "notes": notes, "revisions": revs, "lessons_here": lessons, "current": current, "notes_doc": doc_id,
            "can_revise": can_revise, "commercial": commercial.load(raw),
            "commercial_status": row["commercial_status"] if "commercial_status" in keys else None,
            "commercial_by": row["commercial_by"] if "commercial_by" in keys else None}


def _doc_page(conn, doc_id: str) -> str:
    if conn.execute("SELECT 1 FROM orders WHERE doc_id = ?", (doc_id,)).fetchone():
        return f"/order/{doc_id}"
    if conn.execute("SELECT 1 FROM consultations WHERE doc_id = ?", (doc_id,)).fetchone():
        return f"/consultation/{doc_id}"
    raise HTTPException(404)


def _revise_in_background(doc_id: str) -> None:
    try:
        learning.revise(doc=doc_id)
    except Exception as e:                      # noqa: BLE001 - shown in the audit log, never crashes the app
        with db.session() as conn:
            db.audit(conn, "pipeline", "revise.error", doc_id, {"error": str(e)[:300]})


@app.post("/notes/{doc_id}")
def add_note(request: Request, background: BackgroundTasks, doc_id: str, body: str = Form(...), target: str = Form("summary"),
             quote: str = Form(""), next: str = Form("stay")):
    who = need_reviewer(request)
    with db.session() as conn:
        page = _doc_page(conn, doc_id)
        learning.add_comment(conn, who, body, target, doc_id=doc_id, quote=quote)
    if next == "revise" and page.startswith("/order/"):
        background.add_task(_revise_in_background, doc_id)
    return back(page + "#notes")


@app.post("/revise/{doc_id}")
def revise_now(request: Request, background: BackgroundTasks, doc_id: str):
    need_reviewer(request)
    with db.session() as conn:
        page = _doc_page(conn, doc_id)
    background.add_task(_revise_in_background, doc_id)
    return back(page + "#notes")


@app.post("/comment/{comment_id}")
def decide_note(request: Request, comment_id: int, action: str = Form(...)):
    who = need_reviewer(request)
    if action not in ("resolved", "dismissed", "open"):
        raise HTTPException(400)
    with db.session() as conn:
        row = conn.execute("SELECT doc_id, digest_id FROM review_comments WHERE id = ?", (comment_id,)).fetchone()
        if not row:
            raise HTTPException(404)
        learning.close_comment(conn, comment_id, who, action)
        page = _doc_page(conn, row["doc_id"]) if row["doc_id"] else f"/digest/{row['digest_id']}"
    return back(page + "#notes")


@app.post("/revision/{revision_id}")
def decide_revision(request: Request, revision_id: int, action: str = Form(...)):
    who = need_reviewer(request)
    if action not in ("accept", "reject"):
        raise HTTPException(400)
    with db.session() as conn:
        try:
            doc_id = learning.decide_revision(conn, revision_id, who, action)
        except ValueError:
            raise HTTPException(409, "This revision has already been decided.")
    return back(f"/order/{doc_id}#notes")


@app.post("/digest/{week}/note")
def digest_note(request: Request, week: str, body: str = Form(...), quote: str = Form("")):
    who = need_reviewer(request)
    with db.session() as conn:
        learning.add_comment(conn, who, body, "edition", digest_id=week, quote=quote)
    return back(f"/digest/{week}#notes")


@app.get("/memory", response_class=HTMLResponse)
def memory(request: Request):
    with db.session() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM lessons ORDER BY kind, scope, id DESC")]
    scopes = ["all", *config.COMMISSIONS, *config.TOPICS]
    return templates.TemplateResponse(request, "memory.html", {
        "reviewer": reviewer(request), "scopes": scopes,
        **{k: [r for r in rows if r["status"] == k] for k in ("proposed", "approved", "retired")}})


@app.post("/memory")
def add_memory(request: Request, kind: str = Form(...), text: str = Form(...), scope: str = Form("all"),
               doc_id: str = Form(""), pid: str = Form("")):
    who = need_reviewer(request)
    with db.session() as conn:
        lid = learning.add_lesson(conn, kind, text, who, scope, doc_id.strip() or None, pid.strip() or None, approved=True)
        if not lid:
            raise HTTPException(400, "Not saved: a fact needs its source document and paragraph, and the note must be new.")
        db.audit(conn, who, "lesson.add", str(lid))
        learning.export(conn)
    return back("/memory")


@app.post("/lesson/{lesson_id}")
def decide_lesson(request: Request, lesson_id: int, action: str = Form(...), text: str = Form(None), scope: str = Form(None)):
    who = need_reviewer(request)
    if action not in ("approve", "retire", "save"):
        raise HTTPException(400)
    with db.session() as conn:
        learning.decide_lesson(conn, lesson_id, who, action, text, scope)
    ref = request.headers.get("referer") or "/memory"
    return back(urllib.parse.urlparse(ref).path or "/memory")


@app.post("/commercial/{doc_id}")
def decide_commercial(request: Request, doc_id: str, action: str = Form(...)):
    who = need_reviewer(request)
    with db.session() as conn:
        page = _doc_page(conn, doc_id)
        table = "orders" if page.startswith("/order/") else "consultations"
        if action == "request":
            conn.execute(f"UPDATE {table} SET commercial_status = 'requested', commercial_by = NULL WHERE doc_id = ?", (doc_id,))
        elif action in ("approve", "reject"):
            row = conn.execute(f"SELECT commercial FROM {table} WHERE doc_id = ?", (doc_id,)).fetchone()
            if not row or not row["commercial"]:
                raise HTTPException(409, "There is no illustration to decide on.")
            conn.execute(f"UPDATE {table} SET commercial_status = ?, commercial_by = ? WHERE doc_id = ?",
                         ("approved" if action == "approve" else "rejected", who, doc_id))
        else:
            raise HTTPException(400)
        db.audit(conn, who, f"commercial.{action}", doc_id)
    return back(page + "#commercial")
