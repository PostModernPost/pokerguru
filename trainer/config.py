"""Settings Adam may want to tune. Everything tunable lives here."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHARTS_DIR = PROJECT_ROOT / "data" / "charts"
WEB_DIR = PROJECT_ROOT / "web"
# Drill history. Override with the TRAINER_DB environment variable.
DB_PATH = Path(os.environ.get("TRAINER_DB", PROJECT_ROOT / "data" / "progress.sqlite"))

# Grading of mixed strategies, by how often the chart takes the chosen action:
#   frequency >= correct           -> "correct"
#   acceptable <= frequency < correct -> "acceptable" (mixed)
#   frequency < acceptable         -> "wrong"
GRADE_THRESHOLDS = {
    "correct": 0.5,
    "acceptable": 0.15,
}

# Charts whose source.name is exactly this are fake test data; the UI warns about them.
SAMPLE_SOURCE_NAME = "SAMPLE - NOT REAL STRATEGY"

# Blinds in big blinds. Cash games in phase 1 have no antes.
SMALL_BLIND_BB = 0.5
BIG_BLIND_BB = 1.0

# ---- Phase 2: equity and pot odds drill ----

# Monte Carlo samples per spot. 2,500 gives about +/-1% (one standard error).
EQUITY_ITERATIONS = 2500

# Monte Carlo isn't exact. When the computed equity is this close to a
# bucket edge or to the call/fold line, the "other" answer is graded
# acceptable instead of wrong, since the simulation can't tell them apart.
EQUITY_TOLERANCE = 0.02

# Pot sizes (bb, before villain's bet) and bet sizes (fraction of that pot)
# the drill picks from. Practice values for math, not strategy.
EQUITY_POT_SIZES_BB = [5, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60, 75, 100]
EQUITY_BET_FRACTIONS = {
    "nlhe": [0.25, 0.33, 0.5, 0.66, 0.75, 1.0, 1.5, 2.0],
    "plo": [0.25, 0.33, 0.5, 0.66, 0.75, 1.0],  # pot-limit: a bet can't exceed the pot
}

# ---- Phase 3: PLO drills ----

# Pot-limit sizing drill: (small blind, big blind) in chips, postflop pot sizes
# as multiples of the big blind, and villain's bet as a fraction of the pot.
POT_LIMIT_BLINDS = [(1, 2), (2, 5), (5, 10)]
POT_LIMIT_POSTFLOP_POTS = [5, 8, 10, 12, 15, 20, 25, 30, 40, 50, 75, 100]
POT_LIMIT_BET_FRACTIONS = [0.33, 0.5, 0.66, 0.75, 1.0]
