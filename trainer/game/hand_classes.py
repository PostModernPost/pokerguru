"""The 169 NLHE starting-hand classes (AA, AKs, AKo, ... 32o).

Pure card bookkeeping, no strategy.
"""

from __future__ import annotations

from collections.abc import Iterable

from pokerkit import Card

# Highest to lowest. This is also the row/column order of the standard 13x13 grid.
RANKS = "AKQJT98765432"
RANK_VALUE = {r: 14 - i for i, r in enumerate(RANKS)}  # A=14 ... 2=2


def _class_name(high: str, low: str, suited: bool) -> str:
    if high == low:
        return high + low
    return high + low + ("s" if suited else "o")


def grid() -> list[list[str]]:
    """13x13 grid of hand classes in the usual chart layout.

    Pairs on the diagonal, suited hands above it (row rank is the higher card),
    offsuit hands below it.
    """
    rows = []
    for i, r1 in enumerate(RANKS):
        row = []
        for j, r2 in enumerate(RANKS):
            if i == j:
                row.append(r1 + r2)
            elif i < j:
                row.append(r1 + r2 + "s")
            else:
                row.append(r2 + r1 + "o")
        rows.append(row)
    return rows


ALL_HAND_CLASSES: tuple[str, ...] = tuple(h for row in grid() for h in row)
HAND_CLASS_SET = frozenset(ALL_HAND_CLASSES)


def is_hand_class(name: str) -> bool:
    return name in HAND_CLASS_SET


def combo_count(hand_class: str) -> int:
    """Number of specific card combinations in a class: pairs 6, suited 4, offsuit 12."""
    if not is_hand_class(hand_class):
        raise ValueError(f"Not a hand class: {hand_class!r}")
    if len(hand_class) == 2:
        return 6
    return 4 if hand_class[2] == "s" else 12


def hand_class_of(cards: Iterable[Card] | str) -> str:
    """Hand class for two hole cards, e.g. [As, Kd] -> 'AKo'."""
    if isinstance(cards, str):
        cards = Card.parse(cards)
    cards = list(cards)
    if len(cards) != 2:
        raise ValueError(f"Need exactly 2 cards, got {len(cards)}")
    a, b = cards
    ra, rb = a.rank.value, b.rank.value
    if RANK_VALUE[ra] < RANK_VALUE[rb]:
        ra, rb = rb, ra
    if ra == rb and a.suit == b.suit:
        raise ValueError("Duplicate card")
    return _class_name(ra, rb, a.suit == b.suit)
