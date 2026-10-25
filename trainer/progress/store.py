"""SQLite storage for drill attempts.

Uses Python's built-in sqlite3, no extra dependency. Each call opens its own
short connection, which keeps it safe to use from the web server's threads.
Stores everything phase 5 (leak tracking) will need.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attempts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at       TEXT    NOT NULL,   -- UTC, ISO 8601
    drill_type       TEXT    NOT NULL,   -- e.g. 'preflop_chart'
    game             TEXT    NOT NULL,
    format           TEXT    NOT NULL,
    table_size       INTEGER,
    stack_bb         REAL,
    spot_type        TEXT,
    hero_pos         TEXT,
    villain_pos      TEXT,
    spot_json        TEXT    NOT NULL,   -- every spot parameter, incl. sizes and action history
    hero_cards       TEXT    NOT NULL,   -- e.g. 'AsKd'
    hand_class       TEXT,               -- e.g. 'AKo'
    user_answer      TEXT    NOT NULL,
    correct_answer   TEXT    NOT NULL,   -- highest-frequency action(s), '|'-separated
    frequencies_json TEXT,               -- chart frequencies for this hand
    chosen_frequency REAL,
    grade            TEXT    NOT NULL,   -- correct / acceptable / wrong
    response_time_ms INTEGER,
    chart_id         TEXT,
    chart_source     TEXT,
    is_sample        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_attempts_created ON attempts(created_at);
CREATE INDEX IF NOT EXISTS idx_attempts_drill ON attempts(drill_type, spot_type, hero_pos);
"""


@dataclass
class Attempt:
    drill_type: str
    game: str
    format: str
    spot: dict
    hero_cards: str
    user_answer: str
    correct_answer: list[str]
    grade: str
    table_size: int | None = None
    stack_bb: float | None = None
    spot_type: str | None = None
    hero_pos: str | None = None
    villain_pos: str | None = None
    hand_class: str | None = None
    frequencies: dict[str, float] | None = None
    chosen_frequency: float | None = None
    response_time_ms: int | None = None
    chart_id: str | None = None
    chart_source: str | None = None
    is_sample: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


class AttemptStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(_SCHEMA)
            db.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            with db:  # commits on success, rolls back on error
                yield db
        finally:
            db.close()

    def record(self, a: Attempt) -> int:
        row = asdict(a)
        row["spot_json"] = json.dumps(row.pop("spot"))
        row["frequencies_json"] = json.dumps(row.pop("frequencies")) if a.frequencies is not None else None
        row["correct_answer"] = "|".join(a.correct_answer)
        row["is_sample"] = int(a.is_sample)
        cols = ", ".join(row)
        marks = ", ".join(f":{k}" for k in row)
        with self._connect() as db:
            cur = db.execute(f"INSERT INTO attempts ({cols}) VALUES ({marks})", row)
            return cur.lastrowid

    def recent(self, limit: int = 20) -> list[dict]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM attempts ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["spot"] = json.loads(d.pop("spot_json"))
            fj = d.pop("frequencies_json")
            d["frequencies"] = json.loads(fj) if fj else None
            d["correct_answer"] = d["correct_answer"].split("|") if d["correct_answer"] else []
            d["is_sample"] = bool(d["is_sample"])
            out.append(d)
        return out

    def summary(self, drill_type: str | None = None) -> dict:
        """Counts by grade, optionally for one drill type."""
        q = "SELECT grade, COUNT(*) AS n FROM attempts"
        args: tuple = ()
        if drill_type:
            q += " WHERE drill_type = ?"
            args = (drill_type,)
        q += " GROUP BY grade"
        with self._connect() as db:
            counts = {r["grade"]: r["n"] for r in db.execute(q, args)}
        total = sum(counts.values())
        return {
            "total": total,
            "correct": counts.get("correct", 0),
            "acceptable": counts.get("acceptable", 0),
            "wrong": counts.get("wrong", 0),
        }
