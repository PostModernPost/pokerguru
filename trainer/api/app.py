"""FastAPI app: JSON routes under /api, the web screens at /.

The drill is stateless on the server: /api/preflop/next sends the chart id and
hero's cards, and /api/preflop/answer sends them back with the chosen action.
The server rebuilds the spot from the chart, so a server restart (or a phone
that went to sleep) never loses the question.
"""

from __future__ import annotations

import logging
import random
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from trainer import config
from trainer.advice.library import AdviceLibrary
from trainer.api.basics_routes import make_basics_router
from trainer.api.game_routes import make_game_router
from trainer.version import current_version
from trainer.api.equity_routes import make_equity_router
from trainer.api.plo_routes import make_plo_router
from trainer.charts.loader import Chart, ChartLibrary
from trainer.drills.equity import EquityService
from trainer.drills.plo import NutsService
from trainer.drills.preflop import DRILL_TYPE, LeakProfile, NoMatchingChart, next_spot, review_key, spot_from_chart
from trainer.game.hand_classes import HAND_CATEGORIES, grid, hand_category
from trainer.game.hand_features import why_this_hand
from trainer.game.positions import POSITIONS, SPOT_TYPES
from trainer.graders.preflop_chart import action_label, format_pct, grade
from trainer.progress.store import Attempt, AttemptStore
from trainer.scenarios.preflop import PreflopSpot

log = logging.getLogger(__name__)

SPOT_TYPE_LABELS = {
    "rfi": "Raise first in",
    "vs_open": "Facing an open",
    "vs_3bet": "Facing a 3-bet",
    "push": "Push or fold",
    "vs_push": "Facing a shove",
}
FORMAT_LABELS = {"cash": "Cash", "tournament": "Tournament"}


class NextRequest(BaseModel):
    formats: list[str] = Field(default_factory=list)
    table_sizes: list[int] = Field(default_factory=list)
    hero_positions: list[str] = Field(default_factory=list)
    spot_types: list[str] = Field(default_factory=list)
    stacks: list[float] = Field(default_factory=list)
    leaks_only: bool = False
    include_samples: bool = False


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
        elif spot.spot_type == "vs_push":
            text = f"{who} shoves all-in for {step.to_bb:g}bb"
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


