"""Omaha nut awareness: the best possible hand on a board, whether hero has it,
and what hero can draw to.

PokerKit evaluates every hand (``OmahaHoldemHand`` enforces "exactly two hole
cards and three board cards"; ``StandardLookup`` ranks any five cards). This
module only enumerates candidate holdings and turns results into words.

"The nuts" here means the best hand anyone at the table could hold given the
board *and hero's own cards*: nobody else can hold a card hero holds. So if
hero has the ace of spades on a three-spade board, no opponent can make the
ace-high flush, and the nuts is whatever hero or the best remaining holding
makes. When that differs from the best hand the board allows in the abstract,
``NutInfo.blocked_hand`` says what hero is blocking.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from pokerkit import Card, Deck, OmahaHoldemHand, StandardLookup
from pokerkit.lookups import Entry, Label

from trainer.game.dealing import card_str, parse_cards

_LOOKUP = StandardLookup()
HOLE = 4
RANK_ORDER = "23456789TJQKA"
RANK_WORDS = {
    "2": "deuce", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven",
    "8": "eight", "9": "nine", "T": "ten", "J": "jack", "Q": "queen", "K": "king", "A": "ace",
}
RANK_PLURALS = {r: w + ("es" if w.endswith("x") else "s") for r, w in RANK_WORDS.items()}

# Categories that count as "a made hand worth drawing to" for the draw question.
STRONG_LABELS = (Label.STRAIGHT, Label.FLUSH, Label.FULL_HOUSE, Label.FOUR_OF_A_KIND, Label.STRAIGHT_FLUSH)


@dataclass(frozen=True)
class HandInfo:
    entry: Entry
    cards: tuple[str, ...]  # the five cards that make it
    description: str

    @property
    def label(self) -> str:
        return self.entry.label.value


@dataclass(frozen=True)
class NutInfo:
    nuts: HandInfo  # best hand possible given the board and hero's cards
    hero: HandInfo
    hero_has_nuts: bool
    blocked_hand: HandInfo | None  # a better hand the board allows but hero's cards rule out


@dataclass(frozen=True)
class DrawInfo:
    """What the next card can do for hero (flop/turn only)."""
    category: str  # "nut_draw" | "non_nut_draw" | "none" | "has_nuts"
    nut_outs: tuple[str, ...]  # cards that give hero the nuts
    improving_outs: tuple[str, ...]  # cards that give hero a straight or better, stronger than now
    cards_to_come: int


def _cards(cards) -> list[Card]:
    """Accept 'AsKd', ('As', 'Kd') or a list of PokerKit Cards."""
    cards = list(cards) if not isinstance(cards, str) else cards
    if cards and not isinstance(cards, str) and isinstance(cards[0], Card):
        return cards
    joined = cards if isinstance(cards, str) else "".join(cards)
    return list(Card.parse("".join(parse_cards(joined)))) if joined else []


# ---------- describing hands ----------

def _rank_counts(cards: list[Card]) -> list[tuple[int, str]]:
    """[(count, rank)] sorted by count then rank, highest first."""
    counts: dict[str, int] = {}
    for c in cards:
        counts[c.rank.value] = counts.get(c.rank.value, 0) + 1
    return sorted(((n, r) for r, n in counts.items()), key=lambda x: (-x[0], -RANK_ORDER.index(x[1])))


def _straight_high(cards: list[Card]) -> str:
    ranks = sorted({RANK_ORDER.index(c.rank.value) for c in cards})
    if ranks == [0, 1, 2, 3, 12]:  # wheel: A-2-3-4-5
        return "5"
    return RANK_ORDER[ranks[-1]]


def describe(entry: Entry, cards: list[Card]) -> str:
    label = entry.label
    counts = _rank_counts(cards)
    if label == Label.STRAIGHT_FLUSH:
        high = _straight_high(cards)
        return "Royal flush" if high == "A" else f"Straight flush, {RANK_WORDS[high]}-high"
    if label == Label.FOUR_OF_A_KIND:
        return f"Four of a kind, {RANK_PLURALS[counts[0][1]]}"
    if label == Label.FULL_HOUSE:
        return f"Full house, {RANK_PLURALS[counts[0][1]]} full of {RANK_PLURALS[counts[1][1]]}"
    if label == Label.FLUSH:
        return f"Flush, {RANK_WORDS[counts[0][1]]}-high"
    if label == Label.STRAIGHT:
        high = _straight_high(cards)
        extra = " (Broadway)" if high == "A" else " (the wheel)" if high == "5" else ""
        return f"Straight, {RANK_WORDS[high]}-high{extra}"
    if label == Label.THREE_OF_A_KIND:
        return f"Three of a kind, {RANK_PLURALS[counts[0][1]]}"
    if label == Label.TWO_PAIR:
        return f"Two pair, {RANK_PLURALS[counts[0][1]]} and {RANK_PLURALS[counts[1][1]]}"
    if label == Label.ONE_PAIR:
        return f"One pair, {RANK_PLURALS[counts[0][1]]}"
    return f"{RANK_WORDS[counts[0][1]].capitalize()}-high, no pair"


def _info(entry: Entry, cards: list[Card]) -> HandInfo:
    return HandInfo(entry, tuple(card_str(c) for c in cards), describe(entry, cards))


# ---------- evaluation ----------

def hero_hand(hero, board) -> HandInfo:
    """Hero's best Omaha hand (two hole cards + three board cards), via PokerKit."""
    h = OmahaHoldemHand.from_game(_cards(hero), _cards(board))
    return _info(h.entry, list(h.cards))


