"""Descriptive facts about a starting hand and where it sits in a chart.

Used for the "why this hand" block on the Preflop result screen. Everything
here is computed (from the cards, the 169x169 equity table and the chart you
were graded against); nothing is strategic opinion.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from trainer.charts.loader import Chart
from trainer.game.hand_classes import ALL_HAND_CLASSES, RANK_VALUE, combo_count, hand_category
from trainer.game.preflop_equity import load_table
from trainer.solvers.pushfold import combo_weights

RANK_WORD = {"A": "ace", "K": "king", "Q": "queen", "J": "jack", "T": "ten", "9": "nine", "8": "eight",
             "7": "seven", "6": "six", "5": "five", "4": "four", "3": "three", "2": "two"}
BROADWAY = set("AKQJT")
INDEX = {h: i for i, h in enumerate(ALL_HAND_CLASSES)}


@lru_cache(maxsize=1)
def equity_vs_random_all() -> np.ndarray:
    """All-in equity of each hand class against one random hand, from the computed table.

    Weighted by how many combos of each opponent class are possible given our cards.
    """
    eq = load_table()
    w = combo_weights()
    return (w * eq).sum(axis=1) / w.sum(axis=1)


@lru_cache(maxsize=1)
def equity_rank_all() -> dict[str, int]:
    """1 = best starting hand by all-in equity vs a random hand, 169 = worst."""
    e = equity_vs_random_all()
    order = sorted(range(169), key=lambda i: -e[i])
    return {ALL_HAND_CLASSES[i]: rank + 1 for rank, i in enumerate(order)}


def features(hand_class: str) -> list[str]:
    """Short factual descriptions of the hand's make-up."""
    hi, lo = hand_class[0], hand_class[1]
    suited = len(hand_class) == 3 and hand_class[2] == "s"
    out: list[str] = []
    if hi == lo:
        out.append(f"a pocket pair of {RANK_WORD[hi]}s")
        if RANK_VALUE[hi] >= 10:
            out.append("a high pair, a favourite against most unpaired hands before the flop")
        else:
            out.append("a small pair: it usually needs to hit a set to be strong after the flop")
        return out
    gap = RANK_VALUE[hi] - RANK_VALUE[lo] - 1
    if hi in BROADWAY and lo in BROADWAY:
        out.append("two broadway cards (ten or higher), so it often makes top pair with a strong kicker")
    elif hi == "A":
        out.append("an ace with a " + ("low" if RANK_VALUE[lo] <= 9 else "high") + " kicker")
    if suited:
        out.append("suited: both cards share a suit, which adds flush chances (about 2-3 points of equity)")
    else:
        out.append("offsuit: no shared suit, so no flush draws from both cards")
    if gap == 0:
        out.append("connected: the ranks are next to each other, which helps make straights")
    elif gap == 1:
        out.append("a one-gap hand: straights are possible but need a specific card in the middle")
    if hi == "A" and 2 <= RANK_VALUE[lo] <= 5 and suited:
        out.append("a suited wheel ace: it can make the ace-to-five straight as well as the nut flush")
    if hi == "A":
        out.append("holding an ace makes it less likely an opponent has one (a blocker)")
    return out


@dataclass(frozen=True)
class ChartContext:
    play_frequency: float  # how often the chart does something other than fold with this hand
    played_more_often: int  # number of hand classes the chart plays more often here
    range_share: float  # fraction of all 1326 combos the chart plays here
    category: str
    weakest_played_in_category: str | None  # the lowest-equity hand of the same category still played (>= 50%)
    strongest_folded_in_category: str | None


def chart_context(chart: Chart, hand_class: str) -> ChartContext:
    eq_rank = equity_rank_all()
    play = {h: 1 - chart.hands[h].get("fold", 0.0) for h in ALL_HAND_CLASSES}
    mine = play[hand_class]
    more = sum(1 for h, f in play.items() if f > mine + 1e-9)
    share = sum(f * combo_count(h) for h, f in play.items()) / 1326
    cat = hand_category(hand_class)
    same = [h for h in ALL_HAND_CLASSES if hand_category(h) == cat]
    played = [h for h in same if play[h] >= 0.5]
    folded = [h for h in same if play[h] < 0.5]
    weakest_played = max(played, key=lambda h: eq_rank[h]) if played else None  # highest rank number = weakest
    strongest_folded = min(folded, key=lambda h: eq_rank[h]) if folded else None
    return ChartContext(round(mine, 4), more, round(share, 4), cat, weakest_played, strongest_folded)


def why_this_hand(chart: Chart, hand_class: str) -> dict:
    """Everything the result screen shows under 'Why this hand', as data plus plain sentences."""
    eq = float(equity_vs_random_all()[INDEX[hand_class]])
    rank = equity_rank_all()[hand_class]
    ctx = chart_context(chart, hand_class)
    lines = [f"{hand_class} is " + "; ".join(features(hand_class)) + "."]
    lines.append(f"All-in against one random hand it wins about {eq:.0%} of the time, "
                 f"ranking {rank} of 169 starting hands.")
    who = chart.hero_pos
    if ctx.play_frequency >= 0.999:
        lines.append(f"In this chart {who} always plays it here; {ctx.played_more_often} hands are played more often.")
    elif ctx.play_frequency <= 0.001:
        lines.append(f"In this chart {who} never plays it here; the chart plays {ctx.range_share:.0%} of all hands in this spot.")
    else:
        lines.append(f"In this chart {who} plays it {ctx.play_frequency:.0%} of the time here; "
                     f"{ctx.played_more_often} hands are played more often.")
    if ctx.weakest_played_in_category and ctx.strongest_folded_in_category:
        lines.append(f"Among {ctx.category}s, the weakest this chart still plays here is "
                     f"{ctx.weakest_played_in_category} and the strongest it folds is {ctx.strongest_folded_in_category}.")
    elif ctx.weakest_played_in_category:
        lines.append(f"This chart plays every {ctx.category} here, down to {ctx.weakest_played_in_category}.")
    elif ctx.strongest_folded_in_category:
        lines.append(f"This chart folds every {ctx.category} here, even {ctx.strongest_folded_in_category}.")
    return {
        "features": features(hand_class),
        "equity_vs_random": round(eq, 4),
        "equity_rank": rank,
        "chart": ctx.__dict__,
        "lines": lines,
    }
