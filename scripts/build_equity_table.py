"""Build (or rebuild) the 169x169 preflop all-in equity table.

    python scripts/build_equity_table.py            # ~10-15 minutes on 4 cores
    python scripts/build_equity_table.py --samples 5000   # quick, less accurate

The result is cached in data/equity_cache/preflop_equity_169.json and is
committed, so you normally never need to run this.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trainer.game.fast_eval import five_card_table  # noqa: E402
from trainer.game.preflop_equity import CACHE_PATH, SAMPLES_PER_MATCHUP, SEED, build_table, save_table  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--samples", type=int, default=SAMPLES_PER_MATCHUP, help="boards per matchup")
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--out", default=str(CACHE_PATH))
    args = p.parse_args()

    five_card_table()  # build the 5-card cache first so the workers all find it
    start = time.time()

    def progress(done, total):
        el = time.time() - start
        print(f"  {done}/{total} matchups, {el / 60:.1f} min elapsed, ~{el / done * (total - done) / 60:.1f} min left",
              flush=True)

    table = build_table(samples=args.samples, seed=args.seed, workers=args.workers, progress=progress)
    save_table(table, args.samples, args.seed, Path(args.out))
    print(f"Saved {args.out} in {(time.time() - start) / 60:.1f} minutes")


if __name__ == "__main__":
    main()
