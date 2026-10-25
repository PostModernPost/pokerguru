"""Builds equity / pot odds spots: hero's hand, a flop or turn, a pot and a bet.

Villain's hand is not dealt. It's "any random hand", which the equity
calculation handles.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass

from trainer import config
from trainer.game.dealing import deal, parse_cards
from trainer.game.equity import HOLE_CARDS
from trainer.game.hand_classes import RANK_VALUE, hand_class_of

STREETS = {"flop": 3, "turn": 4}
GAMES = tuple(HOLE_CARDS)


@dataclass(frozen=True)
class EquitySpot:
    game: str
    street: str
    hero_cards: tuple[str, ...]
    board: tuple[str, ...]
    pot_bb: float  # in the middle before villain's bet
    bet_bb: float  # villain's bet; hero has nothing in this round, so this is also the call
    hand_class: str | None  # NLHE only

    @property
    def to_call_bb(self) -> float:
        return self.bet_bb

    def to_dict(self) -> dict:
        d = asdict(self)
        d["to_call_bb"] = self.to_call_bb
        return d


def sort_cards(cards: tuple[str, ...]) -> tuple[str, ...]:
    """High cards first, grouped by suit within a rank, so 4-card PLO hands read easily."""
    return tuple(sorted(cards, key=lambda c: (-RANK_VALUE[c[0]], c[1])))


def build_equity_spot(*, game: str, street: str, hero_cards, board, pot_bb: float, bet_bb: float) -> EquitySpot:
    if game not in GAMES:
        raise ValueError(f"game must be one of {list(GAMES)}")
    if street not in STREETS:
        raise ValueError(f"street must be one of {list(STREETS)}")
    hero = parse_cards(hero_cards if isinstance(hero_cards, str) else "".join(hero_cards))
    brd = parse_cards(board if isinstance(board, str) else "".join(board))
    if len(hero) != HOLE_CARDS[game]:
        raise ValueError(f"{game} needs {HOLE_CARDS[game]} hole cards, got {len(hero)}")
    if len(brd) != STREETS[street]:
        raise ValueError(f"The {street} has {STREETS[street]} board cards, got {len(brd)}")
    if set(hero) & set(brd):
        raise ValueError("A card is in both hero's hand and the board")
    if pot_bb <= 0 or bet_bb <= 0:
        raise ValueError("pot and bet must be positive")
    if game == "plo" and bet_bb > pot_bb:
        raise ValueError("Pot-limit: a bet can't be bigger than the pot")
    return EquitySpot(
        game=game,
        street=street,
        hero_cards=sort_cards(hero),
        board=brd,
        pot_bb=float(pot_bb),
        bet_bb=float(bet_bb),
        hand_class=hand_class_of("".join(hero)) if game == "nlhe" else None,
    )


def round_bet(x: float) -> float:
    """Nearest half big blind, at least 0.5bb."""
    return max(0.5, round(x * 2) / 2)


def random_equity_spot(
    rng: random.Random,
    *,
    games: list[str] | None = None,
    streets: list[str] | None = None,
) -> EquitySpot:
    game = rng.choice(games or list(GAMES))
    street = rng.choice(streets or list(STREETS))
    cards = deal(rng, HOLE_CARDS[game] + STREETS[street])
    pot = float(rng.choice(config.EQUITY_POT_SIZES_BB))
    bet = round_bet(pot * rng.choice(config.EQUITY_BET_FRACTIONS[game]))
    if game == "plo":
        bet = min(bet, pot)
    return build_equity_spot(
        game=game,
        street=street,
        hero_cards=cards[: HOLE_CARDS[game]],
        board=cards[HOLE_CARDS[game]:],
        pot_bb=pot,
        bet_bb=bet,
    )
