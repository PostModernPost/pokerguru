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
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (302, 307) and r.headers["location"] == "/game.html"  # the game is the home page
    r = client.get("/preflop.html")
    assert r.status_code == 200 and "Preflop" in r.text and "equity.html" in r.text
    assert client.get("/app.js").status_code == 200
    assert client.get("/style.css").status_code == 200
    assert client.get("/common.js").status_code == 200


def test_options(ctx):
    client, _ = ctx
    o = client.get("/api/options?include_samples=true").json()
    assert o["table_sizes"] == [2, 6, 9]  # heads-up comes from the push/fold charts
    assert "UTG1" in o["positions"]["9"] and "UTG1" not in o["positions"]["6"]
    assert {s["id"] for s in o["spot_types"]} == {"rfi", "vs_open", "vs_3bet", "push", "vs_push"}
    assert o["sample_in_use"] is True and o["sample_count"] > 0
    real = client.get("/api/options").json()
    assert real["sample_in_use"] is False and real["chart_count"] < o["chart_count"]
    assert o["thresholds"] == {"correct": 0.5, "acceptable": 0.15}


def test_next_respects_filters(ctx):
    client, _ = ctx
    for _ in range(30):
        s = client.post("/api/preflop/next", json={"table_sizes": [6], "spot_types": ["vs_3bet"],
                                                   "hero_positions": ["CO", "BTN"], "include_samples": True}).json()
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


def test_samples_off_by_default(ctx):
    client, _ = ctx
    for _ in range(40):
        s = client.post("/api/preflop/next", json={}).json()
        assert s["is_sample"] is False
    # 6-max facing a 3-bet only has sample charts today.
    r = client.post("/api/preflop/next", json={"table_sizes": [6], "spot_types": ["vs_3bet"]})
    assert r.status_code == 404 and "sample charts" in r.json()["detail"]
    s = client.post("/api/preflop/next", json={"table_sizes": [6], "spot_types": ["vs_3bet"], "include_samples": True}).json()
    assert s["is_sample"] is True


def test_answer_grades_and_records(ctx):
    client, store = ctx
    s = client.post("/api/preflop/next", json={"include_samples": True, "table_sizes": [6], "spot_types": ["vs_3bet"]}).json()
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
    why = res["why"]
    assert why["lines"][0].startswith(res["hand_class"] + " is ")
    assert 1 <= why["equity_rank"] <= 169 and 0 < why["equity_vs_random"] < 1
    assert 0 <= why["chart"]["play_frequency"] <= 1
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
    chart = lib.get("rangeconverter-nlhe-cash-9max-100bb-rfi-CO")
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
        ({"chart_id": "rangeconverter-nlhe-cash-9max-100bb-rfi-CO", "hero_cards": ["As", "As"], "action": "fold"}, 400),
        ({"chart_id": "rangeconverter-nlhe-cash-9max-100bb-rfi-CO", "hero_cards": ["Xx", "Kd"], "action": "fold"}, 400),
        ({"chart_id": "rangeconverter-nlhe-cash-9max-100bb-rfi-CO", "hero_cards": ["As", "Kd"], "action": "call"}, 400),
        ({"chart_id": "rangeconverter-nlhe-cash-9max-100bb-rfi-CO", "hero_cards": ["As"], "action": "fold"}, 422),
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
    chart_id = "rangeconverter-nlhe-cash-9max-100bb-rfi-CO"
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
    o = client.get("/api/options?include_samples=true").json()
    assert "cash" in o["per_format"] and o["per_format"]["cash"]["stacks"] == [100]
    s = client.post("/api/preflop/next", json={"formats": ["cash"], "stacks": [100]}).json()
    assert s["format"] == "cash" and s["stack_bb"] == 100
    assert client.post("/api/preflop/next", json={"stacks": [37]}).status_code == 404


