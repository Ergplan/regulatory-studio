"""Stage `commercial` (beta): a simple worked example of what an order or tender means in money.

Claude chooses the question and sets out the inputs and the steps. Every input is either taken from the
document (with its paragraph id) or marked as an assumption with the reason for it. The arithmetic is done
here, by code, never by the model, and the takeaway can only quote computed values through {step} slots.
The jouleWise commercial team reviews each illustration; it is shown as a beta illustration, not advice.
"""

from __future__ import annotations

import ast
import json
import operator
import re

from . import config, db
from .claude_runner import ClaudeError, UsageLimitReached, ask_json
from .common import NotPrepared, fill, load_prompt, load_schema, order_text, prepared_output, use_prepared

NAME = re.compile(r"^[a-z][a-z0-9_]{0,23}$")
PID = re.compile(r"^p\d+\.\d+$")
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
TABLES = {"orders": "order", "consultations": "draft regulation"}
REQUESTED = "requested"


class BadExpression(ValueError):
    pass


def evaluate(expr: str, env: dict[str, float]) -> float:
    """+ - * / and brackets over numbers and known names. Nothing else is accepted."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return float(n.value)
        if isinstance(n, ast.Name) and n.id in env:
            return env[n.id]
        if isinstance(n, ast.BinOp) and type(n.op) in OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Div) and b == 0:
                raise BadExpression("division by zero")
            return OPS[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -ev(n.operand)
        raise BadExpression(f"not allowed: {ast.dump(n)[:60]}")
    if len(expr) > 200:
        raise BadExpression("too long")
    try:
        return ev(ast.parse(expr, mode="eval"))
    except SyntaxError as e:
        raise BadExpression(str(e)) from e


def fmt(v: float, decimals: int) -> str:
    """Indian digit grouping: 12,34,567.89."""
    s = f"{abs(v):.{decimals}f}"
    whole, _, frac = s.partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        whole = f"{head},{tail}"
    return ("-" if v < 0 else "") + whole + (f".{frac}" if frac else "")


def build(out: dict, pids: set[str]) -> dict | None:
    """Check the inputs, run the steps, fill the takeaway. Returns None if the illustration does not hold up."""
    env: dict[str, float] = {}
    inputs = []
    for i in (out.get("inputs") or [])[:8]:
        name, label = i.get("id", ""), (i.get("label") or "").strip()
        if not (NAME.match(name) and label and isinstance(i.get("value"), (int, float))) or name in env:
            return None
        basis = [b for b in i.get("basis") or [] if PID.match(b) and b in pids][:3]
        assumption = (i.get("assumption") or "").strip()[:240]
        if not basis and not assumption:
            return None                    # every input is either sourced or openly assumed
        env[name] = float(i["value"])
        inputs.append({"id": name, "label": label[:80], "value": i["value"], "unit": (i.get("unit") or "")[:16],
                       **({"basis": basis} if basis else {"assumption": assumption})})
    steps = []
    for s in (out.get("steps") or [])[:6]:
        name, label = s.get("id", ""), (s.get("label") or "").strip()
        if not (NAME.match(name) and label) or name in env:
            return None
        try:
            v = evaluate(s.get("expr") or "", env)
        except BadExpression:
            return None
        d = int(s.get("decimals", 0)) if isinstance(s.get("decimals"), int) and 0 <= s.get("decimals") <= 2 else 0
        env[name] = v
        steps.append({"id": name, "label": label[:100], "expr": s["expr"], "value": round(v, d), "shown": fmt(v, d),
                      "unit": (s.get("unit") or "")[:16]})
    if not inputs or not steps:
        return None
    shown = {s["id"]: s["shown"] for s in steps}
    takeaway = (out.get("takeaway") or "").strip()[:300]
    if re.search(r"\d", re.sub(r"\{[a-z][a-z0-9_]*\}", "", takeaway)):
        return None                        # numbers in prose must come from the computed steps
    try:
        takeaway = re.sub(r"\{([a-z][a-z0-9_]*)\}", lambda m: shown[m.group(1)], takeaway)
    except KeyError:
        return None
    return {"title": (out.get("title") or "").strip()[:90], "question": (out.get("question") or "").strip()[:200],
            "inputs": inputs, "steps": steps, "takeaway": takeaway,
            "caveats": [c.strip()[:200] for c in (out.get("caveats") or [])[:3] if c.strip()]}


def request(conn, prefixes: list[str]) -> int:
    n = 0
    for t in TABLES:
        for p in prefixes:
            n += conn.execute(f"UPDATE {t} SET commercial_status = ? WHERE doc_id LIKE ? AND coalesce(commercial_status, '') != 'approved'",
                              (REQUESTED, p + "%")).rowcount
    return n


def run(limit: int | None = None) -> dict:
    schema = load_schema("commercial_output.schema.json")
    done = failed = 0
    stopped = ""
    with db.session() as conn:
        rows = []
        for t, kind in TABLES.items():
            summary = "o.summary"
            for r in conn.execute(f"""SELECT d.id, d.commission, d.title, '{kind}' AS kind, {summary} AS summary, '{t}' AS tbl,
                                            o.commercial_status FROM {t} o JOIN documents d ON d.id = o.doc_id
                                      WHERE o.summary IS NOT NULL AND (o.commercial_status = 'requested'
                                        OR (o.commercial_status IS NULL AND o.commercial IS NULL))""").fetchall():
                if r["commercial_status"] == REQUESTED or (config.READER_OUTPUTS / f"{r['id']}.commercial.json").exists():
                    rows.append(r)
        for d in rows[: int(limit)] if limit else rows:
            name = f"{d['id']}.commercial.json"
            try:
                if use_prepared(name):
                    out = prepared_output(name, schema)
                elif config.READER == "mock":
                    continue
                else:
                    text, _ = order_text(conn, d["id"], budget=60_000)
                    out = ask_json(fill(load_prompt("commercial.md"), schema=json.dumps(schema), kind=d["kind"],
                                        commission=config.COMMISSIONS[d["commission"]], title=d["title"] or "(none)",
                                        summary=d["summary"] or "", text=text), schema)
            except NotPrepared:
                continue
            except UsageLimitReached as e:
                stopped = f"usage limit: {e}"[:300]
                break
            except ClaudeError as e:
                failed += 1
                db.audit(conn, "pipeline", "commercial.error", d["id"], {"error": str(e)[:300]})
                continue
            pids = {r[0] for r in conn.execute("SELECT pid FROM paragraphs WHERE doc_id = ?", (d["id"],))}
            result = build(out, pids)
            if result is None:
                failed += 1
                db.audit(conn, "pipeline", "commercial.dropped", d["id"], {"why": "inputs or steps did not hold up"})
                conn.execute(f"UPDATE {d['tbl']} SET commercial_status = NULL WHERE doc_id = ?", (d["id"],))
                continue
            conn.execute(f"UPDATE {d['tbl']} SET commercial = ?, commercial_status = 'proposed', commercial_by = NULL WHERE doc_id = ?",
                         (json.dumps(result, ensure_ascii=False), d["id"]))
            done += 1
    return {"illustrations": done, "failed": failed, **({"stopped": stopped} if stopped else {})}


def load(raw: str | None) -> dict | None:
    return json.loads(raw) if raw else None
