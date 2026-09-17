"""Tool registry — every script is a tool with structured I/O.

The LLM picks tools, fires them, gets JSON back. No free-form shell.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIM_DIR = os.path.join(ROOT, "scripts", "simulations")
SCANNER_DIR = os.path.join(ROOT, "scanners")


@dataclass
class Tool:
    name: str
    description: str
    script: str
    args_min: int = 0
    args_max: int = 5
    timeout_s: float = 60
    needs_net: bool = False
    output_schema: str = "json"

    def run(self, args: list[str]) -> dict:
        # Check both scanners/ and scripts/simulations/ directories
        script_path = os.path.join(SCANNER_DIR, self.script)
        if not os.path.exists(script_path):
            script_path = os.path.join(SIM_DIR, self.script)
        cmd = [sys.executable, script_path] + args
        try:
            p = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=self.timeout_s, cwd=ROOT)
            raw = p.stdout.strip() or p.stderr.strip()
            try:
                return {"ok": True, "data": json.loads(raw), "tool": self.name}
            except json.JSONDecodeError:
                return {"ok": True, "data": {"raw": raw}, "tool": self.name}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout", "tool": self.name}
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}",
                    "tool": self.name}


TOOLS: dict[str, Tool] = {}


def register(tool: Tool):
    TOOLS[tool.name] = tool
    return tool


# ── Recon tools ──────────────────────────────────────────────

register(Tool(
    name="gh_search",
    description="Search GitHub for leaked keys. Needs GH_TOKEN.",
    script="gh_secret_scanner.py",
    args_min=0, args_max=0,
    needs_net=True,
))

register(Tool(
    name="env_scan",
    description="Scan a directory for secrets in .env files.",
    script="env_extract.py",
    args_min=1, args_max=1,
))

register(Tool(
    name="git_history",
    description="Find secrets in git commit history.",
    script="git_history_scan.py",
    args_min=1, args_max=1,
))

# ── Classification tools ─────────────────────────────────────

register(Tool(
    name="classify",
    description="Detect secret type + drain authority class.",
    script="classify_secret.py",
    args_min=1, args_max=1,
))

register(Tool(
    name="drain_classify",
    description="Advanced: drain authority class + actions + priority.",
    script="drain_classify.py",
    args_min=1, args_max=2,
))

# ── Balance check tools ──────────────────────────────────────

register(Tool(
    name="eth_check",
    description="Check ETH + ERC-20 balance. Free, no key.",
    script="eth_check.py",
    args_min=1, args_max=2,
    needs_net=True,
))

register(Tool(
    name="sol_check",
    description="Check SOL + SPL balance. Free, no key.",
    script="sol_check.py",
    args_min=1, args_max=1,
    needs_net=True,
))

register(Tool(
    name="batch_check",
    description="Check many addresses in parallel.",
    script="batch_check.py",
    args_min=1, args_max=1,
    needs_net=True,
))

# ── Derivation tools ─────────────────────────────────────────

register(Tool(
    name="mnemonic_derive",
    description="BIP-39 mnemonic → seed + derivation paths.",
    script="mnemonic_derive.py",
    args_min=1, args_max=24,
))

# ── On-chain discovery tools ────────────────────────────────

register(Tool(
    name="whale_feed",
    description="Large crypto transactions across BTC/ETH. No key.",
    script="whale_feed.py",
    args_min=0, args_max=1,
    needs_net=True,
))

register(Tool(
    name="fomo_leaderboard",
    description="Top traders from fomo.family. leaderboard or lookup <handle>.",
    script="fomo_leaderboard.py",
    args_min=1, args_max=2,
    needs_net=True,
))

register(Tool(
    name="wallet_github",
    description="Search GitHub for repos containing a wallet address.",
    script="wallet_github_search.py",
    args_min=2, args_max=2,
    needs_net=True,
))

register(Tool(
    name="clone_scan",
    description="Clone a git repo and scan for secrets (history + env).",
    script="clone_and_scan.py",
    args_min=1, args_max=1,
    needs_net=True,
))

# ── Identity resolution tools ───────────────────────────────

register(Tool(
    name="wallet_identity",
    description="Resolve wallet address to GitHub/social identity (ENS, FOMO, commits).",
    script="wallet_identity.py",
    args_min=1, args_max=1,
    needs_net=True,
))

register(Tool(
    name="wallet_investigate",
    description="Full OSINT chain: wallet → ENS → Farcaster → Lens → FOMO → GitHub → social.",
    script="wallet_investigate.py",
    args_min=1, args_max=1,
    needs_net=True,
))


def tool_names() -> list[str]:
    return sorted(TOOLS.keys())


def tool_specs() -> list[dict]:
    return [{"name": t.name, "description": t.description,
             "args_min": t.args_min, "args_max": t.args_max,
             "needs_net": t.needs_net} for t in TOOLS.values()]


def fire(name: str, args: list[str]) -> dict:
    if name not in TOOLS:
        return {"ok": False, "error": f"unknown tool: {name}", "tool": name}
    tool = TOOLS[name]
    if len(args) < tool.args_min:
        return {"ok": False, "error": f"need >= {tool.args_min} args",
                "tool": name}
    return tool.run(args)
