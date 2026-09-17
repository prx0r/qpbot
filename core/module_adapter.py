"""Module adapter — qdw-workbench Private Lab contract (plain dicts, no deps).

Mirrors lab/modules/__init__.py shapes: ModuleStatus / ModuleProgram.
"""
from __future__ import annotations

from . import arena


def status(pack_id: str = "demo", agent_id: str = "red-01",
           last_summary: dict | None = None) -> dict:
    targets = arena.list_targets(pack_id)
    if last_summary:
        captured = last_summary.get("captured", 0)
        total = last_summary.get("targets", len(targets))
        score = last_summary.get("score", 0.0)
    else:
        captured, total, score = 0, len(targets), 0.0
    state = "LIVE_COMPETE" if score >= 1.0 else "LOCAL_BASELINE" if score > 0 else "DISCOVERED"
    return {
        "module_id": "xmrecon",
        "module_name": "xmrecon redteam sim",
        "programs": [
            {
                "program_id": f"xmrecon/{pack_id}",
                "name": f"xmrecon {pack_id}",
                "state": state,
                "capability_demand": {
                    "security": 0.99,
                    "offensive-security": 0.95,
                    "recon": 0.80,
                },
                "our_performance": {
                    "score": score,
                    "rank": 0,
                    "delta": 0.0,
                    "runs": last_summary.get("targets", 0) if last_summary else 0,
                    "wins": captured,
                    "cost_usd": 0.0,
                    "revenue_usd": 0.0,
                },
                "possible_actions": ["train", "submit", "hold", "explore_new_worker"],
                "estimated_costs": {"submit": 0.0, "train": 0.0},
                "estimated_rewards": {"flags": float(total)},
                "metadata": {
                    "pack": pack_id,
                    "agent": agent_id,
                    "targets": [t["target_id"] for t in targets],
                    "upstream_bundles": 33,
                },
            }
        ],
        "total_cost_usd": 0.0,
        "total_revenue_usd": 0.0,
        "worker_versions": [agent_id],
        "metadata": {"controller": "qdw-workbench", "arena": "xmrecon"},
    }
