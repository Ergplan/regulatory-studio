"""How the studio learns from its reviewers.

1. Comments. A reviewer comments on a summary, headline, impact note, chart, illustration or edition,
   optionally quoting the words in question.
2. Revise (stage `revise`). For each document with open comments, Claude proposes a revision of the summary
   fields that answers each comment, with a reply per comment and the paragraphs it relied on. The revision
   is a proposal: the reviewer accepts or rejects it; accepting does not approve the summary.
3. Lessons. With each revision Claude may propose lessons: a style note (how the legal team wants things
   written) or a fact about the Indian power sector, cited to a paragraph. Stage `learn` also mines each
   read document for a few durable sector facts. A reviewer approves lessons; only approved lessons are used.
4. Memory. Approved lessons go into every prompt sent to Claude (style notes always, facts for the
   commission and topics in question) and are written to data/memory/house_notes.md for Claude Code on the Mac.
"""

from __future__ import annotations

import datetime as dt
import json
import re

from . import config, db
from .claude_runner import ClaudeError, UsageLimitReached, ask_json
from .common import NotPrepared, fill, load_prompt, load_schema, order_text, prepared_output, use_prepared

PID = re.compile(r"^p\d+\.\d+$")
TARGETS = ("summary", "headline", "impact", "figures", "commercial", "edition", "other")
FIELDS = ("headline", "issue", "outcome", "summary")
LIMITS = {"headline": 120, "issue": 600, "outcome": 600, "summary": 2000}
MAX_FACTS_IN_PROMPT = 25


# ---------- comments ----------

def add_comment(conn, author: str, body: str, target: str, doc_id: str | None = None, digest_id: str | None = None,
                quote: str | None = None) -> int:
    body = (body or "").strip()
    if not body:
        raise ValueError("the comment is empty")
    if target not in TARGETS:
        target = "other"
    cur = conn.execute("INSERT INTO review_comments(doc_id, digest_id, target, quote, body, author) VALUES (?, ?, ?, ?, ?, ?)",
                       (doc_id, digest_id, target, (quote or "").strip()[:600] or None, body[:2000], author))
    db.audit(conn, author, "comment.add", doc_id or digest_id, {"target": target})
    return cur.lastrowid


def comments_for(conn, doc_id: str | None = None, digest_id: str | None = None) -> list[dict]:
    col, val = ("doc_id", doc_id) if doc_id else ("digest_id", digest_id)
    return [dict(r) for r in conn.execute(f"SELECT * FROM review_comments WHERE {col} = ? ORDER BY id", (val,))]


def close_comment(conn, comment_id: int, who: str, status: str) -> None:
    assert status in ("resolved", "dismissed", "open")
    conn.execute("UPDATE review_comments SET status = ?, resolved_by = ?, resolved_at = CASE WHEN ? = 'open' THEN NULL ELSE datetime('now') END "
                 "WHERE id = ?", (status, None if status == "open" else who, status, comment_id))
    db.audit(conn, who, f"comment.{status}", str(comment_id))


# ---------- memory ----------

def notes(conn, commission: str | None = None, topics: list[str] | None = None) -> list[dict]:
    """Approved lessons that apply: every style note, and facts for this commission, these topics or all."""
    scopes = {"all", *(topics or [])}
    if commission:
        scopes.add(commission)
    rows = [dict(r) for r in conn.execute("SELECT * FROM lessons WHERE status = 'approved' ORDER BY id DESC")]
    style = [r for r in rows if r["kind"] == "style" and r["scope"] in scopes | {"all"}]
    facts = [r for r in rows if r["kind"] == "fact" and r["scope"] in scopes][:MAX_FACTS_IN_PROMPT]
    return style + facts


def prompt_block(conn, commission: str | None = None, topics: list[str] | None = None) -> str:
    ns = notes(conn, commission, topics)
    if not ns:
        return ""
    style = [n for n in ns if n["kind"] == "style"]
    facts = [n for n in ns if n["kind"] == "fact"]
    out = ["", "HOUSE NOTES (approved by the Regulatory Studio legal team; follow them)"]
    if style:
        out += ["How to write:"] + [f"- {n['text']}" for n in style]
    if facts:
        out += ["What we know about the sector (background only; cite the document in front of you, never these notes):"]
        out += [f"- {n['text']}" for n in facts]
    return "\n".join(out) + "\n"


