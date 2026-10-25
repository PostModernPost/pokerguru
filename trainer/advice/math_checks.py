"""Math cross-checks a tip can name in its "math_check" field.

Each returns (passed, detail). They use the program's own calculations, so a
sourced claim that disagrees with the math fails verification.
"""

from __future__ import annotations

from collections.abc import Callable

from trainer.game.equity import equity_vs_random
from trainer.game.pot_limit import max_raise_to
from trainer.graders.equity import required_equity

CHECKS: dict[str, Callable[[], tuple[bool, str]]] = {}


def check(name: str):
    def deco(fn):
        CHECKS[name] = fn
        return fn
    return deco


@check("pot_odds_formula")
def _pot_odds() -> tuple[bool, str]:
    cases = [((100, 50), 0.25), ((100, 100), 1 / 3), ((100, 200), 0.4)]
    for (pot, bet), expect in cases:
        if abs(required_equity(pot, bet) - expect) > 1e-9:
            return False, f"required_equity({pot}, {bet}) != {expect}"
    return True, "call / (pot + bet + call) gives 25% for a half-pot bet, 33.3% for a pot bet, 40% for 2x pot"


@check("rule_of_2_and_4")
def _rule_of_2_and_4() -> tuple[bool, str]:
    """A nine-out flush draw: about 36% with two cards to come, about 18% with one."""
    flop = equity_vs_random("nlhe", "AhKh", "Qh7h2c", iterations=20000, seed=1).equity
    turn = equity_vs_random("nlhe", "9h8h", "Kh6h2c3d", iterations=20000, seed=1).equity
    # Against a random hand the flush draw also wins with pairs, so equity exceeds the pure
    # hit chance; check the rule against the exact hit chances instead.
    hit_two = 1 - (38 / 47) * (37 / 46)
    hit_one = 9 / 46
    ok = abs(hit_two - 0.36) < 0.02 and abs(hit_one - 0.18) < 0.02
    return ok, (f"9 outs: exact hit chance {hit_two:.1%} by the river vs rule 36%; {hit_one:.1%} on one card vs rule 18%. "
                f"(Equity vs a random hand is higher: {flop:.0%} / {turn:.0%}, since the draw can also win unimproved.)")


@check("pot_limit_formula")
def _pot_limit() -> tuple[bool, str]:
    a = max_raise_to(pot=3, largest_bet=2, hero_in=0).max_raise_to
    b = max_raise_to(pot=200, largest_bet=100, hero_in=0).max_raise_to
    return (a == 7 and b == 400), f"blinds 1/2 first in -> {a} (expect 7); pot 100 bet 100 -> {b} (expect 400)"


@check("shorter_stacks_shove_wider")
def _shove_wider() -> tuple[bool, str]:
    from trainer.solvers.pushfold import solve
    wide = solve(5, 0, iterations=200).push.sum()
    tight = solve(15, 0, iterations=200).push.sum()
    return wide > tight, f"heads-up solver: {wide:.0f} shoving classes at 5bb vs {tight:.0f} at 15bb"


@check("antes_widen_ranges")
def _antes() -> tuple[bool, str]:
    from trainer.solvers.pushfold import solve
    a = solve(10, 0, iterations=200)
    b = solve(10, 0.125, iterations=200)
    return (b.push.sum() > a.push.sum() and b.call.sum() > a.call.sum()), \
        f"heads-up 10bb: push {a.push.sum():.0f} -> {b.push.sum():.0f} classes, call {a.call.sum():.0f} -> {b.call.sum():.0f} with antes"


@check("suited_beats_offsuit")
def _suited() -> tuple[bool, str]:
    from trainer.game.preflop_equity import equity
    pairs = [("AKs", "AKo"), ("T9s", "T9o"), ("72s", "72o")]
    diffs = [equity(s, "22") - equity(o, "22") for s, o in pairs]
    return all(d > 0 for d in diffs), "equity table: suited beats the same hand offsuit vs 22 by " + \
        ", ".join(f"{d:.1%}" for d in diffs)


def run(name: str) -> tuple[bool, str]:
    if name not in CHECKS:
        return False, f"unknown math check {name!r}"
    try:
        ok, detail = CHECKS[name]()
        return bool(ok), str(detail)  # numpy bools aren't JSON/loader friendly
    except Exception as e:  # a crashing check is a failed check
        return False, f"check raised {e!r}"


@check("charts_open_wider_later")
def _charts_open_wider_later() -> tuple[bool, str]:
    """The imported real 6-max charts: each later seat (UTG -> BTN) opens at least as wide as the one before."""
    from trainer.charts.loader import ChartLibrary
    from trainer.charts.sources import range_width
    from trainer.config import CHARTS_DIR
    lib = ChartLibrary.from_directory(CHARTS_DIR / "nlhe" / "pokalab")
    widths = {c.hero_pos: range_width(c.hands) for c in lib.find(spot_types=["rfi"]) if not c.is_sample}
    order = [p for p in ("UTG", "HJ", "CO", "BTN") if p in widths]
    ok = len(order) >= 3 and all(widths[a] <= widths[b] for a, b in zip(order, order[1:]))
    return ok, "real 6-max charts open " + ", ".join(f"{p} {widths[p]:.0%}" for p in order)
