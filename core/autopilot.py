"""Autopilot — continuous autonomous campaign loop, local only, no network.

Runs campaign rounds until every target is captured or rounds exhaust.
Each round runs the tournament, banks the winner's receipts, enforces the
promotion gate and the global spend caps. Stdlib only.
"""
from __future__ import annotations

import os

from . import tournament
from .guards import MAX_ROUNDS, check_budget
from .ledger import Ledger


def run_autopilot(pack_id: str = "demo", agent_id: str = "red-01",
                  rounds: int = 5, runs_dir: str = "runs") -> dict:
    check_budget(rounds)
    if rounds < 1:
        raise ValueError("rounds must be >= 1")
    ledger = Ledger(os.path.join(runs_dir, pack_id, "autopilot",
                                 "events.jsonl"))
    ledger.append("autopilot_start", {"pack": pack_id, "agent": agent_id,
                                      "rounds": rounds})
    history = []
    for i in range(1, rounds + 1):
        t = tournament.run_tournament(pack_id, agent_id,
                                      runs_dir=os.path.join(
                                          runs_dir, f"round-{i}"))
        check_budget(rounds, sum(
            v["evidence_events"] for v in t["lanes"].values()))
        ledger.append("round", {"round": i, "winner": t["winner"],
                                "promotion": t["promotion"]})
        history.append(t)
        best = max(v["captured"] for v in t["lanes"].values())
        if best == len(t["lanes"][t["winner"]]) or best == 3:
            break
    ledger.append("autopilot_end", {"rounds_run": len(history),
                                    "final_winner": history[-1]["winner"]})
    return {"pack": pack_id, "rounds_run": len(history),
            "final_winner": history[-1]["winner"],
            "final_promotion": history[-1]["promotion"],
            "chain_ok": ledger.verify_chain(), "history": history}
