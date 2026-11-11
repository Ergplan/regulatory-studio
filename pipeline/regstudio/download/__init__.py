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
from .inbox import Seen, write_item

ADAPTERS = {
    "cerc": sites.cerc,
    "uperc": sites.uperc,
    "rerc": sites.rerc,
    "merc": sites.merc,
    "gerc": sites.gerc,
    "kerc": sites.kerc,
}


def run(commissions: list[str] | None = None, since: dt.date | None = None, limit: int | None = None,
        dry_run: bool = False) -> dict:
    since = since or (dt.date.today() - dt.timedelta(days=14))
    client, seen = Client(), Seen()
    report: dict = {}
    for name in commissions or list(ADAPTERS):
        out = {"listed": 0, "new": 0, "downloaded": 0, "skipped": [], "errors": []}
        try:
            items = [i for i in ADAPTERS[name](client) if i.doc_date and i.doc_date >= since.isoformat()]
        except Exception as e:  # one site failing must not stop the others
            out["errors"].append(f"listing failed: {e}")
            report[name] = out
            continue
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
