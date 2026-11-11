"""Stopgap until the team's download script exists: fetch one public order PDF into the inbox
with its metadata file, following the inbox contract in pipeline/schemas/inbox_metadata.schema.json.

usage: python3 ops/fetch_one.py <url> <commission> <doc_type> [--date YYYY-MM-DD] [--title T] [--case C]
"""
import argparse, datetime as dt, hashlib, json, re, sys, urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("url"); ap.add_argument("commission"); ap.add_argument("doc_type")
ap.add_argument("--date"); ap.add_argument("--title"); ap.add_argument("--case")
a = ap.parse_args()
req = urllib.request.Request(a.url, headers={"User-Agent": "Mozilla/5.0 (RegulatoryStudio fetch)"})
data = urllib.request.urlopen(req, timeout=170).read()
if not data.startswith(b"%PDF"):
    sys.exit(f"not a PDF: {a.url}")
today = dt.date.today().isoformat()
name = re.sub(r"[^a-zA-Z0-9]+", "-", a.case or a.url.rsplit("/", 1)[-1].rsplit(".", 1)[0]).strip("-")[:60]
folder = Path(__file__).resolve().parents[1] / "data" / "inbox" / a.commission / today
folder.mkdir(parents=True, exist_ok=True)
pdf = folder / f"{name}.pdf"
pdf.write_bytes(data)
meta = {"commission": a.commission, "doc_type": a.doc_type, "source_url": a.url,
        "downloaded_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "sha256": hashlib.sha256(data).hexdigest()}
for k, v in (("doc_date", a.date), ("title", a.title), ("case_number", a.case)):
    if v: meta[k] = v
pdf.with_suffix(".json").write_text(json.dumps(meta, indent=2))
print(f"{pdf.relative_to(folder.parents[2])}  {len(data)//1024} KB")
