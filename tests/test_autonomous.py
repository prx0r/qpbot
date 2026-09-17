from core import tournament, autopilot
from core.guards import assess_promotion, check_budget
import pytest


def test_tournament_all_lanes_capture_and_ranks():
    t = tournament.run_tournament("demo", runs_dir="/tmp/xmrecon-test-tourn")
    assert set(t["lanes"]) == {"creds-first", "traversal-first", "sqli-first"}
    for lane in t["lanes"].values():
        assert lane["captured"] == 3
        assert lane["chain_ok"] is True
    assert t["winner"] in t["lanes"]
    assert t["promotion"]["promoted"] is True


def test_promotion_gate_refuses_weak():
    assert assess_promotion(uses=1, passes=1, total=1,
                            regressions=0)["promoted"] is False
    assert assess_promotion(uses=3, passes=1, total=3,
                            regressions=0)["promoted"] is False
    assert assess_promotion(uses=3, passes=3, total=3,
                            regressions=1)["promoted"] is False
    assert assess_promotion(uses=3, passes=3, total=3,
                            regressions=0)["promoted"] is True


def test_budget_caps():
    with pytest.raises(ValueError):
        check_budget(51)
    with pytest.raises(ValueError):
        check_budget(1, 5001)


def test_autopilot_runs_locally():
    s = autopilot.run_autopilot("demo", rounds=2,
                                runs_dir="/tmp/xmrecon-test-auto")
    assert s["rounds_run"] >= 1
    assert s["chain_ok"] is True
    assert s["final_winner"] in ("creds-first", "traversal-first",
                                 "sqli-first")
