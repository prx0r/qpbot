# qpbot — Audit & Monitoring Guide

## Audit logging

Every mutation is traced to `runs/audit.jsonl`. Format:

```json
{
  "ts": 1789655065,
  "actor": "dashboard",
  "action": "api_call",
  "target": "/api/chat",
  "run_id": "",
  "result": {"tokens_in": 100, "tokens_out": 50}
}
```

## What gets logged

| Action | Actor | What |
|--------|-------|------|
| api_call | dashboard/user | Every API endpoint call |
| file_read | dashboard | Every file read |
| file_write | dashboard | Every file write |
| tool_exec | worker | Every tool execution (whale_feed, eth_check, etc.) |
| llm_call | worker | Every LLM API call |
| subagent_spawn | dashboard | Every sub-agent spawn |
| subagent_complete | system | Every sub-agent completion |
| mission_dispatch | dashboard | Every mission dispatch |
| mission_complete | system | Every mission completion |

## Querying audit logs

```python
from agentcom.audit import recent

# Last 20 events
events = recent(20)

# Filter by action
api_calls = [e for e in events if e["action"] == "api_call"]

# Filter by actor
worker_events = [e for e in events if "worker" in e["actor"]]
```

## Dashboard API

```bash
# Get last 20 audit events
curl "http://localhost:8791/api/audit?token=TOKEN"

# Get last 50
curl "http://localhost:8791/api/audit?n=50&token=TOKEN"
```

## Sub-agent monitoring

Every sub-agent run is tracked in `runs/subagents/<run_id>.status.json`:

```json
{
  "run_id": "sa-123",
  "subagent": "wallet_hunter",
  "pid": 12345,
  "status": "running",
  "started": 1789655065,
  "last_heartbeat": 1789655125,
  "output_file": "runs/subagents/wallet_hunter-sa-123.json"
}
```

## Status lifecycle

```
registered → running → completed/failed/crashed/timeout
```

## Checking for problems

```python
from agentcom.monitor import check_timeouts, check_crashes

# Find sub-agents running > 600s
timeouts = check_timeouts(timeout_s=600)

# Find sub-agents with dead processes
crashes = check_crashes()
```

## Dashboard API

```bash
# List all sub-agent statuses
curl "http://localhost:8791/api/subagent/statuses?token=TOKEN"

# Returns:
{
  "statuses": [...],
  "summary": {"total": 5, "by_status": {"running": 2, "completed": 3}}
}
```

## File locations

```
runs/
├── audit.jsonl              # Every mutation traced
├── missions.jsonl           # Mission lifecycle events
├── missions.jsonl.events    # Mission event stream
├── usage.jsonl              # LLM API usage
├── subagents/
│   ├── *.status.json        # Sub-agent status files
│   ├── *.json               # Sub-agent results
│   └── *.log                # Sub-agent stdout
└── ...
```
