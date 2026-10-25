"""FastAPI app: JSON routes under /api, the web screens at /.

The drill is stateless on the server: /api/preflop/next sends the chart id and
hero's cards, and /api/preflop/answer sends them back with the chosen action.
The server rebuilds the spot from the chart, so a server restart (or a phone
that went to sleep) never loses the question.
"""

from __future__ import annotations

import logging
import random
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from trainer import config
from trainer.charts.loader import Chart, ChartLibrary
from trainer.drills.preflop import DRILL_TYPE, NoMatchingChart, next_spot, spot_from_chart
from trainer.game.hand_classes import grid
from trainer.game.positions import POSITIONS, SPOT_TYPES
from trainer.graders.preflop_chart import action_label, format_pct, grade
from trainer.progress.store import Attempt, AttemptStore
from trainer.scenarios.preflop import PreflopSpot

log = logging.getLogger(__name__)

SPOT_TYPE_LABELS = {
    "rfi": "Raise first in",
    "vs_open": "Facing an open",
    "vs_3bet": "Facing a 3-bet",
}


class NextRequest(BaseModel):
    table_sizes: list[int] = Field(default_factory=list)
    hero_positions: list[str] = Field(default_factory=list)
    spot_types: list[str] = Field(default_factory=list)


class AnswerRequest(BaseModel):
    chart_id: str
    hero_cards: list[str] = Field(min_length=2, max_length=2)
    action: str
    response_time_ms: int | None = Field(default=None, ge=0)


def _history_text(spot: PreflopSpot) -> list[dict]:
    out = []
    raises = 0
    for step in spot.history:
        who = "You" if step.is_hero else step.pos
        if step.action == "fold":
            text = f"{who} fold" if step.is_hero else f"{who} folds"
        else:
            raises += 1
            verb = {1: "raise", 2: "3-bet"}.get(raises, "raise")
            size = f" to {step.to_bb:g}bb" if step.to_bb is not None else ""
            text = f"{who} {verb}{size}" if step.is_hero else f"{who} {verb}s{size}"
        out.append({"pos": step.pos, "action": step.action, "to_bb": step.to_bb,
                    "is_hero": step.is_hero, "text": text})
    return out


def _seats(spot: PreflopSpot) -> list[dict]:
    """Every position in order with what it has done so far (for the table strip)."""
    last: dict[str, dict] = {}
    for step in spot.history:
        last[step.pos] = {"action": step.action, "to_bb": step.to_bb}
    seats = []
    for pos in POSITIONS[spot.table_size]:
        state = last.get(pos)
        if pos == spot.hero_pos:
            status = "hero"
        elif state is None:
            status = "waiting"
        else:
            status = state["action"]
        seats.append({
            "pos": pos,
            "status": status,
            "to_bb": state["to_bb"] if state else None,
            "blind": {"SB": config.SMALL_BLIND_BB, "BB": config.BIG_BLIND_BB}.get(pos),
        })
    return seats


def _spot_payload(chart: Chart, spot: PreflopSpot) -> dict:
    return {
        "chart_id": chart.id,
        "hero_cards": list(spot.hero_cards),
        "game": spot.game,
        "format": spot.format,
        "table_size": spot.table_size,
        "stack_bb": spot.stack_bb,
        "spot_type": spot.spot_type,
        "spot_label": SPOT_TYPE_LABELS[spot.spot_type],
        "hero_pos": spot.hero_pos,
        "villain_pos": spot.villain_pos,
        "history": _history_text(spot),
        "seats": _seats(spot),
        "pot_bb": spot.pot_bb,
        "to_call_bb": spot.to_call_bb,
        "hero_invested_bb": spot.hero_invested_bb,
        "actions": [{"id": a, "label": action_label(a, chart.spot_type)} for a in chart.actions],
        "is_sample": chart.is_sample,
        "source": chart.source,
    }


