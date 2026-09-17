"""Circuit breaker — three-state, RecordNeutral for 429s.

Ported from VoidLLM internal/circuitbreaker/breaker.go. States:
  CLOSED → OPEN → HALF_OPEN → CLOSED (success) or OPEN (failure)
429s are RecordNeutral: neither success nor failure, preserves state.
"""
from __future__ import annotations

import threading
import time


class CircuitBreaker:
    CLOSED, OPEN, HALF_OPEN = "closed", "open", "half_open"

    def __init__(self, threshold: int = 5, timeout_s: int = 60,
                 half_open_max: int = 3):
        self.threshold = threshold
        self.timeout_s = timeout_s
        self.half_open_max = half_open_max
        self.state = self.CLOSED
        self._failures = 0
        self._half_open_successes = 0
        self._opened_at = 0.0
        self._lock = threading.Lock()

    def allow(self) -> bool:
        with self._lock:
            if self.state == self.CLOSED:
                return True
            if self.state == self.OPEN:
                if time.time() - self._opened_at >= self.timeout_s:
                    self.state = self.HALF_OPEN
                    self._half_open_successes = 0
                    return True
                return False
            if self.state == self.HALF_OPEN:
                return True  # allow probe, count below max
            return False

    def record_success(self):
        with self._lock:
            if self.state == self.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self.half_open_max:
                    self.state = self.CLOSED
                    self._failures = 0
            elif self.state == self.CLOSED:
                self._failures = 0

    def record_failure(self):
        with self._lock:
            if self.state == self.HALF_OPEN:
                self.state = self.OPEN
                self._opened_at = time.time()
            elif self.state == self.CLOSED:
                self._failures += 1
                if self._failures >= self.threshold:
                    self.state = self.OPEN
                    self._opened_at = time.time()

    def record_neutral(self):
        """429 — neither success nor failure. Preserve current state."""
        pass

    def view(self) -> dict:
        return {"state": self.state, "failures": self._failures}
