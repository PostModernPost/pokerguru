"""Range-string importer.

Turns published range notation such as ``AA,KK,QQ,AKs,AQs:0.5,A5s:0.6`` or
``22+,A2s+,KTo+`` into per-hand-class frequencies, and builds a chart's
``hands`` table from one range string per action.

A parsing bug here would silently corrupt every answer built on it, so the
parser is strict: anything it does not fully understand raises
``RangeParseError`` instead of being skipped.

Supported notation (tokens separated by commas or new lines; spaces ignored):

    AA          one pocket pair
    AKs / AKo   suited / offsuit
    AK          both AKs and AKo
    22+         22 up to AA
    A2s+        kicker goes up to one below the top card: A2s, A3s, ... AKs
    KTo+        KTo, KJo, KQo
    A2+         both suited and offsuit versions of A2s+
    22-55       inclusive span of pairs (either order)
    A2s-A5s     inclusive kicker span with the same top card and suffix
    X:0.5       any of the above at 50% frequency (also ``X:50%``)

A hand class may appear only once per range string. Overlaps such as
``A2s+,A5s:0.6`` are rejected because different tools resolve them differently.
"""

from __future__ import annotations

import math
import re

from trainer.game.hand_classes import ALL_HAND_CLASSES, RANK_VALUE, RANKS

# Allowed rounding slack when checking that a hand's frequencies add up to 1.
SUM_TOLERANCE = 1e-6


class RangeParseError(ValueError):
    pass


_HAND_RE = re.compile(r"^([AKQJT2-9])([AKQJT2-9])([so]?)$")


def _normalize_hand(text: str) -> str:
    """Upper-case the ranks and lower-case the suited/offsuit letter."""
    if len(text) == 3:
        return text[:2].upper() + text[2].lower()
    return text.upper()


def _parse_hand(text: str, token: str) -> tuple[str, str, str]:
    """Split one hand like 'AKs' into (high rank, low rank, suffix)."""
    norm = _normalize_hand(text)
    m = _HAND_RE.match(norm)
    if not m:
        if len(text) == 4:
            raise RangeParseError(
                f"{token!r}: specific card combos like 'AsKs' are not supported; "
                "use hand classes like 'AKs'"
            )
        raise RangeParseError(f"{token!r}: {text!r} is not a hand like 'AA', 'AKs', 'AKo' or 'AK'")
    r1, r2, suffix = m.groups()
    if RANK_VALUE[r1] < RANK_VALUE[r2]:
        r1, r2 = r2, r1
    if r1 == r2 and suffix:
        raise RangeParseError(f"{token!r}: a pair can't be suited or offsuit")
    return r1, r2, suffix


def _expand_suffix(r1: str, r2: str, suffix: str) -> list[str]:
    if r1 == r2:
        return [r1 + r2]
    if suffix:
        return [r1 + r2 + suffix]
    return [r1 + r2 + "s", r1 + r2 + "o"]


def _ranks_between(lo: str, hi: str) -> list[str]:
    """Ranks from lo up to hi inclusive, lowest first."""
    return [r for r in reversed(RANKS) if RANK_VALUE[lo] <= RANK_VALUE[r] <= RANK_VALUE[hi]]


