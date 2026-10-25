import pytest

from trainer.config import EQUITY_TOLERANCE
from trainer.graders.equity import (
    BUCKETS,
    bucket_for,
    correct_decision,
    grade_bucket,
    grade_decision,
    grade_equity_answer,
    required_equity,
)


@pytest.mark.parametrize(
    "pot,bet,expected",
    [
        (100, 100, 1 / 3),   # pot-sized bet: need 33.3%
        (100, 50, 0.25),     # half pot: need 25%
        (100, 25, 25 / 150),  # quarter pot: 16.7%
        (100, 200, 0.4),     # 2x pot overbet: 40%
        (10, 5, 0.25),
    ],
)
def test_required_equity_known_values(pot, bet, expected):
    assert required_equity(pot, bet) == pytest.approx(expected)


def test_required_equity_explicit_call():
    # Hero already put 10 in this round, villain raised to 30: call 20 into pot 100 + 30 (+ hero's 10).
    assert required_equity(110, 30, call=20) == pytest.approx(20 / 160)


def test_required_equity_rejects_nonsense():
    for args in [(100, 0), (-1, 10), (100, 10, 0)]:
        with pytest.raises(ValueError):
            required_equity(*args)


def test_tolerance_config():
    assert EQUITY_TOLERANCE == 0.02


@pytest.mark.parametrize(
    "equity,bucket",
    [(0.0, "lt20"), (0.1999, "lt20"), (0.2, "20-30"), (0.2999, "20-30"), (0.3, "30-40"),
     (0.45, "40-50"), (0.5, "50-60"), (0.5999, "50-60"), (0.6, "60+"), (1.0, "60+")],
)
def test_bucket_for(equity, bucket):
    assert bucket_for(equity) == bucket


def test_buckets_cover_zero_to_one_without_gaps():
    assert BUCKETS[0][2] == 0.0
    for a, b in zip(BUCKETS, BUCKETS[1:]):
        assert a[3] == b[2]
    assert [b[1] for b in BUCKETS] == ["Under 20%", "20-30%", "30-40%", "40-50%", "50-60%", "60% +"]


@pytest.mark.parametrize(
    "equity,chosen,grade",
    [
        (0.35, "30-40", "correct"),
        (0.35, "40-50", "wrong"),
        (0.41, "30-40", "acceptable"),   # 1 point past the edge
        (0.42, "30-40", "acceptable"),   # exactly 2 points past still counts
        (0.425, "30-40", "wrong"),
        (0.285, "30-40", "acceptable"),
        (0.279, "30-40", "wrong"),
        (0.95, "60+", "correct"),
        (0.59, "60+", "acceptable"),
        (0.19, "20-30", "acceptable"),
    ],
)
def test_grade_bucket(equity, chosen, grade):
    assert grade_bucket(equity, chosen) == grade


def test_grade_bucket_unknown():
    with pytest.raises(ValueError):
        grade_bucket(0.3, "30-35")


@pytest.mark.parametrize(
    "equity,required,chosen,grade",
    [
        (0.40, 0.25, "call", "correct"),
        (0.40, 0.25, "fold", "wrong"),
        (0.10, 0.25, "fold", "correct"),
        (0.10, 0.25, "call", "wrong"),
        (0.25, 0.25, "call", "correct"),   # meets it exactly: call
        (0.25, 0.25, "fold", "acceptable"),
        (0.26, 0.25, "fold", "acceptable"),  # within 2 points
        (0.24, 0.25, "call", "acceptable"),
        (0.2999, 0.3333, "call", "wrong"),
    ],
)
def test_grade_decision(equity, required, chosen, grade):
    assert grade_decision(equity, required, chosen) == grade


def test_correct_decision_meets_or_beats():
    assert correct_decision(1 / 3, 1 / 3) == "call"
    assert correct_decision(0.3333, 1 / 3) == "fold"


def test_grade_equity_answer_explanations():
    g = grade_equity_answer(equity=0.42, std_error=0.01, iterations=2500,
                            pot=100, bet=50, bucket="40-50", decision="call")
    assert g.bucket_grade == "correct" and g.decision_grade == "correct"
    assert g.required == pytest.approx(0.25)
    assert g.best_decision == "call"
    assert g.decision_explanation == (
        "To call 50 you need 50 / (100 + 50 + 50) = 25.0% equity. You have 42.0%, so call is right."
    )
    assert g.bucket_explanation == "Your equity is 42.0% (40-50%)."

    g = grade_equity_answer(equity=0.335, std_error=0.01, iterations=2500,
                            pot=10, bet=10, bucket="20-30", decision="fold")
    assert g.best_decision == "call" and g.decision_grade == "acceptable"
    assert "either answer" in g.decision_explanation
    assert g.bucket_grade == "wrong"
