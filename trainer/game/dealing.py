"""Dealing cards from PokerKit's standard deck."""

from __future__ import annotations

import random

from pokerkit import Card, Deck


def card_str(card: Card) -> str:
    """'As', 'Td', ... (rank then suit letter)."""
    return f"{card.rank.value}{card.suit.value}"


def deal(rng: random.Random, count: int, exclude: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Deal `count` distinct cards from a fresh 52-card deck, minus `exclude`."""
    excluded = {card_str(c) for c in Card.parse("".join(exclude))}
    deck = [c for c in Deck.STANDARD if card_str(c) not in excluded]
    return tuple(card_str(c) for c in rng.sample(deck, count))


def parse_cards(text: str) -> tuple[str, ...]:
    """Validate and normalize a card string like 'AsKd' -> ('As', 'Kd'). Raises ValueError."""
    try:
        cards = tuple(card_str(c) for c in Card.parse(text))
    except Exception as e:  # PokerKit raises ValueError/KeyError on bad input
        raise ValueError(f"Bad cards {text!r}: {e}") from None
    if any("?" in c for c in cards):
        raise ValueError(f"Bad cards {text!r}: unknown card")
    if len(set(cards)) != len(cards):
        raise ValueError(f"Bad cards {text!r}: duplicate card")
    return cards
