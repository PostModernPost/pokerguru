"""Equity / pot odds drill: deals spots and computes their equity in the background.

Equity takes a second or two (PLO is slowest), so it starts as soon as a spot
is dealt and is usually done by the time the user answers. Results are cached
by spot. The seed comes from the cards, so recomputing after a server restart
gives the identical answer.
"""

from __future__ import annotations

import random
import threading
from collections import OrderedDict
from concurrent.futures import Future, ThreadPoolExecutor

from trainer import config
from trainer.game.equity import EquityResult, equity_vs_random, spot_seed
from trainer.scenarios.postflop import EquitySpot, random_equity_spot

ESTIMATE_DRILL = "equity_estimate"
DECISION_DRILL = "pot_odds_decision"


class EquityService:
    def __init__(self, iterations: int = config.EQUITY_ITERATIONS, cache_size: int = 256, workers: int = 2):
        self.iterations = iterations
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="equity")
        self._cache: OrderedDict[tuple, Future] = OrderedDict()
        self._cache_size = cache_size
        self._lock = threading.Lock()

    def _key(self, spot: EquitySpot) -> tuple:
        return (spot.game, spot.hero_cards, spot.board)

    def _compute(self, spot: EquitySpot) -> EquityResult:
        return equity_vs_random(
            spot.game, spot.hero_cards, spot.board,
            iterations=self.iterations,
            seed=spot_seed(spot.game, spot.hero_cards, spot.board),
        )

    def start(self, spot: EquitySpot) -> Future:
        """Begin computing (or reuse a cached computation)."""
        key = self._key(spot)
        with self._lock:
            fut = self._cache.get(key)
            if fut is None:
                fut = self._pool.submit(self._compute, spot)
                self._cache[key] = fut
                while len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
            else:
                self._cache.move_to_end(key)
            return fut

    def equity(self, spot: EquitySpot) -> EquityResult:
        return self.start(spot).result()

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


def next_equity_spot(service: EquityService, rng: random.Random, *,
                     games: list[str] | None = None, streets: list[str] | None = None) -> EquitySpot:
    spot = random_equity_spot(rng, games=games, streets=streets)
    service.start(spot)
    return spot
