import pytest

from trainer.charts.loader import ChartLibrary
from trainer.config import CHARTS_DIR
from trainer.game.hand_features import chart_context, equity_rank_all, equity_vs_random_all, features, why_this_hand
from trainer.game.hand_classes import ALL_HAND_CLASSES

LIB = ChartLibrary.from_directory(CHARTS_DIR / "nlhe" / "pokalab")


def test_equity_vs_random_sanity():
    e = equity_vs_random_all()
    idx = {h: i for i, h in enumerate(ALL_HAND_CLASSES)}
    assert e[idx["AA"]] > 0.84 and e[idx["32o"]] < 0.33
    assert e[idx["AKs"]] > e[idx["AKo"]] > e[idx["A2o"]]
    ranks = equity_rank_all()
    assert ranks["AA"] == 1 and ranks["KK"] == 2 and ranks["32o"] == 169
    assert sorted(ranks.values()) == list(range(1, 170))


@pytest.mark.parametrize("hand,needle", [
    ("AA", "pocket pair of aces"), ("TT", "high pair"), ("55", "small pair"),
    ("AKs", "broadway"), ("AKs", "suited"), ("AKo", "offsuit"), ("98s", "connected"),
    ("97s", "one-gap"), ("A5s", "wheel ace"), ("A5s", "blocker"), ("K2o", "offsuit"),
])
def test_features(hand, needle):
    assert any(needle in f for f in features(hand)), features(hand)


def test_chart_context_on_a_real_chart():
    chart = next(c for c in LIB.charts if c.spot_type == "rfi" and c.hero_pos == "UTG")
    aa = chart_context(chart, "AA")
    assert aa.play_frequency == 1.0 and aa.played_more_often == 0
    trash = chart_context(chart, "72o")
    assert trash.play_frequency == 0.0 and trash.played_more_often > 40  # UTG plays about 51 hand classes
    assert 0.15 < trash.range_share < 0.2  # UTG opens about 17.6% here
    aces = chart_context(chart, "A5s")
    assert aces.category == "suited ace"
    assert aces.weakest_played_in_category is not None


def test_why_this_hand_sentences():
    chart = next(c for c in LIB.charts if c.spot_type == "rfi" and c.hero_pos == "BTN")
    w = why_this_hand(chart, "AKs")
    assert w["equity_rank"] <= 10 and 0.6 < w["equity_vs_random"] < 0.7
    assert w["lines"][0].startswith("AKs is ")
    assert "ranking" in w["lines"][1]
    assert "BTN always plays it here" in w["lines"][2]
    w2 = why_this_hand(chart, "72o")
    assert "never plays it here" in w2["lines"][2]
