"""Patterns — shared secret detection regexes.

Single source of truth. Every scanner, classifier, and extractor
imports from here instead of duplicating patterns.
"""
from __future__ import annotations

import re

# ── Key patterns ───────────────────────────────────────────────────────

ETH_PRIVATE_KEY = re.compile(r"(?:0x)?[0-9a-fA-F]{64}")
SOL_PRIVATE_KEY = re.compile(r"[1-9A-HJ-NP-Za-km-z]{87,88}")
MNEMONIC_12 = re.compile(
    r"(?:mnemonic|seed.?phrase|SEED_PHRASE)[\s:=]+[\"']?([a-z]+(\s+[a-z]+){11})",
    re.I,
)
MNEMONIC_24 = re.compile(
    r"(?:mnemonic|seed.?phrase|SEED_PHRASE)[\s:=]+[\"']?([a-z]+(\s+[a-z]+){23})",
    re.I,
)
ETH_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")
SOL_ADDRESS = re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}")

# Cloud / API keys
AWS_ACCESS_KEY = re.compile(r"AKIA[0-9A-Z]{16}")
AWS_SECRET_KEY = re.compile(r"(?:aws.?secret.?access.?key|AWS_SECRET_ACCESS_KEY)[\s:=]+[\"']?([A-Za-z0-9/+=]{40})")
OPENAI_KEY = re.compile(r"sk-[A-Za-z0-9]{20,}")
GH_TOKEN = re.compile(r"ghp_[A-Za-z0-9]{36}")
SLACK_TOKEN = re.compile(r"xox[bpsa]-[0-9]{10,13}-[0-9a-zA-Z-]{20,}")
GCP_KEY = re.compile(r"AIza[A-Za-z0-9_-]{35}")

# Generic secrets in config files
ENV_SECRET = re.compile(
    r"(?:PRIVATE_KEY|SECRET_KEY|API_KEY|MNEMONIC|PASSWORD|SECRET)[\s:=]+[\"']?([^\s\"']{20,})",
    re.I,
)
BASE64_KEY = re.compile(
    r"(?:PRIVATE_KEY|SIGNING_KEY|SECRET_KEY)[\s:=]+[\"']?([A-Za-z0-9+/]{40,88}={0,2})"
)
DATABASE_URL = re.compile(
    r"(?:DATABASE_URL|DB_URL)[\s:=]+[\"']?(postgres(?:ql)?://[^\s\"']{20,})",
    re.I,
)

# ── Composite patterns for different tools ─────────────────────────────

# For scanning git history / .env files
SCAN_PATTERNS = {
    "eth_private_key": ETH_PRIVATE_KEY,
    "sol_private_key": SOL_PRIVATE_KEY,
    "mnemonic_12": MNEMONIC_12,
    "mnemonic_24": MNEMONIC_24,
    "aws_access_key": AWS_ACCESS_KEY,
    "openai_key": OPENAI_KEY,
    "gh_token": GH_TOKEN,
    "slack_token": SLACK_TOKEN,
    "gcp_key": GCP_KEY,
    "env_secret": ENV_SECRET,
    "base64_key": BASE64_KEY,
    "database_url": DATABASE_URL,
}

# For drain classification (higher fidelity)
DRAIN_PATTERNS = {
    "eth_private_key": ETH_PRIVATE_KEY,
    "sol_private_key": SOL_PRIVATE_KEY,
    "mnemonic_12": MNEMONIC_12,
    "mnemonic_24": MNEMONIC_24,
}

# ── Helpers ────────────────────────────────────────────────────────────

def redact(value: str, head: int = 8, tail: int = 4) -> str:
    """Redact a secret value for safe display."""
    if len(value) <= head + tail + 4:
        return value
    return value[:head] + "..." + value[-tail:]


def extract_from_text(text: str, patterns: dict | None = None) -> list[dict]:
    """Extract all matching secrets from text. Returns list of {type, value, redacted}."""
    patterns = patterns or SCAN_PATTERNS
    found = []
    seen = set()
    for name, pat in patterns.items():
        for m in pat.finditer(text):
            val = m.group(1) if m.lastindex else m.group(0)
            if val and len(val) > 8 and val not in seen:
                seen.add(val)
                found.append({
                    "type": name,
                    "value": val,
                    "redacted": redact(val),
                })
    return found
