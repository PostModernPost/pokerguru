"""Turn published range strings into a chart JSON file.

Example (on Windows, type it all on one line without the backslashes):

    python scripts/import_range.py --id nlhe-cash-6max-100bb-rfi-CO \\
        --table-size 6 --type rfi --hero CO \\
        --action "raise_2.5=AA,KK,QQ,AKs,AQs:0.5,A5s:0.6" \\
        --source-name "My chart source" --out data/charts/nlhe/rfi-6max-CO.json

Give one --action per non-fold action. Whatever frequency is left over for a
hand becomes fold. The file is checked with the same loader the app uses
before it is written.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from trainer.charts.loader import chart_from_dict, dump_chart_json  # noqa: E402
from trainer.charts.range_parser import RangeParseError, build_hands  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--id", required=True)
    p.add_argument("--game", default="nlhe")
    p.add_argument("--format", default="cash", choices=["cash", "tournament"])
    p.add_argument("--table-size", type=int, required=True, choices=[6, 9])
    p.add_argument("--stack-bb", type=float, default=100.0)
    p.add_argument("--type", required=True, choices=["rfi", "vs_open", "vs_3bet"])
    p.add_argument("--hero", required=True, help="hero position, e.g. CO")
    p.add_argument("--villain", default=None, help="opener (vs_open) or 3-bettor (vs_3bet)")
    p.add_argument("--open-size", type=float, help="open size in bb (vs_open / vs_3bet)")
    p.add_argument("--threebet-size", type=float, help="3-bet size in bb (vs_3bet)")
    p.add_argument("--action", action="append", required=True, metavar="NAME=RANGE",
                   help='e.g. "raise_2.5=AA,KK,AQs:0.5" (repeat for each action)')
    p.add_argument("--source-name", required=True)
    p.add_argument("--source-url", default="")
    p.add_argument("--source-notes", default="")
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)

    action_ranges: dict[str, str] = {}
    for item in args.action:
        name, sep, rng = item.partition("=")
        if not sep or not name.strip():
            p.error(f"--action must look like NAME=RANGE, got {item!r}")
        action_ranges[name.strip()] = rng

    facing = {}
    if args.open_size:
        facing["open_size_bb"] = args.open_size
    if args.threebet_size:
        facing["threebet_size_bb"] = args.threebet_size
    stack_bb = float(args.stack_bb)
    stack = int(stack_bb) if stack_bb.is_integer() else stack_bb

    try:
        hands = build_hands(action_ranges)
    except RangeParseError as e:
        print(f"Range error: {e}", file=sys.stderr)
        return 1
    actions = ["fold"] + [a for a in action_ranges if a != "fold"]
    chart = {
        "id": args.id,
        "game": args.game,
        "format": args.format,
        "table_size": args.table_size,
        "stack_bb": stack,
        "spot": {"type": args.type, "hero_pos": args.hero, "villain_pos": args.villain,
                 "facing": facing or None},
        "actions": actions,
        "source": {"name": args.source_name, "url": args.source_url, "notes": args.source_notes},
        "hands": hands,
    }
    chart_from_dict(chart, where=args.out)  # raises if anything is off
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(dump_chart_json(chart), encoding="utf-8")
    print(f"Wrote {out} ({len(hands)} hands)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
