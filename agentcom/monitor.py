"""Sub-agent monitor — track process status, heartbeats, timeouts.

Every sub-agent writes a status file. The monitor checks for crashes
and timeouts. Status files live in runs/subagents/.
"""
from __future__ import annotations

import json
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS_DIR = os.path.join(ROOT, "runs", "subagents")


def _status_path(run_id: str) -> str:
    return os.path.join(STATUS_DIR, f"{run_id}.status.json")


def register(run_id: str, subagent: str, pid: int, output_file: str):
    """Register a new sub-agent run."""
    os.makedirs(STATUS_DIR, exist_ok=True)
    status = {
        "run_id": run_id,
        "subagent": subagent,
        "pid": pid,
        "status": "running",
        "started": int(time.time()),
        "last_heartbeat": int(time.time()),
        "output_file": output_file,
    }
    with open(_status_path(run_id), "w") as f:
        json.dump(status, f, indent=1)


def heartbeat(run_id: str):
    """Update heartbeat timestamp."""
    path = _status_path(run_id)
    if not os.path.exists(path):
        return
    with open(path) as f:
        status = json.load(f)
    status["last_heartbeat"] = int(time.time())
    with open(path, "w") as f:
        json.dump(status, f, indent=1)


def complete(run_id: str, ok: bool, findings: int = 0, error: str = ""):
    """Mark a sub-agent run as complete."""
    path = _status_path(run_id)
    if not os.path.exists(path):
        return
    with open(path) as f:
        status = json.load(f)
    status["status"] = "completed" if ok else "failed"
    status["finished"] = int(time.time())
    status["findings"] = findings
    if error:
        status["error"] = error
    with open(path, "w") as f:
        json.dump(status, f, indent=1)


def get_status(run_id: str) -> dict | None:
    """Get status of a sub-agent run."""
    path = _status_path(run_id)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def list_statuses() -> list[dict]:
    """List all sub-agent statuses."""
    if not os.path.exists(STATUS_DIR):
        return []
    statuses = []
    for f in sorted(os.listdir(STATUS_DIR)):
        if f.endswith(".status.json"):
            try:
                with open(os.path.join(STATUS_DIR, f)) as fh:
                    statuses.append(json.load(fh))
            except Exception:
                pass
    return statuses


def check_timeouts(timeout_s: int = 600) -> list[dict]:
    """Check for timed-out sub-agents. Returns list of timed-out runs."""
    now = int(time.time())
    timeouts = []
    for status in list_statuses():
        if status["status"] == "running":
            if now - status.get("last_heartbeat", status["started"]) > timeout_s:
                status["status"] = "timeout"
                status["finished"] = now
                path = _status_path(status["run_id"])
                with open(path, "w") as f:
                    json.dump(status, f, indent=1)
                timeouts.append(status)
    return timeouts


def check_crashes() -> list[dict]:
    """Check for crashed sub-agents (process no longer running)."""
    import subprocess
    crashes = []
    for status in list_statuses():
        if status["status"] == "running":
            pid = status["pid"]
            try:
                # Check if process exists
                os.kill(pid, 0)
            except OSError:
                status["status"] = "crashed"
                status["finished"] = int(time.time())
                path = _status_path(status["run_id"])
                with open(path, "w") as f:
                    json.dump(status, f, indent=1)
                crashes.append(status)
    return crashes


def summary() -> dict:
    """Summary of all sub-agent runs."""
    statuses = list_statuses()
    by_status = {}
    for s in statuses:
        st = s["status"]
        by_status[st] = by_status.get(st, 0) + 1
    return {
        "total": len(statuses),
        "by_status": by_status,
    }