def best_holding(board: list[Card], pool: list[Card]) -> tuple[Entry, list[Card]]:
    """Best five-card hand using exactly 3 board cards and 2 cards from `pool`."""
    best_entry: Entry | None = None
    best_cards: list[Card] = []
    for trio in combinations(board, 3):
        trio = list(trio)
        for pair in combinations(pool, 2):
            five = trio + list(pair)
            e = _LOOKUP.get_entry(five)
            if best_entry is None or e > best_entry:
                best_entry, best_cards = e, five
    assert best_entry is not None
    return best_entry, best_cards


def _unseen(board: list[Card], hero: list[Card]) -> list[Card]:
    used = {card_str(c) for c in board + hero}
    return sorted((c for c in Deck.STANDARD if card_str(c) not in used), key=card_str)


def _validate(hero: list[Card], board: list[Card]) -> None:
    if len(hero) != HOLE:
        raise ValueError(f"Omaha needs {HOLE} hole cards, got {len(hero)}")
    if len(board) not in (3, 4, 5):
        raise ValueError("Board must have 3, 4 or 5 cards")
    if len({card_str(c) for c in hero + board}) != len(hero) + len(board):
        raise ValueError("The same card appears twice")


def nut_info(hero, board) -> NutInfo:
    hero_c, board_c = _cards(hero), _cards(board)
    _validate(hero_c, board_c)
    mine = hero_hand(hero_c, board_c)
    opp_entry, opp_cards = best_holding(board_c, _unseen(board_c, hero_c))
    if mine.entry >= opp_entry:
        nuts, has = mine, True
    else:
        nuts, has = _info(opp_entry, opp_cards), False
    # What the board allows if hero's cards were unknown (for the blocker note).
    abs_entry, abs_cards = best_holding(board_c, _unseen(board_c, []))
    blocked = None
    if abs_entry > nuts.entry:
        candidate = _info(abs_entry, abs_cards)
        if candidate.description != nuts.description:
            blocked = candidate
    return NutInfo(nuts=nuts, hero=mine, hero_has_nuts=has, blocked_hand=blocked)


def _anyone_beats(hero_entry: Entry, board: list[Card], pool: list[Card]) -> bool:
    for trio in combinations(board, 3):
        trio = list(trio)
        for pair in combinations(pool, 2):
            if _LOOKUP.get_entry(trio + list(pair)) > hero_entry:
                return True
    return False


def draw_info(hero, board) -> DrawInfo:
    """Classify hero's draw with the next card (flop or turn boards only)."""
    hero_c, board_c = _cards(hero), _cards(board)
    _validate(hero_c, board_c)
    if len(board_c) == 5:
        raise ValueError("No cards to come on the river")
    now = nut_info(hero_c, board_c)
    to_come = 5 - len(board_c)
    if now.hero_has_nuts:
        return DrawInfo("has_nuts", (), (), to_come)

    unseen = _unseen(board_c, hero_c)
    nut_outs: list[str] = []
    improving: list[str] = []
    for card in unseen:
        new_board = board_c + [card]
        h = OmahaHoldemHand.from_game(hero_c, new_board)
        if h.entry > now.hero.entry and h.entry.label in STRONG_LABELS:
            improving.append(card_str(card))
            pool = [c for c in unseen if c is not card]
            if not _anyone_beats(h.entry, new_board, pool):
                nut_outs.append(card_str(card))
    if nut_outs:
        category = "nut_draw"
    elif improving:
        category = "non_nut_draw"
    else:
        category = "none"
    return DrawInfo(category, tuple(nut_outs), tuple(improving), to_come)


def possible_hands(hero, board) -> list[HandInfo]:
    """Every distinct hand description anyone could hold, strongest first (for quiz options)."""
    hero_c, board_c = _cards(hero), _cards(board)
    _validate(hero_c, board_c)
    pool = _unseen(board_c, hero_c)
    seen: dict[str, HandInfo] = {}
    for trio in combinations(board_c, 3):
        trio = list(trio)
        for pair in combinations(pool, 2):
            five = trio + list(pair)
            e = _LOOKUP.get_entry(five)
            d = describe(e, five)
            if d not in seen or e > seen[d].entry:
                seen[d] = _info(e, five)
    mine = hero_hand(hero_c, board_c)
    if mine.description not in seen or mine.entry > seen[mine.description].entry:
        seen[mine.description] = mine
    return sorted(seen.values(), key=lambda h: h.entry, reverse=True)
