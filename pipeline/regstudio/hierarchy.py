"""Reviewer precedence and the record of every review decision.

Two ranks. A senior reviewer (config.SENIOR_REVIEWERS, e.g. Shikha Ohri) and everyone else (e.g. Kartik).
- A reviewer reviews, edits and approves on their own; nobody's approval is needed on top of theirs.
- A senior reviewer may change any decision, including another reviewer's. That is recorded as an override.
- Once a senior reviewer has made a decision on something (approve, reject, reopen, ...), it is held: other
  reviewers can still read it and comment on it, but cannot change it. Only a senior reviewer can.
  An attempt to change it is refused and the refusal is recorded too.

Seniority comes only from the email the reviewer signed in with (the review site's account, Cloudflare Access,
or the local sign-in's registered email). A typed or unverified name is never senior.

Every decision is a row in review_decisions: who, their rank, what they did, the status and reviewer before and
after, the text before and after, and which earlier decision it overrode. Nothing is ever deleted from it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from fastapi import HTTPException, Request

from . import auth, config, db

SENIOR = 2
REVIEWER = 1

# Actions that settle something. A senior reviewer's settling action holds the item; editing (save) does not.
DECISIVE = {"approve", "reject", "reopen", "apply", "retire", "remove", "clear"}
SETTLED_BY_SAVE = {"impact", "figures", "rating"}   # parts with no approve button: saving them is the decision

PAST = {"approve": "approved", "reject": "rejected", "reopen": "reopened", "apply": "applied", "retire": "retired",
        "remove": "removed", "clear": "removed", "save": "edited", "set": "set", "accept": "accepted a revision of",
        "add": "added", "request": "requested", "redo": "asked again for",
        "revision_accept": "accepted a revision of", "revision_reject": "rejected a revision of"}


@dataclass(frozen=True)
class Actor:
    name: str
    email: str | None
    rank: int

    @property
    def senior(self) -> bool:
        return self.rank >= SENIOR


def rank_of(email: str | None) -> int:
    return SENIOR if email and email.strip().lower() in config.SENIOR_REVIEWERS else REVIEWER


def actor(request: Request, name: str) -> Actor:
    """The reviewer behind this request, with the email that was verified for them, if any."""
    email = getattr(request.state, "reviewer_email", None)
    if not email and auth.enabled():
        email = (auth._load().get(name) or {}).get("email")   # local sign-in: the email registered for this name
    email = (email or "").strip().lower() or None
    return Actor(name=name, email=email, rank=rank_of(email))


def decisive(kind: str, action: str) -> bool:
    return action in DECISIVE or (kind in SETTLED_BY_SAVE and action in ("save", "set"))


# ---- what an item looks like now --------------------------------------------------------------------------

_STATE = {
    "order": ("SELECT summary_status AS status, reviewer, summary, issue, outcome, headline, topics FROM orders WHERE doc_id = ?", None),
    "consultation": ("SELECT summary_status AS status, reviewer, kind, summary, proposes, comment_deadline, hearing_date, amends "
                     "FROM consultations WHERE doc_id = ?", None),
    "digest": ("SELECT status, reviewer, intro FROM digests WHERE id = ?", None),
    "link": ("SELECT status, reviewer, link_type, target_kind, target_id FROM links WHERE id = ?", None),
    "clause": ("SELECT status, reviewer, heading, text, in_force_from, in_force_to FROM clauses WHERE id = ?", None),
    "regulation": ("SELECT status, reviewer, title, short_title, notified_date FROM regulations WHERE id = ?", None),
    "amendment_change": ("SELECT status, reviewer, new_text, clause_number FROM amendment_changes WHERE id = ?", None),
    "comment_draft": ("SELECT status, reviewer, body FROM comment_drafts WHERE doc_id = ? AND persona = ?", "split"),
    "lesson": ("SELECT status, approved_by AS reviewer, text, scope FROM lessons WHERE id = ?", None),
}


def state(conn, kind: str, obj: str) -> dict:
    if kind in SETTLED_BY_SAVE:
        col = {"impact": "impact", "figures": "figures", "rating": "rating"}[kind]
        from .impact import table_for
        table = table_for(conn, obj)
        row = conn.execute(f"SELECT {col} AS value FROM {table} WHERE doc_id = ?", (obj,)).fetchone() if table else None
        return {"status": None, "reviewer": None, "text": {"value": row["value"]} if row else {}}
    sql, mode = _STATE[kind]
    args = tuple(obj.split(":", 1)) if mode == "split" else (obj,)
    row = conn.execute(sql, args).fetchone()
    if not row:
        return {"status": None, "reviewer": None, "text": {}}
    d = dict(row)
    return {"status": d.pop("status"), "reviewer": d.pop("reviewer"), "text": d}


# ---- holds, refusals and the record -----------------------------------------------------------------------

def held_by(conn, kind: str, obj: str):
    """The senior reviewer's latest settling decision on this item, if there is one."""
    rows = conn.execute("""SELECT * FROM review_decisions WHERE kind = ? AND object = ? AND rank >= ? AND refused = 0
                           ORDER BY id DESC""", (kind, obj, SENIOR)).fetchall()
    return next((r for r in rows if decisive(kind, r["action"])), None)


