"""Async usage logger — buffered, drop-on-full, batch flush.

Ported from VoidLLM internal/usage/logger.go. Non-blocking Log() with
channel-sized buffer. Background thread flushes batches to vault + JSONL.
Drop-on-full prevents backpressure from blocking the hot path.
"""
from __future__ import annotations

import json
import os
import queue
import threading
import time


class UsageLogger:
    def __init__(self, vault=None, log_path: str = "",
                 buffer_size: int = 1000, flush_interval_s: float = 5.0,
                 drop_on_full: bool = True):
        self.vault = vault
        self.log_path = log_path
        self.buffer: queue.Queue = queue.Queue(maxsize=buffer_size)
        self.flush_interval_s = flush_interval_s
        self.drop_on_full = drop_on_full
        self._running = True
        self._thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._thread.start()

    def log(self, name: str, model: str, tokens_in: int = 0,
            tokens_out: int = 0, cost_minor: int = 0,
            duration_ms: int = 0, status_code: int = 200):
        """Non-blocking. Drops event if buffer full and drop_on_full=True."""
        event = {"ts": int(time.time()), "name": name, "model": model,
                 "tokens_in": tokens_in, "tokens_out": tokens_out,
                 "cost_minor": cost_minor, "duration_ms": duration_ms,
                 "status_code": status_code}
        try:
            self.buffer.put_nowait(event)
        except queue.Full:
            if not self.drop_on_full:
                raise

    def _flush_loop(self):
        while self._running:
            time.sleep(self.flush_interval_s)
            self._flush()

    def _flush(self):
        batch = []
        while not self.buffer.empty():
            try:
                batch.append(self.buffer.get_nowait())
            except queue.Empty:
                break
        if not batch:
            return
        if self.vault:
            for e in batch:
                self.vault.record_usage(e["name"], tokens_in=e["tokens_in"],
                                        tokens_out=e["tokens_out"],
                                        cost_minor=e["cost_minor"])
        if self.log_path:
            os.makedirs(os.path.dirname(self.log_path) or ".", exist_ok=True)
            with open(self.log_path, "a") as f:
                for e in batch:
                    f.write(json.dumps(e) + "\n")

    def shutdown(self):
        self._running = False
        self._flush()
