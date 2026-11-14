"""Stage `check`: three checks on a proposed summary before the legal team sees it.

1. Numbers: every figure in the summary must appear in the document's text. Automatic, no model.
2. Fact checker: an AI reviewer that tests each number, date, party and quantity against the text.
3. Legal reader: a second AI reviewer, working separately, that tests whether the summary states the
   holding and its conditions correctly.

Neither reviewer sees the other's answer, and each writes its own reading of the document before it
looks at the summary. They change nothing: their findings go to the review screen, and a summary
with any finding is marked "needs attention". The legal reviewer still decides.
"""

from __future__ import annotations

import json
import re

from . import config, db
from .claude_runner import ClaudeError, UsageLimitReached, ask_json
from .common import NotPrepared, fill, load_prompt, load_schema, order_text, prepared_output, use_prepared
from .impact import PID, paragraph_ids

AGENTS = {"fact": "check_fact.md", "legal": "check_legal.md"}
NUMBER = re.compile(r"(?<![\w.])(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d[\d,]*(?:\.\d+)?)")  # a written date is one token


def _numbers(text: str) -> list[str]:
    out = []
    for m in NUMBER.findall(text or ""):
        n = m.replace(",", "").rstrip(".")
        if len(re.sub(r"\D", "", n)) >= 2 and n not in out:   # single digits match too easily to mean anything
            out.append(n)
    return out


MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]


def _date_found(token: str, hay: str) -> bool:
    """A date counts as found however the document writes it: 04.11.2026, 4-11-26, 4th November, 2026, November 4, 2026."""
    d, m, y = (int(x) for x in re.split(r"[./-]", token))
    if not (1 <= m <= 12):
        return False
    yy = rf"(?:{y}|{y % 100:02d})" if y > 99 else rf"(?:20{y:02d}|{y:02d})"
    name = rf"{MONTHS[m - 1][:3]}[a-z]*\.?"
    forms = [rf"(?<!\d)0?{d}\s*[./-]\s*0?{m}\s*[./-]\s*{yy}(?!\d)",
             rf"(?<!\d)0?{d}(?:\s*(?:st|nd|rd|th))?(?:\s+(?:day\s+)?of)?[\s,-]+{name}[\s,-]+{yy}(?!\d)",
             rf"{name}\s+0?{d}(?:st|nd|rd|th)?[\s,]+{yy}(?!\d)"]
    return any(re.search(f, hay, re.I) for f in forms)


def numbers_check(summary: str, doc_text: str) -> dict:
    """Figures in the summary that are not found in the document. Dates and amounts are compared as digits."""
    hay = re.sub(r"(?<=\d),(?=\d)", "", doc_text or "")
    found, missing = [], []
    for n in _numbers(summary):
        # 16.62 must not match inside 116.625; 2026 may match inside 04.11.2026
        if re.fullmatch(r"\d{1,2}[./-]\d{1,2}[./-]\d{2,4}", n):
            (found if _date_found(n, hay) else missing).append(n)
            continue
        ok = re.search(rf"(?<!\d)(?<!\d\.){re.escape(n)}(?!\d)", hay) or (n.isdigit() and re.search(rf"(?<!\d){re.escape(n)}(?!\d)", hay))
        (found if ok else missing).append(n)
    return {"checked": len(found) + len(missing), "missing": missing}


def clean(out: dict, pids: set[str] | None = None) -> dict:
    issues = []
    for it in out.get("issues") or []:
        claim, problem = (it.get("claim") or "").strip()[:300], (it.get("problem") or "").strip()[:400]
        if not claim or not problem:
            continue
        issues.append({"claim": claim, "problem": problem, "severity": it.get("severity") if it.get("severity") in ("material", "minor") else "minor",
                       "basis": [b for b in it.get("basis") or [] if isinstance(b, str) and PID.match(b) and (pids is None or b in pids)][:4]})
    issues = issues[:8]
    # a reviewer that lists problems has not passed the summary, whatever verdict it wrote
    return {"own_reading": (out.get("own_reading") or "").strip()[:400], "verdict": "concerns" if issues else "pass", "issues": issues}


def status_of(checks: dict) -> str:
    if checks.get("numbers", {}).get("missing"):
        return "attention"
    if any(checks.get(a, {}).get("issues") for a in AGENTS):
        return "attention"
    return "clear" if all(a in checks for a in AGENTS) else "partial"


def _targets(conn, limit):
    rows = []
    for t, kind in (("orders", "order"), ("consultations", "draft regulation")):
        extra = "o.issue, o.outcome, o.headline" if t == "orders" else "'' AS issue, o.proposes AS outcome, '' AS headline"
        rows += conn.execute(
            f"""SELECT d.id, d.commission, d.title, '{kind}' AS kind, o.summary, {extra}, o.checks, '{t}' AS tbl
                FROM {t} o JOIN documents d ON d.id = o.doc_id
                WHERE o.summary_status = 'proposed' AND o.summary IS NOT NULL
                  AND (o.checks IS NULL OR o.checks NOT LIKE '%"legal"%')""").fetchall()
    return rows[: int(limit)] if limit else rows


def run(limit: int | None = None) -> dict:
    schema = load_schema("check_output.schema.json")
    done = failed = attention = 0
    stopped = ""
    with db.session() as conn:
        run_id = db.start_run(conn, "check")
        for d in _targets(conn, limit):
            text, paras = order_text(conn, d["id"], budget=10_000_000)
            written = " ".join(str(d[k] or "") for k in ("summary", "issue", "outcome", "headline"))
            checks = json.loads(d["checks"]) if d["checks"] else {}
            checks["numbers"] = numbers_check(written, " ".join(paras.values()))
            pids = paragraph_ids(conn, d["id"])
            try:
                for agent, prompt in AGENTS.items():
                    if agent in checks:
                        continue
                    if config.READER == "mock":
                        continue
                    if use_prepared(f"{d['id']}.check.{agent}.json"):
                        try:
                            out = prepared_output(f"{d['id']}.check.{agent}.json", schema)
                        except NotPrepared:
                            continue
                    else:
                        body, _ = order_text(conn, d["id"], budget=120_000)
                        out = ask_json(fill(load_prompt(prompt), schema=json.dumps(schema), kind=d["kind"], title=d["title"] or "(none)",
                                            commission=config.COMMISSIONS[d["commission"]], summary=d["summary"], issue=d["issue"] or "(not stated)",
                                            outcome=d["outcome"] or "(not stated)", text=body), schema)
                    checks[agent] = clean(out, pids)
            except UsageLimitReached as e:
                stopped = f"usage limit: {e}"[:300]
            except ClaudeError as e:
                failed += 1
                db.audit(conn, "pipeline", "check.error", d["id"], {"error": str(e)[:300]})
            checks["status"] = status_of(checks)
            conn.execute(f"UPDATE {d['tbl']} SET checks = ? WHERE doc_id = ?", (json.dumps(checks, ensure_ascii=False), d["id"]))
            db.audit(conn, "pipeline", "check", d["id"], {"status": checks["status"]})
            done += 1
            attention += checks["status"] == "attention"
            conn.commit()
            if stopped:
                break
        db.finish_run(conn, run_id, done, failed, stopped)
    return {"checked": done, "needs_attention": attention, "failed": failed, **({"stopped": stopped} if stopped else {})}


def public(raw: str | None) -> dict | None:
    """What the website may say about the checks: how many AI reviewers ran, never their findings."""
    if not raw:
        return None
    c = json.loads(raw)
    return {"reviewers": sum(1 for a in AGENTS if a in c), "numbers": "numbers" in c}
