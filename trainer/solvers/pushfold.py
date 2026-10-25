"""Heads-up push/fold equilibrium by chip EV (no ICM).

Setting: two players, equal stacks of S big blinds (counted before posting),
small blind 0.5, big blind 1, an optional ante per player. The small blind
(the button heads-up) either shoves all-in or folds; the big blind either
calls or folds. Nothing else is allowed, so this is only a model of the game
for short stacks, where push/fold is close to optimal.

Payoffs, measured against the stack each player started the hand with:

    SB folds                 : SB -(0.5 + ante)       BB +(0.5 + ante)
    SB shoves, BB folds      : SB +(1 + ante)         BB -(1 + ante)
    SB shoves, BB calls      : winner +S, loser -S    (ties: 0)

The solver is fictitious play over the 169 hand classes: each side repeatedly
plays the best response to the other side's *average* strategy so far, and the
averages converge to a Nash equilibrium. Card removal is handled by weighting
each opponent class by how many of its combos are still possible. Hand
equities come from the computed 169 x 169 table.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from trainer.game.hand_classes import ALL_HAND_CLASSES
from trainer.game.preflop_equity import compatible_pairs, load_table

N = len(ALL_HAND_CLASSES)

_weights: np.ndarray | None = None


def combo_weights() -> np.ndarray:
    """W[i, j] = number of (combo of i, combo of j) pairs that share no card.

    Dividing row i by its sum gives the chance the opponent holds class j
    when we hold class i (opponent's cards drawn at random from the rest).
    """
    global _weights
    if _weights is None:
        w = np.zeros((N, N))
        for i, h in enumerate(ALL_HAND_CLASSES):
            for j, k in enumerate(ALL_HAND_CLASSES):
                w[i, j] = len(compatible_pairs(h, k))
        _weights = w
    return _weights


@dataclass(frozen=True)
class PushFoldSolution:
    stack_bb: float
    ante_bb: float
    push: np.ndarray  # SB shove frequency per hand class, 0..1
    call: np.ndarray  # BB call frequency per hand class, 0..1
    iterations: int
    sb_ev_bb: float  # SB's expected chips per hand at equilibrium
    exploitability_bb: float  # how much either side could gain by deviating (0 = exact)

    def push_dict(self) -> dict[str, float]:
        return {h: float(self.push[i]) for i, h in enumerate(ALL_HAND_CLASSES)}

    def call_dict(self) -> dict[str, float]:
        return {h: float(self.call[i]) for i, h in enumerate(ALL_HAND_CLASSES)}


def _payoffs(stack_bb: float, ante_bb: float):
    eq = load_table()  # eq[i, j] = P(class i beats class j), ties half
    w = combo_weights()
    sb_fold = -(0.5 + ante_bb)
    bb_fold_gain = 1 + ante_bb  # SB gains this when BB folds
    showdown_sb = (2 * eq - 1) * stack_bb  # SB's EV when called, hand i vs j
    return w, sb_fold, bb_fold_gain, showdown_sb


def sb_push_ev(call: np.ndarray, stack_bb: float, ante_bb: float) -> np.ndarray:
    """EV (in bb) of shoving each hand class, given BB's calling frequencies."""
    w, _, bb_fold_gain, showdown = _payoffs(stack_bb, ante_bb)
    gain = call[None, :] * showdown + (1 - call[None, :]) * bb_fold_gain
    return (w * gain).sum(axis=1) / w.sum(axis=1)


def bb_call_ev(push: np.ndarray, stack_bb: float, ante_bb: float) -> np.ndarray:
    """EV (in bb) of calling a shove with each hand class, given SB's shove frequencies.

    Returns the fold EV (-(1 + ante)) for hands that never face a shove.
    """
    w, _, _, showdown = _payoffs(stack_bb, ante_bb)
    # BB holds j, SB holds i: BB's showdown EV is -showdown[i, j]; weight by push[i] and removal.
    weight = w.T * push[None, :]  # (j, i)
    denom = weight.sum(axis=1)
    ev = np.full(N, -(1 + ante_bb))
    ok = denom > 0
    ev[ok] = (weight[ok] * (-showdown.T)[ok]).sum(axis=1) / denom[ok]
    return ev


def solve(stack_bb: float, ante_bb: float = 0.0, iterations: int = 400) -> PushFoldSolution:
    if stack_bb <= 1:
        raise ValueError("stack must be more than one big blind")
    sb_fold_ev = -(0.5 + ante_bb)
    bb_fold_ev = -(1 + ante_bb)
    push_avg = np.ones(N)  # start: SB shoves everything
    call_avg = np.ones(N)  # start: BB calls everything
    push_sum = push_avg.copy()
    call_sum = call_avg.copy()
    for t in range(2, iterations + 2):
        best_push = (sb_push_ev(call_avg, stack_bb, ante_bb) > sb_fold_ev).astype(float)
        best_call = (bb_call_ev(push_avg, stack_bb, ante_bb) > bb_fold_ev).astype(float)
        push_sum += best_push
        call_sum += best_call
        push_avg = push_sum / t
        call_avg = call_sum / t

    # Value of the game to SB under the averaged strategies, and how exploitable they are.
    w = combo_weights()
    prob_i = w.sum(axis=1) / w.sum()  # chance SB is dealt class i
    sb_ev_per_hand = np.where(push_avg > 0, push_avg * sb_push_ev(call_avg, stack_bb, ante_bb), 0) \
        + (1 - push_avg) * sb_fold_ev
    sb_value = float((prob_i * sb_ev_per_hand).sum())
    # Best responses to the final averages:
    sb_br = float((prob_i * np.maximum(sb_push_ev(call_avg, stack_bb, ante_bb), sb_fold_ev)).sum())
    bb_ev_per_hand = _bb_value_per_hand(push_avg, call_avg, stack_bb, ante_bb)
    bb_value = float((prob_i * bb_ev_per_hand).sum())
    bb_br = float((prob_i * _bb_value_per_hand(push_avg, None, stack_bb, ante_bb)).sum())
    exploitability = max(sb_br - sb_value, bb_br - bb_value, 0.0)
    return PushFoldSolution(stack_bb, ante_bb, np.round(push_avg, 4), np.round(call_avg, 4),
                            iterations, sb_value, exploitability)


def _bb_value_per_hand(push: np.ndarray, call: np.ndarray | None, stack_bb: float, ante_bb: float) -> np.ndarray:
    """BB's EV per hand class: with `call` given, under that strategy; with None, best response."""
    w = combo_weights()
    # Chance BB (holding j) faces a shove, and EV when it does.
    weight = w.T * push[None, :]
    p_shove = weight.sum(axis=1) / w.T.sum(axis=1)
    call_ev = bb_call_ev(push, stack_bb, ante_bb)
    fold_ev = -(1 + ante_bb)
    if call is None:
        facing = np.maximum(call_ev, fold_ev)
    else:
        facing = call * call_ev + (1 - call) * fold_ev
    return p_shove * facing + (1 - p_shove) * (0.5 + ante_bb)
