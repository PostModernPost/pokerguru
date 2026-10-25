import random

import pytest

from trainer.charts.loader import ChartLibrary
from trainer.config import CHARTS_DIR
from trainer.drills.preflop import NoMatchingChart, next_spot, spot_from_chart

LIB = ChartLibrary.from_directory(CHARTS_DIR / "nlhe" / "sample")


def test_next_spot_respects_filters():
    rng = random.Random(0)
    for _ in range(200):
        chart, spot = next_spot(LIB, rng, table_sizes=[6], spot_types=["vs_3bet"])
        assert chart.table_size == 6 and chart.spot_type == "vs_3bet"
        assert spot.hero_pos == chart.hero_pos and spot.villain_pos == chart.villain_pos
        assert spot.threebet_size_bb == chart.facing["threebet_size_bb"]
        assert spot.pot_bb is not None


def test_next_spot_covers_every_matching_chart():
    rng = random.Random(0)
    want = {c.id for c in LIB.find(table_sizes=[9])}
    seen = {next_spot(LIB, rng, table_sizes=[9])[0].id for _ in range(2000)}
    assert seen == want


def test_no_matching_chart():
    with pytest.raises(NoMatchingChart):
        next_spot(LIB, random.Random(0), hero_positions=["UTG1"], table_sizes=[6])


def test_spot_from_chart_is_reproducible():
    chart = LIB.find(spot_types=["vs_open"])[0]
    assert spot_from_chart(chart, "AsKd") == spot_from_chart(chart, ("As", "Kd"))
