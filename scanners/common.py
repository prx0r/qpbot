"""Shared scanner plumbing: qpbot CLI calls + finding schema + wordlists."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

QP_BOT = os.environ.get("QP_BOT", "/home/ubuntu/qpbot")
HERE = os.path.dirname(os.path.abspath(__file__))
WORDLISTS = os.path.join(HERE, "wordlists")


def cli(*args: str) -> dict:
    """Run qpbot core.cli, parse JSON stdout. Never raises."""
    try:
        p = subprocess.run([sys.executable, "-m", "core.cli", *args],
                           capture_output=True, text=True, cwd=QP_BOT,
                           timeout=60)
        return json.loads(p.stdout) if p.stdout.strip() else {"ok": False}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def finding(scanner: str, target_id: str, kind: str, detail: str,
            confidence: float = 1.0) -> dict:
    return {"ts": int(time.time()), "scanner": scanner,
            "target_id": target_id, "kind": kind, "detail": detail,
            "confidence": confidence}


def wordlist(name: str) -> list[str]:
    p = os.path.join(WORDLISTS, name)
    if not os.path.exists(p):
        return []
    with open(p) as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]


def learn_word(name: str, value: str) -> bool:
    """Feed-out: append a learned value to a wordlist. Returns True if new."""
    value = value.strip()
    if not value or "\n" in value:
        return False
    os.makedirs(WORDLISTS, exist_ok=True)
    p = os.path.join(WORDLISTS, name)
    existing = set(wordlist(name))
    if value in existing:
        return False
    with open(p, "a") as f:
        f.write(value + "\n")
    return True


def targets() -> list[str]:
    d = cli("list-targets")
    if isinstance(d, dict):
        return [t.get("target_id", t) if isinstance(t, dict) else t
                for t in d.get("targets", [])]
    if isinstance(d, list):
        return [t.get("target_id", t) if isinstance(t, dict) else t
                for t in d]
    return ["weak-creds-01", "traversal-01", "sqli-sim-01"]
