"""Routes for the PLO drills (phase 3): nut awareness and pot-limit sizing."""

from __future__ import annotations

import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from trainer.advice.library import AdviceLibrary
from trainer.drills.plo import (
    HAS_NUTS_DRILL,
    NUT_DRAW_DRILL,
    NUT_HAND_DRILL,
    POT_LIMIT_DRILL,
    NutsService,
    next_nut_spot,
    next_pot_limit_spot,
)
from trainer.game.equity import spot_seed
from trainer.game.omaha import nut_info
from trainer.graders.plo import DRAW_LABELS, grade_nut_answers, grade_pot_limit, quiz_options
from trainer.progress.store import Attempt, AttemptStore
from trainer.scenarios.plo import (
    NUT_STREETS,
    build_nut_spot,
    build_postflop_pot_limit_spot,
    build_preflop_pot_limit_spot,
)


class NutsNext(BaseModel):
    streets: list[str] = Field(default_factory=list)


class NutsAnswer(BaseModel):
    street: str
    hero_cards: list[str]
    board: list[str]
    nut_choice: str
    has_nuts: bool
    draw_choice: str | None = None
    response_time_ms: int | None = Field(default=None, ge=0)


class PotLimitNext(BaseModel):
    stages: list[str] = Field(default_factory=list)


class PotLimitAnswer(BaseModel):
    spot: dict  # the spot exactly as /next returned it
    answer: float = Field(ge=0)
    response_time_ms: int | None = Field(default=None, ge=0)


def _rebuild_pot_limit_spot(d: dict):
    """Recompute the spot from what the client sent, so the answer can't be tampered with."""
    try:
        if d["stage"] == "preflop":
            actions = []
            for h in d["history"]:
                if h["action"] in ("fold", "check", "call"):
                    actions.append((h["pos"], h["action"]))
                else:
                    actions.append((h["pos"], f"raise:{h['to']}"))
            return build_preflop_pot_limit_spot(small_blind=d["small_blind"], big_blind=d["big_blind"],
                                                hero_pos=d["hero_pos"], actions=actions)
        bets = [h for h in d["history"] if h["action"] == "bet"]
        callers = sum(1 for h in d["history"] if h["action"] == "call")
        return build_postflop_pot_limit_spot(
            pot_before=d["pot_before_round"], bet=bets[0]["to"] if bets else None, callers=callers,
            small_blind=d["small_blind"], big_blind=d["big_blind"], hero_pos=d.get("hero_pos", "BTN"))
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(400, f"Bad spot: {e}") from None


