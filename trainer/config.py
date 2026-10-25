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
