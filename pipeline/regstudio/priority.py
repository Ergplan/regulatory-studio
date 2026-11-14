"""Review priority: which item the legal team should open first.

A score out of 100, worked out by code from what is already in the database, so it is the same every time
and every point can be explained. It orders the review queue and is never published. It has four parts:

  reach        how many stakeholders the document touches (a draft regulation binds a whole State or the
               inter-State market; an order counts its parties, its significance and the groups affected)
  opportunity  work it could bring: jouleWise advisory (tenders, storage, open access ...) and Urja Praxis
               legal work (comments on a draft while the window is open, disputes, relaxations)
  leads        named businesses or whole classes of participants who may want help
  urgency      a comment deadline or hearing coming up, or a fresh order

The weights are plain numbers below; change them here, not in the templates.
"""

from __future__ import annotations

import datetime as dt
import json
import re

REVIEW_FIRST, THIS_WEEK = 70, 45
MAX = {"reach": 40, "opportunity": 30, "leads": 20, "urgency": 10}

# Subjects where jouleWise advises clients. (label, pattern)
ADVISORY = [
    ("tender or power procurement", r"\btender|bidding|\bbid\b|procure|section 63|adoption of tariff"),
    ("storage", r"\bbess\b|battery|energy storage|pumped"),
    ("open access, captive or banking", r"open access|captive|banking|wheeling|cross[- ]subsidy|additional surcharge"),
    ("renewable energy", r"renewable|\bsolar\b|\bwind\b|hybrid|\bfdre\b|green energy|\brpo\b"),
    ("transmission charges or connectivity", r"\bists\b|transmission charge|connectivity|\bgna\b|waiver"),
    ("peak power or demand flexibility", r"peak power|peak hours|demand response|demand flexibility|time[- ]of[- ]day"),
    ("deviation settlement", r"deviation settlement|\bdsm\b"),
]
# Subjects that turn into legal work for Urja Praxis.
LEGAL = [
    ("a dispute over money or security", r"bank guarantee|encash|penalt|compensation|liquidated damages|refund"),
    ("force majeure or change in law", r"force majeure|change in law"),
    ("non-compliance proceedings", r"section 142|contravention|non-compliance"),
    ("a relaxation or deviation", r"power to relax|relax|deviation from|removal of difficult"),
    ("an appeal or remand", r"\bappeal|remand|set aside|\baptel\b"),
]
NOT_A_LEAD = re.compile(r"commission|regulatory|ministry|government of|load despatch|\bsldc\b|\brldc\b|\bnldc\b|grid controller|"
                        r"central electricity authority|secretary|\bothers?\b", re.I)


def _days(date: str | None, today: dt.date) -> int | None:
    try:
        return (dt.date.fromisoformat(date[:10]) - today).days if date else None
    except ValueError:
        return None


def _groups(impact: str | None) -> int:
    try:
        return sum(1 for v in (json.loads(impact).get("stakeholders") or {}).values() if (v or {}).get("comment")) if impact else 0
    except (ValueError, AttributeError):
        return 0


def _matches(table, text: str) -> list[str]:
    return [label for label, pat in table if re.search(pat, text, re.I)]


def lead_names(parties: str | None) -> list[str]:
    try:
        names = [(p.get("name") or "").strip() for p in json.loads(parties or "[]")]
    except (ValueError, AttributeError):
        return []
    out = []
    for n in names:
        if n and not NOT_A_LEAD.search(n) and n.lower() not in (x.lower() for x in out):
            out.append(n)
    return out


