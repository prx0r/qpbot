"""Rate limiter — fixed-window counters, three-tier most-restrictive-wins.

Ported from VoidLLM internal/ratelimit/rate_limiter.go. Python stdlib only.
Three scopes: key → team → org. All must pass; tightest limit wins.
"""
from __future__ import annotations

import threading
import time


class _Counter:
    __slots__ = ("count", "window_start", "window_s", "lock")

    def __init__(self, window_s: int):
        self.count = 0
        self.window_start = _now_window(window_s)
        self.window_s = window_s
        self.lock = threading.Lock()

    def increment(self) -> tuple[int, int]:
        """Returns (current_count, remaining_ms_in_window)."""
        now = _now_window(self.window_s)
        with self.lock:
            if now != self.window_start:
                self.window_start = now
                self.count = 0
            self.count += 1
            remaining_ms = (self.window_s - (time.time() % self.window_s)) * 1000
            return self.count, int(remaining_ms)


def _now_window(window_s: int) -> int:
    return int(time.time() // window_s)


class RateLimit:
    def __init__(self, per_minute: int = 0, per_day: int = 0,
                 monthly_token_cap: int = 0, daily_token_cap: int = 0):
        self.per_minute = per_minute
        self.per_day = per_day
        self.monthly_token_cap = monthly_token_cap
        self.daily_token_cap = daily_token_cap


class RateLimiter:
    """Three-tier rate limiter. Check key, team, org. All must pass."""

    def __init__(self):
        self._minute: dict[str, _Counter] = {}
        self._day: dict[str, _Counter] = {}
        self._lock = threading.Lock()

    def _get(self, store: dict, key: str, window_s: int) -> _Counter:
        if key not in store:
            with self._lock:
                if key not in store:
                    store[key] = _Counter(window_s)
        return store[key]

    def check(self, scopes: list[tuple[str, RateLimit]]) -> dict:
        """Check all scopes. Returns {ok, blocked_scope, retry_after_ms, limits}."""
        worst = {"ok": True, "retry_after_ms": 0, "blocked_scope": "",
                 "remaining_minute": 999999, "remaining_day": 999999}
        for scope_name, limits in scopes:
            if limits.per_minute:
                c = self._get(self._minute, f"{scope_name}:min", 60)
                count, remaining = c.increment()
                if count > limits.per_minute:
                    return {"ok": False, "blocked_scope": scope_name,
                            "retry_after_ms": remaining,
                            "reason": f"per_minute {count}/{limits.per_minute}"}
                worst["remaining_minute"] = min(worst["remaining_minute"],
                                                limits.per_minute - count)
            if limits.per_day:
                c = self._get(self._day, f"{scope_name}:day", 86400)
                count, remaining = c.increment()
                if count > limits.per_day:
                    return {"ok": False, "blocked_scope": scope_name,
                            "retry_after_ms": remaining,
                            "reason": f"per_day {count}/{limits.per_day}"}
                worst["remaining_day"] = min(worst["remaining_day"],
                                             limits.per_day - count)
        return worst