def _spot_payload(chart: Chart, spot: PreflopSpot, reason: str = "random") -> dict:
    return {
        "reason": reason,
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
               seed: int | None = None,
               equity_iterations: int = config.EQUITY_ITERATIONS,
               advice_path: str | Path | None = None) -> FastAPI:
    library = ChartLibrary.from_directory(charts_dir)
    advice = AdviceLibrary.load(advice_path) if advice_path else AdviceLibrary.load()
    log.info("Advice library: %d verified, %d contested, %d unverified", len(advice.verified()),
             len(advice.contested()), len(advice.tips) - len(advice.verified()) - len(advice.contested()))
    store = AttemptStore(db_path)
    rng = random.Random(seed)
    log.info("Loaded %d charts from %s", len(library), charts_dir)

    equity_service = EquityService(iterations=equity_iterations)
    nuts_service = NutsService()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        equity_service.shutdown()
        nuts_service.shutdown()

    app = FastAPI(title="Poker Trainer", lifespan=lifespan)

    @app.middleware("http")
    async def no_cache(request: Request, call_next):
        # Phones cache aggressively; make sure an updated app is picked up.
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache"
        return response

    running_version = current_version()

    @app.get("/api/version")
    def version():
        return {"version": running_version}

    @app.post("/api/shutdown")
    def shutdown(request: Request):
        """Lets a newer launcher replace this server. Only from this computer."""
        if request.client is None or request.client.host not in ("127.0.0.1", "::1"):
            raise HTTPException(403, "only from this computer")
        import os
        import threading
        threading.Timer(0.5, lambda: os._exit(0)).start()
        return {"ok": True}

    @app.get("/api/chart/{chart_id}")
    def chart_view(chart_id: str):
        """A chart's full range for display (the game mode's 'show chart' pop-up)."""
        try:
            chart = library.get(chart_id)
        except KeyError:
            raise HTTPException(404, f"No chart {chart_id!r}") from None
        return {
            "id": chart.id, "spot_type": chart.spot_type, "spot_label": SPOT_TYPE_LABELS[chart.spot_type],
            "hero_pos": chart.hero_pos, "villain_pos": chart.villain_pos, "table_size": chart.table_size,
            "actions": [{"id": a, "label": action_label(a, chart.spot_type)} for a in chart.actions],
            "grid": grid(),
            "range": {h: [chart.hands[h].get(a, 0.0) for a in chart.actions] for h in chart.hands},
            "deal_weights": chart.deal_weights, "source": chart.source, "is_sample": chart.is_sample,
        }

    @app.get("/api/options")
    def options(include_samples: bool = False):
        charts = library.find(game="nlhe", include_samples=include_samples)
        positions: dict[int, list[str]] = {}
        for size in POSITIONS:
            have = {c.hero_pos for c in charts if c.table_size == size}
            if have:
                positions[size] = [p for p in POSITIONS[size] if p in have]
        # Which table sizes / stacks / spot types exist for each format, so the
        # filter screen can hide combinations that have no chart.
        per_format = {}
        for fmt in FORMAT_LABELS:
            fc = [c for c in charts if c.format == fmt]
            if fc:
                per_format[fmt] = {
                    "table_sizes": sorted({c.table_size for c in fc}),
                    "stacks": sorted({c.stack_bb for c in fc}),
                    "spot_types": [s for s in SPOT_TYPES if any(c.spot_type == s for c in fc)],
                }
        return {
            "formats": [{"id": f, "label": FORMAT_LABELS[f]} for f in per_format],
            "per_format": per_format,
            "table_sizes": sorted(positions),
            "positions": positions,
            "stacks": sorted({c.stack_bb for c in charts}),
            "spot_types": [{"id": s, "label": SPOT_TYPE_LABELS[s]}
                           for s in SPOT_TYPES if any(c.spot_type == s for c in charts)],
            "chart_count": len(charts),
            "sample_in_use": any(c.is_sample for c in charts),
            "sample_count": sum(c.is_sample for c in library.find(game="nlhe")),
            "thresholds": config.GRADE_THRESHOLDS,
        }

    @app.post("/api/preflop/next")
    def preflop_next(req: NextRequest):
        try:
            chart, spot, reason = next_spot(
                library, rng,
                formats=req.formats or None,
                table_sizes=req.table_sizes or None,
                hero_positions=req.hero_positions or None,
                spot_types=req.spot_types or None,
                stacks=req.stacks or None,
                store=store,
                leaks_only=req.leaks_only,
                include_samples=req.include_samples,
            )
        except NoMatchingChart as e:
            raise HTTPException(404, str(e)) from None
        return _spot_payload(chart, spot, reason)

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
        store.schedule_review(DRILL_TYPE, review_key(chart.id, spot.hand_class), result.grade)

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
            "why": why_this_hand(chart, spot.hand_class),
            "hand_class": result.hand_class,
            "hero_cards": list(spot.hero_cards),
            "actions": [{"id": a, "label": result.labels[a]} for a in chart.actions],
            "grid": grid(),
            "range": {h: [chart.hands[h].get(a, 0.0) for a in chart.actions] for h in chart.hands},
            "deal_weights": chart.deal_weights,
            "is_sample": chart.is_sample,
            "source": chart.source,
            "summary": store.summary(DRILL_TYPE),
            "tips": [t.public() for t in advice.matching(
                drill="preflop_chart", game=spot.game, format=spot.format, position=spot.hero_pos,
                spot_type=spot.spot_type, street="preflop", hand_category=hand_category(spot.hand_class),
                stack_bb=spot.stack_bb)],
        }

    @app.get("/api/advice")
    def advice_summary():
        """Counts plus the contested items with their evidence (never shown as advice)."""
        return {
            "verified": len(advice.verified()),
            "contested": [dict(t.public(), evidence=t.evidence()) for t in advice.contested()],
            "unverified": len([t for t in advice.tips if t.status == "unverified"]),
        }

    @app.get("/api/advice/{tip_id}")
    def advice_evidence(tip_id: str):
        try:
            tip = advice.get(tip_id)
        except KeyError:
            raise HTTPException(404, "Unknown tip") from None
        return dict(tip.public(), evidence=tip.evidence())

    @app.get("/api/summary")
    def summary(drill_type: str = Query(DRILL_TYPE)):
        return store.summary(drill_type)

    @app.get("/api/stats")
    def stats():
        """Everything the Stats screen shows."""
        drills = {
            "basics_hand": "Basics: what's my hand",
            "basics_outs": "Basics: how many outs",
            "basics_price": "Basics: what's the price",
            "preflop_chart": "Preflop: chart decision",
            "equity_estimate": "Equity: estimate",
            "pot_odds_decision": "Equity: call or fold",
            "plo_nut_hand": "Nuts: name the nuts",
            "plo_has_nuts": "Nuts: do you have it",
            "plo_nut_draw": "Nuts: your draw",
            "plo_pot_limit": "Pot limit: max raise",
        }
        by_drill = {r["key"]: r for r in store.breakdown("drill_type")}
        cats: dict[str, dict] = {}
        for r in store.breakdown("hand_class", DRILL_TYPE):
            c = cats.setdefault(hand_category(r["key"]), {"key": None, "total": 0, "correct": 0, "acceptable": 0, "wrong": 0})
            for k in ("total", "correct", "acceptable", "wrong"):
                c[k] += r[k]
        cat_rows = []
        for name in HAND_CATEGORIES:
            if name in cats:
                c = cats[name]
                c["key"] = name
                c["accuracy"] = round(c["correct"] / c["total"], 4)
                c["score"] = round((c["correct"] + 0.5 * c["acceptable"]) / c["total"], 4)
                cat_rows.append(c)
        profile = LeakProfile.from_store(store)
        return {
            "drills": [dict(by_drill[d], label=label) for d, label in drills.items() if d in by_drill],
            "preflop": {
                "by_position": store.breakdown("hero_pos", DRILL_TYPE),
                "by_spot_type": [dict(r, label=SPOT_TYPE_LABELS.get(r["key"], r["key"]))
                                 for r in store.breakdown("spot_type", DRILL_TYPE)],
                "by_category": cat_rows,
                "by_format": store.breakdown("format", DRILL_TYPE),
                "recent": store.recent_grades(DRILL_TYPE, 30),
                "reviews": store.review_count(DRILL_TYPE),
                "leaks": profile.summary(),
            },
            "equity": {
                "by_street": store.breakdown("spot_type", "pot_odds_decision"),
                "by_game": store.breakdown("game", "pot_odds_decision"),
            },
            "nuts": {"by_street": store.breakdown("spot_type", "plo_nut_hand")},
            "pot_limit": {"by_stage": store.breakdown("spot_type", "plo_pot_limit")},
            "total_attempts": sum(r["total"] for r in by_drill.values()),
            "thresholds": {"min_attempts": 5, "weak_score": 0.7},
        }

    app.include_router(make_equity_router(store, equity_service, rng, advice))
    app.include_router(make_plo_router(store, nuts_service, rng, advice))
    app.include_router(make_basics_router(store, rng, advice))
    app.include_router(make_game_router(store, library, seed))

    app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")
    return app
