import json
import os
import tempfile

from core import arena, agents, module_adapter
from core.campaign import run_campaign
from core.ledger import Ledger


def test_verifier_accepts_correct_rejects_wrong():
    for t in arena.list_targets("demo"):
        real = {"weak-creds-01": "XMCTF{weak_creds_demo_01}",
                "traversal-01": "XMCTF{traversal_demo_02}",
                "sqli-sim-01": "XMCTF{sqli_sim_demo_03}"}[t["target_id"]]
        assert arena.submit_flag(t["target_id"], real)["verdict"] == "CAPTURED"
        bad = arena.submit_flag(t["target_id"], "XMCTF{forged}")
        assert bad["verdict"] == "REJECTED"


def test_broken_exploits_must_fail():
    # anti-cheat: wrong creds, wrong path, wrong sqli must NOT capture
    assert arena.try_creds("weak-creds-01", "admin", "wrong")["captured"] is False
    assert arena.read_file("traversal-01", "index.html")["captured"] is False
    assert arena.exploit_sqli_sim("sqli-sim-01", "1; DROP TABLE users")["captured"] is False
    assert arena.submit_flag("weak-creds-01", "XMCTF{forged}")["ok"] is False


def test_high_risk_tool_denied():
    assert arena.is_allowed("reverse_shell") is False
    try:
        agents._guard("reverse_shell")
        assert False, "must deny"
    except agents.Denied:
        pass


def test_full_campaign_captures_all():
    with tempfile.TemporaryDirectory() as d:
        s = run_campaign("demo", "red-01", runs_dir=os.path.join(d, "runs"))
        assert s["captured"] == s["targets"] == 3
        assert s["chain_ok"] is True
        ledger = Ledger(s["ledger"])
        assert ledger.verify_chain() is True
        for r in s["results"]:
            assert r["verdict"] == "CAPTURED"
            assert agents.verify_receipt(r["receipt"], ledger) is True


def test_forged_receipt_fails():
    with tempfile.TemporaryDirectory() as d:
        s = run_campaign("demo", "red-01", runs_dir=os.path.join(d, "runs"))
        ledger = Ledger(s["ledger"])
        good = s["results"][0]["receipt"]
        forged = dict(good, flag_sha256="0" * 64)
        assert agents.verify_receipt(forged, ledger) is False


def test_module_status_shape():
    st = module_adapter.status("demo", "red-01")
    assert st["module_id"] == "xmrecon"
    assert st["programs"][0]["program_id"] == "xmrecon/demo"
    assert "security" in st["programs"][0]["capability_demand"]


def test_probe_verb():
    import json
    import subprocess
    out = subprocess.run(["python3", "-m", "core.cli", "probe",
                          "weak-creds-01"], capture_output=True, text=True,
                         cwd="/home/ubuntu/qpbot")
    assert out.returncode == 0
    assert json.loads(out.stdout)["ok"] is True
    bad = subprocess.run(["python3", "-m", "core.cli", "probe", "nope"],
                         capture_output=True, text=True,
                         cwd="/home/ubuntu/qpbot")
    assert bad.returncode == 1


def test_submit_verb():
    import json
    import subprocess
    ok = subprocess.run(["python3", "-m", "core.cli", "submit",
                         "weak-creds-01", "XMCTF{weak_creds_demo_01}"],
                        capture_output=True, text=True,
                        cwd="/home/ubuntu/qpbot")
    assert ok.returncode == 0
    assert json.loads(ok.stdout)["verdict"] == "CAPTURED"
    bad = subprocess.run(["python3", "-m", "core.cli", "submit",
                          "weak-creds-01", "XMCTF{forged}"],
                         capture_output=True, text=True,
                         cwd="/home/ubuntu/qpbot")
    assert bad.returncode == 1
