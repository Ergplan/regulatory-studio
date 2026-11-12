"""Commission downloaders: list recent orders on each commission's website and drop new ones
into data/inbox with their metadata, following the inbox contract.

    regstudio download --since 2026-09-11              # all commissions
    regstudio download --commission merc --dry-run     # list what would be fetched

Every request goes through http.Client: identified user agent, a pause between requests to the
same site, robots.txt honoured, full TLS verification (missing intermediate certificates are
fetched from the address in the site's own certificate, never skipped). Nothing is fetched twice:
data/store/download_seen.json records what has been downloaded.
"""

from __future__ import annotations

import datetime as dt

from . import sites
from .http import Client
from .inbox import Item, Seen, write_item

ADAPTERS = {
    "cerc": sites.cerc,
    "uperc": sites.uperc,
    "rerc": sites.rerc,
    "merc": sites.merc,
    "gerc": sites.gerc,
    "kerc": sites.kerc,
    "rerc-regs": sites.rerc_regulations,  # new RERC regulations and amendments
    "cerc-drafts": sites.cerc_drafts,     # draft regulations and consultations
    "gerc-drafts": sites.gerc_drafts,
    "kerc-drafts": sites.kerc_drafts,
}


def _recent(item, since: str) -> bool:
    """Orders by their date; a draft also counts while its comment deadline or hearing is ahead."""
    dates = [item.doc_date] + ([item.extra.get("comment_deadline"), item.extra.get("hearing_date")]
                               if item.doc_type == "draft" else [])
    return any(d and d >= since for d in dates)


def run(commissions: list[str] | None = None, since: dt.date | None = None, limit: int | None = None,
        dry_run: bool = False, match: str | None = None) -> dict:
    since = since or (dt.date.today() - dt.timedelta(days=14))
    client, seen = Client(), Seen()
    report: dict = {}
    for name in commissions or list(ADAPTERS):
        out = {"on_page": 0, "newest": None, "listed": 0, "new": 0, "downloaded": 0,
               "skipped": [], "errors": [], "warnings": []}
        try:
            everything = ADAPTERS[name](client)
        except Exception as e:  # one site failing must not stop the others
            out["errors"].append(f"listing failed: {e}")
            report[name] = out
            continue
        out["on_page"] = len(everything)
        dated = [i.doc_date or i.extra.get("comment_deadline") or i.extra.get("hearing_date")
                 for i in everything if i.doc_date or i.extra.get("comment_deadline") or i.extra.get("hearing_date")]
        out["newest"] = max(dated) if dated else None
        if not everything:
            out["warnings"].append("no orders recognised on the listing page; the site layout may have changed")
        elif len(dated) < len(everything) and not name.endswith("-drafts"):  # old drafts often carry no dates
            out["warnings"].append(f"{len(everything) - len(dated)} listed orders have no date and were left out")
        items = [i for i in everything if _recent(i, since.isoformat())
                 and (not match or match.lower() in i.title.lower())]
        out["listed"] = len(items)
        fresh = [i for i in items if not seen.has(i.key)]
        out["new"] = len(fresh)
        for item in fresh[: limit or None]:
            if dry_run:
                out["skipped"].append(f"{item.doc_date} {item.case_number or ''} {item.title[:80]}")
                continue
            try:
                data = item.fetch(client)
                if not data.startswith(b"%PDF"):
                    raise ValueError("response is not a PDF")
                path, sha = write_item(item, data)
                seen.add(item.key, sha)
                out["downloaded"] += 1
            except Exception as e:
                out["errors"].append(f"{item.case_number or item.title[:40]}: {e}")
        seen.save()
        report[name] = out
    return report


def fetch_one(url: str, commission: str, doc_type: str, date: str | None = None, title: str | None = None,
              case: str | None = None, client=None, source: str | None = None) -> dict:
    """Fetch a single document chosen by a person (APTEL judgments, MERC orders, regulations).

    Uses the same polite client as the listings (robots.txt, pause, TLS chain repair) and the same
    inbox writer, so the file and its metadata follow the inbox contract."""
    import datetime as _dt
    if date:
        _dt.date.fromisoformat(date)  # refuse a malformed date rather than store it
    from pathlib import Path as _P
    local = _P(url).expanduser()
    if local.is_file():  # a PDF a person saved from the site in their browser (e.g. MERC)
        if not source:
            raise SystemExit("give --source-url: the page or PDF address the file was saved from")
        data, url = local.read_bytes(), source
    else:
        client = client or Client()
        data = client.get(url)
    if not data.startswith(b"%PDF"):
        raise SystemExit(f"not a PDF (the site may have returned an error page): {url}")
    item = Item(commission, title or url.rsplit("/", 1)[-1], url, date, case, doc_type=doc_type)
    path, sha = write_item(item, data)
    return {"saved": path, "sha256": sha, "kb": len(data) // 1024}