def commission_in(prompt: str) -> str | None:
    for code, name in config.COMMISSIONS.items():
        if name and name in prompt:
            return code
    return None


def with_notes(prompt: str) -> str:
    """Add the approved house notes to a prompt. Used for every call to Claude."""
    try:
        with db.session() as conn:
            block = prompt_block(conn, commission_in(prompt))
    except Exception:   # memory is a help; a fault in it must never stop a run
        return prompt
    return prompt + block if block else prompt


def export(conn) -> str:
    """Write the approved notes as Markdown for Claude Code sessions on the Mac (data/memory/house_notes.md)."""
    rows = [dict(r) for r in conn.execute("SELECT * FROM lessons WHERE status = 'approved' ORDER BY kind DESC, scope, id")]
    lines = ["# House notes", "", "Approved by the Regulatory Studio legal team. Generated by `regstudio memory`; do not edit by hand.", ""]
    for kind, head in (("style", "## How to write"), ("fact", "## What we know about the Indian power sector")):
        part = [r for r in rows if r["kind"] == kind]
        if part:
            lines += [head, ""] + [f"- {r['text']}" + (f" ({r['scope'].upper()})" if r["scope"] != "all" else "")
                                   + (f" [source: {r['doc_id'][:12]} {r['pid']}]" if r["doc_id"] else "") for r in part] + [""]
    path = config.MEMORY / "house_notes.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines))
    return str(path)


def add_lesson(conn, kind: str, text: str, by: str, scope: str = "all", doc_id: str | None = None, pid: str | None = None,
               comment_id: int | None = None, approved: bool = False) -> int | None:
    text = (text or "").strip()[:400]
    if kind not in ("style", "fact") or not text:
        return None
    if kind == "fact" and not (doc_id and pid and PID.match(pid)):
        return None                       # a fact without a source is not kept
    if conn.execute("SELECT 1 FROM lessons WHERE lower(text) = lower(?) AND status != 'retired'", (text,)).fetchone():
        return None
    scope = scope if scope in ("all", *config.COMMISSIONS, *config.TOPICS) else "all"
    cur = conn.execute(
        """INSERT INTO lessons(kind, text, scope, doc_id, pid, comment_id, status, added_by, approved_by, approved_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? THEN datetime('now') END)""",
        (kind, text, scope, doc_id, pid, comment_id, "approved" if approved else "proposed", by,
         by if approved else None, approved))
    return cur.lastrowid


def decide_lesson(conn, lesson_id: int, who: str, action: str, text: str | None = None, scope: str | None = None) -> None:
    if text is not None and text.strip():
        conn.execute("UPDATE lessons SET text = ? WHERE id = ?", (text.strip()[:400], lesson_id))
    if scope:
        conn.execute("UPDATE lessons SET scope = ? WHERE id = ?", (scope if scope in ("all", *config.COMMISSIONS, *config.TOPICS) else "all", lesson_id))
    if action == "approve":
        conn.execute("UPDATE lessons SET status = 'approved', approved_by = ?, approved_at = datetime('now') WHERE id = ?", (who, lesson_id))
    elif action == "retire":
        conn.execute("UPDATE lessons SET status = 'retired' WHERE id = ?", (lesson_id,))
    db.audit(conn, who, f"lesson.{action}", str(lesson_id))
    export(conn)


# ---------- revise ----------

def _clean_revision(out: dict, comment_ids: set[int], pids: set[str], current: dict) -> dict:
    fields = {}
    for f in FIELDS:
        v = (out.get(f) or "").strip()
        if v and v != (current.get(f) or "").strip():
            fields[f] = v[:LIMITS[f]]
    replies = []
    for r in out.get("replies") or []:
        if r.get("comment_id") in comment_ids and (r.get("reply") or "").strip():
            replies.append({"comment_id": r["comment_id"], "reply": r["reply"].strip()[:600],
                            "action": r.get("action") if r.get("action") in ("changed", "explained", "cannot") else "explained"})
    lessons = []
    for le in (out.get("lessons") or [])[:4]:
        if le.get("kind") == "fact" and not (isinstance(le.get("pid"), str) and le["pid"] in pids):
            continue
        lessons.append(le)
    basis = [b for b in out.get("basis") or [] if b in pids][:12]
    return {"fields": fields, "replies": replies, "lessons": lessons, "basis": basis}


