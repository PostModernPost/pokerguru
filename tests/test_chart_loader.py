import copy
import json
import logging

import pytest

from trainer.charts.loader import ChartError, ChartLibrary, chart_from_dict, load_chart
from trainer.config import SAMPLE_SOURCE_NAME

BASE = {
    "id": "nlhe-cash-6max-100bb-rfi-CO",
    "game": "nlhe",
    "format": "cash",
    "table_size": 6,
    "stack_bb": 100,
    "spot": {"type": "rfi", "hero_pos": "CO", "villain_pos": None, "facing": None},
    "actions": ["fold", "raise_2.5"],
    "source": {"name": "Test source", "url": "", "notes": ""},
    "hands": {
        "AA": {"raise_2.5": 1.0},
        "A5s": {"raise_2.5": 0.6, "fold": 0.4},
        "72o": {"fold": 1.0},
    },
}


def make(**changes):
    d = copy.deepcopy(BASE)
    for k, v in changes.items():
        d[k] = v
    return d


def test_loads_brief_example():
    c = chart_from_dict(make())
    assert c.id == BASE["id"]
    assert c.spot_type == "rfi" and c.hero_pos == "CO" and c.villain_pos is None
    assert c.actions == ("fold", "raise_2.5")
    assert c.frequencies("A5s") == {"fold": 0.4, "raise_2.5": 0.6}
    assert c.frequencies("AA") == {"fold": 0.0, "raise_2.5": 1.0}
    assert len(c.hands) == 169


def test_missing_hands_default_to_fold_with_warning(caplog):
    with caplog.at_level(logging.WARNING):
        c = chart_from_dict(make())
    assert c.frequencies("KK") == {"fold": 1.0, "raise_2.5": 0.0}
    assert len(c.missing_hands) == 166
    assert "KK" in c.missing_hands and "AA" not in c.missing_hands
    assert "166 hands missing" in caplog.text


def test_complete_chart_no_warning(caplog):
    from trainer.charts.range_parser import build_hands

    with caplog.at_level(logging.WARNING):
        c = chart_from_dict(make(hands=build_hands({"raise_2.5": "22+"})))
    assert c.missing_hands == ()
    assert caplog.text == ""


def test_is_sample():
    assert not chart_from_dict(make()).is_sample
    assert chart_from_dict(make(source={"name": SAMPLE_SOURCE_NAME})).is_sample


def test_rounded_sums_tolerated():
    c = chart_from_dict(make(hands={"AA": {"raise_2.5": 0.333, "fold": 0.667}, "KK": {"raise_2.5": 0.9995}}))
    assert c.frequencies("AA")["raise_2.5"] == 0.333


@pytest.mark.parametrize(
    "hands,match",
    [
        ({"AA": {"raise_2.5": 0.6}}, "add up"),
        ({"AA": {"raise_2.5": 0.6, "fold": 0.6}}, "add up"),
        ({"AA": {"call": 1.0}}, "not in 'actions'"),
        ({"AA": {"raise_2.5": 1.5, "fold": -0.5}}, "0..1"),
        ({"AA": {"raise_2.5": "1"}}, "0..1"),
        ({"AA": {"raise_2.5": True}}, "0..1"),
        ({"KAs": {"fold": 1.0}}, "not a hand class"),
        ({"AA": {}}, "non-empty"),
        ({"AA": 1.0}, "non-empty"),
    ],
)
def test_bad_hands(hands, match):
    with pytest.raises(ChartError, match=match):
        chart_from_dict(make(hands=hands))


