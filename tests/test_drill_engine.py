import random

import pytest

from trainer.charts.loader import ChartLibrary
from trainer.config import CHARTS_DIR
from trainer.drills.preflop import NoMatchingChart, next_spot, spot_from_chart

LIB = ChartLibrary.from_directory(CHARTS_DIR / "nlhe")  # samples plus the real 6-max charts


def test_next_spot_respects_filters():
    rng = random.Random(0)
    for _ in range(200):
        chart, spot, reason = next_spot(LIB, rng, table_sizes=[6], spot_types=["vs_3bet"])
        assert reason == "random"
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


def _store(tmp_path):
    from trainer.progress.store import AttemptStore
    return AttemptStore(tmp_path / "p.sqlite")


def _record(store, chart, hand_class, grade):
    from trainer.progress.store import Attempt
    from trainer.drills.preflop import DRILL_TYPE, review_key
    store.record(Attempt(drill_type=DRILL_TYPE, game="nlhe", format="cash", spot={}, hero_cards="AsKd",
                         user_answer="fold", correct_answer=["fold"], grade=grade, table_size=chart.table_size,
                         spot_type=chart.spot_type, hero_pos=chart.hero_pos, hand_class=hand_class, chart_id=chart.id))
    store.schedule_review(DRILL_TYPE, review_key(chart.id, hand_class), grade)


def test_with_empty_store_still_serves_everything(tmp_path):
    store = _store(tmp_path)
    rng = random.Random(0)
    seen = {next_spot(LIB, rng, table_sizes=[6], store=store)[0].id for _ in range(600)}
    assert seen == {c.id for c in LIB.find(table_sizes=[6])}


def test_due_review_comes_back(tmp_path):
    store = _store(tmp_path)
    chart = LIB.find(table_sizes=[6], spot_types=["rfi"])[0]
    _record(store, chart, "72o", "wrong")
    for _ in range(5):  # five more attempts make it due
        _record(store, chart, "AA", "correct")
    rng = random.Random(1)
    reasons = [next_spot(LIB, rng, table_sizes=[6], spot_types=["rfi"], store=store) for _ in range(40)]
    reviews = [(c, s) for c, s, r in reasons if r == "review"]
    assert reviews, "a due review should be served sometimes"
    assert all(c.id == chart.id and s.hand_class == "72o" for c, s in reviews)


def test_weighting_favours_weak_position(tmp_path):
    store = _store(tmp_path)
    rfi = LIB.find(table_sizes=[6], spot_types=["rfi"])
    weak = next(c for c in rfi if c.hero_pos == "UTG")
    strong = next(c for c in rfi if c.hero_pos == "BTN")
    for _ in range(10):
        _record(store, weak, "AA", "wrong")
        _record(store, strong, "AA", "correct")
    rng = random.Random(2)
    counts = {"UTG": 0, "BTN": 0}
    for _ in range(600):
        c, s, r = next_spot(LIB, rng, table_sizes=[6], spot_types=["rfi"], hero_positions=["UTG", "BTN"], store=store)
        if r != "review":
            counts[c.hero_pos] += 1
    assert counts["UTG"] > counts["BTN"] * 1.5


def test_leaks_only_mode(tmp_path):
    from trainer.drills.preflop import LeakProfile
    store = _store(tmp_path)
    with pytest.raises(NoMatchingChart, match="No leaks found yet"):
        next_spot(LIB, random.Random(0), store=store, leaks_only=True)
    chart = LIB.find(table_sizes=[6], spot_types=["vs_open"])[0]
    for h in ("A2s", "A3s", "A4s", "A5s", "A6s", "A7s"):   # suited aces are a leak
        _record(store, chart, h, "wrong")
    profile = LeakProfile.from_store(store)
    assert profile.weak_categories() == ["suited ace"]
    assert profile.summary()["weak_positions"] == [chart.hero_pos]
    rng = random.Random(3)
    for _ in range(30):
        c, s, r = next_spot(LIB, rng, store=store, leaks_only=True)
        if r == "review":
            assert c.id == chart.id
        else:
            assert r == "category" and s.hand_class[0] == "A" and s.hand_class.endswith("s")
            assert c.hero_pos == chart.hero_pos or c.spot_type == chart.spot_type
