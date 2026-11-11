"""Downloader parsers, tested on extracts of each commission's listing page (saved Nov 2026)."""

import json
from pathlib import Path

from regstudio.download import sites
from regstudio.download.inbox import Item, Seen, write_item

L = Path(__file__).parent / "fixtures" / "listings"


def read(name):
    return (L / name).read_text(encoding="utf-8")


def test_cerc():
    items = sites.parse_cerc(read("cerc.html"))
    assert items and all(i.source_url.startswith("https://cercind.gov.in/") and i.source_url.endswith(".pdf") for i in items)
    assert all(i.doc_date and i.case_number.startswith("Petition No.") for i in items)


def test_uperc():
    items = sites.parse_uperc(read("uperc.html"))
    assert items and all(i.source_url.startswith("https://www.uperc.org/App_File/") for i in items)
    assert all(i.doc_date and len(i.doc_date) == 10 for i in items)


def test_rerc_uses_postback_with_unique_keys():
    fields, items = sites.parse_rerc(read("rerc.html"))
    assert "__VIEWSTATE" in fields and len(items) == 3
    assert items[0].case_number == "Petition No. 2416/2026" and items[0].doc_date == "2026-11-04"
    assert len({i.key for i in items}) == 3 and all(i.key.startswith("rerc:") for i in items)


def test_merc():
    items = sites.parse_merc(read("merc.json"))
    assert len(items) == 3 and all(i.source_url.endswith(".pdf") and i.case_number.startswith("Case No.") for i in items)
    assert items[0].doc_date == "2026-11-06"


def test_gerc():
    items = sites.parse_gerc(read("gerc.html"))
    assert items and all("/viewdocument/" in i.source_url and i.doc_date for i in items)


def test_kerc():
    items = sites.parse_kerc(read("kerc.html"))
    assert items and all(i.source_url.endswith(".pdf") for i in items)


def test_dates_and_inbox_contract(env):
    from regstudio import intake
    assert sites._date("04.11.2026") == sites._date("04/11/26") == sites._date("04-11-2026") == "2026-11-04"
    assert sites._date("not a date") is None
    item = Item("cerc", "Sample title", "https://example.invalid/x.pdf", "2026-11-04", "Petition No. 1/MP/2026")
    data = b"%PDF-1.4 sample"
    path, sha = write_item(item, data)
    meta = json.loads(Path(path).with_suffix(".json").read_text())
    assert meta["sha256"] == sha and meta["commission"] == "cerc" and meta["doc_date"] == "2026-11-04"
    report = intake.check()
    assert {"file": str(Path(path).relative_to(intake.config.INBOX)), "problem": "file is not a PDF (check for an HTML error page saved as .pdf)"} not in report["problems"]
    seen = Seen(); seen.add(item.key, sha); seen.save()
    assert Seen().has(item.key)


def test_robots_longest_match():
    from regstudio.download.http import robots_allows, robots_rules
    wp = robots_rules("User-agent: *\nDisallow: /wp-admin/\nAllow: /wp-admin/admin-ajax.php\n")
    assert robots_allows(wp, "/wp-admin/admin-ajax.php?action=x")
    assert not robots_allows(wp, "/wp-admin/options.php")
    assert robots_allows(wp, "/orders/")
    assert not robots_allows(robots_rules("User-agent: *\nDisallow: /\n"), "/anything")
    assert robots_allows(robots_rules(""), "/x")
    own = robots_rules("User-agent: *\nDisallow: /\n\nUser-agent: RegulatoryStudio\nAllow: /\n")
    assert robots_allows(own, "/orders")


def test_run_reports_layout_changes(env, monkeypatch):
    import regstudio.download as dl
    ok = [Item("cerc", "A", "https://example.invalid/a.pdf", "2026-11-04", "P1", fetch=lambda c: b"%PDF-1.4 a"),
          Item("cerc", "B", "https://example.invalid/b.pdf", None, "P2")]
    monkeypatch.setattr(dl, "ADAPTERS", {"cerc": lambda c: ok, "kerc": lambda c: []})
    monkeypatch.setattr(dl, "Client", lambda: None)
    out = dl.run(since=__import__("datetime").date(2026, 11, 1))
    assert out["cerc"]["downloaded"] == 1 and out["cerc"]["newest"] == "2026-11-04"
    assert "no date" in out["cerc"]["warnings"][0]
    assert "layout may have changed" in out["kerc"]["warnings"][0]
    assert dl.run(since=__import__("datetime").date(2026, 11, 1))["cerc"]["new"] == 0  # remembered


def test_status_shows_last_download(env, monkeypatch):
    import regstudio.download as dl
    from regstudio import cli, db
    db.init()
    monkeypatch.setattr(dl, "ADAPTERS", {"kerc": lambda c: []})
    monkeypatch.setattr(dl, "Client", lambda: None)
    cli.main(["download"])
    last = cli.status()["last_download"]
    assert last["at"] and "layout may have changed" in last["kerc"]["problems"][0]


def test_fetch_one_writes_inbox_contract(env):
    import json as _j
    from regstudio import intake
    from regstudio.download import fetch_one

    class Fake:
        def get(self, url):
            return b"%PDF-1.4 regulation"
    out = fetch_one("https://example.invalid/geoa-2025.pdf", "rerc", "regulation", "2025-03-10",
                    "RERC (Terms and Conditions for Green Energy Open Access) Regulations, 2025", client=Fake())
    meta = _j.loads(Path(out["saved"]).with_suffix(".json").read_text())
    assert meta["doc_type"] == "regulation" and meta["doc_date"] == "2025-03-10"
    assert not [p for p in intake.check()["problems"] if "geoa" in p["file"].lower()]

    class Html:
        def get(self, url):
            return b"<html>error</html>"
    import pytest as _p
    with _p.raises(SystemExit):
        fetch_one("https://example.invalid/x.pdf", "aptel", "judgment", client=Html())


def test_rerc_alternate_rows_and_regulations():
    _, orders = sites.parse_rerc(read("rerc.html"))
    assert len(orders) == 3  # rows alternate between "tabrow" and "tabrowalt"
    fields, regs = sites.parse_rerc_regulations(read("rerc_regulations.html"))
    assert "__VIEWSTATE" in fields
    geoa = next(i for i in regs if "Green Energy Open Access" in i.title)
    assert geoa.doc_date == "2025-07-17" and geoa.doc_type == "regulation" and geoa.key == "rerc-reg:158:17/07/2025"
    amend = next(i for i in regs if "Amendment" in i.title)
    assert amend.doc_type == "amendment"


def test_fetch_saved_pdf_needs_its_source(env, tmp_path):
    import pytest as _p
    from regstudio.download import fetch_one
    pdf = tmp_path / "merc-order.pdf"
    pdf.write_bytes(b"%PDF-1.4 merc")
    with _p.raises(SystemExit):
        fetch_one(str(pdf), "merc", "order", "2026-11-06")
    out = fetch_one(str(pdf), "merc", "order", "2026-11-06", case="Case No. 101 of 2026",
                    source="https://merc.gov.in/wp-content/uploads/2026/11/Order-101.pdf")
    assert json.loads(Path(out["saved"]).with_suffix(".json").read_text())["source_url"].startswith("https://merc.gov.in/")
