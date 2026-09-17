"""Investigation Log — record every step of the OSINT chain.

Every investigation run logs: which tools were called, what signals
were found, which handles resolved to GitHub accounts, what was
stored as a prize. The RSI analyzer reads these logs to find
patterns: which signals actually work, which tools are most
productive, what the LLM's decision path looked like.
"""
from __future__ import annotations

import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(ROOT, "runs", "investigations.jsonl")


class InvestigationLog:
    """Append-only log of investigation runs."""

    _counter = 0

    def __init__(self, path: str = LOG_PATH):
        self.path = path
        InvestigationLog._counter += 1

    def log_start(self, address: str, workflow: str = "") -> str:
        """Log investigation start. Returns run_id."""
        InvestigationLog._counter += 1
        run_id = f"inv-{int(time.time()*1000)}-{InvestigationLog._counter}"
        entry = {
            "ts": int(time.time()),
            "event": "start",
            "run_id": run_id,
            "address": address,
            "workflow": workflow,
        }
        self._append(entry)
        return run_id

    def log_step(self, run_id: str, tool: str, args: list[str],
                 output: dict, duration_ms: int = 0):
        """Log a tool execution step."""
        # Extract key signals from output
        signals = []
        handles = []
        if isinstance(output, dict):
            # For wallet_investigate output
            for s in output.get("signals", []):
                signals.append(str(s)[:200])
            for h in output.get("handles", []):
                if isinstance(h, dict):
                    handles.append(h.get("handle", ""))
                else:
                    handles.append(str(h))
            # For balance checks
            if "total_usd" in output:
                signals.append(f"balance=${output['total_usd']}")
            if "ETH" in output:
                signals.append(f"ETH={output['ETH']}")
            if "SOL" in output:
                signals.append(f"SOL={output['SOL']}")
            # For GitHub search
            if "github_repos" in output:
                signals.append(f"github_repos={len(output['github_repos'])}")
            if "results" in output and isinstance(output["results"], list):
                for r in output["results"][:3]:
                    repo = r.get("repo", "")
                    if repo:
                        signals.append(f"repo={repo}")

        entry = {
            "ts": int(time.time()),
            "event": "step",
            "run_id": run_id,
            "tool": tool,
            "args": args[:5],
            "duration_ms": duration_ms,
            "signals_found": len(signals),
            "signals": signals[:10],
            "handles": handles[:5],
        }
        self._append(entry)

    def log_prize(self, run_id: str, prize: dict):
        """Log a prize being stored."""
        entry = {
            "ts": int(time.time()),
            "event": "prize",
            "run_id": run_id,
            "chain": prize.get("chain", ""),
            "key_type": prize.get("key_type", ""),
            "drain_class": prize.get("drain_class", ""),
            "balance_usd": prize.get("balance_usd", 0),
            "has_github": bool(prize.get("github_repos")),
            "has_ens": bool(prize.get("ens_name")),
            "confidence": prize.get("confidence", ""),
        }
        self._append(entry)

    def log_end(self, run_id: str, status: str, total_steps: int,
                total_signals: int, prize_stored: bool):
        """Log investigation end."""
        entry = {
            "ts": int(time.time()),
            "event": "end",
            "run_id": run_id,
            "status": status,
            "total_steps": total_steps,
            "total_signals": total_signals,
            "prize_stored": prize_stored,
        }
        self._append(entry)

    def _append(self, entry: dict):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def iter_runs(self):
        """Iterate over completed investigation runs."""
        if not os.path.exists(self.path):
            return
        runs = {}
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                rid = entry.get("run_id", "")
                if not rid:
                    continue
                if rid not in runs:
                    runs[rid] = {"steps": [], "start": None, "end": None}
                if entry.get("event") == "start":
                    runs[rid]["start"] = entry
                elif entry.get("event") == "step":
                    runs[rid]["steps"].append(entry)
                elif entry.get("event") == "prize":
                    runs[rid]["prize"] = entry
                elif entry.get("event") == "end":
                    runs[rid]["end"] = entry
        for rid, run in sorted(runs.items(), key=lambda x: x[1].get("start", {}).get("ts", 0)):
            yield rid, run
