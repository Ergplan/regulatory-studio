"""Paths and settings. Relative to the repo root unless overridden by env vars."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("REGSTUDIO_ROOT", Path(__file__).resolve().parents[2]))
DATA = REPO_ROOT / "data"
INBOX = Path(os.environ.get("REGSTUDIO_INBOX", DATA / "inbox"))
STORE = Path(os.environ.get("REGSTUDIO_STORE", DATA / "store"))
SNAPSHOT = Path(os.environ.get("REGSTUDIO_SNAPSHOT", DATA / "snapshot"))
PREVIEW = Path(os.environ.get("REGSTUDIO_PREVIEW", DATA / "preview_snapshot"))
DB_PATH = STORE / "working.db"
FILES = STORE / "files"   # PDFs copied out of the inbox, named by hash
TEXT = STORE / "text"     # extracted paragraphs, one JSON per document

PIPELINE = REPO_ROOT / "pipeline"
PROMPTS = PIPELINE / "prompts"
SCHEMAS = PIPELINE / "schemas"

# "claude" runs the Claude Code CLI headless; "mock" uses rule-based stand-ins;
# "file" loads outputs prepared in an interactive Claude session from READER_OUTPUTS.
READER = os.environ.get("REGSTUDIO_READER", "claude")
READER_OUTPUTS = Path(os.environ.get("REGSTUDIO_READER_OUTPUTS", DATA / "reader_outputs"))
CLAUDE_BIN = os.environ.get("REGSTUDIO_CLAUDE_BIN", "claude")
CLAUDE_MODEL = os.environ.get("REGSTUDIO_CLAUDE_MODEL", "")
CLAUDE_TIMEOUT_S = int(os.environ.get("REGSTUDIO_CLAUDE_TIMEOUT", "900"))

COMMISSIONS = {
    "cerc": "Central Electricity Regulatory Commission",
    "aptel": "Appellate Tribunal for Electricity",
    "uperc": "Uttar Pradesh Electricity Regulatory Commission",
    "merc": "Maharashtra Electricity Regulatory Commission",
    "gerc": "Gujarat Electricity Regulatory Commission",
    "kerc": "Karnataka Electricity Regulatory Commission",
    "rerc": "Rajasthan Electricity Regulatory Commission",
    "tnerc": "Tamil Nadu Electricity Regulatory Commission",
}

TOPICS = {
    "open-access": "Open access",
    "banking": "Banking",
    "wheeling": "Wheeling charges",
    "css": "Cross-subsidy surcharge",
    "additional-surcharge": "Additional surcharge",
    "green-energy-oa": "Green energy open access",
    "retail-tariff": "Retail tariff",
    "generation-tariff": "Generation tariff",
    "transmission-tariff": "Transmission tariff",
    "arr-true-up": "ARR and true-up",
    "ppa-adoption": "Tariff adoption and PPA approval",
    "dsm": "Deviation settlement and scheduling",
    "power-market": "Power market",
    "connectivity-gna": "Connectivity and GNA",
    "ists-charges": "ISTS charges and waivers",
}

LINK_TYPES = {
    "applies": "Applies",
    "interprets": "Interprets",
    "relaxes": "Relaxes or deviates from",
    "follows": "Follows",
    "distinguishes": "Distinguishes",
    "appealed_in": "Appealed in",
    "upholds": "Upholds",
    "sets_aside": "Sets aside",
    "remands": "Remands",
    "amends": "Amends",
    "made_under": "Made under",
}

# Orders scoring below this are stored and listed, not summarised.
SIGNIFICANCE_THRESHOLD = int(os.environ.get("REGSTUDIO_SIGNIFICANCE", "3"))


def ensure_dirs() -> None:
    for p in (INBOX, STORE, SNAPSHOT, FILES, TEXT):
        p.mkdir(parents=True, exist_ok=True)
