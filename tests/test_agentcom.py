import pytest

from agentcom.htasks.queue import HQueue, HTask
from agentcom.lanes.seed0 import LaneSpec, contract_root, run_seed0
from agentcom.ledger.spend import SpendLedger
from agentcom.services.daemon import Daemon
from agentcom.runtime.pi_lanes import dispatch_argv, lane_spec
from agentcom.interfaces.agentdeck_bridge import agentdeck_state, tiles_for_status
from agentcom.interfaces.acp_server import route


def test_htask_full_lifecycle():
    q = HQueue()
    t = q.emit(HTask("t1", "digit", "Pick direction?", prediction="7",
                     confidence=0.72, lease_s=600))
    assert t.state == "emitted"
    t.display()
    t.acknowledge()
    ans = t.answer_task("8", prediction_before_display="7")
    assert ans["value"] == "8"
    assert t.state == "answered"


def test_htask_expiry_applies_safe_default():
    q = HQueue()
    t = q.emit(HTask("t2", "confirm", "Merge?", lease_s=-1,
                     safe_default="deny"))
    assert q.sweep() == ["t2"]
    assert t.state == "expired"
    assert t.answer["value"] == "deny"


def test_htask_secret_never_in_queue():
    t = HTask("t3", "secret", "Paste API key")
    t.display()
    with pytest.raises(ValueError):
        t.answer_task("sk-anything")


def test_seed0_complete_on_core():
    root = contract_root("capture demo", ["CAPTURED"], {})
    lanes = [LaneSpec("a", strategy="creds-first", contract_root=root),
             LaneSpec("b", strategy="sqli-first", contract_root=root)]
    r = run_seed0("capture demo", ["CAPTURED"], {}, lanes,
                  runs_dir="/tmp/qpbot-seed0")
    assert r["status"] == "COMPLETE"
    assert r["contract_root"] == root
    assert r["promotion"]["promoted"] is True


def test_seed0_root_mismatch_refuses():
    with pytest.raises(ValueError):
        LaneSpec("x", contract_root="wrong").validate("right")


def test_seed0_pi_backend_parks():
    root = contract_root("capture demo", ["CAPTURED"], {})
    r = run_seed0("capture demo", ["CAPTURED"], {},
                  [LaneSpec("p", backend="pi", contract_root=root)])
    assert r["status"] == "AWAITING_PI_BACKEND"


def test_spend_totals():
    s = SpendLedger()
    s.record("demo", "creds-first", 15, 1200, 8)
    s.record("demo", "sqli-first", 15, 900, 6)
    assert s.totals("demo") == {"campaign": "demo", "runs": 2,
                                "evidence_events": 30, "wall_ms": 2100,
                                "usd_minor": 14}


def test_daemon_tick_and_crash_is_unknown():
    d = Daemon()
    d.submit({"kind": "noop"})
    assert d.tick()["state"] == "done"

    def boom(job):
        raise RuntimeError("worker died")
    d.submit({"kind": "lane"})
    assert d.tick(boom)["state"] == "UNKNOWN"
    assert d.tick() is None


def test_daemon_one_writer():
    d = Daemon()
    d.registry.attach("s1", "w1")
    with pytest.raises(ValueError):
        d.registry.attach("s1", "w2")
    d.registry.detach("s1")
    d.registry.attach("s1", "w2")


def test_pi_lane_spec_needs_model():
    spec = lane_spec("capture demo", model="vendor/model:high")
    assert dispatch_argv(spec, "sess-1")[0] == "node"
    with pytest.raises(ValueError):
        dispatch_argv(lane_spec("capture demo"), "sess-1")


def test_bridge_tiles_and_counts():
    from core import module_adapter
    q = HQueue()
    t = q.emit(HTask("t9", "digit", "Pick one?", prediction="7"))
    t.display()
    tiles = tiles_for_status(module_adapter.status("demo"), hqueue=q,
                             spend={"usd_minor": 14})
    kinds = {t["kind"] for t in tiles}
    assert {"campaign", "htask", "queue"} <= kinds
    counts = agentdeck_state(tiles)
    assert counts["approval"] == 1


def test_acp_route_modes():
    assert route("raw", {})["route"] == "pi-direct"
    assert route("agentcom", {})["route"] == "agentcom-pipeline"
    with pytest.raises(ValueError):
        route("other", {})
