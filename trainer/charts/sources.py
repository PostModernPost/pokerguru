"""Parsers for published preflop chart pages, and the checks that verify them.

Two publishers are read straight from their HTML, because both embed exact
per-hand frequencies:

- **Pokalab** (https://www.pokalab.com/tools/preflop-charts): solver output
  for 6-max, 100bb, opens to 2.5bb (SB to 3bb), GGPoker NL50 rake. Five
  opening ranges and the big blind's defence against each open. Primary.
- **HoldemPro** (https://holdempro.app/tools/preflop-ranges): "simplified from
  widely published solver outputs" for 6-max 100bb. Used to corroborate.

Nothing here is typed from memory: every frequency comes from the page text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from trainer.game.hand_classes import ALL_HAND_CLASSES, HAND_CLASS_SET, combo_count

HAND_RE = r"(?:[AKQJT98765432]{2}[so]?)"

# Pokalab labels 6-max seats LJ/HJ/CO/BTN/SB/BB; the brief's 6-max names are UTG/HJ/CO/BTN/SB/BB.
POKALAB_POS = {"LJ": "UTG", "HJ": "HJ", "CO": "CO", "BTN": "BTN", "SB": "SB", "BB": "BB"}
# HoldemPro labels them UTG/MP/CO/BTN/SB/BB.
HOLDEMPRO_POS = {"UTG": "UTG", "MP": "HJ", "CO": "CO", "BTN": "BTN", "SB": "SB", "BB": "BB"}


@dataclass
class ParsedChart:
    publisher: str
    title: str
    spot_type: str  # rfi | vs_open
    hero_pos: str
    villain_pos: str | None
    hands: dict[str, dict[str, float]]  # hand -> {action: freq}; actions normalised (fold/call/raise_<bb>/raise)
    open_size_bb: float | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def actions(self) -> list[str]:
        seen: list[str] = []
        for f in self.hands.values():
            for a in f:
                if a not in seen:
                    seen.append(a)
        return ["fold"] + [a for a in sorted(seen) if a != "fold"]


def _normalise_action(raw: str) -> str:
    raw = raw.strip().lower()
    if raw in ("fold", "call", "check"):
        return "call" if raw == "check" else raw
    m = re.match(r"(?:raise|3-?bet|4-?bet|open-?raise|open)[_\s-]*([0-9.]+)\s*bb", raw)
    if m:
        return f"raise_{float(m.group(1)):g}"
    if raw.startswith(("raise", "3bet", "3-bet", "4bet", "4-bet", "open", "all-in", "allin")):
        return "raise"
    return raw.replace(" ", "_")


# ---------------- Pokalab ----------------

def parse_pokalab(html: str) -> list[ParsedChart]:
    """Read the ten charts on Pokalab's free preflop page."""
    heads = [(m.start(), m.group(1).strip()) for m in re.finditer(
        r"<h[23][^>]*>([^<]*?(?:opening range|BB vs [A-Z]+ open)[^<]*)</h[23]>", html)]
    if not heads:
        raise ValueError("Pokalab page: no chart headings found (page layout changed?)")
    cells = []
    starts = [m.start() for m in re.finditer(r'class="relative w-full h-full cursor-pointer', html)]
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else min(len(html), start + 4000)
        chunk = html[start:end]
        m = type("M", (), {"start": lambda self, s=start: s})()
        lab = re.search(r'tracking-tight block">(' + HAND_RE + r")</span>", chunk)
        if not lab:
            continue
        segs = re.findall(r'title="([a-zA-Z0-9_.\- ]+?): ([0-9.]+)%"', chunk)
        segs = [(a, float(p)) for a, p in segs if not a.startswith("reach")]
        cells.append((m.start(), lab.group(1), segs))
    charts: list[ParsedChart] = []
    for i, (pos, title) in enumerate(heads):
        end = heads[i + 1][0] if i + 1 < len(heads) else len(html)
        mine = [(h, s) for p, h, s in cells if pos < p < end]
        if len(mine) < 169:
            continue
        hands: dict[str, dict[str, float]] = {}
        for hand, segs in mine[:169]:
            freqs: dict[str, float] = {}
            for a, pct in segs:
                freqs[_normalise_action(a)] = freqs.get(_normalise_action(a), 0.0) + pct / 100
            total = sum(freqs.values())
            if total < 0.999:  # fold is drawn as empty space
                freqs["fold"] = freqs.get("fold", 0.0) + (1 - total)
            hands[hand] = {a: round(f, 4) for a, f in freqs.items() if f > 0.0005}
        if set(hands) != HAND_CLASS_SET:
            raise ValueError(f"Pokalab chart {title!r}: expected 169 hands, got {len(hands)}")
        m_open = re.match(r"([A-Z]+) opening range", title)
        m_def = re.match(r"BB vs ([A-Z]+) open", title)
        if m_open:
            hero, villain, st = POKALAB_POS[m_open.group(1)], None, "rfi"
        elif m_def:
            hero, villain, st = "BB", POKALAB_POS[m_def.group(1)], "vs_open"
        else:
            continue
        raise_sizes = sorted({float(a.split("_")[1]) for f in hands.values() for a in f if a.startswith("raise_")})
        pc = ParsedChart("Pokalab", title, st, hero, villain, hands)
        if st == "rfi" and raise_sizes:
            pc.open_size_bb = raise_sizes[0]
        charts.append(pc)
    return charts


