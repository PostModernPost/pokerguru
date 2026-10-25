"""Basic opponents for the game mode.

Preflop they play the verified charts (sampling mixed strategies), so what they
open, call and 3-bet with is real. Where no chart applies (4-bets, limped pots,
squeezes) and on every later street they use a simple strength-and-odds policy:
bet when strong, call when the price is right, fold otherwise, with a little
randomness. That part is NOT strategy advice; it exists to keep the game moving
and is labelled "basic opponents" in the app. Nothing a bot does is ever shown
to you as the right play.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

from trainer.game.fast_equity import equity_vs_range
from trainer.game.hand_classes import hand_class_of
from trainer.game.hand_features import equity_rank_all
from trainer.gamemode.charts import ChartIndex, ChartMatch
from trainer.gamemode.engine import Hand

BOT_EQUITY_ITERATIONS = 120


@dataclass(frozen=True)
class Preset:
    name: str
    bet_threshold: float      # equity vs a random hand needed to bet/raise for value
    call_margin: float        # how much more equity than the pot odds require before calling (can be negative)
    bluff_chance: float       # chance to bet with nothing when checked to, heads-up or 3-way
    preflop_loosen: float     # extra chance to call instead of folding a chart fold preflop


PRESETS = {
    "standard": Preset("standard", 0.62, 0.06, 0.10, 0.0),
    "loose": Preset("loose", 0.55, -0.06, 0.18, 0.25),
}


class BotPolicy:
    def __init__(self, charts: ChartIndex, preset: str = "standard"):
        self.charts = charts
        self.preset = PRESETS[preset]
        self.ranks = equity_rank_all()

    # ---------- preflop ----------
    def _chart_decision(self, hand: Hand, idx: int, match: ChartMatch, rng: random.Random) -> tuple[str, int | None]:
        chart = match.chart
        hc = hand_class_of("".join(hand.hole[idx]))
        freqs = chart.frequencies(hc)
        action = rng.choices(list(freqs), weights=list(freqs.values()))[0]
        if self.preset.preflop_loosen and action == "fold" and "call" in chart.actions and rng.random() < self.preset.preflop_loosen:
            action = "call"
        legal = hand.legal()
        if action == "fold":
            return ("fold", None) if legal["can_fold"] else ("check", None)
        if action == "call":
            return "call", None
        if action == "allin":
            return "raise", legal.get("max_raise_to")
        size_bb = float(action.split("_", 1)[1])
        bb = hand.blinds[1]
        agg = hand.aggression("preflop")
        facing = chart.facing or {}
        if match.spot_type == "rfi":
            to = size_bb * bb
        elif match.spot_type == "vs_open":
            ratio = size_bb / facing.get("open_size_bb", 2.5)
            to = ratio * agg["last_to"]
        else:
            ratio = size_bb / facing.get("threebet_size_bb", 8)
            to = ratio * agg["last_to"]
        return "raise", int(round(to))

    def _strength_preflop(self, hand: Hand, idx: int, rng: random.Random) -> tuple[str, int | None]:
        rank = self.ranks[hand_class_of("".join(hand.hole[idx]))]
        legal = hand.legal()
        loose = 1.6 if self.preset.name == "loose" else 1.0
        if rank <= 8 * loose:
            return "raise", legal.get("max_raise_to") if legal["to_call"] > 0 else legal.get("pot_raise_to")
        if rank <= 25 * loose or legal["to_call"] == 0:
            return ("call", None) if legal["to_call"] > 0 else ("check", None)
        return "fold", None

    # ---------- postflop ----------
    def _postflop(self, hand: Hand, idx: int, rng: random.Random) -> tuple[str, int | None]:
        legal = hand.legal()
        nprng = np.random.default_rng(rng.getrandbits(32))
        eq = equity_vs_range(hand.hole[idx], tuple(hand.board), None, BOT_EQUITY_ITERATIONS, nprng)
        eq += rng.uniform(-0.04, 0.04)
        opponents = len(hand.players_in_hand()) - 1
        pot, to_call = hand.pot, legal["to_call"]
        p = self.preset
        if to_call == 0:
            strong = eq > p.bet_threshold + 0.05 * max(0, opponents - 1)
            bluff = eq < 0.33 and opponents <= 2 and rng.random() < p.bluff_chance
            if (strong or bluff) and "min_raise_to" in legal:
                size = int(round(pot * rng.choice((0.5, 0.66, 0.75))))
                return "raise", max(legal["min_raise_to"], min(legal["max_raise_to"], size))
            return "check", None
        required = to_call / (pot + to_call)
        if eq > 0.82 and "min_raise_to" in legal and rng.random() < 0.7:
            return "raise", int(round(legal["min_raise_to"] * 1.3 + 0.4 * pot))
        if eq >= required + p.call_margin:
            return "call", None
        return "fold", None

    def decide(self, hand: Hand, idx: int, rng: random.Random) -> tuple[str, int | None]:
        if hand.street == "preflop":
            match = self.charts.for_decision(hand, idx)
            if match:
                return self._chart_decision(hand, idx, match, rng)
            legal = hand.legal()
            if legal["to_call"] == 0:
                return "check", None  # BB with no raise: take the free flop
            return self._strength_preflop(hand, idx, rng)
        return self._postflop(hand, idx, rng)

    def preflop_range(self, hand: Hand, idx: int, match: ChartMatch, kind: str) -> dict[str, float] | None:
        """Hands this bot could hold after taking `kind` from this chart spot: chart
        frequency of that action times how often it has each hand here."""
        chart = match.chart
        key = {"fold": "fold", "call": "call", "check": "call"}.get(kind, "raise")
        out = {}
        for h in chart.hands:
            f = chart.hands[h]
            if key == "raise":
                p = sum(v for a, v in f.items() if a.startswith("raise") or a == "allin")
            else:
                p = f.get(key, 0.0)
            w = (chart.deal_weights or {}).get(h, 1.0)
            if p * w > 0:
                out[h] = p * w
        return out or None
