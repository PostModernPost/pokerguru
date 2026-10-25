import pytest
from fastapi.testclient import TestClient

from trainer.api.app import create_app
from trainer.config import CHARTS_DIR
from trainer.progress.store import AttemptStore


@pytest.fixture
def ctx(tmp_path):
    db = tmp_path / "p.sqlite"
    with TestClient(create_app(charts_dir=CHARTS_DIR, db_path=db, seed=5, equity_iterations=50)) as client:
        yield client, AttemptStore(db)


def test_pages_served(ctx):
    client, _ = ctx
    for page in ("/nuts.html", "/nuts.js", "/potlimit.html", "/potlimit.js"):
        assert client.get(page).status_code == 200, page


def test_nuts_next_and_answer(ctx):
    client, store = ctx
    s = client.post("/api/plo/nuts/next", json={"streets": ["flop"]}).json()
    assert s["street"] == "flop" and len(s["options"]) == 4 and s["asks_draw"] is True
    body = {"street": s["street"], "hero_cards": s["hero_cards"], "board": s["board"],
            "nut_choice": s["options"][0], "has_nuts": False, "draw_choice": "none", "response_time_ms": 900}
    r = client.post("/api/plo/nuts/answer", json=body)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["nut_hand"]["correct"] in s["options"]
    assert res["has_nuts"]["grade"] in ("correct", "wrong")
    assert res["explanation"].startswith("The nuts is ")
    types = {row["drill_type"] for row in store.recent()}
    assert "plo_nut_hand" in types and "plo_has_nuts" in types
    if res["draw"] is not None:
        assert "plo_nut_draw" in types


def test_nuts_known_spot_grades(ctx):
    client, _ = ctx
    body = {"street": "flop", "hero_cards": ["Ac", "Kc", "2d", "3d"], "board": ["Jc", "9c", "4s"],
            "nut_choice": "Three of a kind, jacks", "has_nuts": False, "draw_choice": "nut_draw"}
    res = client.post("/api/plo/nuts/answer", json=body).json()
    assert res["nut_hand"]["grade"] == "correct"
    assert res["has_nuts"]["grade"] == "correct"
    assert res["draw"]["grade"] == "correct" and res["draw"]["nut_outs"] == ["2c", "3c", "5c", "6c"]
    assert res["hero_hand"]["description"] == "Ace-high, no pair"


def test_nuts_river_needs_no_draw(ctx):
    client, _ = ctx
    body = {"street": "river", "hero_cards": ["2c", "3d", "7h", "9s"], "board": ["As", "Ah", "Kd", "Kc", "5s"],
            "nut_choice": "Four of a kind, aces", "has_nuts": False}
    res = client.post("/api/plo/nuts/answer", json=body).json()
    assert res["draw"] is None and res["nut_hand"]["grade"] == "correct"


@pytest.mark.parametrize("change", [
    {"nut_choice": "Royal flush"},            # not among the choices
    {"draw_choice": None},                     # required on the flop
    {"draw_choice": "maybe"},
    {"board": ["Jc", "9c"]},
    {"hero_cards": ["Ac", "Ac", "2d", "3d"]},
])
def test_nuts_bad_input(ctx, change):
    client, store = ctx
    body = {"street": "flop", "hero_cards": ["Ac", "Kc", "2d", "3d"], "board": ["Jc", "9c", "4s"],
            "nut_choice": "Three of a kind, jacks", "has_nuts": False, "draw_choice": "nut_draw"}
    body.update(change)
    assert client.post("/api/plo/nuts/answer", json=body).status_code == 400
    assert store.summary()["total"] == 0


def test_pot_limit_next_hides_answer_and_answer_grades(ctx):
    client, store = ctx
    s = client.post("/api/plo/potlimit/next", json={"stages": ["postflop"]}).json()
    assert "max_raise_to" not in s and "pot" not in s and s["stage"] == "postflop"
    r = client.post("/api/plo/potlimit/answer", json={"spot": s, "answer": 1, "response_time_ms": 100}).json()
    assert r["grade"] == "wrong" and r["correct"] > 1
    r2 = client.post("/api/plo/potlimit/answer", json={"spot": s, "answer": r["correct"]}).json()
    assert r2["grade"] == "correct"
    assert r2["summary"] == {"total": 2, "correct": 1, "acceptable": 0, "wrong": 1}
    [a, b] = store.recent()
    assert a["drill_type"] == "plo_pot_limit" and a["user_answer"] == f"{r['correct']:g}"


def test_pot_limit_brief_case_via_api(ctx):
    client, _ = ctx
    spot = {"stage": "preflop", "small_blind": 1, "big_blind": 2, "hero_pos": "UTG", "hero_in": 0,
            "pot_before_round": 0, "history": []}
    r = client.post("/api/plo/potlimit/answer", json={"spot": spot, "answer": 7}).json()
    assert r["grade"] == "correct" and r["correct"] == 7
    spot = {"stage": "postflop", "small_blind": 1, "big_blind": 2, "hero_pos": "BTN", "hero_in": 0,
            "pot_before_round": 100, "history": [{"pos": "Villain", "action": "bet", "to": 100}]}
    r = client.post("/api/plo/potlimit/answer", json={"spot": spot, "answer": 400}).json()
    assert r["grade"] == "correct"


def test_pot_limit_bad_spot(ctx):
    client, _ = ctx
    assert client.post("/api/plo/potlimit/answer", json={"spot": {"stage": "preflop"}, "answer": 7}).status_code == 400
    assert client.post("/api/plo/potlimit/next", json={"stages": ["river"]}).status_code == 400
