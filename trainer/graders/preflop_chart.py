"""Grades a preflop decision by looking it up in a chart.

No strategy is decided here: the chart says how often each action is taken,
and the grade depends only on how often the chart takes the action the user
chose (thresholds in ``trainer.config.GRADE_THRESHOLDS``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from trainer.charts.loader import Chart
from trainer.config import GRADE_THRESHOLDS

CORRECT = "correct"
ACCEPTABLE = "acceptable"
WRONG = "wrong"

_RAISE_NAMES = {"rfi": "Raise", "vs_open": "3-bet", "vs_3bet": "4-bet"}
_RAISE_VERBS = {"rfi": "raises", "vs_open": "3-bets", "vs_3bet": "4-bets"}


def _raise_size(action: str) -> str | None:
    if action.startswith("raise_"):
        size = action[len("raise_"):]
        try:
            float(size)
        except ValueError:
            return None
        return size
    return None


def action_label(action: str, spot_type: str) -> str:
    """Button text for an action id, e.g. 'raise_2.5' in an rfi spot -> 'Raise to 2.5bb'."""
    if action == "fold":
        return "Fold"
    if action == "call":
        return "Call"
    if action == "allin":
        return "All-in"
    size = _raise_size(action)
    if size is not None:
        return f"{_RAISE_NAMES.get(spot_type, 'Raise')} to {size}bb"
    return action


def _action_verb(action: str, spot_type: str) -> str:
    if action == "fold":
        return "folds"
    if action == "call":
        return "calls"
    if action == "allin":
        return "goes all-in"
    size = _raise_size(action)
    if size is not None:
        return f"{_RAISE_VERBS.get(spot_type, 'raises')} to {size}bb"
    return f"plays {action}"


def format_pct(freq: float) -> str:
    pct = freq * 100
    if abs(pct - round(pct)) < 0.05:
        return f"{round(pct)}%"
    return f"{pct:.1f}%"


def grade_frequency(freq: float, thresholds: dict[str, float] | None = None) -> str:
    """'correct' / 'acceptable' / 'wrong' for the chart frequency of the chosen action."""
    t = GRADE_THRESHOLDS if thresholds is None else thresholds
    if not (0 <= t["acceptable"] <= t["correct"] <= 1):
        raise ValueError(f"Bad grade thresholds: {t}")
    if freq >= t["correct"]:
        return CORRECT
    if freq >= t["acceptable"]:
        return ACCEPTABLE
    return WRONG


@dataclass(frozen=True)
class GradeResult:
    grade: str
    chosen_action: str
    chosen_frequency: float
    frequencies: dict[str, float]  # every chart action, in chart order
    best_actions: tuple[str, ...]  # highest-frequency action(s)
    explanation: str
    hand_class: str
    chart_id: str
    source_name: str
    is_sample: bool
    labels: dict[str, str] = field(default_factory=dict)


def explain(chart: Chart, hand_class: str) -> str:
    """One sentence built from the chart data, e.g.
    'CO raises to 2.5bb with A5s 60% of the time and folds 40% of the time in this chart.'"""
    freqs = chart.frequencies(hand_class)
    played = sorted(((f, a) for a, f in freqs.items() if f > 0), key=lambda x: -x[0])
    who = chart.hero_pos
    if len(played) == 1:
        return f"{who} always {_action_verb(played[0][1], chart.spot_type)} with {hand_class} in this chart."
    parts = [f"{_action_verb(a, chart.spot_type)} {format_pct(f)} of the time" for f, a in played]
    joined = ", ".join(parts[:-1]) + " and " + parts[-1]
    return f"With {hand_class}, {who} {joined} in this chart."


def grade(chart: Chart, hand_class: str, chosen_action: str,
          thresholds: dict[str, float] | None = None) -> GradeResult:
    if chosen_action not in chart.actions:
        raise ValueError(f"{chosen_action!r} is not an action in chart {chart.id} {list(chart.actions)}")
    freqs = chart.frequencies(hand_class)
    chosen = freqs[chosen_action]
    top = max(freqs.values())
    best = tuple(a for a, f in freqs.items() if math.isclose(f, top, abs_tol=1e-9))
    return GradeResult(
        grade=grade_frequency(chosen, thresholds),
        chosen_action=chosen_action,
        chosen_frequency=chosen,
        frequencies=freqs,
        best_actions=best,
        explanation=explain(chart, hand_class),
        hand_class=hand_class,
        chart_id=chart.id,
        source_name=chart.source.get("name", ""),
        is_sample=chart.is_sample,
        labels={a: action_label(a, chart.spot_type) for a in chart.actions},
    )
