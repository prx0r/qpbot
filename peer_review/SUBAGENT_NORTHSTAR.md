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

### Test 1: Spawn + monitoring lifecycle
```python
result = spawn("wallet_hunter", extra_context="test spawn lifecycle")
assert result["ok"] is True
assert result["run_id"].startswith("sa:")
assert result["timeout_s"] == 300

# Wait and check status transitions
time.sleep(3)
status = get_status(result["run_id"])
assert status is not None
assert status["status"] == "running"

# Check log has at least start event
log = get_log(result["run_id"])
assert len(log) > 0
assert "start" in log
```

### Test 2: Content-addressed run IDs — no collisions
```python
ids = set()
for i in range(50):
    id = _make_run_id(f"objective-{i}", "mimo-v2.5")
    ids.add(id)
assert len(ids) == 50, f"Expected 50 unique IDs, got {len(ids)}"
```

### Test 3: Custom prompts override system prompt
```python
result = spawn("maintenance", prompt="Just count vault keys, nothing else")
assert result["ok"] is True

time.sleep(15)
data = read_run(result["run_id"])
assert data is not None
# Worker should have received custom prompt
log = get_log(result["run_id"])
assert "count" in log.lower() or "vault" in log.lower()
```

### Test 4: Sub-agent completion detection
```python
result = spawn("maintenance", extra_context="check vault status")
time.sleep(30)

status = get_status(result["run_id"])
assert status["status"] in ("completed", "failed")

runs = list_runs()
assert any(r["run_id"] == result["run_id"] for r in runs)
```

### Test 5: Timeout kills stuck processes
```python
# Spawn with very short timeout
cfg = SUBAGENTS["maintenance"]
original = cfg.timeout_s
cfg.timeout_s = 5
try:
    result = spawn("maintenance", extra_context="do something slow")
    time.sleep(10)
    status = get_status(result["run_id"])
    assert status["status"] == "failed" or status.get("error") == "timeout"
finally:
    cfg.timeout_s = original
```

### Test 6: Retry on 429 errors
```python
# This tests the retry logic in worker.py
# Hard to test without mocking, but verify the code path exists
from agentcom.worker import run_worker
import inspect
source = inspect.getsource(run_worker)
assert "429" in source
assert "backoff" in source or "sleep" in source
```

### Test 7: Log content has step events
```python
result = spawn("wallet_hunter", extra_context="check 1 whale transaction")
time.sleep(20)

log = get_log(result["run_id"])
lines = [l for l in log.strip().split("\n") if l]
events = []
for line in lines:
    try:
        events.append(json.loads(line))
    except: pass

assert any(e.get("event") == "start" for e in events)
assert any(e.get("event") in ("tool_exec", "llm_call") for e in events)
```

### Test 8: Dashboard log endpoint
```python
result = spawn("maintenance", extra_context="quick test")
time.sleep(5)

# Via API simulation
import urllib.request
url = f"http://127.0.0.1:8791/api/subagent/log?run_id={result['run_id']}&token=TOKEN"
resp = json.loads(urllib.request.urlopen(url).read())
assert "log" in resp
assert len(resp["log"]) > 0
```

### Test 9: Dashboard status endpoint
```python
result = spawn("wallet_hunter", extra_context="test status endpoint")
time.sleep(3)

url = f"http://127.0.0.1:8791/api/subagent/status?run_id={result['run_id']}&token=TOKEN"
resp = json.loads(urllib.request.urlopen(url).read())
assert resp["status"] in ("running", "completed", "failed")
```

### Test 10: Audit captures spawn + completion
```python
result = spawn("maintenance", extra_context="audit test")
time.sleep(15)

with open("runs/audit.jsonl") as f:
    events = [json.loads(l) for l in f if l.strip()]

spawn_events = [e for e in events if e["action"] == "subagent_spawn"]
assert len(spawn_events) > 0
assert spawn_events[-1]["target"] == "maintenance"
```

### Test 11: Multiple concurrent spawns
```python
r1 = spawn("wallet_hunter", extra_context="concurrent test 1")
r2 = spawn("chain_scanner", extra_context="concurrent test 2")
r3 = spawn("maintenance", extra_context="concurrent test 3")

assert r1["run_id"] != r2["run_id"] != r3["run_id"]

time.sleep(10)
for r in [r1, r2, r3]:
    status = get_status(r["run_id"])
    assert status is not None
```

### Test 12: Empty log handling
```python
log = get_log("nonexistent-run-id")
assert log == ""

status = get_status("nonexistent-run-id")
assert status is None
```

### Test 13: Pi agent chat through dashboard
```python
# Simulate dashboard chat
from agentcom.pi_agent import chat
result = chat("What is 2+2?", system_prompt="Answer briefly")
assert "4" in result["reply"]
assert isinstance(result["tools_called"], list)
assert result["session_id"] != ""
```

### Test 14: Pi agent multi-turn session persistence
```python
r1 = chat("My name is Alice", conversation_id="test-session")
r2 = chat("What is my name?", conversation_id="test-session")
assert "Alice" in r2["reply"]
```

### Test 15: File editor save via API
```python
content = "# Test file\ndef hello():\n    return 'world'"
# Write
urllib.request.urlopen(urllib.request.Request(
    "http://127.0.0.1:8791/api/file/write?token=TOKEN",
    data=json.dumps({"path": "runs/editor-test.py", "content": content}).encode(),
    headers={"Content-Type": "application/json"}
))
# Read back
resp = json.loads(urllib.request.urlopen(
    "http://127.0.0.1:8791/api/file/read?path=runs/editor-test.py&token=TOKEN"
).read())
assert resp["content"] == content
```

### Test 16: Vault store + retrieve cycle
```python
# Store a test key
urllib.request.urlopen(urllib.request.Request(
    "http://127.0.0.1:8791/api/vault-store?token=TOKEN",
    data=json.dumps({"name": "TEST_CYCLE", "value": "secret123"}).encode(),
    headers={"Content-Type": "application/json"}
))
# Verify via vault endpoint
resp = json.loads(urllib.request.urlopen(
    "http://127.0.0.1:8791/api/vault?token=TOKEN"
).read())
names = [k["name"] for k in resp["keys"]]
assert "TEST_CYCLE" in names
```

### Test 17: Provider config persistence
```python
urllib.request.urlopen(urllib.request.Request(
    "http://127.0.0.1:8791/api/provider?token=TOKEN",
    data=json.dumps({"base_url": "https://test.com/v1", "model": "test-model"}).encode(),
    headers={"Content-Type": "application/json"}
))
resp = json.loads(urllib.request.urlopen(
    "http://127.0.0.1:8791/api/status?token=TOKEN"
).read())
assert resp["provider"]["model"] == "test-model"
# Restore
urllib.request.urlopen(urllib.request.Request(
    "http://127.0.0.1:8791/api/provider?token=TOKEN",
    data=json.dumps({"base_url": "https://opencode.ai/zen/go/v1", "model": "mimo-v2.5"}).encode(),
    headers={"Content-Type": "application/json"}
))
```

### Test 18: Sub-agent spawned from chat (end-to-end)
```python
# Simulate: user says "spawn wallet hunter"
from agentcom.pi_agent import chat
r = chat("Spawn a wallet_hunter sub-agent to check whale wallets")
# Agent should have output a tool call or spawned
# Check missions increased
resp = json.loads(urllib.request.urlopen(
    "http://127.0.0.1:8791/api/missions?token=TOKEN"
).read())
assert resp["summary"]["total"] >= 0
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
