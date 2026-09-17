"""Spend ledger — real usage totals behind the status feed.

Every lane run records evidence events + wall time; the bridge reads totals
for per-tile burn display. Integer minor units for money, matching the
QuotaLedger convention. No wallet keys live here.
"""
from __future__ import annotations

import time


class SpendLedger:
    def __init__(self):
        self.entries: list[dict] = []

    def record(self, campaign: str, lane: str, evidence_events: int,
               wall_ms: int, usd_minor: int = 0) -> dict:
        e = {"campaign": campaign, "lane": lane,
             "evidence_events": evidence_events, "wall_ms": wall_ms,
             "usd_minor": usd_minor, "ts": int(time.time())}
        self.entries.append(e)
        return e

    def totals(self, campaign: str = "") -> dict:
        rows = [e for e in self.entries
                if not campaign or e["campaign"] == campaign]
        return {"campaign": campaign or "all",
                "runs": len(rows),
                "evidence_events": sum(e["evidence_events"] for e in rows),
                "wall_ms": sum(e["wall_ms"] for e in rows),
                "usd_minor": sum(e["usd_minor"] for e in rows)}
