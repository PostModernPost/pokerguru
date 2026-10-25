"""The 169 x 169 preflop all-in equity table (hold'em, heads-up).

``equity[i][j]`` is the chance hand class i beats hand class j all-in
preflop (ties count half), averaged over every pair of actual card combos
the two classes can be dealt at the same time. It is estimated by seeded
Monte Carlo over random boards, with PokerKit ranking every showdown via
``fast_eval``. Building it takes a while, so the result is cached in
``data/equity_cache/preflop_equity_169.json`` and committed.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor
from itertools import combinations
from pathlib import Path

import numpy as np

from trainer import config
from trainer.game.fast_eval import card_id, rank7
from trainer.game.hand_classes import ALL_HAND_CLASSES, RANKS

CACHE_PATH = Path(config.PROJECT_ROOT) / "data" / "equity_cache" / "preflop_equity_169.json"
SAMPLES_PER_MATCHUP = 40_000
SEED = 20241025
SUITS = "cdhs"


def combos_of(hand_class: str) -> list[tuple[int, int]]:
    """Every two-card combo (as card ids) in a hand class."""
    r1, r2 = hand_class[0], hand_class[1]
    if r1 == r2:
        return [(card_id(r1 + a), card_id(r1 + b)) for a, b in combinations(SUITS, 2)]
    suited = hand_class[2] == "s"
    out = []
    for a in SUITS:
        for b in SUITS:
            if (a == b) == suited:
                out.append((card_id(r1 + a), card_id(r2 + b)))
    return out


def compatible_pairs(h: str, k: str) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """All (combo of h, combo of k) pairs that don't share a card."""
    return [(a, b) for a in combos_of(h) for b in combos_of(k) if not set(a) & set(b)]


def matchup_equity(h: str, k: str, samples: int, seed: int) -> float:
    """Equity of class h vs class k, Monte Carlo over boards, weighted by combos."""
    pairs = compatible_pairs(h, k)
    if not pairs:
        return float("nan")
    rng = np.random.default_rng(seed)
    per_pair = max(1, samples // len(pairs))
    total = 0.0
    n = 0
    for (a1, a2), (b1, b2) in pairs:
        used = {a1, a2, b1, b2}
        deck = np.array([c for c in range(52) if c not in used], dtype=np.int64)
        # per_pair random 5-card boards without replacement
        boards = deck[np.argsort(rng.random((per_pair, len(deck))), axis=1)[:, :5]]
        hero = np.concatenate([np.full((per_pair, 1), a1), np.full((per_pair, 1), a2), boards], axis=1)
        vill = np.concatenate([np.full((per_pair, 1), b1), np.full((per_pair, 1), b2), boards], axis=1)
        rh, rv = rank7(hero), rank7(vill)
        total += float(np.sum(rh > rv) + 0.5 * np.sum(rh == rv))
        n += per_pair
    return total / n


def _job(args):
    i, j, samples, seed = args
    return i, j, matchup_equity(ALL_HAND_CLASSES[i], ALL_HAND_CLASSES[j], samples, seed)


def build_table(samples: int = SAMPLES_PER_MATCHUP, seed: int = SEED, workers: int | None = None,
                progress=None) -> np.ndarray:
    n = len(ALL_HAND_CLASSES)
    table = np.full((n, n), 0.5)
    jobs = [(i, j, samples, seed * 1000 + i * n + j) for i in range(n) for j in range(i + 1, n)]
    done = 0
    with ProcessPoolExecutor(max_workers=workers or os.cpu_count()) as pool:
        for i, j, eq in pool.map(_job, jobs, chunksize=16):
            table[i, j] = eq
            table[j, i] = 1.0 - eq
            done += 1
            if progress and done % 500 == 0:
                progress(done, len(jobs))
    return table


def save_table(table: np.ndarray, samples: int, seed: int, path: Path = CACHE_PATH) -> None:
    data = {
        "source": {
            "name": "computed",
            "notes": (f"Preflop all-in equity, hold'em heads-up. Monte Carlo, {samples} boards per matchup "
                      f"(split evenly over the compatible combo pairs), seed {seed}, showdowns ranked by "
                      "PokerKit 0.7.7 (StandardLookup). Ties count half. Row = hero, column = villain."),
        },
        "hands": list(ALL_HAND_CLASSES),
        "samples_per_matchup": samples,
        "seed": seed,
        "equity": [[round(float(x), 5) for x in row] for row in table],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


_cached: np.ndarray | None = None


def load_table(path: Path = CACHE_PATH) -> np.ndarray:
    global _cached
    if _cached is None:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data["hands"] != list(ALL_HAND_CLASSES):
            raise ValueError("Equity cache hand order doesn't match ALL_HAND_CLASSES")
        _cached = np.array(data["equity"], dtype=np.float64)
    return _cached


INDEX = {h: i for i, h in enumerate(ALL_HAND_CLASSES)}


def equity(hero: str, villain: str) -> float:
    return float(load_table()[INDEX[hero], INDEX[villain]])
