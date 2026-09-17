# Peer Review — qpbot codebase

## What's legit

### 1. Core primitives (solid)
- **Arena** (`core/arena.py`): Server-side flag verification, tool grant table. Simple, correct.
- **Ledger** (`core/ledger.py`): Append-only JSONL with hash chaining. Verified.
- **Vault** (`agentcom/vault/store.py`): Encrypted key storage, scoped grants, 7-check resolution. Solid.
- **Receipts** (`core/ledger.py:settle_capture`): Content-addressed, verifiable. Works.

### 2. RSI loop (legit pattern, weak implementation)
The RSI (Recursive Self-Improvement) pattern is:
1. Read memory bank → inject past insights
2. Run LLM loop with tools
3. Log every step via invlog
4. Analyze all investigation logs
5. Write fresh insights to memory bank
6. Next run reads insights → optimizes

**This is legit.** The pattern works. But:
- `rsi.py:analyze()` only reads JSONL logs — no actual learning
- `memory/bank.py` writes markdown files — not structured data
- No actual model weight updates (by design — training-free)
- The "learning" is just "log more, analyze trends"

### 3. Sub-agent system (functional but fragile)
- 5 sub-agents defined: wallet_hunter, repo_auditor, chain_scanner, maintenance, ctf_runner
- Each runs as a background Python process
- Results written to `runs/subagents/`

**Issues:**
- No process monitoring — if sub-agent crashes, nobody knows
- No retry logic
- No resource limits (CPU, memory)
- Sub-agent prompts are hardcoded — no dynamic adaptation

### 4. Mission control (good pattern)
- Dispatch → start → complete/fail lifecycle
- JSONL logging with events
- Findings tracking

**Missing:**
- No mission cancellation
- No mission priority
- No mission dependencies (DAG)
- No mission timeout

### 5. Workflows (interesting design)
- Declarative step definitions
- Arg mapping from previous outputs
- Validation criteria (QP-like)

**Issues:**
- Validation is string-based (`"data.total_usd > 0"`) — fragile
- No error recovery (one step fails = workflow fails)
- No parallel execution

---

## What's missing (core primitives)

### 1. Audit logging
**Current:** No audit trail for file writes, API calls, or state changes.

**Needed:**
```
runs/audit.jsonl — every mutation logged with timestamp, actor, action, result
```

### 2. Sub-agent lifecycle management
**Current:** Fire-and-forget. No monitoring.

**Needed:**
- Process status tracking (running/completed/crashed)
- Timeout enforcement
- Resource limits
- Retry with backoff

### 3. Rate limiting
**Current:** No rate limiting on any API endpoint.

**Needed:**
- Per-token rate limit on chat
- Per-IP rate limit on all endpoints
- Global rate limit on LLM calls

### 4. Error recovery
**Current:** One failure = mission/workflow fails.

**Needed:**
- Retry with exponential backoff
- Circuit breaker on repeated failures
- Graceful degradation

### 5. State persistence
**Current:** STATE in memory (HISTORY list), lost on restart.

**Needed:**
- Persist chat history to disk
- Resume sessions after restart
- Session checkpointing

### 6. Concurrency control
**Current:** Threading without locks.

**Needed:**
- Lock on shared state (HISTORY, missions)
- File locking for JSONL writes
- Queue for LLM calls (avoid rate limits)

---

## Specific code issues

### dashboard/server.py

| Line | Issue | Severity |
|------|-------|----------|
| 198 | `timeout=30` too short for mimo-v2.5 | Low |
| 551 | Path traversal check uses `startswith` not `realpath` | Medium |
| 563 | Same path issue on write | Medium |
| 208-209 | HISTORY grows unbounded | Low |
| 237 | Only 3 tool calls processed | Low |
| 408 | No message length validation | Low |

### agentcom/worker.py

| Line | Issue | Severity |
|------|-------|----------|
| 141 | `max_tokens: 512` too low for mimo-v2.5 | Low |
| 247 | `'turn' in dir()` is fragile | Medium |
| 163 | `text = resp["choices"][0]["message"]["content"] or ""` — crashes on None | High |
| 232-241 | RSI analysis wrapped in try/except with bare `pass` | Medium |

### agentcom/subagent.py

| Line | Issue | Severity |
|------|-------|----------|
| 211-216 | `start_new_session=True` — process detaches completely | Low |
| 170-205 | Worker script built as string — no syntax validation | Medium |
| 262 | `list_runs` reads all files on every call | Low |

### agentcom/rsi.py

| Line | Issue | Severity |
|------|-------|----------|
| 186 | `import sys` inside function — should be top-level | Low |
| 22-137 | `analyze()` reads entire JSONL into memory | Medium |
| 112-120 | Suggestions are hardcoded heuristics | Low |

---

## What to build (priority order)

### P0: Audit logging
```python
# Every mutation goes here
runs/audit.jsonl — {ts, actor, action, target, result, run_id}
```

### P1: Sub-agent monitoring
```python
# Track process status
runs/subagents/status.json — {run_id: {pid, status, started, last_heartbeat}}
```

### P2: Rate limiting
```python
# Simple token bucket per IP
rate_limit = {"window_s": 60, "max_requests": 30}
```

### P3: Error recovery
```python
# Retry decorator
@retry(max_attempts=3, backoff=2.0)
def call_llm(messages): ...
```

### P4: State persistence
```python
# Save/restore HISTORY
def save_history(): json.dump(HISTORY, open("runs/history.json", "w"))
def load_history(): HISTORY = json.load(open("runs/history.json"))
```

---

## Verdict

**The system is functional but fragile.** The core primitives work. The RSI pattern is legit. But it needs:

1. Audit logging (traceability)
2. Sub-agent monitoring (reliability)
3. Rate limiting (protection)
4. Error recovery (resilience)
5. State persistence (durability)

None of these are architecture changes. They're plumbing additions to make the existing system production-ready.
