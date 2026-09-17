"""Seed0 lanes — frozen-root tournament over Pi-capable lane specs.

Wraps core.tournament strategy lanes today; Pi-backed lanes plug into the
same LaneSpec shape in Phase 3. One ContractRoot per tournament: lanes that
disagree on the root refuse to run together.
Provenance: /agentcomfinal/experiments/policies/lanes.py (doctrine).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


def contract_root(objective: str, proof_requirements: list[str],
                  budget: dict) -> str:
    body = json.dumps({"objective": objective,
                       "proof_requirements": proof_requirements,
                       "budget": budget}, sort_keys=True)
    return hashlib.sha256(body.encode()).hexdigest()


@dataclass
class LaneSpec:
    name: str
    model: str = ""
    strategy: str = ""
    backend: str = "core"  # core | pi
    contract_root: str = ""

    def validate(self, root: str):
        if self.contract_root != root:
            raise ValueError(f"lane {self.name} root mismatch")


def run_seed0(objective: str, proof_requirements: list[str], budget: dict,
              lanes: list[LaneSpec], pack_id: str = "demo",
              runs_dir: str = "runs") -> dict:
    from core import tournament as _t
    root = contract_root(objective, proof_requirements, budget)
    for lane in lanes:
        lane.validate(root)
    core_lanes = [l for l in lanes if l.backend == "core"]
    if len(core_lanes) != len(lanes):
        missing = [l.name for l in lanes if l.backend != "core"]
        return {"contract_root": root, "status": "AWAITING_PI_BACKEND",
                "pending_lanes": missing}
    t = _t.run_tournament(pack_id, runs_dir=runs_dir)
    return {"contract_root": root, "status": "COMPLETE",
            "winner": t["winner"], "ranked": t["ranked"],
            "promotion": t["promotion"], "lanes": t["lanes"]}
