"""One adapter per commission. Each `parse_*` function is pure (page text in, items out) so it can
be tested on saved pages; each adapter function fetches the listing and returns Items.

Listing pages, as found in November 2026:
  CERC   https://cercind.gov.in/recent_orders.html                        HTML table
  UPERC  https://www.uperc.org/Order_Users.aspx                           links "Order dated DD/MM/YY for ..."
  RERC   https://rerc.rajasthan.gov.in/rerc-user-files/office-orders      ASP.NET table; PDF via postback
  MERC   https://merc.gov.in/wp-admin/admin-ajax.php?action=getpostsfororderdatatables   JSON
         (merc.gov.in's robots.txt disallows all bots as of Nov 2026, so the client refuses it)
  GERC   https://gercin.org/orders/orders_petition/judgement_orders?page=N              HTML table, paged
  KERC   https://kerc.karnataka.gov.in/42/miscellaneous-orders/en (and tariff pages)    HTML table
APTEL's judgment list is rendered in the browser with no data endpoint; use ops/fetch_one.py.
"""

from __future__ import annotations

import html as htmllib
import json
import re
import urllib.parse

from .inbox import Item

TAG = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")


def _text(fragment: str) -> str:
    return WS.sub(" ", htmllib.unescape(TAG.sub(" ", fragment))).strip()


def _cells(row: str) -> list[str]:
    return re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)


def _date(s: str, order: str = "dmy") -> str | None:
    """'04.11.2026', '04/11/26', '07-11-2026' -> '2026-11-04'."""
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", s or "")
    if not m:
        return None
    d, mth, y = (int(x) for x in m.groups())
    y = y + 2000 if y < 100 else y
    if not (1 <= mth <= 12 and 1 <= d <= 31):
        return None
    return f"{y:04d}-{mth:02d}-{d:02d}"


# --- CERC -------------------------------------------------------------------------------------
CERC_URL = "https://cercind.gov.in/recent_orders.html"


def parse_cerc(page: str, base: str = CERC_URL) -> list[Item]:
    items = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        cells = _cells(row)
        if len(cells) < 5:
            continue
        link = re.search(r'href="([^"]+\.pdf)"[^>]*>(.*?)</a>', cells[2], re.S | re.I)
        if not link:
            continue
        party = re.search(r"<strong>(.*?)</strong>", link.group(2), re.S | re.I)
        subject = _text(re.sub(r"<strong>.*?</strong>", "", link.group(2), flags=re.S | re.I))
        petition = _text(cells[1])
        title = f"{_text(party.group(1)) + ': ' if party else ''}{subject}"
        items.append(Item("cerc", title, urllib.parse.urljoin(base, link.group(1).strip()), _date(_text(cells[3])),
                          f"Petition No. {petition}" if petition else None))
    return items


def cerc(client) -> list[Item]:
    return parse_cerc(client.get(CERC_URL).decode("utf-8", "ignore"))


# --- UPERC ------------------------------------------------------------------------------------
UPERC_URL = "https://www.uperc.org/Order_Users.aspx"
UPERC_LINK = re.compile(r"<a\s+href=['\"]?(App_File/[^'\"\s>]+\.pdf)['\"]?[^>]*>(.*?)</a>", re.S | re.I)


def parse_uperc(page: str, base: str = UPERC_URL) -> list[Item]:
    items, seen = [], set()
    for href, label in UPERC_LINK.findall(page):
        text = _text(label)
        m = re.search(r"Order dated\s+([\d/.\-]+)", text, re.I)
        if not m:
            continue
        url = urllib.parse.urljoin(base, href)
        if url in seen:
            continue
        seen.add(url)
        pet = re.search(r"(\d{3,5}\s+of\s+\d{4})", text)
        subject = re.sub(r"^Order dated\s+[\d/.\-]+\s+for\s+(Petition\s+(Number|No\.?)\s*)?-?\s*", "", text, flags=re.I)
        items.append(Item("uperc", subject, url, _date(m.group(1)), f"Petition No. {pet.group(1)}" if pet else None))
    return items


def uperc(client) -> list[Item]:
    return parse_uperc(client.get(UPERC_URL).decode("utf-8", "ignore"))


# --- RERC -------------------------------------------------------------------------------------
RERC_URL = "https://rerc.rajasthan.gov.in/rerc-user-files/office-orders"


