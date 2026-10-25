"""Hand reading basics: what hero holds right now, and which next cards improve it.

Works for Hold'em (two hole cards, best five of seven) and Omaha (exactly two
hole cards plus three board cards). PokerKit evaluates every hand; the hand
descriptions come from ``trainer.game.omaha.describe``.

"Improving outs" are the unseen cards that give hero a hand of a straight or
better that beats the current hand: the same definition the Nuts drill uses
for draws. Pairing up is not counted as an out here.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import comb

from pokerkit import Card, Deck, OmahaHoldemHand, StandardHighHand

from trainer.game.dealing import card_str, parse_cards
from trainer.game.omaha import STRONG_LABELS, HandInfo, _info, describe

HAND_TYPES = {"nlhe": StandardHighHand, "plo": OmahaHoldemHand}
HOLE = {"nlhe": 2, "plo": 4}


def _cards(cards) -> list[Card]:
    """Accept 'AsKd', ('As', 'Kd') or a list of PokerKit Cards."""
    if not isinstance(cards, str):
        cards = list(cards)
        if cards and isinstance(cards[0], Card):
            return cards
    joined = cards if isinstance(cards, str) else "".join(cards)
    return list(Card.parse("".join(parse_cards(joined)))) if joined else []


def _check(game: str, hero: list[Card], board: list[Card]) -> None:
    if game not in HAND_TYPES:
        raise ValueError(f"game must be one of {list(HAND_TYPES)}")
    if len(hero) != HOLE[game]:
        raise ValueError(f"{game} needs {HOLE[game]} hole cards, got {len(hero)}")
    if len(board) not in (3, 4, 5):
        raise ValueError("board must have 3, 4 or 5 cards")
    if len({card_str(c) for c in hero + board}) != len(hero) + len(board):
        raise ValueError("the same card appears twice")


def current_hand(game: str, hero, board) -> HandInfo:
    hero_c, board_c = _cards(hero), _cards(board)
    _check(game, hero_c, board_c)
    h = HAND_TYPES[game].from_game(hero_c, board_c)
    return _info(h.entry, list(h.cards))


def unseen(hero: list[Card], board: list[Card]) -> list[Card]:
    used = {card_str(c) for c in hero + board}
    return sorted((c for c in Deck.STANDARD if card_str(c) not in used), key=card_str)


@dataclass(frozen=True)
class OutsInfo:
    outs: tuple[str, ...]  # cards that make a straight or better, stronger than now
    cards_to_come: int
    hit_chance_next_card: float  # exact: outs / unseen
    hit_chance_by_river: float  # exact for two cards to come (at least one out arrives)
    rule_estimate: float  # rule of 2 and 4
    best_outcome: str  # description of the best hand an out makes


def improving_outs(game: str, hero, board) -> OutsInfo:
    hero_c, board_c = _cards(hero), _cards(board)
    _check(game, hero_c, board_c)
    if len(board_c) == 5:
        raise ValueError("no cards to come on the river")
    now = HAND_TYPES[game].from_game(hero_c, board_c)
    pool = unseen(hero_c, board_c)
    outs: list[str] = []
    best = None
    for card in pool:
        h = HAND_TYPES[game].from_game(hero_c, board_c + [card])
        if h.entry > now.entry and h.entry.label in STRONG_LABELS:
            outs.append(card_str(card))
            if best is None or h.entry > best.entry:
                best = h
    n, u = len(outs), len(pool)
    to_come = 5 - len(board_c)
    next_card = n / u
    if to_come == 2:
        # Chance at least one of the n outs comes in two cards (ignoring new draws the first card could open).
        by_river = 1 - comb(u - n, 2) / comb(u, 2)
        rule = min(1.0, 4 * n / 100)
    else:
        by_river = next_card
        rule = min(1.0, 2 * n / 100)
    return OutsInfo(tuple(outs), to_come, round(next_card, 4), round(by_river, 4), rule,
                    describe(best.entry, list(best.cards)) if best else "")


def possible_hands(game: str, hero, board, limit: int = 12) -> list[HandInfo]:
    """Distinct hand descriptions anyone could hold on this board, strongest first.

    Used for quiz distractors. For Hold'em every two-card holding is tried;
    for Omaha the nut-awareness module's enumeration is reused.
    """
    hero_c, board_c = _cards(hero), _cards(board)
    _check(game, hero_c, board_c)
    if game == "plo":
        from trainer.game.omaha import possible_hands as plo_possible
        return plo_possible(hero_c, board_c)[:limit]
    seen: dict[str, HandInfo] = {}
    pool = unseen(hero_c, board_c)
    for a, b in combinations(pool, 2):
        h = StandardHighHand.from_game([a, b], board_c)
        d = describe(h.entry, list(h.cards))
        if d not in seen or h.entry > seen[d].entry:
            seen[d] = _info(h.entry, list(h.cards))
    mine = current_hand(game, hero_c, board_c)
    out = sorted(seen.values(), key=lambda x: x.entry, reverse=True)[:limit]
    if mine.description not in {h.description for h in out}:
        out.append(mine)  # hero's own hand is always a candidate answer
    return out
