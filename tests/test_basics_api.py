import pytest
from fastapi.testclient import TestClient

from trainer.api.app import create_app
from trainer.config import CHARTS_DIR
from trainer.progress.store import AttemptStore


@pytest.fixture
def ctx(tmp_path):
    db = tmp_path / "p.sqlite"
    with TestClient(create_app(charts_dir=CHARTS_DIR, db_path=db, seed=8, equity_iterations=20)) as client:
        yield client, AttemptStore(db)


def test_page_and_options(ctx):
    client, _ = ctx
    assert "Basics" in client.get("/basics.html").text and client.get("/basics.js").status_code == 200
    o = client.get("/api/basics/options").json()
    assert [q["id"] for q in o["questions"]] == ["hand", "outs", "price"]


def test_each_question_round_trip(ctx):
    client, store = ctx
    for q in ("hand", "outs", "price"):
        n = client.post("/api/basics/next", json={"questions": [q]}).json()
        assert n["spot"]["question"] == q and len(n["options"]) == 4 and n["prompt"]
        # Answer every option: exactly one is correct, all are recorded.
        grades = []
        for opt in n["options"]:
            r = client.post("/api/basics/answer", json={"spot": n["spot"], "answer": opt, "response_time_ms": 50})
            assert r.status_code == 200, r.text
            grades.append(r.json()["grade"])
        assert grades.count("correct") == 1
        assert client.post("/api/basics/answer", json={"spot": n["spot"], "answer": "nope"}).status_code == 400
    types = {row["drill_type"] for row in store.recent(100)}
    assert types == {"basics_hand", "basics_outs", "basics_price"}
    stats = client.get("/api/stats").json()
    assert any(d["label"].startswith("Basics") for d in stats["drills"])


def test_price_answer_matches_formula_and_shows_tip(ctx):
    client, _ = ctx
    spot = {"question": "price", "game": "nlhe", "street": "flop", "hero_cards": ["Ah", "Kh"],
            "board": ["Qh", "7h", "2c"], "pot_bb": 100, "bet_bb": 50}
    r = client.post("/api/basics/answer", json={"spot": spot, "answer": "25%"}).json()
    assert r["grade"] == "correct" and r["detail"]["required"] == 0.25
    assert any(t["id"] == "pot-odds-formula" for t in r["tips"])


def test_bad_spot_rejected(ctx):
    client, _ = ctx
    spot = {"question": "outs", "game": "plo", "street": "flop", "hero_cards": ["Ah", "Kh", "Qd", "Jd"], "board": ["Qh", "7h", "2c"]}
    assert client.post("/api/basics/answer", json={"spot": spot, "answer": "9"}).status_code == 400
    assert client.post("/api/basics/next", json={"questions": ["riddle"]}).status_code == 400
