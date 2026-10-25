"""Builds preflop spots: who has acted, what they did, pot size, hero's cards.

No strategy here. Bet sizes come from the caller (normally the chart's
``facing`` field); the generator only does the bookkeeping.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass

from trainer.config import BIG_BLIND_BB, SMALL_BLIND_BB
from trainer.game.dealing import deal, parse_cards
from trainer.game.hand_classes import hand_class_of
from trainer.game.positions import SPOT_TYPES, positions_for, spot_position_error, valid_spots


@dataclass(frozen=True)
class ActionStep:
    pos: str
    action: str  # "fold" or "raise"
    to_bb: float | None = None  # total bet after a raise (None if size unknown)
    is_hero: bool = False


@dataclass(frozen=True)
class PreflopSpot:
    game: str
    format: str
    table_size: int
    stack_bb: float
    spot_type: str
    hero_pos: str
    villain_pos: str | None
    hero_cards: tuple[str, ...]
    hand_class: str
    history: tuple[ActionStep, ...]
    pot_bb: float | None  # None when a bet size is unknown
    to_call_bb: float | None
    hero_invested_bb: float
    open_size_bb: float | None = None
    threebet_size_bb: float | None = None
    ante_bb: float = 0.0
    small_blind_bb: float = SMALL_BLIND_BB
    big_blind_bb: float = BIG_BLIND_BB

    def to_dict(self) -> dict:
        return asdict(self)


def _blind(pos: str) -> float:
    return {"SB": SMALL_BLIND_BB, "BB": BIG_BLIND_BB}.get(pos, 0.0)


def build_preflop_spot(
    *,
    table_size: int,
    spot_type: str,
    hero_pos: str,
    villain_pos: str | None,
    hero_cards: tuple[str, ...] | str,
    stack_bb: float = 100,
    open_size_bb: float | None = None,
    threebet_size_bb: float | None = None,
    ante_bb: float = 0.0,
    game: str = "nlhe",
    format: str = "cash",
) -> PreflopSpot:
    """Lay out the action up to hero's decision.

    rfi:     everyone before hero folds.
    vs_open: players before the opener fold, villain opens, players between fold.
    vs_3bet: players before hero fold, hero opens, players between fold,
             villain 3-bets, everyone after villain folds; back to hero.
    """
    problem = spot_position_error(table_size, spot_type, hero_pos, villain_pos)
    if problem:
        raise ValueError(problem)
    cards = parse_cards(hero_cards) if isinstance(hero_cards, str) else parse_cards("".join(hero_cards))
    if len(cards) != 2:
        raise ValueError(f"NLHE needs 2 hole cards, got {len(cards)}")
    if stack_bb <= 0 or ante_bb < 0:
        raise ValueError("stack must be positive and ante non-negative")
    if open_size_bb is not None and not (BIG_BLIND_BB < open_size_bb <= stack_bb):
        raise ValueError(f"open size {open_size_bb} must be above 1bb and at most the stack")
    if threebet_size_bb is not None:
        if open_size_bb is not None and threebet_size_bb <= open_size_bb:
            raise ValueError("3-bet size must be bigger than the open size")
        if threebet_size_bb > stack_bb:
            raise ValueError("3-bet size can't exceed the stack")
    if spot_type == "rfi" and (open_size_bb or threebet_size_bb):
        raise ValueError("rfi spots face no bets")
    if spot_type == "vs_open" and threebet_size_bb:
        raise ValueError("vs_open spots face no 3-bet")

    order = positions_for(table_size)
    contrib: dict[str, float | None] = {p: _blind(p) for p in order}
    history: list[ActionStep] = []

    def fold_range(start: int, stop: int) -> None:
        for p in order[start:stop]:
            history.append(ActionStep(p, "fold"))

    def raise_to(p: str, size: float | None) -> None:
        contrib[p] = size
        history.append(ActionStep(p, "raise", size, is_hero=(p == hero_pos)))

    hero_i = order.index(hero_pos)
    if spot_type == "rfi":
        fold_range(0, hero_i)
    elif spot_type == "vs_open":
        vil_i = order.index(villain_pos)
        fold_range(0, vil_i)
        raise_to(villain_pos, open_size_bb)
        fold_range(vil_i + 1, hero_i)
    else:  # vs_3bet
        vil_i = order.index(villain_pos)
        fold_range(0, hero_i)
        raise_to(hero_pos, open_size_bb)
        fold_range(hero_i + 1, vil_i)
        raise_to(villain_pos, threebet_size_bb)
        fold_range(vil_i + 1, len(order))

    if any(v is None for v in contrib.values()):
        pot = to_call = None
    else:
        pot = round(sum(contrib.values()) + ante_bb * table_size, 4)
        to_call = round(max(contrib.values()) - contrib[hero_pos], 4)
    hero_in = contrib[hero_pos]

    return PreflopSpot(
        game=game,
        format=format,
        table_size=table_size,
        stack_bb=stack_bb,
        spot_type=spot_type,
        hero_pos=hero_pos,
        villain_pos=villain_pos,
        hero_cards=cards,
        hand_class=hand_class_of("".join(cards)),
        history=tuple(history),
        pot_bb=pot,
        to_call_bb=to_call,
        hero_invested_bb=hero_in if hero_in is not None else 0.0,
        open_size_bb=open_size_bb,
        threebet_size_bb=threebet_size_bb,
        ante_bb=ante_bb,
    )


def random_preflop_spot(
    rng: random.Random,
    *,
    table_sizes: list[int] | None = None,
    spot_types: list[str] | None = None,
    hero_positions: list[str] | None = None,
    stack_bb: float = 100,
    open_size_bb: float | None = None,
    threebet_size_bb: float | None = None,
) -> PreflopSpot:
    """A random valid spot within the given constraints, with random hole cards.

    Sizes are only attached where the spot type uses them.
    """
    candidates = []
    for size in table_sizes or [6, 9]:
        for st in spot_types or list(SPOT_TYPES):
            for hero, villain in valid_spots(size, st):
                if hero_positions and hero not in hero_positions:
                    continue
                candidates.append((size, st, hero, villain))
    if not candidates:
        raise ValueError("No valid spot matches these constraints")
    size, st, hero, villain = rng.choice(candidates)
    return build_preflop_spot(
        table_size=size,
        spot_type=st,
        hero_pos=hero,
        villain_pos=villain,
        hero_cards=deal(rng, 2),
        stack_bb=stack_bb,
        open_size_bb=open_size_bb if st != "rfi" else None,
        threebet_size_bb=threebet_size_bb if st == "vs_3bet" else None,
    )
