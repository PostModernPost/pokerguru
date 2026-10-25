"""The advice library: sourced, verified tips shown on result screens.

One JSON file, ``data/advice/tips.json``. Every tip carries its scope, its
sources with quotes, the checks it passed, and a status. ``verified`` (two
publishers agree), ``single_source`` (one publisher confirmed) and
``contested`` (sources disagree with each other or with the math) are all
shown, each with a short footnote saying which; ``unverified`` tips are never
shown (CLAUDE.md ground rule 1). The loader enforces the evidence requirements
so a tip can't carry a status its evidence doesn't support.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from trainer import config
from trainer.game.hand_classes import HAND_CATEGORIES
from trainer.game.positions import POSITIONS, SPOT_TYPES

log = logging.getLogger(__name__)

TIPS_PATH = Path(config.ADVICE_PATH)

STATUSES = ("verified", "single_source", "contested", "unverified")
SHOWN_STATUSES = ("verified", "single_source", "contested")
DRILLS = ("preflop_chart", "equity", "nuts", "pot_limit")
GAMES = ("nlhe", "plo")
FORMATS = ("cash", "tournament")
STREETS = ("preflop", "flop", "turn", "river")
CHECK_TYPES = ("source_fetched", "corroborated", "math_consistent", "chart_sanity")
MIN_INDEPENDENT_SOURCES = 2
ALL_POSITIONS = sorted({p for ps in POSITIONS.values() for p in ps})


class AdviceError(ValueError):
    pass


@dataclass(frozen=True)
class Source:
    name: str
    publisher: str
    url: str
    quote: str
    accessed: str  # YYYY-MM-DD


@dataclass(frozen=True)
class Check:
    type: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class Scope:
    drills: tuple[str, ...] = ()
    games: tuple[str, ...] = ()
    formats: tuple[str, ...] = ()
    positions: tuple[str, ...] = ()
    spot_types: tuple[str, ...] = ()
    streets: tuple[str, ...] = ()
    hand_categories: tuple[str, ...] = ()
    stack_bb_min: float | None = None
    stack_bb_max: float | None = None

    def matches(self, **ctx: Any) -> bool:
        """True if every scope field that is set agrees with the context given.

        Context keys: drill, game, format, position, spot_type, street,
        hand_category, stack_bb. A missing context key only fails when the
        scope restricts that field.
        """
        for key, allowed in (("drill", self.drills), ("game", self.games), ("format", self.formats),
                             ("position", self.positions), ("spot_type", self.spot_types),
                             ("street", self.streets), ("hand_category", self.hand_categories)):
            if allowed and ctx.get(key) not in allowed:
                return False
        stack = ctx.get("stack_bb")
        if self.stack_bb_min is not None and (stack is None or stack < self.stack_bb_min):
            return False
        if self.stack_bb_max is not None and (stack is None or stack > self.stack_bb_max):
            return False
        return True


@dataclass(frozen=True)
class Tip:
    id: str
    text: str
    status: str
    scope: Scope
    sources: tuple[Source, ...]
    checks: tuple[Check, ...]
    notes: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_verified(self) -> bool:
        return self.status == "verified"

    def evidence(self) -> dict:
        return {
            "id": self.id,
            "status": self.status,
            "sources": [s.__dict__ for s in self.sources],
            "checks": [c.__dict__ for c in self.checks],
            "notes": self.notes,
        }

    def public(self) -> dict:
        names: list[str] = []
        for src in self.sources:
            n = src.publisher or src.name
            if n not in names:
                names.append(n)
        return {"id": self.id, "text": self.text, "status": self.status, "source_names": names}


def _fail(where: str, msg: str) -> None:
    raise AdviceError(f"{where}: {msg}")


def _strs(where: str, value: Any, allowed: tuple[str, ...] | list[str], label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        _fail(where, f"scope.{label} must be a list of strings")
    bad = [v for v in value if v not in allowed]
    if bad:
        _fail(where, f"scope.{label} has unknown values {bad}; allowed: {list(allowed)}")
    return tuple(value)


def _date(where: str, text: Any, label: str) -> str:
    try:
        date.fromisoformat(text)
    except (TypeError, ValueError):
        _fail(where, f"{label} must be a date like 2026-10-25, got {text!r}")
    return text


def tip_from_dict(d: Any, where: str = "<tip>") -> Tip:
    if not isinstance(d, dict):
        _fail(where, "tip must be an object")
    for key in ("id", "text", "status", "scope", "sources", "checks"):
        if key not in d:
            _fail(where, f"missing {key!r}")
    tid = d["id"]
    if not isinstance(tid, str) or not tid.strip():
        _fail(where, "'id' must be a non-empty string")
    where = f"{where} (tip {tid})"
    text = d["text"]
    if not isinstance(text, str) or len(text.strip()) < 15:
        _fail(where, "'text' must be a sentence or two")
    status = d["status"]
    if status not in STATUSES:
        _fail(where, f"status must be one of {STATUSES}")

    sc = d["scope"]
    if not isinstance(sc, dict):
        _fail(where, "'scope' must be an object")
    for k in sc:
        if k not in ("drills", "games", "formats", "positions", "spot_types", "streets", "hand_categories",
                     "stack_bb_min", "stack_bb_max"):
            _fail(where, f"unknown scope field {k!r}")
    for k in ("stack_bb_min", "stack_bb_max"):
        v = sc.get(k)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0):
            _fail(where, f"scope.{k} must be a positive number")
    scope = Scope(
        drills=_strs(where, sc.get("drills"), DRILLS, "drills"),
        games=_strs(where, sc.get("games"), GAMES, "games"),
        formats=_strs(where, sc.get("formats"), FORMATS, "formats"),
        positions=_strs(where, sc.get("positions"), ALL_POSITIONS, "positions"),
        spot_types=_strs(where, sc.get("spot_types"), SPOT_TYPES, "spot_types"),
        streets=_strs(where, sc.get("streets"), STREETS, "streets"),
        hand_categories=_strs(where, sc.get("hand_categories"), HAND_CATEGORIES, "hand_categories"),
        stack_bb_min=sc.get("stack_bb_min"),
        stack_bb_max=sc.get("stack_bb_max"),
    )
    if not scope.drills:
        _fail(where, "scope.drills is required: advice is only shown inside its scope")

    sources = []
    for i, s in enumerate(d["sources"] if isinstance(d["sources"], list) else []):
        sw = f"{where} source {i + 1}"
        if not isinstance(s, dict):
            _fail(sw, "must be an object")
        for k in ("name", "publisher", "url"):
            if not isinstance(s.get(k), str) or not s[k].strip():
                _fail(sw, f"'{k}' is required")
        if not s["url"].startswith(("http://", "https://")):
            _fail(sw, "'url' must be a web address")
        quote = str(s.get("quote") or "")
        accessed = str(s.get("accessed") or "")
        if status == "verified":
            # Verified means the page was fetched and the passage recorded; placeholders don't pass.
            if len(quote.strip()) < 20:
                _fail(sw, "'quote' must be the actual supporting passage, not a summary")
            _date(sw, accessed, "accessed")
        elif accessed:
            _date(sw, accessed, "accessed")
        sources.append(Source(s["name"], s["publisher"], s["url"], quote, accessed))

    checks = []
    for i, c in enumerate(d["checks"] if isinstance(d["checks"], list) else []):
        cw = f"{where} check {i + 1}"
        if not isinstance(c, dict) or c.get("type") not in CHECK_TYPES or not isinstance(c.get("passed"), bool):
            _fail(cw, f"needs 'type' in {CHECK_TYPES} and a boolean 'passed'")
        if not isinstance(c.get("detail"), str) or not c["detail"].strip():
            _fail(cw, "'detail' is required")
        checks.append(Check(c["type"], c["passed"], c["detail"]))

    if status in ("contested", "single_source") and not sources:
        _fail(where, f"a {status} tip is shown to the user, so it needs its sources")
    if status == "single_source":
        if not any(c.type == "source_fetched" and c.passed for c in checks):
            _fail(where, "a single_source tip needs a passed 'source_fetched' check")
        if any(c.type == "math_consistent" and not c.passed for c in checks):
            _fail(where, "a tip that fails its math check is contested, not single_source")
    if status == "verified":
        publishers = {s.publisher.strip().lower() for s in sources}
        if len(publishers) < MIN_INDEPENDENT_SOURCES:
            _fail(where, f"a verified tip needs at least {MIN_INDEPENDENT_SOURCES} sources from different publishers")
        passed = {c.type for c in checks if c.passed}
        if {"source_fetched", "corroborated"} - passed:
            _fail(where, "a verified tip needs passed 'source_fetched' and 'corroborated' checks")
        if any(not c.passed for c in checks):
            _fail(where, "a verified tip can't have a failed check")

    return Tip(id=tid, text=text.strip(), status=status, scope=scope, sources=tuple(sources),
               checks=tuple(checks), notes=str(d.get("notes", "")), tags=tuple(d.get("tags", [])))


class AdviceLibrary:
    def __init__(self, tips: list[Tip]):
        ids = [t.id for t in tips]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise AdviceError(f"duplicate tip ids: {sorted(dupes)}")
        self.tips = list(tips)
        self._by_id = {t.id: t for t in tips}

    @classmethod
    def load(cls, path: str | Path = TIPS_PATH) -> "AdviceLibrary":
        path = Path(path)
        if not path.exists():
            log.warning("No advice file at %s; no tips will be shown", path)
            return cls([])
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise AdviceError(f"{path}: not valid JSON ({e})") from None
        if not isinstance(data, dict) or not isinstance(data.get("tips"), list):
            raise AdviceError(f"{path}: expected an object with a 'tips' list")
        return cls([tip_from_dict(t, where=str(path)) for t in data["tips"]])

    def get(self, tip_id: str) -> Tip:
        return self._by_id[tip_id]

    def verified(self) -> list[Tip]:
        return [t for t in self.tips if t.is_verified]

    def contested(self) -> list[Tip]:
        return [t for t in self.tips if t.status == "contested"]

    def matching(self, limit: int = 3, **ctx: Any) -> list[Tip]:
        """Shown tips (verified, single_source, contested) whose scope fits the context.

        Verified first, then single-source, then contested; narrower scopes
        first within each. Unverified tips are never returned.
        """
        rank = {"verified": 0, "single_source": 1, "contested": 2}
        hits = [t for t in self.tips if t.status in SHOWN_STATUSES and t.scope.matches(**ctx)]
        hits.sort(key=lambda t: (rank[t.status], -_specificity(t.scope)))
        return hits[:limit]


def _specificity(s: Scope) -> int:
    n = sum(1 for f in (s.games, s.formats, s.positions, s.spot_types, s.streets, s.hand_categories) if f)
    return n + (s.stack_bb_min is not None) + (s.stack_bb_max is not None)
