"""Graders for the Basics drill. Every answer is computed."""

from __future__ import annotations

import random
from dataclasses import dataclass

from trainer.game.outs import current_hand, improving_outs, possible_hands
from trainer.graders.equity import required_equity
from trainer.graders.preflop_chart import CORRECT, WRONG
from trainer.scenarios.basics import BasicsSpot

OPTION_COUNT = 4


@dataclass(frozen=True)
class BasicsQuestion:
    prompt: str
    options: list[str]  # what the user picks from (strings, shown as given)
    answer: str
    explanation: str
    detail: dict


def _shuffle(options: list[str], seed: int) -> list[str]:
    opts = list(options)
    random.Random(seed).shuffle(opts)
    return opts


def hand_question(spot: BasicsSpot, seed: int) -> BasicsQuestion:
    mine = current_hand(spot.game, spot.hero_cards, spot.board)
    others = [h.description for h in possible_hands(spot.game, spot.hero_cards, spot.board)
              if h.description != mine.description]
    # Distractors: the nearest stronger and weaker hands other players could hold.
    picks = others[:OPTION_COUNT - 1]
    options = _shuffle([mine.description] + picks, seed)
    rule = (" Remember: in Omaha you must use exactly two hole cards and three board cards."
            if spot.game == "plo" else "")
    return BasicsQuestion(
        prompt="What is your best hand right now?",
        options=options,
        answer=mine.description,
        explanation=f"You have {mine.description.lower()}: {' '.join(mine.cards)}.{rule}",
        detail={"cards": list(mine.cards)},
    )


def outs_question(spot: BasicsSpot, seed: int) -> BasicsQuestion:
    info = improving_outs(spot.game, spot.hero_cards, spot.board)
    n = len(info.outs)
    rng = random.Random(seed)
    wrong = set()
    for delta in (-4, -3, -2, -1, 1, 2, 3, 4):
        if 0 <= n + delta <= 21:
            wrong.add(n + delta)
    picks = rng.sample(sorted(wrong), OPTION_COUNT - 1)
    options = [str(x) for x in sorted([n] + picks)]
    street_word = "two cards to come" if info.cards_to_come == 2 else "one card to come"
    expl = (f"{n} outs ({' '.join(info.outs)}): any of them gives you {info.best_outcome.lower()} or better. "
            f"Rule of {'4' if info.cards_to_come == 2 else '2'}: about {info.rule_estimate:.0%}; "
            f"exact chance with {street_word}: {info.hit_chance_by_river:.0%}"
            + (f" ({info.hit_chance_next_card:.0%} on the next card alone)." if info.cards_to_come == 2 else "."))
    return BasicsQuestion(
        prompt="How many outs do you have to a straight or better?",
        options=options,
        answer=str(n),
        explanation=expl,
        detail={"outs": list(info.outs), "hit_by_river": info.hit_chance_by_river,
                "hit_next": info.hit_chance_next_card, "rule": info.rule_estimate},
    )


def price_question(spot: BasicsSpot, seed: int) -> BasicsQuestion:
    req = required_equity(spot.pot_bb, spot.bet_bb)
    answer = f"{req * 100:.0f}%"
    # Distractors: other common break-even points.
    common = [20, 25, 29, 33, 40, 44, 50]
    rng = random.Random(seed)
    cands = [f"{c}%" for c in common if f"{c}%" != answer and abs(c - req * 100) >= 3]
    picks = rng.sample(cands, OPTION_COUNT - 1)
    options = sorted([answer] + picks, key=lambda s: int(s.rstrip("%")))
    call = spot.bet_bb
    return BasicsQuestion(
        prompt="What share of the pot do you need to win for a call to break even?",
        options=options,
        answer=answer,
        explanation=(f"You call {call:g} to win a pot of {spot.pot_bb:g} + {spot.bet_bb:g}. Required equity = "
                     f"call ÷ (pot + bet + call) = {call:g} ÷ {spot.pot_bb + spot.bet_bb + call:g} = {req * 100:.1f}%."),
        detail={"required": round(req, 4)},
    )


BUILDERS = {"hand": hand_question, "outs": outs_question, "price": price_question}


def build_question(spot: BasicsSpot, seed: int) -> BasicsQuestion:
    return BUILDERS[spot.question](spot, seed)


@dataclass(frozen=True)
class BasicsGrade:
    grade: str
    answer: str
    correct: str
    explanation: str


def grade_basics(q: BasicsQuestion, chosen: str) -> BasicsGrade:
    if chosen not in q.options:
        raise ValueError("That answer wasn't one of the choices")
    return BasicsGrade(CORRECT if chosen == q.answer else WRONG, chosen, q.answer, q.explanation)
