"""Rule-based stand-ins for the Claude stages (REGSTUDIO_READER=mock). For tests and demos only.

Their output is marked so it can never be mistaken for a real summary.
"""

from __future__ import annotations

import re

REG_CITE = re.compile(r"Regulation\s+(\d{1,3}[A-Z]?(?:\(\d{1,2}[a-z]?\))?)", re.I)
SEC_CITE = re.compile(r"Section\s+(\d{1,3}[A-Z]?)\s+of\s+the\s+Electricity\s+Act", re.I)

KEYWORDS = {
    "banking": ["banking", "banked"],
    "open-access": ["open access"],
    "green-energy-oa": ["green energy"],
    "css": ["cross-subsidy", "cross subsidy"],
    "wheeling": ["wheeling"],
    "retail-tariff": ["retail tariff", "tariff order"],
}


def triage(text: str) -> dict:
    low = text.lower()
    topics = [t for t, words in KEYWORDS.items() if any(w in low for w in words)]
    sig = 4 if "relax" in low else (3 if topics else 1)
    return {"in_scope": bool(topics), "topics": topics[:5], "significance": sig,
            "reason": "[mock triage] keyword match: " + (", ".join(topics) or "none")}


def read(paras: dict[str, str], registry: list[dict], commission: str) -> dict:
    refs = []
    for pid, text in paras.items():
        for m in REG_CITE.finditer(text):
            num = m.group(1)
            cands = [r["clause_id"] for r in registry
                     if r["number"] == num and r["commission"] == commission]
            link = "relaxes" if "relax" in text.lower() else "applies"
            refs.append({"citation_text": m.group(0), "link_type": link, "target_kind": "clause",
                         "target_id": cands[0] if len(cands) == 1 else None, "pid": pid,
                         "excerpt": text[:280]})
        for m in SEC_CITE.finditer(text):
            refs.append({"citation_text": m.group(0), "link_type": "applies",
                         "target_kind": "act_section", "target_id": f"ea2003/s{m.group(1)}",
                         "pid": pid, "excerpt": text[:280]})
    body = [t for t in paras.values() if re.match(r"^\d+\.\s", t)]
    return {
        "parties": [{"name": t.split("...")[0].strip(), "role": t.split("...")[-1].strip().lower()}
                    for t in paras.values() if "..." in t][:4],
        "issue": body[0][:300] if body else "",
        "outcome": body[-1][:300] if body else "",
        "summary": "[MOCK SUMMARY - not reviewed] " + " ".join(body)[:900],
        "references": refs,
    }


def digest(items: list[dict]) -> dict:
    return {"intro": "[MOCK DIGEST INTRO] " + f"{len(items)} items this week.",
            "order": [i["id"] for i in sorted(items, key=lambda i: -(i.get("significance") or 0))]}
