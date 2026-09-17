"""Sub-agent spawner — cheap algorithmic workers in background.

Main agent talks to user. Sub-agents run as nohup background processes
with hardcoded system prompts. Results write to runs/subagents/.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_DIR = os.path.join(ROOT, "runs", "subagents")


@dataclass
class SubAgentConfig:
    name: str
    description: str
    model: str  # cheap model for sub-agents
    system_prompt: str
    tools: list[str] = field(default_factory=list)
    max_turns: int = 10
    budget_tokens: int = 5000
    timeout_s: int = 300
    output_file: str = ""  # auto-generated if empty


# ── Sub-agent configs ────────────────────────────────────────

SUBAGENTS: dict[str, SubAgentConfig] = {}


def register(sa: SubAgentConfig):
    SUBAGENTS[sa.name] = sa
    return sa


register(SubAgentConfig(
    name="wallet_hunter",
    description="Find funded wallets via whale feed, check balances, investigate identity",
    model="mimo-v2.5",
    system_prompt="""You are a wallet hunting sub-agent. Your job is algorithmic:
1. Call whale_feed to get recent large transactions
2. For each interesting wallet, call eth_check or sol_check
3. If wallet has balance > $1000, call wallet_investigate for OSINT
4. For any findings, call classify on extracted secrets
5. Write a summary of all findings

Be methodical. Check every wallet. Report balances and identities found.
Format your final output as a structured report.""",
    tools=["whale_feed", "eth_check", "sol_check", "wallet_investigate",
           "wallet_identity", "classify", "drain_classify"],
    max_turns=15,
    budget_tokens=8000,
))

register(SubAgentConfig(
    name="repo_auditor",
    description="Clone a repo and scan for secrets, keys, and credentials",
    model="mimo-v2.5",
    system_prompt="""You are a repository security auditor. Your job is algorithmic:
1. Call clone_scan on the target repository
2. If secrets found, classify each one with classify
3. For any wallet addresses found, check balances with eth_check/sol_check
4. Check git_history for additional secrets
5. Write a full audit report

Be thorough. Check every file. Report all findings with severity.""",
    tools=["clone_scan", "env_scan", "git_history", "classify",
           "drain_classify", "eth_check", "sol_check"],
    max_turns=10,
    budget_tokens=5000,
))

register(SubAgentConfig(
    name="chain_scanner",
    description="Scan on-chain for opportunities across multiple wallets",
    model="mimo-v2.5",
    system_prompt="""You are an on-chain scanner sub-agent. Your job is algorithmic:
1. Call whale_feed to find large recent transactions
2. For each wallet in the top 10 transactions, call eth_check
3. Sort by balance, focus on wallets with > $10,000
4. For top 3 wallets, call wallet_github to search for leaked keys
5. Call fomo_leaderboard leaderboard to find top traders
6. Cross-reference: check if any leaderboard traders appear in whale transactions
7. Write a market intelligence report

Be systematic. Cover all chains. Report USD values.""",
    tools=["whale_feed", "eth_check", "sol_check", "wallet_github",
           "fomo_leaderboard", "wallet_investigate", "classify"],
    max_turns=20,
    budget_tokens=10000,
))

register(SubAgentConfig(
    name="maintenance",
    description="Run maintenance: check vault health, usage stats, system status",
    model="mimo-v2.5",
    system_prompt="""You are a maintenance sub-agent. Your job is to check system health:
1. Check vault status: python3 -m core.cli vault-find --kind llm-inference
2. Check usage stats: python3 -m core.cli vault-usage
3. Check arena status: python3 -m core.cli list-targets
4. Check prize stats: python3 -m core.cli prize-stats
5. Run a quick smoke test of each scanner tool
6. Write a maintenance report with any issues found

Be thorough. Check everything. Report problems clearly.""",
    tools=[],
    max_turns=5,
    budget_tokens=2000,
))

register(SubAgentConfig(
    name="ctf_runner",
    description="Run the CTF arena autonomously: probe, attack, capture flags",
    model="mimo-v2.5",
    system_prompt="""You are a CTF runner sub-agent. Your job is to capture all 3 flags:
Targets:
- weak-creds-01: login portal, try default creds
- traversal-01: file server, try path traversal to /flag.txt
- sqli-sim-01: user lookup API, try SQL injection

For each target:
1. Call probe to understand the service
2. Attack with try-creds, read-file, or sqli
3. When you find XMCTF{...}, call submit immediately
4. Report captures

