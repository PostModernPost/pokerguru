import random

import pytest

from trainer.game.outs import current_hand, improving_outs, possible_hands
from trainer.graders.basics import build_question, grade_basics
from trainer.scenarios.basics import build_basics_spot, random_basics_spot


# ---------- game layer ----------

def test_current_hand_nlhe_and_plo():
    assert current_hand("nlhe", "AsKs", "QsJsTs2c3d").description == "Royal flush"
    assert current_hand("nlhe", "2c3d", "AhAdAcKhKd").description == "Full house, aces full of kings"  # board plays
    assert current_hand("plo", "AhKhQhJh", "Th2c3d").description == "Ace-high, no pair"  # two-card rule
    assert current_hand("plo", "AsKs9d8d", "QsJsTs2h").description == "Royal flush"


def test_flush_draw_outs_nlhe():
    info = improving_outs("nlhe", "AhKh", "Qh7h2c")
    assert len(info.outs) == 9 and all(c.endswith("h") for c in info.outs)
    assert info.cards_to_come == 2 and info.rule_estimate == 0.36
    assert info.hit_chance_by_river == pytest.approx(0.3497, abs=0.001)  # 1 - C(38,2)/C(47,2)
    assert info.hit_chance_next_card == pytest.approx(9 / 47, abs=0.001)
    assert info.best_outcome == "Flush, ace-high"


def test_open_ender_and_gutshot_outs():
    assert len(improving_outs("nlhe", "9h8h", "7c6d2s").outs) == 8  # any 5 or T
    turn = improving_outs("nlhe", "9h8h", "7c6d2s2d")
    assert len(turn.outs) == 8 and turn.cards_to_come == 1 and turn.rule_estimate == 0.16
    assert turn.hit_chance_by_river == pytest.approx(8 / 46, abs=0.001)
    assert len(improving_outs("nlhe", "9h8h", "7cJd2s").outs) == 4  # gutshot: any T


def test_combo_draw_counts_each_card_once():
    info = improving_outs("nlhe", "9h8h", "7h6h2c")  # flush draw + open-ender
    assert len(info.outs) == 15  # 9 hearts + 3 non-heart fives + 3 non-heart tens
    assert info.rule_estimate == 0.60 and info.hit_chance_by_river == pytest.approx(0.5412, abs=0.001)  # 1 - C(32,2)/C(47,2)


def test_outs_exclude_mere_pairs_and_river():
    assert improving_outs("nlhe", "AhKd", "Qc7s2d").outs == ()  # overcards only: no straight/flush outs
    with pytest.raises(ValueError):
        improving_outs("nlhe", "AhKd", "Qc7s2d3c4h")


def test_possible_hands_nlhe():
    hands = possible_hands("nlhe", "AhKd", "Qc7s2d")
    descs = [h.description for h in hands]
    assert descs[0] == "Three of a kind, queens"
    assert "Ace-high, no pair" in descs and len(descs) == len(set(descs))


# ---------- scenarios ----------

def test_random_spots_are_valid_and_outs_have_draws():
    rng = random.Random(1)
    seen = set()
    for _ in range(150):
        s = random_basics_spot(rng)
        seen.add(s.question)
        if s.question == "outs":
            assert s.game == "nlhe" and s.street in ("flop", "turn")
            assert 3 <= len(improving_outs("nlhe", s.hero_cards, s.board).outs) <= 15
        if s.question == "price":
            assert s.pot_bb > 0 and s.bet_bb > 0
            if s.game == "plo":
                assert s.bet_bb <= s.pot_bb
    assert seen == {"hand", "outs", "price"}
    assert random_basics_spot(random.Random(4)) == random_basics_spot(random.Random(4))


@pytest.mark.parametrize("kw", [
    dict(question="outs", game="plo", street="flop", hero_cards="AsKsQdJd", board="2c3c4c"),
    dict(question="outs", game="nlhe", street="river", hero_cards="AsKs", board="2c3c4c5c6c"),
    dict(question="price", game="nlhe", street="flop", hero_cards="AsKs", board="2c3c4c"),
    dict(question="hand", game="nlhe", street="flop", hero_cards="AsKs", board="As3c4c"),
    dict(question="guess", game="nlhe", street="flop", hero_cards="AsKs", board="2c3c4c"),
])
def test_invalid_spots(kw):
    with pytest.raises(ValueError):
        build_basics_spot(**kw)


# ---------- questions and grading ----------

def test_hand_question():
    s = build_basics_spot(question="hand", game="nlhe", street="turn", hero_cards="AsKd", board="QhJcTd2s")
    q = build_question(s, seed=1)
    assert q.answer == "Straight, ace-high (Broadway)" and q.answer in q.options and len(q.options) == 4
    assert len(set(q.options)) == 4
    assert build_question(s, seed=1).options == q.options  # seeded order
    assert grade_basics(q, q.answer).grade == "correct"
    wrong = next(o for o in q.options if o != q.answer)
    assert grade_basics(q, wrong).grade == "wrong"
    with pytest.raises(ValueError):
        grade_basics(q, "Royal flush, maybe")


def test_outs_question():
    s = build_basics_spot(question="outs", game="nlhe", street="flop", hero_cards="AhKh", board="Qh7h2c")
    q = build_question(s, seed=2)
    assert q.answer == "9" and "9" in q.options and len(q.options) == 4
    assert "Rule of 4: about 36%" in q.explanation and "35%" in q.explanation
    assert grade_basics(q, "9").grade == "correct"


def test_price_question():
    s = build_basics_spot(question="price", game="nlhe", street="flop", hero_cards="AhKh", board="Qh7h2c",
                          pot_bb=100, bet_bb=50)
    q = build_question(s, seed=3)
    assert q.answer == "25%" and q.answer in q.options and len(q.options) == 4
    assert "50 ÷ 200 = 25.0%" in q.explanation
    s2 = build_basics_spot(question="price", game="plo", street="turn", hero_cards="AhKhQsJs", board="Qh7h2c3d",
                           pot_bb=10, bet_bb=10)
    assert build_question(s2, seed=3).answer == "33%"
