"""Solve heads-up push/fold and write the results as chart files.

    python scripts/build_pushfold_charts.py

Writes data/charts/pushfold/*.json: for each stack depth and ante setting, one
"push" chart (SB: shove or fold) and one "vs_push" chart (BB facing the shove:
call or fold). Source is marked "computed" with the method, so the Preflop
drill treats them as real charts, not samples.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trainer import config  # noqa: E402
from trainer.charts.loader import chart_from_dict, dump_chart_json  # noqa: E402
from trainer.solvers.pushfold import solve  # noqa: E402

OUT_DIR = ROOT / "data" / "charts" / "pushfold"


def chart_dicts(stack_bb: float, ante_bb: float, iterations: int) -> list[dict]:
    sol = solve(stack_bb, ante_bb, iterations=iterations)
    ante_tag = f"-ante{ante_bb:g}" if ante_bb else ""
    stack_tag = f"{stack_bb:g}bb"
    notes = (
        f"Heads-up push/fold Nash equilibrium by chip EV (no ICM). Equal stacks of {stack_bb:g}bb, "
        f"blinds 0.5/1, ante {ante_bb:g}bb per player. Fictitious play, {iterations} iterations, over the "
        f"169 hand classes with card removal; all-in equities from data/equity_cache/preflop_equity_169.json "
        f"(Monte Carlo, PokerKit-ranked). Exploitability {sol.exploitability_bb:.4f} bb/hand. "
        f"SB EV {sol.sb_ev_bb:+.3f} bb/hand. Mixed frequencies mean the hand is close to indifferent."
    )
    source = {"name": "computed", "url": "", "notes": notes}
    push = {
        "id": f"pushfold-hu-{stack_tag}{ante_tag}-push-SB",
        "game": "nlhe", "format": "tournament", "table_size": 2, "stack_bb": stack_bb,
        "spot": {"type": "push", "hero_pos": "SB", "villain_pos": None,
                 "facing": {"ante_bb": ante_bb} if ante_bb else None},
        "actions": ["fold", "allin"],
        "source": source,
        "hands": {h: _freqs("allin", f) for h, f in sol.push_dict().items()},
    }
    call = {
        "id": f"pushfold-hu-{stack_tag}{ante_tag}-vs_push-BB",
        "game": "nlhe", "format": "tournament", "table_size": 2, "stack_bb": stack_bb,
        "spot": {"type": "vs_push", "hero_pos": "BB", "villain_pos": "SB",
                 "facing": {"open_size_bb": stack_bb, **({"ante_bb": ante_bb} if ante_bb else {})}},
        "actions": ["fold", "call"],
        "source": source,
        "hands": {h: _freqs("call", f) for h, f in sol.call_dict().items()},
    }
    return [push, call]


def _freqs(action: str, f: float) -> dict[str, float]:
    f = round(float(f), 3)
    if f >= 0.999:
        return {action: 1.0}
    if f <= 0.001:
        return {"fold": 1.0}
    return {action: f, "fold": round(1 - f, 3)}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    start = time.time()
    count = 0
    for ante in config.PUSHFOLD_ANTES_BB:
        for stack in config.PUSHFOLD_STACKS_BB:
            for chart in chart_dicts(stack, ante, config.PUSHFOLD_ITERATIONS):
                chart_from_dict(chart)  # validate with the app's own loader
                (OUT_DIR / f"{chart['id']}.json").write_text(dump_chart_json(chart), encoding="utf-8")
                count += 1
            print(f"  {stack:g}bb ante {ante:g}: done ({time.time() - start:.0f}s)", flush=True)
    print(f"Wrote {count} charts to {OUT_DIR}")


if __name__ == "__main__":
    main()
