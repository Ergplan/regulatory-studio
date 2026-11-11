"""Write downloaded orders into data/inbox following the inbox contract; remember what was fetched."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Callable

from .. import config


@dataclass
class Item:
    commission: str
    title: str
    source_url: str
    doc_date: str | None                 # YYYY-MM-DD
    case_number: str | None = None
    doc_type: str = "order"
    key: str = ""                        # unique per document; defaults to source_url
    fetch: Callable = field(default=None, repr=False)

    def __post_init__(self):
        self.key = self.key or self.source_url
        if self.fetch is None:
            url = self.source_url
            self.fetch = lambda client: client.get(url)


class Seen:
    def __init__(self):
        self.path = config.STORE / "download_seen.json"
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {}

    def has(self, key: str) -> bool:
        return key in self.data

    def add(self, key: str, sha: str):
        self.data[key] = {"sha256": sha, "at": dt.datetime.now().astimezone().isoformat(timespec="seconds")}

    def save(self):
        config.STORE.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=1, sort_keys=True))


def write_item(item: Item, data: bytes) -> tuple[str, str]:
    sha = hashlib.sha256(data).hexdigest()
    today = dt.date.today().isoformat()
    base = re.sub(r"[^A-Za-z0-9]+", "-", item.case_number or item.title)[:60].strip("-") or sha[:12]
    folder = config.INBOX / item.commission / today
    folder.mkdir(parents=True, exist_ok=True)
    pdf = folder / f"{base}-{sha[:6]}.pdf"
    pdf.write_bytes(data)
    meta = {"commission": item.commission, "doc_type": item.doc_type, "source_url": item.source_url,
            "downloaded_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "sha256": sha,
            "title": item.title[:300]}
    if item.doc_date:
        meta["doc_date"] = item.doc_date
    if item.case_number:
        meta["case_number"] = item.case_number
    pdf.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return str(pdf), sha
