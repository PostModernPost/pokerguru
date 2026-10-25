import pytest

from trainer.charts.range_parser import RangeParseError, build_hands, parse_range
from trainer.game.hand_classes import ALL_HAND_CLASSES


def hands(text):
    return set(parse_range(text))


# ---- single hands -----------------------------------------------------------

def test_brief_example():
    r = parse_range("AA,KK,QQ,AKs,AQs:0.5,A5s:0.6")
    assert r == {"AA": 1.0, "KK": 1.0, "QQ": 1.0, "AKs": 1.0, "AQs": 0.5, "A5s": 0.6}


def test_unsuffixed_means_both():
    assert parse_range("AK") == {"AKs": 1.0, "AKo": 1.0}


def test_low_card_first_is_reordered():
    assert parse_range("KAs") == {"AKs": 1.0}
    assert parse_range("27o") == {"72o": 1.0}


def test_case_and_whitespace_insensitive():
    assert parse_range(" aks , kQo ,tt,\n 9 8 s ") == {"AKs": 1.0, "KQo": 1.0, "TT": 1.0, "98s": 1.0}


def test_empty_tokens_ignored():
    assert parse_range("AA,,KK,") == {"AA": 1.0, "KK": 1.0}
    assert parse_range("") == {}


# ---- plus shorthand -------------------------------------------------------

def test_pairs_plus():
    assert hands("22+") == {r + r for r in "AKQJT98765432"}
    assert hands("TT+") == {"TT", "JJ", "QQ", "KK", "AA"}
    assert hands("AA+") == {"AA"}


def test_suited_plus():
    assert hands("A2s+") == {f"A{k}s" for k in "KQJT98765432"}
    assert len(hands("A2s+")) == 12


def test_offsuit_plus_brief_example():
    assert hands("KTo+") == {"KTo", "KJo", "KQo"}


def test_plus_without_suffix():
    assert hands("QT+") == {"QTs", "QTo", "QJs", "QJo"}


def test_plus_at_top_kicker():
    assert hands("AKs+") == {"AKs"}
    assert hands("32o+") == {"32o"}


def test_plus_does_not_include_pair():
    assert "KK" not in hands("K2s+")
    assert "AA" not in hands("A2o+")


# ---- spans ----------------------------------------------------------------

def test_pair_span():
    assert hands("22-55") == {"22", "33", "44", "55"}
    assert hands("55-22") == {"22", "33", "44", "55"}
    assert hands("77-77") == {"77"}


def test_kicker_span():
    assert hands("A2s-A5s") == {"A2s", "A3s", "A4s", "A5s"}
    assert hands("K9o-KJo") == {"K9o", "KTo", "KJo"}
    assert hands("Q8-QT") == {"Q8s", "Q8o", "Q9s", "Q9o", "QTs", "QTo"}


@pytest.mark.parametrize("bad", ["A2s-K5s", "A2s-A5o", "22-A5s", "22-", "22-33-44", "-22"])
def test_bad_spans(bad):
    with pytest.raises(RangeParseError):
        parse_range(bad)


# ---- frequencies ----------------------------------------------------------

def test_weights_on_shorthand():
    r = parse_range("A2s+:0.5")
    assert len(r) == 12 and set(r.values()) == {0.5}
    assert parse_range("22-44:0.25") == {"22": 0.25, "33": 0.25, "44": 0.25}


def test_percent_weight():
    assert parse_range("AQs:50%") == {"AQs": 0.5}


def test_weight_bounds():
    assert parse_range("AA:1") == {"AA": 1.0}
    assert parse_range("AA:0") == {"AA": 0.0}
    for bad in ["AA:1.5", "AA:50", "AA:-0.1", "AA:nan", "AA:inf", "AA:x", "AA:", "AA:0.5:0.5"]:
        with pytest.raises(RangeParseError):
            parse_range(bad)


# ---- rejects ----------------------------------------------------------------

@pytest.mark.parametrize(
    "bad",
    ["AAs", "AAo", "A1s", "AKx", "AsKs", "XYZ", "A", "AKss", "1010", "AK+s", "++", ":0.5"],
)
def test_rejects_garbage(bad):
    with pytest.raises(RangeParseError):
        parse_range(bad)


def test_rejects_overlap():
    with pytest.raises(RangeParseError, match="already"):
        parse_range("A2s+,A5s:0.6")
    with pytest.raises(RangeParseError):
        parse_range("AK,AKs")
    with pytest.raises(RangeParseError):
        parse_range("AA,AA")


def test_error_names_the_token():
    with pytest.raises(RangeParseError, match="'AKx'"):
        parse_range("AA,AKx,KK")


# ---- build_hands ------------------------------------------------------------

def test_build_hands_fills_fold():
    h = build_hands({"raise_2.5": "AA,AQs:0.5,A5s:0.6"})
    assert set(h) == set(ALL_HAND_CLASSES)
    assert h["AA"] == {"raise_2.5": 1.0}
    assert h["AQs"] == {"raise_2.5": 0.5, "fold": 0.5}
    assert h["A5s"] == {"raise_2.5": 0.6, "fold": 0.4}
    assert h["72o"] == {"fold": 1.0}
    for freqs in h.values():
        assert sum(freqs.values()) == pytest.approx(1.0)


def test_build_hands_multiple_actions():
    h = build_hands({"raise_9": "AA,KK,A5s:0.4", "call": "QQ,JJ:0.5,A5s:0.3"})
    assert h["AA"] == {"raise_9": 1.0}
    assert h["QQ"] == {"call": 1.0}
    assert h["JJ"] == {"call": 0.5, "fold": 0.5}
    assert h["A5s"] == {"raise_9": 0.4, "call": 0.3, "fold": 0.3}


def test_build_hands_over_one_fails():
    with pytest.raises(RangeParseError, match="AA"):
        build_hands({"raise_9": "AA:0.7", "call": "AA:0.5"})


def test_build_hands_explicit_fold_must_cover_everything():
    with pytest.raises(RangeParseError):
        build_hands({"raise_2.5": "AA", "fold": "KK"})


def test_build_hands_error_names_action():
    with pytest.raises(RangeParseError, match="call"):
        build_hands({"raise_2.5": "AA", "call": "KKx"})


def test_build_hands_zero_weight_dropped():
    h = build_hands({"raise_2.5": "AA:0"})
    assert h["AA"] == {"fold": 1.0}
