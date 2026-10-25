import numpy as np
import pytest
from pokerkit import Card, StandardHighHand

from trainer.game import fast_eval as fe
from trainer.game.preflop_equity import combos_of, compatible_pairs, matchup_equity


def test_card_ids_round_trip():
    assert [fe.card_name(fe.card_id(c)) for c in ("2c", "As", "Td", "9h")] == ["2c", "As", "Td", "9h"]
    assert fe.card_id("2c") == 0 and fe.card_id("As") == 51


def test_rank7_matches_pokerkit_on_random_hands():
    rng = np.random.default_rng(7)
    hands = np.array([rng.permutation(52)[:7] for _ in range(400)])
    ranks = fe.rank7(hands)
    for h, rk in zip(hands, ranks):
        cards = list(Card.parse("".join(fe.card_name(i) for i in h)))
        assert StandardHighHand.from_game(cards[:2], cards[2:]).entry.index == rk


def test_rank5_known_order():
    ids = lambda s: np.array([[fe.card_id(s[i:i + 2]) for i in range(0, 10, 2)]])
    royal, quads, wheel, nothing = (fe.rank5(ids(s))[0] for s in ("AsKsQsJsTs", "7c7d7h7s2d", "Ah2d3c4s5d", "2c3d4h5s7d"))
    assert royal > quads > wheel > nothing
    assert nothing == 0


def test_combos_of():
    assert len(combos_of("AA")) == 6 and len(combos_of("AKs")) == 4 and len(combos_of("AKo")) == 12
    assert len(compatible_pairs("AA", "AKs")) == 6 * 4 - 12  # each AKs combo clashes with 3 AA combos
    assert len(compatible_pairs("AA", "KK")) == 36
    assert compatible_pairs("AA", "AA") and len(compatible_pairs("AA", "AA")) == 6  # disjoint pairs only


def test_matchup_equity_known_values():
    # Well-known preflop numbers (to within Monte Carlo error at 20k samples, about +/-0.4%).
    assert matchup_equity("AA", "KK", 20000, 1) == pytest.approx(0.82, abs=0.01)
    assert matchup_equity("AKs", "QQ", 20000, 1) == pytest.approx(0.46, abs=0.01)
    assert matchup_equity("AKo", "22", 20000, 1) == pytest.approx(0.475, abs=0.02)
    assert matchup_equity("AA", "AA", 20000, 1) == pytest.approx(0.5, abs=0.01)
    assert matchup_equity("72o", "AA", 20000, 1) == pytest.approx(0.12, abs=0.01)
