"""PLO drills: nut awareness (computed in the background) and pot-limit sizing."""

from __future__ import annotations

import random
from dataclasses import dataclass

from trainer.drills.background import BackgroundCache
from trainer.game.omaha import DrawInfo, NutInfo, draw_info, nut_info
from trainer.scenarios.plo import NutSpot, PotLimitSpot, random_nut_spot, random_pot_limit_spot

NUT_HAND_DRILL = "plo_nut_hand"
HAS_NUTS_DRILL = "plo_has_nuts"
NUT_DRAW_DRILL = "plo_nut_draw"
POT_LIMIT_DRILL = "plo_pot_limit"


@dataclass(frozen=True)
class NutAnalysis:
    info: NutInfo
    draw: DrawInfo | None  # None on the river


def _analyse(key: tuple[tuple[str, ...], tuple[str, ...]]) -> NutAnalysis:
    hero, board = key
    info = nut_info(hero, board)
    draw = draw_info(hero, board) if len(board) < 5 else None
    return NutAnalysis(info, draw)


class NutsService:
    def __init__(self, workers: int = 2):
        self._cache: BackgroundCache = BackgroundCache(_analyse, workers=workers, name="nuts")

    @staticmethod
    def _key(spot: NutSpot):
        return (spot.hero_cards, spot.board)

    def start(self, spot: NutSpot) -> None:
        self._cache.start(self._key(spot))

    def analysis(self, spot: NutSpot) -> NutAnalysis:
        return self._cache.get(self._key(spot))

    def shutdown(self) -> None:
        self._cache.shutdown()


def next_nut_spot(service: NutsService, rng: random.Random, *, streets: list[str] | None = None) -> NutSpot:
    spot = random_nut_spot(rng, streets=streets)
    service.start(spot)
    return spot


def next_pot_limit_spot(rng: random.Random, *, stages: list[str] | None = None) -> PotLimitSpot:
    return random_pot_limit_spot(rng, stages=stages)
