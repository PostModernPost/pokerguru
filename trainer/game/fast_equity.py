"""Fast Hold'em equity against one opponent whose hand comes from a weighted range.

Used by the game mode, which needs many equity estimates per hand (bots deciding,
feedback after your calls). Vectorised with numpy on top of the five-card rank
table that PokerKit built (trainer/game/fast_eval.py); no new hand evaluator.

`weights` maps hand classes ('AKs', '77', ...) to how likely the opponent holds
them (0..1). None means a random hand. Combos that clash with known cards are
removed before sampling.
"""

from __future__ import annotations

import numpy as np

from trainer.game.fast_eval import card_id, rank7
from trainer.game.hand_classes import ALL_HAND_CLASSES, RANK_VALUE

RANKS = "23456789TJQKA"
SUITS = "cdhs"


def _combos_of(hand_class: str) -> list[tuple[int, int]]:
    r1, r2 = hand_class[0], hand_class[1]
    out = []
    if r1 == r2:
        for i in range(4):
            for j in range(i + 1, 4):
                out.append((card_id(r1 + SUITS[i]), card_id(r2 + SUITS[j])))
    elif hand_class[2] == "s":
        for s in SUITS:
            out.append((card_id(r1 + s), card_id(r2 + s)))
    else:
        for s1 in SUITS:
            for s2 in SUITS:
                if s1 != s2:
                    out.append((card_id(r1 + s1), card_id(r2 + s2)))
    return out


_ALL_COMBOS = [(h, c) for h in ALL_HAND_CLASSES for c in _combos_of(h)]
_COMBO_CARDS = np.array([c for _, c in _ALL_COMBOS], dtype=np.int64)  # (1326, 2)
_COMBO_CLASS = [h for h, _ in _ALL_COMBOS]
_CLASS_INDEX = {h: i for i, h in enumerate(ALL_HAND_CLASSES)}
_COMBO_CLASS_IDX = np.array([_CLASS_INDEX[h] for h in _COMBO_CLASS])


def equity_vs_range(hero: tuple[str, ...], board: tuple[str, ...], weights: dict[str, float] | None,
                    iterations: int, rng: np.random.Generator) -> float:
    """Hero's chance of winning at showdown (ties count half) against one opponent."""
    hero_ids = np.array([card_id(c) for c in hero], dtype=np.int64)
    board_ids = np.array([card_id(c) for c in board], dtype=np.int64)
    dead = set(hero_ids.tolist()) | set(board_ids.tolist())
    if weights is None:
        w = np.ones(169)
    else:
        w = np.array([weights.get(h, 0.0) for h in ALL_HAND_CLASSES])
    combo_w = w[_COMBO_CLASS_IDX].astype(float)
    clash = np.isin(_COMBO_CARDS, list(dead)).any(axis=1)
    combo_w[clash] = 0.0
    if combo_w.sum() <= 0:
        combo_w = (~clash).astype(float)
    combo_w /= combo_w.sum()
    picks = rng.choice(len(combo_w), size=iterations, p=combo_w)
    villain = _COMBO_CARDS[picks]  # (it, 2)

    need = 5 - len(board_ids)
    if need:
        keys = rng.random((iterations, 52))
        keys[:, list(dead)] = np.inf
        np.put_along_axis(keys, villain, np.inf, axis=1)
        runout = np.argpartition(keys, need, axis=1)[:, :need]
    else:
        runout = np.zeros((iterations, 0), dtype=np.int64)
    full_board = np.concatenate([np.broadcast_to(board_ids, (iterations, len(board_ids))), runout], axis=1)
    hero7 = np.concatenate([np.broadcast_to(hero_ids, (iterations, 2)), full_board], axis=1)
    vill7 = np.concatenate([villain, full_board], axis=1)
    hr, vr = rank7(hero7), rank7(vill7)
    return float(((hr > vr).sum() + 0.5 * (hr == vr).sum()) / iterations)
