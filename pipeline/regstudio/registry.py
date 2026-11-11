"""Stage 3: split regulations into clause-level registry entries.

This is a rule-based first pass for Indian regulation layouts:
  '8. Banking.-(1) ...'  starts regulation 8 with heading 'Banking'
  '(2) ...'              starts sub-regulation 8(2)
Everything it writes is 'proposed'; the review app approves registry entries.
Amendments are registered as their own regulation entries; linking an amendment to the
clauses it changes (and setting in_force_to) is done at review.
"""

from __future__ import annotations

import re

from . import config, db

TOP = re.compile(r"^(\d{1,3}[A-Z]?)\.\s+(?:([A-Z][^.:]{2,100}?)\s*[.:]\s*[-—–]+\s*)?(.*)$", re.S)
SUB = re.compile(r"^\((\d{1,2}[a-z]?)\)\s+(.*)$", re.S)
YEAR = re.compile(r"(19|20)\d{2}")


def slugify(text: str, max_len: int = 60) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].rstrip("-") or "untitled"


STOP = {"the", "of", "and", "for", "to", "in", "regulation", "regulations", "electricity", "regulatory",
        "commission", "central", "state", "cerc", "aptel", "uperc", "merc", "gerc", "kerc", "rerc",
        "uttar", "pradesh", "maharashtra", "gujarat", "karnataka", "rajasthan", "sample"}


def regulation_id(commission: str, title: str, doc_date: str | None) -> str:
    """Readable, permanent id such as 'cerc/deviation-settlement-mechanism-related-matters-2024'."""
    m = YEAR.search(title)
    year = m.group(0) if m else (doc_date[:4] if doc_date else "")
    words = [w for w in re.findall(r"[a-z0-9]+", title.lower()) if w not in STOP and not YEAR.fullmatch(w)]
    slug, n = [], 0
    for w in words:
        if n + len(w) > 55:
            break
        slug.append(w); n += len(w) + 1
    base = "-".join(slug) or "untitled"
    return f"{commission}/{base}-{year}" if year else f"{commission}/{base}"


def split_clauses(paragraphs: list[dict]) -> list[dict]:
    clauses: list[dict] = []
    current_top: str | None = None
    current_heading: str | None = None
    for p in paragraphs:
        text = p["text"]
        m = TOP.match(text)
        if m and len(m.group(1)) <= 4:
            current_top, current_heading, rest = m.group(1), (m.group(2) or "").strip() or None, m.group(3)
            sub = SUB.match(rest or "")
            if sub:
                clauses.append({"number": current_top, "heading": current_heading, "text": "",
                                "pid": p["pid"]})
                clauses.append({"number": f"{current_top}({sub.group(1)})", "heading": current_heading,
                                "text": sub.group(2).strip(), "pid": p["pid"]})
            else:
                clauses.append({"number": current_top, "heading": current_heading,
                                "text": (rest or "").strip(), "pid": p["pid"]})
            continue
        s = SUB.match(text)
        if s and current_top:
            clauses.append({"number": f"{current_top}({s.group(1)})", "heading": current_heading,
                            "text": s.group(2).strip(), "pid": p["pid"]})
            continue
        if clauses:  # continuation of the previous clause
            clauses[-1]["text"] = (clauses[-1]["text"] + " " + text).strip()
    for c in clauses:
        if not c["heading"] and "(" not in c["number"] and 0 < len(c["text"]) <= 70 and not c["text"].endswith("."):
            c["heading"], c["text"] = c["text"], ""
        elif not c["heading"] and "(" not in c["number"]:
            m = re.match(r"^([A-Z][A-Za-z ,'&-]{3,60}?)\s+(These|This|The|In|If|Every|For|Save|Deviation|Charges|Notwithstanding)\b", c["text"])
            if m:
                c["heading"], c["text"] = m.group(1).strip(), c["text"][len(m.group(1)):].strip()
    heads = {c["number"]: c["heading"] for c in clauses if "(" not in c["number"]}
    for c in clauses:
        if "(" in c["number"] and not c["heading"]:
            c["heading"] = heads.get(c["number"].split("(")[0])
    # Merge duplicates (same number seen twice, e.g. a table of contents) keeping the longer text.
    merged: dict[str, dict] = {}
    for c in clauses:
        if c["number"] not in merged or len(c["text"]) > len(merged[c["number"]]["text"]):
            merged[c["number"]] = c
    return list(merged.values())


def run(limit: int | None = None) -> dict:
    registered = failed = 0
    with db.session() as conn:
        run_id = db.start_run(conn, "registry")
        docs = conn.execute(
            "SELECT * FROM documents WHERE stage = 'extracted' AND doc_type IN ('regulation', 'amendment')"
            + (f" LIMIT {int(limit)}" if limit else "")
        ).fetchall()
        for d in docs:
            paras = [dict(r) for r in conn.execute(
                "SELECT pid, text FROM paragraphs WHERE doc_id = ? ORDER BY page, idx", (d["id"],))]
            title = d["title"] or (paras[0]["text"][:200] if paras else "Untitled regulation")
            reg_id = regulation_id(d["commission"], title, d["doc_date"])
            if d["doc_type"] == "amendment":
                reg_id += "-amendment-" + d["id"][:8]
            clauses = split_clauses(paras)
            if not clauses:
                db.set_stage(conn, d["id"], "error", "registry: no numbered clauses found")
                failed += 1
                continue
            conn.execute(
                """INSERT OR REPLACE INTO regulations(id, commission, title, notified_date, doc_id, status)
                   VALUES (?, ?, ?, ?, ?, 'proposed')""",
                (reg_id, d["commission"], title, d["doc_date"], d["id"]),
            )
            conn.execute("DELETE FROM clauses WHERE regulation_id = ? AND status = 'proposed'", (reg_id,))
            for c in clauses:
                conn.execute(
                    """INSERT OR IGNORE INTO clauses(id, regulation_id, number, heading, text,
                           in_force_from, source_pid, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'proposed')""",
                    (f"{reg_id}/{c['number']}", reg_id, c["number"], c["heading"], c["text"],
                     d["doc_date"], c["pid"]),
                )
            db.set_stage(conn, d["id"], "registered")
            db.audit(conn, "pipeline", "registry", reg_id, {"clauses": len(clauses)})
            registered += 1
        db.finish_run(conn, run_id, registered, failed)
    return {"registered": registered, "failed": failed}


def lookup_index(conn) -> list[dict]:
    """Compact registry listing handed to the reader so it can resolve citations."""
    rows = conn.execute(
        """SELECT r.id AS reg_id, r.commission, r.title, c.id AS clause_id, c.number, c.heading
           FROM regulations r JOIN clauses c ON c.regulation_id = r.id
           WHERE r.status != 'rejected' AND c.status != 'rejected'
           ORDER BY r.id, c.number"""
    ).fetchall()
    return [dict(r) for r in rows]


_ = config  # config imported for callers that patch paths in tests
