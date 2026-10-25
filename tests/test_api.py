import pytest
from fastapi.testclient import TestClient

from trainer.api.app import create_app
from trainer.config import CHARTS_DIR
from trainer.progress.store import AttemptStore


@pytest.fixture
def ctx(tmp_path):
    db = tmp_path / "p.sqlite"
    client = TestClient(create_app(charts_dir=CHARTS_DIR, db_path=db, seed=1))
    return client, AttemptStore(db)


def test_home_page_served(ctx):
    client, _ = ctx
    r = client.get("/")
    assert r.status_code == 200 and "Preflop" in r.text and "equity.html" in r.text
    assert client.get("/app.js").status_code == 200
    assert client.get("/style.css").status_code == 200
    assert client.get("/common.js").status_code == 200


def test_options(ctx):
    client, _ = ctx
    o = client.get("/api/options").json()
    assert o["table_sizes"] == [6, 9]
    assert "UTG1" in o["positions"]["9"] and "UTG1" not in o["positions"]["6"]
    assert {s["id"] for s in o["spot_types"]} == {"rfi", "vs_open", "vs_3bet"}
    assert o["sample_in_use"] is True
    assert o["thresholds"] == {"correct": 0.5, "acceptable": 0.15}


def test_next_respects_filters(ctx):
    client, _ = ctx
    for _ in range(30):
        s = client.post("/api/preflop/next", json={"table_sizes": [6], "spot_types": ["vs_3bet"],
                                                   "hero_positions": ["CO", "BTN"]}).json()
        assert s["table_size"] == 6 and s["spot_type"] == "vs_3bet" and s["hero_pos"] in ("CO", "BTN")
        assert len(s["hero_cards"]) == 2
        assert s["is_sample"] is True
        assert [a["id"] for a in s["actions"]] == ["fold", "call", "raise_20"]
        assert s["actions"][2]["label"] == "4-bet to 20bb"
        assert any(h["text"].startswith("You raise to") for h in s["history"])
        assert [x["pos"] for x in s["seats"]] == ["UTG", "HJ", "CO", "BTN", "SB", "BB"]


def test_next_no_match(ctx):
    client, _ = ctx
    r = client.post("/api/preflop/next", json={"table_sizes": [6], "hero_positions": ["UTG1"]})
    assert r.status_code == 404 and "No chart" in r.json()["detail"]


def test_answer_grades_and_records(ctx):
    client, store = ctx
    s = client.post("/api/preflop/next", json={}).json()
    r = client.post("/api/preflop/answer", json={
        "chart_id": s["chart_id"], "hero_cards": s["hero_cards"], "action": "fold",
        "response_time_ms": 1500,
    })
    assert r.status_code == 200
    res = r.json()
    assert res["grade"] in ("correct", "acceptable", "wrong")
    assert sum(f["freq"] for f in res["frequencies"]) == pytest.approx(1.0)
    assert len(res["range"]) == 169 and len(res["grid"]) == 13
    assert res["summary"]["total"] == 1
    [row] = store.recent()
    assert row["chart_id"] == s["chart_id"]
    assert row["hero_cards"] == "".join(s["hero_cards"])
    assert row["user_answer"] == "fold"
    assert row["grade"] == res["grade"]
    assert row["response_time_ms"] == 1500
    assert row["is_sample"] is True
    assert row["spot"]["hero_pos"] == s["hero_pos"]


def test_answer_grade_matches_chart(ctx):
    """The API grade must equal what the chart file says for that hand."""
    from trainer.charts.loader import ChartLibrary
    from trainer.graders.preflop_chart import grade_frequency

    client, _ = ctx
    lib = ChartLibrary.from_directory(CHARTS_DIR)
    chart = lib.get("SAMPLE-nlhe-cash-6max-100bb-rfi-CO")
    for cards, hand in [(["As", "Ah"], "AA"), (["Ks", "Qd"], "KQo"), (["7c", "2d"], "72o")]:
        for action in chart.actions:
            res = client.post("/api/preflop/answer", json={
                "chart_id": chart.id, "hero_cards": cards, "action": action}).json()
            f = chart.frequencies(hand)[action]
            assert res["hand_class"] == hand
            assert res["chosen_frequency"] == f
            assert res["grade"] == grade_frequency(f)


@pytest.mark.parametrize(
    "body,status",
    [
        ({"chart_id": "nope", "hero_cards": ["As", "Kd"], "action": "fold"}, 404),
        ({"chart_id": "SAMPLE-nlhe-cash-6max-100bb-rfi-CO", "hero_cards": ["As", "As"], "action": "fold"}, 400),
        ({"chart_id": "SAMPLE-nlhe-cash-6max-100bb-rfi-CO", "hero_cards": ["Xx", "Kd"], "action": "fold"}, 400),
        ({"chart_id": "SAMPLE-nlhe-cash-6max-100bb-rfi-CO", "hero_cards": ["As", "Kd"], "action": "call"}, 400),
        ({"chart_id": "SAMPLE-nlhe-cash-6max-100bb-rfi-CO", "hero_cards": ["As"], "action": "fold"}, 422),
    ],
)
def test_answer_bad_input(ctx, body, status):
    client, store = ctx
    assert client.post("/api/preflop/answer", json=body).status_code == status
    assert store.summary()["total"] == 0


def test_stats_and_leak_mode(ctx):
    client, store = ctx
    assert client.get("/stats.html").status_code == 200 and client.get("/stats.js").status_code == 200
    s = client.get("/api/stats").json()
    assert s["total_attempts"] == 0 and s["drills"] == []
    # Leak mode with no history is a clear 404, not a crash.
    r = client.post("/api/preflop/next", json={"leaks_only": True})
    assert r.status_code == 404 and "No leaks found yet" in r.json()["detail"]

    # Miss the same spot repeatedly, then it should show up as a leak and as a due review.
    chart_id = "SAMPLE-nlhe-cash-6max-100bb-rfi-CO"
    for cards in (["As", "Ah"], ["Ks", "Kh"], ["Qs", "Qh"], ["Js", "Jh"], ["Ts", "Th"], ["9s", "9h"]):
        res = client.post("/api/preflop/answer", json={"chart_id": chart_id, "hero_cards": cards, "action": "fold"}).json()
        if res["grade"] == "correct":  # make sure we have misses: answer the other way too
            client.post("/api/preflop/answer", json={"chart_id": chart_id, "hero_cards": cards, "action": "raise_2.5"})
    s = client.get("/api/stats").json()
    assert s["total_attempts"] >= 6
    assert s["preflop"]["by_position"][0]["key"] == "CO"
    assert s["preflop"]["by_category"][0]["key"] == "pair"
    assert s["preflop"]["reviews"]["total"] >= 1
    assert "pair" in s["preflop"]["leaks"]["weak_categories"] or s["preflop"]["leaks"]["weak_positions"] == ["CO"]
    spot = client.post("/api/preflop/next", json={"leaks_only": True}).json()
    assert spot["reason"] in ("review", "category")


def test_format_and_stack_filters(ctx):
    client, _ = ctx
    o = client.get("/api/options").json()
    assert "cash" in o["per_format"] and o["per_format"]["cash"]["stacks"] == [100]
    s = client.post("/api/preflop/next", json={"formats": ["cash"], "stacks": [100]}).json()
    assert s["format"] == "cash" and s["stack_bb"] == 100
    assert client.post("/api/preflop/next", json={"stacks": [37]}).status_code == 404
