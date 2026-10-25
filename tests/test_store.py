import sqlite3

import pytest

from trainer.progress.store import Attempt, AttemptStore


def make(**kw):
    base = dict(
        drill_type="preflop_chart", game="nlhe", format="cash",
        spot={"table_size": 6, "history": [{"pos": "UTG", "action": "fold"}]},
        hero_cards="AsKd", user_answer="fold", correct_answer=["raise_2.5"], grade="wrong",
        table_size=6, stack_bb=100, spot_type="rfi", hero_pos="CO", hand_class="AKo",
        frequencies={"fold": 0.0, "raise_2.5": 1.0}, chosen_frequency=0.0,
        response_time_ms=1834, chart_id="c1", chart_source="Test", is_sample=True,
    )
    base.update(kw)
    return Attempt(**base)


def test_record_and_read_back(tmp_path):
    store = AttemptStore(tmp_path / "sub" / "p.sqlite")
    rid = store.record(make())
    assert rid == 1
    [row] = store.recent()
    assert row["hero_cards"] == "AsKd"
    assert row["spot"]["history"][0]["pos"] == "UTG"
    assert row["frequencies"] == {"fold": 0.0, "raise_2.5": 1.0}
    assert row["correct_answer"] == ["raise_2.5"]
    assert row["is_sample"] is True
    assert row["response_time_ms"] == 1834
    assert row["villain_pos"] is None
    assert row["created_at"].endswith("+00:00")


def test_persists_across_instances(tmp_path):
    p = tmp_path / "p.sqlite"
    AttemptStore(p).record(make())
    AttemptStore(p).record(make(grade="correct", user_answer="raise_2.5"))
    store = AttemptStore(p)
    assert [r["grade"] for r in store.recent()] == ["correct", "wrong"]  # newest first
    with sqlite3.connect(p) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2


def test_summary(tmp_path):
    store = AttemptStore(tmp_path / "p.sqlite")
    assert store.summary() == {"total": 0, "correct": 0, "acceptable": 0, "wrong": 0}
    for g in ["correct", "correct", "acceptable", "wrong"]:
        store.record(make(grade=g))
    store.record(make(grade="correct", drill_type="other"))
    assert store.summary() == {"total": 5, "correct": 3, "acceptable": 1, "wrong": 1}
    assert store.summary("preflop_chart")["total"] == 4


def test_multiple_correct_answers(tmp_path):
    store = AttemptStore(tmp_path / "p.sqlite")
    store.record(make(correct_answer=["fold", "raise_2.5"]))
    assert store.recent()[0]["correct_answer"] == ["fold", "raise_2.5"]


def test_recent_limit(tmp_path):
    store = AttemptStore(tmp_path / "p.sqlite")
    for _ in range(5):
        store.record(make())
    assert len(store.recent(3)) == 3


def test_record_without_optional_fields(tmp_path):
    store = AttemptStore(tmp_path / "p.sqlite")
    store.record(Attempt(drill_type="equity_estimate", game="plo", format="cash", spot={"board": ["As"]},
                         hero_cards="AsKdQcJc", user_answer="30-40", correct_answer=["40-50"], grade="wrong"))
    [row] = store.recent()
    assert row["frequencies"] is None and row["hand_class"] is None and row["table_size"] is None


def test_breakdown_and_count(tmp_path):
    store = AttemptStore(tmp_path / "p.sqlite")
    for pos, grade in [("CO", "correct"), ("CO", "wrong"), ("BTN", "acceptable"), ("BTN", "correct"), ("BTN", "correct")]:
        store.record(make(hero_pos=pos, grade=grade))
    rows = store.breakdown("hero_pos", "preflop_chart")
    assert rows[0] == {"key": "BTN", "total": 3, "correct": 2, "acceptable": 1, "wrong": 0, "accuracy": 0.6667, "score": 0.8333}
    assert rows[1]["key"] == "CO" and rows[1]["score"] == 0.5
    assert store.count("preflop_chart") == 5 and store.count("other") == 0
    assert store.recent_grades("preflop_chart", 2) == ["correct", "correct"]
    with pytest.raises(ValueError):
        store.breakdown("grade; DROP TABLE attempts")


def test_review_scheduling(tmp_path):
    store = AttemptStore(tmp_path / "p.sqlite")
    d = "preflop_chart"
    store.schedule_review(d, "c1|AKo", "correct")  # right first time: not tracked
    assert store.review_count(d) == {"total": 0, "due": 0}
    store.schedule_review(d, "c1|72o", "wrong")  # due after 5 more attempts
    assert store.due_reviews(d) == []
    for _ in range(5):
        store.record(make())
    assert store.due_reviews(d) == ["c1|72o"]
    store.schedule_review(d, "c1|72o", "correct")  # interval doubles to at least 25
    assert store.due_reviews(d) == []
    for _ in range(25):
        store.record(make())
    assert store.due_reviews(d) == ["c1|72o"]
    # Keep answering right: it eventually graduates and disappears.
    for _ in range(5):
        store.schedule_review(d, "c1|72o", "correct")
    assert store.review_count(d)["total"] == 0


def test_review_lapses_order(tmp_path):
    store = AttemptStore(tmp_path / "p.sqlite")
    d = "preflop_chart"
    store.schedule_review(d, "a", "wrong")
    store.schedule_review(d, "b", "wrong")
    store.schedule_review(d, "b", "wrong")
    for _ in range(5):
        store.record(make())
    assert store.due_reviews(d) == ["b", "a"]  # more lapses first


def test_schema_upgrade_from_v1(tmp_path):
    """A database made by the phase-1 code must still open and gain the reviews table."""
    p = tmp_path / "p.sqlite"
    with sqlite3.connect(p) as db:
        db.execute("CREATE TABLE attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL, "
                   "drill_type TEXT NOT NULL, game TEXT NOT NULL, format TEXT NOT NULL, table_size INTEGER, "
                   "stack_bb REAL, spot_type TEXT, hero_pos TEXT, villain_pos TEXT, spot_json TEXT NOT NULL, "
                   "hero_cards TEXT NOT NULL, hand_class TEXT, user_answer TEXT NOT NULL, correct_answer TEXT NOT NULL, "
                   "frequencies_json TEXT, chosen_frequency REAL, grade TEXT NOT NULL, response_time_ms INTEGER, "
                   "chart_id TEXT, chart_source TEXT, is_sample INTEGER NOT NULL DEFAULT 0)")
        db.execute("PRAGMA user_version = 1")
    store = AttemptStore(p)
    store.record(make())
    store.schedule_review("preflop_chart", "x", "wrong")
    assert store.review_count("preflop_chart")["total"] == 1