# ---------------- HoldemPro ----------------

def parse_holdempro(rendered: dict) -> list[ParsedChart]:
    """Read HoldemPro's 6-max charts from the page as rendered by scripts/fetch_holdempro.js.

    `rendered` maps a tab label ("UTG", "MP", ..., "BB vs UTG", ...) to
    {"cells": ["AA — Open-raise 100%", ...]}; the page draws the charts with
    JavaScript, so a plain download only contains the first one.
    """
    charts: list[ParsedChart] = []
    for label, data in rendered.items():
        m_open = re.fullmatch(r"(UTG|MP|CO|BTN|SB)", label)
        m_def = re.fullmatch(r"BB vs (UTG|MP|CO|BTN|SB)", label)
        if not (m_open or m_def):
            continue
        st, hero, villain = ("rfi", m_open.group(1), None) if m_open else ("vs_open", "BB", m_def.group(1))
        g = []
        for cell in data.get("cells", []):
            m = re.match(r"(" + HAND_RE + r") — (.+)", cell)
            if m:
                g.append((m.group(1), m.group(2)))
        if len(g) != 169:
            continue
        hands: dict[str, dict[str, float]] = {}
        for hand, desc in g:
            freqs: dict[str, float] = {}
            for part in re.split(r"\s*[/·,]\s*", desc):
                m = re.match(r"([A-Za-z0-9 .\-]+?)\s+([0-9.]+)%", part.strip())
                if not m:
                    continue
                a = _normalise_action(m.group(1))
                freqs[a] = freqs.get(a, 0.0) + float(m.group(2)) / 100
            total = sum(freqs.values())
            if total < 0.999:
                freqs["fold"] = freqs.get("fold", 0.0) + (1 - total)
            hands[hand] = {a: round(f, 4) for a, f in freqs.items() if f > 0.0005}
        if set(hands) != HAND_CLASS_SET:
            continue
        charts.append(ParsedChart("HoldemPro", label, st,
                                  HOLDEMPRO_POS[hero], HOLDEMPRO_POS[villain] if villain else None, hands))
    return charts


# ---------------- checks ----------------

def aggression(freqs: dict[str, float]) -> float:
    """Share of the hand that is not a fold."""
    return 1 - freqs.get("fold", 0.0)


def range_width(hands: dict[str, dict[str, float]]) -> float:
    """Fraction of all 1326 combos played (not folded), weighted by combo counts."""
    return sum(aggression(f) * combo_count(h) for h, f in hands.items()) / 1326


def primary(freqs: dict[str, float]) -> str:
    """Most frequent action, with raise variants collapsed to 'raise'."""
    a = max(freqs.items(), key=lambda kv: kv[1])[0]
    return "raise" if a.startswith("raise") else a


def agreement(a: dict[str, dict[str, float]], b: dict[str, dict[str, float]]) -> dict:
    """How closely two charts for the same spot agree."""
    same = sum(1 for h in ALL_HAND_CLASSES if primary(a[h]) == primary(b[h]))
    mean_diff = sum(abs(aggression(a[h]) - aggression(b[h])) for h in ALL_HAND_CLASSES) / 169
    return {"primary_action_agreement": round(same / 169, 4), "mean_play_frequency_diff": round(mean_diff, 4),
            "width_a": round(range_width(a), 4), "width_b": round(range_width(b), 4)}


def sanity_problems(charts: list[ParsedChart]) -> list[str]:
    """Math/common-sense checks a set of real charts must pass. Empty list = fine."""
    problems: list[str] = []
    order = ["UTG", "HJ", "CO", "BTN", "SB"]
    rfi = {c.hero_pos: c for c in charts if c.spot_type == "rfi"}
    for c in rfi.values():
        for h in ("AA", "KK", "QQ", "AKs"):
            if aggression(c.hands[h]) < 0.999:
                problems.append(f"{c.publisher} {c.title}: {h} is not always raised")
    widths = [(p, range_width(rfi[p].hands)) for p in order if p in rfi]
    for (p1, w1), (p2, w2) in zip(widths, widths[1:]):
        if p1 != "SB" and p2 != "SB" and w1 > w2 + 1e-9:
            problems.append(f"{p1} opens wider ({w1:.1%}) than {p2} ({w2:.1%})")
    for c in charts:
        if c.spot_type == "vs_open":
            if aggression(c.hands["AA"]) < 0.999:
                problems.append(f"{c.publisher} {c.title}: AA folds to an open")
            if c.hands["72o"].get("fold", 0) < 0.5:
                problems.append(f"{c.publisher} {c.title}: 72o mostly continues against an open")
    return problems
