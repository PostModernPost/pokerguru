"""What to pay attention to before you act, and feedback after you act.

Every sentence here is computed. Preflop decisions covered by a chart are graded
exactly like the Preflop drill. Calls and folds facing a bet are judged on direct
pot odds against the equity you had versus the hands the bettor entered the pot
with (their preflop chart range), which is labelled as such. Bets, raises and
checks get the facts but no grade: there is no verified answer key for them yet.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import numpy as np

from trainer import config
from trainer.game.fast_equity import equity_vs_range
from trainer.game.hand_classes import hand_category, hand_class_of
from trainer.game.hand_features import equity_rank_all, features
from trainer.game.outs import current_hand, improving_outs
from trainer.gamemode.charts import ChartIndex, ChartMatch, game_action_to_chart
from trainer.gamemode.engine import Hand
from trainer.graders.preflop_chart import action_label, format_pct, grade, grade_frequency

FEEDBACK_EQUITY_ITERATIONS = 600
CHART_MARK = {"contested": "†", "single_source": "*"}


def pct(x: float) -> str:
    return f"{round(x * 100)}%"


def required_equity(pot: int, to_call: int) -> float:
    return to_call / (pot + to_call) if to_call else 0.0


# ---------------- before you act ----------------

def attention(hand: Hand, idx: int, charts: ChartIndex) -> list[dict]:
    """Short checklist items: {"title", "text"}."""
    items = []
    pos = hand.positions[idx]
    legal = hand.legal()
    players = hand.players_in_hand()
    behind = [i for i in players if i != idx and i not in hand.state.acted_player_indices] if hand.street == "preflop" else []
    agg = hand.aggression()
    # position
    if hand.street == "preflop":
        yet = sum(1 for i in players if i != idx and hand.bets()[i] < max(hand.bets()) and i not in {agg["last_raiser"]})
        items.append({"title": "Position", "text": f"You are {pos}. {len(players) - 1} other player{'s' if len(players) != 2 else ''} still in; "
                      f"{yet} still to act after you this round."})
    else:
        order = [i for i in players]
        last = order[-1] if order else idx
        items.append({"title": "Position", "text": f"You are {pos}, acting {'last' if idx == last else 'before ' + str(len([i for i in order if i > idx])) + ' player(s)'} on the {hand.street}."})
    # price
    pot, to_call = hand.pot, legal.get("to_call", 0)
    if to_call:
        req = required_equity(pot, to_call)
        items.append({"title": "Price", "text": f"Pot {pot}, {to_call} to call: you need about {pct(req)} equity to break even on a call (direct odds only)."})
    else:
        items.append({"title": "Price", "text": f"Pot {pot}; nothing to call yet."})
    # hand
    hole = hand.hole[idx]
    if hand.street == "preflop":
        hc = hand_class_of("".join(hole))
        rank = equity_rank_all()[hc]
        items.append({"title": "Your hand", "text": f"{hc}: " + "; ".join(features(hc)[:2]) + f". Ranks {rank} of 169 against a random hand."})
        match = charts.for_decision(hand, idx)
        if match:
            play = {h: 1 - f.get("fold", 0.0) for h, f in match.chart.hands.items()}
            share = sum(1 for h, p in play.items() if p > play[hc] + 1e-9)
            items.append({"title": "Your range here", "text": f"The chart for this spot plays {len([p for p in play.values() if p >= 0.5])} of the 169 hands at least half the time; "
                          f"{share} hands are played more often than yours."})
    else:
        now = current_hand("nlhe", hole, tuple(hand.board))
        text = f"{now.description}."
        if hand.street != "river":
            o = improving_outs("nlhe", hole, tuple(hand.board))
            if o.outs:
                text += f" {len(o.outs)} outs to {o.best_outcome}: about {pct(o.hit_chance_next_card)} on the next card, {pct(o.hit_chance_by_river)} by the river."
            else:
                text += " No draw to a straight or better."
        items.append({"title": "Your hand", "text": text})
    # table
    eff = min(hand.stacks_now()[i] + hand.bets()[i] for i in players) if players else 0
    spr = (eff / pot) if pot else 0
    items.append({"title": "Table", "text": f"{len(players)} players in the pot. Effective stack {eff}, about {spr:.1f} times the pot."})
    if agg["last_raiser"] is not None and agg["last_raiser"] != idx:
        items.append({"title": "Aggressor", "text": f"{hand.positions[agg['last_raiser']]} made the last raise this round, to {agg['last_to']}."})
    return items


# ---------------- after you act ----------------

@dataclass
class Feedback:
    kind: str                 # chart | odds | facts
    title: str
    grade: str | None = None  # correct | acceptable | wrong | None
    lines: list[str] = field(default_factory=list)
    footnotes: list[str] = field(default_factory=list)
    chart: dict | None = None
    attempt: dict | None = None  # what to record in the progress store

    def to_dict(self) -> dict:
        return {"kind": self.kind, "title": self.title, "grade": self.grade, "lines": self.lines,
                "footnotes": self.footnotes, "chart": self.chart}


def chart_feedback(hand: Hand, idx: int, match: ChartMatch, kind: str, all_in: bool) -> Feedback:
    chart = match.chart
    hc = hand_class_of("".join(hand.hole[idx]))
    chosen = game_action_to_chart(chart, kind, all_in)
    labels = {a: action_label(a, chart.spot_type) for a in chart.actions}
    freqs = chart.frequencies(hc)
    foot = []
    if match.approximate:
        foot.append(f"9-handed chart used for a {hand.n}-handed table (same seat counted from the button).")
    if CHART_MARK.get(chart.source.get("status", "")):
        foot.append({"contested": "† sources disagree on this chart; shown as one view",
                     "single_source": "* one publisher only for this chart"}[chart.source["status"]])
    if chosen is None:
        # e.g. limping where the chart only raises or folds
        best = max(freqs, key=freqs.get)
        return Feedback("chart", f"Preflop: {hc} from {chart.hero_pos}", "wrong",
                        [f"This chart never {'calls' if kind in ('call', 'check') else kind + 's'} here. "
                         f"With {hc} it {labels[best].lower()}s {format_pct(freqs[best])} of the time."],
                        foot, {"frequencies": [{"label": labels[a], "freq": f} for a, f in freqs.items()],
                               "source": chart.source.get("name"), "status": chart.source.get("status")},
                        {"drill_type": "game_preflop", "chart": chart, "hand_class": hc, "user_answer": kind,
                         "correct": [labels[best]], "grade": "wrong", "chosen_frequency": 0.0})
    g = grade(chart, hc, chosen, config.GRADE_THRESHOLDS)
    lines = [f"You chose {labels[chosen].lower()} (chart: {format_pct(g.chosen_frequency)}).", g.explanation]
    return Feedback("chart", f"Preflop: {hc} from {chart.hero_pos}", g.grade, lines, foot,
                    {"frequencies": [{"label": labels[a], "freq": f} for a, f in freqs.items()],
                     "source": chart.source.get("name"), "status": chart.source.get("status")},
                    {"drill_type": "game_preflop", "chart": chart, "hand_class": hc, "user_answer": chosen,
                     "correct": [labels[a] for a in g.best_actions], "grade": g.grade, "chosen_frequency": g.chosen_frequency})


def odds_feedback(hand: Hand, idx: int, kind: str, pot: int, to_call: int, villain_idx: int | None,
                  villain_range: dict[str, float] | None, seed: int) -> Feedback:
    """Call or fold facing a bet, judged on direct pot odds and equity vs the bettor's range."""
    req = required_equity(pot, to_call)
    rng = np.random.default_rng(seed)
    eq = equity_vs_range(hand.hole[idx], tuple(hand.board), villain_range, FEEDBACK_EQUITY_ITERATIONS, rng)
    who = hand.positions[villain_idx] if villain_idx is not None else "the bettor"
    vs = f"the hands {who} entered the pot with" if villain_range else "a random hand"
    margin = eq - req
    if kind == "call":
        g = "correct" if margin >= 0 else ("acceptable" if margin > -0.05 else "wrong")
        verdict = "The call is fine by direct odds." if margin >= 0 else "By direct odds this call loses a little." if g == "acceptable" else "By direct odds this call loses."
    else:
        g = "correct" if margin < 0 else ("acceptable" if margin < 0.05 else "wrong")
        verdict = "Folding was fine by direct odds." if margin < 0 else "You folded a hand that had the price to call." if g == "wrong" else "Close: the call was marginally profitable."
    lines = [f"You needed about {pct(req)} equity ({to_call} to call into {pot}). "
             f"Against {vs} you had about {pct(eq)}.", verdict]
    foot = ["* direct odds only: ignores later betting and implied odds; the opponent's range is what they entered the pot with preflop, not narrowed by later action."]
    hc = hand_class_of("".join(hand.hole[idx]))
    return Feedback("odds", f"{hand.street.capitalize()}: {kind} facing a bet", g, lines, foot, None,
                    {"drill_type": "game_call", "chart": None, "hand_class": hc, "user_answer": kind,
                     "correct": ["call" if margin >= 0 else "fold"], "grade": g, "chosen_frequency": None,
                     "equity": eq, "required": req})


def facts_feedback(hand: Hand, idx: int, kind: str, amount: int | None, villain_idx: int | None,
                   villain_range: dict[str, float] | None, seed: int) -> Feedback:
    lines = []
    if hand.street == "preflop":
        lines.append("No chart covers this exact preflop spot (limped pot, 4-bet or squeeze), so no grade.")
    else:
        lines.append(f"No verified answer key for {'bets and raises' if kind in ('bet', 'raise', 'allin') else 'checks'} after the flop yet, so no grade. The AI coach will give an opinion here in a later phase.")
    if hand.board and villain_idx is not None:
        rng = np.random.default_rng(seed)
        eq = equity_vs_range(hand.hole[idx], tuple(hand.board), villain_range, 300, rng)
        who = hand.positions[villain_idx]
        lines.append(f"For the record: against the hands {who} entered the pot with you had about {pct(eq)} equity.")
    return Feedback("facts", f"{hand.street.capitalize()}: {kind}", None, lines, [], None, None)


def hand_category_of(hc: str) -> str:
    return hand_category(hc)
