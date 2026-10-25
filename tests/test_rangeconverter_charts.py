"""The real 9-handed charts (RangeConverter import) and the deal-weights feature they use."""
import random

import pytest

from trainer.charts.loader import ChartError, ChartLibrary, chart_from_dict
from trainer.config import CHARTS_DIR
from trainer.drills.preflop import deal_for_chart, next_spot
from trainer.game.hand_classes import ALL_HAND_CLASSES, combo_count, hand_class_of
from trainer.game.positions import POSITIONS, acts_before

LIB = ChartLibrary.from_directory(CHARTS_DIR / "nlhe" / "rangeconverter")
SEATS = POSITIONS[9]


def test_every_nine_handed_spot_has_a_real_chart():
    have = {(c.spot_type, c.hero_pos, c.villain_pos) for c in LIB.charts}
    for hero in SEATS[:-1]:
        assert ("rfi", hero, None) in have
    for hero in SEATS:
        for villain in SEATS:
            if villain != hero and acts_before(9, villain, hero):
                assert ("vs_open", hero, villain) in have, (hero, villain)
            if villain != hero and hero != "BB" and acts_before(9, hero, villain):
                assert ("vs_3bet", hero, villain) in have, (hero, villain)
    assert len(LIB.charts) == 80
    assert not any(c.is_sample for c in LIB.charts)
    assert {c.source["status"] for c in LIB.charts} <= {"verified", "contested", "single_source"}


def test_rfi_charts_make_sense():
    rfi = {c.hero_pos: c for c in LIB.charts if c.spot_type == "rfi"}
    width = {p: sum((1 - c.hands[h].get("fold", 0)) * combo_count(h) for h in ALL_HAND_CLASSES) / 1326 for p, c in rfi.items()}
    assert 0.09 < width["UTG"] < 0.12 and 0.38 < width["BTN"] < 0.43  # the chart prints 10.09% and 40.49%
    for a, b in zip(SEATS[:-2], SEATS[1:-2]):
        assert width[a] <= width[b] + 0.005, (a, b)
    for c in rfi.values():
        assert c.hands["AA"] == {"raise_3": 1.0} and c.hands["72o"] == {"fold": 1.0}


def test_vs_3bet_charts_only_deal_opened_hands():
    c = next(x for x in LIB.charts if x.spot_type == "vs_3bet" and x.hero_pos == "UTG" and x.villain_pos == "BTN")
    assert c.deal_weights is not None
    assert c.deal_weights["AA"] == 1.0 and c.deal_weights["72o"] == 0.0
    rng = random.Random(3)
    for _ in range(300):
        cards = deal_for_chart(rng, c)
        assert c.deal_weights[hand_class_of(''.join(cards))] > 0
    # the drill engine uses it too
    for _ in range(100):
        chart, spot, _ = next_spot(LIB, rng, spot_types=["vs_3bet"], hero_positions=["UTG"])
        assert chart.deal_weights[spot.hand_class] > 0
    # a weighted chart with a category restriction stays inside the category when it can
    pairs = [h for h in ALL_HAND_CLASSES if h[0] == h[1]]
    for _ in range(50):
        assert hand_class_of(''.join(deal_for_chart(rng, c, pairs))) in pairs


def test_sizes_match_the_source():
    for c in LIB.charts:
        if c.spot_type == "rfi":
            assert c.actions == ("fold", "raise_3")
        elif c.spot_type == "vs_open":
            size = {"SB": "raise_12", "BB": "raise_13"}.get(c.hero_pos, "raise_10")
            assert c.actions[0] == "fold" and c.actions[-1] == size and set(c.actions) <= {"fold", "call", size}
            assert c.facing == {"open_size_bb": 3.0}
        else:
            four = "raise_28" if c.villain_pos == "BB" else "raise_26"
            assert c.actions[:3] == ("fold", "call", four) and c.actions[3:] in ((), ("allin",))
            assert c.facing["threebet_size_bb"] == {"SB": 12.0, "BB": 13.0}.get(c.villain_pos, 10.0)


def _chart(**over):
    base = {
        "id": "t", "game": "nlhe", "format": "cash", "table_size": 6, "stack_bb": 100,
        "spot": {"type": "vs_3bet", "hero_pos": "CO", "villain_pos": "BTN", "facing": {"open_size_bb": 2.5, "threebet_size_bb": 8}},
        "actions": ["fold", "call", "raise_20"], "source": {"name": "test"},
        "hands": {"AA": {"raise_20": 1.0}},
    }
    base.update(over)
    return base


def test_deal_weights_validation():
    c = chart_from_dict(_chart(deal_weights={"AA": 1.0, "KK": 0.5}))
    assert c.deal_weights["KK"] == 0.5 and c.deal_weights["72o"] == 1.0  # unlisted hands default to 1
    assert chart_from_dict(_chart()).deal_weights is None
    with pytest.raises(ChartError):
        chart_from_dict(_chart(deal_weights={"AA": 1.5}))
    with pytest.raises(ChartError):
        chart_from_dict(_chart(deal_weights={"ZZ": 1.0}))
    with pytest.raises(ChartError):
        chart_from_dict(_chart(deal_weights={h: 0.0 for h in ALL_HAND_CLASSES}))
