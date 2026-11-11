"""Generate clearly marked SAMPLE PDFs for tests and demos. Not real orders or regulations."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pymupdf

BANNER = "SAMPLE - NOT A REAL ORDER OR REGULATION - FOR SOFTWARE TESTING ONLY"

REGULATION = [
    "SAMPLE STATE ELECTRICITY REGULATORY COMMISSION",
    "Sample Green Energy Open Access Regulations, 2026",
    "1. Short title and commencement.- (1) These regulations may be called the Sample Green Energy "
    "Open Access Regulations, 2026. (2) They shall come into force on the date of notification.",
    "2. Definitions.- (1) In these regulations, unless the context otherwise requires, 'banking' means "
    "the surplus green energy injected into the grid and credited with the distribution licensee.",
    "8. Banking.- (1) Banking of green energy shall be permitted on a monthly basis.",
    "(2) Banking charges shall be eight percent of the energy banked, payable in kind.",
    "(3) Energy banked during peak hours may be drawn during off-peak hours, but not the reverse.",
    "9. Cross-subsidy surcharge.- (1) Cross-subsidy surcharge shall not exceed twenty percent of the "
    "average cost of supply.",
    "(2) No cross-subsidy surcharge shall apply to green energy supplied to a captive user.",
]

ORDER = [
    "SAMPLE STATE ELECTRICITY REGULATORY COMMISSION",
    "Petition No. SAMPLE-12 of 2026",
    "In the matter of: Petition seeking relaxation of the peak-hour banking restriction.",
    "Sample Textiles Ltd. ... Petitioner",
    "Sample Distribution Company Ltd. ... Respondent",
    "ORDER",
    "1. The petitioner, a green energy open access consumer, seeks to draw energy banked during "
    "off-peak hours in peak hours, contrary to Regulation 8(3) of the Sample Green Energy Open Access "
    "Regulations, 2026.",
    "2. The respondent submits that Regulation 8(3) is clear and admits no exception.",
    "3. The Commission notes its power to relax under Regulation 20 of the Sample Conduct of "
    "Business Regulations and Section 86 of the Electricity Act, 2003.",
    "4. The Commission finds that banking charges under Regulation 8(2) compensate the licensee for "
    "the cost of banking, and the restriction in Regulation 8(3) protects peak supply.",
    "5. The petition is dismissed. Regulation 8(3) shall apply as written.",
]


def make_pdf(lines: list[str], path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    y = 50
    for line in [BANNER] + lines + [BANNER]:
        rect = pymupdf.Rect(50, y, 545, y + 120)
        rc = page.insert_textbox(rect, line, fontsize=10, fontname="helv")
        used = 120 - rc if rc >= 0 else 120
        y += max(used, 14) + 10
        if y > 760:
            page = doc.new_page()
            y = 50
    doc.save(path)


def write(inbox: Path) -> list[Path]:
    out = []
    specs = [
        ("rerc", "2026-11-02", "sample-goa-regulation", "regulation", REGULATION,
         {"title": "Sample Green Energy Open Access Regulations, 2026 (SAMPLE)", "doc_date": "2026-01-15"}),
        ("rerc", "2026-11-09", "sample-banking-order", "order", ORDER,
         {"title": "SAMPLE petition on peak-hour banking", "doc_date": "2026-11-05",
          "case_number": "SAMPLE-12 of 2026"}),
    ]
    for comm, day, name, dtype, lines, extra in specs:
        folder = inbox / comm / day
        folder.mkdir(parents=True, exist_ok=True)
        pdf = folder / f"{name}.pdf"
        make_pdf(lines, pdf)
        sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
        meta = {"commission": comm, "doc_type": dtype,
                "source_url": f"https://example.invalid/sample/{name}.pdf",
                "downloaded_at": f"{day}T09:00:00+05:30", "sha256": sha, **extra}
        pdf.with_suffix(".json").write_text(json.dumps(meta, indent=2))
        out.append(pdf)
    return out


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "fixtures" / "inbox"
    for p in write(target):
        print(p)
