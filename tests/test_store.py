import sqlite3

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
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1


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
