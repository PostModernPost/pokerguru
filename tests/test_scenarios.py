import random

import pytest

from trainer.game.dealing import deal, parse_cards
from trainer.game.positions import valid_spots
from trainer.scenarios.preflop import ActionStep, build_preflop_spot, random_preflop_spot


def spot(**kw):
    kw.setdefault("hero_cards", "AsKd")
    kw.setdefault("villain_pos", None)
    return build_preflop_spot(**kw)


def summary(s):
    return [(a.pos, a.action, a.to_bb) for a in s.history]


def test_rfi_co_6max():
    s = spot(table_size=6, spot_type="rfi", hero_pos="CO")
    assert summary(s) == [("UTG", "fold", None), ("HJ", "fold", None)]
    assert s.pot_bb == 1.5 and s.to_call_bb == 1.0 and s.hero_invested_bb == 0
    assert s.hand_class == "AKo" and s.hero_cards == ("As", "Kd")


def test_rfi_utg_nobody_acted():
    s = spot(table_size=9, spot_type="rfi", hero_pos="UTG")
    assert s.history == ()


def test_rfi_sb():
    s = spot(table_size=6, spot_type="rfi", hero_pos="SB")
    assert [a.pos for a in s.history] == ["UTG", "HJ", "CO", "BTN"]
    assert s.pot_bb == 1.5 and s.to_call_bb == 0.5 and s.hero_invested_bb == 0.5


def test_rfi_with_antes():
    s = spot(table_size=6, spot_type="rfi", hero_pos="CO", ante_bb=0.1)
    assert s.pot_bb == pytest.approx(2.1)


def test_vs_open_btn_vs_co():
    s = spot(table_size=6, spot_type="vs_open", hero_pos="BTN", villain_pos="CO", open_size_bb=2.5)
    assert summary(s) == [("UTG", "fold", None), ("HJ", "fold", None), ("CO", "raise", 2.5)]
    assert s.pot_bb == 4.0 and s.to_call_bb == 2.5


def test_vs_open_bb_vs_sb():
    s = spot(table_size=6, spot_type="vs_open", hero_pos="BB", villain_pos="SB", open_size_bb=3)
    assert summary(s)[-1] == ("SB", "raise", 3)
    assert len(s.history) == 5
    assert s.pot_bb == 4.0 and s.to_call_bb == 2.0 and s.hero_invested_bb == 1.0


def test_vs_open_folds_between():
    s = spot(table_size=9, spot_type="vs_open", hero_pos="BTN", villain_pos="UTG1", open_size_bb=3)
    assert summary(s) == [
        ("UTG", "fold", None), ("UTG1", "raise", 3), ("UTG2", "fold", None),
        ("LJ", "fold", None), ("HJ", "fold", None), ("CO", "fold", None),
    ]
    assert s.pot_bb == 4.5


def test_vs_3bet_co_vs_btn():
    s = spot(table_size=6, spot_type="vs_3bet", hero_pos="CO", villain_pos="BTN",
             open_size_bb=2.5, threebet_size_bb=8)
    assert summary(s) == [
        ("UTG", "fold", None), ("HJ", "fold", None), ("CO", "raise", 2.5),
        ("BTN", "raise", 8), ("SB", "fold", None), ("BB", "fold", None),
    ]
    assert s.history[2].is_hero and not s.history[3].is_hero
    assert s.pot_bb == 12.0 and s.to_call_bb == 5.5 and s.hero_invested_bb == 2.5


def test_vs_3bet_sb_vs_bb():
    s = spot(table_size=6, spot_type="vs_3bet", hero_pos="SB", villain_pos="BB",
             open_size_bb=3, threebet_size_bb=9)
    assert s.pot_bb == 12.0 and s.to_call_bb == 6.0


def test_vs_3bet_utg_vs_bb_9handed():
    s = spot(table_size=9, spot_type="vs_3bet", hero_pos="UTG", villain_pos="BB",
             open_size_bb=2.5, threebet_size_bb=10)
    assert s.history[0] == ActionStep("UTG", "raise", 2.5, is_hero=True)
    assert [a.action for a in s.history[1:-1]] == ["fold"] * 7
    assert s.history[-1] == ActionStep("BB", "raise", 10)
    assert s.pot_bb == 13.0 and s.to_call_bb == 7.5


def test_unknown_size_gives_unknown_pot():
    s = spot(table_size=6, spot_type="vs_open", hero_pos="BTN", villain_pos="CO")
    assert s.pot_bb is None and s.to_call_bb is None
    assert s.history[-1] == ActionStep("CO", "raise", None)


