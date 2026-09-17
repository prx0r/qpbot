# qpbot — Architecture

## System overview

```
                    ┌─────────────────┐
                    │   Dashboard     │
                    │   (Web UI)      │
                    │   :8791         │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   Main Agent    │
                    │   (mimo-v2.5)   │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
     ┌──────▼──────┐  ┌─────▼─────┐  ┌──────▼──────┐
     │  Sub-Agents │  │  Missions │  │  Workflows  │
     │  (background)│  │  (queue)  │  │  (step-by-  │
     └──────┬──────┘  └─────┬─────┘  │   step)     │
            │                │        └──────┬──────┘
            │                │               │
     ┌──────▼────────────────▼───────────────▼──────┐
     │              Tool Registry                    │
     │  arena | whale_feed | eth_check | fomo | ... │
     └──────────────────────┬───────────────────────┘
                            │
                 ┌──────────▼──────────┐
                 │   Vault (encrypted) │
                 │   5 LLM keys        │
                 └─────────────────────┘
```

## Data flow

1. User sends message via dashboard
2. Main agent (mimo-v2.5) processes message
3. Agent decides: respond directly, spawn sub-agent, or run tool
4. Tools execute via registry (arena, on-chain, scanners)
5. Results logged to `runs/` (audit, usage, missions)
6. Sub-agents run in background, results appear in `runs/subagents/`

## Key modules

| Module | Role | File |
|--------|------|------|
| Arena | CTF targets, flag verification | core/arena.py |
| Ledger | Append-only hash chain | core/ledger.py |
| Vault | Encrypted key storage | agentcom/vault/store.py |
| Worker | LLM + tools + RSI loop | agentcom/worker.py |
| SubAgent | Background workers | agentcom/subagent.py |
| Monitor | Process tracking | agentcom/monitor.py |
| Audit | Mutation tracing | agentcom/audit.py |
| Missions | Task queue | agentcom/missions.py |
| Workflows | Step-by-step pipelines | agentcom/workflows.py |
| RSI | Recursive self-improvement | agentcom/rsi.py |
| Memory | Cross-run experience | agentcom/memory/bank.py |
| Dashboard | Web UI | dashboard/server.py |

## RSI loop

```
Read memory bank → inject insights into prompt
        ↓
Run LLM loop with tools
        ↓
Log every step (invlog)
        ↓
Analyze all investigation logs (rsi.py)
        ↓
Write fresh insights to memory bank
        ↓
Next run reads insights → optimizes behavior
```

## State files

```
~/.qpbot/vault.json          # Encrypted API keys
runs/audit.jsonl             # Every mutation
runs/usage.jsonl             # LLM API usage
runs/missions.jsonl          # Mission lifecycle
runs/subagents/              # Sub-agent results + status
runs/htasks.json             # Human task queue
runs/provider.json           # LLM provider config
runs/system_prompt.txt       # Agent system prompt
memory/                      # Cross-run experience bank
```