def parse_rerc(page: str) -> tuple[dict, list[Item]]:
    fields = {k: htmllib.unescape(v) for k, v in
              re.findall(r'<input type="hidden" name="(__[A-Z]+)" id="__[A-Z]+" value="([^"]*)"', page)}
    items = []
    for row in re.findall(r'<tr class="tabrow(?:alt)?">(.*?)</tr>', page, re.S):  # rows alternate classes
        cells = _cells(row)
        target = re.search(r"__doPostBack\(&#39;([^&]+LinkButton[12])&#39;", row)
        if len(cells) < 5 or not target:
            continue
        petition, party, subject, date = (_text(c) for c in cells[1:5])
        key = f"rerc:{petition}:{date}:{subject[:60]}"
        items.append(Item("rerc", f"{party}: {subject}" if party else subject, RERC_URL, _date(date),
                          f"Petition No. {petition}" if petition else None, key=key,
                          fetch=_rerc_fetch(target.group(1))))
    return fields, items


def _rerc_fetch(target: str):
    def fetch(client):
        # Each download replays the postback against a fresh copy of the page (view state changes).
        fields, _ = parse_rerc(client.get(RERC_URL).decode("utf-8", "ignore"))
        return client.post(RERC_URL, {**fields, "__EVENTTARGET": target, "__EVENTARGUMENT": ""})
    return fetch


def rerc(client) -> list[Item]:
    _, items = parse_rerc(client.get(RERC_URL).decode("utf-8", "ignore"))
    return items


RERC_REGS_URL = "https://rerc.rajasthan.gov.in/rerc-user-files/regulations"


def parse_rerc_regulations(page: str) -> tuple[dict, list[Item]]:
    """RERC's regulations list: S.No, notification no., date, title; PDF via the same postback."""
    fields = {k: htmllib.unescape(v) for k, v in
              re.findall(r'<input type="hidden" name="(__[A-Z]+)" id="__[A-Z]+" value="([^"]*)"', page)}
    items = []
    for row in re.findall(r'<tr class="tabrow(?:alt)?">(.*?)</tr>', page, re.S):
        cells = _cells(row)
        target = re.search(r"__doPostBack\(&#39;([^&]+LinkButton[12])&#39;", row)
        if len(cells) < 5 or not target:
            continue
        notification, date, title = (_text(c) for c in cells[1:4])
        kind = "amendment" if re.search(r"\bamendment\b", title, re.I) else "regulation"
        items.append(Item("rerc", title, RERC_REGS_URL, _date(date), None, doc_type=kind,
                          key=f"rerc-reg:{notification}:{date}", fetch=_rerc_regs_fetch(target.group(1))))
    return fields, items


def _rerc_regs_fetch(target: str):
    def fetch(client):
        fields, _ = parse_rerc_regulations(client.get(RERC_REGS_URL).decode("utf-8", "ignore"))
        return client.post(RERC_REGS_URL, {**fields, "__EVENTTARGET": target, "__EVENTARGUMENT": ""})
    return fetch


def rerc_regulations(client) -> list[Item]:
    _, items = parse_rerc_regulations(client.get(RERC_REGS_URL).decode("utf-8", "ignore"))
    return items


# --- MERC -------------------------------------------------------------------------------------
MERC_URL = "https://merc.gov.in/wp-admin/admin-ajax.php?action=getpostsfororderdatatables"


def parse_merc(raw: str) -> list[Item]:
    data = json.loads(raw)
    rows = data.get("data", data) if isinstance(data, dict) else data
    items = []
    for r in rows:
        raw_att = r.get("attachment") or []
        raw_att = raw_att if isinstance(raw_att, list) else [raw_att]
        atts = [a if isinstance(a, dict) else {"name": "", "url": str(a)} for a in raw_att]
        pdfs = [a for a in atts if str(a.get("url", "")).lower().endswith(".pdf")]
        if not pdfs:
            continue
        pdf = next((a for a in pdfs if "order" in a.get("name", "").lower()), pdfs[0])
        ts = str(r.get("timestamp", ""))
        date = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}" if re.fullmatch(r"\d{8}", ts) else _date(r.get("order_date", ""))
        case = (r.get("case_no") or "").strip()
        items.append(Item("merc", _text(r.get("order_desc", ""))[:300], pdf["url"], date,
                          f"Case No. {case}" if case else None))
    return items


