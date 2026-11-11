"""Write approved data to data/snapshot/ for the site. Nothing proposed or rejected leaves.

A link is published only if the link is approved AND its target is publishable
(an approved clause or regulation, an Act section, or another published order).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil

from . import config, db

SAMPLE_MARK = "example.invalid"


def slug(text: str, n: int = 70) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:n].rstrip("-") or "untitled"


def clause_slug(number: str) -> str:
    return number.replace("(", "-").replace(")", "").lower()


def order_path(d) -> str:
    year = (d["doc_date"] or d["downloaded_at"])[:4]
    label = re.sub(r"^\s*(petition|appeal|case|o\.?p\.?)s?\s+nos?\.?\s*", "", d["case_number"] or "", flags=re.I)
    name = slug(label or d["title"] or d["id"][:12], 60)
    return f"/orders/{d['commission']}/{year}/{name}-{d['id'][:6]}"


def run(clean: bool = False) -> dict:
    out = config.SNAPSHOT
    out.mkdir(parents=True, exist_ok=True)
    (out / "pdf").mkdir(exist_ok=True)
    with db.session() as conn:
        docs = conn.execute(
            """SELECT d.*, o.topics, o.significance, o.parties, o.issue, o.outcome, o.summary,
                      o.reviewer, o.approved_at, o.revised_at
               FROM documents d JOIN orders o ON o.doc_id = d.id
               WHERE o.summary_status = 'approved'""").fetchall()
        docs = [d for d in docs if not (clean and SAMPLE_MARK in d["source_url"])]
        published_docs = {d["id"]: d for d in docs}

        regs = [dict(r) for r in conn.execute("SELECT * FROM regulations WHERE status = 'approved'")]
        if clean:
            sample_reg_docs = {r[0] for r in conn.execute(
                "SELECT id FROM documents WHERE source_url LIKE ?", (f"%{SAMPLE_MARK}%",))}
            regs = [r for r in regs if r["doc_id"] not in sample_reg_docs]
        reg_ids = {r["id"] for r in regs}
        clauses = [dict(c) for c in conn.execute(
            "SELECT * FROM clauses WHERE status = 'approved' ORDER BY regulation_id, CAST(number AS INTEGER), number")
            if c["regulation_id"] in reg_ids]
        clause_ids = {c["id"] for c in clauses}
        acts = [dict(a) for a in conn.execute("SELECT * FROM act_sections")]
        act_ids = {a["id"] for a in acts}

        def publishable(kind: str, tid: str | None) -> bool:
            return bool(tid) and ((kind == "clause" and tid in clause_ids) or
                                  (kind == "regulation" and tid in reg_ids) or
                                  (kind == "act_section" and tid in act_ids) or
                                  (kind == "document" and tid in published_docs))

        orders, held_back = [], 0
        for d in docs:
            links = []
            for l in conn.execute("SELECT * FROM links WHERE from_doc = ? AND status = 'approved' ORDER BY pid",
                                  (d["id"],)):
                if publishable(l["target_kind"], l["target_id"]):
                    links.append({"type": l["link_type"], "kind": l["target_kind"], "target": l["target_id"],
                                  "cited_as": l["citation_text"], "pid": l["pid"], "excerpt": l["excerpt"]})
                else:
                    held_back += 1
            page = {r["pid"]: r["page"] for r in conn.execute(
                "SELECT pid, page FROM paragraphs WHERE doc_id = ?", (d["id"],))}
            for l in links:
                l["page"] = page.get(l["pid"])
            pdf_name = f"{d['id'][:16]}.pdf"
            src = config.STORE / d["file_path"]
            if src.exists() and not (out / "pdf" / pdf_name).exists():
                shutil.copyfile(src, out / "pdf" / pdf_name)
            orders.append({
                "id": d["id"], "path": order_path(d), "commission": d["commission"], "doc_type": d["doc_type"],
                "title": d["title"], "case_number": d["case_number"], "date": d["doc_date"],
                "source_url": d["source_url"], "pdf": f"/pdf/{pdf_name}",
                "topics": json.loads(d["topics"] or "[]"), "significance": d["significance"],
                "parties": json.loads(d["parties"] or "[]"), "issue": d["issue"], "outcome": d["outcome"],
                "summary": d["summary"], "reviewed_by": d["reviewer"], "approved_at": d["approved_at"],
                "revised_at": d["revised_at"], "language": d["language"],
                "sample": SAMPLE_MARK in d["source_url"], "links": links,
            })

        for r in regs:
            r["path"] = f"/regulations/{r['id']}"
            r["made_under"] = json.loads(r["made_under"] or "[]")
            r["sample"] = False
            if r["doc_id"]:
                src_doc = conn.execute("SELECT source_url FROM documents WHERE id = ?", (r["doc_id"],)).fetchone()
                r["source_url"] = src_doc["source_url"] if src_doc else None
                r["sample"] = bool(src_doc and SAMPLE_MARK in src_doc["source_url"])
        for c in clauses:
            c["path"] = f"/regulations/{c['regulation_id']}/{clause_slug(c['number'])}"
            c["versions"] = [dict(v) for v in conn.execute(
                """SELECT text, in_force_from, in_force_to FROM clause_versions WHERE clause_id = ?
                   ORDER BY coalesce(in_force_from, '') DESC""", (c["id"],))]

        digests = []
        for g in conn.execute("SELECT * FROM digests WHERE status = 'approved' ORDER BY id DESC"):
            items = [i for i in json.loads(g["items"] or "[]") if i in published_docs]
            if items:
                digests.append({"id": g["id"], "from": g["from_date"], "to": g["to_date"], "intro": g["intro"],
                                "items": items, "approved_at": g["approved_at"], "reviewed_by": g["reviewer"],
                                "path": f"/digest/{g['id'].lower()}"})
            if g["published_at"] is None:
                conn.execute("UPDATE digests SET published_at = datetime('now') WHERE id = ?", (g["id"],))

    files = {
        "site.json": {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                      "commissions": config.COMMISSIONS, "topics": config.TOPICS,
                      "link_types": config.LINK_TYPES,
                      "contains_sample_data": any(o["sample"] for o in orders) or any(r["sample"] for r in regs)},
        "orders.json": orders,
        "regulations.json": regs,
        "clauses.json": clauses,
        "act_sections.json": acts,
        "digests.json": digests,
    }
    for name, data in files.items():
        (out / name).write_text(json.dumps(data, indent=1, ensure_ascii=False))
    return {"orders": len(orders), "regulations": len(regs), "clauses": len(clauses),
            "digests": len(digests), "links_held_back": held_back, "snapshot": str(out)}
