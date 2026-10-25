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

SCHEMA_VERSION = 2

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

-- Spaced repetition: one row per (drill, item) that has been missed or is being re-checked.
-- Intervals are counted in attempts of that drill type, not in days.
CREATE TABLE IF NOT EXISTS reviews (
    drill_type   TEXT    NOT NULL,
    item_key     TEXT    NOT NULL,   -- e.g. '<chart id>|<hand class>'
    interval     INTEGER NOT NULL,
    due_at       INTEGER NOT NULL,   -- attempt count of this drill type at which it's due
    lapses       INTEGER NOT NULL DEFAULT 0,
    last_grade   TEXT    NOT NULL,
    PRIMARY KEY (drill_type, item_key)
);
"""

# Review intervals (in attempts): after a miss the item comes back soon; after a
# correct answer the gap doubles; once it's long enough the item graduates.
REVIEW_AFTER_WRONG = 5
REVIEW_AFTER_ACCEPTABLE = 12
REVIEW_MIN_AFTER_CORRECT = 25
REVIEW_GRADUATE_AT = 200

GROUPABLE = ("drill_type", "game", "format", "table_size", "spot_type", "hero_pos", "hand_class", "chart_id")


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
        freqs = row.pop("frequencies")
        row["frequencies_json"] = json.dumps(freqs) if freqs is not None else None
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

    def count(self, drill_type: str) -> int:
        with self._connect() as db:
            return db.execute("SELECT COUNT(*) FROM attempts WHERE drill_type = ?", (drill_type,)).fetchone()[0]

    def breakdown(self, group: str, drill_type: str | None = None, since_id: int = 0) -> list[dict]:
        """Accuracy per value of `group` (a column name), most attempts first.

        `score` counts an acceptable answer as half right; `accuracy` is correct only.
        """
        if group not in GROUPABLE:
            raise ValueError(f"Can't group by {group!r}")
        where = ["id > ?"]
        args: list = [since_id]
        if drill_type:
            where.append("drill_type = ?")
            args.append(drill_type)
        q = (f"SELECT {group} AS key, COUNT(*) AS n, "
             f"SUM(grade = 'correct') AS c, SUM(grade = 'acceptable') AS a, SUM(grade = 'wrong') AS w "
             f"FROM attempts WHERE {' AND '.join(where)} AND {group} IS NOT NULL "
             f"GROUP BY {group} ORDER BY n DESC, key")
        with self._connect() as db:
            rows = db.execute(q, args).fetchall()
        return [_stats_row(r["key"], r["n"], r["c"], r["a"], r["w"]) for r in rows]

    def recent_grades(self, drill_type: str, limit: int = 50) -> list[str]:
        """Grades of the last `limit` attempts, newest first (for a trend line)."""
        with self._connect() as db:
            rows = db.execute("SELECT grade FROM attempts WHERE drill_type = ? ORDER BY id DESC LIMIT ?",
                              (drill_type, limit)).fetchall()
        return [r["grade"] for r in rows]

    # ---- spaced repetition ----

    def schedule_review(self, drill_type: str, item_key: str, grade: str) -> None:
        """Update when this item should come back, based on the grade just earned."""
        now = self.count(drill_type)
        with self._connect() as db:
            row = db.execute("SELECT interval, lapses FROM reviews WHERE drill_type = ? AND item_key = ?",
                             (drill_type, item_key)).fetchone()
            lapses = row["lapses"] if row else 0
            if grade == "wrong":
                interval, lapses = REVIEW_AFTER_WRONG, lapses + 1
            elif grade == "acceptable":
                interval = REVIEW_AFTER_ACCEPTABLE
            else:
                if row is None:
                    return  # got it right first time: nothing to review
                interval = max(row["interval"] * 2, REVIEW_MIN_AFTER_CORRECT)
                if interval > REVIEW_GRADUATE_AT:
                    db.execute("DELETE FROM reviews WHERE drill_type = ? AND item_key = ?", (drill_type, item_key))
                    return
            db.execute(
                "INSERT INTO reviews (drill_type, item_key, interval, due_at, lapses, last_grade) "
                "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(drill_type, item_key) DO UPDATE SET "
                "interval = excluded.interval, due_at = excluded.due_at, lapses = excluded.lapses, "
                "last_grade = excluded.last_grade",
                (drill_type, item_key, interval, now + interval, lapses, grade),
            )

    def due_reviews(self, drill_type: str) -> list[str]:
        """Item keys that are due now, most overdue first."""
        now = self.count(drill_type)
        with self._connect() as db:
            rows = db.execute("SELECT item_key FROM reviews WHERE drill_type = ? AND due_at <= ? "
                              "ORDER BY due_at, lapses DESC", (drill_type, now)).fetchall()
        return [r["item_key"] for r in rows]

    def review_count(self, drill_type: str) -> dict:
        now = self.count(drill_type)
        with self._connect() as db:
            total = db.execute("SELECT COUNT(*) FROM reviews WHERE drill_type = ?", (drill_type,)).fetchone()[0]
            due = db.execute("SELECT COUNT(*) FROM reviews WHERE drill_type = ? AND due_at <= ?",
                             (drill_type, now)).fetchone()[0]
        return {"total": total, "due": due}

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


def _stats_row(key, n: int, c: int, a: int, w: int) -> dict:
    return {
        "key": key, "total": n, "correct": c, "acceptable": a, "wrong": w,
        "accuracy": round(c / n, 4) if n else None,
        "score": round((c + 0.5 * a) / n, 4) if n else None,
    }