@pytest.mark.parametrize(
    "changes,match",
    [
        ({"game": "plo"}, "not supported"),
        ({"format": "mtt"}, "format"),
        ({"table_size": 7}, "table_size"),
        ({"stack_bb": 0}, "stack_bb"),
        ({"actions": ["raise_2.5"]}, "must include 'fold'"),
        ({"actions": ["fold", "fold", "raise_2.5"]}, "duplicates"),
        ({"actions": []}, "non-empty"),
        ({"source": {"name": ""}}, "source.name"),
        ({"source": {}}, "source.name"),
        ({"spot": {"type": "squeeze", "hero_pos": "CO"}}, "spot.type"),
        ({"spot": {"type": "rfi", "hero_pos": "UTG1"}}, "hero_pos"),
        ({"spot": {"type": "rfi", "hero_pos": "BB"}}, "BB"),
        ({"spot": {"type": "rfi", "hero_pos": "CO", "villain_pos": "UTG"}}, "null"),
        ({"spot": {"type": "vs_open", "hero_pos": "CO", "villain_pos": "BTN"}}, "act before"),
        ({"spot": {"type": "vs_open", "hero_pos": "CO", "villain_pos": "CO"}}, "same"),
        ({"spot": {"type": "vs_open", "hero_pos": "CO", "villain_pos": None}}, "villain_pos"),
        ({"spot": {"type": "vs_3bet", "hero_pos": "CO", "villain_pos": "UTG"}}, "act after"),
        ({"spot": {"type": "rfi", "hero_pos": "CO", "facing": {"open_size_bb": -1}}}, "facing"),
    ],
)
def test_bad_fields(changes, match):
    with pytest.raises(ChartError, match=match):
        chart_from_dict(make(**changes))


def test_missing_required_field():
    d = make()
    del d["source"]
    with pytest.raises(ChartError, match="source"):
        chart_from_dict(d)


def test_valid_vs_open_and_vs_3bet():
    chart_from_dict(make(spot={"type": "vs_open", "hero_pos": "BB", "villain_pos": "SB",
                               "facing": {"open_size_bb": 3}}))
    chart_from_dict(make(spot={"type": "vs_3bet", "hero_pos": "SB", "villain_pos": "BB",
                               "facing": {"open_size_bb": 3, "threebet_size_bb": 9}}))


def test_load_chart_file_and_bad_json(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(make()), encoding="utf-8")
    assert load_chart(p).path == str(p)
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ChartError, match="not valid JSON"):
        load_chart(p)


def test_library(tmp_path):
    (tmp_path / "sub").mkdir()
    a = make()
    b = make(id="b", spot={"type": "vs_open", "hero_pos": "BTN", "villain_pos": "CO"},
             actions=["fold", "call", "raise_8"], hands={"AA": {"raise_8": 1.0}})
    c = make(id="c", table_size=9, spot={"type": "rfi", "hero_pos": "UTG1"})
    (tmp_path / "a.json").write_text(json.dumps(a))
    (tmp_path / "sub" / "b.json").write_text(json.dumps(b))
    (tmp_path / "sub" / "c.json").write_text(json.dumps(c))
    lib = ChartLibrary.from_directory(tmp_path)
    assert len(lib) == 3
    assert lib.get("b").hero_pos == "BTN"
    assert {x.id for x in lib.find(table_sizes=[6])} == {a["id"], "b"}
    assert [x.id for x in lib.find(spot_types=["vs_open"])] == ["b"]
    assert [x.id for x in lib.find(hero_positions=["UTG1"])] == ["c"]
    assert len(lib.find(table_sizes=[], spot_types=None)) == 3
    with pytest.raises(KeyError):
        lib.get("nope")


def test_library_rejects_duplicates():
    c1 = chart_from_dict(make())
    with pytest.raises(ChartError, match="Duplicate"):
        ChartLibrary([c1, chart_from_dict(make())])
    with pytest.raises(ChartError, match="same spot"):
        ChartLibrary([c1, chart_from_dict(make(id="other"))])


def test_leftover_sample_for_a_real_spot_is_ignored(tmp_path, caplog):
    """An old sample file surviving an update must not stop the app."""
    import json
    import shutil
    from trainer.charts.loader import ChartLibrary
    from trainer.config import CHARTS_DIR
    src = CHARTS_DIR / "nlhe" / "rangeconverter" / "rangeconverter-nlhe-cash-9max-100bb-rfi-BTN.json"
    shutil.copy(src, tmp_path / "real.json")
    d = json.load(open(src))
    d["id"] = "SAMPLE-nlhe-cash-9max-100bb-rfi-BTN"
    d["source"] = {"name": "SAMPLE - NOT REAL STRATEGY", "url": "", "notes": ""}
    (tmp_path / "sample.json").write_text(json.dumps(d))
    lib = ChartLibrary.from_directory(tmp_path)
    assert [c.id for c in lib.charts] == ["rangeconverter-nlhe-cash-9max-100bb-rfi-BTN"]
    assert "sample chart ignored" in caplog.text
