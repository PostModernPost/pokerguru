"""Equity / pot odds drill: deals spots and computes their equity in the background.

Equity takes a second or two (PLO is slowest), so it starts as soon as a spot
is dealt and is usually done by the time the user answers. Results are cached
by spot. The seed comes from the cards, so recomputing after a server restart
gives the identical answer.
"""

from __future__ import annotations

import random
from concurrent.futures import Future

from trainer import config
from trainer.drills.background import BackgroundCache
from trainer.game.equity import EquityResult, equity_vs_random, spot_seed
from trainer.scenarios.postflop import EquitySpot, random_equity_spot

ESTIMATE_DRILL = "equity_estimate"
DECISION_DRILL = "pot_odds_decision"


class EquityService:
    def __init__(self, iterations: int = config.EQUITY_ITERATIONS, cache_size: int = 256, workers: int = 2):
        self.iterations = iterations
        self._cache: BackgroundCache = BackgroundCache(self._compute, workers=workers, size=cache_size, name="equity")

    @staticmethod
    def _key(spot: EquitySpot) -> tuple:
        return (spot.game, spot.hero_cards, spot.board)

    def _compute(self, key: tuple) -> EquityResult:
        game, hero, board = key
        return equity_vs_random(game, hero, board, iterations=self.iterations, seed=spot_seed(game, hero, board))

    def start(self, spot: EquitySpot) -> Future:
        """Begin computing (or reuse a cached computation)."""
        return self._cache.start(self._key(spot))

    def equity(self, spot: EquitySpot) -> EquityResult:
        return self._cache.get(self._key(spot))

    def shutdown(self) -> None:
        self._cache.shutdown()


def next_equity_spot(service: EquityService, rng: random.Random, *,
                     games: list[str] | None = None, streets: list[str] | None = None) -> EquitySpot:
    spot = random_equity_spot(rng, games=games, streets=streets)
    service.start(spot)
    return spot
