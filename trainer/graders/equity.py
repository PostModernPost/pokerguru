"""Grades the equity / pot odds drill. Everything is computed, no charts.

Direct odds only: implied odds (money won on later streets) are ignored.

    required equity to call = call / (pot + bet + call)

where `pot` is what was in the middle before villain bet. Calling is right when
hero's equity meets or beats that number.
"""

from __future__ import annotations

from dataclasses import dataclass

from trainer.config import EQUITY_TOLERANCE
from trainer.graders.preflop_chart import ACCEPTABLE, CORRECT, WRONG

# (id, label, low, high): low inclusive, high exclusive. Fractions of the pot.
BUCKETS: tuple[tuple[str, str, float, float], ...] = (
    ("lt20", "Under 20%", 0.0, 0.20),
    ("20-30", "20-30%", 0.20, 0.30),
    ("30-40", "30-40%", 0.30, 0.40),
    ("40-50", "40-50%", 0.40, 0.50),
    ("50-60", "50-60%", 0.50, 0.60),
    ("60+", "60% +", 0.60, 1.0000001),  # includes 100%
)
BUCKET_IDS = tuple(b[0] for b in BUCKETS)
_BY_ID = {b[0]: b for b in BUCKETS}

DECISIONS = ("call", "fold")


def required_equity(pot: float, bet: float, call: float | None = None) -> float:
    """call / (pot + bet + call). `call` defaults to the full bet (hero has nothing in yet)."""
    if call is None:
        call = bet
    if pot < 0 or bet <= 0 or call <= 0:
        raise ValueError("pot must be >= 0, bet and call must be positive")
    return call / (pot + bet + call)


def bucket_for(equity: float) -> str:
    if not 0 <= equity <= 1:
        raise ValueError(f"equity {equity} out of range")
    for bid, _, lo, hi in BUCKETS:
        if lo <= equity < hi:
            return bid
    raise AssertionError("unreachable")


def bucket_label(bucket_id: str) -> str:
    return _BY_ID[bucket_id][1]


def grade_bucket(equity: float, chosen: str, tolerance: float = EQUITY_TOLERANCE) -> str:
    """correct if equity is in the chosen bucket; acceptable if within `tolerance` of its edges."""
    if chosen not in _BY_ID:
        raise ValueError(f"Unknown bucket {chosen!r}")
    _, _, lo, hi = _BY_ID[chosen]
    if lo <= equity < hi:
        return CORRECT
    if lo - tolerance <= equity <= hi + tolerance:
        return ACCEPTABLE
    return WRONG


def correct_decision(equity: float, required: float) -> str:
    return "call" if equity >= required else "fold"


def grade_decision(equity: float, required: float, chosen: str,
                   tolerance: float = EQUITY_TOLERANCE) -> str:
    """correct if it matches equity vs required; acceptable if they're within `tolerance`."""
    if chosen not in DECISIONS:
        raise ValueError(f"Decision must be call or fold, got {chosen!r}")
    if chosen == correct_decision(equity, required):
        return CORRECT
    if abs(equity - required) <= tolerance:
        return ACCEPTABLE
    return WRONG


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


@dataclass(frozen=True)
class EquityGrade:
    equity: float
    std_error: float
    iterations: int
    actual_bucket: str
    bucket_grade: str
    required: float
    best_decision: str
    decision_grade: str
    bucket_explanation: str
    decision_explanation: str


def grade_equity_answer(*, equity: float, std_error: float, iterations: int,
                        pot: float, bet: float, bucket: str, decision: str,
                        tolerance: float = EQUITY_TOLERANCE) -> EquityGrade:
    req = required_equity(pot, bet)
    actual = bucket_for(equity)
    best = correct_decision(equity, req)
    b_grade = grade_bucket(equity, bucket, tolerance)
    d_grade = grade_decision(equity, req, decision, tolerance)

    b_text = f"Your equity is {pct(equity)} ({bucket_label(actual)})."
    if b_grade == ACCEPTABLE:
        b_text += f" That's within {tolerance * 100:g} points of the {bucket_label(bucket)} range, close enough."

    call = bet
    d_text = (
        f"To call {call:g} you need {call:g} / ({pot:g} + {bet:g} + {call:g}) = {pct(req)} equity. "
        f"You have {pct(equity)}, so {best} is right."
    )
    if abs(equity - req) <= tolerance:
        d_text += " It's very close, so either answer is accepted."
    return EquityGrade(
        equity=equity, std_error=std_error, iterations=iterations,
        actual_bucket=actual, bucket_grade=b_grade, required=req, best_decision=best,
        decision_grade=d_grade, bucket_explanation=b_text, decision_explanation=d_text,
    )
