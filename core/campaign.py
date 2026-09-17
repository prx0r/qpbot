"""Campaign controller — queue -> allocate -> run -> outcome."""
from __future__ import annotations

import os

from . import agents, arena
from .ledger import Ledger


def run_campaign(pack_id: str = "demo", agent_id: str = "red-01",
                 runs_dir: str = "runs") -> dict:
    targets = arena.list_targets(pack_id)
    out_dir = os.path.join(runs_dir, pack_id)
    os.makedirs(out_dir, exist_ok=True)
    ledger = Ledger(os.path.join(out_dir, "events.jsonl"))
    ledger.append("campaign_start", {"pack": pack_id, "agent": agent_id,
                                     "targets": [t["target_id"] for t in targets]})
    results = []
    for t in targets:
        results.append(agents.run_target(ledger, agent_id, t["target_id"]))
    captured = sum(1 for r in results if r.get("verdict") == "CAPTURED")
    summary = {
        "pack": pack_id,
        "agent": agent_id,
        "targets": len(targets),
        "captured": captured,
        "score": captured / len(targets) if targets else 0.0,
        "chain_ok": ledger.verify_chain(),
        "ledger": ledger.path,
        "results": results,
    }
    ledger.append("campaign_end", {k: v for k, v in summary.items()
                                   if k != "results"})
    return summary
