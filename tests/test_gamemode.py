"""Game mode: the hand engine on PokerKit, the bots, feedback, and the API."""
import random
import warnings

import numpy as np
import pytest
from fastapi.testclient import TestClient

from trainer.api.app import create_app
from trainer.charts.loader import ChartLibrary
from trainer.config import CHARTS_DIR
from trainer.game.fast_equity import equity_vs_range
from trainer.gamemode.bots import BotPolicy
from trainer.gamemode.charts import ChartIndex
from trainer.gamemode.engine import Hand, chart_positions, pk_positions
from trainer.gamemode.feedback import required_equity
from trainer.gamemode.session import GameConfig, Session
from trainer.progress.store import AttemptStore

LIB = ChartLibrary.from_directory(CHARTS_DIR)
INDEX = ChartIndex(LIB)


def test_positions_by_pokerkit_index():
    assert pk_positions(2) == ["BB", "SB"]
    assert pk_positions(6) == ["SB", "BB", "UTG", "HJ", "CO", "BTN"]
    assert pk_positions(9) == ["SB", "BB", "UTG", "UTG1", "UTG2", "LJ", "HJ", "CO", "BTN"]
    assert pk_positions(4) == ["SB", "BB", "CO", "BTN"]
    assert chart_positions(6) == ["SB", "BB", "LJ", "HJ", "CO", "BTN"]
    assert chart_positions(3) == ["SB", "BB", "BTN"]


def play_out(n, hands, seed, hero_policy):
    """Run hands with bots and a scripted hero; returns the list of results."""
    bot = BotPolicy(INDEX, "loose" if seed % 2 else "standard")
    rng = random.Random(seed)
    stacks = [200] * n
    results = []
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # PokerKit warns on illegal-ish play (double-dealt cards, pointless folds)
        for h in range(hands):
            hand = Hand(n, h % n, tuple(stacks), (1, 2), rng)
            steps = 0
            while not hand.finished:
                steps += 1
                assert steps < 400, "hand did not finish"
                i = hand.actor
                assert i is not None
                if i == h % n:
                    hero_policy(hand, rng)
                else:
                    kind, amt = bot.decide(hand, i, rng)
                    hand.act(kind, amt)
            res = hand.result()
            assert sum(res["payoffs"]) == 0  # chips are conserved (no rake)
            assert sum(res["stacks"]) == sum(stacks)
            dealt = hand.board + [c for cs in hand.hole.values() for c in cs]
            assert len(set(dealt)) == len(dealt)  # no card dealt twice
            results.append(res)
            stacks = [200 if s < 40 else s for s in res["stacks"]]
    return results


def random_hero(hand, rng):
    legal = hand.legal()
    r = rng.random()
    if r < 0.2 and legal["can_fold"]:
        hand.act("fold")
    elif r < 0.75 or "min_raise_to" not in legal:
        hand.act("call" if legal["to_call"] else "check")
    else:
        hand.act("raise", rng.choice([legal["min_raise_to"], legal["pot_raise_to"], legal["max_raise_to"]]))


@pytest.mark.parametrize("n", [2, 3, 6, 9])
def test_hands_complete_for_every_table_size(n):
    results = play_out(n, 30, n, random_hero)
    assert any(r["winners"] for r in results)
    assert any(r["shown"] for r in results)  # some hands reach showdown and table their cards


def test_legal_actions_and_clamping():
    hand = Hand(6, 2, (200,) * 6, (1, 2), random.Random(1))
    legal = hand.legal()
    assert hand.actor == 2 and legal["to_call"] == 2 and legal["can_fold"] and not legal["can_check"]
    assert legal["min_raise_to"] == 4 and legal["max_raise_to"] == 200
    ev = hand.act("raise", 1)  # below the minimum: clamped up
    assert ev.kind == "raise" and ev.amount == 4
    hand.act("fold"); hand.act("fold"); hand.act("fold"); hand.act("fold")  # 3, 4, 5, SB
    assert hand.actor == 1 and hand.legal()["to_call"] == 2
    ev = hand.act("fold")
    assert ev.kind == "fold" and hand.finished and hand.result()["payoffs"][2] == 3
    assert hand.showdown == []


