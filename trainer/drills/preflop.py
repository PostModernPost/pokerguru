"""Preflop chart drill: picks the next spot and turns a chart into a spot.

Without a store, picks are uniform: a random chart among those matching the
filters, then two random cards. With a store (phase 5), picks lean toward
weak areas and bring back missed spots:

- Each candidate chart is weighted by how badly you do in its position and
  spot type (more misses, more weight). Charts with few attempts stay neutral.
- Half the time the hand is drawn from a hand category weighted the same way,
  instead of fully at random.
- Items that are due for review (a chart + hand you missed earlier) are served
  ahead of everything else some of the time.
- "Leaks only" mode serves nothing but weak categories and due reviews.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from trainer.charts.loader import Chart, ChartLibrary
from trainer.game.dealing import deal, deal_hand_class
from trainer.game.hand_classes import HAND_CATEGORIES, hand_category, hands_in_category
from trainer.progress.store import AttemptStore
from trainer.scenarios.preflop import PreflopSpot, build_preflop_spot

DRILL_TYPE = "preflop_chart"

# Leak weighting knobs.
MIN_ATTEMPTS = 5          # below this a category counts as "unknown", weighted neutrally
WEAK_SCORE = 0.7          # score below this (acceptable counts half) makes a category a leak
REVIEW_CHANCE = 0.35      # chance a due review is served when one exists
CATEGORY_CHANCE = 0.5     # chance the hand comes from a weighted category rather than a random deal
WEIGHT_GAIN = 4.0         # how strongly a weak area is favoured: weight = 1 + gain * deficit


class NoMatchingChart(LookupError):
    pass


def spot_from_chart(chart: Chart, hero_cards: tuple[str, ...] | str) -> PreflopSpot:
    facing = chart.facing or {}
    return build_preflop_spot(
        game=chart.game,
        format=chart.format,
        table_size=chart.table_size,
        spot_type=chart.spot_type,
        hero_pos=chart.hero_pos,
        villain_pos=chart.villain_pos,
        hero_cards=hero_cards,
        stack_bb=chart.stack_bb,
        open_size_bb=facing.get("open_size_bb") if chart.spot_type in ("vs_open", "vs_3bet") else None,
        threebet_size_bb=facing.get("threebet_size_bb") if chart.spot_type == "vs_3bet" else None,
    )


def review_key(chart_id: str, hand_class: str) -> str:
    return f"{chart_id}|{hand_class}"


@dataclass
class LeakProfile:
    """Your scores per position, spot type and hand category (None = too few attempts)."""
    by_pos: dict[str, float]
    by_spot: dict[str, float]
    by_category: dict[str, float]
    due: list[str]

    @classmethod
    def from_store(cls, store: AttemptStore) -> "LeakProfile":
        def scores(group: str) -> dict[str, float]:
            return {r["key"]: r["score"] for r in store.breakdown(group, DRILL_TYPE) if r["total"] >= MIN_ATTEMPTS}

        cats: dict[str, list[int]] = {}
        for r in store.breakdown("hand_class", DRILL_TYPE):
            c = cats.setdefault(hand_category(r["key"]), [0, 0.0])
            c[0] += r["total"]
            c[1] += r["score"] * r["total"]
        by_category = {k: round(v[1] / v[0], 4) for k, v in cats.items() if v[0] >= MIN_ATTEMPTS}
        return cls(scores("hero_pos"), scores("spot_type"), by_category, store.due_reviews(DRILL_TYPE))

    def chart_weight(self, chart: Chart) -> float:
        deficit = 0.0
        for score in (self.by_pos.get(chart.hero_pos), self.by_spot.get(chart.spot_type)):
            deficit += (1 - score) if score is not None else (1 - WEAK_SCORE) / 2
        return 1 + WEIGHT_GAIN * deficit

    def chart_is_weak(self, chart: Chart) -> bool:
        return any(s is not None and s < WEAK_SCORE
                   for s in (self.by_pos.get(chart.hero_pos), self.by_spot.get(chart.spot_type)))

    def weak_categories(self) -> list[str]:
        return [c for c in HAND_CATEGORIES if self.by_category.get(c) is not None and self.by_category[c] < WEAK_SCORE]

    def category_weights(self) -> dict[str, float]:
        out = {}
        for c in HAND_CATEGORIES:
            s = self.by_category.get(c)
            out[c] = 1 + WEIGHT_GAIN * ((1 - s) if s is not None else (1 - WEAK_SCORE) / 2)
        return out

    def summary(self) -> dict:
        return {
            "weak_positions": sorted(k for k, s in self.by_pos.items() if s < WEAK_SCORE),
            "weak_spot_types": sorted(k for k, s in self.by_spot.items() if s < WEAK_SCORE),
            "weak_categories": self.weak_categories(),
            "due_reviews": len(self.due),
        }


def next_spot(
    library: ChartLibrary,
    rng: random.Random,
    *,
    table_sizes: list[int] | None = None,
    hero_positions: list[str] | None = None,
    spot_types: list[str] | None = None,
    game: str = "nlhe",
    formats: list[str] | None = None,
    stacks: list[float] | None = None,
    store: AttemptStore | None = None,
    leaks_only: bool = False,
    include_samples: bool = False,
) -> tuple[Chart, PreflopSpot, str]:
    """Returns (chart, spot, reason). reason is 'random', 'weighted', 'category' or 'review'."""
    charts = library.find(game=game, formats=formats, table_sizes=table_sizes,
                          hero_positions=hero_positions, spot_types=spot_types, stacks=stacks,
                          include_samples=include_samples)
    if not charts:
        raise NoMatchingChart("No chart matches these filters. Try selecting more positions or spot types"
                              + ("" if include_samples else ", or switch on sample charts (test data only)")
                              + ".")
    if store is None:
        chart = rng.choice(charts)
        return chart, spot_from_chart(chart, deal(rng, 2)), "random"

    profile = LeakProfile.from_store(store)
    by_id = {c.id: c for c in charts}

    # 1. Due reviews (a specific chart + hand you got wrong before).
    due = [k for k in profile.due if k.split("|", 1)[0] in by_id]
    if due and (leaks_only or rng.random() < REVIEW_CHANCE):
        chart_id, hand_class = rng.choice(due[:5]).split("|", 1)
        chart = by_id[chart_id]
        return chart, spot_from_chart(chart, deal_hand_class(rng, hand_class)), "review"

    # 2. Pick the chart, leaning toward weak positions / spot types.
    pool = charts
    weak_cats = profile.weak_categories()
    if leaks_only:
        weak_charts = [c for c in charts if profile.chart_is_weak(c)]
        if weak_charts:
            pool = weak_charts
        elif not weak_cats:
            raise NoMatchingChart(
                "No leaks found yet in these filters. Drill normally for a while (at least "
                f"{MIN_ATTEMPTS} hands per position, spot type or hand category) and try again."
            )
    chart = rng.choices(pool, weights=[profile.chart_weight(c) for c in pool])[0]

    # 3. Pick the hand: from a weighted category, or a plain deal.
    if leaks_only and weak_cats:
        cat = rng.choice(weak_cats)
        return chart, spot_from_chart(chart, deal_hand_class(rng, rng.choice(hands_in_category(cat)))), "category"
    if rng.random() < CATEGORY_CHANCE:
        weights = profile.category_weights()
        cat = rng.choices(list(weights), weights=list(weights.values()))[0]
        return chart, spot_from_chart(chart, deal_hand_class(rng, rng.choice(hands_in_category(cat)))), "category"
    return chart, spot_from_chart(chart, deal(rng, 2)), "weighted"
