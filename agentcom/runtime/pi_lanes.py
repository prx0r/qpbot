"""Pi lane runtime — ATask spec → Pi subprocess command builder.

One ACP/pi session per lane (one writer rule). Live dispatch shells pi-acp;
without a pi binary + key this module only builds and validates specs.
Provenance: pi-acp README session mapping; Pi SDK tool/mode options.
"""
from __future__ import annotations

PI_ACP = "/home/ubuntu/pi-acp/dist/index.js"


def lane_spec(objective: str, pack: str = "demo", model: str = "",
              strategy: str = "", budget: dict | None = None,
              contract_root: str = "") -> dict:
    if not objective:
        raise ValueError("objective required")
    return {"objective": objective, "pack": pack, "model": model,
            "strategy": strategy, "budget": budget or {},
            "contract_root": contract_root,
            "mode": "redteam", "session": ""}


def dispatch_argv(spec: dict, session_id: str) -> list[str]:
    """Command that would run this lane. Pure builder — no execution."""
    if not spec.get("model"):
        raise ValueError("lane has no model; refusing silent fallback")
    return ["node", PI_ACP, "--session", session_id,
            "--mode", spec.get("mode", "redteam")]
