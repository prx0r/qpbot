"""Tournament — competing redteam lanes vs one pack, deterministic.

Lanes are strategy orders, not separate agents. Each lane runs the full pack
against a private ledger. Winner ranks by captures, then evidence efficiency.
Promotion requires the frozen gate (see guards.py), never self-certifies.
"""
from __future__ import annotations

import os
import tempfile

from . import agents, arena
from .guards import assess_promotion
from .ledger import Ledger

LANES = {
    "creds-first": ["creds", "traversal", "sqli"],
    "traversal-first": ["traversal", "creds", "sqli"],
    "sqli-first": ["sqli", "creds", "traversal"],
}

_TECHNIQUE_RUNNERS = {
    "creds": lambda tid: [
        arena.try_creds(tid, u, p)
        for u, p in [("admin", "admin"), ("root", "toor"), ("user", "password")]
    ],
    "traversal": lambda tid: [
        arena.read_file(tid, p)
        for p in ["../../flag.txt", "/flag.txt", "index.html"]
    ],
    "sqli": lambda tid: [
        arena.exploit_sqli_sim(tid, p)
        for p in ["' OR '1'='1", "admin'--", "1; DROP TABLE users"]
    ],
}


def run_lane(ledger: Ledger, agent_id: str, target_id: str,
             order: list[str]) -> dict:
    from .agents import _capture, _guard
    evidence_hashes: list[str] = []

    def log(kind: str, detail: str):
        ev = ledger.append("evidence", {"agent": agent_id, "target": target_id,
                                        "kind": kind, "detail": detail})
        evidence_hashes.append(ev["hash"])

    _guard("probe")
    log("recon", arena.probe(target_id).get("banner", ""))
    for tech in order:
        _guard({"creds": "try_creds", "traversal": "read_file",
                "sqli": "exploit_sqli_sim"}[tech])
        for r in _TECHNIQUE_RUNNERS[tech](target_id):
            log(tech, str(r.get("evidence")))
            if r.get("captured"):
                return _capture(ledger, agent_id, target_id, r["flag"],
                                evidence_hashes)
    ledger.append("run_result", {"agent": agent_id, "target": target_id,
                                 "verdict": "FAILED"})
    return {"target_id": target_id, "agent_id": agent_id, "verdict": "FAILED"}


def run_tournament(pack_id: str = "demo", agent_id: str = "red-01",
                   runs_dir: str = "runs") -> dict:
    targets = [t["target_id"] for t in arena.list_targets(pack_id)]
    lanes = {}
    for lane, order in LANES.items():
        path = os.path.join(runs_dir, pack_id, f"tournament-{lane}",
                            "events.jsonl")
        ledger = Ledger(path)
        results = [run_lane(ledger, f"{agent_id}-{lane}", t, order)
                   for t in targets]
        captured = sum(1 for r in results if r.get("verdict") == "CAPTURED")
        lanes[lane] = {
            "captured": captured,
            "targets": len(targets),
            "score": captured / len(targets) if targets else 0,
            "evidence_events": sum(1 for e in ledger.read_all()
                                   if e["type"] == "evidence"),
            "chain_ok": ledger.verify_chain(),
            "ledger": path,
        }
    ranked = sorted(lanes, key=lambda l: (-lanes[l]["captured"],
                                          lanes[l]["evidence_events"]))
    winner = ranked[0] if ranked else None
    promotion = assess_promotion(
        uses=3, passes=lanes[winner]["captured"] if winner else 0,
        total=lanes[winner]["targets"] if winner else 0, regressions=0)
    return {"pack": pack_id, "lanes": lanes, "ranked": ranked,
            "winner": winner, "promotion": promotion}
