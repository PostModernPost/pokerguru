"""Chart files: loading and validation.

One JSON file per spot (format documented in README.md). Charts are the answer
keys for the preflop trainer, so the loader is strict: a malformed file raises
``ChartError`` naming the file and the problem. The one lenient case is the
brief's rule that hands missing from a file default to fold; those are filled
in and logged as a warning.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from trainer.config import SAMPLE_SOURCE_NAME
from trainer.game.hand_classes import ALL_HAND_CLASSES, HAND_CLASS_SET
from trainer.game.positions import POSITIONS, SPOT_TYPES, spot_position_error

log = logging.getLogger(__name__)

SUPPORTED_GAMES = ("nlhe",)
FORMATS = ("cash", "tournament")
DEFAULT_ACTION = "fold"
SUM_TOLERANCE = 1e-3  # published charts are often rounded to 1-3 decimals


class ChartError(ValueError):
    pass


@dataclass(frozen=True)
class Chart:
    id: str
    game: str
    format: str
    table_size: int
    stack_bb: float
    spot_type: str
    hero_pos: str
    villain_pos: str | None
    facing: dict[str, Any] | None
    actions: tuple[str, ...]
    source: dict[str, str]
    hands: dict[str, dict[str, float]]  # all 169 classes, missing ones filled with fold
    missing_hands: tuple[str, ...] = ()
    path: str | None = field(default=None, compare=False)

    @property
    def is_sample(self) -> bool:
        return self.source.get("name") == SAMPLE_SOURCE_NAME

    def frequencies(self, hand_class: str) -> dict[str, float]:
        """Frequency of every chart action for a hand, zeros included, in chart order."""
        if hand_class not in HAND_CLASS_SET:
            raise ValueError(f"Not a hand class: {hand_class!r}")
        freqs = self.hands[hand_class]
        return {a: freqs.get(a, 0.0) for a in self.actions}


def _fail(where: str, msg: str) -> None:
    raise ChartError(f"{where}: {msg}")


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def chart_from_dict(data: Any, where: str = "<chart>") -> Chart:
    """Validate a parsed chart JSON object and build a Chart."""
    if not isinstance(data, dict):
        _fail(where, "chart must be a JSON object")
    for key in ("id", "game", "format", "table_size", "stack_bb", "spot", "actions", "source", "hands"):
        if key not in data:
            _fail(where, f"missing required field {key!r}")

    chart_id = data["id"]
    if not isinstance(chart_id, str) or not chart_id.strip():
        _fail(where, "'id' must be a non-empty string")
    where = f"{where} (id {chart_id})"

    game = data["game"]
    if game not in SUPPORTED_GAMES:
        _fail(where, f"game {game!r} not supported yet (supported: {list(SUPPORTED_GAMES)})")
    fmt = data["format"]
    if fmt not in FORMATS:
        _fail(where, f"format must be one of {list(FORMATS)}, got {fmt!r}")

    table_size = data["table_size"]
    if table_size not in POSITIONS or isinstance(table_size, bool):
        _fail(where, f"table_size must be one of {list(POSITIONS)}, got {table_size!r}")
    stack_bb = data["stack_bb"]
    if not _is_number(stack_bb) or stack_bb <= 0:
        _fail(where, f"stack_bb must be a positive number, got {stack_bb!r}")

    spot = data["spot"]
    if not isinstance(spot, dict):
        _fail(where, "'spot' must be an object")
    spot_type = spot.get("type")
    if spot_type not in SPOT_TYPES:
        _fail(where, f"spot.type must be one of {list(SPOT_TYPES)}, got {spot_type!r}")
    hero = spot.get("hero_pos")
    villain = spot.get("villain_pos")
    problem = spot_position_error(table_size, spot_type, hero, villain)
    if problem:
        _fail(where, f"spot: {problem}")
    facing = spot.get("facing")
    if facing is not None:
        if not isinstance(facing, dict):
            _fail(where, "spot.facing must be an object or null")
        for k, v in facing.items():
            if not _is_number(v) or v <= 0:
                _fail(where, f"spot.facing.{k} must be a positive number, got {v!r}")

    actions = data["actions"]
    if (
        not isinstance(actions, list)
        or not actions
        or not all(isinstance(a, str) and a for a in actions)
    ):
        _fail(where, "'actions' must be a non-empty list of action names")
    if len(set(actions)) != len(actions):
        _fail(where, "'actions' has duplicates")
    if DEFAULT_ACTION not in actions:
        _fail(where, f"'actions' must include {DEFAULT_ACTION!r} (missing hands default to it)")

    source = data["source"]
    if not isinstance(source, dict) or not isinstance(source.get("name"), str) or not source["name"].strip():
        _fail(where, "'source.name' is required: every chart must say where it came from")
    source = {k: ("" if v is None else str(v)) for k, v in source.items()}

    raw_hands = data["hands"]
    if not isinstance(raw_hands, dict):
        _fail(where, "'hands' must be an object")
    hands: dict[str, dict[str, float]] = {}
    for hand, freqs in raw_hands.items():
        if hand not in HAND_CLASS_SET:
            _fail(where, f"{hand!r} is not a hand class (expected e.g. 'AA', 'AKs', 'AKo')")
        if not isinstance(freqs, dict) or not freqs:
            _fail(where, f"{hand}: frequencies must be a non-empty object")
        for action, f in freqs.items():
            if action not in actions:
                _fail(where, f"{hand}: action {action!r} is not in 'actions' {actions}")
            if not _is_number(f) or f < 0 or f > 1:
                _fail(where, f"{hand}: frequency for {action!r} must be 0..1, got {f!r}")
        total = math.fsum(freqs.values())
        if abs(total - 1) > SUM_TOLERANCE:
            _fail(where, f"{hand}: frequencies add up to {total:g}, not 1.0")
        hands[hand] = {a: float(f) for a, f in freqs.items()}

    missing = tuple(h for h in ALL_HAND_CLASSES if h not in hands)
    if missing:
        shown = ", ".join(missing[:12]) + (" ..." if len(missing) > 12 else "")
        log.warning("%s: %d hands missing, treated as fold: %s", where, len(missing), shown)
        for h in missing:
            hands[h] = {DEFAULT_ACTION: 1.0}

    return Chart(
        id=chart_id,
        game=game,
        format=fmt,
        table_size=table_size,
        stack_bb=stack_bb,
        spot_type=spot_type,
        hero_pos=hero,
        villain_pos=villain,
        facing=dict(facing) if facing else None,
        actions=tuple(actions),
        source=source,
        hands={h: hands[h] for h in ALL_HAND_CLASSES},
        missing_hands=missing,
        path=None,
    )


def load_chart(path: str | Path) -> Chart:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ChartError(f"{path}: not valid JSON ({e})") from None
    chart = chart_from_dict(data, where=str(path))
    object.__setattr__(chart, "path", str(path))
    return chart


class ChartLibrary:
    """All charts found under a folder, searchable by spot."""

    def __init__(self, charts: list[Chart]):
        self.charts = list(charts)
        self._by_id: dict[str, Chart] = {}
        seen_spots: dict[tuple, str] = {}
        for c in self.charts:
            if c.id in self._by_id:
                raise ChartError(f"Duplicate chart id {c.id!r} ({self._by_id[c.id].path} and {c.path})")
            self._by_id[c.id] = c
            key = spot_key(c)
            if key in seen_spots:
                raise ChartError(
                    f"Charts {seen_spots[key]!r} and {c.id!r} describe the same spot; keep only one"
                )
            seen_spots[key] = c.id

    @classmethod
    def from_directory(cls, root: str | Path) -> "ChartLibrary":
        root = Path(root)
        charts = [load_chart(p) for p in sorted(root.rglob("*.json"))]
        return cls(charts)

    def get(self, chart_id: str) -> Chart:
        try:
            return self._by_id[chart_id]
        except KeyError:
            raise KeyError(f"No chart with id {chart_id!r}") from None

    def find(
        self,
        *,
        game: str | None = None,
        format: str | None = None,
        table_sizes: list[int] | None = None,
        hero_positions: list[str] | None = None,
        spot_types: list[str] | None = None,
        stack_bb: float | None = None,
        formats: list[str] | None = None,
        stacks: list[float] | None = None,
    ) -> list[Chart]:
        """Charts matching every filter given. Empty or None filters match everything."""
        out = []
        for c in self.charts:
            if game and c.game != game:
                continue
            if format and c.format != format:
                continue
            if formats and c.format not in formats:
                continue
            if stacks and c.stack_bb not in stacks:
                continue
            if table_sizes and c.table_size not in table_sizes:
                continue
            if hero_positions and c.hero_pos not in hero_positions:
                continue
            if spot_types and c.spot_type not in spot_types:
                continue
            if stack_bb is not None and c.stack_bb != stack_bb:
                continue
            out.append(c)
        return out

    def __len__(self) -> int:
        return len(self.charts)


def spot_key(c: Chart) -> tuple:
    facing = tuple(sorted((c.facing or {}).items()))
    return (c.game, c.format, c.table_size, c.stack_bb, c.spot_type, c.hero_pos, c.villain_pos, facing)


def dump_chart_json(data: dict) -> str:
    """Chart dict as JSON text, one hand per line so files are easy to read and diff."""
    head = {k: v for k, v in data.items() if k != "hands"}
    lines = json.dumps(head, indent=2)[:-2].rstrip()  # drop the closing brace
    hand_lines = [f"    {json.dumps(h)}: {json.dumps(f)}" for h, f in data["hands"].items()]
    return lines + ',\n  "hands": {\n' + ",\n".join(hand_lines) + "\n  }\n}\n"
