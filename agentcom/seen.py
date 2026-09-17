"""SeenTracker — track which wallets have been investigated, avoid duplicates.

Every investigation logs its address. Before starting a new run,
check if this address was already investigated. Skip if seen,
unless forced or enough time has passed for a re-check.
"""
from __future__ import annotations

import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEN_FILE = os.path.join(ROOT, "runs", "seen_wallets.jsonl")


class SeenTracker:
    """Append-only log of investigated wallet addresses."""

    def __init__(self, path: str = SEEN_FILE):
        self.path = path
        self._seen: dict[str, dict] = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    addr = entry.get("address", "")
                    if addr:
                        self._seen[addr.lower()] = entry
                except ValueError:
                    pass

    def is_seen(self, address: str, max_age_s: int = 86400) -> bool:
        """Check if address was investigated recently.

        Args:
            address: wallet address to check
            max_age_s: skip if seen within this many seconds (default 24h)
        """
        entry = self._seen.get(address.lower())
        if not entry:
            return False
        last_ts = entry.get("ts", 0)
        return (time.time() - last_ts) < max_age_s

    def mark(self, address: str, *, workflow: str = "", run_id: str = "",
             signals_found: int = 0, prize_stored: bool = False,
             github_found: bool = False, chain: str = ""):
        """Record that this address was investigated."""
        entry = {
            "ts": int(time.time()),
            "address": address.lower(),
            "workflow": workflow,
            "run_id": run_id,
            "signals_found": signals_found,
            "prize_stored": prize_stored,
            "github_found": github_found,
            "chain": chain,
        }
        self._seen[address.lower()] = entry
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def count(self) -> int:
        return len(self._seen)

    def list_seen(self, chain: str = "") -> list[dict]:
        """List all seen addresses, optionally filtered by chain."""
        results = list(self._seen.values())
        if chain:
            results = [r for r in results if r.get("chain") == chain]
        return sorted(results, key=lambda x: x.get("ts", 0), reverse=True)

    def stats(self) -> dict:
        """Summary stats of seen wallets."""
        by_chain = {}
        prizes = 0
        githubs = 0
        for entry in self._seen.values():
            chain = entry.get("chain", "unknown")
            by_chain[chain] = by_chain.get(chain, 0) + 1
            if entry.get("prize_stored"):
                prizes += 1
            if entry.get("github_found"):
                githubs += 1
        return {
            "total": len(self._seen),
            "by_chain": by_chain,
            "with_prize": prizes,
            "with_github": githubs,
        }