def _expand_item(item: str, token: str) -> list[str]:
    if not item:
        raise RangeParseError(f"{token!r}: missing hand")

    if "-" in item:
        parts = item.split("-")
        if len(parts) != 2 or not all(parts):
            raise RangeParseError(f"{token!r}: a span needs exactly two hands, like '22-55'")
        a = _parse_hand(parts[0], token)
        b = _parse_hand(parts[1], token)
        a_pair, b_pair = a[0] == a[1], b[0] == b[1]
        if a_pair and b_pair:
            lo, hi = sorted((a[0], b[0]), key=RANK_VALUE.get)
            return [r + r for r in _ranks_between(lo, hi)]
        if a_pair or b_pair:
            raise RangeParseError(f"{token!r}: can't span between a pair and a non-pair")
        if a[0] != b[0]:
            raise RangeParseError(
                f"{token!r}: both ends of a span must share the top card, like 'A2s-A5s'"
            )
        if a[2] != b[2]:
            raise RangeParseError(f"{token!r}: both ends of a span must have the same s/o suffix")
        lo, hi = sorted((a[1], b[1]), key=RANK_VALUE.get)
        out = []
        for k in _ranks_between(lo, hi):
            out.extend(_expand_suffix(a[0], k, a[2]))
        return out

    if item.endswith("+"):
        r1, r2, suffix = _parse_hand(item[:-1], token)
        if r1 == r2:
            return [r + r for r in _ranks_between(r1, "A")]
        # Kicker climbs to one rank below the top card.
        top_kicker = RANKS[RANKS.index(r1) + 1]
        out = []
        for k in _ranks_between(r2, top_kicker):
            out.extend(_expand_suffix(r1, k, suffix))
        return out

    r1, r2, suffix = _parse_hand(item, token)
    return _expand_suffix(r1, r2, suffix)


def _parse_weight(text: str, token: str) -> float:
    raw = text.strip()
    percent = raw.endswith("%")
    if percent:
        raw = raw[:-1]
    try:
        w = float(raw)
    except ValueError:
        raise RangeParseError(f"{token!r}: {text!r} is not a number") from None
    if not math.isfinite(w):
        raise RangeParseError(f"{token!r}: frequency must be a real number")
    if percent:
        w /= 100
    if w < 0 or w > 1:
        hint = " (for percentages write '50%' or 0.5)" if w > 1 else ""
        raise RangeParseError(f"{token!r}: frequency must be between 0 and 1{hint}")
    return w


def parse_range(text: str) -> dict[str, float]:
    """Parse a range string into {hand class: frequency}.

    Hands not mentioned are simply absent from the result.
    """
    result: dict[str, float] = {}
    for raw_token in re.split(r"[,\n]", text):
        token = re.sub(r"\s+", "", raw_token)
        if not token:
            continue
        if token.count(":") > 1:
            raise RangeParseError(f"{token!r}: more than one ':'")
        item, _, weight_text = token.partition(":")
        if _ and not weight_text:
            raise RangeParseError(f"{token!r}: missing frequency after ':'")
        weight = _parse_weight(weight_text, token) if weight_text else 1.0
        for hand in _expand_item(item, token):
            if hand in result:
                raise RangeParseError(
                    f"{token!r}: {hand} is already in this range; each hand may appear once"
                )
            result[hand] = weight
    return result


def build_hands(
    action_ranges: dict[str, str],
    default_action: str = "fold",
) -> dict[str, dict[str, float]]:
    """Build a chart's ``hands`` table from one range string per action.

    Every one of the 169 hand classes gets an entry. Whatever frequency the
    given actions leave over goes to ``default_action`` (normally fold).

    If ``default_action`` itself is given a range, no filling is done and every
    hand must already add up to exactly 1.
    """
    if not action_ranges:
        raise RangeParseError("No action ranges given")
    parsed = {}
    for action, text in action_ranges.items():
        try:
            parsed[action] = parse_range(text)
        except RangeParseError as e:
            raise RangeParseError(f"action {action!r}: {e}") from None
    explicit_default = default_action in parsed

    hands: dict[str, dict[str, float]] = {}
    for hand in ALL_HAND_CLASSES:
        freqs = {a: parsed[a][hand] for a in parsed if parsed[a].get(hand, 0) > 0}
        total = math.fsum(freqs.values())
        if total > 1 + SUM_TOLERANCE:
            detail = ", ".join(f"{a} {f:g}" for a, f in freqs.items())
            raise RangeParseError(f"{hand}: frequencies add up to {total:g} (> 1): {detail}")
        leftover = 1 - total
        if leftover > SUM_TOLERANCE:
            if explicit_default:
                raise RangeParseError(
                    f"{hand}: frequencies add up to {total:g}, not 1. Since a "
                    f"{default_action!r} range was given explicitly, every hand must be covered"
                )
            freqs[default_action] = round(leftover, 6)
        hands[hand] = {a: round(f, 6) for a, f in freqs.items()}
    return hands
