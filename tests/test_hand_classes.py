import pytest
from pokerkit import Card

from trainer.game.hand_classes import (
    ALL_HAND_CLASSES,
    combo_count,
    grid,
    hand_class_of,
    is_hand_class,
)


def test_169_unique_classes():
    assert len(ALL_HAND_CLASSES) == 169
    assert len(set(ALL_HAND_CLASSES)) == 169


def test_class_counts():
    pairs = [h for h in ALL_HAND_CLASSES if len(h) == 2]
    suited = [h for h in ALL_HAND_CLASSES if h.endswith("s")]
    offsuit = [h for h in ALL_HAND_CLASSES if h.endswith("o")]
    assert (len(pairs), len(suited), len(offsuit)) == (13, 78, 78)


def test_combos_total_1326():
    assert sum(combo_count(h) for h in ALL_HAND_CLASSES) == 1326


def test_grid_layout():
    g = grid()
    assert g[0][0] == "AA"
    assert g[0][1] == "AKs"  # suited above the diagonal
    assert g[1][0] == "AKo"  # offsuit below
    assert g[12][12] == "22"
    assert g[11][12] == "32s"
    assert g[12][11] == "32o"


@pytest.mark.parametrize(
    "cards,expected",
    [
        ("AsKs", "AKs"),
        ("KsAs", "AKs"),
        ("AsKd", "AKo"),
        ("2c7d", "72o"),
        ("ThTd", "TT"),
        ("9h8h", "98s"),
        ("3c2c", "32s"),
    ],
)
def test_hand_class_of(cards, expected):
    assert hand_class_of(cards) == expected
    assert hand_class_of(Card.parse(cards)) == expected


def test_hand_class_of_rejects_bad_input():
    with pytest.raises(ValueError):
        hand_class_of("AsKsQs")
    with pytest.raises(ValueError):
        hand_class_of("AsAs")


def test_is_hand_class():
    assert is_hand_class("AKs")
    assert not is_hand_class("KAs")
    assert not is_hand_class("AA s")
    assert not is_hand_class("AAs")


@pytest.mark.parametrize("hand,cat", [
    ("AA", "pair"), ("22", "pair"), ("A5s", "suited ace"), ("A5o", "offsuit ace"), ("AKs", "suited ace"),
    ("KQs", "suited broadway"), ("KTo", "offsuit broadway"), ("JTs", "suited broadway"),
    ("98s", "suited connector"), ("97s", "suited other"), ("96s", "suited other"), ("T8s", "suited other"),
    ("98o", "offsuit other"), ("72o", "offsuit other"),
])
def test_hand_category(hand, cat):
    from trainer.game.hand_classes import hand_category
    assert hand_category(hand) == cat


def test_categories_cover_all_169():
    from trainer.game.hand_classes import HAND_CATEGORIES, hands_in_category
    assert sum(len(hands_in_category(c)) for c in HAND_CATEGORIES) == 169


def test_deal_hand_class():
    import random
    from trainer.game.dealing import deal_hand_class
    rng = random.Random(1)
    for hc in ("AA", "AKs", "AKo", "72o", "32s"):
        for _ in range(20):
            cards = deal_hand_class(rng, hc)
            assert hand_class_of("".join(cards)) == hc
