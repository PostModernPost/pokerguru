import json
import re

from trainer.config import WEB_DIR


def load():
    return json.loads((WEB_DIR / "glossary.json").read_text(encoding="utf-8"))


def test_glossary_is_well_formed():
    data = load()
    names = []
    for g in data["groups"]:
        assert g["title"] and g["terms"]
        for t in g["terms"]:
            assert t["term"].strip() and len(t["definition"]) > 20, t
            assert not t["definition"].strip().endswith(("...", "..")), t
            names.append(t["term"].lower())
            names.extend(a.lower() for a in t.get("aliases", []))
    assert len(names) == len(set(names)), "duplicate term/alias: " + ", ".join(n for n in names if names.count(n) > 1)
    assert len(names) > 100


def test_glossary_has_no_advice_words():
    """Definitions describe; they don't tell the player what to do."""
    data = load()
    banned = re.compile(r"\byou should\b|\balways (raise|fold|call|shove)\b|\bnever (raise|fold|call|shove)\b", re.I)
    for g in data["groups"]:
        for t in g["terms"]:
            assert not banned.search(t["definition"]), t["term"]


def test_glossary_served_and_docs_in_sync(tmp_path):
    from fastapi.testclient import TestClient
    from trainer.api.app import create_app
    from trainer.config import CHARTS_DIR, PROJECT_ROOT

    with TestClient(create_app(charts_dir=CHARTS_DIR, db_path=tmp_path / "p.sqlite", equity_iterations=10)) as c:
        assert c.get("/glossary.json").status_code == 200
        assert c.get("/glossary.js").status_code == 200
        for page in ("/game.html", "/preflop.html", "/equity.html", "/nuts.html", "/potlimit.html", "/stats.html"):
            assert "glossary.js" in c.get(page).text, page
    md = (PROJECT_ROOT / "docs" / "glossary.md").read_text(encoding="utf-8")
    for g in load()["groups"]:
        for t in g["terms"]:
            assert f"**{t['term']}**" in md, f"docs/glossary.md is stale: run scripts/export_glossary.py ({t['term']})"
