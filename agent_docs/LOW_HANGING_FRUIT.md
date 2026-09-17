# qpbot — Low-Hanging Fruit

## Quick wins (do these first)

### 1. Add retry to LLM calls
```python
# In worker.py and dashboard/server.py
@retry(max_attempts=3, backoff=2.0)
def call_llm(messages, model):
    ...
```

### 2. Add rate limiting to dashboard
```python
# Simple token bucket
rate_limit = {"window_s": 60, "max_requests": 30}
```

### 3. Add file write permissions
```python
# In dashboard, allow only specific paths
ALLOWED_WRITE_PATHS = ["runs/", "memory/", "configs/"]
```

### 4. Add mission timeout
```python
# In missions.py
def check_timeouts(self, timeout_s=3600):
    for m in self.missions.values():
        if m.status == "running" and time.time() - m.started > timeout_s:
            self.fail(m.id, "timeout")
```

### 5. Add sub-agent retry
```python
# In subagent.py
def spawn_with_retry(name, max_retries=2):
    for i in range(max_retries):
        result = spawn(name)
        if result["ok"]:
            return result
    return result
```

## Medium effort (do next)

### 6. Add session persistence
```python
# Save/restore HISTORY
def save_history():
    json.dump(HISTORY, open("runs/history.json", "w"))

def load_history():
    global HISTORY
    if os.path.exists("runs/history.json"):
        HISTORY = json.load(open("runs/history.json"))
```

### 7. Add workflow error recovery
```python
# In workflows.py
# Instead of failing on first error, skip and continue
for step in wf["steps"]:
    try:
        output = self.execute(step.tool, args)
    except Exception as e:
        result.steps.append(StepResult(step=step.name, tool=step.tool,
                                       output={"error": str(e)}, valid=False))
        continue  # skip failed step
```

### 8. Add concurrency locks
```python
# Protect shared state
import threading
HISTORY_LOCK = threading.Lock()
MISSIONS_LOCK = threading.Lock()

# Use in dashboard
with HISTORY_LOCK:
    HISTORY.append(message)
```

### 9. Add health check endpoint
```python
# In dashboard
elif path == "/api/health":
    self._json({
        "status": "ok",
        "vault": bool(vault.find(kind="llm-inference")),
        "audit": os.path.exists("runs/audit.jsonl"),
        "uptime": time.time() - START_TIME,
    })
```

### 10. Add sub-agent resource limits
```python
# In subagent.py
SubAgentConfig(
    ...
    max_memory_mb=512,
    max_cpu_percent=50,
)
```

## Future work

### 11. Wire Pi agent as main agent
Replace the simple LLM loop with Pi's agent framework:
- Multi-turn conversation
- Tool calling with validation
- Session persistence
- Streaming responses

### 12. Add QP proofs to workflows
Each workflow step produces a receipt:
```python
step_result.receipt = transition(state, claim, evidence, gates, run={...})
```

### 13. Add tournament for processor selection
Run 5 processor variants, select winner by cost/quality.

### 14. Add seesaw for constraint tracking
Track which constraints are binding, detect migration.

### 15. Add killfeed for trade monitoring
Monitor known trades, detect state changes.
