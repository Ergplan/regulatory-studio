"""Stage 2: PDF to paragraphs with page positions.

Each text block on a page becomes a paragraph with id 'p<page>.<n>'. Running headers and
footers that repeat on most pages are dropped. Pages with no text layer are flagged for OCR.
"""

from __future__ import annotations

import json
import re
import shutil
from collections import Counter

import pymupdf

from . import config, db

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
WS = re.compile(r"\s+")


def _norm(text: str) -> str:
    return WS.sub(" ", text).strip()


def _language(text: str) -> str:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "unknown"
    dev = sum(1 for c in letters if DEVANAGARI.match(c))
    return "hi" if dev / len(letters) > 0.3 else "en"


STARTS_NEW = re.compile(r"^(\(?[0-9ivxlc]{1,5}[.)]\s|\(?[a-z][.)]\s|\d+(\.\d+)+\s|[A-Z][A-Z .&,-]{6,}$|Page \d|Order in Petition|In the matter of|ORDER$)", re.I)


def _merge_lines(blocks: list) -> list:
    """Join line-level blocks into paragraphs. A block continues the previous one when the gap
    between them is no wider than this page's usual line gap, and it does not start with a
    number, letter label or heading. A block starting in lower case always continues."""
    gaps = sorted(b[1][1] - a[1][3] for a, b in zip(blocks, blocks[1:]) if 0 <= b[1][1] - a[1][3] < 30)
    usual = gaps[len(gaps) // 2] if gaps else 4.0
    out: list = []
    for text, bbox in blocks:
        if out:
            ptext, pbox = out[-1]
            gap = bbox[1] - pbox[3]
            lower = text[:1].islower()
            close = -2 <= gap <= usual * 1.35 + 1.5
            if len(ptext) < 4000 and (lower and gap < 30 or close and not STARTS_NEW.match(text)
                                      and not ptext.endswith(":")):
                out[-1] = (ptext + " " + text, [min(pbox[0], bbox[0]), pbox[1], max(pbox[2], bbox[2]), bbox[3]])
                continue
        out.append((text, bbox))
    return out


_LANGS: str | None = None


def _ocr_languages() -> str:
    """'eng+hin' when both are installed, else whichever is; '' when Tesseract is missing."""
    global _LANGS
    if _LANGS is None:
        _LANGS = ""
        if shutil.which("tesseract"):
            import subprocess
            out = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True).stdout.split()
            _LANGS = "+".join(l for l in ("eng", "hin") if l in out)
    return _LANGS


def _ocr_blocks(page) -> list:
    """OCR one page with Tesseract (English and Hindi) when it is installed; else no text."""
    langs = _ocr_languages()
    if not langs:
        return []
    try:
        tp = page.get_textpage_ocr(language=langs, dpi=300, full=True)
        return page.get_text("blocks", textpage=tp, sort=True)
    except Exception:
        return []


def extract_pdf(path) -> tuple[list[dict], int, list[int]]:
    """Return (paragraphs, page_count, pages_without_text)."""
    doc = pymupdf.open(path)
    pages: list[list[tuple[str, list[float]]]] = []
    empty: list[int] = []
    for pno, page in enumerate(doc, start=1):
        blocks = []
        raw = page.get_text("blocks", sort=True)
        if not any(_norm(b[4]) for b in raw if b[6] == 0):
            raw = _ocr_blocks(page)
            if raw:
                empty.append(pno)  # recorded as OCR'd so reviewers know to check it closely
        for b in raw:
            x0, y0, x1, y1, text, _bno, btype = b[:7]
            if btype != 0:
                continue
            t = _norm(text)
            if t:
                blocks.append((t, [round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)]))
        if not blocks and pno not in empty:
            empty.append(pno)
        pages.append(_merge_lines(blocks))
    page_count = len(doc)
    doc.close()

    # Drop lines that repeat on more than half the pages (headers, footers, page numbers).
    counts = Counter(re.sub(r"\d+", "#", t) for blocks in pages for t, _ in blocks)
    threshold = max(3, page_count // 2 + 1)
    repeated = {k for k, c in counts.items() if c >= threshold and len(k) < 120}

    paragraphs = []
    for pno, blocks in enumerate(pages, start=1):
        n = 0
        for text, bbox in blocks:
            if re.sub(r"\d+", "#", text) in repeated:
                continue
            if re.fullmatch(r"(page\s*)?\d+(\s*(of|/)\s*\d+)?", text, re.I):
                continue
            n += 1
            paragraphs.append({"pid": f"p{pno}.{n}", "page": pno, "idx": n, "text": text, "bbox": bbox})
    return paragraphs, page_count, empty


def run(limit: int | None = None) -> dict:
    config.ensure_dirs()
    done = failed = 0
    with db.session() as conn:
        run_id = db.start_run(conn, "extract")
        rows = conn.execute(
            "SELECT id, file_path FROM documents WHERE stage = 'new' ORDER BY created_at"
            + (f" LIMIT {int(limit)}" if limit else "")
        ).fetchall()
        for row in rows:
            try:
                paras, page_count, empty = extract_pdf(config.STORE / row["file_path"])
                if not paras:
                    conn.execute("UPDATE documents SET page_count = ?, ocr = 1 WHERE id = ?",
                                 (page_count, row["id"]))
                    db.set_stage(conn, row["id"], "error",
                                 "no text layer and OCR unavailable or empty: install Tesseract (brew install tesseract tesseract-lang)")
                    failed += 1
                    continue
                full = " ".join(p["text"] for p in paras)
                conn.execute("DELETE FROM paragraphs WHERE doc_id = ?", (row["id"],))
                conn.executemany(
                    "INSERT INTO paragraphs(doc_id, pid, page, idx, text, bbox) VALUES (?, ?, ?, ?, ?, ?)",
                    [(row["id"], p["pid"], p["page"], p["idx"], p["text"], json.dumps(p["bbox"])) for p in paras],
                )
                conn.execute(
                    "UPDATE documents SET page_count = ?, ocr = ?, language = ? WHERE id = ?",
                    (page_count, 1 if empty else 0, _language(full), row["id"]),
                )
                (config.TEXT / f"{row['id']}.json").write_text(
                    json.dumps({"doc_id": row["id"], "pages_without_text": empty, "paragraphs": paras},
                               ensure_ascii=False))
                db.set_stage(conn, row["id"], "extracted")
                done += 1
            except Exception as e:  # keep the batch going; the error is visible in status
                db.set_stage(conn, row["id"], "error", f"extract: {e}")
                failed += 1
        db.finish_run(conn, run_id, done, failed)
    return {"extracted": done, "failed": failed}
