"""Agents — autonomous redteam loop (perceive -> act -> verify).

Deterministic v0. Techniques ordered by prior. Every attempt appends
evidence to the ledger. Capture settles only through arena.submit_flag.
"""
from __future__ import annotations

from . import arena
from .ledger import Ledger, obj_hash, settle_capture


class Denied(Exception):
    pass


def _guard(tool: str):
    if not arena.is_allowed(tool):
        raise Denied(f"tool denied by grant: {tool}")


def run_target(ledger: Ledger, agent_id: str, target_id: str) -> dict:
    evidence_hashes: list[str] = []

    def log_evidence(kind: str, detail: str) -> dict:
        ev = ledger.append("evidence", {"agent": agent_id, "target": target_id,
                                        "kind": kind, "detail": detail})
        evidence_hashes.append(ev["hash"])
        return ev

    _guard("probe")
    recon = arena.probe(target_id)
    log_evidence("recon", recon.get("banner", ""))

    # Technique 1: weak creds
    _guard("try_creds")
    for user, pw in [("admin", "admin"), ("root", "toor"), ("user", "password")]:
        r = arena.try_creds(target_id, user, pw)
        log_evidence("try_creds", f"{user}:{pw} -> {r.get('evidence')}")
        if r.get("captured"):
            return _capture(ledger, agent_id, target_id, r["flag"], evidence_hashes)

    # Technique 2: traversal
    _guard("read_file")
    for path in ["../../flag.txt", "/flag.txt", "index.html"]:
        r = arena.read_file(target_id, path)
        log_evidence("read_file", f"{path} -> {r.get('evidence')}")
        if r.get("captured"):
            return _capture(ledger, agent_id, target_id, r["flag"], evidence_hashes)

    # Technique 3: sqli-sim
    _guard("exploit_sqli_sim")
    for payload in ["' OR '1'='1", "admin'--", "1; DROP TABLE users"]:
        r = arena.exploit_sqli_sim(target_id, payload)
        log_evidence("exploit_sqli_sim", f"{payload!r} -> {r.get('evidence')}")
        if r.get("captured"):
            return _capture(ledger, agent_id, target_id, r["flag"], evidence_hashes)

    ledger.append("run_result", {"agent": agent_id, "target": target_id,
                                 "verdict": "FAILED"})
    return {"target_id": target_id, "agent_id": agent_id, "verdict": "FAILED"}


def _capture(ledger: Ledger, agent_id: str, target_id: str, flag: str,
             evidence_hashes: list[str]) -> dict:
    _guard("submit_flag")
    verdict = arena.submit_flag(target_id, flag)
    if not verdict.get("ok"):
        ledger.append("run_result", {"agent": agent_id, "target": target_id,
                                     "verdict": "REJECTED"})
        return {"target_id": target_id, "agent_id": agent_id,
                "verdict": "REJECTED"}
    receipt = settle_capture(target_id, agent_id, verdict["flag_sha256"],
                             list(evidence_hashes), ledger.cursor + 1)
    ledger.append("capture", receipt)
    # Prize store
    try:
        from agentcom.vault.store import Vault
        import os
        v = Vault(os.path.expanduser("~/.qpbot/vault.json"))
        v.capture(target_id=target_id, agent_id=agent_id,
                  flag_sha256=verdict["flag_sha256"],
                  receipt_id=receipt["id"],
                  tools_used=["probe", "try_creds", "read_file",
                              "exploit_sqli_sim", "submit_flag"])
    except Exception:
        pass  # prize store is best-effort, never breaks the loop
    return {"target_id": target_id, "agent_id": agent_id,
            "verdict": "CAPTURED", "receipt": receipt}


def verify_receipt(receipt: dict, ledger: Ledger) -> bool:
    """Re-check a capture receipt against arena truth + ledger."""
    if receipt.get("verdict") != "CAPTURED":
        return False
    if receipt.get("flag_sha256") != arena.flag_sha256(receipt["target_id"]):
        return False
    if not ledger.verify_chain():
        return False
    known = {e["hash"] for e in ledger.read_all()}
    for h in receipt.get("evidence_hashes", []):
        if h not in known:
            return False
    expected_id = obj_hash({k: v for k, v in receipt.items() if k != "id"})
    return receipt.get("id") == expected_id
