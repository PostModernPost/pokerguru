import pytest
from fastapi.testclient import TestClient

from trainer.api.app import create_app
from trainer.config import CHARTS_DIR
from trainer.progress.store import AttemptStore


@pytest.fixture
def ctx(tmp_path):
    db = tmp_path / "p.sqlite"
    with TestClient(create_app(charts_dir=CHARTS_DIR, db_path=db, seed=3, equity_iterations=300)) as client:
        yield client, AttemptStore(db)


def test_equity_page_served(ctx):
    client, _ = ctx
    r = client.get("/equity.html")
    assert r.status_code == 200 and "Direct odds only" in r.text
    assert client.get("/equity.js").status_code == 200


def test_options(ctx):
    client, _ = ctx
    o = client.get("/api/equity/options").json()
    assert [g["id"] for g in o["games"]] == ["nlhe", "plo"]
    assert [s["id"] for s in o["streets"]] == ["flop", "turn"]


def test_next_filters(ctx):
    client, _ = ctx
    for _ in range(10):
        s = client.post("/api/equity/next", json={"games": ["plo"], "streets": ["turn"]}).json()
        assert s["game"] == "plo" and len(s["hero_cards"]) == 4 and len(s["board"]) == 4
        assert s["bet_bb"] <= s["pot_bb"]
        assert len(s["buckets"]) == 6
    assert client.post("/api/equity/next", json={"games": ["stud"]}).status_code == 400


def test_answer_known_spot(ctx):
    client, store = ctx
    # Hero has a king-high straight flush that nothing can beat (PLO two-card rule): equity 100%.
    # Pot 10, bet 10: need 33.3%, so call.
    body = {"game": "plo", "street": "turn", "hero_cards": ["Ts", "9s", "8d", "7d"],
            "board": ["Ks", "Qs", "Js", "2h"], "pot_bb": 10, "bet_bb": 10,
            "bucket": "60+", "decision": "call", "response_time_ms": 4000}
    r = client.post("/api/equity/answer", json=body).json()
    assert r["equity"] == 1.0
    assert r["bucket"]["grade"] == "correct" and r["decision"]["grade"] == "correct"
    assert r["decision"]["required"] == pytest.approx(1 / 3)
    rows = store.recent()
    assert {row["drill_type"] for row in rows} == {"equity_estimate", "pot_odds_decision"}
    for row in rows:
        assert row["spot"]["equity"] == 1.0
        assert row["chart_source"] == "computed"
        assert row["response_time_ms"] == 4000
        assert row["hand_class"] is None

    body.update(bucket="lt20", decision="fold")
    r = client.post("/api/equity/answer", json=body).json()
    assert r["bucket"]["grade"] == "wrong" and r["decision"]["grade"] == "wrong"
    assert r["summary"] == {"total": 2, "correct": 1, "acceptable": 0, "wrong": 1}
    assert client.get("/api/summary", params={"drill_type": "equity_estimate"}).json()["total"] == 2


def test_answer_is_reproducible(ctx):
    client, _ = ctx
    s = client.post("/api/equity/next", json={"games": ["nlhe"]}).json()
    body = {k: s[k] for k in ("game", "street", "hero_cards", "board", "pot_bb", "bet_bb")}
    body.update(bucket="30-40", decision="call")
    a = client.post("/api/equity/answer", json=body).json()
    b = client.post("/api/equity/answer", json=body).json()
    assert a["equity"] == b["equity"]
    assert 0 < a["equity"] < 1


@pytest.mark.parametrize(
    "change",
    [
        {"bucket": "35-45"},
        {"decision": "raise"},
        {"hero_cards": ["Ts", "Ts", "8d", "7d"]},
        {"board": ["Ks", "Qs", "Js"]},         # 3 cards but street says turn
        {"bet_bb": 20},                          # PLO bet bigger than pot
        {"game": "stud"},
    ],
)
def test_answer_bad_input(ctx, change):
    client, store = ctx
    body = {"game": "plo", "street": "turn", "hero_cards": ["Ts", "9s", "8d", "7d"],
            "board": ["Ks", "Qs", "Js", "2h"], "pot_bb": 10, "bet_bb": 10,
            "bucket": "60+", "decision": "call"}
    body.update(change)
    assert client.post("/api/equity/answer", json=body).status_code == 400
    assert store.summary()["total"] == 0
