"""Fast hold'em showdown evaluation for bulk work (the 169x169 equity table).

PokerKit stays the judge of every hand: a table of all 2,598,960 five-card
hands is filled from ``StandardLookup`` once and cached on disk. Seven-card
hands are then ranked by taking the best of the 21 five-card subsets, in
numpy, which is roughly a hundred times faster than calling PokerKit per hand.

Card ids are 0..51: id = rank_index * 4 + suit_index, ranks 2..A, suits c d h s.
"""

from __future__ import annotations

import logging
from itertools import combinations
from math import comb
from pathlib import Path

import numpy as np
from pokerkit import Card, StandardLookup

from trainer import config

log = logging.getLogger(__name__)

RANKS = "23456789TJQKA"
SUITS = "cdhs"
TABLE_PATH = Path(config.PROJECT_ROOT) / "data" / "equity_cache" / "five_card_ranks.npy"
TABLE_SIZE = comb(52, 5)

# Index of a sorted 5-card id tuple in the combinatorial number system.
_BINOM = np.array([[comb(n, k) for k in range(6)] for n in range(53)], dtype=np.int64)
_SUBSETS = np.array(list(combinations(range(7), 5)), dtype=np.int64)  # (21, 5)


def card_id(card: str | Card) -> int:
    if isinstance(card, Card):
        card = f"{card.rank.value}{card.suit.value}"
    return RANKS.index(card[0]) * 4 + SUITS.index(card[1])


def card_name(cid: int) -> str:
    return RANKS[cid // 4] + SUITS[cid % 4]


def combo_index(sorted_ids: np.ndarray) -> np.ndarray:
    """(..., 5) sorted ascending card ids -> (...) table index."""
    idx = np.zeros(sorted_ids.shape[:-1], dtype=np.int64)
    for k in range(5):
        idx += _BINOM[sorted_ids[..., k], k + 1]
    return idx


def build_table() -> np.ndarray:
    """Rank index (higher is better) for every 5-card hand, straight from PokerKit."""
    lookup = StandardLookup()
    cards = [next(iter(Card.parse(card_name(i)))) for i in range(52)]
    table = np.empty(TABLE_SIZE, dtype=np.int16)
    for ids in combinations(range(52), 5):
        table[combo_index(np.array(ids))] = lookup.get_entry([cards[i] for i in ids]).index
    return table


_table: np.ndarray | None = None


def five_card_table() -> np.ndarray:
    global _table
    if _table is None:
        if TABLE_PATH.exists():
            _table = np.load(TABLE_PATH)
            if _table.shape != (TABLE_SIZE,):
                _table = None
        if _table is None:
            log.info("Building the 5-card rank table from PokerKit (about 20 s, done once)...")
            _table = build_table()
            TABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
            np.save(TABLE_PATH, _table)
    return _table


def rank7(hands: np.ndarray) -> np.ndarray:
    """(N, 7) card ids -> (N,) rank of the best five-card hand. Higher wins."""
    table = five_card_table()
    subsets = np.sort(hands[:, _SUBSETS], axis=2)  # (N, 21, 5)
    return table[combo_index(subsets)].max(axis=1)


def rank5(hands: np.ndarray) -> np.ndarray:
    """(N, 5) card ids -> (N,) rank."""
    return five_card_table()[combo_index(np.sort(hands, axis=1))]
