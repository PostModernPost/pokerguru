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
    """Short checklist tiles: {"title", "value", "detail"}. Value is the one thing to read."""
    items = []
    pos = hand.positions[idx]
    legal = hand.legal()
    players = hand.players_in_hand()
    agg = hand.aggression()
    others = len(players) - 1
    # position
    if hand.street == "preflop":
        yet = sum(1 for i in players if i != idx and hand.bets()[i] < max(hand.bets()) and i != agg["last_raiser"])
        items.append({"title": "Position", "gloss": "position", "value": pos, "value_gloss": pos,
                      "detail": f"{yet} still to act after you · {others} other{'s' if others != 1 else ''} in"})
    else:
        last = players[-1] if players else idx
        after = len([i for i in players if i > idx])
        items.append({"title": "Position", "gloss": "position", "value": pos, "value_gloss": pos,
                      "detail": "you act last" if idx == last else f"{after} act{'s' if after == 1 else ''} after you"})
    # price
    pot, to_call = hand.pot, legal.get("to_call", 0)
    if to_call:
        req = required_equity(pot, to_call)
        items.append({"title": "Price", "gloss": "pot odds", "value": f"{pct(req)} to call", "detail": f"${to_call} into ${pot} · direct odds only"})
    else:
        items.append({"title": "Price", "gloss": "pot odds", "value": "Free to check", "detail": f"pot ${pot}"})
    # hand
    hole = hand.hole[idx]
    if hand.street == "preflop":
        hc = hand_class_of("".join(hole))
        rank = equity_rank_all()[hc]
        feats = features(hc)
        head = feats[0].split(":")[0].split(",")[0]
        items.append({"title": "Your hand", "gloss": "hand class", "value": hc, "detail": f"{head} · ranks {rank} of 169"})
        match = charts.for_decision(hand, idx)
        if match:
            play = {h: 1 - f.get("fold", 0.0) for h, f in match.chart.hands.items()}
            played = len([p for p in play.values() if p >= 0.5])
            better = sum(1 for h, p in play.items() if p > play[hc] + 1e-9)
            items.append({"title": "Your range here", "gloss": "range", "value": f"{played} of 169 hands",
                          "detail": f"played from this seat · {better} ranked above yours" if better else "played from this seat · yours is one of them"})
    else:
        now = current_hand("nlhe", hole, tuple(hand.board))
        detail = ""
        if hand.street != "river":
            o = improving_outs("nlhe", hole, tuple(hand.board))
            detail = f"{len(o.outs)} outs to {o.best_outcome} · {pct(o.hit_chance_by_river)} by the river" if o.outs else "no draw to a straight or better"
        items.append({"title": "Your hand", "gloss": "hand rankings", "value": now.description, "detail": detail})
    # table
    eff = min(hand.stacks_now()[i] + hand.bets()[i] for i in players) if players else 0
    spr = (eff / pot) if pot else 0
    items.append({"title": "Table", "gloss": "stack-to-pot ratio", "value": f"{len(players)} in the pot", "detail": f"effective stack ${eff} · {spr:.0f}× the pot"})
    if agg["last_raiser"] is not None and agg["last_raiser"] != idx:
        items.append({"title": "Aggressor", "gloss": "aggressor", "value": hand.positions[agg["last_raiser"]], "value_gloss": hand.positions[agg["last_raiser"]], "detail": f"raised to ${agg['last_to']} this round"})
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
    action: str = ""             # what you did, e.g. "called $14"
    street: str = ""

    def to_dict(self) -> dict:
        return {"kind": self.kind, "title": self.title, "grade": self.grade, "lines": self.lines,
                "footnotes": self.footnotes, "chart": self.chart, "action": self.action, "street": self.street}


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
                               "source": chart.source.get("name"), "status": chart.source.get("status"),
                               "chart_id": chart.id, "hand_class": hc},
                        {"drill_type": "game_preflop", "chart": chart, "hand_class": hc, "user_answer": kind,
                         "correct": [labels[best]], "grade": "wrong", "chosen_frequency": 0.0})
    g = grade(chart, hc, chosen, config.GRADE_THRESHOLDS)
    lines = [f"You chose {labels[chosen].lower()} (chart: {format_pct(g.chosen_frequency)}).", g.explanation]
    return Feedback("chart", f"Preflop: {hc} from {chart.hero_pos}", g.grade, lines, foot,
                    {"frequencies": [{"label": labels[a], "freq": f} for a, f in freqs.items()],
                     "source": chart.source.get("name"), "status": chart.source.get("status"),
                     "chart_id": chart.id, "hand_class": hc},
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
