import pytest

from trainer.charts.loader import chart_from_dict
from trainer.config import GRADE_THRESHOLDS
from trainer.graders.preflop_chart import (
    ACCEPTABLE,
    CORRECT,
    WRONG,
    action_label,
    format_pct,
    grade,
    grade_frequency,
)

CHART = chart_from_dict({
    "id": "t-rfi-CO",
    "game": "nlhe",
    "format": "cash",
    "table_size": 6,
    "stack_bb": 100,
    "spot": {"type": "rfi", "hero_pos": "CO", "villain_pos": None, "facing": None},
    "actions": ["fold", "raise_2.5"],
    "source": {"name": "Test source"},
    "hands": {
        "AA": {"raise_2.5": 1.0},
        "A5s": {"raise_2.5": 0.6, "fold": 0.4},
        "K9s": {"raise_2.5": 0.15, "fold": 0.85},
        "Q9s": {"raise_2.5": 0.14, "fold": 0.86},
        "J9s": {"raise_2.5": 0.5, "fold": 0.5},
        "72o": {"fold": 1.0},
    },
})

VS3 = chart_from_dict({
    "id": "t-vs3",
    "game": "nlhe",
    "format": "cash",
    "table_size": 6,
    "stack_bb": 100,
    "spot": {"type": "vs_3bet", "hero_pos": "CO", "villain_pos": "BTN",
             "facing": {"open_size_bb": 2.5, "threebet_size_bb": 8}},
    "actions": ["fold", "call", "raise_20"],
    "source": {"name": "Test source"},
    "hands": {"AQs": {"call": 0.5, "raise_20": 0.3, "fold": 0.2}},
})


def test_thresholds_are_the_brief_values():
    assert GRADE_THRESHOLDS == {"correct": 0.5, "acceptable": 0.15}


@pytest.mark.parametrize(
    "freq,expected",
    [
        (1.0, CORRECT),
        (0.5, CORRECT),     # 0.5 or higher is correct
        (0.4999, ACCEPTABLE),
        (0.15, ACCEPTABLE),  # 0.15 to 0.5 is acceptable
        (0.1499, WRONG),
        (0.0, WRONG),
    ],
)
def test_grade_frequency_boundaries(freq, expected):
    assert grade_frequency(freq) == expected


def test_custom_thresholds():
    t = {"correct": 0.7, "acceptable": 0.3}
    assert grade_frequency(0.6, t) == ACCEPTABLE
    assert grade_frequency(0.7, t) == CORRECT
    assert grade_frequency(0.29, t) == WRONG
    with pytest.raises(ValueError):
        grade_frequency(0.5, {"correct": 0.2, "acceptable": 0.5})


@pytest.mark.parametrize(
    "hand,action,expected,freq",
    [
        ("AA", "raise_2.5", CORRECT, 1.0),
        ("AA", "fold", WRONG, 0.0),
        ("A5s", "raise_2.5", CORRECT, 0.6),
        ("A5s", "fold", ACCEPTABLE, 0.4),
        ("J9s", "fold", CORRECT, 0.5),
        ("K9s", "raise_2.5", ACCEPTABLE, 0.15),
        ("Q9s", "raise_2.5", WRONG, 0.14),
        ("72o", "fold", CORRECT, 1.0),
        ("KK", "fold", CORRECT, 1.0),       # missing from chart -> fold
        ("KK", "raise_2.5", WRONG, 0.0),
    ],
)
def test_grade_from_chart(hand, action, expected, freq):
    r = grade(CHART, hand, action)
    assert r.grade == expected
    assert r.chosen_frequency == freq
    assert sum(r.frequencies.values()) == pytest.approx(1.0)


def test_best_actions():
    assert grade(CHART, "A5s", "fold").best_actions == ("raise_2.5",)
    assert grade(CHART, "J9s", "fold").best_actions == ("fold", "raise_2.5")


def test_unknown_action_rejected():
    with pytest.raises(ValueError):
        grade(CHART, "AA", "call")


def test_explanations():
    assert grade(CHART, "AA", "fold").explanation == "CO always raises to 2.5bb with AA in this chart."
    assert grade(CHART, "A5s", "fold").explanation == (
        "With A5s, CO raises to 2.5bb 60% of the time and folds 40% of the time in this chart."
    )
    assert grade(VS3, "AQs", "call").explanation == (
        "With AQs, CO calls 50% of the time, 4-bets to 20bb 30% of the time "
        "and folds 20% of the time in this chart."
    )


def test_result_metadata():
    r = grade(CHART, "AA", "raise_2.5")
    assert r.chart_id == "t-rfi-CO"
    assert r.source_name == "Test source"
    assert r.is_sample is False
    assert r.labels == {"fold": "Fold", "raise_2.5": "Raise to 2.5bb"}


def test_action_labels():
    assert action_label("raise_2.5", "rfi") == "Raise to 2.5bb"
    assert action_label("raise_8", "vs_open") == "3-bet to 8bb"
    assert action_label("raise_22", "vs_3bet") == "4-bet to 22bb"
    assert action_label("call", "vs_open") == "Call"
    assert action_label("allin", "vs_3bet") == "All-in"
    assert action_label("limp", "rfi") == "limp"
    assert action_label("raise_big", "rfi") == "raise_big"


def test_format_pct():
    assert format_pct(0.6) == "60%"
    assert format_pct(0.333) == "33.3%"
    assert format_pct(1.0) == "100%"
    assert format_pct(0.005) == "0.5%"
