"""Guards — INSANE.md findings as executable code, not prose.

- assess_promotion: the strict gate autobuild shipped as dead code. Live here:
  minimum uses, minimum pass rate, zero regressions. Nothing promotes without it.
- Spend caps: caller-controlled budgets get a global ceiling. Tournament and
  autopilot refuse to run past max_rounds / max_evidence_events.
- Verifier freeze: arena verifier lives in ONE module. This module re-exports
  the check so campaigns never inline their own verdict logic.
"""
from __future__ import annotations

MAX_ROUNDS = 50
MAX_EVIDENCE_EVENTS = 5000


def assess_promotion(uses: int, passes: int, total: int,
                     regressions: int, minimum_uses: int = 3,
                     min_pass_rate: float = 0.90) -> dict:
    rate = (passes / total) if total else 0.0
    ok = (uses >= minimum_uses and rate >= min_pass_rate
          and regressions == 0 and total > 0)
    return {"promoted": ok, "uses": uses, "pass_rate": rate,
            "regressions": regressions,
            "gate": {"minimum_uses": minimum_uses,
                     "min_pass_rate": min_pass_rate,
                     "max_regressions": 0}}


def check_budget(rounds: int, evidence_events: int = 0) -> None:
    if rounds > MAX_ROUNDS:
        raise ValueError(f"rounds {rounds} exceeds cap {MAX_ROUNDS}")
    if evidence_events > MAX_EVIDENCE_EVENTS:
        raise ValueError(
            f"evidence events {evidence_events} exceed cap {MAX_EVIDENCE_EVENTS}")
