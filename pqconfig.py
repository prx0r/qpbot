"""Config — single source of truth for all pq settings.

Reads pq.json from the repo root. Every script imports from here
instead of hardcoding paths, models, or env vars.
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
_CONFIG: dict | None = None


def _load() -> dict:
    global _CONFIG
    if _CONFIG is None:
        path = os.path.join(ROOT, "pq.json")
        if os.path.exists(path):
            with open(path) as f:
                _CONFIG = json.load(f)
        else:
            _CONFIG = {}
    return _CONFIG


def get(dotpath: str, default=None):
    """Get a config value by dot path. E.g. get('llm.model')"""
    cfg = _load()
    parts = dotpath.split(".")
    node = cfg
    for p in parts:
        if isinstance(node, dict) and p in node:
            node = node[p]
        else:
            return default
    return node


def vault_path() -> str:
    return os.path.expanduser(get("vault.path", "~/.qpbot/vault.json"))


def vault_key_path() -> str:
    return os.path.expanduser(get("vault.key_path", "~/.qpbot/vault.key"))


def llm_model() -> str:
    return os.environ.get("PQ_MODEL", get("llm.model", "muse-spark-1.3-contributor"))


def llm_base_url() -> str:
    return get("llm.base_url", "https://opencode.ai/zen/go/v1")


def llm_api_key() -> str:
    """Get API key from env var named in config."""
    env_var = get("llm.api_key_env", "PQ_API_KEY")
    return os.environ.get(env_var, "")


def qp_bot_path() -> str:
    return os.environ.get("QP_BOT", get("arena.qp_bot", "/home/ubuntu/qpbot"))


def arena_pack() -> str:
    return get("arena.pack", "demo")


def spend_cap_tokens() -> int:
    return int(os.environ.get("PQ_SPEND_CAP_TOKENS",
                              get("spend.cap_tokens", 0)))


def spend_cap_minor() -> int:
    return int(os.environ.get("PQ_SPEND_CAP_MINOR",
                              get("spend.cap_minor", 0)))


def dashboard_port() -> int:
    return int(os.environ.get("DASH_PORT", get("dashboard.port", 8791)))


def dashboard_host() -> str:
    return get("dashboard.host", "127.0.0.1")


def gh_token() -> str:
    env_var = get("scanners.gh_token_env", "GH_TOKEN")
    return os.environ.get(env_var, "")


def runs_dir() -> str:
    d = os.path.join(ROOT, "runs")
    os.makedirs(d, exist_ok=True)
    return d


def memory_dir() -> str:
    return os.path.join(ROOT, "memory")


def summary() -> dict:
    """Human-readable config summary."""
    return {
        "vault": vault_path(),
        "model": llm_model(),
        "base_url": llm_base_url(),
        "api_key_set": bool(llm_api_key()),
        "qp_bot": qp_bot_path(),
        "pack": arena_pack(),
        "spend_cap_tokens": spend_cap_tokens(),
        "spend_cap_minor": spend_cap_minor(),
        "dashboard": f"{dashboard_host()}:{dashboard_port()}",
    }
