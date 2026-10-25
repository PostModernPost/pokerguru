import pytest

from trainer.game.pot_limit import max_raise_to


def test_brief_case_utg_preflop():
    # Blinds 1/2, UTG first to act: pot = 3, facing 2, to call 2 -> max raise to 7
    s = max_raise_to(pot=3, largest_bet=2, hero_in=0)
    assert s.to_call == 2 and s.max_raise_to == 7


def test_brief_case_postflop_pot_bet():
    # Pot 100, villain bets 100, hero has nothing in: pot = 200, to call 100 -> 400
    s = max_raise_to(pot=200, largest_bet=100, hero_in=0)
    assert s.to_call == 100 and s.max_raise_to == 400


def test_small_blind_facing_open():
    # Blinds 1/2, CO raises to 7: pot = 1 + 2 + 7 = 10. SB has 1 in, calls 6 -> pot 16 -> raise to 23.
    s = max_raise_to(pot=10, largest_bet=7, hero_in=1)
    assert s.to_call == 6 and s.pot_after_call == 16 and s.max_raise_to == 23


def test_big_blind_option_after_limps():
    # Blinds 1/2, three limpers: pot = 1 + 2 + 2*3 = 9. BB has 2 in, nothing to call -> raise to 11.
    s = max_raise_to(pot=9, largest_bet=2, hero_in=2)
    assert s.to_call == 0 and s.max_raise_to == 11


def test_first_to_act_postflop_is_a_pot_bet():
    s = max_raise_to(pot=50, largest_bet=0, hero_in=0)
    assert s.to_call == 0 and s.max_raise_to == 50


def test_facing_a_three_bet_preflop():
    # Blinds 1/2. Hero (CO) opens to 7, BTN re-raises to 24, blinds fold.
    # pot = 1 + 2 + 7 + 24 = 34; hero has 7 in, calls 17 -> pot 51 -> raise to 75.
    s = max_raise_to(pot=34, largest_bet=24, hero_in=7)
    assert s.to_call == 17 and s.max_raise_to == 75


@pytest.mark.parametrize("kw", [
    dict(pot=-1, largest_bet=0, hero_in=0),
    dict(pot=10, largest_bet=5, hero_in=6),
    dict(pot=3, largest_bet=5, hero_in=0),
])
def test_rejects_nonsense(kw):
    with pytest.raises(ValueError):
        max_raise_to(**kw)
