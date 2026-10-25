import random

import pytest

from trainer.scenarios.postflop import build_equity_spot, random_equity_spot, round_bet, sort_cards


def test_random_spots_follow_rules():
    rng = random.Random(0)
    for _ in range(500):
        s = random_equity_spot(rng)
        n_hole = 2 if s.game == "nlhe" else 4
        assert len(s.hero_cards) == n_hole
        assert len(s.board) == {"flop": 3, "turn": 4}[s.street]
        assert len(set(s.hero_cards + s.board)) == n_hole + len(s.board)
        assert s.pot_bb > 0 and s.bet_bb > 0
        if s.game == "plo":
            assert s.bet_bb <= s.pot_bb
            assert s.hand_class is None
        else:
            assert s.hand_class is not None


def test_filters():
    rng = random.Random(1)
    for _ in range(100):
        s = random_equity_spot(rng, games=["plo"], streets=["turn"])
        assert s.game == "plo" and s.street == "turn"


def test_seeded():
    assert random_equity_spot(random.Random(5)) == random_equity_spot(random.Random(5))


def test_build_and_to_call():
    s = build_equity_spot(game="nlhe", street="flop", hero_cards="KdAs", board="Qh7c2s", pot_bb=100, bet_bb=50)
    assert s.hero_cards == ("As", "Kd")
    assert s.to_call_bb == 50 and s.hand_class == "AKo"
    assert s.to_dict()["to_call_bb"] == 50


@pytest.mark.parametrize(
    "kw",
    [
        dict(game="nlhe", street="flop", hero_cards="AsKdQc", board="Qh7c2s"),
        dict(game="plo", street="flop", hero_cards="AsKd", board="Qh7c2s"),
        dict(game="nlhe", street="turn", hero_cards="AsKd", board="Qh7c2s"),
        dict(game="nlhe", street="flop", hero_cards="AsKd", board="As7c2s"),
        dict(game="nlhe", street="river", hero_cards="AsKd", board="Qh7c2s3d4d"),
        dict(game="nlhe", street="flop", hero_cards="AsKd", board="Qh7c2s", bet_bb=0),
        dict(game="plo", street="flop", hero_cards="AsKdJcTc", board="Qh7c2s", bet_bb=150),
    ],
)
def test_invalid(kw):
    kw.setdefault("pot_bb", 100)
    kw.setdefault("bet_bb", 50)
    with pytest.raises(ValueError):
        build_equity_spot(**kw)


def test_round_bet():
    assert round_bet(1.25) == 1.0  # Python rounds halves to even: 2.5 -> 2
    assert round_bet(1.3) == 1.5
    assert round_bet(0.1) == 0.5
    assert round_bet(33.0) == 33.0


def test_sort_cards():
    assert sort_cards(("2c", "Ah", "Td", "As")) == ("Ah", "As", "Td", "2c")
