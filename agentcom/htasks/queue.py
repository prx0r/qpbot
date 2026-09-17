"""H-tasks — human work queue with leases and safe-default expiry.

Lifecycle: emitted → displayed → acknowledged → answered → expired.
Expiry is never approval: the task's safe_default applies instead.
Secrets never enter this queue (see vault rule in docs/HTASK_PANEL.md).
Provenance: schemas from scarce-state htask drafts; lifecycle is qpbot-new.
"""
from __future__ import annotations

import hashlib
import json
import time


def _hid(task_id: str, question: str) -> str:
    return hashlib.sha256(f"{task_id}:{question}".encode()).hexdigest()[:16]


class HTask:
    Kinds = ("digit", "confirm", "secret")

    def __init__(self, task_id: str, kind: str, question: str,
                 prediction: str = "", confidence: float = 0.0,
                 lease_s: int = 300, safe_default: str = "deny",
                 campaign: str = "", lane: str = ""):
        if kind not in self.Kinds:
            raise ValueError(f"unknown kind {kind}")
        self.task_id = task_id
        self.kind = kind
        self.question = question
        self.prediction = prediction
        self.confidence = confidence
        self.safe_default = safe_default
        self.campaign = campaign
        self.lane = lane
        self.state = "emitted"
        self.created = int(time.time())
        self.deadline = self.created + lease_s
        self.context_hash = _hid(task_id, question)
        self.answer = None

    def display(self):
        self._require("emitted")
        self.state = "displayed"
        return self.view()

    def acknowledge(self):
        self._require("displayed")
        self.state = "acknowledged"

    def answer_task(self, answer: str, prediction_before_display: str = ""):
        self._require("acknowledged", "displayed")
        if self.kind == "secret":
            raise ValueError("secrets deposit to the vault, never the queue")
        self.answer = {"value": answer,
                       "prediction_before_display": prediction_before_display,
                       "ts": int(time.time())}
        self.state = "answered"
        return self.answer

    def expire(self, now: int = 0):
        if self.state in ("answered", "expired"):
            return self.state
        if (now or int(time.time())) >= self.deadline:
            self.state = "expired"
            self.answer = {"value": self.safe_default, "expired": True,
                           "ts": int(time.time())}
        return self.state

    def view(self) -> dict:
        return {"task_id": self.task_id, "kind": self.kind,
                "question": self.question, "prediction": self.prediction,
                "confidence": self.confidence, "state": self.state,
                "context_hash": self.context_hash,
                "campaign": self.campaign, "lane": self.lane,
                "deadline": self.deadline}

    def _require(self, *states):
        if self.state not in states:
            raise ValueError(f"task {self.task_id} is {self.state}, "
                             f"need one of {states}")


class HQueue:
    """In-memory queue. Persistence is the daemon's job, not this module's."""

    def __init__(self):
        self.tasks: dict[str, HTask] = {}

    def emit(self, task: HTask) -> HTask:
        self.tasks[task.task_id] = task
        return task

    def sweep(self, now: int = 0) -> list[str]:
        expired = []
        for t in self.tasks.values():
            before = t.state
            t.expire(now)
            if before != "expired" and t.state == "expired":
                expired.append(t.task_id)
        return expired

    def active(self) -> HTask | None:
        for t in self.tasks.values():
            if t.state in ("displayed", "acknowledged"):
                return t
        return None

    def pending_count(self) -> int:
        return sum(1 for t in self.tasks.values()
                   if t.state in ("emitted", "displayed", "acknowledged"))

    def to_json(self) -> str:
        return json.dumps([t.view() for t in self.tasks.values()], indent=1)
