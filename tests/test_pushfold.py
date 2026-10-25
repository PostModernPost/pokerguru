"""Push/fold solver tests. These need the committed 169x169 equity cache."""

import numpy as np
import pytest

from trainer.game.hand_classes import ALL_HAND_CLASSES
from trainer.game.preflop_equity import CACHE_PATH, equity, load_table
from trainer.solvers.pushfold import bb_call_ev, combo_weights, sb_push_ev, solve

pytestmark = pytest.mark.skipif(not CACHE_PATH.exists(), reason="equity cache not built")

IDX = {h: i for i, h in enumerate(ALL_HAND_CLASSES)}


def test_equity_table_sanity():
    t = load_table()
    assert t.shape == (169, 169)
    assert np.allclose(t + t.T, 1.0, atol=1e-4)  # equity(i, j) + equity(j, i) = 1
    assert equity("AA", "KK") == pytest.approx(0.82, abs=0.01)
    assert equity("AA", "72o") > 0.85
    assert equity("AKs", "AKo") == pytest.approx(0.52, abs=0.015)  # suited edge
    # Every hand beats 32o or is 32o itself (ties half); AA beats everything.
    assert all(t[IDX["AA"], j] > 0.5 for j in range(169) if j != IDX["AA"])


def test_combo_weights():
    w = combo_weights()
    assert w[IDX["AA"], IDX["KK"]] == 36 and w[IDX["AA"], IDX["AKs"]] == 12
    assert w[IDX["AA"], IDX["AA"]] == 6
    assert (w == w.T).all()


def test_push_ev_when_bb_always_folds_is_the_blinds():
    ev = sb_push_ev(np.zeros(169), stack_bb=10, ante_bb=0)
    assert np.allclose(ev, 1.0)
    ev = sb_push_ev(np.zeros(169), stack_bb=10, ante_bb=0.125)
    assert np.allclose(ev, 1.125)


def test_call_ev_vs_shove_with_everything_is_showdown_equity():
    ev = bb_call_ev(np.ones(169), stack_bb=10, ante_bb=0)
    assert ev[IDX["AA"]] > 6  # AA vs a random hand is about 85%: (2*0.85-1)*10 = 7
    assert ev[IDX["72o"]] < -2


def test_solution_has_sensible_shape():
    sol = solve(10, 0, iterations=300)
    push, call = sol.push_dict(), sol.call_dict()
    # Monotone sanity: premium hands always shove and call; trash folds.
    for h in ("AA", "KK", "QQ", "AKs", "AKo", "JJ", "TT"):
        assert push[h] == 1.0 and call[h] == 1.0, h
    assert push["72o"] < 0.05 and call["72o"] == 0.0
    assert call["32o"] == 0.0
    # SB shoves far more than BB calls.
    assert sum(push.values()) > sum(call.values()) + 20
    assert 0 <= sol.exploitability_bb < 0.02
    assert all(0 <= f <= 1 for f in push.values()) and all(0 <= f <= 1 for f in call.values())


def test_shorter_stacks_shove_more():
    wide = sum(solve(5, 0, iterations=200).push_dict().values())
    tight = sum(solve(15, 0, iterations=200).push_dict().values())
    assert wide > tight


def test_antes_widen_both_ranges():
    no_ante = solve(10, 0, iterations=200)
    ante = solve(10, 0.125, iterations=200)
    assert ante.push.sum() > no_ante.push.sum()
    assert ante.call.sum() > no_ante.call.sum()


def test_very_short_stack_shoves_any_two():
    sol = solve(2, 0, iterations=200)
    assert sol.push.min() > 0.95


def test_bad_stack():
    with pytest.raises(ValueError):
        solve(1, 0)
