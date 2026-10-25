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
