"""Spots for the Basics drill: name your hand, count your outs, know the price.

All three are pure arithmetic/evaluation; nothing here is strategy.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass

from trainer import config
from trainer.game.dealing import deal, parse_cards
from trainer.game.outs import HOLE, improving_outs
from trainer.scenarios.postflop import round_bet, sort_cards

QUESTIONS = ("hand", "outs", "price")
STREETS = {"flop": 3, "turn": 4, "river": 5}
OUTS_MIN, OUTS_MAX = 3, 15  # only serve outs questions where there is a real draw to count


@dataclass(frozen=True)
class BasicsSpot:
    question: str  # hand | outs | price
    game: str  # nlhe | plo (price questions carry the game only for flavour)
    street: str
    hero_cards: tuple[str, ...]
    board: tuple[str, ...]
    pot_bb: float | None = None  # price questions
    bet_bb: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def build_basics_spot(*, question: str, game: str, street: str, hero_cards, board,
                      pot_bb: float | None = None, bet_bb: float | None = None) -> BasicsSpot:
    if question not in QUESTIONS:
        raise ValueError(f"question must be one of {QUESTIONS}")
    if game not in HOLE:
        raise ValueError(f"game must be one of {list(HOLE)}")
    if street not in STREETS:
        raise ValueError(f"street must be one of {list(STREETS)}")
    hero = parse_cards(hero_cards if isinstance(hero_cards, str) else "".join(hero_cards))
    brd = parse_cards(board if isinstance(board, str) else "".join(board))
    if len(hero) != HOLE[game]:
        raise ValueError(f"{game} needs {HOLE[game]} hole cards")
    if len(brd) != STREETS[street]:
        raise ValueError(f"the {street} has {STREETS[street]} board cards")
    if set(hero) & set(brd):
        raise ValueError("a card is in both hero's hand and the board")
    if question == "outs":
        if game != "nlhe":
            raise ValueError("outs questions are Hold'em only")
        if street == "river":
            raise ValueError("no outs to count on the river")
    if question == "price":
        if pot_bb is None or bet_bb is None or pot_bb <= 0 or bet_bb <= 0:
            raise ValueError("price questions need a positive pot and bet")
    return BasicsSpot(question, game, street, sort_cards(hero), brd,
                      float(pot_bb) if pot_bb else None, float(bet_bb) if bet_bb else None)


def random_basics_spot(rng: random.Random, *, questions: list[str] | None = None,
                       games: list[str] | None = None) -> BasicsSpot:
    question = rng.choice(questions or list(QUESTIONS))
    game = "nlhe" if question == "outs" else rng.choice(games or list(HOLE))
    if question == "outs":
        for _ in range(200):  # keep dealing until there's a draw worth counting
            street = rng.choice(["flop", "turn"])
            cards = deal(rng, 2 + STREETS[street])
            info = improving_outs("nlhe", cards[:2], cards[2:])
            if OUTS_MIN <= len(info.outs) <= OUTS_MAX:
                return build_basics_spot(question="outs", game="nlhe", street=street,
                                         hero_cards=cards[:2], board=cards[2:])
        raise RuntimeError("could not find an outs spot")  # practically impossible
    street = rng.choice(list(STREETS)) if question == "hand" else rng.choice(["flop", "turn"])
    cards = deal(rng, HOLE[game] + STREETS[street])
    pot = bet = None
    if question == "price":
        pot = float(rng.choice(config.EQUITY_POT_SIZES_BB))
        bet = round_bet(pot * rng.choice(config.EQUITY_BET_FRACTIONS[game]))
    return build_basics_spot(question=question, game=game, street=street,
                             hero_cards=cards[:HOLE[game]], board=cards[HOLE[game]:], pot_bb=pot, bet_bb=bet)
