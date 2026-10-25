"""Build the 9-handed 100bb cash charts from RangeConverter's free PDF, and verify them.

    python scripts/import_rangeconverter.py            # from the grids already read into _pages/grids.json
    python scripts/import_rangeconverter.py --fetch    # download the PDF again and re-read the grids first

Primary source: RangeConverter, "9 max 100bb Live Cash GTO Ranges" (free PDF,
https://rangeconverter.com/articles/poker-charts-9-max-100bb-no-limit-texas-holdem).
Its charts are images, so scripts/rangeconverter_grids.py reads the colours of
every cell (see that file). This script then:

1. Checks the read grids against the totals printed on the charts (raise-first-in
   percentages per seat), so a mis-read grid cannot slip through.
2. Turns each grid into a chart in our format: open to 3bb; 3-bet to 10bb (12bb
   from the SB, 13bb from the BB); 4-bet to 26bb (28bb against a BB 3-bet) or
   all-in. Facing a 3-bet, hands the hero would not have opened get deal weight
   0 so the drill never deals them; partly-opened hands get their opening share.
3. Verifies every chart against unrelated publishers (CLAUDE.md verification
   standard): Pokerspot's 9-max charts for every spot type; RunoutPoker,
   PokerCoaching and Preflop Wizard for the opening ranges; our verified Pokalab
   6-max charts for the big blind's defence where the seats left to act are the
   same. A chart whose main action agrees with another publisher for at least
   AGREEMENT_MIN of the hands is "verified"; below that it is "contested" and
   shown with a footnote; with no second publisher it is "single_source".
4. Sanity checks (premiums always open, earlier seats open fewer hands).
5. Writes data/charts/nlhe/rangeconverter/*.json and _verification.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from trainer.charts.loader import ChartLibrary, chart_from_dict, dump_chart_json  # noqa: E402
from trainer.charts.range_parser import parse_range  # noqa: E402
from trainer.charts.sources import agreement, primary  # noqa: E402
from trainer.game.hand_classes import ALL_HAND_CLASSES, combo_count  # noqa: E402

PDF_URL = "https://rangeconverter.com/downloads/9-max-100bb-Poker-Charts-No-Limit-Texas-Holdem-Cash"
ARTICLE_URL = "https://rangeconverter.com/articles/poker-charts-9-max-100bb-no-limit-texas-holdem"
OUT_DIR = ROOT / "data" / "charts" / "nlhe" / "rangeconverter"
PAGES = OUT_DIR / "_pages"
AGREEMENT_MIN = 0.85

# RangeConverter's seat names -> the brief's 9-handed names.
RC_SEATS = ["UTG", "UTG1", "MP", "LJ", "HJ", "CO", "BTN", "SB", "BB"]
RC_TO_OURS = {"UTG": "UTG", "UTG1": "UTG1", "MP": "UTG2", "LJ": "LJ", "HJ": "HJ", "CO": "CO", "BTN": "BTN", "SB": "SB", "BB": "BB"}
# Pokerspot's 9-max seat names -> ours.
PS_TO_OURS = {"UTG": "UTG", "UTG+1": "UTG1", "UTG+2": "UTG2", "MP": "LJ", "HJ": "HJ", "CO": "CO", "BTN": "BTN", "SB": "SB"}
# RunoutPoker's seat names -> ours.
RO_TO_OURS = {"UTG": "UTG", "UTG+1": "UTG1", "UTG+2": "UTG2", "LJ": "LJ", "HJ": "HJ", "CO": "CO", "BTN": "BTN", "SB": "SB"}
# Our 9-max big-blind spots whose seats left to act match a Pokalab 6-max spot.
POKALAB_BB = {"LJ": "UTG", "HJ": "HJ", "CO": "CO", "BTN": "BTN", "SB": "SB"}

OPEN_BB = 3.0
THREEBET_BB = {"SB": 12.0, "BB": 13.0}  # anyone else 3-bets to 10bb
FOURBET_BB = {"BB": 28.0}               # against anyone else the 4-bet is to 26bb

# Totals printed on the RFI page, read by eye from the chart images (raise %). The grid
# reader must land within RFI_TOLERANCE points of each, or the import stops.
RFI_PRINTED = {"UTG": 10.09, "UTG1": 11.44, "MP": 13.29, "LJ": 15.8, "HJ": 19.76, "CO": 25.62, "BTN": 40.49, "SB": 46.36}
RFI_TOLERANCE = 1.0
NOISE = 0.08  # colour shares below this are bleed from the next cell, not a drawn frequency

RC_NOTE = ("RangeConverter free PDF '9 max 100bb Live Cash GTO Ranges' (solver output, simplified: "
           "'the frequency of an action for each hand combo is rounded to the nearest 50%'). Open to 3bb; "
           "3-bets to 10bb (SB 12bb, BB 13bb); 4-bets to 26bb (28bb vs a BB 3-bet) or all-in. Frequencies read "
           "from the drawn grids by scripts/rangeconverter_grids.py and checked against the printed totals.")


def grid_titles(spot_type: str, section: str | None, n: int) -> list[tuple[str, str | None]]:
    """(hero, villain) for each grid on a page, in RangeConverter's seat order, as the
    page titles read them (e.g. 'LJ vs UTG RFI', 'UTG vs HJ 3bet')."""
    if spot_type == "rfi":
        out = [(s, None) for s in RC_SEATS[:-1]]
    elif spot_type == "vs_open":
        heroes = ["UTG1", "MP"] if section == "EPMP" else [section]
        out = [(h, v) for h in heroes for v in RC_SEATS[:RC_SEATS.index(h)]]
    else:
        out = [(section, v) for v in RC_SEATS[RC_SEATS.index(section) + 1:]]
    if len(out) != n:
        raise SystemExit(f"{spot_type} {section}: expected {len(out)} grids, the page has {n}")
    return out


def snap(v: float) -> float:
    """Pixel shares -> drawn frequencies. RangeConverter draws halves (and the odd quarter or
    thin strip); a read of 0.45/0.55 is a half with a pixel of noise, so values within 0.07 of a
    quarter snap to it, anything else keeps a 0.05 grid."""
    q = round(v * 4) / 4
    if abs(v - q) <= 0.07:
        return q
    return round(v * 20) / 20


def round_freqs(cell: dict | None, actions: dict[str, str]) -> tuple[dict[str, float], float]:
    """Cell colours -> chart frequencies (summing to 1) and the in-play weight."""
    if cell is None:
        return {"fold": 1.0}, 0.0
    weight = snap(cell.get("_in_play", 1.0))
    # Colour read across a neighbouring cell's edge shows up as a few percent of a wrong
    # colour; the smallest share RangeConverter draws is far larger, so drop the noise.
    shares = {actions[k]: v for k, v in cell.items() if k != "_in_play" and k in actions and v >= NOISE}
    if not shares:
        return {"fold": 1.0}, weight
    total = sum(shares.values())
    freqs = {a: snap(v / total) for a, v in shares.items()}
    freqs = {a: f for a, f in freqs.items() if f > 0}
    drift = round(1 - sum(freqs.values()), 4)
    if drift:
        top = max(freqs, key=freqs.get)
        freqs[top] = round(freqs[top] + drift, 4)
    return freqs, weight


def build_chart(spot_type: str, hero_rc: str, villain_rc: str | None, hands_raw: dict) -> dict:
    hero, villain = RC_TO_OURS[hero_rc], RC_TO_OURS.get(villain_rc) if villain_rc else None
    if spot_type == "rfi":
        actions = {"fold": "fold", "raise": f"raise_{OPEN_BB:g}"}
        facing = None
        ident = f"rangeconverter-nlhe-cash-9max-100bb-rfi-{hero}"
    elif spot_type == "vs_open":
        three = THREEBET_BB.get(hero, 10.0)
        actions = {"fold": "fold", "call": "call", "raise": f"raise_{three:g}"}
        facing = {"open_size_bb": OPEN_BB}
        ident = f"rangeconverter-nlhe-cash-9max-100bb-vs_open-{hero}-vs-{villain}"
    else:
        three = THREEBET_BB.get(villain, 10.0)
        four = FOURBET_BB.get(villain, 26.0)
        actions = {"fold": "fold", "call": "call", "raise": f"raise_{four:g}", "allin": "allin"}
        facing = {"open_size_bb": OPEN_BB, "threebet_size_bb": three}
        ident = f"rangeconverter-nlhe-cash-9max-100bb-vs_3bet-{hero}-vs-{villain}"
    hands, weights = {}, {}
    for h in ALL_HAND_CLASSES:
        freqs, w = round_freqs(hands_raw.get(h), actions)
        hands[h] = freqs
        weights[h] = w
    used = ["fold"] + [a for a in actions.values() if a != "fold" and any(a in f for f in hands.values())]
    data = {
        "id": ident, "game": "nlhe", "format": "cash", "table_size": 9, "stack_bb": 100,
        "spot": {"type": spot_type, "hero_pos": hero, "villain_pos": villain, "facing": facing},
        "actions": used,
        "source": {"name": "RangeConverter (solver output, simplified)", "url": ARTICLE_URL, "status": "", "notes": ""},
        "hands": hands,
    }
    if spot_type == "vs_3bet":
        data["deal_weights"] = weights
    return data


# ---------------- corroborating publishers ----------------

def from_sets(raise_hands=(), call_hands=()) -> dict[str, dict[str, float]]:
    out = {}
    for h in ALL_HAND_CLASSES:
        if h in raise_hands:
            out[h] = {"raise": 1.0}
        elif h in call_hands:
            out[h] = {"call": 1.0}
        else:
            out[h] = {"fold": 1.0}
    return out


def load_corroboration() -> dict:
    ps = json.load(open(PAGES / "pokerspot_9max_cash.json"))["ranges"]
    ro = json.load(open(PAGES / "runout_fullring_100bb.json"))["charts"]
    strings = json.load(open(PAGES / "corroboration_rfi.json"))["sources"]
    others: dict[tuple, list[tuple[str, dict]]] = {}

    def add(key, name, hands):
        others.setdefault(key, []).append((name, hands))

    for seat, hands in ps["RFI_CASH_9"].items():
        add(("rfi", PS_TO_OURS[seat], None), "Pokerspot", from_sets(set(hands)))
    for seat, rc in ps["VS_RAISE_CASH_9"].items():
        add(("vs_open", PS_TO_OURS[seat]), "Pokerspot", from_sets(set(rc["raise"]), set(rc["call"])))
    for seat, rc in ps["VS_3BET_CASH_9"].items():
        add(("vs_3bet", PS_TO_OURS[seat]), "Pokerspot", from_sets(set(rc["raise"]), set(rc["call"])))
    for seat, cells in ro.items():
        add(("rfi", RO_TO_OURS[seat], None), "RunoutPoker", {h: {a: 1.0} for h, a in cells.items()})
    for src in strings:
        seat_map = src.get("seat_map") or src["seat_map_to_9max_by_players_behind"]
        for seat, text in src["rfi"].items():
            if seat in seat_map:
                add(("rfi", seat_map[seat], None), src["publisher"], from_sets(set(parse_range(text))))
    pokalab = ChartLibrary.from_directory(ROOT / "data" / "charts" / "nlhe" / "pokalab")
    for c in pokalab.charts:
        if c.spot_type == "vs_open" and c.hero_pos == "BB":
            for ours9, six in POKALAB_BB.items():
                if six == c.villain_pos:
                    add(("vs_open", "BB", ours9), "Pokalab (6-max, same seats left to act)", c.hands)
    return others


def agreement_in_play(a: dict, b: dict, weights: dict[str, float]) -> dict:
    """Agreement over the hands the hero actually has here (deal weight >= 0.5)."""
    keep = [h for h in ALL_HAND_CLASSES if weights.get(h, 1.0) >= 0.5]
    def main_action(f):  # a 4-bet and an all-in are both "raise" for this comparison
        return "raise" if primary(f) in ("allin", "raise") else primary(f)
    same = sum(1 for h in keep if main_action(a[h]) == main_action(b[h]))
    return {"primary_action_agreement": round(same / len(keep), 4), "hands_compared": len(keep)}


def corroborate(data: dict, others: dict) -> tuple[str, list[dict]]:
    st = data["spot"]
    keys = [(st["type"], st["hero_pos"], st["villain_pos"]), (st["type"], st["hero_pos"])]
    cands = [c for k in keys for c in others.get(k, [])]
    results = []
    for name, hands in cands:
        if data["spot"]["type"] == "vs_3bet":
            r = agreement_in_play(data["hands"], hands, data["deal_weights"])
        else:
            r = agreement(data["hands"], hands)
        results.append({"publisher": name, **r})
    if not results:
        return "single_source", results
    best = max(r["primary_action_agreement"] for r in results)
    return ("verified" if best >= AGREEMENT_MIN else "contested"), results


def describe(results: list[dict], status: str) -> str:
    if not results:
        return "No second publisher found for this exact spot (single source)."
    parts = [f"{r['publisher']} agrees on the main action for {r['primary_action_agreement']:.0%} of hands"
             + (f" ({r['hands_compared']} hands the hero opens)" if "hands_compared" in r else "")
             for r in results]
    tail = {"verified": "Verified.", "contested": "Below the agreement bar, so marked as sources disagree."}[status]
    return "Corroboration: " + "; ".join(parts) + ". " + tail


def sanity(charts: list[dict]) -> list[str]:
    problems = []
    rfi = {c["spot"]["hero_pos"]: c for c in charts if c["spot"]["type"] == "rfi"}
    order = ["UTG", "UTG1", "UTG2", "LJ", "HJ", "CO", "BTN"]
    widths = {}
    for pos, c in rfi.items():
        for h in ("AA", "KK", "QQ", "AKs", "AKo"):
            if c["hands"][h].get("fold", 0) > 0:
                problems.append(f"rfi {pos}: {h} folds sometimes")
        widths[pos] = sum((1 - f.get("fold", 0)) * combo_count(h) for h, f in c["hands"].items()) / 1326
    for a, b in zip(order, order[1:]):
        if a in widths and b in widths and widths[a] > widths[b] + 0.005:
            problems.append(f"rfi: {a} opens more hands ({widths[a]:.1%}) than {b} ({widths[b]:.1%})")
    for c in charts:
        if c["spot"]["type"] != "rfi":
            for h in ("AA", "KK"):
                if c["hands"][h].get("fold", 0) > 0:
                    problems.append(f"{c['id']}: {h} folds sometimes")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fetch", action="store_true", help="download the PDF and re-read the grids")
    args = ap.parse_args()
    PAGES.mkdir(parents=True, exist_ok=True)
    grids_path = PAGES / "grids.json"
    if args.fetch or not grids_path.exists():
        pdf = PAGES / "9max-100bb.pdf"
        subprocess.run(["curl", "-sL", "-m", "180", "-A", "Mozilla/5.0 (poker-trainer importer)", "-o", str(pdf), PDF_URL], check=True)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "rangeconverter_grids.py"), str(pdf), str(grids_path)], check=True)
        pdf.unlink()  # 11MB; the read grids and the sha256 are what we keep
    grids = json.load(open(grids_path))

    charts: list[dict] = []
    for page in grids["pages"]:
        titles = grid_titles(page["spot_type"], page["section"], len(page["grids"]))
        for (hero, villain), g in zip(titles, page["grids"]):
            if page["spot_type"] == "rfi":
                got = g["shares"].get("raise", 0)
                want = RFI_PRINTED[hero]
                if abs(got - want) > RFI_TOLERANCE:
                    raise SystemExit(f"rfi {hero}: grid reads {got}% raise but the chart prints {want}%")
            charts.append(build_chart(page["spot_type"], hero, villain, g["hands"]))

    problems = sanity(charts)
    if problems:
        print("SANITY PROBLEMS:\n  " + "\n  ".join(problems))
        return 1

    others = load_corroboration()
    report = {"date": str(date.today()), "primary": ARTICLE_URL, "pdf": PDF_URL, "pdf_sha256": grids.get("pdf_sha256"),
              "agreement_min": AGREEMENT_MIN, "charts": []}
    counts = {"verified": 0, "contested": 0, "single_source": 0}
    for data in charts:
        status, results = corroborate(data, others)
        counts[status] += 1
        data["source"]["status"] = status
        data["source"]["notes"] = f"{RC_NOTE} Fetched {date.today()}. {describe(results, status)}"
        chart_from_dict(data, data["id"])  # validates
        (OUT_DIR / f"{data['id']}.json").write_text(dump_chart_json(data), encoding="utf-8")
        report["charts"].append({"id": data["id"], "status": status, "corroboration": results})
        print(f"{status:13s} {data['id']}")
    (OUT_DIR / "_verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\n{len(charts)} charts: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
