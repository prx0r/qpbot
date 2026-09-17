"""ACP server surface — Argos → AgentCom routing table (scaffold).

Transport is pi-acp / ACP JSON-RPC; this module owns AgentCom-side routing:
RAW mode passes straight to a Pi session, AGENTCOM mode compiles work into
ATasks for Pi lanes. No transport code until the daemon runs headless.
"""
from __future__ import annotations

MODES = ("raw", "agentcom")


def route(mode: str, payload: dict) -> dict:
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode}")
    if mode == "raw":
        return {"route": "pi-direct", "session": payload.get("session", ""),
                "note": "no QP, no portfolio, minimal harness"}
    return {"route": "agentcom-pipeline",
            "stages": ["compile", "dispatch", "evidence", "qp-settle",
                       "htask-or-commit"]}