def make_plo_router(store: AttemptStore, nuts: NutsService, rng: random.Random,
                    advice: AdviceLibrary | None = None) -> APIRouter:
    advice = advice or AdviceLibrary([])
    router = APIRouter(prefix="/api/plo")

    # ---- nut awareness ----

    @router.get("/nuts/options")
    def nuts_options():
        return {"streets": [{"id": s, "label": s.capitalize()} for s in NUT_STREETS],
                "draw_options": [{"id": k, "label": v} for k, v in DRAW_LABELS.items()]}

    @router.post("/nuts/next")
    def nuts_next(req: NutsNext):
        bad = [s for s in req.streets if s not in NUT_STREETS]
        if bad:
            raise HTTPException(400, f"Unknown street(s): {bad}")
        spot = next_nut_spot(nuts, rng, streets=req.streets or None)
        # The full analysis (draws) runs in the background; the quiz choices only need the
        # quick part, so compute that now (about 60 ms) rather than making the user wait later.
        info = nut_info(spot.hero_cards, spot.board)
        options = quiz_options(info, spot.hero_cards, spot.board, spot_seed("plo", spot.hero_cards, spot.board))
        return {"street": spot.street, "hero_cards": list(spot.hero_cards), "board": list(spot.board),
                "options": options, "asks_draw": spot.street != "river"}

    @router.post("/nuts/answer")
    def nuts_answer(req: NutsAnswer):
        try:
            spot = build_nut_spot(street=req.street, hero_cards=tuple(req.hero_cards), board=tuple(req.board))
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        if req.draw_choice is not None and req.draw_choice not in DRAW_LABELS:
            raise HTTPException(400, f"Unknown draw answer {req.draw_choice!r}")
        a = nuts.analysis(spot)
        options = quiz_options(a.info, spot.hero_cards, spot.board, spot_seed("plo", spot.hero_cards, spot.board))
        if req.nut_choice not in options:
            raise HTTPException(400, "That hand wasn't one of the choices")
        try:
            g = grade_nut_answers(a.info, a.draw, nut_choice=req.nut_choice,
                                  has_nuts_choice=req.has_nuts, draw_choice=req.draw_choice)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None

        record = spot.to_dict() | {"nuts": a.info.nuts.description, "hero_hand": a.info.hero.description,
                                   "method": "computed: enumerated every holding, PokerKit evaluation"}
        common = dict(game="plo", format="cash", spot=record, hero_cards="".join(spot.hero_cards),
                      spot_type=spot.street, response_time_ms=req.response_time_ms, chart_source="computed")
        store.record(Attempt(drill_type=NUT_HAND_DRILL, user_answer=req.nut_choice,
                             correct_answer=[g.nut_answer], grade=g.nut_grade, **common))
        store.record(Attempt(drill_type=HAS_NUTS_DRILL, user_answer=str(req.has_nuts).lower(),
                             correct_answer=[str(g.has_nuts_answer).lower()], grade=g.has_nuts_grade, **common))
        if g.draw_answer is not None:
            store.record(Attempt(drill_type=NUT_DRAW_DRILL, user_answer=req.draw_choice,
                                 correct_answer=[g.draw_answer], grade=g.draw_grade, **common))

        return {
            "nut_hand": {"chosen": req.nut_choice, "correct": g.nut_answer, "grade": g.nut_grade,
                         "cards": list(a.info.nuts.cards)},
            "has_nuts": {"chosen": req.has_nuts, "correct": g.has_nuts_answer, "grade": g.has_nuts_grade},
            "draw": None if g.draw_answer is None else {
                "chosen": req.draw_choice, "chosen_label": DRAW_LABELS[req.draw_choice],
                "correct": g.draw_answer, "correct_label": DRAW_LABELS[g.draw_answer], "grade": g.draw_grade,
                "nut_outs": list(a.draw.nut_outs), "improving_outs": list(a.draw.improving_outs),
            },
            "hero_hand": {"description": a.info.hero.description, "cards": list(a.info.hero.cards)},
            "blocked_hand": None if a.info.blocked_hand is None else a.info.blocked_hand.description,
            "explanation": g.explanation,
            "summary": store.summary(NUT_HAND_DRILL),
            "tips": [t.public() for t in advice.matching(drill="nuts", game="plo", street=spot.street)],
        }

    # ---- pot-limit sizing ----

    @router.get("/potlimit/options")
    def pot_limit_options():
        return {"stages": [{"id": "preflop", "label": "Preflop"}, {"id": "postflop", "label": "Postflop"}]}

    @router.post("/potlimit/next")
    def pot_limit_next(req: PotLimitNext):
        bad = [s for s in req.stages if s not in ("preflop", "postflop")]
        if bad:
            raise HTTPException(400, f"Unknown stage(s): {bad}")
        spot = next_pot_limit_spot(rng, stages=req.stages or None)
        d = spot.to_dict()
        # Never send the answer with the question.
        for k in ("pot", "largest_bet", "to_call", "max_raise_to"):
            d.pop(k)
        return d

    @router.post("/potlimit/answer")
    def pot_limit_answer(req: PotLimitAnswer):
        spot = _rebuild_pot_limit_spot(req.spot)
        g = grade_pot_limit(pot=spot.pot, largest_bet=spot.largest_bet, hero_in=spot.hero_in,
                            to_call=spot.to_call, max_raise_to=spot.max_raise_to, answer=req.answer)
        store.record(Attempt(
            drill_type=POT_LIMIT_DRILL, game="plo", format="cash", spot=spot.to_dict(), hero_cards="",
            spot_type=spot.stage, user_answer=f"{req.answer:g}", correct_answer=[f"{spot.max_raise_to:g}"],
            grade=g.grade, response_time_ms=req.response_time_ms, chart_source="computed",
        ))
        return {
            "grade": g.grade, "answer": req.answer, "correct": spot.max_raise_to,
            "pot": spot.pot, "largest_bet": spot.largest_bet, "hero_in": spot.hero_in, "to_call": spot.to_call,
            "explanation": g.explanation,
            "summary": store.summary(POT_LIMIT_DRILL),
            "tips": [t.public() for t in advice.matching(drill="pot_limit", game="plo",
                                                          street="preflop" if spot.stage == "preflop" else "flop")],
        }

    return router
