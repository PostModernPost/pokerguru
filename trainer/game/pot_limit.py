"""Pot-limit bet sizing. Pure arithmetic, no strategy.

With `pot` meaning every chip already in the middle *plus* every bet made so
far this round:

    amount_to_call = largest_bet_this_round - hero_chips_already_in_this_round
    max_raise_to   = largest_bet_this_round + pot + amount_to_call

The idea: hero first calls, then raises by the size of the pot that results.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PotLimitSizing:
    pot: float  # everything in the middle, including this round's bets
    largest_bet: float
    hero_in: float
    to_call: float
    pot_after_call: float
    max_raise_to: float


def max_raise_to(pot: float, largest_bet: float, hero_in: float = 0.0) -> PotLimitSizing:
    """Largest total bet hero may make (the "raise to" amount)."""
    if pot < 0 or largest_bet < 0 or hero_in < 0:
        raise ValueError("pot, largest_bet and hero_in can't be negative")
    if hero_in > largest_bet:
        raise ValueError("hero can't already have more in than the largest bet")
    if largest_bet > pot:
        raise ValueError("the largest bet is part of the pot, so it can't exceed it")
    to_call = largest_bet - hero_in
    pot_after_call = pot + to_call
    return PotLimitSizing(
        pot=pot,
        largest_bet=largest_bet,
        hero_in=hero_in,
        to_call=to_call,
        pot_after_call=pot_after_call,
        max_raise_to=largest_bet + pot_after_call,
    )
