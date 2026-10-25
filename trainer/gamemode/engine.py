"""One hand of no-limit Hold'em on top of PokerKit's state machine, plus seat bookkeeping.

PokerKit numbers players so that index 0 posts the small blind, index 1 the big
blind and the last index is the button (heads-up: index 1 is the button and posts
the small blind). The table keeps its own fixed seats and rotates the button, so a
seat's PokerKit index changes every hand.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from pokerkit import Automation, Deck, Mode, NoLimitTexasHoldem

from trainer.game.dealing import card_str
from trainer.game.positions import POSITIONS

AUTOMATIONS = (
    Automation.ANTE_POSTING, Automation.BET_COLLECTION, Automation.BLIND_OR_STRADDLE_POSTING,
    Automation.HOLE_CARDS_SHOWING_OR_MUCKING, Automation.HAND_KILLING,
    Automation.CHIPS_PUSHING, Automation.CHIPS_PULLING, Automation.RUNOUT_COUNT_SELECTION,
)
STREETS = ("preflop", "flop", "turn", "river")
NINE = POSITIONS[9]  # UTG, UTG1, UTG2, LJ, HJ, CO, BTN, SB, BB


def pk_positions(n: int) -> list[str]:
    """Position name for each PokerKit index at an n-handed table (the brief's names)."""
    if n == 2:
        return ["BB", "SB"]
    if n in POSITIONS:  # the brief names 6- and 9-handed seats
        names = list(POSITIONS[n])  # ... BTN, SB, BB
        return ["SB", "BB"] + names[:-3] + ["BTN"]
    return chart_positions(n)  # other sizes: 9-handed names counted back from the button


def chart_positions(n: int) -> list[str]:
    """9-handed chart seat for each PokerKit index, counted back from the button
    (BTN, CO, HJ, ...). Used when no chart exists for this table size."""
    if n == 2:
        return ["BB", "BTN"]
    non_blind = n - 2
    late_first = ["BTN", "CO", "HJ", "LJ", "UTG2", "UTG1", "UTG"][:non_blind]
    return ["SB", "BB"] + list(reversed(late_first))


@dataclass
class Event:
    street: str
    idx: int
    kind: str          # post_sb, post_bb, fold, check, call, bet, raise, allin, deal
    amount: int = 0    # for call: amount added; for bet/raise: total bet this street ("to")
    text: str = ""


@dataclass
class Hand:
    """A hand in progress. Chip amounts are in the table's units (1 unit = $1 at $1/$2)."""
    n: int
    hero_idx: int
    stacks: tuple[int, ...]
    blinds: tuple[int, int]
    rng: random.Random
    state: object = field(init=False)
    deck: list = field(init=False)
    events: list[Event] = field(default_factory=list)
    hole: dict[int, tuple[str, str]] = field(default_factory=dict)
    board: list[str] = field(default_factory=list)
    hand_no: int = 0
    showdown: list[int] = field(default_factory=list)  # players whose cards were tabled at the end

    def __post_init__(self):
        sb, bb = self.blinds
        self.state = NoLimitTexasHoldem.create_state(
            AUTOMATIONS, False, 0, (sb, bb), bb, tuple(self.stacks), self.n, mode=Mode.CASH_GAME)
        self.deck = list(Deck.STANDARD)
        self.rng.shuffle(self.deck)
        self.positions = pk_positions(self.n)
        if self.n == 2:
            self.events += [Event("preflop", 1, "post_sb", sb), Event("preflop", 0, "post_bb", bb)]
        else:
            self.events += [Event("preflop", 0, "post_sb", sb), Event("preflop", 1, "post_bb", bb)]
        self._deal_if_needed()

    # ---------- dealing ----------
    def _draw(self, k: int) -> list:
        out = self.deck[:k]
        del self.deck[:k]
        return out

    def _deal_if_needed(self) -> None:
        st = self.state
        while st.status and (st.can_deal_hole() or st.can_deal_board() or st.can_burn_card()):
            if st.can_burn_card():
                st.burn_card(self._draw(1)[0])  # burn from our deck so PokerKit never deals a card twice
                continue
            if st.can_deal_hole():
                who = st.hole_dealee_index
                card = self._draw(1)
                st.deal_hole(card)
                have = self.hole.get(who, ())
                self.hole[who] = tuple(have) + (card_str(card[0]),)
            else:
                cards = self._draw(st.board_dealing_count)
                st.deal_board(cards)
                self.board += [card_str(c) for c in cards]
                name = {3: "flop", 4: "turn", 5: "river"}.get(len(self.board), self.street)
                self.events.append(Event(name, -1, "deal", 0, " ".join(card_str(c) for c in cards)))

    # ---------- reading the state ----------
    @property
    def street(self) -> str:
        i = self.state.street_index
        return STREETS[i] if i is not None and i < 4 else STREETS[min(len(self.board) - 2, 3)] if self.board else "preflop"

    @property
    def finished(self) -> bool:
        return not self.state.status

    @property
    def actor(self) -> int | None:
        return self.state.actor_index if self.state.status else None

    @property
    def hero_turn(self) -> bool:
        return self.actor == self.hero_idx

    @property
    def pot(self) -> int:
        return int(self.state.total_pot_amount)

    def bets(self) -> list[int]:
        return [int(b) for b in self.state.bets]

    def stacks_now(self) -> list[int]:
        return [int(s) for s in self.state.stacks]

    def in_hand(self, idx: int) -> bool:
        """Still holding cards: during the hand PokerKit's status; once it is over, whoever
        reached the showdown (PokerKit marks losers as out, which would read as 'folded')."""
        if self.finished and self.showdown:
            return idx in self.showdown
        return bool(self.state.statuses[idx])

    def players_in_hand(self) -> list[int]:
        return [i for i in range(self.n) if self.in_hand(i)]

    def to_call(self, idx: int | None = None) -> int:
        if idx is not None and idx != self.actor:
            return max(0, max(self.bets()) - self.bets()[idx])
        return int(self.state.checking_or_calling_amount or 0)

    def legal(self) -> dict:
        """What the actor may do now, with amounts (total 'to' amounts for raises)."""
        st = self.state
        if not st.status or st.actor_index is None:
            return {}
        to_call = int(st.checking_or_calling_amount or 0)
        out = {"to_call": to_call, "can_fold": to_call > 0 and bool(st.can_fold()),
               "can_check": to_call == 0, "can_call": to_call > 0}
        if st.can_complete_bet_or_raise_to():
            out["min_raise_to"] = int(st.min_completion_betting_or_raising_to_amount)
            out["max_raise_to"] = int(st.max_completion_betting_or_raising_to_amount)
            out["pot_raise_to"] = int(st.pot_completion_betting_or_raising_to_amount)
        return out

    # ---------- acting ----------
    def act(self, kind: str, amount: int | None = None) -> Event:
        """kind: fold | check | call | raise (amount = total to). Raises are clamped to legal."""
        st = self.state
        idx = st.actor_index
        if idx is None or not st.status:
            raise ValueError("nobody to act")
        legal = self.legal()
        street = self.street
        alive = self.players_in_hand()
        if kind == "fold":
            if not legal["can_fold"]:
                kind = "check"  # folding when a check is free is never right; PokerKit warns too
            else:
                st.fold()
                ev = Event(street, idx, "fold")
        if kind in ("check", "call"):
            amt = legal["to_call"]
            st.check_or_call()
            ev = Event(street, idx, "call" if amt > 0 else "check", amt)
        elif kind == "raise":
            if "min_raise_to" not in legal:
                st.check_or_call()
                ev = Event(street, idx, "call" if legal["to_call"] else "check", legal["to_call"])
            else:
                to = int(round(amount if amount is not None else legal["min_raise_to"]))
                to = max(legal["min_raise_to"], min(legal["max_raise_to"], to))
                st.complete_bet_or_raise_to(to)
                is_bet = legal["to_call"] == 0
                all_in = self.stacks_now()[idx] == 0
                ev = Event(street, idx, "allin" if all_in else ("bet" if is_bet else "raise"), to)
        elif kind != "fold":
            raise ValueError(f"unknown action {kind!r}")
        self.events.append(ev)
        self._deal_if_needed()
        if self.finished and kind != "fold" and len(alive) > 1:
            self.showdown = alive  # everyone still in when the betting ended: a trainer shows them all
        return ev

    # ---------- after the hand ----------
    def result(self) -> dict:
        st = self.state
        payoffs = [int(p) for p in st.payoffs]
        shown = {i: self.hole[i] for i in self.showdown if i in self.hole}
        return {"payoffs": payoffs, "stacks": self.stacks_now(), "board": list(self.board),
                "shown": shown, "winners": [i for i, p in enumerate(payoffs) if p > 0]}

    # ---------- betting context (for bots and feedback) ----------
    def street_events(self, street: str | None = None) -> list[Event]:
        s = street or self.street
        return [e for e in self.events if e.street == s and e.idx >= 0]

    def aggression(self, street: str | None = None) -> dict:
        """Raises so far on a street: count, who made the last one, and the amounts."""
        evs = self.street_events(street)
        raises = [e for e in evs if e.kind in ("bet", "raise", "allin")]
        limps = [e for e in evs if e.kind == "call"]
        opener = raises[0].idx if raises else None
        return {"raises": len(raises), "opener": opener,
                "last_raiser": raises[-1].idx if raises else None,
                "open_to": raises[0].amount if raises else None,
                "last_to": raises[-1].amount if raises else None,
                "callers": [e.idx for e in limps]}
