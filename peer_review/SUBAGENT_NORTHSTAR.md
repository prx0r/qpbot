# Peer Review — Sub-Agent System (Northstar)

## Current state

The sub-agent system works but has critical gaps. Here's what's broken and what needs to be built.

---

## What works

1. **Spawn**: `spawn("wallet_hunter")` creates a background process ✓
2. **Monitor**: `register()`, `heartbeat()`, `complete()` track status ✓
3. **Audit**: `log_subagent_spawn()` logs to audit.jsonl ✓
4. **Results**: Output written to `runs/subagents/<name>-<run_id>.json` ✓

---

## What's broken

### 1. No real-time visibility
**Problem**: You can't see what a sub-agent is doing until it finishes.

**Current**: Log file is empty until process completes.

**Need**: Stream logs as they're written. `tail -f` on the log file.

```bash
# This should show real-time output
tail -f runs/subagents/wallet_hunter-sa-123.log
```

### 2. Sub-agents freeze on API errors
**Problem**: If LLM returns 403, sub-agent hangs forever.

**Current**: No retry, no timeout, no error handling in worker.

**Need**:
- Retry with backoff on API errors
- Kill process after timeout
- Log error and mark as failed

### 3. No unique run IDs
**Problem**: Run IDs are timestamp-based (`sa-{int(time.time())}`), not content-addressed.

**Current**: Two sub-agents spawned in the same second get same ID.

**Need**: Content-addressed run IDs:
```python
run_id = f"sa:{sha256(objective + model + timestamp)[:12]}"
```

### 4. No LLM-driven execution
**Problem**: Sub-agents run hardcoded system prompts. The main LLM can't control them.

**Current**: Each sub-agent has a fixed `system_prompt` in `SubAgentConfig`.

**Need**: Main LLM can send custom prompts:
```python
result = spawn("wallet_hunter", prompt="Focus on Bitcoin whales only")
```

### 5. Log population is broken
**Problem**: Logs are empty when sub-agent gets stuck.

**Current**: Worker writes to log file only on completion.

**Need**: Log every step as it happens:
```python
# In worker loop
with open(log_file, "a") as f:
    f.write(json.dumps({"turn": turn, "tool": tool, "result": result}) + "\n")
```

### 6. No status streaming
**Problem**: Dashboard can't show live sub-agent status.

**Current**: `/api/subagent/statuses` returns static snapshot.

**Need**: WebSocket or polling endpoint that updates in real-time.

---

## What needs to be built

### P0: Real-time log streaming

**File**: `agentcom/subagent.py`

Add log streaming:
```python
def stream_logs(run_id: str):
    """Yield log lines as they're written."""
    log_file = os.path.join(RESULTS_DIR, f"{run_id}.log")
    with open(log_file) as f:
        for line in f:
            yield line
```

**File**: `dashboard/server.py`

Add streaming endpoint:
```python
elif path == "/api/subagent/logs":
    run_id = parse_qs(urlparse(self.path).query).get("run_id", [""])[0]
    if not run_id:
        self._json({"error": "missing run_id"}, 400)
        return
    log_file = os.path.join(ROOT, "runs", "subagents", f"{run_id}.log")
    if not os.path.exists(log_file):
        self._json({"error": "log not found"}, 404)
        return
    self._json({"log": open(log_file).read()})
```

### P0: Sub-agent timeout + retry

**File**: `agentcom/worker.py`

Add retry and timeout:
```python
def call_llm_with_retry(messages, model, max_retries=3, timeout=60):
    for attempt in range(max_retries):
        try:
            # ... API call ...
            return resp
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(2 ** attempt)  # exponential backoff
                continue
            raise
    raise Exception(f"LLM failed after {max_retries} retries")
```

**File**: `agentcom/subagent.py`

Add process timeout:
```python
# In spawn()
proc = subprocess.Popen(...)
# Monitor in background
def monitor_process(proc, run_id, timeout_s=600):
    start = time.time()
    while proc.poll() is None:
        if time.time() - start > timeout_s:
            proc.kill()
            monitor.complete(run_id, ok=False, error="timeout")
            return
        time.sleep(5)
    monitor.complete(run_id, ok=True)
```

### P0: Content-addressed run IDs

**File**: `agentcom/subagent.py`

