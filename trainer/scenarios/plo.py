"""Spots for the PLO drills: nut awareness and pot-limit sizing. No strategy."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass

from trainer import config
from trainer.game.dealing import deal, parse_cards
from trainer.game.positions import positions_for
from trainer.game.pot_limit import PotLimitSizing, max_raise_to
from trainer.scenarios.postflop import sort_cards

NUT_STREETS = {"flop": 3, "turn": 4, "river": 5}


# ---------- nut awareness ----------

@dataclass(frozen=True)
class NutSpot:
    street: str
    hero_cards: tuple[str, ...]
    board: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def build_nut_spot(*, street: str, hero_cards, board) -> NutSpot:
    if street not in NUT_STREETS:
        raise ValueError(f"street must be one of {list(NUT_STREETS)}")
    hero = parse_cards(hero_cards if isinstance(hero_cards, str) else "".join(hero_cards))
    brd = parse_cards(board if isinstance(board, str) else "".join(board))
    if len(hero) != 4:
        raise ValueError(f"PLO needs 4 hole cards, got {len(hero)}")
    if len(brd) != NUT_STREETS[street]:
        raise ValueError(f"The {street} has {NUT_STREETS[street]} board cards, got {len(brd)}")
    if set(hero) & set(brd):
        raise ValueError("A card is in both hero's hand and the board")
    return NutSpot(street=street, hero_cards=sort_cards(hero), board=brd)


def random_nut_spot(rng: random.Random, *, streets: list[str] | None = None) -> NutSpot:
    street = rng.choice(streets or list(NUT_STREETS))
    cards = deal(rng, 4 + NUT_STREETS[street])
    return build_nut_spot(street=street, hero_cards=cards[:4], board=cards[4:])


# ---------- pot-limit sizing ----------

@dataclass(frozen=True)
class PotLimitSpot:
    """Everything the user sees, plus the sizing answer (computed, never shown first)."""
    stage: str  # "preflop" or "postflop"
    small_blind: float
    big_blind: float
    hero_pos: str
    hero_in: float  # hero's chips already in this round (blinds or an earlier raise)
    pot_before_round: float  # chips in the middle from earlier streets (postflop only)
    history: tuple[dict, ...]  # [{"pos", "action", "to"}] this round, in order
    pot: float  # everything in the middle including this round's bets
    largest_bet: float
    to_call: float
    max_raise_to: float

    def to_dict(self) -> dict:
        d = asdict(self)
        d["history"] = list(self.history)
        return d


def _pot_limit_spot(stage: str, sb: float, bb: float, hero_pos: str, hero_in: float,
                    pot_before: float, history: list[dict], pot: float, largest: float) -> PotLimitSpot:
    sizing: PotLimitSizing = max_raise_to(pot=pot, largest_bet=largest, hero_in=hero_in)
    return PotLimitSpot(
        stage=stage, small_blind=sb, big_blind=bb, hero_pos=hero_pos, hero_in=hero_in,
        pot_before_round=pot_before, history=tuple(history), pot=pot, largest_bet=largest,
        to_call=sizing.to_call, max_raise_to=sizing.max_raise_to,
    )


def build_preflop_pot_limit_spot(*, small_blind: float, big_blind: float, hero_pos: str,
                                 actions: list[tuple[str, str]], table_size: int = 6) -> PotLimitSpot:
    """`actions`: (position, 'fold' | 'check' | 'call' | 'pot' | 'raise:<to>') for each player before hero."""
    order = positions_for(table_size)
    if hero_pos not in order:
        raise ValueError(f"Unknown position {hero_pos}")
    contrib = {p: 0.0 for p in order}
    contrib["SB"], contrib["BB"] = small_blind, big_blind
    largest = big_blind
    history: list[dict] = []
    for pos, act in actions:
        if pos == hero_pos or pos not in order:
            raise ValueError(f"Bad position {pos} in actions")
        if act == "fold":
            history.append({"pos": pos, "action": "fold", "to": None})
        elif act == "check":
            if contrib[pos] != largest:
                raise ValueError(f"{pos} can't check facing a bet")
            history.append({"pos": pos, "action": "check", "to": None})
        elif act == "call":
            contrib[pos] = largest
            history.append({"pos": pos, "action": "call", "to": largest})
        elif act == "pot" or act.startswith("raise:"):
            pot_now = sum(contrib.values())
            if act == "pot":
                to = max_raise_to(pot=pot_now, largest_bet=largest, hero_in=contrib[pos]).max_raise_to
            else:
                to = float(act.split(":")[1])
                if to <= largest:
                    raise ValueError("A raise must be bigger than the current largest bet")
            contrib[pos] = to
            largest = to
            history.append({"pos": pos, "action": "raise", "to": to})
        else:
            raise ValueError(f"Unknown action {act!r}")
    pot = sum(contrib.values())
    return _pot_limit_spot("preflop", small_blind, big_blind, hero_pos, contrib[hero_pos], 0.0,
                           history, pot, largest)


def build_postflop_pot_limit_spot(*, pot_before: float, bet: float | None, callers: int = 0,
                                  small_blind: float = 1, big_blind: float = 2,
                                  hero_pos: str = "BTN") -> PotLimitSpot:
    """Villain bets `bet` (or None if nobody has bet yet), `callers` others call, hero to act."""
    if pot_before <= 0:
        raise ValueError("pot must be positive")
    history: list[dict] = []
    largest = 0.0
    pot = pot_before
    if bet is not None:
        if not 0 < bet <= pot_before:
            raise ValueError("A pot-limit bet must be between 0 and the pot")
        largest = bet
        pot += bet
        history.append({"pos": "Villain", "action": "bet", "to": bet})
        for i in range(callers):
            pot += bet
            history.append({"pos": f"Player {i + 2}", "action": "call", "to": bet})
    elif callers:
        raise ValueError("Nobody can call before there is a bet")
    return _pot_limit_spot("postflop", small_blind, big_blind, hero_pos, 0.0, pot_before,
                           history, pot, largest)


def random_pot_limit_spot(rng: random.Random, *, stages: list[str] | None = None) -> PotLimitSpot:
    stage = rng.choice(stages or ["preflop", "postflop"])
    sb, bb = rng.choice(config.POT_LIMIT_BLINDS)
    if stage == "postflop":
        pot = float(rng.choice(config.POT_LIMIT_POSTFLOP_POTS)) * bb
        if rng.random() < 0.2:
            return build_postflop_pot_limit_spot(pot_before=pot, bet=None, small_blind=sb, big_blind=bb)
        bet = max(bb, round(pot * rng.choice(config.POT_LIMIT_BET_FRACTIONS)))
        callers = 1 if rng.random() < 0.3 else 0
        return build_postflop_pot_limit_spot(pot_before=pot, bet=float(bet), callers=callers,
                                             small_blind=sb, big_blind=bb)

    order = positions_for(6)
    hero_pos = rng.choice(order)
    actions: list[tuple[str, str]] = []
    raises = 0
    for pos in order[: order.index(hero_pos)]:
        so_far = build_preflop_pot_limit_spot(small_blind=sb, big_blind=bb, hero_pos=hero_pos, actions=actions)
        largest = so_far.largest_bet
        r = rng.random()
        if pos == "BB" and raises == 0:
            # Nobody raised: the big blind checks (usually) or raises.
            if r < 0.7:
                actions.append((pos, "check"))
                continue
        elif r < 0.45:
            actions.append((pos, "fold"))
            continue
        elif r < 0.75 or raises >= 2:
            actions.append((pos, "call"))
            continue
        raises += 1
        if rng.random() < 0.6:
            actions.append((pos, "pot"))
        else:
            # A smaller, round-number raise: at least a min-raise, at most the pot.
            hero_in_now = bb if pos == "BB" else sb if pos == "SB" else 0.0
            cap = max_raise_to(pot=so_far.pot, largest_bet=largest, hero_in=hero_in_now).max_raise_to
            choices = sorted({x for x in (2 * largest, 3 * largest) if x <= cap} | {2 * largest})
            actions.append((pos, f"raise:{rng.choice(choices):g}"))
    return build_preflop_pot_limit_spot(small_blind=sb, big_blind=bb, hero_pos=hero_pos, actions=actions)