def merc(client) -> list[Item]:
    return parse_merc(client.get(MERC_URL).decode("utf-8", "ignore"))


# --- GERC -------------------------------------------------------------------------------------
GERC_PAGES = ["https://gercin.org/orders/orders_petition/judgement_orders",
              "https://gercin.org/orders/orders_renewable_energy"]


def parse_gerc(page: str) -> list[Item]:
    items = []
    for row in re.findall(r"<tr>(.*?)</tr>", page, re.S):
        cell = dict((label, _text(v)) for label, v in re.findall(r'data-label="([^"]+)"[^>]*>(.*?)</td>', row, re.S))
        link = re.search(r'href="(https://gercin\.org/viewdocument/[^"]+)"', row)
        if not link or "Order Date" not in cell:
            continue
        petition = cell.get("Petition No", "")
        party = " v. ".join(x for x in (cell.get("Petitioner"), cell.get("Respondent")) if x)
        subject = cell.get("Download Matter", "")
        items.append(Item("gerc", f"{party}: {subject}" if party else subject, link.group(1), _date(cell["Order Date"]),
                          _case(petition)))
    return items


def _case(petition: str) -> str | None:
    """'2695/2026' -> 'Petition No. 2695/2026'; 'IA No. 85/2026 in Petition No. 2749/2026' stays as is."""
    if not petition:
        return None
    return petition if re.match(r"[A-Za-z]", petition) else f"Petition No. {petition}"


def gerc(client, max_pages: int = 5) -> list[Item]:
    items = []
    for base in GERC_PAGES:
        for page in range(1, max_pages + 1):
            got = parse_gerc(client.get(f"{base}?page={page}").decode("utf-8", "ignore"))
            items += got
            if not got:
                break
    return items


# --- KERC -------------------------------------------------------------------------------------
KERC_PAGES = ["https://kerc.karnataka.gov.in/42/miscellaneous-orders/en",
              "https://kerc.karnataka.gov.in/73/generic-tariff-orders/en",
              "https://kerc.karnataka.gov.in/96/tariff-order/en"]


def parse_kerc(page: str) -> list[Item]:
    items = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        cells = _cells(row)
        link = re.search(r'href="([^"]+\.pdf)\s*"', row, re.I)
        if len(cells) < 3 or not link:
            continue
        title = _text(cells[-1])
        date = _date(" ".join(_text(c) for c in cells[:-1])) or _date(title)
        case = re.search(r"\b((?:OP|RP|IA|Petition)\s*(?:No\.?)?\s*\d+\s*(?:of|/)\s*\d{4})", title, re.I)
        items.append(Item("kerc", title, link.group(1).strip(), date, case.group(1) if case else None))
    return items


def kerc(client) -> list[Item]:
    items = []
    for url in KERC_PAGES:
        items += parse_kerc(client.get(url).decode("utf-8", "ignore"))
    return items


# --- Draft regulations and consultations --------------------------------------------------------
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}


def _any_date(s: str) -> str | None:
    """'02.11.2026', '27th November, 2026' or '27 Nov 2026' -> ISO date."""
    d = _date(s)
    if d:
        return d
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})", s or "")
    if m:
        month = next((n for name, n in MONTHS.items() if name.startswith(m.group(2).lower()[:3])), None)
        if month:
            return f"{int(m.group(3)):04d}-{month:02d}-{int(m.group(1)):02d}"
    return None


CERC_DRAFTS_URL = "https://cercind.gov.in/Draft_reg.html"