```python
import hashlib

def make_run_id(objective: str, model: str) -> str:
    """Content-addressed run ID."""
    content = f"{objective}:{model}:{time.time()}"
    h = hashlib.sha256(content.encode()).hexdigest()[:12]
    return f"sa:{h}"
```

### P0: Log every step

**File**: `agentcom/worker.py`

Add step logging in the LLM loop:
```python
# After each tool execution
with open(log_file, "a") as f:
    f.write(json.dumps({
        "turn": turn,
        "tool": tool_name,
        "args": tool_args,
        "result_ok": result.get("ok"),
        "duration_ms": duration_ms,
        "timestamp": int(time.time()),
    }) + "\n")
```

### P1: Custom prompts from main LLM

**File**: `agentcom/subagent.py`

```python
def spawn(subagent_name: str, prompt: str = "", **kwargs):
    """Spawn with custom prompt from main LLM."""
    cfg = SUBAGENTS[subagent_name]
    if prompt:
        context = prompt  # Override system prompt
    else:
        context = cfg.system_prompt
    # ... rest of spawn
```

### P1: Dashboard log viewer

**File**: `dashboard/server.py`

Add endpoint to view sub-agent logs:
```python
elif path == "/api/subagent/log":
    run_id = body.get("run_id", "")
    log_file = os.path.join(ROOT, "runs", "subagents", f"*.log")
    # Find matching log file
    for f in os.listdir(os.path.join(ROOT, "runs", "subagents")):
        if run_id in f and f.endswith(".log"):
            content = open(os.path.join(ROOT, "runs", "subagents", f)).read()
            self._json({"log": content, "lines": content.count("\n")})
            return
    self._json({"error": "log not found"}, 404)
```

---

## Test plan

### Test 1: Spawn with monitoring
```python
# Spawn sub-agent
result = spawn("wallet_hunter", extra_context="test")
assert result["ok"] is True

# Wait and check status
time.sleep(5)
status = monitor.get_status(result["run_id"])
assert status["status"] == "running"

# Check log file exists
assert os.path.exists(result["stdout_file"])
```

### Test 2: Sub-agent completion
```python
# Spawn and wait for completion
result = spawn("maintenance", extra_context="check vault status")
time.sleep(30)  # Wait for completion

# Check status
status = monitor.get_status(result["run_id"])
assert status["status"] in ("completed", "failed")

# Check results
runs = list_runs()
assert any(r["run_id"] == result["run_id"] for r in runs)
```

### Test 3: Audit logging
```python
# Spawn sub-agent
result = spawn("wallet_hunter", extra_context="test")

# Check audit log
events = audit.recent(10)
spawn_events = [e for e in events if e["action"] == "subagent_spawn"]
assert len(spawn_events) > 0
assert spawn_events[-1]["target"] == "wallet_hunter"
```

### Test 4: Timeout detection
```python
# Spawn sub-agent
result = spawn("wallet_hunter", extra_context="test")

# Wait longer than timeout
time.sleep(10)

# Check for timeouts
timeouts = monitor.check_timeouts(timeout_s=5)
# Should detect the sub-agent as timed out if it's stuck
```

### Test 5: Log content
```python
# Spawn sub-agent
result = spawn("wallet_hunter", extra_context="test")
time.sleep(10)

# Check log has content
with open(result["stdout_file"]) as f:
    content = f.read()
    assert len(content) > 0, "Log should have content"
```

---

## Work separation

**Other agent writes:**
1. Real-time log streaming in subagent.py
2. Retry + timeout in worker.py
3. Content-addressed run IDs in subagent.py
4. Step logging in worker.py
5. Custom prompts in subagent.py
6. Dashboard log viewer endpoint

**I test:**
1. Spawn + monitoring
2. Completion detection
3. Audit logging
4. Timeout detection
5. Log content verification
6. Dashboard API endpoints
7. Error handling (API failures)

---

## Success criteria

1. Every sub-agent spawn creates a unique run ID
2. Every sub-agent step is logged to its log file
3. Sub-agent status is visible in real-time
4. Sub-agent timeout kills the process
5. Sub-agent API errors retry with backoff
6. Dashboard shows sub-agent logs
7. Audit log captures all sub-agent events
8. No sub-agent hangs forever
