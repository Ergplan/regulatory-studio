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
    assert "__VIEWSTATE" in fields and len(items) == 2
    assert items[0].case_number == "Petition No. 2416/2026" and items[0].doc_date == "2026-11-04"
    assert len({i.key for i in items}) == 2 and all(i.key.startswith("rerc:") for i in items)


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
