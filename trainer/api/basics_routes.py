"""Routes for the Basics drill (phase 8): name your hand, count outs, know the price."""

from __future__ import annotations

import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from trainer.advice.library import AdviceLibrary
from trainer.game.equity import spot_seed
from trainer.graders.basics import build_question, grade_basics
from trainer.progress.store import Attempt, AttemptStore
from trainer.scenarios.basics import QUESTIONS, BasicsSpot, build_basics_spot, random_basics_spot

DRILL_TYPES = {"hand": "basics_hand", "outs": "basics_outs", "price": "basics_price"}
QUESTION_LABELS = {"hand": "What's my hand?", "outs": "How many outs?", "price": "What's the price?"}
GAME_LABELS = {"nlhe": "Hold'em", "plo": "Omaha"}


class BasicsNext(BaseModel):
    questions: list[str] = Field(default_factory=list)
    games: list[str] = Field(default_factory=list)


class BasicsAnswer(BaseModel):
    spot: dict
    answer: str
    response_time_ms: int | None = Field(default=None, ge=0)


def _seed(spot: BasicsSpot) -> int:
    return spot_seed(f"basics-{spot.question}-{spot.game}", spot.hero_cards, spot.board)


def _rebuild(d: dict) -> BasicsSpot:
    try:
        return build_basics_spot(question=d["question"], game=d["game"], street=d["street"],
                                 hero_cards=tuple(d["hero_cards"]), board=tuple(d["board"]),
                                 pot_bb=d.get("pot_bb"), bet_bb=d.get("bet_bb"))
    except (KeyError, TypeError, ValueError) as e:
        raise HTTPException(400, f"Bad spot: {e}") from None


def make_basics_router(store: AttemptStore, rng: random.Random, advice: AdviceLibrary | None = None) -> APIRouter:
    advice = advice or AdviceLibrary([])
    router = APIRouter(prefix="/api/basics")

    @router.get("/options")
    def options():
        return {"questions": [{"id": q, "label": QUESTION_LABELS[q]} for q in QUESTIONS],
                "games": [{"id": g, "label": GAME_LABELS[g]} for g in GAME_LABELS]}

    @router.post("/next")
    def next_spot(req: BasicsNext):
        bad = [q for q in req.questions if q not in QUESTIONS] + [g for g in req.games if g not in GAME_LABELS]
        if bad:
            raise HTTPException(400, f"Unknown option(s): {bad}")
        spot = random_basics_spot(rng, questions=req.questions or None, games=req.games or None)
        q = build_question(spot, _seed(spot))
        return {"spot": spot.to_dict(), "question_label": QUESTION_LABELS[spot.question],
                "game_label": GAME_LABELS[spot.game], "prompt": q.prompt, "options": q.options}

    @router.post("/answer")
    def answer(req: BasicsAnswer):
        spot = _rebuild(req.spot)
        q = build_question(spot, _seed(spot))
        try:
            g = grade_basics(q, req.answer)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        record = spot.to_dict() | {"method": "computed: PokerKit evaluation / exact counting / pot odds formula"}
        store.record(Attempt(
            drill_type=DRILL_TYPES[spot.question], game=spot.game, format="cash", spot=record,
            hero_cards="".join(spot.hero_cards), spot_type=spot.street, user_answer=req.answer,
            correct_answer=[g.correct], grade=g.grade, response_time_ms=req.response_time_ms,
            chart_source="computed",
        ))
        street_for_tips = spot.street if spot.street != "river" else None
        tips = advice.matching(drill="basics", game=spot.game, format="cash", street=street_for_tips) \
            if spot.question in ("outs", "price") else []
        return {
            "grade": g.grade, "answer": g.answer, "correct": g.correct, "explanation": g.explanation,
            "detail": q.detail, "summary": store.summary(DRILL_TYPES[spot.question]),
            "tips": [t.public() for t in tips],
        }

    return router
