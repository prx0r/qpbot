"""Daemon — job queue with writer exclusivity and UNKNOWN-on-crash.

One writer per session: attach() refuses a second live writer for the same
session id (pi-acp constraint). A job whose worker dies without a verdict
is UNKNOWN with evidence preserved, never FAILED.
"""
from __future__ import annotations

import time
import traceback


class SessionRegistry:
    def __init__(self):
        self.writers: dict[str, str] = {}

    def attach(self, session_id: str, worker_id: str):
        if session_id in self.writers:
            raise ValueError(f"session {session_id} already has a writer: "
                             f"{self.writers[session_id]}")
        self.writers[session_id] = worker_id

    def detach(self, session_id: str):
        self.writers.pop(session_id, None)


class Daemon:
    def __init__(self):
        self.queue: list[dict] = []
        self.registry = SessionRegistry()
        self.journal: list[dict] = []

    def submit(self, job: dict) -> dict:
        job = {"job_id": f"job-{len(self.queue) + 1}", "state": "queued",
               **job}
        self.queue.append(job)
        return job

    def tick(self, runner=None) -> dict | None:
        """Run the next queued job once. runner(job) executes it."""
        job = next((j for j in self.queue if j["state"] == "queued"), None)
        if job is None:
            return None
        job["state"] = "running"
        try:
            result = runner(job) if runner else {"ok": True}
            job["state"] = "done"
            job["result"] = result
        except Exception as e:  # noqa: BLE001 — crash must bank, not raise
            job["state"] = "UNKNOWN"
            job["error"] = f"{type(e).__name__}: {e}"
            job["trace"] = traceback.format_exc(limit=3)
        self.journal.append({"job_id": job["job_id"], "state": job["state"],
                             "ts": int(time.time())})
        return job