def test_bots_follow_the_chart_preflop():
    # UTG at a 9-handed table opens AA every time and folds 72o every time in the chart
    seen = {"AA": set(), "72o": set()}
    for seed in range(12):
        hand = Hand(9, 8, (200,) * 9, (1, 2), random.Random(seed))
        cards = {"AA": ("As", "Ad"), "72o": ("7s", "2d")}
        for hc, cs in cards.items():
            hand.hole[2] = cs
            kind, amt = BotPolicy(INDEX).decide(hand, 2, random.Random(seed))
            seen[hc].add(kind)
    assert seen["AA"] == {"raise"} and seen["72o"] == {"fold"}


def test_fast_equity_sanity():
    rng = np.random.default_rng(1)
    aa = equity_vs_range(("As", "Ad"), (), None, 2000, rng)
    assert 0.80 < aa < 0.90
    weak = equity_vs_range(("7s", "2d"), ("Ah", "Kd", "Qc"), None, 2000, rng)
    assert weak < 0.25
    # against a range of only AA, the AK on an A-high flop is far worse than vs random
    tight = equity_vs_range(("Ah", "Kh"), ("Ad", "7c", "2s"), {"AA": 1.0}, 2000, rng)
    loose = equity_vs_range(("Ah", "Kh"), ("Ad", "7c", "2s"), None, 2000, rng)
    assert tight < 0.5 < loose
    assert required_equity(14, 7) == pytest.approx(1 / 3)


def test_session_feedback_and_recording(tmp_path):
    store = AttemptStore(tmp_path / "g.sqlite")
    s = Session(GameConfig(players=9, seed=3), LIB, store)
    s.start_hand()
    kinds = set()
    rng = random.Random(2)
    for _ in range(20):
        while not s.hand.finished:
            st = s.state()
            assert st["hand"]["hero_turn"] and st["hand"]["attention"]
            legal = st["hand"]["legal"]
            r = rng.random()
            if r < 0.25 and legal["can_fold"]:
                fb = s.hero_act("fold")
            elif r < 0.7 or "min_raise_to" not in legal:
                fb = s.hero_act("call" if legal["to_call"] else "check")
            else:
                fb = s.hero_act("raise", legal["pot_raise_to"])
            if fb:
                kinds.add(fb.kind)
                assert fb.kind in ("chart", "odds", "facts")
                if fb.kind == "chart":
                    assert fb.grade in ("correct", "acceptable", "wrong") and fb.chart["frequencies"]
        assert s.state()["result"] is not None
        s.start_hand()
    assert {"chart", "facts"} <= kinds
    assert store.summary("game_preflop")["total"] > 0
    assert sum(seat.net for seat in s.seats) == 0


def test_hero_turn_only():
    s = Session(GameConfig(players=3, seed=1), LIB, None)
    s.start_hand()
    while not s.hand.hero_turn:  # the bots may fold the hand to you before you act
        s.start_hand()
    legal = s.hand.legal()
    s.hero_act("call" if legal["to_call"] else "check")
    if not s.hand.finished and not s.hand.hero_turn:
        with pytest.raises(ValueError):
            s.hero_act("check")


def test_game_api(tmp_path):
    client = TestClient(create_app(charts_dir=CHARTS_DIR, db_path=tmp_path / "p.sqlite", seed=4))
    o = client.get("/api/game/options").json()
    assert {b["id"] for b in o["bots"]} == {"standard", "loose"}
    st = client.post("/api/game/new", json={"players": 6, "bots": "loose"}).json()
    sid = st["id"]
    assert len(st["seats"]) == 6 and st["hand"]["hero_turn"]
    hero = next(x for x in st["seats"] if x["is_hero"])
    assert len(hero["cards"]) == 2 and all(x["cards"] is None for x in st["seats"] if not x["is_hero"])
    for _ in range(30):
        if st["hand"]["finished"]:
            st = client.post("/api/game/next", json={"session": sid}).json()
            continue
        legal = st["hand"]["legal"]
        st = client.post("/api/game/act", json={"session": sid, "action": "call" if legal["to_call"] else "check"}).json()
    assert client.post("/api/game/act", json={"session": "nope", "action": "fold"}).status_code == 404
    assert client.post("/api/game/new", json={"players": 12}).status_code == 422
    assert client.get("/game.html").status_code == 200
