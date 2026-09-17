"""Missions — dispatch sub-agents on objectives, track results, report back.

The main agent (dashboard chat) dispatches missions. Each mission is a
harness run with a specific objective: find whale wallets, scan a repo,
classify secrets, etc. Results log to runs/ and feed back to the main
agent via the memory bank.

Architecture:
  main agent (you) -> dispatch mission -> daemon queues job
       -> worker runs harness with objective -> logs to runs/
       -> results available to main agent via /api/missions
       -> memory bank updated with findings
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MISSIONS_FILE = os.path.join(ROOT, "runs", "missions.jsonl")


@dataclass
class Mission:
    id: str
    objective: str
    tools: list[str] = field(default_factory=list)
    status: str = "queued"  # queued -> running -> done -> failed
    created: float = 0.0
    started: float = 0.0
    finished: float = 0.0
    result: dict = field(default_factory=dict)
    findings: list[dict] = field(default_factory=list)
    run_id: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Mission:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


class MissionControl:
    """Manages the mission queue: dispatch, track, collect."""

    def __init__(self, path: str = MISSIONS_FILE):
        self.path = path
        self.missions: dict[str, Mission] = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        m = Mission.from_dict(json.loads(line))
                        self.missions[m.id] = m
                    except Exception:
                        pass

    def _save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            for m in self.missions.values():
                f.write(json.dumps(m.to_dict()) + "\n")
        os.replace(tmp, self.path)

    def dispatch(self, objective: str, tools: list[str] | None = None,
                 mission_id: str = "") -> Mission:
        """Create a new mission. Returns the mission object."""
        if not mission_id:
            mission_id = f"m-{int(time.time())}-{len(self.missions)}"
        m = Mission(
            id=mission_id,
            objective=objective,
            tools=tools or [],
            status="queued",
            created=time.time(),
        )
        self.missions[mission_id] = m
        self._save()
        self._log_event("dispatched", m)
        return m

    def start(self, mission_id: str, run_id: str = "") -> Mission:
        """Mark a mission as running."""
        m = self.missions[mission_id]
        m.status = "running"
        m.started = time.time()
        m.run_id = run_id
        self._save()
        self._log_event("started", m)
        return m

    def complete(self, mission_id: str, result: dict,
                 findings: list[dict] | None = None,
                 tokens_in: int = 0, tokens_out: int = 0) -> Mission:
        """Mark a mission as done with results."""
        m = self.missions[mission_id]
        m.status = "done"
        m.finished = time.time()
        m.result = result
        m.findings = findings or []
        m.tokens_in = tokens_in
        m.tokens_out = tokens_out
        self._save()
        self._log_event("completed", m)
        return m

    def fail(self, mission_id: str, error: str) -> Mission:
        """Mark a mission as failed."""
        m = self.missions[mission_id]
        m.status = "failed"
        m.finished = time.time()
        m.error = error
        self._save()
        self._log_event("failed", m)
        return m

    def get(self, mission_id: str) -> Mission | None:
        return self.missions.get(mission_id)

    def list_missions(self, status: str = "") -> list[dict]:
        missions = list(self.missions.values())
        if status:
            missions = [m for m in missions if m.status == status]
        return [m.to_dict() for m in sorted(missions,
                                             key=lambda x: x.created, reverse=True)]

    def summary(self) -> dict:
        by_status = {}
        for m in self.missions.values():
            by_status[m.status] = by_status.get(m.status, 0) + 1
        total_findings = sum(len(m.findings) for m in self.missions.values())
        return {
            "total": len(self.missions),
            "by_status": by_status,
            "total_findings": total_findings,
        }

    def _log_event(self, event: str, m: Mission):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        entry = {"ts": int(time.time()), "event": event,
                 "mission_id": m.id, "objective": m.objective[:100],
                 "status": m.status}
        with open(self.path + ".events", "a") as f:
            f.write(json.dumps(entry) + "\n")