def score(item: dict, today: dt.date | None = None) -> dict:
    """item: kind ('draft' | 'order'), commission, title, summary, text (issue, outcome, proposes), impact,
    significance, parties, comment_deadline, hearing_date, doc_date."""
    today = today or dt.date.today()
    text = " ".join(str(item.get(k) or "") for k in ("title", "summary", "text", "topics"))
    groups = _groups(item.get("impact"))
    parts, why, leads = dict.fromkeys(MAX, 0), [], []
    advisory, legal = _matches(ADVISORY, text), _matches(LEGAL, text)

    if item["kind"] == "draft":
        central = item.get("commission") in ("cerc", "aptel")
        parts["reach"] = 30 + min(10, 2 * groups)
        why.append("Draft regulation: it will bind every participant " + ("in the inter-State market" if central else "in the State")
                   + (f"; {groups} stakeholder groups affected" if groups else ""))
        left = _days(item.get("comment_deadline"), today)
        hearing = _days(item.get("hearing_date"), today)
        window = left is None or left >= 0
        parts["opportunity"] = (14 if window else 2) + min(16, 4 * len(advisory))
        if window:
            why.append("Comments can still be filed: work for Urja Praxis and a reason to call clients")
        else:
            why.append("The comment window has closed")
        parts["leads"] = 12 + min(8, 2 * groups) if window else 6
        why.append("Leads: every discom, developer and large consumer it affects may want comments or an impact note")
        if left is not None and left >= 0:
            parts["urgency"] = 10 if left <= 7 else 8 if left <= 14 else 5 if left <= 30 else 3
            why.append(f"Comments due in {left} day{'s' if left != 1 else ''}" if left else "Comments are due today")
        elif left is None:
            parts["urgency"] = 4
        if hearing is not None and 0 <= hearing <= 14:
            parts["urgency"] = max(parts["urgency"], 8)
            why.append(f"Public hearing in {hearing} day{'s' if hearing != 1 else ''}")
    else:
        leads = lead_names(item.get("parties"))
        try:
            n_parties = len(json.loads(item.get("parties") or "[]"))
        except ValueError:
            n_parties = 0
        sig = int(item.get("significance") or 1)
        by_parties = 0 if n_parties <= 1 else 6 if n_parties == 2 else 12 if n_parties <= 4 else 18
        parts["reach"] = min(40, by_parties + 4 * (sig - 1) + min(8, 2 * groups))
        if n_parties >= 3:
            why.append(f"{n_parties} parties are involved")
        if sig >= 4:
            why.append("Sector-wide effect" if sig == 5 else "Interprets or relaxes a regulation, so others can rely on it")
        if groups:
            why.append(f"{groups} stakeholder groups affected")
        parts["opportunity"] = min(30, min(16, 4 * len(advisory)) + min(14, 5 * len(legal)))
        parts["leads"] = min(20, 4 * len(leads) + (4 if sig >= 4 else 0))
        if leads:
            why.append("Leads: " + ", ".join(leads[:4]) + (f" and {len(leads) - 4} more" if len(leads) > 4 else ""))
        age = _days(item.get("doc_date"), today)
        if age is not None:
            parts["urgency"] = 10 if age >= -7 else 6 if age >= -14 else 3 if age >= -30 else 0
    if advisory:
        why.append("jouleWise advisory: " + ", ".join(advisory[:3]))
    if legal and item["kind"] != "draft":
        why.append("Urja Praxis: " + ", ".join(legal[:3]))
    parts = {k: max(0, min(MAX[k], v)) for k, v in parts.items()}
    total = sum(parts.values())
    band = "Review first" if total >= REVIEW_FIRST else "This week" if total >= THIS_WEEK else "When time allows"
    return {"score": total, "band": band, "parts": parts, "max": MAX, "why": why, "leads": leads}


def for_order(row, today: dt.date | None = None) -> dict:
    r = dict(row)
    return score({"kind": "order", "commission": r.get("commission"), "title": r.get("title"), "summary": r.get("summary"),
                  "text": f"{r.get('issue') or ''} {r.get('outcome') or ''} {r.get('headline') or ''}", "topics": r.get("topics"),
                  "impact": r.get("impact"), "significance": r.get("significance"), "parties": r.get("parties"),
                  "doc_date": r.get("doc_date")}, today)


def for_consultation(row, today: dt.date | None = None) -> dict:
    r = dict(row)
    return score({"kind": "draft", "commission": r.get("commission"), "title": r.get("title"), "summary": r.get("summary"),
                  "text": f"{r.get('proposes') or ''} {r.get('amends') or ''}", "impact": r.get("impact"),
                  "comment_deadline": r.get("comment_deadline"), "hearing_date": r.get("hearing_date")}, today)
