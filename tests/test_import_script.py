import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import import_range  # noqa: E402

from trainer.charts.loader import load_chart  # noqa: E402


def test_import_script_writes_valid_chart(tmp_path):
    out = tmp_path / "c.json"
    rc = import_range.main([
        "--id", "t", "--table-size", "6", "--type", "vs_open", "--hero", "BTN",
        "--villain", "CO", "--open-size", "2.5",
        "--action", "raise_8=AA,KK,A5s:0.5", "--action", "call=QQ-TT,A5s:0.25",
        "--source-name", "test", "--out", str(out),
    ])
    assert rc == 0
    data = json.loads(out.read_text())
    assert data["actions"] == ["fold", "raise_8", "call"]
    assert data["stack_bb"] == 100
    c = load_chart(out)
    assert c.frequencies("A5s") == {"fold": 0.25, "raise_8": 0.5, "call": 0.25}
    assert c.facing == {"open_size_bb": 2.5}
    assert c.missing_hands == ()


def test_import_script_reports_range_error(tmp_path, capsys):
    rc = import_range.main([
        "--id", "t", "--table-size", "6", "--type", "rfi", "--hero", "CO",
        "--action", "raise_2.5=AA,AKx", "--source-name", "x", "--out", str(tmp_path / "c.json"),
    ])
    assert rc == 1
    assert "AKx" in capsys.readouterr().err
    assert not (tmp_path / "c.json").exists()
