"""Audit log — every mutation traced.

Every state change, API call, file write, and tool execution logs here.
Format: JSONL with timestamp, actor, action, target, result, run_id.
"""
from __future__ import annotations

import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT_FILE = os.path.join(ROOT, "runs", "audit.jsonl")


def log(actor: str, action: str, target: str = "", result: dict = None,
        run_id: str = "", **extra):
    """Log an audit event. Every mutation goes through this."""
    os.makedirs(os.path.dirname(AUDIT_FILE) or ".", exist_ok=True)
    entry = {
        "ts": int(time.time()),
        "actor": actor,
        "action": action,
        "target": target,
        "run_id": run_id,
    }
    if result:
        entry["result"] = result
    if extra:
        entry.update(extra)
    with open(AUDIT_FILE, "a") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def log_file_write(path: str, actor: str = "dashboard"):
    """Log a file write."""
    log(actor, "file_write", target=path)


def log_file_read(path: str, actor: str = "dashboard"):
    """Log a file read."""
    log(actor, "file_read", target=path)


def log_api_call(endpoint: str, actor: str = "user"):
    """Log an API call."""
    log(actor, "api_call", endpoint)


def log_tool_exec(tool: str, args: list, actor: str = "worker",
                  result: dict = None, **extra):
    """Log a tool execution."""
    log(actor, "tool_exec", target=tool,
        result={"args": args, **(result or {})}, **extra)


def log_llm_call(model: str, tokens_in: int, tokens_out: int,
                 actor: str = "worker", **extra):
    """Log an LLM API call."""
    log(actor, "llm_call", target=model,
        result={"tokens_in": tokens_in, "tokens_out": tokens_out}, **extra)


def log_subagent_spawn(subagent: str, pid: int, run_id: str):
    """Log a sub-agent spawn."""
    log("dashboard", "subagent_spawn", target=subagent,
        result={"pid": pid}, run_id=run_id)


def log_subagent_complete(subagent: str, run_id: str, ok: bool, findings: int):
    """Log a sub-agent completion."""
    log("system", "subagent_complete", target=subagent,
        result={"ok": ok, "findings": findings}, run_id=run_id)


def log_mission_dispatch(mission_id: str, objective: str):
    """Log a mission dispatch."""
    log("dashboard", "mission_dispatch", target=mission_id,
        result={"objective": objective[:200]})


def log_mission_complete(mission_id: str, ok: bool, findings: int):
    """Log a mission completion."""
    log("system", "mission_complete", target=mission_id,
        result={"ok": ok, "findings": findings})


def recent(n: int = 20) -> list[dict]:
    """Read the last n audit events."""
    if not os.path.exists(AUDIT_FILE):
        return []
    with open(AUDIT_FILE) as f:
        lines = f.readlines()
    events = []
    for line in lines[-n:]:
        line = line.strip()
        if line:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events
