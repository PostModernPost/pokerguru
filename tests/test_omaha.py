import pytest
from pokerkit import Card, StandardLookup

from trainer.game.omaha import describe, draw_info, hero_hand, nut_info, possible_hands

LK = StandardLookup()


def d(cards):
    c = list(Card.parse(cards))
    return describe(LK.get_entry(c), c)


@pytest.mark.parametrize("cards,text", [
    ("AsKsQsJsTs", "Royal flush"),
    ("9s8s7s6s5s", "Straight flush, nine-high"),
    ("As2s3s4s5s", "Straight flush, five-high"),
    ("7c7d7h7s2d", "Four of a kind, sevens"),
    ("KcKdKh7s7d", "Full house, kings full of sevens"),
    ("7c7d7h KsKd".replace(" ", ""), "Full house, sevens full of kings"),
    ("Ah9h7h4h2h", "Flush, ace-high"),
    ("AhKdQcJsTd", "Straight, ace-high (Broadway)"),
    ("Ah2d3c4s5d", "Straight, five-high (the wheel)"),
    ("9h8d7c6s5d", "Straight, nine-high"),
    ("6c6d6h2s9d", "Three of a kind, sixes"),
    ("AcAdKhKs2d", "Two pair, aces and kings"),
    ("2c2dKhQs9d", "One pair, deuces"),
    ("KcJd9h5s2d", "King-high, no pair"),
])
def test_describe(cards, text):
    assert d(cards) == text


def test_hero_hand_uses_exactly_two_hole_cards():
    # Four hearts in hand, one on board: no flush in Omaha.
    h = hero_hand("AhKhQhJh", "Th2c3d")
    assert h.description == "Ace-high, no pair"
    # Board has five hearts; hero must still use two hole cards: no flush.
    h = hero_hand("2c3c4c5c", "AhKhQhJh9h")
    assert h.label != "Flush"


def test_nuts_royal_flush():
    n = nut_info("AsKs9d8d", "QsJsTs2h")
    assert n.nuts.description == "Royal flush" and n.hero_has_nuts and n.blocked_hand is None


def test_nuts_second_nut_flush_is_not_nuts():
    n = nut_info("Js3s9d8d", "KsQs7s2d")
    assert n.hero.description == "Flush, king-high"
    assert n.nuts.description == "Flush, ace-high"
    assert not n.hero_has_nuts


def test_ace_blocker_makes_king_high_flush_the_nuts():
    # Hero holds the As without a second spade: nobody can make the ace-high flush.
    n = nut_info("As3d9d8d", "KsQs7s2d")
    assert n.nuts.description == "Flush, king-high"
    assert not n.hero_has_nuts
    assert n.blocked_hand is not None and n.blocked_hand.description == "Flush, ace-high"


def test_hero_ace_high_flush_is_nuts_even_with_small_kicker():
    n = nut_info("As3s9d8d", "KsQs7s2d")
    assert n.hero_has_nuts and n.nuts.description == "Flush, ace-high"
    assert n.blocked_hand is None  # the note would just repeat the nuts


def test_nuts_dry_board_is_top_set():
    n = nut_info("AhAd7c6c", "Kd9s4h")
    assert n.nuts.description == "Three of a kind, kings"
    assert n.hero.description == "One pair, aces" and not n.hero_has_nuts


def test_nuts_paired_board_is_quads():
    n = nut_info("2c3d7h9s", "AsAhKdKc5s")
    assert n.nuts.description == "Four of a kind, aces"


def test_board_straight_does_not_play_without_two_hole_cards():
    n = nut_info("2c3d7h9s", "AsKhQdJc5s")
    assert n.nuts.description == "Straight, ace-high (Broadway)"
    assert n.hero.description == "Ace-high, no pair"  # a Hold'em player would think they have it
    assert not n.hero_has_nuts


def test_tie_with_the_nuts_counts_as_having_them():
    n = nut_info("TdKc2c3d", "AsKhQdJc5s")
    assert n.hero.description == "Straight, ace-high (Broadway)"
    assert n.hero_has_nuts


def test_hero_with_nuts_has_no_draw_question():
    assert draw_info("AsKs9d8d", "QsJsTs2h").category == "has_nuts"


def test_nut_flush_draw_with_straight_flush_danger():
    dr = draw_info("AcKc2d3d", "Jc9c4s")
    assert dr.category == "nut_draw"
    # Low clubs make the nut flush; Qc/Tc/8c/7c let an opponent hold a straight flush.
    assert set(dr.nut_outs) == {"2c", "3c", "5c", "6c"}
    assert len(dr.improving_outs) == 9
    assert dr.cards_to_come == 2


def test_king_high_flush_draw_is_nut_only_when_the_ace_falls():
    dr = draw_info("Kc9c2d3d", "Jc8c4s")
    assert dr.category == "nut_draw"
    assert dr.nut_outs == ("Ac",)  # with the Ac on board nobody can out-flush the king
    assert len(dr.improving_outs) == 9


def test_non_nut_flush_draw():
    # Queen-high flush draw; both the Ac and Kc are out there, and no club makes it the nuts.
    dr = draw_info("Qc7c2d3h", "Jc8c4s")
    assert dr.category == "non_nut_draw"
    assert dr.nut_outs == () and len(dr.improving_outs) == 9


def test_no_draw_backdoor_only_on_flop():
    dr = draw_info("JhTh9c8c", "Qd7s2h")
    assert dr.category == "none" and dr.improving_outs == ()


def test_turn_draw_one_card_to_come():
    dr = draw_info("AhKd9c8c", "QsJs2d7h")  # Broadway draw needs a ten
    assert dr.cards_to_come == 1
    assert dr.category == "nut_draw"
    assert set(dr.nut_outs) <= {"Tc", "Td", "Th"} and len(dr.nut_outs) >= 2
    # Ts gives A K Q J T but also puts three spades out: not the nuts (flush possible).
    assert "Ts" not in dr.nut_outs and "Ts" in dr.improving_outs


def test_draw_on_river_rejected():
    with pytest.raises(ValueError):
        draw_info("AsKs9d8d", "QsJsTs2h3c")


@pytest.mark.parametrize("hero,board", [
    ("AsKs", "QsJsTs"), ("AsKs9d8d", "QsJs"), ("AsKs9d8d", "AsJsTs"), ("AsKs9d8dXx", "QsJsTs"),
])
def test_bad_input(hero, board):
    with pytest.raises(ValueError):
        nut_info(hero, board)


def test_possible_hands_sorted_and_distinct():
    hands = possible_hands("AhAd7c6c", "Kd9s4h")
    descs = [h.description for h in hands]
    assert descs[0] == "Three of a kind, kings"
    assert len(descs) == len(set(descs))
    assert all(a.entry >= b.entry for a, b in zip(hands, hands[1:]))
    assert "One pair, aces" in descs  # hero's own hand is included