def parse_cerc_drafts(page: str, base: str = CERC_DRAFTS_URL) -> list[Item]:
    """One row per draft: title, then numbered links (public notices, draft, memorandum, hearing).

    The main document is the newest draft text ('Supplementary Draft Notification' before 'Draft
    Amendment'); the comment deadline is the latest 'Last date' given; the hearing date is read
    from 'Public Hearing will be held on ...'."""
    items = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        cells = _cells(row)
        if len(cells) < 2 or not re.match(r"\s*\d+\.\s*$", _text(cells[0])):
            continue
        body = cells[1]
        title = _text(re.split(r"<br\s*/?>|<a\s", body, maxsplit=1, flags=re.I)[0]).rstrip(" .-")
        title = re.sub(r"\s*\(Last date[^)]*\)\s*$", "", title, flags=re.I).strip(" .-")
        links = [(urllib.parse.urljoin(base, h.strip()), re.sub(r"^\d+\.\s*", "", _text(t)))
                 for h, t in re.findall(r'<a\s+href="([^"]+)"[^>]*>(.*?)</a>', body, re.S | re.I)]
        pdfs = [(u, t) for u, t in links if u.lower().endswith(".pdf")]
        if not pdfs:
            continue
        main = next((p for p in pdfs if re.search(r"draft (amendment|notification|regulation)", p[1], re.I)), None) \
            or next((p for p in pdfs if re.search(r"\b(order|draft)\b", p[1], re.I)), pdfs[0])
        text = _text(body)
        deadlines = [d for d in (_any_date(m) for m in re.findall(
            r"Last date[^:)]*?[:\-–]+\s*([^)]{6,30})", text, re.I)) if d]
        hearing = re.search(r"Public Hearing will be held on\s+([\d./-]{8,10})", text, re.I)
        kind_title = title if title.lower().startswith("draft") else f"Proposal: {title}"
        items.append(Item(
            "cerc", kind_title[:300], main[0], None, None, doc_type="draft",
            key=f"cerc-draft:{main[0]}",
            extra={"comment_deadline": max(deadlines) if deadlines else None,
                   "hearing_date": _date(hearing.group(1)) if hearing else None,
                   "related": [{"label": t, "url": u} for u, t in pdfs if u != main[0]][:8]}))
    return items


def cerc_drafts(client) -> list[Item]:
    return parse_cerc_drafts(client.get(CERC_DRAFTS_URL).decode("utf-8", "ignore"))


GERC_DRAFTS_URL = "https://gercin.org/regulations/draft_regulations"


def parse_gerc_drafts(page: str) -> list[Item]:
    """Rows of draft regulations; an 'Explanatory Memorandum' or 'Consultation Paper' row belongs
    to the draft above it. GERC's listing gives no comment deadline."""
    items: list[Item] = []
    for row in re.findall(r"<tr>(.*?)</tr>", page, re.S):
        cell = dict((label, _text(v)) for label, v in re.findall(r'data-label="([^"]+)"[^>]*>(.*?)</td>', row, re.S))
        link = re.search(r'href="(https://gercin\.org/viewdocument/[^"]+)"', row)
        title = cell.get("Regulations", "")
        if not link or not title:
            continue
        if re.match(r"(explanatory memorandum|consultation paper)", title, re.I) and items:
            items[-1].extra["related"].append({"label": title, "url": link.group(1)})
            continue
        if not re.search(r"\bdraft\b", title, re.I):
            continue  # final regulations also appear here briefly; the regulations adapter covers them
        items.append(Item("gerc", title[:300], link.group(1), _date(cell.get("Date", "")), None, doc_type="draft",
                          key=f"gerc-draft:{link.group(1)}", extra={"related": []}))
    return items


def gerc_drafts(client) -> list[Item]:
    return parse_gerc_drafts(client.get(GERC_DRAFTS_URL).decode("utf-8", "ignore"))


KERC_DRAFTS_URL = "https://kerc.karnataka.gov.in/28/draft-regulations/en"


def parse_kerc_drafts(page: str) -> list[Item]:
    """Columns: Sl No., Date of issue, Description (linked), Last date for suggestions."""
    items = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        cells = _cells(row)
        link = re.search(r'href="([^"]+\.pdf)\s*"', row, re.I)
        if len(cells) < 3 or not link or not _date(_text(cells[1])):
            continue
        title = re.sub(r"^Drat\b", "Draft", _text(cells[2]))
        deadline = _date(_text(cells[3])) if len(cells) > 3 else None
        items.append(Item("kerc", title[:300], link.group(1).strip(), _date(_text(cells[1])), None,
                          doc_type="draft", key=f"kerc-draft:{link.group(1).strip()}",
                          extra={"comment_deadline": deadline}))
    return items


def kerc_drafts(client) -> list[Item]:
    return parse_kerc_drafts(client.get(KERC_DRAFTS_URL).decode("utf-8", "ignore"))
