import json

from trainer.charts.loader import ChartLibrary, chart_from_dict, dump_chart_json
from trainer.config import CHARTS_DIR, SAMPLE_SOURCE_NAME

SAMPLE_DIR = CHARTS_DIR / "nlhe" / "sample"


def test_all_sample_charts_load_and_are_marked_fake():
    lib = ChartLibrary.from_directory(SAMPLE_DIR)
    assert len(lib) > 0
    for c in lib.charts:
        assert c.is_sample, c.id
        assert c.source["name"] == SAMPLE_SOURCE_NAME
        assert c.id.startswith("SAMPLE-")
        assert c.missing_hands == ()


def test_charts_cover_all_spot_types_and_table_sizes():
    """Across samples and real charts, every cash spot type exists at both table sizes."""
    lib = ChartLibrary.from_directory(CHARTS_DIR)
    for size in (6, 9):
        for spot in ("rfi", "vs_open", "vs_3bet"):
            assert lib.find(format="cash", table_sizes=[size], spot_types=[spot]), (size, spot)


def test_real_6max_charts_replace_samples():
    lib = ChartLibrary.from_directory(CHARTS_DIR)
    rfi6 = lib.find(format="cash", table_sizes=[6], spot_types=["rfi"])
    assert len(rfi6) == 5 and not any(c.is_sample for c in rfi6)
    assert {c.hero_pos for c in rfi6} == {"UTG", "HJ", "CO", "BTN", "SB"}
    bb = [c for c in lib.find(format="cash", table_sizes=[6], spot_types=["vs_open"]) if c.hero_pos == "BB"]
    assert bb and not any(c.is_sample for c in bb)
    for c in rfi6 + bb:
        assert c.source["name"].startswith("Pokalab")
        assert "Corroboration" in c.source["notes"] and c.missing_hands == ()


def test_whole_chart_directory_loads():
    ChartLibrary.from_directory(CHARTS_DIR)


def test_dump_round_trip():
    path = next(SAMPLE_DIR.glob("*.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert json.loads(dump_chart_json(data)) == data
    chart_from_dict(json.loads(dump_chart_json(data)))