def _when(at: str) -> str:
    import datetime as dt
    try:
        return dt.datetime.fromisoformat(at).strftime("%d %b %Y, %H:%M UTC")
    except (TypeError, ValueError):
        return str(at)


def guard(who: Actor, kind: str, obj: str, action: str) -> None:
    """Refuses (409) a change to an item a senior reviewer has decided, unless the reviewer is senior too.
    The refusal is recorded in its own transaction, so it stays on record although the change is not made."""
    if who.senior:
        return
    with db.session() as conn:
        held = held_by(conn, kind, obj)
        if not held:
            return
        now = state(conn, kind, obj)
        conn.execute("""INSERT INTO review_decisions(kind, object, action, reviewer, email, rank, status_before, status_after,
                            reviewer_before, refused, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                     (kind, obj, action, who.name, who.email, who.rank, now["status"], now["status"], now["reviewer"],
                      f"held by {held['reviewer']} ({held['action']}, decision {held['id']})"))
    raise HTTPException(409, f"{held['reviewer']} (senior reviewer) {PAST.get(held['action'], held['action'])} this on "
                             f"{_when(held['at'])}. Only a senior reviewer can change it. You can still add a comment.")


def record(conn, who: Actor, kind: str, obj: str, action: str, before: dict, after: dict | None = None,
           note: str | None = None) -> int:
    """Writes one decision. `before` is state() taken before the change; `after` is taken now if not given."""
    after = after if after is not None else state(conn, kind, obj)
    prev = conn.execute("""SELECT id, reviewer, rank, action FROM review_decisions WHERE kind = ? AND object = ? AND refused = 0
                           ORDER BY id DESC LIMIT 1""", (kind, obj)).fetchone()
    changed = before.get("status") != after.get("status") or before.get("text") != after.get("text")
    overrides = prev["id"] if (prev and who.senior and prev["rank"] < who.rank and prev["reviewer"] != who.name
                               and decisive(kind, prev["action"]) and changed) else None
    return conn.execute(
        """INSERT INTO review_decisions(kind, object, action, reviewer, email, rank, status_before, status_after,
               reviewer_before, text_before, text_after, overrides, note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (kind, obj, action, who.name, who.email, who.rank, before.get("status"), after.get("status"), before.get("reviewer"),
         json.dumps(before.get("text") or {}, ensure_ascii=False), json.dumps(after.get("text") or {}, ensure_ascii=False),
         overrides, note)).lastrowid


def history(conn, doc_id: str | None = None, kind: str | None = None, obj: str | None = None, limit: int = 40) -> list[dict]:
    """Decisions about one document (its summary, links, impact, figures, rating, comment drafts), or one item."""
    if doc_id:
        rows = conn.execute(
            """SELECT * FROM review_decisions WHERE (object = ? AND kind IN ('order','consultation','impact','figures','rating'))
                   OR (kind = 'link' AND object IN (SELECT CAST(id AS TEXT) FROM links WHERE from_doc = ?))
                   OR (kind = 'comment_draft' AND object LIKE ? || ':%')
               ORDER BY id DESC LIMIT ?""", (doc_id, doc_id, doc_id, limit)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM review_decisions WHERE kind = ? AND object = ? ORDER BY id DESC LIMIT ?",
                            (kind, obj, limit)).fetchall()
    byid = {}
    out = []
    for r in rows:
        d = dict(r)
        d["senior"] = d["rank"] >= SENIOR
        d["what"] = _describe(d)
        out.append(d)
        byid[d["id"]] = d
    for d in out:
        if d["overrides"]:
            o = byid.get(d["overrides"]) or dict(conn.execute("SELECT reviewer, action FROM review_decisions WHERE id = ?",
                                                              (d["overrides"],)).fetchone() or {})
            d["overrode"] = f"{o.get('reviewer', 'another reviewer')}'s {PAST.get(o.get('action', ''), o.get('action', 'decision'))} decision"
    return out


_PART = {"order": "summary", "consultation": "summary", "digest": "edition", "link": "link", "clause": "clause",
         "regulation": "regulation", "amendment_change": "amendment", "comment_draft": "comment draft", "lesson": "memory note",
         "impact": "market impact", "figures": "charts", "rating": "rating"}


def _describe(d: dict) -> str:
    part = _PART.get(d["kind"], d["kind"])
    if d["kind"] == "link":
        part = f"link {d['object']}"
    if d["refused"]:
        return f"tried to change the {part}; refused, {d['note'] or 'held by a senior reviewer'}"
    verb = PAST.get(d["action"], d["action"])
    if d["action"] in ("revision_accept", "revision_reject"):
        return f"{verb} the {part}" + (f" ({d['status_before']} → {d['status_after']})" if d["status_before"] != d["status_after"] else "")
    s = f"{verb} the {part}"
    if d["status_before"] != d["status_after"] and d["status_after"]:
        s += f" ({d['status_before'] or 'new'} → {d['status_after']})"
    elif d["text_before"] != d["text_after"] and d["action"] not in ("save",):
        s += " and changed its text"
    return s


def holds_for(conn, items: list[tuple[str, str]]) -> dict[str, dict]:
    """{object: hold row} for queue pages."""
    out = {}
    for kind, obj in items:
        h = held_by(conn, kind, obj)
        if h:
            out[obj] = dict(h)
    return out