def revise(limit: int | None = None, doc: str | None = None) -> dict:
    """Propose revisions for documents with open comments on their summary or headline."""
    schema = load_schema("revise_output.schema.json")
    done = failed = 0
    stopped = ""
    with db.session() as conn:
        docs = conn.execute(
            """SELECT DISTINCT c.doc_id FROM review_comments c JOIN orders o ON o.doc_id = c.doc_id
               WHERE c.status = 'open' AND c.target IN ('summary', 'headline', 'other')
                 AND (? IS NULL OR c.doc_id = ?)""", (doc, doc)).fetchall()
        for (doc_id,) in docs[: int(limit)] if limit else docs:
            d = conn.execute("""SELECT d.id, d.commission, d.title, o.headline, o.issue, o.outcome, o.summary, o.topics
                                FROM documents d JOIN orders o ON o.doc_id = d.id WHERE d.id = ?""", (doc_id,)).fetchone()
            open_c = [dict(r) for r in conn.execute(
                "SELECT id, target, quote, body, author FROM review_comments WHERE doc_id = ? AND status = 'open' "
                "AND target IN ('summary', 'headline', 'other') ORDER BY id", (doc_id,))]
            pids = {r[0] for r in conn.execute("SELECT pid FROM paragraphs WHERE doc_id = ?", (doc_id,))}
            name = f"{doc_id}.revise.json"
            try:
                if use_prepared(name):
                    out = prepared_output(name, schema)
                elif config.READER == "mock":
                    out = {"replies": [{"comment_id": c["id"], "reply": "[MOCK] noted.", "action": "explained"} for c in open_c]}
                else:
                    text, _ = order_text(conn, doc_id, budget=80_000)
                    comments = "\n".join(f"[comment {c['id']}] on {c['target']}" + (f', about "{c["quote"]}"' if c["quote"] else "")
                                         + f": {c['body']}" for c in open_c)
                    out = ask_json(fill(load_prompt("revise.md"), schema=json.dumps(schema),
                                        commission=config.COMMISSIONS[d["commission"]], title=d["title"] or "(none)",
                                        headline=d["headline"] or "(none)", issue=d["issue"] or "", outcome=d["outcome"] or "",
                                        summary=d["summary"] or "", comments=comments, text=text), schema)
            except NotPrepared:
                continue
            except UsageLimitReached as e:
                stopped = f"usage limit: {e}"[:300]
                break
            except ClaudeError as e:
                failed += 1
                db.audit(conn, "pipeline", "revise.error", doc_id, {"error": str(e)[:300]})
                continue
            c = _clean_revision(out, {x["id"] for x in open_c}, pids, dict(d))
            if c["fields"]:
                conn.execute("INSERT INTO revisions(doc_id, fields, comment_ids) VALUES (?, ?, ?)",
                             (doc_id, json.dumps(c["fields"], ensure_ascii=False), json.dumps([x["id"] for x in open_c])))
            replied = {r["comment_id"]: r for r in c["replies"]}
            for x in open_c:
                r = replied.get(x["id"])
                reply = r["reply"] if r else "No reply was proposed for this comment."
                conn.execute("UPDATE review_comments SET status = 'answered', reply = ? WHERE id = ?", (reply, x["id"]))
            first = open_c[0]["id"] if open_c else None
            for le in c["lessons"]:
                add_lesson(conn, le.get("kind"), le.get("text"), "model", le.get("scope") or "all",
                           doc_id if le.get("kind") == "fact" else None, le.get("pid"), first)
            db.audit(conn, "pipeline", "revise", doc_id, {"changed": list(c["fields"]), "lessons": len(c["lessons"])})
            done += 1
    return {"revised": done, "failed": failed, **({"stopped": stopped} if stopped else {})}


