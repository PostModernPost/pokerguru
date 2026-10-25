"""Import real 6-max 100bb preflop charts from Pokalab, corroborated by HoldemPro.

    python scripts/import_real_charts.py                  # fetch both pages, verify, write charts
    python scripts/import_real_charts.py --no-fetch       # reuse pages saved in data/charts/nlhe/pokalab/_pages/

Needs network access, and Node with Playwright for the HoldemPro page (it is
drawn by JavaScript). The saved pages are kept so the import can be repeated
and audited without the network.

What it does (the verification standard in CLAUDE.md, applied to charts):
1. Downloads both pages and parses the exact frequencies from the HTML.
2. Sanity checks (premiums always raise, earlier seats open fewer hands, ...).
3. Compares each Pokalab chart with HoldemPro's chart for the same spot.
   A chart is written only if the two agree on the main action for at least
   AGREEMENT_MIN of the 169 hands; otherwise it is reported as contested.
4. Writes data/charts/nlhe/pokalab/*.json with source, assumptions, fetch date
   and the comparison numbers in the notes, plus a verification report.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trainer.charts.loader import chart_from_dict, dump_chart_json  # noqa: E402
from trainer.charts.sources import agreement, parse_holdempro, parse_pokalab, sanity_problems  # noqa: E402

POKALAB_URL = "https://www.pokalab.com/tools/preflop-charts"
HOLDEMPRO_URL = "https://holdempro.app/tools/preflop-ranges"
OUT_DIR = ROOT / "data" / "charts" / "nlhe" / "pokalab"
PAGES_DIR = OUT_DIR / "_pages"
AGREEMENT_MIN = 0.85


def fetch(url: str) -> str:
    return subprocess.run(["curl", "-sL", "-m", "60", "-A", "Mozilla/5.0 (poker-trainer importer)", url],
                          capture_output=True, text=True, check=True).stdout


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--no-fetch", action="store_true")
    args = p.parse_args()
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    pok_path = PAGES_DIR / "pokalab.html"
    if args.no_fetch and pok_path.exists():
        pokalab_html = pok_path.read_text(encoding="utf-8")
    else:
        pokalab_html = fetch(POKALAB_URL)
        pok_path.write_text(pokalab_html, encoding="utf-8")
    hp_path = PAGES_DIR / "holdempro.json"
    if not (args.no_fetch and hp_path.exists()):
        # HoldemPro draws its charts with JavaScript: render the page in Chromium (Playwright).
        subprocess.run(["node", str(ROOT / "scripts" / "fetch_holdempro.js"), str(hp_path)], check=True,
                       capture_output=True, text=True, timeout=300)
    rendered = json.loads(hp_path.read_text(encoding="utf-8"))
    today = date.today().isoformat()

    primary = parse_pokalab(pokalab_html)
    secondary = parse_holdempro(rendered)
    print(f"Pokalab: {len(primary)} charts; HoldemPro: {len(secondary)} charts")
    problems = sanity_problems(primary) + sanity_problems(secondary)
    for pr in problems:
        print("  sanity:", pr)

    by_spot = {(c.spot_type, c.hero_pos, c.villain_pos): c for c in secondary}
    report = {"date": today, "primary": POKALAB_URL, "secondary": HOLDEMPRO_URL, "agreement_min": AGREEMENT_MIN,
              "sanity_problems": problems, "charts": []}
    written = contested = 0
    for c in primary:
        other = by_spot.get((c.spot_type, c.hero_pos, c.villain_pos))
        stats = agreement(c.hands, other.hands) if other else None
        ok = other is not None and stats["primary_action_agreement"] >= AGREEMENT_MIN and not problems
        entry = {"spot": f"{c.spot_type} {c.hero_pos}" + (f" vs {c.villain_pos}" if c.villain_pos else ""),
                 "agreement": stats, "status": "verified" if ok else "contested"}
        report["charts"].append(entry)
        if not ok:
            contested += 1
            print(f"  contested: {entry['spot']} {stats}")
            continue
        vs = f"-vs-{c.villain_pos}" if c.villain_pos else ""
        chart_id = f"pokalab-nlhe-cash-6max-100bb-{c.spot_type}-{c.hero_pos}{vs}"
        facing = {"open_size_bb": c.open_size_bb or _opener_size(primary, c.villain_pos)} if c.spot_type == "vs_open" else None
        d = {
            "id": chart_id, "game": "nlhe", "format": "cash", "table_size": 6, "stack_bb": 100,
            "spot": {"type": c.spot_type, "hero_pos": c.hero_pos, "villain_pos": c.villain_pos, "facing": facing},
            "actions": c.actions,
            "source": {
                "name": "Pokalab (solver output)",
                "url": POKALAB_URL,
                "notes": (f"Pokalab free 6-max preflop charts: '{c.title}'. Solved at 100bb, opens to 2.5bb (SB to 3bb, "
                          f"no SB limp), GGPoker NL50 rake. Seat names mapped LJ->UTG for 6-max. Fetched {today}. "
                          f"Corroboration: HoldemPro's chart for the same spot agrees on the main action for "
                          f"{stats['primary_action_agreement']:.0%} of hands (mean play-frequency difference "
                          f"{stats['mean_play_frequency_diff']:.1%}); HoldemPro's charts are simplified from published "
                          f"solver outputs. Sanity checks passed. Where the two differ on a detail, these are Pokalab's numbers."),
            },
            "hands": {h: c.hands[h] for h in c.hands},
        }
        chart_from_dict(d)
        (OUT_DIR / f"{chart_id}.json").write_text(dump_chart_json(d), encoding="utf-8")
        written += 1
    (OUT_DIR / "_verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {written} charts, {contested} contested, report in {OUT_DIR / '_verification.json'}")
    return 0 if written else 1


def _opener_size(charts, villain_pos):
    for c in charts:
        if c.spot_type == "rfi" and c.hero_pos == villain_pos and c.open_size_bb:
            return c.open_size_bb
    return 2.5


if __name__ == "__main__":
    raise SystemExit(main())
