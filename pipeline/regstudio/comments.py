"""Stage `comments`: Studio draft comments on a draft regulation, for one stakeholder group at a time.

Opt-in like the impact stage: a reviewer requests a draft for (document, persona) on the review screen
or with `regstudio run comments --doc <id> --as <persona>`. The model's draft is a proposal. Every
point cites paragraph ids of the draft regulation; points whose citations are not in the text are
dropped. Each draft is also written as a Markdown file under data/comments/ so the team can work on
it outside the site. It reaches the website only after a named reviewer approves it.
"""

from __future__ import annotations

import json

from . import config, db
from .claude_runner import ClaudeError, UsageLimitReached, ask_json
from .common import NotPrepared, fill, load_prompt, load_schema, order_text, prepared_output
from .impact import GROUPS, PID, paragraph_ids

PERSONA_VOICE = {
    "discoms": "a distribution licensee", "ci_consumers": "a commercial or industrial consumer buying through open access",
    "captive": "a consumer with a captive generating plant", "re_developers": "a renewable energy developer",
    "storage": "an energy storage developer (BESS or pumped hydro)", "conventional": "a thermal or hydro generating company",
    "transmission": "a transmission licensee or system operator", "traders": "an electricity trader or power exchange",
}


def request(conn, doc_prefixes: list[str], personas: list[str]) -> list[tuple[str, str]]:
    queued = []
    for p in doc_prefixes:
        for r in conn.execute("SELECT doc_id FROM consultations WHERE doc_id LIKE ?", (p + "%",)).fetchall():
            for persona in personas:
                if persona in GROUPS:
                    conn.execute("""INSERT INTO comment_drafts(doc_id, persona, status) VALUES (?, ?, 'requested')
                                    ON CONFLICT(doc_id, persona) DO UPDATE SET status = 'requested', reviewer = NULL, approved_at = NULL""",
                                 (r[0], persona))
                    queued.append((r[0], persona))
    conn.commit()
    return queued


def clean(out: dict, pids: set[str] | None = None) -> dict:
    points = []
    for it in out.get("points") or []:
        basis = [b for b in it.get("basis") or [] if isinstance(b, str) and PID.match(b) and (pids is None or b in pids)][:4]
        clause, comment = (it.get("clause") or "").strip()[:120], (it.get("comment") or "").strip()[:600]
        if clause and comment and (basis or pids is None):
            points.append({"clause": clause, "comment": comment, "suggestion": (it.get("suggestion") or "").strip()[:500], "basis": basis})
    return {"position": (out.get("position") or "").strip()[:700], "points": points[:6], "closing": (out.get("closing") or "").strip()[:300]}


def as_markdown(title: str, commission: str, persona: str, body: dict, status: str) -> str:
    lines = [f"# Comments on: {title}", "", f"To: The Secretary, {commission}", f"From: [Organisation name], {PERSONA_VOICE[persona]}",
             f"Status: {status} (prepared in Regulatory Studio; edit before filing)", "", "## Our position", "", body["position"], "",
             "## Comments by provision", ""]
    for i, p in enumerate(body["points"], 1):
        cite = ", ".join(f"p.{b[1:].split('.')[0]} ¶{b.split('.')[1]}" for b in p["basis"])
        lines += [f"### {i}. {p['clause']}", "", p["comment"], "", f"**Requested change:** {p['suggestion']}" if p["suggestion"] else "",
                  "", f"_Draft reference: {cite}_" if cite else "", ""]
    lines += [body["closing"], "", "[Name, designation, contact]", ""]
    return "\n".join(l for i, l in enumerate(lines) if l != "" or (i and lines[i - 1] != ""))


def write_file(conn, doc_id: str, persona: str, body: dict, status: str):
    d = conn.execute("SELECT title, commission FROM documents WHERE id = ?", (doc_id,)).fetchone()
    folder = config.COMMENTS / d["commission"] / doc_id[:12]
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{persona}.md"
    path.write_text(as_markdown(d["title"] or doc_id[:12], config.COMMISSIONS[d["commission"]], persona, body, status), encoding="utf-8")
    return path


def _targets(conn, limit):
    rows = [dict(r) for r in conn.execute(
        """SELECT k.doc_id, k.persona, d.commission, d.title, c.summary FROM comment_drafts k
           JOIN documents d ON d.id = k.doc_id JOIN consultations c ON c.doc_id = k.doc_id WHERE k.status = 'requested'""")]
    if config.READER == "file":  # a prepared file counts as a request
        have = {(r["doc_id"], r["persona"]) for r in conn.execute("SELECT doc_id, persona FROM comment_drafts")}
        for c in conn.execute("SELECT c.doc_id, d.commission, d.title, c.summary FROM consultations c JOIN documents d ON d.id = c.doc_id").fetchall():
            for persona in GROUPS:
                if (c["doc_id"], persona) not in have and (config.READER_OUTPUTS / f"{c['doc_id']}.comment.{persona}.json").exists():
                    rows.append({**dict(c), "persona": persona})
    return rows[: int(limit)] if limit else rows


def run(limit: int | None = None, docs: list[str] | None = None, personas: list[str] | None = None) -> dict:
    schema = load_schema("comment_output.schema.json")
    template = load_prompt("comment.md")
    done = failed = 0
    stopped = ""
    with db.session() as conn:
        if docs and personas:
            request(conn, docs, personas)
        run_id = db.start_run(conn, "comments")
        for t in _targets(conn, limit):
            key = f"{t['doc_id']}:{t['persona']}"
            try:
                if config.READER == "file":
                    out = prepared_output(f"{t['doc_id']}.comment.{t['persona']}.json", schema)
                elif config.READER == "mock":
                    continue
                else:
                    text, _ = order_text(conn, t["doc_id"], budget=60_000)
                    out = ask_json(fill(template, schema=json.dumps(schema), persona=PERSONA_VOICE[t["persona"]],
                                        title=t["title"] or "(none)", commission=config.COMMISSIONS[t["commission"]],
                                        summary=t["summary"] or "(none)", text=text), schema)
            except NotPrepared:
                continue
            except UsageLimitReached as e:
                stopped = f"usage limit: {e}"[:300]
                break
            except ClaudeError as e:
                failed += 1
                db.audit(conn, "pipeline", "comments.error", key, {"error": str(e)[:300]})
                continue
            body = clean(out, paragraph_ids(conn, t["doc_id"]))
            if not body["points"]:
                failed += 1
                db.audit(conn, "pipeline", "comments.error", key, {"error": "no point had a valid citation"})
                continue
            conn.execute("""INSERT INTO comment_drafts(doc_id, persona, body, status) VALUES (?, ?, ?, 'proposed')
                            ON CONFLICT(doc_id, persona) DO UPDATE SET body = excluded.body, status = 'proposed', reviewer = NULL, approved_at = NULL""",
                         (t["doc_id"], t["persona"], json.dumps(body, ensure_ascii=False)))
            write_file(conn, t["doc_id"], t["persona"], body, "AI draft, not reviewed")
            db.audit(conn, "pipeline", "comments", key)
            done += 1
            conn.commit()
        db.finish_run(conn, run_id, done, failed, stopped)
    return {"comments": done, "failed": failed, **({"stopped": stopped} if stopped else {})}
