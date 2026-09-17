# qpbot — blueteamer simulations & experiments

**By blueteamer. For testing our own systems.**

qpbot is a simulation environment where we run autonomous agents against
our own CTF arena, on-chain tools, and control plane. Every experiment
is logged. Every receipt is verifiable. Nothing is trusted — everything
is proven.

## What we're testing

1. **Can our agents find what they're supposed to find?** — Arena with 3 targets, server-side verification, hash-chained receipts.

2. **Can our agents use on-chain tools correctly?** — Whale feed, ETH/SOL balance, FOMO leaderboard, GitHub search, wallet investigation.

3. **Can our agents manage themselves?** — Sub-agents with unique run IDs, real-time logs, timeout monitoring, audit trails.

4. **Can we verify everything with QP proofs?** — Every finding validated through gates. Every receipt content-addressed. Every claim either PASS or FAIL.

## The experiment

```bash
# Run all simulations
python3 -m pytest tests/ -q

# Spawn an agent and watch it work
python3 frameworks/wallet_sleuth.py 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045

# Check what the agent found
cat runs/wallet-sleuth.jsonl
```

## What we proved

| Experiment | Result | Receipt |
|------------|--------|---------|
| Vitalik wallet → GitHub identity | ENS: vitalik.eth, GitHub: vitalik | receipt:3ce241954ab25623 |
| Binance hot wallet → balance check | $1.48B verified | receipt:801280d5085e6f7f |
| Sub-agent spawn → complete → QP proof | 7 findings, receipt verified | receipt:1e0ff00504ce7969 |

## How it works

```
Blueteamer defines task
    ↓
Agent spawns sub-agents (unique run IDs)
    ↓
Sub-agents execute tools (whale_feed, eth_check, etc.)
    ↓
Results logged to runs/ (JSONL, timestamped)
    ↓
QP proof validates: claim + evidence + gates → receipt
    ↓
Receipt verified by anyone, anywhere
```

## Layout

- `core/` — Arena, ledger, tournament, autopilot (simulated CTF)
- `agentcom/` — Vault, sub-agents, missions, RSI, audit, monitor
- `frameworks/` — Test scripts, wallet sleuthing pipeline
- `dashboard/` — Web UI (localhost:8791)
- `scanners/` — On-chain tools (whale_feed, eth_check, etc.)
- `tests/` — Unit tests
- `runs/` — Experiment logs (gitignored)

## Rules

1. Everything is logged. No silent failures.
2. Every finding gets a QP receipt. No unverified claims.
3. Sub-agents run in background. Main agent stays responsive.
4. Keys stay in vault. Never in code or logs.
5. We test our own systems. Nothing is trusted — everything is proven.
