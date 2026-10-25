import copy
import json

import pytest

from trainer.advice.library import TIPS_PATH, AdviceError, AdviceLibrary, tip_from_dict

GOOD = {
    "id": "t1",
    "text": "Compare your equity with the price: call / (pot + bet + call).",
    "status": "verified",
    "scope": {"drills": ["equity"], "games": ["nlhe"], "streets": ["flop", "turn"]},
    "sources": [
        {"name": "Pot odds", "publisher": "Publisher A", "url": "https://a.example/pot-odds",
         "quote": "Pot odds are the ratio of the current size of the pot to the cost of a contemplated call.",
         "accessed": "2026-10-25"},
        {"name": "Pot odds explained", "publisher": "Publisher B", "url": "https://b.example/odds",
         "quote": "You need equity of at least call divided by pot plus bet plus call to break even.",
         "accessed": "2026-10-25"},
    ],
    "checks": [
        {"type": "source_fetched", "passed": True, "detail": "both pages fetched 2026-10-25"},
        {"type": "corroborated", "passed": True, "detail": "two unrelated publishers agree"},
        {"type": "math_consistent", "passed": True, "detail": "matches trainer.graders.equity.required_equity"},
    ],
}


def make(**changes):
    """A copy of GOOD with fields replaced (a 'scope' replaces the whole scope)."""
    d = copy.deepcopy(GOOD)
    for k, v in changes.items():
        d[k] = v
    return d


def test_good_tip_loads():
    t = tip_from_dict(make())
    assert t.is_verified and t.scope.streets == ("flop", "turn")
    assert t.public()["source_names"] == ["Publisher A", "Publisher B"]
    assert t.evidence()["checks"][0]["type"] == "source_fetched"


@pytest.mark.parametrize("changes,match", [
    ({"status": "maybe"}, "status"),
    ({"text": "short"}, "sentence"),
    ({"scope": {"drills": []}}, "scope.drills is required"),
    ({"scope": {"drills": ["equity"], "positions": ["MP"]}}, "unknown values"),
    ({"scope": {"drills": ["equity"], "streets": "flop"}}, "list of strings"),
    ({"scope": {"drills": ["equity"], "stack_bb_min": -5}}, "positive"),
    ({"scope": {"drills": ["equity"], "bogus": 1}}, "unknown scope field"),
])
def test_bad_fields(changes, match):
    with pytest.raises(AdviceError, match=match):
        tip_from_dict(make(**changes))


def test_verified_needs_two_publishers():
    d = make()
    d["sources"][1]["publisher"] = "Publisher A"
    with pytest.raises(AdviceError, match="different publishers"):
        tip_from_dict(d)
    d["status"] = "unverified"
    assert not tip_from_dict(d).is_verified  # fine when not claiming verification


def test_verified_needs_real_quotes_and_checks():
    d = make()
    d["sources"][0]["quote"] = "says so"
    with pytest.raises(AdviceError, match="actual supporting passage"):
        tip_from_dict(d)
    d = make()
    d["checks"] = [d["checks"][0]]
    with pytest.raises(AdviceError, match="corroborated"):
        tip_from_dict(d)
    d = make()
    d["checks"].append({"type": "math_consistent", "passed": False, "detail": "disagrees with solver"})
    with pytest.raises(AdviceError, match="failed check"):
        tip_from_dict(d)
    d["status"] = "contested"
    assert tip_from_dict(d).status == "contested"


def test_source_fields_required():
    d = make()
    d["sources"][0]["url"] = "page 12"
    with pytest.raises(AdviceError, match="web address"):
        tip_from_dict(d)
    d = make()
    d["sources"][0]["accessed"] = "yesterday"
    with pytest.raises(AdviceError, match="date"):
        tip_from_dict(d)


def test_scope_matching_and_ordering():
    broad = tip_from_dict(make(id="broad", scope={"drills": ["equity"]}))
    narrow = tip_from_dict(make(id="narrow", scope={"drills": ["equity"], "games": ["plo"], "streets": ["flop"]}))
    stack = tip_from_dict(make(id="stack", scope={"drills": ["preflop_chart"], "stack_bb_max": 15}))
    lib = AdviceLibrary([broad, narrow, stack])
    assert [t.id for t in lib.matching(drill="equity", game="plo", street="flop")] == ["narrow", "broad"]
    assert [t.id for t in lib.matching(drill="equity", game="nlhe", street="flop")] == ["broad"]
    assert [t.id for t in lib.matching(drill="preflop_chart", stack_bb=10)] == ["stack"]
    assert lib.matching(drill="preflop_chart", stack_bb=100) == []
    assert lib.matching(drill="preflop_chart") == []  # stack scope needs a stack
    assert lib.matching(drill="nuts") == []


def test_contested_tips_are_listed_and_shown():
    t = tip_from_dict(make(status="contested"))
    assert AdviceLibrary([t]).matching(drill="equity", game="nlhe", street="flop") == [t]
    assert AdviceLibrary([t]).contested() == [t]


def test_duplicate_ids_and_missing_file(tmp_path):
    with pytest.raises(AdviceError, match="duplicate"):
        AdviceLibrary([tip_from_dict(make()), tip_from_dict(make())])
    assert AdviceLibrary.load(tmp_path / "nope.json").tips == []
    p = tmp_path / "tips.json"
    p.write_text(json.dumps({"tips": [make()]}))
    assert len(AdviceLibrary.load(p).verified()) == 1


def test_shipped_tips_file_is_valid():
    """Every tip in data/advice/tips.json passes the evidence rules."""
    if not TIPS_PATH.exists():
        pytest.skip("no tips yet")
    lib = AdviceLibrary.load()
    assert lib.tips
    for t in lib.verified():
        assert len({s.url for s in t.sources}) >= 2


def test_single_source_and_contested_are_shown_with_rules():
    single = make(id="single", status="single_source")
    single["sources"] = [single["sources"][0]]
    single["checks"] = [{"type": "source_fetched", "passed": True, "detail": "ok"},
                        {"type": "corroborated", "passed": False, "detail": "1 publisher"}]
    t = tip_from_dict(single)
    assert t.status == "single_source"
    contested = make(id="contested", status="contested")
    contested["checks"] = contested["checks"] + [{"type": "math_consistent", "passed": False, "detail": "disagrees"}]
    c = tip_from_dict(contested)
    v = tip_from_dict(make(id="v"))
    lib = AdviceLibrary([c, t, v])
    assert [x.id for x in lib.matching(drill="equity", game="nlhe", street="flop")] == ["v", "single", "contested"]
    # single_source can't hide a failed math check, and needs a fetched source.
    bad = make(id="bad", status="single_source")
    bad["checks"] = [{"type": "source_fetched", "passed": True, "detail": "ok"},
                     {"type": "math_consistent", "passed": False, "detail": "no"}]
    with pytest.raises(AdviceError, match="contested, not single_source"):
        tip_from_dict(bad)
    bad["checks"] = []
    with pytest.raises(AdviceError, match="source_fetched"):
        tip_from_dict(bad)
    assert AdviceLibrary([tip_from_dict(make(status="unverified"))]).matching(drill="equity") == []
