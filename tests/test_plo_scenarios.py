import random

import pytest

from trainer.scenarios.plo import (
    build_nut_spot,
    build_postflop_pot_limit_spot,
    build_preflop_pot_limit_spot,
    random_nut_spot,
    random_pot_limit_spot,
)


def test_nut_spot_random_and_filters():
    rng = random.Random(1)
    for _ in range(200):
        s = random_nut_spot(rng, streets=["turn"])
        assert s.street == "turn" and len(s.board) == 4 and len(s.hero_cards) == 4
        assert len(set(s.hero_cards + s.board)) == 8
    assert random_nut_spot(random.Random(2)) == random_nut_spot(random.Random(2))


@pytest.mark.parametrize("kw", [
    dict(street="flop", hero_cards="AsKd", board="2c3c4c"),
    dict(street="turn", hero_cards="AsKdQcJc", board="2c3c4c"),
    dict(street="flop", hero_cards="AsKdQcJc", board="As3c4c"),
    dict(street="street", hero_cards="AsKdQcJc", board="2c3c4c"),
])
def test_bad_nut_spot(kw):
    with pytest.raises(ValueError):
        build_nut_spot(**kw)


def test_preflop_brief_case():
    s = build_preflop_pot_limit_spot(small_blind=1, big_blind=2, hero_pos="UTG", actions=[])
    assert (s.pot, s.to_call, s.max_raise_to) == (3, 2, 7)


def test_preflop_pot_raise_then_calls():
    s = build_preflop_pot_limit_spot(small_blind=1, big_blind=2, hero_pos="BB",
                                     actions=[("UTG", "fold"), ("HJ", "pot"), ("CO", "call"), ("BTN", "fold"), ("SB", "call")])
    # HJ pot raise: 2 + 3 + 2 = 7. Pot = 7 + 7 + 7 (SB completes to 7) + 2 = 23. BB has 2 in, calls 5 -> 28 -> raise to 35.
    assert [h["to"] for h in s.history if h["action"] == "raise"] == [7.0]
    assert s.pot == 23 and s.hero_in == 2 and s.to_call == 5 and s.max_raise_to == 35


def test_preflop_big_blind_checks_after_limps():
    s = build_preflop_pot_limit_spot(small_blind=1, big_blind=2, hero_pos="BTN",
                                     actions=[("UTG", "call"), ("HJ", "call"), ("CO", "fold")])
    assert s.pot == 7 and s.to_call == 2 and s.max_raise_to == 11
    s = build_preflop_pot_limit_spot(small_blind=1, big_blind=2, hero_pos="BB",
                                     actions=[("UTG", "call"), ("HJ", "call"), ("CO", "fold"), ("BTN", "fold"), ("SB", "call")])
    assert s.to_call == 0 and s.max_raise_to == 2 + 8  # pot 8 (1->2, 2, 2, 2)
    with pytest.raises(ValueError):
        build_preflop_pot_limit_spot(small_blind=1, big_blind=2, hero_pos="BTN",
                                     actions=[("UTG", "pot"), ("HJ", "check")])


def test_preflop_explicit_raise_size():
    s = build_preflop_pot_limit_spot(small_blind=2, big_blind=5, hero_pos="SB",
                                     actions=[("UTG", "raise:15"), ("HJ", "fold"), ("CO", "fold"), ("BTN", "call")])
    assert s.pot == 2 + 5 + 15 + 15 and s.to_call == 13 and s.max_raise_to == 15 + (37 + 13)
    with pytest.raises(ValueError):
        build_preflop_pot_limit_spot(small_blind=2, big_blind=5, hero_pos="SB", actions=[("UTG", "raise:5")])


def test_postflop_brief_case_and_variants():
    s = build_postflop_pot_limit_spot(pot_before=100, bet=100)
    assert (s.pot, s.to_call, s.max_raise_to) == (200, 100, 400)
    s = build_postflop_pot_limit_spot(pot_before=100, bet=50, callers=1)
    assert s.pot == 200 and s.to_call == 50 and s.max_raise_to == 50 + 250
    s = build_postflop_pot_limit_spot(pot_before=60, bet=None)
    assert s.to_call == 0 and s.max_raise_to == 60 and s.history == ()
    with pytest.raises(ValueError):
        build_postflop_pot_limit_spot(pot_before=100, bet=150)
    with pytest.raises(ValueError):
        build_postflop_pot_limit_spot(pot_before=100, bet=None, callers=1)


def test_random_pot_limit_spots_are_consistent():
    from trainer.game.pot_limit import max_raise_to

    rng = random.Random(9)
    stages = set()
    for _ in range(400):
        s = random_pot_limit_spot(rng)
        stages.add(s.stage)
        assert s.max_raise_to == max_raise_to(s.pot, s.largest_bet, s.hero_in).max_raise_to
        assert s.to_call >= 0 and s.max_raise_to > s.largest_bet
        assert s.max_raise_to == int(s.max_raise_to)  # whole chips only
        for h in s.history:
            if h["action"] == "raise":
                assert h["to"] == int(h["to"])
    assert stages == {"preflop", "postflop"}
