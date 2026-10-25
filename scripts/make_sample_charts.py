"""Generate the SAMPLE charts in data/charts/nlhe/sample/.

These are FAKE. Every frequency is random noise from a seeded random number
generator, on purpose: the build brief forbids inventing strategy, and random
data can't be mistaken for a real chart. They exist only so the app can be
built and tested before real charts are added. The bet sizes are placeholders
too.

Run:  python scripts/make_sample_charts.py
"""

from __future__ import annotations

import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trainer.charts.loader import chart_from_dict, dump_chart_json  # noqa: E402
from trainer.config import SAMPLE_SOURCE_NAME  # noqa: E402
from trainer.game.hand_classes import ALL_HAND_CLASSES  # noqa: E402
from trainer.game.positions import POSITIONS  # noqa: E402

OUT_DIR = ROOT / "data" / "charts" / "nlhe" / "sample"
SEED = 12345

# Placeholder sizes (bb). Not a recommendation; real charts bring their own.
OPEN = 2.5
THREEBET = 8
FOURBET = 20

# (table size, spot type, hero, villain)
# 6-max raise-first-in and big-blind defence now come from real charts
# (data/charts/nlhe/pokalab), so no samples are made for those spots.
SPOTS = (
    [(6, "vs_open", h, v) for h, v in [("CO", "UTG"), ("BTN", "CO"), ("SB", "BTN")]]
    + [(6, "vs_3bet", h, v) for h, v in [("UTG", "BB"), ("CO", "BTN"), ("BTN", "SB"), ("BTN", "BB")]]
    # 9-handed spots all have real charts now (data/charts/nlhe/rangeconverter), so no samples.
)


def random_freqs(rng: random.Random, actions: list[str]) -> dict[str, float]:
    """Random frequencies: about half pure, half a two-way mix in 5% steps."""
    if rng.random() < 0.5:
        return {rng.choice(actions): 1.0}
    a, b = rng.sample(actions, 2)
    f = rng.randrange(1, 20) * 0.05
    return {a: round(f, 2), b: round(1 - f, 2)}


def make_chart(rng: random.Random, table_size: int, spot_type: str, hero: str, villain: str | None) -> dict:
    if spot_type == "rfi":
        actions, facing = ["fold", f"raise_{OPEN}"], None
    elif spot_type == "vs_open":
        actions, facing = ["fold", "call", f"raise_{THREEBET}"], {"open_size_bb": OPEN}
    else:
        actions = ["fold", "call", f"raise_{FOURBET}"]
        facing = {"open_size_bb": OPEN, "threebet_size_bb": THREEBET}
    vs = f"-vs-{villain}" if villain else ""
    chart_id = f"SAMPLE-nlhe-cash-{table_size}max-100bb-{spot_type}-{hero}{vs}"
    return {
        "id": chart_id,
        "game": "nlhe",
        "format": "cash",
        "table_size": table_size,
        "stack_bb": 100,
        "spot": {"type": spot_type, "hero_pos": hero, "villain_pos": villain, "facing": facing},
        "actions": actions,
        "source": {
            "name": SAMPLE_SOURCE_NAME,
            "url": "",
            "notes": (
                f"Random frequencies from scripts/make_sample_charts.py (seed {SEED}). "
                "For testing the app only. Do not learn from this."
            ),
        },
        "hands": {h: random_freqs(rng, actions) for h in ALL_HAND_CLASSES},
    }


def main() -> None:
    rng = random.Random(SEED)
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    for spot in SPOTS:
        chart = make_chart(rng, *spot)
        chart_from_dict(chart)  # validate
        (OUT_DIR / f"{chart['id']}.json").write_text(dump_chart_json(chart), encoding="utf-8")
    print(f"Wrote {len(SPOTS)} sample charts to {OUT_DIR}")


if __name__ == "__main__":
    main()
