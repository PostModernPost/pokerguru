"""Equity of a known hand against one random opponent hand, by Monte Carlo.

All hand evaluation is done by PokerKit (StandardHighHand for hold'em,
OmahaHoldemHand for PLO, which enforces "exactly two hole cards and three
board cards"). This module only draws the random cards and counts results.

Why not PokerKit's ``calculate_equities`` directly? It draws from Python's
shared random generator and builds its deck from a ``set`` whose order changes
every time Python starts, so the same seed doesn't give the same answer from
one run to the next. The brief requires seedable results, so the sampling
loop is here. Tests check it against ``calculate_equities``.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass

from pokerkit import Card, Deck, OmahaHoldemHand, StandardHighHand

from trainer.game.dealing import card_str, parse_cards

HAND_TYPES = {"nlhe": StandardHighHand, "plo": OmahaHoldemHand}
HOLE_CARDS = {"nlhe": 2, "plo": 4}
BOARD_SIZE = 5


@dataclass(frozen=True)
class EquityResult:
    equity: float  # 0..1, ties count half
    iterations: int
    std_error: float  # one standard error of the estimate (0 when exact)
    exact: bool = False


def _cards(cards: tuple[str, ...] | str) -> list[Card]:
    text = cards if isinstance(cards, str) else "".join(cards)
    return list(Card.parse("".join(parse_cards(text)))) if text else []


def spot_seed(game: str, hero: tuple[str, ...], board: tuple[str, ...]) -> int:
    """A stable seed derived from the cards, so the same spot always gets the same answer."""
    key = f"{game}|{''.join(hero)}|{''.join(board)}".encode()
    return int.from_bytes(hashlib.sha256(key).digest()[:8], "big")


def equity_vs_random(
    game: str,
    hero: tuple[str, ...] | str,
    board: tuple[str, ...] | str,
    *,
    iterations: int,
    seed: int | None = None,
) -> EquityResult:
    """Hero's share of the pot against one uniformly random opponent hand.

    The opponent's hole cards and the rest of the board are drawn at random
    from the cards hero can't see. On a complete (5-card) board every possible
    opponent hand is enumerated instead, which is exact.
    """
    if game not in HAND_TYPES:
        raise ValueError(f"Unknown game {game!r}; expected one of {list(HAND_TYPES)}")
    hand_type = HAND_TYPES[game]
    n_hole = HOLE_CARDS[game]
    hero_cards = _cards(hero)
    board_cards = _cards(board)
    if len(hero_cards) != n_hole:
        raise ValueError(f"{game} needs {n_hole} hole cards, got {len(hero_cards)}")
    if len(board_cards) > BOARD_SIZE:
        raise ValueError("Board can't have more than 5 cards")
    used = {card_str(c) for c in hero_cards + board_cards}
    if len(used) != len(hero_cards) + len(board_cards):
        raise ValueError("The same card appears twice")
    if iterations <= 0:
        raise ValueError("iterations must be positive")

    # Fixed order (not set order) so a seed always gives the same draws.
    deck = sorted((c for c in Deck.STANDARD if card_str(c) not in used), key=card_str)
    missing = BOARD_SIZE - len(board_cards)

    if missing == 0 and game == "nlhe":
        return _exact_river(hand_type, hero_cards, board_cards, deck)

    rng = random.Random(seed)
    hero_hand_cache: dict[tuple[str, ...], object] = {}
    total = 0.0
    sq_total = 0.0
    for _ in range(iterations):
        drawn = rng.sample(deck, n_hole + missing)
        villain = drawn[:n_hole]
        runout = drawn[n_hole:]
        full_board = board_cards + runout
        key = tuple(sorted(card_str(c) for c in runout))
        hero_hand = hero_hand_cache.get(key)
        if hero_hand is None:
            hero_hand = hand_type.from_game(hero_cards, full_board)
            hero_hand_cache[key] = hero_hand
        villain_hand = hand_type.from_game(villain, full_board)
        if hero_hand > villain_hand:
            score = 1.0
        elif hero_hand == villain_hand:
            score = 0.5
        else:
            score = 0.0
        total += score
        sq_total += score * score
    mean = total / iterations
    variance = max(sq_total / iterations - mean * mean, 0.0)
    return EquityResult(mean, iterations, math.sqrt(variance / iterations))


def _exact_river(hand_type, hero_cards, board_cards, deck) -> EquityResult:
    """Every opponent hand on a complete board (NLHE: at most 1,081 hands)."""
    hero_hand = hand_type.from_game(hero_cards, board_cards)
    total = 0.0
    n = 0
    for i in range(len(deck)):
        for j in range(i + 1, len(deck)):
            villain_hand = hand_type.from_game([deck[i], deck[j]], board_cards)
            total += 1.0 if hero_hand > villain_hand else 0.5 if hero_hand == villain_hand else 0.0
            n += 1
    return EquityResult(total / n, n, 0.0, exact=True)