VERIFIED_TIP = {
    "id": "t-preflop", "text": "A verified sentence of advice for testing the plumbing only.", "status": "verified",
    "scope": {"drills": ["preflop_chart"], "games": ["nlhe"], "formats": ["cash"], "spot_types": ["rfi"]},
    "sources": [
        {"name": "A", "publisher": "Pub A", "url": "https://a.example/x", "quote": "a long enough supporting passage here", "accessed": "2026-10-25"},
        {"name": "B", "publisher": "Pub B", "url": "https://b.example/y", "quote": "another long enough supporting passage", "accessed": "2026-10-25"},
    ],
    "checks": [{"type": "source_fetched", "passed": True, "detail": "ok"}, {"type": "corroborated", "passed": True, "detail": "ok"}],
}
CONTESTED_TIP = dict(VERIFIED_TIP, id="t-bad", status="contested",
                     checks=VERIFIED_TIP["checks"] + [{"type": "math_consistent", "passed": False, "detail": "disagrees"}])


def test_tips_shown_only_in_scope_and_only_verified(tmp_path):
    import json
    from fastapi.testclient import TestClient
    tips = tmp_path / "tips.json"
    tips.write_text(json.dumps({"tips": [VERIFIED_TIP, CONTESTED_TIP]}))
    with TestClient(create_app(charts_dir=CHARTS_DIR, db_path=tmp_path / "p.sqlite", seed=1, equity_iterations=20,
                               advice_path=tips)) as client:
        rfi = client.post("/api/preflop/answer", json={"chart_id": "rangeconverter-nlhe-cash-9max-100bb-rfi-CO",
                                                       "hero_cards": ["As", "Kd"], "action": "fold"}).json()
        assert [t["id"] for t in rfi["tips"]] == ["t-preflop", "t-bad"]  # contested shown too, after verified
        assert rfi["tips"][1]["status"] == "contested"
        assert rfi["tips"][0]["source_names"] == ["Pub A", "Pub B"]
        vs3 = client.post("/api/preflop/answer", json={"chart_id": "SAMPLE-nlhe-cash-6max-100bb-vs_3bet-CO-vs-BTN",
                                                       "hero_cards": ["As", "Kd"], "action": "fold"}).json()
        assert vs3["tips"] == []  # out of scope
        ev = client.get("/api/advice/t-preflop").json()
        assert ev["evidence"]["sources"][0]["quote"].startswith("a long enough")
        assert client.get("/api/advice/nope").status_code == 404
        summary = client.get("/api/advice").json()
        assert summary["verified"] == 1 and [t["id"] for t in summary["contested"]] == ["t-bad"]
        # The other drills carry a (possibly empty) tips list too.
        s = client.post("/api/equity/next", json={"games": ["nlhe"]}).json()
        body = {k: s[k] for k in ("game", "street", "hero_cards", "board", "pot_bb", "bet_bb")}
        assert client.post("/api/equity/answer", json=dict(body, bucket="30-40", decision="call")).json()["tips"] == []


def test_shipped_advice_shows_nothing_unverified(ctx):
    """With the real tips file, every tip returned by the API has a shown status (never unverified)."""
    client, _ = ctx
    s = client.get("/api/advice").json()
    assert isinstance(s["verified"], int) and isinstance(s["unverified"], int)
    for cid, cards in (("rangeconverter-nlhe-cash-9max-100bb-rfi-CO", ["As", "Kd"]),):
        r = client.post("/api/preflop/answer", json={"chart_id": cid, "hero_cards": cards, "action": "fold"}).json()
        assert all(t["status"] in ("verified", "single_source", "contested") for t in r["tips"])


def test_version_and_shutdown_guard(ctx):
    client, _ = ctx
    v = client.get("/api/version").json()["version"]
    assert isinstance(v, str) and len(v) >= 8
    # the test client is not 127.0.0.1, so shutdown is refused (and the test process survives)
    assert client.post("/api/shutdown").status_code == 403


def test_chart_view_route(ctx):
    client, _ = ctx
    c = client.get("/api/chart/rangeconverter-nlhe-cash-9max-100bb-vs_3bet-CO-vs-BTN").json()
    assert len(c["range"]) == 169 and len(c["grid"]) == 13 and c["deal_weights"]["72o"] == 0
    assert [a["id"] for a in c["actions"]][:3] == ["fold", "call", "raise_26"]
    assert client.get("/api/chart/nope").status_code == 404
