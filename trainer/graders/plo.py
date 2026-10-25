"""Graders for the PLO drills. Every answer is computed, nothing is looked up."""

from __future__ import annotations

import random
from dataclasses import dataclass

from trainer.game.omaha import DrawInfo, HandInfo, NutInfo, possible_hands
from trainer.graders.preflop_chart import CORRECT, WRONG

DRAW_LABELS = {
    "nut_draw": "Drawing to the nuts",
    "non_nut_draw": "Drawing to a non-nut hand",
    "none": "Neither",
}
OPTION_COUNT = 4


def quiz_options(info: NutInfo, hero, board, seed: int) -> list[str]:
    """Four hand descriptions, the nuts among them, in a seeded shuffled order.

    Distractors are the strongest other hands anyone could hold on this board,
    plus hero's own hand when it isn't the nuts (the tempting wrong answer).
    """
    others = [h.description for h in possible_hands(hero, board) if h.description != info.nuts.description]
    picks: list[str] = []
    if not info.hero_has_nuts and info.hero.description in others:
        picks.append(info.hero.description)
    for d in others:
        if len(picks) >= OPTION_COUNT - 1:
            break
        if d not in picks:
            picks.append(d)
    options = [info.nuts.description] + picks
    random.Random(seed).shuffle(options)
    return options


def _exact(chosen: str, correct: str) -> str:
    return CORRECT if chosen == correct else WRONG


@dataclass(frozen=True)
class NutGrade:
    nut_answer: str
    nut_grade: str
    has_nuts_answer: bool
    has_nuts_grade: str
    draw_answer: str | None
    draw_grade: str | None
    explanation: str


def grade_nut_answers(info: NutInfo, draw: DrawInfo | None, *, nut_choice: str,
                      has_nuts_choice: bool, draw_choice: str | None) -> NutGrade:
    draw_answer = draw_grade = None
    if draw is not None and draw.category != "has_nuts":
        if draw_choice not in DRAW_LABELS:
            raise ValueError("A draw answer is required on this spot")
        draw_answer = draw.category
        draw_grade = _exact(draw_choice, draw.category)
    return NutGrade(
        nut_answer=info.nuts.description,
        nut_grade=_exact(nut_choice, info.nuts.description),
        has_nuts_answer=info.hero_has_nuts,
        has_nuts_grade=_exact(str(has_nuts_choice), str(info.hero_has_nuts)),
        draw_answer=draw_answer,
        draw_grade=draw_grade,
        explanation=explain_nuts(info, draw),
    )


def _cards_text(h: HandInfo) -> str:
    return " ".join(h.cards)


def explain_nuts(info: NutInfo, draw: DrawInfo | None) -> str:
    parts = [f"The nuts is {info.nuts.description.lower()} ({_cards_text(info.nuts)})."]
    if info.blocked_hand:
        parts.append(
            f"The board allows {info.blocked_hand.description.lower()}, but your cards block it: "
            "nobody else can hold what you hold."
        )
    if info.hero_has_nuts:
        parts.append(f"You have it: {info.hero.description.lower()} ({_cards_text(info.hero)}).")
    else:
        parts.append(f"You have {info.hero.description.lower()} ({_cards_text(info.hero)}).")
    if draw is not None and draw.category != "has_nuts":
        n_nut, n_imp = len(draw.nut_outs), len(draw.improving_outs)
        if draw.category == "nut_draw":
            parts.append(
                f"Next card: {n_nut} of your {n_imp} improving cards make the nuts "
                f"({' '.join(draw.nut_outs)})."
            )
        elif draw.category == "non_nut_draw":
            parts.append(
                f"Next card: {n_imp} cards give you a straight or better ({' '.join(draw.improving_outs)}), "
                "but none of them makes the nuts."
            )
        else:
            parts.append("No single next card gives you a straight or better.")
    return " ".join(parts)


# ---------- pot-limit sizing ----------

@dataclass(frozen=True)
class PotLimitGrade:
    grade: str
    answer: float
    correct: float
    explanation: str


def _n(x: float) -> str:
    return f"{x:g}"


def grade_pot_limit(*, pot: float, largest_bet: float, hero_in: float, to_call: float,
                    max_raise_to: float, answer: float) -> PotLimitGrade:
    grade = CORRECT if abs(answer - max_raise_to) < 1e-9 else WRONG
    after_call = pot + to_call
    if largest_bet == 0:
        text = (f"Nobody has bet, so the pot is {_n(pot)} and the most you can bet is the pot: "
                f"{_n(max_raise_to)}.")
    else:
        text = (f"Pot including all bets: {_n(pot)}. To call: {_n(largest_bet)} - {_n(hero_in)} = "
                f"{_n(to_call)}. After your call the pot is {_n(after_call)}, and you may raise by "
                f"that much on top: {_n(largest_bet)} + {_n(after_call)} = raise to {_n(max_raise_to)}.")
    return PotLimitGrade(grade=grade, answer=answer, correct=max_raise_to, explanation=text)
