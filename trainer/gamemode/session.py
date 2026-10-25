"""A game session: fixed seats, a rotating button, stacks that carry over, rebuys,
bots that act until it is your turn, and feedback on what you did."""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field

from trainer.charts.loader import ChartLibrary
from trainer.game.hand_classes import hand_category, hand_class_of
from trainer.game.outs import current_hand
from trainer.gamemode.bots import PRESETS, BotPolicy
from trainer.gamemode.charts import ChartIndex
from trainer.gamemode.engine import Hand
from trainer.gamemode.feedback import Feedback, attention, chart_feedback, facts_feedback, odds_feedback
from trainer.progress.store import Attempt, AttemptStore

BOT_NAMES = ["Alex", "Sam", "Jordan", "Casey", "Riley", "Morgan", "Taylor", "Drew", "Quinn", "Jamie"]


@dataclass
class Seat:
    seat: int
    name: str
    is_hero: bool
    stack: int
    buy_ins: int = 1
    net: int = 0  # chips won or lost over the session, rebuys excluded


@dataclass
class GameConfig:
    players: int = 9
    small_blind: int = 1
    big_blind: int = 2
    buy_in_bb: int = 100
    bots: str = "standard"
    feedback: bool = True
    attention: bool = True
    seed: int | None = None


@dataclass
class Session:
    config: GameConfig
    library: ChartLibrary
    store: AttemptStore | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    seats: list[Seat] = field(default_factory=list)
    button: int = -1
    hand: Hand | None = None
    hand_no: int = 0
    rng: random.Random = field(init=False)
    bots: BotPolicy = field(init=False)
    charts: ChartIndex = field(init=False)
    bot_ranges: dict[int, dict[str, float] | None] = field(default_factory=dict)  # pk index -> preflop range this hand
    last_feedback: Feedback | None = None
    last_result: dict | None = None
    hand_feedback: list[dict] = field(default_factory=list)
    pending_hero_action: dict | None = None

    def __post_init__(self):
        c = self.config
        if not 2 <= c.players <= 9:
            raise ValueError("players must be 2 to 9")
        if c.bots not in PRESETS:
            raise ValueError(f"bots must be one of {list(PRESETS)}")
        self.rng = random.Random(c.seed)
        self.charts = ChartIndex(self.library)
        self.bots = BotPolicy(self.charts, c.bots)
        buy_in = c.buy_in_bb * c.big_blind
        names = BOT_NAMES[:]
        self.rng.shuffle(names)
        self.seats = [Seat(0, "You", True, buy_in)] + [Seat(i, names[i - 1], False, buy_in) for i in range(1, c.players)]
        self.button = self.rng.randrange(c.players)

    # ---------- seat <-> PokerKit index ----------
    def idx_of(self, seat: int) -> int:
        n = self.config.players
        if n == 2:
            return 1 if seat == self.button else 0
        return (seat - self.button - 1) % n

    def seat_of(self, idx: int) -> int:
        n = self.config.players
        if n == 2:
            return self.button if idx == 1 else (1 - self.button)
        return (self.button + 1 + idx) % n

    @property
    def hero_idx(self) -> int:
        return self.idx_of(0)

    # ---------- hands ----------
    def start_hand(self) -> None:
        c = self.config
        n = c.players
        self.button = (self.button + 1) % n
        buy_in = c.buy_in_bb * c.big_blind
        for s in self.seats:
            if s.stack < c.big_blind:  # busted: rebuy for a full buy-in
                s.stack = buy_in
                s.buy_ins += 1
        stacks = tuple(self.seats[self.seat_of(i)].stack for i in range(n))
        self.hand_no += 1
        self.hand = Hand(n, self.hero_idx, stacks, (c.small_blind, c.big_blind), self.rng, hand_no=self.hand_no)
        self.bot_ranges = {}
        self.last_feedback = None
        self.last_result = None
        self.hand_feedback = []
        self.run_bots()

    def run_bots(self) -> None:
        """Let the bots act until it is your turn or the hand is over."""
        hand = self.hand
        while not hand.finished and hand.actor is not None and hand.actor != hand.hero_idx:
            i = hand.actor
            match = self.charts.for_decision(hand, i)
            kind, amount = self.bots.decide(hand, i, self.rng)
            ev = hand.act(kind, amount)
            if match is not None and i not in self.bot_ranges:
                self.bot_ranges[i] = self.bots.preflop_range(hand, i, match, ev.kind)
        if hand.finished:
            self.finish_hand()

    def finish_hand(self) -> None:
        res = self.hand.result()
        for i, s in enumerate(res["stacks"]):
            seat = self.seats[self.seat_of(i)]
            seat.net += res["payoffs"][i]
            seat.stack = s
        self.last_result = res

    def hero_act(self, kind: str, amount: int | None = None) -> Feedback | None:
        hand = self.hand
        if hand is None or hand.finished or not hand.hero_turn:
            raise ValueError("it is not your turn")
        idx = hand.hero_idx
        legal = hand.legal()
        before = {"pot": hand.pot, "to_call": legal["to_call"], "street": hand.street,
                  "agg": hand.aggression(), "stack": hand.stacks_now()[idx]}
        match = self.charts.for_decision(hand, idx) if hand.street == "preflop" else None
        ev = hand.act(kind, amount)
        fb = self._feedback(before, match, ev) if self.config.feedback else None
        if fb is not None:
            self.last_feedback = fb
            self.hand_feedback.append(fb.to_dict())
            self._record(fb, before)
        self.run_bots()
        return fb

    def _feedback(self, before: dict, match, ev) -> Feedback | None:
        hand = self.hand
        idx = hand.hero_idx
        all_in = ev.kind == "allin"
        if match is not None:
            return chart_feedback(hand, idx, match, ev.kind, all_in)
        villain = before["agg"]["last_raiser"]
        vrange = self.bot_ranges.get(villain) if villain is not None else None
        seed = self.rng.getrandbits(32)
        if before["to_call"] > 0 and ev.kind in ("call", "fold"):
            return odds_feedback(hand, idx, ev.kind, before["pot"], before["to_call"], villain, vrange, seed)
        return facts_feedback(hand, idx, ev.kind, ev.amount, villain, vrange, seed)

    def _record(self, fb: Feedback, before: dict) -> None:
        if self.store is None or fb.attempt is None:
            return
        a = fb.attempt
        hand = self.hand
        chart = a["chart"]
        hc = a["hand_class"]
        self.store.record(Attempt(
            drill_type=a["drill_type"], game="nlhe", format="cash",
            spot={"players": self.config.players, "street": before["street"], "hero_pos": hand.positions[hand.hero_idx],
                  "pot": before["pot"], "to_call": before["to_call"], "board": list(hand.board),
                  "equity": a.get("equity"), "required": a.get("required")},
            hero_cards="".join(hand.hole[hand.hero_idx]), user_answer=a["user_answer"],
            correct_answer=list(a["correct"]), grade=a["grade"], table_size=self.config.players,
            stack_bb=self.config.buy_in_bb, spot_type=chart.spot_type if chart else before["street"],
            hero_pos=hand.positions[hand.hero_idx],
            villain_pos=chart.villain_pos if chart else None, hand_class=hc,
            frequencies=chart.frequencies(hc) if chart else None, chosen_frequency=a.get("chosen_frequency"),
            chart_id=chart.id if chart else None, chart_source=chart.source.get("name") if chart else None,
            is_sample=chart.is_sample if chart else False,
        ))

    # ---------- what the screen needs ----------
    def state(self) -> dict:
        c = self.config
        hand = self.hand
        n = c.players
        seats = []
        for s in self.seats:
            i = self.idx_of(s.seat) if hand else None
            entry = {"seat": s.seat, "name": s.name, "is_hero": s.is_hero, "stack": s.stack, "net": s.net,
                     "buy_ins": s.buy_ins, "is_button": s.seat == self.button}
            if hand:
                entry.update({"pos": hand.positions[i], "stack": hand.stacks_now()[i], "bet": hand.bets()[i],
                              "in_hand": hand.in_hand(i), "to_act": hand.actor == i and not hand.finished,
                              "cards": list(hand.hole.get(i, ())) if (s.is_hero or (hand.finished and i in hand.showdown)) else None,
                              "all_in": hand.in_hand(i) and hand.stacks_now()[i] == 0})
            seats.append(entry)
        out = {"id": self.id, "config": c.__dict__, "hand_no": self.hand_no, "seats": seats,
               "hand": None, "feedback": self.last_feedback.to_dict() if self.last_feedback else None,
               "hand_feedback": self.hand_feedback, "result": None, "bots_note": "Opponents are basic: charts preflop, strength and odds after. Not a model of good play."}
        if hand:
            hero_turn = hand.hero_turn and not hand.finished
            out["hand"] = {
                "street": hand.street, "board": list(hand.board), "pot": hand.pot, "finished": hand.finished,
                "hero_turn": hero_turn, "legal": hand.legal() if hero_turn else {},
                "events": [{"street": e.street, "pos": hand.positions[e.idx] if e.idx >= 0 else None,
                            "name": self.seats[self.seat_of(e.idx)].name if e.idx >= 0 else None,
                            "kind": e.kind, "amount": e.amount, "text": e.text} for e in hand.events],
                "attention": attention(hand, hand.hero_idx, self.charts) if (hero_turn and c.attention) else [],
            }
            if hand.finished and self.last_result:
                r = self.last_result
                def describe(cards):
                    if len(r["board"]) >= 3:
                        return current_hand("nlhe", tuple(cards), tuple(r["board"])).description
                    return hand_class_of("".join(cards))
                shown = [{"name": self.seats[self.seat_of(i)].name, "is_hero": i == hand.hero_idx, "cards": list(cs),
                          "hand": describe(cs), "won": r["payoffs"][i]} for i, cs in r["shown"].items()]
                shown.sort(key=lambda x: -x["won"])
                by_fold = not hand.showdown
                winners = [{"name": self.seats[self.seat_of(i)].name, "is_hero": i == hand.hero_idx, "amount": r["payoffs"][i],
                            "hand": None if by_fold else describe(hand.hole[i])} for i in r["winners"]]
                out["result"] = {"payoffs": r["payoffs"], "winners": winners, "by_fold": by_fold,
                                 "hero_net": r["payoffs"][hand.hero_idx], "board": r["board"], "shown": shown}
        return out
