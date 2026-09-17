# qpbot — Sub-Agent Guide

## What are sub-agents

Background workers that run autonomous tasks. The main agent (dashboard chat) stays responsive while sub-agents do long-running work.

## Available sub-agents

| Name | Description | Tools |
|------|-------------|-------|
| wallet_hunter | Find funded wallets, check balances, investigate identity | whale_feed, eth_check, sol_check, wallet_investigate, classify |
| repo_auditor | Clone repos, scan for secrets, audit security | clone_scan, env_scan, git_history, classify |
| chain_scanner | Scan whale feed, check top wallets, find opportunities | whale_feed, eth_check, sol_check, wallet_github, fomo_leaderboard |
| ctf_runner | Run CTF arena autonomously, capture flags | probe, try-creds, read-file, sqli, submit |
| maintenance | Check vault health, usage stats, system status | (CLI commands) |

## Spawning sub-agents

```python
from agentcom.subagent import spawn

# Spawn with context
result = spawn("wallet_hunter", extra_context="find wallets with > $10k")
print(result)  # {"ok": True, "run_id": "sa-123", "pid": 12345}

# Spawn with wallet address
result = spawn("wallet_hunter", wallet_address="0xd8dA...")

# Spawn with repo URL
result = spawn("repo_auditor", repo_url="https://github.com/user/repo")
```

## Monitoring sub-agents

```python
from agentcom.monitor import list_statuses, check_timeouts, check_crashes

# List all statuses
statuses = list_statuses()
for s in statuses:
    print(f"{s['run_id']}: {s['status']} ({s['subagent']})")

# Check for problems
timeouts = check_timeouts(timeout_s=600)
crashes = check_crashes()
```

## How sub-agents work

1. Main agent calls `spawn("wallet_hunter", extra_context="...")`
2. Spawn creates a Python worker script in `runs/subagents/`
3. Worker runs as background process (detached from parent)
4. Worker calls LLM (mimo-v2.5) with tools
5. LLM calls tools (whale_feed, eth_check, etc.)
6. Results written to `runs/subagents/<name>-<run_id>.json`
7. Status tracked in `runs/subagents/<run_id>.status.json`

## Sub-agent system prompts

Each sub-agent has a hardcoded system prompt that tells it:
1. What tools to use
2. What order to use them
3. What to report

Example (wallet_hunter):
```
1. Call whale_feed to get recent large transactions
2. For each interesting wallet, call eth_check or sol_check
3. If wallet has balance > $1000, call wallet_investigate for OSINT
4. For any findings, call classify on extracted secrets
5. Write a summary of all findings
```

## Dashboard API

```bash
# List sub-agents
curl "http://localhost:8791/api/subagents?token=TOKEN"

# List runs
curl "http://localhost:8791/api/subagent/runs?token=TOKEN"

# Spawn via API
curl -X POST "http://localhost:8791/api/subagent/spawn?token=TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"subagent": "wallet_hunter", "context": "find whale wallets"}'

# Auto-detect and spawn
curl -X POST "http://localhost:8791/api/subagent/run?token=TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "investigate wallet 0xd8dA..."}'
```
