"""Finding the chart for a preflop decision in the game, for bots and for your feedback.

The bots and the feedback share one rule: use a real chart for this exact table size
if there is one; otherwise use the 9-handed chart for the seat with the same place
relative to the button (trainer.gamemode.engine.chart_positions). Sample charts are
never used.
"""

from __future__ import annotations

from dataclasses import dataclass

from trainer.charts.loader import Chart, ChartLibrary
from trainer.gamemode.engine import Hand, chart_positions


@dataclass(frozen=True)
class ChartMatch:
    chart: Chart
    spot_type: str
    villain_idx: int | None
    approximate: bool  # a 9-handed chart standing in for another table size


class ChartIndex:
    def __init__(self, library: ChartLibrary):
        self.by_key: dict[tuple, Chart] = {}
        for c in library.find(game="nlhe", format="cash", include_samples=False):
            if c.stack_bb == 100 and c.spot_type in ("rfi", "vs_open", "vs_3bet"):
                self.by_key[(c.table_size, c.spot_type, c.hero_pos, c.villain_pos)] = c

    def lookup(self, n: int, spot_type: str, hero_pos: str, villain_pos: str | None,
               hero_chart_pos: str, villain_chart_pos: str | None) -> tuple[Chart, bool] | None:
        exact = self.by_key.get((n, spot_type, hero_pos, villain_pos))
        if exact:
            return exact, False
        nine = self.by_key.get((9, spot_type, hero_chart_pos, villain_chart_pos))
        if nine:
            return nine, n != 9
        return None

    def for_decision(self, hand: Hand, idx: int) -> ChartMatch | None:
        """The chart that covers this player's preflop decision right now, if any.

        Covered: nobody raised yet (raise first in), one raise and you were not the
        raiser (facing an open), you opened and got 3-bet. Limpers are ignored for the
        raise-first-in case. Anything else (4-bets, squeezes, limped pots in the BB) has
        no chart.
        """
        if hand.street != "preflop":
            return None
        agg = hand.aggression("preflop")
        cpos = chart_positions(hand.n)
        pos = hand.positions
        if agg["raises"] == 0:
            if pos[idx] == "BB":
                return None
            r = self.lookup(hand.n, "rfi", pos[idx], None, cpos[idx], None)
            return ChartMatch(r[0], "rfi", None, r[1]) if r else None
        if agg["raises"] == 1 and agg["opener"] != idx:
            v = agg["opener"]
            r = self.lookup(hand.n, "vs_open", pos[idx], pos[v], cpos[idx], cpos[v])
            return ChartMatch(r[0], "vs_open", v, r[1]) if r else None
        if agg["raises"] == 2 and agg["opener"] == idx:
            v = agg["last_raiser"]
            r = self.lookup(hand.n, "vs_3bet", pos[idx], pos[v], cpos[idx], cpos[v])
            return ChartMatch(r[0], "vs_3bet", v, r[1]) if r else None
        return None


def chart_raise_action(chart: Chart) -> str | None:
    for a in chart.actions:
        if a.startswith("raise"):
            return a
    return None


def game_action_to_chart(chart: Chart, kind: str, all_in: bool) -> str | None:
    """Map what a player did in the game onto the chart's action names."""
    if kind == "fold":
        return "fold"
    if kind in ("call", "check"):
        return "call" if "call" in chart.actions else None
    if kind in ("bet", "raise", "allin"):
        if all_in and "allin" in chart.actions:
            return "allin"
        return chart_raise_action(chart)
    return None
