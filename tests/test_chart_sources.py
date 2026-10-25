"""The real-chart importer: parser behaviour on small synthetic pages, and the shipped charts."""

import json

from trainer.charts.sources import agreement, parse_holdempro, parse_pokalab, range_width, sanity_problems
from trainer.config import CHARTS_DIR
from trainer.game.hand_classes import ALL_HAND_CLASSES


def _pokalab_page(charts):
    """charts: list of (heading, {hand: [(action, pct), ...]})."""
    out = []
    for heading, hands in charts:
        out.append(f"<h3>{heading}</h3>")
        for h in ALL_HAND_CLASSES:
            segs = "".join(f'<div style="width:{p}%" title="{a}: {p:.2f}%"></div>' for a, p in hands.get(h, []))
            out.append('<div class="relative w-full h-full cursor-pointer x"><div title="reach: 100%">' + segs +
                       f'</div><span class="tracking-tight block">{h}</span></div>')
    return "\n".join(out)


def test_parse_pokalab_synthetic():
    rfi = {h: [("raise_2.5bb", 100.0)] for h in ("AA", "KK", "QQ", "AKs")}
    rfi["A5s"] = [("raise_2.5bb", 40.0)]  # rest is fold (drawn as empty space)
    bb = {h: [("3bet_13bb", 100.0)] for h in ("AA", "KK")}
    bb["76s"] = [("call", 70.0), ("3bet_13bb", 10.0)]
    charts = parse_pokalab(_pokalab_page([("LJ opening range", rfi), ("BB vs LJ open", bb)]))
    assert len(charts) == 2
    a, b = charts
    assert (a.spot_type, a.hero_pos, a.open_size_bb) == ("rfi", "UTG", 2.5)
    assert a.hands["A5s"] == {"raise_2.5": 0.4, "fold": 0.6} and a.hands["72o"] == {"fold": 1.0}
    assert (b.spot_type, b.hero_pos, b.villain_pos) == ("vs_open", "BB", "UTG")
    assert b.hands["76s"] == {"call": 0.7, "raise_13": 0.1, "fold": 0.2}
    assert b.actions == ["fold", "call", "raise_13"]


def test_parse_holdempro_synthetic():
    cells = [f"{h} — Open-raise 100%" if h in ("AA", "KK") else f"{h} — Fold 100%" for h in ALL_HAND_CLASSES]
    cells[ALL_HAND_CLASSES.index("A5s")] = "A5s — Open-raise 50% / Fold 50%"
    bbcells = [f"{h} — 3-bet 60% / Call 40%" if h == "AA" else f"{h} — Call 100%" for h in ALL_HAND_CLASSES]
    charts = parse_holdempro({"MP": {"cells": cells}, "BB vs BTN": {"cells": bbcells}, "Other": {"cells": []}})
    assert len(charts) == 2
    assert charts[0].hero_pos == "HJ" and charts[0].hands["A5s"] == {"raise": 0.5, "fold": 0.5}
    assert charts[1].villain_pos == "BTN" and charts[1].hands["AA"] == {"raise": 0.6, "call": 0.4}


def test_agreement_and_sanity():
    a = {h: {"raise_2.5": 1.0} if h in ("AA", "KK", "QQ", "AKs", "AKo") else {"fold": 1.0} for h in ALL_HAND_CLASSES}
    b = dict(a, AKo={"fold": 1.0})
    s = agreement(a, b)
    assert s["primary_action_agreement"] == round(168 / 169, 4)
    assert range_width(a) > range_width(b)
    charts = parse_pokalab(_pokalab_page([
        ("LJ opening range", {h: [("raise_2.5bb", 100.0)] for h in ALL_HAND_CLASSES}),   # UTG opens everything
        ("HJ opening range", {h: [("raise_2.5bb", 100.0)] for h in ("AA", "KK", "QQ", "AKs")}),
    ]))
    problems = sanity_problems(charts)
    assert any("UTG opens wider" in p for p in problems)


def test_shipped_verification_report_matches_files():
    report = json.loads((CHARTS_DIR / "nlhe" / "pokalab" / "_verification.json").read_text())
    assert report["sanity_problems"] == []
    shipped = [c for c in report["charts"] if c["status"] in ("verified", "contested")]
    files = [f for f in (CHARTS_DIR / "nlhe" / "pokalab").glob("*.json") if not f.name.startswith("_")]
    assert len(shipped) == len(files)
    import json as _json
    statuses = {_json.loads(f.read_text())["source"]["status"] for f in files}
    assert statuses <= {"verified", "contested"}
    verified = [c for c in shipped if c["status"] == "verified"]
    for c in verified:
        assert c["agreement"]["primary_action_agreement"] >= report["agreement_min"]
    assert all(c["status"] in ("verified", "contested") for c in report["charts"])
