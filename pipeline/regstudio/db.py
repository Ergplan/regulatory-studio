"""SQLite access for the working database."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Iterator

from . import config

ACT_SECTIONS = [
    # Electricity Act, 2003: sections most cited in open access and tariff matters.
    ("ea2003/s9", "9", "Captive generation"),
    ("ea2003/s14", "14", "Grant of licence"),
    ("ea2003/s38", "38", "Central Transmission Utility and functions"),
    ("ea2003/s39", "39", "State Transmission Utility and functions"),
    ("ea2003/s40", "40", "Duties of transmission licensees"),
    ("ea2003/s42", "42", "Duties of distribution licensees and open access"),
    ("ea2003/s43", "43", "Duty to supply on request"),
    ("ea2003/s49", "49", "Agreement with respect to supply or purchase of electricity"),
    ("ea2003/s61", "61", "Tariff regulations"),
    ("ea2003/s62", "62", "Determination of tariff"),
    ("ea2003/s63", "63", "Determination of tariff by bidding process"),
    ("ea2003/s64", "64", "Procedure for tariff order"),
    ("ea2003/s66", "66", "Development of market"),
    ("ea2003/s79", "79", "Functions of Central Commission"),
    ("ea2003/s86", "86", "Functions of State Commission"),
    ("ea2003/s94", "94", "Powers of Appropriate Commission"),
    ("ea2003/s111", "111", "Appeal to Appellate Tribunal"),
    ("ea2003/s121", "121", "Power of Appellate Tribunal"),
    ("ea2003/s125", "125", "Appeal to Supreme Court"),
    ("ea2003/s142", "142", "Punishment for non-compliance of directions"),
    ("ea2003/s178", "178", "Powers of Central Commission to make regulations"),
    ("ea2003/s181", "181", "Powers of State Commissions to make regulations"),
]


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def session(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init(path: Path | None = None) -> None:
    sql = resources.files("regstudio").joinpath("schema.sql").read_text()
    with session(path) as conn:
        conn.executescript(sql)
        conn.executemany(
            "INSERT OR IGNORE INTO act_sections(id, act, number, title) VALUES (?, 'Electricity Act, 2003', ?, ?)",
            ACT_SECTIONS,
        )
        mig_dir = resources.files("regstudio").joinpath("migrations")
        conn.execute("CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY)")
        done = {r[0] for r in conn.execute("SELECT name FROM migrations")}
        for f in sorted(p for p in mig_dir.iterdir() if p.name.endswith(".sql")):
            if f.name not in done:
                conn.executescript(f.read_text())
                conn.execute("INSERT INTO migrations(name) VALUES (?)", (f.name,))


def set_stage(conn: sqlite3.Connection, doc_id: str, stage: str, error: str | None = None) -> None:
    conn.execute(
        "UPDATE documents SET stage = ?, error = ?, updated_at = datetime('now') WHERE id = ?",
        (stage, error, doc_id),
    )


def audit(conn: sqlite3.Connection, actor: str, action: str, obj: str, detail: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO audit(actor, action, object, detail) VALUES (?, ?, ?, ?)",
        (actor, action, obj, json.dumps(detail) if detail else None),
    )


def start_run(conn: sqlite3.Connection, stage: str) -> int:
    return conn.execute("INSERT INTO runs(stage) VALUES (?)", (stage,)).lastrowid


def finish_run(conn: sqlite3.Connection, run_id: int, ok: int, failed: int, note: str = "") -> None:
    conn.execute(
        "UPDATE runs SET finished = datetime('now'), ok = ?, failed = ?, note = ? WHERE id = ?",
        (ok, failed, note, run_id),
    )
