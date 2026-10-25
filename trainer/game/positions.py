"""Table positions in preflop action order. No strategy here."""

from __future__ import annotations

POSITIONS: dict[int, tuple[str, ...]] = {
    6: ("UTG", "HJ", "CO", "BTN", "SB", "BB"),
    9: ("UTG", "UTG1", "UTG2", "LJ", "HJ", "CO", "BTN", "SB", "BB"),
}

TABLE_SIZES = tuple(POSITIONS)


def positions_for(table_size: int) -> tuple[str, ...]:
    try:
        return POSITIONS[table_size]
    except KeyError:
        raise ValueError(
            f"Unsupported table size {table_size}; supported: {list(POSITIONS)}"
        ) from None


def preflop_index(table_size: int, pos: str) -> int:
    """Position's place in preflop action order (UTG = 0, BB = last)."""
    order = positions_for(table_size)
    if pos not in order:
        raise ValueError(f"{pos!r} is not a position at a {table_size}-handed table")
    return order.index(pos)


def acts_before(table_size: int, a: str, b: str) -> bool:
    """True if position a acts before position b preflop."""
    return preflop_index(table_size, a) < preflop_index(table_size, b)


SPOT_TYPES = ("rfi", "vs_open", "vs_3bet")


def spot_position_error(table_size: int, spot_type: str, hero: str, villain: str | None) -> str | None:
    """Why these positions can't form this spot type, or None if they can.

    rfi:     folded to hero; no villain; hero isn't BB.
    vs_open: villain opened, so villain acts before hero.
    vs_3bet: hero opened and villain 3-bet, so hero acts before villain.
    """
    if table_size not in POSITIONS:
        return f"table size {table_size!r} not supported; supported: {list(POSITIONS)}"
    positions = POSITIONS[table_size]
    if spot_type not in SPOT_TYPES:
        return f"spot type must be one of {list(SPOT_TYPES)}, got {spot_type!r}"
    if hero not in positions:
        return f"hero_pos {hero!r} is not a {table_size}-handed position {list(positions)}"
    if spot_type == "rfi":
        if villain is not None:
            return "rfi spots must have villain_pos null"
        if hero == "BB":
            return "BB can't raise first in (everyone folded means BB wins the blinds)"
        return None
    if villain not in positions:
        return f"villain_pos {villain!r} is not a {table_size}-handed position"
    if villain == hero:
        return "hero and villain can't be the same position"
    if spot_type == "vs_open" and not acts_before(table_size, villain, hero):
        return f"vs_open: opener {villain} must act before hero {hero}"
    if spot_type == "vs_3bet":
        if hero == "BB":
            return "vs_3bet: BB can't be the opener"
        if not acts_before(table_size, hero, villain):
            return f"vs_3bet: 3-bettor {villain} must act after hero {hero}"
    return None


def valid_spots(table_size: int, spot_type: str) -> list[tuple[str, str | None]]:
    """Every (hero, villain) pair that forms a valid spot of this type."""
    positions = positions_for(table_size)
    villains: list[str | None] = [None] if spot_type == "rfi" else list(positions)
    return [
        (h, v)
        for h in positions
        for v in villains
        if spot_position_error(table_size, spot_type, h, v) is None
    ]
