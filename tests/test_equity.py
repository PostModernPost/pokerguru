import random

import pytest
from pokerkit import Card, Deck, OmahaHoldemHand, StandardHighHand, calculate_equities

from trainer.game.equity import equity_vs_random, spot_seed


def test_same_seed_same_answer():
    a = equity_vs_random("nlhe", "AsKd", "Qh7c2s", iterations=500, seed=42)
    b = equity_vs_random("nlhe", ("As", "Kd"), ("Qh", "7c", "2s"), iterations=500, seed=42)
    assert a == b
    c = equity_vs_random("nlhe", "AsKd", "Qh7c2s", iterations=500, seed=43)
    assert c.equity != a.equity


def test_spot_seed_is_stable_across_runs():
    # A fixed number: if this changed between Python runs, grading wouldn't be reproducible.
    assert spot_seed("nlhe", ("As", "Kd"), ("Qh", "7c", "2s")) == 6045456148989372510
    assert spot_seed("plo", ("As", "Kd"), ("Qh", "7c", "2s")) != spot_seed("nlhe", ("As", "Kd"), ("Qh", "7c", "2s"))


def test_river_royal_flush_is_exactly_one():
    r = equity_vs_random("nlhe", "As3c", "TsJsQsKs2d", iterations=1)
    assert r.exact and r.equity == 1.0 and r.iterations == 990


def test_river_board_plays_is_exactly_half():
    # Board AAAA K: nobody can beat it or improve it, every hand ties.
    r = equity_vs_random("nlhe", "QsQh", "AsAhAdAcKs", iterations=1)
    assert r.exact and r.equity == 0.5


def test_turn_monte_carlo_matches_exact_enumeration():
    # The true turn equity is the average, over all 46 unseen river cards, of the exact
    # river equity (each river is equally likely, then villain is uniform over the rest).
    hero, turn = "AsKd", "Qh7c2s3d"
    used = set(Card.parse(hero + turn))
    rivers = sorted(f"{c.rank.value}{c.suit.value}" for c in Deck.STANDARD if c not in used)
    assert len(rivers) == 46
    exact = sum(equity_vs_random("nlhe", hero, turn + r, iterations=1).equity for r in rivers) / 46
    mc = equity_vs_random("nlhe", hero, turn, iterations=4000, seed=1)
    assert mc.equity == pytest.approx(exact, abs=4 * mc.std_error)


def test_plo_uses_exactly_two_hole_cards():
    # Five hearts on board. In hold'em hero plays the board flush; in PLO hero must use
    # two hole cards (two clubs), so there's no flush.
    plo = equity_vs_random("plo", "2c3c4c5c", "AhKhQhJh9h", iterations=2000, seed=1)
    nlhe = equity_vs_random("nlhe", "2c3c", "AhKhQhJh9h", iterations=1)
    assert plo.equity < 0.1
    assert nlhe.equity > 0.4


def test_plo_nut_straight_flush_wins_every_time():
    # Ts9s + KsQsJs = king-high straight flush. A royal needs Ts + four board spades,
    # which PLO doesn't allow, so nothing beats it.
    r = equity_vs_random("plo", "Ts9s8d7d", "AsKsQsJs2h", iterations=1000, seed=1)
    assert r.equity == 1.0


def test_preflop_board_allowed():
    assert 0 <= equity_vs_random("nlhe", "AsKs", "", iterations=50, seed=1).equity <= 1


@pytest.mark.parametrize(
    "game,hero,board",
    [
        ("nlhe", "AsKsQs", "2c3c4c"),   # wrong hole count
        ("plo", "AsKs", "2c3c4c"),
        ("nlhe", "AsKs", "As3c4c"),     # duplicate card
        ("nlhe", "AsKs", "2c3c4c5c6c7c"),  # 6-card board
        ("stud", "AsKs", "2c3c4c"),
        ("nlhe", "AsXs", "2c3c4c"),
    ],
)
def test_bad_input(game, hero, board):
    with pytest.raises(ValueError):
        equity_vs_random(game, hero, board, iterations=10, seed=1)


def _pokerkit_equity(hand_type, n_hole, hero, board, samples):
    random.seed(0)
    return calculate_equities(
        ([list(Card.parse(hero))], [[]]),  # [[]] = one random opponent hand
        list(Card.parse(board)), n_hole, 5, Deck.STANDARD, (hand_type,), sample_count=samples,
    )[0]


def test_agrees_with_pokerkit_calculate_equities_nlhe():
    ours = equity_vs_random("nlhe", "AsKd", "Qh7c2s", iterations=6000, seed=7)
    theirs = _pokerkit_equity(StandardHighHand, 2, "AsKd", "Qh7c2s", 6000)
    assert ours.equity == pytest.approx(theirs, abs=0.03)


def test_agrees_with_pokerkit_calculate_equities_plo():
    ours = equity_vs_random("plo", "AsKdJcTc", "Qh7c2s", iterations=2000, seed=7)
    theirs = _pokerkit_equity(OmahaHoldemHand, 4, "AsKdJcTc", "Qh7c2s", 2000)
    assert ours.equity == pytest.approx(theirs, abs=0.06)
