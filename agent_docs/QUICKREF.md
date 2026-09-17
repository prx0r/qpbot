# qpbot — Agent Quick Reference (blueteamer)

## What this is

qpbot is blueteamer's simulation environment for testing autonomous agents:
- CTF arena (3 targets, server-side verification)
- Vault (encrypted API keys, scoped grants)
- On-chain tools (whale feed, ETH/SOL balance, FOMO, GitHub search)
- LLM harness (mimo-v2.5 via OpenCode Go)
- Sub-agents (background workers with unique run IDs)
- Dashboard (web UI at localhost:8791)
- Audit logging (every mutation traced)
- RSI (recursive self-improvement via memory)
- QP proofs (every finding validated with receipts)

## Your role

You are a blueteamer agent. You test our systems. Everything you do is:
- Logged to runs/ (JSONL, timestamped)
- Validated with QP proofs (receipts)
- Audited (every mutation traced)

You never trust — you prove.

## Quick commands

```bash
# Arena
python3 -m core.cli list-targets
python3 -m core.cli probe weak-creds-01
python3 -m core.cli try-creds weak-creds-01 admin admin
python3 -m core.cli submit weak-creds-01 "XMCTF{weak_creds_demo_01}"

# Vault
python3 -m core.cli vault-find --kind llm-inference --tier paid
python3 -m core.cli vault-usage

# On-chain tools
python3 scripts/simulations/whale_feed.py 100000
python3 scripts/simulations/eth_check.py 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045
python3 scripts/simulations/fomo_leaderboard.py leaderboard

# Dashboard
python3 dashboard/server.py  # localhost:8791
```

## LLM calls

```python
from agentcom.vault.store import Vault
from harness import call_api

vault = Vault("/home/ubuntu/.qpbot/vault.json")
active = vault.find(kind="llm-inference", tier="paid")
key = vault.resolve(active[0]["name"], "dashboard-chat", "chat-session",
                    active[0]["capability"])

resp = call_api(key, [{"role": "user", "content": "Say HI"}])
text = resp["choices"][0]["message"]["content"]
```

## Sub-agents

```python
from agentcom.subagent import spawn, list_subagents, list_runs

# List available
list_subagents()

# Spawn (runs in background)
result = spawn("wallet_hunter", extra_context="find whale wallets")

# Check runs
list_runs()
```

## Audit logging

```python
from agentcom.audit import log_tool_exec, log_llm_call, recent

# Log tool execution
log_tool_exec("whale_feed", ["100000"], result={"ok": True})

# Log LLM call
log_llm_call("mimo-v2.5", tokens_in=100, tokens_out=50)

# Read recent events
events = recent(20)
```

## Monitoring

```python
from agentcom.monitor import register, heartbeat, complete, list_statuses

# Track sub-agent
register("sa-123", "wallet_hunter", pid=12345, output_file="/tmp/out.json")
heartbeat("sa-123")
complete("sa-123", ok=True, findings=3)

# Check statuses
list_statuses()
```

## File structure

```
qpbot/
├── core/               Arena, ledger, tournament, autopilot
├── agentcom/           Vault, subagents, missions, RSI, audit, monitor
├── dashboard/          Web UI (localhost:8791)
├── scanners/           On-chain tools (whale_feed, eth_check, etc.)
├── scripts/simulations/ Tool implementations
├── tests/              Unit tests
├── runs/               Logs, audit, subagent results
├── peer_review/        Code review notes
└── agent_docs/         This documentation
```

## Rules

1. Never commit secrets (vault file, API keys)
2. Code flows qpbot → pq (never reverse)
3. Tests must pass before claiming success
4. Every mutation goes through audit log
5. Sub-agents run in background — check status before assuming completion
