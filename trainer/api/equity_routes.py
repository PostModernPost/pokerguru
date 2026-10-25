"""Routes for the equity / pot odds drill (phase 2)."""

from __future__ import annotations

import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from trainer.drills.equity import (
    DECISION_DRILL,
    ESTIMATE_DRILL,
    EquityService,
    next_equity_spot,
)
from trainer.graders.equity import BUCKETS, BUCKET_IDS, bucket_label, grade_equity_answer
from trainer.progress.store import Attempt, AttemptStore
from trainer.scenarios.postflop import GAMES, STREETS, EquitySpot, build_equity_spot

GAME_LABELS = {"nlhe": "No-Limit Hold'em", "plo": "Pot-Limit Omaha"}


class EquityNext(BaseModel):
    games: list[str] = Field(default_factory=list)
    streets: list[str] = Field(default_factory=list)


class EquityAnswer(BaseModel):
    game: str
    street: str
    hero_cards: list[str]
    board: list[str]
    pot_bb: float = Field(gt=0)
    bet_bb: float = Field(gt=0)
    bucket: str
    decision: str
    response_time_ms: int | None = Field(default=None, ge=0)


def _spot_payload(spot: EquitySpot) -> dict:
    return {
        "game": spot.game,
        "game_label": GAME_LABELS[spot.game],
        "street": spot.street,
        "hero_cards": list(spot.hero_cards),
        "board": list(spot.board),
        "pot_bb": spot.pot_bb,
        "bet_bb": spot.bet_bb,
        "to_call_bb": spot.to_call_bb,
        "buckets": [{"id": b[0], "label": b[1]} for b in BUCKETS],
    }


def make_equity_router(store: AttemptStore, service: EquityService, rng: random.Random) -> APIRouter:
    router = APIRouter(prefix="/api/equity")

    @router.get("/options")
    def options():
        return {
            "games": [{"id": g, "label": GAME_LABELS[g]} for g in GAMES],
            "streets": [{"id": s, "label": s.capitalize()} for s in STREETS],
            "iterations": service.iterations,
        }

    @router.post("/next")
    def next_spot(req: EquityNext):
        bad = [g for g in req.games if g not in GAMES] + [s for s in req.streets if s not in STREETS]
        if bad:
            raise HTTPException(400, f"Unknown option(s): {bad}")
        spot = next_equity_spot(service, rng, games=req.games or None, streets=req.streets or None)
        return _spot_payload(spot)

    @router.post("/answer")
    def answer(req: EquityAnswer):
        if req.bucket not in BUCKET_IDS:
            raise HTTPException(400, f"Unknown equity range {req.bucket!r}")
        if req.decision not in ("call", "fold"):
            raise HTTPException(400, "Decision must be call or fold")
        try:
            spot = build_equity_spot(game=req.game, street=req.street, hero_cards=tuple(req.hero_cards),
                                     board=tuple(req.board), pot_bb=req.pot_bb, bet_bb=req.bet_bb)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None

        eq = service.equity(spot)
        g = grade_equity_answer(equity=eq.equity, std_error=eq.std_error, iterations=eq.iterations,
                                pot=spot.pot_bb, bet=spot.bet_bb, bucket=req.bucket, decision=req.decision)

        spot_record = spot.to_dict() | {
            "equity": eq.equity, "std_error": eq.std_error, "iterations": eq.iterations,
            "required_equity": g.required, "method": "computed: Monte Carlo vs one random hand (PokerKit)",
        }
        common = dict(
            game=spot.game, format="cash", spot=spot_record, hero_cards="".join(spot.hero_cards),
            spot_type=spot.street, hand_class=spot.hand_class,
            response_time_ms=req.response_time_ms, chart_source="computed",
        )
        store.record(Attempt(drill_type=ESTIMATE_DRILL, user_answer=req.bucket,
                             correct_answer=[g.actual_bucket], grade=g.bucket_grade, **common))
        store.record(Attempt(drill_type=DECISION_DRILL, user_answer=req.decision,
                             correct_answer=[g.best_decision], grade=g.decision_grade, **common))

        return {
            "equity": eq.equity,
            "equity_pct": f"{eq.equity * 100:.1f}%",
            "margin_pct": f"{eq.std_error * 100:.1f}%",
            "iterations": eq.iterations,
            "exact": eq.exact,
            "bucket": {"chosen": req.bucket, "chosen_label": bucket_label(req.bucket),
                       "actual": g.actual_bucket, "actual_label": bucket_label(g.actual_bucket),
                       "grade": g.bucket_grade, "explanation": g.bucket_explanation},
            "decision": {"chosen": req.decision, "best": g.best_decision, "grade": g.decision_grade,
                         "required": g.required, "required_pct": f"{g.required * 100:.1f}%",
                         "explanation": g.decision_explanation},
            "summary": store.summary(DECISION_DRILL),
        }

    return router
