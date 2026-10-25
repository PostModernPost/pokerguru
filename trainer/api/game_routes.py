"""Routes for the game mode (phase 11): a continuous simulated cash game with feedback."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from trainer.charts.loader import ChartLibrary
from trainer.gamemode.bots import PRESETS
from trainer.gamemode.session import GameConfig, Session
from trainer.progress.store import AttemptStore


class NewGame(BaseModel):
    step: bool = False
    players: int = Field(default=9, ge=2, le=9)
    small_blind: int = Field(default=1, ge=1)
    big_blind: int = Field(default=2, ge=2)
    buy_in_bb: int = Field(default=100, ge=20, le=500)
    bots: str = "standard"
    feedback: bool = True
    attention: bool = True
    seed: int | None = None


class Act(BaseModel):
    session: str
    action: str  # fold | check | call | raise
    amount: int | None = Field(default=None, ge=0)
    step: bool = False  # True: bots act one at a time via /step so the screen can animate them


class SessionRef(BaseModel):
    session: str
    step: bool = False


def make_game_router(store: AttemptStore, library: ChartLibrary, seed: int | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/game")
    sessions: dict[str, Session] = {}

    def get(sid: str) -> Session:
        s = sessions.get(sid)
        if s is None:
            raise HTTPException(404, "No such game session (the server may have restarted). Start a new game.")
        return s

    @router.get("/options")
    def options():
        return {"bots": [{"id": k, "label": {"standard": "Standard", "loose": "Loose (calls too much)"}[k]} for k in PRESETS],
                "players": list(range(2, 10)), "defaults": GameConfig().__dict__}

    @router.post("/new")
    def new_game(req: NewGame):
        if req.small_blind > req.big_blind:
            raise HTTPException(400, "small blind must not exceed the big blind")
        cfg = GameConfig(**req.model_dump(exclude={"step"}))
        if cfg.seed is None and seed is not None:
            cfg.seed = seed + len(sessions)
        try:
            s = Session(cfg, library, store)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        s.step_limit = 0 if req.step else None
        sessions[s.id] = s
        if len(sessions) > 20:  # single-user app; keep memory bounded
            oldest = next(iter(sessions))
            if oldest != s.id:
                del sessions[oldest]
        s.start_hand()
        return s.state()

    @router.post("/state")
    def state(req: SessionRef):
        return get(req.session).state()

    @router.post("/act")
    def act(req: Act):
        s = get(req.session)
        if req.action not in ("fold", "check", "call", "raise"):
            raise HTTPException(400, "action must be fold, check, call or raise")
        s.step_limit = 0 if req.step else None
        try:
            s.hero_act(req.action, req.amount)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        return s.state()

    @router.post("/step")
    def step(req: SessionRef):
        s = get(req.session)
        s.step()
        return s.state()

    @router.post("/next")
    def next_hand(req: SessionRef):
        s = get(req.session)
        if s.hand is not None and not s.hand.finished:
            raise HTTPException(400, "the current hand is not over")
        s.step_limit = 0 if req.step else None
        s.start_hand()
        return s.state()

    return router