Be efficient. One target at a time. Submit flags immediately.""",
    tools=["probe", "try-creds", "read-file", "sqli", "submit"],
    max_turns=20,
    budget_tokens=5000,
))


# ── Spawner ──────────────────────────────────────────────────

def spawn(subagent_name: str, extra_context: str = "",
          wallet_address: str = "", repo_url: str = "") -> dict:
    """Spawn a sub-agent as a background process. Returns spawn info."""
    if subagent_name not in SUBAGENTS:
        return {"ok": False, "error": f"unknown sub-agent: {subagent_name}. "
                f"Available: {list(SUBAGENTS.keys())}"}

    cfg = SUBAGENTS[subagent_name]
    os.makedirs(RESULTS_DIR, exist_ok=True)
    run_id = f"sa-{int(time.time())}"
    output_file = os.path.join(RESULTS_DIR, f"{subagent_name}-{run_id}.json")
    stdout_file = os.path.join(RESULTS_DIR, f"{subagent_name}-{run_id}.log")

    # Build the worker command
    context = cfg.system_prompt
    if extra_context:
        context += f"\n\nAdditional context: {extra_context}"
    if wallet_address:
        context += f"\n\nTarget wallet: {wallet_address}"
    if repo_url:
        context += f"\n\nTarget repo: {repo_url}"

    # Write system prompt to temp file (avoid shell escaping)
    prompt_file = os.path.join(RESULTS_DIR, f"{run_id}-prompt.txt")
    with open(prompt_file, "w") as f:
        f.write(context)

    # Build Python worker script
    worker_script = f"""
import sys, json, os, time
sys.path.insert(0, {ROOT!r})
os.chdir({ROOT!r})

from agentcom.worker import run_worker
from agentcom.vault.store import Vault

# Read system prompt
with open({prompt_file!r}) as f:
    objective = f.read().strip()

# Run the worker
result = run_worker(
    objective,
    tools={cfg.tools!r},
    max_turns={cfg.max_turns},
    model="{cfg.model}",
    use_rsi=True,
    force=True,
)

# Write results
output = {{
    "subagent": "{subagent_name}",
    "run_id": "{run_id}",
    "objective": objective[:500],
    "result": result,
    "timestamp": int(time.time()),
    "model": "{cfg.model}",
}}
with open({output_file!r}, "w") as f:
    json.dump(output, f, indent=1)

print(json.dumps(output))
"""
    worker_file = os.path.join(RESULTS_DIR, f"{run_id}-worker.py")
    with open(worker_file, "w") as f:
        f.write(worker_script)

    # Launch as background process (nohup-style)
    proc = subprocess.Popen(
        [sys.executable, worker_file],
        stdout=open(stdout_file, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,  # detach from parent
    )

    return {
        "ok": True,
        "run_id": run_id,
        "subagent": subagent_name,
        "pid": proc.pid,
        "output_file": output_file,
        "stdout_file": stdout_file,
        "model": cfg.model,
        "description": cfg.description,
    }


def list_subagents() -> dict:
    """List available sub-agents."""
    return {
        name: {
            "description": cfg.description,
            "model": cfg.model,
            "tools": cfg.tools,
            "max_turns": cfg.max_turns,
        }
        for name, cfg in SUBAGENTS.items()
    }


def list_runs() -> list[dict]:
    """List completed sub-agent runs."""
    if not os.path.exists(RESULTS_DIR):
        return []
    runs = []
    for f in sorted(os.listdir(RESULTS_DIR)):
        if f.endswith(".json") and not f.endswith("-prompt.txt"):
            try:
                data = json.load(open(os.path.join(RESULTS_DIR, f)))
                runs.append({
                    "run_id": data.get("run_id"),
                    "subagent": data.get("subagent"),
                    "model": data.get("model"),
                    "ok": data.get("result", {}).get("ok"),
                    "findings": len(data.get("result", {}).get("findings", [])),
                    "tokens": data.get("result", {}).get("tokens_in", 0) + data.get("result", {}).get("tokens_out", 0),
                    "timestamp": data.get("timestamp"),
                })
            except Exception:
                pass
    return runs


def read_run(run_id: str) -> dict | None:
    """Read a specific run's results."""
    if not os.path.exists(RESULTS_DIR):
        return None
    for f in os.listdir(RESULTS_DIR):
        if f.endswith(".json") and run_id in f:
            try:
                return json.load(open(os.path.join(RESULTS_DIR, f)))
            except Exception:
                pass
    return None