def create_app(charts_dir: str | Path = config.CHARTS_DIR,
               db_path: str | Path = config.DB_PATH,
               web_dir: str | Path = config.WEB_DIR,
               seed: int | None = None) -> FastAPI:
    library = ChartLibrary.from_directory(charts_dir)
    store = AttemptStore(db_path)
    rng = random.Random(seed)
    log.info("Loaded %d charts from %s", len(library), charts_dir)

    app = FastAPI(title="Poker Trainer")

    @app.middleware("http")
    async def no_cache(request: Request, call_next):
        # Phones cache aggressively; make sure an updated app is picked up.
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/api/options")
    def options():
        charts = library.find(game="nlhe", format="cash")
        positions: dict[int, list[str]] = {}
        for size in POSITIONS:
            have = {c.hero_pos for c in charts if c.table_size == size}
            if have:
                positions[size] = [p for p in POSITIONS[size] if p in have]
        return {
            "table_sizes": sorted(positions),
            "positions": positions,
            "spot_types": [{"id": s, "label": SPOT_TYPE_LABELS[s]}
                           for s in SPOT_TYPES if any(c.spot_type == s for c in charts)],
            "chart_count": len(charts),
            "sample_in_use": any(c.is_sample for c in charts),
            "thresholds": config.GRADE_THRESHOLDS,
        }

    @app.post("/api/preflop/next")
    def preflop_next(req: NextRequest):
        try:
            chart, spot = next_spot(
                library, rng,
                table_sizes=req.table_sizes or None,
                hero_positions=req.hero_positions or None,
                spot_types=req.spot_types or None,
            )
        except NoMatchingChart as e:
            raise HTTPException(404, str(e)) from None
        return _spot_payload(chart, spot)

    @app.post("/api/preflop/answer")
    def preflop_answer(req: AnswerRequest):
        try:
            chart = library.get(req.chart_id)
        except KeyError:
            raise HTTPException(404, f"Unknown chart {req.chart_id!r}") from None
        try:
            spot = spot_from_chart(chart, tuple(req.hero_cards))
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        if req.action not in chart.actions:
            raise HTTPException(400, f"{req.action!r} is not an option in this spot")

        result = grade(chart, spot.hand_class, req.action)
        store.record(Attempt(
            drill_type=DRILL_TYPE,
            game=spot.game,
            format=spot.format,
            spot=spot.to_dict(),
            hero_cards="".join(spot.hero_cards),
            user_answer=req.action,
            correct_answer=list(result.best_actions),
            grade=result.grade,
            table_size=spot.table_size,
            stack_bb=spot.stack_bb,
            spot_type=spot.spot_type,
            hero_pos=spot.hero_pos,
            villain_pos=spot.villain_pos,
            hand_class=spot.hand_class,
            frequencies=result.frequencies,
            chosen_frequency=result.chosen_frequency,
            response_time_ms=req.response_time_ms,
            chart_id=chart.id,
            chart_source=result.source_name,
            is_sample=chart.is_sample,
        ))

        return {
            "grade": result.grade,
            "chosen_action": result.chosen_action,
            "chosen_label": result.labels[result.chosen_action],
            "chosen_frequency": result.chosen_frequency,
            "chosen_pct": format_pct(result.chosen_frequency),
            "frequencies": [
                {"id": a, "label": result.labels[a], "freq": f, "pct": format_pct(f)}
                for a, f in result.frequencies.items()
            ],
            "best_actions": [result.labels[a] for a in result.best_actions],
            "explanation": result.explanation,
            "hand_class": result.hand_class,
            "hero_cards": list(spot.hero_cards),
            "actions": [{"id": a, "label": result.labels[a]} for a in chart.actions],
            "grid": grid(),
            "range": {h: [chart.hands[h].get(a, 0.0) for a in chart.actions] for h in chart.hands},
            "is_sample": chart.is_sample,
            "source": chart.source,
            "summary": store.summary(DRILL_TYPE),
        }

    @app.get("/api/summary")
    def summary():
        return store.summary(DRILL_TYPE)

    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")
    return app
