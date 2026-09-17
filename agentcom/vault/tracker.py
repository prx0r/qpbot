"""Usage tracker — deterministic per-call logging for any API provider.

Wraps vault.record_usage. Call after every API response. Knows OpenCode Go
pricing by model. Logs to vault audit + an append-only JSONL for dashboards.
"""
from __future__ import annotations

import json
import os
import time

# OpenCode Go pricing per 1M tokens (from docs, 2026-09-17)
PRICING = {
    "mimo-v2.5": {"input": 0.14, "output": 0.28, "monthly_cap_minor": 6000},
    "mimo-v2.5-pro": {"input": 0.435, "output": 0.87, "monthly_cap_minor": 1500},
    "deepseek-v4-flash": {"input": 0.15, "output": 0.60, "monthly_cap_minor": 3000},
    "deepseek-v4-pro": {"input": 0.435, "output": 0.87, "monthly_cap_minor": 1500},
    "glm-5.3-flash": {"input": 0.15, "output": 0.50, "monthly_cap_minor": 6000},
    "qwen3.7-plus": {"input": 0.40, "output": 1.60, "monthly_cap_minor": 6000},
    "kimi-k2.6": {"input": 0.95, "output": 4.00, "monthly_cap_minor": 6000},
    "hy3": {"input": 0.14, "output": 0.58, "monthly_cap_minor": 6000},
}

# Rate limits from OpenCode Go docs
RATE_LIMITS = {
    "mimo-v2.5": {"per_minute": 600, "per_day": 5000, "monthly_cap": 150400},
    "mimo-v2.5-pro": {"per_minute": 65, "per_day": 500, "monthly_cap": 16300},
    "deepseek-v4-flash": {"per_minute": 630, "per_day": 5000, "monthly_cap": 65000},
    "glm-5.3-flash": {"per_minute": 126, "per_day": 1000, "monthly_cap": 31580},
}


def cost_minor(model: str, tokens_in: int, tokens_out: int) -> int:
    p = PRICING.get(model, {})
    if not p:
        return 0
    return int(tokens_in / 1_000_000 * p["input"] * 100 +
               tokens_out / 1_000_000 * p["output"] * 100)


def track(vault, name: str, response: dict, log_path: str = "") -> dict:
    """Extract usage from an OpenAI-compatible response and record it."""
    usage = response.get("usage", {})
    tokens_in = usage.get("prompt_tokens", 0)
    tokens_out = usage.get("completion_tokens", 0)
    model = response.get("model", "")
    c = cost_minor(model, tokens_in, tokens_out)
    vault.record_usage(name, tokens_in=tokens_in, tokens_out=tokens_out,
                       cost_minor=c)
    entry = {"ts": int(time.time()), "name": name, "model": model,
             "tokens_in": tokens_in, "tokens_out": tokens_out,
             "cost_minor": c, "id": response.get("id", "")}
    if log_path:
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    return entry