def decide_revision(conn, revision_id: int, who: str, action: str) -> str:
    rev = conn.execute("SELECT * FROM revisions WHERE id = ?", (revision_id,)).fetchone()
    if not rev or rev["status"] != "proposed":
        raise ValueError("no such open revision")
    if action == "accept":
        fields = json.loads(rev["fields"])
        sets = ", ".join(f"{k} = ?" for k in fields)
        # The summary changes, so it goes back to 'proposed' until a reviewer approves it again.
        conn.execute(f"UPDATE orders SET {sets}, summary_status = 'proposed' WHERE doc_id = ?", (*fields.values(), rev["doc_id"]))
        conn.execute("UPDATE orders SET checks = NULL WHERE doc_id = ?", (rev["doc_id"],))   # check the new text again
        for cid in json.loads(rev["comment_ids"]):
            conn.execute("UPDATE review_comments SET status = 'resolved', resolved_by = ?, resolved_at = datetime('now') "
                         "WHERE id = ? AND status = 'answered'", (who, cid))
    elif action == "reject":
        for cid in json.loads(rev["comment_ids"]):
            conn.execute("UPDATE review_comments SET status = 'open' WHERE id = ? AND status = 'answered'", (cid,))
    else:
        raise ValueError(action)
    conn.execute("UPDATE revisions SET status = ?, decided_by = ?, decided_at = datetime('now') WHERE id = ?",
                 ("accepted" if action == "accept" else "rejected", who, revision_id))
    db.audit(conn, who, f"revision.{action}", rev["doc_id"], {"revision": revision_id})
    return rev["doc_id"]


# ---------- learn ----------

def learn(limit: int | None = None) -> dict:
    """Propose a few durable sector facts from each read document, each cited to a paragraph."""
    schema = load_schema("learn_output.schema.json")
    done = failed = proposed = 0
    stopped = ""
    with db.session() as conn:
        rows = conn.execute(
            """SELECT d.id, d.commission, d.title FROM documents d
               WHERE d.learnt_at IS NULL AND d.stage IN ('read', 'drafted')
                 AND (EXISTS (SELECT 1 FROM orders o WHERE o.doc_id = d.id AND o.summary IS NOT NULL)
                      OR EXISTS (SELECT 1 FROM consultations c WHERE c.doc_id = d.id AND c.summary IS NOT NULL))
               ORDER BY d.created_at DESC""").fetchall()
        for d in rows[: int(limit)] if limit else rows:
            name = f"{d['id']}.learn.json"
            try:
                if use_prepared(name):
                    out = prepared_output(name, schema)
                elif config.READER == "mock":
                    continue
                else:
                    text, _ = order_text(conn, d["id"], budget=60_000)
                    known = "\n".join(f"- {n['text']}" for n in notes(conn, d["commission"])) or "(nothing yet)"
                    out = ask_json(fill(load_prompt("learn.md"), schema=json.dumps(schema), commission=config.COMMISSIONS[d["commission"]],
                                        title=d["title"] or "(none)", known=known, text=text), schema)
            except NotPrepared:
                continue
            except UsageLimitReached as e:
                stopped = f"usage limit: {e}"[:300]
                break
            except ClaudeError as e:
                failed += 1
                db.audit(conn, "pipeline", "learn.error", d["id"], {"error": str(e)[:300]})
                continue
            pids = {r[0] for r in conn.execute("SELECT pid FROM paragraphs WHERE doc_id = ?", (d["id"],))}
            for f in (out.get("facts") or [])[:4]:
                if f.get("pid") in pids and add_lesson(conn, "fact", f.get("text"), "model", f.get("scope") or d["commission"], d["id"], f["pid"]):
                    proposed += 1
            conn.execute("UPDATE documents SET learnt_at = ? WHERE id = ?", (dt.datetime.now().isoformat(timespec="seconds"), d["id"]))
            done += 1
    return {"documents": done, "facts_proposed": proposed, "failed": failed, **({"stopped": stopped} if stopped else {})}
