import pytest

from trainer.game.omaha import draw_info, nut_info
from trainer.graders.plo import grade_nut_answers, grade_pot_limit, quiz_options


def test_quiz_options_contain_nuts_and_hero_hand():
    hero, board = "AhAd7c6c", "Kd9s4h"
    info = nut_info(hero, board)
    opts = quiz_options(info, hero, board, seed=1)
    assert len(opts) == 4 and len(set(opts)) == 4
    assert "Three of a kind, kings" in opts
    assert "One pair, aces" in opts  # hero's own (wrong) hand is a tempting choice
    assert quiz_options(info, hero, board, seed=1) == opts  # seeded order
    assert quiz_options(info, hero, board, seed=2) != opts or True  # may coincide; just must not crash


def test_grade_nut_answers_flop():
    hero, board = "AcKc2d3d", "Jc9c4s"
    info, draw = nut_info(hero, board), draw_info(hero, board)
    g = grade_nut_answers(info, draw, nut_choice="Three of a kind, jacks", has_nuts_choice=False, draw_choice="nut_draw")
    assert (g.nut_grade, g.has_nuts_grade, g.draw_grade) == ("correct", "correct", "correct")
    assert "2c 3c 5c 6c" in g.explanation
    g = grade_nut_answers(info, draw, nut_choice="Three of a kind, nines", has_nuts_choice=True, draw_choice="none")
    assert (g.nut_grade, g.has_nuts_grade, g.draw_grade) == ("wrong", "wrong", "wrong")
    with pytest.raises(ValueError):
        grade_nut_answers(info, draw, nut_choice="x", has_nuts_choice=False, draw_choice=None)


def test_grade_nut_answers_when_hero_has_nuts_skips_draw():
    hero, board = "AsKs9d8d", "QsJsTs2h"
    g = grade_nut_answers(nut_info(hero, board), draw_info(hero, board),
                          nut_choice="Royal flush", has_nuts_choice=True, draw_choice=None)
    assert g.draw_answer is None and g.draw_grade is None
    assert g.explanation.startswith("The nuts is royal flush (")
    assert "You have it" in g.explanation


def test_grade_nut_answers_river_has_no_draw():
    hero, board = "2c3d7h9s", "AsAhKdKc5s"
    g = grade_nut_answers(nut_info(hero, board), None, nut_choice="Four of a kind, aces",
                          has_nuts_choice=False, draw_choice=None)
    assert g.nut_grade == "correct" and g.has_nuts_grade == "correct" and g.draw_grade is None


def test_blocker_explanation():
    hero, board = "As3d9d8d", "KsQs7s2d"
    g = grade_nut_answers(nut_info(hero, board), draw_info(hero, board),
                          nut_choice="Flush, king-high", has_nuts_choice=False, draw_choice="none")
    assert "your cards block it" in g.explanation


def test_grade_pot_limit():
    g = grade_pot_limit(pot=3, largest_bet=2, hero_in=0, to_call=2, max_raise_to=7, answer=7)
    assert g.grade == "correct"
    assert g.explanation == ("Pot including all bets: 3. To call: 2 - 0 = 2. After your call the pot is 5, "
                             "and you may raise by that much on top: 2 + 5 = raise to 7.")
    assert grade_pot_limit(pot=3, largest_bet=2, hero_in=0, to_call=2, max_raise_to=7, answer=6).grade == "wrong"
    g = grade_pot_limit(pot=60, largest_bet=0, hero_in=0, to_call=0, max_raise_to=60, answer=60)
    assert g.grade == "correct" and "Nobody has bet" in g.explanation
