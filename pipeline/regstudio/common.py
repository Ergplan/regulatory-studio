"""Helpers shared by the model-driven stages."""

from __future__ import annotations

import json
import re

from . import config

WS = re.compile(r"\s+")


def norm(s: str) -> str:
    return WS.sub(" ", s or "").strip().lower()


def load_schema(name: str) -> dict:
    return json.loads((config.SCHEMAS / name).read_text())


def load_prompt(name: str) -> str:
    return (config.PROMPTS / name).read_text()


def fill(template: str, **values) -> str:
    # str.format would choke on the JSON braces inside schemas; replace named slots only.
    out = template
    for k, v in values.items():
        out = out.replace("{" + k + "}", str(v))
    return out


def order_text(conn, doc_id: str, budget: int = 150_000) -> tuple[str, dict[str, str]]:
    """Paragraphs as '[pid] text' lines. Long orders keep the opening and the conclusion."""
    rows = conn.execute("SELECT pid, text FROM paragraphs WHERE doc_id = ? ORDER BY page, idx",
                        (doc_id,)).fetchall()
    paras = {r["pid"]: r["text"] for r in rows}
    lines = [f"[{r['pid']}] {r['text']}" for r in rows]
    total = sum(len(l) + 1 for l in lines)
    if total <= budget:
        return "\n".join(lines), paras
    head, tail, used = [], [], 0
    i, j = 0, len(lines) - 1
    while i <= j and used < budget:
        head.append(lines[i]); used += len(lines[i]) + 1; i += 1
        if i <= j and used < budget:
            tail.insert(0, lines[j]); used += len(lines[j]) + 1; j -= 1
    return "\n".join(head + ["[...] (middle of the order omitted for length)"] + tail), paras


class NotPrepared(Exception):
    """READER=file and no prepared output exists yet for this document."""


def prepared_output(name: str, schema: dict) -> dict:
    import jsonschema
    path = config.READER_OUTPUTS / name
    if not path.exists():
        raise NotPrepared(name)
    data = json.loads(path.read_text())
    jsonschema.validators.validator_for(schema)(schema).validate(data)
    return data