@pytest.mark.parametrize(
    "kw",
    [
        dict(table_size=6, spot_type="rfi", hero_pos="BB"),
        dict(table_size=6, spot_type="rfi", hero_pos="UTG1"),
        dict(table_size=6, spot_type="vs_open", hero_pos="CO", villain_pos="BTN", open_size_bb=2.5),
        dict(table_size=6, spot_type="vs_3bet", hero_pos="BTN", villain_pos="CO",
             open_size_bb=2.5, threebet_size_bb=8),
        dict(table_size=6, spot_type="vs_open", hero_pos="BTN", villain_pos="CO", open_size_bb=0.5),
        dict(table_size=6, spot_type="vs_3bet", hero_pos="CO", villain_pos="BTN",
             open_size_bb=8, threebet_size_bb=8),
        dict(table_size=6, spot_type="vs_3bet", hero_pos="CO", villain_pos="BTN",
             open_size_bb=2.5, threebet_size_bb=150),
        dict(table_size=6, spot_type="rfi", hero_pos="CO", open_size_bb=2.5),
        dict(table_size=6, spot_type="rfi", hero_pos="CO", hero_cards="AsAs"),
        dict(table_size=6, spot_type="rfi", hero_pos="CO", hero_cards="AsKsQs"),
        dict(table_size=7, spot_type="rfi", hero_pos="CO"),
    ],
)
def test_invalid_spots(kw):
    with pytest.raises(ValueError):
        spot(**kw)


def test_valid_spot_counts():
    assert len(valid_spots(6, "rfi")) == 5
    assert len(valid_spots(6, "vs_open")) == 15
    assert len(valid_spots(6, "vs_3bet")) == 15
    assert len(valid_spots(9, "rfi")) == 8
    assert len(valid_spots(9, "vs_open")) == 36
    assert len(valid_spots(9, "vs_3bet")) == 36
    assert ("BB", "SB") in valid_spots(6, "vs_open")
    assert ("SB", "BB") in valid_spots(6, "vs_3bet")


def test_random_spot_respects_constraints_and_seed():
    rng = random.Random(7)
    for _ in range(300):
        s = random_preflop_spot(rng, table_sizes=[9], spot_types=["vs_open", "vs_3bet"],
                                hero_positions=["BTN", "SB"], open_size_bb=2.5, threebet_size_bb=9)
        assert s.table_size == 9 and s.spot_type in ("vs_open", "vs_3bet")
        assert s.hero_pos in ("BTN", "SB")
        assert len(set(s.hero_cards)) == 2
        assert s.pot_bb is not None
    a = random_preflop_spot(random.Random(1))
    b = random_preflop_spot(random.Random(1))
    assert a == b


def test_random_spot_impossible_constraints():
    with pytest.raises(ValueError):
        random_preflop_spot(random.Random(0), spot_types=["rfi"], hero_positions=["BB"])


def test_deal_distinct_and_excludes():
    rng = random.Random(3)
    cards = deal(rng, 52)
    assert len(set(cards)) == 52
    assert "As" not in deal(rng, 50, exclude=("As", "Kd"))
    assert len(deal(rng, 50, exclude=("As", "Kd"))) == 50


def test_deal_covers_all_hand_classes():
    from trainer.game.hand_classes import ALL_HAND_CLASSES, hand_class_of

    rng = random.Random(0)
    seen = {hand_class_of("".join(deal(rng, 2))) for _ in range(20000)}
    assert seen == set(ALL_HAND_CLASSES)


def test_parse_cards():
    assert parse_cards("AsKd") == ("As", "Kd")
    for bad in ["AsAs", "Xx", "??", "AsK"]:
        with pytest.raises(ValueError):
            parse_cards(bad)


def test_push_and_vs_push_spots():
    s = spot(table_size=2, spot_type="push", hero_pos="SB", stack_bb=10)
    assert s.history == () and s.pot_bb == 1.5 and s.to_call_bb == 0.5
    s = spot(table_size=2, spot_type="vs_push", hero_pos="BB", villain_pos="SB", stack_bb=10)
    assert summary(s) == [("SB", "raise", 10)]  # the open is the whole stack
    assert s.pot_bb == 11 and s.to_call_bb == 9 and s.open_size_bb == 10
    with pytest.raises(ValueError):
        spot(table_size=2, spot_type="push", hero_pos="BB", stack_bb=10)
    assert valid_spots(2, "push") == [("SB", None)]
    assert valid_spots(2, "vs_push") == [("BB", "SB")]
