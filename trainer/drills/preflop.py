"""Preflop chart drill: picks the next spot and turns a chart into a spot.

Phase 1 picks uniformly: a random chart among those matching the filters,
then two random cards. Phase 5 will weight this toward weak areas.
"""

from __future__ import annotations

import random

from trainer.charts.loader import Chart, ChartLibrary
from trainer.game.dealing import deal
from trainer.scenarios.preflop import PreflopSpot, build_preflop_spot

DRILL_TYPE = "preflop_chart"


class NoMatchingChart(LookupError):
    pass


def spot_from_chart(chart: Chart, hero_cards: tuple[str, ...] | str) -> PreflopSpot:
    facing = chart.facing or {}
    return build_preflop_spot(
        game=chart.game,
        format=chart.format,
        table_size=chart.table_size,
        spot_type=chart.spot_type,
        hero_pos=chart.hero_pos,
        villain_pos=chart.villain_pos,
        hero_cards=hero_cards,
        stack_bb=chart.stack_bb,
        open_size_bb=facing.get("open_size_bb") if chart.spot_type != "rfi" else None,
        threebet_size_bb=facing.get("threebet_size_bb") if chart.spot_type == "vs_3bet" else None,
    )


def next_spot(
    library: ChartLibrary,
    rng: random.Random,
    *,
    table_sizes: list[int] | None = None,
    hero_positions: list[str] | None = None,
    spot_types: list[str] | None = None,
    game: str = "nlhe",
    format: str = "cash",
    stack_bb: float | None = 100,
) -> tuple[Chart, PreflopSpot]:
    charts = library.find(
        game=game,
        format=format,
        table_sizes=table_sizes,
        hero_positions=hero_positions,
        spot_types=spot_types,
        stack_bb=stack_bb,
    )
    if not charts:
        raise NoMatchingChart("No chart matches these filters. Try selecting more positions or spot types.")
    chart = rng.choice(charts)
    return chart, spot_from_chart(chart, deal(rng, 2))
